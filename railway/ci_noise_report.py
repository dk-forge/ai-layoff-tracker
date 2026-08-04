#!/usr/bin/env python3
"""Weekly CI-noise report: one email naming the causes, or no email at all.

WHY. The per-failure alerting (ci_alert.py) is deduped by cause, so a broken
thing emails once — but nothing was watching the SHAPE of the week: runs that
went red again for a cause already reported, or runs that ended `cancelled`
having created zero jobs (a concurrency slot displacing work with no record
anywhere in the UI). In the sibling tracker one unhandled queue item produced
180 red runs in a week, each one a GitHub failure notification in the owner's
inbox, after every per-run alarm was already deduplicated. The week's run
list is the only vantage point that shows that class of noise, so once a week
this reads it and mails ONE line naming the causes — and on a quiet week it
mails NOTHING, which is the point: the owner's inbox is quiet exactly when
nothing needs him.

WHAT THIS NEVER DOES: silence anything. Category-(a) failures — a real
breakage that reddened once and alerted once — count ZERO here. This is a
regression alarm over the structural fixes, not a softer exit code for
anything.

Causes are read with ci_alert.extract_cause — the same extractor the alert
email uses, so both name one failure one way. Reading a log costs one gh call
per failed run, capped by --max-logs; runs beyond the cap group per workflow
as "(cause not read)" rather than pretending to match across workflows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ci_alert

#: Conclusions that count as failures — the same set ci_alert reacts to.
FAILED = frozenset({"failure", "timed_out", "startup_failure"})

#: Placeholder cause for failed runs past the --max-logs cap. Grouped per
#: WORKFLOW, never across workflows: two unread causes in one workflow are
#: plausibly one fact; across two workflows they are plausibly two.
UNREAD = "(cause not read)"

_FIELDS = "databaseId,workflowName,status,conclusion,createdAt,event"

_UNAVAILABLE = re.compile(
    r"gh auth login|not logged in|authentication|bad credentials|HTTP 401"
    r"|could not resolve host|no such host|network is unreachable"
    r"|connection refused|timed? ?out|timeout",
    re.I,
)


class GhUnavailable(RuntimeError):
    """gh could not answer at all. 'I could not check' must never exit like
    'the week was quiet' — the caller exits 3, the UNKNOWN code."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _gh(args: list[str]) -> str:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise GhUnavailable("the GitHub CLI (gh) is not installed") from None
    if result.returncode != 0:
        err = result.stderr.strip()
        if _UNAVAILABLE.search(err):
            raise GhUnavailable(f"gh {' '.join(args[:2])} failed: {err}")
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {err}")
    return result.stdout


def fetch_runs(repo: str, limit: int) -> list[dict]:
    return json.loads(_gh(["run", "list", "-R", repo, "-L", str(limit),
                           "--json", _FIELDS]))


def attach_job_counts(runs: list[dict], repo: str) -> list[dict]:
    """Fill in `job_count` on cancelled runs only — zero jobs is the eviction
    fingerprint, and only cancelled runs can carry it."""
    for run in runs:
        if run.get("conclusion") != "cancelled":
            continue
        raw = _gh(["api", f"repos/{repo}/actions/runs/{run['databaseId']}/jobs",
                   "--jq", ".total_count"])
        try:
            run["job_count"] = int(raw.strip())
        except ValueError:
            run["job_count"] = None  # unknown is not zero
    return runs


def classify(runs: list[dict], causes: dict[str, str],
             since: datetime) -> dict:
    """The week's run list -> noise, as plain data. Pure and offline.

    `causes` maps run id (str) -> extracted cause for whichever failed runs
    the caller could afford to read; missing ids group as UNREAD.
    """
    recent = []
    for run in runs:
        created = run.get("createdAt") or ""
        try:
            when = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
        if when >= since and run.get("status") == "completed":
            recent.append(run)

    groups: Counter = Counter()
    for run in recent:
        if run.get("conclusion") not in FAILED:
            continue
        cause = causes.get(str(run.get("databaseId")), "").strip()
        label = ci_alert.normalise(cause) if cause else UNREAD
        groups[(run.get("workflowName") or "?", label)] += 1

    evictions = [run for run in recent
                 if run.get("conclusion") == "cancelled"
                 and run.get("job_count") == 0]

    repeats = sum(n - 1 for n in groups.values())
    return {
        "window_runs": len(recent),
        "failed_runs": sum(groups.values()),
        "causes": sorted(((wf, cause, n) for (wf, cause), n in groups.items()),
                         key=lambda item: -item[2]),
        "repeats": repeats,
        "evictions": [{"run_id": str(r.get("databaseId")),
                       "workflow": r.get("workflowName"),
                       "event": r.get("event"),
                       "created_at": r.get("createdAt")} for r in evictions],
        "noise": repeats + len(evictions),
    }


