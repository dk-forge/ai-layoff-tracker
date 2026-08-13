#!/usr/bin/env python3
"""Record a human's adjudication of a gold event. The ONLY thing that may.

WHAT THIS IS FOR
----------------
`recall_goldset.measure()` counts an event only where the manifest says
`matched`, and a row that newly satisfies the alias/window rule for a
not-matched event is reported as `candidates_needing_adjudication` and never
counted: "a machine must not promote its own recall". This module is the other
half of that sentence — the place a PERSON promotes one, on the record.

It is local, stdlib-only and network-free ON PURPOSE, the same reason
`data_integrity.close_incident` refuses to re-read the site it is about: the
decision is made against the evidence pack the reviewer read, not against
whatever the live host happens to be serving at the moment they press return.

THE FOUR PROPERTIES IT HAS TO HAVE
----------------------------------
1. REVERSIBLE. Every write snapshots the event's prior fields into the ledger
   first, so `--revert` restores them byte for byte, including removing the
   `adjudication` key on an event that did not have one.
2. ATTRIBUTED. `--reviewed-by` and `--reason` are required and may not be
   blank. A decision with no name on it is indistinguishable from the machine
   promoting itself, which is the thing being prevented.
3. NO SILENT MATCH. `--verify` fails if any event is `matched` without either an
   `adjudication` block or membership in PRE_TOOL_MATCHED — the 24 an editor
   decided on 2026-08-01, before this tool existed. `tests/test_recall_
   adjudication.py` runs it against the real manifest, so a hand-edited
   `match_decision` reddens CI instead of quietly raising the published figure.
4. IDEMPOTENT. Re-running the same decision writes nothing and exits 0. A
   DIFFERENT decision on an already-adjudicated event is REFUSED and told to
   revert first. The numerator counts distinct events, so a double run cannot
   double-count; the ledger must not double-record either.

`--event-ids` TAKES EVERY VALUE UNTIL THE NEXT FLAG. That is not a detail: on
2026-08-12 `--rows 114335 113529 64351` recorded only the first id and exited
zero, closing an incident that named one of three rows. The same field, the same
failure mode, so the same fix, and a test that types it the way a person does.

USAGE
    python3 railway/recall_adjudicate.py --queue
    python3 railway/recall_adjudicate.py --show <reference_row_id>
    python3 railway/recall_adjudicate.py --accept <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why' --event-ids 149909
    python3 railway/recall_adjudicate.py --reject <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why' --event-ids 149625
    python3 railway/recall_adjudicate.py --revert <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why'
    python3 railway/recall_adjudicate.py --verify

EXIT CODES
    0  recorded, or already recorded identically, or verified clean
    2  REFUSED (nothing written), or --verify found an unattributed match
    3  a file could not be read, so nothing could be judged — UNKNOWN
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
MANIFEST_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
                 / "sec-item-205-us-2025-07_2026-06.goldset.json")
PACK_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
             / "sec-item-205-adjudication-queue.json")
# Committed, and append-only. It is the audit trail for the one number in this
# repo a human is allowed to move by hand, so it lives next to the manifest it
# explains rather than in a runner that resets every night.
LEDGER_PATH = HERE / "recall_adjudications.json"

MATCHED = "matched"
NOT_MATCHED = "not_matched"

# The 24 events an editor adjudicated on 2026-08-01, before this tool existed.
# They carry `match_notes` and no `adjudication` block, and that is not a defect
# — it is what a decision made before the ledger looks like. Listed explicitly
# rather than inferred, so the set cannot grow by someone editing the manifest:
# any NEW matched event must come through this module.
PRE_TOOL_MATCHED = frozenset({
    "sec-205-0001751788-25-000139", "sec-205-0001396814-25-000093",
    "sec-205-0000950170-25-096257", "sec-205-0001140361-25-026946",
    "sec-205-0000051434-25-000059", "sec-205-0001193125-25-195066",
    "sec-205-0000829224-25-000067", "sec-205-0001193125-25-245102",
    "sec-205-0001364954-25-000112", "sec-205-0001306830-25-000203",
    "sec-205-0001193125-25-307535", "sec-205-0001193125-25-318445",
    "sec-205-0001705110-26-000005", "sec-205-0000769397-26-000006",
    "sec-205-0001104659-26-007986", "sec-205-0001193125-26-048738",
    "sec-205-0001650372-26-000021", "sec-205-0001193125-26-154873",
    "sec-205-0001679788-26-000049", "sec-205-0001544522-26-000088",
    "sec-205-0001794515-26-000033", "sec-205-0001490281-26-000013",
    "sec-205-0001628280-26-039805", "sec-205-0001193125-26-278582",
})

# The event fields a decision may touch. Everything else in the manifest — the
# accession, the filing URL, the stated count, the aliases, the window — is the
# frozen reference and this module must never write it. Snapshotting exactly
# these is what makes --revert exact.
MUTABLE_FIELDS = ("match_decision", "match_notes", "rejected_candidate_event_ids",
                  "adjudication")


class Refused(Exception):
    """Nothing was written. Raised before any file is touched."""


class Unreadable(Exception):
    """A file this module needs could not be read or parsed."""


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable(f"{what} at {path} could not be read: {exc}") from exc


def load_manifest(path=None):
    return _load(path or MANIFEST_PATH, "the gold-set manifest")


def load_pack(path=None):
    return _load(path or PACK_PATH, "the adjudication pack")


def load_ledger(path=None):
    path = Path(path or LEDGER_PATH)
    if not path.exists():
        return {"note": LEDGER_NOTE, "decisions": []}
    ledger = _load(path, "the adjudication ledger")
    if not isinstance(ledger.get("decisions"), list):
        raise Unreadable(f"the adjudication ledger at {path} has no `decisions` list")
    return ledger


LEDGER_NOTE = (
    "Append-only record of every human adjudication of the SEC Item 2.05 gold set, and of "
    "every reversal. Written ONLY by railway/recall_adjudicate.py. `manifest_before` is the "
    "snapshot --revert restores; do not hand-edit this file, and do not hand-edit "
    "match_decision in the manifest -- `--verify` fails on a matched event that has no "
    "entry here, and the test suite runs it.")


def _event(manifest, reference_row_id):
    for ev in manifest["reference_events"]:
        if ev.get("reference_row_id") == reference_row_id:
            return ev
    known = ", ".join(sorted(e["reference_row_id"] for e in manifest["reference_events"])[:3])
    raise Refused(f"no gold event {reference_row_id!r} in the manifest "
                  f"({len(manifest['reference_events'])} events, e.g. {known})")


def _snapshot(event):
    return {f: json.loads(json.dumps(event[f])) for f in MUTABLE_FIELDS if f in event}


def _restore(event, snapshot):
    for field in MUTABLE_FIELDS:
        event.pop(field, None)
    for field, value in snapshot.items():
        event[field] = value


def _live_entries(ledger, reference_row_id):
    """This event's decisions that have not been reverted, oldest first."""
    reverted = {d["reverts"] for d in ledger["decisions"]
                if d.get("decision") == "revert" and d.get("reverts")}
    return [d for d in ledger["decisions"]
            if d.get("reference_row_id") == reference_row_id
            and d.get("decision") in ("accept", "reject")
            and d.get("entry_id") not in reverted]


