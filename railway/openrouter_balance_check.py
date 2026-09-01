"""Low-balance early warning for the OpenRouter account.

The whole LLM pipeline (extraction, industry/role/reason classification, tips,
self-audit) silently stalls the moment OpenRouter credits hit zero. That is
exactly what happened once, unnoticed, until jobs had been failing for a while.
This is the cheap tripwire that turns "discovered it ran dry" into "warned in
time": a daily read of the account balance that emails the owner while the
balance is low.

WHO IT COMES FROM, AND WHY THAT IS WORTH A PARAGRAPH.

It goes through `ops_notify`, so the alarm carries the operational From line
and the `[AI Layoff Tracker]` subject prefix that every other alert carries.
Until 2026-08-20 it POSTed to the site's `/alert` route, which calls bare
`wp_mail()`, which the Brevo plugin on this install rewrites to the SUBSCRIBER
newsletter identity. The owner received this alarm from
`newsletter@asktherecruiter.com` under the reader newsletter's display name,
one inbox row away from a digest he had actually subscribed to.

An alarm wearing the newsletter's face gets filtered with the newsletter, and
a filtered alarm is the original silence wearing a new hat.

Read-only, no LLM calls, ~0 cost. Never raises: a monitoring job must not page
the owner about its own failure. Env: OPENROUTER_API_KEY (already a GitHub
secret), RESEND_API_KEY, ALERT_THRESHOLD (default 10 USD).
"""
import json
import os
import sys
import urllib.request

import ops_notify

BASE = "https://openrouter.ai/api/v1"
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

# AN ABSOLUTE FLOOR IS MEANINGLESS AGAINST A CAP SMALLER THAN THE FLOOR.
#
# 2026-09-01: this repo's key carries a $10/MONTH limit and THRESHOLD is $10,
# so `key_remaining` can never exceed the floor. `binding < THRESHOLD` became
# true at the first cent of spend and stayed true for the rest of the month.
# The alert was not reporting a low balance, it was reporting that the cap
# equals the floor -- every month, forever, with $58.23 sitting untouched in
# the account behind it.
#
# An alarm that cannot stop firing is one a reader learns to delete, and this
# one guards the moment all AI enrichment stops. So the floor is now chosen
# per CEILING rather than applied to both:
#
#   * ACCOUNT BALANCE keeps the absolute floor. An account is a pool that can
#     be any size, and "under $10 left" is a real, scale-free statement.
#   * A KEY CAP gets a FRACTION of its own limit. A cap is a policy the owner
#     set; what matters is how much of THIS month's allowance is gone, not how
#     it compares to a number chosen for a different quantity.
#
# Runway is untouched and still fires independently -- it answers "how fast",
# which no level can, and it is the half that caught the 2026-08-02 case.
KEY_FLOOR_FRACTION = float(os.environ.get("ALERT_KEY_FLOOR_FRACTION") or "0.2")
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
    """Undeduped on purpose, which is the cadence this always had.

    The subject carries the figure, so the endpoint's old suppress-by-subject
    transient could almost never match two days running. Keeping it undeduped
    also happens to be right for this particular alarm: a balance heading for
    zero should go on saying so every day until somebody tops it up, and the
    thing it is warning about gets worse while it waits.
    """
    ops_notify.notify(subject, body, what="OpenRouter balance alert")


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


def floor_for(binding, balance, key_limit):
    """The floor that applies to whichever ceiling actually binds.

    Pure, and extracted so it can be TESTED. The first version of the fix left
    this inline in ``main`` and the test mirrored the arithmetic instead of
    calling it -- which passed happily when the fix was mutated away, because
    it was checking a copy rather than the shipped code. A test that cannot
    fail is the same defect as an alarm that cannot stop.

    Returns ``(floor, note)``; the note is reader-facing and goes in the mail.

    ``key_limit is None`` means the key reports no cap at all -- the unlimited
    case -- so only the account can bind and the absolute floor is right.
    """
    if binding == balance or key_limit is None:
        return THRESHOLD, f"floor ${THRESHOLD:,.0f}"
    floor = key_limit * KEY_FLOOR_FRACTION
    return floor, (f"floor ${floor:,.2f}, which is "
                   f"{KEY_FLOOR_FRACTION:.0%} of this key's "
                   f"${key_limit:,.0f} cap")


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
    key_limit = _num(keyinfo.get("limit"))
    floor, floor_note = floor_for(binding, balance, key_limit)
    print(f"account balance={balance} key_remaining={key_left} binding={binding} ({which})")

    days_left, burn = (None, None)
    if balance is not None:
        days_left, burn = _runway(_record(balance))
    if days_left is None:
        print("runway: UNKNOWN (need two readings and a falling balance)")
    else:
        print(f"runway: {days_left:.1f} days at ${burn:,.2f}/day "
              f"(warn under {RUNWAY_DAYS:.0f})")

    low = binding < floor
    short = days_left is not None and days_left < RUNWAY_DAYS
    if low or short:
        headline = (f"{which} is ${binding:,.2f} ({floor_note})" if low
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
