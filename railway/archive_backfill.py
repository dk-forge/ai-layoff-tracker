"""Give every tracker row a permanent Internet Archive (Wayback) copy of its source.

Why: each row cites an official source link (WARN notice / list / FY PDF, SEC
filing, or news URL). Sources rot — states rotate WARN files, outlets unpublish,
PDFs 404. A dead citation weakens the record. This job captures a permanent,
neutral, third-party snapshot for EVERY distinct source URL (WARN + news + SEC +
ERM), so the tracker can show an "Archived copy (Wayback Machine)" link beside
the official one on every row.

Relationship to archive_sources.py: that job snapshots the ~50 WARN SOURCE FILES
(state registries + CA PDFs + the rolling xlsx) on a schedule. This job covers
EVERY per-row source URL of every type AND stores the resulting snapshot so the
API can serve it. They are complementary; the WARN files this one requests will
usually already be in Wayback (found free via the availability API) thanks to
archive_sources.py, so this job mostly spends its Save-Page-Now budget on the
news/SEC/ERM long tail.

How it stays correct and cheap:
- The server computes the gap (distinct source URLs with no snapshot yet) via
  /archive-candidates, so this job is naturally RESUMABLE — a URL drops out once
  it is 'archived' or 'unavailable', and a brand-new row's URL appears here
  automatically until captured. Running daily guarantees forward coverage with
  NO change to the ingest write path.
- Dedup is free: the store is keyed by md5(source_url), so the thousands of WARN
  rows that share one state file resolve to ONE snapshot.
- Free first: check the Wayback availability API (fast, no save) before spending
  a Save-Page-Now capture. Only URLs with no existing snapshot cost a save.
- Rate-limited: Save Page Now is throttled for anonymous callers, so captures
  are spaced with a polite gap and backed off on HTTP 429. A bounded number of
  saves per run keeps this well inside Wayback's limits.
- Honest about failure: a URL that cannot be archived is recorded 'pending' and
  retried on a later run; after ALT_ARCHIVE_MAX_ATTEMPTS rounds the server
  records it 'unavailable' (dead / bot-walled) so it is reported, not faked, and
  not retried forever.
- Fail-open: archiving never touches or blocks an ingest. Wayback being down
  means everything stays 'pending' and is retried; nothing raises per URL.

A run works in two passes so links appear FAST regardless of ordering: first a
free availability sweep over ALL candidates (lands the bulk of links, since most
source URLs are already in Wayback), then the bounded, rate-limited Save-Page-Now
captures for the misses. Records are flushed to the server every FLUSH_EVERY URLs
so coverage climbs during the run and a killed run never loses everything.

Env: WP_SITE_URL, WP_API_KEY.
Optional: ARCHIVE_BACKFILL_LIMIT (candidate URLs/run, default 1200),
ARCHIVE_FLUSH_EVERY (post to server every N URLs, default 25),
ARCHIVE_SPN_MAX (max Save-Page-Now captures/run, default 60),
ARCHIVE_SPN_GAP_SECONDS (gap between captures, default 6),
ARCHIVE_BACKFILL_DEADLINE_SECONDS (default 1500, stops safely between URLs),
ARCHIVE_BACKFILL_DRY_RUN=1 (check + print, no saves, no writes).
"""
import os
import sys
import time

import requests

from source_health import report_source_health

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")

AVAILABILITY = "https://archive.org/wayback/available"
SAVE = "https://web.archive.org/save/"

LIMIT = max(1, min(4000, int(os.environ.get("ARCHIVE_BACKFILL_LIMIT", "1200"))))
# Post captured records to the server every N URLs so a run's progress is
# durable and coverage climbs DURING the run, not only at its end.
FLUSH_EVERY = max(5, int(os.environ.get("ARCHIVE_FLUSH_EVERY", "25")))
SPN_MAX = max(0, int(os.environ.get("ARCHIVE_SPN_MAX", "60")))
SPN_GAP_SECONDS = max(1, int(os.environ.get("ARCHIVE_SPN_GAP_SECONDS", "6")))
# CAP RAISED 3000 -> 6600 on 2026-08-06, because the old cap silently clamped
# the workflow and made ARCHIVE_BACKFILL_LIMIT a number that never happened.
# MEASURED (run 30883391601, 2026-08-04): 1,231 URLs in the 2400s deadline =
# 0.513 URL/s, and the run stopped on the DEADLINE mid-batch-3, never on its
# 1,500 limit. Runs on 08-05 and 08-06 managed a single 500-URL batch each for
# the same reason. So raising the batch size alone would have changed nothing —
# the knob that was binding was the clock. 6600s keeps a run inside the job's
# 120-minute timeout with room for checkout, install and the final flush.
DEADLINE_CAP_SECONDS = 6600
DEADLINE_SECONDS = max(60, min(DEADLINE_CAP_SECONDS,
                               int(os.environ.get("ARCHIVE_BACKFILL_DEADLINE_SECONDS", "1500"))))
