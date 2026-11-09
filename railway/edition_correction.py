"""Attach a dated correction note to a published edition (dispatch only).

Published editions are immutable (includes/digest-archive.php): a revised
figure is disclosed as a note above the original text, never by re-rendering
it. This is the caller for the keyed `/edition-correction` endpoint. Dry run
unless --apply; every failure exits non-zero; the read-back must find the
note on the public page.

    WP_SITE_URL=... WP_API_KEY=... python3 railway/edition_correction.py \
        --freq weekly --slug 2026-W45 --note "..." [--apply]
"""
import argparse
import html
import os
import re
import sys
import time
import uuid

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 45
READBACK_SLEEP = 30  # the page cache is bounded to 60s
SLUGS = {"weekly": r"\d{4}-W\d{2}", "daily": r"\d{4}-\d{2}-\d{2}"}


def validate(freq, slug, note):
    problems = []
    if freq not in SLUGS:
        problems.append(f"freq must be one of {sorted(SLUGS)}")
    elif not re.fullmatch(SLUGS[freq], slug or ""):
        problems.append(f"slug {slug!r} is not a {freq} edition slug")
    note = (note or "").strip()
    if not note:
        problems.append("note is empty")
    if len(note) > 1000:
        problems.append("note is over 1000 characters (the server truncates)")
    if "—" in note:
        problems.append("note contains an em-dash (house style)")
    return problems


def edition_url(site, freq, slug):
    return f"{site}/ai-layoff-tracker/editions/{freq}/{slug}/"


def run(freq, slug, note, apply, site, key):
    note = (note or "").strip()
    problems = validate(freq, slug, note)
    if problems:
        print("REFUSED: " + "; ".join(problems))
        return 1
    print(f"edition: {edition_url(site, freq, slug)}")
    print(f"note: {note}")
    if not apply:
        print("DRY RUN - nothing written. Re-run with --apply to attach the note.")
        return 0
    if not key:
        print("WP_API_KEY required to apply")
        return 1
    r = requests.post(f"{site}/wp-json/layoffs/v1/edition-correction",
                      json={"freq": freq, "slug": slug, "note": note},
                      headers={"X-Layoff-API-Key": key, **UA}, timeout=TIMEOUT)
    if r.status_code != 200 or not (r.json() or {}).get("ok"):
        print(f"FAILED: HTTP {r.status_code}; the edition was not found or not published")
        return 1
    want = (html.escape(note, quote=False)[:80], note[:80])
    for attempt in range(4):
        page = requests.get(edition_url(site, freq, slug), params={"cb": str(uuid.uuid4())},
                            headers=UA, timeout=TIMEOUT)
        if any(w in page.text for w in want):
            break
        if attempt < 3:
            time.sleep(READBACK_SLEEP)
    else:
        print("FAILED: the note was accepted but is not on the public page yet")
        return 1
    print("applied: the note is on the public page")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freq", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--note", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    return run(a.freq, a.slug, a.note, a.apply,
               os.environ.get("WP_SITE_URL", "https://asktherecruiter.com/blog").rstrip("/"),
               os.environ.get("WP_API_KEY", ""))


if __name__ == "__main__":
    sys.exit(main())
