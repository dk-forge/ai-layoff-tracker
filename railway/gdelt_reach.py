#!/usr/bin/env python3
"""GDELT REACH — what the worldwide news query actually returned, and what we did
with it. A MEASUREMENT module. It changes no behaviour and drops nothing new.

WHY THIS EXISTS
---------------
114 countries have a configured trusted outlet and zero stored rows. Three
explanations have been offered and NONE of them can be told apart from the
outside, because `sources/gdelt._fetch_trusted` discarded silently. Nobody could
say whether a Turkish article was never returned by GDELT, returned and dropped
at the allowlist, returned and already seen, or fetched and turned into nothing.

Two explanations have already been checked and were WRONG:

  "the allowlist is too small"  — it holds 706 domains across 117 TLDs, and the
                                  MENA and Turkish outlets are all in it.
  "there is no such news"       — the owner found five real events in English
                                  from outlets that are already allowlisted.

So the honest state is UNKNOWN, and an unknown is closed by instrumenting, not
by widening a list. This module records, per run:

  1. CANDIDATES RETURNED per query, and WHETHER THE QUERY HIT `maxrecords`.
     This is the single most valuable number here. `sortby=datedesc` over a
     36-hour window with `maxrecords=250` means a query that returns exactly
     250 is TRUNCATED: everything below the cut is invisible, and no log line
     anywhere said so. A capped query is not an error and never becomes one --
     it is a fact about reach.

  2. KEPT vs DROPPED per source country, with the reason. `not_allowlisted`
     and `kept` answer the allowlist question directly and in opposite
     directions.

  3. QUERY OUTCOME: answered, or ABANDONED after `QUERY_ATTEMPTS`. An abandoned
     window loses a whole slice of a day of worldwide news with no trace, and
     it is a COMPLETELY INDEPENDENT cause from the cap -- do not let a report
     blur them.

WHERE IT SURFACES, AND WHY NOWHERE ELSE
---------------------------------------
The gdelt row of the existing source-health ledger, whose `detail` was empty.
Every health write is also appended to the public `/source-runs` telemetry
table, so this is durable and readable history from day one WITHOUT a new
store, a new workflow, a new alert channel or a plugin change.
`ops_status.py [2d]` reads it back at session start.

`alt_source_health_record` truncates `detail` to 240 characters. That is the
whole reason `health_detail()` is a budget rather than a dump: the headline
facts are spent first and the per-country tail fills whatever is left, worst
countries first. The FULL table goes to stdout for the run log.

NAMELESS BY CONSTRUCTION
------------------------
Everything published passes `assert_nameless`, in the whitelist style
`tracker_diff.assert_nameless` and `curated_probe.assert_nameless` already
use here: numbers, and words from a frozen vocabulary. A country is recorded
as a TWO-LETTER code and nothing else, so this module cannot spell an employer,
a headline or a URL even if one is handed to it. `zz` is the honest bucket for
a generic TLD we cannot attribute, and it is REPORTED rather than hidden --
a large `zz` means the country signal is weak, which is itself a finding.

Country comes from the domain's ccTLD, NOT from GDELT's `sourcecountry` field,
because the BigQuery mirror path (`sources/gdelt_bq.query_window_articles`)
selects no such column. One derivation that works on both paths beats two that
disagree.
"""

import re
import threading


class LeakGuard(Exception):
    """Raised when something that must be nameless is not."""


# --- the frozen public vocabulary -----------------------------------------

# Drop reasons. `kept` is the only non-drop; every candidate lands in exactly
# one of these, which is what makes the columns add up to the returned count.
REASONS = (
    "kept",             # fetched, non-empty text, handed to the pipeline
    "not_allowlisted",  # domain is not in TRUSTED_DOMAINS
    "duplicate_url",    # same URL already seen inside this run
    "fetch_failed",     # the publisher would not serve the article
    "empty_text",       # served, but stripped to nothing
    "already_ingested", # filter_already_seen: this URL was read on a past run
    "gate_no",          # the cheap pre-extraction headline gate said no
    "budget_stop",      # the per-run spend brake was closed
    "not_an_event",     # extraction ran and produced no layoff record
)

# Query slots, by ROLE not by text: the segment/native/euphemism rotations
# change every run and their terms must never reach a public string.
QUERY_LABELS = ("broad", "segment", "native", "euphemism", "theme", "euro", "mirror")

_PUBLIC_WORDS = frozenset(REASONS) | frozenset(QUERY_LABELS) | frozenset({
    "queries", "returned", "capped", "cap", "abandoned", "rate_limited",
    "answered", "countries", "reasons", "totals", "candidates", "trusted",
    "kept", "dropped", "unknown_country", "by_country", "by_reason",
    "by_label", "max_records", "source", "gdelt", "reach",
})
_CC_RX = re.compile(r"^[a-z]{2}$")