# Throughput floor observed across a full run INCLUDING the whole rate-limited
# Save-Page-Now budget, which is the slow part. Two independent measurements:
#   run 30883391601 (2026-08-04)  1,231 URLs / 2,400s = 0.513/s, deadline-cut
#   run 31147628741 (2026-08-07)  1,657 URLs / 3,628s = 0.457/s, POOL-EXHAUSTED
# The lower of the two is used, because a floor that flatters itself is not a
# floor. tests/test_archive_promise.py uses it to assert the deadline is
# actually long enough to reach LIMIT, so this number is load-bearing: raise it
# only against a measured run, never to make an assertion fit.
MEASURED_URLS_PER_SECOND = 1657 / 3628.0
DRY_RUN = os.environ.get("ARCHIVE_BACKFILL_DRY_RUN", "").lower() in {"1", "true", "yes"}

# Sentinel returned by save_page_now when Wayback throttled the request, so the
# caller backs off instead of treating it as a permanent failure.
RATE_LIMITED = "__rate_limited__"


# --- pure helpers (unit-tested) -------------------------------------------

def dedupe_urls(urls):
    """Trim, drop non-http(s)/blank, de-duplicate preserving order.

    Mirrors the server's own source-URL filtering so the worker never wastes a
    capture on a value the store would reject."""
    out, seen = [], set()
    for u in urls or []:
        u = str(u or "").strip()
        if not u or not u.lower().startswith(("http://", "https://")):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def parse_availability(payload):
    """Return a permanent snapshot permalink from an availability-API payload,
    or None. The API answers {'archived_snapshots': {'closest': {...}}} with a
    'closest' only when a usable snapshot exists."""
    if not isinstance(payload, dict):
        return None
    closest = (payload.get("archived_snapshots") or {}).get("closest") or {}
    if not closest.get("available"):
        return None
    status = str(closest.get("status") or "")
    if status and not status.startswith("2") and status not in ("", "3"):
        # Only accept snapshots that actually captured content (2xx). A stored
        # 4xx/5xx snapshot is a receipt of a dead page, not a usable archive.
        if not status.startswith("3"):
            return None
    url = str(closest.get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return None
    # Prefer https for the link we display.
    return url.replace("http://web.archive.org", "https://web.archive.org", 1)


def classify_outcome(availability_url, spn_url):
    """Decide the status to record for one URL from this round's results.

    Returns ('archived', permalink) when either the availability check found an
    existing snapshot or Save Page Now returned a fresh one; otherwise
    ('pending', '') so the URL is retried on a later run. The server promotes a
    long-pending URL to 'unavailable' after ALT_ARCHIVE_MAX_ATTEMPTS, so the
    worker never has to guess when a source is dead — it only reports what this
    round observed. Never raises."""
    if availability_url:
        return "archived", availability_url
    if spn_url and spn_url != RATE_LIMITED and str(spn_url).lower().startswith("http"):
        return "archived", spn_url
    return "pending", ""


# --- network (fail-open) ---------------------------------------------------

def check_availability(url, session):
    """Free existence check. Returns a permalink or None; never raises."""
    try:
        r = session.get(AVAILABILITY, params={"url": url}, headers=UA, timeout=30)
        if r.status_code != 200:
            return None
        return parse_availability(r.json())
    except Exception:
        return None


def save_page_now(url, session):
    """Trigger a Wayback capture. Returns a permalink, RATE_LIMITED, or None.

    Never raises: a save failure just leaves the URL 'pending' for a later run."""
    try:
        r = session.get(SAVE + url, headers=UA, timeout=90, allow_redirects=True)
        if r.status_code == 429:
            return RATE_LIMITED
        loc = r.headers.get("Content-Location") or ""
        if loc.startswith("/web/"):
            return "https://web.archive.org" + loc
        # Some captures land on the final snapshot URL directly.
        if r.status_code in (200, 301, 302) and "/web/" in r.url:
            return r.url.replace("http://web.archive.org", "https://web.archive.org", 1)
        return None
    except Exception:
        return None


# --- server I/O ------------------------------------------------------------

def fetch_candidates():
    """Distinct un-archived source URLs from the server (already the gap).

    The server caps one response at 500 URLs, so run() fetches REPEATEDLY:
    recorded URLs drop out of the candidate list (or move to the back of the
    oldest-attempt-first ordering), so each fetch pages naturally through the
    due pool until the run's LIMIT, deadline, or an empty batch stops it. One
    batch per run was the quiet defect that made the weekly re-check promise
    unkeepable: a ~4,000-URL pending pool needs ~1,300 re-checks a day and a
    single 500 batch cannot deliver that.
    """
    try:
        r = requests.get(f"{SITE}/wp-json/layoffs/v1/archive-candidates",
                         params={"limit": LIMIT},
                         headers={**UA, "X-Layoff-API-Key": KEY}, timeout=60)
    except requests.RequestException as exc:
        raise RuntimeError(f"/archive-candidates unreachable: {exc}")
    if r.status_code != 200:
        raise RuntimeError(f"/archive-candidates HTTP {r.status_code}: {r.text[:200]}")
    payload = r.json()
    return dedupe_urls(payload.get("urls", [])), payload.get("coverage", {})


def post_records(items):
    """POST results to /archive-record. Raises on HTTP failure (loud)."""
    if not items:
        return {}
    r = requests.post(f"{SITE}/wp-json/layoffs/v1/archive-record",
                      json={"items": items},
                      headers={**UA, "X-Layoff-API-Key": KEY}, timeout=120)
    r.raise_for_status()
    return r.json()


def run():
    session = requests.Session()
    records = []
    archived = pending = checked = saves = rate_limited = 0
    started = time.monotonic()
    seen = set()
    coverage_before = None
    batches = 0

    def past_deadline():
        return time.monotonic() - started >= DEADLINE_SECONDS

    def flush(force=False):
        """Post accumulated records so progress is DURABLE and visible DURING
        the run. Batching everything to the end meant a long/killed run wrote
        nothing at all (coverage stuck at 0). Never raises — a failed flush is
        logged and the batch is retried on the next flush / at run end."""
        nonlocal records
        if DRY_RUN or not records:
            return
        if force or len(records) >= FLUSH_EVERY:
            try:
                post_records(records)
                records = []
            except Exception as exc:
                print(f"::warning::flush failed ({exc}); will retry the batch next flush")

    def process(urls):
        """One batch: the free availability pass, then the bounded SPN pass."""
        nonlocal archived, pending, checked, saves, rate_limited
        # PASS 1 — free availability checks over ALL candidates FIRST. Most WARN
        # files and much crawled news are already in Wayback, so this lands the
        # bulk of the links FAST and independent of candidate ordering. A Wayback
        # miss is queued for the (slow, rate-limited) save pass below rather than
        # blocking the quick wins behind a 90s capture.
        misses = []
        for url in urls:
            if past_deadline():
                print(f"deadline ({DEADLINE_SECONDS}s) reached during availability pass "
                      f"after {checked} URL(s)")
                break
            checked += 1
            snap = check_availability(url, session)
            if snap:
                archived += 1
                records.append({"url": url, "archived_url": snap, "status": "archived"})
                print(f"  [archived:availability] {url} -> {snap}")
                flush()
            else:
                misses.append(url)

        # PASS 2 — spend the bounded Save-Page-Now budget on the misses (slow,
        # rate-limited). Over budget / past deadline / dry-run: record 'pending'.
        # Recording without a save is HONEST — pass 1 just re-checked Wayback for
        # this URL — and it is what stamps checked_at, so the row's public
        # "next check by <date>" moves forward off a check that really happened.
        for url in misses:
            if DRY_RUN or saves >= SPN_MAX or past_deadline():
                pending += 1
                records.append({"url": url, "archived_url": "", "status": "pending"})
                flush()
                continue
            spn = save_page_now(url, session)
            saves += 1
            if spn == RATE_LIMITED:
                rate_limited += 1
                # Back off harder when throttled, then keep going.
                time.sleep(SPN_GAP_SECONDS * 3)
            else:
                time.sleep(SPN_GAP_SECONDS)
            status, permalink = classify_outcome(None, spn)
            if status == "archived":
                archived += 1
            else:
                pending += 1
            records.append({"url": url, "archived_url": permalink, "status": status})
            print(f"  [{status}:{'save' if permalink else 'pending'}] {url}"
                  + (f" -> {permalink}" if permalink else ""))
            flush()
        return misses

    # Batch loop: page through the due pool (the server hands out at most 500
    # per response) until the run LIMIT, the deadline, or an empty batch. The
    # `seen` guard makes the loop terminate even if a flush failed and the
    # server hands the same URLs back.
    dry_misses = 0
    while len(seen) < LIMIT and not past_deadline():
        urls, coverage = fetch_candidates()
        if coverage_before is None:
            coverage_before = coverage
        urls = [u for u in urls if u not in seen][: LIMIT - len(seen)]
        batches += 1
        print(f"archive backfill: batch {batches}: {len(urls)} candidate URL(s); "
              f"coverage before: {coverage}")
        if not urls:
            break
        seen.update(urls)
        dry_misses += len(process(urls))
        if DRY_RUN:
            break   # nothing was recorded, so a second fetch would repeat this batch

    if not seen:
        coverage_before = coverage_before or {}
        detail = (f"nothing to archive this run; coverage {coverage_before.get('archived', 0)}/"
                  f"{coverage_before.get('distinct_source_urls', 0)} distinct source URLs "
                  f"({coverage_before.get('coverage_pct', 0)}%)")
        if not DRY_RUN:
            report_source_health("archive_backfill", "ok", 0, detail)
        print(detail)
        return {"archived": 0, "pending": 0, "checked": 0}

    if DRY_RUN:
        print(f"DRY RUN: checked={checked} would-archive={archived} "
              f"would-pend={dry_misses}; no writes.")
        return {"archived": 0, "pending": dry_misses, "checked": checked}

    flush(force=True)  # post the remainder
    # FAIL LOUD: flush() swallows a failed post so it can retry, but if the
    # final forced flush also failed the records were never persisted and are
    # still buffered here. A run that captured nothing because every write
    # failed must NOT report "ok" (that was the whole "succeeds while writing
    # nothing" trap). Raise so main() degrades health and exits non-zero.
    if records:
        raise RuntimeError(
            f"archive backfill could not persist {len(records)} record(s) to "
            f"/archive-record (all flushes failed this run); reporting degraded")
    # Read the true server coverage for the health detail (accurate regardless
    # of how records were batched above).
    try:
        coverage_after = session.get(f"{SITE}/wp-json/layoffs/v1/archive-coverage",
                                     headers=UA, timeout=30).json()
    except Exception:
        coverage_after = {}
    detail = (f"{archived} archived / {pending} still pending this run "
              f"({saves} Save-Page-Now captures, {rate_limited} throttled); "
              f"coverage {coverage_after.get('archived', 0)}/"
              f"{coverage_after.get('distinct_source_urls', 0)} distinct source URLs "
              f"({coverage_after.get('coverage_pct', 0)}%), "
              f"{coverage_after.get('unavailable', 0)} recorded unavailable")
    print(detail)
    # A run that captured nothing AND could not even find existing snapshots,
    # only because every save was throttled, is a degraded (not failed) state:
    # the work retries next run. A hard failure would be a raise above.
    status = "degraded" if (archived == 0 and rate_limited and rate_limited == saves) else "ok"
    if not report_source_health("archive_backfill", status, archived, detail):
        print("::warning::archive_backfill completed but the health-ledger write failed (data is fine)")
    return {"archived": archived, "pending": pending, "checked": checked}


def main():
    if not SITE or (not KEY and not DRY_RUN):
        print("WP_SITE_URL and WP_API_KEY are required (or set ARCHIVE_BACKFILL_DRY_RUN=1)")
        return 1
    if not DRY_RUN:
        if not report_source_health("archive_backfill", "running", 0,
                                    "capturing permanent Wayback snapshots of source URLs"):
            raise RuntimeError("Could not publish archive_backfill running health status")
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY_RUN:
            report_source_health("archive_backfill", "degraded", 0, f"archive backfill failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
