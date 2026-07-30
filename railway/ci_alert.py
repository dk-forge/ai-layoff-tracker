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

Exit codes: 0 = handled (mailed, suppressed, or nothing to do)
            1 = the alert POST itself failed. The run goes RED so the failure of
                the alerter is itself visible — including in ops_status.py [4].
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# ModSecurity on the WP host blocks python-requests outright; every request to
# asktherecruiter.com must look like a real client. (Iron rule, see CLAUDE.md.)
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# Conclusions worth an email. `cancelled` is deliberately NOT here: runs are
# cancelled routinely (superseded pushes, concurrency groups) and alerting on
# them is exactly the noise that gets a sender filtered.
ALERTABLE = {"failure", "timed_out", "startup_failure"}

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


def extract_cause(raw_log):
    """Pull the actual failing assertion out of a failed run's log.

    Returns (cause, context) where `cause` is the single most specific line and
    `context` is up to a handful of supporting lines. `cause` is what gets
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
    return cause[:400], context[:5]


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
        print(f"could not read the failed log ({exc}) — alerting without the cause line")
        return ""
    if proc.returncode != 0:
        print(f"gh run view exited {proc.returncode}: {proc.stderr.strip()[:300]}")
    return proc.stdout or ""


def build_alert(*, repo, workflow, branch, event, run_url, run_id, cause, context):
    """Compose the email and the cause key it is deduped on."""
    scope = f"{_slug(workflow)}:{_slug(branch, 32)}"
    fingerprint = hashlib.md5(
        f"{scope}\n{normalise(cause)}".encode("utf-8")).hexdigest()[:16]
    dedupe_key = f"{scope}:{fingerprint}"

    headline = cause or "no error line could be extracted from the log"
    subject = f"CI RED: {workflow} — {headline}"[:180]

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
            "have expired, or the job died before producing one). Open the run URL — this "
            "email is telling you the truth it has, not guessing at one.")
    lines.append(
        "\nWhat to do: open a Claude Code session in the ai-layoff-tracker repo and paste "
        "this line:\n"
        f'  "The GitHub Actions workflow \'{workflow}\' is failing on {branch} with: '
        f'{headline}. The run is {run_url}. Reproduce it locally, find the root cause, '
        'and fix it."\n')
    lines.append(
        "You will get ONE more email about this workflow: a RECOVERED notice on its next "
        "green run. Repeats of this same failure are suppressed deliberately — an alarm "
        "that mails eight times in an afternoon is one you learn to filter, and a filtered "
        "alarm is how this defect stayed live for hours in the first place.")
    return subject, "\n".join(lines), dedupe_key


def post_alert(site, key, payload):
    """POST to the plugin's keyed /alert. Returns (ok, description)."""
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
        return False, f"HTTP {exc.code} from /alert: {detail}"
    except Exception as exc:
        return False, f"could not reach /alert: {exc}"
    if body.get("sent"):
        return True, "emailed the owner"
    return True, f"not emailed: {body.get('reason', 'the endpoint reported no send')}"


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
    args = ap.parse_args(argv)

    conclusion = (args.conclusion or "").lower()
    scope = f"{_slug(args.workflow)}:{_slug(args.branch, 32)}"

    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")

    if conclusion == "success":
        # Recovery. The endpoint mails exactly once IF something was open for
        # this scope, and stays silent otherwise — so this is cheap to post on
        # every green run and cannot itself become noise.
        payload = {"resolve_scope": scope,
                   "subject": f"RECOVERED: {args.workflow} is green again",
                   "body": (f"'{args.workflow}' on {args.branch} passed again.\n\n"
                            f"  run: {args.run_url}\n\n"
                            "Whatever was failing is no longer failing. Nothing to do.")}
        if args.dry_run or not (site and key):
            print(f"[dry-run] resolve scope={scope}")
            return 0
        ok, note = post_alert(site, key, payload)
        print(f"resolve {scope}: {note}")
        if not ok:
            print(f"::error::CI recovery notice could not be delivered — {note}")
            return 1
        return 0

    if conclusion not in ALERTABLE:
        print(f"conclusion '{conclusion}' is not alertable — nothing to do")
        return 0

    cause, context = extract_cause(fetch_failed_log(args.repo, args.run_id))
    subject, body, dedupe_key = build_alert(
        repo=args.repo, workflow=args.workflow, branch=args.branch, event=args.event,
        run_url=args.run_url, run_id=args.run_id, cause=cause, context=context)

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
        print("::error::WP_SITE_URL / WP_API_KEY are not set — the CI alert was NOT sent.")
        return 1

    ok, note = post_alert(site, key, {"subject": subject, "body": body,
                                      "dedupe_key": dedupe_key})
    print(f"alert {dedupe_key}: {note}")
    if not ok:
        # This run going red is the point: it is a separate workflow from the one
        # that failed, so it can never mask the original failure, and ops_status
        # [4] will surface the alerter's own breakage at the next session start.
        print(f"::error::CI alert could not be delivered — {note}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