def assert_nameless(obj, path="root"):
    """Prove a structure carries no free text, recursively. Raises LeakGuard.

    A whitelist, deliberately, and for the same reason the two existing copies
    of this function are whitelists: a reviewer noticing a name is not a
    mechanism, a function that cannot spell one is. Admitted strings are
    two-letter country codes and words from the frozen vocabulary above --
    nothing else, at any depth, in any key.
    """
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, float)):
        return obj
    if isinstance(obj, str):
        if obj in _PUBLIC_WORDS or _CC_RX.match(obj):
            return obj
        raise LeakGuard(f"{path}: refusing to publish free text")
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert_nameless(k, f"{path}.<key>")
            assert_nameless(v, f"{path}.{k}")
        return obj
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_nameless(v, f"{path}[{i}]")
        return obj
    raise LeakGuard(f"{path}: unsupported type {type(obj).__name__}")


# --- country attribution ---------------------------------------------------

# Two-letter ccTLDs that are NOT a usable country signal for a news outlet:
# they are sold as generic vanity domains and an outlet using one tells us
# nothing about where it publishes. Attributing `.io` to the Indian Ocean
# Territory or `.tv` to Tuvalu would be worse than admitting `zz`.
_VANITY_CC = frozenset({"io", "tv", "co", "me", "ai", "fm", "cc", "gg", "ly", "to", "in"})
# `in` is India's real ccTLD and a real signal, so it is put back: the vanity
# use of `.in` is rare in news. Keep this list SHORT and justified.
_VANITY_CC = _VANITY_CC - {"in"}

_UNKNOWN_CC = "zz"


def country_of(domain):
    """A two-letter country code for a news domain, or `zz`.

    ccTLD only. `dailysabah.com` is Turkish and resolves to `zz`, and that is
    the honest answer from a domain alone -- inventing a domain-to-country map
    would make the gTLD bucket look attributed when it is guessed. The bucket
    is reported, so its size is visible.
    """
    dom = (domain or "").strip().lower().rstrip(".")
    if not dom:
        return _UNKNOWN_CC
    last = dom.rsplit(".", 1)[-1]
    if len(last) == 2 and last.isalpha() and last not in _VANITY_CC:
        return last
    return _UNKNOWN_CC


# --- the per-run recorder --------------------------------------------------

