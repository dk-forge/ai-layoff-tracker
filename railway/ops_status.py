#!/usr/bin/env python3
"""One-command operational status — run this FIRST in any session (esp. cloud).

Read-only. No dependencies (stdlib only), no keys needed. Prints the live
version, the source-health triage (what's degraded/stale and what to DO about
it), the LIVE DATA-INTEGRITY verdict, ANY WORKFLOW THAT IS CURRENTLY RED, and
the four surfaces to keep current.

Section [4] shells out to the `gh` CLI, which is the one part that needs
something beyond stdlib and the one part that is allowed to be absent: no gh, no
auth or no egress prints UNKNOWN and exits 3. It never prints a clean bill of
health off a signal it could not read.

WHY IT CHECKS THE DATA, NOT JUST THE COLLECTORS (added 2026-07-30)
------------------------------------------------------------------
For a long time this tool reported source STALENESS only, and was blind to
whether the data those sources produced was CORRECT. On 2026-07-30 a live defect
had Spirit Airlines reading 11,069 US-2026 jobs instead of ~7,069 — a news row
stacking on top of the WARN notices for the same layoff — CI went red five
times, and this tool said:

    ACTION NEEDED: 1 item(s) -> newsapi stale

A session could fix the stale source, read "1 item", and walk away from a
company overstated by 4,000 jobs on the live site. Section [3] now runs the same
invariants tests/test_dedup_live.py asserts, from the shared registry in
data_integrity.py, so the guard and the dashboard can never disagree.

Exit codes:
    0  ALL CLEAR — healthy, data-integrity checks verified and passing.
    2  A human is needed: a source needs one -> RUNBOOK 'a data source broke',
       and/or a LIVE DATA-INTEGRITY check is FAILING -> RUNBOOK 'a data-integrity
       check is failing', and/or a WORKFLOW IS CURRENTLY RED. A failing integrity
       check is at least as serious as a stale collector (it is wrong data on a
       live public surface, not missing data), so it never exits 0. Doubles as a
       CI check.
    3  Surfaces are unreachable FROM THIS ENVIRONMENT only (egress/network-policy
       block, e.g. a cloud session denied asktherecruiter.com) — NOT a source
       outage. Deploys still work via git push; see docs/CLOUD-SESSION.md.
       Integrity is then reported UNKNOWN, never "clear": absence of a signal is
       not a pass.

    python3 railway/ops_status.py
"""
import json
import sys
import uuid
from pathlib import Path
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
# staleness ceilings (days) — matches health_digest.py.
# A ceiling MUST match the job's real cadence. "newsapi" sat here at 2 days long
# after the twice-daily collector was retired, while the only job still posting
# under that id ran WEEKLY — so it read stale 5 days out of 7, forever, and that
# permanent amber was the only thing this tool reported on the day Spirit was
# live and overstated by 4,000 jobs. A ceiling a job cannot meet is not a
# monitor, it is noise that hides real breakage. See news_catchup.py.
MAX_AGE = {"edgar": 2, "news_catchup": 9, "google_news": 2, "gdelt": 2, "warn_us": 3,
           "eurofound_erm": 3, "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4,
           "press_releases": 3, "warn_quebec": 3, "federal_rif": 35, "warn_hi_ocr": 3,
           "warn_mazowieckie": 3, "data_integrity": 2}


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


def _gh(args, timeout=30):
    """Run a `gh` command. Returns (ok, stdout, why_not).

    Every failure mode — gh not installed, not authenticated, rate limited,
    egress blocked — comes back as a REASON, never as an empty success. A tool
    that turns "I could not look" into "nothing is wrong" is the exact bug this
    section exists to prevent.
    """
    import subprocess
    try:
        proc = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return False, "", "the gh CLI is not installed here"
    except subprocess.TimeoutExpired:
        return False, "", f"gh timed out after {timeout}s (network or rate limit)"
    except OSError as exc:
        return False, "", f"could not run gh: {exc}"
    if proc.returncode != 0:
        err = " ".join(proc.stderr.split())[:160] or f"gh exited {proc.returncode}"
        return False, "", err
    return True, proc.stdout, ""


