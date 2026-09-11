#!/usr/bin/env python3
"""Adjudicate one doubtful published row with two independent AI referees.

THE RULE THIS IMPLEMENTS (owner, 2026-09-11). A correction that used to wait
for the owner's sign-off is instead put to two referees from different
vendors, each reading the row and its own cited source under the tracker's
published rules. It is applied only when both return the same action. A
disagreement is written down and left for a human; nothing is changed. An
unreadable source is UNKNOWN, and UNKNOWN never applies anything, because
absence of evidence is not evidence.

WHY TWO VENDORS. One model grading a row is one opinion with a confident
voice. Two models that share no weights and agree is the evidence bar the
owner accepts for a numeric change, and it is cheap: two short calls, a few
cents, metered like every other paid read in this repository.

WHAT IT NEVER DOES. It never edits live data by hand: the write goes through
apply_correction.py and the same /trash and /edit routes every correction has
used, so the dedup hash is suppressed and the public corrections log gets its
line. It never prints a key, and it never retries inside the metered callable
(CLAUDE.md iron rule; retries are metered_call(attempts=2)).

USAGE
    WP_SITE_URL=... WP_API_KEY=... OPENROUTER_API_KEY=... \\
    python3 railway/adjudicate_row.py --id 179276 --company Amazon          # dry run
    python3 railway/adjudicate_row.py --id 179276 --company Amazon --apply  # apply on agreement

Exit codes: 0 applied or dry-run agreement; 3 UNKNOWN (disagreement or
unreadable evidence, spec written for a human); 1 a hard failure.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import apply_correction  # noqa: E402
import extractor  # noqa: E402
import spend  # noqa: E402

REFEREES = [
    os.environ.get("ADJ_REFEREE_A", "anthropic/claude-sonnet-4.5"),
    os.environ.get("ADJ_REFEREE_B", "openai/gpt-4o"),
]
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
EVIDENCE_CAP = 12000
SPEC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "correction_specs")

RULES = """The tracker's published rules, which you must apply:
1. layoff_date is the date the cuts take effect (or, for a news row, the date the
   report says they take effect). A report published on a later date about an
   announcement made earlier is a RE-REPORT, not a new event on the publish date.
2. ai_explicit is true only when THE EMPLOYER attributed the cuts to AI: the
   report quotes or reports the employer saying so. A journalist's own framing
   ("as AI spending rises") is not employer attribution.
3. The stored job_count must be a figure the cited source states for THIS event.
   A count the source does not state, or that belongs to a different, earlier
   announcement, is unsupported.
4. A row is real and correctly dated only if the source describes NEW cuts taking
   effect on or about layoff_date. If the source is a summary, an explainer, or a
   retrospective about an announcement already public before layoff_date, the row
   is a duplicate or misdated entry and the honest action is "trash" (the tracker
   holds the original event elsewhere or will re-ingest it from a primary report).
5. If the row is real but one field is wrong (date, count, country, ai_explicit),
   the action is "edit" with exactly the corrected fields.
"""

PROMPT = """You are one of two independent referees adjudicating a published row in a
public layoff tracker. The other referee is a model from a different vendor;
you will not see its answer. Be strict and literal. Decide only from the row
and the source text below. If the source text is empty or unrelated, say so and
recommend "keep" with confidence 0.

{rules}

THE ROW (as published):
{row}

THE CITED SOURCE (archived copy, text only, may be truncated):
<<<
{evidence}
>>>

Answer with ONE JSON object and nothing else:
{{"event_is_new_on_layoff_date": true|false,
  "count_supported_by_source": true|false,
  "employer_attributed_to_ai": true|false,
  "recommended_action": "keep"|"trash"|"edit",
  "edit_fields": null or {{"field": value, ...}},
  "confidence": 0-100,
  "reasoning": "at most 600 characters, cite the sentence in the source that decides it"}}
