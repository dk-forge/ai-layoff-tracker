#!/usr/bin/env python3
"""Recall against an INDEPENDENT gold set — one definition, three consumers.

WHY THIS EXISTS (the gap it closes, 2026-08-01)
-----------------------------------------------
`recall_precision.py` has printed a recall percentage since it was written and
has never been able to report a regression: no threshold, `return 0` at the end
of main(), so every run is green whatever the number says. That is the exact
"a check that resolves to a silent pass" this project forbids, one level up from
the bug data_integrity.py exists to catch.

It also measured the wrong thing. `seed_data/recall_goldset.csv` is 40 hand-
listed companies from a research sweep, matched by asking whether that company
appears ANYWHERE in our data in that YEAR. Amazon, Microsoft, Meta, Oracle,
Volkswagen: the largest and most-reported cuts of the year, checked for company
presence rather than for the event. It cannot go far below the ~80% it reports,
because the companies in it are the ones every source covers. It is kept and
still printed — it is a useful smoke test of the biggest names — but it is
labelled for what it is and it carries no threshold.

WHAT THIS MODULE MEASURES INSTEAD
---------------------------------
`docs/recall-reference-sets/sec-item-205-us-2025-07_2026-06.goldset.json`:
every SEC Form 8-K filed 2025-07-01..2026-06-30 whose STRUCTURED item array
carries code 2.05 ("Costs Associated with Exit or Disposal Activities") and
whose text states an absolute count of affected employees. 57 events. The
manifest carries, per event, the filing URL, the verbatim count sentence, the
employer aliases (all taken from the filing, never from a tracker lookup), the
match window, and an editor's per-row decision with its evidence.

Independent because the enumeration is the filer's own item code in a primary
regulator index; no aggregator and no competitor list was consulted, and the
selection rule was fixed before any tracker query. NOT independent of the
tracker's design: an EDGAR collector already reads this corpus, so what this
measures is whether the pipeline captures what its own primary source publishes.

WHY THE FLOOR IS A COUNT AND NOT THE INTERVAL'S LOWER BOUND
-----------------------------------------------------------
Two different questions, and mixing them is a scope error of the kind
data_integrity.plausibility_ratio() refuses:

  "What is recall over all such filings?"  -> a proportion estimated from a
      sample of 57. At 24 matched, the Wilson 95% interval is [30%, 55%]. A
      small sample is a WIDE INTERVAL, not a precise number.
  "Did we lose events we already held?"    -> the gold set is FROZEN and
      re-measured against live data, so between runs the denominator cannot
      move and the numerator changes only when the tracker really gains or
      loses one of those 57 events. There is no sampling noise to absorb.

The floor answers the second question. It is MATCHED_FLOOR events out of the
frozen 57, set below today's measurement with headroom for name-normalisation
churn and dedup merges. Do not "update" it to whatever the current run says;
that is how a tripwire becomes a rubber stamp.

HONEST DEGRADATION
------------------
PASS / FAIL / UNKNOWN, never two of them. An event whose query could not be
completed is UNKNOWN, never a miss, and above UNREACHABLE_CEILING the whole
measurement is UNKNOWN — a Bluehost 504 must not manufacture a recall
regression, which is the same rule ci_alert.py learned on 2026-07-31. A missing
or stale measurement file is UNKNOWN too. Absence of a signal is not a pass.

USAGE
    python3 railway/recall_goldset.py            # re-measure, print, exit 0/2/3
    python3 railway/recall_goldset.py --write    # write recall_measurement.json AND
                                                 # the plugin's render copy (one
                                                 # writer: write_measurement)
"""
import json
import math
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MANIFEST_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
                 / "sec-item-205-us-2025-07_2026-06.goldset.json")
# Committed, because the thing being watched changes without a commit and a
# result that lives only in a runner is a result that resets every night. This
# is the same reasoning as railway/headline_baseline.json.
MEASUREMENT_PATH = HERE / "recall_measurement.json"
# The tracker page's "how complete is that, measured?" paragraph renders from
# this file (db.php alt_recall_measurement()), so the public numbers follow the
# measurement instead of being typed into the template. It lives INSIDE the
# plugin directory because the FTPS deploy only uploads that tree.
PLUGIN_MEASUREMENT_PATH = (REPO_ROOT / "wordpress-plugin" / "ai-layoff-tracker"
                           / "data" / "recall-measurement.json")

# ---------------------------------------------------------------------------
# THE BOUNDS. Read the reasoning above before changing one.
# ---------------------------------------------------------------------------
# Measured 2026-08-01: 24 of 57 events matched (42.1%, Wilson 95% [30.2%,
# 55.0%]). The floor sits four events below that. Four is the headroom, and it
# is the number of currently-held events that would have to vanish before this
# fires: enough that a company rename breaking one alias, or a dedup pass
# merging a pair of rows, does not redden CI; few enough that a collector
# regression or a bad purge-reload does. It is NOT 30% (the interval's lower
# bound) because that bound describes uncertainty about the POPULATION, and the
# denominator here is frozen.
MATCHED_FLOOR = 20

