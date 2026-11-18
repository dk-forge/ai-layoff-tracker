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

from buyout_guard import _number_alt

_NEGATION = (
    # "not related to / not linked to / not due to / has nothing to do with N cuts"
    r"\b(?:not|n't|never)\s+(?:\w+\s+){0,2}(?:related|linked|connected|due|tied|"
    r"attributable|caused|because)\b"
    r"|\bnothing\s+to\s+do\s+with\b|\bunrelated\s+to\b"
    # "denies / denied / refutes / rejects reports of N layoffs"
    r"|\b(?:den(?:y|ies|ied|ying)|denials?|refut\w+|debunk\w*)\b"
    r"|\b(?:rejects?|rejected|dismiss(?:es|ed)?)\s+(?:the\s+)?(?:reports?|claims?|rumou?rs?|speculation)\b"
    r"|\brul(?:es|ed|ing)\s+out\b"
    # "no layoffs (are) planned", "no plans to cut", "not planning layoffs"
    r"|\bno\s+(?:plans?\s+(?:for|to)\s+)?(?:\w+\s+){0,2}(?:layoffs?|job\s+cuts?|redundanc\w+|lay\s?offs?)\b"
    r"|\b(?:layoffs?|job\s+cuts?|redundanc\w+)\s+(?:are\s+|is\s+)?not\s+(?:planned|expected|happening)\b"
    r"|\bnot\s+(?:planning|considering)\s+(?:any\s+)?(?:layoffs?|job\s+cuts?)\b"
    r"|\b(?:false|fake|untrue|baseless)\s+(?:reports?|claims?|rumou?rs?)\b")
# A confirmation counts only when it GOVERNS a cut: "confirmed 800 job cuts",
# "announced it will cut 500 jobs". "confirmed no layoffs" governs a denial.
_CONFIRM = (r"\b(?:confirm(?:s|ed|ing)?|announc(?:e|es|ed|ing))\s+(?:that\s+)?"
            r"(?:(?:it|the\s+company)\s+(?:will|would|is\s+going\s+to)\s+)?"
            r"(?:(?:cut|cutting|eliminat\w*|lay(?:ing)?\s+off|shed\w*)\b"
            r"|(?:about\s+|some\s+|around\s+)?[\d][\d,.]*\s+(?:job\s+cuts?|lay-?\s?offs?|jobs|roles|positions|redundanc\w+))")

HOLD = "hold"
PASS = "pass"


def negation_verdict(job_count, raw_text):
    """HOLD when a negation cue shares a sentence with the count.

    Not a drop and not a publish (2026-11-18 design, PR #691): a regex cannot
    tell "not related to 60,000 job cuts" from "cut 500 jobs, not related to
    AI" reliably, so both go to review instead of either side being decided
    here. A missed denial and a false denial are both held, never lost and
    never published. The whole sentence is the context, count included; a
    neighbouring sentence never lends its negation ("Acme cut 500 jobs. No
    layoffs are planned next year." passes). A confirmation that governs a cut
    verb or noun in the same sentence passes ("After weeks of denials, Acme
    confirmed 800 job cuts").
    """
    if not job_count or not raw_text:
        return PASS
    text = re.sub(r"\s+", " ", str(raw_text))
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not re.search(_number_alt(job_count), sentence):
            continue
        if re.search(_NEGATION, sentence, re.I) and not re.search(_CONFIRM, sentence, re.I):
            return HOLD
    return PASS


def count_is_negated(job_count, raw_text):
    """Back-compat name: True when the count must be held for review."""
    return negation_verdict(job_count, raw_text) == HOLD
