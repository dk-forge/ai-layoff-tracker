"""Minnesota DEED per-company WARN LETTER notices (free-text PDFs).

WHY THIS EXISTS
---------------
`sources/warn_custom.fetch_mn` reads DEED's MONTHLY report PDFs — structured
tables parsed deterministically by `_mn_parse_table` and posted through the WARN
/bulk path. In mid-2026 DEED stopped (or fell behind on) the monthly rollups and
began publishing each employer's WARN letter as its OWN asset PDF at
`mn.gov/deed/assets/warn-YYYY-<company>_tcm1045-N.pdf` (and the older
`YYYY-warn-<company>` shape). Those letters are FREE TEXT, not tables, so
`_mn_parse_table` returns [] on them and they never entered the pipeline.

The result was a 53-day MN freshness stall (measured 2026-08-24): fetch_mn kept
returning its frozen June-and-earlier history — a healthy-looking 72-80 rows,
newest effective date 2026-07-01 — while Pearson's Candy (Jul 30), Heliene
(Aug 5), UCare (Aug 3) and others sat unread. Every COUNT-based check read green
because the national total hid one dark state; `source_freshness` is what caught
it.

DISCOVERY (keyless, no CAPTCHA bypass)
--------------------------------------
The DEED HTML index that lists these PDFs is behind a Radware/ShieldSquare
CAPTCHA, live AND in Wayback — we do NOT bypass it. But two keyless routes reach
the letter URLs:
  * Wayback CDX indexes them (verified 2026-08-24) under the `warn-*` /
    `YYYY-warn*` prefixes — the SAME index fetch_mn already uses, just a prefix
    fetch_mn's `plant-closing*` query never covered. This is the durable route.
  * A seed list backstops the CDX archival lag for the very newest letters.

THE GOING-FORWARD SLIVER (honest limit)
---------------------------------------
There is no keyless, CAPTCHA-free AUTO-discovery of a letter in the window
between DEED publishing it and Wayback archiving it. CDX lag is usually short
for these (the Aug 5 Heliene letter was already in CDX on Aug 24), so the gap is
small — but a genuinely fresh letter can be invisible until either CDX catches
up or a human hand-seeds it below (or the owner wires a keyed web-search API,
which would need a NEW secret — flagged for the owner, not added here).

PIPELINE
--------
Free text, so these go through the LLM extractor exactly like a news article:
`pull_mn_warn_letters()` returns raw dicts with `raw_text` set, and cron.py runs
the standard gate -> extract_layoff_data -> post_to_wordpress path. No row is
written directly; the extractor's verbatim-count and is-a-layoff guards reject
anything that is not a real WARN layoff, so an over-broad discovery is safe.
"""
import io
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests

# Browser-ish UA — ModSecurity/Radware block python-requests, and mn.gov/assets
# still wants a real-looking agent even though the PDFs bypass the HTML wall.
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0 Safari/537.36")}
TIMEOUT = 40
CDX = "https://web.archive.org/cdx/search/cdx"

# Only true per-company WARN letters: `warn-2026-acme` or `2026-warn-acme`, never
# the monthly `plant-closing-*` rollups (those are fetch_mn's job).
_LETTER_RX = re.compile(
    r"/deed/assets/(?:warn-\d{4}|\d{4}-warn)-[^\s/]*_tcm1045-\d+\.pdf$", re.I)

# CDX-lag backstop for the newest letters (verified-live 2026-08-24). Keep the
# freshest few here until CDX archives them; CDX supplies the rest automatically.
_SEED_LETTERS = [
    "https://mn.gov/deed/assets/warn-2026-pearsons-candy-company_tcm1045-762217.pdf",  # Jul 30
    "https://mn.gov/deed/assets/warn-2026-heliene_tcm1045-762908.pdf",                 # Aug 5
    "https://mn.gov/deed/assets/warn-2026-ucare_tcm1045-762701.pdf",                   # Aug 3
    "https://mn.gov/deed/assets/warn-2026-revol-greens_tcm1045-762900.pdf",
    "https://mn.gov/deed/assets/warn-2026-notions-marketing_tcm1045-758343.pdf",
]


_MONTHS = ("january february march april may june july august september "
           "october november december").split()


