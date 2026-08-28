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
import os as _os
import re
import sys
import uuid
from pathlib import Path
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import reader_freshness  # noqa: E402  - sibling module, stdlib only
import benchmark_freshness  # noqa: E402  - sibling module, stdlib only
import stash_watch  # noqa: E402  - sibling module, stdlib only
import subscriber_routes  # noqa: E402  - sibling module, stdlib only
import alert_state  # noqa: E402  - sibling module, stdlib only
import run_completion  # noqa: E402  - sibling module, stdlib only
import state_liveness  # noqa: E402  - sibling module, stdlib only (git only)

# The repo this script lives in — [8] reads its stash stack. Derived from the
# file, never from the cwd: ops_status.py is run from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent

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
MAX_AGE = {"edgar": 2, "news_catchup": 9, "google_news": 2, "regional_feeds": 2,
           "national_feeds": 2,
           "gdelt": 2, "warn_us": 3,
           "eurofound_erm": 3, "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4,
           "press_releases": 3, "warn_quebec": 3, "federal_rif": 35, "warn_hi_ocr": 3,
           "warn_mazowieckie": 3, "data_integrity": 2, "digest_mailer": 3,
           # source_audit is the third instance of the same defect, and it had
           # been reading STALE for ~2 weeks in 3, every month, since it shipped.
           # source-verification-audit.yml is `0 13 1 * *` — the 1st of each
           # month — and nothing else posts under that id. DERIVATION: the
           # longest legitimate gap between two runs is the longest month, 31
           # days, plus 4 days of slack so ONE missed monthly run is reported on
           # day 35 rather than a healthy 31-day-old run being reported forever.
           # Identical arithmetic to federal_rif above (6th of the month).
           "source_audit": 35}


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


def _is_deferral(detail):
    """A deferral CLOSES its running note, and must not alarm twice.

    host_call.defer writes a `degraded` row so the collector does not sit at
    `running` looking healthy. That row is honest -- the work did not happen --
    but deferrals already have their own escalation in [4d], which counts them
    and goes red on the third in a row. Treating one transient 503 as an
    ACTION NEEDED here would raise the same incident on two channels, which is
    how a channel gets ignored.
    """
    try:
        import host_call
        marker = host_call.DEFERRED_DETAIL
    except Exception:                                    # pragma: no cover
        return False
    # Prefix, not equality: defer() appends the underlying reason.
    return str(detail).startswith(marker[:40])


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


def _last_deploy_finished_at():
    """When the last SUCCESSFUL plugin deploy finished. Returns (datetime, why_not).

    Needed to tell "shipped a minute ago and still propagating" apart from
    "readers are stuck on an old build". Returns (None, reason) when it cannot
    be determined, so the caller reports UNKNOWN rather than inventing a
    deadline it can meet.
    """
    ok, out, why = _gh(["run", "list", "--workflow=Deploy WordPress plugin",
                        "-L", "10", "--json", "conclusion,updatedAt"])
    if not ok:
        return None, why
    try:
        runs = json.loads(out or "[]")
    except ValueError as exc:
        return None, f"could not parse gh output: {exc}"
    for run in runs:
        if run.get("conclusion") == "success":
            try:
                return datetime.fromisoformat(str(run["updatedAt"]).replace("Z", "+00:00")), ""
            except (KeyError, ValueError) as exc:
                return None, f"unreadable deploy timestamp: {exc}"
    return None, "no successful deploy run found in the last 10 runs"


def _report_ci():
    """(failures, unknown_reason) for the latest run of each workflow on main.

    Offline-safe by construction: no exception escapes, and every not-looked-at
    path returns a reason string rather than an empty failure list.
    """
    limit = 300
    ok, out, why = _gh(["run", "list", "-L", str(limit), "--branch", "main",
                        "--json", "name,conclusion,status,url,createdAt"], timeout=60)
    if not ok:
        return [], why
    try:
        runs = json.loads(out or "[]")
    except ValueError:
        return [], "gh returned output that was not JSON"

    # THE WINDOW IS A SIGNAL, NOT A BACKGROUND DETAIL (2026-08-14). This asks
    # for one page of recent runs and calls a workflow green when its newest
    # FINISHED run is green. That is only sound while the page reaches back far
    # enough to contain every workflow's newest run. At -L 80 it did not: two
    # merges in one afternoon generated enough runs that the page began at
    # 17:10Z, the 15:42Z "Data quality report" failure fell off the end, and
    # this section printed "No workflow is currently failing on main" while it
    # was. A red run scrolling out of view is exactly the silence this section
    # exists to break, so a full page is now UNKNOWN rather than a pass. Every
    # workflow here runs at least daily, so a page spanning 24h holds them all.
    if len(runs) >= limit:
        newest, oldest = runs[0].get("createdAt", ""), runs[-1].get("createdAt", "")
        span_h = 0.0
        try:
            span_h = (datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ")
                      - datetime.strptime(oldest, "%Y-%m-%dT%H:%M:%SZ")).total_seconds() / 3600
        except (ValueError, TypeError):
            pass
        if span_h < 24:
            # Do not give up and do not pretend. Ask the question directly:
            # "which runs FAILED", which needs no window, then re-check each
            # named workflow's own newest run so a failure already superseded
            # by a green one is not reported as current.
            f_ok, f_out, f_why = _gh(["run", "list", "--status", "failure",
                                      "--branch", "main", "-L", "20", "--json", "name"],
                                     timeout=45)
            if not f_ok:
                return [], (f"the run list came back full ({limit}) spanning {span_h:.1f}h, "
                            f"and the failure-only query also failed ({f_why}). Not a pass")
            try:
                names = {r.get("name") for r in json.loads(f_out or "[]") if r.get("name")}
            except ValueError:
                return [], "gh returned output that was not JSON for the failure query"
            runs = []
            for name in sorted(names):
                w_ok, w_out, _ = _gh(["run", "list", "--workflow", name, "--branch", "main",
                                      "-L", "5", "--json",
                                      "name,conclusion,status,url,createdAt"], timeout=45)
                if not w_ok:
                    return [], (f"could not read the newest run of {name!r} after the run "
                                f"list truncated at {limit}. Not a pass")
                try:
                    runs.extend(json.loads(w_out or "[]"))
                except ValueError:
                    return [], "gh returned output that was not JSON for a workflow query"

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

#: Mirrors alert_outbox.MAX_HELD_HOURS, duplicated for the same reason.
#:
#: The attempt count above only moves when alert-drain.yml RUNS. A drain that is
#: disabled, broken, or stopped by GitHub's inactivity rule on scheduled
#: workflows leaves every held alert at `attempts: 1` for ever, and this section
#: used to print that as "1 held (most-tried: x1)" and exit 0 — a dashboard that
#: got greener the more completely the delivery path had failed. Age is the
#: question attempts cannot answer.
_HELD_ALERT_MAX_HOURS = 6


def _held_alert_age_hours(entry):
    """Hours since this was raised. Unparseable -> 0.0: an entry whose age
    cannot be read is UNKNOWN, and UNKNOWN is not escalated on age alone (the
    attempt count still speaks for it) — but it is never silently a pass
    either, because it is reported as UNKNOWN in the lines below."""
    from datetime import datetime, timezone

    try:
        when = datetime.fromisoformat(entry.get("raised_at") or "")
    except (TypeError, ValueError):
        return 0.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 3600.0)


def _held_alerts():
    return [e for e in _outbox_doc().get("entries", [])
            if e.get("state") == "pending"]


def _held_alerts_need_a_human():
    """A queue that quietly never drains is the original silence with extra
    steps. A queue that is holding an alert through a ten-minute outage is the
    design working, and must NOT page.

    Two ways to stop being an outage: too many refusals, or too much silence."""
    held = _held_alerts()
    return (any(e.get("attempts", 0) >= _HELD_ALERT_FAIL_LOUD for e in held)
            or any(_held_alert_age_hours(e) >= _HELD_ALERT_MAX_HOURS for e in held))


def _report_held_alerts():
    held = _held_alerts()
    if not held:
        return ["none — every alert raised has reached the owner"]
    worst = max(e.get("attempts", 0) for e in held)
    oldest = max(_held_alert_age_hours(e) for e in held)
    lines = [f"{len(held)} held (most-tried: x{worst}, oldest {oldest:.1f}h); "
             f"alert-drain.yml delivers them when the relay answers"]
    for e in held[:4]:
        subject = (e.get("payload") or {}).get("subject", e.get("key", ""))
        age = _held_alert_age_hours(e)
        stamp = f"{age:.1f}h" if e.get("raised_at") else "age UNKNOWN"
        lines.append(f"  {e.get('raised_at')}  x{e.get('attempts', 0)}  "
                     f"[{stamp}]  {subject[:56]}")
    if len(held) > 4:
        lines.append(f"  ... and {len(held) - 4} more")
    if worst >= _HELD_ALERT_FAIL_LOUD:
        lines.append("  ACTION NEEDED: these have failed too many times to be an "
                     "outage. Check RESEND_API_KEY, and check that OPS_MAIL_FROM "
                     "uses a domain the Resend account has verified.")
    if oldest >= _HELD_ALERT_MAX_HOURS:
        lines.append(f"  ACTION NEEDED: held longer than {_HELD_ALERT_MAX_HOURS}h. "
                     "At a drain every 30 minutes that is not an outage waiting "
                     "to pass — check alert-drain.yml is still running AT ALL "
                     "(`gh run list --workflow=alert-drain.yml`). Nobody has "
                     "been told about the failure this alert describes.")
    return lines


#: The committed open/resolved ledger, read straight off disk like the outbox
#: above and for the same reason: this file promises no dependencies and no
#: side effects.
#: Resolved by `alert_state.state_path()` AT CALL TIME, not bound to a constant
#: here. `classify_open` below reads that same path, and two paths that agree
#: everywhere except under ALERT_STATE_PATH is a discrepancy only a test would
#: ever meet — which is exactly the kind that survives. Binding it at import
#: would reintroduce the split for anything that sets the variable after import.


