#!/usr/bin/env python3
"""A red CI run becomes an email, deduped by CAUSE rather than by run.

THE GAP THIS CLOSES
-------------------
On 2026-07-30 `tests/test_dedup_live.py` caught a real live defect — Spirit
Airlines reading 11,069 US-2026 jobs instead of ~7,069 because a news row was
stacking on top of the WARN notices for the same layoff — and CI went red EIGHT
consecutive times over several hours. Nobody acted, because the signal reached
GitHub Actions and stopped there. The owner's words: "I don't get notified of
workflow failures. I only see them when I check."

The defect was far bigger than the one company the guard names: 64 employers
double-counting 60,367 jobs, and 43 employers with 113,786 real jobs suppressed
to zero, including Boeing's genuine 17,000-job announcement reading as nothing.
A test that finds that and tells no one is a test that did not run.

WHY DEDUPE BY CAUSE IS THE WHOLE DESIGN, NOT A REFINEMENT
---------------------------------------------------------
Eight identical emails would have trained the owner to filter this sender, and a
filtered alert channel is the ORIGINAL problem wearing a new hat. This repo has
already proved that at first hand: a `newsapi` staleness alarm carried a 2-day
ceiling on a job that ran WEEKLY, so it read stale five days out of seven
forever — and that permanently-red, un-clearable amber was the ONLY item
ops_status showed on the day Spirit was live and wrong. **An alarm that cannot
be cleared is an alarm nobody reads.**

So: the numbers are normalised OUT of the failure message before it is
fingerprinted. `Spirit US-2026=11069: news-vs-WARN dedup regressed` and
`Spirit US-2026=11071: ...` are the SAME cause and mail once. A different
assertion in the same workflow is a different cause and mails immediately. The
open/resolved state itself lives server-side in the WordPress `/alert` endpoint,
next to the mailer, because a "sent" record that can disagree with what was
actually sent is worth less than no record.

AND IT CLEARS. On the next green run of the same workflow+branch, this posts a
resolve for that scope and the endpoint mails "RECOVERED" exactly once (and
nothing at all if nothing was open). A fixed alarm that never says so is one the
owner has to go and check, which is what we are trying to stop.

Usage (the workflow passes these from the `workflow_run` event payload):

    python3 railway/ci_alert.py --run-id 30581225504 --workflow Tests \\
        --conclusion failure --branch main --event push \\
        --run-url https://github.com/dk-forge/ai-layoff-tracker/actions/runs/...

WHAT HAPPENS WHEN THE HOST IS DOWN (added 2026-07-31, after it was)
-------------------------------------------------------------------
`/alert` is a route on the WordPress site. Bluehost answered 504 for everything
under /blog/ for about seven minutes on 2026-07-31 and about six that afternoon,
and in the sibling tracker — the same alerter, the same host — the alarm failed
four times saying "HTTP 504 from /alert". **The alerting system depended on the
host it was alerting about**, and it exited 1 while doing so, so one outage
manufactured extra red runs, which manufactured more alerts, which also failed.
This file had the identical defect and simply had no red run that night.

Two separate fixes, for two separate defects:

1. DELIVERY IS DURABLE. A failed POST is retried in-run (transient failures
   only) and then HELD in `railway/alert_outbox.json` — committed, so it
   outlives the runner and the outage. `alert-drain.yml` delivers it later. See
   railway/alert_outbox.py for why a committed file rather than a longer backoff.

2. A HELD ALERT IS NOT A FAILURE. Holding exits 0. The only non-zero left is
   "could neither deliver NOR hold", which is the one state where the owner will
   never hear about the original failure. **Do not restore the old `exit 1` on a
   failed POST**: it told a session the ALERTER was broken when the alerter was
   working perfectly and the host was down.

Exit codes: 0 = handled (mailed, suppressed, held for later, or nothing to do)
            1 = could neither deliver the alert NOR hold it. Nobody is going to
                be told about the original failure, so this run goes RED and
                ops_status.py [4] surfaces it at the next session start.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ModSecurity on the WP host blocks python-requests outright; every request to
# asktherecruiter.com must look like a real client. (Iron rule, see CLAUDE.md.)
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# Conclusions worth an email. `cancelled` is deliberately NOT here: runs are
# cancelled routinely (superseded pushes, concurrency groups) and alerting on
# them is exactly the noise that gets a sender filtered.
ALERTABLE = {"failure", "timed_out", "startup_failure"}

# ...BUT A JOB THAT KILLS ITSELF ON `timeout-minutes` ALSO REPORTS `cancelled`,
# and that is a different animal entirely. GitHub reserves the `timed_out`
# conclusion for a handful of cases; a step that simply runs past the job's own
# `timeout-minutes` ends the run `cancelled`, indistinguishable at the
# conclusion level from a superseded push. So the blanket "cancelled is noise"
# rule silenced a whole class of permanent failure:
#
#   * "Archive WARN sources to Wayback" (weekly, timeout-minutes: 20) has been
#     killed at 20m21s and 20m19s — EVERY run it has ever had, 2026-07-27 and
#     2026-08-03. It has never once completed and no email has ever fired.
#   * "Data quality report" (daily, timeout-minutes: 10) died at 10m27s on
#     2026-07-29 and 10m27s on 2026-08-03, against a normal runtime of ~45s.
#
# A self-timeout is never routine: nothing outside the job cancelled it, it hit
# a wall the repository itself set. Repeated on a schedule it is precisely the
# silent-forever failure this alerter exists to abolish — the archive re-check
# invariant was sitting at 8.6 days against a 10-day bound while the archiver
# had not finished in two weeks and nothing said a word.
#
# So `cancelled` is still not alertable by conclusion. It is alertable by
# EVIDENCE, and the evidence is NOT in the log: a self-killed job's log ends on
# a bare "##[error]The operation was canceled.", which is character-for-character
# what an externally cancelled job prints. The distinguishing line lives in the
# job's CHECK-RUN ANNOTATIONS:
#
#   failure  The job has exceeded the maximum execution time of 20m0s
#   failure  The operation was canceled.
#
# (verified against run 30799948006). Only a self-timeout produces the first
# line, so that is what is matched, and `--log-failed` is useless here anyway:
# a cancelled run has no failed STEP, so it returns empty.
_SELF_TIMEOUT = re.compile(
    r"has exceeded the maximum (?:execution|operation) time of\s*(.+?)\.?$",
    re.IGNORECASE)

#: The opening of every cause line this module writes for a self-killed job.
#: It is a CONSTANT because a second reader needs to recognise the verdict
#: without re-deriving it: self_heal.py's gate is handed the cause string and
#: must know whether it came from here. Matching `_SELF_TIMEOUT` against this
#: line does not work and must not be attempted — the annotation says "has
#: exceeded", the line below says "it exceeded", and that near-miss is exactly
#: the kind of second-copy drift that left the healer blind to self-timeouts
#: until 2026-08-18.
SELF_TIMEOUT_MARKER = "the job cancelled ITSELF on timeout-minutes"


def fetch_annotations(repo, run_id):
    """The job annotations for a run, one message per line. "" on any problem.

    Two `gh api` calls, and neither may raise: this runs on the failure path,
    and a notifier that dies while handling a failure has told nobody anything.
    """
    def _api(path, jq):
        try:
            proc = subprocess.run(["gh", "api", path, "-q", jq],
                                  capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"could not read {path} ({exc})")
            return ""
        if proc.returncode != 0:
            print(f"gh api {path} exited {proc.returncode}: "
                  f"{proc.stderr.strip()[:200]}")
        return proc.stdout or ""

    jobs = _api(f"repos/{repo}/actions/runs/{run_id}/jobs", ".jobs[].id")
    out = []
    for job_id in jobs.split():
        out.append(_api(f"repos/{repo}/check-runs/{job_id}/annotations",
                        ".[].message"))
    return "\n".join(out)


def self_timeout_cause(text):
    """-> the runner's own timeout line, or None if this run was cancelled by
    something OUTSIDE itself (a superseded push, a concurrency group, a human).

    Returning None is the common case and it MUST stay silent. Mailing about
    every cancelled run is the noise that gets a sender filtered, which is the
    defect this whole module exists to abolish, not a bar it may trade away.
    """
    for raw in (text or "").splitlines():
        found = _SELF_TIMEOUT.search(strip_prefix(raw))
        if found:
            return (f"{SELF_TIMEOUT_MARKER}: it exceeded "
                    f"the maximum execution time of {found.group(1).strip()}")
    return None


# THE ONE ANSWER to "is this `cancelled` run a real failure?", for every caller.
#
# It is a function, and it is exported, because it was not: this alerter learned
# that a self-timeout hides inside `cancelled` and self_heal.py did not, so the
# healer's gate refused `cancelled` wholesale and skipped every self-timeout the
# alerter had just emailed. On 2026-08-18 "Tests" self-killed at 15m0s on main
# and six Self-heal runs in the next half hour evaluated their job condition to
# false. Two components reading one event with two vocabularies. Anything that
# needs to tell a superseded push from a job that ran past its own wall calls
# THIS, so there is one definition to correct when GitHub changes the wording.
def is_self_timeout_cause(cause):
    """Was this cause line produced by self_timeout_cause()? -> bool.

    The read side of SELF_TIMEOUT_MARKER, for any caller holding the cause
    string rather than the run.
    """
    return bool(cause) and SELF_TIMEOUT_MARKER in cause


def self_timeout_of_run(repo, run_id):
    """-> the timeout cause line for a run that killed itself, else None.

    None means the cancellation came from OUTSIDE the job (a superseded push, a
    concurrency group, a human) and is routine: no email, no heal.
    """
    return self_timeout_cause(fetch_annotations(repo, run_id))


# Actions log lines arrive as "<job>\t<step>\t<ISO timestamp> <content>".
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s?")

# The generic tail that every failed step prints. It is true and it is useless:
# "a job failed" is precisely the alert the owner already ignores.
_GENERIC_ERROR = re.compile(r"^Process completed with exit code \d+\.?$")

_ANNOTATION = re.compile(r"^##\[error\](.*)$")
# A Python traceback's terminal line: "AssertionError: False is not true : ..."
_PY_EXCEPTION = re.compile(r"^(?:[A-Za-z_][\w.]*\.)?[A-Z]\w*(?:Error|Exception|Failure)\b.*$")
# pytest's assertion detail lines, and its per-test summary.
_PYTEST_DETAIL = re.compile(r"^E\s{2,}(\S.*)$")
_PYTEST_SUMMARY = re.compile(r"^FAILED\s+\S+::\S+.*$")
# unittest's failure header — names the test, which is context the exception lacks.
_UNITTEST_HEAD = re.compile(r"^(?:FAIL|ERROR):\s+\w+\s+\(.*\)\s*$")
_LOOSE_ERROR = re.compile(r"(?i)(?:^|\s)(?:error|fatal|failed)[: ]")

# Applied IN ORDER to turn a message into a cause fingerprint. Anything that can
# change run-to-run while the underlying defect stays the same must die here, or
# the same broken thing mails twice.
_NORMALISE = (
    (re.compile(r"/home/runner/work/[^/\s]+/[^/\s]+/"), ""),   # runner-absolute paths
    (re.compile(r"\b\d{4}-\d{2}-\d{2}T[\d:.]+Z?\b"), "<TS>"),  # timestamps
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "<DATE>"),
    (re.compile(r"\b[0-9a-f]{7,40}\b"), "<HEX>"),              # SHAs, uuid chunks
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<ADDR>"),
    (re.compile(r"\d+(?:[.,]\d+)*"), "<N>"),                   # every remaining number
    (re.compile(r"\s+"), " "),
)


#: The EXACT shape `/alert` accepts for `dedupe_key` and `resolve_scope`,
#: mirrored from `alt_api_alert()` in wordpress-plugin/.../includes/api.php
#: (`$safe = '/^[a-z0-9][a-z0-9:._-]{0,159}$/'`). Lowercase only, and the
#: endpoint answers a settled 400 for anything else.
#:
#: This lives here because a key rejected by the endpoint is not a bad email,
#: it is NO email: the sibling's weekly noise report minted `ci-noise:2026-W32`
#: with `%G-W%V`, took a 400 sixteen times, went `stuck` in the outbox, and the
#: host watchdog then failed every tick on "alerts are stuck with the host up".
#: A permanently red watchdog cannot report an outage. Any caller that composes
#: a key by hand rather than through `_slug` must assert against this.
KEY_SAFE = re.compile(r"^[a-z0-9][a-z0-9:._-]{0,159}$")


def _slug(text, limit=48):
    """A stable, key-safe scope fragment. Two different workflows must never
    collide here — a collision would silence a real, separate breakage."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:limit] or "unknown")


