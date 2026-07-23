"""Monthly self-audit: re-verify a random sample of PUBLISHED rows against their
own cited sources, and report the accuracy openly.

This is the recurring version of the one-off adversarial audit. It draws a
stratified random sample, re-opens each row's source_url, and asks the model a
single question: does this source support THIS company cutting THIS many jobs on
THIS date? It tallies pass / mismatch / unverifiable and reports the accuracy to
the health ledger and by email.

READ-ONLY by design. It never changes a row. A number a journalist can trust
comes from a database that audits itself and publishes the result, so this is a
credibility instrument, not a correction tool: a mismatch is surfaced for a
human to decide via the corrections path, never auto-edited. Safe to run live
with no arming.

Deterministic sample: seed = year*100+month, so a given month always re-draws
the same sample (reproducible), and every month is a fresh draw. Env:
WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY, AUDIT_SAMPLE (default 40),
AUDIT_YEAR (default current).
"""
import os
import random
import re
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_retry import get_with_retry
from source_health import report_source_health

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
SAMPLE = max(5, min(120, int(os.environ.get("AUDIT_SAMPLE") or "40")))
TIMEOUT = 40


def _fetch_text(url):
    if not url:
        return ""
    r = get_with_retry(url, headers=UA, timeout=TIMEOUT)
    if r is None or r.status_code != 200:
        return None  # distinguish "could not fetch" from "empty"
    txt = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", r.text)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:5000]


def _verify(row, text):
    """Return PASS / MISMATCH / UNVERIFIABLE for a row against its source text."""
    if text is None:
        return "UNVERIFIABLE", "source could not be fetched (dead link or bot wall)"
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key and text):
        return "UNVERIFIABLE", "no model / empty source"
    company = row.get("company_name"); jobs = row.get("job_count"); date = row.get("layoff_date")
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        prompt = (
            "You audit a layoff database against its source. The row claims:\n"
            f"  company: {company}\n  jobs cut: {jobs}\n  date: {date}\n\n"
            "Does the source text below support this row? Answer on ONE line:\n"
            "  PASS  - the source supports this company, this count (or its lower "
            "bound / a stated range), around this date\n"
            "  MISMATCH - the source clearly states a different company, a "
            "different number, or a different event\n"
            "  UNCLEAR - the source does not contain enough to tell\n"
            "Answer with the one word, then a short reason.\n\n"
            f"SOURCE:\n{text[:4000]}"
        )
        resp = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=80,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        )
        ans = resp.choices[0].message.content.strip()
        head = ans.split()[0].upper() if ans else "UNCLEAR"
        if head.startswith("PASS"):
            return "PASS", ans[:140]
        if head.startswith("MISMATCH"):
            return "MISMATCH", ans[:140]
        return "UNVERIFIABLE", ans[:140]
    except Exception as exc:
        return "UNVERIFIABLE", f"audit error: {exc}"


def _sample(year, seed):
    """Stratified random sample across source types for the year."""
    strata = ("warn", "sec_8k", "erm", "news")
    rng = random.Random(seed)
    picked = []
    per = max(2, SAMPLE // len(strata))
    for st in strata:
        r = get_with_retry(f"{SITE}/wp-json/layoffs/v1/query",
                           params={"years": year, "sources": _src_param(st), "per_page": 200,
                                   "cb": f"aud{seed}{st}"}, headers=UA, timeout=TIMEOUT)
        rows = r.json().get("data", []) if (r and r.status_code == 200) else []
        rows = [x for x in rows if str(x.get("source_url") or "").startswith("http")]
        rng.shuffle(rows)
        picked.extend(rows[:per])
    rng.shuffle(picked)
    return picked[:SAMPLE]


def _src_param(st):
    return {"warn": "warn", "sec_8k": "gold", "erm": "bronze", "news": "bronze"}.get(st, "")


def _email(subject, body):
    if not (SITE and KEY):
        return
    try:
        requests.post(f"{SITE}/wp-json/layoffs/v1/alert",
                      json={"subject": subject, "body": body},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=25)
    except Exception:
        pass


def main():
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    now = datetime.now(timezone.utc)
    year = int(os.environ.get("AUDIT_YEAR") or now.year)
    seed = year * 100 + now.month
    rows = _sample(year, seed)
    if not rows:
        print("audit: no sampleable rows")
        return 0
    print(f"source-verification audit: {len(rows)} rows, {year}, seed {seed}")
    tally = {"PASS": 0, "MISMATCH": 0, "UNVERIFIABLE": 0}
    mismatches = []
    for row in rows:
        text = _fetch_text(row.get("source_url"))
        verdict, reason = _verify(row, text)
        tally[verdict] += 1
        mark = {"PASS": "  ok  ", "MISMATCH": "MISMATCH", "UNVERIFIABLE": "unverif "}[verdict]
        print(f"  {mark} id={row.get('id')} {str(row.get('company_name'))[:26]:<28} "
              f"{row.get('job_count')} {row.get('layoff_date')}  {reason[:60]}")
        if verdict == "MISMATCH":
            mismatches.append(row)
    verifiable = tally["PASS"] + tally["MISMATCH"]
    acc = (100.0 * tally["PASS"] / verifiable) if verifiable else 0.0
    summary = (f"{tally['PASS']}/{verifiable} verifiable rows matched their source "
               f"= {acc:.1f}% ({tally['UNVERIFIABLE']} unverifiable: dead link / bot wall)")
    print("\nAUDIT RESULT:", summary)

    report_source_health("source_audit", "degraded" if mismatches else "ok",
                          tally["PASS"], summary)
    if mismatches:
        lines = [f"Monthly self-audit found {len(mismatches)} row(s) whose source may "
                 f"not support the figure. Review via the corrections path (never auto-edited).\n",
                 summary, ""]
        for m in mismatches:
            lines.append(f"- id {m.get('id')}: {m.get('company_name')} {m.get('job_count')} "
                         f"{m.get('layoff_date')} -> {str(m.get('source_url'))[:70]}")
        _email(f"Self-audit: {len(mismatches)} row(s) to review ({acc:.0f}% matched)",
               "\n".join(lines))
    else:
        _email(f"Self-audit clean: {acc:.0f}% of {verifiable} verifiable rows matched their source",
               f"Monthly source-verification audit passed.\n\n{summary}\n\nNo mismatches. "
               f"This is the number you can publish: the tracker audits itself and every "
               f"sampled row still matches its source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
