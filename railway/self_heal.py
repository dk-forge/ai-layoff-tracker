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
  * a cancellation from OUTSIDE the job (a superseded push, a concurrency
    group, a human) is routine and healable by nobody. But a job that ran past
    its own `timeout-minutes` ALSO arrives as `cancelled`, and that is a real,
    repeating, permanent failure — one this gate refused wholesale until
    2026-08-18, while ci_alert.py emailed the very same event as CI SELF-TIMEOUT.
    The two are told apart by `ci_alert.self_timeout_of_run()`, called here,
    never re-implemented. A self-timeout IS healed, and the healer's hard limit
    against widening a ceiling is what keeps the fix honest: the answer is to
    make the job fit, not to move the wall.
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
    conc = (conclusion or "").lower()
    if conc == "cancelled":
        # `cancelled` is TWO different events wearing one word. A run stopped by
        # a superseded push or a concurrency group is not a failure and must
        # stay out of here. A job that ran past its own `timeout-minutes` is a
        # real, permanent, repeating failure — GitHub just reports it as
        # `cancelled` rather than `timed_out`. The discrimination is
        # ci_alert.is_self_timeout_cause() and it is CALLED, never re-implemented:
        # this gate refused `cancelled` wholesale until 2026-08-18, when "Tests"
        # self-killed at 15m0s on main and six Self-heal runs in the next half
        # hour skipped, while ci_alert emailed the same event as CI SELF-TIMEOUT.
        if not ci_alert.is_self_timeout_cause(cause):
            return False, ("cancelled by something OUTSIDE the job (a superseded "
                           "push, a concurrency group, a human). That is routine "
                           "and is not a failure. Only a run that killed itself "
                           "on its own timeout-minutes is healable here.")
        # fall through: a self-timeout IS a failure, and a code-shaped one.
    elif conc != "failure":
        return False, (f"conclusion '{conclusion}' is not healable: only a plain "
                       "failure, or a `cancelled` that is really a self-timeout, "
                       "is. Cancellations from outside the job are routine; "
                       "success needs nothing.")
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
    conc = (conclusion or "").lower()
    if conc == "failure":
        cause, _context = ci_alert.extract_cause(
            ci_alert.fetch_failed_log(repo, args.run_id),
            limit=ci_alert.ALERT_CAUSE_LIMIT)
    elif conc == "cancelled":
        # A self-killed job has NO failed step, so --log-failed returns nothing;
        # the distinguishing line lives in the job's check-run annotations. Same
        # call the alerter makes, so the two cannot disagree about one run.
        cause = ci_alert.self_timeout_of_run(repo, args.run_id) or ""

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


# --------------------------------------------------------------------------
# The MERGE GATE — owner-authorized auto-merge, 2026-08-14 ("a human clicks
# merge — I want you to click merge, I'm okay with that"). The click is
# delegated; the CONDITIONS are not, and every one of them resolves UNKNOWN
# to "stay a draft", never to a pass:
#
#   1. the adversarial reviewer's LATEST machine-readable verdict is exactly
#      LOOKS SOUND (absent, ambiguous, or anything else = no merge);
#   2. the forbidden-path guard passed (the workflow wires this: the
#      automerge job `needs` the guard job's success);
#   3. the branch's diff is source/test files only — never workflows, and
#      never anything in FORBIDDEN (a plugin fix may carry its own version
#      bump; that is a source file);
#   4. the merged preview runs the offline test suite and produces NO failure
#      that main does not already have. This is the honest form of "CI is
#      green except the documented expected live-data reds": a standing red
#      (the live-data incident) fails BOTH runs and is subtracted; a fix that
#      breaks anything new fails the gate. It also closes the gap where a
#      branch pushed with GITHUB_TOKEN triggers no checks at all.
#
# Kill switch: repository variable SELF_HEAL_AUTOMERGE_DISABLED=true turns
# only the merge off; the healer keeps drafting for a human.
# --------------------------------------------------------------------------

#: The first line of the adversarial reviewer's PR comment. Anything that
#: does not match, or matches with a different verdict, keeps the draft.
VERDICT_MARKER = "SELF-HEAL-REVIEW-VERDICT:"
_VERDICT = re.compile(rf"^{re.escape(VERDICT_MARKER)}\s*(LOOKS SOUND|NEEDS WORK|DO NOT MERGE)\s*$",
                      re.MULTILINE)


def review_verdict(comment_bodies):
    """The LATEST verdict across the PR's comments, or None. One comment may
    carry at most one marker line; a comment with several is ambiguous and
    counts as no verdict at all."""
    verdict = None
    for body in comment_bodies:
        found = _VERDICT.findall(body or "")
        if len(found) == 1:
            verdict = found[0]
        elif len(found) > 1:
            verdict = None
    return verdict