def strip_prefix(line):
    """Drop the job/step/timestamp columns `gh run view --log` prepends."""
    parts = line.split("\t")
    if len(parts) >= 3:
        line = parts[-1]
    return _TS.sub("", line).rstrip()


def normalise(message):
    """Reduce a failure message to its CAUSE — what stays the same while a
    still-broken thing keeps failing with different numbers."""
    out = (message or "").strip()
    for pattern, replacement in _NORMALISE:
        out = pattern.sub(replacement, out)
    return out.strip()


# ---------------------------------------------------------------------------
# ONE LIVE-DATA INCIDENT IS ONE ALARM, WHATEVER BRANCH NOTICED IT
# ---------------------------------------------------------------------------
#
# Measured on 2026-08-10/11. ONE open incident — the US headline moving +93,210
# jobs with no row that explains it — mailed the owner SIX times in seven hours,
# from runs 31421748713, 31421827146, 31421971041, 31425792582, 31448285345,
# 31450680641 and 31450792070.
#
# The obvious suspect is wrong, and it matters that it is wrong, because "the
# numbers keep moving" would have been fixed by widening `_NORMALISE` and the
# widening would have bought nothing. Run the six real assertion strings through
# `normalise` and they are BYTE-IDENTICAL: +93,210 and +93,290, 3.0d and 3.3d,
# +18 and +19 entries all collapse to `<N>` exactly as designed.
#
# What actually differed was the SCOPE. `scope = workflow:branch`, so the same
# live-data incident minted a separate key on every branch that ran the suite:
#
#   tests:main:8a5b96fc74f3e59d                        (3 runs, correctly 1 email)
#   tests:docs-handoff-external-review:4fe3831793263ff8
#   tests:feat-changed-rows-endpoint:efeece54c1a18dcd
#   tests:feat-filed-basis-default:d9078245a54da1c5
#   tests:claude-sticky-headline-incidents:555efd27b335228d
#
# Branch belongs in the scope for a CODE failure: a test that only fails on one
# branch is that branch's defect, and folding it into main's alarm would hide it.
# A LIVE-DATA invariant is the opposite animal. It reads asktherecruiter.com, not
# the checkout. Every branch is looking at the same one wrong number, so every
# branch is the SAME incident and the branch that happened to notice it is noise.
#
# The seventh run adds the second half of the defect. The sticky-incident ledger
# prefixes the detail with "OPEN INCIDENT, opened 0d ago (<timestamp>)", which
# pushed the sentence past `extract_cause`'s 400-character cut and lopped a
# different tail off it ("...reconcile-supers" instead of "...corrections log").
# A key built by regexing numbers out of a sentence is hostage to every later
# change in that sentence's SHAPE, and that sentence is written to be read by a
# human, so it will keep changing.
#
# So the key is not built from the sentence at all. It is built from the STABLE
# IDENTITY of the incident: which invariant, and which slice. Both come from
# data_integrity's own registries, which is what makes this narrow — an
# unrecognised assertion is not a live-data incident and keeps the branch-scoped
# behaviour above, and two different invariants, or two different slices of one
# invariant, are two different identities and two different emails.

