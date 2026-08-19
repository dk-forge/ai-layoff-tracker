#!/usr/bin/env python3
"""Which alarms are open, held in the repository instead of on the host.

WHY THIS MOVED, AND WHY THAT IS NOT A DOWNGRADE
-----------------------------------------------
Dedup by CAUSE is the whole design of this repo's alerting, not a refinement.
On 2026-07-30 one assertion reddened CI eight consecutive times in an afternoon.
Eight identical emails would have taught the owner to filter the sender, and a
filtered alarm is the original silence wearing a new hat. So an alarm is RAISED
once per cause and RECOVERED exactly once on the next green run.

That open/resolved state used to live server side, in the `alt_ci_alert_state`
option next to `wp_mail`. It lived there for a good reason: a "sent" record that
can disagree with what was actually sent is worth less than no record.

Sending moved to Resend so the alarm would stop depending on the host it
monitors, and a fire and forget send keeps no record of its own. So the ledger
came here, to a committed file, which this repo already trusts for
`alert_outbox.json`.

THE RACE THIS FILE EXISTS TO CLOSE
----------------------------------
A committed file read at checkout and written at push has a window tens of
seconds wide. Two runners that both read "nothing is open" both send, and the
dedup guarantee is gone. That would be a real weakening, and a quota fix that
costs the dedup guarantee is a bad trade.

So the claim is committed BEFORE the email is sent, and the commit is the
compare and swap. `git push` to main is atomic: exactly one racing runner wins
it. The loser re-derives on the new main, finds the cause already open, and goes
quiet. The window is closed by the same mechanism that stores the state.

Two consequences worth naming rather than discovering:

* An alarm is recorded open before it is known to be delivered. The endpoint
  recorded only on a successful send. The promise is kept a different way: an
  undeliverable alert is HELD in `alert_outbox.json` and delivered by
  `alert-drain.yml`, so a claimed alarm is a queued one. The only gap left is
  "could neither send NOR hold", which is already the one state that reddens the
  run and is surfaced by `ops_status.py [4]` at the next session start.
* Losing the push five times running does NOT silence the alert. Five failed
  pushes with the cause still absent means five DIFFERENT concurrent alarms, not
  a duplicate of ours. Silence is the worse failure, so it sends and says
  loudly that the claim went unrecorded.

Resend's own `Idempotency-Key` is a second, independent guard on the same
24 hours. This ledger is what makes RECOVERED work and what holds the fourteen
day reminder window; the header only closes a gap of seconds.

Stdlib only. This is the notification path and no dependency resolver may take
it down.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT / "alert_state.json"

VERSION = 1

#: One reminder a fortnight, no more. Total silence until a green run would mean
#: a breakage the owner missed once is never mentioned again. Twice a month is a
#: reminder, not alarm fatigue. Mirrored from the endpoint it replaces.
REMIND_AFTER_SECONDS = 14 * 24 * 3600

#: A caller looping on a mutating cause key could otherwise grow this file
#: without bound. Keep the newest entries and drop the oldest by first-seen.
MAX_OPEN = 200

#: Set by ci-alert.yml and alert-drain.yml. Anywhere else, including every test
#: and every local run, the ledger is read and written in place with no git.
COMMIT_ENV = "ALERT_STATE_COMMIT"


def _now() -> int:
    return int(time.time())


def _stamp(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def _ago(seconds: int) -> str:
    if seconds < 90 * 60:
        return f"{max(1, seconds // 60)} minutes"
    if seconds < 36 * 3600:
        return f"{seconds // 3600} hours"
    return f"{seconds // 86400} days"


def empty() -> dict:
    return {"version": VERSION, "updated_at": _stamp(_now()), "open": {}}


def load(path: Path | str = STATE) -> dict:
    """Read the ledger. A missing or unreadable file is an EMPTY ledger and
    never an exception: this runs on the failure path, and a notifier that
    crashes while handling a failure has told nobody anything."""
    p = Path(path)
    if not p.exists():
        return empty()
    try:
        doc = json.loads(p.read_text() or "{}")
    except (OSError, ValueError) as exc:
        print(f"alert_state: {p} is unreadable ({exc}), starting a fresh ledger")
        return empty()
    if not isinstance(doc, dict) or not isinstance(doc.get("open"), dict):
        print(f"alert_state: {p} has an unexpected shape, starting a fresh ledger")
        return empty()
    doc.setdefault("version", VERSION)
    return doc


def save(doc: dict, path: Path | str = STATE) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    entries = doc.get("open") or {}
    if len(entries) > MAX_OPEN:
        newest = sorted(entries.items(), key=lambda kv: int(kv[1].get("first", 0)))
        entries = dict(newest[-MAX_OPEN:])
    doc["open"] = dict(sorted(entries.items()))
    doc["updated_at"] = _stamp(_now())
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


class Decision:
    """What the ledger says to do about one message.

    `kind` is 'raise', 'resolve' or 'silent'. A silent decision is the common
    case on a green run and is what makes it safe to post a resolve after EVERY
    success without the clear becoming noise itself.
    """

    def __init__(self, kind, *, subject="", body="", note="", key="",
                 scope="", cleared=()):
        self.kind = kind
        self.subject = subject
        self.body = body
        self.note = note
        self.key = key
        self.scope = scope
        self.cleared = list(cleared)

    @property
    def sends(self) -> bool:
        return self.kind in ("raise", "resolve")

    def idempotency_key(self) -> str:
        """Stable for one alarm transition, so a racing duplicate collapses at
        Resend even if it got past the committed claim."""
        if self.kind == "raise":
            return f"alt-raise-{self.key}"
        if self.kind == "resolve":
            return f"alt-resolve-{self.scope}-{len(self.cleared)}"
        return ""


def decide(state: dict, payload: dict, now: int | None = None) -> Decision:
    """Pure. Given the ledger and a message, say whether it is sent and how.

    Mirrors `alt_api_alert()` exactly, because two definitions of "have we told
    them yet" is how one becomes wrong quietly:

      {subject, body}                 send it, no dedup (the legacy shape)
      {subject, body, dedupe_key}     raise once per cause, remind at 14 days
      {subject, body, resolve_scope}  clear, mailing once if anything was open
    """
    now = _now() if now is None else now
    subject = str(payload.get("subject") or "")
    body = str(payload.get("body") or "")
    resolve = str(payload.get("resolve_scope") or "")
    dedupe = str(payload.get("dedupe_key") or "")
    entries = state.get("open") or {}

    if resolve:
        open_keys = sorted(k for k in entries if k.startswith(resolve + ":"))
        if not open_keys:
            return Decision("silent", note="nothing was open for this scope",
                            scope=resolve)
        extra = f"\n\nThis clears {len(open_keys)} open alert(s):\n"
        for k in open_keys:
            extra += "  - " + str(entries[k].get("subject") or k) + "\n"
        return Decision("resolve", subject=subject, body=body + extra,
                        scope=resolve, cleared=open_keys)

    if dedupe:
        prior = entries.get(dedupe)
        if prior:
            first = int(prior.get("first", now))
            last = int(prior.get("last", first))
            if (now - last) < REMIND_AFTER_SECONDS:
                return Decision(
                    "silent", key=dedupe,
                    note=("suppressed: this exact cause is already open "
                          f"(raised {_ago(now - first)} ago)"))
            subject = "STILL FAILING: " + subject
        return Decision("raise", subject=subject, body=body, key=dedupe)

    return Decision("raise", subject=subject, body=body)


def apply(state: dict, decision: Decision, now: int | None = None) -> None:
    """Fold a decision into the ledger. Called before the send, so the commit
    that records it is the claim that stops a racing runner sending too."""
    now = _now() if now is None else now
    entries = state.setdefault("open", {})
    if decision.kind == "resolve":
        # Cleared whether or not the mail lands. The flag answers "is there an
        # unresolved failure", and the answer is now no. Leaving it open would
        # suppress the NEXT genuine alert for this cause, which is the more
        # expensive of the two mistakes.
        for k in decision.cleared:
            entries.pop(k, None)
        return
    if decision.kind == "raise" and decision.key:
        prior = entries.get(decision.key) or {}
        entries[decision.key] = {"first": int(prior.get("first", now)),
                                 "last": now, "subject": decision.subject}


# ---------------------------------------------------------------------------
# The claim, which is a git push
# ---------------------------------------------------------------------------

def _git(*args, cwd=None):
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True,
                              timeout=120, cwd=cwd or str(ROOT.parent))
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"git {args[0]} could not run ({exc})"
    return proc.returncode, (proc.stdout + proc.stderr).strip()[:300]


def commit_enabled() -> bool:
    return os.environ.get(COMMIT_ENV, "").lower() in {"1", "true", "yes"}


def _re_derive(path, payload, now):
    state = load(path)
    return state, decide(state, payload, now)


# Deliberately NOT a config knob. Five attempts is the same ceiling the outbox
# hold loop uses, and a sixth would not change the verdict: if five racing
# pushes all landed and the cause is still absent, they were five different
# alarms and ours is real.
CLAIM_ATTEMPTS = 5


def state_path(path: Path | str | None = None) -> Path:
    """The ledger this process reads. `ALERT_STATE_PATH` exists so the offline
    test suite can drive the real code against a temporary file rather than
    writing the committed one."""
    return Path(path or os.environ.get("ALERT_STATE_PATH") or STATE)


def claim(payload: dict, *, path: Path | str | None = None, now: int | None = None,
          sleep=time.sleep, commit: bool | None = None):
    """Decide, and record the decision durably before anything is sent.

    Returns (decision, recorded). `recorded` is False only when the ledger could
    not be written at all, which is loud and still sends.
    """
    now = _now() if now is None else now
    commit = commit_enabled() if commit is None else commit
    path = state_path(path)

    state, decision = _re_derive(path, payload, now)
    if not decision.sends:
        # The overwhelmingly common case on a green run. Nothing to write, no
        # git, no network, nothing to race with.
        return decision, True

    if decision.kind == "raise" and not decision.key:
        # The legacy shape: no cause key, so there is nothing to dedup and
        # nothing to record. Writing an unchanged ledger would be a commit that
        # says nothing, on the path where noise is the enemy.
        return decision, True

    if not commit:
        apply(state, decision, now)
        save(state, path)
        return decision, True

    rel = os.path.relpath(str(Path(path).resolve()), str(ROOT.parent))
    for attempt in range(1, CLAIM_ATTEMPTS + 1):
        code, note = _git("fetch", "origin", "main")
        if code:
            print(f"::warning::could not fetch main to claim the alarm: {note}")
        else:
            _git("reset", "--hard", "origin/main")
        state, decision = _re_derive(path, payload, now)
        if not decision.sends:
            print(f"another run claimed this first: {decision.note}")
            return decision, True
        apply(state, decision, now)
        save(state, path)
        _git("add", rel)
        code, _ = _git("diff", "--staged", "--quiet")
        if code == 0:
            return decision, True
        _git("commit", "-q", "-m",
             f"alert: claim {decision.kind} {decision.key or decision.scope}")
        code, note = _git("push", "origin", "HEAD:main")
        if code == 0:
            return decision, True
        print(f"claim push rejected (attempt {attempt}), re-deriving: {note}")
        sleep(attempt * 3)

    print("::warning::the alarm could not be recorded in railway/alert_state.json "
          "after five attempts, so this email is not deduped against a "
          "simultaneous one. It is being sent anyway. Silence is the worse "
          "failure, and five lost races with this cause still absent means five "
          "different alarms rather than a duplicate of this one.")
    return decision, False


#: The endpoint accepted these and the outbox still carries them, so the shape
#: is pinned here too. Lowercase only.
KEY_SAFE = re.compile(r"^[a-z0-9][a-z0-9:._-]{0,159}$")


def open_alarms(path: Path | str | None = None):
    """-> [(key, first_iso, last_iso, subject)], oldest first. For ops_status."""
    entries = (load(state_path(path)).get("open") or {})
    rows = sorted(entries.items(), key=lambda kv: int(kv[1].get("first", 0)))
    return [(k, _stamp(int(v.get("first", 0))), _stamp(int(v.get("last", 0))),
             str(v.get("subject") or "")) for k, v in rows]


# ---------------------------------------------------------------------------
# The orphan, and the human who closes it
# ---------------------------------------------------------------------------
#
# THE GAP. A cause key raised by `ci_alert.build_alert` is scoped
# `<workflow>:<branch>:<fingerprint>`, and it clears when a GREEN RUN OF THAT
# SAME SCOPE posts its resolve. `.github/workflows/tests.yml` fires on
# `pull_request` and on pushes to `main`. So the moment a feature branch is
# merged and deleted, no run of that scope can ever happen again, and the entry
# it left behind is unclearable. It sits open forever and earns one
# `STILL FAILING` reminder every fourteen days about a branch that does not
# exist, for a cause that was very likely fixed by the merge itself.
#
# This is not new. The endpoint-backed design had the identical gap and
# `alert_outbox.json` is full of `resolve:tests:<feature-branch>` entries that
# had nothing to clear. What changed on 2026-08-19 is that the ledger is a
# committed file printed by `ops_status.py [4b2]`, so the residue is finally
# VISIBLE — and a visible stale record that no one is allowed to touch is an
# invitation to hand-edit the JSON, which is how the fourteen-day window and the
# RECOVERED-once guarantee get broken without either failure announcing itself.
#
# THE RULE, taken from `data_integrity.close_incident` because this repo already
# settled the question there: a record a machine cannot clear is closed by a
# HUMAN, never by the calendar and never by an editor. `close_alarm` demands the
# three things a real resolution produces:
#
#   a reviewer, a reason, and WHERE THE CAUSE WAS ACTUALLY FIXED — the commit,
#   the version or the PR. That last field is this file's equivalent of
#   `--rows`: it is the difference between "the branch is gone" and "the defect
#   is gone". A branch being deleted is not evidence about a defect. If nobody
#   can name where it was fixed, the cause may still be live on main and closing
#   the alarm would suppress the next genuine raise of it.
#
# NOTHING ABOUT DEDUP MOVES. A close removes one entry exactly the way a
# `resolve` does, so the same cause raises again the next time it happens, one
# email, RECOVERED once, fourteen-day window untouched. What a close does that a
# resolve does not is leave an audit record saying who decided and why.

#: A closing reason has to be a finding, not a shrug. Mirrors
#: data_integrity.MIN_CLOSE_REASON_CHARS on purpose — a reviewer closing either
#: ledger is doing the same job and should meet the same bar.
MIN_CLOSE_REASON_CHARS = 40

#: Closed records are an audit trail, not an archive. Same reasoning as
#: MAX_OPEN: a caller looping on a mutating key must not grow the file forever.
MAX_CLOSED = 100

#: Duplicated from `ci_alert`, which imports THIS module — the dependency only
#: runs one way and must keep doing so. `tests/test_alert_state_close.py` pins
#: the two spellings together, so a rename over there fails here rather than
#: quietly turning every live-data alarm into an orphan candidate.
LIVE_DATA_SEGMENT = "live.data"

#: Statuses `classify_open` reports.
#:
#: ORPHANED and MERGED are two ways of being unclearable, and they are kept
#: apart because they are proved differently and one is stronger.
#:
#:   ORPHANED  the branch is GONE from origin. Permanent and unarguable: there
#:             is no ref left to push to, so no run of that scope can ever
#:             exist.
#:   MERGED    the branch is still on origin but is an ancestor of main — its
#:             work has landed and it is parked. This is the case that was
#:             actually sitting in the ledger on 2026-08-19: `ops/resend-ua`,
#:             PR #143 merged, zero commits ahead of main, ref never deleted.
#:             `tests.yml` fires on `pull_request` and on pushes to `main`, and
#:             a parked branch will see neither, so nothing will clear it either
#:             — but someone COULD push to it tomorrow, which is why this is a
#:             separate, weaker word rather than a second spelling of ORPHANED.
#:
#: UNKNOWN is never a pass and never an accusation: the remote was asked and did
#: not answer, so nothing about the branch was established.
OPEN = "open"
ORPHANED = "orphaned"
MERGED = "merged"
UNKNOWN = "unknown"

#: Both of the above need a human. Neither is going to resolve itself.
UNCLEARABLE = (ORPHANED, MERGED)

#: `<workflow>:<branch>:<md5[:16]>`, the shape `ci_alert.build_alert` mints and
#: the ONLY shape a branch can be read out of. Deliberately strict: other
#: senders put their own keys in this ledger (`ci-noise:<iso-week>`,
#: `relabel-hold:<ids>`) and a loose pattern would read a week number as a
#: deleted branch and declare a live alarm unclearable.
_BRANCH_KEY = re.compile(r"^([a-z0-9][a-z0-9._-]*):([a-z0-9][a-z0-9._-]*):([0-9a-f]{16})$")


def _slug(text, limit=48):
    """Duplicated from `ci_alert._slug` for the import-direction reason above.
    Must stay byte-identical: this is how a remote branch name is compared
    against the slug baked into a key."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:limit] or "unknown")