def fetch_review_verdict(repo, pr):
    out = _gh(["api", f"repos/{repo}/issues/{pr}/comments",
               "--paginate", "-q", "[.[].body]"])
    if not out:
        return None
    bodies = []
    try:
        for chunk in out.strip().splitlines():
            bodies.extend(json.loads(chunk))
    except ValueError:
        return None
    return review_verdict(bodies)


def automergeable_paths(changed):
    """(ok, reason). Stricter than the guard: auto-merge additionally refuses
    ANY workflow/CI change — a human can merge those from the draft."""
    bad = violations(changed)
    if bad:
        return False, f"forbidden paths changed: {', '.join(bad)}"
    ci = [p for p in changed if p.strip().startswith(".github/")]
    if ci:
        return False, ("the fix edits CI/workflows "
                       f"({', '.join(ci)}); auto-merge never ships those")
    if not changed:
        return False, "the branch changes nothing"
    return True, "source/test files only"


#: unittest -q / pytest -q failure headers, one per failing test.
_SUITE_FAIL = re.compile(
    r"^(?:FAIL|ERROR):\s+(\S+(?:\s+\([^)]*\))?)\s*$"      # unittest
    r"|^FAILED\s+(\S+::\S+)",                              # pytest
    re.MULTILINE)


def suite_failures(output):
    """The set of failing test identities in a suite run's output."""
    return {a or b for a, b in _SUITE_FAIL.findall(output or "")}


def run_suite(test_cmd, cwd):
    proc = subprocess.run(["bash", "-c", test_cmd], capture_output=True,
                          text=True, timeout=3600, cwd=cwd)
    return suite_failures(proc.stdout + "\n" + proc.stderr), proc.returncode


def merge_gate(args):
    """Exit 0 = every condition holds and the PR may be merged. Any other
    outcome prints why and exits 1 — which the workflow treats as 'stays a
    draft', a decision rather than a red run."""
    repo = args.repo

    verdict = fetch_review_verdict(repo, args.pr)
    if verdict != "LOOKS SOUND":
        print(f"no merge: the reviewer's verdict is "
              f"{verdict or 'absent/ambiguous'}, and only LOOKS SOUND merges. "
              "UNKNOWN is never a pass.")
        return 1
    print("reviewer verdict: LOOKS SOUND")

    changed = changed_between("origin/main", f"origin/{args.branch}")
    ok, reason = automergeable_paths(changed)
    if not ok:
        print(f"no merge: {reason}")
        return 1
    print(f"paths: {reason} ({len(changed)} changed)")

    # The merged preview, against main's own baseline. A standing red fails
    # both suites and is subtracted; anything NEW blocks the merge.
    git = lambda *a: subprocess.run(["git"] + list(a), capture_output=True,
                                    text=True, timeout=120)
    base_fail, _ = run_suite(args.test_cmd, args.test_cwd)
    print(f"main baseline: {len(base_fail)} failing test(s)")
    merge = git("merge", "--no-commit", "--no-ff", f"origin/{args.branch}")
    if merge.returncode != 0:
        print(f"no merge: the branch does not merge cleanly onto main: "
              f"{merge.stderr.strip()[:200]}")
        return 1
    head_fail, _ = run_suite(args.test_cmd, args.test_cwd)
    print(f"merged preview: {len(head_fail)} failing test(s)")
    new = sorted(head_fail - base_fail)
    if new:
        print("no merge: the fix introduces failures main does not have:")
        for name in new[:10]:
            print(f"  {name}")
        return 1
    fixed = sorted(base_fail - head_fail)
    print(f"no new failures; {len(fixed)} baseline failure(s) fixed"
          + (f": {', '.join(fixed[:5])}" if fixed else ""))
    print("merge-gate: ALL CONDITIONS HOLD")
    return 0


# --------------------------------------------------------------------------
# THE HEALING LEDGER — the owner's words: "if things break it's easy to
# backtrack and fix fast". Every auto-merge appends a terse revert-index
# entry to docs/HEALING-LOG.md and a narrative entry to docs/TECHLOG.md (a
# heal is a change AND an incident, and the house rule is both get logged).
# The append is BEST-EFFORT and must never fail the heal: the workflow step
# that calls this warns loudly on failure and stays green. Both files are
# append-only newest-first; a concurrent-merge conflict is resolved by
# keeping BOTH entries, same as any TECHLOG conflict.
# --------------------------------------------------------------------------

