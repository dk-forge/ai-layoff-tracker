"""Earnings-call transcript ingest — the highest-yield missing source class.

Many big cuts (and the AI framing) surface in the Q&A of an earnings call, not in
a discrete 8-K or a clean news story — so this closes a real gap. Cost is
controlled by a two-stage sieve: only watchlist companies that reported recently
are pulled, and only transcripts whose text contains layoff/restructuring/AI
language are sent (chunked) to the extractor.

Ships DORMANT: with no EARNINGS_API_KEY set it exits clean. Built against the
Financial Modeling Prep transcript API shape (earning_call_transcript); swap the
base URL/parsing if you use a different vendor. Owner adds the secret to activate.

Env: EARNINGS_API_KEY (activates it), EARNINGS_API_BASE (default FMP),
EARNINGS_BATCH (tickers/run, default 40), EARNINGS_DRY=1.
"""
import csv
import os
import re
import sys
import time
from datetime import date

import requests

from extractor import extract_layoff_data
from wp_poster import post_to_wordpress
from source_health import report_source_health

API_KEY = os.environ.get("FMP_API_KEY") or os.environ.get("EARNINGS_API_KEY", "")
API_BASE = os.environ.get("EARNINGS_API_BASE", "https://financialmodelingprep.com/api/v3")
BATCH = max(1, int(os.environ.get("EARNINGS_BATCH", "40")))
DRY = os.environ.get("EARNINGS_DRY", "").lower() in {"1", "true", "yes"}
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TICKERS_PATH = os.path.join(os.path.dirname(__file__), "seed_data", "earnings_tickers.csv")

# Two-stage sieve keywords: only transcripts mentioning these reach the LLM.
SIEVE = re.compile(
    r"\b(layoff|laid off|job cuts?|headcount|reduc(e|tion|ing)|restructur|"
    r"attrition|right ?siz|role eliminat|workforce|severance|redundanc|"
    r"efficienc(y|ies)|streamlin)\w*", re.I)
AI_HINT = re.compile(r"\b(AI|artificial intelligence|automation|automate|agentic)\b", re.I)


def load_tickers():
    out = []
    try:
        with open(TICKERS_PATH, newline="") as f:
            for row in csv.DictReader(f):
                t = (row.get("ticker") or "").strip().upper()
                if t and not t.startswith("#"):
                    out.append(t)
    except FileNotFoundError:
        pass
    return out


_DIAG_DONE = False


def latest_transcript(ticker):
    """Most recent transcript for a ticker (FMP shape). Returns text or ''.

    FMP retired the v3 /earning_call_transcript path (legacy, pre-Aug-2025
    accounts only). The current path is the `stable` API: earning-call-transcript
    ?symbol=. Transcripts remain a premium feature, so a free key may still 403 —
    the diagnostic below surfaces exactly that instead of a silent 0.
    """
    global _DIAG_DONE
    try:
        r = requests.get("https://financialmodelingprep.com/stable/earning-call-transcript",
                         params={"symbol": ticker, "apikey": API_KEY}, headers=UA, timeout=40)
        # Log the first response verbatim so a paywalled/empty free tier is
        # visible in the run log instead of looking like "no layoffs found".
        if not _DIAG_DONE:
            _DIAG_DONE = True
            print(f"FMP diag [{ticker}]: HTTP {r.status_code}, body starts: {r.text[:220]}")
        if r.status_code != 200:
            return ""
        data = r.json()
        if isinstance(data, list) and data:
            return str(data[0].get("content") or "")
    except Exception as exc:
        print(f"{ticker}: transcript fetch failed ({exc})")
    return ""


def relevant_chunks(text):
    """Paragraphs mentioning layoff/restructuring language (+neighbors for context)."""
    paras = re.split(r"\n{2,}|\.\s{2,}", text)
    hits = []
    for i, p in enumerate(paras):
        if SIEVE.search(p):
            ctx = " ".join(paras[max(0, i - 1):i + 2])
            hits.append(ctx)
    return hits[:6]


def run():
    if not API_KEY:
        print("EARNINGS_API_KEY not set — earnings ingest dormant. Add the secret to activate.")
        return
    tickers = load_tickers()
    if not tickers:
        print("no earnings_tickers.csv — nothing to sweep")
        return
    ordinal = date.today().toordinal()
    pages = max(1, (len(tickers) + BATCH - 1) // BATCH)
    todays = tickers[(ordinal % pages) * BATCH:(ordinal % pages) * BATCH + BATCH]
    print(f"earnings: {len(tickers)} tickers, checking {len(todays)} this run")
    posted = ai = sieved = 0
    for tk in todays:
        text = latest_transcript(tk)
        time.sleep(0.4)
        if not text or not SIEVE.search(text):
            continue
        sieved += 1
        for chunk in relevant_chunks(text):
            raw = {
                "source_type": "news",
                "source_name": f"{tk} earnings call",
                "source_url": f"{API_BASE}/earning_call_transcript/{tk}",
                "title": f"{tk} earnings call transcript",
                "content": chunk,
                "text": chunk,
            }
            try:
                ex = extract_layoff_data(raw)
            except Exception:
                continue
            if not ex:
                continue
            if DRY:
                print(f"  DRY {tk}: {ex.get('company_name')} {ex.get('job_count')}")
                continue
            if post_to_wordpress(ex) == "posted":
                posted += 1
                ai += 1 if ex.get("ai_explicit") else 0
                print(f"  + {ex.get('company_name')} {ex.get('job_count')} (earnings, {tk})")
    detail = f"{len(todays)} tickers, {sieved} transcripts w/ layoff language, {posted} added ({ai} AI)"
    print("earnings ingest:", detail)
    if not DRY:
        report_source_health("earnings_ingest", "ok", posted, detail)


def main():
    if not os.environ.get("WP_SITE_URL"):
        print("WP_SITE_URL required")
        return 1
    try:
        run()
        return 0
    except Exception as exc:
        if not DRY and API_KEY:
            report_source_health("earnings_ingest", "degraded", 0, f"earnings ingest failed: {exc}")
        raise


if __name__ == "__main__":
    sys.exit(main())
