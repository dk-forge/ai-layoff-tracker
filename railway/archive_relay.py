"""Save-Page-Now from an address the Internet Archive will answer.

archive_backfill.py must run on the one VPS the host whitelists (its candidate
list is a keyed route, and the host challenges every other datacenter). From
that VPS web.archive.org throttled 80 of 80 captures on every run from
2026-09-16; from a hosted runner the week before it throttled 0 to 4 of 80.
The backfill is slow BY DESIGN and nothing here makes it faster: the same
SPN_MAX, the same gap, the same triple back-off on a 429. Only the address the
captures leave from changes.

Three stages, two files:

  plan     (VPS, keyed)     archive_backfill.py with ARCHIVE_SPN_HANDOFF_FILE
                            set writes the misses it would have captured.
  capture  (hosted, NO      `python archive_relay.py capture PLAN RESULTS`
            secret at all)  reads PLAN, calls Save Page Now, writes RESULTS.
  post     (VPS, keyed)     `python archive_relay.py post PLAN RESULTS`
                            records the outcome and writes the terminal note.

THE HOSTED STAGE IS NOT TRUSTED. `post` reads the plan the VPS wrote itself,
records ONLY urls that are in it, and accepts a permalink only when it is an
https://web.archive.org/web/ address. Anything else, and any planned URL the
capture stage never reported (it failed, timed out, or never ran), is recorded
`pending`, which is true: the plan stage re-checked Wayback for it this run.
So a dead capture job costs a day of captures and nothing else.
"""
import json
import os
import sys
import time

VERSION = 1
PERMALINK_PREFIX = "https://web.archive.org/web/"
#: The capture stage stops itself before its runner does. 80 captures at a 90s
#: worst case plus an 18s back-off is over two hours; the ordinary case is a
#: few minutes. What is not reached is recorded pending and retried tomorrow.
CAPTURE_DEADLINE_SECONDS = max(60, min(5400, int(
    os.environ.get("ARCHIVE_CAPTURE_DEADLINE_SECONDS") or "5400")))
POST_CHUNK = 25


def write_plan(path, urls):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"v": VERSION, "urls": list(urls)}, fh)
    print(f"archive relay: {len(urls)} URL(s) planned for capture -> {path}")


def read_plan(path):
    """The planned URLs, or [] when there is no readable plan. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("v") == VERSION and isinstance(doc.get("urls"), list):
            return [u for u in doc["urls"] if isinstance(u, str)]
    except (OSError, ValueError, AttributeError):
        pass
    return []


def capture(plan_path, results_path, *, save=None, sleep=time.sleep, clock=time.monotonic):
    import archive_backfill as ab
    import requests
    save = save or ab.save_page_now
    session = requests.Session()
    urls = read_plan(plan_path)[: ab.SPN_MAX]   # the budget is the budget
    started = clock()
    results, throttled = [], 0
    for url in urls:
        if clock() - started >= CAPTURE_DEADLINE_SECONDS:
            print(f"capture deadline reached after {len(results)} URL(s)")
            break
        spn = save(url, session)
        if spn == ab.RATE_LIMITED:
            throttled += 1
            sleep(ab.SPN_GAP_SECONDS * 3)
        else:
            sleep(ab.SPN_GAP_SECONDS)
        status, permalink = ab.classify_outcome(None, spn)
        results.append({"url": url, "archived_url": permalink, "status": status,
                        "throttled": spn == ab.RATE_LIMITED})
        print(f"  [{status}] capture {len(results)}/{len(urls)}"
              + (" (throttled)" if spn == ab.RATE_LIMITED else ""))
    with open(results_path, "w", encoding="utf-8") as fh:
        json.dump({"v": VERSION, "results": results}, fh)
    print(f"archive relay: {sum(r['status'] == 'archived' for r in results)} captured, "
          f"{throttled} throttled, of {len(urls)} planned")
    return 0


def settle(planned, results_doc):
    """(records, captured, throttled, unreported) for the post stage. Pure."""
    by_url = {}
    rows = results_doc.get("results") if isinstance(results_doc, dict) else None
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, dict) and isinstance(row.get("url"), str):
            by_url.setdefault(row["url"], row)
    records, captured, throttled, unreported = [], 0, 0, 0
    for url in planned:
        row = by_url.get(url)
        link = (row or {}).get("archived_url") or ""
        if row is None:
            unreported += 1
        elif row.get("throttled"):
            throttled += 1
        if (row and row.get("status") == "archived" and isinstance(link, str)
                and link.startswith(PERMALINK_PREFIX)):
            captured += 1
            records.append({"url": url, "archived_url": link, "status": "archived"})
        else:
            records.append({"url": url, "archived_url": "", "status": "pending"})
    return records, captured, throttled, unreported


def post(plan_path, results_path):
    import archive_backfill as ab
    from source_health import report_source_health
    planned = read_plan(plan_path)
    if not planned:
        print("archive relay: nothing was planned; the plan stage already closed this run")
        return 0
    try:
        with open(results_path, encoding="utf-8") as fh:
            results_doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"::warning::no readable capture results ({exc}); recording every "
              f"planned URL pending, which is what the plan stage observed")
        results_doc = {}
    records, captured, throttled, unreported = settle(planned, results_doc)
    for i in range(0, len(records), POST_CHUNK):
        ab.post_records(records[i:i + POST_CHUNK])   # raises: loud, by design
    attempted = len(planned) - unreported
    detail = (f"{captured} archived by capture / {len(planned) - captured} still pending "
              f"({attempted} Save-Page-Now captures from the capture job, {throttled} "
              f"throttled, {unreported} not reached)")
    print(detail)
    # Same rule as archive_backfill: nothing captured because EVERYTHING that
    # was attempted was throttled is degraded, and so is a capture job that
    # reported nothing at all. Both retry tomorrow; neither is a failure.
    all_throttled = attempted > 0 and captured == 0 and throttled == attempted
    status = "degraded" if (all_throttled or attempted == 0) else "ok"
    if not report_source_health("archive_backfill", status, captured, detail):
        print("::warning::capture outcome recorded but the health-ledger write failed")
    return 0


def main(argv):
    if len(argv) == 4 and argv[1] == "capture":
        return capture(argv[2], argv[3])
    if len(argv) == 4 and argv[1] == "post":
        return post(argv[2], argv[3])
    print("usage: archive_relay.py capture|post PLAN RESULTS")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
