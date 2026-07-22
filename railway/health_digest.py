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
    "press_releases": 3, "warn_hi_ocr": 3,
}
DEFAULT_MAX_AGE = 10
# Sources whose 0/degraded is expected-by-design or transient, so a DEGRADED
# status alone should not be treated as an incident (still shown in the digest).
SOFT_DEGRADED = {"gdelt_historical"}  # historical recovery is rate-limit prone


# States with no public WARN register: a custom scraper returning 0 for them is
# correct, not drift, so a drift-detail naming ONLY these is benign.
_BENIGN_STATES = {"AR", "WY", "NH"}  # HI now flows via the OCR importer; NV via the Bluehost mirror


def _benign_degraded(detail):
    import re
    # Two-letter codes named in the drift detail. Benign ONLY if every code is a
    # no-public-register state; any other code (a real state, or "AI") -> alert.
    codes = re.findall(r"\b([A-Z]{2})\b", str(detail))
    return bool(codes) and all(c in _BENIGN_STATES for c in codes)


def _email_alert(stale, degraded):
    """POST an actionable breakage email to the owner via the site's /alert."""
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        return
    names = [s for s, _, _ in stale] + [s for s, _ in degraded]
    subject = f"{len(names)} data source(s) need attention: {', '.join(names[:4])}"
    lines = ["The weekly health check found collectors that stopped or degraded.\n"]
    for s, a, m in stale:
        lines.append(f"STALE — {s}: last reported {a} days ago (expected within {m}). It likely stopped running.")
    for s, d in degraded:
        lines.append(f"DEGRADED — {s}: {str(d)[:160]}")
    lines.append(
        "\nWhat to do: open a Claude Code session in the ai-layoff-tracker repo and paste this line:\n"
        f'  "The health digest flagged these sources: {", ".join(names)}. '
        'For each, find its collector in railway/ (or railway/sources/), check whether the '
        'third-party site changed, and fix the parser; a scraper returning 0 usually means the '
        'page layout changed. Then dry-run it to confirm."\n'
        "\nMost breakages are a government/state site changing its page layout — the fix is a "
        "quick re-recon of that one scraper.")
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
        # Email ONLY on real breakage, with a ready-to-paste fix instruction.
        # Drop benign flags first (Hawaii has no WARN register by design, so its
        # custom scraper is *expected* to return 0) so the alert never cries wolf.
        real_degraded = [(s, d) for s, d in degraded if not _benign_degraded(d)]
        if stale or real_degraded:
            _email_alert(stale, real_degraded)

    # A STALE source is the real silent failure — fail the run loudly so the red
    # workflow is the alert. Degraded-only (transient) does not fail the digest.
    if stale:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
