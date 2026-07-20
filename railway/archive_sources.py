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


def source_urls():
    urls = []
    seen = set()
    for u in list(STATE_WARN_URL.values()) + list(KNOWN_EDD_ANNUAL_PDFS) + [CA_XLSX]:
        u = (u or "").strip()
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def archive(url):
    """Trigger a Wayback capture. Returns the snapshot URL or None (fail-soft)."""
    try:
        r = requests.get(SAVE + url, headers={"User-Agent": UA},
                         timeout=90, allow_redirects=True)
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
    urls = source_urls()
    print(f"Archiving {len(urls)} WARN source documents to the Wayback Machine…")
    ok = 0
    for i, url in enumerate(urls, 1):
        snap = archive(url)
        if snap:
            ok += 1
            print(f"[{i}/{len(urls)}] saved: {url}")
        if i < len(urls):
            time.sleep(GAP_SECONDS)
    print(f"Archive done: {ok}/{len(urls)} source documents snapshotted.")
    # Don't fail the job for a few Wayback throttles — but a total wipeout means
    # the endpoint/network is down and is worth a red run.
    if urls and ok == 0:
        print("ERROR: zero snapshots taken — Wayback unreachable?")
        sys.exit(1)


if __name__ == "__main__":
    main()
