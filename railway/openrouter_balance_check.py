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

# A LEVEL alone cannot tell you that you are three days from zero. On
# 2026-08-02 this job printed "balance healthy" at $22.92 while the account was
# falling ~$7/day across both trackers -- comfortably above the $10 floor and
# about to hit it inside a long weekend. The floor answers "is it low"; nobody
# was asking "how fast".
#
# So the balance is now recorded daily and the alert fires on RUNWAY, whichever
# comes first. Runway is the honest question because the answer scales with
# whatever the pipelines actually do: a quiet week stretches it, a backfill
# sprint shortens it, and neither needs this number retuned.
RUNWAY_DAYS = float(os.environ.get("ALERT_RUNWAY_DAYS") or "10")
HISTORY = os.path.join(os.path.dirname(__file__), "openrouter_balance_history.json")
# Enough readings to see through one noisy day, few enough to react inside a
# week. Averaging the whole file would hide a sprint that started yesterday.
BURN_WINDOW_DAYS = 5


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


def _history():
    try:
        with open(HISTORY) as fh:
            rows = json.load(fh)
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _live_row_count():
    """Total rows on the live site, or None.

    Recorded alongside the balance so cost per stored row is derivable from one
    committed file (ops_status.py [2a]). A balance alone answers "how much is
    left" and never "did that money buy anything" — `backfill.py` firing ~5,150
    calls/day for ~234 useful rows was invisible for exactly as long as nobody
    divided one by the other. Best-effort: a failed read records no count
    rather than blocking the balance reading this job exists to take.
    """
    try:
        req = urllib.request.Request(
            "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate",
            headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8"))
        return int(((data.get("totals") or {}).get("entries")) or 0) or None
    except Exception as exc:
        print(f"row-count read failed ({exc}) — recording the balance without it")
        return None


def _record(balance):
    """Append today's reading and return the trimmed history.

    One row per day: a workflow that runs twice would otherwise halve the
    apparent burn. A read-only checkout just skips the write and reports on
    whatever history it already has.
    """
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    rows = [r for r in _history() if r.get("date") != today]
    reading = {"date": today, "balance": balance}
    live_rows = _live_row_count()
    if live_rows is not None:
        reading["rows"] = live_rows
    rows.append(reading)
    rows = sorted(rows, key=lambda r: r["date"])[-30:]
    try:
        with open(HISTORY, "w") as fh:
            json.dump(rows, fh, indent=1)
    except OSError:
        pass
    return rows


def _runway(rows):
    """(days_left, burn_per_day) or (None, None) when it cannot be known.

    UNKNOWN is a real answer here: with one reading there is no slope, and a
    balance that went UP (a top-up) is not a negative burn, it is a reset. Both
    return None rather than a reassuring number.
    """
    if len(rows) < 2:
        return None, None
    import datetime
    window = rows[-(BURN_WINDOW_DAYS + 1):]
    first, last = window[0], window[-1]
    d0 = datetime.date.fromisoformat(first["date"])
    d1 = datetime.date.fromisoformat(last["date"])
    days = (d1 - d0).days
    spent = first["balance"] - last["balance"]
    if days <= 0 or spent <= 0:
        return None, None
    burn = spent / days
    return (last["balance"] / burn), burn


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

    days_left, burn = (None, None)
    if balance is not None:
        days_left, burn = _runway(_record(balance))
    if days_left is None:
        print("runway: UNKNOWN (need two readings and a falling balance)")
    else:
        print(f"runway: {days_left:.1f} days at ${burn:,.2f}/day "
              f"(warn under {RUNWAY_DAYS:.0f})")

    low = binding < THRESHOLD
    short = days_left is not None and days_left < RUNWAY_DAYS
    if low or short:
        headline = (f"{which} is ${binding:,.2f} (floor ${THRESHOLD:,.0f})" if low
                    else f"{days_left:.1f} days of credit left at ${burn:,.2f}/day")
        body = f"OpenRouter needs attention: {headline}.\n\n"
        if balance is not None:
            body += f"  account balance : ${balance:,.2f}\n"
        if days_left is not None:
            body += (f"  burn rate       : ${burn:,.2f}/day over the last "
                     f"{BURN_WINDOW_DAYS} readings\n"
                     f"  runway          : {days_left:.1f} days\n")
        if key_left is not None:
            body += f"  key cap left    : ${key_left:,.2f}\n"
        body += ("\nWhen this hits zero, all AI enrichment (extraction, industry/role/"
                 "reason tagging, tips, self-audit) stops until topped up. WARN, SEC and "
                 "ERM row ingestion keep running (they use no LLM).\n\n"
                 "Top up: https://openrouter.ai/settings/credits\n"
                 "If it is the key cap, raise the key's limit instead.")
        subject = (f"OpenRouter low: ${binding:,.2f} left ({which})" if low
                   else f"OpenRouter runway: {days_left:.0f} days at ${burn:,.2f}/day")
        _email(subject, body)
    else:
        print(f"balance healthy (>= ${THRESHOLD:,.0f}) and runway is not short")
    return 0


if __name__ == "__main__":
    sys.exit(main())