#: The branch component of the scope, replaced for live-data incidents. A dot
#: cannot appear in a `_slug`, so no branch name can ever collide with this.
LIVE_DATA_SEGMENT = "live.data"

#: How much of the failing line the ALERTER reads. Only ever used to decide the
#: key; the email still shows the first 400 characters, unchanged. The live
#: roll-up sentence runs to 741 characters with the sticky-incident prefix, and
#: `_roll_up` appends a second slice AFTER the first, so a cut anywhere inside
#: it is a cut through the identity.
ALERT_CAUSE_LIMIT = 2000

_VOCABULARY = None


def _live_data_vocabulary():
    """(invariant labels, slice labels) that mark an assertion as live-data.

    Read from data_integrity's OWN registries rather than copied, for the same
    reason ops_status imports them: a hand-copied list goes stale silently and a
    stale list here means a renamed invariant quietly returns to mailing once
    per branch. Only invariants with `reads_live_data` qualify — a local
    invariant CAN genuinely fail on one branch and not another, and that one
    must keep its branch.

    Never raises: this runs on the failure path.
    """
    global _VOCABULARY
    if _VOCABULARY is not None:
        return _VOCABULARY
    invariants, slices = (), ()
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import data_integrity
        invariants = tuple(sorted(
            {i.label for i in data_integrity.INVARIANTS
             if getattr(i, "label", "") and getattr(i, "reads_live_data", False)},
            key=len, reverse=True))
        slices = tuple(sorted(
            {h.label for h in data_integrity.HEADLINES if getattr(h, "label", "")},
            key=len, reverse=True))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"could not read the data-integrity vocabulary ({exc}): "
              "live-data failures will be keyed per branch")
    _VOCABULARY = (invariants, slices)
    return _VOCABULARY


