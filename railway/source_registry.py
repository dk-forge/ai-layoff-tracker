"""Source and vocabulary registry for the autonomous discovery pipeline.

This is deliberately data, not prompt text.  Collectors use it to decide what
to search and the public methodology can describe the resulting coverage.  A
country is *not* complete merely because it is listed here: every source must
also have a working connector and a health check before the site can claim
structured coverage for it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    iso2: str
    # ``status`` describes a live collector, never a source we merely intend
    # to build. This keeps the registry safe to expose to reporters later.
    # Values: reconciled | structured_official | discovery_only.
    status: str
    benchmark: str
    terms: tuple[str, ...]
    live_sources: tuple[str, ...]
    candidate_official_sources: tuple[str, ...]


# Cross-market terms are intentionally broad.  They are discovery terms only;
# extraction and evidence validation decide whether an article is a real event.
GLOBAL_TERMS = (
    "layoff", "layoffs", "laid off", "job cuts", "cutting jobs",
    # Verb-phrase gap (2026-08-24, discovery-learning loop): the vocabulary had
    # the noun "job cuts" and the gerund "cutting jobs" but not the base/infinitive
    # "cut jobs" ("... to cut jobs", "will cut jobs"), the standard headline form
    # for a mid-size cut. Layoff-specific and low-noise; NOT the bare word "cut".
    "cut jobs",
    "job losses", "redundancy", "redundancies", "staff cuts",
    "workforce reduction", "headcount reduction", "headcount cuts",
    "reduction in force", "RIF", "downsizing", "position eliminations",
    "role eliminations", "workforce realignment", "organizational realignment",
    "restructuring plan", "collective redundancy", "collective dismissal",
    "plant closure", "site closure",
    # Dialect synonyms (2026-07-19): "retrenchment" is the standard word in
    # Indian, Singaporean, Malaysian, South African and Nigerian English
    # press; "sacked"/"dismissals" dominate UK/AU/African headlines and
    # machine-translated coverage. Expat and translated papers use these
    # where US outlets say "layoffs".
    "retrenchment", "retrenchments", "mass dismissal", "dismissals",
    "sacked", "jobs axed",
    # Corporate euphemisms (2026-07-25). Comms teams increasingly avoid the words
    # above, so these soften-speak variants are a real recall gap. Only the
    # LOW-NOISE, layoff-specific ones live in the always-on base (they match few
    # extra articles, so cost barely moves); the noisy cost/efficiency doublespeak
    # ("cost optimization", "operating model", "efficiency program") is kept OUT of
    # the base and instead rotates as layoff-signal-PAIRED segments in gdelt.py, so
    # discovery stays inside the monthly LLM budget instead of flooding extraction.
    "rightsizing", "workforce optimization", "workforce rebalancing",
    "job eliminations", "voluntary separation", "organizational simplification",
    # Verb-form gap, the second of the same shape (2026-09-06, city recall
    # sweep). "cut jobs" was added on 2026-08-24 because the vocabulary held the
    # noun and the gerund but not the base form. The identical hole was still
    # open on the OTHER layoff verb: "laid off" (past participle) was here,
    # "lays off" / "lay off" / "laying off" were not, although "X lays off 250
    # employees" is the single most common layoff headline in the English
    # press. Measured over 260 headlines carrying a headcount from a 120-city
    # index sweep, 159 matched no term at all and these three close 49 of them.
    # Layoff-specific and low-noise, like "cut jobs" and unlike a bare "cut".
    "lay off", "lays off", "laying off",
)


MARKETS = {
    "US": Market("US", "reconciled", "Announcement survey",
                 ("WARN notice", "mass layoff", "workforce reduction"),
                 ("state WARN notices", "SEC EDGAR 8-K/6-K", "company IR"), ()),
    "EU": Market("EU", "structured_official", "European Restructuring Monitor (Eurofound)",
                 ("collective redundancy", "collective dismissal", "restructuring"),
                 ("European Restructuring Monitor (Eurofound)", "worldwide news", "reviewed company IR feeds"), ()),
    # These markets have worldwide-news discovery today. Their named filing
    # systems are candidates, not active feeds. Do not turn one into a coverage
    # claim until it has a documented public interface, connector, fixtures and
    # source-health reporting.
    "CA": Market("CA", "discovery_only", "", ("termination notice", "mass termination"),
                 ("worldwide news", "reviewed company IR feeds"), ("SEDAR+",)),
    "GB": Market("GB", "discovery_only", "", ("redundancy consultation", "redundancies"),
                 ("worldwide news", "reviewed company IR feeds"), ("RNS",)),
    "AU": Market("AU", "discovery_only", "", ("redundancy", "job cuts"),
                 ("worldwide news", "reviewed company IR feeds"), ("ASX announcements",)),
    "JP": Market("JP", "discovery_only", "", ("restructuring", "workforce reduction"),
                 ("worldwide news", "reviewed company IR feeds"), ("TDnet", "EDINET")),
    "IN": Market("IN", "discovery_only", "", ("retrenchment", "job cuts"),
                 ("worldwide news", "reviewed company IR feeds"), ("NSE", "BSE")),
    "HK": Market("HK", "discovery_only", "", ("restructuring", "job cuts"),
                 ("worldwide news", "reviewed company IR feeds"), ("HKEXnews",)),
    "SG": Market("SG", "discovery_only", "", ("retrenchment", "workforce reduction"),
                 ("worldwide news", "reviewed company IR feeds"), ("SGXNet",)),
    "ZA": Market("ZA", "discovery_only", "", ("retrenchment", "section 189"),
                 ("worldwide news", "reviewed company IR feeds"), ("SENS",)),
    "BR": Market("BR", "discovery_only", "", ("demissões", "cortes de empregos"),
                 ("worldwide news", "reviewed company IR feeds"), ()),
    "MX": Market("MX", "discovery_only", "", ("despidos", "recorte de personal"),
                 ("worldwide news", "reviewed company IR feeds"), ()),
    "KR": Market("KR", "discovery_only", "", ("restructuring", "job cuts"),
                 ("worldwide news", "reviewed company IR feeds"), ("DART",)),
    "IL": Market("IL", "discovery_only", "", ("layoffs", "workforce reduction"),
                 ("worldwide news", "reviewed company IR feeds"), ("TASE",)),
}


def discovery_terms() -> tuple[str, ...]:
    """Deduplicated, bounded vocabulary for broad global-news discovery."""
    terms = list(GLOBAL_TERMS)
    for market in MARKETS.values():
        terms.extend(market.terms)
    # GDELT queries become less reliable when needlessly huge; the ceiling is a
    # deliberate cap (36 -> 42 on 2026-07-19 for dialect synonyms; 42 -> 48 on
    # 2026-07-25 for the low-noise corporate euphemisms; 48 -> 51 on 2026-09-06
    # for the layoff verb forms) and the global terms occupy the most valuable
    # slots.
    #
    # RAISE THIS DELIBERATELY OR NOT AT ALL. The unique count sat at EXACTLY 48
    # before the 2026-09-06 addition, so three new global terms would have
    # pushed three market terms off the end silently: the truncation is at the
    # tail, the tail is whichever market MARKETS happens to iterate last, and
    # nothing anywhere would have reported a market losing its vocabulary.
    # `tests/test_source_registry_parity.py` now fails when the cap is reached,
    # so a future addition has to make this decision on purpose too.
    return tuple(dict.fromkeys(terms))[:51]


def coverage_manifest() -> list[dict[str, object]]:
    """JSON-safe data used by monitoring and future public coverage pages."""
    return [
        {"country": m.iso2, "status": m.status, "benchmark": m.benchmark,
         "live_sources": list(m.live_sources),
         "candidate_official_sources": list(m.candidate_official_sources)}
        for m in MARKETS.values()
    ]
