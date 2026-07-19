"""Reviewable Japanese/Korean layoff-language vocabulary and detector.

This module is the evidence-only language gate for the EDINET (Japan) and
OpenDART (South Korea) document stages.  It is deliberately pure: no network
calls, no LLM, no tracker writes.  Given already-extracted filing text it
returns term matches with bounded excerpts so a human/agent reviewer can see
exactly why a filing was flagged.  A match is NEVER an event; extraction and
review decide that later.

Vocabulary provenance (researched 2026-07-18, kept deliberately small and
tiered so every term can be reviewed):

Japanese ``strong`` terms map to the disclosure/legal vocabulary of workforce
reductions.  The Tokyo Stock Exchange's timely-disclosure category for these
events is 人員削減等の合理化 ("rationalisation such as workforce reduction"),
and Japanese employment-law practice distinguishes 整理解雇 (economic-dismissal
layoff), 希望退職 (solicited voluntary retirement, usually disclosed as
希望退職者の募集), 早期退職 (early-retirement solicitation) and 退職勧奨
(individually encouraged resignation).  All were observed verbatim in 2025-2026
EDINET filings (see railway/tests/fixtures/official_filings_manifest.json).

Korean ``strong`` terms are the parallel disclosure/legal set: 정리해고
(economic-dismissal layoff), 희망퇴직 (voluntary retirement programme),
명예퇴직 (honorary/early retirement), 권고사직 (recommended resignation),
인력감축/인원감축 (workforce/headcount reduction) and the statutory phrase
경영상 해고 (dismissal for managerial reasons).

``context`` terms are real restructuring vocabulary that is NOT sufficient
alone, with observed false-positive evidence:

- 구조조정 appears inside statute names (기업구조조정 촉진법), debt
  restructuring and business-line divestment text with no workforce event.
- Korean 감축 compounds freely (재고감축 inventory cuts, 부채비율 감축 debt
  ratio cuts, 인플레이션 감축법 the US Inflation Reduction Act), so only the
  full compounds 인력감축/인원감축 are strong and bare 감원 is context with a
  Hangul-boundary guard.
- Japanese 構造改革 appears in incentive-plan/governance boilerplate, and
  リストラ can mean asset restructuring (リストラクチャリング).

A document is a review candidate only when at least one strong term matches.
Context-only matches are returned for reviewer statistics but do not flag.
"""
from __future__ import annotations

import html as _html
import re
import unicodedata
from dataclasses import dataclass


# --- Reviewable vocabulary (edit only with fixture evidence) ----------------

STRONG_TERMS_JA: tuple[str, ...] = (
    "整理解雇",    # economic-dismissal layoff
    "希望退職",    # solicited voluntary retirement (希望退職者の募集)
    "早期退職",    # early-retirement solicitation (see review note on 制度)
    "退職勧奨",    # encouraged resignation
    "人員削減",    # workforce reduction (TSE category 人員削減等の合理化)
    "人員整理",    # personnel rationalisation
)

CONTEXT_TERMS_JA: tuple[str, ...] = (
    "リストラ",      # colloquial restructuring/layoffs; also リストラクチャリング
    "構造改革",      # structural reform (governance boilerplate risk)
    "事業構造改善",  # business-structure improvement (charges line item)
    "雇用調整",      # employment adjustment (also 雇用調整助成金 subsidy)
    "工場閉鎖",      # plant closure
    "事業所閉鎖",    # site closure
    "操業停止",      # operations halt
    "特別退職金",    # special severance payment
    "割増退職金",    # premium severance payment
    "人員適正化",    # headcount optimisation
)

STRONG_TERMS_KO: tuple[str, ...] = (
    "정리해고",      # economic-dismissal layoff
    "희망퇴직",      # voluntary retirement programme
    "명예퇴직",      # honorary/early retirement programme
    "권고사직",      # recommended resignation
    "인력감축",      # workforce reduction (also written 인력 감축)
    "인원감축",      # headcount reduction (also written 인원 감축)
    "경영상해고",    # statutory 경영상 (이유에 의한) 해고
)

CONTEXT_TERMS_KO: tuple[str, ...] = (
    "구조조정",      # restructuring (statute/debt noise: 기업구조조정 촉진법)
    "사업철수",      # business withdrawal
    "공장폐쇄",      # plant closure
    "퇴직위로금",    # ex-gratia severance payment
    "특별퇴직금",    # special severance payment
    "고용조정",      # employment adjustment
    "감원",          # headcount cut; 2-char, Hangul-boundary guarded
)