def live_data_identity(cause):
    """-> the stable identity of a live-data incident, or None.

    "No headline moves without rows to explain it | United States jobs, all time"
    for every run of the US incident, no matter what the numbers, the elapsed
    span, the entry count, the opened-Nd-ago clause or the truncation did.

    Deliberately NOT a catch-all. It matches only labels data_integrity declares,
    and it keeps EVERY slice named in the message, so a second slice going bad is
    a new identity and a new email rather than something swallowed by the first.
    """
    text = cause or ""
    if not text:
        return None
    invariants, slices = _live_data_vocabulary()
    invariant = next((label for label in invariants if label in text), None)
    if not invariant:
        return None
    named = sorted({label for label in slices if label in text})
    return " | ".join([invariant] + named) if named else invariant


#: The two steps a workflow uses to say whether the live-data invariants really
#: were evaluated in this run. Exactly one of them runs.
#:
#: TWO steps rather than one step read as success-or-skipped, deliberately: a
#: skipped step is reported by the jobs API today, and a channel whose "no"
#: state is an ABSENCE degrades to the old behaviour the moment that changes.
#: Both states are therefore something that positively ran. Pinned to
#: .github/workflows/tests.yml by tests/test_ci_alert.py, because a rename on
#: either side would silently return RECOVERED to being mailed on no evidence.
LIVE_DATA_STEP = "Live-data invariants were evaluated"
LIVE_DATA_STEP_UNKNOWN = "Live-data invariants were NOT evaluated"


