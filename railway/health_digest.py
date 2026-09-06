"""Weekly source-health digest — the autonomy tripwire.

Reads the public source-health ledger and flags any collector that is DEGRADED
or STALE (has not reported within its expected cadence — i.e. it silently
stopped). This is the last line of defence for unattended operation: a scraper
whose site changed and now returns nothing gets surfaced within a week instead
of bleeding coverage indefinitely.

Detection, not auto-repair: a broken third-party parser can't be fixed without
a human, so the honest goal is FAST, LOUD detection. Reports the digest to the
health ledger and exits non-zero when a source has gone stale so the workflow
turns red.

Env: WP_SITE_URL (required), WP_API_KEY (to post the digest; optional for a
read-only run), HEALTH_DIGEST_DRY=1.
"""
import os
import sys
from datetime import datetime, timezone

import requests

import opsmail
from source_value import (escalation_line, repair_brief, routes_for,
                          zero_is_outage)

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
DRY = os.environ.get("HEALTH_DIGEST_DRY", "").lower() in {"1", "true", "yes"}

# Max age (days) before a source counts as STALE, matched to its cadence. A
# source not listed here uses DEFAULT_MAX_AGE. Discovery-only probes and
# low-priority backfills are given a longer leash; the daily live collectors a
# short one, because those going quiet is real coverage loss.
# A ceiling MUST match the job's real cadence — "newsapi" sat at 2 days here
# while the only job still posting under that id ran WEEKLY, so it read stale
# 5 days out of 7 forever (see news_catchup.py). Renamed to news_catchup @ 9d.
# federal_rif is the same defect one rung down: it is imported by a MONTHLY job
# (federal-rif-import.yml, the 6th of each month) and nothing else posts under
# that id, but it was missing here and fell through to DEFAULT_MAX_AGE = 10. So
# from day 11 of every month until the next run it read STALE — ~2 weeks in 3,
# every month, turning the weekly digest red and mailing the owner a breakage
# that never happened. ops_status.py already had it right at 35; this file did
# not, and the two comments each claimed to match the other.
# test_source_registry_parity now asserts the two maps agree, so the next
# divergence fails CI instead of becoming background noise.
MAX_AGE_DAYS = {
    "edgar": 2, "news_catchup": 9, "gdelt": 2, "regional_feeds": 2,
    "national_feeds": 2,
    "warn_us": 3, "eurofound_erm": 3,
    "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4,
    "press_releases": 3, "warn_hi_ocr": 3, "warn_mazowieckie": 3,
    "data_integrity": 2, "warn_quebec": 3, "federal_rif": 35, "digest_mailer": 3,
    # digest_weekly: the WEEKLY digest slot, which got its own cron on
    # 2026-08-19 (7:30 AM ET Mondays). DERIVATION: 7 days between two healthy
    # runs + 2 days of slack, so ONE missed Monday is reported on the Wednesday
    # rather than a healthy 6-day-old row reading STALE for most of every week.
    # `digest_mailer` cannot stand in for this: the daily slot stamps that row
    # every morning, so it is green whatever the weekly tier does. Mirrored by
    # ops_status.WEEKLY_DIGEST_MAX_AGE_DAYS, which reads the same row.
    "digest_weekly": 9,
    # digest_monthly: the MONTHLY digest slot, armed 2026-09-06 (9:00 AM ET on
    # the 1st). 31 (longest month) + 4 days of slack, the source_audit
    # derivation. Mirrored by ops_status.MONTHLY_DIGEST_MAX_AGE_DAYS.
    "digest_monthly": 35,
    # source_audit: MONTHLY (source-verification-audit.yml, `0 13 1 * *`), and
    # nothing else posts under that id. 31 (longest month) + 4 days of slack, so
    # one missed run is reported on day 35 instead of a healthy 31-day-old run
    # reading STALE for two weeks in every three. Same derivation as federal_rif.
    "source_audit": 35,
}
DEFAULT_MAX_AGE = 10
# Sources whose 0/degraded is expected-by-design or transient, so a DEGRADED
# status alone should not be treated as an incident (still shown in the digest).
SOFT_DEGRADED = {"gdelt_historical", "source_audit"}  # historical recovery is rate-limit prone


# States with no public WARN register: a custom scraper returning 0 for them is
# correct, not drift, so a drift-detail naming ONLY these is benign.
_BENIGN_STATES = {"AR", "WY", "NH", "OK"}  # OK publishes no headcounts; 0 is correct (F23)  # HI now flows via the OCR importer; NV via the Bluehost mirror