# Above this many unresolvable queries the run says UNKNOWN instead of
# reporting a recall figure. 6 of 57 is ~10%: enough to ride out a couple of
# timeouts, few enough that a real outage cannot be laundered into a number.
UNREACHABLE_CEILING = 6

# The measurement is refreshed by recall-precision.yml, which runs MONDAYS.
# A ceiling must match the job's REAL cadence — a 2-day ceiling on a weekly job
# is permanent noise that hides real breakage (see CLAUDE.md, news_catchup).
MAX_MEASUREMENT_AGE_DAYS = 9

PASS, FAIL, UNKNOWN = "pass", "fail", "unknown"

# Corporate suffixes dropped before the token-prefix comparison. Kept small and
# explicit: an over-eager stopword list is how "Vertex, Inc." starts matching
# "Vertex Pharmaceuticals".
_SUFFIXES = {"inc", "corp", "corporation", "co", "company", "ltd", "limited",
             "llc", "lp", "plc", "nv", "sa", "se", "ag", "the", "holdings",
             "holding"}


def wilson(successes, total, z=1.96):
    """(point, low, high) — the Wilson score interval for a proportion.

    Wilson rather than the normal approximation because the numbers here are
    small and sometimes at the boundary: at 53 of 53 the normal interval is
    [1.0, 1.0], which reads as certainty from 53 observations. Wilson gives
    [93.2%, 100%], which is the truth.

    Returns (None, None, None) for an empty sample — never 0.0, which a caller
    would render as a measured zero.
    """
    if not total:
        return (None, None, None)
    p = successes / float(total)
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / total + z * z / (4.0 * total * total))
    return (p, max(0.0, centre - margin), min(1.0, centre + margin))


def format_interval(successes, total):
    p, lo, hi = wilson(successes, total)
    if p is None:
        return f"{successes}/{total} — no sample, so no interval"
    return (f"{successes}/{total} = {p:.1%}  (Wilson 95% CI [{lo:.1%}, {hi:.1%}], "
            f"width {hi - lo:.1%})")


def _tokens(name):
    words = re.sub(r"[^A-Za-z0-9]+", " ", (name or "").lower()).split()
    return [w for w in words if w and w not in _SUFFIXES]


def name_matches(alias, company_name):
    """True when `company_name` starts with every token of `alias`.

    A PREFIX and not a substring, which is the whole reason the numbers here
    mean anything: the live API's `company=` filter is a substring LIKE, so a
    naive containment test scores Experian as Xperi, Capgemini as Gemini,
    Insight Behavioral as Sight Sciences and a Baltic fish processor as KALA
    BIO. All four were observed on 2026-08-01.
    """
    a, n = _tokens(alias), _tokens(company_name)
    return bool(a) and n[:len(a)] == a


def _default_fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_manifest(path=None):
    return json.loads(Path(path or MANIFEST_PATH).read_text(encoding="utf-8"))


