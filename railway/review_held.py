#!/usr/bin/env python3
"""Review the HELD rows: two referees release (publish) or trash each one.

A guard that cannot decide a row (negation_guard: a denial in the count's own
sentence) posts it with meta.held_reason. WordPress stores it as a `pending`
post that no public surface, total or feed can see (includes/api.php, /held).
This script is the other half: it lists the queue, puts each row to the same
two referees adjudicate_row.py uses under the same published rules, and acts
only on agreement:

    both "keep"   -> release: the row is published (duplicate checks re-run)
    both "trash"  -> trash: the post is trashed and its hash suppressed
    anything else -> stays HELD, written down, exit 3 (a human or a later run)

An unreadable source is UNKNOWN and changes nothing, as in adjudicate_row.

USAGE (review-held.yml runs it daily)
    WP_SITE_URL=... WP_API_KEY=... OPENROUTER_API_KEY=... python3 railway/review_held.py [--apply]
Exit: 0 every held row decided (or none held), 3 some row left held, 1 hard failure.
"""
from __future__ import annotations

try:
    import blog_read_cache as blog_reads
except ModuleNotFoundError:
    from railway import blog_read_cache as blog_reads

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adjudicate_row as adj  # noqa: E402
import spend  # noqa: E402

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


def decision_for(status: str, action: str) -> str | None:
    """The queue action for a referee outcome; None leaves the row held."""
    if status != "agree":
        return None
    return {"keep": "release", "trash": "trash"}.get(action)


def _call(site: str, key: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"{site}/wp-json/layoffs/v1/{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method="POST" if body is not None else "GET",
        headers={"X-Layoff-API-Key": key, "Content-Type": "application/json", "User-Agent": UA})
    with blog_reads.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def review_one(row: dict) -> tuple[str | None, str]:
    """(queue action or None, reason) for one held row. Pays for two referee calls."""
    evidence, read = adj.gather_evidence(row, [])
    if not evidence:
        return None, "UNKNOWN: the source could not be read"
    prompt = adj.build_prompt(adj.row_view(row), evidence, _dt.date.today().isoformat())
    verdicts = {}
    for model in adj.REFEREES:
        try:
            verdicts[model] = adj.ask_referee(model, prompt)
        except spend.PaidReadsOff as exc:
            print(f"  {model}: budget stop ({exc})")
            verdicts[model] = None
        v = verdicts[model]
        print(f"  {model}: " + (json.dumps(v, ensure_ascii=False)[:300] if v else "no usable verdict"))
    status, action, _ = adj.decide(verdicts)
    reasons = "; ".join((v.get("reasoning") or "")[:140] for v in verdicts.values() if v)
    return decision_for(status, action), f"{status}/{action}: {reasons}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="release/trash on agreement (otherwise dry run)")
    a = ap.parse_args()
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        print("WP_SITE_URL and WP_API_KEY are required")
        return 1
    held = _call(site, key, "held").get("held") or []
    print(f"{len(held)} held row(s)")
    left = 0
    for row in held:
        print(f"HELD {row['id']}: {row.get('company_name')} {row.get('job_count')} "
              f"{row.get('layoff_date')} ({row.get('held_reason')}) {row.get('source_url')}")
        action, reason = review_one(row)
        if action is None:
            left += 1
            print(f"  stays HELD: {reason[:300]}")
            continue
        if not a.apply:
            print(f"  dry run: would {action}")
            continue
        out = _call(site, key, f"held/{row['id']}",
                    {"action": action, "reason": f"two-referee review ({' + '.join(adj.REFEREES)}): {reason}"[:480]})
        print(f"  {out.get('result')}")
    print(f"spend ${round(spend.run_cost_usd(), 4)}; {left} row(s) left held")
    return 3 if left else 0


if __name__ == "__main__":
    sys.exit(main())