def branch_slug(key: str) -> str | None:
    """-> the branch fragment of a ci_alert cause key, or None.

    None for every key whose branch cannot be read with certainty: a live-data
    key (branch-free by design, and cleared by any branch's green run) and every
    non-ci_alert shape.
    """
    m = _BRANCH_KEY.match(key or "")
    if not m or m.group(2) == LIVE_DATA_SEGMENT:
        return None
    return m.group(2)


def remote_branches(timeout: int = 20):
    """-> {branch slug: tip sha} for every branch on `origin`, or None.

    None is the honest answer for a checkout with no remote, no network or an
    egress block, and it must never be confused with an empty dict — an empty
    dict would orphan every alarm in the ledger at once.

    Keyed by SLUG rather than by name because that is what a cause key carries:
    `ci_alert` bakes `_slug(branch, 32)` into the scope, so the ref
    `refs/heads/ops/resend-ua` is what the key `tests:ops-resend-ua:...` is
    talking about. Comparing names would have missed it.
    """
    try:
        proc = subprocess.run(["git", "ls-remote", "--heads", "origin"],
                              capture_output=True, text=True, timeout=timeout,
                              cwd=str(ROOT.parent))
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = {}
    for line in proc.stdout.splitlines():
        sha, _tab, ref = line.partition("\t")
        if ref.startswith("refs/heads/") and sha.strip():
            out[_slug(ref[len("refs/heads/"):], 32)] = sha.strip()
    return out or None


