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
        print(f"  /alert did not answer ({note}) — retrying in {delay}s")
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
              "settled refusal will not fix itself — check WP_API_KEY and that "
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
        ok, note, transient = post_alert(site, key, payload)
        print(f"resolve {scope}: {note}")
        if not ok:
            # Held like any other alert. Holding a RESOLVE is what lets the
            # outbox cancel a RED for the same scope that never went out: if
            # both were raised during one outage, the owner hears about
            # neither, because neither was still true by the time anyone could
            # have read it. See alert_outbox.enqueue.
            return hold(envelope=args.envelope, key=f"resolve:{scope}",
                        kind="resolve", scope=scope, payload=payload,
                        note=note, transient=transient, run_url=args.run_url)
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
