#!/usr/bin/env python3
"""Record ONE editor decision on the US WARN reference set. Network-free.

Deciding and looking are separate programs on purpose, the same way
`recall_adjudicate.py` is separate from `recall_adjudication_pack.py`: a module
that can re-read the thing it is about can talk itself into a decision. This one
opens no socket.

It writes two places, both committed:

  * the manifest's `match_decision` / `match_notes` / `adjudicated_*` fields, so
    the frozen set carries its own decisions;
  * `railway/warn_recall_adjudications.json`, an append-only ledger of who
    decided what, when, why, and against which tracker rows.

Every decision REQUIRES a reviewer, a reason and the row ids it applies to. The
row ids are not decoration: the sheet lists one line per candidate row, and an
accept that does not name a row cannot be checked later against the row that was
actually looked at. That is the Dow failure written as a required argument.

USAGE
    python3 railway/warn_adjudicate.py --accept <reference_row_id> \\
        --reviewed-by 'Name' --reason '...' --row-ids 137101 137100
    python3 railway/warn_adjudicate.py --reject <reference_row_id> \\
        --reviewed-by 'Name' --reason '...' --row-ids 137101
    python3 railway/warn_adjudicate.py --list          # what is still pending
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_reference_set as W                                    # noqa: E402

LEDGER_PATH = W.HERE / "warn_recall_adjudications.json"


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def record(reference_row_id, decision, reviewed_by, reason, row_ids):
    manifest = json.loads(W.MANIFEST_PATH.read_text(encoding="utf-8"))
    target = None
    for key in ("reference_events", "large_event_census"):
        for ev in manifest[key]:
            if ev["reference_row_id"] == reference_row_id:
                target = ev
    if target is None:
        raise SystemExit(f"no such reference event: {reference_row_id}")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    target["match_decision"] = "matched" if decision == "accept" else "not_matched"
    target["match_notes"] = reason
    target["adjudicated_by"] = reviewed_by
    target["adjudicated_at"] = stamp
    target["adjudicated_tracker_row_ids"] = list(row_ids)
    if decision == "reject":
        target["rejected_candidate_event_ids"] = sorted(
            set(target.get("rejected_candidate_event_ids") or []) | set(row_ids))
    W.MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    ledger = _load(LEDGER_PATH, {"note": ("Append-only ledger of editor decisions on "
                                          "the US WARN reference set. Written only by "
                                          "warn_adjudicate.py. Do not hand-edit."),
                                 "decisions": []})
    ledger["decisions"].append({
        "reference_row_id": reference_row_id, "decision": decision,
        "reviewed_by": reviewed_by, "reason": reason,
        "tracker_row_ids": list(row_ids), "at": stamp,
    })
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(f"{decision.upper()} recorded for {reference_row_id} by {reviewed_by} "
          f"against rows {list(row_ids)}")
    print("Re-measure to move the figure: python3 railway/warn_reference_set.py --measure")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--accept")
    p.add_argument("--reject")
    p.add_argument("--reviewed-by")
    p.add_argument("--reason")
    p.add_argument("--row-ids", nargs="+", type=int, default=[])
    p.add_argument("--list", action="store_true")
    args = p.parse_args(argv)
    if args.list:
        manifest = json.loads(W.MANIFEST_PATH.read_text(encoding="utf-8"))
        pending = [e for e in manifest["reference_events"] + manifest["large_event_census"]
                   if e.get("match_decision") != "matched"]
        print(f"{len(pending)} reference events are not adjudicated as matched")
        for ev in pending[:40]:
            print(f"  {ev['reference_row_id']}  {ev['state']} {ev['notice_date']} "
                  f"{ev['employer_published'][:44]}")
        return 0
    if bool(args.accept) == bool(args.reject):
        p.error("give exactly one of --accept / --reject")
    if not args.reviewed_by or not args.reason:
        p.error("--reviewed-by and --reason are required; a decision without an "
                "author and a stated reason cannot be audited")
    if not args.row_ids:
        p.error("--row-ids is required: name the tracker row(s) this decision is "
                "about. An accept that names no row cannot later be checked against "
                "the row that was actually looked at — that is the Dow failure.")
    record(args.accept or args.reject, "accept" if args.accept else "reject",
           args.reviewed_by, args.reason, args.row_ids)
    return 0


if __name__ == "__main__":
    sys.exit(main())
