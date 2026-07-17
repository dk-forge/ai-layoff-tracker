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
    status: str  # reconciled | structured_official | partial | discovery_only
    benchmark: str
    terms: tuple[str, ...]
    sources: tuple[str, ...]


# Cross-market terms are intentionally broad.  They are discovery terms only;
# extraction and evidence validation decide whether an article is a real event.
GLOBAL_TERMS = (
    "layoff", "layoffs", "laid off", "job cuts", "cutting jobs",
    "job losses", "redundancy", "redundancies", "staff cuts",
    "workforce reduction", "headcount reduction", "headcount cuts",
    "reduction in force", "RIF", "downsizing", "position eliminations",
    "role eliminations", "workforce realignment", "organizational realignment",
    "restructuring plan", "collective redundancy", "collective dismissal",
    "plant closure", "site closure",
)


MARKETS = {
    "US": Market("US", "reconciled", "Challenger, Gray & Christmas",
                 ("WARN notice", "mass layoff", "workforce reduction"),
                 ("state WARN notices", "SEC EDGAR 8-K/6-K", "company IR")),
    "CA": Market("CA", "partial", "", ("termination notice", "mass termination"),
                 ("SEDAR+", "company IR", "national business news")),
    "GB": Market("GB", "partial", "", ("redundancy consultation", "redundancies"),
                 ("RNS", "company IR", "national business news")),
    "AU": Market("AU", "partial", "", ("redundancy", "job cuts"),
                 ("ASX announcements", "company IR", "national business news")),
    "JP": Market("JP", "partial", "", ("restructuring", "workforce reduction"),
                 ("TDnet", "EDINET", "company IR")),
    "IN": Market("IN", "partial", "", ("retrenchment", "job cuts"),
                 ("NSE", "BSE", "company IR")),
    "HK": Market("HK", "partial", "", ("restructuring", "job cuts"),
                 ("HKEXnews", "company IR")),
    "SG": Market("SG", "partial", "", ("retrenchment", "workforce reduction"),
                 ("SGXNet", "company IR")),
    "ZA": Market("ZA", "partial", "", ("retrenchment", "section 189"),
                 ("SENS", "company IR")),
    "BR": Market("BR", "discovery_only", "", ("demissões", "cortes de empregos"),
                 ("company IR", "national business news")),
    "MX": Market("MX", "discovery_only", "", ("despidos", "recorte de personal"),
                 ("company IR", "national business news")),
    "KR": Market("KR", "partial", "", ("restructuring", "job cuts"),
                 ("DART", "company IR")),
    "IL": Market("IL", "partial", "", ("layoffs", "workforce reduction"),
                 ("TASE", "company IR")),
}


def discovery_terms() -> tuple[str, ...]:
    """Deduplicated, bounded vocabulary for broad global-news discovery."""
    terms = list(GLOBAL_TERMS)
    for market in MARKETS.values():
        terms.extend(market.terms)
    # GDELT queries become less reliable when needlessly huge; 36 terms is a
    # deliberate ceiling and the global terms occupy the most valuable slots.
    return tuple(dict.fromkeys(terms))[:36]


def coverage_manifest() -> list[dict[str, object]]:
    """JSON-safe data used by monitoring and future public coverage pages."""
    return [
        {"country": m.iso2, "status": m.status, "benchmark": m.benchmark,
         "sources": list(m.sources)}
        for m in MARKETS.values()
    ]