def live_data_was_evaluated(repo, run_id):
    """True / False / None — did this run actually check the live numbers?

    None means the run publishes no verdict at all, which is every workflow that
    does not read the live site, and those keep today's behaviour. False is the
    case worth the code: a green run of a workflow that DOES check, in which the
    checks skipped.

    THE INCIDENT. 2026-08-13/14, three emails about one wrong number in 33
    minutes: RED at 23:37 (`tests:live.data:2e215caae5bac21b`), RECOVERED at
    00:03, RED again at 00:10 under the SAME key. The branch-free scope was
    working perfectly — main and fix/reader-freshness-content produced the
    identical key, which is what it was built for. What re-armed the alarm was
    the green run in between: run 31755860626, in which every live check read
    `skipped 'site is in its deploy maintenance window (HTTP 503)'`. Nothing had
    recovered; nobody had looked.

    One `gh api` call, the same one `fetch_annotations` already makes. Never
    raises: this runs on the notification path.
    """
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/runs/{run_id}/jobs",
             "-q", ".jobs[].steps[] | \"\\(.conclusion)\\t\\(.name)\""],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"could not read the run's steps ({exc}): live-data verdict UNKNOWN")
        return None
    if proc.returncode != 0:
        print(f"gh api jobs exited {proc.returncode}: {proc.stderr.strip()[:200]}")
        return None
    verdict = None
    for line in (proc.stdout or "").splitlines():
        conclusion, _, name = line.partition("\t")
        if conclusion.strip() != "success":
            continue
        if name.strip() == LIVE_DATA_STEP:
            return True
        if name.strip() == LIVE_DATA_STEP_UNKNOWN:
            verdict = False
    return verdict


def live_data_scope(workflow):
    """The branch-free scope live-data incidents are raised and cleared under.

    Still workflow-qualified: `/alert` clears by key PREFIX, and a green run of
    one workflow must not clear an alarm only another workflow can see.
    """
    return f"{_slug(workflow)}:{LIVE_DATA_SEGMENT}"


def extract_cause(raw_log, limit=400):
    """Pull the actual failing assertion out of a failed run's log.

    Returns (cause, context) where `cause` is the single most specific line and
    `context` is up to a handful of supporting lines.

    `limit` defaults to 400 because two other readers print this string
    verbatim (ops_status.py section [4], ci_noise_report's email) and a
    700-character line wrecks both. The ALERTER passes a wider one: its
    fingerprint has to see the whole sentence, and 400 characters is exactly
    where the sticky-incident prefix moved the cut and gave one open incident a
    second identity. Widening the default would have quietly reformatted two
    surfaces to fix a third. `cause` is what gets
    fingerprinted and what leads the subject line, because the Spirit failure
    carried its own diagnosis in the message and that sentence — not "a job
    failed" — is the entire reason the email is worth opening.
    """
    lines = [strip_prefix(ln) for ln in (raw_log or "").splitlines()]

    # Everything after the first generic "Process completed with exit code N" is
    # runner teardown (git config, orphan cleanup) and never diagnostic. The
    # real output is the last thing before it.
    cut = len(lines)
    for i, ln in enumerate(lines):
        body = _ANNOTATION.sub(r"\1", ln).strip()
        if _GENERIC_ERROR.match(body):
            cut = i
            break
    body_lines = [ln for ln in lines[:cut] if ln.strip()]

    annotations, exceptions, pytest_detail, test_heads, loose = [], [], [], [], []
    for ln in body_lines:
        stripped = ln.strip()
        m = _ANNOTATION.match(stripped)
        if m and m.group(1).strip() and not _GENERIC_ERROR.match(m.group(1).strip()):
            annotations.append(m.group(1).strip())
            continue
        if _PYTEST_DETAIL.match(stripped):
            pytest_detail.append(_PYTEST_DETAIL.match(stripped).group(1).strip())
            continue
        if _PYTEST_SUMMARY.match(stripped) or _UNITTEST_HEAD.match(stripped):
            test_heads.append(stripped)
            continue
        if _PY_EXCEPTION.match(stripped):
            exceptions.append(stripped)
            continue
        if _LOOSE_ERROR.search(stripped):
            loose.append(stripped)

    # Most specific wins. A traceback's LAST exception line is the one that
    # actually stopped the run; earlier ones are usually chained or captured.
    for bucket in (exceptions, pytest_detail, annotations, test_heads, loose):
        if bucket:
            cause = bucket[-1]
            break
    else:
        # No recognisable error shape. The last real output line still beats
        # "a job failed", and saying so honestly beats inventing a diagnosis.
        cause = body_lines[-1].strip() if body_lines else ""

    context = []
    for bucket in (test_heads, exceptions, pytest_detail, annotations):
        for ln in bucket[-3:]:
            if ln != cause and ln not in context:
                context.append(ln)
    return cause[:limit], context[:5]