def _benign_degraded(detail):
    import re
    # Two-letter codes named in the drift detail. Benign ONLY if every code is a
    # no-public-register state; any other code (a real state, or "AI") -> alert.
    codes = re.findall(r"\b([A-Z]{2})\b", str(detail))
    return bool(codes) and all(c in _BENIGN_STATES for c in codes)


def subscriber_line():
    """One line about the digest audience, for the owner's weekly email.

    COUNTS ONLY. The keyed /subscriber-stats route returns no address in any
    field or error path, and this formats numbers from it.

    An install with no subscriber table, or a run that cannot reach the route,
    says UNKNOWN. It must never say 0: "nobody subscribed" and "we could not
    see" are different facts, and printing the first when the second is true is
    a wrong number in the owner's inbox. That distinction is the most repeated
    lesson in this codebase; do not simplify it away with `or 0`.
    """
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return ("Subscribers UNKNOWN: no site URL or API key in this run, so the stats "
                "route was not called. This is not a zero.")
    try:
        r = requests.get(f"{site}/wp-json/layoffs/v1/subscriber-stats",
                         headers={"X-Layoff-API-Key": key, "User-Agent": UA["User-Agent"]},
                         timeout=25)
        data = r.json() if r.status_code == 200 else {}
    except Exception as exc:
        return f"Subscribers UNKNOWN: could not read the stats route ({exc}). This is not a zero."
    if not isinstance(data, dict) or not data.get("available"):
        reason = (data or {}).get("reason") or "the endpoint reported no data"
        return f"Subscribers UNKNOWN: {reason}. This is not a zero."

    total = (data.get("confirmed") or {}).get("total")
    new = data.get("confirmed_last_7_days")
    last = data.get("last_send")
    if not last:
        return (f"Subscribers {total} (+{new} this week), no digest sent yet, "
                f"so no clicks or unsubscribes to report.")
    clicks = "UNKNOWN" if last.get("clicks") is None else last.get("clicks")
    unsub = "UNKNOWN" if last.get("unsubscribes_48h") is None else last.get("unsubscribes_48h")
    return (f"Subscribers {total} (+{new} this week), last digest sent to "
            f"{last.get('recipients')}, {clicks} clicks, {unsub} unsubscribed.")


def _dark_source_lines():
    """The committed dark-source ledger, as email-ready blocks.

    Read from railway/source_state.json rather than re-derived, so the digest,
    ops_status and the import that wrote it all say the same thing. A collector
    that answers with a frozen archive is invisible to every count-based check
    in this file, which is why it has its own ledger at all.
    """
    try:
        import source_alert
        import source_freshness
        rows = source_freshness.broken(source_freshness.load_ledger())
    except Exception as exc:                                   # noqa: BLE001
        return [f"(the dark-source ledger could not be read: {exc} - UNKNOWN, "
                f"not a clean bill of health)"], []
    if not rows:
        return [], []
    out = ["\nThese collectors run and answer, but have published NOTHING NEW, "
           "on evidence strong enough to call a break (p below 0.01 against "
           "their own recent filing rate). Every count-based check reads them "
           "as healthy:\n"]
    for r in rows:
        out.append(source_alert.block(r))
        out.append("")
    return out, rows


def _never_reported_lines(health):
    """Collectors declared on the health page that have NO health row at all.

    Absent is the state nothing in this repo could see: it does not render
    green, it does not render. This is the only place that says the number.
    """
    try:
        import source_inventory
        missing = source_inventory.never_reported(health)
    except Exception as exc:                                   # noqa: BLE001
        return [f"(the source inventory could not be built: {exc} - UNKNOWN)"], []
    if not missing:
        return [], []
    return (["\n" + f"{len(missing)} declared collector(s) have NEVER reported "
             f"health at all: {', '.join(missing)}.",
             "  Absent is not green. Either they do not run, or they run and "
             "never report. Both need a look.\n"], list(missing))


