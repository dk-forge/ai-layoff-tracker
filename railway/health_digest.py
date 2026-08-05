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
    "edgar": 2, "news_catchup": 9, "gdelt": 2, "warn_us": 3, "eurofound_erm": 3,
    "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4,
    "press_releases": 3, "warn_hi_ocr": 3, "warn_mazowieckie": 3,
    "data_integrity": 2, "warn_quebec": 3, "federal_rif": 35, "digest_mailer": 3,
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


def _email_alert(stale, degraded, integrity_failed=(), subscribers=""):
    """POST an actionable breakage email to the owner via the site's /alert."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    names = [s for s, _, _ in stale] + [s for s, _ in degraded]
    integrity_failed = list(integrity_failed)
    if integrity_failed:
        # Lead the subject line with it. A wrong published number outranks a
        # collector that stopped: one is misinformation already served, the
        # other is coverage we have not collected yet.
        subject = (f"WRONG NUMBER LIVE: {len(integrity_failed)} data-integrity check(s) failing"
                   + (f" (+{len(names)} source issue(s))" if names else ""))
    else:
        subject = f"{len(names)} data source(s) need attention: {', '.join(names[:4])}"
    lines = ["The weekly health check found collectors that stopped or degraded.\n"]
    if integrity_failed:
        lines = ["The weekly health check found the live site publishing a number that "
                 "fails a data-integrity guard.\n"]
        for r in integrity_failed:
            lines.append(f"DATA INTEGRITY — {r.inv.label}: {r.detail}")
        lines.append(
            "\nThis means a published figure is WRONG right now, not merely missing. "
            "Paste this into a Claude Code session in the ai-layoff-tracker repo:\n"
            f'  "railway/data_integrity.py reports these live invariants failing: '
            f'{", ".join(r.inv.key for r in integrity_failed)}. Run python3 '
            'railway/data_integrity.py, then follow docs/RUNBOOK.md \'a data-integrity '
            'check is failing\'."\n')
    for s, a, m in stale:
        lines.append(f"STALE — {s}: last reported {a} days ago (expected within {m}). It likely stopped running.")
    for s, d in degraded:
        lines.append(f"DEGRADED — {s}: {str(d)[:160]}")
    # The source-repair paste-line only makes sense when a SOURCE is implicated.
    # An integrity-only email already carries its own instruction above, and
    # appending "flagged these sources: " with an empty list is the kind of
    # nonsense that teaches an owner to stop reading these.
    if names:
        lines.append(
            "\nWhat to do: open a Claude Code session in the ai-layoff-tracker repo and paste this line:\n"
            f'  "The health digest flagged these sources: {", ".join(names)}. '
            'For each, find its collector in railway/ (or railway/sources/), check whether the '
            'third-party site changed, and fix the parser; a scraper returning 0 usually means the '
            'page layout changed. Then dry-run it to confirm."\n'
            "\nMost breakages are a government/state site changing its page layout — the fix is a "
            "quick re-recon of that one scraper.")
    # The audience, in one line, counts only. It rides along with whatever else
    # went wrong so the owner sees it without opening a dashboard.
    if subscribers:
        lines.append("\n" + subscribers)
    body = "\n".join(lines)
    try:
        requests.post(f"{site}/wp-json/layoffs/v1/alert",
                      json={"subject": subject, "body": body},
                      headers={"X-Layoff-API-Key": key, "User-Agent": UA["User-Agent"]},
                      timeout=25)
        print("alert email sent to owner")
    except Exception as exc:
        print(f"alert email failed: {exc}")


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
    ok, degraded, stale = 0, [], []
    for src, info in health.items():
        if not isinstance(info, dict):
            continue
        status = info.get("status")
        age = _age_days(info.get("checked_at"), now)
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
        print(f"  ::warning:: DATA INTEGRITY could not be checked ({exc}) — state UNKNOWN, not ok")

    subscribers = subscriber_line()
    print(f"SUBSCRIBERS: {subscribers}")

    print(f"HEALTH DIGEST: {ok} ok · {len(degraded)} degraded · {len(stale)} stale")
    for s, d in degraded:
        print(f"  ::warning:: DEGRADED {s}: {str(d)[:120]}")
    for s, a, m in stale:
        print(f"  ::error:: STALE {s}: last reported {a}d ago (expected <= {m}d) — collector may have stopped")

    integrity_failed = list(integrity.failed) if integrity is not None else []
    detail = f"{ok} ok, {len(degraded)} degraded, {len(stale)} stale"
    if integrity is not None and integrity.verdict != "pass":
        detail += " | " + integrity.one_line()
    if degraded:
        detail += " | degraded: " + ", ".join(s for s, _ in degraded)
    if stale:
        detail += " | STALE: " + ", ".join(s for s, _, _ in stale)

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
                "health_digest", "degraded" if stale else "ok", ok, detail)
        except Exception as exc:
            print(f"(digest health post skipped: {exc})")
        # Email ONLY on real breakage, with a ready-to-paste fix instruction.
        if stale or real_degraded or integrity_failed:
            _email_alert(stale, real_degraded, integrity_failed, subscribers)

    # A STALE source is the real silent failure — fail the run loudly so the red
    # workflow is the alert. Degraded-only (transient) does not fail the digest.
    # A FAILING data-integrity check is at least as serious: it is a wrong number
    # already published, not coverage we might miss, so it fails the run too.
    if stale or integrity_failed:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
