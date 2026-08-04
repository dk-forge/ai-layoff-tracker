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
DEADLINE_SECONDS = int(os.environ.get("ARCHIVE_DEADLINE_SECONDS") or str(50 * 60))

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

    # Don't fail the job for a few Wayback throttles — but a total wipeout means
    # the endpoint/network is down and is worth a red run. `attempted` and not
    # `total`: a deadline-truncated run that archived nothing because it
    # attempted nothing is a scheduling problem, and calling it "Wayback is
    # unreachable" would send a human hunting the wrong thing.
    if attempted and ok == 0:
        print("ERROR: zero snapshots taken — Wayback unreachable?")
        sys.exit(1)
    if total and not attempted:
        print("ERROR: the deadline left room for no captures at all — "
              "ARCHIVE_DEADLINE_SECONDS is smaller than one URL's timeout.")
        sys.exit(1)


if __name__ == "__main__":
    main()