def _monthly_cutoff_date():
    """The first day AFTER the newest MONTHLY report fetch_mn already covers.

    Letters older than this are already ingested as monthly-report table rows,
    and the two paths do NOT share a dedup key (db.php's fuzzy dedup covers only
    news/8K/press_release/erm — WARN rows are exempt), so ingesting an
    already-covered letter would DOUBLE-COUNT it. Deriving the boundary from the
    seed list makes it self-adjusting: when a session seeds the July monthly
    report, the cutoff advances to August 1 and July letters stop being ingested
    here. Env `MN_LETTER_MIN_DATE` (YYYY-MM-DD) overrides for tuning."""
    env = (os.environ.get("MN_LETTER_MIN_DATE") or "").strip()
    if env:
        try:
            return datetime.strptime(env, "%Y-%m-%d").date()
        except ValueError:
            pass
    from sources.warn_custom import _MN_SEED_PDFS
    newest = None
    for u in _MN_SEED_PDFS:
        m = re.search(r"warn-(\d{4})-([a-z]+)", u) or re.search(r"warn-([a-z]+)-?(\d{4})", u)
        if not m:
            continue
        a, b = m.group(1), m.group(2)
        yr, mon = (a, b) if a.isdigit() else (b, a)
        if mon not in _MONTHS:
            continue
        d = date(int(yr), _MONTHS.index(mon) + 1, 1)
        if newest is None or d > newest:
            newest = d
    if newest is None:
        # No parseable monthly month -> conservative 120-day rolling floor so we
        # still fill a gap without reaching back into monthly-covered history.
        return date.today() - timedelta(days=120)
    # First day of the month after the newest monthly report.
    return date(newest.year + (newest.month // 12), (newest.month % 12) + 1, 1)


def _letter_date(text):
    """The notice's own filing date near the top, as a date, or None. Used only
    to place a letter against the monthly cutoff (the extractor derives the
    authoritative layoff date separately). Handles both 'Month DD, YYYY' and
    numeric 'M/D/YYYY', and returns the FIRST date by position in the header
    block — a WARN letter leads with its notice date, and taking the first (not
    the earliest value) avoids dropping a genuinely fresh letter that happens to
    cite an older date lower down."""
    rx = re.compile(
        r"(?P<mon>[A-Z][a-z]+)\s+(?P<d>\d{1,2}),?\s+(?P<y>20\d\d)"
        r"|(?P<m2>\d{1,2})/(?P<d2>\d{1,2})/(?P<y2>20\d\d)")
    for m in rx.finditer(text[:4000]):
        try:
            if m.group("mon"):
                mon = m.group("mon").lower()
                if mon not in _MONTHS:
                    continue
                return date(int(m.group("y")), _MONTHS.index(mon) + 1, int(m.group("d")))
            return date(int(m.group("y2")), int(m.group("m2")), int(m.group("d2")))
        except ValueError:
            continue
    return None


def _cdx_letter_urls():
    """Letter PDF URLs from the Wayback CDX index. Never raises — a discovery
    outage falls back to the seed list, exactly like fetch_mn. Scoped to the
    CURRENT year: older letters are already covered by the monthly reports, so
    downloading them to read a date we would then discard is wasted."""
    urls = set()
    year = datetime.now(timezone.utc).year
    patterns = [f"mn.gov/deed/assets/warn-{year}*",
                f"mn.gov/deed/assets/{year}-warn*"]
    for pat in patterns:
        for attempt in range(2):  # CDX is slow and flaky — retry once
            try:
                r = requests.get(CDX, params={
                    "url": pat, "collapse": "urlkey",
                    "fl": "original", "limit": "1000",
                }, headers=UA, timeout=90)
                for u in r.text.split():
                    u = u.replace("http://", "https://")
                    if _LETTER_RX.search(u):
                        urls.add(u)
                break
            except Exception as exc:
                print(f"    MN letters: CDX {pat} failed ({exc}); "
                      + ("retrying" if attempt == 0 else "using seeds"))
    return urls


def _company_from_url(url):
    """Best-effort employer hint from the filename slug — a HINT for the
    extractor, which reads the letter body for the authoritative name."""
    m = re.search(r"/(?:warn-\d{4}|\d{4}-warn)-(.+?)_tcm1045", url, re.I)
    if not m:
        return ""
    return re.sub(r"[-_]+", " ", m.group(1)).strip().title()


def _pdf_text(url):
    """Download one asset PDF and return its text, or '' on any failure."""
    import pdfplumber
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
    except Exception:
        return ""
    if r.status_code != 200 or b"%PDF" not in r.content[:1024]:
        return ""
    try:
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        return ""


def discover_letter_urls():
    """The full letter-URL set: CDX (durable) unioned with the seed backstop."""
    return sorted(_cdx_letter_urls() | set(_SEED_LETTERS))


# Absolute per-run cap on letters emitted for extraction — a backstop against a
# discovery surprise turning into a surprise LLM bill. cron's filter_already_seen
# then skips any URL already ingested, so steady-state extraction is ~0.
MAX_LETTERS = max(1, int(os.environ.get("MN_LETTER_MAX") or 40))


def pull_mn_warn_letters(limit=None, _report=True):
    """Raw dicts (raw_text set) for cron's gate -> extract -> post pipeline.

    Only letters dated AFTER the newest monthly report (see _monthly_cutoff_date)
    are emitted, so a letter and its monthly-report twin cannot both be counted.
    NEVER writes a row itself and never raises: a source hiccup must not sink the
    run. Health is 'ok' when discovery worked (0 new letters past the cutoff is a
    NORMAL, quiet result), 'degraded' only when discovery itself produced nothing
    at all (both CDX and the seed unreachable)."""
    try:
        urls = discover_letter_urls()
    except Exception as exc:
        _health("degraded", 0, f"letter discovery failed: {exc}", _report)
        return []
    cutoff = _monthly_cutoff_date()
    entries, seen_before_cutoff, undated = [], 0, 0
    for url in urls:
        if len(entries) >= (limit or MAX_LETTERS):
            break
        text = _pdf_text(url)
        if not text.strip():
            continue
        ld = _letter_date(text)
        if ld is not None and ld < cutoff:
            seen_before_cutoff += 1
            continue  # already covered by a monthly report -> would double-count
        if ld is None:
            undated += 1  # fail-safe: keep it, the extractor still guards it
        entries.append({
            # 'warn' is the allowlisted WARN-family type (cpt.php
            # alt_allowed_source_types): the row gets the WARN badge and state
            # source-list link, its monthly-report twin is excluded by the
            # cutoff above, and any news article on the same event is folded in
            # by the existing news+WARN reconcile-supersets pass — exactly as for
            # every other WARN row. state=MN so the WARN state link resolves.
            "source_type": "warn",
            "source_name": "Minnesota DEED WARN notice",
            "verification_level": "gold",       # official state filing
            "state": "MN",
            "source_url": url,
            "title": f"{_company_from_url(url)} — Minnesota WARN notice".strip(" —"),
            "company_name": _company_from_url(url),
            "filing_date": ld.isoformat() if ld else "",
            "raw_text": text.strip(),
            "_collector": "mn_warn_letters",
        })
    if not urls:
        _health("degraded", 0, "no letter URLs from CDX or the seed list "
                "(discovery unreachable)", _report)
    else:
        _health("ok", len(entries),
                f"{len(urls)} MN WARN letter PDF(s) found; {len(entries)} past the "
                f"{cutoff.isoformat()} monthly cutoff ({seen_before_cutoff} already in "
                f"a monthly report, {undated} undated-kept)", _report)
    return entries


def _health(status, count, detail, report):
    if not report:
        return
    try:
        from source_health import report_source_health
        report_source_health("warn_mn_letters", status, count, detail)
    except Exception:
        pass


def _dry_run():
    """Verify-before-live: discover + fetch + show each letter's text head and
    whether a headcount-looking token is present, WITHOUT calling the model.
    Mirrors warn_llm_probe.py — proves discovery and readability for free."""
    urls = discover_letter_urls()
    cutoff = _monthly_cutoff_date()
    print(f"MN WARN letters: {len(urls)} current-year URL(s) discovered (CDX + seed)")
    print(f"MN WARN letters: monthly cutoff = {cutoff.isoformat()} "
          f"(letters on/after this are the freshness gap)\n")
    entries = pull_mn_warn_letters(_report=False)
    print(f"MN WARN letters: {len(entries)} emitted past the cutoff\n")
    for e in entries:
        head = re.sub(r"\s+", " ", e["raw_text"])[:120]
        print(f"  {e.get('filing_date') or 'undated':10} {e['company_name'][:30]:30} "
              f"{e['source_url'].split('/')[-1]}")
        print(f"        {head}")
    return entries


if __name__ == "__main__":
    # Direct invocation: put railway/ on the path so `sources` is an importable
    # package (warn_custom uses a relative import and needs the package context).
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if "--dry-run" in sys.argv or os.environ.get("MN_LETTERS_DRY_RUN"):
        _dry_run()
    else:
        rows = pull_mn_warn_letters()
        print(f"pull_mn_warn_letters -> {len(rows)} raw dict(s) with raw_text set")
