#!/usr/bin/env python3
"""Attribute the SHARED OpenRouter account's spend, which no ledger can.

    python3 railway/openrouter_activity.py            # last 7 days, grouped
    python3 railway/openrouter_activity.py --days 30

WHY THIS EXISTS. On 2026-09-15 `ops_status [2a]` read the account burning
$1.85/day (~$56/month) against a combined target of $18, with this repo's own
meter explaining $0.10/day. The remaining ~$1.75/day could not be attributed
from committed state, and that was not for want of looking:

  * THIS repo keeps `railway/spend_jobs.json`, a real per-job ledger. It is the
    only one of the three that can say which job spent what.
  * talent-intelligence-tracker keeps `data/spend_month.json`, a month-start
    LIFETIME snapshot. No $/day, no $/job, nothing attributable.
  * asktherecruiter-sandbox keeps no CI spend ledger at all, and its
    `llm-canary` runs nightly against a production model plus an LLM judge.

Three consumers, one balance, and two of them cannot account for themselves.
Adding a ledger to each is the durable fix and is not this file's business.
This file answers the question that blocks every spending decision NOW, from
the one place the answer exists: OpenRouter's own activity record.

WHAT IT REPORTS. Daily rows grouped by API key and by model, so "which repo"
and "which job" can be read off a key name, plus the same $/day the balance
check computes, from a second source. Two numbers that disagree is a finding.

WHAT IT IS NOT. It is NOT a second balance check and does not write
`openrouter_balance_history.json`; that file has ONE writer and this is not it.
It makes NO model call and costs $0.00: `/activity` is metadata about spend
already incurred, so reading it cannot add to the bill.

IT CANNOT RUN FROM A SESSION WITHOUT THE KEY, and says so rather than
returning an empty report. A key-less run exits 3 (UNKNOWN), never 0, because
"no activity found" and "never asked" are different answers and this whole
module exists because they were conflated once already.

PRIVACY. Prompts and completions are never requested and never printed. The
activity endpoint returns spend metadata only; the key is never echoed, not
even inside an error string.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict

BASE = "https://openrouter.ai/api/v1"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")

#: Exit codes. 0 = read and reported. 3 = could not be read, which is UNKNOWN
#: and must never be presented as "nothing is spending".
OK, UNKNOWN = 0, 3


def _scrub(text):
    """Never echo the key, even inside an error string."""
    s = str(text)
    return s.replace(OR_KEY, "***") if OR_KEY else s


def fetch_activity(days=7, get=None):
    """-> (rows, note). rows is None when the read failed: UNKNOWN, not empty.

    `get` is injectable so tests never open a socket.
    """
    if not OR_KEY:
        return None, ("OPENROUTER_API_KEY is not set, so the account's activity "
                      "was never requested. That is UNKNOWN, not an empty account")
    getter = get or _http_get
    try:
        payload = getter(f"{BASE}/activity")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return None, f"activity read failed: {_scrub(exc)}"
    if payload is None:
        return None, "activity read returned nothing"
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return None, "activity response had an unexpected shape"
    return rows, "ok"


def _http_get(url):
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {OR_KEY}", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def group(rows, days=7):
    """-> {"by_key": {...}, "by_model": {...}, "by_date": {...}, "total": x}

    Pure. Whatever the endpoint calls its fields, spend is read from the first
    of `usage`, `cost` or `total_cost` that is present, because a renamed field
    read as 0.0 would look exactly like a quiet account.
    """
    dates = sorted({str(r.get("date") or "")[:10] for r in rows if r.get("date")})
    keep = set(dates[-days:]) if dates else set()
    by_key, by_model, by_date = defaultdict(float), defaultdict(float), defaultdict(float)
    total = 0.0
    for r in rows:
        d = str(r.get("date") or "")[:10]
        if keep and d not in keep:
            continue
        spend = 0.0
        for field in ("usage", "cost", "total_cost"):
            if r.get(field) is not None:
                spend = _f(r[field])
                break
        key = str(r.get("api_key_label") or r.get("api_key") or "unlabelled key")
        by_key[key] += spend
        by_model[str(r.get("model") or "unknown model")] += spend
        by_date[d] += spend
        total += spend
    return {"by_key": dict(by_key), "by_model": dict(by_model),
            "by_date": dict(by_date), "total": round(total, 4),
            "days_seen": len([d for d in by_date if d])}


def render(g):
    out = [f"account activity: ${g['total']:.4f} over {g['days_seen']} day(s) with a record"]
    if g["days_seen"]:
        out.append(f"  ${g['total'] / g['days_seen']:.4f}/day, "
                   f"~${g['total'] / g['days_seen'] * 30:.2f}/month at that rate")
    for title, book in (("BY API KEY (this is which repo)", g["by_key"]),
                        ("BY MODEL", g["by_model"])):
        out.append(f"\n{title}")
        if not book:
            out.append("  nothing recorded")
        for name, amount in sorted(book.items(), key=lambda kv: -kv[1]):
            share = (amount / g["total"] * 100) if g["total"] else 0.0
            out.append(f"  {amount:9.4f}  {share:5.1f}%  {name}")
    out.append("\nAn unlabelled key is a repo nobody named. Label it in OpenRouter "
               "so the next reading attributes itself.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args(argv)

    rows, note = fetch_activity(days=args.days)
    if rows is None:
        print(f"UNKNOWN: {note}")
        print("A check that could not run is not a pass, and an account with no "
              "readable activity is not an account at rest.")
        return UNKNOWN
    g = group(rows, days=args.days)
    print(render(g))
    return OK


if __name__ == "__main__":
    sys.exit(main())
