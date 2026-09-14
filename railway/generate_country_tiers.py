#!/usr/bin/env python3
"""Generate the country pages' coverage block: tier, languages, sources, recall.

Every country page (/country-layoffs/<slug>/) says what kind of coverage it
rests on. The tier is DERIVED from research already committed, never assigned
by hand here:

  Tier 1  official structured    an official body's structured employer-level
                                 dataset is read straight into the tracker:
                                 the per-employer registers country_coverage
                                 marks `in_tracker` (US state WARN units,
                                 Quebec, Mazowieckie), SEC EDGAR Item 2.05
                                 (US), and Eurofound's ERM for the EU + Norway
                                 set generate_country_table.EU names.
  Tier 2  official unstructured  country_coverage.REGISTER classes the country
                                 REGIME_WITH_AGGREGATE: an official body
                                 publishes collective-dismissal figures we can
                                 read or compare against, but no employer-level
                                 register is ingested.
  Tier 3  verified reported      REGISTER classes it REGIME_NO_AGGREGATE,
                                 NO_REGIME or REFUSED: nothing official is
                                 published in a countable form, so every entry
                                 rests on a filing or a named report.
  Tier 4  discovery only         the country is in the news-scan scope (the
                                 GDELT allowlist, a local-language market, a
                                 regional or national feed) and holds no entry
                                 in the register at all.
  UNKNOWN                        the register holds the country but its entry
                                 is UNASSESSED, incomplete or expired. Rendered
                                 as "not yet classified", never as a tier.

Tier 1 beats Tier 2 beats Tier 3 for a country that qualifies for more than
one (Sweden has an official aggregate AND ERM: Tier 1, and the row names both).

Everything else on the block is derived the same way:

  languages searched     the Google News editions sources/local_news_markets
                         asks for this country, plus a feed's own stated
                         language; GDELT's translated index is noted once for
                         every country rather than claimed per country
  sources monitored      the country's outlets in the GDELT allowlist
                         (generate_country_table.parse()), its reviewed local
                         publishers, and the regional/national feeds that name
                         it
  official sources       the register's regime, authority and citation, and
                         the official collectors that serve the country
  health ids             the collector ids whose newest 'ok' completion the
                         plugin prints as "last successful collection"
  measured recall        ONLY where a real event-recall sample exists:
                         rolling_recall's SEC Item 2.05 slice (US),
                         warn_recall_measurement (US WARN, editor-confirmed),
                         recall_uk_measurement (UK Hansard set). Copied with
                         numerator, denominator, window and date.
  official-total         national_denominators_measurement slices, which
  comparison             compare held jobs against a national NOTIFIED total.
                         Estonia and Taiwan (and GB, NI, IS, LV, NL, PL, RO)
                         carry this and it is labelled as a comparison against
                         an official total, never as recall or accuracy.

Re-run after any change to the inputs, and commit data/country-coverage.json:

    python3 railway/generate_country_tiers.py

tests/test_country_tiers.py fails when the committed file no longer matches.
"""
import datetime as _dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import country_coverage as cc          # noqa: E402
import generate_country_table as gct   # noqa: E402
from generate_jurisdiction_table import edgar_reads_item_205   # noqa: E402
from sources import local_news_markets as markets      # noqa: E402
from sources import regional_feeds, national_feeds     # noqa: E402

OUT = (HERE.parent / "wordpress-plugin" / "ai-layoff-tracker" / "data"
       / "country-coverage.json")

TIER_LABELS = {
    1: "Official structured",
    2: "Official unstructured",
    3: "Verified reported",
    4: "Discovery only",
}

#: Google News edition language codes -> names. A code the map does not know
#: is emitted as the code itself, never dropped.
LANGUAGE_NAMES = {
    "ar": "Arabic", "ca": "Catalan", "de": "German", "en": "English",
    "es": "Spanish", "fa": "Persian", "fr": "French", "it": "Italian",
    "kk": "Kazakh", "pt": "Portuguese", "ru": "Russian", "si": "Sinhala",
    "sq": "Albanian", "sr": "Serbian", "ta": "Tamil", "tr": "Turkish",
    "uk": "Ukrainian", "ur": "Urdu",
}

#: The official collectors and the health id each reports under. The country
#: sets are read from the code, not typed: EU/Norway from
#: generate_country_table.EU (the ERM scope), the per-employer registers from
#: country_coverage.PER_EMPLOYER_REGISTERS where in_tracker is set.
OFFICIAL_COLLECTORS = {
    "eurofound_erm": "Eurofound ERM restructuring announcements",
    "edgar": "SEC EDGAR 8-K Item 2.05 filings",
    "warn_us": "State WARN notices",
    "warn_quebec": "Quebec collective-dismissal notices",
    "warn_mazowieckie": "Mazowieckie collective-dismissal register",
}

NEWS_HEALTH_IDS = ("gdelt", "google_news")


def erm_countries():
    """Countries ERM covers, as the country table names them (EU + Norway)."""
    fixes = {"Czech Republic": "Czechia"}
    return {fixes.get(c, c) for c in gct.EU}


