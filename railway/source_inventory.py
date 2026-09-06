#!/usr/bin/env python3
"""What the pipeline is SUPPOSED to have, so absence can be a finding.

THE BUG THIS IS FOR, WHICH IS NOT THE FRESHNESS BUG
---------------------------------------------------
`source_freshness` answers "this collector reports ok — is it actually bringing
back anything new?". That is a source that lies.

This module answers a different and worse question: **which sources never
report at all?** A collector that has never written a health row does not show
up green. It does not show up. Every guard in this repo was built against the
list of things that DO report — the health ledger, the digest's staleness map,
ops_status's MAX_AGE table — and a thing missing from that list reads as "no
problem" rather than "never looked at". Nothing anywhere hints it exists.

So the inventory is deliberately built from the OTHER side: from what the code
and the public sources page say should exist, never from what answered. Then the
diff against the health ledger names the gap.

NEVER_REPORTED is the fourth state, alongside HEALTHY / BROKEN / UNAVAILABLE,
and it is the most alarming of the four.

WHY THE US JURISDICTION LIST IS SPELLED OUT AND THE COLLECTOR LIST IS NOT
-------------------------------------------------------------------------
The 56 US jurisdictions are a constitutional fact, not a fact about this
codebase, and they are exactly the "should exist" side of the diff: a state with
no collector wired at all cannot be discovered by reading the collectors. That
list is therefore written down.

Everything else is DERIVED — from `warn.ALL_STATES`, from the custom-scraper
registries, and from the public health page's own `meta{}` map — so a collector
added later is inventoried by construction rather than by somebody remembering
to add it here. `tests/test_source_freshness.py` pins that: a new id in the
health page's registry is a new inventory row the same day.
"""

import datetime as _dt
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
HEALTH_JS = os.path.join(os.path.dirname(HERE), "wordpress-plugin",
                         "ai-layoff-tracker", "assets", "health.js")

NEVER_REPORTED = "NEVER_REPORTED"

#: The 50 states, DC, and the five inhabited territories. The "should exist"
#: side of the diff. PR/GU/VI publish no WARN list and are recorded UNAVAILABLE
#: in railway/source_state.json by a human; AS and MP have no WARN programme.
US_STATES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS "
    "MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV "
    "WI WY".split())
US_TERRITORIES = ["DC", "PR", "GU", "VI", "AS", "MP"]
US_JURISDICTIONS = US_STATES + US_TERRITORIES


def warn_collectors():
    """{STATE: [collector tier, ...]} for every US jurisdiction we collect.

    Read from the scrapers' own registries. A state served by two tiers lists
    both; a state served by none is absent, and that absence is the finding.
    """
    out = {}

    def add(states, tier):
        for st in states or ():
            out.setdefault(str(st).upper(), []).append(tier)

    try:
        from sources.warn import ALL_STATES
        add(ALL_STATES, "generic")
    except Exception:
        pass
    try:
        from sources.warn_custom import CUSTOM_STATES
        add(CUSTOM_STATES, "legacy_custom")
    except Exception:
        pass
    try:
        from sources.warn_new_states import NEW_CUSTOM_STATES
        add(NEW_CUSTOM_STATES, "new_custom")
    except Exception:
        pass
    # Hawaii's notices are scanned images and it has its own OCR collector,
    # which reports under its own health id rather than through warn_import.
    out.setdefault("HI", []).append("hi_ocr")
    return out


_META_ID = re.compile(r"^\s{4}([a-z][a-z0-9_]*)\s*:\s*\[", re.M)


def declared_collectors(path=HEALTH_JS):
    """Every collector id the public health page declares a label for.

    The `meta{}` map in assets/health.js is the registry the session ritual
    already requires to be updated whenever a source is added, removed or
    blocked ("add its friendly label to assets/health.js meta{}"). Reading it
    here is what turns that ritual into a checkable fact instead of a habit.

    Returns () when the file cannot be read — the caller must report that as
    UNKNOWN. An inventory that silently reads empty is the very failure this
    module exists to catch.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
    except OSError:
        return ()
    start = body.find("const meta")
    if start < 0:
        return ()
    return tuple(sorted(set(_META_ID.findall(body[start:]))))


def reporting_collectors(health):
    """Every id present in the live health ledger, whatever its status."""
    return tuple(sorted(k for k, v in (health or {}).items()
                        if isinstance(v, dict)))


#: Declared collectors whose FIRST run is scheduled for a date that has not
#: arrived yet. A monthly slot armed on the 6th cannot have a health row until
#: the 1st, and calling that "never reported" hands the owner a red action item
#: for 25 days, which is how a real never-reported collector learns to hide in
#: a list nobody reads. The entry carries the date the first run is due; on and
#: after that date the collector is judged like any other, with no exemption.
#: Absence stays UNKNOWN either way. It is never a pass.
NOT_YET_DUE = {
    # The monthly digest slot was armed 2026-09-06 and first fires 9:00 ET on
    # 2026-10-01 (railway/digest_send.py SEND_TIMES).
    "digest_monthly": "2026-10-01",
}


def not_yet_due(collector, today=None):
    """True while a declared collector's first scheduled run is still ahead."""
    due = NOT_YET_DUE.get(collector)
    if not due:
        return False
    if today is None:
        today = _dt.date.today().isoformat()
    return str(today) < due


