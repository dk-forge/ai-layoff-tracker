#!/usr/bin/env python3
"""Contabo box status / restart / watchdog. Stdlib only.

Runs on a GitHub-hosted runner (contabo-ops.yml) so it works when both
boxes are down. Docs: docs/TECHLOG.md 2026-10-18.

  contabo_watch.py status  --box box1
  contabo_watch.py restart --box box1
  contabo_watch.py watch   --state state.json [--dry-run]

Watch rules (owner spec, sandbox docs/AUTOMATION_MAP.md Layer 1):
  - healthy = API status "running" AND TCP 22 answers within 5 s
  - restart after 3 consecutive unhealthy checks (30 min)
  - at most 2 restarts per box per 6 h; after a restart, wait 15 min
    (cooldown) before judging the box again so it can boot
  - when the cap is hit: ONE email per cap window (Resend via
    railway/opsmail.py), else a ::error:: line. Never a GitHub issue.
Tokens are never printed; the workflow masks them with ::add-mask::.
"""
import argparse
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request
import uuid

AUTH_URL = "https://auth.contabo.com/auth/realms/contabo/protocol/openid-connect/token"
API = "https://api.contabo.com/v1/compute/instances"
BOXES = {
    "box1": {"id": "203574635", "ip": "173.249.57.163"},
    "box2": {"id": "203655919", "ip": "95.111.255.7"},
}
UNHEALTHY_BEFORE_RESTART = 3  # 2 false-alarmed on a busy-but-healthy box2 (2026-10-18 17:47-17:56 UTC)
MAX_RESTARTS = 2
WINDOW_S = 6 * 3600
COOLDOWN_S = 15 * 60


# ---------- HTTP (mocked in tests) ----------
def _http(method, url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode() or "{}"
        return r.status, json.loads(body)


def get_token(env=os.environ, http=_http):
    data = urllib.parse.urlencode({
        "client_id": env["CONTABO_CLIENT_ID"],
        "client_secret": env["CONTABO_CLIENT_SECRET"],
        "username": env["CONTABO_API_USER"],
        "password": env["CONTABO_API_PASSWORD"],
        "grant_type": "password",
    }).encode()
    _, body = http("POST", AUTH_URL, data,
                   {"Content-Type": "application/x-www-form-urlencoded"})
    tok = body["access_token"]
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{tok}")
    return tok


def _hdr(token):
    return {"Authorization": f"Bearer {token}", "x-request-id": str(uuid.uuid4()),
            "Content-Type": "application/json"}


def instance_status(token, box, http=_http):
    _, body = http("GET", f"{API}/{BOXES[box]['id']}", None, _hdr(token))
    return (body.get("data") or [{}])[0].get("status", "unknown")


def restart(token, box, http=_http):
    status, _ = http("POST", f"{API}/{BOXES[box]['id']}/actions/restart", b"{}", _hdr(token))
    return status


def tcp22(ip, timeout=5):
    try:
        with socket.create_connection((ip, 22), timeout=timeout):
            return True
    except OSError:
        return False


# ---------- pure decision logic (unit tested) ----------
def decide(box_state, healthy, now):
    """Return (action, new_state). action: ok|wait|cooldown|restart|capped.

    box_state: {"fails": int, "restarts": [epoch...], "capped_mailed_at": epoch|None}
    """
    s = {"fails": int(box_state.get("fails", 0)),
         "restarts": [t for t in box_state.get("restarts", []) if now - t < WINDOW_S],
         "capped_mailed_at": box_state.get("capped_mailed_at")}
    if s["restarts"] and now - max(s["restarts"]) < COOLDOWN_S:
        return "cooldown", s
    if healthy:
        s["fails"] = 0
        if not s["restarts"]:
            s["capped_mailed_at"] = None
        return "ok", s
    s["fails"] += 1
    if s["fails"] < UNHEALTHY_BEFORE_RESTART:
        return "wait", s
    if len(s["restarts"]) >= MAX_RESTARTS:
        mailed = s["capped_mailed_at"]
        if mailed is None or now - mailed >= WINDOW_S:
            s["capped_mailed_at"] = now
            return "capped", s
        return "capped-quiet", s
    s["restarts"].append(now)
    s["fails"] = 0
    return "restart", s


def notify_capped(box, detail):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "railway"))
    try:
        import opsmail
        if opsmail.configured():
            ok, note, _ = opsmail.send(
                f"Contabo {box} still down after {MAX_RESTARTS} restarts in 6h",
                f"{detail}\nWatchdog stopped restarting {box}. Check the Contabo panel "
                "(https://my.contabo.com) or run contabo-ops.yml action=status.",
                idempotency_key=f"contabo-capped-{box}-{int(time.time() // WINDOW_S)}")
            print(f"mail: {note}")
            if ok:
                return
    except Exception as e:  # mail failure must not hide the error line
        print(f"mail failed: {type(e).__name__}")
    print(f"::error::Contabo {box} still unhealthy after {MAX_RESTARTS} restarts in 6h ({detail})")


def watch(state, token, now, dry=False, http=_http, probe=tcp22, notify=notify_capped):
    for box, meta in BOXES.items():
        try:
            st = instance_status(token, box, http)
        except Exception as e:
            st = f"api-error:{type(e).__name__}"
        up = probe(meta["ip"])
        healthy = st == "running" and up
        action, state[box] = decide(state.get(box, {}), healthy, now)
        print(f"{box}: status={st} tcp22={'up' if up else 'down'} -> {action}")
        if action == "restart" and not dry:
            print(f"{box}: restart HTTP {restart(token, box, http)}")
        elif action == "capped" and not dry:
            notify(box, f"status={st} tcp22={'up' if up else 'down'}")
    return state


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["status", "restart", "watch"])
    p.add_argument("--box", choices=sorted(BOXES))
    p.add_argument("--state", default="state.json")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    token = get_token()
    if a.cmd == "status":
        print(f"{a.box}: status={instance_status(token, a.box)} "
              f"tcp22={'up' if tcp22(BOXES[a.box]['ip']) else 'down'}")
    elif a.cmd == "restart":
        print(f"{a.box}: restart HTTP {restart(token, a.box)}")
    else:
        try:
            with open(a.state) as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
        state = watch(state, token, time.time(), a.dry_run)
        if not a.dry_run:
            with open(a.state, "w") as f:
                json.dump(state, f, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