def _per_employer_in_tracker():
    out = {}
    for r in cc.PER_EMPLOYER_REGISTERS:
        if not r.get("in_tracker"):
            continue
        out.setdefault(r["country"], []).append(r["jurisdiction"])
    return out


def official_collectors_for(country):
    """[(health_id, label), ...] of the official collectors serving a country."""
    out = []
    if country in erm_countries():
        out.append(("eurofound_erm", OFFICIAL_COLLECTORS["eurofound_erm"]))
    if country == "United States" and edgar_reads_item_205():
        out.append(("edgar", OFFICIAL_COLLECTORS["edgar"]))
    for jurisdiction in _per_employer_in_tracker().get(country, []):
        if jurisdiction.startswith("United States"):
            out.append(("warn_us", OFFICIAL_COLLECTORS["warn_us"]))
        elif jurisdiction == "Quebec":
            out.append(("warn_quebec", OFFICIAL_COLLECTORS["warn_quebec"]))
        elif jurisdiction.startswith("Mazowieckie"):
            out.append(("warn_mazowieckie", OFFICIAL_COLLECTORS["warn_mazowieckie"]))
    return out


def scan_scope():
    """Every country the news collectors name, with what names it."""
    # Keys are the register's canonical spellings (cc.ALIASES), so "Turkey" in
    # a market table and "Türkiye" in the register are one row, not two.
    scope = {}
    for label, outlets in gct.parse().items():
        if gct.classify(label)[1]:
            scope.setdefault(cc.canonical(label), {})["gdelt_outlets"] = list(outlets)
    for mk in markets.MARKETS:
        s = scope.setdefault(cc.canonical(mk.country), {})
        s["local_editions"] = [e.lang for e in mk.editions]
        s["local_publishers"] = len(mk.publishers)
    for feed in regional_feeds.FEEDS:
        for c in feed.countries:
            scope.setdefault(cc.canonical(c), {}).setdefault("regional_feeds", []).append(
                {"outlet": feed.outlet, "note": feed.note})
    for feed in national_feeds.FEEDS:
        scope.setdefault(cc.canonical(feed.country), {}).setdefault("national_feeds", []).append(
            {"outlet": feed.outlet, "note": getattr(feed, "note", "")})
    return scope


def languages_for(scope_row):
    langs = []
    for lang in scope_row.get("local_editions", []):
        name = LANGUAGE_NAMES.get(lang.split("-")[0], lang.split("-")[0])
        if name not in langs:
            langs.append(name)
    for feed in scope_row.get("regional_feeds", []) + scope_row.get("national_feeds", []):
        note = (feed.get("note") or "").lower()
        for name in LANGUAGE_NAMES.values():
            if ("in " + name.lower()) in note and name not in langs:
                langs.append(name)
    return langs


def tier_for(country, entry, in_scan_scope):
    """(tier or None, reason). The rule in the module docstring, in code."""
    if official_collectors_for(country):
        return 1, "an official employer-level dataset is read into the tracker"
    klass = entry.get("class")
    if klass == cc.UNASSESSED and in_scan_scope and country not in cc.REGISTER:
        return 4, "in the news-scan scope, no entry in the disclosure-regime register"
    if klass == cc.UNASSESSED or entry.get("state") == cc.UNKNOWN:
        return None, "the disclosure-regime register has no settled entry for this country"
    if klass == cc.REGIME_WITH_AGGREGATE:
        return 2, ("an official body publishes collective-dismissal figures, "
                   "but no employer-level register is ingested")
    if klass in (cc.REGIME_NO_AGGREGATE, cc.NO_REGIME, cc.REFUSED):
        return 3, ("nothing official is published in a countable form; "
                   "entries rest on filings and named reports")
    return None, "no settled classification"


def recall_samples():
    """Real event-recall measurements, keyed by country. Copied, not computed."""
    out = {}
    try:
        rr = json.loads((HERE / "rolling_recall_measurement.json").read_text(encoding="utf-8"))
        s = rr["slices"]["sec_item_205_us"]
        if s.get("state") == "measured" and int(s.get("in_scope") or 0) > 0:
            out.setdefault("United States", []).append({
                "label": s["label"],
                "matched": int(s["confirmed"]),
                "reference": int(s["in_scope"]),
                "interval": s.get("confirmed_interval"),
                "window": s.get("window"),
                "measured_at": rr.get("measured_at"),
                "source": "railway/rolling_recall_measurement.json",
            })
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        wr = json.loads((HERE / "warn_recall_measurement.json").read_text(encoding="utf-8"))
        s = wr["summary"]["editor_confirmed_overall"]
        out.setdefault("United States", []).append({
            "label": "US state WARN reference set (CA, TX, FL, TN), editor-confirmed",
            "matched": int(s["k"]),
            "reference": int(s["n"]),
            "interval": [s.get("low"), s.get("high")],
            "window": None,
            "measured_at": wr.get("measured_at"),
            "source": "railway/warn_recall_measurement.json",
        })
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        uk = json.loads((HERE / "recall_uk_measurement.json").read_text(encoding="utf-8"))
        if int(uk.get("reference_events") or 0) > 0:
            out.setdefault("United Kingdom", []).append({
                "label": "UK reference set (Hansard-derived)",
                "matched": int(uk["matched"]),
                "reference": int(uk["reference_events"]),
                "pending_adjudication": len(uk.get("candidates_needing_adjudication") or []),
                "interval": None,
                "window": None,
                "measured_at": uk.get("measured_at"),
                "source": "railway/recall_uk_measurement.json",
            })
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return out