"""


def fetch_evidence(url: str, timeout: int = 15) -> str:
    """Text of the cited page (archived copy preferred), or '' when unreadable."""
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(400_000).decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - any failure is "unreadable", reported not raised
        print(f"  evidence: could not read {url[:80]} ({type(exc).__name__})")
        return ""
    raw = re.sub(r"(?is)<(script|style|nav|header|footer).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text[:EVIDENCE_CAP]


def row_view(row: dict) -> dict:
    keep = ("id", "company_name", "job_count", "job_count_max", "layoff_date",
            "announcement_date", "country", "state", "industry", "source_type",
            "source_name", "source_url", "verification_level", "review_status",
            "ai_explicit", "ai_causation", "ai_language", "confidence", "excerpt",
            "announced", "reason_tags")
    return {k: row.get(k) for k in keep if k in row}


def ask_referee(model: str, prompt: str) -> dict | None:
    """One verdict from one model, metered. None when the answer is not JSON."""
    response = spend.metered_call(
        model,
        lambda: extractor._get_client().chat.completions.create(
            extra_body=extractor.USAGE_ACCOUNTING,
            model=model, max_tokens=500, temperature=0,
            messages=[{"role": "system", "content": extractor.MINI_SYSTEM},
                      {"role": "user", "content": prompt}],
        ),
        what=f"row adjudication by {model}", attempts=2, retry_sleep=1.0,
    )
    content = response.choices[0].message.content if response.choices else ""
    parsed = extractor._parse_json_response(content or "")
    if not isinstance(parsed, dict) or "recommended_action" not in parsed:
        return None
    return parsed


def decide(verdicts: dict[str, dict | None]) -> tuple[str, str, dict | None]:
    """(status, action, edit_fields). status is 'agree', 'disagree' or 'unknown'."""
    answered = {m: v for m, v in verdicts.items() if v}
    if len(answered) < 2:
        return "unknown", "keep", None
    actions = {v.get("recommended_action") for v in answered.values()}
    if len(actions) != 1:
        return "disagree", "keep", None
    action = actions.pop()
    if action == "edit":
        fields = [json.dumps(v.get("edit_fields") or {}, sort_keys=True) for v in answered.values()]
        if len(set(fields)) != 1:
            return "disagree", "keep", None
        return "agree", "edit", json.loads(fields[0])
    return "agree", action, None


def write_spec(row_id: int, status: str, verdicts: dict, extra: dict) -> str:
    os.makedirs(SPEC_DIR, exist_ok=True)
    stamp = _dt.date.today().isoformat()
    path = os.path.join(SPEC_DIR, f"{stamp}-adjudication-{row_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"row_id": row_id, "status": status, "verdicts": verdicts,
                   "referees": REFEREES, **extra}, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return path


def apply_via_machinery(row: dict, action: str, fields: dict | None,
                        reason: str, apply: bool) -> int:
    argv = ["apply_correction.py", "--ids", str(row["id"]), "--action", action,
            "--reason", reason, "--verify-company", str(row.get("company_name") or "")]
    if action == "edit":
        argv += ["--fields", json.dumps(fields or {})]
    if apply:
        argv.append("--apply")
    saved = sys.argv
    try:
        sys.argv = argv
        return int(apply_correction.main() or 0)
    finally:
        sys.argv = saved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", type=int, required=True)
    ap.add_argument("--company", required=True, help="company filter used to fetch the row")
    ap.add_argument("--apply", action="store_true", help="write on agreement (otherwise dry run)")
    a = ap.parse_args()
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL required")
        return 1
    rows = apply_correction._rows_for(site, a.company)
    row = rows.get(a.id)
    if not row:
        print(f"row {a.id} not found under company {a.company!r}")
        return 1
    view = row_view(row)
    print(f"ROW {a.id}: {view.get('company_name')} {view.get('job_count')} jobs "
          f"{view.get('layoff_date')} {view.get('verification_level')}/{view.get('review_status')}")
    evidence = fetch_evidence(row.get("archived_url") or "") or fetch_evidence(row.get("source_url") or "")
    if not evidence:
        path = write_spec(a.id, "unknown", {}, {"why": "no evidence page could be read"})
        print(f"UNKNOWN: no evidence could be read. Nothing applied. Spec: {path}")
        return 3
    print(f"  evidence: {len(evidence)} characters read")
    prompt = PROMPT.format(rules=RULES, row=json.dumps(view, indent=1, ensure_ascii=False),
                           evidence=evidence)
    verdicts: dict[str, dict | None] = {}
    for model in REFEREES:
        try:
            verdicts[model] = ask_referee(model, prompt)
        except spend.PaidReadsOff as exc:
            print(f"  {model}: budget stop ({exc}); UNDECIDED")
            verdicts[model] = None
        v = verdicts[model]
        print(f"  {model}: " + (json.dumps(v, ensure_ascii=False)[:400] if v else "no usable verdict"))
    status, action, fields = decide(verdicts)
    cost = round(spend.run_cost_usd(), 4)
    extra = {"cost_usd": cost, "archived_url": row.get("archived_url"), "action": action,
             "edit_fields": fields}
    if status != "agree":
        path = write_spec(a.id, status, verdicts, extra)
        print(f"{status.upper()}: the referees did not agree. Nothing applied. "
              f"A human decides. Spec: {path}  (spend ${cost})")
        return 3
    if action == "keep":
        write_spec(a.id, "agree-keep", verdicts, extra)
        print(f"AGREE: keep. Nothing to change. (spend ${cost})")
        return 0
    reasons = "; ".join((v.get("reasoning") or "")[:140] for v in verdicts.values() if v)
    reason = f"two-model adjudication ({' + '.join(REFEREES)} agree: {action}): {reasons}"
    rc = apply_via_machinery(row, action, fields, reason, a.apply)
    write_spec(a.id, "applied" if (a.apply and rc == 0) else "agree-dry-run", verdicts,
               {**extra, "reason": reason, "apply_rc": rc})
    print(f"AGREE: {action}. {'APPLIED' if a.apply else 'dry run'} rc={rc} (spend ${cost})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