class Reach:
    """One ingest run's reach facts. Pure accounting: no network, no clock."""

    def __init__(self):
        self.queries = []            # [{label, returned, max_records, capped, abandoned, rate_limited}]
        self._by_country = {}        # cc -> {reason: count}
        # `_fetch_trusted` records `kept` / `fetch_failed` / `empty_text` from
        # inside a ThreadPoolExecutor, so the counters are touched by up to
        # GDELT_FETCH_WORKERS threads at once. A read-modify-write on a plain
        # dict loses increments there, and a measurement that undercounts
        # silently is the exact defect this module exists to remove.
        self._lock = threading.Lock()

    # -- recording ---------------------------------------------------------

    def note_query(self, label, returned, max_records,
                   abandoned=False, rate_limited=False):
        """One GDELT window request outcome.

        `returned is None` means the window was ABANDONED -- it is not zero.
        Zero is "GDELT answered and there was nothing"; abandoned is "we never
        found out". Collapsing them is exactly the silence this module exists
        to remove.
        """
        if label not in QUERY_LABELS:
            raise LeakGuard(f"unknown query label: not in the frozen vocabulary")
        capped = returned is not None and max_records and returned >= max_records
        with self._lock:
            self.queries.append({
                "label": label,
                "returned": -1 if returned is None else int(returned),
                "max_records": int(max_records or 0),
                "capped": bool(capped),
                "abandoned": bool(abandoned or returned is None),
                "rate_limited": bool(rate_limited),
            })

    def note(self, domain, reason, count=1):
        """Attribute `count` candidates from `domain` to one outcome."""
        if reason not in REASONS:
            raise LeakGuard(f"unknown reason: not in the frozen vocabulary")
        cc = country_of(domain)
        with self._lock:
            self._by_country.setdefault(cc, {})
            self._by_country[cc][reason] = self._by_country[cc].get(reason, 0) + int(count)

    def note_cc(self, cc, reason, count=1):
        """Same, when the caller already holds a code (downstream stages)."""
        if reason not in REASONS:
            raise LeakGuard(f"unknown reason: not in the frozen vocabulary")
        cc = cc if _CC_RX.match(cc or "") else _UNKNOWN_CC
        with self._lock:
            self._by_country.setdefault(cc, {})
            self._by_country[cc][reason] = self._by_country[cc].get(reason, 0) + int(count)

    # -- reading -----------------------------------------------------------

    def by_reason(self):
        out = {}
        for reasons in self._by_country.values():
            for reason, n in reasons.items():
                out[reason] = out.get(reason, 0) + n
        return out

    def totals(self):
        """Query-level and candidate-level totals for the run.

        `returned` counts only ANSWERED windows. An abandoned window contributes
        to `abandoned`, never a zero to `returned`, so a bad day cannot read as
        a quiet one.
        """
        answered = [q for q in self.queries if not q["abandoned"]]
        by_reason = self.by_reason()
        seen = sum(by_reason.values())
        return {
            "queries": len(self.queries),
            "answered": len(answered),
            "abandoned": sum(1 for q in self.queries if q["abandoned"]),
            "capped": sum(1 for q in answered if q["capped"]),
            "rate_limited": sum(1 for q in self.queries if q["rate_limited"]),
            "returned": sum(q["returned"] for q in answered),
            "candidates": seen,
            "kept": by_reason.get("kept", 0),
            "dropped": seen - by_reason.get("kept", 0),
            "unknown_country": sum(self._by_country.get(_UNKNOWN_CC, {}).values()),
        }

    def summary(self):
        """The whole run as a nameless structure. Raises LeakGuard otherwise."""
        return assert_nameless({
            "totals": self.totals(),
            "by_reason": self.by_reason(),
            "by_label": self._by_label(),
            "by_country": {cc: dict(r) for cc, r in self._by_country.items()},
        })

    def _by_label(self):
        out = {}
        for q in self.queries:
            slot = out.setdefault(q["label"], {
                "queries": 0, "returned": 0, "capped": 0, "abandoned": 0})
            slot["queries"] += 1
            slot["capped"] += 1 if q["capped"] else 0
            slot["abandoned"] += 1 if q["abandoned"] else 0
            if not q["abandoned"]:
                slot["returned"] += q["returned"]
        return out

    # -- publishing --------------------------------------------------------

    def health_detail(self, budget=240):
        """A <=240 character health `detail`, headline facts first.

        The store truncates at 240, so this SPENDS rather than dumps. Order is
        the order of the open question: how much came back, was the cap
        binding, did we lose a window, then where the drops fell. Countries are
        appended worst-dropped-first until the budget runs out, so a tight
        budget loses the least interesting tail and never the headline.
        """
        t = self.totals()
        # `key=value` with full words, because this string is rendered RAW on
        # the public health page (assets/health.js) next to rows that already
        # read `queue=573 checked=40 stated=6`. A terse operator code would be
        # cheaper in characters and unreadable to the person the page is for.
        head = (f"returned={t['returned']} queries={t['queries']} "
                f"answered={t['answered']} abandoned={t['abandoned']} "
                f"capped={t['capped']} kept={t['kept']} dropped={t['dropped']}")
        by_reason = self.by_reason()
        reasons = " ".join(f"{r}={by_reason[r]}"
                           for r in REASONS if r != "kept" and by_reason.get(r))
        parts = [head]
        if reasons:
            parts.append(reasons)
        line = "; ".join(parts)

        ranked = sorted(
            self._by_country.items(),
            key=lambda kv: (-(sum(kv[1].values()) - kv[1].get("kept", 0)),
                            -sum(kv[1].values()), kv[0]))
        tail = []
        for cc, reasons_map in ranked:
            total = sum(reasons_map.values())
            chunk = f"{cc} {reasons_map.get('kept', 0)}/{total}"
            if len(line) + len("; ") + len(" ".join(tail + [chunk])) > budget:
                break
            tail.append(chunk)
        if tail:
            line = f"{line}; {' '.join(tail)}"
        return line[:budget]

    def report_lines(self):
        """The FULL per-country table, for the run log. Nameless like the rest."""
        s = self.summary()
        t = s["totals"]
        lines = [
            "GDELT reach: "
            f"{t['queries']} quer(ies), {t['answered']} answered, "
            f"{t['abandoned']} ABANDONED, {t['capped']} hit maxrecords, "
            f"{t['returned']} article(s) returned",
            f"GDELT reach: {t['candidates']} candidate(s) -> "
            f"{t['kept']} kept, {t['dropped']} dropped "
            f"({t['unknown_country']} of them from a generic TLD, country unknown)",
        ]
        for label in QUERY_LABELS:
            slot = s["by_label"].get(label)
            if slot:
                lines.append(
                    f"GDELT reach [{label}]: {slot['queries']} quer(ies), "
                    f"{slot['returned']} returned, {slot['capped']} capped, "
                    f"{slot['abandoned']} abandoned")
        for cc, reasons_map in sorted(
                s["by_country"].items(),
                key=lambda kv: (-sum(kv[1].values()), kv[0])):
            detail = " ".join(f"{r}={reasons_map[r]}"
                              for r in REASONS if reasons_map.get(r))
            lines.append(f"GDELT reach [{cc}]: {detail}")
        return lines


# A run-scoped singleton, so the collector and the pipeline stages downstream
# of it record into the same ledger without threading an object through every
# signature. `reset()` at the top of a run; a module import must never inherit
# a previous run's counts.
_current = Reach()


def current():
    return _current


def reset():
    global _current
    _current = Reach()
    return _current
