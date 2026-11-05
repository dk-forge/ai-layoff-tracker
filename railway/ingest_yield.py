"""Did the nightly ingest BRING anything? The alarm for "running, but posting 0".

WHY THIS EXISTS (incident found 2026-11-05). From at least 2026-10-28 every
nightly railway-cron run pulled 800 to 1409 candidates and posted 0 events.
`spend.py --degrade` had switched paid reads off ("OpenRouter provider key
exhausted"), so extraction was deferred on every candidate. Nothing paged:

  * the ingest run is green by design (degrade, never halt);
  * `ingest_silence.py` asks whether ANY collector note is recent, and the
    collectors kept writing fresh notes every night, so it said "alive";
  * `ci_alert.py` only mails a RED run, and there was none;
  * `openrouter_balance_check.py` reads the key's `limit_remaining`, which
    read $15, while `spend.py` compares the limit to LIFETIME usage.

This module asks the two questions none of them ask, from the run's own
committed record (`railway/spend_jobs.json`, harvested daily) and the key's
live state:

  (a) are paid reads OFF because the key is exhausted or at its limit?
  (b) has railway-cron posted 0 events on 2+ consecutive nightly runs that
      each pulled more than MIN_ITEMS candidates?

Each is one cause in the alert ledger (`ops_notify` dedupe_key), so the owner
gets ONE mail per incident and ONE recovered notice, never one per run.

It never prints or mails the key. The key is named by the tail OpenRouter
itself shows on the keys page (the masked `label`), or by
`spend.key_fingerprint` when no label is returned.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import sys

import ops_notify
import spend

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "spend_jobs.json")

JOB = "railway-cron"
# DERIVATION: a normal night pulls 800 to 1400 candidates; under 100 is a
# partial or quiet run where 0 posted is plausible and proves nothing.
MIN_ITEMS = 100
# Two nights, not one: one 0-post night can be a quiet news day.
MIN_STREAK = 2

KEY_PAID_READS = "ingest-yield:paid-reads-off"
KEY_ZERO_POSTS = "ingest-yield:zero-posts"
KEYS_URL = "https://openrouter.ai/settings/keys"
PAID_OFF_MARK = "paid reads were switched off"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def job_runs(entries, job=JOB):
    """The job's runs, oldest first, ordered by run_id (a UTC timestamp)."""
    rows = [e for e in entries or () if isinstance(e, dict) and e.get("job") == job]
    return sorted(rows, key=lambda e: (str(e.get("run_id") or ""), str(e.get("date") or "")))


def zero_post_streak(entries, job=JOB, min_items=MIN_ITEMS):
    """Consecutive newest runs that pulled > min_items and stored 0.

    A run that stored anything ends the streak. A small pull (<= min_items)
    with 0 stored neither extends nor ends it."""
    streak = 0
    for e in reversed(job_runs(entries, job)):
        stored = _num(e.get("stored")) or 0
        items = _num(e.get("items")) or 0
        if stored > 0:
            break
        if items > min_items:
            streak += 1
    return streak


def paid_reads_off(key_state, entries):
    """True / False, or None when nothing could be read.

    True when the key is at its limit by either reading (lifetime usage vs
    limit, which is what spend.py gates on, or OpenRouter's limit_remaining),
    or when the newest railway-cron run says paid reads were switched off."""
    runs = job_runs(entries)
    if runs and PAID_OFF_MARK in str(runs[-1].get("truncated") or ""):
        return True
    if not key_state:
        return None if not runs else False
    limit = _num(key_state.get("limit"))
    if limit is None:
        return False
    left = _num(key_state.get("limit_remaining"))
    if left is not None and left <= 0:
        return True
    usage = _num(key_state.get("usage"))
    return usage is not None and limit - usage <= 0


def key_tail(key_state, api_key):
    """The key's public tail as the OpenRouter keys page shows it, else the
    one-way fingerprint. Never the key."""
    label = str((key_state or {}).get("label") or "")
    if "..." in label:
        tail = label.rsplit("...", 1)[1].strip()
        if tail and len(tail) <= 6:
            return tail
    return spend.key_fingerprint(api_key) if api_key else "unknown"


def _fix_line(tail):
    return (f"OpenRouter key for the layoff tracker hit its limit. Open {KEYS_URL}, "
            f"edit the key ending {tail}, raise the limit.")