def _report_open_alarms():
    """What the alerter is currently keeping QUIET, and since when.

    New with the move to Resend, and worth having in its own right. The
    open/resolved state used to live in a WordPress option where no session
    could read it, so "why have I heard nothing about this?" had no answer short
    of the database. A suppressed alarm is a deliberate silence, and a
    deliberate silence should be legible.

    AND SOME OF THEM ARE NOT WAITING FOR ANYTHING. A cause raised on a feature
    branch is scoped `<workflow>:<branch>:<fingerprint>` and clears only when a
    green run of THAT scope posts its resolve. `tests.yml` fires on
    `pull_request` and on pushes to `main`, so once that branch's PR has landed
    no such run can ever happen: the entry is unclearable, and it earns one
    `STILL FAILING` reminder a fortnight for a branch nobody will touch again.

    Those are named here rather than counted as ordinary open alarms, because
    "quiet until a green run clears it" is FALSE for them and the only thing
    that will ever clear one is a reviewed close. Two words, because they are
    proved differently: ORPHANED is the branch gone from origin, MERGED is the
    branch still present but an ancestor of main. The one sitting in the ledger
    on 2026-08-19 was the second kind — `ops/resend-ua`, PR #143 merged, ref
    never deleted — which a plain does-the-branch-exist test reads as healthy.

    -> (lines, unclearable_count). The remote is asked ONCE, and a remote that
    does not answer is UNKNOWN — never orphaned, and never a clean read.
    """
    import json

    try:
        doc = json.loads(alert_state.state_path().read_text())
        entries = doc.get("open") or {}
    except Exception as exc:  # noqa: BLE001
        return [f"UNKNOWN: could not read alert_state.json ({exc})"], 0
    if not entries:
        return ["none — nothing is being suppressed, so a red run will mail"], 0

    # ONE definition of "which branch is this keyed to", imported rather than
    # re-spelled here: a second copy of that regex is a second thing to get
    # wrong, and getting it wrong declares a live alarm unclearable.
    rows = alert_state.classify_open(remote=True)
    statuses = {k: st for k, _f, _l, _sub, st in rows}

    ordered = sorted(entries.items(), key=lambda kv: int(kv[1].get("first", 0)))
    stuck = [k for k, _ in ordered if statuses.get(k) in alert_state.UNCLEARABLE]
    unknown = [k for k, _ in ordered if statuses.get(k) == alert_state.UNKNOWN]
    live = len(ordered) - len(stuck)
    lines = [f"{len(ordered)} open ({live} live, {len(stuck)} unclearable); a live "
             f"cause stays quiet until a green run clears it"]
    for key, meta in ordered[:4]:
        tag = {alert_state.ORPHANED: "  ORPHANED (branch gone from origin)",
               alert_state.MERGED: "  MERGED (branch parked, PR landed)",
               alert_state.UNKNOWN: "  branch?"}.get(statuses.get(key), "")
        lines.append(f"  {key}{tag}\n        {str(meta.get('subject') or '')[:66]}")
    if len(ordered) > 4:
        lines.append(f"  ... and {len(ordered) - 4} more")
    if unknown:
        lines.append("  `branch?` means origin did not answer, so it is not known "
                     "whether those branches still exist. That is UNKNOWN, not a pass.")
    if stuck:
        lines.append("  No green run of those scopes can ever fire, so nothing will clear "
                     "them, and")
        lines.append("  each costs a false STILL FAILING email every 14 days until a human "
                     "closes it:")
        lines.append(f"    {alert_state.CLOSE_HELP}")
        lines.append("  See docs/RUNBOOK.md 'an open alarm cannot clear itself'.")
    return lines, len(stuck)


#: Read straight off disk for the same reason as the outbox above: this file
#: promises no dependencies and no side effects.
_DEFERRAL_LEDGER = Path(__file__).resolve().parent / "deferral_ledger.json"

#: Mirrors deferral_ledger.ESCALATE_AFTER, duplicated for that same reason.
_DEFERRAL_ESCALATE_AFTER = 3


#: Conclusions ci_alert.py treats as a red run. Kept in step with its ALERTABLE
#: rather than re-guessed here, because two vocabularies for one event is the
#: defect that left self_heal blind to self-timeouts until 2026-08-18.
_ROUTED_CONCLUSIONS = ("failure", "timed_out", "startup_failure")


