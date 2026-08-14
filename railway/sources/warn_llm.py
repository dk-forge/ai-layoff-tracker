"""Shared DeepSeek count-fallback for fragile WARN scrapers.

When a scraper's deterministic count parse fails on a row it OTHERWISE has
(company + date come from a stable part of the row, only the count column/regex
is brittle), it can pass that row's ALREADY-ISOLATED text here to recover the
affected count. The model only ever sees one notice's text and returns one
number, accepted only if it appears verbatim in that text (anti-hallucination)
and clears a floor -- so it can recover a real count but never invent one, and
never a company or a row.

Gated behind WARN_LLM_FALLBACK=1 + OPENROUTER_API_KEY; returns 0 otherwise, so
the scraper drops the row exactly as before. Returns 0 (never raises) on any LLM
failure, so it can never break a scrape. Because it fires ONLY when the regex
count is already 0, enabling it can only ADD rows the scraper currently drops --
it cannot change a row that already parsed.
"""
import os
import re

# WARN filings are mass layoffs, so a single-digit recovered count is almost
# always a stray number the model latched onto, not a headcount (matches the HI
# OCR fallback floor). _entry already caps the upper bound at 100000.
_MIN_COUNT = 5
_MAX_COUNT = 100000


def llm_count_from_text(text, label=""):
    """Recover an affected-employee count from one isolated WARN notice's text,
    or 0 if disabled / not confidently present. Never raises."""
    if os.environ.get("WARN_LLM_FALLBACK") != "1" or not os.environ.get("OPENROUTER_API_KEY"):
        return 0
    snippet = re.sub(r"\s+", " ", str(text or ""))[:2000].strip()
    if not snippet:
        return 0
    prompt = (
        "This is one row/notice from a US state WARN mass-layoff filing. Return "
        'ONLY JSON: {"affected": <integer or null>}. "affected" is the number of '
        "employees to be laid off / affected / separated / terminated in THIS "
        "notice -- NOT a total employed, a ZIP code, a year, or a case number. "
        "Return null if no such count is clearly present. The number you return "
        "MUST appear verbatim in the text.\n\nTEXT:\n" + snippet
    )
    try:
        import spend
        from extractor import _get_client, _parse_json_response, MODEL
        resp = spend.metered_call(MODEL, lambda: _get_client().chat.completions.create(
            model=MODEL, max_tokens=40, temperature=0,
            messages=[{"role": "user", "content": prompt}],
        ), what="a WARN count recovery")
        data = _parse_json_response(resp.choices[0].message.content or "")
        v = int(data.get("affected"))
    except Exception:
        return 0
    if not (_MIN_COUNT <= v <= _MAX_COUNT):
        return 0
    # Anti-hallucination: the number must actually appear in the row's text.
    if str(v) not in snippet and f"{v:,}" not in snippet:
        return 0
    # A recovery means the deterministic parser missed a real count -- log it so
    # the workflow run surfaces both the win and a hint the parser has drifted.
    print(f"    ::notice:: [warn-llm-fallback] {label or 'row'}: recovered count {v}")
    return v
