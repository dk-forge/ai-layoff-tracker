#!/usr/bin/env python3
"""What KIND of claim each country can support — derived, never typed.

READ docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md and the
2026-09-15 TECHLOG entry on Europe first. Both establish the rule this module
mechanises:

    The only denominator that supports the word RECALL is one that enumerates
    IDENTIFIABLE EVENTS. A labour ministry publishing a periodic count of
    affected workers, or of procedures with no identities attached, supports
    SHARE OF THE OFFICIAL TOTAL and nothing stronger. Where neither exists,
    the honest label is DISCOVERY ONLY and nothing further is proved.

WHY THIS FILE EXISTS
--------------------
The measurement brief asks for per-country samples across the world. Most
countries cannot carry one, and the reason is a property of what their
authority publishes rather than a property of our collectors. Answering
"can this country carry a number at all?" one country at a time, by hand,
is how a wrong answer gets typed into a launch surface and quoted for months.

So the matrix DERIVES from `country_coverage.REGISTER` and
`country_coverage.PER_EMPLOYER_REGISTERS`, which are this repo's own committed,
dated assessments. The generated document is committed beside them and a test
fails if the two drift apart — the same shape as the US jurisdiction registry,
and for the same reason that registry taught on 2026-09-15: a generated
artifact with no generator on a schedule is born stale and nothing notices.

THE FOUR CLAIM TIERS, and they are not a quality ranking
--------------------------------------------------------
  EVENT_RECALL    a register NAMES the employer, so the denominator is a set
                  of identifiable events. Recall is measurable here and
                  NOWHERE ELSE.
  OFFICIAL_SHARE  a periodic aggregate exists. Our stored total over it is a
                  SHARE, never recall, and `country_coverage` forbids printing
                  it beside the Item 2.05 band.
  DISCOVERY_ONLY  a disclosure regime exists but publishes no complete
                  periodic count and no employer-named register, OR there is
                  no regime at all. Nothing beyond discovery is provable.
  REFUSED         the publisher declines automated access. Recorded as a
                  finding, never routed around: this project does not rename
                  its agent to evade a block aimed at the agent.

A country in EVENT_RECALL is not "better covered" than one in DISCOVERY_ONLY.
It is a statement about the PUBLISHER, not about us.

NO NETWORK. NO MODEL. This module reads two committed Python structures and
writes one Markdown file. Cost against the $18 monthly allowance: $0.00.

USAGE
    python3 railway/worldwide_claim_matrix.py            # print a summary
    python3 railway/worldwide_claim_matrix.py --write    # regenerate the doc
    python3 railway/worldwide_claim_matrix.py --check    # exit 1 if stale
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import country_coverage as cc  # noqa: E402

OUT = HERE.parent / "docs" / "recall-reference-sets" / "WORLDWIDE-CLAIM-MATRIX.md"

EVENT_RECALL = "EVENT_RECALL"
OFFICIAL_SHARE = "OFFICIAL_SHARE"
DISCOVERY_ONLY = "DISCOVERY_ONLY"
REFUSED = "REFUSED"

TIERS = (EVENT_RECALL, OFFICIAL_SHARE, DISCOVERY_ONLY, REFUSED)


def naming_jurisdictions():
    """Registers that NAME the employer, keyed by country.

    Only a named employer turns an official total into a set of events, so
    only these can carry the word recall. `names_employers` is the committed
    verdict and several entries carry `verified_from_file`, which is a
    stronger claim than reading a catalogue page.
    """
    out = {}
    for r in cc.PER_EMPLOYER_REGISTERS:
        if not r.get("names_employers"):
            continue
        out.setdefault(r["country"], []).append(r)
    return out


def tier_for(country, entry, naming):
    """The strongest claim this country can support, and why.

    Order matters: a refusal is reported as a refusal even when an aggregate
    is known to exist, because the point of the refusal ledger is that the
    figure is NOT ours to take.
    """
    if entry.get("class") == cc.REFUSED:
        return REFUSED, "the publisher declines automated access"
    if country in naming:
        js = ", ".join(r["jurisdiction"] for r in naming[country])
        return EVENT_RECALL, f"a register names the employer ({js})"
    if entry.get("class") == cc.REGIME_WITH_AGGREGATE:
        return OFFICIAL_SHARE, "a periodic aggregate exists, with no identities attached"
    if entry.get("class") == cc.REGIME_NO_AGGREGATE:
        return DISCOVERY_ONLY, "a disclosure regime exists but publishes no complete periodic count"
    if entry.get("class") == cc.NO_REGIME:
        return DISCOVERY_ONLY, "no collective-dismissal disclosure regime located"
    return DISCOVERY_ONLY, "unassessed"


def search_languages():
    """Languages the native layoff vocabulary covers.

    Keyed by language, NOT by country — there is no country-to-language map in
    this repo, and inventing one to fill a per-country column is how a typed
    coverage claim gets published. Reported as a capability instead.
    """
    from sources import native_layoff_terms
    return tuple(native_layoff_terms.languages())


def build():
    """Rows for every country in the committed register, sorted by tier then name."""
    naming = naming_jurisdictions()
    rows = []
    for country, entry in cc.REGISTER.items():
        tier, why = tier_for(country, entry, naming)
        ingested = None
        if country in naming:
            ingested = all(bool(r.get("in_tracker")) for r in naming[country])
        rows.append({
            "country": country,
            "tier": tier,
            "why": why,
            "assessed": entry.get("assessed"),
            "register_ingested": ingested,
        })
    rows.sort(key=lambda r: (TIERS.index(r["tier"]), r["country"]))
    return rows


def counts(rows=None):
    rows = build() if rows is None else rows
    return {t: sum(1 for r in rows if r["tier"] == t) for t in TIERS}


def render(rows=None):
    rows = build() if rows is None else rows
    n = counts(rows)
    L = []
    A = L.append
    A("# What kind of claim each country can support")
    A("")
    A("**Generated by `railway/worldwide_claim_matrix.py` from "
      "`railway/country_coverage.py`. Do not hand-edit — a test fails if this "
      "file and the registers disagree.**")
    A("")
    A("This file contains **no measurement**. It answers the question that has "
      "to be settled before any country is sampled: *what kind of claim is even "
      "possible here?* The answer is a property of what the national authority "
      "publishes, not of how well this tracker performs.")
    A("")
    A("The rule it mechanises is the one the US WARN and Europe assessments "
      "fixed: the only denominator that supports the word **recall** is one "
      "enumerating **identifiable events**. An aggregate of affected workers "
      "supports a **share of the official total** and nothing stronger. Where "
      "neither exists, the honest label is **discovery only**, and nothing "
      "further is proved.")
    A("")
    A("## Totals")
    A("")
    A("| Claim tier | Countries | What may be published |")
    A("|---|---:|---|")
    A(f"| EVENT_RECALL | {n[EVENT_RECALL]} | a recall figure with an interval |")
    A(f"| OFFICIAL_SHARE | {n[OFFICIAL_SHARE]} | a share of the official total, never labelled recall |")
    A(f"| DISCOVERY_ONLY | {n[DISCOVERY_ONLY]} | that we discover events; no coverage rate |")
    A(f"| REFUSED | {n[REFUSED]} | that the publisher declines automated access |")
    A("")
    A(f"**{n[EVENT_RECALL]} of {len(rows)} countries can carry the word recall at all.** "
      "That is the single most important number in this file, and it is a fact "
      "about the world's disclosure regimes rather than a shortfall in this "
      "project.")
    A("")
    A("## Where event-recall is possible, and whether we ingest it")
    A("")
    A("| Jurisdiction | Country | Ingested |")
    A("|---|---|---|")
    for country, regs in sorted(naming_jurisdictions().items()):
        for r in regs:
            A(f"| {r['jurisdiction']} | {country} | "
              f"{'yes' if r.get('in_tracker') else '**no**'} |")
    A("")
    A("A register we do **not** ingest still bounds what is provable: a miss "
      "there measures the general net rather than a collector, which is a "
      "weaker and different claim and must be labelled as one.")
    A("")
    A("## Every country")
    A("")
    A("| Country | Claim tier | Why | Assessed |")
    A("|---|---|---|---|")
    for r in rows:
        A(f"| {r['country']} | {r['tier']} | {r['why']} | {r['assessed'] or 'UNKNOWN'} |")
    A("")
    A("## Search vocabulary: a capability, not a per-country claim")
    A("")
    langs = search_languages()
    A(f"The native layoff vocabulary is keyed by LANGUAGE, and carries "
      f"**{len(langs)}**: {', '.join(langs)}.")
    A("")
    A("**There is no country-to-language map in this repository**, so this "
      "file does not print one. A per-country 'languages searched' column "
      "would have to be invented and typed, and a typed claim about coverage "
      "is the defect the cadence work of 2026-08-14 punished across seven "
      "surfaces. What is true and derivable is the list above: these are the "
      "languages the vocabulary covers, everywhere it is applied.")
    A("")
    A("## What this file deliberately does NOT say")
    A("")
    A("- **Nothing about last successful collection.** That reads the live "
      "health ledger, which is a different question (did the collector run?) "
      "from this one (could a number exist?). Mixing them is how a stale "
      "source and an unmeasurable country come to look alike.")
    A("- **Nothing about quality.** A DISCOVERY_ONLY country is not covered "
      "worse than an EVENT_RECALL one. It is a country whose authority "
      "publishes less.")
    A("- **No route around a refusal.** REFUSED rows are findings. This "
      "project does not rename its agent to evade a block aimed at the agent.")
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rows = build()
    if "--write" in argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(render(rows), encoding="utf-8")
        print(f"written: {OUT}")
        return 0
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != render(rows):
            print("STALE: the committed matrix disagrees with the registers. "
                  "Run: python3 railway/worldwide_claim_matrix.py --write")
            return 1
        print("matrix matches the registers")
        return 0
    n = counts(rows)
    for t in TIERS:
        print(f"{t:<16} {n[t]}")
    print(f"{'TOTAL':<16} {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
