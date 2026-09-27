#!/usr/bin/env python3
"""Daily subscriber watch: who subscribes, to what, and is the welcome cap right.

Owner request 2026-09-27. Once a day this reads the keyed
/wp-json/layoffs/v1/subscriber-stats route (COUNTS ONLY, no address in any
field), writes a short plain-English summary to the job summary, keeps a
rolling history for the trend, and emails the owner through ops_notify (the
same deduped Resend door every other watchdog here uses) when the welcome-mail
cap or the Brevo 300/day budget needs revisiting, or signups drop or spike.

UNKNOWN IS NOT ZERO. A missing field prints UNKNOWN, never 0, and raises no
flag. In particular `welcome_mail` only exists once 2.20.213 (PR #422) is
live; before that the summary says "welcome counter not live yet" and the
welcome rules stay silent rather than reading an absent counter as "0 sent".

NEW CONFIRMATIONS PER DAY. The route exposes `confirmed_last_7_days` but no
per-day count. If a future plugin adds `confirmed_yesterday` it is used as is;
otherwise the day's figure is the NET change in the confirmed total against
yesterday's snapshot, and the summary labels it "net" so nobody reads it as
gross signups. Follows added/stopped are reported only if the route carries
`follows` ({added, stopped}); today it does not, so they print UNKNOWN.

Pure functions (parse, daily_new, evaluate, recommend_cap, summary) carry all
the logic and are tested with synthetic numbers in
tests/test_subscriber_watch.py. Only main() touches the network.
"""
from __future__ import annotations

import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

# Flag thresholds. Pinned by tests/test_subscriber_watch.py: change them there
# too, and say why in TECHLOG.
BREVO_DAILY_LIMIT = 300          # Brevo free plan, sends per day
WELCOME_CAP_DEFAULT = 40         # ALT_WELCOME_DAILY_CAP default in the plugin
WELCOME_WARN_FRACTION = 0.75     # welcome sends >= 75% of cap on any day
BREVO_WARN_FRACTION = 0.80       # total sends >= 80% of 300
DROP_ZERO_DAYS = 3               # 0 new confirmations for 3 days ...
DROP_LOOKBACK_DAYS = 7           # ... after a non-zero week before them
SPIKE_MULTIPLE = 3.0             # a day >= 3x the prior 7-day average
CAP_HEADROOM = 1.5               # recommended cap = observed peak x 1.5
DIGEST_RESERVE = 0.20            # never let welcomes eat the last 20% of 300
HISTORY_DAYS = 60

UNKNOWN = "UNKNOWN"


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def parse(payload: dict, today: str) -> dict:
    """One day's snapshot from the route payload. Absent -> None, never 0."""
    p = payload if isinstance(payload, dict) else {}
    conf = p.get("confirmed") if isinstance(p.get("confirmed"), dict) else {}
    freq = p.get("frequency") if isinstance(p.get("frequency"), dict) else {}
    snap = {
        "day": today,
        "available": bool(p.get("available")),
        "total": _int(conf.get("total")),
        "lists": {k: _int(conf.get(k)) for k in ("layoff", "talent", "articles")},
        "frequency": {k: _int(freq.get(k)) for k in ("daily", "weekly")},
        "last_7_days": _int(p.get("confirmed_last_7_days")),
        "confirmed_yesterday": _int(p.get("confirmed_yesterday")),
        "follows": None,
        "welcome": None,
        "digest_today": None,
    }
    f = p.get("follows")
    if isinstance(f, dict):
        snap["follows"] = {"added": _int(f.get("added")), "stopped": _int(f.get("stopped"))}
    w = p.get("welcome_mail")
    if isinstance(w, dict) and _int(w.get("welcome")) is not None:
        snap["welcome"] = {
            "day": str(w.get("day") or today),
            "sent": _int(w.get("welcome")),
            "skipped": _int(w.get("welcome_skipped")) or 0,
            "cap": _int(w.get("welcome_cap")) or WELCOME_CAP_DEFAULT,
            "limit": _int(w.get("brevo_daily_limit")) or BREVO_DAILY_LIMIT,
        }
    last = p.get("last_send")
    if isinstance(last, dict) and str(last.get("sent_at") or "")[:10] == today:
        snap["digest_today"] = _int(last.get("recipients"))
    return snap


