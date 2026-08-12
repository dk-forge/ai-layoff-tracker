#!/usr/bin/env python3
"""A host call that never happened is COUNTED, not forgotten.

THE DEFECT THIS CLOSES
----------------------
On 2026-07-31 Bluehost answered 5xx under `/blog/` twice in one day, and the
jobs that talk to that host died red. A red run fires `ci_alert.py`, which posts
to `/alert` — a route on the host that is down. The alerter was fixed by HOLDING
an undeliverable alert and exiting 0. The jobs themselves were not: they still
turn a six-minute outage into a red run, an email that cannot be sent, and a
session that reads `ops_status [4]` and is told two workflows are broken when
nothing in either of them is.

So a call the host never answered now DEFERS and exits 0. Which immediately
raises the harder question, and the only one worth writing a file for: a
deferral nobody counts is a silently green job, which is the exact failure
family this repo has spent the week digging out of — a queue nobody drained, a
badge with no JS behind it, a coverage guard satisfiable by typing strings.

Hence this ledger. It answers two questions a green run cannot:

  * is anything deferred RIGHT NOW (ops_status `[4d]`), and
  * has a job deferred `ESCALATE_AFTER` times in a row — at which point it is
    not an outage, it is a broken job wearing an outage as a disguise.

WHY A COMMITTED FILE
--------------------
The same constraint that put `alert_outbox.json` in the repository: the state is
about the WordPress host, so it cannot live on the WordPress host, and a
runner's disk does not outlive the job. GitHub Actions cache is evicted silently
after 7 days; an artifact needs an API call to the same GitHub that may be the
thing failing.

WHY A HEALTHY RUN WRITES NOTHING
--------------------------------
`alert-drain.yml` makes NO request to the host when the outbox is empty, which
is why that tick is free. Same rule here: a call that succeeds against a job
with no open deferral touches nothing — no file write, no commit, no push. The
ledger only ever records anomalies and their resolution, so a daily job that
works produces no churn at all, and `git log` on this file is a list of
outages rather than a heartbeat.

Stdlib only, deliberately: this is read by `ops_status.py` (which promises no
dependencies) and written from workflows that do no `pip install`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEDGER = ROOT / "deferral_ledger.json"

#: Consecutive deferrals before a job stops being "the host had a bad night".
#: Every job converted so far runs DAILY, so three in a row is three days in
#: which the host was reachable from every other job and this one still never
#: got an answer. That is not an outage, and the run goes red like any other
#: broken job — which mails the owner through the normal (held-if-needed) path.
ESCALATE_AFTER = 3

#: Resolved deferrals kept as forensics. Enough to reconstruct an outage after
#: the fact, small enough that the committed file stays reviewable.
HISTORY_KEPT = 50

VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty() -> dict:
    return {"version": VERSION, "updated_at": _now(), "entries": []}


def load(path: Path | str = LEDGER) -> dict:
    """Read the ledger. A missing or unreadable file is an EMPTY ledger, never
    an exception: this is called from a failure path, and a bookkeeper that
    crashes while recording a failure has recorded nothing."""
    p = Path(path)
    if not p.exists():
        return empty()
    try:
        doc = json.loads(p.read_text() or "{}")
    except (OSError, ValueError) as exc:
        print(f"deferral_ledger: {p} is unreadable ({exc}) — starting fresh")
        return empty()
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        print(f"deferral_ledger: {p} has an unexpected shape — starting fresh")
        return empty()
    doc.setdefault("version", VERSION)
    return doc


def save(doc: dict, path: Path | str = LEDGER) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc["updated_at"] = _now()
    doc["entries"] = _trim(doc.get("entries", []))
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def _trim(entries: list[dict]) -> list[dict]:
    open_ = [e for e in entries if e.get("state") == "pending"]
    done = [e for e in entries if e.get("state") != "pending"]
    done.sort(key=lambda e: e.get("resolved_at") or e.get("first_deferred_at") or "")
    return open_ + done[-HISTORY_KEPT:]


def pending(doc: dict) -> list[dict]:
    out = [e for e in doc.get("entries", []) if e.get("state") == "pending"]
    out.sort(key=lambda e: e.get("first_deferred_at") or "")
    return out


def escalated(doc: dict) -> list[dict]:
    return [e for e in pending(doc) if e.get("consecutive", 0) >= ESCALATE_AFTER]


def record_deferral(doc: dict, *, job: str, reason: str = "", run_url: str = "",
                    key: str = "") -> dict:
    """Count one deferral for `job`, and return its entry.

    Idempotent in `key` when one is given. The commit loop answers a rejected
    push by fetching main, resetting onto it and RE-RECORDING (the lesson
    `alert_outbox.enqueue_envelope` already learned), so a race must cost a
    retry rather than walk a job to escalation on retries alone.
    """
    entries = doc.setdefault("entries", [])
    for e in entries:
        if e.get("state") == "pending" and e.get("job") == job:
            if key and e.get("last_key") == key:
                return e  # the same run, recorded again after a push race
            e["consecutive"] = e.get("consecutive", 0) + 1
            e["last_deferred_at"] = _now()
            e["last_reason"] = reason
            e["last_run_url"] = run_url
            e["last_key"] = key
            return e
    entry = {
        "job": job,
        "state": "pending",
        "consecutive": 1,
        "first_deferred_at": _now(),
        "last_deferred_at": _now(),
        "last_reason": reason,
        "last_run_url": run_url,
        "last_key": key,
    }
    entries.append(entry)
    return entry


def record_success(doc: dict, *, job: str) -> bool:
    """Close any open deferral for `job`. Returns True when anything changed.

    False is the normal case and the reason this ledger is free to keep: a
    healthy job leaves the file untouched, so there is nothing to commit.
    """
    changed = False
    for e in doc.get("entries", []):
        if e.get("state") == "pending" and e.get("job") == job:
            e["state"] = "resolved"
            e["resolved_at"] = _now()
            changed = True
    return changed


def describe(doc: dict) -> list[str]:
    """Lines for ops_status.py. Kept here so the dashboard and the ledger can
    never describe the same backlog two different ways."""
    open_ = pending(doc)
    if not open_:
        settled = [e for e in doc.get("entries", []) if e.get("state") != "pending"]
        if not settled:
            return ["none — every host call so far got an answer"]
        last = max(settled, key=lambda e: e.get("resolved_at") or "")
        return [f"none pending; last deferral resolved {last.get('resolved_at')} "
                f"({last.get('job')})"]

    lines = [f"{len(open_)} job(s) DEFERRED — the host did not answer; "
             f"the next scheduled run retries"]
    for e in open_[:5]:
        lines.append(f"  {e.get('job')}  x{e.get('consecutive', 0)}  since "
                     f"{e.get('first_deferred_at')}  {str(e.get('last_reason', ''))[:56]}")
    if len(open_) > 5:
        lines.append(f"  ... and {len(open_) - 5} more")
    if escalated(doc):
        lines.append(f"  {ESCALATE_AFTER}+ in a row is NOT an outage. See docs/RUNBOOK.md "
                     "'a job is DEFERRING (and what three in a row means)'.")
    return lines


def write_envelope(path: Path | str, *, job: str, state: str, reason: str = "",
                   run_url: str = "", key: str = "") -> None:
    """Park what was recorded where the commit loop can REPLAY it.

    A rejected push is answered by fetching main, resetting onto it and
    re-deriving — the lesson `alert_outbox.enqueue_envelope` already learned —
    and a reset throws away the ledger edit along with everything else. The
    envelope is untracked, so it survives the reset; `record_deferral` is
    idempotent in `key`, so the replay cannot double-count the streak.
    """
    Path(path).write_text(json.dumps(
        {"job": job, "state": state, "reason": reason, "run_url": run_url,
         "key": key}, indent=2, sort_keys=True) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="inspect the deferred-call ledger")
    ap.add_argument("command", choices=["status", "list", "record"],
                    nargs="?", default="status")
    ap.add_argument("--path", default=str(LEDGER))
    ap.add_argument("--job")
    ap.add_argument("--state", choices=["deferred", "success"])
    ap.add_argument("--reason", default="")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--envelope", help="replay a record written by host_call.py")
    args = ap.parse_args(argv)

    if args.command == "record" and args.envelope:
        env = json.loads(Path(args.envelope).read_text())
        args.job = env.get("job")
        args.state = env.get("state")
        args.reason = env.get("reason", "")
        args.run_url = env.get("run_url", "")
        args.key = env.get("key", "")

    if args.command == "record":
        if not args.job or not args.state:
            print("::error::deferral_ledger.py record needs --job and --state")
            return 2
        doc = load(args.path)
        if args.state == "deferred":
            entry = record_deferral(doc, job=args.job, reason=args.reason,
                                    run_url=args.run_url, key=args.key)
            save(doc, args.path)
            print(f"deferred: {args.job} x{entry['consecutive']}")
        elif record_success(doc, job=args.job):
            save(doc, args.path)
            print(f"resolved: {args.job}")
        else:
            print(f"nothing to record for {args.job} (no open deferral)")
        return 0

    doc = load(args.path)
    for line in describe(doc):
        print(line)
    if args.command == "list":
        print(json.dumps(doc, indent=2, sort_keys=True))

    blocked = escalated(doc)
    if blocked:
        print(f"::error::{len(blocked)} job(s) have deferred {ESCALATE_AFTER}+ times "
              "in a row — that is no longer an outage.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
