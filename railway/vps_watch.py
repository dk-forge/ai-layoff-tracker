#!/usr/bin/env python3
"""Watch the self-hosted runner box FROM OUTSIDE it, and say so once.

WHY THIS EXISTS
---------------
The owner's Contabo VPS (`atr-runner`) is the self-hosted GitHub Actions
runner for three repositories. It carries all sandbox CI and, soon, every
tracker job that touches the WordPress host. Nothing watched it. A box that
goes offline, fills its disk or loses its runner service does not fail a
single job: the jobs QUEUE, forever, and every surface in this repo reads
"no run happened" as "nothing is wrong". That is the absent-read-as-ok shape
(docs/INCIDENT_CLASSES.md) wearing a new hat.

Two halves, deliberately on two different machines:

* `vps-heartbeat.yml` runs ON the box every 30 minutes and reads disk,
  memory, load, swap, the runner services and the reboot flag. It can only
  report while the box is up, which is exactly why it is not enough.
* This module runs OFF the box (`vps-watch.yml`, hourly, GitHub-hosted). It
  asks the GitHub API whether each repo's `atr-runner-*` runner is online and
  whether the heartbeat's latest run is recent and green. A box that is up
  but whose heartbeat stopped is also a fault.

WHAT IT MAILS, AND HOW OFTEN
----------------------------
Every fault has one stable dedupe key and goes through `ops_notify.notify`,
the one door for operational mail. The ledger in `railway/alert_state.json`
raises a key ONCE, reminds at fourteen days and mails RECOVERED once when the
same key is resolved. So an outage that lasts a weekend is two emails: one
when it starts, one when it ends.

    vps:offline:<repo>      that repo's runner is not `online` (or is absent)
    vps:heartbeat-stale     the heartbeat has not succeeded in HEARTBEAT_MAX_AGE

THREE STATES, NOT TWO
---------------------
A GitHub API error is UNKNOWN. It is never a pass (the runner may well be
down) and never a fault (mailing "offline" because api.github.com hiccuped
is how an alert channel earns a filter). On UNKNOWN nothing is raised and
NOTHING IS RESOLVED either: clearing an open alarm on a reading we did not
get would mail RECOVERED for a box that is still dark. The run exits 3, the
same code `ops_status.py` uses for "could not check", so the failure is
visible without being an alarm.

WHAT IS NOT HERE
----------------
No remediation. This module cannot reboot the box or restart a service, and
nothing in a workflow can start a Claude session that could. See RUNBOOK
"the VPS watchdog fired". Stdlib only: it is a notification path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

#: The three repositories the box serves. The runner in each is named
#: `atr-runner-<repo>`; the match is on the prefix so a rename of the suffix
#: does not silently turn every repo into "absent".
REPOS = (
    "dk-forge/ai-layoff-tracker",
    "dk-forge/talent-intelligence-tracker",
    "dk-forge/asktherecruiter-sandbox",
)
RUNNER_PREFIX = "atr-runner-"

#: The heartbeat runs every 30 minutes on the box. Two hours is four missed
#: ticks: long enough that a queued tick behind a long sandbox job is not a
#: fault, short enough that a dead runner is noticed the same morning.
HEARTBEAT_WORKFLOW = "vps-heartbeat.yml"
HEARTBEAT_REPO = "dk-forge/ai-layoff-tracker"
HEARTBEAT_MAX_AGE_SECONDS = 2 * 60 * 60

KEY_HEARTBEAT = "vps:heartbeat-stale"

EXIT_OK = 0
EXIT_UNKNOWN = 3


def key_offline(repo: str) -> str:
    """`vps:offline:<repo>` with only the repository name, lowercase, so the
    key satisfies the ledger's KEY_SAFE shape (`dk-forge/` carries a slash)."""
    return "vps:offline:" + repo.split("/")[-1].lower()


ALL_KEYS = tuple(key_offline(r) for r in REPOS) + (KEY_HEARTBEAT,)