def fetch_failed_log(repo, run_id):
    """`gh run view --log-failed` — only the failed steps, so it stays small.

    Returns "" (never raises) when gh is missing, unauthenticated, or the logs
    have expired. A missing log must degrade the email's detail, never suppress
    the email: knowing a workflow is red is already more than the owner had.
    """
    try:
        proc = subprocess.run(
            ["gh", "run", "view", str(run_id), "-R", repo, "--log-failed"],
            capture_output=True, text=True, timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"could not read the failed log ({exc}): alerting without the cause line")
        return ""
    if proc.returncode != 0:
        print(f"gh run view exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout or ""


def build_alert(*, repo, workflow, branch, event, run_url, run_id, cause,
                context, label="CI RED"):
    """Compose the email and the cause key it is deduped on.

    `label` names the CLASS of red in the subject. The scope is unchanged
    across classes on purpose: a self-timeout and an assertion failure in the
    same workflow both clear on that workflow's next green run, so the resolve
    path needs no new vocabulary. The cause fingerprint keeps them distinct
    emails.
    """
    # The display line is cut; the identity is not. See extract_cause.
    headline = (cause or "")[:400] or "no error line could be extracted from the log"

    identity = live_data_identity(cause)
    if identity:
        # One live number is wrong. Every branch is reading the same one, so
        # the branch that noticed drops out of the key entirely.
        scope = live_data_scope(workflow)
        fingerprint = hashlib.md5(
            f"{scope}\n{identity}".encode("utf-8")).hexdigest()[:16]
    else:
        scope = f"{_slug(workflow)}:{_slug(branch, 32)}"
        fingerprint = hashlib.md5(
            f"{scope}\n{normalise(headline)}".encode("utf-8")).hexdigest()[:16]
    dedupe_key = f"{scope}:{fingerprint}"
    subject = f"{label}: {workflow} — {headline}"[:180]

    lines = [
        f"The workflow '{workflow}' failed on GitHub Actions and nothing else would "
        "have told you.\n",
        f"  repo:     {repo}",
        f"  workflow: {workflow}",
        f"  branch:   {branch}",
        f"  trigger:  {event}",
        f"  run:      {run_url}",
        "",
        "WHAT FAILED:",
        f"  {headline}",
    ]
    if context:
        lines.append("")
        lines.append("Context from the failed step:")
        lines.extend(f"  {c}" for c in context)
    if not cause:
        lines.append("")
        lines.append(
            "No assertion or error line could be read out of this run's log (the log may "
            "have expired, or the job died before producing one). Open the run URL. This "
            "email is telling you the truth it has, not guessing at one.")
    lines.append(
        "\nWhat to do: open a Claude Code session in the ai-layoff-tracker repo and paste "
        "this line:\n"
        f'  "The GitHub Actions workflow \'{workflow}\' is failing on {branch} with: '
        f'{headline}. The run is {run_url}. Reproduce it locally, find the root cause, '
        'and fix it."\n')
    lines.append(
        "You will get ONE more email about this workflow: a RECOVERED notice on its next "
        "green run. We suppress repeats of this same failure on purpose. An alarm that "
        "mails eight times in an afternoon is one you learn to filter. A filtered alarm "
        "is how this defect stayed live for hours in the first place.")
    return subject, "\n".join(lines), dedupe_key


#: A shared host under load answers 5xx, and a proxy in front of a dead origin
#: answers 502/503/504. Those are worth asking about again in a few seconds.
#: 401/403 (wrong key) and 404 (route not deployed) are not: retrying a settled
#: "no" only makes the run longer, and both are held for a human either way.
_TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}

#: Seconds between in-run retries. Three attempts over ~15 seconds catches the
#: single bad response and the brief wobble, which is most of what this host
#: produces. It deliberately does NOT try to outlast an outage: the 2026-07-31
#: window was seven minutes and a job has ten. Outlasting is the outbox's job.
_BACKOFF = (3, 12)