def _routed_branch_failures():
    """(lines, unknown) — the pull-request failures ci_alert.py did NOT mail.

    THE OTHER HALF OF THE ROUTING CHANGE, and the half that makes it safe. From
    2026-08-20 a pull-request-triggered failure on a branch that is not main
    goes here instead of to the owner's inbox. Silence and INVISIBILITY are
    different things, and this repo has already paid for confusing them: a
    filtered alarm is how a defect stayed live for hours. So every failure that
    was not mailed is listed here, by branch, with its age.

    Only the NEWEST run per workflow+branch is shown. A branch that failed and
    was then fixed is not an open item, and listing every historical red run
    would rebuild the wall of noise this change exists to remove.

    NO ESCALATION THRESHOLD IS SET, ON PURPOSE. A branch red for many hours is a
    session that stopped or a branch nobody owns, and that is worth knowing --
    but sizing that window needs a distribution of how long branch failures
    normally live, and the only data this repo can read is 2026-08-19/20, six
    events, several of them created by the session that would have been setting
    the threshold. A ceiling guessed from that is the 2-day staleness bound on a
    weekly job all over again: permanently-red amber that hides real breakage.
    The AGE is printed from today so the distribution accumulates in plain
    sight, and a later session can size it from data rather than from a feeling.

    Never contributes to the exit code. A routed failure is somebody's working
    branch, not a call for the owner.
    """
    ok, out, why = _gh(["run", "list", "-L", "200", "--json",
                        "name,conclusion,status,url,createdAt,headBranch,event"],
                       timeout=60)
    if not ok:
        return [f"UNKNOWN - {why}. Routed branch failures could not be read, "
                f"which is not the same as there being zero of them."], True
    try:
        runs = json.loads(out or "[]")
    except ValueError:
        return ["UNKNOWN - gh returned output that was not JSON"], True

    newest = {}
    for run in runs:
        if run.get("status") != "completed":
            continue
        branch = run.get("headBranch") or ""
        if run.get("event") != "pull_request" or branch == "main" or not branch:
            continue
        seat = (run.get("name") or "", branch)
        if seat not in newest:            # gh returns newest first
            newest[seat] = run

    still_red = [(seat, run) for seat, run in newest.items()
                 if run.get("conclusion") in _ROUTED_CONCLUSIONS]
    if not still_red:
        return ["none - no pull-request branch is currently red"], False

    still_red.sort(key=lambda pair: pair[1].get("createdAt", ""))
    lines = [f"{len(still_red)} pull-request failure(s) not mailed; each is red in "
             f"its own PR and blocks that merge"]
    for (workflow, branch), run in still_red:
        age = ""
        try:
            started = datetime.strptime(run.get("createdAt", ""),
                                        "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - started).total_seconds() / 3600
            age = f"{hours:.1f}h ago" if hours < 48 else f"{hours / 24:.1f}d ago"
        except (ValueError, TypeError):
            age = "age unknown"
        lines.append(f"  {workflow} on {branch}  ({age})")
        lines.append(f"    {run.get('url', '')}")
    lines.append("A LIVE-DATA failure is never routed here, and a failure on main "
                 "is never routed here. Both still mail.")
    return lines, False


def _deferral_doc():
    import json

    try:
        doc = json.loads(_DEFERRAL_LEDGER.read_text())
    except (OSError, ValueError):
        return {"entries": []}
    return doc if isinstance(doc, dict) else {"entries": []}


def _open_deferrals():
    return [e for e in _deferral_doc().get("entries", [])
            if e.get("state") == "pending"]


def _deferrals_need_a_human():
    """One deferral is an outage and the design working. Three in a row is a job
    hiding behind the outage story, and needs a person."""
    return any(e.get("consecutive", 0) >= _DEFERRAL_ESCALATE_AFTER
               for e in _open_deferrals())


def _report_deferrals():
    open_ = _open_deferrals()
    if not open_:
        return ["none — every host call got an answer"]
    lines = [f"{len(open_)} job(s) deferred; the next scheduled run retries"]
    for e in open_[:4]:
        lines.append(f"  {e.get('job')}  x{e.get('consecutive', 0)}  since "
                     f"{e.get('first_deferred_at')}  "
                     f"{str(e.get('last_reason', ''))[:52]}")
    if len(open_) > 4:
        lines.append(f"  ... and {len(open_) - 4} more")
    if _deferrals_need_a_human():
        lines.append(f"  {_DEFERRAL_ESCALATE_AFTER}+ in a row is NOT the host having a "
                     "bad night. -> RUNBOOK 'a job is DEFERRING'.")
    return lines


#: Runway below this many days is the owner's problem to solve, across both
#: repos. Raised from 7 on 2026-08-14: at the measured account rate 7 days is
#: inside the time it takes to notice, decide and top up.
RUNWAY_FLOOR_DAYS = 14


def burn_problems(account_per_day, repo_per_day, allowance_month, runway_days):
    """The spend verdict, split by which denominator each half belongs to.

    Pulled out of `_report_run_cost` so it can be tested without a filesystem.
    `account_per_day` is the OpenRouter BALANCE delta, which covers every repo
    billing that key. `repo_per_day` is THIS repo's own metered ledger, or None
    when the ledger could not be read. `allowance_month` is this repo's policy.

    The bug this shape exists to prevent: those first two numbers were compared
    against each other until 2026-08-14, so a sibling tracker's spend on the
    shared key read as this repo exceeding its allowance, and no change here
    could ever have cleared it. Nothing is silenced -- an account burning more
    than this repo's allowance still reports, as an ACCOUNT fact naming what
    this repo could and could not account for.
    """
    out = []
    if runway_days < RUNWAY_FLOOR_DAYS:
        out.append(
            f"~{runway_days:.1f} days of OpenRouter runway left on the SHARED account "
            f"(${account_per_day:.2f}/day across both trackers) — a top-up or a "
            f"cross-repo cut is the owner's call, not this repo's")
    if repo_per_day is None:
        return out
    if repo_per_day * 30 > allowance_month:
        out.append(
            f"THIS repo's own metered burn (${repo_per_day:.2f}/day, "
            f"~${repo_per_day * 30:.0f}/month) is above its "
            f"${allowance_month:.2f}/month allowance")
    elif account_per_day * 30 > allowance_month:
        out.append(
            f"the SHARED account is burning ${account_per_day:.2f}/day "
            f"(~${account_per_day * 30:.0f}/month) while this repo's meter explains only "
            f"${repo_per_day:.2f}/day of it — this repo is inside its "
            f"${allowance_month:.2f}/month allowance, so the balance is the other "
            f"tracker on the same key. No combined account allowance is recorded here")
    return out


def _report_run_cost():
    """[2a] What the models are costing, and what that money bought.

    Reads only committed files, so it works from any session with no key and no
    network. Returns a list of issue strings for the exit-code verdict.

    Returns (problems, unverified). The split matters: a burn ABOVE the
    allowance is a fact that needs a human (exit 2), while a figure that could
    not be measured at all is UNKNOWN (exit 3). Absence of a signal is not a
    pass, and it is also not evidence of a fault.

    Deliberately reports UNKNOWN rather than a pass in three cases: no history,
    a history with no row counts yet, and a rising balance (a top-up, which
    makes that day's delta meaningless as a spend figure).
    """
    import os
    import re

    here = os.path.dirname(os.path.abspath(__file__))
    problems, unverified = [], []

    # --- per-job attribution, from the committed ledger -------------------
    # railway/spend_jobs.json is filled by each job's SPEND_LEDGER_V1 line,
    # harvested daily out of the Actions run logs by the balance job (the one
    # workflow that commits). A job with no entry since metering began is
    # UNKNOWN — never a guessed number, and never a pass.
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import spend as _spend
        _ceilings = dict(_spend.JOB_RUN_CEILINGS_USD)
        _ledger = _spend._load_ledger()["entries"]
    except Exception as exc:
        _ceilings, _ledger = {}, None
        print(f"    per-job: UNKNOWN — could not read spend.py/spend_jobs.json ({exc})")
        unverified.append("per-job LLM cost attribution")
    if _ledger is not None:
        window_days = 14
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(days=window_days)).strftime("%Y-%m-%d")
        recent = [e for e in _ledger if str(e.get("date", "")) >= cutoff]
        jobs = sorted(set(_ceilings) | {e.get("job") for e in recent if e.get("job")})
        metered = {}
        for e in recent:
            metered.setdefault(e["job"], []).append(e)
        if not recent:
            print(f"    per-job     UNKNOWN — no metered run in the ledger yet "
                  f"(railway/spend_jobs.json); the daily harvest fills it. "
                  f"Not a pass.")
            unverified.append("per-job LLM cost attribution")
        else:
            unjudged: dict[str, list] = {}
            print(f"    per-job (last {window_days}d, railway/spend_jobs.json; "
                  f"$/row over stored+changed):")
            print(f"      {'job':26} {'runs':>4} {'$/day':>8} {'$/run':>8} "
                  f"{'rows':>6} {'$/row':>9}  ceiling")
            for job in jobs:
                entries = metered.get(job)
                ceiling = _ceilings.get(job)
                ceil_txt = f"${ceiling:.3f}/run" if ceiling is not None else "default"
                if not entries:
                    print(f"      {job:26} {'—':>4} {'UNKNOWN':>8} {'':8} "
                          f"{'':6} {'':9}  {ceil_txt} (no metered run yet)")
                    continue
                cost = sum(float(e.get("cost_usd") or 0) for e in entries)
                rows_vals = [(e.get("stored") or 0) + (e.get("changed") or 0)
                             for e in entries
                             if e.get("stored") is not None or e.get("changed") is not None]
                rows = sum(rows_vals) if rows_vals else None
                per_run = cost / len(entries)
                per_row = (f"${cost / rows:.4f}" if rows else
                           ("bought 0" if cost > 0 and rows == 0 else "UNKNOWN"))
                print(f"      {job:26} {len(entries):>4} {cost / window_days:>8.4f} "
                      f"{per_run:>8.4f} {(str(rows) if rows is not None else 'UNK'):>6} "
                      f"{per_row:>9}  {ceil_txt}")
                # Judge each run against the ceiling THAT RUN ran under, which
                # its own ledger entry now records. A dispatch may carry an
                # authorised ALT_RUN_CEILING_USD override (edgar-history-sweep
                # offers one as a workflow input on purpose), and comparing
                # that run to the table's named number reports a brake failure
                # where an operator made a deliberate one-off decision. Entries
                # written before ceiling_usd existed have no such record, so
                # they fall back to the named ceiling — the old behaviour, and
                # the reason the message says which basis it used.
                worst, basis = None, None
                for e in entries:
                    cost = float(e.get("cost_usd") or 0)
                    own = e.get("ceiling_usd")
                    # Judge a run ONLY against the ceiling it RECORDED running
                    # under — never against the table's CURRENT named number
                    # when the run recorded none of its own. An unrecorded
                    # entry cannot be proven to have overshot: it may have run
                    # under an operator's authorised one-off override (
                    # edgar-history-sweep offers a per-dispatch run_ceiling_usd
                    # input on purpose — the $0.2721 run on 2026-08-12 ran under
                    # an authorised $0.40, not the named $0.150), or it may
                    # simply predate ceiling recording (added 2026-08-14). Either
                    # way, asserting a brake failure on it is a false alarm in
                    # the one place that must only ever report real ones, and a
                    # false ACTION item is exactly how a real overshoot later
                    # goes unread. Unrecorded is UNKNOWN — collected and PRINTED
                    # below, never silent, never an ACTION. Since 2026-08-14
                    # every run records its ceiling (pinned by
                    # tests/test_spend_ceiling_is_recorded.py), so an unrecorded
                    # entry is a pre-fix relic that ages out of the window on its
                    # own. This subsumes the old railway-cron case (no named AND
                    # no recorded ceiling): it too recorded none, so it too is
                    # UNKNOWN, by the same rule rather than a separate branch.
                    if own is None:
                        unjudged.setdefault(job, [0, 0.0])
                        unjudged[job][0] += 1
                        unjudged[job][1] = max(unjudged[job][1], cost)
                        continue
                    ran_under = float(own)
                    if cost <= ran_under * 1.25:
                        continue
                    if worst is None or cost > worst:
                        worst, basis = cost, ran_under
                if worst is not None:
                    problems.append(
                        f"{job} spent ${worst:.3f} in one run, past its "
                        f"${basis:.3f} ceiling (the ceiling that run ran under) "
                        f"— the per-job brake is not holding")
            if unjudged:
                # UNKNOWN, printed. Deliberately NOT an ACTION item: a run
                # nobody can audit is not evidence of an overshoot, and putting
                # it in the same list as a measured overshoot is how the one
                # place that reports real overshoot stops being read. It is
                # also self-clearing — entries written since 2026-08-15 carry
                # their own ceiling, so these age out of the window rather than
                # needing to be closed.
                print(f"    not judged  run(s) that recorded no ceiling of "
                      f"their own — UNKNOWN, not a pass (a run is judged only "
                      f"against the ceiling it ran under, and these recorded "
                      f"none; pre-2026-08-14 relics that age out of the window):")
                for job in sorted(unjudged):
                    n, worst = unjudged[job]
                    print(f"      {job:26} {n:>4} run(s), dearest ${worst:.4f}, "
                          f"compared against nothing")
            # Per-collector split, for entries that carry one (the Railway
            # cron posts its breakdown via /tracker-meta). This is the table
            # that replaces attributing the cron's burn by subtraction.
            src_totals = {}
            for e in recent:
                for name, s in (e.get("sources") or {}).items():
                    if not isinstance(s, dict):
                        continue
                    agg = src_totals.setdefault(name, {
                        "cost": 0.0, "calls": 0, "items": 0, "stored": 0,
                        "kept": 0, "dropped": 0})
                    agg["cost"] += float(s.get("cost_usd") or 0)
                    for k in ("calls", "items", "stored", "kept", "dropped"):
                        agg[k] += int(s.get(k) or 0)
            if src_totals:
                print(f"    per-source (entries carrying a breakdown, last "
                      f"{window_days}d; gate kept/dropped incl. shadow verdicts):")
                print(f"      {'source':22} {'$':>8} {'calls':>6} {'items':>6} "
                      f"{'stored':>6} {'$/stored':>9} {'gate k/d':>9}")
                for name in sorted(src_totals, key=lambda n: -src_totals[n]["cost"]):
                    a = src_totals[name]
                    per_stored = (f"${a['cost'] / a['stored']:.4f}"
                                  if a["stored"] else
                                  ("bought 0" if a["cost"] > 0 else "-"))
                    print(f"      {name:22} {a['cost']:>8.4f} {a['calls']:>6} "
                          f"{a['items']:>6} {a['stored']:>6} {per_stored:>9} "
                          f"{a['kept']:>4}/{a['dropped']}")

    # --- is the guard armed at all? ---
    snap_path = os.path.join(here, "spend_month.json")
    try:
        with open(snap_path) as fh:
            snap = json.load(fh) or {}
    except (OSError, ValueError):
        snap = {}
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    armed = [fp for fp, e in snap.items()
             if isinstance(e, dict) and e.get("month") == month]
    allowance = "10.00"
    try:
        with open(os.path.join(here, "spend.py")) as fh:
            m = re.search(r"MONTHLY_ALLOWANCE_USD = ([\d.]+)", fh.read())
            if m:
                allowance = f"{float(m.group(1)):.2f}"
    except OSError:
        pass
    print(f"    allowance   ${allowance}/month (policy, railway/spend.py)")
    # "Am I on track for the month?" in one line, from the committed ledger.
    # No key, no network — the same property the rest of this section has.
    try:
        print(f"    budget      {_spend.budget_line()}")
    except Exception as exc:  # noqa: BLE001 — a status line must not crash ops
        print(f"    budget      UNKNOWN — could not compute ({exc}). Not a pass.")
        unverified.append("month-to-date budget projection")
    if armed:
        print(f"    guard       armed for {month}: {len(armed)} key(s) have a "
              f"month-start snapshot")
    else:
        print(f"    guard       NO month-start snapshot for {month} yet — "
              f"month-to-date is UNKNOWN")
        print("                (the daily OpenRouter balance job takes and "
              "commits it; UNKNOWN is not a pass)")
        unverified.append(f"month-to-date spend for {month}")

    # --- $/day and $/stored row, from the committed daily readings ---
    hist_path = os.path.join(here, "openrouter_balance_history.json")
    try:
        with open(hist_path) as fh:
            hist = json.load(fh)
        hist = [r for r in hist if isinstance(r, dict) and r.get("date")]
        hist.sort(key=lambda r: r["date"])
    except (OSError, ValueError):
        hist = []

    if len(hist) < 2:
        print("    UNKNOWN: fewer than two committed balance readings, so no "
              "burn rate can be computed.")
        unverified.append("LLM burn rate")
        return problems, unverified

    window = hist[-6:]
    first, last = window[0], window[-1]
    spent = float(first.get("balance") or 0) - float(last.get("balance") or 0)
    days = max(1, (datetime.strptime(last["date"], "%Y-%m-%d")
                   - datetime.strptime(first["date"], "%Y-%m-%d")).days)
    print(f"    balance     ${float(last.get('balance') or 0):,.2f} "
          f"as of {last['date']}")
    if spent <= 0:
        print(f"    burn        UNKNOWN over {days}d — the balance did not fall "
              f"(a top-up lands here), so no rate is derivable.")
        unverified.append("LLM burn rate")
        return problems, unverified

    # THE BALANCE IS AN ACCOUNT, THE ALLOWANCE IS A REPO. Until 2026-08-14
    # these two lines were compared directly and the comparison was a category
    # error: `spent` is the fall in ONE OpenRouter account's balance, and both
    # trackers bill to that account, while `allowance` is the policy in THIS
    # repo's spend.py and covers this repo alone. Measured on 2026-08-14, the
    # account fell $1.04/day while this repo's own meter recorded $0.23/day of
    # it; the remaining ~$0.81 is the sibling tracker, which this repo has no
    # ledger for and no authority over. So the old alarm compared a two-repo
    # numerator against a one-repo denominator and would have stayed red
    # forever no matter what this repo did.
    #
    # It is NOT silenced, because the account really is burning more than the
    # trackers' stated allowances and the runway really is short. It is split
    # into the two questions it was conflating, each against its own
    # denominator:
    #   * IS THIS REPO INSIDE ITS ALLOWANCE?  ledger vs allowance. Actionable
    #     here, and the only half any change in this repo can move.
    #   * IS THE ACCOUNT SOLVENT?  balance vs runway, plus how much of the
    #     account's burn this repo can account for. Actionable only by the
    #     owner, across both repos, so it says so instead of naming a number
    #     this repo could not have caused.
    per_day = spent / days
    mine = None
    if _ledger is not None:
        window_dates = {r["date"] for r in window}
        mine = sum(float(e.get("cost_usd") or 0) for e in _ledger
                   if str(e.get("date", "")) in window_dates) / days
    print(f"    burn        ${per_day:,.2f}/day over the last {days}d "
          f"(${spent:,.2f} total) — ACCOUNT-WIDE, both trackers bill this key")
    if mine is None:
        print("    of which     UNKNOWN — this repo's ledger could not be read, "
              "so none of the account burn is attributed. Not a pass.")
        unverified.append("this repo's share of the account burn")
    else:
        print(f"    of which    ${mine:,.2f}/day is THIS repo's metered spend; "
              f"${max(0.0, per_day - mine):,.2f}/day is not in this ledger")
    runway = float(last.get("balance") or 0) / per_day
    print(f"    runway      ~{runway:,.1f} days at that rate")
    problems.extend(burn_problems(per_day, mine, float(allowance), runway))

    r0, r1 = first.get("rows"), last.get("rows")
    if not isinstance(r0, int) or not isinstance(r1, int):
        print("    $/row       UNKNOWN — the readings predate row-count "
              "recording. The next daily balance job starts recording it.")
        unverified.append("cost per stored row")
        return problems, unverified
    gained = r1 - r0
    if gained <= 0:
        print(f"    $/row       {gained} rows stored over {days}d, so every "
              f"cent of ${spent:,.2f} bought nothing storable.")
        problems.append("spend produced no new rows over the measured window")
        return problems, unverified
    print(f"    $/row       ${spent / gained:.4f} per stored row "
          f"({gained:,} rows for ${spent:,.2f} over {days}d)")
    return problems, unverified