def _pack_ids(pack, reference_row_id):
    for entry in pack.get("entries") or []:
        if entry.get("reference_row_id") == reference_row_id:
            return set(entry.get("proposed_tracker_event_ids") or []), entry
    return None, None


def decide(reference_row_id, decision, reviewed_by, reason, event_ids,
           manifest=None, pack=None, ledger=None, now=None):
    """Apply one decision. Returns (manifest, ledger, entry, changed).

    Pure with respect to the filesystem: the caller writes. `changed` is False
    when this exact decision is already recorded, which is the idempotence
    contract — the second run must not append a second identical entry.
    """
    if decision not in ("accept", "reject"):
        raise Refused(f"decision must be accept or reject, not {decision!r}")
    if not (reviewed_by or "").strip():
        raise Refused("--reviewed-by is required and may not be blank. An adjudication "
                      "with no name on it is indistinguishable from the machine "
                      "promoting its own recall, which is the thing this gate prevents")
    if not (reason or "").strip():
        raise Refused("--reason is required and may not be blank. Record what in the "
                      "filing and in the row decided it, not that a decision was made")
    ids = sorted({int(x) for x in (event_ids or [])})
    if not ids:
        raise Refused("--event-ids is required: name the tracker event(s) this decision is "
                      "about. It takes every value until the next flag, so "
                      "`--event-ids 149625 149911` records BOTH")

    manifest = manifest if manifest is not None else load_manifest()
    ledger = ledger if ledger is not None else load_ledger()
    event = _event(manifest, reference_row_id)

    if pack is not None:
        proposed, _ = _pack_ids(pack, reference_row_id)
        if proposed is None:
            raise Refused(
                f"{reference_row_id} is not in the adjudication pack, so there is no "
                f"evidence block behind this decision. Rebuild it with "
                f"`python3 railway/recall_adjudication_pack.py --write` and read the entry "
                f"before deciding")
        unknown = sorted(set(ids) - proposed)
        if unknown:
            raise Refused(
                f"tracker event(s) {unknown} are not proposed for {reference_row_id}; the "
                f"pack proposes {sorted(proposed)}. A typed id that no evidence block covers "
                f"is exactly the mistake this check exists for. Rebuild the pack if the live "
                f"data has moved")

    existing = _live_entries(ledger, reference_row_id)
    if existing:
        last = existing[-1]
        if last["decision"] == decision and last["tracker_event_ids"] == ids:
            return manifest, ledger, last, False
        raise Refused(
            f"{reference_row_id} is already adjudicated: {last['decision']} of "
            f"{last['tracker_event_ids']} by {last['reviewed_by']} at {last['reviewed_at']}. "
            f"A decision is changed by REVERTING it and deciding again, so both readings "
            f"stay on the record: `--revert {reference_row_id} --reviewed-by ... --reason ...`")

    before = _snapshot(event)
    entry = {
        "entry_id": f"{reference_row_id}@{now or _utc_now_iso()}",
        "reference_row_id": reference_row_id,
        "decision": decision,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now or _utc_now_iso(),
        "reason": reason.strip(),
        "tracker_event_ids": ids,
        "evidence_pack_built_at": (pack or {}).get("built_at"),
        "manifest_before": before,
    }

    if decision == "accept":
        event["match_decision"] = MATCHED
    else:
        event["match_decision"] = event.get("match_decision") or NOT_MATCHED
        rejected = sorted(set(event.get("rejected_candidate_event_ids") or []) | set(ids))
        event["rejected_candidate_event_ids"] = rejected
    event["adjudication"] = {
        "decision": MATCHED if decision == "accept" else NOT_MATCHED,
        "reviewed_by": entry["reviewed_by"],
        "reviewed_at": entry["reviewed_at"],
        "reason": entry["reason"],
        "tracker_event_ids": ids,
        "entry_id": entry["entry_id"],
    }
    ledger["decisions"].append(entry)
    ledger.setdefault("note", LEDGER_NOTE)
    return manifest, ledger, entry, True


