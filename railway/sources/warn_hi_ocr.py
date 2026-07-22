"""Hawaii WARN — OCR path (DORMANT until verified via the dry-run workflow).

Hawaii's WDC posts each WARN notice as an IMAGE-SCAN PDF (no text layer), so the
affected-employee count exists only as pixels. The list page carries no count.
This module recovers the count by rendering each notice PDF (pypdfium2) and
running OCR (tesseract via pytesseract), then extracting the headcount with a
priority list of explicit phrasings — and SKIPPING anything ambiguous rather
than guessing (the house rule: never invent a number).

Every emitted row keeps its source-PDF URL, so the number is always auditable.

DORMANT: this is NOT wired into the live warn_import pipeline. It runs only via
`railway/hi_warn_dryrun.py` (and the manual `hi-warn-dryrun` workflow, which
installs tesseract) so a human can eyeball the extracted counts before it is
promoted to live. All OCR imports are lazy so importing this module never fails
in an environment without pytesseract/tesseract.
"""
from __future__ import annotations

import re

import requests

from .warn_custom import _entry
from .warn_new_states import (
    UA, TIMEOUT, _HI_YEAR_URL, _HI_ENTRY_RE, _iso, _hi_clean,
)

_MAX_REASONABLE = 100000
# A single Hawaii notice above this is unusual enough that we trust it ONLY from
# the strongest explicit signals (grand total, or "employed by the establishment
# is N" for a full closure). A big number from weaker context is far more likely
# OCR noise than a real HI layoff — and any genuinely huge one reaches the tracker
# via SEC/news anyway — so we flag it for review instead of auto-posting.
_HI_OUTLIER = 1000

# A candidate number is only a headcount if an employee-unit word sits next to it.
_EMP_UNIT = re.compile(
    r"\b(?:employees|workers|positions|associates|staff|personnel|team\s*members)\b", re.I)
# Layoff language in the window promotes a candidate from "generic" to "affected".
_LAYOFF_CTX = re.compile(
    r"affect|laid\s*off|lay\s*off|layoff|terminat|separat|impact|displac|reduc|to\s+be\b|eliminat", re.I)
# Numeric token that is not glued to another number / decimal / currency.
_NUM_TOKEN = re.compile(r"(?<![\d.,$])(\d[\d,]{0,6})(?![\d.])")


def _to_int(raw: str) -> int:
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def _candidate_numbers(flat: str):
    """Yield (value, start) for numeric tokens that aren't obvious non-counts
    (ZIP codes, years, dollar amounts)."""
    for nm in _NUM_TOKEN.finditer(flat):
        raw = nm.group(1)
        v = _to_int(raw)
        if not (0 < v <= _MAX_REASONABLE):
            continue
        digits = raw.replace(",", "")
        if len(digits) == 5:                       # ZIP code
            continue
        if len(digits) == 4 and 1990 <= v <= 2035:  # a year, not a headcount
            continue
        s = nm.start(1)
        if s > 0 and flat[s - 1] == "$":            # dollar amount
            continue
        yield v, s, nm.end(1)


def _extract_count(text: str):
    """Return (count, pattern_label) or (0, reason) if no trustworthy count.

    Priority: (1) an explicit multi-site "Grand Total"; (2) a full-closure
    "employed by the establishment is N"; (3) a number sitting beside an
    employee-unit word, preferring one whose window also carries layoff language.
    Never guesses: bare "N employees" is trusted only when there is a SINGLE
    distinct candidate, and any count above _HI_OUTLIER from a non-explicit
    signal is flagged for review rather than posted."""
    if not text:
        return 0, "no_ocr_text"
    flat = re.sub(r"\s+", " ", text)

    m = re.search(r"grand\s+total[^0-9]{0,20}(\d[\d,]{0,6})", flat, re.I)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "grand_total"

    m = re.search(r"employed\s+by\s+the\s+establishment[^0-9]{0,25}(?:is|:)?\s*(\d[\d,]{0,6})", flat, re.I)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "employed_by_establishment"

    low = flat.lower()
    strong, weak = [], []
    for v, s, e in _candidate_numbers(flat):
        win = low[max(0, s - 70):min(len(low), e + 70)]
        if not _EMP_UNIT.search(win):
            continue
        (strong if _LAYOFF_CTX.search(win) else weak).append(v)

    if strong:
        v = sorted(set(strong))[-1]
        if v > _HI_OUTLIER:
            return 0, f"outlier_needs_review({v})"
        return v, "affected_context"
    if weak:
        vals = sorted(set(weak))
        if len(vals) > 1:
            return 0, f"ambiguous_generic({','.join(map(str, vals))})"
        if vals[0] > _HI_OUTLIER:
            return 0, f"outlier_needs_review({vals[0]})"
        return vals[0], "generic_single"
    return 0, "no_count_pattern"


