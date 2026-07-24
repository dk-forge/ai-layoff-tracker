"""Low-balance early warning for the OpenRouter account.

The whole LLM pipeline (extraction, industry/role/reason classification, tips,
self-audit) silently stalls the moment OpenRouter credits hit zero. That is
exactly what happened once, unnoticed, until jobs had been failing for a while.
This is the cheap tripwire that turns "discovered it ran dry" into "warned in
time": a daily read of the account balance that emails the owner (via the same
keyed /alert endpoint the health digest uses) while the balance is low.

Read-only, no LLM calls, ~0 cost. Never raises: a monitoring job must not page
the owner about its own failure. Env: OPENROUTER_API_KEY (already a GitHub
secret), WP_SITE_URL, WP_API_KEY, ALERT_THRESHOLD (default 10 USD).
"""
import json
import os
import sys
import urllib.request

BASE = "https://openrouter.ai/api/v1"
SITE = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
THRESHOLD = float(os.environ.get("ALERT_THRESHOLD") or "10")


def _get(path):
    req = urllib.request.Request(f"{BASE}{path}",
                                 headers={"Authorization": f"Bearer {OR_KEY}", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8")).get("data") or {}
    except Exception as exc:
        # Never echo the key, even inside an error string.
        print(f"balance read failed ({path}): {str(exc).replace(OR_KEY, '***') if OR_KEY else exc}")
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _email(subject, body):
    if not (SITE and KEY):
        print("WP_SITE_URL / WP_API_KEY not set; cannot send alert")
        return
    try:
        import requests
        requests.post(f"{SITE}/wp-json/layoffs/v1/alert",
                      json={"subject": subject, "body": body},
                      headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=25)
        print("alert email sent")
    except Exception as exc:
        print(f"alert send failed: {exc}")


def main():
    if not OR_KEY:
        print("OPENROUTER_API_KEY not set; skipping (nothing to check)")
        return 0

    credits = _get("/credits") or {}
    keyinfo = _get("/key") or {}
    total_credits = _num(credits.get("total_credits"))
    total_usage = _num(credits.get("total_usage"))
    balance = None
    if total_credits is not None and total_usage is not None:
        balance = round(total_credits - total_usage, 2)

    # This key's own remaining cap: a key can 402 on its cap while the account
    # still has money, so warn on whichever ceiling is closest first.
    key_left = _num(keyinfo.get("limit_remaining"))
    if key_left is None:
        kl, ku = _num(keyinfo.get("limit")), _num(keyinfo.get("usage"))
        key_left = (kl - ku) if (kl is not None and ku is not None) else None

    if balance is None and key_left is None:
        print("could not read balance or key cap; nothing sent")
        return 0

    ceilings = [c for c in (balance, key_left) if c is not None]
    binding = min(ceilings)
    which = "account balance" if binding == balance else "this key's spend cap"
    print(f"account balance={balance} key_remaining={key_left} binding={binding} ({which})")

    if binding < THRESHOLD:
        body = (
            f"OpenRouter is running low: {which} is ${binding:,.2f} "
            f"(alert threshold ${THRESHOLD:,.0f}).\n\n"
            f"  account balance : ${balance:,.2f}\n" if balance is not None else ""
        )
        if key_left is not None:
            body += f"  key cap left    : ${key_left:,.2f}\n"
        body += ("\nWhen this hits zero, all AI enrichment (extraction, industry/role/"
                 "reason tagging, tips, self-audit) stops until topped up. WARN, SEC and "
                 "ERM row ingestion keep running (they use no LLM).\n\n"
                 "Top up: https://openrouter.ai/settings/credits\n"
                 "If it is the key cap, raise the key's limit instead.")
        _email(f"OpenRouter low: ${binding:,.2f} left ({which})", body)
    else:
        print(f"balance healthy (>= ${THRESHOLD:,.0f}); no alert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