def _report_ci():
    """(failures, unknown_reason) for the latest run of each workflow on main.

    Offline-safe by construction: no exception escapes, and every not-looked-at
    path returns a reason string rather than an empty failure list.
    """
    ok, out, why = _gh(["run", "list", "-L", "80", "--branch", "main",
                        "--json", "name,conclusion,status,url,createdAt"], timeout=30)
    if not ok:
        return [], why
    try:
        runs = json.loads(out or "[]")
    except ValueError:
        return [], "gh returned output that was not JSON"

    latest = {}
    for run in runs:
        name = run.get("name")
        # Only COMPLETED runs carry a verdict. A workflow whose newest run is
        # still in progress is judged on its newest FINISHED one, not called green.
        if not name or run.get("status") != "completed":
            continue
        if name not in latest or run.get("createdAt", "") > latest[name].get("createdAt", ""):
            latest[name] = run

    red = [(n, r) for n, r in sorted(latest.items())
           if r.get("conclusion") in ("failure", "timed_out", "startup_failure")]

    failures = []
    for name, run in red[:6]:
        cause = "(cause line not read)"
        # Only pay for the log when something is actually red, and only for the
        # first few. The extractor is SHARED with railway/ci_alert.py on purpose:
        # the email and this dashboard must never describe the same failure
        # differently — that drift is the same class of bug as a test bound
        # disagreeing with the health page.
        try:
            import os as _o
            _here = _o.path.dirname(_o.path.abspath(__file__))
            if _here not in sys.path:
                sys.path.insert(0, _here)
            import ci_alert
            repo = "dk-forge/ai-layoff-tracker"
            log_ok, log, _ = _gh(["run", "view", str(run.get("url", "")).rsplit("/", 1)[-1],
                                  "-R", repo, "--log-failed"], timeout=45)
            if log_ok:
                extracted, _ctx = ci_alert.extract_cause(log)
                if extracted:
                    cause = extracted
        except Exception:
            pass  # a cause we could not read must not cost us the RED itself
        failures.append((name, run.get("url", ""), cause))
    if len(red) > 6:
        failures.append((f"...and {len(red) - 6} more failing workflow(s)", "", "run: gh run list"))
    return failures, ""


def _outbox_doc():
    """The held-alert queue, read straight off disk.

    Deliberately not imported through alert_outbox: this file promises no deps
    and no side effects, and the queue is three lines of JSON. If the file is
    missing or unreadable the answer is "nothing held", the same way the queue
    itself treats it — this runs in the same neighbourhood as a failure path and
    must not become one.
    """
    import json

    path = Path(__file__).resolve().parent / "alert_outbox.json"
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return {"entries": []}
    return doc if isinstance(doc, dict) else {"entries": []}


#: Mirrors alert_outbox.FAIL_LOUD_ATTEMPTS. Duplicated rather than imported for
#: the reason above; if they ever disagree the queue's own value wins and this
#: one only makes ops_status escalate at a slightly different point.
_HELD_ALERT_FAIL_LOUD = 12


def _held_alerts():
    return [e for e in _outbox_doc().get("entries", [])
            if e.get("state") == "pending"]


def _held_alerts_need_a_human():
    """A queue that quietly never drains is the original silence with extra
    steps. A queue that is holding an alert through a ten-minute outage is the
    design working, and must NOT page."""
    return any(e.get("attempts", 0) >= _HELD_ALERT_FAIL_LOUD for e in _held_alerts())


def _report_held_alerts():
    held = _held_alerts()
    if not held:
        return ["none — every alert raised has reached the owner"]
    worst = max(e.get("attempts", 0) for e in held)
    lines = [f"{len(held)} held (most-tried: x{worst}); alert-drain.yml delivers "
             f"them when the host answers"]
    for e in held[:4]:
        subject = (e.get("payload") or {}).get("subject", e.get("key", ""))
        lines.append(f"  {e.get('raised_at')}  x{e.get('attempts', 0)}  {subject[:66]}")
    if len(held) > 4:
        lines.append(f"  ... and {len(held) - 4} more")
    if worst >= _HELD_ALERT_FAIL_LOUD:
        lines.append("  These have failed too many times to be an outage. Check "
                     "WP_API_KEY and that the plugin carrying /alert is live.")
    return lines


