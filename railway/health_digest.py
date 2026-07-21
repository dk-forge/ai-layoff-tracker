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
MAX_AGE_DAYS = {
    "edgar": 2, "newsapi": 2, "gdelt": 2, "warn_us": 3, "eurofound_erm": 3,
    "supplemental_news": 3, "company_watchlist": 4, "dedupe_llm": 4,
    "press_releases": 3,
}
DEFAULT_MAX_AGE = 10
# Sources whose 0/degraded is expected-by-design or transient, so a DEGRADED
# status alone should not be treated as an incident (still shown in the digest).
SOFT_DEGRADED = {"gdelt_historical"}  # historical recovery is rate-limit prone


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
        if age is not None and age > maxage:
            stale.append((src, round(age, 1), maxage))
        elif status == "degraded" and src not in SOFT_DEGRADED:
            degraded.append((src, info.get("detail", "")))
        else:
            ok += 1

    print(f"HEALTH DIGEST: {ok} ok · {len(degraded)} degraded · {len(stale)} stale")
    for s, d in degraded:
        print(f"  ::warning:: DEGRADED {s}: {str(d)[:120]}")
    for s, a, m in stale:
        print(f"  ::error:: STALE {s}: last reported {a}d ago (expected <= {m}d) — collector may have stopped")

    detail = f"{ok} ok, {len(degraded)} degraded, {len(stale)} stale"
    if degraded:
        detail += " | degraded: " + ", ".join(s for s, _ in degraded)
    if stale:
        detail += " | STALE: " + ", ".join(s for s, _, _ in stale)

    if not DRY and os.environ.get("WP_API_KEY"):
        try:
            from source_health import report_source_health
            report_source_health("health_digest", "degraded" if (stale or degraded) else "ok", ok, detail)
        except Exception as exc:
            print(f"(digest health post skipped: {exc})")

    # A STALE source is the real silent failure — fail the run loudly so the red
    # workflow is the alert. Degraded-only (transient) does not fail the digest.
    if stale:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
