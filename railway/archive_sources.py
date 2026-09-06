"""Push every WARN source document to the Internet Archive (Wayback Machine).

Why: the tracker stores each notice's extracted data + a link to its official
state source, but states rotate and delete their WARN files (the CA FY2019-20
PDF already 404s). A dead source link weakens a citation. This job captures a
permanent, neutral, third-party snapshot of each source so the citation always
resolves — no self-hosted screenshots (which invite "did you doctor it?").

What it archives: every state's official WARN registry URL (STATE_WARN_URL) +
California's annual EDD PDFs + the live rolling xlsx. These are the ~50 distinct
source documents behind the bulk of WARN rows. Fail-soft per URL; rate-limited
so the Wayback save endpoint isn't hammered. Dispatch-only / weekly schedule.

A snapshot, once taken, lives at:
  https://web.archive.org/web/*/<source_url>
so the plugin can later add a "view archived copy" link with no per-row storage.
"""
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

try:
    from sources.warn import STATE_WARN_URL
except Exception:
    STATE_WARN_URL = {}
try:
    from ca_backfill import KNOWN_EDD_ANNUAL_PDFS
except Exception:
    KNOWN_EDD_ANNUAL_PDFS = []

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
SAVE = "https://web.archive.org/save/"
CA_XLSX = "https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn_report1.xlsx"
# Wayback throttles aggressive callers; keep a polite gap between captures.
GAP_SECONDS = int(os.environ.get("ARCHIVE_GAP_SECONDS") or "8")

# ---------------------------------------------------------------------------
# WHY THIS JOB HAS A CLOCK NOW
#
# It had never once finished. Both runs it has ever had were killed by the
# workflow's own `timeout-minutes: 20`: 20m21s on 2026-07-27 and 20m19s on
# 2026-08-03, both ending `cancelled`, which the CI alerter used to discard as
# routine — so a weekly job that has never completed was also completely
# silent, while the archive re-check invariant drifted to 8.6 days against its
# 10-day bound.
#
# THE MEASURED REASON. 54 distinct source documents; `/save/` is a LIVE crawl,
# not a lookup, so a capture routinely takes tens of seconds and the per-URL
# ceiling was 90s. Worst case was 54 * (90 + 8) = 88 minutes against a 20-minute
# job. Twenty minutes was never enough and no amount of retrying would have
# made it enough.
#
# So both halves of the fix, because either alone leaves a hole:
#   * the ceiling is raised to a number derived from the work (below), and
#   * the script owns a DEADLINE and stops itself before the runner does.
# A run that hits the deadline is a partial success, not a kill: it says which
# URLs it did not reach and exits 0, and the next weekly run starts where this
# one stopped, so no document can be starved.
#
# PER-URL TIMEOUT: 45s, down from 90. A capture that has not answered in 45
# seconds is a Wayback queue, not a slow byte stream; waiting the other 45
# spends a twelfth of the budget to learn the same thing. Wayback records the
# capture request regardless.
PER_URL_TIMEOUT = int(os.environ.get("ARCHIVE_URL_TIMEOUT") or "45")

# The script's own wall clock: 54 * (45 + 8) = 47.7 minutes worst case, so 50
# covers a full sweep with the deadline as the belt rather than the trousers.
# The workflow allows 60, which is that plus checkout, pip and the runner's own
# overhead. If the URL list grows past ~68, this stops being a full sweep and
# starts being a rotation, which is exactly what the cursor below is for.
# Clamped to 3300s (55min) against archive-sources.yml's 60 minute
# timeout-minutes. Unclamped until 2026-09-06, so one env var could put the
# run past the point the runner kills it.
DEADLINE_SECONDS = max(60, min(3300, int(os.environ.get("ARCHIVE_DEADLINE_SECONDS") or str(50 * 60))))