HEALING_LOG = "docs/HEALING-LOG.md"
TECHLOG = "docs/TECHLOG.md"

_HEALING_HEADER = """# Healing log — auto-merged fixes

The terse revert index for everything the self-healer merged on its own
(owner authorization 2026-08-14). **Every heal is ONE squash commit: the
revert is `git revert <merge sha>`.** Draft-only mode is one line: set the
repository variable `SELF_HEAL_AUTOMERGE_DISABLED=true` (RUNBOOK, "The
self-healer"). Newest first; if two merges race, keep BOTH entries. The
narrative for each heal lives in docs/TECHLOG.md under the same date.
"""


def _insert_entry(path, header, entry):
    """Prepend `entry` before the first '## ' heading (newest-first), creating
    the file with `header` when absent."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        text = header
    lines = text.splitlines(keepends=True)
    at = next((i for i, ln in enumerate(lines) if ln.startswith("## ")),
              len(lines))
    lines[at:at] = [entry if entry.endswith("\n") else entry + "\n"]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(lines))


def record(args):
    """Append the two ledger entries for one auto-merged heal. Returns 0 on
    success, 1 on any problem — the CALLER treats 1 as a warning, never as a
    failed heal."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    day = now.strftime("%Y-%m-%d")
    files = [f for f in (args.files or []) if f.strip()]
    filelist = ", ".join(files) if files else "(unrecorded)"

    ledger_entry = (
        f"## {stamp} — {args.workflow} — PR #{args.pr} — merge {args.merge_sha}\n"
        f"- run:      {args.run_url or '(unrecorded)'}\n"
        f"- cause:    {args.cause or '(no cause line extracted)'}\n"
        f"- files:    {filelist}\n"
        f"- reviewer: {VERDICT_MARKER} {args.verdict}\n"
        f"- revert:   `git revert {args.merge_sha}`\n\n")

    techlog_entry = (
        f"## {day} - self-heal: auto-merged fix for '{args.workflow}' (PR #{args.pr})\n\n"
        f"**What failed:** {args.cause or 'no cause line could be extracted'} "
        f"({args.run_url or 'run url unrecorded'}).\n\n"
        f"**The fix:** {filelist}. PR #{args.pr} carries the diff and the "
        f"red-before/green-after evidence; the squash merge is "
        f"{args.merge_sha}.\n\n"
        f"**Adversarial review:** {args.verdict} — the reviewer's PR comment "
        f"records what it tried in order to break the fix.\n\n"
        f"**Revert:** `git revert {args.merge_sha}`. Auto-merged under the "
        f"owner's 2026-08-14 authorization; the kill switch is the repository "
        f"variable `SELF_HEAL_AUTOMERGE_DISABLED=true` (draft-only mode).\n\n")

    ok = True
    for path, header, entry in ((args.healing_log, _HEALING_HEADER, ledger_entry),
                                (args.techlog, "# Tech Log\n\n", techlog_entry)):
        try:
            _insert_entry(path, header, entry)
            print(f"recorded in {path}")
        except OSError as exc:
            print(f"::warning::could not record the heal in {path}: {exc}. "
                  "The merge itself is unaffected; add the entry by hand.")
            ok = False
    return 0 if ok else 1


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

    m = sub.add_parser("merge-gate",
                       help="exit 0 only if every owner-authorized "
                            "auto-merge condition holds")
    m.add_argument("--pr", required=True)
    m.add_argument("--branch", required=True)
    m.add_argument("--test-cmd",
                   default="python3 -m unittest discover -s tests -q")
    m.add_argument("--test-cwd", default="railway")
    m.add_argument("--repo", default=os.environ.get(
        "GITHUB_REPOSITORY", "dk-forge/ai-layoff-tracker"))

    r = sub.add_parser("record",
                       help="append one auto-merged heal to the ledgers "
                            "(best-effort; the caller never fails the heal "
                            "on this)")
    r.add_argument("--pr", required=True)
    r.add_argument("--workflow", required=True)
    r.add_argument("--merge-sha", required=True)
    r.add_argument("--run-url", default="")
    r.add_argument("--cause", default="")
    r.add_argument("--verdict", default="LOOKS SOUND")
    r.add_argument("--files", nargs="*", default=None)
    r.add_argument("--healing-log", default=HEALING_LOG)
    r.add_argument("--techlog", default=TECHLOG)

    args = ap.parse_args(argv)
    if args.cmd == "gate":
        return gate(args)
    if args.cmd == "merge-gate":
        return merge_gate(args)
    if args.cmd == "record":
        return record(args)
    return check(args)


if __name__ == "__main__":
    sys.exit(main())
