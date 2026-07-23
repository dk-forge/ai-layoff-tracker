"""Deterministic industry backfill: propagate a company's known industry to its
own blank-industry rows. No LLM, no cost, no guessing.

Why this exists: ~96% of US rows carry no `industry`, because every structured
WARN notice arrives without one. That means most of our job volume counts toward
NO sector, which makes the by-industry view badly under-represent reality. The
LLM classifier (industry_backfill.py) is careful but does ~40 rows/day with two
model passes each, so it can never drain that backlog.

But a large share of those rows need no inference at all: the SAME company
already has a tagged row elsewhere in the table. Walgreens has a row tagged
"Healthcare & Pharma", so its blank Walgreens rows are Healthcare & Pharma. This
worker fills only those, using the company's own majority label.

Safety: writes through the same /industry-backfill endpoint as the LLM path, so
it inherits every guarantee — blank-only (a set industry is never overwritten),
closed-vocabulary validation server-side, and the corrections trail. A company
whose tagged rows disagree beyond a clear majority is skipped, not guessed.

Env: WP_SITE_URL, WP_API_KEY. Optional INDUSTRY_PROPAGATE_DRY_RUN=1,
INDUSTRY_PROPAGATE_MAX (cap rows written this run, default 5000).
"""
import collections
import json
import os
import sys
import urllib.parse
import urllib.request

SITE = os.environ.get("WP_SITE_URL", "https://asktherecruiter.com/blog").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
DRY = os.environ.get("INDUSTRY_PROPAGATE_DRY_RUN", "").lower() in {"1", "true", "yes"}
# `or` not a get-default: the workflow passes an EMPTY string when the input is
# blank, which a plain default would not catch.
MAX_WRITE = int(os.environ.get("INDUSTRY_PROPAGATE_MAX") or "5000")
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
PAGE = 200
# A company's label is only trusted when it clearly dominates its tagged rows;
# a genuinely mixed conglomerate is left to the LLM path rather than guessed.
MAJORITY = 0.75


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))


def _post(path, payload):
    req = urllib.request.Request(
        f"{SITE}/wp-json/layoffs/v1/{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": UA, "Content-Type": "application/json", "X-Layoff-API-Key": KEY},
        method="POST")
    return json.load(urllib.request.urlopen(req, timeout=120))


def scan():
    """Return (company -> Counter(industry), [blank rows])."""
    tagged = collections.defaultdict(collections.Counter)
    blanks = []
    page = 1
    while True:
        url = (f"{SITE}/wp-json/layoffs/v1/query?per_page={PAGE}&page={page}"
               f"&cb=prop{page}")
        try:
            data = _get(url)
        except Exception as exc:
            print(f"  query page {page} failed: {exc}")
            break
        rows = data.get("data") or []
        if not rows:
            break
        for r in rows:
            comp = (r.get("company_name") or "").strip().lower()
            ind = (r.get("industry") or "").strip()
            if not comp:
                continue
            if ind:
                tagged[comp][ind] += 1
            else:
                blanks.append((r.get("id"), comp))
        total = int(data.get("total") or 0)
        if page * PAGE >= total or page > 400:
            break
        page += 1
    return tagged, blanks


def main():
    if not DRY and not KEY:
        print("WP_API_KEY required (or set INDUSTRY_PROPAGATE_DRY_RUN=1)")
        return 1
    print("Scanning rows to learn each company's industry...")
    tagged, blanks = scan()
    print(f"  companies with a tagged row: {len(tagged):,}")
    print(f"  rows missing industry:       {len(blanks):,}")

    items = []
    skipped_mixed = skipped_unknown = 0
    for rid, comp in blanks:
        counts = tagged.get(comp)
        if not counts:
            skipped_unknown += 1
            continue
        label, n = counts.most_common(1)[0]
        if n / sum(counts.values()) < MAJORITY:
            skipped_mixed += 1
            continue
        items.append({"id": rid, "industry": label})
        if len(items) >= MAX_WRITE:
            break

    print(f"  fillable from the company's own label: {len(items):,}")
    print(f"  skipped (no tagged sibling): {skipped_unknown:,} | (mixed labels): {skipped_mixed:,}")
    if not items:
        print("nothing to propagate")
        return 0
    by_label = collections.Counter(i["industry"] for i in items)
    for lbl, n in by_label.most_common(12):
        print(f"    {lbl:<28}{n:>7,}")
    if DRY:
        print("\nDRY RUN: nothing written.")
        return 0

    filled = 0
    for i in range(0, len(items), 200):
        batch = items[i:i + 200]
        try:
            res = _post("industry-backfill", {"items": batch})
            filled += len(res.get("filled") or [])
        except Exception as exc:
            print(f"  batch {i//200+1} failed: {exc}")
    print(f"\nPropagated industry to {filled:,} row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
