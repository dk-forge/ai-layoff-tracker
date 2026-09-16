#!/usr/bin/env python3
"""Generate the plugin's US jurisdiction registry: one row per jurisdiction.

The public page `/ai-layoff-tracker/us-warn-registry/` answers, for each of
the 56 US jurisdictions (50 states, DC, five inhabited territories): where the
official notices are published, how we collect them, whether the register is
fresh, and where there is no public register at all. Every value on that page
is DERIVED. Nothing here is typed by hand:

  jurisdiction list      railway/source_inventory.py US_JURISDICTIONS
  collector tiers        source_inventory.warn_collectors(), which reads the
                         scrapers' own registries (warn.ALL_STATES,
                         warn_custom.CUSTOM_STATES, warn_new_states
                         .NEW_CUSTOM_STATES), plus the two per-state collectors
                         cron.py runs by name
  official source        railway/sources/warn.py STATE_WARN_URL, the same map
                         the importer stamps onto list-only notices
  freshness + policy     railway/source_state.json, the per-source ledger
                         source_freshness.py writes (HEALTHY / UNAVAILABLE /
                         UNKNOWN, and a human-written reason where a state
                         publishes no usable register)
  collection cadence     the cron line of the WARN workflows, parsed, never
                         typed (tests/test_cadence_is_derived.py is the reason)

The plugin merges this committed file with two things only it holds: the live
source-health ledger (last successful collection per collector) and the
layoffs table (historical range, whether worker counts and notice documents
exist per state). `tests/test_us_registry.py` fails when the committed JSON no
longer matches this generator, so a scraper added, removed or marked
UNAVAILABLE reaches the public page the same commit.

Re-run after any change to the inputs above:

    python3 railway/generate_us_registry.py
"""
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from source_inventory import US_JURISDICTIONS, US_STATES, warn_collectors  # noqa: E402
from generate_jurisdiction_table import STATE_NAMES  # noqa: E402

OUT = (HERE.parent / "wordpress-plugin" / "ai-layoff-tracker" / "data"
       / "us-jurisdictions.json")
SOURCE_STATE = HERE / "source_state.json"
WORKFLOWS = HERE.parent / ".github" / "workflows"

#: Names for the six non-state jurisdictions. STATE_NAMES (the methodology
#: table's map) carries DC already; the five territories are a constitutional
#: fact, like the jurisdiction list itself.
TERRITORY_NAMES = {
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "GU": "Guam",
    "VI": "US Virgin Islands",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

#: How each collector tier reads its register, and which health-ledger id it
#: reports under. The ids are the literal strings the collectors post
#: (warn_import.py, hi_warn_import.py, cron.py), so a renamed id is a red test
#: here rather than a blank cell on the public page.
TIERS = {
    "generic": {
        "method": "Open WARN scraper reading the state register",
        "health_id": "warn_us",
        "workflow": "warn-import.yml",
    },
    "legacy_custom": {
        "method": "Custom scraper written for this state's register",
        "health_id": "warn_custom_legacy",
        "workflow": "warn-import.yml",
    },
    "new_custom": {
        "method": "Custom scraper written for this state's register",
        "health_id": "warn_custom_states",
        "workflow": "warn-import.yml",
    },
    "hi_ocr": {
        "method": "OCR of the state's scanned notice images",
        "health_id": "warn_hi_ocr",
        "workflow": "hi-warn-import.yml",
    },
    "mn_letters": {
        "method": "Per-company notice letters read from the state page",
        "health_id": "warn_mn_letters",
        "workflow": None,   # runs inside the Railway cron (cron.py)
    },
}


def _cron_of(workflow):
    """The first `cron:` line of a workflow, or '' when it has none."""
    try:
        text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"cron:\s*'([^']+)'", text) or re.search(r'cron:\s*"([^"]+)"', text)
    return m.group(1).strip() if m else ""


def cadence_phrase(cron):
    """'daily' / 'weekly' / '' from a five-field cron. Never guesses."""
    parts = cron.split()
    if len(parts) != 5:
        return ""
    minute, hour, dom, month, dow = parts
    if dom == "*" and month == "*" and dow == "*" and hour.isdigit():
        return "daily"
    if dom == "*" and month == "*" and dow.isdigit() and hour.isdigit():
        return "weekly"
    return ""


def _railway_cadence():
    """The Railway cron's cadence, from the file the plugin already reads."""
    path = (HERE.parent / "wordpress-plugin" / "ai-layoff-tracker" / "data"
            / "ingest-schedule.json")
    try:
        hours = json.loads(path.read_text(encoding="utf-8")).get("utc_hours") or []
    except Exception:
        return ""
    return {1: "daily"}.get(len(hours), "")


def _cron_names(collector_id):
    """Does railway/cron.py run a collector by this id?"""
    try:
        return collector_id in (HERE / "cron.py").read_text(encoding="utf-8")
    except OSError:
        return False


def collectors():
    """{code: [tier, ...]}, the inventory's map plus the cron-run per-state ids."""
    out = {k: list(v) for k, v in warn_collectors().items()}
    if (HERE / "sources" / "warn_mn_letters.py").exists() and _cron_names("warn_mn_letters"):
        out.setdefault("MN", []).append("mn_letters")
    return out


def state_urls():
    from sources.warn import STATE_WARN_URL
    return dict(STATE_WARN_URL)


def source_state():
    try:
        return json.loads(SOURCE_STATE.read_text(encoding="utf-8")).get("sources", {})
    except (OSError, ValueError):
        return {}


