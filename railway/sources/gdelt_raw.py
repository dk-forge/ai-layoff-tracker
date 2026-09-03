"""GDELT via its PUBLISHED index files (data.gdeltproject.org/gdeltv2/).

WHY A THIRD PATH. The public DOC query API (`api.gdeltproject.org/api/v2/doc/doc`)
abandoned the broad window on 100% of measured runs from 2026-08-19 and
answered HTTP 000 after a 45s timeout from the owner's machine on 2026-09-03.
The BigQuery mirror answers, but it filters `gkg_partitioned` on
`_PARTITIONTIME`, so the newest slice of a window can sit outside the
partition when the run reads it, and no surface ever recorded how far behind
it was (TECHLOG 2026-09-03 bounds it at under seven hours for one story and
calls the exact value UNKNOWN). It also spends a 1 TB/month quota, 30 GB per
query. This path records the newest file it consumed, every run.

GDELT publishes the SAME GKG records as static files, one per 15 minutes, on
a CDN, with no key and no quota. Measured 2026-09-03 10:37 UTC from the
owner's machine: `lastupdate.txt` answered in 0.19s and named a file stamped
10:30, i.e. seven minutes of lag against a query service that does not answer
at all. Two feeds make up the worldwide set:

    YYYYMMDDHHMMSS.gkg.csv.zip              English-source articles
    YYYYMMDDHHMMSS.translation.gkg.csv.zip  every other language, original
                                            title kept in <PAGE_TITLE>

The English file lands about five minutes after its stamp, the translation
file five to forty-five minutes after (measured: at 10:38 UTC the 09:45
translation file existed, 10:00 and 10:30 did not, and 10:15 did). A file
that is not there yet is PENDING, not a gap, and the next run's overlapping
window reads it.

WHAT IT COSTS, MEASURED (36h window, 2026-09-03). 145 slots x 2 feeds = 290
files, 695 MB English + 1,271 MB translation = 1,966 MB. A 24-file sample
with four workers ran at 17.7 MB/s effective, download and parse included,
so the whole window is about 110 s of wall clock from that machine. That is
inside the daily run's 900 s budget with room for the sweeps, and it is free
of quota; it is not free of bandwidth, about 2 GB a day, and the module
STREAMS: one zip in memory per worker, rows read line by line, only the
matching rows kept. Never hold the window.

SAME SEMANTICS AS THE MIRROR, on purpose. A row is a candidate when its
V2Themes carry UNEMPLOYMENT or its page title matches `gdelt_bq.title_pattern`
over the shared discovery vocabulary plus the native phrases from
`native_layoff_terms.mirror_title_terms()` -- the one regex definition, so
the two paths cannot drift. The title is HTML-unescaped before matching,
which the mirror's SQL never did; a Devanagari headline in the translation
feed is `&#x915;...` on disk. Everything downstream is untouched: the
allowlist, the robots gate before any article body, dedup, the headline gate
and the reach ledger all sit behind `sources.gdelt._fetch_trusted`, which is
the only exit from every one of the three paths.

The file names are deterministic (every 15 minutes, on the quarter hour), so
nothing here reads the 127 MB `masterfilelist.txt`; a window is enumerated
from its bounds and each file is asked for by name.
"""
from __future__ import annotations

import html
import io
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

from sources import gdelt_bq

BASE_URL = "https://data.gdeltproject.org/gdeltv2/"
# The identifying string with a contact URL, the same one the article fetch
# sends. GDELT's files are published for bulk download; no robots gate is
# involved because no publisher is asked for anything here.
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# The two feeds that together are the worldwide set. Dropping the translation
# feed would silently return the collector to English-only, the exact defect
# 2.20.158 closed for the mirror, so the pair is a constant, not a knob.
FEEDS = ("", "translation.")

SLOT = timedelta(minutes=15)

# A 404 newer than this, measured from the window's END, is a file GDELT has
# not published yet (PENDING); an older 404 is a GAP. Sized from the measured
# translation-feed lag (up to ~45 min) with headroom; it is not a threshold
# to widen when a gap appears, because a gap is a fact about the source.
PUBLICATION_LAG = timedelta(hours=2)

# How far back this path applies. A 36h window is ~2 GB; a two-year backfill
# window is the same per window and the mirror already serves history under
# quota, so windows whose START is older than this go to the mirror. Clamped.
def _clamped_horizon_days(raw=None):
    if raw is None:
        raw = os.environ.get("GDELT_RAW_FEED_HORIZON_DAYS", "7")
    try:
        return max(1, min(30, int(raw)))
    except (TypeError, ValueError):
        return 7