def _post_once(site, key, payload):
    """One POST. Returns (ok, description, transient)."""
    req = urllib.request.Request(
        f"{site.rstrip('/')}/wp-json/layoffs/v1/alert",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Layoff-API-Key": key,
                 "User-Agent": UA},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300] if exc.fp else ""
        return False, f"HTTP {exc.code} from /alert: {detail}", exc.code in _TRANSIENT_STATUS
    except urllib.error.URLError as exc:
        # DNS, TCP, TLS, timeout: the host is not answering at all. Always
        # transient — there is nothing here for a human to fix in this repo.
        return False, f"could not reach /alert: {exc.reason}", True
    except Exception as exc:
        return False, f"could not reach /alert: {exc}", True
    if body.get("sent"):
        return True, "emailed the owner", False
    return True, f"not emailed: {body.get('reason', 'the endpoint reported no send')}", False


def post_alert(site, key, payload, sleep=time.sleep):
    """POST to the plugin's keyed /alert, retrying transient failures.

    Returns (ok, description, transient). `transient` tells the caller whether
    this looked like a host outage (hold it quietly, do not go red) or a settled
    refusal like a bad key (hold it, and be loud about it).
    """
    ok, note, transient = _post_once(site, key, payload)
    for delay in _BACKOFF:
        if ok or not transient:
            break
        print(f"  /alert did not answer ({note}): retrying in {delay}s")
        sleep(delay)
        ok, note, transient = _post_once(site, key, payload)
    return ok, note, transient


def write_envelope(path, *, key, kind, scope, payload, reason, run_url):
    """Park an undeliverable alert where the workflow can commit it.

    Writing the envelope and folding it into railway/alert_outbox.json are two
    steps because the commit has to survive a racing push: the workflow loops
    fetch -> reset -> `alert_outbox.py enqueue --envelope` -> commit -> push, and
    `enqueue` is idempotent in `key`, so a race costs a retry, never a duplicate
    email.
    """
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"key": key, "kind": kind, "scope": scope,
                       "payload": payload, "reason": reason,
                       "run_url": run_url}, fh, indent=2, sort_keys=True)
    except OSError as exc:
        print(f"::error::could not write the alert envelope to {path}: {exc}")
        return False
    return True


