#!/usr/bin/env python3
"""The recorder that lets a HUMAN move a recall figure, for ANY reference set.

WHY THIS MODULE EXISTS AT ALL
-----------------------------
`recall_adjudicate.py` was written for the SEC Item 2.05 gold set and had four
properties that took two incidents to earn:

    1. REVERSIBLE — every write snapshots the event's prior fields, so a revert
       restores them byte for byte, including removing a key that was absent.
    2. ATTRIBUTED — a reviewer and a reason are required and may not be blank. A
       decision with no name on it is indistinguishable from the machine
       promoting its own recall, which is the thing being prevented.
    3. NO SILENT MATCH — `--verify` fails on any event that reads `matched`
       without a named decision and a ledger entry behind it, and the test suite
       runs it against the committed files so a hand-edit reddens CI.
    4. IDEMPOTENT — the same decision twice writes once; a DIFFERENT decision on
       an already-decided event is refused and told to revert first.

The US WARN reference set needs exactly those four properties. The first WARN
recorder re-implemented them and got three of the four wrong: it appended a
ledger entry on every invocation (so a double run double-recorded), it had no
`--revert` at all, and it had no `--verify`, so a hand-edited `match_decision`
was indistinguishable from an adjudicated one.

Two adjudication tools that drift apart is a worse outcome than one slightly
awkward one, so the mechanism lives here, once, set-neutral, and each set
supplies a `Profile`. What differs between the two sets is genuinely only data:
where the files are, what the manifest calls its event lists, whether a decision
names tracker EVENT ids or tracker ROW ids, and how the manifest is serialised.

NOTHING HERE OPENS A SOCKET, and that is deliberate for the same reason
`data_integrity.close_incident` refuses to re-read the site it is about: the
decision is made against the evidence pack the reviewer read, not against
whatever the host happens to be serving at the moment they press return.

EXIT CODES (used by both CLIs)
    0  recorded, or already recorded identically, or verified clean
    2  REFUSED (nothing written), or --verify found an unattributed match
    3  a file could not be read, so nothing could be judged -- UNKNOWN
"""
import json
from datetime import datetime, timezone
from pathlib import Path

MATCHED = "matched"
NOT_MATCHED = "not_matched"


class Refused(Exception):
    """Nothing was written. Raised before any file is touched."""


class Unreadable(Exception):
    """A file this module needs could not be read or parsed."""


class Profile:
    """Everything that differs between one reference set and another.

    Every field is data about a set, never a behaviour. If a profile ever needs
    to carry a function that DECIDES something, that is the point at which the
    two sets have diverged in substance and the divergence belongs in the open,
    not in a keyword argument.
    """

    def __init__(self, set_id, tool, manifest_path, ledger_path, pack_path,
                 event_lists, ids_flag, ids_field, id_noun, label_field,
                 mutable_fields, ledger_note, pack_ids, dump_manifest,
                 dump_ledger, pre_tool_matched=frozenset(), on_accept=None,
                 pack_rebuild_command=""):
        self.set_id = set_id
        self.tool = tool                          # e.g. "railway/warn_adjudicate.py"
        self.manifest_path = Path(manifest_path)
        self.ledger_path = Path(ledger_path)
        self.pack_path = Path(pack_path)
        self.event_lists = tuple(event_lists)
        self.ids_flag = ids_flag                  # "--event-ids" / "--row-ids"
        self.ids_field = ids_field                # key inside the adjudication block
        self.id_noun = id_noun                    # "tracker event" / "tracker row"
        self.label_field = label_field            # human name of an event
        self.mutable_fields = tuple(mutable_fields)
        self.ledger_note = ledger_note
        self.pack_ids = pack_ids                  # (pack entry) -> iterable of ids
        self.dump_manifest = dump_manifest        # (doc) -> str, byte-stable
        self.dump_ledger = dump_ledger
        self.pre_tool_matched = frozenset(pre_tool_matched)
        self.on_accept = on_accept                # (event, entry) -> None, optional
        self.pack_rebuild_command = pack_rebuild_command


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path, what):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable(f"{what} at {path} could not be read: {exc}") from exc


def load_manifest(profile, path=None):
    return _load(path or profile.manifest_path, f"the {profile.set_id} manifest")


def load_pack(profile, path=None):
    return _load(path or profile.pack_path, f"the {profile.set_id} adjudication pack")


def load_ledger(profile, path=None):
    path = Path(path or profile.ledger_path)
    if not path.exists():
        return {"note": profile.ledger_note, "decisions": []}
    ledger = _load(path, f"the {profile.set_id} adjudication ledger")
    if not isinstance(ledger.get("decisions"), list):
        raise Unreadable(f"the adjudication ledger at {path} has no `decisions` list")
    return ledger


