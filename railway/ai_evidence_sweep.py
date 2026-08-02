"""Actively hunt an AI quote for BIG layoffs we have NOT tagged as AI.

The existing reclassify worker only RE-checks rows already tagged AI (to keep
them honest). Nothing looked the other way: a large cut that we stored from a
source framing it as, say, 'market pressure' stays AI-untagged forever, even
if the employer ALSO said 'as we shift to AI' somewhere we did not capture.
British American Tobacco is the worked example - our stored source blamed
'illegal Chinese products', while other coverage framed the same 9,000 cuts as
an AI transformation.

This sweep closes that gap WITHOUT loosening the standard. For each big untagged
event it re-reads the stored source and runs a targeted press search, then asks
the model for an EXACT employer AI quote. Only if a verbatim quote is found (and
a second pass agrees) does it upgrade the row via /reclassify, which itself
rejects any AI tag whose quote is under 12 chars. No quote -> the row correctly
stays untagged. So Canada Post and UPS (real non-AI cuts) never get mislabelled;
only events where the employer genuinely named AI get the tag, with the receipt.

Why not hourly: this is not a freshness problem, it is an evidence-completeness
problem. Cuts are collected twice daily; this runs ONCE daily over the biggest
untagged events, where a missed AI attribution moves the headline most. Hourly
would burn model budget re-reading the same rows with nothing new to find.

Ships DRY-RUN by default: reports what it WOULD upgrade and writes nothing until
AI_SWEEP_LIVE=1. Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY,
AI_SWEEP_MIN_JOBS (default 2000), AI_SWEEP_MAX (default 20), AI_SWEEP_LIVE=1.
"""
import os
import re
import sys
import time
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from http_retry import get_with_retry
import spend

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from sources.newsapi import pull_news_articles
except Exception:
    pull_news_articles = None

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
LIVE = os.environ.get("AI_SWEEP_LIVE", "").lower() in {"1", "true", "yes"}
MIN_JOBS = max(500, int(os.environ.get("AI_SWEEP_MIN_JOBS") or "2000"))
MAX_EVENTS = max(1, int(os.environ.get("AI_SWEEP_MAX") or "20"))
TIMEOUT = 40

def _fetch_text(url):
    if not url:
        return ""
    r = get_with_retry(url, headers=UA, timeout=TIMEOUT)
    if r is None or r.status_code != 200:
        return ""
    txt = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", r.text)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:6000]


def _ai_quote(company, text):
    """Return an EXACT employer AI-attribution quote from the text, or ''.

    Constrained hard: the quote must be a verbatim substring of the source, or
    we discard it (the model does not get to paraphrase AI evidence into
    existence). Fails closed on any error.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key and text):
        return ""
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        prompt = (
            f"Text about {company}'s layoffs is below. If the EMPLOYER names AI "
            "or automation as a reason for the cuts, copy the exact sentence that "
            "says so, verbatim, and nothing else. If the employer does not name "
            "AI/automation as a cause (market pressure, demand, costs, merger, "
            "etc. do NOT count), answer exactly NONE.\n\n"
            f"TEXT:\n{text[:4500]}"
        )
        resp = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=120,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        )
        spend.record_usage("deepseek/deepseek-chat", getattr(resp, "usage", None))
        quote = resp.choices[0].message.content.strip().strip('"').strip()
        if not quote or quote.upper().startswith("NONE") or len(quote) < 12:
            return ""
        # Must appear (loosely) in the source text; otherwise the model invented it.
        norm = lambda s: re.sub(r"\s+", " ", s.lower())
        if norm(quote)[:60] not in norm(text):
            return ""
        return quote[:300]
    except Exception:
        return ""


def _second_pass_agrees(company, quote):
    """A cheap independent check that the quote really is an EMPLOYER AI cause."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key):
        return False
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        resp = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": (
                "Answer only yes or no. Does this sentence show the EMPLOYER "
                f"naming AI or automation as a reason for {company}'s job cuts "
                f"(not a journalist's framing, not investment, not a future "
                f"projection)?\n\n\"{quote}\"")}],
            temperature=0, max_tokens=4,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        )
        spend.record_usage("deepseek/deepseek-chat", getattr(resp, "usage", None))
        return resp.choices[0].message.content.strip().lower().startswith("y")
    except Exception:
        return False


def _big_untagged():
    r = get_with_retry(f"{SITE}/wp-json/layoffs/v1/query",
                       params={"years": "2026", "min_jobs": MIN_JOBS,
                               "sort": "job_count", "dir": "desc", "per_page": 100},
                       headers=UA, timeout=TIMEOUT)
    if r is None or r.status_code != 200:
        return []
    rows = r.json().get("data", [])
    return [x for x in rows if not x.get("ai_explicit")][:MAX_EVENTS]


def _upgrade(row_id, quote):
    if not LIVE:
        return "would-upgrade"
    r = requests.post(f"{SITE}/wp-json/layoffs/v1/reclassify",
                      json={"items": [{"id": row_id, "ai_causation": "contributing_cause",
                                       "ai_language": quote, "confidence": 70}]},
                      headers={"X-Layoff-API-Key": KEY, **UA}, timeout=TIMEOUT)
    if r.status_code != 200:
        return f"failed({r.status_code})"
    out = r.json()
    if row_id in (out.get("updated") or []):
        return "upgraded"
    return "rejected" if row_id in (out.get("rejected") or []) else "no-op"


def main():
    # Spend guard: this script builds its own OpenRouter client, so
    # extractor.py's gate does not cover it. Skip cleanly (exit 0) rather than
    # failing — a deferred AI-evidence sweep is re-run on its next
    # schedule, and reddening CI over a budget decision is noise.
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling) — skipping the AI-evidence sweep "
              "this run; it resumes on the next schedule")
        return 0
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    print(f"AI evidence sweep: {'LIVE' if LIVE else 'DRY RUN'} | "
          f">= {MIN_JOBS} jobs, up to {MAX_EVENTS} events")
    events = _big_untagged()
    print(f"{len(events)} big untagged 2026 event(s) to check")
    upgraded = checked = 0
    for row in events:
        if not spend.paid_reads_enabled():
            # Per-run ceiling tripped mid-sweep: keep what was decided,
            # defer the rest to the next schedule.
            print("  per-run spend ceiling reached — deferring the remaining "
                  "events to the next run")
            break
        checked += 1
        rid = row.get("id")
        company = str(row.get("company_name") or "").strip()
        # Re-read the stored source, then a targeted AI-focused press search.
        texts = [_fetch_text(row.get("source_url"))]
        if pull_news_articles:
            try:
                for a in pull_news_articles(days_back=200, queries=[
                        f'"{company}" (AI OR automation) (layoffs OR "job cuts")']):
                    texts.append(str(a.get("raw_text") or a.get("description") or ""))
            except Exception:
                pass
        quote = ""
        for txt in texts:
            quote = _ai_quote(company, txt)
            if quote and _second_pass_agrees(company, quote):
                break
            quote = ""
        if not quote:
            print(f"  keep-untagged  {company} ({row.get('job_count')}): no employer AI quote found")
            continue
        status = _upgrade(rid, quote)
        upgraded += 1 if status in ("would-upgrade", "upgraded") else 0
        print(f"  {status:14} {company} ({row.get('job_count')}): \"{quote[:90]}\"")
        time.sleep(0.5)
    print(f"done: {checked} checked, {upgraded} "
          f"{'would upgrade' if not LIVE else 'upgraded'} with an employer AI quote")
    spend.record_job_run(items=checked, changed=upgraded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
