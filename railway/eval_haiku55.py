#!/usr/bin/env python3
"""Would anthropic/claude-haiku-5.5 do each paid job as well as today's model?

    python3 railway/eval_haiku55.py --dry-run   # build every prompt, spend nothing

Owner question, 2026-10-08. DISPATCH-ONLY (eval-haiku55.yml), posts nothing,
edits nothing, reads no WP key. Every call goes through spend.metered_call()
on the production client (max_retries=0), under a hard $1.00 run cap that this
script also enforces itself (EVAL_CAP_USD) so the brake does not depend on the
spend table's job resolution.

THREE CALL TYPES, each scored against an answer key no candidate wrote:

  causation   extractor.ai_causation_prompt() + finalize_ai_causation(), the
              exact production decision path (OPENROUTER_MODEL: extractor,
              ai_evidence_sweep, daily spot-check). Gold: the owner-adjudicated
              ai-causation-2026-08 gold set (labels by agreement or by human).
  extraction  the news-path extraction (SYSTEM_PROMPT, production guards) over
              frozen Wayback windows, gold = corroborated stated job count
              (reuses ab_extraction_models.judge, never restated).
  referee     adjudicate_row.PROMPT (ADJ_REFEREE_A/B: Sonnet 4.5, GPT-4o) and
              the same yes/no question the panel (ALT_PANEL_MODELS) votes on,
              over gold-set rows: `employer_attributed_to_ai` vs the gold label.

An errored call or unparseable answer is reported as such (json_ok), never
silently dropped. Results leave as ::notice:: annotation lines.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "docs" / "recall-reference-sets"
SAMPLE = REF / "ai-causation-2026-08.sample.json"
GOLD = REF / "ai-causation-2026-08.goldset.json"

CANDIDATE = "anthropic/claude-haiku-5.5"
CAUSATION_MODELS = ("google/gemini-2.5-flash-lite", CANDIDATE)
EXTRACTION_MODELS = ("google/gemini-2.5-flash-lite", CANDIDATE)
REFEREE_MODELS = ("anthropic/claude-sonnet-4.5", "openai/gpt-4o",
                  "anthropic/claude-haiku-4.5", "openai/gpt-4o-mini", CANDIDATE)
CAP_USD = float(os.environ.get("EVAL_CAP_USD", "1.00"))

_spent = {"usd": 0.0}


def notice(title, msg):
    print(f"::notice title={title}::{msg}", flush=True)


def load_items():
    items = json.loads(SAMPLE.read_text(encoding="utf-8"))["items"]
    labels = json.loads(GOLD.read_text(encoding="utf-8"))["labels"]
    out = []
    for it in items:
        lab = labels.get(str(it["id"]))
        if isinstance(lab, bool):
            out.append({**it, "gold": lab})
    return out


def stratified(items, n):
    """Round-robin across strata so a small n still holds positives."""
    by = {}
    for it in items:
        by.setdefault(it["stratum"], []).append(it)
    pick, keys = [], sorted(by)
    while len(pick) < n and any(by.values()):
        for k in keys:
            if by[k] and len(pick) < n:
                pick.append(by[k].pop(0))
    return pick


def _cost(resp):
    u = getattr(resp, "usage", None)
    if u is None:
        return 0.0, 0, 0
    get = (lambda k: getattr(u, k, None)) if not isinstance(u, dict) else u.get
    return float(get("cost") or 0), int(get("prompt_tokens") or 0), \
        int(get("completion_tokens") or 0)


def call(model, system, user, max_tokens):
    """(content | None, cost, error). Exactly one request per metered_call."""
    import extractor
    import spend
    if _spent["usd"] >= CAP_USD:
        return None, 0.0, "cap"
    try:
        resp = spend.metered_call(
            model,
            lambda: extractor._get_client().chat.completions.create(
                extra_body=extractor.USAGE_ACCOUNTING, model=model,
                max_tokens=max_tokens, temperature=0,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}]),
            what=f"haiku-5.5 eval on {model}", attempts=2, retry_sleep=1.0)
    except spend.PaidReadsOff:
        return None, 0.0, "budget_stop"
    except Exception as exc:  # noqa: BLE001 - an errored call is reported, not scored
        return None, 0.0, type(exc).__name__
    cost, _, _ = _cost(resp)
    _spent["usd"] += cost
    content = resp.choices[0].message.content if resp.choices else ""
    return content or "", cost, None


def tally():
    return {"n": 0, "json_ok": 0, "errors": 0, "tp": 0, "fp": 0, "tn": 0,
            "fn": 0, "cost": 0.0, "calls": 0}


def add(t, pred, gold, cost, ok, err):
    t["n"] += 1
    t["calls"] += 0 if err in ("cap", "budget_stop") else 1
    t["cost"] += cost
    if err:
        t["errors"] += 1
        return
    if not ok:
        return
    t["json_ok"] += 1
    key = ("t" if pred == gold else "f") + ("p" if pred else "n")
    t[key] += 1


def summary(t):
    judged = t["tp"] + t["fp"] + t["tn"] + t["fn"]
    acc = (t["tp"] + t["tn"]) / judged if judged else 0
    prec = t["tp"] / (t["tp"] + t["fp"]) if t["tp"] + t["fp"] else 0
    rec = t["tp"] / (t["tp"] + t["fn"]) if t["tp"] + t["fn"] else 0
    per_k = 1000 * t["cost"] / t["calls"] if t["calls"] else 0
    return (f"acc={acc:.1%} ({t['tp'] + t['tn']}/{judged}) precision={prec:.1%} "
            f"recall={rec:.1%} json_ok={t['json_ok']}/{t['n']} errors={t['errors']} "
            f"spend=${t['cost']:.4f} cost_per_1k_calls=${per_k:.3f}")


def run_causation(items, dry):
    import extractor
    res = {m: tally() for m in CAUSATION_MODELS}
    for it in items:
        prompt = extractor.ai_causation_prompt(it["text"])
        if dry:
            continue
        for m in CAUSATION_MODELS:
            content, cost, err = call(m, extractor.MINI_SYSTEM, prompt, 250)
            fin = None
            if content is not None:
                try:
                    fin = extractor.finalize_ai_causation(
                        extractor._parse_json_response(content), it["text"])
                except Exception:  # noqa: BLE001 - unparseable = json not ok
                    fin = None
            pred = bool(fin) and extractor.ai_explicit_from_causation(fin["ai_causation"])
            add(res[m], pred, it["gold"], cost, fin is not None, err)
            time.sleep(0.1)
    for m, t in res.items():
        notice(f"causation {m}", summary(t))


def run_referee(items, dry):
    import adjudicate_row
    import extractor
    res = {m: tally() for m in REFEREE_MODELS}
    for it in items:
        row = {"id": it["id"], "company_name": it["company_name"],
               "job_count": it.get("job_count"), "layoff_date": it.get("layoff_date"),
               "source_type": it.get("source_type"), "source_name": it.get("source_name"),
               **(it.get("stored") or {})}
        prompt = adjudicate_row.PROMPT.format(
            rules=adjudicate_row.RULES, row=json.dumps(adjudicate_row.row_view(row)),
            evidence=it["text"])
        if dry:
            continue
        for m in REFEREE_MODELS:
            content, cost, err = call(m, extractor.MINI_SYSTEM, prompt, 500)
            parsed = None
            if content is not None:
                try:
                    parsed = extractor._parse_json_response(content)
                except Exception:  # noqa: BLE001
                    parsed = None
            ok = isinstance(parsed, dict) and "recommended_action" in parsed \
                and isinstance(parsed.get("employer_attributed_to_ai"), bool)
            pred = bool(ok and parsed["employer_attributed_to_ai"])
            add(res[m], pred, it["gold"], cost, ok, err)
            time.sleep(0.1)
    for m, t in res.items():
        notice(f"referee {m}", summary(t))


def run_extraction(limit, dry):
    import ab_extraction_models as ab
    out = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "eval-haiku55-extraction.json"
    if _spent["usd"] >= CAP_USD:
        notice("extraction", "skipped: run cap reached")
        return
    rc = ab.run_news(EXTRACTION_MODELS, limit, dry, str(out))
    if dry or rc != 0 or not out.exists():
        notice("extraction", f"no comparison (rc={rc}, dry={dry})")
        return
    scored = json.loads(out.read_text())["scored"]
    for m in EXTRACTION_MODELS:
        s = scored[m]
        _spent["usd"] += s["cost"]
        per_k = 1000 * s["cost"] / s["calls"] if s["calls"] else 0
        notice(f"extraction {m}",
               f"correct_count={s['correct']}/{s['scorable']} wrong_count={s['wrong_count']} "
               f"accepted={s['accepted']} unknown={s['unknown']} spend=${s['cost']:.4f} "
               f"cost_per_1k_calls=${per_k:.3f} stages={json.dumps(s['stages'])}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--causation", type=int, default=int(os.environ.get("EVAL_CAUSATION_N", 193)))
    ap.add_argument("--referee", type=int, default=int(os.environ.get("EVAL_REFEREE_N", 40)))
    ap.add_argument("--extraction", type=int, default=int(os.environ.get("EVAL_EXTRACTION_N", 20)))
    args = ap.parse_args(argv)
    dry = args.dry_run or bool(os.environ.get("EVAL_DRY_RUN"))
    items = load_items()
    notice("eval-haiku55", f"gold items={len(items)} causation={args.causation} "
           f"referee={args.referee} extraction={args.extraction} cap=${CAP_USD:.2f} dry={dry}")
    run_causation(stratified(items, args.causation), dry)
    run_referee(stratified(items, args.referee), dry)
    if args.extraction:
        run_extraction(args.extraction, dry)
    notice("eval-haiku55 total", f"metered spend this run ${_spent['usd']:.4f} (cap ${CAP_USD:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