def all_events(manifest, profile):
    """Every event of the set, across every list the manifest keeps them in.

    The WARN set keeps two — a systematic sample and a census of the large
    events — and they are never pooled into one figure, but they are both
    adjudicated by the same person with the same tool. A recorder that saw only
    the first list would report "no such reference event" for a third of them.
    """
    out = []
    for key in profile.event_lists:
        out.extend(manifest.get(key) or [])
    return out


def _event(manifest, profile, reference_row_id):
    for ev in all_events(manifest, profile):
        if ev.get("reference_row_id") == reference_row_id:
            return ev
    events = all_events(manifest, profile)
    known = ", ".join(sorted(e["reference_row_id"] for e in events)[:3])
    raise Refused(f"no reference event {reference_row_id!r} in the manifest "
                  f"({len(events)} events, e.g. {known})")


def _snapshot(event, profile):
    return {f: json.loads(json.dumps(event[f]))
            for f in profile.mutable_fields if f in event}


def _restore(event, profile, snapshot):
    for field in profile.mutable_fields:
        event.pop(field, None)
    for field, value in snapshot.items():
        event[field] = value


def live_entries(ledger, reference_row_id):
    """This event's decisions that have not been reverted, oldest first."""
    reverted = {d["reverts"] for d in ledger["decisions"]
                if d.get("decision") == "revert" and d.get("reverts")}
    return [d for d in ledger["decisions"]
            if d.get("reference_row_id") == reference_row_id
            and d.get("decision") in ("accept", "reject")
            and d.get("entry_id") not in reverted]


def pack_entry(pack, profile, reference_row_id):
    # A pack may keep the events its rule proposes nothing for in a separate
    # `no_candidate` list (the WARN sheet renders them above the index, as their
    # own section). They are still adjudicable — the sheet prints accept/reject
    # commands for them — so a recorder that only scanned `entries` refused
    # exactly the decision the sheet asked for (found 2026-08-14, Wood Group).
    for entry in (pack.get("entries") or []) + (pack.get("no_candidate") or []):
        if entry.get("reference_row_id") == reference_row_id:
            return set(profile.pack_ids(entry) or []), entry
    return None, None


def decide(profile, reference_row_id, decision, reviewed_by, reason, ids,
           manifest=None, pack=None, ledger=None, now=None):
    """Apply one decision. Returns (manifest, ledger, entry, changed).

    Pure with respect to the filesystem: the caller writes. `changed` is False
    when this exact decision is already recorded, which is the idempotence
    contract -- the second run must not append a second identical entry.
    """
    if decision not in ("accept", "reject"):
        raise Refused(f"decision must be accept or reject, not {decision!r}")
    if not (reviewed_by or "").strip():
        raise Refused("--reviewed-by is required and may not be blank. An adjudication "
                      "with no name on it is indistinguishable from the machine "
                      "promoting its own recall, which is the thing this gate prevents")
    if not (reason or "").strip():
        raise Refused("--reason is required and may not be blank. Record what in the "
                      "source and in the row decided it, not that a decision was made")
    ids = sorted({int(x) for x in (ids or [])})
    if not ids:
        raise Refused(f"{profile.ids_flag} is required: name the {profile.id_noun}(s) this "
                      f"decision is about. It takes every value until the next flag, so "
                      f"`{profile.ids_flag} 149625 149911` records BOTH")

    manifest = manifest if manifest is not None else load_manifest(profile)
    ledger = ledger if ledger is not None else load_ledger(profile)
    event = _event(manifest, profile, reference_row_id)

    if pack is not None:
        proposed, _ = pack_entry(pack, profile, reference_row_id)
        if proposed is None:
            raise Refused(
                f"{reference_row_id} is not in the adjudication pack, so there is no "
                f"evidence block behind this decision. Rebuild it with "
                f"`{profile.pack_rebuild_command}` and read the entry before deciding")
        unknown = sorted(set(ids) - proposed)
        if unknown:
            raise Refused(
                f"{profile.id_noun}(s) {unknown} are not proposed for {reference_row_id}; "
                f"the pack proposes {sorted(proposed)}. A typed id that no evidence block "
                f"covers is exactly the mistake this check exists for. Rebuild the pack if "
                f"the live data has moved")

    existing = live_entries(ledger, reference_row_id)
    if existing:
        last = existing[-1]
        if last["decision"] == decision and last[profile.ids_field] == ids:
            return manifest, ledger, last, False
        raise Refused(
            f"{reference_row_id} is already adjudicated: {last['decision']} of "
            f"{last[profile.ids_field]} by {last['reviewed_by']} at {last['reviewed_at']}. "
            f"A decision is changed by REVERTING it and deciding again, so both readings "
            f"stay on the record: `--revert {reference_row_id} --reviewed-by ... "
            f"--reason ...`")

    before = _snapshot(event, profile)
    entry = {
        "entry_id": f"{reference_row_id}@{now or utc_now_iso()}",
        "reference_row_id": reference_row_id,
        "decision": decision,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now or utc_now_iso(),
        "reason": reason.strip(),
        profile.ids_field: ids,
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
        profile.ids_field: ids,
        "entry_id": entry["entry_id"],
    }
    if profile.on_accept is not None:
        profile.on_accept(event, entry)
    ledger["decisions"].append(entry)
    ledger.setdefault("note", profile.ledger_note)
    return manifest, ledger, entry, True


