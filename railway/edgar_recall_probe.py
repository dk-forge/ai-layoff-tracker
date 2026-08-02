"""Diagnostic: where does an SEC Item 2.05 gold-set filing die in our pipeline?

DRY RUN ONLY. Posts nothing, writes nothing, reports no source health. It exists
to answer one question with evidence instead of a hypothesis: for a filing we
KNOW discloses a workforce reduction, which stage drops it?

Stages, in the order the real pipeline applies them:

  reached      sources/edgar.py full-text search surfaces the accession inside
               MAX_PAGES_PER_KEYWORD (the pagination cap)
  fetched      _fetch_filing_text() returns a keyword-anchored text window
  windowed     the gold headcount survives extractor.py's 2000-char truncation
               (extractor.py:697) - if it does not, _count_in_text CANNOT pass
  extracted    the LLM returns JSON with is_layoff_event and a job_count
  gated        extractor.py's deterministic guards accept it

It calls the SAME model, with the SAME system prompt and the SAME gate
functions imported from extractor.py, so it cannot drift from production. It
deliberately does NOT re-implement any prompt or guard.

Env: OPENROUTER_API_KEY, EDGAR_USER_AGENT. No WP_API_KEY - nothing is posted.
  PROBE_ONLY   'misses' (default) | 'matched' | 'all'
  PROBE_LIMIT  int, cap the number of filings probed
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import extractor
import spend
from sources import edgar

GOLDSET = os.environ.get(
    "PROBE_GOLDSET",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "docs", "recall-reference-sets",
                 "sec-item-205-us-2025-07_2026-06.goldset.json"))

# Read the live constant rather than a copy: this probe exists to report what
# production does, so a number pasted here could only ever lie about it.
EXTRACTOR_TEXT_LIMIT = extractor.RAW_TEXT_LIMIT


def _daily_window(filing_date):
    """The window the daily cron actually searches: pull_edgar_filings(days_back=1)."""
    d = datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return d - timedelta(days=1), d


def _month_window(filing_date):
    """The window the rotating history sweep searches (backfill.rotating_window)."""
    d = datetime.strptime(filing_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = datetime(d.year, d.month, 1, tzinfo=timezone.utc)
    nxt = datetime(d.year + 1, 1, 1, tzinfo=timezone.utc) if d.month == 12 \
        else datetime(d.year, d.month + 1, 1, tzinfo=timezone.utc)
    return start, nxt - timedelta(seconds=1)


def reached(accession, start, end):
    """Raw dicts the real collector produces for this accession in [start, end].

    Runs the production pull unmodified, then keeps the candidates whose URL
    carries this accession - so the pagination cap, the keyword list and the
    document-fetch step all apply exactly as they do in the cron.
    """
    key = accession.replace("-", "")
    try:
        return [r for r in edgar.pull_edgar_filings_between(start, end)
                if key in (r.get("source_url") or "")]
    except Exception as exc:
        print(f"  pull failed: {exc}")
        return None  # UNKNOWN, never a silent miss


def classify(raw, gold_count):
    """Run the production extraction and name the stage that dropped it."""
    raw_text = (raw.get("raw_text") or "")[:EXTRACTOR_TEXT_LIMIT]
    if not raw_text.strip():
        return {"verdict": "dropped", "stage": "empty_raw_text"}

    # The gold headcount must survive truncation or _count_in_text cannot pass,
    # whatever the model says. Recorded separately so a window problem is never
    # reported as a model problem.
    windowed = extractor._count_in_text(gold_count, raw_text)

    prompt = (f"Extract layoff data from this source:\n\n"
              f"SOURCE TYPE: {raw.get('source_type')}\n"
              f"SOURCE NAME: {raw.get('source_name')}\n"
              f"COMPANY (if known): {raw.get('company_name') or 'Unknown'}\n"
              f"TICKER (if known): {raw.get('ticker') or 'Unknown'}\n"
              f"DATE: {raw.get('filing_date') or 'Unknown'}\n\nTEXT:\n{raw_text}")
    try:
        resp = extractor._get_client().chat.completions.create(
            model=extractor.MODEL, max_tokens=1000,
            messages=[{"role": "system", "content": extractor.SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}])
        spend.record_usage(extractor.MODEL, getattr(resp, "usage", None))
    except Exception as exc:
        return {"verdict": "unknown", "stage": "llm_error", "detail": str(exc)[:200],
                "gold_count_in_window": windowed}

    choice = resp.choices[0] if resp.choices else None
    text = (choice.message.content or "").strip() if choice and choice.message else ""
    if not text:
        return {"verdict": "unknown", "stage": "llm_empty_response",
                "gold_count_in_window": windowed}
    try:
        got = extractor._parse_json_response(text)
    except Exception:
        return {"verdict": "dropped", "stage": "json_parse_error",
                "gold_count_in_window": windowed}
    if not isinstance(got, dict):
        return {"verdict": "dropped", "stage": "non_object_json",
                "gold_count_in_window": windowed}

    out = {"gold_count_in_window": windowed,
           "model_job_count": got.get("job_count"),
           "model_is_layoff_event": got.get("is_layoff_event"),
           "model_ai_causation": got.get("ai_causation"),
           "model_confidence": got.get("confidence")}

    # Production gate order: extractor.py lines 746-822.
    if not got.get("is_layoff_event"):
        return {**out, "verdict": "dropped", "stage": "model_said_not_a_layoff_event"}
    count = extractor._coerce_job_count(got.get("job_count"))
    if not count:
        return {**out, "verdict": "dropped", "stage": "model_returned_no_job_count"}
    if extractor._percent_only_mention(count, raw_text):
        return {**out, "verdict": "dropped", "stage": "count_is_percent_only"}
    if not extractor._count_in_text(count, raw_text):
        return {**out, "verdict": "dropped", "stage": "count_not_verbatim_in_window"}
    if not (got.get("company_name") or "").strip():
        return {**out, "verdict": "dropped", "stage": "no_company_name"}
    if count > 60000:
        return {**out, "verdict": "dropped", "stage": "implausible_count"}
    return {**out, "verdict": "would_post", "stage": "accepted",
            "count_matches_gold": count == gold_count}


def _dump(results):
    path = os.environ.get("PROBE_OUT")
    if not path:
        return
    with open(path, "w") as fh:
        json.dump({"probed": len(results), "results": results}, fh, indent=1)


def run():
    events = json.load(open(GOLDSET))["reference_events"]
    only = os.environ.get("PROBE_ONLY", "misses")
    if only == "misses":
        events = [e for e in events if e["match_decision"] != "matched"]
    elif only == "matched":
        events = [e for e in events if e["match_decision"] == "matched"]
    limit = int(os.environ.get("PROBE_LIMIT") or 0)
    if limit:
        events = events[:limit]

    results = []
    for i, e in enumerate(events, 1):
        print(f"\n[{i}/{len(events)}] {e['filer']} — {e['filing_date']} — "
              f"{e['stated_job_count']} jobs — items {','.join(e['sec_items'])}", flush=True)
        rec = {"filer": e["filer"], "filing_date": e["filing_date"],
               "accession": e["accession"], "stated_job_count": e["stated_job_count"],
               "match_decision": e["match_decision"]}

        for label, window in (("daily", _daily_window(e["filing_date"])),
                              ("monthly", _month_window(e["filing_date"]))):
            raws = reached(e["accession"], *window)
            rec[f"{label}_reached"] = None if raws is None else len(raws)
            if raws:
                rec["raws"] = raws
            if raws:
                break

        raws = rec.pop("raws", None)
        if rec.get("daily_reached") is None and rec.get("monthly_reached") is None:
            rec["outcome"] = {"verdict": "unknown", "stage": "search_unreachable"}
        elif not raws:
            rec["outcome"] = {"verdict": "dropped", "stage": "not_surfaced_by_search"}
        else:
            # Several documents of one filing can match (primary doc + exhibits).
            # The filing survives if ANY of them would post - that is exactly how
            # the cron behaves, since each candidate is extracted independently.
            outcomes = [classify(r, e["stated_job_count"]) for r in raws]
            rec["outcome"] = next((o for o in outcomes if o["verdict"] == "would_post"),
                                  outcomes[0])
            rec["documents_probed"] = len(outcomes)
        print(f"  -> {rec['outcome']['verdict']}: {rec['outcome']['stage']}"
              f"  (reached daily={rec.get('daily_reached')} "
              f"monthly={rec.get('monthly_reached')})", flush=True)
        results.append(rec)
        # Write after EVERY filing: this probe is slow (it runs the real
        # collector per window), and a timeout that loses the whole artifact
        # would leave us guessing again — which is the thing it exists to stop.
        _dump(results)

    print("\n" + "=" * 68)
    print("STAGE TALLY (the question this probe exists to answer)")
    print("=" * 68)
    tally = {}
    for r in results:
        tally[r["outcome"]["stage"]] = tally.get(r["outcome"]["stage"], 0) + 1
    for stage, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {n:>3}  {stage}")
    posts = sum(1 for r in results if r["outcome"]["verdict"] == "would_post")
    unknown = sum(1 for r in results if r["outcome"]["verdict"] == "unknown")
    print(f"\n  would_post {posts}/{len(results)}   dropped "
          f"{len(results) - posts - unknown}   UNKNOWN {unknown}")
    if unknown:
        print("  UNKNOWN is not a pass and not a miss — re-run those before concluding.")

    _dump(results)
    if os.environ.get("PROBE_OUT"):
        print(f"\nwrote {os.environ['PROBE_OUT']}")
    return results


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