def revert(reference_row_id, reviewed_by, reason, manifest=None, ledger=None, now=None):
    """Undo this event's most recent live decision, exactly."""
    if not (reviewed_by or "").strip():
        raise Refused("--reviewed-by is required to revert")
    if not (reason or "").strip():
        raise Refused("--reason is required to revert. A reversal is a second finding, "
                      "not an erasure of the first")
    manifest = manifest if manifest is not None else load_manifest()
    ledger = ledger if ledger is not None else load_ledger()
    event = _event(manifest, reference_row_id)
    existing = _live_entries(ledger, reference_row_id)
    if not existing:
        raise Refused(f"{reference_row_id} has no live adjudication to revert. Nothing was "
                      f"written; `--queue` lists what is pending")
    last = existing[-1]
    _restore(event, last["manifest_before"])
    entry = {
        "entry_id": f"{reference_row_id}@{now or _utc_now_iso()}",
        "reference_row_id": reference_row_id,
        "decision": "revert",
        "reverts": last["entry_id"],
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now or _utc_now_iso(),
        "reason": reason.strip(),
        "restored": last["manifest_before"],
    }
    ledger["decisions"].append(entry)
    return manifest, ledger, entry, last


def verify(manifest=None, ledger=None):
    """(ok, problems). The gate: no event is `matched` without a named decision."""
    manifest = manifest if manifest is not None else load_manifest()
    ledger = ledger if ledger is not None else load_ledger()
    live_by_id = {}
    for ev in manifest["reference_events"]:
        live_by_id[ev["reference_row_id"]] = _live_entries(ledger, ev["reference_row_id"])
    problems = []
    for ev in manifest["reference_events"]:
        rid = ev["reference_row_id"]
        adj = ev.get("adjudication")
        live = live_by_id[rid]
        if ev.get("match_decision") == MATCHED and rid not in PRE_TOOL_MATCHED:
            if not adj:
                problems.append(
                    f"{rid} ({ev['filer']}) is `matched` with no `adjudication` block and is "
                    f"not one of the 24 adjudicated on 2026-08-01. A gold event was promoted "
                    f"by hand, so the published recall figure counts an event nobody signed "
                    f"for. Revert the manifest edit and use "
                    f"`recall_adjudicate.py --accept {rid}`")
            elif not live:
                problems.append(
                    f"{rid} ({ev['filer']}) carries an `adjudication` block by "
                    f"{adj.get('reviewed_by')!r} with no live entry in "
                    f"{LEDGER_PATH.name}. The ledger is the audit trail; a block without one "
                    f"was hand-written or the ledger was truncated")
        if adj:
            expected = MATCHED if adj.get("decision") == MATCHED else NOT_MATCHED
            if expected == MATCHED and ev.get("match_decision") != MATCHED:
                problems.append(
                    f"{rid} was adjudicated `matched` by {adj.get('reviewed_by')!r} but "
                    f"match_decision reads {ev.get('match_decision')!r} — the decision and "
                    f"the field that counts disagree")
            if not (adj.get("reviewed_by") or "").strip() or not adj.get("reviewed_at"):
                problems.append(f"{rid} has an `adjudication` block with no reviewer or no "
                                f"timestamp: {adj!r}")
    return (not problems), problems


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _arg(argv, flag, default=None):
    try:
        value = argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return default
    return default if value.startswith("--") else value