def revert(profile, reference_row_id, reviewed_by, reason,
           manifest=None, ledger=None, now=None):
    """Undo this event's most recent live decision, exactly."""
    if not (reviewed_by or "").strip():
        raise Refused("--reviewed-by is required to revert")
    if not (reason or "").strip():
        raise Refused("--reason is required to revert. A reversal is a second finding, "
                      "not an erasure of the first")
    manifest = manifest if manifest is not None else load_manifest(profile)
    ledger = ledger if ledger is not None else load_ledger(profile)
    event = _event(manifest, profile, reference_row_id)
    existing = live_entries(ledger, reference_row_id)
    if not existing:
        raise Refused(f"{reference_row_id} has no live adjudication to revert. Nothing was "
                      f"written; `--queue` lists what is pending")
    last = existing[-1]
    _restore(event, profile, last["manifest_before"])
    entry = {
        "entry_id": f"{reference_row_id}@{now or utc_now_iso()}",
        "reference_row_id": reference_row_id,
        "decision": "revert",
        "reverts": last["entry_id"],
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now or utc_now_iso(),
        "reason": reason.strip(),
        "restored": last["manifest_before"],
    }
    ledger["decisions"].append(entry)
    return manifest, ledger, entry, last


def verify(profile, manifest=None, ledger=None):
    """(ok, problems). The gate: no event is `matched` without a named decision."""
    manifest = manifest if manifest is not None else load_manifest(profile)
    ledger = ledger if ledger is not None else load_ledger(profile)
    problems = []
    for ev in all_events(manifest, profile):
        rid = ev["reference_row_id"]
        adj = ev.get("adjudication")
        live = live_entries(ledger, rid)
        label = ev.get(profile.label_field)
        if ev.get("match_decision") == MATCHED and rid not in profile.pre_tool_matched:
            if not adj:
                problems.append(
                    f"{rid} ({label}) is `matched` with no `adjudication` block and is "
                    f"not one of the {len(profile.pre_tool_matched)} adjudicated before "
                    f"this ledger existed. A reference event was promoted by hand, so the "
                    f"recall figure counts an event nobody signed for. Revert the manifest "
                    f"edit and use `{profile.tool} --accept {rid}`")
            elif not live:
                problems.append(
                    f"{rid} ({label}) carries an `adjudication` block by "
                    f"{adj.get('reviewed_by')!r} with no live entry in "
                    f"{profile.ledger_path.name}. The ledger is the audit trail; a block "
                    f"without one was hand-written or the ledger was truncated")
        if adj:
            expected = MATCHED if adj.get("decision") == MATCHED else NOT_MATCHED
            if expected == MATCHED and ev.get("match_decision") != MATCHED:
                problems.append(
                    f"{rid} was adjudicated `matched` by {adj.get('reviewed_by')!r} but "
                    f"match_decision reads {ev.get('match_decision')!r} -- the decision and "
                    f"the field that counts disagree")
            if not (adj.get("reviewed_by") or "").strip() or not adj.get("reviewed_at"):
                problems.append(f"{rid} has an `adjudication` block with no reviewer or no "
                                f"timestamp: {adj!r}")
    return (not problems), problems


def write(profile, manifest, ledger, manifest_path=None, ledger_path=None):
    """Serialise both files through the profile, so the diff of a decision is the
    decision and not a reformat of the whole manifest with the change hidden."""
    Path(manifest_path or profile.manifest_path).write_text(
        profile.dump_manifest(manifest), encoding="utf-8")
    Path(ledger_path or profile.ledger_path).write_text(
        profile.dump_ledger(ledger), encoding="utf-8")


# ---------------------------------------------------------------------------
# Argument reading, shared because the bug was shared.
# ---------------------------------------------------------------------------
def arg(argv, flag, default=None):
    try:
        value = argv[argv.index(flag) + 1]
    except (ValueError, IndexError):
        return default
    return default if value.startswith("--") else value


def multi_arg(argv, flag):
    """Every value after `flag` until the next `--flag`.

    `arg` would take one token. `--event-ids 149625 149911` typed the way a
    person types it must record BOTH; recording only the first is a decision
    asserting a finding nobody made, and it exits zero while doing it. That
    happened on 2026-08-12 with `--rows 114335 113529 64351`.
    """
    if flag not in argv:
        return []
    out = []
    for token in argv[argv.index(flag) + 1:]:
        if token.startswith("--"):
            break
        out.extend(p for p in token.replace(",", " ").split() if p)
    return out