def total_sends(snap: dict):
    """Welcome + digest sends today, or None when either half is unseen."""
    if snap.get("welcome") is None:
        return None
    return snap["welcome"]["sent"] + (snap.get("digest_today") or 0)


def daily_new(history: list) -> list:
    """(day, count, is_net) per snapshot; count None when not derivable."""
    out, prev = [], None
    for s in history:
        if s.get("confirmed_yesterday") is not None:
            out.append((s["day"], s["confirmed_yesterday"], False))
        elif prev is not None and prev.get("total") is not None and s.get("total") is not None:
            out.append((s["day"], max(0, s["total"] - prev["total"]), True))
        else:
            out.append((s["day"], None, True))
        prev = s
    return out


def recommend_cap(history: list):
    """Observed peak welcome demand x headroom, bounded to leave digest room."""
    peak_welcome = max((s["welcome"]["sent"] + s["welcome"]["skipped"]
                        for s in history if s.get("welcome")), default=None)
    if peak_welcome is None:
        return None
    peak_digest = max((s.get("digest_today") or 0 for s in history), default=0)
    ceiling = int(BREVO_DAILY_LIMIT * (1 - DIGEST_RESERVE)) - peak_digest
    return max(1, min(math.ceil(peak_welcome * CAP_HEADROOM), max(1, ceiling)))


def evaluate(history: list) -> list:
    """WARN reasons for the latest snapshot in `history` (oldest first)."""
    if not history:
        return []
    today = history[-1]
    warns = []
    w = today.get("welcome")
    if w:
        if w["cap"] and w["sent"] >= WELCOME_WARN_FRACTION * w["cap"]:
            warns.append(f"welcome emails reached {w['sent']} of the {w['cap']} daily cap "
                         f"(>= {int(WELCOME_WARN_FRACTION * 100)}%)")
        if w["skipped"] > 0:
            warns.append(f"{w['skipped']} welcome email(s) skipped over the cap today")
    t = total_sends(today)
    if t is not None and t >= BREVO_WARN_FRACTION * BREVO_DAILY_LIMIT:
        warns.append(f"total Brevo sends {t} of {BREVO_DAILY_LIMIT} "
                     f"(>= {int(BREVO_WARN_FRACTION * 100)}%)")

    series = [c for _, c, _ in daily_new(history)]
    recent = series[-DROP_ZERO_DAYS:]
    before = series[-(DROP_ZERO_DAYS + DROP_LOOKBACK_DAYS):-DROP_ZERO_DAYS]
    if (len(recent) == DROP_ZERO_DAYS and all(c == 0 for c in recent)
            and len(before) == DROP_LOOKBACK_DAYS and None not in before and sum(before) > 0):
        warns.append(f"sudden drop: 0 new confirmations for {DROP_ZERO_DAYS} days "
                     f"after {sum(before)} in the week before")
    prior = series[-(DROP_LOOKBACK_DAYS + 1):-1]
    if series and series[-1] is not None and len(prior) == DROP_LOOKBACK_DAYS and None not in prior:
        avg = sum(prior) / DROP_LOOKBACK_DAYS
        if avg > 0 and series[-1] >= SPIKE_MULTIPLE * avg:
            warns.append(f"spike: {series[-1]} new confirmations today vs a 7-day average "
                         f"of {avg:.1f} (>= {SPIKE_MULTIPLE:g}x)")
    return warns


def _v(x):
    return UNKNOWN if x is None else str(x)


