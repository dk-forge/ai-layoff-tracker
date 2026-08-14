#!/usr/bin/env python3
"""The gate and the guard for the DRAFT-ONLY self-healer (self-heal.yml).

WHAT THE HEALER IS, AND POINTEDLY IS NOT
----------------------------------------
When a data/test workflow goes red with a NEW, code-shaped failure, the
self-heal workflow asks Claude (via the pinned anthropics/claude-code-action)
to reproduce it from the failing run's log, diagnose it, and open a **draft
pull request** with a proposed fix. A second, adversarial pass reviews that
draft and posts its findings as a PR comment. A human merges — always. The
healer never merges, never pushes to main, never dispatches or re-runs a
workflow, never touches the database, and never edits spend or guardrail
constants (see FORBIDDEN below, enforced twice: named in the prompt, and
re-checked here by `check` after the fact, on the branch's real diff).

THIS MODULE IS THE PART THAT SAYS NO
------------------------------------
Most red runs in this repo must NOT be healed, because they are alarms that
are working as designed and already have an owner:

  * a live-data invariant FAIL (headline_movement, headline_containment,
    archive_recheck_cadence, ...) is a wrong number on the live site. It is
    closed by a HUMAN with --close-incident, never by code, and ci_alert.py
    has already emailed the owner about it under the branch-free live.data
    scope. A healer that "fixes" one can only loosen the invariant.
  * a self-timeout has already been mailed as CI SELF-TIMEOUT, and the right
    answer (raise the ceiling with the measured reason, or shrink the job) is
    a judgement call. Self-timeouts arrive as conclusion `cancelled`, which
    this gate refuses wholesale — only `failure` is ever healable.
  * a host-outage-shaped failure (5xx from asktherecruiter.com, unreachable
    /alert) has nothing wrong in this checkout. The sibling repo's host-watch
    owns the outage; healing it would mint a PR against weather.
  * the alerting workflows themselves (CI failure alert, Alert drain) — a
    healer thrashing on the alarm channel is the one loop worse than silence.

The classification is REUSED from ci_alert.py, not re-derived: the live-data
vocabulary comes from `ci_alert.live_data_identity()` (which reads
data_integrity's own registries), and the cause line comes from
`ci_alert.extract_cause()` on the same `--log-failed` text the email quotes.
Two classifiers that can disagree about one failure is how a failure gets
healed AND emailed as needs-a-human at the same time.

BUDGET IS STRUCTURAL. One healer at a time (the workflow's concurrency
group), one open PR per cause fingerprint (branch name = the fingerprint, so
`gh pr list` is the ledger), and a hard ceiling on simultaneous open healer
PRs. A flapping workflow cannot fan out drafts.

Exit codes: `gate` always exits 0 — a decision not to heal is a decision,
not a failure. `check` exits 1 when the branch touched a forbidden path,
which is precisely the red run the healer deserves.
"""
import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_alert  # noqa: E402  the ONE classification, reused not re-derived

#: Workflow display names (lowercased) the healer must never touch: the alarm
#: channel itself, and the healer. A healer PR "fixing" the alerter is a PR
#: nobody asked for against the one system that reports the healer's mistakes.
NEVER_HEAL = {
    "ci failure alert",
    "alert drain",
    "self-heal",
}

#: Workflows whose ONLY job is evaluating the live-data invariants. Any red
#: here is live data by construction, whatever the cause line looks like —
#: which matters because the assertion text often names a slice by its snake
#: key ("worldwide_all_time: CONTAINMENT FAILED") rather than by the registry
#: label `live_data_identity` matches on.
LIVE_DATA_WORKFLOWS = {
    "live data-integrity check",
}

#: A failure whose cause line looks like the HOST failing, not the code. The
#: 2026-07-31 outage manufactured red runs across both trackers with nothing
#: wrong in either checkout; a healer would have opened drafts against weather.
#: Deliberately narrow — a plain "error:" must not match, or everything would.
_HOST_OUTAGE = re.compile(
    r"HTTP 5\d\d\b"
    r"|returned error: 5\d\d\b"
    r"|could not reach"
    r"|Connection (?:refused|reset|timed out)"
    r"|\b50[234] (?:Bad Gateway|Service (?:Temporarily )?Unavailable|Gateway Time-?out)"
    r"|Gateway Time-?out"
    r"|Service Temporarily Unavailable"
    r"|site is in its deploy maintenance window",
    re.IGNORECASE)

#: Ceiling on simultaneously open healer PRs. Three distinct causes waiting on
#: a human is already a queue; a fourth draft is spend with no reader.
MAX_OPEN_PRS = 3

BRANCH_PREFIX = "self-heal/"

#: Paths the healer's branch may never change. Named in the action prompt AND
#: re-checked by `check` on the real diff, because a prompt is a request and a
#: diff is a fact. Everything here is either state a human owns
#: (headline_incidents, the outbox, the baton), a spend/guardrail constant
#: (spend.py), a supply-chain artifact nobody unattended may refresh (the
#: hash-pinned locks), or the healer itself.
FORBIDDEN = (
    "railway/spend.py",
    "railway/headline_incidents.json",
    "railway/alert_outbox.json",
    "railway/requirements.lock",
    "railway/requirements-min.lock",
    "docs/HANDOFF.md",
    ".github/workflows/self-heal.yml",
)