def build():
    have = collectors()
    urls = state_urls()
    ledger = source_state()
    cadences = {}
    for tier, spec in TIERS.items():
        if spec["workflow"]:
            cadences[tier] = cadence_phrase(_cron_of(spec["workflow"]))
        else:
            cadences[tier] = _railway_cadence()

    rows = []
    for code in US_JURISDICTIONS:
        name = STATE_NAMES.get(code) or TERRITORY_NAMES.get(code) or code
        tiers = have.get(code, [])
        fresh = ledger.get("warn:" + code) or {}
        state = str(fresh.get("state") or "")
        row = {
            "code": code,
            "name": name,
            "kind": "state" if code in US_STATES else "territory",
            "official_url": urls.get(code, ""),
            "collectors": [
                {"tier": t,
                 "method": TIERS[t]["method"],
                 "health_id": TIERS[t]["health_id"],
                 "cadence": cadences.get(t, "")}
                for t in tiers if t in TIERS
            ],
            # Freshness, as source_freshness.py last judged it. Three ledger
            # states plus the absent one; the verdict is the sub-state of
            # HEALTHY (PASS / QUIET / DARK / UNKNOWN).
            "freshness": {
                "state": state or "ABSENT",
                "verdict": str(fresh.get("last_verdict") or ""),
                "reason": str(fresh.get("last_reason") or ""),
                "newest_notice": str(fresh.get("frontier") or fresh.get("max_effective") or ""),
                "newest_received": str(fresh.get("frontier_advanced_at") or ""),
                "checked": str(fresh.get("last_checked") or ""),
            },
        }
        if state == "UNAVAILABLE":
            row["unavailable"] = {
                "reason": str(fresh.get("unavailable_reason") or ""),
                "since": str(fresh.get("unavailable_since") or ""),
                "classification": str(fresh.get("classification") or ""),
            }
        # "No public register" is a finding, not a default: it is said only
        # where a human recorded the source UNAVAILABLE for a policy reason AND
        # the importer holds no official page to read (Oklahoma is UNAVAILABLE
        # with a page: it publishes notices without headcounts, which is a
        # different sentence), or where the jurisdiction has no collector, no
        # official URL and no ledger entry at all (the two territories with no
        # WARN programme).
        row["no_public_register"] = bool(
            (state == "UNAVAILABLE" and str(fresh.get("classification")) == "policy"
             and not urls.get(code))
            or (not tiers and not urls.get(code) and not fresh)
        )
        rows.append(row)

    return {
        "note": ("GENERATED by railway/generate_us_registry.py from "
                 "source_inventory.py, the WARN scrapers' own registries, "
                 "sources/warn.py STATE_WARN_URL, source_state.json and the "
                 "WARN workflows' cron lines. Do not hand-edit; re-run the "
                 "generator. tests/test_us_registry.py pins the parity."),
        "generated_on": _dt.date.today().isoformat(),
        "jurisdictions": len(rows),
        "collected": sum(1 for r in rows if r["collectors"]),
        "no_public_register": sum(1 for r in rows if r["no_public_register"]),
        "rows": rows,
    }


def render(doc=None):
    doc = doc or build()
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


#: Per-row keys that are a LIVE READING, not a committed fact, and so are
#: excluded from the parity comparison below.
#:
#: WHY (2026-09-15). `committed_matches` already dropped the top-level
#: `generated_on`, so the calendar was thought about. It did not drop the
#: per-row `freshness` block, which carries `checked` (today's date) and a
#: `reason` recomputed from live history on every run: "14d quiet ... p=0.257"
#: became "15d quiet ... p=0.233" overnight, and Arizona moved QUIET to UNKNOWN
#: because its measured history shrank. So the committed file could not match a
#: fresh build on any day after it was written, and it was committed the day
#: AFTER it was generated, which means this test was red from the moment it
#: landed and stayed red on main, failing every pull request in the repository
#: for a reason no pull request could fix.
#:
#: A guard that fails daily whatever the code does is a guard everybody learns
#: to scroll past, which is the same lesson as eight identical CI emails in one
#: afternoon. What the test exists to catch is a COLLECTOR change reaching the
#: public page in the same commit, and that is entirely outside this block: the
#: jurisdiction set, the health ids, the official URLs, the cadence and the
#: no_public_register flags all still compare exactly.
#:
#: Freshness on the page is not weakened by this. The plugin reads the live
#: health ledger at render time, which is the only place a current reading can
#: come from; a date frozen into a committed artifact is stale the moment it is
#: written, and comparing it promised a currency the file never had.
LIVE_ROW_KEYS = ("freshness",)


def _without_live_readings(doc):
    """A copy of `doc` with the volatile per-row readings removed."""
    out = dict(doc)
    out.pop("generated_on", None)
    out["rows"] = [
        {k: v for k, v in row.items() if k not in LIVE_ROW_KEYS}
        for row in doc.get("rows", [])
    ]
    return out


def committed_matches(path=OUT):
    """True when the committed file equals a fresh build.

    Compares everything the COLLECTORS determine and nothing that a clock
    determines. See LIVE_ROW_KEYS for why, and for what is still pinned.
    """
    try:
        old = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return _without_live_readings(old) == _without_live_readings(build())


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    OUT.write_text(render(doc), encoding="utf-8")
    print(f"wrote {OUT}: {doc['jurisdictions']} jurisdictions, "
          f"{doc['collected']} collected, {doc['no_public_register']} with no public register")