HORIZON = timedelta(days=_clamped_horizon_days())

WORKERS = max(1, min(6, int(os.environ.get("GDELT_RAW_FEED_WORKERS", "4"))))
FETCH_TIMEOUT = 60
FETCH_ATTEMPTS = 2
# A file larger than this is not a GKG slice (the biggest measured was 15 MB).
MAX_FILE_BYTES = 64 * 1024 * 1024

# GKG 2.1 column positions (tab-separated, 27 columns, no header).
COL_DATE = 1
COL_DOMAIN = 3
COL_URL = 4
COL_V2THEMES = 8
COL_EXTRAS = 26
NCOLS = 27

_TITLE_RX = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)
THEME_TOKEN = "UNEMPLOYMENT"


def enabled() -> bool:
    """On unless GDELT_RAW_FEED=0. Off is a decision, not a default."""
    return os.environ.get("GDELT_RAW_FEED", "1") not in ("0", "false", "no")


def within_horizon(start, now=None) -> bool:
    now = now or datetime.now(timezone.utc)
    return (now - start.astimezone(timezone.utc)) <= HORIZON


def slot_stamps(start, end):
    """Every 15-minute file stamp whose slot touches [start, end], oldest first.

    `start` is floored to the quarter hour so the slot containing it is read;
    `end` is floored so a slot that has not begun is never asked for.
    """
    s = start.astimezone(timezone.utc).replace(second=0, microsecond=0)
    s = s.replace(minute=(s.minute // 15) * 15)
    e = end.astimezone(timezone.utc).replace(second=0, microsecond=0)
    e = e.replace(minute=(e.minute // 15) * 15)
    out = []
    t = s
    while t <= e:
        out.append(t.strftime("%Y%m%d%H%M%S"))
        t += SLOT
    return out


def file_url(stamp, feed):
    return f"{BASE_URL}{stamp}.{feed}gkg.csv.zip"


def stamp_to_dt(stamp):
    return datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _seendate(stamp):
    return f"{stamp[0:8]}T{stamp[8:14]}Z" if len(stamp) == 14 else ""


class NotPublished(Exception):
    """HTTP 404: the file is not on the CDN (yet, or ever)."""


def fetch_file(url, session=None, timeout=FETCH_TIMEOUT):
    """The zip bytes of one file. Raises NotPublished on 404, else on error.

    Two attempts on transport errors and 5xx; a 404 is asked twice too, because
    the CDN has been seen to answer 404 for a file the master list already
    names, and a single 404 must not become a recorded gap.
    """
    get = (session or requests).get
    last = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            resp = get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except Exception as exc:  # transport
            last = exc
            time.sleep(1.0 * (attempt + 1))
            continue
        if resp.status_code == 404:
            last = NotPublished(url)
            time.sleep(0.5)
            continue
        if resp.status_code >= 500:
            last = RuntimeError(f"HTTP {resp.status_code} {url}")
            time.sleep(1.0 * (attempt + 1))
            continue
        resp.raise_for_status()
        body = resp.content
        if len(body) > MAX_FILE_BYTES:
            raise RuntimeError(f"file over {MAX_FILE_BYTES} bytes: {url}")
        return body
    raise last


def matcher(terms):
    """The row predicate: UNEMPLOYMENT theme OR title regex. One definition
    of the regex, shared with the mirror (`gdelt_bq.title_pattern`)."""
    rx = re.compile(gdelt_bq.title_pattern(terms))

    def match(title_lower, themes):
        return THEME_TOKEN in themes or bool(rx.search(title_lower))

    return match


def iter_rows(zip_bytes):
    """Yield (date_stamp, domain, url, title, v2themes) per GKG row, streaming.

    The member is read line by line through a text wrapper over the zip
    stream, so the 40 MB decompressed CSV is never held whole; only the five
    columns a candidate needs are kept per row.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        if not names:
            return
        with z.open(names[0]) as fh:
            for line in io.TextIOWrapper(fh, encoding="utf-8", errors="replace"):
                f = line.rstrip("\n").split("\t")
                if len(f) < NCOLS:
                    continue
                m = _TITLE_RX.search(f[COL_EXTRAS])
                title = html.unescape(m.group(1)).strip() if m else ""
                yield f[COL_DATE], f[COL_DOMAIN], f[COL_URL], title, f[COL_V2THEMES]


def parse_candidates(zip_bytes, match):
    """The matching rows of one file, in the DOC-API article shape."""
    out = []
    for date_stamp, domain, url, title, themes in iter_rows(zip_bytes):
        url = (url or "").strip()
        domain = (domain or "").strip().lower()
        if not url or not domain:
            continue
        if not match(title.lower(), themes):
            continue
        out.append({"url": url, "domain": domain, "title": title,
                    "seendate": _seendate(date_stamp)})
    return out


def read_window(start, end, terms, *, deadline=None, fetch=None, now=None,
                workers=WORKERS):
    """Read every file of [start, end] across both feeds, streaming.

    Returns (articles, report). `report` is plain numbers and stamps:
      files_expected   slots x feeds
      files_read       files fetched and parsed
      pending          404s newer than PUBLICATION_LAG before `end` (not yet
                       published; the next run's overlapping window reads them)
      gaps             404s older than that (GDELT never published the slot)
      failed           transport/5xx errors after FETCH_ATTEMPTS
      skipped          files not attempted because `deadline` passed
      newest           the newest stamp actually consumed, per feed and overall
      status           "complete" when nothing was skipped, failed or a gap;
                       else "partial" (the caller records the slot as such)
    `fetch(url) -> bytes` is injectable, so this is testable with no network.
    """
    fetch = fetch or _session_fetch()
    match = matcher(terms)
    end_utc = end.astimezone(timezone.utc)
    stamps = slot_stamps(start, end)
    jobs = [(stamp, feed) for stamp in stamps for feed in FEEDS]
    report = {
        "files_expected": len(jobs), "files_read": 0, "pending": 0,
        "gaps": 0, "failed": 0, "skipped": 0,
        "newest": None, "newest_by_feed": {feed: None for feed in FEEDS},
        "candidates": 0, "status": "complete",
    }
    articles, seen = [], set()

    def one(job):
        stamp, feed = job
        if deadline is not None and time.monotonic() >= deadline:
            return job, "skipped", None
        try:
            data = fetch(file_url(stamp, feed))
        except NotPublished:
            lag = end_utc - stamp_to_dt(stamp)
            return job, ("pending" if lag <= PUBLICATION_LAG else "gap"), None
        except Exception as exc:
            print(f"GDELT raw feed: {stamp} {feed or 'english'} failed: {exc}")
            return job, "failed", None
        try:
            return job, "read", parse_candidates(data, match)
        except Exception as exc:
            print(f"GDELT raw feed: {stamp} {feed or 'english'} unreadable: {exc}")
            return job, "failed", None

    # Ordered submission, ordered consumption: the newest-consumed stamp is a
    # max over what was READ, so order only affects log tidiness.
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for (stamp, feed), outcome, rows in pool.map(one, jobs):
            if outcome == "read":
                report["files_read"] += 1
                if report["newest_by_feed"][feed] is None or stamp > report["newest_by_feed"][feed]:
                    report["newest_by_feed"][feed] = stamp
                if report["newest"] is None or stamp > report["newest"]:
                    report["newest"] = stamp
                for a in rows:
                    report["candidates"] += 1
                    if a["url"] in seen:
                        continue
                    seen.add(a["url"])
                    articles.append(a)
            elif outcome == "pending":
                report["pending"] += 1
            elif outcome == "gap":
                report["gaps"] += 1
            elif outcome == "failed":
                report["failed"] += 1
            else:
                report["skipped"] += 1
    if report["gaps"] or report["failed"] or report["skipped"]:
        report["status"] = "partial"
    if report["files_read"] == 0:
        # Nothing read is not a window; the caller falls through to the mirror.
        raise RuntimeError(
            f"GDELT raw feed read 0 of {report['files_expected']} files "
            f"(pending={report['pending']} gaps={report['gaps']} "
            f"failed={report['failed']} skipped={report['skipped']})")
    return articles, report


def _session_fetch():
    session = requests.Session()
    return lambda url: fetch_file(url, session=session)


def lag_minutes(newest_stamp, at):
    """Minutes between the newest consumed file stamp and `at` (window end)."""
    if not newest_stamp:
        return None
    delta = at.astimezone(timezone.utc) - stamp_to_dt(newest_stamp)
    return max(0, int(delta.total_seconds() // 60))