def fingerprint(workflow, cause):
    """A stable id for one cause of one workflow's red, branch-free.

    Branch-free on purpose: the healer fixes the CAUSE, and the same assertion
    failing on two branches is one fix, not two drafts. Numbers are normalised
    out exactly as ci_alert does for its dedupe key, so a count that drifts
    while the same thing stays broken is still one fingerprint.
    """
    text = f"{ci_alert._slug(workflow)}\n{ci_alert.normalise(cause or '')}"
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def branch_name(workflow, cause):
    return f"{BRANCH_PREFIX}{ci_alert._slug(workflow, 32)}-{fingerprint(workflow, cause)}"


def _live_data_marker(workflow, cause):
    """The live-data identity of a failure, or None.

    STRICTER than ci_alert.live_data_identity on purpose: the alerter only
    needs the registry LABELS (they are what the roll-up sentence prints),
    but an invariant that fails early can surface its snake KEY instead
    ("worldwide_all_time: CONTAINMENT FAILED" did, run 31828616421), and a
    healer that misses one live-data failure opens a draft that can only
    loosen an invariant. So this also matches the registry keys, and treats
    any red of a LIVE_DATA_WORKFLOWS member as live data by construction.
    """
    if (workflow or "").strip().lower() in LIVE_DATA_WORKFLOWS:
        return f"any red of '{workflow}' evaluates the live site"
    identity = ci_alert.live_data_identity(cause)
    if identity:
        return identity
    names = set()
    try:
        import data_integrity
        names |= {i.key for i in data_integrity.INVARIANTS
                  if getattr(i, "reads_live_data", False)}
        names |= {h.name for h in data_integrity.HEADLINES}
    except Exception as exc:  # pragma: no cover - defensive, gate must decide
        print(f"could not read the data-integrity registries ({exc})")
    hits = sorted(n for n in names if n and n in cause)
    return " | ".join(hits) if hits else None


def classify(workflow, conclusion, cause, branch="main"):
    """-> (heal: bool, reason: str). The reason is printed and shipped as a
    step output, so a skipped run says exactly which class it skipped as."""
    if branch and branch != "main":
        return False, (f"the failure is on branch '{branch}', not main. A "
                       "branch red is that branch's defect and its session's "
                       "(or PR author's) to fix — the healer only heals "
                       "unattended breakage on main.")
    if (conclusion or "").lower() != "failure":
        return False, (f"conclusion '{conclusion}' is not healable: only a plain "
                       "failure is. Self-timeouts arrive as 'cancelled' and are "
                       "already mailed as CI SELF-TIMEOUT; cancellations are "
                       "routine; success needs nothing.")
    if (workflow or "").strip().lower() in NEVER_HEAL:
        return False, (f"'{workflow}' is the alarm channel (or the healer "
                       "itself), and the healer never touches the alarm channel.")
    identity = _live_data_marker(workflow, cause or "")
    if identity:
        return False, ("this is a LIVE-DATA invariant failure "
                       f"({identity}): a wrong number on the live site, closed "
                       "by a human with --close-incident, never by code. "
                       "ci_alert.py has already emailed it under the "
                       "branch-free live.data scope. A code 'fix' here could "
                       "only loosen the invariant.")
    if cause and _HOST_OUTAGE.search(cause):
        return False, ("the cause line is host-outage-shaped "
                       "(5xx / unreachable): nothing in this checkout is "
                       "wrong. The sibling repo's host-watch owns outages.")
    return True, "a code-shaped failure with no standing owner: healable."


# --------------------------------------------------------------------------
# gh plumbing — same never-raise contract as ci_alert's: the gate runs on the
# failure path, and a gate that dies has decided nothing.
# --------------------------------------------------------------------------

def _gh(args_list, timeout=60):
    try:
        proc = subprocess.run(["gh"] + args_list, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"gh {' '.join(args_list[:2])} failed ({exc})")
        return None
    if proc.returncode != 0:
        print(f"gh {' '.join(args_list[:2])} exited {proc.returncode}: "
              f"{proc.stderr.strip()[:200]}")
        return None
    return proc.stdout


def run_metadata(repo, run_id):
    """(workflow_name, conclusion, branch, html_url) for a run id, or Nones.

    Lets `workflow_dispatch` point the gate at any PAST failed run, which is
    how the no-secret path is verified end to end without waiting for a new
    failure.
    """
    out = _gh(["api", f"repos/{repo}/actions/runs/{run_id}",
               "-q", "[.name, .conclusion, .head_branch, .html_url] | @tsv"])
    if not out:
        return None, None, None, None
    parts = out.strip().split("\t")
    return tuple(parts + [None] * (4 - len(parts)))[:4]


