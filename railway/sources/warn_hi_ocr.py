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

# Count-extraction patterns, HIGHEST confidence first. We stop at the first that
# matches. "Grand Total" comes from the multi-site "Number of Employees to be
# Laid Off" table; the "to be laid off / affected" phrasings are the affected
# count for partial layoffs; "employed by the establishment ... is N" is the
# affected count for a full closure. Anything else is not trusted.
_COUNT_PATTERNS = [
    ("grand_total", re.compile(r"grand\s+total[^0-9]{0,20}([0-9][0-9,]{0,6})", re.I)),
    ("to_be_laid_off", re.compile(
        r"(?:number\s+of\s+employees|employees)[^0-9]{0,60}?"
        r"(?:to\s+be\s+(?:laid\s+off|terminated|separated)|affected)[^0-9]{0,20}([0-9][0-9,]{0,6})", re.I)),
    ("n_to_be_laid_off", re.compile(
        r"([0-9][0-9,]{0,6})\s+(?:employees|workers|positions)\s+"
        r"(?:will\s+be\s+|are\s+being\s+)?(?:laid\s+off|terminated|separated|affected|impacted)", re.I)),
    ("employed_by_establishment", re.compile(
        r"number\s+of\s+employees\s+employed\s+by\s+the\s+establishment[^0-9]{0,20}"
        r"(?:is|:)?\s*([0-9][0-9,]{0,6})", re.I)),
    ("n_employees_generic", re.compile(
        r"([0-9][0-9,]{0,6})\s+(?:employees|workers)\b", re.I)),
]

_MAX_REASONABLE = 100000


def _to_int(raw: str) -> int:
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def _extract_count(text: str):
    """Return (count, pattern_label) or (0, reason) if no trustworthy count.

    Never guesses: if the only signal is the generic "N employees" phrase and it
    yields more than one DISTINCT value, that is ambiguous -> skip."""
    if not text:
        return 0, "no_ocr_text"
    flat = re.sub(r"\s+", " ", text)
    for label, pat in _COUNT_PATTERNS:
        matches = pat.findall(flat)
        if not matches:
            continue
        vals = sorted({_to_int(m) for m in matches if 0 < _to_int(m) <= _MAX_REASONABLE})
        if not vals:
            continue
        if label == "grand_total":
            return vals[-1], label  # the total, if several numbers matched
        if label == "n_employees_generic" and len(vals) > 1:
            return 0, f"ambiguous_generic({','.join(map(str, vals))})"
        # Explicit phrasings: if multiple, the largest explicit affected figure.
        return vals[-1], label
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
