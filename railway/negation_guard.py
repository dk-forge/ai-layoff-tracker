"""A headline that DENIES or disowns a cut is not that cut (2026-11-18).

Row 183489 stored Microsoft 60,000 jobs on 2026-11-13 from a Syracuse.com
headline: "Outlook down: Microsoft says outage cause is not related to 60,000
job cuts". The buyout guard let it through because "job cuts" reads as a real
cut, and nothing asked whether the sentence was saying the opposite. It was
the third time the same buyout-eligibility pool entered as a layoff (183020,
183237, 183489) and it inflated the week, month and year totals.

Pure and text-based, like buyout_guard: a count is refused only when EVERY
clause holding it negates, denies or disowns the cut, and none confirms one.
"""
import re

from buyout_guard import _clause_around, _number_alt

_NEGATION = (
    # "not related to / not linked to / not due to / has nothing to do with N cuts"
    r"\b(?:not|n't|never)\s+(?:\w+\s+){0,2}(?:related|linked|connected|due|tied|"
    r"attributable|caused|because)\b"
    r"|\bnothing\s+to\s+do\s+with\b|\bunrelated\s+to\b"
    # "denies / denied / refutes / rejects reports of N layoffs"
    r"|\b(?:den(?:y|ies|ied|ying)|refut\w+|deny\w*|debunk\w*)\b"
    r"|\b(?:rejects?|rejected|dismiss(?:es|ed)?)\s+(?:the\s+)?(?:reports?|claims?|rumou?rs?|speculation)\b"
    r"|\brul(?:es|ed|ing)\s+out\b"
    # "no layoffs (are) planned", "no plans to cut", "not planning layoffs"
    r"|\bno\s+(?:plans?\s+(?:for|to)\s+)?(?:\w+\s+){0,2}(?:layoffs?|job\s+cuts?|redundanc\w+|lay\s?offs?)\b"
    r"|\b(?:layoffs?|job\s+cuts?|redundanc\w+)\s+(?:are\s+|is\s+)?not\s+(?:planned|expected|happening)\b"
    r"|\bnot\s+(?:planning|considering)\s+(?:any\s+)?(?:layoffs?|job\s+cuts?)\b"
    r"|\b(?:false|fake|untrue|baseless)\s+(?:reports?|claims?|rumou?rs?)\b")
_CONFIRM = (r"\bconfirm(?:s|ed|ing)?\b|\bwill\s+(?:lay\s+off|cut|eliminate)\b"
            r"|\b(?:laid|lays|laying)\s+off\b|\bis\s+cutting\b|\bannounced\b")


def count_is_negated(job_count, raw_text):
    """True when job_count appears only in clauses that deny or disown the cut."""
    if not job_count or not raw_text:
        return False
    text = re.sub(r"\s+", " ", str(raw_text))
    seen = False
    for m in re.finditer(_number_alt(job_count), text):
        seen = True
        clause = _clause_around(text, m.start(), m.end())
        if not re.search(_NEGATION, clause, re.I) or re.search(_CONFIRM, clause, re.I):
            return False
    return seen