def open_healer_prs(repo):
    """Open PRs whose head branch is the healer's. [] on any gh problem —
    which fails OPEN toward healing; the per-fingerprint branch check in
    `gh pr create` still refuses an exact duplicate."""
    out = _gh(["pr", "list", "-R", repo, "--state", "open",
               "--json", "number,headRefName"])
    if not out:
        return []
    try:
        prs = json.loads(out)
    except ValueError:
        return []
    return [p for p in prs
            if (p.get("headRefName") or "").startswith(BRANCH_PREFIX)]


# --------------------------------------------------------------------------
# The forbidden-path guard. A prompt is a request; this is the check.
# --------------------------------------------------------------------------

def violations(changed_paths):
    """The subset of changed paths that the healer may never change."""
    bad = []
    for path in changed_paths:
        path = path.strip()
        if not path:
            continue
        for pattern in FORBIDDEN:
            if path == pattern or fnmatch.fnmatch(path, pattern) \
                    or (pattern.endswith("/") and path.startswith(pattern)):
                bad.append(path)
                break
    return bad


def changed_between(base, head):
    """`git diff --name-only base...head` — the branch's own changes only."""
    proc = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise SystemExit(f"git diff failed: {proc.stderr.strip()[:300]}")
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def _emit(outputs):
    """Step outputs for the workflow, plus a readable transcript."""
    for k, v in outputs.items():
        print(f"{k}: {v}")
    path = os.environ.get("GITHUB_OUTPUT", "")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for k, v in outputs.items():
            v = str(v).replace("\n", " ")
            fh.write(f"{k}={v}\n")


def gate(args):
    repo = args.repo
    workflow, conclusion = args.workflow, args.conclusion
    fetched_branch = None
    if not (workflow and conclusion):
        workflow, conclusion, fetched_branch, _url = run_metadata(repo, args.run_id)
        if not workflow:
            _emit({"heal": "no",
                   "reason": f"could not read run {args.run_id} from the API, "
                             "and a gate that cannot see the failure heals "
                             "nothing."})
            return 0

    branch = args.branch or fetched_branch
    if not branch:
        _wf, _con, branch, _url = run_metadata(repo, args.run_id)

    cause = ""
    if (conclusion or "").lower() == "failure":
        cause, _context = ci_alert.extract_cause(
            ci_alert.fetch_failed_log(repo, args.run_id),
            limit=ci_alert.ALERT_CAUSE_LIMIT)

    heal, reason = classify(workflow, conclusion, cause, branch or "main")
    if not heal:
        _emit({"heal": "no", "reason": reason})
        return 0

    branch = branch_name(workflow, cause)
    open_prs = open_healer_prs(repo)
    same = [p["number"] for p in open_prs if p.get("headRefName") == branch]
    if same:
        _emit({"heal": "no",
               "reason": f"a healer PR for this exact cause is already open "
                         f"(#{same[0]}, branch {branch}). One draft per "
                         "cause; the human has not merged or closed it yet."})
        return 0
    if len(open_prs) >= MAX_OPEN_PRS:
        _emit({"heal": "no",
               "reason": f"{len(open_prs)} healer PRs are already open "
                         f"(ceiling {MAX_OPEN_PRS}). More drafts than "
                         "readers is spend, not healing."})
        return 0

    _emit({"heal": "yes", "reason": reason, "branch": branch,
           "fingerprint": fingerprint(workflow, cause),
           "cause": (cause or "(no cause line could be extracted)")[:400]})
    return 0


def check(args):
    if args.files is not None:
        changed = [p for p in args.files if p.strip()]
    else:
        changed = changed_between(args.base, args.head)
    bad = violations(changed)
    if bad:
        print("::error::the healer's branch touched FORBIDDEN paths:")
        for path in bad:
            print(f"::error::  {path}")
        print("::error::These are spend/guardrail constants, human-owned "
              "state, hash-pinned locks, or the healer itself. This PR must "
              "not be merged as it stands; the guard has failed the healer "
              "run so the red is on the healer, not hidden in the draft.")
        return 1
    print(f"checked {len(changed)} changed path(s): none are forbidden.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="decide whether a failed run is healable")
    g.add_argument("--run-id", required=True)
    g.add_argument("--workflow", default="",
                   help="from the workflow_run payload; fetched from the API "
                        "when absent (the workflow_dispatch path)")
    g.add_argument("--conclusion", default="")
    g.add_argument("--branch", default="",
                   help="the failing run's head branch; fetched when absent")
    g.add_argument("--repo", default=os.environ.get(
        "GITHUB_REPOSITORY", "dk-forge/ai-layoff-tracker"))

    c = sub.add_parser("check", help="fail if a branch touched forbidden paths")
    c.add_argument("--base", default="origin/main")
    c.add_argument("--head", default="HEAD")
    c.add_argument("--files", nargs="*", default=None,
                   help="explicit changed-path list (tests use this)")

    args = ap.parse_args(argv)
    return gate(args) if args.cmd == "gate" else check(args)


if __name__ == "__main__":
    sys.exit(main())