def _is_ancestor(sha: str, other: str, timeout: int = 20):
    """-> True / False / None, and None means LOCALLY UNANSWERABLE.

    A shallow or partial checkout does not hold the branch tip's object, and
    `git merge-base` says so with a non-zero exit that is indistinguishable from
    "no". Conflating the two would read every branch as live on a CI runner
    (harmless) or, with the test inverted, as merged (not harmless). So the
    object is checked for first and a missing one answers None, which
    `classify_open` reads as "nothing established" and leaves OPEN.
    """
    if not sha or not other:
        return None
    try:
        for obj in (sha, other):
            probe = subprocess.run(["git", "cat-file", "-e", f"{obj}^{{commit}}"],
                                   capture_output=True, text=True, timeout=timeout,
                                   cwd=str(ROOT.parent))
            if probe.returncode != 0:
                return None
        proc = subprocess.run(["git", "merge-base", "--is-ancestor", sha, other],
                              capture_output=True, text=True, timeout=timeout,
                              cwd=str(ROOT.parent))
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode in (0, 1):
        return proc.returncode == 0
    return None


def classify_open(path: Path | str | None = None, remote=False, *,
                  main_branch: str = "main", is_ancestor=None):
    """-> [(key, first_iso, last_iso, subject, status)], oldest first.

    `remote` is opt-in because asking costs a network round trip and this is
    read on the failure path. Pass True to have the remote asked, or a
    {slug: sha} mapping to supply the answer (which is how the tests drive it,
    with `is_ancestor` for the merged half).

    NOT ASKING and ASKING AND GETTING NO ANSWER are different facts, and only
    the second is UNKNOWN. A checkout with no network must not report every
    branch-scoped alarm as doubtful, and it must never report one as ORPHANED —
    `remote_branches` returning None means the remote was silent, not empty.

    Every fallback in here lands on OPEN, which is the conservative direction:
    the cost of missing an orphan is one stale line in a report, and the cost of
    inventing one is sending a reviewer to close a live alarm.
    """
    rows = open_alarms(path)
    asked = remote is not False
    known = remote_branches() if remote is True else (
        None if remote is False else dict(remote))
    ancestor = is_ancestor or _is_ancestor
    main_sha = (known or {}).get(_slug(main_branch, 32))
    out = []
    for key, first, last, subject in rows:
        slug = branch_slug(key)
        if slug is None or not asked:
            # Not a branch-scoped raise, or nobody looked. Either way there is
            # nothing to say beyond "open".
            status = OPEN
        elif known is None:
            # We asked and origin did not answer. Never a pass, never a verdict.
            status = UNKNOWN
        elif slug not in known:
            status = ORPHANED
        elif slug == _slug(main_branch, 32):
            # main is never parked and never deleted.
            status = OPEN
        else:
            status = MERGED if ancestor(known[slug], main_sha) is True else OPEN
        out.append((key, first, last, subject, status))
    return out