def _multi_arg(argv, flag):
    """Every value after `flag` until the next `--flag`.

    `_arg` would take one token. `--event-ids 149625 149911` typed the way a
    person types it must record BOTH; recording only the first is a decision
    asserting a finding nobody made, and it exits zero while doing it.
    """
    if flag not in argv:
        return []
    out = []
    for token in argv[argv.index(flag) + 1:]:
        if token.startswith("--"):
            break
        out.extend(p for p in token.replace(",", " ").split() if p)
    return out


def _write(manifest, ledger, manifest_path=None, ledger_path=None):
    # indent=1, ensure_ascii=False and NO trailing newline: verified to
    # round-trip the manifest byte for byte, so the diff of a decision is the
    # decision and not a reformat of 1,657 lines with the change hidden in it.
    Path(manifest_path or MANIFEST_PATH).write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    Path(ledger_path or LEDGER_PATH).write_text(
        json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _print_queue(pack, manifest, ledger):
    done = {d["reference_row_id"] for e in pack.get("entries") or []
            for d in _live_entries(ledger, e["reference_row_id"])}
    print(f"ADJUDICATION QUEUE — pack built {pack.get('built_at')}, "
          f"{pack.get('pending')} entries, {len(done)} already decided")
    for i, e in enumerate(pack.get("entries") or [], 1):
        rid = e["reference_row_id"]
        live = _live_entries(ledger, rid)
        mark = f"{live[-1]['decision'].upper():8s}" if live else "pending "
        print(f"  {i:2d}. {mark} {e['filing_date']} {e['filer'][:32]:32s} "
              f"{e['stated_job_count']:>6,}  events {e['proposed_tracker_event_ids']}")
        if not live:
            for row in e["rows"]:
                for flag in row["flags"]:
                    print(f"        look twice: {flag}")
    print(f"  the sheet: docs/recall-reference-sets/"
          f"sec-item-205-adjudication-queue.md")


def _print_show(pack, reference_row_id):
    _, entry = _pack_ids(pack, reference_row_id)
    if entry is None:
        print(f"{reference_row_id} is not in the pack. `--queue` lists what is.")
        return 2
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0


def main(argv=None, manifest_path=None, ledger_path=None, pack_path=None, now=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    try:
        ledger = load_ledger(ledger_path)
        if "--verify" in argv:
            ok, problems = verify(load_manifest(manifest_path), ledger)
            if ok:
                print("ADJUDICATION LEDGER verified: every `matched` gold event is either "
                      "one of the 24 decided on 2026-08-01 or carries a named, timestamped "
                      "decision with a ledger entry behind it.")
                return 0
            print("ADJUDICATION LEDGER FAILED verification:")
            for p in problems:
                print(f"  {p}")
            return 2
        pack = load_pack(pack_path)
        if "--queue" in argv:
            _print_queue(pack, load_manifest(manifest_path), ledger)
            return 0
        if "--show" in argv:
            return _print_show(pack, _arg(argv, "--show"))

        for flag, decision in (("--accept", "accept"), ("--reject", "reject")):
            if flag in argv:
                manifest, ledger, entry, changed = decide(
                    _arg(argv, flag), decision,
                    reviewed_by=_arg(argv, "--reviewed-by", ""),
                    reason=_arg(argv, "--reason", ""),
                    event_ids=_multi_arg(argv, "--event-ids"),
                    manifest=load_manifest(manifest_path), pack=pack, ledger=ledger,
                    now=now)
                if not changed:
                    print(f"ALREADY RECORDED — {entry['decision']} of "
                          f"{entry['tracker_event_ids']} by {entry['reviewed_by']} at "
                          f"{entry['reviewed_at']}. Nothing was written.")
                    return 0
                _write(manifest, ledger, manifest_path, ledger_path)
                print(f"{decision.upper()}ED {entry['reference_row_id']} — "
                      f"tracker event(s) {entry['tracker_event_ids']}, "
                      f"reviewed by {entry['reviewed_by']}")
                print(f"  reason: {entry['reason']}")
                print(f"  COMMIT both {MANIFEST_PATH.name} and {LEDGER_PATH.name}. "
                      f"The published figure moves on the next measurement.")
                return 0

        if "--revert" in argv:
            manifest, ledger, entry, undone = revert(
                _arg(argv, "--revert"),
                reviewed_by=_arg(argv, "--reviewed-by", ""),
                reason=_arg(argv, "--reason", ""),
                manifest=load_manifest(manifest_path), ledger=ledger, now=now)
            _write(manifest, ledger, manifest_path, ledger_path)
            print(f"REVERTED {entry['reference_row_id']} — undid the {undone['decision']} "
                  f"by {undone['reviewed_by']} at {undone['reviewed_at']}")
            print(f"  reason: {entry['reason']}")
            print(f"  the event is back to {entry['restored'] or 'its pre-decision state'}")
            print(f"  COMMIT both {MANIFEST_PATH.name} and {LEDGER_PATH.name}.")
            return 0
    except Refused as exc:
        print(f"REFUSED: {exc}")
        print("Nothing was written.")
        return 2
    except Unreadable as exc:
        print(f"UNKNOWN: {exc}")
        print("Nothing was written, and nothing was judged.")
        return 3

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
