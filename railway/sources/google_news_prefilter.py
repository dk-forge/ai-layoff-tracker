"""Free, deterministic title prefilter for the BROAD Google News sweeps.

WHY THIS EXISTS (cost trim, 2026-09-28).

A broad discovery query ("layoffs" OR "restructuring" ...) is matched by Google
against the article BODY, so an edition returns many items whose headline is
about something else: merger announcements, earnings, a CEO interview that
mentions a restructuring once. Every one of those used to buy a pre-extraction
gate call and often a full extraction. The headline is where Google News puts
the headcount ("Oracle fires 21,000 employees", "Meta to cut 8,000 jobs"), so a
headline that names no reduction at all is a poor candidate.

What this keeps: a title that carries a reduction term IN THE EDITION'S OWN
LANGUAGE. It does not decide what is stored -- the gate and the extractor still
rule on every kept item.

THE VOCABULARY IS NOT WRITTEN HERE. It is read from the tables the other
collectors already share, so they cannot drift apart:

  English     sources/regional_feeds.EN_TERMS / EN_PATTERNS / PAIRED_TERMS
              (via regional_feeds.relevance), plus HEADCOUNT_PATTERN below:
              the verb + figure + workforce-noun shape of a headline
              ("cuts up to 600 customer support jobs", "may slash 20,000
              roles", "to cut thousands of jobs"), which a bare term list
              cannot see. It is a SHAPE, not a new term list.
  other       sources/native_layoff_terms.PHRASES_BY_LANG, the one worldwide
              table the Google News queries themselves are built from.

LANGUAGE MATCH. A non-English edition keeps only a title carrying one of its own
language's phrases, so an English wire headline surfacing in the German edition
(a duplicate of the US pull) is dropped. A script check backs this up for the
non-Latin languages, and an English edition refuses a title that is mostly in
another script.

Company-chase queries and explicit caller queries are NOT filtered (see
google_news.pull_google_news): a chase is already scoped to one employer and
its callers read the rows for their own purposes.

Switch off with GOOGLE_NEWS_PREFILTER=off (no deploy; env only).
"""
from __future__ import annotations

import os
import re
import unicodedata

from sources import native_layoff_terms as _native
from sources import regional_feeds as _regional

# Verb, up to five short words (a figure, "up to", "thousands of", an
# adjective), then a workforce noun. Anchored on word boundaries so "shed"
# never matches "finished", and bounded so it cannot span a whole paragraph.
HEADCOUNT_PATTERN = re.compile(
    r"\b(?:cut|cuts|cutting|slash|slashes|slashing|axe|axes|axing|axed|"
    r"shed|sheds|shedding|fire|fires|fired|firing|eliminate|eliminates|"
    r"eliminating|eliminated|trim|trims|trimming|lay|lays|laying|"
    r"let go|lets go|dismiss|dismisses|dismissing)"
    r"(?:\s+[\w,.%'’-]+){0,5}?\s+"
    r"(?:jobs?|employees|workers|staff|staffers|roles|positions|"
    r"workforce|headcount|people)\b"
    r"|\bjob\s+loss(?:es)?\b|\bworkforce\s+cuts?\b",
    re.I)

# Scripts a language is written in, for the non-Latin editions. A title in the
# Japanese edition must contain Japanese script, and so on.
_SCRIPT_OF_LANG = {
    "ja": ("CJK", "HIRAGANA", "KATAKANA"),
    "zh": ("CJK",),
    "ko": ("HANGUL",),
    "th": ("THAI",),
    "ar": ("ARABIC",),
    "ru": ("CYRILLIC",),
}


def enabled() -> bool:
    return (os.environ.get("GOOGLE_NEWS_PREFILTER", "on") or "").strip().lower() \
        not in ("off", "0", "false", "no")


def _letters(title):
    return [ch for ch in title if ch.isalpha()]


def _latin_share(title):
    letters = _letters(title)
    if not letters:
        return 0.0
    latin = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
    return latin / len(letters)


def _has_script(title, scripts):
    return any(any(s in unicodedata.name(ch, "") for s in scripts)
               for ch in _letters(title))


def language_matches(title: str, hl: str) -> bool:
    lang = _native.language_of_hl(hl)
    if _native.is_english_hl(hl):
        return _latin_share(title) >= 0.8
    scripts = _SCRIPT_OF_LANG.get(lang)
    if scripts:
        return _has_script(title, scripts)
    # Latin-script languages: the native-phrase match below is itself the
    # language check (an English headline carries no German phrase).
    return _latin_share(title) >= 0.8


def title_verdict(title: str, hl: str) -> tuple[bool, str]:
    """(keep, why) for one headline in one edition. Never raises."""
    title = str(title or "")
    if not title.strip():
        return False, "empty-title"
    if not language_matches(title, hl):
        return False, "language-mismatch"
    if _native.is_english_hl(hl):
        keep, why = _regional.relevance(title, "")
        if keep:
            return True, why
        if HEADCOUNT_PATTERN.search(title):
            return True, "pattern:headcount"
        return False, "no-layoff-term"
    low = title.lower()
    lang = _native.language_of_hl(hl)
    for phrase in _native.PHRASES_BY_LANG.get(lang, ()):
        if phrase.lower() in low:
            return True, f"term:{lang}:{phrase}"
    return False, "no-layoff-term"