# Terms shorter than this are matched only in the original text with a
# same-script boundary guard; longer terms are also matched in a
# whitespace-stripped shadow so PDF/XML line breaks inside a word still hit.
MIN_STRIPPED_MATCH_LEN = 3

_HANGUL = re.compile(r"[가-힣]")

_VOCABULARY: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ja", "strong", STRONG_TERMS_JA),
    ("ja", "context", CONTEXT_TERMS_JA),
    ("ko", "strong", STRONG_TERMS_KO),
    ("ko", "context", CONTEXT_TERMS_KO),
)


@dataclass(frozen=True)
class TermMatch:
    language: str   # "ja" | "ko"
    tier: str       # "strong" | "context"
    term: str       # vocabulary entry that matched
    offset: int     # character offset in the normalised original text
    excerpt: str    # bounded window around the match, for review only


def strip_markup(document: str) -> str:
    """Reduce an HTML/XML filing body to reviewable plain text.

    Drops script/style/comment blocks, removes tags, unescapes entities and
    collapses whitespace.  This is deliberately simple, offline and identical
    for both document stages so fixtures test the exact production behaviour.
    """
    text = str(document or "")
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", text)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalise(text: str) -> str:
    """NFKC-fold and collapse runs of whitespace to single spaces."""
    folded = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"\s+", " ", folded)


def _stripped_with_map(text: str) -> tuple[str, list[int]]:
    """Whitespace-free shadow of ``text`` plus a map back to original offsets."""
    chars: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        if not char.isspace():
            chars.append(char)
            offsets.append(index)
    return "".join(chars), offsets


def _boundary_ok(text: str, start: int, end: int) -> bool:
    """Reject short-term matches glued to more Hangul (절감 원가 → 절감원가)."""
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not (_HANGUL.match(before) or _HANGUL.match(after))


def detect_layoff_language(
    text: str,
    *,
    excerpt_radius: int = 160,
    max_matches: int = 40,
) -> tuple[TermMatch, ...]:
    """Scan text for the tiered vocabulary and return bounded, review-ready matches.

    Matching is done both on the normalised original text and (for terms of
    at least ``MIN_STRIPPED_MATCH_LEN`` characters) on a whitespace-stripped
    shadow, so words split across extracted PDF/XML line breaks still match.
    Results are deduplicated by (term, original offset), ordered by offset,
    and capped at ``max_matches`` so a pathological document cannot flood the
    review output.
    """
    normalised = _normalise(text)
    stripped, offset_map = _stripped_with_map(normalised)
    seen: set[tuple[str, int]] = set()
    matches: list[TermMatch] = []
    for language, tier, terms in _VOCABULARY:
        for term in terms:
            compact = term.replace(" ", "")
            # Pass 1: the normalised original text (always).
            for found in re.finditer(re.escape(term), normalised):
                start = found.start()
                if len(term) < MIN_STRIPPED_MATCH_LEN and not _boundary_ok(
                    normalised, start, found.end()
                ):
                    continue
                if (term, start) in seen:
                    continue
                seen.add((term, start))
                lo = max(0, start - excerpt_radius)
                hi = min(len(normalised), found.end() + excerpt_radius)
                matches.append(TermMatch(language, tier, term, start, normalised[lo:hi]))
            # Pass 2: the stripped shadow (long terms only), mapped back.
            if len(compact) < MIN_STRIPPED_MATCH_LEN:
                continue
            for found in re.finditer(re.escape(compact), stripped):
                start = offset_map[found.start()]
                if (term, start) in seen:
                    continue
                seen.add((term, start))
                lo = max(0, start - excerpt_radius)
                end = offset_map[found.end() - 1] + 1
                hi = min(len(normalised), end + excerpt_radius)
                matches.append(TermMatch(language, tier, term, start, normalised[lo:hi]))
    matches.sort(key=lambda m: (m.offset, m.term))
    return tuple(matches[:max_matches])


def is_review_candidate(matches: tuple[TermMatch, ...]) -> bool:
    """True only when at least one strong-tier term matched."""
    return any(match.tier == "strong" for match in matches)
