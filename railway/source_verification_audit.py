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
import ops_notify
from source_health import report_source_health
import spend

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# THE AUDIT MODEL. This is a company/jobs/date fact check against a fetched
# source -- the same kind of correctness question extraction answers -- so it
# tracks extractor.MODEL rather than carrying its own opinion. Until
# 2026-09-03 this was a bare "deepseek/deepseek-chat" literal: a fifth
# undocumented DeepSeek call site, on a model the owner had ruled out months
# earlier on EU compliance grounds. Falls back to the same default extractor.py
# uses if extractor is not importable, so this file degrades the same way the
# OpenAI import above does rather than reintroducing a private default.
try:
    import extractor
    AUDIT_MODEL = extractor.MODEL
except Exception:                   # pragma: no cover - import guard, mirrors OpenAI above
    AUDIT_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

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
    """Return PASS / MISMATCH / UNVERIFIABLE / DEFERRED for a row.

    DEFERRED is not a verdict about the row: the per-run ceiling stopped us
    before we asked, so nobody has read it. main() checks the brake once before
    the sample is drawn, and that check cannot bound a loop that makes one paid
    call per row — 40 of them by default, with the ceiling read exactly once.
    The brake is inside spend.metered_call, at the call.
    """
    if text is None:
        return "UNVERIFIABLE", "source could not be fetched (dead link or bot wall)"
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key and text):
        return "UNVERIFIABLE", "no model / empty source"
    company = row.get("company_name"); jobs = row.get("job_count"); date = row.get("layoff_date")
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key,
                        # ZERO: the SDK retries by default (2), which
                        # re-POSTs inside the callable handed to
                        # metered_call — a charge with no gate read and
                        # no meter entry. Retry via metered_call's own
                        # `attempts=`, which re-reads the brake and
                        # meters each try.
                        max_retries=0)
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
        resp = spend.metered_call(AUDIT_MODEL, lambda: client.chat.completions.create(
            model=AUDIT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=80,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        ), what=f"the source audit of row {row.get('id')}")
        ans = resp.choices[0].message.content.strip()
        head = ans.split()[0].upper() if ans else "UNCLEAR"
        if head.startswith("PASS"):
            return "PASS", ans[:140]
        if head.startswith("MISMATCH"):
            return "MISMATCH", ans[:140]
        return "UNVERIFIABLE", ans[:140]
    except spend.PaidReadsOff as exc:
        # NOT "UNVERIFIABLE". That word means we looked at the source and could
        # not tell; this row was never read. Folding a budget stop into a
        # verdict bucket would publish an accuracy percentage whose denominator
        # includes rows nobody audited.
        return "DEFERRED", str(exc)[:140]
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
        # Skip rows a human already reconciled/pinned (edited=1): a deliberate
        # net-new figure (e.g. Dow 3,700 of a 4,500 plan) correctly looks like a
        # "mismatch" to a naive re-read of the headline, so auditing it re-flags
        # a known-good decision every month. Audit only un-reviewed rows.
        rows = [x for x in rows
                if str(x.get("source_url") or "").startswith("http") and not x.get("edited")]
        rng.shuffle(rows)
        picked.extend(rows[:per])
    rng.shuffle(picked)
    return picked[:SAMPLE]


def _src_param(st):
    # Filter by source_type (not verification tier): ERM rows are silver and
    # SEC rows are gold, but two tiers collapse — mapping erm->"bronze" sampled
    # NEWS rows (bronze) and never touched ERM, while news+erm drew the same
    # pool. source_type values are 1:1 with the strata, so each stratum samples
    # its own rows. (`sources` matches source_type OR tier, so these are valid.)
    return {"warn": "warn", "sec_8k": "8K", "erm": "erm", "news": "news"}.get(st, "")


def _email(subject, body):
    """Through the one operational sender. See ops_notify for why the site's
    `/alert` route stopped being an acceptable way to reach the owner: it
    posted the audit under the reader newsletter's From line."""
    ops_notify.notify(subject, body, what="source-verification audit")


def main():
    # Spend guard: this script builds its own OpenRouter client, so
    # extractor.py's gate does not cover it. Skip cleanly (exit 0) rather than
    # failing — a deferred source-verification audit is re-run on its next
    # schedule, and reddening CI over a budget decision is noise.
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling) — skipping the source-verification audit "
              "this run; it resumes on the next schedule")
        return 0
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
    tally = {"PASS": 0, "MISMATCH": 0, "UNVERIFIABLE": 0, "DEFERRED": 0}
    mismatches = []
    truncated = None
    for row in rows:
        text = _fetch_text(row.get("source_url"))
        verdict, reason = _verify(row, text)
        tally[verdict] += 1
        if verdict == "DEFERRED":
            # The ceiling tripped. Every remaining row would defer too, so stop
            # fetching sources for questions we are not going to ask.
            tally["DEFERRED"] = len(rows) - (tally["PASS"] + tally["MISMATCH"]
                                             + tally["UNVERIFIABLE"])
            truncated = (f"spend ceiling reached with {tally['DEFERRED']} of "
                         f"{len(rows)} sampled row(s) unread")
            print(f"  deferred spend ceiling reached — {tally['DEFERRED']} row(s) "
                  f"unread; the next monthly run re-samples")
            break
        mark = {"PASS": "  ok  ", "MISMATCH": "MISMATCH", "UNVERIFIABLE": "unverif "}[verdict]
        print(f"  {mark} id={row.get('id')} {str(row.get('company_name'))[:26]:<28} "
              f"{row.get('job_count')} {row.get('layoff_date')}  {reason[:60]}")
        if verdict == "MISMATCH":
            mismatches.append(row)
    verifiable = tally["PASS"] + tally["MISMATCH"]
    acc = (100.0 * tally["PASS"] / verifiable) if verifiable else 0.0
    summary = (f"{tally['PASS']}/{verifiable} verifiable rows matched their source "
               f"= {acc:.1f}% ({tally['UNVERIFIABLE']} unverifiable: dead link / bot wall)")
    if tally["DEFERRED"]:
        # Said in the same sentence as the percentage, because the percentage is
        # over a SMALLER sample than the one this run drew and a reader who does
        # not know that will read it as the month's full audit.
        summary += (f"; {tally['DEFERRED']} of {len(rows)} sampled row(s) were "
                    f"NOT read (spend ceiling), so this is a partial audit")
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
    # `items` is rows actually READ, not rows sampled: a deferred row cost
    # nothing and reporting it would divide this run's spend over work nobody
    # paid for.
    spend.record_job_run(items=len(rows) - tally["DEFERRED"],
                         changed=len(mismatches), truncated=truncated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