def close_alarm(key: str, reviewed_by: str, reason: str, fixed_in: str,
                path: Path | str | None = None) -> dict:
    """Close one open alarm on a human's finding. Returns the closed record.

    Raises ValueError on any missing argument, and writes NOTHING when it
    raises. `fixed_in` is required for the reason given in the section comment:
    a deleted branch is evidence about a branch, not about a defect.
    """
    p = state_path(path)
    state = load(p)
    entries = state.get("open") or {}
    rec = entries.get(key)
    if not rec:
        raise ValueError(f"no open alarm with key {key!r} "
                         f"(open: {sorted(entries) or 'nothing'})")
    reviewed_by = (reviewed_by or "").strip()
    reason = (reason or "").strip()
    fixed_in = (fixed_in or "").strip()
    if not reviewed_by:
        raise ValueError("--reviewed-by is required: a closed alarm names who closed it")
    if len(reason) < MIN_CLOSE_REASON_CHARS:
        raise ValueError(f"--reason must be at least {MIN_CLOSE_REASON_CHARS} characters "
                         f"of actual finding (got {len(reason)})")
    if not fixed_in:
        raise ValueError(
            "--fixed-in is required: name the commit, version or PR where the CAUSE "
            "was fixed. A deleted branch is not evidence that a defect is gone, and "
            "closing an alarm whose cause is still live suppresses the next real raise")

    now = _now()
    closed = {"key": key,
              "first": int(rec.get("first", now)),
              "last": int(rec.get("last", now)),
              "subject": str(rec.get("subject") or ""),
              "closed_at": _stamp(now),
              "reviewed_by": reviewed_by,
              "reason": reason,
              "fixed_in": fixed_in}
    entries.pop(key, None)
    history = list(state.get("closed") or [])
    history.append(closed)
    state["closed"] = history[-MAX_CLOSED:]
    save(state, p)
    return closed


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv and argv.index(flag) + 1 < len(argv) \
        else default