def official_total_comparisons():
    """national_denominators slices by country. A comparison, never recall."""
    out = {}
    try:
        nd = json.loads((HERE / "national_denominators_measurement.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for key, s in (nd.get("slices") or {}).items():
        if s.get("state") != "measured":
            continue
        country = cc.canonical(s.get("country") or "")
        if not country:
            continue
        out.setdefault(country, []).append({
            "key": key,
            "label": s.get("label"),
            "authority": s.get("authority"),
            "denominator": s.get("denominator"),
            "unit": s.get("unit"),
            "period": (s.get("period") or {}).get("label"),
            "held_jobs_strict": s.get("held_jobs_strict"),
            "held_jobs_any": s.get("held_jobs_any"),
            "coverage_lower": s.get("coverage_lower"),
            "coverage_upper": s.get("coverage_upper"),
            "measured_at": nd.get("measured_at"),
            "source": "railway/national_denominators_measurement.json",
        })
    return out


def build(today=None):
    scope = scan_scope()
    recall = recall_samples()
    totals = official_total_comparisons()
    rows = {}
    for country in sorted(set(cc.REGISTER) | set(scope)):
        in_register = country in cc.REGISTER
        entry = cc.entry_for(country, today) if in_register else {"class": cc.UNASSESSED, "state": cc.UNKNOWN}
        s = scope.get(country, {})
        tier, why = tier_for(country, entry, bool(s))
        officials = official_collectors_for(country)
        register = None
        if in_register:
            raw = cc.REGISTER[country]
            register = {
                "class": raw.get("class"),
                "regime": raw.get("regime"),
                "authority": raw.get("authority"),
                "cite": raw.get("cite"),
                "assessed": raw.get("assessed"),
                "state": entry.get("state"),
            }
        feeds = ([f["outlet"] for f in s.get("regional_feeds", [])]
                 + [f["outlet"] for f in s.get("national_feeds", [])])
        health_ids = [h for h, _ in officials] + list(NEWS_HEALTH_IDS)
        if s.get("local_editions"):
            health_ids.append("local_news")
        if s.get("regional_feeds"):
            health_ids.append("regional_feeds")
        if s.get("national_feeds"):
            health_ids.append("national_feeds")
        rows[country] = {
            "tier": tier,
            "tier_label": TIER_LABELS.get(tier, "Not yet classified"),
            "tier_reason": why,
            "official_collectors": [{"health_id": h, "label": l} for h, l in officials],
            "health_ids": health_ids,
            "languages": languages_for(s),
            "sources": {
                "gdelt_outlets": len(s.get("gdelt_outlets", [])),
                "local_publishers": int(s.get("local_publishers") or 0),
                "feeds": feeds,
            },
            "register": register,
            "recall": recall.get(country, []),
            "official_total_comparisons": totals.get(country, []),
        }
    return {
        "note": ("GENERATED by railway/generate_country_tiers.py from "
                 "country_coverage.REGISTER and PER_EMPLOYER_REGISTERS, "
                 "generate_country_table (GDELT allowlist + ERM scope), "
                 "local_news_markets, the regional/national feeds and the "
                 "committed recall and national-denominator measurements. Do "
                 "not hand-edit; re-run the generator. "
                 "tests/test_country_tiers.py pins the parity."),
        "generated_on": (today or _dt.date.today()).isoformat(),
        "tier_labels": {str(k): v for k, v in TIER_LABELS.items()},
        "aliases": dict(cc.ALIASES),
        "gdelt_index_note": "GDELT translates 65 languages into English before we query its index",
        "countries": rows,
    }


def render(doc=None):
    return json.dumps(doc or build(), indent=2, ensure_ascii=False) + "\n"


def committed_matches(path=OUT):
    """True when the committed file equals a build made on its own date.

    The register's assessments expire by age, so a build is a function of
    the day; the committed stamp is the day to rebuild against. A stale file
    still fails when a collector, a market or a measurement moved.
    """
    try:
        old = json.loads(Path(path).read_text(encoding="utf-8"))
        today = _dt.date.fromisoformat(old.get("generated_on"))
    except (OSError, ValueError, TypeError):
        return False
    return old == build(today=today)


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    OUT.write_text(render(doc), encoding="utf-8")
    tally = {}
    for c, r in doc["countries"].items():
        tally.setdefault(r["tier_label"], []).append(c)
    print(f"wrote {OUT}: {len(doc['countries'])} countries")
    for label, cs in sorted(tally.items()):
        print(f"  {label}: {len(cs)}")