def subscriber_lines():
    """Digest subscriber counts, as the lines this section prints.

    COUNTS ONLY. /subscriber-stats returns no address in any field or error
    path, and nothing here would print one if it did.

    Three outcomes, kept distinct on purpose:
      * no WP_API_KEY in this environment  -> UNKNOWN (we did not ask)
      * the route says available=false     -> UNKNOWN (the table is not there)
      * numbers                            -> print them
    A zero is only ever printed when the endpoint counted zero rows. "We could
    not look" and "nobody has subscribed" are different facts and a 0 standing
    in for the first one is a lie with a number attached.

    Deliberately INFORMATIONAL: an unreadable panel does not push this tool to
    exit 3. Most local sessions carry no key, and making the common case exit
    non-zero is how a status tool stops being read. The health of the mailer
    itself is already guarded, loudly, by the digest_mailer staleness ceiling
    in section [2]. Do not "upgrade" this to an issue.
    """
    key = _os.environ.get("WP_API_KEY", "")
    if not key:
        return ["UNKNOWN - no WP_API_KEY in this environment, so the keyed stats route",
                "          was not called. This is NOT 'zero subscribers'."]
    try:
        req = urllib.request.Request(
            f"{BASE}/wp-json/layoffs/v1/subscriber-stats?cb={uuid.uuid4().hex[:8]}",
            headers={"User-Agent": UA, "Accept": "application/json",
                     "X-Layoff-API-Key": key})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    except Exception as exc:
        return [f"UNKNOWN - could not read /subscriber-stats ({exc}).",
                "          Not a pass and not a zero: this run did not look."]
    if not isinstance(data, dict) or not data.get("available"):
        reason = (data or {}).get("reason") or "the endpoint reported no data"
        return [f"UNKNOWN - {reason}.",
                "          A 0 here would claim nobody subscribed; the truth is we cannot see."]

    c = data.get("confirmed") or {}
    freq = data.get("frequency") or {}
    rate = data.get("confirm_rate")
    lines = [
        f"subscribers {c.get('total')} confirmed "
        f"(layoff {c.get('layoff')}, talent {c.get('talent')}, articles {c.get('articles')}); "
        f"+{data.get('confirmed_last_7_days')} in the last 7 days",
        f"pending {data.get('pending')}, unsubscribed {data.get('unsubscribed')}, "
        f"confirm rate {'UNKNOWN' if rate is None else format(rate * 100, '.1f') + '%'}; "
        f"daily {freq.get('daily')}, weekly {freq.get('weekly')}",
    ]
    # Bounces are counted apart from unsubscribes because they are a different
    # fact: a mailbox that does not exist, not a reader who left. A rising
    # bounce count is a deliverability problem, and rolling it into the
    # unsubscribe number would hide it as readers losing interest. Older
    # installs have no such field, and that is UNKNOWN rather than zero.
    bounced = data.get("bounced")
    if bounced is not None:
        lines.append(f"bounced {bounced} (dead mailboxes, stopped automatically; "
                     f"counted apart from unsubscribes)")
    last = data.get("last_send")
    if not last:
        lines.append("last send  none logged yet (the send log is empty, not unreadable)")
    else:
        clicks = "UNKNOWN" if last.get("clicks") is None else last.get("clicks")
        unsub = "UNKNOWN" if last.get("unsubscribes_48h") is None else last.get("unsubscribes_48h")
        lines.append(
            f"last send  {last.get('sent_at')} ({last.get('freq')}): sent to "
            f"{last.get('recipients')}, {clicks} click(s), {unsub} unsubscribed within 48h")
    lines.append("no open-rate figure exists here on purpose: open tracking needs a")
    lines.append("          per-person pixel and about half of inboxes preload it.")
    return lines


def digest_credential_lines(health):
    """What the mailer's last run established about its own credential.

    WHY THIS IS A LINE OF ITS OWN rather than left to the staleness ceiling in
    [2]. Between 2026-08-17 and 2026-08-19 the armed Brevo credential was being
    refused with 535 and this tool said nothing at all, three sessions running.
    The health row was not stale and it was not degraded: it read `ok, 0
    entries`, which was a true description of a run with nobody due and no
    description whatsoever of a relay that had stopped accepting us. The row
    now carries `credential=<STATE>` and this reads it, because the fact worth
    seeing at session start is not how many people got an email yesterday - it
    is whether anyone COULD have.

    PASS / FAIL / UNKNOWN, and a fourth for dormancy. An unreadable row is
    UNKNOWN and never a pass.

    ONLY `REJECTED` raises an issue, and that does not contradict the rule in
    `subscriber_lines` above about keeping this panel informational. That rule
    is about an unreadable panel, and it still holds here: an unreadable row,
    an absent row and an unreachable relay all print UNKNOWN and raise nothing.
    A refusal is not an unreadable panel. It is a settled fault with a named
    remedy that only the owner can perform.
    """
    if not isinstance(health, dict):
        return ["credential UNKNOWN - the health endpoint could not be read, so",
                "          the mailer's credential state is not established here."], False
    row = health.get("digest_mailer")
    if not isinstance(row, dict):
        return ["credential UNKNOWN - no digest_mailer health row. The sender has",
                "          not recorded a run, which is not a sender that is working."], False
    detail = str(row.get("detail") or "")
    match = re.search(r"credential=([A-Z]+)", detail)
    if not match:
        return ["credential UNKNOWN - the mailer's last row predates this check, so it",
                "          says how many were sent, not whether it could have sent."], False
    state = match.group(1)
    if state == "REJECTED":
        return (["credential REJECTED - the relay refused us on the mailer's last run.",
                 f"          {detail[:150]}",
                 "          -> RUNBOOK 'the digest cannot authenticate'. A human has to",
                 "          rotate the secret; nothing in this repo can."], True)
    if state == "OK":
        return ["credential OK - the relay accepted us on the mailer's last run."], False
    if state == "ABSENT":
        return ["credential DORMANT - none is armed, so nothing sends. A state,",
                "          not a fault. Arming it is a reviewed change to digest-send.yml."], False
    return (["credential UNKNOWN - not established on the mailer's last run:",
             f"          {detail[:150]}",
             "          Not a pass. The next run settles it."], False)


# The weekly digest slot has its own schedule since 2026-08-19, so it needs its
# own liveness ceiling. 7 days between two legitimate runs, plus 2 days of
# slack, so ONE missed Monday is reported on the Wednesday rather than a healthy
# 6-day-old row reading STALE for most of every week. Identical arithmetic to
# federal_rif and source_audit: the real cadence, then slack.
WEEKLY_DIGEST_MAX_AGE_DAYS = 9


def weekly_digest_lines(health):
    """Has the weekly digest slot actually run? (lines, raises_an_issue).

    WHY THIS IS NOT LEFT TO THE `digest_mailer` CEILING IN [2]. Until
    2026-08-19 both tiers went out from one daily run, so one row and one
    3-day ceiling covered both. The daily digest now has its own 6:00 Eastern
    slot and the weekly its own 7:30 Monday slot, and `digest_mailer` is
    stamped by whichever pass ran - which is every single morning. A weekly
    slot that stopped firing would sit behind a permanently green row and
    nothing would say a word. Splitting the schedule is only defensible
    because this check exists; if this is ever removed, put the schedule back.

    WHAT THE ROW MEANS, precisely: the EXTERNAL weekly sender completed a pass.
    The in-WordPress fallback sender does not write it. So a stale row can mean
    readers missed an edition, or it can mean this repo's schedule broke and
    the fallback quietly carried it. Both are worth a human, and the message
    says so rather than guessing which one happened.

    PASS / FAIL / UNKNOWN, and only FAIL raises. An unreadable health endpoint
    and an absent row are UNKNOWN: absence of a signal is never a pass, and it
    is never a fault either. A row that exists and is older than the weekly
    cadence plus its slack is a settled FAIL.
    """
    if not isinstance(health, dict):
        return ["weekly slot UNKNOWN - the health endpoint could not be read, so",
                "          whether the weekly digest ran is not established here."], False
    row = health.get("digest_weekly")
    if not isinstance(row, dict):
        return (["weekly slot UNKNOWN - no digest_weekly health row yet. The first",
                 "          weekly pass after 2026-08-19 writes it; until then this",
                 "          says 'not established', which is not a pass."], False)
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(
            str(row.get("checked_at")).replace("Z", "+00:00"))).days
    except Exception:
        return (["weekly slot UNKNOWN - the digest_weekly row carries no readable",
                 "          timestamp, so its age could not be established."], False)
    detail = str(row.get("detail") or "")[:110]
    if age > WEEKLY_DIGEST_MAX_AGE_DAYS:
        return ([f"weekly slot STALE - the weekly digest has not completed a pass in",
                 f"          {age}d (ceiling {WEEKLY_DIGEST_MAX_AGE_DAYS}d = its 7-day cadence + 2 of slack).",
                 f"          Either Monday's 7:30 ET slot stopped firing, or it ran and",
                 f"          failed. Check the 'Send email digest' Monday runs and the",
                 f"          send log; the in-WordPress fallback may have covered the",
                 f"          send, which would leave readers fine and the schedule broken.",
                 f"          last: {detail}"], True)
    if str(row.get("status")) == "degraded":
        return ([f"weekly slot DEGRADED - last pass {age}d ago did not send cleanly:",
                 f"          {detail}"], False)
    return [f"weekly slot OK - last weekly pass {age}d ago: {detail}"], False


