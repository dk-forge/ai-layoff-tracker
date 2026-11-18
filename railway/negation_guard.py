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


_CUT = r"(?:lay-?\s?offs?|job\s+cuts?|cuts?|redundanc\w+|job\s+losses|dismissals?)"


def _denies_the_cut(clause, job_count):
    """The denial must TARGET the cut or the count, never only its cause.

    "not related to 60,000 job cuts" and "denies layoffs" deny the cut;
    "cut 500 jobs, not related to AI" denies a cause and the cut stands
    (Codex P2 on PR #691). A cue counts only when the count or a cut noun
    follows it within a few words, or it already names the cut itself.
    """
    target = r"(?:" + _number_alt(job_count) + r"|\b" + _CUT + r"\b)"
    for m in re.finditer(_NEGATION, clause, re.I):
        if re.search(r"\b" + _CUT + r"\b", m.group(0), re.I):
            return True
        if re.match(r"[^.;]{0,30}?" + target, clause[m.end():], re.I):
            return True
    return False


def count_is_negated(job_count, raw_text):
    """True when job_count appears only in clauses that deny or disown the cut."""
    if not job_count or not raw_text:
        return False
    text = re.sub(r"\s+", " ", str(raw_text))
    seen = False
    # The context is the SENTENCE holding the count, never its neighbour:
    # "Acme cut 500 jobs. No layoffs are planned next year." is a real cut.
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        for m in re.finditer(_number_alt(job_count), sentence):
            seen = True
            clause = _clause_around(sentence, m.start(), m.end())
            if not _denies_the_cut(clause, job_count) or re.search(_CONFIRM, clause, re.I):
                return False
    return seen