# WHERE A TRUNCATED SWEEP RESUMES, WITHOUT KEEPING ANY STATE.
#
# A full sweep fits inside the deadline, so truncation is the exception. It is
# still worth handling, because the failure it produces is invisible: a run that
# always starts at index 0 and always stops early archives the head of the list
# forever and the tail never, and every one of those runs is green.
#
# The obvious fix, a cursor file, does not work here: the runner is ephemeral,
# so the file is gone before the next run and the cursor reads 0 every week —
# the starvation bug with extra code. Committing it would need `contents: write`
# on a job that otherwise writes nothing.
#
# So the offset is DERIVED from the ISO week instead. No state, nothing to lose,
# and the rotation is reproducible from the date alone. The stride is coprime
# with nothing in particular on purpose — it just has to be large enough that
# consecutive weeks start in genuinely different places.
WEEK_STRIDE = 17


def week_offset(total, now=None):
    """A start index that moves every week. `now` is injectable so the rotation
    is testable without waiting a week."""
    if total <= 0:
        return 0
    week = (now or datetime.now(timezone.utc)).isocalendar()[1]
    return (week * WEEK_STRIDE) % total


def source_urls():
    urls = []
    seen = set()
    for u in list(STATE_WARN_URL.values()) + list(KNOWN_EDD_ANNUAL_PDFS) + [CA_XLSX]:
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def rotate(urls, start):
    """The same list, starting at `start`. Every URL still appears exactly
    once, so a full sweep is unchanged and a truncated one drops a DIFFERENT
    tail each week instead of starving the same documents forever."""
    if not urls:
        return []
    start %= len(urls)
    return urls[start:] + urls[:start]


# ---------------------------------------------------------------------------
# WHY "ZERO SNAPSHOTS" NEEDS A SECOND QUESTION ASKED
#
# The old ending was `if attempted and ok == 0: sys.exit(1)` with the message
# "Wayback unreachable?". The question mark was the whole defect: the run could
# not tell, so it guessed, and on 2026-08-17 it guessed by reddening CI for a
# week over an Internet Archive outage. The run log shows both halves of that
# outage in one sweep — connect timeouts to web.archive.org interleaved with
# blanket 404s from /save/ for forty-odd URLs that archive fine from a laptop.
#
# This repo already settled the general form of this question for undeliverable
# alerts: HELD, not lost, and exiting 0, because a red run caused by an outage
# manufactures alerts that the same outage cannot deliver. The same reasoning
# transfers here and only here because an unarchived URL is genuinely not lost:
# `/save/` is idempotent, the full set fits inside one sweep, and the week
# rotation re-attempts every document. Nothing has to be remembered for next
# week to be equivalent to this week — which is exactly the bar RUNBOOK sets
# for converting a job to defer.
#
# What is NOT softened: zero captures while the Internet Archive is answering
# normally is a defect in THIS script (an empty URL list, a changed /save/
# contract, a wrong UA) and still exits 1. So the verdict needs one more fact
# than the sweep produces, and `wayback_reachable` is the cheapest honest way
# to get it: the availability API is a LOOKUP, not a crawl, so it answers in
# well under a second, it is free, and it is independent of whether any
# particular capture succeeded.
IA_PROBE = "https://archive.org/wayback/available?url=example.com"


def wayback_reachable(get=None, timeout=20):
    """Is the Internet Archive answering AT ALL, independent of any capture?

    True only when archive.org returns a coherent, non-overloaded HTTP answer.
    A transport error, a throttle (429) or a 5xx all mean the host is not
    serving us right now, which is the fact the verdict below turns on. `get`
    is injectable so the tests never touch the network.
    """
    do_get = get or (lambda u, **kw: requests.get(u, **kw))
    try:
        r = do_get(IA_PROBE, headers={"User-Agent": UA}, timeout=timeout)
    except Exception as exc:
        print(f"  Internet Archive probe failed ({exc}) — the host is not "
              f"answering this runner")
        return False
    status = getattr(r, "status_code", 0)
    if status == 429 or status >= 500:
        print(f"  Internet Archive probe: HTTP {status} — the host is "
              f"throttling or down")
        return False
    return True


