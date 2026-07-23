#!/usr/bin/env python3
"""One-command operational status — run this FIRST in any session (esp. cloud).

Read-only. No dependencies (stdlib only), no keys needed. Prints the live
version, the source-health triage (what's degraded/stale and what to DO about
it), and the four surfaces to keep current.

Exit codes:
    0  ALL CLEAR — healthy, nothing needs a human.
    2  A source needs a human -> RUNBOOK 'a data source broke'. (Doubles as a
       CI check; CI can reach the site, so it never hits code 3.)
    3  The site is unreachable FROM THIS ENVIRONMENT only (egress/network-policy
       block, e.g. a cloud session denied asktherecruiter.com) — NOT a source
       outage. Deploys still work via git push; see docs/CLOUD-SESSION.md.

    python3 railway/ops_status.py
"""
import json
import sys
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = "https://asktherecruiter.com/blog"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# A degraded/stale source is BENIGN (no action) when it's one of these: a
# transient rate-limit, or a state with no public register.
SOFT = {"gdelt_historical", "source_audit"}
# States with no usable public register: a custom scraper returning 0 is correct,
# not drift. NV is NOT here anymore — the site mirrors DETR's master PDF daily
# (Bluehost's IP clears the Akamai bot-wall), so CI reads NV via the mirror; a 0
# now means the mirror broke and IS actionable.
BENIGN_STATES = {"AR", "WY", "NH"}
# A WARN custom scraper returning 0 is only real DRIFT for high-volume states
# (matches warn_import.py). A low-volume state filing nothing on a run is normal.
HIGH_VOLUME = {"TX", "FL", "GA", "CA", "OH", "MI", "NY", "NC"}
# staleness ceilings (days) — matches health_digest.py
MAX_AGE = {"edgar": 2, "newsapi": 2, "gdelt": 2, "warn_us": 3, "eurofound_erm": 3,
           "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4, "press_releases": 3,
           "warn_quebec": 3, "federal_rif": 35, "warn_hi_ocr": 3, "warn_mazowieckie": 3}


def _get(url, browser=False):
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA if browser else UA,
                                               "Accept": "application/json"})
    return urllib.request.urlopen(req, timeout=40)


def _is_egress_block(exc):
    """True when the failure is THIS ENVIRONMENT's egress/network policy denying
    the host (a proxy 403/407 CONNECT, tunnel failure, DNS/route block) — the
    request never reached the site, so it is NOT a source outage. Some cloud
    sessions can't reach asktherecruiter.com but can still deploy (git push ->
    Actions FTPS is server-side). See docs/CLOUD-SESSION.md.

    An HTTPError means the site actually answered (a real HTTP status), so it is
    a real problem, never an egress block — hence the isinstance short-circuit."""
    if isinstance(exc, urllib.error.HTTPError):
        return False
    s = str(exc).lower()
    return any(m in s for m in (
        "tunnel connection failed", "connect tunnel", "connect", "forbidden",
        "proxy", "connection refused", "network is unreachable", "no route to host",
        "name or service not known", "temporary failure in name resolution",
        "nodename nor servname", "407", "403"))


def _benign_states_only(detail):
    import re
    codes = re.findall(r"\b([A-Z]{2})\b", str(detail))
    return bool(codes) and all(c in BENIGN_STATES for c in codes)


def _low_volume_warn(src, detail):
    """A warn_custom_* degraded is benign if it names no high-volume state."""
    if not src.startswith("warn_custom"):
        return False
    import re
    codes = re.findall(r"\b([A-Z]{2})\b", str(detail))
    return not any(c in HIGH_VOLUME for c in codes)


