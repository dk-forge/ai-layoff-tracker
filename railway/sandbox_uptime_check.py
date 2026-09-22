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

THE TLS CERT, TOO (2026-09-22). The sandbox repo's own probe also read the
public certificate's expiry with openssl and opened an issue under 14 days
of runway. On 2026-09-22 that probe's GitHub-hosted job was retired: a
private repo pays for every hosted minute and a six-second job is billed
as one, so 96 runs a day was the single largest line on the sandbox's
Actions bill (~350 of its 4,829 September minutes), for a check this free
job already made. Its VPS twin still runs there; THIS is now the copy that
does not depend on the VPS. So this check reads the certificate too, at
the TLS layer (no HTTP request, so Cloudflare does not stand in the way),
for the public site and the sandbox host. A certificate that cannot be
read is UNKNOWN: printed, never an alarm, never a pass, and never a
RECOVERED. Expiry is its own cause (`sandbox-uptime:cert`), because two
weeks of runway is a warning and not an outage, and it must not count
toward the outage streak or be silenced by it.

Stdlib only. This is the notification path and no dependency resolution
failure may take it down, the same rule as ci_alert.py, opsmail.py and
new_error_watch.py.
"""
from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
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

#: The certificates the retired hosted probe read, plus the sandbox's own.
CERT_HOSTS = ("asktherecruiter.com", "sandbox.asktherecruiter.com")
CERT_WARN_DAYS = 14
CERT_CAUSE_KEY = "sandbox-uptime:cert"


def _cert_not_after(host: str, timeout: int = 15) -> float:
    """The certificate's notAfter as a unix time, read at the TLS layer.
    Raises on any transport or handshake failure (the caller reads that
    as UNKNOWN)."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=timeout) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            cert = tls.getpeercert()
    not_after = (cert or {}).get("notAfter")
    if not not_after:
        raise ValueError("certificate carries no notAfter")
    return float(ssl.cert_time_to_seconds(not_after))


def check_certs(read_cert=None, now: float | None = None
                ) -> tuple[list[str], list[str], dict[str, int]]:
    """-> (expiring, unknown, days_left). `expiring` names hosts with fewer
    than CERT_WARN_DAYS of runway; `unknown` names hosts whose certificate
    could not be read (never a pass, never an alarm). `read_cert(host)`
    returns notAfter as a unix time; injectable so tests open no socket."""
    reader = read_cert or _cert_not_after
    now = time.time() if now is None else now
    expiring, unknown, days_left = [], [], {}
    for host in CERT_HOSTS:
        try:
            not_after = float(reader(host))
        except Exception as exc:  # noqa: BLE001 - any failure to read is UNKNOWN
            unknown.append(f"{host} ({type(exc).__name__}: {exc})")
            continue
        days = int((not_after - now) // 86400)
        days_left[host] = days
        if days < CERT_WARN_DAYS:
            expiring.append(f"{host} expires in {days} day(s)")
    return expiring, unknown, days_left


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
        "(asktherecruiter-sandbox-production.up.railway.app). It is the "
        "copy of the sandbox's backend probe that does not depend on the "
        "VPS: the sandbox repo's own uptime-cert-monitor.yml runs only on "
        "the VPS runner since 2026-09-22.\n\n"
        "You will get ONE more email about this cause: a note when it "
        "recovers. A repeat within 14 days is suppressed on purpose."
    )


def _run_cert_check(state: dict, *, read_cert, now, notify) -> None:
    """The certificate half. Own cause, no streak: expiry is not transient.
    UNKNOWN changes nothing in the ledger, in either direction."""
    expiring, unknown, days_left = check_certs(read_cert=read_cert,
                                               now=None if now is None else float(now))
    for host, days in sorted(days_left.items()):
        print(f"sandbox_uptime_check: cert {host}: {days} day(s) left")
    for text in unknown:
        print(f"sandbox_uptime_check: cert UNKNOWN, could not read {text}")
    if expiring:
        detail = "; ".join(expiring)
        decision = alert_state.decide(
            state,
            {"subject": f"TLS certificate expiring: {detail}"[:180],
             "body": ("A public TLS certificate is inside its renewal window "
                      f"(under {CERT_WARN_DAYS} days):\n\n  {detail}\n\n"
                      "Read at the TLS layer by the sandbox uptime check, which "
                      "took this over from the sandbox repo's retired hosted "
                      "probe on 2026-09-22. Renewal is normally automatic "
                      "(Cloudflare, Railway); this is the alarm for when it is "
                      "not. You will get ONE more email about this cause: a "
                      "note when every certificate is past the window again."),
             "dedupe_key": CERT_CAUSE_KEY},
            now=now)
        if decision.kind == "raise":
            if notify(decision.subject, decision.body):
                alert_state.apply(state, decision, now=now)
                print(f"sandbox_uptime_check: {decision.subject}: sent")
            else:
                print("sandbox_uptime_check: cert alert NOT sent, cause stays "
                      "new so the next run retries it")
        else:
            print(f"sandbox_uptime_check: cert {decision.note or decision.kind}")
        return
    if unknown:
        # Nothing read short, but not every host was read: not a recovery.
        return
    decision = alert_state.decide(
        state,
        {"subject": "RECOVERED: TLS certificate renewed",
         "body": "Every public certificate the sandbox uptime check reads is "
                 f"past the {CERT_WARN_DAYS}-day window again.",
         "resolve_scope": CERT_CAUSE_KEY},
        now=now)
    if decision.kind == "resolve":
        if notify(decision.subject, decision.body):
            alert_state.apply(state, decision, now=now)
            print("sandbox_uptime_check: cert RECOVERED sent")
        else:
            print("sandbox_uptime_check: cert RECOVERED NOT sent "
                  "(cause stays open, next run retries)")


def run(*, fetch=None, state_path: Path | str = STATE_PATH,
        now: int | None = None, notify=None, read_cert=None) -> int:
    """-> exit code, always 0. This job's whole purpose is the alarm; see
    module docstring on why it never also reddens itself."""
    notify = notify or ops_notify.notify
    ok, detail = check_all(fetch=fetch)
    state = alert_state.load(state_path)
    _run_cert_check(state, read_cert=read_cert, now=now, notify=notify)

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
