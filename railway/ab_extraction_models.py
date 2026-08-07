#!/usr/bin/env python3
"""A/B candidate extraction models against GROUND TRUTH, not against each other.

    python3 ab_extraction_models.py                    # SEC gold set, default models
    python3 ab_extraction_models.py --corpus news      # the news gold set
    python3 ab_extraction_models.py --limit 8          # cheaper, noisier
    python3 ab_extraction_models.py --dry-run          # fetch + window only, no spend

TWO CORPORA, ONE SCORER
-----------------------
`--corpus sec` reads the SEC Item 2.05 gold set (counts a filing states about
itself). `--corpus news` reads the news gold set built by
`news_goldset_build.py` (counts two independent outlets, or an outlet and an
official filing, both state). They differ only in where an item's gold count
and its window come from; the guard order, the three states and the arithmetic
below are shared, because two definitions of "correct" is how a swap ships on
the friendlier one.

The news corpus exists because the SEC result was not transferable. On SEC
filings the incumbent and `google/gemini-2.5-flash-lite` both scored 16/16 at
0.388x the price, and the swap was still not made: news is the higher-volume,
messier, worse-punctuated path, and nothing had measured it.

WHY THIS IS NOT THE SIBLING'S HARNESS
-------------------------------------
The sibling project scores a candidate model by AGREEMENT WITH THE INCUMBENT,
because it has no independent answer key. Its own output says so in as many
words: read the disagreements, not the percentages, because the incumbent is
not ground truth. That is the best it can do there.

This tracker can do better, and the difference is the whole reason to trust a
swap. `docs/recall-reference-sets/sec-item-205-us-2025-07_2026-06.goldset.json`
is 57 SEC Form 8-K Item 2.05 events enumerated from the filer's own structured
item code, each carrying `stated_job_count` and the verbatim sentence it came
from, decided by an editor before any model saw them. So the question here is
not "does the cheap model agree with DeepSeek" but "does the cheap model
recover the number the filing actually states" — and a model that disagrees
with the incumbent by being RIGHT scores as right.

The second answer key is this repo's own guard stack. `_count_in_text`
enforces a verbatim receipt for the headcount, `_percent_only_mention` refuses
a percentage dressed as a count. A model that invents a plausible number is
rejected by production without a human, so "how often would this model be
thrown out by our own guards" is measurable rather than estimated.

WHAT IT DELIBERATELY DOES NOT MEASURE
-------------------------------------
Search recall. `edgar_recall_probe.py` already answers "which stage drops a
gold filing", including the full-text-search pagination cap, and it re-runs the
production search to do it. Re-searching per model would let two models see
different windows and would price the comparison in SEC round trips. So every
model here reads the SAME bytes: one fetch per filing, through the production
window builder (`edgar._fetch_filing_text`), then N models over that one string.

THREE STATES, NEVER TWO
-----------------------
An item whose gold count is not inside the production window is not a model
failure — no model could pass `_count_in_text` on it — so it is EXCLUDED from
the accuracy denominator and reported on its own line. An item whose call
errored is UNKNOWN, never a miss. Absence of a signal is not a pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# extractor / spend / sources.edgar are imported INSIDE the functions that call
# them, not here. `score()` is pure arithmetic over already-collected results,
# and its guards are the ones that decide whether a swap ships; requiring the
# openai SDK to import them would make the one test that must always run depend
# on the one dependency a scoring bug cannot involve.

GOLDSET = Path(__file__).resolve().parent.parent / "docs" / "recall-reference-sets" / \
    "sec-item-205-us-2025-07_2026-06.goldset.json"
NEWS_GOLDSET = Path(__file__).resolve().parent.parent / "docs" / "recall-reference-sets" / \
    "news-corroborated-2026-08.goldset.json"

# Incumbent FIRST. Every table below is read against it, and the cost column is
# only meaningful next to the model currently being paid for.
DEFAULT_MODELS = (
    "deepseek/deepseek-chat",
    "deepseek/deepseek-chat-v3.1",
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
)

# Production sends max_tokens=1000 (extractor.extract_layoff_data). Kept
# identical: a harness that lets the model write more than production allows
# measures a model production would have truncated.
MAX_TOKENS = 1000

# Pacing for the news corpus, which reads dozens of frozen snapshots from ONE
# archive. Measured 2026-08-06: at a 1-second gap the Internet Archive stopped
# accepting connections outright after 20 reads and refused the remaining 48,
# which is a rate limit wearing the costume of a corpus. Five seconds is under
# the ~15/minute the archive tolerates.
WAYBACK_GAP_SECONDS = float(os.environ.get("AB_WAYBACK_GAP_SECONDS", "5.0"))
# Below this share of the corpus actually read, the run reports UNKNOWN instead
# of a table. A percentage computed over whatever survived an archive outage is
# not a smaller measurement, it is a different one, and nothing on the page
# would say so. Same rule as recall_goldset.UNREACHABLE_CEILING.
MIN_FETCHED_SHARE = float(os.environ.get("AB_MIN_FETCHED_SHARE", "0.75"))


def load_goldset(path=GOLDSET):
    events = json.loads(Path(path).read_text())["reference_events"]
    return [e for e in events if e.get("stated_job_count")]


def load_news_goldset(path=NEWS_GOLDSET):
    """The news items whose model input can actually be rebuilt.

    `window_source` is decided by the BUILDER, before any model runs, and
    anything other than `wayback_article` means the bytes production fed the
    model no longer exist (a Google News headline window) or were never frozen.
    Those items are listed in the manifest's `excluded_rows` with their reason;
    scoring them against a substituted window would measure a task production
    never performed.
    """
    events = json.loads(Path(path).read_text(encoding="utf-8"))["reference_events"]
    return [e for e in events if e.get("stated_job_count")
            and e.get("window_source") == "wayback_article"
            and e.get("frozen_window_url")]


def build_prompt(raw):
    """Byte-identical to extractor.extract_layoff_data's user message."""
    return (f"Extract layoff data from this source:\n\n"
            f"SOURCE TYPE: {raw.get('source_type')}\n"
            f"SOURCE NAME: {raw.get('source_name')}\n"
            f"COMPANY (if known): {raw.get('company_name') or 'Unknown'}\n"
            f"TICKER (if known): {raw.get('ticker') or 'Unknown'}\n"
            f"DATE: {raw.get('filing_date') or 'Unknown'}\n\n"
            f"TEXT:\n{raw.get('raw_text')}")