def main():
    issues = []
    egress_blocked = []
    unverified = []
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
            # Retired collectors keep their REAL last-run timestamp (no forged
            # freshness), so they will always look old — a retired row is never
            # stale, it is deliberately stopped.
            stale = status != "retired" and age is not None and age > MAX_AGE.get(src, 10)
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
            elif status == "retired":
                print(f"    (retired) {src}: {str(detail)[:60]}")
                ok += 1
            else:
                ok += 1
        print(f"    {ok} source(s) OK.")
    except Exception as exc:
        print(f"    HEALTH UNREACHABLE: {exc}")
        (egress_blocked if _is_egress_block(exc) else issues).append("health endpoint unreachable")

    # 3. LIVE DATA INTEGRITY — is the data those collectors produced CORRECT?
    #
    # Section [2] answers "did the collectors run?". It cannot answer "is what
    # they produced right?", and for months nothing on this dashboard could.
    # The invariants come from data_integrity.INVARIANTS, the SAME registry
    # tests/test_dedup_live.py asserts, so a bound can never drift between the
    # guard that reddens CI and the dashboard that tells a session all is well.
    #
    # We re-query the LIVE API rather than read the last CI conclusion on
    # purpose: this data changes without a commit (WARN lands daily,
    # reconcile-supersets runs at 12:40 ET), and the Spirit defect appeared
    # because a running SUM crossed a threshold with no code change at all. A
    # green tick from the last push is not evidence about the data now.
    print("\n[3] LIVE DATA INTEGRITY  (invariants shared with tests/test_dedup_live.py)")
    integrity = None
    try:
        # data_integrity lives beside this file. Running as `python3
        # railway/ops_status.py` already puts railway/ on sys.path, but be
        # explicit so a `python3 -m` or a cwd-relative invocation still resolves.
        if _os.path.dirname(_os.path.abspath(__file__)) not in sys.path:
            sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import data_integrity
        integrity = data_integrity.check_all()
        for r in integrity.results:
            if r.state == data_integrity.FAIL:
                print(f"    FAILING   {r.inv.label}: {r.detail}")
            elif r.state == data_integrity.UNKNOWN:
                print(f"    UNKNOWN   {r.inv.label}: {r.detail}")
        if integrity.verdict == data_integrity.PASS:
            print(f"    {len(integrity.passed)} check(s) verified and passing.")
        elif integrity.verdict == data_integrity.FAIL:
            print(f"    {len(integrity.passed)} passing, {len(integrity.failed)} FAILING "
                  f"-> RUNBOOK 'a data-integrity check is failing'.")
            print("    This is WRONG DATA on a live public surface, not missing data.")
            issues.extend(f"DATA INTEGRITY: {r.inv.key}" for r in integrity.failed)
        else:
            # UNKNOWN is never rendered as a pass. Route it by CAUSE: if we could
            # not reach the host at all, that is this environment's egress block
            # (exit 3, honest and non-alarming). If the site ANSWERED but
            # answered wrongly on the parameterised path, that is a real server
            # regression on exactly the query readers use -> a human (exit 2).
            print(f"    {len(integrity.unknown)} check(s) NOT VERIFIED — integrity state is "
                  f"UNKNOWN, which is NOT a pass.")
            if all(r.transport for r in integrity.unknown):
                egress_blocked.append("data-integrity checks (site unreachable)")
            else:
                issues.append("DATA INTEGRITY: unverifiable (the live API answered, but wrongly)")
    except Exception as exc:
        # Even the checker failing must not read as clean.
        print(f"    UNKNOWN — could not run the integrity checks: {exc}")
        issues.append("DATA INTEGRITY: checker could not run")

    # 4. RECENT CI — is any workflow red right now?
    #
    # Section [3] deliberately re-queries the live API instead of reading a CI
    # conclusion, because the DATA changes with no commit and a green tick from
    # the last push says nothing about the numbers now. That reasoning does not
    # transfer here and the distinction is worth keeping straight: the last CI
    # conclusion is a cached verdict about the data, but it is the PRIMARY
    # SOURCE about the workflows. "Is anything red?" has no better answer.
    #
    # This exists because a red run used to reach GitHub Actions and stop there.
    # test_dedup_live.py caught Spirit reading 11,069 jobs instead of ~7,069 and
    # reddened CI eight times over an afternoon while this tool — the one
    # CLAUDE.md tells every session to run FIRST — said nothing about it.
    print("\n[4] RECENT CI  (latest run per workflow on main)")
    ci_failures, ci_unknown = _report_ci()
    for label, url, cause in ci_failures:
        print(f"    RED       {label}")
        print(f"              {cause}")
        print(f"              {url}")
        issues.append(f"CI red: {label}")
    if ci_unknown:
        # Never a clean bill of health off a signal we could not read. The
        # sibling repo printed "Nothing queued, nothing lost" from a stale local
        # file while 15 runs had been destroyed; absence of a signal is not a pass.
        print(f"    UNKNOWN — could not read CI state: {ci_unknown}")
        print("              This is NOT 'everything is green'. It is 'nobody looked'.")
        unverified.append("recent CI runs")
    elif not ci_failures:
        print("    No workflow is currently failing on main.")

    # 4b. Did anything we tried to SAY about a red run actually get out?
    #
    # [1] above already tells a session whether the host is reachable right now
    # — it printed `UNREACHABLE: HTTP Error 504` during the 2026-07-31 window.
    # What it could not tell anyone is that /alert is a route on that same host,
    # so while it was down the CI alerter could not send mail either. Alerts
    # raised in that window are HELD in railway/alert_outbox.json and delivered
    # by alert-drain.yml; this is where a session sees what is still waiting.
    print("\n[4b] HELD ALERTS  (raised, not yet delivered — /alert lives on the host)")
    for line in _report_held_alerts():
        print(f"    {line}")
    if _held_alerts_need_a_human():
        issues.append("alerts are held and not being delivered")

    # 5+6. Surfaces to keep current
    print("\n[5] SOURCES PAGE   https://asktherecruiter.com/blog/ai-layoff-tracker/sources/")
    print("      -> must list EXACTLY the live collectors; update on any source add/remove.")
    print("[6] BENCHMARK      scratchpad/bm-live.html (LOCAL ONLY, never commit)")
    print("      -> refresh vs-competitor read; every table shows ours + theirs.")

    print("\n" + "-" * 64)
    if issues:
        if egress_blocked:
            print(f"(also unreachable from this environment, likely egress-blocked: "
                  f"{', '.join(egress_blocked)} — see docs/CLOUD-SESSION.md)")
        print(f"ACTION NEEDED: {len(issues)} item(s) -> {', '.join(issues)}")
        if integrity is not None and integrity.failed:
            # Say it twice and say it first: a stale collector loses future
            # coverage, a failing integrity check is publishing a wrong number
            # RIGHT NOW to every reader, the press page and the API.
            print("*** A DATA-INTEGRITY CHECK IS FAILING — the live site is serving a wrong")
            print("*** number. Fix this BEFORE any source-staleness item.")
            print("See docs/RUNBOOK.md 'a data-integrity check is failing (START HERE)'.")
        elif any(i.startswith("DATA INTEGRITY") for i in issues):
            # Answered, but not with an answer. Do not overstate it as a
            # confirmed wrong number — say exactly what is and is not known.
            print("*** DATA INTEGRITY IS UNVERIFIED. The site answered but did not return")
            print("*** usable totals, so the numbers were NOT checked. That is not a pass:")
            print("*** the parameterised query path may itself be broken.")
            print("See docs/RUNBOOK.md 'a data-integrity check is failing (START HERE)'.")
        if any(not i.startswith("DATA INTEGRITY") for i in issues):
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
        print("    DATA INTEGRITY IS UNKNOWN, NOT CLEAR — nothing here verified the numbers.")
        return 3
    # Only ever claim a clean bill of health we actually verified. If the
    # integrity checks did not resolve to a pass, say so and do not exit 0 — the
    # sibling repo printed "Nothing queued, nothing lost" off a stale local file
    # while 15 runs had been destroyed. Absence of a signal is not a pass.
    if integrity is None or integrity.verdict != "pass" or unverified:
        if integrity is None or integrity.verdict != "pass":
            print("NOT VERIFIED: sources look healthy, but the live data-integrity checks did")
            print("    not return a pass. The data may or may not be correct — this run did not")
            print("    establish it. Re-run with network access before trusting the numbers.")
        if unverified:
            print(f"NOT VERIFIED: {', '.join(unverified)} could not be read from this")
            print("    environment. Nothing here established that CI is green — it established")
            print("    only that nobody looked. Re-run where `gh auth status` succeeds.")
        return 3
    print(f"ALL CLEAR — system healthy, {len(integrity.passed)} data-integrity check(s) "
          f"verified passing, all surfaces current. Nothing needs a human.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