def never_reported(health, path=HEALTH_JS):
    """Declared but never seen in the health ledger. The fourth state.

    Raises ValueError when the declaration cannot be read, because an empty
    inventory would answer "nothing is missing" — a true-but-empty signal, which
    is the class of bug this whole change is about.
    """
    declared = declared_collectors(path)
    if not declared:
        raise ValueError(f"could not read the collector registry from {path}")
    missing = set(declared) - set(reporting_collectors(health))
    return tuple(sorted(c for c in missing if not not_yet_due(c)))


def awaiting_first_run(health, path=HEALTH_JS, today=None):
    """Declared, silent, and legitimately so: the first run is still ahead."""
    declared = declared_collectors(path)
    if not declared:
        raise ValueError(f"could not read the collector registry from {path}")
    missing = set(declared) - set(reporting_collectors(health))
    return tuple(sorted(c for c in missing if not_yet_due(c, today=today)))


def uncollected_jurisdictions():
    """US jurisdictions with no WARN collector wired at all."""
    have = warn_collectors()
    return tuple(j for j in US_JURISDICTIONS if j not in have)


#: Directories that cannot vouch for a collector's existence.
#:
#: `__pycache__` / `.pytest_cache` are build residue —
#: `.pytest_cache/v/cache/nodeids` mentions almost every id in the repo, so
#: counting it would let a deleted collector keep vouching for itself until
#: somebody cleared a cache.
#:
#: `tests` is excluded on the merits, not for convenience: a collector named
#: ONLY by a test that asserts something about it has still not been built, and
#: the test asserting this very property necessarily spells its own fixture id.
_NOT_CODE = {"__pycache__", ".pytest_cache", ".git", "node_modules", "tests"}


def _implementation_corpus():
    """Every byte of code that could plausibly name a collector.

    railway/ (the modules that run and the workflows' entry points) plus
    .github/workflows/ (the schedules that run them). Read as text, searched
    for the literal id — deliberately the WEAKEST possible test of existence,
    because the finding it has to survive is "no hit anywhere at all".
    """
    roots = [HERE, os.path.join(os.path.dirname(HERE), ".github", "workflows")]
    blob = []
    for root in roots:
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _NOT_CODE]
            for name in files:
                if not name.endswith((".py", ".yml", ".yaml", ".json", ".csv")):
                    continue
                try:
                    with open(os.path.join(dirpath, name),
                              encoding="utf-8", errors="ignore") as fh:
                        blob.append(fh.read())
                except OSError:
                    continue
    return "\n".join(blob)


def unimplemented_collectors(path=HEALTH_JS):
    """Declared on the public health page, but named by NO code in this repo.

    THE DEFECT THIS IS FOR
    ----------------------
    `never_reported` catches a collector that exists and is silent. This
    catches the one underneath it: a collector that was never built, whose
    label was written anyway.

    One collector was declared in `meta{}` in 2.19.84 with a full description
    ending "Transcript API", and no module, no workflow and no `cron.py` line
    ever followed — the transcript endpoint it needed turned out to be
    paid-only and the intent was dropped the same week, but the label stayed.
    For thirteen months every session was told a collector had never reported,
    which was true and which no amount of investigating a collector could ever
    resolve, because there was no collector. (Its id is deliberately NOT spelled
    anywhere in this module: naming it here would put it in the corpus below and
    make the label vouch for itself. The story is in the test and in TECHLOG,
    both outside the corpus. Found by mutating this very guard.)

    A `meta{}` entry is a promise on a public surface. This makes the promise
    cost something: the id must be named by at least one file that runs.

    Raises ValueError when the declaration cannot be read, for the same reason
    `never_reported` does — an empty registry would answer "nothing is missing".
    """
    declared = declared_collectors(path)
    if not declared:
        raise ValueError(f"could not read the collector registry from {path}")
    corpus = _implementation_corpus()
    return tuple(i for i in declared if i not in corpus)


def summary(health, path=HEALTH_JS):
    """The thirty-second picture: watched, reporting, never looked at."""
    out = {"jurisdictions": len(US_JURISDICTIONS),
           "jurisdictions_collected": len(warn_collectors()),
           "jurisdictions_uncollected": list(uncollected_jurisdictions()),
           "declared_collectors": len(declared_collectors(path))}
    try:
        out["never_reported"] = list(never_reported(health, path))
        out["awaiting_first_run"] = list(awaiting_first_run(health, path))
    except ValueError as exc:
        out["never_reported"] = None          # UNKNOWN, never an empty pass
        out["awaiting_first_run"] = None
        out["never_reported_error"] = str(exc)
    try:
        out["unimplemented"] = list(unimplemented_collectors(path))
    except ValueError as exc:
        out["unimplemented"] = None           # UNKNOWN, never an empty pass
        out["unimplemented_error"] = str(exc)
    out["reporting_collectors"] = len(reporting_collectors(health))
    return out


if __name__ == "__main__":
    import urllib.request
    UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
    url = (os.environ.get("WP_SITE_URL", "https://asktherecruiter.com/blog")
           + "/wp-json/layoffs/v1/source-health")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        live = json.load(urllib.request.urlopen(req, timeout=45))
    except Exception as exc:                                  # noqa: BLE001
        print(f"UNKNOWN: could not read the health ledger ({exc})")
        raise SystemExit(3)
    print(json.dumps(summary(live), indent=2))