CLOSE_HELP = (
    "python3 railway/alert_state.py --close <key> --reviewed-by <name> "
    "--reason <what you found, 40+ chars> --fixed-in <commit|version|PR>")


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--close" in argv:
        # Local, key-free and offline on purpose. Closing an alarm is a human
        # act on a committed ledger, never a re-read of anything.
        try:
            closed = close_alarm(_arg(argv, "--close"),
                                 reviewed_by=_arg(argv, "--reviewed-by"),
                                 reason=_arg(argv, "--reason"),
                                 fixed_in=_arg(argv, "--fixed-in"))
        except ValueError as exc:
            print(f"REFUSED: {exc}")
            print("Nothing was written. An alarm closes on a finding, not on a flag.")
            print(f"  {CLOSE_HELP}")
            return 2
        print(f"CLOSED {closed['key']} — reviewed by {closed['reviewed_by']}")
        print(f"  raised:   {_stamp(closed['first'])}")
        print(f"  fixed in: {closed['fixed_in']}")
        print(f"  reason:   {closed['reason']}")
        print(f"  COMMIT {STATE.name}. The cause raises again, one email, if it recurs.")
        return 0

    if "--closed" in argv:
        history = list(load(state_path()).get("closed") or [])
        if not history:
            print("No alarm has been closed by review.")
            return 0
        print(f"{len(history)} alarm(s) closed by review (newest last):")
        for rec in history:
            print(f"  {rec.get('closed_at')}  {rec.get('key')}")
            print(f"      by {rec.get('reviewed_by')}, fixed in {rec.get('fixed_in')}")
            print(f"      {rec.get('reason')}")
        return 0

    # `--check-branches` asks the remote whether each raise's branch still
    # exists. Off by default so the plain listing stays offline and instant.
    rows = classify_open(remote="--check-branches" in argv)
    if not rows:
        print("No alarm is open. Nothing is being suppressed.")
        return 0
    print(f"{len(rows)} alarm(s) open (a repeat of the same cause stays quiet "
          f"until a green run clears it):")
    stuck = [r for r in rows if r[4] in UNCLEARABLE]
    for key, first, _last, subject, status in rows:
        # `.get`, not `[]`. The one command a human is required to run must not
        # crash on a status it has not been taught to spell — that is the
        # `close_incident` CLI's own scar, where every successful close printed
        # a traceback and read as "it failed, run it again".
        mark = {ORPHANED: "  ORPHANED", MERGED: "  MERGED",
                UNKNOWN: "  branch?"}.get(status, "")
        print(f"  {first}  {key}{mark}\n      {subject[:110]}")
    if stuck:
        print(f"\n{len(stuck)} of these cannot clear themselves:")
        print("  ORPHANED  the branch is gone from origin — no run of that scope can")
        print("            ever exist again.")
        print("  MERGED    the branch is still on origin but is an ancestor of main:")
        print("            its PR landed and it is parked. tests.yml fires on")
        print("            `pull_request` and on pushes to `main`, and a parked branch")
        print("            sees neither.")
        print("  Either way nothing will clear them but a review, and each one costs a")
        print("  false STILL FAILING email every 14 days until it is closed. See")
        print("  docs/RUNBOOK.md 'an open alarm cannot clear itself':")
        print(f"    {CLOSE_HELP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