def _key_numbers(key_state):
    if not key_state:
        return "  key state         : could not be read\n"
    limit, usage = _num(key_state.get("limit")), _num(key_state.get("usage"))
    out = f"  key limit         : {limit}\n  lifetime usage    : {usage}\n"
    left = _num(key_state.get("limit_remaining"))
    if left is not None:
        out += f"  limit_remaining   : {left} (as OpenRouter reports it)\n"
    return out


def evaluate(entries, key_state, api_key):
    """{"paid_reads": alert|None, "zero_posts": alert|None, plus the readings}.

    Pure apart from key_tail. An alert is {subject, body, dedupe_key}."""
    off = paid_reads_off(key_state, entries)
    streak = zero_post_streak(entries)
    tail = key_tail(key_state, api_key)
    runs = job_runs(entries)
    last = runs[-1] if runs else {}
    out = {"paid_off": off, "streak": streak, "has_runs": bool(runs),
           "paid_reads": None, "zero_posts": None}
    if off:
        body = (_fix_line(tail) + "\n\n"
                "Paid reads are OFF for the daily ingest, so no news or extraction "
                "event can be posted until the limit is raised. Free sources (WARN, "
                "SEC rows) keep running.\n\n" + _key_numbers(key_state) +
                "\nIf the keys page shows the limit is NOT used up, the spend guard "
                "is reading lifetime usage against a monthly limit: tell a session "
                "to check provider_exhausted in railway/spend.py.\n\n"
                "Raised once per incident by railway/ingest_yield.py "
                "(ingest-silence.yml). A RECOVERED mail follows when it clears.")
        out["paid_reads"] = {"subject": "Paid reads OFF: OpenRouter key limit reached",
                             "body": body, "dedupe_key": KEY_PAID_READS}
    if streak >= MIN_STREAK:
        body = (f"The daily ingest (railway-cron) posted 0 events on {streak} nightly "
                f"runs in a row, each pulling more than {MIN_ITEMS} candidates. "
                f"Last run {last.get('run_id')}: {last.get('items')} pulled, "
                f"{last.get('stored')} posted.\n\n")
        if off:
            body += "Cause: paid reads are OFF.\n" + _fix_line(tail) + "\n"
        else:
            body += ("Paid reads look ON, so the cause is elsewhere: read the "
                     "'Run complete' and 'LLM SPEND' lines in the newest "
                     "ingest-cron-vps.yml log.\n")
        body += "\nRaised once per incident by railway/ingest_yield.py (ingest-silence.yml)."
        out["zero_posts"] = {"subject": f"Ingest posted 0 events for {streak} nights",
                             "body": body, "dedupe_key": KEY_ZERO_POSTS}
    return out


def deliver(verdict):
    """Raise each open cause once; clear a cause only on a CLEAR reading."""
    for name, key, clear in (
            ("paid_reads", KEY_PAID_READS, verdict.get("paid_off") is False),
            ("zero_posts", KEY_ZERO_POSTS, verdict.get("has_runs") and verdict.get("streak", 0) == 0)):
        alert = verdict.get(name)
        if alert:
            ops_notify.notify(alert["subject"], alert["body"],
                              dedupe_key=alert["dedupe_key"], what="ingest yield alarm")
        elif clear:
            ops_notify.resolve(key, f"Recovered: {name.replace('_', ' ')}",
                               "The daily ingest is posting events again.",
                               what="ingest yield recovery")


def main():
    try:
        with open(LEDGER, encoding="utf-8") as fh:
            entries = (json.load(fh) or {}).get("entries") or []
    except (OSError, ValueError) as exc:
        print(f"INGEST YIELD UNKNOWN: could not read spend_jobs.json ({type(exc).__name__})")
        entries = []
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    key_state = None
    if api_key:
        try:
            key_state = spend.fetch_key_state(api_key)
        except Exception as exc:  # unreadable is UNKNOWN, never a pass
            print(f"INGEST YIELD: key state UNKNOWN ({type(exc).__name__})")
    verdict = evaluate(entries, key_state, api_key)
    print(f"ingest yield: paid_reads_off={verdict['paid_off']} "
          f"zero_post_streak={verdict['streak']} (alarm at {MIN_STREAK})")
    deliver(verdict)
    # Exit 0 even when alarming: the mail IS the page. A red run would make
    # ci_alert send a second mail about the same incident.
    return 0


if __name__ == "__main__":
    sys.exit(main())