def _print_wrapped(text, width=86, indent="        "):
    """One slice per line, wrapped, so a multi-slice verdict stays readable."""
    import textwrap
    for part in str(text).split("; "):
        for line in textwrap.wrap(part, width) or [""]:
            print(indent + line)



# --- [2d] worldwide news reach --------------------------------------------

_REACH_RX = re.compile(
    r"returned=(\d+) queries=(\d+) answered=(\d+) abandoned=(\d+) "
    r"capped=(\d+) kept=(\d+) dropped=(\d+)")


def gdelt_reach_lines(runs):
    """Read the reach facts back out of the gdelt /source-runs history.

    `_fetch_trusted` discarded silently for the whole life of this collector,
    so "114 countries have a configured outlet and zero rows" had three live
    explanations and no way to tell them apart. The two that this section can
    actually distinguish are:

      THE CAP IS BINDING   a query returned exactly `maxrecords` over a 36h
                           window sorted newest-first, so everything below the
                           cut was never offered to us at all.
      THE WINDOW WAS LOST  the query was abandoned after its retries, which is
                           a whole slice of a day of worldwide news gone with
                           no trace, and a COMPLETELY INDEPENDENT cause.

    Informational by design. It appends nothing to `issues`: an abandoned
    window already degrades the gdelt row in section [2], and a capped query
    is a fact about reach, not a fault. Never turn a normal run into an alarm
    here -- a quiet Tuesday is not news.

    Returns (lines, unmeasured) where `unmeasured` is True when no run in the
    window carried reach facts. Absence of the signal is UNKNOWN, never a pass.
    """
    terminal = [r for r in runs
                if isinstance(r, dict) and r.get("status") in ("ok", "degraded")]
    parsed = []
    for r in terminal:
        m = _REACH_RX.search(str(r.get("detail") or ""))
        if m:
            ret, q, ans, aband, cap, kept, drop = (int(g) for g in m.groups())
            parsed.append({"at": r.get("attempted_at"), "q": q, "ans": ans,
                           "aband": aband, "cap": cap, "ret": ret,
                           "kept": kept, "drop": drop})
    if not parsed:
        return ([
            "reach UNKNOWN - no run in this window recorded what GDELT returned.",
            "  Either the instrumented collector has not run yet, or the runs",
            "  predate it. Not a pass: a silent collector is unmeasured, not clean.",
        ], True)

    latest = parsed[0]
    capped_runs = sum(1 for p in parsed if p["cap"])
    aband_runs = sum(1 for p in parsed if p["aband"])
    lines = [
        f"last measured run {str(latest['at'])[:16]}: {latest['q']} quer(ies), "
        f"{latest['ans']} answered, {latest['ret']} article(s) returned",
        f"  kept {latest['kept']}, dropped {latest['drop']}",
    ]
    if latest["cap"]:
        lines.append(
            f"  CAP BINDING: {latest['cap']} quer(ies) returned exactly maxrecords."
            " Coverage below the cut was never offered.")
    if latest["aband"]:
        lines.append(
            f"  WINDOW LOST: {latest['aband']} quer(ies) abandoned after retries."
            " That slice of the day has no trace. -> RUNBOOK 'a data source broke'")
    lines.append(
        f"over {len(parsed)} measured run(s): {capped_runs} with a capped query, "
        f"{aband_runs} with an abandoned window")
    return (lines, False)



