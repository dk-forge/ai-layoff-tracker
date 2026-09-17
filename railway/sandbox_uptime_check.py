#!/usr/bin/env python3
"""Sandbox crash check that runs on time for free.

WHY THIS EXISTS. The private sandbox repo's own `uptime-cert-monitor.yml`
runs on the single busy self-hosted runner shared by three repositories and
has been getting to run only every 2-3 hours instead of its intended
cadence. This repo is public, so GitHub-hosted `ubuntu-latest` runners are
free and unmetered here, and this check needs nothing the sandbox repo has
that this one does not: three unauthenticated GET requests and this repo's
own mail door.

WHAT IT CHECKS. Three URLs:
  - https://sandbox.asktherecruiter.com/healthz         (200)
  - https://sandbox.asktherecruiter.com/healthz/deep     (200, every check
    inside the body reports ok:true)
  - https://asktherecruiter-sandbox-production.up.railway.app/  (200, the
    Railway origin directly, bypassing the custom-domain/DNS hop so a DNS
    or proxy failure and an application failure read as two different
    causes rather than one "sandbox is down")

DEDUPE, THE SAME SHAPE AS EVERY OTHER ALARM HERE. A cause is its OWN
committed ledger (`railway/sandbox_uptime_state.json`), built with
`alert_state.py` exactly as `new_error_watch.py` uses it for Sentry: raise
once, remind at 14 days, resolve once. A CI cause and a Sentry cause and a
sandbox-uptime cause each get their own namespace on purpose - see
`new_error_watch.py`'s docstring for why sharing one ledger across kinds of
cause is a bug waiting to collide.

WHY TWO CONSECUTIVE FAILURES, NOT ONE. This job runs every 15 minutes. A
single failed run is exactly as likely to be a transient network blip
between two GitHub-hosted runners and a Railway origin as a real outage,
and alerting on every blip is how an alert channel earns a filter (see
CLAUDE.md, the eight-identical-emails lesson). Two consecutive failures
(a real window of at least ~15 minutes) is the same bar `source_freshness`
and `host_call`'s deferral ledger use elsewhere in this repo: quiet and
broken are different states, and this job's whole job is not to confuse
them.

The counter is stored on the SAME ledger file the alarm ledger lives in
(alert_state.py preserves any extra top-level key across load/save), so
there is exactly one committed file for this whole check.

WHY THIS JOB NEVER GOES RED ON A FAILED CHECK. This check's entire purpose
is the alarm; asserting on itself and ALSO tripping ci-alert.yml on top
would be two alarms for one cause, exactly what alert_state.py exists to
prevent. Same shape as `host-watch.yml` in the sibling repo: a probe that
finds an outage reports it through the one door and keeps running on
schedule.

Stdlib only. This is the notification path and no dependency resolution
failure may take it down, the same rule as ci_alert.py, opsmail.py and
new_error_watch.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alert_state  # noqa: E402
import ops_notify  # noqa: E402

ROOT = Path(__file__).resolve().parent

#: Own ledger, own namespace - see module docstring.
STATE_PATH = ROOT / "sandbox_uptime_state.json"

CAUSE_KEY = "sandbox-uptime:down"

HEALTHZ_URL = "https://sandbox.asktherecruiter.com/healthz"
DEEP_URL = "https://sandbox.asktherecruiter.com/healthz/deep"
RAILWAY_ORIGIN_URL = "https://asktherecruiter-sandbox-production.up.railway.app/"

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: A real outage two runs running is the bar; see module docstring.
CONSECUTIVE_FAILS_TO_ALERT = 2


def _http_get(url: str, timeout: int = 15):
    """One GET. Returns (status, text). Never raises for an HTTP error
    status (translated to a normal return), only for a transport failure."""
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                "Accept": "application/json, */*"},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - best-effort diagnostics only
            body = ""
        return exc.code, body


def _find_not_ok(node, path: str = "") -> list[str]:
    """Walk a parsed JSON body and collect every path whose "ok" key is not
    exactly True. A deep-health body nests its checks arbitrarily; this does
    not assume a shape beyond "look for ok:false anywhere"."""
    hits = []
    if isinstance(node, dict):
        if "ok" in node and node["ok"] is not True:
            hits.append(path or "(root)")
        for key, value in node.items():
            hits.extend(_find_not_ok(value, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            hits.extend(_find_not_ok(value, f"{path}[{i}]"))
    return hits


def check_all(fetch=None) -> tuple[bool, str]:
    """-> (ok, detail). `detail` is a short, name-free-enough diagnostic
    (endpoint + status/failing-check-paths) suitable for the alert body.
    `fetch` is injectable so tests never open a socket."""
    getter = fetch or _http_get
    problems = []

    try:
        status, _body = getter(HEALTHZ_URL)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        problems.append(f"{HEALTHZ_URL}: could not reach it ({exc})")
    else:
        if status != 200:
            problems.append(f"{HEALTHZ_URL}: HTTP {status}")

    try:
        status, body = getter(DEEP_URL)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        problems.append(f"{DEEP_URL}: could not reach it ({exc})")
    else:
        if status != 200:
            problems.append(f"{DEEP_URL}: HTTP {status}")
        else:
            try:
                parsed = json.loads(body or "{}")
            except ValueError:
                problems.append(f"{DEEP_URL}: response was not valid JSON")
            else:
                not_ok = _find_not_ok(parsed)
                if not_ok:
                    problems.append(f"{DEEP_URL}: check(s) not ok: "
                                    + ", ".join(sorted(not_ok)[:10]))

    try:
        status, _body = getter(RAILWAY_ORIGIN_URL)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        problems.append(f"{RAILWAY_ORIGIN_URL}: could not reach it ({exc})")
    else:
        if status != 200:
            problems.append(f"{RAILWAY_ORIGIN_URL}: HTTP {status}")

    if problems:
        return False, "; ".join(problems)
    return True, "ok"


def build_body(detail: str, consecutive: int) -> str:
    return (
        "The sandbox uptime check has now failed "
        f"{consecutive} runs in a row (checked every 15 minutes):\n\n"
        f"  {detail}\n\n"
        "This checks https://sandbox.asktherecruiter.com/healthz, "
        "/healthz/deep, and the Railway origin directly "
        "(asktherecruiter-sandbox-production.up.railway.app). It is a "
        "stand-in for the sandbox repo's own uptime-cert-monitor.yml, which "
        "has been running late on its shared self-hosted runner.\n\n"
        "You will get ONE more email about this cause: a note when it "
        "recovers. A repeat within 14 days is suppressed on purpose."
    )


def run(*, fetch=None, state_path: Path | str = STATE_PATH,
        now: int | None = None, notify=None) -> int:
    """-> exit code, always 0. This job's whole purpose is the alarm; see
    module docstring on why it never also reddens itself."""
    notify = notify or ops_notify.notify
    ok, detail = check_all(fetch=fetch)
    state = alert_state.load(state_path)

    if ok:
        state["consecutive_fails"] = 0
        decision = alert_state.decide(
            state,
            {"subject": "RECOVERED: sandbox uptime check",
             "body": "The sandbox uptime check is passing again "
                     "(healthz, healthz/deep and the Railway origin all "
                     "answered ok).",
             "resolve_scope": CAUSE_KEY},
            now=now)
        if decision.kind == "resolve":
            if notify(decision.subject, decision.body):
                alert_state.apply(state, decision, now=now)
                print("sandbox_uptime_check: ok, RECOVERED sent")
            else:
                print("sandbox_uptime_check: ok, RECOVERED NOT sent "
                      "(cause stays open, next run retries)")
        else:
            print("sandbox_uptime_check: ok")
    else:
        streak = int(state.get("consecutive_fails", 0)) + 1
        state["consecutive_fails"] = streak
        print(f"sandbox_uptime_check: FAIL ({detail}); consecutive={streak}")
        if streak >= CONSECUTIVE_FAILS_TO_ALERT:
            subject = f"sandbox uptime check failing: {detail}"[:180]
            decision = alert_state.decide(
                state,
                {"subject": subject, "body": build_body(detail, streak),
                 "dedupe_key": CAUSE_KEY},
                now=now)
            if decision.kind == "raise":
                if notify(decision.subject, decision.body):
                    alert_state.apply(state, decision, now=now)
                    print(f"sandbox_uptime_check: {decision.subject}: sent")
                else:
                    print("sandbox_uptime_check: alert NOT sent, cause "
                          "stays new so the next run retries it")
            else:
                print(f"sandbox_uptime_check: {decision.note or decision.kind}")
        else:
            print("sandbox_uptime_check: one failure is not yet a streak "
                  f"({streak}/{CONSECUTIVE_FAILS_TO_ALERT}), not alerting")

    alert_state.save(state, state_path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
