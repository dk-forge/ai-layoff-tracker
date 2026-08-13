#!/usr/bin/env python3
"""Record a human's adjudication of a SEC Item 2.05 gold event. The ONLY thing that may.

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

Those four are now implemented ONCE, in `adjudication_ledger.py`, because the
US WARN reference set needs the same four and a second hand-written recorder
got three of them wrong. This module is that mechanism plus the SEC set's
profile: where its files are, what its ids mean, and the 24 it inherited.
**Nothing about SEC behaviour changed when the mechanism moved** — the same
messages, the same exit codes, the same byte-stable serialisation, pinned by
`tests/test_recall_adjudication.py`.

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adjudication_ledger as AL                                    # noqa: E402
from adjudication_ledger import Refused, Unreadable                 # noqa: E402,F401

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

MATCHED = AL.MATCHED
NOT_MATCHED = AL.NOT_MATCHED

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

LEDGER_NOTE = (
    "Append-only record of every human adjudication of the SEC Item 2.05 gold set, and of "
    "every reversal. Written ONLY by railway/recall_adjudicate.py. `manifest_before` is the "
    "snapshot --revert restores; do not hand-edit this file, and do not hand-edit "
    "match_decision in the manifest -- `--verify` fails on a matched event that has no "
    "entry here, and the test suite runs it.")


# indent=1, ensure_ascii=False and NO trailing newline on the manifest: verified
# to round-trip it byte for byte, so the diff of a decision is the decision and
# not a reformat of 1,657 lines with the change hidden in it.
def _dump_manifest(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False)


def _dump_ledger(doc):
    return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"


PROFILE = AL.Profile(
    set_id="SEC Item 2.05",
    tool="recall_adjudicate.py",
    manifest_path=MANIFEST_PATH,
    ledger_path=LEDGER_PATH,
    pack_path=PACK_PATH,
    event_lists=("reference_events",),
    ids_flag="--event-ids",
    ids_field="tracker_event_ids",
    id_noun="tracker event",
    label_field="filer",
    mutable_fields=MUTABLE_FIELDS,
    ledger_note=LEDGER_NOTE,
    pack_ids=lambda entry: entry.get("proposed_tracker_event_ids") or [],
    dump_manifest=_dump_manifest,
    dump_ledger=_dump_ledger,
    pre_tool_matched=PRE_TOOL_MATCHED,
    pack_rebuild_command="python3 railway/recall_adjudication_pack.py --write",
)


def load_manifest(path=None):
    return AL.load_manifest(PROFILE, path)


def load_pack(path=None):
    return AL.load_pack(PROFILE, path)


def load_ledger(path=None):
    return AL.load_ledger(PROFILE, path)


def decide(reference_row_id, decision, reviewed_by, reason, event_ids,
           manifest=None, pack=None, ledger=None, now=None):
    return AL.decide(PROFILE, reference_row_id, decision, reviewed_by, reason,
                     event_ids, manifest=manifest, pack=pack, ledger=ledger, now=now)


def revert(reference_row_id, reviewed_by, reason, manifest=None, ledger=None, now=None):
    return AL.revert(PROFILE, reference_row_id, reviewed_by, reason,
                     manifest=manifest, ledger=ledger, now=now)


def verify(manifest=None, ledger=None):
    return AL.verify(PROFILE, manifest=manifest, ledger=ledger)


def _live_entries(ledger, reference_row_id):
    return AL.live_entries(ledger, reference_row_id)


def _pack_ids(pack, reference_row_id):
    return AL.pack_entry(pack, PROFILE, reference_row_id)


def _write(manifest, ledger, manifest_path=None, ledger_path=None):
    AL.write(PROFILE, manifest, ledger, manifest_path, ledger_path)


_arg = AL.arg
_multi_arg = AL.multi_arg


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
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
                      f"The published figure moves on the next measurement — Monday's "
                      f"recall-precision.yml, or `python3 railway/recall_goldset.py "
                      f"--write` now, which also refreshes the plugin's render copy so "
                      f"the live page does not keep publishing the superseded number.")
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
