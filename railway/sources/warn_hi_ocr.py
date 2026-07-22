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
# The recurring failure mode (calibrated against verified notices) is grabbing
# TOTAL employed instead of AFFECTED. WARN letters say "X employees work at /
# employs Y ... Z affected/separated" — the real count is the one tied to a
# layoff verb, not the workforce total. So we classify each number by its nearest
# cue and trust the affected one; a lone total is used only for a full closure.

# A candidate number is only a headcount if an employee-unit word sits near it.
_EMP_UNIT = re.compile(r"employe|workers|positions|associates|staff|personnel|jobs", re.I)
# Cues that mark a number as the AFFECTED count (the thing we want).
_AFFECTED_CTX = re.compile(
    r"separat|laid\s*off|lay\s*off|layoff|terminat|affected|impact|displac|eliminat"
    r"|ending\s+their\s+employ|let\s+go", re.I)
# Cues that mark a number as a TOTAL workforce figure (NOT affected).
_TOTAL_CTX = re.compile(
    r"work(?:s|ing|ed)?\s+(?:at|for)|currently\s+employ|\bemploys\b|employed\s+by"
    r"|workforce|of\s+whom|on\s+staff|currently\s+has|headcount", re.I)
# Full-shutdown markers: for a closure, the total workforce IS the affected count.
_CLOSURE = re.compile(
    r"permanent|entire\s+facility|clos(?:e|ing|ure)|shut(?:ting| down)"
    r"|cease\s+operations|all\s+(?:of\s+its\s+)?employees\s+will", re.I)
# High-confidence airline/large-employer phrasing: "N of them ... separated".
_OF_THEM = re.compile(
    r"(\d[\d,]{0,6})\s+of\s+(?:them|these|which|whom)\s+(?:are|will\s+be|is|were)?\s*"
    r"(?:anticipated|expected|projected)?\s*(?:to\s+be\s+)?"
    r"(?:separat|laid\s*off|terminat|affected|impact|let\s+go)", re.I)
# Full-closure WARN form field: "employed by the establishment is N".
_ESTAB = re.compile(
    r"employed\s+by\s+the\s+establishment[^0-9]{0,25}(?:is|:)?\s*(\d[\d,]{0,6})", re.I)
# "total number of (potentially) affected employees is N" — the stated grand
# figure, trusted over the redacted per-line breakdown numbers around it.
_TOTAL_AFFECTED = re.compile(
    r"total\s+number\s+of\s+(?:potentially\s+)?affected\s+(?:employees|workers)\s+is\b"
    r"[^0-9]{0,25}(\d[\d,]{0,6})", re.I)
# "N employees are/will be ... affected/laid off" — one explicit affected clause.
_N_AFFECTED = re.compile(
    r"(\d[\d,]{0,6})\s+(?:employees|workers|positions)\s+"
    r"(?:are\s+|will\s+be\s+|is\s+)?(?:expected\s+to\s+be\s+|anticipated\s+to\s+be\s+)?"
    r"(?:affected|laid\s*off|terminated|separated|impacted|eliminated)", re.I)
# A numeric token not glued to another number / decimal / currency.
_NUM_TOKEN = re.compile(r"(?<![\d.,$])(\d[\d,]{0,6})(?![\d.])")

# A count above this is unusual for a single Hawaii notice, so we trust it ONLY
# from a structurally unambiguous pattern (an explicit Grand Total or an "N of
# them separated" summary). A big number from any softer signal is far more
# likely an OCR misread (a permit/address/phone number) than a real HI layoff —
# and a genuinely large one reaches the tracker via SEC/news — so we flag it for
# review instead of posting. (Caught the phantom "Honolulu Roofing 754".)
_HI_OUTLIER = 500
_TRUSTED_LABELS = {"grand_total", "of_them_separated", "total_affected"}
# WARN notices are mass-layoff filings, so a single-digit affected count from the
# LLM fallback is almost always a stray small number the model latched onto (a
# section/date fragment) rather than a real headcount — the anti-hallucination
# check can't catch that (the number IS in the text), so a floor does. The
# trusted regex set bottoms out at 5, so 5 is the plausibility floor.
_LLM_MIN_COUNT = 5


def _to_int(raw: str) -> int:
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def _candidate_numbers(flat: str):
    """Yield (value, start, end) for numeric tokens that aren't obvious non-counts
    (ZIP codes, years, dollar amounts, percentages)."""
    for nm in _NUM_TOKEN.finditer(flat):
        raw = nm.group(1)
        v = _to_int(raw)
        if not (0 < v <= _MAX_REASONABLE):
            continue
        digits = raw.replace(",", "")
        if len(digits) == 5:                        # ZIP code
            continue
        if len(digits) == 4 and 1990 <= v <= 2035:  # a year, not a headcount
            continue
        s, e = nm.start(1), nm.end(1)
        if s > 0 and flat[s - 1] == "$":            # dollar amount
            continue
        if e < len(flat) and flat[e] == "%":        # percentage
            continue
        yield v, s, e


