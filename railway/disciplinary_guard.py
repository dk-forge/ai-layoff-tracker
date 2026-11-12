"""Officers or staff dismissed for misconduct are not job cuts (2026-11-12).

Row 183367 led the 2026-11-12 daily edition with "1,562 officers who were
dismissed from their positions, during an internal cleansing drive": a police
force disciplining its own officers. A layoff is an employer removing jobs; a
disciplinary dismissal removes a person and the post stays. Pure and
text-based, like buyout_guard: a count is refused only when EVERY clause
holding it reads as discipline and none names an economic reason.
"""
import re

from buyout_guard import _clause_around, _number_alt

_DISCIPLINE = (r"\bpenali[sz]\w*|\bmisconduct\b|\bdisciplin\w*|\bcleans(?:e|ing)\s+(?:drive|campaign|operation)"
               r"|\binternal\s+cleans\w*|\bcorrupt\w*|\bdrug\s+(?:test|use)\w*|\bAWOL\b"
               r"|\babsen(?:t|ce)\s+without\s+(?:official\s+)?leave\b|\bdereliction\b"
               r"|\bgrave\s+offen[cs]es?\b|\bsanction(?:s|ed)\b|\bunethical\b|\bfraudulent\b")
_ECONOMIC = (r"\brestructur\w*|\bcost[\s-]?(?:cut\w*|saving\w*|s\b|reduction)|\bto\s+cut\s+costs\b"
             r"|\blay(?:s|ing)?\s+off\b|\blaid\s+off\b|\blayoffs?\b|\bredundan\w+"
             r"|\bjob\s+cuts?\b|\bworkforce\s+reduction|\bclos(?:e|es|ed|ing|ure)\b"
             r"|\bdownsiz\w*|\bbudget\b")


def count_is_disciplinary(job_count, raw_text):
    """True when job_count appears only beside disciplinary-dismissal language."""
    if not job_count or not raw_text:
        return False
    text = re.sub(r"\s+", " ", str(raw_text))
    seen = False
    for m in re.finditer(_number_alt(job_count), text):
        seen = True
        clause = _clause_around(text, m.start(), m.end(), width=120)
        if not re.search(_DISCIPLINE, clause, re.I) or re.search(_ECONOMIC, clause, re.I):
            return False
    return seen