def _ocr_pdf(content: bytes, max_pages: int = 4) -> str:
    """Render the first few pages and OCR them. Lazy imports so this module is
    safe to import without OCR deps installed."""
    import pypdfium2 as pdfium
    import pytesseract

    out = []
    pdf = pdfium.PdfDocument(content)
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            page = pdf[i]
            bitmap = page.render(scale=300 / 72)  # ~300 DPI, good for clean scans
            pil = bitmap.to_pil()
            out.append(pytesseract.image_to_string(pil))
    finally:
        pdf.close()
    return "\n".join(out)


def _hi_notices(years):
    """Yield (date_iso, company, pdf_url) from the HI per-year listing pages."""
    for year in years:
        url = _HI_YEAR_URL.format(year=year)
        try:
            resp = requests.get(url, headers=UA, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            html_text = re.sub(r"<script.*?</script>", "", resp.text, flags=re.S | re.I)
        except Exception as exc:
            print(f"    HI {year}: listing failed ({exc})")
            continue
        for m in _HI_ENTRY_RE.finditer(html_text):
            date = _iso(_hi_clean(m.group(1)))
            company = _hi_clean(m.group(3))
            href = (m.group(2) or "").strip()
            if not (date and company and href):
                continue
            yield date, company, href


def fetch_hi_ocr(years=None, limit=None, dry_run=False):
    """OCR each Hawaii notice PDF and emit a countable WARN entry.

    dry_run=True prints a reviewable table (date, company, count, pattern, url)
    and does not require any posting context. Returns the list of `_entry` dicts
    for notices where a trustworthy count was found; ambiguous/absent counts are
    skipped and (in dry-run) reported so a human can judge accuracy."""
    from datetime import date as _date
    if years is None:
        y = _date.today().year
        years = sorted({y - 1, y, y + 1})
    out, skipped = [], []
    seen_urls = set()
    for date, company, url in _hi_notices(years):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            resp = requests.get(url, headers=UA, timeout=TIMEOUT)
            if resp.status_code != 200 or not resp.content[:4] == b"%PDF":
                skipped.append((date, company, url, f"pdf_unreachable({resp.status_code})"))
                continue
            text = _ocr_pdf(resp.content)
        except Exception as exc:
            skipped.append((date, company, url, f"ocr_failed({exc})"))
            continue
        count, label = _extract_count(text)
        if count <= 0:
            skipped.append((date, company, url, label))
            continue
        e = _entry("HI", company, count, date, detail_url=url)
        if e:
            e["_ocr_pattern"] = label  # dry-run diagnostic only; ignored by /bulk
            out.append(e)
        if limit and len(out) >= limit:
            break

    if dry_run:
        print(f"\n=== HAWAII WARN OCR DRY-RUN — {len(out)} extracted, {len(skipped)} skipped ===")
        print(f"{'DATE':<12} {'COUNT':>6}  {'PATTERN':<26} COMPANY")
        for e in out:
            print(f"{e['layoff_date']:<12} {e['job_count']:>6}  {e.get('_ocr_pattern',''):<26} {e['company_name'][:40]}")
            print(f"{'':<12} {'':>6}  source: {e['source_url']}")
        if skipped:
            print(f"\n--- skipped (no trustworthy count — never guessed) ---")
            for date, company, url, why in skipped:
                print(f"{date:<12} {company[:38]:<40} {why}")
    return out


if __name__ == "__main__":
    # Manual dry-run entry point (see railway/hi_warn_dryrun.py for the runner).
    fetch_hi_ocr(dry_run=True)
