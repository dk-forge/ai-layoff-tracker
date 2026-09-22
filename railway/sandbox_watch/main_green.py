#!/usr/bin/env python3
"""Once a day: what is the SANDBOX repo's main ACTUAL state?

THIS FILE WATCHES ANOTHER REPOSITORY. It is a port of
`backend/scripts/main_green.py` in the private `dk-forge/asktherecruiter-sandbox`,
moved here on 2026-09-22 and running from this PUBLIC repo on a free
GitHub-hosted runner. It imports nothing from that repo and reaches it only
through `gh api` with `MERGE_TRAIN_TOKEN`.

WHY IT MOVED, AND WHAT THAT DID NOT BUY. It did NOT save hosted minutes:
`main-green-check.yml` there already ran on `${{ vars.CI_RUNNER }}`, the VPS,
so its GitHub bill was already zero. What it buys is INDEPENDENCE. That repo's
CI, its merge train and this check all ran on one VPS box, so the thing
answering "is main green?" died with the thing that makes main green, and a
VPS outage read as silence rather than as UNKNOWN. A watchdog on the machine
it watches is the `/alert`-on-the-host-it-reports-about mistake, which this
repo's CLAUDE.md already names twice.

WHAT STAYED BEHIND, AND WHY THIS IS TWO COPIES ON PURPOSE. The module there
is NOT deleted: `live_look.py`, `hosted_billing_sentinel.py` and
`train_watchdog.py` import `sync_issue`, `find_issue`, `problem_set`,
`never_started`, `Verdict`, `gh_json` and `ReadError` from it, and all three
still run in that repo. Only its SCHEDULE moved. So the judging half below
exists in two repositories and can drift, which is a real cost and is
accepted knowingly rather than hidden: the copy that RUNS daily is this one,
and `tests/test_sandbox_main_green.py` is what pins its behaviour.

THE RUNNING ISSUE STAYS IN THE SANDBOX. It is opened, rewritten and closed on
`dk-forge/asktherecruiter-sandbox`, so that repo's issue list remains the one
place to look for what is wrong with it. Nothing about the issue changes
because the judge moved.

Below is the original docstring, unchanged.

Once a day, independently: what is main's ACTUAL state?

On 2026-09-21 we found that merges made by the merge train (the default
Actions token) never started an on-push workflow, so main's colour was simply
unknown for a day and nobody was told. The train now dispatches follow-up
jobs, but that is the train marking its own homework. This asks from outside.

For every workflow in WORKFLOWS it reads the runs on main and reports one of
four states. They are four states, not two:

  PASS           the newest conclusive completed run succeeded, and it is current
  FAIL           the newest conclusive completed run did not succeed
  NEVER_STARTED  the newest run "failed" with runner_id 0 and zero steps: hosted
                 capacity refused (the org's Actions spending limit). Not code.
  UNKNOWN  no run at all; or no conclusive completed run; or the newest one is
           older than its ceiling while main has moved on (main's head carries
           no run of it and is past the grace); or the read failed or came
           back empty. ABSENCE OF A RUN IS NEVER GREEN.

Exit 0 only when every workflow is PASS. 1 = at least one FAIL or
NEVER_STARTED, 3 = neither but at least one UNKNOWN. Any non-zero is a red run, which self-heal.yml and the
hourly ops check already read; the running issue is what reaches a person.

It also keeps ONE running issue, found by a hidden marker: opened on the first
non-green run, its body rewritten only when the SET of failing or unknown
workflows changes, closed on the next all-PASS run. Never a second one.

Stdlib only. Every read goes through `gh api`; tests replace `gh_json`.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

DEFAULT_REPO = "dk-forge/asktherecruiter-sandbox"
BRANCH = "main"
GRACE = timedelta(hours=2)
ISSUE_TITLE = "Main is not green"
MARKER = "<!-- main-green-check:running-issue -->"
SET_PREFIX = "<!-- main-green-check:set="

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
# The FOURTH state. When the org's Actions spending limit trips, a hosted job
# "completes" in seconds with runner_id 0, runner_name "", zero steps and
# conclusion failure (2026-08-31, 2026-09-11, 2026-09-22). That is hosted
# capacity refused: not a FAIL (nothing ran), not UNKNOWN (there IS a run),
# never a PASS. hosted_billing_sentinel.py names the cause from the VPS.
NEVER_STARTED = "NEVER_STARTED"
NEVER_STARTED_TEXT = "NEVER_STARTED: hosted capacity refused (billing), runner_id 0, zero steps"
# A cancelled or skipped run decided nothing, so the judge looks past it.
INCONCLUSIVE = frozenset({"cancelled", "skipped", "stale", ""})


def never_started(jobs: Sequence[dict]) -> bool:
    """True when EVERY job was refused by the runner pool: runner_id 0 or no
    runner_name, no steps, conclusion failure. An empty job list is not
    evidence of anything and reads False."""
    jobs = list(jobs or [])
    if not jobs:
        return False
    for j in jobs:
        # Absence of a field is not evidence: the API always carries both.
        if "runner_id" not in j or "steps" not in j:
            return False
        if str(j.get("conclusion") or "") != "failure":
            return False
        if j.get("runner_id") not in (0, None) and str(j.get("runner_name") or ""):
            return False
        if list(j.get("steps") or []):
            return False
    return True


@dataclass(frozen=True)
class Workflow:
    file: str
    why: str
    # Days after which a green run stops vouching for a main that has moved.
    # None = path-filtered with no schedule, so age alone says nothing.
    max_age_days: float | None = 3.0


WORKFLOWS: tuple[Workflow, ...] = (
    # The five merge gates. Each also runs nightly on main, so three days
    # without a green run on a main that moved means nothing vouches for it.
    Workflow("backend-architecture-gate.yml", "Backend Test Gate, both test trees"),
    Workflow("frontend-ci.yml", "Frontend CI"),
    Workflow("frontend-arch-checks.yml", "Frontend Arch Checks"),
    Workflow("chrome-extension-ci.yml", "Chrome Extension CI"),
    Workflow("frontend-railway-parity.yml", "the build Railway will actually run"),
    Workflow("security-scan.yml", "Security Scan, scheduled daily"),
    Workflow("changelog-check.yml", "push-only, so a token merge cannot start it "
             "and age says nothing; its last result is still judged",
             max_age_days=None),
    # Absent on purpose: ci-gate-selftest.yml and every "fixture:" job are red
    # by design; production-e2e-gate.yml judges production, not main; the
    # crons and canaries have their own alarms.
)


class ReadError(RuntimeError):
    """A read that did not happen. Always UNKNOWN, never zero and never PASS."""


def gh_json(path: str, *, method: str = "GET", payload: dict | None = None) -> Any:
    cmd = ["gh", "api", path]
    if method != "GET":
        cmd += ["-X", method]
    if payload is not None:
        cmd += ["--input", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                              input=json.dumps(payload) if payload is not None else None)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReadError(f"gh api {path}: {exc}") from exc
    if proc.returncode != 0:
        raise ReadError(f"gh api {path} exited {proc.returncode}: "
                        f"{(proc.stderr or proc.stdout).strip()[:300]}")
    text = proc.stdout.strip()
    if not text:
        raise ReadError(f"gh api {path} returned nothing (NOREAD, not zero)")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReadError(f"gh api {path} did not return JSON: {exc}") from exc


def _when(text: str) -> datetime:
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


@dataclass(frozen=True)
class Verdict:
    file: str
    state: str
    detail: str
    url: str = ""


def _newest_decided(runs: Sequence[dict]) -> dict | None:
    decided = [r for r in runs if r.get("status") == "completed"
               and str(r.get("conclusion") or "") not in INCONCLUSIVE]
    # Never trust the listing's order: one live read on 2026-09-21 put a
    # six day old run first. ISO timestamps sort as text.
    return max(decided, key=lambda r: str(r.get("created_at") or "")) if decided else None


def judge(wf: Workflow, payload: Any, head_sha: str, head_at: datetime,
          now: datetime) -> Verdict:
    """Pure. `payload` is the Actions runs listing for one workflow on main."""
    if not isinstance(payload, dict) or "workflow_runs" not in payload:
        return Verdict(wf.file, UNKNOWN, "runs listing had no workflow_runs (NOREAD)")
    runs = payload.get("workflow_runs") or []
    if not runs:
        return Verdict(wf.file, UNKNOWN, "no run on main at all")
    newest = _newest_decided(runs)
    if newest is None:
        return Verdict(wf.file, UNKNOWN,
                       f"{len(runs)} run(s) on main, none completed with a verdict")
    url = str(newest.get("html_url") or "")
    sha = str(newest.get("head_sha") or "")[:8]
    conclusion = str(newest.get("conclusion"))
    if conclusion != "success":
        return Verdict(wf.file, FAIL, f"newest completed run is {conclusion} on {sha}", url)
    try:
        age = now - _when(newest.get("updated_at") or newest.get("created_at"))
    except (TypeError, ValueError):
        return Verdict(wf.file, UNKNOWN, "newest run carries no readable date", url)
    if wf.max_age_days is not None and age > timedelta(days=wf.max_age_days):
        head_has_run = any(r.get("head_sha") == head_sha for r in runs)
        if not head_has_run and (now - head_at) > GRACE:
            return Verdict(
                wf.file, UNKNOWN,
                f"newest green run is {age.days}d old (ceiling {wf.max_age_days:g}d) "
                f"and main's head {head_sha[:8]} has no run", url)
    return Verdict(wf.file, PASS, f"success on {sha}, {_age_text(age)} ago", url)


def _age_text(age: timedelta) -> str:
    hours = int(age.total_seconds() // 3600)
    return f"{hours}h" if hours < 48 else f"{age.days}d"


def read_head(repo: str, api: Callable[..., Any]) -> tuple[str, datetime]:
    data = api(f"repos/{repo}/commits/{BRANCH}")
    sha = str((data or {}).get("sha") or "") if isinstance(data, dict) else ""
    when = str((((data or {}).get("commit") or {}).get("committer") or {}).get("date") or "") \
        if isinstance(data, dict) else ""
    if not sha or not when:
        raise ReadError(f"could not read the head of {BRANCH} (NOREAD)")
    return sha, _when(when)


def check(repo: str, api: Callable[..., Any], now: datetime,
          workflows: Sequence[Workflow] = WORKFLOWS) -> list[Verdict]:
    try:
        head_sha, head_at = read_head(repo, api)
    except ReadError as exc:
        return [Verdict(wf.file, UNKNOWN, f"main's head unreadable: {exc}") for wf in workflows]
    out = []
    for wf in workflows:
        try:
            payload = api(f"repos/{repo}/actions/workflows/{wf.file}/runs"
                          f"?branch={BRANCH}&per_page=30")
        except ReadError as exc:
            out.append(Verdict(wf.file, UNKNOWN, f"read failed: {exc}"))
            continue
        out.append(refine(wf, judge(wf, payload, head_sha, head_at, now), payload, repo, api))
    return out


def refine(wf: Workflow, verdict: Verdict, payload: Any, repo: str,
           api: Callable[..., Any]) -> Verdict:
    """A FAIL whose run never started is NEVER_STARTED, not FAIL. Only a
    failure is looked at, and a jobs read that fails leaves the FAIL alone:
    the fourth state needs evidence, never absence."""
    if verdict.state != FAIL:
        return verdict
    run = _newest_decided((payload or {}).get("workflow_runs") or [])
    if run is None or run.get("id") is None:
        return verdict
    try:
        jobs = (api(f"repos/{repo}/actions/runs/{run['id']}/jobs?per_page=100") or {}).get("jobs")
    except ReadError:
        return verdict
    if never_started(jobs or []):
        return Verdict(wf.file, NEVER_STARTED, NEVER_STARTED_TEXT, verdict.url)
    return verdict


def exit_code(verdicts: Sequence[Verdict]) -> int:
    states = {v.state for v in verdicts}
    if not verdicts or states - {PASS, FAIL, UNKNOWN, NEVER_STARTED}:
        return 3
    if FAIL in states or NEVER_STARTED in states:
        return 1
    if UNKNOWN in states:
        return 3
    return 0


# --------------------------------------------------------------------------
# The one running issue
# --------------------------------------------------------------------------
def problem_set(verdicts: Sequence[Verdict]) -> str:
    """Identity of the incident: WHICH workflows are not green, and how.
    No SHA, no age, no URL, so a daily re-run of the same trouble is quiet."""
    bad = sorted(f"{v.file}={v.state}" for v in verdicts if v.state != PASS)
    return hashlib.sha256("|".join(bad).encode()).hexdigest()[:16] if bad else ""


def issue_body(verdicts: Sequence[Verdict], now: datetime) -> str:
    lines = [MARKER, f"{SET_PREFIX}{problem_set(verdicts)} -->", "",
             "The daily main-green check found main is not verifiably green. "
             "UNKNOWN is not a pass: it means nothing vouches for main. NEVER_STARTED is "
             "hosted capacity refused (billing): see the sentinel issue "
             "\"Hosted runners are blocked (billing)\" for the one-click fix.", "",
             "| Workflow | State | Detail |", "|---|---|---|"]
    for v in verdicts:
        link = f" ([run]({v.url}))" if v.url else ""
        lines.append(f"| `{v.file}` | {v.state} | {v.detail}{link} |")
    lines += ["", f"As of {now.strftime('%Y-%m-%d %H:%M')} UTC. This body changes only "
              "when the set of failing or unknown workflows changes, and the issue "
              "closes itself on the next all-PASS run. Do not open a second one."]
    return "\n".join(lines)


def find_issue(repo: str, api: Callable[..., Any], marker: str = MARKER) -> dict | None:
    found = []
    for page in range(1, 11):
        data = api(f"repos/{repo}/issues?state=open&per_page=100&page={page}")
        if not isinstance(data, list):
            raise ReadError("open-issues listing was not a list (NOREAD)")
        found += [i for i in data if "pull_request" not in i
                  and marker in str(i.get("body") or "")]
        if len(data) < 100:
            break
    return min(found, key=lambda i: int(i["number"])) if found else None


def sync_issue(repo: str, verdicts: Sequence[Verdict], api: Callable[..., Any],
               now: datetime, *, title: str = ISSUE_TITLE, marker: str = MARKER,
               set_prefix: str = SET_PREFIX,
               body: Callable[[Sequence[Verdict], datetime], str] | None = None) -> str:
    """Returns what it did, for the log. Raises ReadError if it could not.

    The keyword arguments let another checker (live_look.py) keep its OWN one
    running issue with this same logic; its `body` must carry `marker` and
    `set_prefix + problem_set(verdicts) + " -->"`."""
    body = body or issue_body
    current = find_issue(repo, api, marker)
    wanted = problem_set(verdicts)
    if not wanted:
        if current is None:
            return "no open issue, none needed"
        n = current["number"]
        api(f"repos/{repo}/issues/{n}/comments", method="POST", payload={
            "body": f"All PASS at {now.strftime('%Y-%m-%d %H:%M')} UTC. Closing."})
        api(f"repos/{repo}/issues/{n}", method="PATCH",
            payload={"state": "closed", "state_reason": "completed"})
        return f"closed issue #{n}"
    if current is None:
        made = api(f"repos/{repo}/issues", method="POST",
                   payload={"title": title, "body": body(verdicts, now)})
        return f"opened issue #{(made or {}).get('number', '?')}"
    n = current["number"]
    if f"{set_prefix}{wanted} -->" in str(current.get("body") or ""):
        return f"issue #{n} already describes this set, left alone"
    api(f"repos/{repo}/issues/{n}", method="PATCH",
        payload={"body": body(verdicts, now)})
    return f"updated issue #{n} (the set changed)"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # NEVER `GITHUB_REPOSITORY`. In the sandbox that variable named the repo
    # to judge, because the check ran inside it. Here it names THIS repo, so
    # reading it would silently judge the layoff tracker's own workflows
    # (which do not exist by those names) and report a wall of UNKNOWN about
    # the wrong repository while looking like it ran. The target is explicit
    # or it is the default, and `tests/test_sandbox_main_green.py` pins that.
    repo = os.environ.get("SANDBOX_REPO") or DEFAULT_REPO
    now = datetime.now(timezone.utc)
    verdicts = check(repo, gh_json, now)
    print(f"main-green check, {repo}@{BRANCH}, {now.strftime('%Y-%m-%d %H:%M')} UTC")
    for v in verdicts:
        print(f"  {v.state:<8}{v.file:<34}{v.detail}")
    code = exit_code(verdicts)
    if "--no-issue" not in args:
        try:
            print(f"issue: {sync_issue(repo, verdicts, gh_json, now)}")
        except ReadError as exc:
            print(f"issue: UNKNOWN, the running issue could not be synced: {exc}")
    bad = [v for v in verdicts if v.state != PASS]
    if code:
        print("\nerror: main is NOT verifiably green: "
              + "; ".join(f"{v.file} {v.state} ({v.detail})" for v in bad))
    else:
        print("\nmain is green: every listed workflow PASS")
    return code


if __name__ == "__main__":
    sys.exit(main())
