"""Recall + precision measurement — the 'measure before building' harness.

Converts 'what are we missing / getting wrong?' from eyeballing into numbers.

EVERY RATE HERE IS REPORTED WITH A WILSON 95% INTERVAL (added 2026-08-01).
Before that this module printed bare percentages off samples of 40-57, which
invites reading "98%" as a precise figure when the honest statement is "between
91% and 99.7%". A small sample is a WIDE INTERVAL, not a precise number. The
same rule bit this project in the other direction on 2026-08-01, when a session
declared the archiver broken on 0 of 40 rows while the true rate was 0.4%.

PRECISION (what we wrongly ADMIT): sample published entries, re-fetch each's
source, and confirm the stored job_count appears verbatim in the source text.
A miss is a likely fabricated/misread number — the dangerous failure class.
Reported as a rate with an interval and a per-reason breakdown. FAILS the run
when the interval's lower bound falls below PRECISION_LOWER_FLOOR.

RECALL, two sets, and they measure different things:

  SEC ITEM 2.05 GOLD SET (railway/recall_goldset.py) — 57 workforce reductions
  enumerated from the filer's own structured item code in SEC EDGAR, adjudicated
  row by row, frozen, and re-measured against live data. THIS is the one with a
  floor, and the floor can fail the run.

  seed_data/recall_goldset.csv — 40 hand-listed companies from a research sweep,
  matched by asking whether the company appears anywhere in our data that year.
  Kept because it is a useful smoke test of the biggest names, and printed with
  its interval, but it carries NO threshold: the companies in it are the ones
  every source covers, so it cannot fall far, and company-presence-in-a-year is
  not event recall. Do not quote it as recall.

Read-only (no writes, no LLM) apart from the committed measurement file. Run
weekly; the precision reasons prioritize the guards, the recall misses prioritize
the sources.

EXIT CODES — this module used to `return 0` unconditionally, which is what made
the recall claim unfalsifiable:
    0  measured and inside every bound
    2  a bound was breached (the workflow reddens, ci_alert.py mails the cause)
    3  could not measure enough to judge — UNKNOWN, never a pass

Env: RP_PRECISION_SAMPLE (default 40), RP_DRY (skip health post + file write).
"""
import csv
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import date

import requests

from recall_goldset import (MEASUREMENT_PATH, format_interval, judge, measure,
                            wilson)

SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
GOLDSET = os.path.join(os.path.dirname(__file__), "seed_data", "recall_goldset.csv")
SAMPLE = max(5, int(os.environ.get("RP_PRECISION_SAMPLE", "40")))

# PRECISION FLOOR, and why it is this number.
#
# The check is on the WILSON LOWER BOUND, not on the observed rate, because this
# sample IS redrawn every run (the newest news rows) so it carries real sampling
# noise, unlike the frozen recall set.
#
# Measured 2026-08-01: 56 of 57 counts verbatim in their source = 98.2%, lower
# bound 90.7%. At n=57 the lower bound crosses 0.80 at 51 verified, i.e. six bad
# rows. If the true rate really is 98%, six or more bad rows in 57 happens about
# once in 200 runs — roughly a quarter of a false alarm per year at this weekly
# cadence, which is the point: the Spirit assertion reddened CI eight times in
# one afternoon and eight identical emails is how an alert channel gets
# filtered. A tighter floor of 0.85 would trip on four bad rows and fire ~1.5
# times a year for no reason.
#
# If it proves noisy: RAISE NOTHING, LOWER NOTHING without saying why in TECHLOG.
PRECISION_LOWER_FLOOR = 0.80
# Below this many reachable sources the precision sample cannot judge anything,
# so the run says UNKNOWN rather than reporting a rate off six rows.
PRECISION_MIN_CHECKED = 20
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
    _, lo, hi = wilson(ok, checked)
    print(f"\nPRECISION: {format_interval(ok, checked)}; "
          f"unreachable {reasons.get('source_unreachable', 0)}; reasons={reasons}")
    return {"checked": checked, "ok": ok, "precision_pct": rate,
            "ci_low": lo, "ci_high": hi, "reasons": reasons}


_AI_TERMS = re.compile(
    r"\b(AI|A\.I\.|artificial intelligence|automation|automate|machine learning|"
    r"generative|agentic|algorithm|chatbot|GPT|LLM)\b", re.I)


def measure_ai_precision():
    """Of rows we tag AI, what fraction carry a QUOTABLE, AI-naming statement?

    This is the number a journalist probes: not 'is the count real' but 'can you
    show me where the employer named AI'. A row tagged AI with no quote, or a
    quote that never names AI/automation (e.g. 'technology-enabled efficiency'),
    is a precision miss and is printed for the reclassifier to downgrade.
    """
    try:
        yr = date.today().year
        r = requests.get(f"{SITE}/wp-json/layoffs/v1/query",
                         params={"years": str(yr), "ai": "1", "per_page": 300},
                         headers=UA, timeout=30)
        rows = r.json().get("data", []) if r.status_code == 200 else []
    except Exception as exc:
        print(f"ai_precision: could not sample ({exc})")
        return None
    if not rows:
        return None
    quoted = ai_named = 0
    misses = []
    for x in rows:
        q = (x.get("ai_language") or "").strip()
        if q:
            quoted += 1
            if _AI_TERMS.search(q):
                ai_named += 1
            else:
                misses.append((x, q))
        else:
            misses.append((x, ""))
    n = len(rows)
    rate = round(100 * ai_named / n) if n else None
    print(f"\nAI PRECISION: {format_interval(ai_named, n)} of AI-tagged rows carry an "
          f"AI-naming quote; {quoted}/{n} have any quote. (An interval matters most here: "
          f"53/53 is not 100% certainty, it is 93%-100%.)")
    for x, q in misses[:15]:
        print(f"  AI PRECISION MISS: {x.get('company_name')} {x.get('job_count')} "
              f"[{x.get('review_status')}] quote={q[:60]!r}")
    return {"checked": n, "ai_named": ai_named, "with_quote": quoted,
            "ai_precision_pct": rate, "misses": len(misses)}


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
    print(f"\nLEGACY NAME-PRESENCE CHECK (seed_data/recall_goldset.csv, NOT event recall, "
          f"NO threshold): {format_interval(hits, total)} of these companies appear somewhere "
          f"in our data that year")
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