def _classify(low: str, s: int, e: int):
    """Classify a number as 'aff' (affected) or 'tot' (workforce total) by its
    nearest cue — cues AFTER the number (within 90 chars) or just BEFORE (45)."""
    best = (9999, None)
    for pat, cls in ((_AFFECTED_CTX, "aff"), (_TOTAL_CTX, "tot")):
        for m in pat.finditer(low):
            if e <= m.start() <= e + 90:
                d = m.start() - e
            elif s - 45 <= m.end() <= s:
                d = s - m.end()
            else:
                continue
            if d < best[0]:
                best = (d, cls)
    return best[1]


def _extract_raw(text: str):
    """Best (count, label) before the outlier guard. Priority: (1) multi-site
    "Grand Total"; (2) "N of them ... separated"; (3) "total number of affected
    employees is N"; (4) full-closure "employed by the establishment is N"; (5)
    one explicit "N employees ... affected" clause; (6) classify each nearby
    number as affected vs workforce-total and trust the affected one; (7) for a
    full closure with no explicit affected number, the single total is the count.
    Never guesses: multiple distinct affected values, or a bare total outside a
    closure, are skipped (the affected count is the one tied to a layoff verb,
    never the 'X employees work here' workforce figure)."""
    flat = re.sub(r"\s+", " ", text)
    low = flat.lower()

    m = re.search(r"grand\s+total[^0-9]{0,20}(\d[\d,]{0,6})", flat, re.I)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "grand_total"

    m = _OF_THEM.search(flat)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "of_them_separated"

    m = _TOTAL_AFFECTED.search(flat)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "total_affected"

    m = _ESTAB.search(flat)
    if m and _CLOSURE.search(low) and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "establishment_closure"

    m = _N_AFFECTED.search(flat)
    if m and 0 < _to_int(m.group(1)) <= _MAX_REASONABLE:
        return _to_int(m.group(1)), "n_affected"

    affected, total = [], []
    for v, s, e in _candidate_numbers(flat):
        if not _EMP_UNIT.search(low[max(0, s - 60):min(len(low), e + 60)]):
            continue
        cls = _classify(low, s, e)
        if cls == "aff":
            affected.append(v)
        elif cls == "tot":
            total.append(v)

    if affected:
        vals = sorted(set(affected))
        if len(vals) > 1:
            return 0, f"ambiguous_affected({','.join(map(str, vals))})"
        return vals[0], "affected"
    if _CLOSURE.search(low) and total:
        vals = sorted(set(total))
        if len(vals) == 1:
            return vals[0], "closure_total"
        return 0, f"closure_multi_total({','.join(map(str, vals))})"
    return 0, "no_affected_count"


def _extract_count(text: str):
    """Return (count, label) with a final outlier guard: a count above
    _HI_OUTLIER is trusted only from a structurally unambiguous pattern; any
    softer signal that large is flagged for review, not posted."""
    if not text:
        return 0, "no_ocr_text"
    v, label = _extract_raw(text)
    if v > _HI_OUTLIER and label not in _TRUSTED_LABELS:
        return 0, f"outlier_review({v},{label})"
    return v, label


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


def _llm_affected_count(text: str):
    """DeepSeek fallback for notices the deterministic extractor skipped.

    Asks the model for the AFFECTED count and accepts it ONLY if that exact
    number appears verbatim in the OCR text (anti-hallucination), so it can
    recover a value but never invent one. Gated: returns (0, reason) unless
    HI_LLM_FALLBACK=1 and OPENROUTER_API_KEY are set. Lazy imports keep the
    module import-safe without the LLM stack."""
    import os
    if os.environ.get("HI_LLM_FALLBACK") != "1" or not os.environ.get("OPENROUTER_API_KEY"):
        return 0, "llm_disabled"
    snippet = re.sub(r"\s+", " ", text)[:4000].strip()
    if not snippet:
        return 0, "llm_no_text"
    prompt = (
        "This is the OCR'd text of a WARN layoff notice. Return ONLY JSON: "
        '{"affected": <integer or null>}. "affected" is the number of employees '
        "to be LAID OFF / affected / separated / terminated - NOT the total "
        "employed by the establishment, UNLESS the notice is a full permanent "
        "closure (then they are the same). If a per-site table has a grand total, "
        "use that total. If no affected count is clearly stated, return null. The "
        "number you return MUST appear verbatim in the text.\n\nTEXT:\n" + snippet
    )
    try:
        from extractor import _get_client, _parse_json_response, MODEL
        resp = _get_client().chat.completions.create(
            model=MODEL, max_tokens=40, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        data = _parse_json_response(resp.choices[0].message.content or "")
    except Exception as exc:
        return 0, f"llm_error({str(exc)[:40]})"
    v = data.get("affected") if isinstance(data, dict) else None
    try:
        v = int(v)
    except (TypeError, ValueError):
        return 0, "llm_null"
    if not (0 < v <= _MAX_REASONABLE):
        return 0, "llm_out_of_range"
    if v < _LLM_MIN_COUNT:
        return 0, f"llm_implausibly_small({v})"
    if str(v) not in snippet and f"{v:,}" not in snippet:
        return 0, f"llm_not_in_text({v})"
    return v, "llm_fallback"


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
            # Deterministic extractor skipped it — try the constrained LLM
            # fallback (no-op unless enabled). Only accepts a number present in
            # the text, so it recovers coverage without inventing a figure.
            lv, llabel = _llm_affected_count(text)
            if lv > 0:
                count, label = lv, llabel
            else:
                skipped.append((date, company, url, f"{label}|{llabel}"))
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