def main():
    issues = []
    egress_blocked = []
    unverified = []
    # Guards that exist but are not watching yet: the deployed build predates the
    # field they read, or the first baseline has not been written. Exit 3, never
    # 0 — an unarmed guard is not a passing guard.
    not_provisioned = []
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

    # 1. Live version, as the ORIGIN reports it. The cache buster is what makes
    #    this the origin's answer and not a reader's. See [1b], which is the
    #    one that speaks for readers.
    try:
        html = _get(f"{BASE}/ai-layoff-tracker/?cb={uuid.uuid4()}", browser=True).read().decode("utf-8", "replace")
        import re
        ver = (re.search(r"ver=(\d+\.\d+\.\d+)", html) or [None, "?"])[1]
        print(f"\n[1] LIVE TRACKER  ver={ver}  (origin, cache-busted)")
    except Exception as exc:
        print(f"\n[1] LIVE TRACKER  UNREACHABLE: {exc}")
        (egress_blocked if _is_egress_block(exc) else issues).append("live tracker unreachable")

    # 1b. What READERS are served. A deploy that only reached the origin has not
    #     shipped. On 2026-08-05 the bare URL served a superseded build for 18
    #     minutes while [1] above, and the deploy workflow, both read green:
    #     every check carried a query string, so every check measured the origin.
    print("\n[1b] READER VIEW   (bare URL, browser UA, NO cache buster)")
    try:
        deploy_at, why_not = _last_deploy_finished_at()
        freshness = reader_freshness.check(deploy_finished_at=deploy_at)
        print(f"    {freshness.verdict}: {freshness.detail}")
        if freshness.verdict == reader_freshness.FAIL:
            print("    -> docs/RUNBOOK.md 'a deploy is not reaching readers'.")
            issues.append("deploys are not reaching readers")
        elif freshness.verdict == reader_freshness.UNKNOWN:
            if why_not:
                print(f"    (last deploy time unavailable: {why_not})")
            unverified.append("what readers are served")
    except Exception as exc:                      # noqa: BLE001
        print(f"    UNKNOWN: {exc}")
        (egress_blocked if _is_egress_block(exc) else unverified).append("what readers are served")

    # 1c. The two links inside an email. [1b] watches the page a reader browses
    #     to; this watches the only two URLs a reader is ever SENT. Both turned
    #     up in the live 404 log on 2026-08-19, and nothing in this product
    #     could have said so: the send reports success, the credential
    #     verifies, and a confirmation nobody completes reads as "0 of 0
    #     eligible". A dead unsubscribe is a compliance failure rather than a
    #     bug, because the List-Unsubscribe-Post header promises Gmail and
    #     Yahoo a working POST endpoint.
    print("\n[1c] SUBSCRIBER ROUTES  (confirm + unsubscribe, probed from outside)")
    try:
        routes = subscriber_routes.check()
        for probe in routes.probes:
            print(f"    {probe.verdict:<7} {probe.label}: {probe.detail}")
        if routes.verdict == subscriber_routes.FAIL:
            print("    -> docs/RUNBOOK.md 'a subscriber route is 404ing'.")
            issues.append("a subscriber-facing email route is not answering")
        elif routes.verdict == subscriber_routes.UNKNOWN:
            print("    THIS IS NOT A PASS.")
            unverified.append("whether the confirm and unsubscribe links work")
    except Exception as exc:                      # noqa: BLE001
        print(f"    UNKNOWN: {exc}")
        (egress_blocked if _is_egress_block(exc) else unverified).append(
            "whether the confirm and unsubscribe links work")

    # 2. Health triage
    print("\n[2] SOURCE HEALTH  (https://asktherecruiter.com/blog/ai-layoff-tracker/ai-tracker-health/)")
    health = None
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
                  and not _is_deferral(detail)
                  and not _benign_states_only(detail) and not _low_volume_warn(src, detail)):
                print(f"    DEGRADED  {src}: {str(detail)[:80]} -> RUNBOOK 'a data source broke'")
                issues.append(f"{src} degraded")
            elif status in ("degraded",):
                print(f"    (benign)  {src}: {str(detail)[:60]}")
                ok += 1
            elif status == "retired":
                print(f"    (retired) {src}: {str(detail)[:60]}")
                ok += 1
            elif status == "running":
                # NOT ok. This ledger keeps only the LATEST note, and a `running`
                # note carries a fresh checked_at, so a collector that died
                # mid-flight used to land in the `else` below as one of the
                # "N source(s) OK" AND reset its own staleness clock while doing
                # it. Whether this one is in flight or stranded is [2e]'s
                # question; here it is simply not evidence of health.
                print(f"    (running) {src}: started, no terminal note yet — "
                      f"see [2e]")
            else:
                ok += 1
        print(f"    {ok} source(s) OK.")
    except Exception as exc:
        print(f"    HEALTH UNREACHABLE: {exc}")
        (egress_blocked if _is_egress_block(exc) else issues).append("health endpoint unreachable")

    # 2b. SOURCE FRESHNESS + INVENTORY.
    #
    # Section [2] above reads the health ledger, which answers "did the
    # collector run?". It cannot answer either of the two questions below, and
    # for months nothing could:
    #
    #   * is what it returned NEW? A collector re-reading a frozen archive
    #     returns its whole history every run and clears every count floor.
    #     Kansas looked green for 110 days while publishing nothing.
    #   * which collectors never report AT ALL? Those do not show up green.
    #     They do not show up, and absent reads as "no problem" rather than
    #     "never looked at".
    #
    # Both are read from committed files and one live ledger, so this works from
    # any session, including an egress-blocked one for the committed half.
    print("\n[2b] SOURCE FRESHNESS  (committed railway/source_state.json)")
    try:
        import source_freshness as _sf
        _ledger = _sf.load_ledger()
        _dark_rows = _sf.broken(_ledger)
        for _r in _dark_rows:
            print(f"    DARK      {_r['key']}: {_r.get('days_dark')}d with no new "
                  f"record ({_r.get('classification')}), open {_r['age_days']}d")
            _print_wrapped(str(_r.get("last_reason") or ""))
        if _dark_rows:
            # ONE issue, not one per source. A backlog found on the first run is
            # a backlog, and six entries in this list is how a session learns to
            # skim it.
            issues.append(f"{len(_dark_rows)} source(s) dark "
                          f"(publishing nothing new) -> RUNBOOK 'a collector went dark'")
        for _q in _sf.quiet(_ledger):
            # Advisory, and pointedly NOT an issue: Kansas read like this at
            # p=0.023 with an audit showing every notice already collected.
            print(f"    (quiet)   {_q['key']}: {_q.get('days_dark')}d with no "
                  f"new record, recent {_q.get('rate_per_year')}/yr vs long-run "
                  f"{_q.get('rate_long_run_per_year')}/yr. Not evidence of a break.")
        _unavail = _sf.unavailable(_ledger)
        _unk_src = _sf.unknown_sources(_ledger)
        print(f"    {len(_dark_rows)} BROKEN, {len(_unavail)} UNAVAILABLE "
              f"(human-classified), {len(_unk_src)} UNKNOWN.")
        if _unk_src:
            print(f"    UNKNOWN   too little history to judge, which is NOT a "
                  f"pass: {', '.join(_unk_src[:12])}")
    except Exception as exc:                                   # noqa: BLE001
        print(f"    UNKNOWN: source freshness could not be read ({exc})")
        unverified.append("whether any collector has gone dark")

    print("\n[2c] SOURCE INVENTORY  (what SHOULD exist, vs what reports)")
    try:
        import source_inventory as _si
        _inv = _si.summary(health or {})
        print(f"    {_inv['jurisdictions_collected']} of {_inv['jurisdictions']} "
              f"US jurisdictions have a WARN collector; no public register in: "
              f"{', '.join(_inv['jurisdictions_uncollected'])}")
        _never = _inv.get("never_reported")
        if _never is None:
            print(f"    UNKNOWN: {_inv.get('never_reported_error')}")
            unverified.append("which collectors have never reported health")
        elif _never:
            print(f"    NEVER REPORTED  {len(_never)} declared collector(s) have "
                  f"NO health row at all: {', '.join(_never)}")
            print("        Absent is not green. Either the collector does not "
                  "run, or it runs and never reports.")
            issues.append(f"{len(_never)} collector(s) declared but never reported")
        else:
            print(f"    every one of the {_inv['declared_collectors']} declared "
                  f"collectors has reported at least once.")
    except Exception as exc:                                   # noqa: BLE001
        print(f"    UNKNOWN: inventory could not be built ({exc})")
        unverified.append("the source inventory")

    # 2a. RUN COST — "is this run expensive" was unanswerable until 2026-08-02.
    #
    # The only cost signal in this repo was a daily account balance, which
    # cannot attribute a cent to a run and could not see the Railway cron's key
    # at all. Between 2026-07-26 and 2026-08-02 the account fell $71.86 ->
    # $22.92 with nothing in the repo able to say what had bought that.
    #
    # This reads the two committed ledgers (no key needed, so it works from any
    # session) and divides spend by rows stored. Cost per stored row is the
    # number that makes a run judgeable: 100 calls that store 40 rows and 100
    # calls that store 0 rows cost the same and are not the same event.
    print("\n[2a] RUN COST  (committed ledgers; $/day and $/stored row)")
    try:
        _cost_problems, _cost_unknown = _report_run_cost()
        issues += _cost_problems
        unverified += _cost_unknown
    except Exception as exc:
        print(f"    UNKNOWN: could not read the spend ledgers ({exc}).")
        print("    Not a pass — this run did not measure cost.")
        unverified.append("LLM run cost")

    # 2d. WORLDWIDE NEWS REACH — what GDELT actually returned, and what we did
    # with it. See railway/gdelt_reach.py for why this had to be built: the
    # trusted-domain gate discarded silently, so nobody could say whether a
    # country was never returned, returned and dropped, or returned and
    # deduped. Read off the PUBLIC /source-runs telemetry, so it needs no key.
    print("\n[2d] WORLDWIDE NEWS REACH  (public /source-runs; informational, never an alarm)")
    try:
        _runs = json.load(_get(
            f"{BASE}/wp-json/layoffs/v1/source-runs?source=gdelt&days=30&per_page=120&cb={uuid.uuid4()}"))
        _rl, _unmeasured = gdelt_reach_lines(_runs.get("runs") or [])
        for _line in _rl:
            print(f"    {_line}")
        if _unmeasured:
            unverified.append("worldwide news reach")
    except Exception as exc:
        print(f"    REACH UNKNOWN: {exc}")
        if _is_egress_block(exc):
            egress_blocked.append("source-runs unreachable")
        else:
            unverified.append("worldwide news reach")

    # 2e. RUN COMPLETION — did the collectors FINISH, or only start?
    #
    # Section [2] reads the health ledger, which keeps only the LATEST note per
    # source, so an orphaned `running` is erased by the next run within a day.
    # [2b] judges whether a source is PUBLISHING; a run that dies before it
    # queries publishes nothing and reads as a quiet day. The append-only
    # /source-runs telemetry is the only place a start/finish PAIR survives.
    #
    # Three gdelt runs since 2026-05-23 started and never finished, and the
    # 2026-08-16 run died earlier still. Two are provably dead processes rather
    # than dropped telemetry (no end-of-run record in railway/spend_jobs.json).
    # Every surface read green throughout. See railway/run_completion.py.
    print("\n[2e] RUN COMPLETION  (public /source-runs; a start with no finish)")
    try:
        def _runs_fetch(params):
            _q = "&".join(f"{k}={v}" for k, v in params.items())
            return json.load(_get(
                f"{BASE}/wp-json/layoffs/v1/source-runs?{_q}&cb={uuid.uuid4()}"))
        _crows, _cincomplete = run_completion.collect(_runs_fetch)
        _cl, _cissue = run_completion.verdict_lines(_crows, incomplete=_cincomplete)
        for _line in _cl:
            print(f"    {_line}")
        if _cissue:
            issues.append(_cissue)
        if _cincomplete:
            unverified.append("collector run completion (page cap)")
        elif not _crows:
            unverified.append("collector run completion")
    except Exception as exc:
        print(f"    RUN COMPLETION UNKNOWN: {exc}")
        if _is_egress_block(exc):
            egress_blocked.append("source-runs unreachable")
        else:
            unverified.append("collector run completion")

    # [2f] STATE LIVENESS — is each MECHANISM still writing its own file?
    #
    # [2e] asks whether a collector run finished. This asks a wider question
    # the dashboard could not: is the machinery still doing anything at all?
    # A mechanism that stops does not raise; it stops changing its committed
    # state file, which is visible in git and was visible in nobody's read of
    # it. The GDELT work ledger held zero slots from the day it shipped while
    # production abandoned 7 of 12 windows a run.
    #
    # Reads git only, so it needs no key and no network.
    print()
    try:
        _srows = state_liveness.collect()
        print(state_liveness.render(_srows))
        _sdead = state_liveness.problems(_srows)
        if _sdead:
            issues.append(f"{len(_sdead)} mechanism(s) that have never written "
                          f"their own state")
        if any(r["state"] == state_liveness.UNKNOWN for r in _srows):
            unverified.append("state liveness (too little history to judge)")
    except Exception as exc:
        print(f"[2f] STATE LIVENESS UNKNOWN: {exc}")
        unverified.append("state liveness")

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
        # The shape guards cover several slices each, so their detail is a
        # sentence per slice. Wrap it here rather than shortening the message:
        # the full text is what ci_alert.py extracts into the failure email, and
        # a truncated cause is how an alert stops being actionable.
        for r in integrity.results:
            if r.state == data_integrity.FAIL:
                print(f"    FAILING   {r.inv.label}:")
                _print_wrapped(r.detail)
            elif r.state == data_integrity.UNKNOWN:
                print(f"    UNKNOWN   {r.inv.label}:")
                _print_wrapped(r.detail)
        if integrity.verdict == data_integrity.PASS:
            print(f"    {len(integrity.passed)} check(s) verified and passing.")
        elif integrity.verdict == data_integrity.FAIL:
            print(f"    {len(integrity.passed)} passing, {len(integrity.failed)} FAILING "
                  f"-> RUNBOOK 'a data-integrity check is failing'.")
            print("    This is WRONG DATA on a live public surface, not missing data.")
            issues.extend(f"DATA INTEGRITY: {r.inv.key}" for r in integrity.failed)
        else:
            # UNKNOWN is never rendered as a pass. Route it by CAUSE, in three
            # buckets, because "we could not check" has three quite different
            # meanings and collapsing them is how a real regression gets read as
            # a network hiccup:
            #   transport  the host was never reached -> this environment's
            #              egress block (exit 3, honest and non-alarming).
            #   pending    the host answered, but the thing being read is not
            #              there yet: a build that predates the field, or a
            #              baseline the daily job has not written. Exit 3, and
            #              the line says what to wait for. Still NOT a pass.
            #   otherwise  the site ANSWERED and answered wrongly on the
            #              parameterised path readers use -> a human (exit 2).
            print(f"    {len(integrity.unknown)} check(s) NOT VERIFIED — integrity state is "
                  f"UNKNOWN, which is NOT a pass.")
            if all(r.transport for r in integrity.unknown):
                egress_blocked.append("data-integrity checks (site unreachable)")
            elif all(r.transport or getattr(r, "pending", False) for r in integrity.unknown):
                for r in integrity.unknown:
                    if getattr(r, "pending", False):
                        print(f"    PENDING   {r.inv.key}: waiting on a deploy or on the first "
                              f"baseline write — this guard is not watching yet.")
                not_provisioned.extend(r.inv.key for r in integrity.unknown
                                       if getattr(r, "pending", False))
            else:
                issues.append("DATA INTEGRITY: unverifiable (the live API answered, but wrongly)")
    except Exception as exc:
        # Even the checker failing must not read as clean.
        print(f"    UNKNOWN — could not run the integrity checks: {exc}")
        issues.append("DATA INTEGRITY: checker could not run")

    # 3c. MEASURED COVERAGE — the answer to "we cover X%", with its denominator.
    #
    # Section [3] can only say that this check passed, and "18 checks passing"
    # is not a coverage figure. The number itself is printed here because the
    # question it answers — "what fraction of the events that exist do we
    # hold?" — is the one the owner is asked in public, and until 2026-08-17 the
    # only answer in the repo was a hand-maintained file that had been stale for
    # 24 days. A figure a session cannot see at a glance is a figure that gets
    # re-derived from memory.
    #
    # It prints the BAND and the denominator, never a bare percentage, and it
    # prints every declared slice including the ones that are not measurable.
    print("\n[3c] MEASURED COVERAGE  (rolling recall vs a denominator we do not ingest)")
    try:
        import rolling_recall
        rr_doc = rolling_recall.load_measurement()
        rr_state, rr_detail = rolling_recall.judge(rr_doc)
        if rr_doc is None:
            print("    UNKNOWN - no measurement has been written yet. Coverage is "
                  "UNMEASURED, not fine.")
            print("              Run: python3 railway/rolling_recall.py --write")
            not_provisioned.append("rolling_recall (never measured)")
        else:
            for key in rr_doc.get("declared_slices") or []:
                s = (rr_doc.get("slices") or {}).get(key) or {
                    "state": rolling_recall.UNKNOWN, "detail": "absent from the report"}
                if s.get("state") == rolling_recall.MEASURED:
                    w = s["window"]
                    lo = s["confirmed"] / s["judged"]
                    hi = (s["confirmed"] + s["proposed"]) / s["judged"]
                    print(f"    MEASURED  {key}  {lo:.1%}-{hi:.1%} of {s['judged']} events"
                          f"  ({w['from']}..{w['to']})")
                    print(f"              {s['enumerated_filings']} enumerated, "
                          f"{s['out_of_scope']} out of scope, {s['undecidable']} UNKNOWN, "
                          f"{s.get('unreachable', 0)} unreachable")
                elif s.get("state") == rolling_recall.NOT_MEASURABLE:
                    print(f"    NOT MEASURABLE  {key}")
                    _print_wrapped(s.get("detail") or "", indent="              ")
                else:
                    print(f"    UNKNOWN   {key}:")
                    _print_wrapped(s.get("detail") or "", indent="              ")
            # A stale or incomplete report is UNKNOWN, and UNKNOWN is not a pass.
            if rr_state == rolling_recall.UNKNOWN:
                issues.append("COVERAGE: rolling recall is UNVERIFIED")
            print(f"    measured {rr_doc.get('measured_at')} - a band, not a point, "
                  f"because no editor adjudicated these matches")
    except Exception as exc:
        print(f"    UNKNOWN - could not read the rolling coverage measurement: {exc}")
        issues.append("COVERAGE: measurement unreadable")

    # 3d. PER-COUNTRY PICTURE — what EXISTS to be found, per country.
    #
    # [3c] measures one slice of one country exactly and says nothing about the
    # other 72 in the corpus. The gap that leaves is not "coverage we have not
    # measured yet", it is a claim nobody can defend: for most countries there
    # is NO countable denominator to be complete against, and for many of them
    # that is a fact about the country's law rather than a gap in ours.
    #
    # This prints the shape of that answer — how many countries publish a
    # countable total, how many have a notification regime that publishes
    # nothing, how many have no disclosure regime at all, and how many are
    # REFUSED because the publisher disallows AI agents. It deliberately prints
    # NO percentage: a worldwide rate over a register whose own coverage is the
    # denominator would be quoted as a coverage figure and would flatter.
    #
    # An UNASSESSED country is the one thing here that is a defect on our side,
    # so it is named and it makes the section UNKNOWN.
    print("\n[3d] PER-COUNTRY DISCLOSURE REGIMES  (what exists to be found, by country)")
    try:
        import country_coverage
        cc_doc = country_coverage.load_measurement()
        cc_state, cc_detail = country_coverage.judge(cc_doc)
        if cc_doc is None:
            print("    UNKNOWN - no per-country register has been written yet. What "
                  "exists to be found per country is UNESTABLISHED, not fine.")
            print("              Run: python3 railway/country_coverage.py --write")
            not_provisioned.append("country_coverage (never classified)")
        else:
            t = cc_doc.get("tallies") or {}
            if cc_doc.get("scope_state") == country_coverage.MEASURED:
                print(f"    {cc_doc.get('countries_in_scope')} countries in the corpus, "
                      f"classified against their own disclosure law:")
                for cls, caption in (
                        (country_coverage.REGIME_WITH_AGGREGATE,
                         "publish a countable total -> a denominator exists"),
                        (country_coverage.REGIME_NO_AGGREGATE,
                         "regime exists, no aggregate published -> sampling only"),
                        (country_coverage.NO_REGIME,
                         "no disclosure regime at all -> nothing to be complete against"),
                        (country_coverage.REFUSED,
                         "REFUSED - publisher disallows AI agents, recorded not routed around"),
                        (country_coverage.UNASSESSED,
                         "not yet classified (see the backlog line below)")):
                    n = t.get(cls, 0)
                    if n:
                        print(f"      {n:>3}  {caption}")
                exact = cc_doc.get("exactly_measurable") or []
                if exact:
                    print(f"    a denominator exists in: {', '.join(exact)}")
                    # Said every session, because it is the sentence that stops
                    # the next number from being labelled wrongly.
                    print("    ONLY the US slice supports the word RECALL (Item 2.05 "
                          "enumerates events). The rest are national worker totals, so "
                          "the honest label there is SHARE OF THE OFFICIAL TOTAL.")
                backlog = cc_doc.get("backlog") or []
                if backlog:
                    print(f"    backlog: {len(backlog)} acknowledged, oldest declared "
                          f"{cc_doc.get('backlog_oldest')} - shrinking this is the work")
                for name in (cc_doc.get("undeclared") or [])[:8]:
                    print(f"      UNDECLARED  {name}  (arrived in the data unnoticed)")
                naming = cc_doc.get("per_employer_naming") or []
                if naming:
                    # A DIFFERENT QUESTION from coverage, and the more valuable
                    # one: a total makes coverage measurable, a register makes
                    # layoffs findable. Printed every session so the count of
                    # places on earth that name employers stays in view.
                    print(f"    per-employer registers: {len(naming)} jurisdictions on "
                          f"earth NAME the filing employer - {', '.join(naming)}")
                ledger = cc_doc.get("refusal_ledger") or []
                if ledger:
                    ver = sum(1 for r in ledger if r.get("verified_here"))
                    print(f"    refusal ledger: {len(ledger)} hosts refuse us "
                          f"({ver} re-verified here). Do NOT re-probe or build against "
                          f"them - see REFUSAL_LEDGER in railway/country_coverage.py")
                for dup in cc_doc.get("vocabulary_duplicates") or []:
                    print(f"      VOCABULARY  '{dup['stored']}' stored alongside "
                          f"'{dup['canonical']}' - one country, two spellings")
            else:
                print("    UNKNOWN   the live country scope could not be read:")
                _print_wrapped(cc_doc.get("detail") or "", indent="              ")
            if cc_state == country_coverage.UNKNOWN:
                issues.append("COVERAGE: the per-country register is UNVERIFIED")
                _print_wrapped(cc_detail, indent="              ")
            print(f"    classified {cc_doc.get('measured_at')} - a register of what "
                  f"EXISTS to be found, never a worldwide percentage")
    except Exception as exc:
        print(f"    UNKNOWN - could not read the per-country register: {exc}")
        issues.append("COVERAGE: per-country register unreadable")
    # 3e. COVERAGE OUTSIDE THE US — measured against national denominators.
    #
    # [3c] measures ONE slice of ONE country exactly, and until this section
    # existed everything else was an opinion. "We cover country X well" is not a
    # claim anybody should publish unmeasured, and a goal you cannot measure is
    # a hope.
    #
    # These are counts of collective-redundancy notifications published by the
    # authority that RECEIVES them, so the denominator is the publisher's own
    # universe rather than anything we assembled. Each figure is a BAND: the low
    # end is strict job location, the high end unions employer domicile and
    # therefore counts a global cut whole.
    #
    # It prints NO total and NO average. The denominators are not comparable —
    # Directive 98/59/EC lets every member state pick its own threshold and
    # Taiwan counts plants — and national_denominators.combine() refuses to add
    # two series that count different things. A worldwide percentage here would
    # be exactly the flattering nonsense that refusal exists to prevent.
    print("\n[3e] COVERAGE OUTSIDE THE US  (vs national collective-redundancy totals)")
    try:
        import national_denominators
        nd_doc = national_denominators.load_measurement()
        nd_state, _nd_detail = national_denominators.judge(nd_doc)
        if nd_doc is None:
            print("    UNKNOWN - no national-denominator measurement has been written "
                  "yet. Coverage outside the US is UNMEASURED, not fine.")
            print("              Run: python3 railway/national_denominators.py --write")
            not_provisioned.append("national_denominators (never measured)")
        else:
            for key in nd_doc.get("declared_slices") or []:
                s = (nd_doc.get("slices") or {}).get(key) or {
                    "state": national_denominators.UNKNOWN,
                    "detail": "absent from the report"}
                state = s.get("state")
                country = s.get("country", "?")
                if state == national_denominators.MEASURED:
                    lo, hi = s["confirmed_interval"]
                    print(f"    MEASURED  {country}: {s['coverage_lower']:.1%}"
                          f"-{s['coverage_upper']:.1%} of {s['denominator']:,} "
                          f"{s['unit']} notified  ({s['period']['label']})")
                    print(f"              {s['label']}")
                    print(f"              we hold {s['held_jobs_strict']:,}.."
                          f"{s['held_jobs_any']:,}; Wilson on the low end "
                          f"{lo:.1%}-{hi:.1%} (sampling only — the definitional "
                          f"mismatch is larger)")
                elif state == national_denominators.NOT_MEASURABLE:
                    print(f"    NOT MEASURABLE  {country}: {key}")
                    _print_wrapped(s.get("detail") or "", indent="              ")
                else:
                    print(f"    UNKNOWN   {country}: {key}")
                    _print_wrapped(s.get("detail") or "", indent="              ")
            if nd_state == national_denominators.UNKNOWN:
                issues.append("COVERAGE: national denominators are UNVERIFIED")
            print(f"    measured {nd_doc.get('measured_at')} - bands, never a point, "
                  f"and never summed across countries")
    except Exception as exc:
        print(f"    UNKNOWN - could not read the national denominators: {exc}")
        issues.append("COVERAGE: national denominators unreadable")

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
    print("\n[4b] HELD ALERTS  (raised, not yet delivered by alert-drain.yml)")
    for line in _report_held_alerts():
        print(f"    {line}")
    if _held_alerts_need_a_human():
        issues.append("alerts are held and not being delivered")

    # And the other half of the same question: what is deliberately NOT being
    # said. Operational mail moved off the host on 2026-08-19 and the ledger
    # came with it, so this is readable from a checkout for the first time.
    print("\n[4b2] OPEN ALARMS  (railway/alert_state.json; what is being suppressed)")
    _alarm_lines, _orphaned = _report_open_alarms()
    for line in _alarm_lines:
        print(f"    {line}")
    if _orphaned:
        # A stale record nothing can clear is exactly the shape of thing this
        # report exists to hand to a human. It is cheap to close and it costs a
        # false STILL FAILING email every fortnight until someone does.
        issues.append(f"{_orphaned} unclearable alarm(s) need a reviewed close")

    # And the failures that are deliberately NOT mailed. From 2026-08-20 a
    # pull-request failure on a side branch is ROUTED here instead of to the
    # owner's inbox, and routing is only honest if the routed thing is visible.
    print("\n[4e] ROUTED BRANCH FAILURES  (red in a PR, deliberately not mailed)")
    _routed_lines, _routed_unknown = _routed_branch_failures()
    for line in _routed_lines:
        print(f"    {line}")
    # Deliberately NOT an `issues.append`. A session's own branch being red is
    # not a call for the owner; that is the entire point of routing it here.

    # 4c. The audience. Counts only, never an address.
    print("\n[4c] DIGEST SUBSCRIBERS  (keyed /subscriber-stats; counts only, no addresses)")
    for line in subscriber_lines():
        print(f"    {line}")
    # Can the sender still authenticate? A separate question from how many
    # people are on the list, and the one that was invisible for three days.
    _cred_lines, _cred_bad = digest_credential_lines(health)
    for line in _cred_lines:
        print(f"    {line}")
    if _cred_bad:
        issues.append("the digest relay is refusing our credential")
    # The weekly tier has its own cron since 2026-08-19, so it needs its own
    # liveness answer: the shared digest_mailer row is refreshed by the daily
    # pass every morning and cannot report a weekly slot that stopped.
    _wk_lines, _wk_bad = weekly_digest_lines(health)
    for line in _wk_lines:
        print(f"    {line}")
    if _wk_bad:
        issues.append("the weekly digest slot has not run within its cadence")

    # 4d. Did anything decline to run at all because the host was unreachable?
    #
    # [4] shows red workflows. Until 2026-08-11 a host outage PUT them there:
    # `curl --fail-with-body` against a 504 is a dead run, so a six-minute
    # Bluehost window left "Superset dedup reconciliation" and "Announcement
    # lifecycle review candidates" red with no defect in either, and the red
    # runs fired an alerter that had to reach the same down host to say so.
    # Those calls now DEFER and exit 0 — which is only honest if the deferral is
    # visible somewhere, because a deferral nobody counts is a silently green
    # job. This is that somewhere. PASS / DEFERRED / FAIL are three states.
    print("\n[4d] DEFERRED HOST CALLS  (never reached the host — NOT a pass)")
    for line in _report_deferrals():
        print(f"    {line}")
    if _deferrals_need_a_human():
        issues.append("a job has deferred 3+ times in a row")

    # 5+6. Surfaces to keep current
    print("\n[5] SOURCES PAGE   https://asktherecruiter.com/blog/ai-layoff-tracker/sources/")
    print("      -> must list EXACTLY the live collectors; update on any source add/remove.")
    # [6] used to be two printed sentences telling a human to go and look. The
    # coverage figure it pointed at is the most quotable number the project has
    # and it was the least watched: on 2026-08-12 the comparator side had been
    # re-verified two days earlier while the paragraph carrying the headline
    # percentage was still the one written on 2026-07-27, standing on a
    # denominator that had moved underneath it. A reminder cannot catch that.
    #
    # It still cannot be checked the ordinary way. Half the ratio is competitor
    # data and may not enter the repo, a secret, or any log, so the comparison
    # itself stays manual and local. What CAN be automated is its AGE: a date is
    # not a figure and names nobody. benchmark_freshness.py reads dates out of
    # the local-only file and returns dates — see its header for why that is a
    # structural property and not a promise.
    print("\n[6] BENCHMARK COMPARISON  scratchpad/bm-live.html (LOCAL ONLY, never commit)")
    try:
        bench = benchmark_freshness.check_file()
        print(f"    verdict: {bench.verdict}")
        for line in bench.lines:
            print(f"    {line}")
        if bench.needs_a_human:
            issues.append("the coverage comparison is stale")
    except Exception as exc:  # noqa: BLE001 - never let this block the ritual
        print(f"    UNKNOWN — could not run the freshness check ({exc}).")
        print("    THIS IS NOT A PASS.")
    print("      -> the refresh is MANUAL by design (competitor figures stay off")
    print("         this machine's repo); every table shows ours + theirs.")
    # [1b] proves which VERSION a reader is served. It cannot tell a readable
    # page from one whose paragraphs are 1.06:1, which is exactly what shipped
    # on 2026-08-10. Not run inline: it needs a browser, and this script is
    # stdlib-only and must work anywhere. A red run shows up in [4] on its own.
    print("[7] RENDERED CONTRAST  python3 railway/contrast_audit.py")
    print("      -> what the page RENDERS AS in both themes, not which version")
    print("         it is. Runs daily (Rendered contrast audit) and on deploy.")

    # [8] The stash stack is per-REPOSITORY and every worktree shares it, so a
    # stash made in one agent's worktree is a stash another agent can pop. This
    # repo's own stash@{0} is labelled "popped by accident from a sibling
    # worktree", so that is measured, not hypothetical. CLAUDE.md forbids `git
    # stash`, and `git rebase/pull --autostash` breaks the rule silently — the
    # sibling talent repo collected four that way. It cannot be enforced:
    # rebase.autoStash=false is set locally here, but an explicit --autostash
    # overrides config and no hook can refuse a stash push safely. So it is
    # watched instead, and the verdict names what is IN each entry rather than
    # counting them, because a count gets skimmed.
    print("\n[8] STASH STACK  (shared by every worktree of this repo)")
    try:
        verdict, why, lines = stash_watch.check(str(REPO_ROOT))
        print(f"    verdict: {verdict} — {why}")
        for line in lines:
            print(f"    {line}")
        if verdict in (stash_watch.FAIL, stash_watch.UNKNOWN):
            issues.append("the shared stash stack needs adjudicating")
    except Exception as exc:  # noqa: BLE001 - never let this block the ritual
        print(f"    UNKNOWN — could not read the stash stack ({exc}).")
        print("    THIS IS NOT A PASS.")
        issues.append("the shared stash stack could not be read")

    # 9. IS THERE A COPY OF THE DATA ANYWHERE BUT THE HOST.
    #
    #    Read from the committed baseline, so it answers offline and cannot be
    #    answered by the host it is a backup OF. A backup whose only record of
    #    itself lives on the machine that might be gone is not a backup.
    print("\n[9] OFF-HOST BACKUP  (railway/backup_state.json; weekly)")
    try:
        # Read the file, do NOT import backup_export: that module imports
        # source_health, which imports `requests`, and ops_status is
        # dependency-free on purpose so it runs anywhere at session start.
        import datetime as _dt
        _state_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                    "backup_state.json")
        state = {}
        if _os.path.exists(_state_path):
            with open(_state_path, encoding="utf-8") as _fh:
                state = json.load(_fh)
        if not state:
            print("    UNKNOWN — no export has been recorded yet. That is not a pass:")
            print("    until one lands, wp_alt_layoffs exists only on Bluehost.")
            print("    -> gh workflow run backup-export.yml")
            unverified.append("whether any off-host backup exists")
        else:
            taken = state.get("recorded_at", "?")
            age_days = None
            try:
                taken_at = _dt.datetime.strptime(taken, "%Y-%m-%dT%H:%M:%SZ")
                age_days = (_dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
                            - taken_at).days
            except Exception:  # noqa: BLE001
                pass
            age = f"{age_days}d ago" if age_days is not None else "age unknown"
            print(f"    last export {taken} ({age}), plugin {state.get('plugin_version','?')}")
            print(f"    {state.get('total_rows', 0):,} rows, "
                  f"{state.get('total_bytes', 0) / 1e6:.1f} MB compressed, "
                  f"{state.get('took_seconds', '?')}s")
            for name, entry in sorted((state.get("tables") or {}).items()):
                print(f"      {name:20s} {entry.get('rows', 0):>9,} rows")
            # The job runs weekly, so the ceiling is the cadence plus a miss.
            # A 2-day ceiling on a weekly job is permanent noise that hides the
            # real breakage; 15 days means two runs in a row did not land.
            if age_days is not None and age_days > 15:
                print(f"    STALE — no export in {age_days} days against a weekly cadence.")
                print("    -> docs/RECOVERY.md 'the weekly backup stopped'")
                issues.append("the weekly off-host backup has stopped")
            print("    restore: docs/RECOVERY.md. Subscriber data is NEVER in this artifact.")
    except Exception as exc:  # noqa: BLE001 - never let this block the ritual
        print(f"    UNKNOWN — could not read the backup baseline ({exc}).")
        print("    THIS IS NOT A PASS.")
        unverified.append("whether the off-host backup is current")

    # [10] A row whose citation cannot be verified is the one defect this
    #      product cannot absorb, and until now the only archive signal any
    #      session saw was the CADENCE promise (data_integrity's
    #      archive_recheck_cadence, which surfaces in [4]). "Are we re-checking
    #      on time?" and "what share of our citations actually has a permanent
    #      copy?" are different questions, and only the first was on any
    #      dashboard — the same source-health-is-not-data-integrity split this
    #      repo has already been bitten by once.
    #
    #      DELIBERATELY NOT AN ALARM. It appends to neither `issues` nor
    #      `unverified`, because the steady state here IS a backlog: the
    #      un-archivable tail is re-checked every ALT_ARCHIVE_RECHECK_DAYS
    #      forever and never given up on, so a non-zero gap is the system
    #      working, not a fault. An unreachable endpoint prints UNKNOWN and
    #      stays silent rather than manufacturing an action item.
    print("\n[10] SOURCE ARCHIVE COVERAGE  (public /archive-coverage; NOT an alarm)")
    try:
        with _get(f"{BASE}/wp-json/layoffs/v1/archive-coverage"
                  f"?cb={uuid.uuid4().hex[:8]}") as _resp:
            cov = json.load(_resp)
        total = int(cov.get("distinct_source_urls") or 0)
        archived = int(cov.get("archived") or 0)
        pending = int(cov.get("pending") or 0)
        unavailable = int(cov.get("unavailable") or 0)
        if total <= 0:
            raise ValueError(f"no denominator in /archive-coverage: {cov!r}")
        gap = total - archived
        print(f"    {100.0 * archived / total:.1f}% archived — {archived:,} of {total:,} "
              f"distinct cited source URLs have a permanent Wayback copy")
        # Split the missing set by CAUSE. "Never attempted" and "attempted and
        # failed" are different problems with different fixes, and a merged
        # count hides which one you have.
        print(f"    the {gap:,} without one, by CAUSE:")
        print(f"      attempted, retrying   {pending:>7,}  'pending' — re-tried every "
              f"72h, up to 5 rounds")
        print(f"      attempted, exhausted  {unavailable:>7,}  'unavailable' — 5 failed "
              f"rounds; re-checked every")
        print(f"                                     {cov.get('recheck_days', '?')} days "
              f"FOREVER, never given up on")
        # `queued` is derived and CLAMPED at zero server-side, so it cannot be
        # quoted as a clean "nothing is unattempted". The archive index keeps
        # rows for URLs whose layoff rows were later purged or re-sourced; those
        # orphans inflate the status tallies above the live denominator and the
        # clamp then hides however much real queue sits underneath. Say that,
        # rather than reporting a reassuring zero we cannot stand behind.
        queued = cov.get("queued")
        orphans = (archived + pending + unavailable) - total
        if orphans > 0:
            print(f"      never attempted       {'UNKNOWN':>7}  reads {queued}, but the index "
                  f"holds ~{orphans:,} orphan row(s)")
            print("                                     for purged/re-sourced URLs and the "
                  "figure is")
            print("                                     clamped at 0, so a small queue "
                  "cannot be ruled out")
        else:
            print(f"      never attempted       {int(queued or 0):>7,}  no archive row yet; "
                  f"the next daily run takes it")
        oldest = cov.get("oldest_unarchived_checked_at")
        print(f"    oldest un-archived attempt: {oldest or 'none'} "
              f"(pool {int(cov.get('unarchived_live') or 0):,})")
        print("    -> FORWARD coverage is the DAILY archive-backfill (05:25 UTC), which")
        print("       drains every newly cited URL, brand-new rows included, with no")
        print("       ingest-path change. archive-sources.yml (weekly) is a DIFFERENT")
        print("       job: the ~54 WARN source DOCUMENTS, re-captured because their")
        print("       CONTENT rolls. It is not the path any per-row link waits on.")
        print("    -> the cadence PROMISE is data_integrity's archive_recheck_cadence "
              "and reports in [4].")
    except Exception as exc:  # noqa: BLE001 - never let this block the ritual
        if _is_egress_block(exc):
            print(f"    UNKNOWN — /archive-coverage unreachable from this environment "
                  f"({exc}).")
            print("    Likely an ENVIRONMENT BLOCK, not an archive outage. Not a pass, "
                  "and not a fault.")
        else:
            print(f"    UNKNOWN — could not read /archive-coverage ({exc}).")
            print("    THIS IS NOT A PASS. It is also not an action item on its own.")

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
    if not_provisioned and not egress_blocked:
        print(f"NOT WATCHING YET: {len(not_provisioned)} data-integrity guard(s) are armed in "
              f"the code but have nothing to read")
        print(f"    ({', '.join(not_provisioned)}).")
        print("    Either the deployed plugin predates the field the guard reads (wait for a")
        print("    green 'Deploy WordPress plugin' run, then re-check), or the first baseline")
        print("    has not been written (run `python3 railway/data_integrity.py")
        print("    --record-baseline`, or wait for data-integrity.yml at 17:30 UTC).")
        print("    THIS IS NOT A PASS. Until it resolves, nothing is watching that number.")
        return 3
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
