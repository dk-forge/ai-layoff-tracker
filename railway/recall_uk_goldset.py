#!/usr/bin/env python3
"""Recall against the INDEPENDENT UK reference set — the second country measured.

WHY A SECOND MODULE AND NOT A SECOND MANIFEST
---------------------------------------------
The US set (`recall_goldset.py`) measures ONE event type from ONE primary index:
SEC Form 8-K carrying structured item code 2.05. The UK has no Item 2.05 and no
public employer-level equivalent, so the UK set is a DIFFERENT EVENT TYPE — see
`docs/recall-reference-sets/UK-REFERENCE-SET-DEFINITION.md`, which was written
and committed before any number was measured, deliberately.

What must NOT differ between the two is the discipline, so everything that
encodes the discipline is IMPORTED from recall_goldset rather than re-typed:

    wilson / format_interval   one interval definition
    name_matches / match_event one alias+window rule, prefix not substring
    PASS / FAIL / UNKNOWN      three states, absence of a signal is not a pass

A copy of `name_matches` here would be a second place for the Xperi/Experian
bug to come back.

THE NUMERATOR IS EDITOR-CONFIRMED, exactly as in the US set. Only events whose
`match_decision` is "matched" count. A row that newly satisfies alias+window for
an unmatched event is reported under `candidates_needing_adjudication` and is
NEVER counted: a machine must not promote its own recall by finding a row nobody
has looked at. On 2026-08-01 the loose rule scored 31 of 57 against an editor's
24 on the US set; there is no reason to think it is kinder here.

NO FLOOR YET, AND THAT IS DELIBERATE
------------------------------------
`recall_goldset.MATCHED_FLOOR` exists to detect LOSS of events already held. It
was set four events below a figure an editor had adjudicated. This module ships
with `MATCHED_FLOOR = None`, which judges to UNKNOWN-with-a-figure rather than
PASS, because on day one nobody has adjudicated anything and a floor invented by
the same run that produced the number is a rubber stamp, not a tripwire. Set it
after the first human adjudication pass, in a commit that says who did it.

USAGE
    python3 railway/recall_uk_goldset.py            # measure, print, exit 0/2/3
    python3 railway/recall_uk_goldset.py --write    # also write the measurement
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from recall_goldset import (FAIL, PASS, UNKNOWN, _cachebust, _days_since,
                            _utc_now_iso, format_interval, match_event, wilson)

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MANIFEST_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
                 / "uk-hansard-2024-07_2026-06.goldset.json")
# Named UK_MEASUREMENT_PATH, not MEASUREMENT_PATH, on purpose. The SEC figure
# is published and its two files must never drift, so
# test_archive_promise.test_only_one_function_writes_either_measurement_file
# forbids any railway/*.py but recall_goldset.py from writing a name-matched
# MEASUREMENT_PATH. This is a different, unpublished file with no plugin render
# copy; the distinct name keeps that guard exactly as strict as it was.
UK_MEASUREMENT_PATH = HERE / "recall_uk_measurement.json"

# See the module docstring. None means "no tripwire armed yet", which judges to
# UNKNOWN rather than PASS. It is not zero: zero would be a floor that can
# never fire, dressed as a floor that can.
MATCHED_FLOOR = None

# 10% of a ~50-event set, same reasoning as the US ceiling: enough to ride out
# a couple of timeouts, few enough that a host outage cannot be laundered into
# a recall figure.
UNREACHABLE_CEILING_FRACTION = 0.10

MAX_MEASUREMENT_AGE_DAYS = 9


def _default_fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_manifest(path=None):
    return json.loads(Path(path or MANIFEST_PATH).read_text(encoding="utf-8"))


def load_measurement(path=None):
    try:
        return json.loads(Path(path or UK_MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def measure(fetch=None, manifest=None, sleep=None):
    """Re-run the frozen UK set against the LIVE API. Read-only GETs.

    Identical contract to recall_goldset.measure(): a transport fault lands in
    `unreachable` and becomes UNKNOWN, never a miss.

    ONE UK-SPECIFIC PARAMETER. The query is asked with `country_basis=any`,
    which is the basis the reader's own country filter uses (CLAUDE.md: the
    table and exports union job-location OR employer-HQ). A UK reference event
    is a UK job cut; asking on the strict job-location basis would score a
    US-HQ multinational's British redundancies as a miss when the reader can
    see them perfectly well under a UK filter. The basis is recorded in the
    measurement so it cannot drift silently.
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
                {"company": alias, "country_basis": "any", "per_page": 100,
                 "cb": _cachebust()})
            try:
                payload = json.loads(fetch(url)) or {}
            except Exception as exc:                       # noqa: BLE001
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
        record = {"id": event["reference_row_id"], "employer": event["employer"],
                  "announcement_date": event["announcement_date"],
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
        "note": ("Recall of the frozen UK reference set against the live API. "
                 "Committed on purpose: the data being measured changes without a "
                 "commit. Do not hand-edit this file to clear a failing floor."),
        "reference_set_id": manifest.get("reference_set_id"),
        "reference_set_path": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "country_basis": "any",
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
    """(state, detail). UNKNOWN until a human arms a floor — see the docstring."""
    if not isinstance(measurement, dict):
        return UNKNOWN, ("no UK recall measurement has been written yet — UK recall is "
                         "UNMEASURED, not fine. Run "
                         "`python3 railway/recall_uk_goldset.py --write` to seed it")
    total = measurement.get("reference_events")
    matched = measurement.get("matched")
    unreachable = measurement.get("unreachable") or 0
    floor = measurement.get("matched_floor", MATCHED_FLOOR)
    if not isinstance(total, int) or not isinstance(matched, int) or not total:
        return UNKNOWN, f"unreadable UK recall measurement: {measurement!r}"

    age = _days_since(measurement.get("measured_at"), now)
    if age is None:
        return UNKNOWN, (f"measurement has no readable timestamp: "
                         f"{measurement.get('measured_at')!r}")
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the UK recall measurement is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind "
                         f"main or the refresh job has stopped. UNVERIFIED, not passing")
    ceiling = max(1, int(round(total * UNREACHABLE_CEILING_FRACTION)))
    if unreachable > ceiling:
        return UNKNOWN, (f"{unreachable} of {total} UK reference events could not be looked "
                         f"up (ceiling {ceiling}) — the host was unreachable for enough of "
                         f"the set that no recall figure is trustworthy. NOT a regression")

    shown = format_interval(matched, total)
    if floor is None:
        return UNKNOWN, (f"{shown}. No floor is armed: this set has not yet been through a "
                         f"human adjudication pass, and a floor set by the same run that "
                         f"produced the number is a rubber stamp. The figure is REPORTED, "
                         f"not GUARDED")
    if matched < floor:
        lost = ", ".join(f"{x['employer']} ({x['announcement_date']})"
                         for x in (measurement.get("lost_since_adjudication") or [])[:6])
        return FAIL, (f"only {matched} of the {total} frozen UK reference events are in the "
                      f"published data — floor is {floor}. {shown}. The set is frozen, so "
                      f"this is not sampling noise"
                      + (f". Gone: {lost}" if lost else ""))
    return PASS, f"{shown}; floor {floor} of {total}, {unreachable} unreachable"


def main(argv=None):
    argv = argv or sys.argv[1:]
    try:
        measurement = measure()
    except Exception as exc:                              # noqa: BLE001
        print(f"UK reference set: could not measure ({exc}) — UNKNOWN, not a pass")
        return 3
    state, detail = judge(measurement)
    print("UK REFERENCE-SET RECALL")
    print(f"  {state.upper():7s} {detail}")
    for miss in measurement["lost_since_adjudication"]:
        print(f"    LOST {miss['announcement_date']} {miss['employer'][:40]:40s} "
              f"{miss['stated_job_count']}  (an editor confirmed this one was held)")
    for miss in measurement["missed_events"]:
        print(f"    MISS {miss['announcement_date']} {miss['employer'][:40]:40s} "
              f"{miss['stated_job_count']}")
    for c in measurement["candidates_needing_adjudication"]:
        print(f"    ADJUDICATE {c['announcement_date']} {c['employer'][:36]:36s} new tracker "
              f"events {c['new_tracker_event_ids']} — NOT counted until an editor decides")
    if "--write" in argv:
        UK_MEASUREMENT_PATH.write_text(
            json.dumps(measurement, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"  written: {UK_MEASUREMENT_PATH}")
    return {PASS: 0, FAIL: 2, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