@dataclass
class Reading:
    """One checked thing: a fault, a clear, or an unknown."""
    key: str
    state: str          # "FAULT" | "CLEAR" | "UNKNOWN"
    detail: str = ""


@dataclass
class Verdict:
    readings: list = field(default_factory=list)

    @property
    def faults(self):
        return [r for r in self.readings if r.state == "FAULT"]

    @property
    def clears(self):
        return [r for r in self.readings if r.state == "CLEAR"]

    @property
    def unknowns(self):
        return [r for r in self.readings if r.state == "UNKNOWN"]


# --------------------------------------------------------------------------
# The API. One function, injectable, so the tests never spawn `gh`.
# --------------------------------------------------------------------------

def gh_api(path: str, timeout: int = 60):
    """-> (ok, parsed_json_or_error_text). Uses the `gh` CLI, which carries
    the workflow's GH_TOKEN. Any failure is (False, text); never raises."""
    try:
        proc = subprocess.run(["gh", "api", path], capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"gh api {path} could not run ({exc})"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip()[:300] or "gh api failed"
    try:
        return True, json.loads(proc.stdout)
    except ValueError as exc:
        return False, f"gh api {path} returned something that is not JSON ({exc})"


# --------------------------------------------------------------------------
# Pure judgement over the two payload shapes.
# --------------------------------------------------------------------------

def judge_runner(repo: str, payload) -> Reading:
    """The runners list for one repo -> FAULT / CLEAR on `vps:offline:<repo>`."""
    key = key_offline(repo)
    runners = (payload or {}).get("runners") or []
    ours = [r for r in runners if str(r.get("name", "")).startswith(RUNNER_PREFIX)]
    if not ours:
        names = ", ".join(sorted(str(r.get("name")) for r in runners)) or "none"
        return Reading(key, "FAULT",
                       f"no runner named {RUNNER_PREFIX}* is registered in "
                       f"{repo} (registered: {names})")
    bad = [r for r in ours if str(r.get("status")) != "online"]
    if bad:
        what = "; ".join(f"{r.get('name')} is {r.get('status')}" for r in bad)
        return Reading(key, "FAULT", f"{repo}: {what}")
    return Reading(key, "CLEAR", f"{repo}: {ours[0].get('name')} is online")


def _parse_iso(text) -> float | None:
    try:
        return datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def judge_heartbeat(payload, now: float | None = None,
                    max_age: int = HEARTBEAT_MAX_AGE_SECONDS) -> Reading:
    """The heartbeat's runs list -> FAULT / CLEAR on `vps:heartbeat-stale`.

    Stale means the newest run is older than `max_age`, OR the newest COMPLETED
    run did not succeed. A run that is still in progress is not judged on its
    own; the one before it is, because an in-flight run says nothing yet."""
    now = time.time() if now is None else now
    runs = (payload or {}).get("workflow_runs") or []
    if not runs:
        return Reading(KEY_HEARTBEAT, "FAULT",
                       f"{HEARTBEAT_WORKFLOW} has never run")
    newest = runs[0]
    stamp = _parse_iso(newest.get("run_started_at") or newest.get("created_at"))
    if stamp is None:
        return Reading(KEY_HEARTBEAT, "UNKNOWN",
                       "the newest heartbeat run carries no readable timestamp")
    age = now - stamp
    if age > max_age:
        return Reading(KEY_HEARTBEAT, "FAULT",
                       f"the newest heartbeat run started {int(age // 60)} min "
                       f"ago (ceiling {max_age // 60} min); the box is up but "
                       "its heartbeat stopped, or the runner is not picking up "
                       "jobs")
    completed = [r for r in runs if r.get("status") == "completed"]
    if not completed:
        return Reading(KEY_HEARTBEAT, "UNKNOWN",
                       "no completed heartbeat run yet (one is in flight)")
    last = completed[0]
    if last.get("conclusion") != "success":
        return Reading(KEY_HEARTBEAT, "FAULT",
                       f"the latest completed heartbeat concluded "
                       f"{last.get('conclusion')}: {last.get('html_url', '')}")
    return Reading(KEY_HEARTBEAT, "CLEAR",
                   f"heartbeat ran {int(age // 60)} min ago and succeeded")


def check(api=gh_api, now: float | None = None) -> Verdict:
    """Read everything once. An API error on any reading is UNKNOWN for that
    reading only; the other readings are still judged."""
    verdict = Verdict()
    for repo in REPOS:
        ok, payload = api(f"repos/{repo}/actions/runners?per_page=100")
        if not ok:
            verdict.readings.append(Reading(key_offline(repo), "UNKNOWN",
                                            f"{repo}: {payload}"))
            continue
        verdict.readings.append(judge_runner(repo, payload))

    ok, payload = api(f"repos/{HEARTBEAT_REPO}/actions/workflows/"
                      f"{HEARTBEAT_WORKFLOW}/runs?per_page=5")
    if not ok:
        verdict.readings.append(Reading(KEY_HEARTBEAT, "UNKNOWN", str(payload)))
    else:
        verdict.readings.append(judge_heartbeat(payload, now=now))
    return verdict


# --------------------------------------------------------------------------
# Reporting: raise once, clear once, say nothing on UNKNOWN.
# --------------------------------------------------------------------------

def _fault_subject(reading: Reading) -> str:
    if reading.key == KEY_HEARTBEAT:
        return "VPS heartbeat is stale: atr-runner may be down"
    return f"VPS runner offline: {reading.key.split(':')[-1]}"


def _fault_body(reading: Reading) -> str:
    return "\n".join([
        f"Fault: {reading.detail}",
        "",
        "What is automatic: this email (once per fault, RECOVERED once when it",
        "clears). Nothing reboots the box or restarts a runner.",
        "",
        "What a human does (RUNBOOK: \"the VPS watchdog fired\"):",
        "  box unreachable  -> Contabo panel: reboot, or VNC console",
        "  runner not online -> ssh in, cd ~/runners/<repo>, sudo ./svc.sh status",
        "                      then sudo ./svc.sh start",
        "  disk floor        -> the heartbeat run's summary names the usage;",
        "                      clear _work/ and old docker layers, then rerun",
        "",
        "Every job on the contabo label is queued, not failed, until this clears.",
    ])


def report(verdict: Verdict, notify) -> None:
    """Send the ledger one message per key. FAULT raises, CLEAR resolves (the
    ledger stays silent when nothing was open), UNKNOWN sends nothing."""
    for reading in verdict.readings:
        if reading.state == "FAULT":
            notify(_fault_subject(reading), _fault_body(reading),
                   dedupe_key=reading.key, what="VPS watchdog alarm")
        elif reading.state == "CLEAR":
            notify(f"RECOVERED: {reading.key}",
                   f"The watchdog now reads: {reading.detail}",
                   resolve_scope=reading.key, what="VPS watchdog recovery")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry-run" in argv
    verdict = check()
    for r in verdict.readings:
        print(f"[{r.state:7}] {r.key}: {r.detail}")

    if dry:
        print("dry run: nothing sent, nothing recorded")
    else:
        import ops_notify  # local import: keeps this module importable offline
        report(verdict, ops_notify.notify)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        try:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write("## VPS watch\n\n| key | state | detail |\n|---|---|---|\n")
                for r in verdict.readings:
                    fh.write(f"| `{r.key}` | {r.state} | {r.detail} |\n")
        except OSError:
            pass

    if verdict.unknowns:
        print(f"UNKNOWN: {len(verdict.unknowns)} reading(s) could not be taken. "
              "Not a pass, not a fault.")
        return EXIT_UNKNOWN
    # A fault has already been mailed through the ledger. Going red here as
    # well would make ci-alert.yml mail the same cause a second time.
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
