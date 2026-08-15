#!/usr/bin/env python3
"""`curl --fail-with-body`, with the third outcome it never had.

WHAT THIS REPLACES AND WHY
--------------------------
Workflows that talk to the WordPress host used to run

    curl -sS --fail-with-body -X POST ... && python3 - <<'PY' ... PY

which resolves every call to two states: exit 0, or dead. On 2026-07-31
Bluehost 5xx'd under `/blog/` twice in one day, and this repo's `ops_status [4]`
still showed two workflows RED for it — "curl: (22) ... error: 504" and
"... error: 502". Neither had a defect. A red run then fires `ci_alert.py`,
which posts to `/alert`, a route ON THE HOST THAT IS DOWN: an outage
manufacturing red runs which manufacture alerts which also fail. `ci_alert.py`
was fixed by holding and exiting 0; this is the same fix for the callers.

THREE OUTCOMES
--------------
  ok        the host answered and gave us the body            -> exit 0, parse it
  DEFERRED  the host was never reached (transport error, or a
            transient status that survived every retry)       -> exit 0, count it
  failure   the host answered with something we do not accept
            (401/403/404, any non-transient status, or a 2xx
            body reporting its own failure)                   -> exit non-zero

The middle one is the new state, and the whole design risk. A deferral that
nobody counts is just a silently green job. So every deferral is written to
`railway/deferral_ledger.json` (committed, because the state is about the host
and cannot live on it), shown in `ops_status [4d]`, and the THIRD consecutive
deferral for a job exits non-zero — at that point the job is not waiting out an
outage, it is hiding behind one.

WHAT THIS DOES NOT DO
---------------------
It does not soften failure. `--fail-with-body` existed so a refusal could never
be read as a success, and that is preserved exactly: a wrong key, a missing
route and a 2xx body reporting a failed batch all still go red on the first
occurrence, because none of them gets better by waiting.

It also does not parse anything. A deferred call writes NO response file, and
the workflow's own parse step is gated on `outcome == 'ok'`, so each job keeps
its existing reporting (the superset job's bounded per-company rollup exists
because the Actions log uploader silently drops an over-long line) untouched.

Stdlib only for the CLI path: those workflows do no `pip install`. The Python
worker API below (`get_json` / `post_json`) is used by jobs that already install
`requests`, and only its GET half touches it.

THE SAME THREE OUTCOMES, FOR A PYTHON WORKER
--------------------------------------------
The CLI above resolves ONE call made by a workflow. The enrichment and backfill
workers make many calls interleaved with model work, so they cannot shell out
per call. They get `get_json` / `post_json`, which raise `Deferred` when the
host never answered and raise loudly on a settled refusal, plus `defer()` /
`clear()` — the same ledger bookkeeping `main()` does, factored out rather than
copied, because `http_retry.py` exists precisely because the last thing worth
having one of got re-derived by the next scan.

`Extract affected-role categories` died on 2026-08-12 with one 503 from
`/enrich-roles`, almost certainly WordPress in maintenance mode while an FTPS
deploy of this very repo landed. A worker that cannot survive its own deploy is
not fail-loud, it is just loud.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import deferral_ledger
import http_retry

#: Where the composite action `commit-deferral-ledger` looks by default. The
#: path is relative to the writer's CWD — workspace root for the CLI, railway/
#: for the workers behind `cd railway` — so the action probes BOTH this name
#: and railway/<this name>. A worker that records a deferral the workflow
#: never commits is a silently green job, so these defaults must agree
#: (railway/tests/test_job_deferrals.py holds them together).
DEFAULT_ENVELOPE = "deferral_envelope.json"


class Deferred(Exception):
    """The host never answered — not a pass, not a failure.

    Raised from deep inside a worker and caught at its top level, so the
    "did we get to ask?" question is answered in one place per job instead of
    at every call site.
    """


# --------------------------------------------------------------------------
# The ledger bookkeeping, shared by the CLI and the Python workers.
# --------------------------------------------------------------------------

def defer(job: str, reason: str, *, ledger=deferral_ledger.LEDGER,
          envelope: str = DEFAULT_ENVELOPE) -> int:
    """Record one deferral and return the process exit code.

    0 normally — a host that never answered is not a job that failed — and
    non-zero on the `ESCALATE_AFTER`th in a row, at which point the job is not
    waiting out an outage, it is hiding behind one.
    """
    doc = deferral_ledger.load(ledger)
    entry = deferral_ledger.record_deferral(doc, job=job, reason=reason,
                                            run_url=_run_url(), key=_run_key())
    deferral_ledger.save(doc, ledger)
    if envelope:
        deferral_ledger.write_envelope(envelope, job=job, state="deferred",
                                       reason=reason, run_url=_run_url(),
                                       key=_run_key())
    streak = entry.get("consecutive", 1)
    _github_output("outcome", "deferred")
    print(f"DEFERRED: {job} could not reach the host ({reason}).")
    print("This is NOT a pass. The next scheduled run retries. "
          f"Consecutive deferrals: {streak}.")
    if streak >= deferral_ledger.ESCALATE_AFTER:
        print(f"::error::{job} has now deferred {streak} times in a row. That is "
              "no longer an outage — the host is answering other jobs. See "
              "docs/RUNBOOK.md 'a job is DEFERRING'.")
        return 1
    print("Exiting 0: a host that never answered is not a job that failed. "
          "ops_status [4d] shows this until it clears.")
    return 0


def clear(job: str, *, ledger=deferral_ledger.LEDGER,
          envelope: str = DEFAULT_ENVELOPE) -> None:
    """Close any open deferral for `job`. Free when there is none: a healthy
    job touches no file, so `git log` on the ledger stays a list of outages."""
    doc = deferral_ledger.load(ledger)
    if not deferral_ledger.record_success(doc, job=job):
        return
    deferral_ledger.save(doc, ledger)
    if envelope:
        deferral_ledger.write_envelope(envelope, job=job, state="success",
                                       key=_run_key())
    print(f"{job}: the host is answering again — deferral cleared.")


# --------------------------------------------------------------------------
# The Python worker API.
# --------------------------------------------------------------------------

def get_json(url, *, params=None, headers=None, timeout=60):
    """GET our host, resolved to the same three outcomes.

    `Deferred` when every attempt died transiently; a settled refusal (403, a
    missing route) raises through `raise_for_status` exactly as it always did.
    """
    response = http_retry.get_with_retry(url, params=params, headers=headers,
                                         timeout=timeout)
    if response is None:
        raise Deferred(f"GET {url} never got an answer from the host")
    response.raise_for_status()
    return response.json()


def post_json(url, payload, *, headers=None, timeout=90):
    """POST JSON to our host, resolved to the same three outcomes.

    Deliberately NOT softer than `raise_for_status`: a non-transient status, and
    a 2xx body that reports its own failed rows, both raise. Only "we never got
    to ask" is new.
    """
    data, body_headers = http_retry.json_body(payload)
    sent = dict(body_headers)
    sent.update(headers or {})
    result = http_retry.call_with_retry(url, method="POST", data=data,
                                        headers=sent, timeout=timeout)
    if result.outcome == http_retry.DEFERRED:
        raise Deferred(f"POST {url}: {result.detail}")
    if result.outcome == http_retry.FAILURE:
        raise RuntimeError(f"POST {url}: {result.detail}")
    reason = http_retry.body_reports_failure(result.body)
    if reason:
        raise RuntimeError(f"POST {url}: {reason}")
    try:
        return json.loads(result.body or "{}")
    except ValueError:
        return {}


def _github_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")
    except OSError as exc:  # pragma: no cover - runner-only path
        print(f"could not write {name} to GITHUB_OUTPUT: {exc}")


def _run_key() -> str:
    """Identifies THIS run, so a re-record after a rejected push is a no-op.

    Empty off a runner: with no run id there is nothing to replay, and a
    constant "local" key would make every local invocation look like the same
    one and never advance the streak.
    """
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not run_id:
        return ""
    return f"{run_id}:{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"


def _run_url() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"https://github.com/{repo}/actions/runs/{run_id}" if repo and run_id else ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--job", required=True,
                    help="ledger key; use the workflow's file stem")
    ap.add_argument("--url", required=True)
    ap.add_argument("--method", default="POST", choices=["GET", "POST"])
    ap.add_argument("--form", action="append", default=[], metavar="K=V",
                    help="urlencoded form field (the --data-urlencode equivalent)")
    ap.add_argument("--header", action="append", default=[], metavar="K: V")
    ap.add_argument("--api-key-env", default="",
                    help="env var holding the value for X-Layoff-API-Key; the key "
                         "is never passed on the command line")
    ap.add_argument("--output", default="", help="write the response body here")
    ap.add_argument("--ledger", default=str(deferral_ledger.LEDGER))
    ap.add_argument("--envelope", default="",
                    help="write what was recorded here, so a rejected push can "
                         "re-derive it after resetting onto main")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--no-sleep", action="store_true", help="tests only")
    args = ap.parse_args(argv)

    headers = {}
    for raw in args.header:
        name, sep, value = raw.partition(":")
        if not sep:
            print(f"::error::--header must look like 'Name: value', got {raw!r}")
            return 2
        headers[name.strip()] = value.strip()
    if args.api_key_env:
        key = os.environ.get(args.api_key_env, "")
        if not key:
            # A missing key is a real, settled problem — never a deferral. It
            # would fail identically tomorrow, and pretending otherwise is how
            # a broken secret sits undiscovered for a week.
            print(f"::error::{args.api_key_env} is empty; refusing to call {args.url}")
            return 2
        headers["X-Layoff-API-Key"] = key

    data = None
    if args.form:
        pairs = []
        for raw in args.form:
            name, _sep, value = raw.partition("=")
            pairs.append((name, value))
        data, form_headers = http_retry.urlencode_form(pairs)
        headers.update(form_headers)

    out_path = Path(args.output) if args.output else None
    # A stale body from a previous run is worse than none: the parse step would
    # report yesterday's numbers as today's.
    if out_path and out_path.exists():
        out_path.unlink()

    result = http_retry.call_with_retry(
        args.url, method=args.method, data=data, headers=headers,
        timeout=args.timeout,
        sleep=(lambda _s: None) if args.no_sleep else time.sleep)

    if result.outcome == http_retry.DEFERRED:
        return defer(args.job, result.detail, ledger=args.ledger,
                     envelope=args.envelope)

    if result.outcome == http_retry.FAILURE:
        _github_output("outcome", "failure")
        print(f"::error::{args.job}: {result.detail}")
        return 1

    reason = http_retry.body_reports_failure(result.body)
    if reason:
        _github_output("outcome", "failure")
        print(f"::error::{args.job}: {reason}")
        return 1

    clear(args.job, ledger=args.ledger, envelope=args.envelope)
    if out_path:
        out_path.write_text(result.body)
    _github_output("outcome", "ok")
    print(f"{args.job}: HTTP {result.status} from the host.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