def _email_alert(stale, degraded, integrity_failed=(), zero_outage=(), subscribers="",
                 dark_lines=(), never_lines=()):
    """Mail the owner an actionable breakage report, through Resend.

    THIS USED TO GO THROUGH `/alert` ON THE WORDPRESS HOST, which is the host
    the digest is reporting about, and it shared the subscriber relay's 300 a
    day free tier with the reader digest. Both were wrong for the same reason
    in two different ways: a weekly report on whether the machine is healthy
    should not need the machine to be healthy, and a bad afternoon of alarms
    should not be able to eat the allowance the readers depend on. Operational
    mail is Resend now; the subscriber digest keeps Brevo and is untouched.
    """
    if not opsmail.configured():
        print("RESEND_API_KEY is not set, so the health digest email was NOT sent")
        return
    names = [s for s, _, _ in stale] + [s for s, _ in degraded]
    zero_outage = list(zero_outage)
    integrity_failed = list(integrity_failed)
    if zero_outage and not integrity_failed:
        # A declared-never-zero collector at zero outranks a generic degrade:
        # it is a source we have gone BLIND on, and the subject line should say
        # which one rather than making the owner open a dashboard to find out.
        subject = ("SOURCE RETURNING NOTHING: "
                   + ", ".join(s for s, _ in zero_outage)
                   + (f" (+{len(names) - len(zero_outage)} other source issue(s))"
                      if len(names) > len(zero_outage) else ""))
    elif integrity_failed:
        # Lead the subject line with it. A wrong published number outranks a
        # collector that stopped: one is misinformation already served, the
        # other is coverage we have not collected yet.
        subject = (f"WRONG NUMBER LIVE: {len(integrity_failed)} data-integrity check(s) failing"
                   + (f" (+{len(names)} source issue(s))" if names else ""))
    else:
        subject = f"{len(names)} data source(s) need attention: {', '.join(names[:4])}"
    lines = ["The weekly health check found collectors that stopped or degraded.\n"]
    lines.extend(dark_lines)
    lines.extend(never_lines)
    if integrity_failed:
        lines = ["The weekly health check found the live site publishing a number that "
                 "fails a data-integrity guard.\n"]
        for r in integrity_failed:
            lines.append(f"DATA INTEGRITY {r.inv.label}: {r.detail}")
        lines.append(
            "\nThis means a published figure is WRONG right now, not merely missing. "
            "Paste this into a Claude Code session in the ai-layoff-tracker repo:\n"
            f'  "railway/data_integrity.py reports these live invariants failing: '
            f'{", ".join(r.inv.key for r in integrity_failed)}. Run python3 '
            'railway/data_integrity.py, then follow docs/RUNBOOK.md \'a data-integrity '
            'check is failing\'."\n')
    # A collector at zero goes ABOVE the stale/degraded list, with what it is
    # worth spelled out. "warn_quebec degraded" is a status; "the only named
    # layoff register in Canada is returning nothing" is a decision.
    for s, d in zero_outage:
        lines.append("\n" + escalation_line(s, d))
        lines.append(f"  last detail: {str(d)[:160]}")
        lines.append("  " + repair_brief(s).replace("\n", "\n  "))
    for s, a, m in stale:
        lines.append(f"STALE {s}: last reported {a} days ago (expected within {m}). It likely stopped running.")
    for s, d in degraded:
        lines.append(f"DEGRADED {s}: {str(d)[:160]}")
    # The source-repair paste-line only makes sense when a SOURCE is implicated.
    # An integrity-only email already carries its own instruction above, and
    # appending "flagged these sources: " with an empty list is the kind of
    # nonsense that teaches an owner to stop reading these.
    if names:
        # The paste-line now carries the candidate ROUTES for each named source,
        # so the next session starts with somewhere to look instead of a shrug.
        # A repair that begins "the parser is broken" wastes the first hour when
        # the parser is usually fine and discovery is what died.
        routes = "; ".join(
            f"for {s}: " + " OR ".join(routes_for(s)) for s in dict.fromkeys(names))
        lines.append(
            "\nWhat to do: open a Claude Code session in the ai-layoff-tracker repo "
            "and paste this line:\n"
            f'  "The health digest flagged these sources: {", ".join(names)}. '
            "Find each collector in railway/ or railway/sources/. "
            "Check DISCOVERY before the parser. "
            "A scraper returning 0 has usually lost the step that finds its documents, "
            "not the step that reads them. "
            f"Candidate routes to try: {routes}. "
            'Then dry-run it against the totals the source declares for itself."\n'
            "\nMost breakages are a government site changing its layout, or one scraped "
            "index page that stopped answering. Prefer a route that needs no HTML at all.")
    # The audience, in one line, counts only. It rides along with whatever else
    # went wrong so the owner sees it without opening a dashboard.
    if subscribers:
        lines.append("\n" + subscribers)
    body = "\n".join(lines)
    ok, note, _transient = opsmail.send(subject, body)
    print(f"health digest email: {note}")


