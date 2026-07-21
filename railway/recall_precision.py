"""Recall + precision measurement — the 'measure before building' harness.

Converts 'what are we missing / getting wrong?' from eyeballing into numbers.

PRECISION (what we wrongly ADMIT): sample published entries, re-fetch each's
source, and confirm the stored job_count appears verbatim in the source text.
A miss is a likely fabricated/misread number — the dangerous failure class.
Reported as a false-positive rate with per-reason breakdown.

RECALL (what we MISS): diff against a held-out gold set of real layoffs
(seed_data/recall_goldset.csv), stratified across geography/size/sector, matched
against our own data with word-boundary + date-window logic. Reports recall %
and the labeled miss list — the discovery roadmap, per cell.

Read-only (no writes, no LLM). Run weekly; the precision reasons prioritize the
guards, the recall misses prioritize the sources.
Env: RP_PRECISION_SAMPLE (default 40), RP_DRY (skip health post).
"""
import csv
import os
import re
import sys
import time
import urllib.parse
from datetime import date

import requests

SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
GOLDSET = os.path.join(os.path.dirname(__file__), "seed_data", "recall_goldset.csv")
SAMPLE = max(5, int(os.environ.get("RP_PRECISION_SAMPLE", "40")))
_STOP = {"inc", "corp", "co", "ltd", "plc", "llc", "the", "group", "sa", "se", "ag"}


def _count_in_text(n, text):
    if not text or not n:
        return False
    n = int(n)
    grouped = f"{n:,}"
    variants = {str(n), grouped, grouped.replace(",", " "), grouped.replace(",", ".")}
    if n % 1000 == 0 and n >= 1000:
        variants.update({f"{n // 1000}k", f"{n // 1000}K"})
    return any(re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d])", text) for v in variants)


def _token(name):
    for w in re.split(r"[^A-Za-z0-9]+", name or ""):
        if w and w.lower() not in _STOP:
            return w
    return (name or "").strip()


def _fetch_text(url):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        # crude tag strip is enough to confirm a number's presence
        return re.sub(r"<[^>]+>", " ", r.text), None
    except Exception as exc:
        return None, f"fetch_error:{type(exc).__name__}"


def measure_precision():
    """Sample published entries and confirm the count is real in the source."""
    try:
        yr = date.today().year
        r = requests.get(f"{SITE}/wp-json/layoffs/v1/query",
                         params={"years": str(yr), "sources": "news", "per_page": SAMPLE * 3,
                                 "sort": "id", "dir": "desc"}, headers=UA, timeout=30)
        rows = r.json().get("data", []) if r.status_code == 200 else []
    except Exception as exc:
        print(f"precision: could not sample ({exc})")
        return None
    rows = [x for x in rows if (x.get("source_url") or "").startswith("http")][:SAMPLE]
    ok = bad = 0
    reasons = {}
    for x in rows:
        text, err = _fetch_text(x["source_url"])
        time.sleep(0.3)
        if text is None:
            reasons["source_unreachable"] = reasons.get("source_unreachable", 0) + 1
            continue  # unreachable != wrong; excluded from the rate
        if _count_in_text(x.get("job_count"), text):
            ok += 1
        else:
            bad += 1
            reasons["number_not_in_source"] = reasons.get("number_not_in_source", 0) + 1
            print(f"  PRECISION MISS: {x.get('company_name')} {x.get('job_count')} not in "
                  f"{x['source_url'][:70]}")
    checked = ok + bad
    rate = round(100 * ok / checked) if checked else None
    print(f"\nPRECISION: {ok}/{checked} verified in-source ({rate}%); "
          f"unreachable {reasons.get('source_unreachable', 0)}; reasons={reasons}")
    return {"checked": checked, "ok": ok, "precision_pct": rate, "reasons": reasons}


def measure_recall():
    """Diff the gold set against our data; classify hits/misses per cell."""
    if not os.path.exists(GOLDSET):
        print(f"recall: gold set not found at {GOLDSET}")
        return None
    gold = []
    with open(GOLDSET, newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("company") or "").strip().startswith("#"):
                continue
            if (row.get("company") or "").strip():
                gold.append(row)
    hits = 0
    misses = []
    for g in gold:
        company = g["company"].strip()
        try:
            r = requests.get(f"{SITE}/wp-json/layoffs/v1/query",
                             params={"company": company, "years": g.get("year", "2026"),
                                     "per_page": 30}, headers=UA, timeout=30)
            data = r.json().get("data", []) if r.status_code == 200 else []
        except Exception:
            data = []
        pat = re.compile(r"\b" + re.escape(_token(company)) + r"\b", re.I)
        if any(pat.search(d.get("company_name") or "") for d in data):
            hits += 1
        else:
            misses.append(g)
        time.sleep(0.15)
    total = len(gold)
    rate = round(100 * hits / total) if total else None
    print(f"\nRECALL: {hits}/{total} of the gold set present ({rate}%)")
    # cell breakdown by geo + sector tags in the gold set
    cells = {}
    for m in misses:
        cell = f"{m.get('geo', '?')}/{m.get('sector', '?')}"
        cells[cell] = cells.get(cell, 0) + 1
    if misses:
        print("  MISSES (the discovery roadmap):")
        for m in misses:
            print(f"    - {m['company']} ({m.get('geo')}/{m.get('sector')}, ~{m.get('jobs')})")
        print(f"  miss cells: {cells}")
    return {"gold": total, "hits": hits, "recall_pct": rate, "miss_cells": cells}


def main():
    print(f"=== recall/precision @ {SITE} ===")
    prec = measure_precision()
    rec = measure_recall()
    if os.environ.get("RP_DRY"):
        return 0
    try:
        from source_health import report_source_health
        detail = (f"precision {prec['precision_pct'] if prec else '?'}% "
                  f"({prec['reasons'] if prec else {}}); "
                  f"recall {rec['recall_pct'] if rec else '?'}% "
                  f"miss_cells={rec['miss_cells'] if rec else {}}")
        report_source_health("recall_precision", "ok", (rec or {}).get("hits", 0), detail)
    except Exception as exc:
        print(f"(health post skipped: {exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