def verdict(*, attempted, ok, total, done, reachable):
    """The exit code, as a pure function of what the sweep observed.

    Split out from `main` so both branches are testable without a network and
    without a process exit. Returns 0 (green or held) or 1 (red).
    """
    if total and not attempted:
        print("ERROR: the deadline left room for no captures at all — "
              "ARCHIVE_DEADLINE_SECONDS is smaller than one URL's timeout.")
        return 1
    if attempted and ok == 0:
        if not reachable:
            # HELD, not lost. Nothing is recorded and nothing needs to be: the
            # next weekly run re-attempts every one of these documents, and
            # `archive_recheck_cadence` in data_integrity.py is the backstop
            # that goes red if the outage outlasts the promised cycle. That
            # bound is the thing that must notice a long outage, not this run.
            print(f"HELD: {attempted} capture(s) attempted, none taken, and the "
                  f"Internet Archive is not answering this runner at all. "
                  f"Nothing is lost — /save/ is idempotent and next week's "
                  f"sweep re-attempts every document. Exiting 0 so a "
                  f"third-party outage does not manufacture a red run; the "
                  f"archive_recheck_cadence invariant is what fails if this "
                  f"outage outlasts the promised re-check cycle.")
            return 0
        print(f"ERROR: zero snapshots from {attempted} attempt(s) while the "
              f"Internet Archive IS answering — this is a defect here, not an "
              f"outage. Check the URL list, the /save/ contract and the UA.")
        return 1
    return 0


def archive(url):
    """Trigger a Wayback capture. Returns the snapshot URL or None (fail-soft)."""
    try:
        r = requests.get(SAVE + url, headers={"User-Agent": UA},
                         timeout=PER_URL_TIMEOUT, allow_redirects=True)
        # A capture reports its snapshot path in Content-Location; fall back to
        # the canonical latest-snapshot URL, which resolves once a capture exists.
        loc = r.headers.get("Content-Location") or ""
        if loc:
            return "https://web.archive.org" + loc
        if r.status_code in (200, 301, 302):
            return "https://web.archive.org/web/*/" + url
        print(f"  archive HTTP {r.status_code}: {url}")
        return None
    except Exception as exc:
        print(f"  archive failed ({exc}): {url}")
        return None


def main():
    every = source_urls()
    total = len(every)
    start = week_offset(total)
    urls = rotate(every, start)
    started = time.monotonic()
    print(f"Archiving {total} WARN source documents to the Wayback Machine, "
          f"from index {start}, within {DEADLINE_SECONDS // 60} minutes…")

    ok = 0
    done = 0
    for i, url in enumerate(urls, 1):
        spent = time.monotonic() - started
        # Checked BEFORE the request, against the worst case of the request
        # that is about to be made. Stopping only once the clock has already
        # run out is how you get killed inside the last capture, which is the
        # failure this replaces.
        if spent + PER_URL_TIMEOUT > DEADLINE_SECONDS:
            print(f"\nDeadline: {spent / 60:.1f} min spent, stopping before "
                  f"URL {i} of {total} so the runner does not have to.")
            break
        snap = archive(url)
        done = i
        if snap:
            ok += 1
            print(f"[{i}/{total}] saved: {url}")
        if i < len(urls):
            time.sleep(GAP_SECONDS)

    attempted = done
    print(f"Archive done: {ok}/{attempted} attempted snapshotted "
          f"({total} documents in the full set, "
          f"{'complete sweep' if done >= total else f'{total - done} deferred to next week'}).")

    # Don't fail the job for a few Wayback throttles — but a total wipeout has
    # two possible causes and they need two different verdicts, so ask the one
    # extra question before deciding (see `verdict` above). `attempted` and not
    # `total`: a deadline-truncated run that archived nothing because it
    # attempted nothing is a scheduling problem, and calling it "Wayback is
    # unreachable" would send a human hunting the wrong thing.
    reachable = True
    if attempted and ok == 0:
        reachable = wayback_reachable()
    code = verdict(attempted=attempted, ok=ok, total=total, done=done,
                   reachable=reachable)
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