def main():
    issues = []
    egress_blocked = []
    print("=" * 64)
    print("AI LAYOFF TRACKER — OPS STATUS")
    print("=" * 64)

    # 0. Handoff baton — is another session editing the repo right now?
    import os as _os
    _baton = _os.path.join(_os.path.dirname(__file__), "..", "docs", "HANDOFF.md")
    try:
        import re as _re
        _txt = open(_baton).read()
        _status = (_re.search(r"\*\*STATUS:\*\*\s*(\w+)", _txt) or [None, "?"])[1]
        _holder = (_re.search(r"\*\*HOLDER:\*\*\s*(.+)", _txt) or [None, "-"])[1].strip()
        if _status == "HELD":
            print(f"\n[0] HANDOFF BATON: HELD by {_holder} — another session is editing. "
                  "Do NOT edit; coordinate first (docs/HANDOFF.md).")
        else:
            print("\n[0] HANDOFF BATON: FREE — claim it in docs/HANDOFF.md before editing.")
    except Exception:
        print("\n[0] HANDOFF BATON: (docs/HANDOFF.md not found)")

    # 1. Live version
    try:
        html = _get(f"{BASE}/ai-layoff-tracker/?cb={uuid.uuid4()}", browser=True).read().decode("utf-8", "replace")
        import re
        ver = (re.search(r"ver=(\d+\.\d+\.\d+)", html) or [None, "?"])[1]
        print(f"\n[1] LIVE TRACKER  ver={ver}  (https://asktherecruiter.com/blog/ai-layoff-tracker/)")
    except Exception as exc:
        print(f"\n[1] LIVE TRACKER  UNREACHABLE: {exc}")
        (egress_blocked if _is_egress_block(exc) else issues).append("live tracker unreachable")

    # 2. Health triage
    print("\n[2] SOURCE HEALTH  (https://asktherecruiter.com/blog/ai-layoff-tracker/ai-tracker-health/)")
    try:
        health = json.load(_get(f"{BASE}/wp-json/layoffs/v1/source-health?cb={uuid.uuid4()}"))
        now = datetime.now(timezone.utc)
        ok = 0
        for src, info in (health or {}).items():
            if not isinstance(info, dict):
                continue
            status, detail = info.get("status"), info.get("detail", "")
            age = None
            try:
                age = (now - datetime.fromisoformat(str(info.get("checked_at")).replace("Z", "+00:00"))).days
            except Exception:
                pass
            stale = age is not None and age > MAX_AGE.get(src, 10)
            if stale:
                print(f"    STALE     {src}: {age}d old — collector may have STOPPED. -> RUNBOOK 'a data source broke'")
                issues.append(f"{src} stale")
            elif (status == "degraded" and src not in SOFT
                  and not _benign_states_only(detail) and not _low_volume_warn(src, detail)):
                print(f"    DEGRADED  {src}: {str(detail)[:80]} -> RUNBOOK 'a data source broke'")
                issues.append(f"{src} degraded")
            elif status in ("degraded",):
                print(f"    (benign)  {src}: {str(detail)[:60]}")
                ok += 1
            else:
                ok += 1
        print(f"    {ok} source(s) OK.")
    except Exception as exc:
        print(f"    HEALTH UNREACHABLE: {exc}")
        (egress_blocked if _is_egress_block(exc) else issues).append("health endpoint unreachable")

    # 3+4. Surfaces to keep current
    print("\n[3] SOURCES PAGE   https://asktherecruiter.com/blog/ai-layoff-tracker/sources/")
    print("      -> must list EXACTLY the live collectors; update on any source add/remove.")
    print("[4] BENCHMARK      scratchpad/bm-live.html (LOCAL ONLY, never commit)")
    print("      -> refresh vs-competitor read; every table shows ours + theirs.")

    print("\n" + "-" * 64)
    if issues:
        if egress_blocked:
            print(f"(also unreachable from this environment, likely egress-blocked: "
                  f"{', '.join(egress_blocked)} — see docs/CLOUD-SESSION.md)")
        print(f"ACTION NEEDED: {len(issues)} item(s) -> {', '.join(issues)}")
        print("See docs/RUNBOOK.md 'a data source broke (START HERE)'.")
        return 2
    if egress_blocked:
        print(f"ENVIRONMENT BLOCK: {len(egress_blocked)} surface(s) unreachable FROM THIS "
              f"ENVIRONMENT")
        print(f"    ({', '.join(egress_blocked)}) — an egress/network-policy block, NOT a "
              f"source outage.")
        print("    A proxy 403/407 tunnel CONNECT never reaches the site, so this is not an")
        print("    incident. You can still DEPLOY: edit -> bump Version:/ALT_VERSION -> git push")
        print("    (Actions FTPS-uploads server-side); confirm via a green 'Deploy WordPress")
        print("    plugin' run. To restore the visual curl check, allowlist asktherecruiter.com")
        print("    in this environment's egress policy. See docs/CLOUD-SESSION.md.")
        return 3
    print("ALL CLEAR — system healthy, all surfaces current. Nothing needs a human.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
