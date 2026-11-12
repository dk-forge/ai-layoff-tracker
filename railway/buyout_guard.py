"""A voluntary buyout OFFER to N employees is not N job cuts (2026-11-09).

Row 183020 stored "Microsoft offered buyouts to around 60,000 employees" as
60,000 verified cuts. The figure is how many people are ELIGIBLE for a
voluntary programme; how many accept is unknown, so the count describes no
job loss at all. Pure and text-based: no model, no network. A count is
refused only when EVERY sentence holding it reads as an offer or eligibility
and none says the offer was accepted or that jobs are being cut.

2026-11-12: row 183237 re-entered the same 60,000 from a headline about
"employees mulling a buyout" and "buyout packages to some 60,000 employees";
weighing or packaging a buyout is the same offer (tests/test_email_lead_guards).
"""
import re

_OFFER = (r"\b(?:offer(?:s|ed|ing)?|extend(?:s|ed|ing)?|expand(?:s|ed|ing)?)\b[^.;]{0,40}"
          r"\b(?:buy-?outs?|voluntary\s+(?:exit|separation|redundanc\w*|retirement)|"
          r"early[\s-]retirement)\b"
          r"|\b(?:buy-?outs?|voluntary\s+(?:exit|separation|programme|program))\b[^.;]{0,40}"
          r"\b(?:offer(?:s|ed)?|to)\b"
          r"|\b(?:mull\w*|consider\w*|weigh\w*|eye\w*|offer\w*)\s+(?:an?\s+|the\s+)?buy-?outs?\b"
          r"|\bbuy-?out\s+(?:packages?|offers?|deals?)\s+to\b"
          r"|\beligible\b|\belegibles?\b|\bberechtigt\w*\b"
          r"|\bofreci(?:ó|o|endo)\b[^.;]{0,40}\b(?:bajas|retiros)\s+voluntari\w+")
_REAL = (r"\baccept(?:s|ed|ing)?\b|\btook\b|\bsigned\s+up\b|\bwill\s+leave\b"
         r"|\blay(?:s|ing)?\s+off\b|\blaid\s+off\b|\blayoffs?\b|\bjob\s+cuts?\b|\beliminat\w+\b"
         r"|\bcut(?:s|ting)?\s+[\d,.]+\s+(?:jobs|roles|positions|staff)\b"
         r"|\bdismiss\w*\b|\bredundan\w+\b(?![^.;]{0,10}\bscheme)")


def _number_alt(n):
    n = int(n)
    g = f"{n:,}"
    variants = {str(n), g, g.replace(",", "."), g.replace(",", " ")}
    alt = "|".join(re.escape(v) for v in sorted(variants, key=len, reverse=True))
    return rf"(?<![\d.,])(?:{alt})(?![\d])(?![.,]\d{{3}})"


def _clause_around(sentence, start, end, width=60):
    left = sentence[max(0, start - width):start]
    right = sentence[end:end + width]
    # A clause stops at a comma-joined conjunction so "lay off 1,200 after
    # only 300 accepted buyouts" does not lend "accepted" to the 1,200.
    left = re.split(r"\b(?:after|while|but|as|and)\b", left)[-1]
    right = re.split(r"\b(?:after|while|but|and)\b", right)[0]
    return left + right


def count_is_only_an_offer(job_count, raw_text):
    """True when job_count appears only as a buyout offer or eligibility figure."""
    if not job_count or not raw_text:
        return False
    text = re.sub(r"\s+", " ", str(raw_text))
    pattern = _number_alt(job_count)
    seen = False
    for m in re.finditer(pattern, text):
        seen = True
        clause = _clause_around(text, m.start(), m.end())
        if not re.search(_OFFER, clause, re.I) or re.search(_REAL, clause, re.I):
            return False
    return seen