def hold(*, envelope, key, kind, scope, payload, note, transient, run_url):
    """The undeliverable path, in one place so both kinds behave identically.

    Returns the process exit code. It is 0 when the alert is safely held, and
    that is the fix for the amplification loop rather than an oversight.
    """
    if not envelope:
        print("::error::the alert could not be delivered and there is nowhere to "
              "hold it (no ALERT_ENVELOPE path was given), so nobody will be told "
              f"about this failure at all. Delivery said: {note}")
        return 1

    if not write_envelope(envelope, key=key, kind=kind, scope=scope,
                          payload=payload, reason=note, run_url=run_url):
        print("::error::the alert could not be delivered AND could not be held. "
              f"Nobody will be told about this failure. Delivery said: {note}")
        return 1

    # Loud, but not red. A session reading this log must be able to tell "the
    # host was down and we kept the alert" from "the alerter is broken".
    if transient:
        print(f"::warning::/alert is unreachable ({note}). The alert is HELD in "
              "railway/alert_outbox.json and will be delivered by the next "
              "alert-drain run that reaches the host. This run is NOT failing: "
              "an outage must not manufacture red runs on top of the ones it "
              "caused.")
    else:
        print(f"::error::/alert refused this alert and it is not a transient "
              f"failure: {note}. It is HELD in railway/alert_outbox.json, but a "
              "settled refusal will not fix itself: check WP_API_KEY and that "
              "the plugin carrying /alert is deployed. ops_status.py escalates "
              "a held alert that keeps failing.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--conclusion", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--event", default="unknown")
    ap.add_argument("--run-url", default="")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "dk-forge/ai-layoff-tracker"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the alert instead of posting it")
    ap.add_argument("--envelope", default=os.environ.get("ALERT_ENVELOPE", ""),
                    help="where to park an undeliverable alert for the workflow "
                         "to commit into railway/alert_outbox.json")
    args = ap.parse_args(argv)

    conclusion = (args.conclusion or "").lower()
    scope = f"{_slug(args.workflow)}:{_slug(args.branch, 32)}"

    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")

    if conclusion == "success":
        # Recovery. The endpoint mails exactly once IF something was open for
        # each scope, and stays silent otherwise — so this is cheap to post on
        # every green run and cannot itself become noise.
        #
        # TWO scopes, because a live-data incident is raised under a branch-free
        # one (see live_data_identity). Both are posted from every green run of
        # this workflow: whichever one has nothing open answers "nothing was
        # open for this scope" and sends no mail. Leaving the second one out is
        # how a closed incident would keep its alarm open and earn a STILL
        # FAILING reminder a fortnight later.
        scopes = [scope, live_data_scope(args.workflow)]
        # ...unless this run did not actually look. A live check that SKIPPED is
        # UNKNOWN, and clearing an incident on an UNKNOWN is how the owner was
        # mailed RECOVERED at 00:03 on 2026-08-14 for a number every check in
        # that run had declined to read, and RED again at 00:10. The branch
        # scope stays: whatever failed in this checkout really is green again.
        # `--dry-run` makes no API calls at all, here or anywhere else, so the
        # offline unit suite can drive this path without reaching a runner.
        evaluated = None if args.dry_run else live_data_was_evaluated(
            args.repo, args.run_id)
        if evaluated is False:
            print(f"not clearing {live_data_scope(args.workflow)}: the live-data "
                  f"invariants did not run in this run (they skipped), so this "
                  f"green run is UNKNOWN about the live numbers, not a pass. The "
                  f"next run that evaluates them clears it.")
            scopes = [scope]
        if args.dry_run or not (site and key):
            print(f"[dry-run] resolve scopes={scopes}")
            return 0
        for sc in scopes:
            payload = {"resolve_scope": sc,
                       "subject": f"RECOVERED: {args.workflow} is green again",
                       "body": (f"'{args.workflow}' on {args.branch} passed again.\n\n"
                                f"  run: {args.run_url}\n\n"
                                "Whatever was failing is no longer failing. Nothing to do.")}
            ok, note, transient = post_alert(site, key, payload)
            print(f"resolve {sc}: {note}")
            if not ok:
                # Held like any other alert. Holding a RESOLVE is what lets the
                # outbox cancel a RED for the same scope that never went out: if
                # both were raised during one outage, the owner hears about
                # neither, because neither was still true by the time anyone could
                # have read it. See alert_outbox.enqueue.
                #
                # And STOP after holding one. There is exactly ONE envelope
                # path and ci-alert.yml commits exactly one, so a second hold
                # would overwrite the first and lose the alert we were in the
                # middle of saving. A failure here means the host is not
                # answering, so the next scope would fail too, and the next
                # green run reposts it.
                remaining = scopes[scopes.index(sc) + 1:]
                if remaining:
                    print(f"not attempting resolve scope(s) {remaining}: the host "
                          f"is not answering, and there is one envelope to hold. "
                          f"The next green run of this workflow reposts them")
                return hold(envelope=args.envelope, key=f"resolve:{sc}",
                            kind="resolve", scope=sc, payload=payload,
                            note=note, transient=transient, run_url=args.run_url)
        return 0

    label = "CI RED"
    if conclusion == "cancelled":
        # See _SELF_TIMEOUT. A cancelled run is silent UNLESS it killed itself,
        # in which case nothing outside the job cancelled it: it ran past a
        # wall this repository set, and on a schedule that is permanent and
        # was, until now, completely silent.
        timeout_cause = self_timeout_of_run(args.repo, args.run_id)
        if not timeout_cause:
            print("cancelled by something outside the job (superseded push, "
                  "concurrency group, or a human): deliberately not alertable")
            return 0
        label = "CI SELF-TIMEOUT"
        cause, context = timeout_cause, [
            "The job was not cancelled by a push or a concurrency group. It ran "
            "past its own `timeout-minutes` and the runner killed it.",
            "GitHub reports this as `cancelled`, not `timed_out`, which is why "
            "it produced no email before now.",
            "Raise the ceiling with the measured reason written down, or make "
            "the job fit inside it. Do not simply retry.",
        ]
    elif conclusion not in ALERTABLE:
        print(f"conclusion '{conclusion}' is not alertable, nothing to do")
        return 0
    else:
        # ALERT_CAUSE_LIMIT, not the default 400: see extract_cause.
        cause, context = extract_cause(fetch_failed_log(args.repo, args.run_id),
                                       limit=ALERT_CAUSE_LIMIT)

    subject, body, dedupe_key = build_alert(
        repo=args.repo, workflow=args.workflow, branch=args.branch, event=args.event,
        run_url=args.run_url, run_id=args.run_id, cause=cause, context=context,
        label=label)

    print(f"cause:      {cause or '(none extracted)'}")
    print(f"normalised: {normalise(cause)}")
    print(f"dedupe_key: {dedupe_key}")

    if args.dry_run:
        print("--- subject ---")
        print(subject)
        print("--- body ---")
        print(body)
        return 0

    if not (site and key):
        # Loud, and non-zero. A silent "no credentials so I did nothing" is the
        # same class of lie as a green run over destroyed work.
        print("::error::WP_SITE_URL / WP_API_KEY are not set. The CI alert was NOT sent.")
        return 1

    payload = {"subject": subject, "body": body, "dedupe_key": dedupe_key}
    ok, note, transient = post_alert(site, key, payload)
    print(f"alert {dedupe_key}: {note}")
    if not ok:
        return hold(envelope=args.envelope, key=dedupe_key, kind="alert",
                    scope=scope, payload=payload, note=note,
                    transient=transient, run_url=args.run_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