def _age_days(checked_at, now):
    if not checked_at:
        return None
    try:
        dt = datetime.fromisoformat(str(checked_at).replace("Z", "+00:00"))
        return (now - dt).total_seconds() / 86400.0
    except Exception:
        return None


def main():
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    try:
        r = requests.get(f"{SITE}/wp-json/layoffs/v1/source-health", headers=UA, timeout=40)
        health = r.json() if r.status_code == 200 else {}
    except Exception as exc:
        print(f"could not read source-health: {exc}")
        return 1
    if not isinstance(health, dict) or not health:
        print("source-health ledger empty or unexpected shape")
        return 1

    now = datetime.now(timezone.utc)
    ok, degraded, stale, zero_outage = 0, [], [], []
    for src, info in health.items():
        if not isinstance(info, dict):
            continue
        status = info.get("status")
        age = _age_days(info.get("checked_at"), now)
        # A collector that RAN and returned nothing, where returning nothing is
        # declared impossible for that source (source_value.py). This is checked
        # independently of `status`, because the whole failure mode is a source
        # that reports itself "ok" while producing no rows -- the staleness
        # clock cannot see that at all, since the collector is running fine.
        if status not in ("retired", "running") and zero_is_outage(src):
            try:
                entries = int(info.get("entries") or 0)
            except (TypeError, ValueError):
                entries = 0
            if entries == 0:
                zero_outage.append((src, info.get("detail", "")))
        maxage = MAX_AGE_DAYS.get(src, DEFAULT_MAX_AGE)
        if status == "retired":
            ok += 1            # deliberately stopped; real old timestamp is expected
        elif age is not None and age > maxage:
            stale.append((src, round(age, 1), maxage))
        elif status == "degraded" and src not in SOFT_DEGRADED:
            degraded.append((src, info.get("detail", "")))
        else:
            ok += 1

    # LIVE DATA INTEGRITY — "did the collectors run?" is not "is the data right?".
    #
    # WHY THIS IS HERE AND WHY IT IS NOT ENOUGH ON ITS OWN. This digest runs
    # MONDAYS 12:00 UTC. A live data regression (a company suddenly reading
    # 4,000 jobs too high because a news row started stacking on its WARN
    # notices) misleads every reader of the tracker, the press page and the API
    # from the moment it lands — up to SEVEN DAYS before this email goes out.
    # Weekly is the right cadence for "a scraper quietly died"; it is far too
    # slow for "we are publishing a wrong number right now".
    #
    # So this is the BACKSTOP for an unattended week, deliberately not the
    # primary alarm. The fast paths are, in order: ops_status.py section [3],
    # run at the top of every session; the daily data-integrity.yml run; and
    # tests/test_dedup_live.py on every push. Do not move this signal to the
    # digest alone. It is included here only so the owner sees it in the inbox
    # without reading CI — requirement 4 of the 2026-07-30 build.
    integrity = None
    try:
        from data_integrity import check_all
        integrity = check_all()
        print(f"DATA INTEGRITY: {integrity.one_line()}")
        for r in integrity.failed:
            print(f"  ::error:: DATA INTEGRITY {r.inv.key}: {r.detail}")
        for r in integrity.unknown:
            print(f"  ::warning:: DATA INTEGRITY {r.inv.key} NOT VERIFIED: {r.detail}")
    except Exception as exc:
        print(f"  ::warning:: DATA INTEGRITY could not be checked ({exc}): state UNKNOWN, not ok")

    # MEASURED COVERAGE, carried in the digest for one reason: this is the
    # figure the owner is asked for in public ("what percentage do you cover?"),
    # and until 2026-08-17 the only answer in the repo was a hand-maintained
    # file that had been stale for 24 days. A number nobody sees on a schedule
    # is a number that gets re-derived from memory at the moment it is quoted.
    #
    # It is REPORTED here and never alarmed on. The invariant does not carry a
    # floor (the denominator moves every month, so a fall can be a quiet quarter
    # of filings), and adding one to the digest would be a floor by the back
    # door. A band with its denominator, or an honest UNKNOWN.
    try:
        import rolling_recall
        rr_doc = rolling_recall.load_measurement()
        rr_state, rr_detail = rolling_recall.judge(rr_doc)
        print(f"COVERAGE: {rr_state.upper()} — {rr_detail}")
    except Exception as exc:
        print(f"  ::warning:: COVERAGE could not be read ({exc}): UNKNOWN, not ok")

    subscribers = subscriber_line()
    print(f"SUBSCRIBERS: {subscribers}")

    print(f"HEALTH DIGEST: {ok} ok · {len(degraded)} degraded · {len(stale)} stale"
          + (f" · {len(zero_outage)} returning NOTHING" if zero_outage else ""))
    for s, d in zero_outage:
        print(f"  ::error:: {escalation_line(s, d)}")
        for line in repair_brief(s).splitlines():
            print(f"      {line}")
    for s, d in degraded:
        print(f"  ::warning:: DEGRADED {s}: {str(d)[:120]}")
    for s, a, m in stale:
        print(f"  ::error:: STALE {s}: last reported {a}d ago (expected <= {m}d): collector may have stopped")

    integrity_failed = list(integrity.failed) if integrity is not None else []
    dark_lines, dark_rows = _dark_source_lines()
    never_lines, never_missing = _never_reported_lines(health)
    for _line in dark_lines + never_lines:
        for _sub in str(_line).splitlines():
            if _sub.strip():
                print(f"  {_sub}")
    detail = f"{ok} ok, {len(degraded)} degraded, {len(stale)} stale"
    if dark_rows:
        detail += f" | DARK (publishing nothing new): " + ", ".join(
            r["key"] for r in dark_rows)
    if never_missing:
        detail += f" | NEVER REPORTED: " + ", ".join(never_missing)
    if integrity is not None and integrity.verdict != "pass":
        detail += " | " + integrity.one_line()
    if degraded:
        detail += " | degraded: " + ", ".join(s for s, _ in degraded)
    if stale:
        detail += " | STALE: " + ", ".join(s for s, _, _ in stale)
    if zero_outage:
        detail += " | RETURNING NOTHING: " + ", ".join(s for s, _ in zero_outage)

    # Drop benign flags BEFORE anything is signalled: a state with no public
    # WARN register returning 0 is correct, not a breakage.
    real_degraded = [(s, d) for s, d in degraded if not _benign_degraded(d)]

    if not DRY and os.environ.get("WP_API_KEY"):
        try:
            from source_health import report_source_health
            # The digest's OWN status describes whether the DIGEST ran, not what
            # it found. Marking itself degraded because another collector is
            # degraded double-counted one problem as two on ops_status and the
            # health page, and read as "the digest is broken" when it had just
            # done its job (2026-07-28: warn_us degraded -> health_digest
            # degraded -> two amber lights for one issue). A genuinely stale
            # collector still escalates here, since that means data is missing.
            report_source_health(
                "health_digest", "degraded" if (stale or zero_outage) else "ok",
                ok, detail)
        except Exception as exc:
            print(f"(digest health post skipped: {exc})")
        # Email ONLY on real breakage, with a ready-to-paste fix instruction.
        # A DARK source and a NEVER-REPORTED one are breakage too, and neither
        # could reach this email before: a dark collector is degraded only if
        # the freshness check caught it, and a collector with no health row at
        # all is in none of the lists above by definition.
        if (stale or real_degraded or integrity_failed or zero_outage
                or dark_rows or never_missing):
            _email_alert(stale, real_degraded, integrity_failed, zero_outage,
                         dark_lines=dark_lines, never_lines=never_lines,
                         subscribers=subscribers)

    # A STALE source is the real silent failure — fail the run loudly so the red
    # workflow is the alert. Degraded-only (transient) does not fail the digest.
    # A FAILING data-integrity check is at least as serious: it is a wrong number
    # already published, not coverage we might miss, so it fails the run too.
    #
    # A collector RETURNING NOTHING joins them, and it is the case the other two
    # cannot see: it runs on schedule (so never stale) and it may even report
    # itself ok (so never degraded), while producing no rows at all. warn_quebec
    # sat exactly there and only ever earned an amber light, which is why it was
    # still broken days later. Only sources DECLARED never-legitimately-zero in
    # source_value.py reach here, so a genuinely quiet week cannot redden this.
    if stale or integrity_failed or zero_outage:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