def load_measurement(path=None):
    try:
        return json.loads(Path(path or MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def match_event(event, rows):
    """The tracker rows that represent this gold event, by the manifest's rule."""
    aliases = event.get("employer_aliases") or []
    blocked = event.get("excluded_name_prefixes") or []
    lo, hi = (_parse_date(x) for x in (event.get("match_window") or [None, None]))
    hits = []
    for row in rows:
        name = row.get("company_name") or ""
        if any(name_matches(b, name) for b in blocked):
            continue
        if not any(name_matches(a, name) for a in aliases):
            continue
        when = _parse_date(row.get("layoff_date")) or _parse_date(row.get("announcement_date"))
        if when and lo and hi and lo <= when <= hi:
            hits.append(row)
    return hits


def measure(fetch=None, manifest=None, sleep=None):
    """Re-run the frozen gold set against the LIVE API. Read-only GETs.

    THE NUMERATOR IS EDITOR-CONFIRMED, AND THAT IS DELIBERATE. Only events whose
    `match_decision` is "matched" can count. The alias/window rule is what a
    machine can do; deciding that a row is the SAME UNDERLYING EVENT is not, and
    when the two were compared on 2026-08-01 the machine scored 31 of 57 against
    the editor's 24 — it had accepted a Hormel Georgia WARN filed ten weeks
    before the announcement it was supposed to represent, an Italian composites
    maker for HP Inc, and Dow Jones for Dow. Letting the loose rule set the
    published figure would have inflated recall by twelve points. So a row that
    newly satisfies alias+window for a NOT-matched event is reported as needing
    adjudication and is never counted: a machine must not promote its own recall
    by finding a row nobody has looked at.

    Returns the measurement dict that gets committed. Never raises on a
    transport fault: a failed lookup lands in `unreachable`, which the judge
    turns into UNKNOWN rather than into a miss.
    """
    import time
    fetch = fetch or _default_fetch
    sleep = time.sleep if sleep is None else sleep
    manifest = manifest or load_manifest()
    events = manifest["reference_events"]
    present, lost, known_absent, unreachable, candidates = [], [], [], [], []
    for event in events:
        rows, failed = {}, None
        for alias in event.get("employer_aliases") or []:
            url = BASE + "query?" + urllib.parse.urlencode(
                {"company": alias, "per_page": 100, "cb": _cachebust()})
            try:
                payload = json.loads(fetch(url)) or {}
            except Exception as exc:                       # noqa: BLE001 — any transport fault
                failed = f"{type(exc).__name__}: {exc}"
                continue
            for row in payload.get("data") or []:
                rows[row.get("id")] = row
            sleep(0.15)
        if failed and not rows:
            unreachable.append({"id": event["reference_row_id"], "why": failed})
            continue
        hits = match_event(event, list(rows.values()))
        found = sorted({h.get("event_id") for h in hits if h.get("event_id") is not None})
        record = {"id": event["reference_row_id"], "filer": event["filer"],
                  "filing_date": event["filing_date"],
                  "stated_job_count": event.get("stated_job_count"),
                  "tracker_event_ids": found}
        if event.get("match_decision") == "matched":
            (present if hits else lost).append(record)
        else:
            known_absent.append(record)
            fresh = [i for i in found
                     if i not in (event.get("rejected_candidate_event_ids") or [])]
            if fresh:
                candidates.append({**record, "new_tracker_event_ids": fresh})
    return {
        "note": ("Recall of the frozen SEC Item 2.05 gold set against the live API. "
                 "Written by recall-precision.yml. Committed on purpose: the data being "
                 "measured changes without a commit. Do not hand-edit this file to clear "
                 "a failing floor."),
        "reference_set_id": manifest.get("reference_set_id"),
        "reference_set_path": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "measured_at": _utc_now_iso(),
        "reference_events": len(events),
        "matched": len(present),
        "missed": len(lost) + len(known_absent),
        "lost_since_adjudication": lost,
        "unreachable": len(unreachable),
        "matched_floor": MATCHED_FLOOR,
        "matched_ids": [m["id"] for m in present],
        "missed_events": known_absent,
        "unreachable_events": unreachable,
        "candidates_needing_adjudication": candidates,
    }


def judge(measurement, now=None):
    """(state, detail) for one measurement. The single definition of the floor.

    Imported by data_integrity.RecallFloorInvariant, by recall_precision.py's
    exit code and by the tests, so the bound cannot drift between the guard that
    reddens CI and the dashboard that says all is well.
    """
    if not isinstance(measurement, dict):
        return UNKNOWN, ("no recall measurement has been written yet — recall is UNMEASURED, "
                         "not fine. recall-precision.yml writes railway/recall_measurement.json "
                         "on Mondays; run `python3 railway/recall_goldset.py --write` to seed it")
    total = measurement.get("reference_events")
    matched = measurement.get("matched")
    unreachable = measurement.get("unreachable") or 0
    floor = measurement.get("matched_floor", MATCHED_FLOOR)
    if not isinstance(total, int) or not isinstance(matched, int) or not total:
        return UNKNOWN, f"unreadable recall measurement: {measurement!r}"

    age = _days_since(measurement.get("measured_at"), now)
    if age is None:
        return UNKNOWN, (f"measurement has no readable timestamp: "
                         f"{measurement.get('measured_at')!r}")
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the recall measurement is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind main or "
                         f"recall-precision.yml has stopped. Recall is UNVERIFIED, not passing")
    if unreachable > UNREACHABLE_CEILING:
        return UNKNOWN, (f"{unreachable} of {total} gold events could not be looked up (ceiling "
                         f"{UNREACHABLE_CEILING}) — the host was unreachable for enough of the "
                         f"set that no recall figure is trustworthy. NOT a recall regression")

    shown = format_interval(matched, total)
    if matched < floor:
        lost = ", ".join(f"{x['filer']} ({x['filing_date']})"
                         for x in (measurement.get("lost_since_adjudication") or [])[:6])
        return FAIL, (f"only {matched} of the {total} frozen SEC Item 2.05 gold events are in the "
                      f"published data — floor is {floor}. {shown}. The gold set is frozen, so "
                      f"this is not sampling noise: {floor - matched} event(s) the tracker used "
                      f"to hold are gone, or the employer names they are matched on changed"
                      + (f". Gone: {lost}" if lost else "") +
                      f". Check the last /bulk-purge, the reconcile-supersets run and any company "
                      f"rename before quoting a coverage figure")
    return PASS, f"{shown}; floor {floor} of {total}, {unreachable} unreachable"


def _cachebust():
    import uuid
    return uuid.uuid4().hex[:10]


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_since(stamp, now=None):
    if not stamp:
        return None
    try:
        when = datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return max(0.0, ((now or datetime.now(timezone.utc)) - when).total_seconds() / 86400.0)


def _render_payload(measurement, precision=None, previous=None):
    """What the plugin renders: the four public fields, plus precision if known.

    When `precision` is None the caller measured recall WITHOUT a precision
    sample (`recall_goldset.py --write`, the path a re-measure after an
    adjudication takes). Dropping the block would silently delete the "counts
    appear verbatim in their own source" sentence from the live page, so the
    previous copy's block is carried forward instead — it is dated, and the page
    prints it as a separate claim.
    """
    payload = {
        "matched": measurement.get("matched"),
        "reference_events": measurement.get("reference_events"),
        "reference_set_id": measurement.get("reference_set_id"),
        "measured_at": measurement.get("measured_at"),
        "note": ("Render copy of railway/recall_measurement.json for the tracker page's "
                 "measured-completeness paragraph. Written by recall_goldset.write_measurement(), "
                 "which is the ONLY writer of either file — so every path that moves the "
                 "canonical figure moves this one too. railway/tests/test_archive_promise.py "
                 "pins them together. Do not hand-edit."),
    }
    prec = None
    if precision and precision.get("checked"):
        prec = {"ok": precision["ok"], "checked": precision["checked"],
                "measured_at": str(date.today())}
    elif isinstance((previous or {}).get("precision_verbatim"), dict):
        prec = previous["precision_verbatim"]
    if prec:
        payload["precision_verbatim"] = prec
    return payload


def write_measurement(measurement, precision=None, measurement_path=None,
                      plugin_path=None):
    """Write the canonical measurement AND the plugin's render copy. The ONE writer.

    Both files or neither. They drifted for two days because there were two
    writers: recall_precision.py wrote the pair, and `recall_goldset.py --write`
    — the path a human takes right after an adjudication moves the figure —
    wrote only the canonical file. The live page kept publishing 24 of 57 while
    the repo said 52. A second writer of one of two files that must agree is the
    defect; this function exists so there is one.

    The render copy is still rewritten only when a FIGURE moves: a timestamp-only
    weekly refresh would touch the plugin tree and trigger a real FTPS deploy
    every Monday for no reader-visible change.
    """
    canonical = Path(measurement_path or MEASUREMENT_PATH)
    canonical.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    print(f"measurement written: {canonical}")

    render = Path(plugin_path or PLUGIN_MEASUREMENT_PATH)
    try:
        old = json.loads(render.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    payload = _render_payload(measurement, precision, old)

    def figures(d):
        return (d.get("matched"), d.get("reference_events"), d.get("reference_set_id"),
                (d.get("precision_verbatim") or {}).get("ok"),
                (d.get("precision_verbatim") or {}).get("checked"))

    if figures(old) == figures(payload):
        print(f"plugin render copy unchanged (no figure moved): {render}")
        return False
    render.parent.mkdir(parents=True, exist_ok=True)
    render.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"plugin render copy written: {render}")
    return True


def main(argv=None):
    argv = argv or sys.argv[1:]
    try:
        measurement = measure()
    except Exception as exc:                              # noqa: BLE001
        print(f"recall gold set: could not measure ({exc}) — UNKNOWN, not a pass")
        return 3
    state, detail = judge(measurement)
    print("SEC ITEM 2.05 GOLD-SET RECALL")
    print(f"  {state.upper():7s} {detail}")
    for miss in measurement["lost_since_adjudication"]:
        print(f"    LOST {miss['filing_date']} {miss['filer'][:40]:40s} "
              f"{miss['stated_job_count']}  (an editor confirmed this one was held)")
    for miss in measurement["missed_events"]:
        print(f"    MISS {miss['filing_date']} {miss['filer'][:40]:40s} "
              f"{miss['stated_job_count']}")
    for c in measurement["candidates_needing_adjudication"]:
        print(f"    ADJUDICATE {c['filing_date']} {c['filer'][:36]:36s} new tracker events "
              f"{c['new_tracker_event_ids']} — NOT counted until an editor decides")
    if "--write" in argv:
        # Writes the plugin render copy too. This path has no precision sample,
        # so the copy's existing precision block is carried forward rather than
        # dropped — see _render_payload.
        write_measurement(measurement)
    return {PASS: 0, FAIL: 2, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
