#!/usr/bin/env python3
"""Score the AI-causation classifier against an answer key two models could not
have written on their own.

    python3 railway/ab_ai_causation.py            # label + score the frozen sample
    python3 railway/ab_ai_causation.py --dry-run  # build every prompt, spend nothing
    python3 railway/ab_ai_causation.py --limit 20 # cheaper, noisier

THE QUESTION
------------
On 2026-08-07 `OPENROUTER_MODEL` moved to `google/gemini-2.5-flash-lite` on a
news-EXTRACTION gold set: 30/30 counts, 0.388x the cost. Sound, on the thing it
measured. But `MODEL` also governs AI CAUSATION — `extract_layoff_data` derives
`ai_explicit` from the causation label, `classify_ai_evidence()` re-derives it on
the daily sweep, and both use `MODEL` on purpose ("AI-causation is
correctness-critical"). The swap therefore moved the classifier behind the field
the whole product is named after, and nothing measured that.

WHY THE CANDIDATE IS NOT ONE OF THE LABELLERS
----------------------------------------------
A gold set is worth nothing if the model being scored helped write it: every row
where it agreed with the other labeller would be correct BY CONSTRUCTION, and
only the disagreements could ever count against it. So the two labellers are the
PRE-SWAP INCUMBENT (`deepseek/deepseek-chat`) and one model from a third family
(`openai/gpt-4.1-mini`) — neither of them the candidate, and not two members of
the same family, because two models that share a lineage agreeing is one
observation wearing two coats.

Where the two labellers AGREE, that is the label. Where they DISAGREE, a HUMAN
reads: the run writes those rows to a single review file and marks them
UNADJUDICATED, and they enter no score until `--adjudications` supplies the
owner's calls. A tie broken by a third model vote would make this a measurement
of model consensus, and model consensus is exactly what the disagreements say is
unreliable.

The incumbent's own score is therefore INFLATED BY CONSTRUCTION on the
model-agreed rows and is printed with that said out loud. The one fair
head-to-head is the human-adjudicated subset, and it is reported separately.

THE DECISION RULE IS IMPORTED, NOT RESTATED
--------------------------------------------
Every model here is asked `extractor.ai_causation_prompt()` and its answer is
put through `extractor.finalize_ai_causation()` — the same verbatim-quote guard
production runs, which downgrades a causal label with no receipt to `unknown`.
So a model that invents a supporting phrase scores as production would treat it,
not as it would like to be treated. `ai_explicit` comes from
`extractor.ai_explicit_from_causation()`, the single definition.

STRATIFIED, SO THE ARITHMETIC IS WEIGHTED
------------------------------------------
The corpus (railway/ai_causation_sample_build.py) over-samples the 96
AI-attributed rows and the 94 hard negatives against 1,742 plain negatives,
because a uniform draw of 200 from 1,938 would hold ~10 positives and almost no
hard negatives — the two places error lives. Sample precision is therefore NOT
population precision. Both are printed: per-stratum rates with Wilson intervals
(the primitive), and a population-weighted figure whose interval is the weighted
average of the per-stratum Wilson bounds.

THREE STATES, NEVER TWO. A call that errored is UNKNOWN, not a miss. A budget
stop is UNDECIDED and exits 0. A row whose labellers disagree is UNADJUDICATED
and is counted nowhere until a human has read it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import extractor  # noqa: E402
import spend  # noqa: E402
from recall_goldset import wilson  # noqa: E402

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "docs" / "recall-reference-sets"
SAMPLE_PATH = REF / "ai-causation-2026-08.sample.json"
GOLDSET_PATH = REF / "ai-causation-2026-08.goldset.json"
REVIEW_PATH = REF / "ai-causation-2026-08.review.md"
ADJUDICATION_PATH = REF / "ai-causation-2026-08.adjudications.json"

# The pre-swap incumbent, first. The second is deliberately from neither the
# incumbent's family nor the candidate's.
LABELLERS = os.environ.get(
    "AIC_LABELLERS", "deepseek/deepseek-chat,openai/gpt-4.1-mini").split(",")
# The model actually in production since 2026-08-07 (extractor.MODEL's default).
CANDIDATE = os.environ.get("AIC_CANDIDATE", "google/gemini-2.5-flash-lite")

MAX_ATTEMPTS = 2          # retry by calling metered_call AGAIN, never by looping inside it
SLEEP_BETWEEN = 0.15


# ---------------------------------------------------------------------------
# One call, one gate read
# ---------------------------------------------------------------------------

def ask(model, text):
    """One AI-causation verdict, or None if the call could not be made.

    Exactly ONE request per `metered_call`. Retrying happens by calling this
    function again from `ask_with_retry` — a callable that retries inside the
    gate puts several charges behind one gate read, which is the defect that
    overshot a run ceiling by 36 calls on 2026-08-11.
    """
    prompt = extractor.ai_causation_prompt(text)
    response = spend.metered_call(
        model,
        lambda: extractor._get_client().chat.completions.create(
            extra_body=extractor.USAGE_ACCOUNTING,
            model=model, max_tokens=250,
            messages=[{"role": "system", "content": extractor.MINI_SYSTEM},
                      {"role": "user", "content": prompt}],
        ),
        what=f"AI-causation label from {model}")
    content = response.choices[0].message.content if response.choices else ""
    return extractor.finalize_ai_causation(
        extractor._parse_json_response(content or ""), text)


def ask_with_retry(model, text):
    """(verdict_dict, state). state is 'ok', 'error' or 'budget_stop'."""
    last = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            result = ask(model, text)
        except spend.PaidReadsOff:
            # Not a verdict and not a failure. Nothing was asked.
            return None, "budget_stop"
        except Exception as exc:  # noqa: BLE001 — an errored call is UNKNOWN
            last = exc
            time.sleep(0.5 * (attempt + 1))
            continue
        if result is not None:
            return result, "ok"
        last = "model returned no parsable object"
    print(f"  ! {model} could not be read: {last}")
    return None, "error"


def verdict_of(result):
    """True/False `ai_explicit`, or None when there is no verdict."""
    if not result:
        return None
    return extractor.ai_explicit_from_causation(result.get("ai_causation"))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _fmt(successes, total):
    p, lo, hi = wilson(successes, total)
    if p is None:
        return f"{successes}/{total} — no sample, so no interval"
    return f"{successes}/{total} = {p:.1%} (Wilson 95% CI [{lo:.1%}, {hi:.1%}])"


def _weighted(pairs):
    """pairs = [(weight, successes, total)]. Returns (point, lo, hi) as the
    weight-averaged per-stratum Wilson bounds, or (None, None, None).

    A weighted average of per-stratum bounds is CONSERVATIVE relative to a
    single pooled interval and is the honest shape here: the denominators are
    observed counts, not estimates, so only the per-stratum rates carry the
    uncertainty."""
    usable = [(w, s, t) for (w, s, t) in pairs if t]
    if not usable:
        return (None, None, None)
    mass = sum(w * t for w, s, t in usable)
    if mass <= 0:
        return (None, None, None)
    out = []
    for idx in range(3):
        acc = 0.0
        for w, s, t in usable:
            acc += w * t * wilson(s, t)[idx]
        out.append(acc / mass)
    return tuple(out)


def score_model(name, items, gold, verdicts, population, drawn):
    """Per-stratum and population-weighted precision/recall for one model."""
    strata = sorted({i["stratum"] for i in items})
    per = {}
    for stratum in strata:
        tp = fp = fn = tn = 0
        for item in items:
            if item["stratum"] != stratum:
                continue
            g = gold.get(item["id"])
            v = verdicts.get(name, {}).get(item["id"])
            if g is None or v is None:
                continue          # UNADJUDICATED or UNKNOWN: counted nowhere
            if v and g:
                tp += 1
            elif v and not g:
                fp += 1
            elif (not v) and g:
                fn += 1
            else:
                tn += 1
        per[stratum] = {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                        "judged": tp + fp + fn + tn}
    weights = {s: (population.get(s, 0) / drawn[s]) if drawn.get(s) else 0.0
               for s in strata}
    precision = _weighted([(weights[s], per[s]["tp"], per[s]["tp"] + per[s]["fp"])
                           for s in strata])
    recall = _weighted([(weights[s], per[s]["tp"], per[s]["tp"] + per[s]["fn"])
                        for s in strata])
    return {"per_stratum": per, "weights": weights,
            "precision": precision, "recall": recall,
            "totals": {k: sum(per[s][k] for s in strata)
                       for k in ("tp", "fp", "fn", "tn", "judged")}}


def _render(triple):
    point, lo, hi = triple
    if point is None:
        return "UNKNOWN — nothing judged in any stratum"
    return f"{point:.1%} (95% CI [{lo:.1%}, {hi:.1%}])"


# ---------------------------------------------------------------------------
# The review file — the only thing that asks for a human
# ---------------------------------------------------------------------------

def write_review(path, rows, candidate_rows, meta):
    lines = [
        "# AI causation — rows that need the owner's eye",
        "",
        f"Built {meta['run_at']} by `railway/ab_ai_causation.py` over "
        f"`docs/recall-reference-sets/ai-causation-2026-08.sample.json`.",
        "",
        "## How to use this file",
        "",
        "Read the TEXT. The only question is: **does this text explicitly say "
        "AI, automation, machine learning or robots CAUSED these cuts, in a "
        "phrase quoted from the text itself?** A company's AI strategy, AI "
        "investment, AI products, or AI used to pick who goes is NOT a cause. "
        "That is the production rule, verbatim.",
        "",
        "Write your call into "
        "`docs/recall-reference-sets/ai-causation-2026-08.adjudications.json` "
        "as `{\"<id>\": true|false}` — `true` means the text supports "
        "`ai_explicit`. Anything you leave out stays UNADJUDICATED and is "
        "scored nowhere; it is never quietly defaulted.",
        "",
        f"**Section 1 is the one that must be filled in** ({len(rows)} rows): the "
        "two independent labellers disagreed, so there is no label at all. "
        f"**Section 2** ({len(candidate_rows)} rows) is optional and is where "
        "the candidate model disagrees with a label the two labellers agreed "
        "on. Filling it in removes the one bias left in the score — a "
        "two-model agreement standing in for truth exactly where the candidate "
        "objects.",
        "",
        "---",
        "",
        f"## Section 1 — the labellers disagree ({len(rows)} rows, REQUIRED)",
        "",
    ]
    if not rows:
        lines += ["_None. The two labellers agreed on every row._", ""]
    for row in rows:
        lines += _review_block(row)
    lines += ["---", "",
              f"## Section 2 — the candidate objects to a model-agreed label "
              f"({len(candidate_rows)} rows, optional)", ""]
    if not candidate_rows:
        lines += ["_None._", ""]
    for row in candidate_rows:
        lines += _review_block(row)
    path.write_text("\n".join(lines) + "\n")


def _yn(value):
    return "UNKNOWN" if value is None else ("AI" if value else "not AI")


def _review_block(row):
    stored = row["stored"]
    votes = " | ".join(f"**{m}**: {_yn(v)}" for m, v in row["votes"].items())
    return [
        f"### id {row['id']} — {row['company_name']}  ",
        f"`{row['stratum']}` · {row['source_type']} · {row['source_name']} · "
        f"{row['layoff_date']} · {row['job_count']} jobs  ",
        f"source: {row['source_url'] or '(none stored)'}",
        "",
        "> " + (row["text"] or "").replace("\n", " ").strip(),
        "",
        f"votes: {votes}  ",
        f"currently stored: `ai_explicit={stored['ai_explicit']}` "
        f"`{stored['ai_causation']}` quote={stored['ai_language']!r}  ",
        f"**owner's call ({row['id']}): [ ] AI    [ ] not AI**",
        "",
    ]


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="score fewer items")
    ap.add_argument("--dry-run", action="store_true",
                    help="build every prompt and call nothing")
    ap.add_argument("--out", default=os.environ.get("AIC_OUT", ""),
                    help="also write the full per-item record here")
    args = ap.parse_args(argv)
    if os.environ.get("AIC_LIMIT"):
        args.limit = int(os.environ["AIC_LIMIT"])
    if os.environ.get("AIC_DRY_RUN"):
        args.dry_run = True

    if not SAMPLE_PATH.exists():
        print(f"no frozen sample at {SAMPLE_PATH}; run "
              f"railway/ai_causation_sample_build.py --write first")
        return 1
    manifest = json.loads(SAMPLE_PATH.read_text())
    items = manifest["items"]
    if args.limit:
        items = items[:args.limit]
    population = manifest["strata_population"]
    drawn = {s: sum(1 for i in items if i["stratum"] == s)
             for s in {i["stratum"] for i in items}}

    models = list(LABELLERS) + [CANDIDATE]
    print(f"corpus: {len(items)} item(s); strata {drawn}")
    print(f"labellers (gold): {' + '.join(LABELLERS)}")
    print(f"candidate (scored): {CANDIDATE}")

    if args.dry_run:
        chars = sum(len(extractor.ai_causation_prompt(i["text"])) for i in items)
        print(f"\nDRY RUN: {len(items) * len(models)} call(s) would be made, "
              f"{chars:,} prompt characters per model (~{chars // 4:,} tokens). "
              f"Nothing was asked and nothing is decided.")
        return 0

    verdicts = {m: {} for m in models}
    raw = {m: {} for m in models}
    states = {m: {"ok": 0, "error": 0, "budget_stop": 0} for m in models}
    budget_stopped = False
    for n, item in enumerate(items, 1):
        for model in models:
            if budget_stopped:
                states[model]["budget_stop"] += 1
                continue
            result, state = ask_with_retry(model, item["text"])
            states[model][state] += 1
            if state == "budget_stop":
                budget_stopped = True
                continue
            if result is not None:
                verdicts[model][item["id"]] = verdict_of(result)
                raw[model][item["id"]] = result
            time.sleep(SLEEP_BETWEEN)
        if n % 25 == 0:
            print(f"  ... {n}/{len(items)} items, "
                  f"${spend.logical_run_cost_usd():.4f} spent")

    print(f"\n{spend.run_summary()}")
    for model in models:
        print(f"  {model:32s} ok={states[model]['ok']:3d} "
              f"error={states[model]['error']:3d} "
              f"not-asked={states[model]['budget_stop']:3d}")

    if budget_stopped:
        # A budget stop is UNDECIDED, never a verdict and never a red run.
        print("\n::notice::spend: the run stopped at its ceiling. The rows "
              "below it were NOT read by anybody, no gold label was written "
              "for them, and nothing is decided by their absence. Re-dispatch "
              "to continue; this run exits 0.")
        spend.note_truncated("per-run ceiling reached mid-corpus")

    # --- gold: where the two labellers agree -------------------------------
    a, b = LABELLERS[0], LABELLERS[1]
    gold, disagree, unread = {}, [], []
    for item in items:
        va, vb = verdicts[a].get(item["id"]), verdicts[b].get(item["id"])
        if va is None or vb is None:
            unread.append(item)
            continue
        if va == vb:
            gold[item["id"]] = va
        else:
            disagree.append(dict(item, votes={a: va, b: vb}))

    adjudications = {}
    if ADJUDICATION_PATH.exists():
        try:
            adjudications = {int(k): bool(v) for k, v in
                             json.loads(ADJUDICATION_PATH.read_text()).items()}
        except (ValueError, TypeError, AttributeError) as exc:
            print(f"::warning::could not read {ADJUDICATION_PATH}: {exc}")
    human_ids = set()
    for item in items:
        if item["id"] in adjudications:
            gold[item["id"]] = adjudications[item["id"]]
            human_ids.add(item["id"])

    still_open = [d for d in disagree if d["id"] not in adjudications]
    candidate_objections = [
        dict(item, votes={a: verdicts[a].get(item["id"]),
                          b: verdicts[b].get(item["id"]),
                          CANDIDATE: verdicts[CANDIDATE].get(item["id"])})
        for item in items
        if item["id"] in gold and item["id"] not in human_ids
        and verdicts[CANDIDATE].get(item["id"]) is not None
        and verdicts[CANDIDATE][item["id"]] != gold[item["id"]]
    ]

    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\ngold labels: {len(gold)} of {len(items)} "
          f"({len(gold) - len(human_ids)} by labeller agreement, "
          f"{len(human_ids)} adjudicated by the owner)")
    print(f"awaiting the owner: {len(still_open)} disagreement(s) "
          f"+ {len(candidate_objections)} optional candidate objection(s)")
    if unread:
        print(f"UNKNOWN (a labeller could not be read): {len(unread)} item(s) — "
              f"no gold label, scored nowhere")

    # --- score --------------------------------------------------------------
    scored = {m: score_model(m, items, gold, verdicts, population, drawn)
              for m in models}
    fair = {}
    if human_ids:
        fair_items = [i for i in items if i["id"] in human_ids]
        fair_drawn = {s: sum(1 for i in fair_items if i["stratum"] == s)
                      for s in {i["stratum"] for i in fair_items}}
        fair = {m: score_model(m, fair_items, gold, verdicts, population,
                               fair_drawn) for m in models}

    print("\n" + "=" * 72)
    print(f"AI CAUSATION — `ai_explicit` against the frozen gold set")
    print("=" * 72)
    for model in models:
        s = scored[model]
        tag = ""
        if model in LABELLERS:
            tag = ("   [INFLATED BY CONSTRUCTION: this model is a gold "
                   "labeller and is right by definition wherever the two "
                   "labellers agreed]")
        print(f"\n{model}{tag}")
        t = s["totals"]
        print(f"  judged {t['judged']}  tp={t['tp']} fp={t['fp']} "
              f"fn={t['fn']} tn={t['tn']}")
        print(f"  precision (population-weighted): {_render(s['precision'])}")
        print(f"  recall    (population-weighted): {_render(s['recall'])}")
        for stratum in sorted(s["per_stratum"]):
            p = s["per_stratum"][stratum]
            print(f"    {stratum:18s} weight x{s['weights'][stratum]:6.2f}  "
                  f"precision {_fmt(p['tp'], p['tp'] + p['fp'])}  |  "
                  f"recall {_fmt(p['tp'], p['tp'] + p['fn'])}")
    if fair:
        print(f"\nFAIR head-to-head — the {len(human_ids)} human-adjudicated "
              f"row(s) only. Small, and the only subset where no model's own "
              f"vote helped write the answer:")
        for model in models:
            t = fair[model]["totals"]
            correct = t["tp"] + t["tn"]
            print(f"  {model:32s} {_fmt(correct, t['judged'])}")
    else:
        print("\nFAIR head-to-head: UNAVAILABLE. No row has been adjudicated by "
              "a human yet, so every gold label here is two models agreeing. "
              "That is not a reason to read the numbers above as truth: it is "
              "the reason the review file exists.")

    verdict = "UNKNOWN"
    if still_open or candidate_objections:
        verdict = ("UNKNOWN pending adjudication — " +
                   f"{len(still_open)} row(s) have no label at all and "
                   f"{len(candidate_objections)} model-agreed label(s) the "
                   f"candidate disputes are unread by a human")
    print(f"\nVERDICT ON THE 2026-08-07 SWAP: {verdict}")
    print("Nothing here changes a production model. That is the owner's call.")

    # --- freeze -------------------------------------------------------------
    REF.mkdir(parents=True, exist_ok=True)
    write_review(REVIEW_PATH, still_open, candidate_objections,
                 {"run_at": run_at})
    goldset = {
        "version": 1,
        "name": "ai-causation-2026-08",
        "run_at": run_at,
        "sample": SAMPLE_PATH.name,
        "labellers": LABELLERS,
        "candidate": CANDIDATE,
        "rule": ("gold = the two labellers agreeing, or the owner's "
                 "adjudication where they did not. No third model vote breaks "
                 "a tie."),
        "strata_population": population,
        "strata_drawn": drawn,
        "counts": {
            "items": len(items),
            "gold_by_agreement": len(gold) - len(human_ids),
            "gold_by_human": len(human_ids),
            "awaiting_human_required": len(still_open),
            "awaiting_human_optional": len(candidate_objections),
            "unknown_unreadable": len(unread),
        },
        "spend_usd": round(spend.logical_run_cost_usd(), 6),
        "truncated": spend.run_truncation(),
        "labels": {str(k): v for k, v in sorted(gold.items())},
        "verdicts": {m: {str(k): v for k, v in sorted(verdicts[m].items())}
                     for m in models},
        "raw": {m: {str(k): v for k, v in sorted(raw[m].items())}
                for m in models},
        "score": {m: scored[m] for m in models},
    }
    GOLDSET_PATH.write_text(json.dumps(goldset, indent=1, sort_keys=True) + "\n")
    print(f"\nwrote {GOLDSET_PATH}")
    print(f"wrote {REVIEW_PATH}")
    if args.out:
        Path(args.out).write_text(json.dumps(goldset, indent=1, sort_keys=True) + "\n")
        print(f"wrote {args.out}")

    spend.record_job_run(items=len(items) * len(models))
    return 0


if __name__ == "__main__":
    sys.exit(main())