def judge(model, raw_text, prompt, gold_count):
    """One production-shaped extraction, scored by the production guard order.

    Returns a dict whose `verdict` is one of accepted / dropped / unknown, plus
    `count_matches_gold` when a count survived. The guards are IMPORTED from
    extractor, never restated, so this cannot drift from what production does.
    """
    import extractor
    import spend

    # Re-checked before EVERY call, not once at startup. record_usage() trips
    # the per-run ceiling mid-loop, and a harness that only asked at the top
    # would sail straight past it -- eighty calls is exactly the shape of run
    # that discovers its own estimate was low. A stop here is `budget_stop`,
    # which score() treats as UNKNOWN, never as a model failing.
    if not spend.paid_reads_enabled():
        return {"verdict": "unknown", "stage": "budget_stop"}

    try:
        resp = extractor._get_client().chat.completions.create(
            extra_body=extractor.USAGE_ACCOUNTING,
            model=model, max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": extractor.SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}])
    except Exception as exc:
        return {"verdict": "unknown", "stage": "llm_error", "detail": str(exc)[:160]}

    usage = getattr(resp, "usage", None)
    spend.record_usage(model, usage)
    out = {"usage": _usage_dict(usage)}

    choice = resp.choices[0] if resp.choices else None
    text = (choice.message.content or "").strip() if choice and choice.message else ""
    if not text:
        return {**out, "verdict": "unknown", "stage": "llm_empty_response"}
    try:
        got = extractor._parse_json_response(text)
    except Exception:
        return {**out, "verdict": "dropped", "stage": "json_parse_error",
                "detail": text[:120]}
    if not isinstance(got, dict):
        return {**out, "verdict": "dropped", "stage": "non_object_json"}

    out["model_job_count"] = got.get("job_count")
    out["model_company"] = got.get("company_name")

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
    return {**out, "verdict": "accepted", "stage": "accepted",
            "count_matches_gold": count == gold_count, "count": count}


def _usage_dict(usage):
    if usage is None:
        return {}
    get = (lambda k: getattr(usage, k, None)) if not isinstance(usage, dict) \
        else usage.get
    return {"prompt_tokens": get("prompt_tokens") or 0,
            "completion_tokens": get("completion_tokens") or 0,
            "cost": float(get("cost") or 0)}


def score(rows, models):
    """Per-model tallies from the raw per-item judgements. Pure, so it is
    testable without a network or a key.

    `rows` is a list of {"gold_count_in_window": bool, "by_model": {m: judge}}.

    THE DENOMINATOR IS THE POINT. An item whose gold count never entered the
    window cannot be recovered by any model, so counting it as a miss would
    charge every model for a window defect and flatten the very difference this
    exists to measure. It is excluded here and reported on its own line.
    """
    out = {}
    for m in models:
        scorable = [r for r in rows if r["gold_count_in_window"]]
        judged = [r["by_model"][m] for r in scorable if m in r["by_model"]]
        known = [j for j in judged if j.get("verdict") != "unknown"]
        accepted = [j for j in known if j["verdict"] == "accepted"]
        cost = sum((j.get("usage") or {}).get("cost", 0) for r in rows
                   for j in [r["by_model"].get(m)] if j)
        tin = sum((j.get("usage") or {}).get("prompt_tokens", 0) for r in rows
                  for j in [r["by_model"].get(m)] if j)
        tout = sum((j.get("usage") or {}).get("completion_tokens", 0) for r in rows
                   for j in [r["by_model"].get(m)] if j)
        stages = {}
        for j in known:
            stages[j["stage"]] = stages.get(j["stage"], 0) + 1
        out[m] = {
            "scorable": len(scorable),
            "unknown": len(judged) - len(known),
            "accepted": len(accepted),
            "correct": sum(1 for j in accepted if j.get("count_matches_gold")),
            "wrong_count": sum(1 for j in accepted if not j.get("count_matches_gold")),
            "calls": sum(1 for r in rows if r["by_model"].get(m)),
            "cost": cost, "tokens_in": tin, "tokens_out": tout,
            "stages": stages,
        }
    return out


def _fmt_pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "n/a"


def report(rows, models, scored, heading="ACCURACY AGAINST THE SEC ITEM 2.05 GOLD SET",
           item_word="filings"):
    excluded = [r for r in rows if not r["gold_count_in_window"]]
    print("\n" + "=" * 78)
    print(heading)
    print("=" * 78)
    print(f"{len(rows)} {item_word} fetched; {len(excluded)} excluded because the stated "
          f"count never entered\nthe production window (a window defect, not a model "
          f"defect); {len(rows) - len(excluded)} scorable.")
    for r in excluded:
        print(f"    EXCLUDED  {r['label'][:44]:46} gold={r['gold_count']}  "
              f"the count is not in the rebuilt window")
    print()
    print(f"{'model':32}{'posts':>7}{'correct':>9}{'wrong':>7}{'unkn':>6}"
          f"{'$/item':>10}{'$/mo @470':>11}")
    print("-" * 78)
    for m in models:
        s = scored[m]
        per_item = s["cost"] / s["calls"] if s["calls"] else 0
        print(f"{m:32}{s['accepted']:>7}{s['correct']:>9}{s['wrong_count']:>7}"
              f"{s['unknown']:>6}{per_item:>10.6f}{per_item * 470 * 30.4:>11.2f}")
    print("\n'correct' = the count this model posted equals the gold count."
          "\n'$/mo @470' prices THIS token mix at the measured 470 cron calls/day.")

    print("\n" + "=" * 78)
    print("WHERE THE CANDIDATES DIFFER FROM THE INCUMBENT, ITEM BY ITEM")
    print("=" * 78)
    print("Read these before the percentages. A candidate that disagrees by being")
    print("RIGHT is not a regression, and a percentage cannot tell you which it is.\n")
    incumbent = models[0]
    for r in rows:
        base = r["by_model"].get(incumbent) or {}
        diffs = []
        for m in models[1:]:
            mine = r["by_model"].get(m) or {}
            if (mine.get("verdict"), mine.get("count")) != (base.get("verdict"), base.get("count")):
                diffs.append((m, mine))
        if not diffs:
            continue
        print(f"  {r['label'][:44]:46} gold={r['gold_count']}"
              f"{'' if r['gold_count_in_window'] else '  [NOT IN WINDOW]'}")
        print(f"      {incumbent:30} {base.get('stage', '?')}"
              f" count={base.get('count')}")
        for m, mine in diffs:
            print(f"      {m:30} {mine.get('stage', '?')} count={mine.get('count')}")
    print()
    for m in models:
        print(f"  {m}: " + ", ".join(f"{k}={v}" for k, v in
                                     sorted(scored[m]["stages"].items(),
                                            key=lambda kv: -kv[1])))


def run(models, limit, dry_run, out_path):
    import extractor
    from sources import edgar

    events = load_goldset()[:limit]
    print(f"{len(events)} gold events; models: {', '.join(models)}")
    if dry_run:
        print("DRY RUN: fetching and windowing only, no model is called and "
              "nothing is spent.")

    rows = []
    for i, ev in enumerate(events, 1):
        gold = int(ev["stated_job_count"])
        try:
            raw_text = edgar._fetch_filing_text(ev["official_source_url"])
        except Exception as exc:
            print(f"  {i:>2}. {ev['filer'][:40]:42} FETCH FAILED ({str(exc)[:60]}) "
                  f"— UNKNOWN, not a miss")
            continue
        raw = {"source_type": "8K", "source_name": "SEC EDGAR",
               "company_name": ev["filer"], "ticker": None,
               "filing_date": ev["filing_date"], "raw_text": raw_text}
        in_window = extractor._count_in_text(gold, raw_text)
        print(f"  {i:>2}. {ev['filer'][:40]:42} gold={gold:<7} "
              f"window={'has count' if in_window else 'MISSING count'}")
        row = {"label": ev["filer"], "gold_count": gold,
               "gold_count_in_window": in_window, "by_model": {}}
        _judge_row(row, raw, raw_text, gold, models, dry_run)
        rows.append(row)

    return _finish(rows, models, dry_run, out_path,
                   "ACCURACY AGAINST THE SEC ITEM 2.05 GOLD SET", "filings")


def run_news(models, limit, dry_run, out_path):
    """The same comparison over corroborated NEWS events.

    The window is `gdelt.window_article_markup`, the production news window
    builder, run over the FROZEN Wayback snapshot the manifest names rather than
    over the live URL. A live re-fetch would let the corpus drift between runs
    and would score today's page against a count taken from the page as it was
    read; a frozen snapshot makes the comparison repeatable and re-auditable.
    The FETCH is the harness's own problem and gets the shared retry, because
    an archive that stops answering is not a model result.
    A snapshot that will not load is UNKNOWN and the item is skipped, never
    counted against a model. Too many of them and the whole run is UNKNOWN.
    """
    import extractor
    from http_retry import get_with_retry
    from sources import gdelt

    events = load_news_goldset()[:limit]
    print(f"{len(events)} corroborated news events; models: {', '.join(models)}")
    if dry_run:
        print("DRY RUN: fetching and windowing only, no model is called and "
              "nothing is spent.")

    rows, unreachable = [], 0
    for i, ev in enumerate(events, 1):
        gold = int(ev["stated_job_count"])
        label = f"{ev['company_name']} ({ev['primary_outlet']})"
        # One archive, dozens of sequential reads. The politeness gap is the
        # difference between a measurement and a rate-limit that reads as a
        # model failure, and every second here is cheaper than a re-run.
        time.sleep(WAYBACK_GAP_SECONDS)
        resp = get_with_retry(ev["frozen_window_url"],
                              headers={"User-Agent": gdelt.BROWSER_UA},
                              attempts=3, timeout=30, backoff=20)
        if resp is None or resp.status_code != 200:
            unreachable += 1
            got = "no response" if resp is None else f"HTTP {resp.status_code}"
            print(f"  {i:>2}. {label[:40]:42} SNAPSHOT UNREADABLE ({got}) "
                  f"- UNKNOWN, not a miss")
            continue
        try:
            raw_text = gdelt.window_article_markup(resp.text)
        except Exception as exc:
            unreachable += 1
            print(f"  {i:>2}. {label[:40]:42} WINDOW FAILED "
                  f"({str(exc)[:50]}) - UNKNOWN, not a miss")
            continue
        # company_name is None because that is what the news path passes: the
        # collectors never know the employer, the model names it. Handing the
        # answer to the model in its own prompt would measure nothing.
        raw = {"source_type": "news", "source_name": ev.get("primary_outlet"),
               "company_name": None, "ticker": None,
               "filing_date": ev.get("announcement_date") or ev.get("layoff_date"),
               "raw_text": raw_text}
        in_window = extractor._count_in_text(gold, raw_text)
        print(f"  {i:>2}. {label[:40]:42} gold={gold:<7} "
              f"window={'has count' if in_window else 'MISSING count'}")
        row = {"label": label, "gold_count": gold,
               "gold_count_in_window": in_window,
               "corroboration": ev.get("corroboration_kinds"), "by_model": {}}
        _judge_row(row, raw, raw_text, gold, models, dry_run)
        rows.append(row)

    if events and len(rows) < MIN_FETCHED_SHARE * len(events):
        print(f"\nUNKNOWN: only {len(rows)} of {len(events)} snapshots could be read "
              f"({unreachable} unreadable).\nThe archive, not a model, decided which "
              f"items were in this run, so there is no\ncomparison here to report. "
              f"Re-dispatch later, or raise AB_WAYBACK_GAP_SECONDS.")
        return 3

    return _finish(rows, models, dry_run, out_path,
                   "ACCURACY AGAINST THE CORROBORATED NEWS GOLD SET", "news events")


def _judge_row(row, raw, raw_text, gold, models, dry_run):
    if dry_run:
        return
    prompt = build_prompt(raw)
    for m in models:
        row["by_model"][m] = judge(m, raw_text, prompt, gold)
        j = row["by_model"][m]
        print(f"        {m:32} {j['stage']:32} count={j.get('count')}")


def _finish(rows, models, dry_run, out_path, heading, item_word):
    if dry_run:
        n_in = sum(1 for r in rows if r["gold_count_in_window"])
        print(f"\nDRY RUN COMPLETE: {len(rows)} fetched, {n_in} would be scorable, "
              f"{len(rows) - n_in} excluded for a window that lacks the count.")
        return 0

    scored = score(rows, models)
    report(rows, models, scored, heading, item_word)
    if out_path:
        Path(out_path).write_text(json.dumps(
            {"rows": rows, "scored": scored, "models": list(models)}, indent=1))
        print(f"\nwrote {out_path}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", default=os.environ.get("AB_MODELS", ""),
                    help="comma-separated; incumbent first. Default: the tuned list.")
    ap.add_argument("--limit", type=int,
                    default=int(os.environ.get("AB_LIMIT") or 20),
                    help="how many gold events to run (each costs one call per model)")
    ap.add_argument("--dry-run", action="store_true",
                    default=bool(os.environ.get("AB_DRY_RUN")),
                    help="fetch and window only; calls no model and spends nothing")
    ap.add_argument("--out", default=os.environ.get("AB_OUT", ""))
    ap.add_argument("--corpus", choices=("sec", "news"),
                    default=(os.environ.get("AB_CORPUS") or "sec"),
                    help="which gold set to score against")
    args = ap.parse_args()

    models = tuple(m.strip() for m in args.models.split(",") if m.strip()) \
        or DEFAULT_MODELS

    if not args.dry_run:
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("OPENROUTER_API_KEY is not set — nothing can be measured. "
                  "This is UNKNOWN, not a pass.", file=sys.stderr)
            return 3
        # The same brake every paid job here honours. A degraded run reports
        # that it measured nothing and exits 0: a spend guard tripping is a
        # deferral, never a red run.
        import spend
        if not spend.paid_reads_enabled():
            print("DEGRADED: the spend guard is holding paid reads off, so this "
                  "comparison measured nothing. Exiting 0 — a budget stop is a "
                  "deferral, not a failure. Re-dispatch after the window resets.")
            return 0
    runner = run_news if args.corpus == "news" else run
    return runner(models, args.limit, args.dry_run, args.out)


if __name__ == "__main__":
    sys.exit(main())