def judge_precision(prec):
    """(state, detail) for the precision sample. Three states, never two."""
    if not prec or not prec.get("checked"):
        return "unknown", ("no precision sample could be drawn — precision is UNMEASURED, "
                           "not fine")
    if prec["checked"] < PRECISION_MIN_CHECKED:
        return "unknown", (f"only {prec['checked']} sources were reachable (need "
                           f"{PRECISION_MIN_CHECKED}) — too few to judge a rate. Check the "
                           f"source_unreachable count before reading anything into this run")
    lo = prec.get("ci_low")
    shown = format_interval(prec["ok"], prec["checked"])
    if lo is not None and lo < PRECISION_LOWER_FLOOR:
        return "fail", (f"stored job counts verified verbatim in their own source: {shown}. The "
                        f"95% lower bound is below the {PRECISION_LOWER_FLOOR:.0%} floor, so this "
                        f"is not sample noise. Every miss printed above is a published number "
                        f"that is not in the source it cites — read those first")
    return "pass", f"{shown}; floor is a {PRECISION_LOWER_FLOOR:.0%} lower bound"


def main():
    print(f"=== recall/precision @ {SITE} ===")
    prec = measure_precision()
    aiprec = measure_ai_precision()
    legacy = measure_recall()

    # The SEC Item 2.05 gold set — the one that can fail. Its bound, its
    # unreachable policy and its three-state verdict all live in
    # recall_goldset.py, which data_integrity.RecallFloorInvariant and the tests
    # import too, so the number that reddens this workflow and the number
    # ops_status prints can never drift apart.
    print("\n=== SEC Item 2.05 gold set (independent; the one with a floor) ===")
    try:
        sec = measure()
    except Exception as exc:                                  # noqa: BLE001
        print(f"  could not measure ({exc}) — UNKNOWN, not a pass")
        sec, sec_state, sec_detail = None, "unknown", f"could not measure ({exc})"
    else:
        sec_state, sec_detail = judge(sec)
        print(f"  {sec_state.upper()}: {sec_detail}")
        for x in sec["lost_since_adjudication"]:
            print(f"    LOST {x['filing_date']} {x['filer'][:40]:40s} {x['stated_job_count']}"
                  f"  (an editor confirmed this one was held)")
        for x in sec["missed_events"]:
            print(f"    MISS {x['filing_date']} {x['filer'][:40]:40s} {x['stated_job_count']}")
        for c in sec["candidates_needing_adjudication"]:
            print(f"    ADJUDICATE {c['filing_date']} {c['filer'][:36]:36s} new tracker events "
                  f"{c['new_tracker_event_ids']} — NOT counted until an editor decides")

    prec_state, prec_detail = judge_precision(prec)
    print(f"\nPRECISION VERDICT: {prec_state.upper()}: {prec_detail}")

    if os.environ.get("RP_DRY"):
        return 0

    if sec is not None:
        # Committed by the workflow. The data being measured changes without a
        # commit, so a result that lives only in the runner is a result that
        # resets every night — the same reasoning as headline_baseline.json.
        MEASUREMENT_PATH.write_text(json.dumps(sec, indent=2, sort_keys=True) + "\n",
                                    encoding="utf-8")
        print(f"measurement written: {MEASUREMENT_PATH}")

    # UNKNOWN maps to 'degraded' on the health page, never to 'ok': the ledger
    # must not show green for a rate nobody could measure.
    worst = ("fail" if "fail" in (prec_state, sec_state)
             else "unknown" if "unknown" in (prec_state, sec_state) else "pass")
    try:
        from source_health import report_source_health
        detail = (f"precision {prec_detail} | sec_205_recall {sec_detail} | "
                  f"ai_precision {aiprec['ai_precision_pct'] if aiprec else '?'}%")
        report_source_health("recall_precision",
                             "ok" if worst == "pass" else "degraded",
                             (sec or {}).get("matched", 0), detail[:240])
    except Exception as exc:
        print(f"(health post skipped: {exc})")

    if worst == "fail":
        print(f"::error::recall/precision bound breached — precision: {prec_detail} | "
              f"sec 2.05 recall: {sec_detail}")
        return 2
    if worst == "unknown":
        print(f"::warning::recall/precision could not be verified — precision: {prec_detail} | "
              f"sec 2.05 recall: {sec_detail}. UNKNOWN is not a pass.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
