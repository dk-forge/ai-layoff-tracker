#!/usr/bin/env python3
"""Record ONE editor decision on the US WARN reference set. Network-free.

Deciding and looking are separate programs on purpose: a module that can
re-read the thing it is about can talk itself into a decision. This one opens
no socket.

THE MECHANISM IS NOT WRITTEN HERE, AND THAT IS THE POINT
-------------------------------------------------------
The SEC set's recorder already had the four properties a decision has to have —
reversible, attributed, no silent match, idempotent — and each of them cost an
incident to learn. The first version of THIS file re-implemented them and got
three wrong: it appended a ledger entry on every invocation (so running the same
accept twice double-recorded it), it had no `--revert`, and it had no
`--verify`, so a hand-edited `match_decision` was indistinguishable from an
adjudicated one.

So the mechanism now lives once, in `adjudication_ledger.py`, and this file is
the WARN set's PROFILE: where its files are, that its manifest keeps events in
two lists, and that a decision here names tracker ROW ids rather than tracker
event ids. Two adjudication tools that drift apart is a worse outcome than one
slightly awkward one.

It writes two places, both committed:

  * the manifest's `match_decision` / `adjudication` / `adjudicated_*` fields, so
    the frozen set carries its own decisions;
  * `railway/warn_recall_adjudications.json`, an append-only ledger of who
    decided what, when, why, and against which tracker rows.

Every decision REQUIRES a reviewer, a reason and the row ids it applies to. The
row ids are not decoration: the sheet lists one line per candidate row, and an
accept that does not name a row cannot be checked later against the row that was
actually looked at. That is the Dow failure written as a required argument.

THE SEC FIGURE IS NOT THIS SET'S BUSINESS. This module names, opens and writes
only the two WARN files above; `tests/test_warn_adjudication.py` drives a real
decision through it and then asserts the SEC manifest, the SEC ledger and the
SEC measurement are byte-identical afterwards.

USAGE
    python3 railway/warn_adjudicate.py --queue
    python3 railway/warn_adjudicate.py --show <reference_row_id>
    python3 railway/warn_adjudicate.py --accept <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why' --row-ids 137101 137100
    python3 railway/warn_adjudicate.py --reject <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why' --row-ids 137101
    python3 railway/warn_adjudicate.py --revert <reference_row_id> \\
        --reviewed-by 'Name' --reason 'why'
    python3 railway/warn_adjudicate.py --verify

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
import warn_reference_set as W                                      # noqa: E402

LEDGER_PATH = W.HERE / "warn_recall_adjudications.json"
PACK_PATH = W.REF_DIR / "us-warn-adjudication-queue.json"
SHEET_REL = "docs/recall-reference-sets/us-warn-adjudication-queue.md"

# The event fields a decision may touch. Everything else — the notice date, the
# published count, the component rows, the aliases, the window — is the frozen
# reference and a decision must never write it. Snapshotting exactly these is
# what makes a revert exact, so the `adjudicated_*` mirror fields MUST be listed
# here: a mirror outside the snapshot survives its own revert.
MUTABLE_FIELDS = ("match_decision", "match_notes", "rejected_candidate_event_ids",
                  "adjudication", "adjudicated_by", "adjudicated_at",
                  "adjudicated_tracker_row_ids")

LEDGER_NOTE = (
    "Append-only ledger of every editor decision on the US WARN reference set, and of "
    "every reversal. Written ONLY by railway/warn_adjudicate.py. `manifest_before` is the "
    "snapshot --revert restores; do not hand-edit this file, and do not hand-edit "
    "match_decision in the manifest -- `--verify` fails on a matched event that has no "
    "entry here, and the test suite runs it.")


def _dump_manifest(doc):
    # indent=2 + a trailing newline is how warn_reference_set.build() wrote this
    # manifest, so a decision diffs as the decision and not as a reformat of
    # 10,000 lines with the change hidden inside it.
    return json.dumps(doc, indent=2) + "\n"


def _dump_ledger(doc):
    return json.dumps(doc, indent=2) + "\n"


def _mirror_onto_event(event, entry):
    """The manifest carries its own flat copy of the decision.

    `warn_reference_set` and the offline guards read `adjudicated_by` directly —
    a matched event with no adjudicator is the assertion that catches a machine
    promoting itself — so the block and the mirror are written together and
    reverted together.
    """
    event["match_notes"] = entry["reason"]
    event["adjudicated_by"] = entry["reviewed_by"]
    event["adjudicated_at"] = entry["reviewed_at"]
    event["adjudicated_tracker_row_ids"] = list(entry["tracker_row_ids"])


PROFILE = AL.Profile(
    set_id="US WARN",
    tool="warn_adjudicate.py",
    manifest_path=W.MANIFEST_PATH,
    ledger_path=LEDGER_PATH,
    pack_path=PACK_PATH,
    # Two lists, never pooled into one figure, but adjudicated by one person
    # with one tool. A recorder that saw only the first would report "no such
    # reference event" for the whole 500-plus census.
    event_lists=("reference_events", "large_event_census"),
    ids_flag="--row-ids",
    ids_field="tracker_row_ids",
    id_noun="tracker row",
    label_field="employer_published",
    mutable_fields=MUTABLE_FIELDS,
    ledger_note=LEDGER_NOTE,
    pack_ids=lambda entry: [c["tracker_row_id"] for c in entry.get("candidates") or []],
    dump_manifest=_dump_manifest,
    dump_ledger=_dump_ledger,
    pre_tool_matched=frozenset(),          # nothing here was decided before the ledger
    on_accept=_mirror_onto_event,
    pack_rebuild_command="python3 railway/warn_adjudication_pack.py --write",
)


def load_manifest(path=None):
    return AL.load_manifest(PROFILE, path)


def load_pack(path=None):
    return AL.load_pack(PROFILE, path)


def load_ledger(path=None):
    return AL.load_ledger(PROFILE, path)


def verify(manifest=None, ledger=None):
    return AL.verify(PROFILE, manifest=manifest, ledger=ledger)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_queue(pack, ledger):
    entries = pack.get("entries") or []
    done = sum(1 for e in entries if AL.live_entries(ledger, e["reference_row_id"]))
    print(f"ADJUDICATION QUEUE — pack built {pack.get('built_at')}, "
          f"{len(entries)} events, {done} already decided")
    for i, e in enumerate(entries, 1):
        rid = e["reference_row_id"]
        live = AL.live_entries(ledger, rid)
        mark = f"{live[-1]['decision'].upper():8s}" if live else "pending "
        lead = e.get("lead_row_id")
        print(f"  {i:3d}. {mark} {e['state']} {e['notice_says_date']} "
              f"{str(e['notice_says_employer'])[:34]:34s} "
              f"{e['notice_says_job_count']:>6,}  lead row {lead}")
    print(f"  the sheet: {SHEET_REL}")


def _print_show(pack, reference_row_id):
    _, entry = AL.pack_entry(pack, PROFILE, reference_row_id)
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
                print("ADJUDICATION LEDGER verified: every `matched` reference event "
                      "carries a named, timestamped decision with a ledger entry behind "
                      "it. Nothing in this set was promoted by a machine.")
                return 0
            print("ADJUDICATION LEDGER FAILED verification:")
            for p in problems:
                print(f"  {p}")
            return 2
        pack = load_pack(pack_path)
        if "--queue" in argv or "--list" in argv:
            _print_queue(pack, ledger)
            return 0
        if "--show" in argv:
            return _print_show(pack, AL.arg(argv, "--show"))

        for flag, decision in (("--accept", "accept"), ("--reject", "reject")):
            if flag in argv:
                manifest, ledger, entry, changed = AL.decide(
                    PROFILE, AL.arg(argv, flag), decision,
                    reviewed_by=AL.arg(argv, "--reviewed-by", ""),
                    reason=AL.arg(argv, "--reason", ""),
                    ids=AL.multi_arg(argv, "--row-ids"),
                    manifest=load_manifest(manifest_path), pack=pack, ledger=ledger,
                    now=now)
                if not changed:
                    print(f"ALREADY RECORDED — {entry['decision']} of "
                          f"{entry['tracker_row_ids']} by {entry['reviewed_by']} at "
                          f"{entry['reviewed_at']}. Nothing was written.")
                    return 0
                AL.write(PROFILE, manifest, ledger, manifest_path, ledger_path)
                print(f"{decision.upper()}ED {entry['reference_row_id']} — "
                      f"tracker row(s) {entry['tracker_row_ids']}, "
                      f"reviewed by {entry['reviewed_by']}")
                print(f"  reason: {entry['reason']}")
                print(f"  COMMIT both {PROFILE.manifest_path.name} and "
                      f"{LEDGER_PATH.name}. The figure moves on the next measurement: "
                      f"`python3 railway/warn_reference_set.py --measure`.")
                return 0

        if "--revert" in argv:
            manifest, ledger, entry, undone = AL.revert(
                PROFILE, AL.arg(argv, "--revert"),
                reviewed_by=AL.arg(argv, "--reviewed-by", ""),
                reason=AL.arg(argv, "--reason", ""),
                manifest=load_manifest(manifest_path), ledger=ledger, now=now)
            AL.write(PROFILE, manifest, ledger, manifest_path, ledger_path)
            print(f"REVERTED {entry['reference_row_id']} — undid the {undone['decision']} "
                  f"by {undone['reviewed_by']} at {undone['reviewed_at']}")
            print(f"  reason: {entry['reason']}")
            print(f"  the event is back to {entry['restored'] or 'its pre-decision state'}")
            print(f"  COMMIT both {PROFILE.manifest_path.name} and {LEDGER_PATH.name}.")
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