def summary(history: list, warns: list) -> str:
    s = history[-1]
    if not s.get("available"):
        return (f"Subscriber watch {s['day']}: subscriber stats UNKNOWN (route reported no "
                "data). This is not a zero.")
    news = daily_new(history)
    _, n, is_net = news[-1]
    known7 = [c for _, c, _ in news[-7:] if c is not None]
    trend = (f"{sum(known7)} over the last {len(known7)} day(s) of history"
             if known7 else "no history yet")
    L, F = s["lists"], s["frequency"]
    lines = [
        f"Subscriber watch {s['day']}",
        f"- Active subscribers: {_v(s['total'])}",
        f"- New confirmations today{' (net change)' if is_net else ''}: {_v(n)}; "
        f"last 7 days (route): {_v(s['last_7_days'])}; history trend: {trend}",
        f"- By list: layoffs {_v(L['layoff'])}, talent {_v(L['talent'])}, "
        f"articles {_v(L['articles'])}",
        f"- By frequency: daily {_v(F['daily'])}, weekly {_v(F['weekly'])}",
    ]
    fo = s.get("follows")
    lines.append(f"- Follows added/stopped: {_v(fo and fo['added'])}/{_v(fo and fo['stopped'])}"
                 + ("" if fo else " (not in the stats route)"))
    w = s.get("welcome")
    if w:
        lines.append(f"- Welcome emails: {w['sent']} sent of cap {w['cap']}, "
                     f"{w['skipped']} skipped over cap")
        lines.append(f"- Total Brevo sends today: {_v(total_sends(s))} of {BREVO_DAILY_LIMIT}")
    else:
        lines.append("- Welcome emails: welcome counter not live yet (needs plugin 2.20.213)")
        lines.append(f"- Total Brevo sends today: {UNKNOWN} (welcome counter not live yet)")
    if warns:
        lines.append("")
        lines.append("WARN:")
        lines += [f"- {x}" for x in warns]
        rec = recommend_cap(history)
        if rec is not None:
            cur = w["cap"] if w else WELCOME_CAP_DEFAULT
            verb = "raise" if rec > cur else "keep or lower"
            lines.append(f"Recommendation: {verb} ALT_WELCOME_DAILY_CAP to {rec} "
                         f"(peak demand x{CAP_HEADROOM:g}, bounded to leave "
                         f"{int(DIGEST_RESERVE * 100)}% of {BREVO_DAILY_LIMIT} plus the peak "
                         f"digest for the digests).")
    else:
        lines.append("Status: OK, nothing to revisit.")
    return "\n".join(lines)


def merge_history(history: list, snap: dict) -> list:
    h = [s for s in history if isinstance(s, dict) and s.get("day") != snap["day"]]
    h.append(snap)
    h.sort(key=lambda s: s["day"])
    return h[-HISTORY_DAYS:]


def main(argv=None) -> int:  # pragma: no cover - network
    hist_path = (argv or sys.argv[1:] or ["subscriber_watch_history.json"])[0]
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not (site and key):
        print("Subscriber watch UNKNOWN: no WP_SITE_URL/WP_API_KEY. This is not a zero.")
        return 3
    req = urllib.request.Request(f"{site}/wp-json/layoffs/v1/subscriber-stats",
                                 headers={"X-Layoff-API-Key": key,
                                          "User-Agent": "ai-layoff-tracker-subscriber-watch"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        print(f"Subscriber watch UNKNOWN: could not read the stats route ({type(exc).__name__}).")
        return 3
    try:
        with open(hist_path) as fh:
            history = json.load(fh)
    except Exception:
        history = []
    snap = parse(payload, today)
    history = merge_history(history if isinstance(history, list) else [], snap)
    warns = evaluate(history) if snap["available"] else []
    text = summary(history, warns)
    print(text)
    with open(hist_path, "w") as fh:
        json.dump(history, fh)
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    if out:
        with open(out, "a") as fh:
            fh.write(text.replace("\n", "  \n") + "\n")
    if warns:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ops_notify
        ops_notify.notify("Subscriber watch: revisit the welcome cap / send budget", text,
                          dedupe_key=f"subscriber-watch:{today}", what="subscriber watch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