def compose(result: dict, *, repo: str, days: int,
            now: datetime | None = None) -> tuple[str, str, str]:
    """-> (subject, body, dedupe_key). Only called when noise > 0."""
    moment = now or _now()
    # LOWERCASE `w`, and it is load-bearing. The ISO-week token goes into the
    # dedupe key, and /alert accepts `^[a-z0-9][a-z0-9:._-]{0,159}$` — an
    # uppercase W is a SETTLED 400, not a retryable one, so the report is held,
    # retried to exhaustion, and finally `stuck`, which reddens the drainer
    # forever and buries a real outage under a permanent red. The sibling paid
    # for this on 2026-08-03. Asserted against ci_alert.KEY_SAFE in
    # railway/tests/test_ci_noise_report.py.
    week = moment.strftime("%G-w%V")
    subject = (f"CI noise, week {week}: {result['noise']} noisy run(s) "
               f"in {repo.split('/')[-1]}")
    lines = [
        f"Last {days} days in {repo}: {result['window_runs']} completed runs, "
        f"{result['failed_runs']} failed across {len(result['causes'])} "
        f"cause(s), {result['repeats']} repeat red(s), "
        f"{len(result['evictions'])} zero-job eviction(s).",
        "",
        "A repeat red is a run that went red for a cause an earlier run",
        "already reported. The first red of each cause is signal, was",
        "already emailed once by the CI alerter, and is not counted here.",
        "",
    ]
    for wf, cause, n in result["causes"]:
        note = "reported once, correctly" if n == 1 else f"{n - 1} repeat red(s)"
        lines.append(f"  {wf}: {n} run(s) — {note}")
        lines.append(f"      cause: {cause}")
    if result["evictions"]:
        lines.append("")
        lines.append("Zero-job cancelled runs (a concurrency slot displaced "
                     "them; the UI shows nothing):")
        for orphan in result["evictions"]:
            lines.append(f"  {orphan['workflow']} run {orphan['run_id']} "
                         f"({orphan['event']}, {orphan['created_at']})")
    lines.append("")
    lines.append("Noise means a structural fix regressed or is missing; the fix")
    lines.append("is never to silence the run or soften an exit code.")
    # The week is part of the key so next week's report is a NEW cause to the
    # endpoint rather than a suppressed repeat of an open one.
    return subject, "\n".join(lines), f"ci-noise:{week}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--limit", type=int, default=400,
                    help="how many runs to read from gh")
    ap.add_argument("--max-logs", type=int, default=25,
                    help="failed-run logs to read for causes; the rest group "
                         "as unread rather than pretending to match")
    ap.add_argument("--repo", default=os.environ.get(
        "GITHUB_REPOSITORY", "dk-forge/ai-layoff-tracker"))
    ap.add_argument("--dry-run", action="store_true",
                    help="print the report; post nothing")
    args = ap.parse_args(argv)

    try:
        runs = fetch_runs(args.repo, args.limit)
        attach_job_counts(runs, args.repo)
    except GhUnavailable as exc:
        print(f"::error::could not read the run list at all: {exc}")
        return 3

    since = _now() - timedelta(days=args.days)
    failed_ids = [str(r.get("databaseId")) for r in runs
                  if r.get("conclusion") in FAILED]
    causes: dict[str, str] = {}
    for run_id in failed_ids[:args.max_logs]:
        cause, _context = ci_alert.extract_cause(
            ci_alert.fetch_failed_log(args.repo, run_id))
        if cause:
            causes[run_id] = cause

    result = classify(runs, causes, since)
    subject, body, dedupe_key = compose(result, repo=args.repo, days=args.days)

    print(f"window: {result['window_runs']} completed runs / {args.days} days")
    print(f"failed: {result['failed_runs']}  repeats: {result['repeats']}  "
          f"evictions: {len(result['evictions'])}  noise: {result['noise']}")

    if result["noise"] == 0:
        print("quiet week: no repeat reds, no evictions — nothing to send, "
              "and that silence is the product working.")
        return 0

    print("--- subject ---")
    print(subject)
    print("--- body ---")
    print(body)
    if args.dry_run:
        return 0

    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        print("::error::WP_SITE_URL / WP_API_KEY are not set — the noise "
              "report was NOT sent.")
        return 1

    payload = {"subject": subject, "body": body, "dedupe_key": dedupe_key}
    ok, note, transient = ci_alert.post_alert(site, key, payload)
    print(f"noise report {dedupe_key}: {note}")
    if ok:
        return 0
    return ci_alert.hold(envelope=os.environ.get("ALERT_ENVELOPE", ""),
                         key=dedupe_key, kind="alert", scope="ci-noise",
                         payload=payload, note=note, transient=transient,
                         run_url="")


if __name__ == "__main__":
    sys.exit(main())
