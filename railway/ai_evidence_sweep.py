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
AI_SWEEP_MIN_JOBS (default 2000), AI_SWEEP_MAX (default 20), AI_SWEEP_LIVE=1,
AI_SWEEP_DEADLINE_SECONDS (default 1320, whole-run wall clock).

THE RUN OWNS ITS OWN CLOCK (archive_backfill / reason_backfill pattern).
AI_SWEEP_MAX bounds the number of EVENTS, not the time: each event re-fetches
its stored source (up to 3 retries x 40s) plus an unbounded number of Google
News articles, and asks the model about EVERY one of them. When the Google News
route started returning results on 2026-08-03 this job went from ~1.2 min/run
to 8.7-15.4 min/run against a 20-minute ceiling. Per-event work is committed as
it is decided (each upgrade POSTs immediately), so stopping between events --
or between texts within an event -- loses nothing: the row stays untagged and
the next daily run re-reads it. Stopping ourselves beats being cancelled, which
would also drop the spend-ledger write at the end.
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

# AI-CAUSATION MODEL. This sweep decides ai_explicit exactly like the two
# places CLAUDE.md already names (extractor.py's full extraction and
# classify_ai_evidence()): "AI-causation is correctness-critical", so it uses
# extractor.MODEL, never the cheaper classify-path model. Until 2026-09-03 it
# used a bare "deepseek/deepseek-chat" literal that answered to neither name --
# a third, undocumented AI-causation call site on a model the owner had ruled
# out months earlier on EU compliance grounds. Importing extractor.MODEL both
# fixes the compliance problem and closes that gap: this sweep now moves with
# the one AI-causation model everywhere else, instead of carrying its own
# frozen copy.
try:
    import extractor
    AI_CAUSATION_MODEL = extractor.MODEL
except Exception:                   # pragma: no cover - import guard, mirrors OpenAI above
    AI_CAUSATION_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

# Google News RSS, not NewsAPI. NewsAPI was retired 2026-07-25, and this sweep
# kept querying it six times per event, printing "0 unique articles" every
# single time -- wasted HTTP on a corpse, found by the 2026-08-02 per-job cost
# attribution. Same discovery route the daily cron already uses.
try:
    from sources.google_news import pull_google_news
except Exception:
    pull_google_news = None

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
LIVE = os.environ.get("AI_SWEEP_LIVE", "").lower() in {"1", "true", "yes"}
MIN_JOBS = max(500, int(os.environ.get("AI_SWEEP_MIN_JOBS") or "2000"))
MAX_EVENTS = max(1, int(os.environ.get("AI_SWEEP_MAX") or "20"))
TIMEOUT = 40
# MEASURED, the successful runs since the Google News route began returning
# results on 2026-08-03 ("Run AI evidence sweep" step): 12.8, 12.4, 8.7, 15.4,
# 13.7, 9.5, 9.6 minutes of job time across the scheduled runs to 08-10, then
# 1022s on the verification dispatch 31469499159 (2026-08-11), which checked
# all 20 events and is the new max. 1022 x 1.25 = 1278s, rounded up to the
# whole minute. Below this the sweep would truncate runs that finish today --
# safely now, and reported, but truncation is still lost throughput.
# The ceiling is 1500s (25min) because ai-evidence-sweep.yml allows the job
# 27 minutes. A deadline that can be raised past its own workflow's
# timeout-minutes is not a deadline: the run is killed mid-flight instead of
# stopping itself and reporting. Raise the workflow first, then this.
DEADLINE_SECONDS = max(60, min(1500, int(os.environ.get("AI_SWEEP_DEADLINE_SECONDS") or "1320")))
STARTED_AT = time.monotonic()


def past_deadline():
    """True once the run must stop starting new work."""
    return time.monotonic() - STARTED_AT >= DEADLINE_SECONDS

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

    THREE RETURN VALUES, and the third is why this comment exists:
      a quote  -- the employer named AI
      ''       -- we asked and the employer did not name AI (a VERDICT)
      None     -- we did not ask (budget), so there is NO verdict

    None is not '' . The caller writes "keep-untagged: no employer AI quote
    found" on '', which is a statement that we looked. Collapsing a budget stop
    into that branch would publish a finding about a row nobody read.
    """
    # Read the brake BEFORE the "no client configured" answer, and before
    # spend.metered_call reads it again at the request. Both checks are one
    # call apart (this function makes exactly one), so neither is the coarse
    # per-item gate; this one exists because '' below is a VERDICT and a run
    # with paid reads off must not reach it by way of a missing client.
    if not spend.paid_reads_enabled():
        return None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key and text):
        return ""
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
            f"Text about {company}'s layoffs is below. If the EMPLOYER names AI "
            "or automation as a reason for the cuts, copy the exact sentence that "
            "says so, verbatim, and nothing else. If the employer does not name "
            "AI/automation as a cause (market pressure, demand, costs, merger, "
            "etc. do NOT count), answer exactly NONE.\n\n"
            f"TEXT:\n{text[:4500]}"
        )
        resp = spend.metered_call(AI_CAUSATION_MODEL, lambda: client.chat.completions.create(
            model=AI_CAUSATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0, max_tokens=120,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        ), what=f"the AI-quote read for {company}")
        quote = resp.choices[0].message.content.strip().strip('"').strip()
        if not quote or quote.upper().startswith("NONE") or len(quote) < 12:
            return ""
        # Must appear (loosely) in the source text; otherwise the model invented it.
        norm = lambda s: re.sub(r"\s+", " ", s.lower())
        if norm(quote)[:60] not in norm(text):
            return ""
        return quote[:300]
    except spend.PaidReadsOff:
        return None            # not asked: there is no verdict about this text
    except Exception:
        return ""


def _second_pass_agrees(company, quote):
    """A cheap independent check that the quote really is an EMPLOYER AI cause.

    True / False are verdicts; None means the budget stopped us before asking.
    """
    if not spend.paid_reads_enabled():   # see _ai_quote: False is a verdict too
        return None
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not (OpenAI and api_key):
        return False
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key,
                        # ZERO: the SDK retries by default (2), which
                        # re-POSTs inside the callable handed to
                        # metered_call — a charge with no gate read and
                        # no meter entry. Retry via metered_call's own
                        # `attempts=`, which re-reads the brake and
                        # meters each try.
                        max_retries=0)
        resp = spend.metered_call(AI_CAUSATION_MODEL, lambda: client.chat.completions.create(
            model=AI_CAUSATION_MODEL,
            messages=[{"role": "user", "content": (
                "Answer only yes or no. Does this sentence show the EMPLOYER "
                f"naming AI or automation as a reason for {company}'s job cuts "
                f"(not a journalist's framing, not investment, not a future "
                f"projection)?\n\n\"{quote}\"")}],
            temperature=0, max_tokens=4,
            timeout=int(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "35")),
        ), what=f"the second-pass check for {company}")
        return resp.choices[0].message.content.strip().lower().startswith("y")
    except spend.PaidReadsOff:
        return None            # not asked: no verdict, not a disagreement
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
        print("paid reads are OFF (spend ceiling or the monthly cap) — skipping "
              "the AI-evidence sweep this run; it resumes on the next schedule")
        # Record the skip: a job that never ran is not a job that found nothing,
        # and a month with no ledger entry for it reads as 'no metered run yet'
        # (UNKNOWN) rather than as a budget stop nobody can see.
        spend.record_job_run(items=0, changed=0,
                             truncated=spend.run_truncation()
                             or "paid reads were off for the whole run")
        return 0
    if not SITE:
        print("WP_SITE_URL required")
        return 1
    print(f"AI evidence sweep: {'LIVE' if LIVE else 'DRY RUN'} | "
          f">= {MIN_JOBS} jobs, up to {MAX_EVENTS} events")
    events = _big_untagged()
    print(f"{len(events)} big untagged 2026 event(s) to check")
    upgraded = checked = 0
    deferred = 0
    truncated = None
    for row in events:
        # Nothing is half-written per event (each upgrade POSTs as it is
        # decided), so stopping here is safe and the row is re-read tomorrow.
        if past_deadline():
            deferred = len(events) - checked
            truncated = (f"wall-clock deadline {DEADLINE_SECONDS}s reached with "
                         f"{deferred} event(s) unread")
            print(f"  reached AI_SWEEP_DEADLINE_SECONDS={DEADLINE_SECONDS}s — "
                  f"stopping cleanly with {deferred} event(s) deferred to the next run")
            break
        if not spend.paid_reads_enabled():
            # Ceiling or monthly cap tripped mid-sweep: keep what was decided,
            # defer the rest to the next schedule.
            deferred = len(events) - checked
            truncated = (f"spend ceiling reached with {deferred} event(s) unread")
            print(f"  spend ceiling reached — deferring the remaining "
                  f"{deferred} event(s) to the next run")
            break
        checked += 1
        rid = row.get("id")
        company = str(row.get("company_name") or "").strip()
        # Re-read the stored source, then a targeted AI-focused press search.
        texts = [_fetch_text(row.get("source_url"))]
        if pull_google_news:
            try:
                for a in pull_google_news(queries=[
                        f'"{company}" (AI OR automation) (layoffs OR "job cuts")']):
                    texts.append(str(a.get("raw_text") or a.get("description") or ""))
            except Exception:
                pass
        quote = ""
        unread = ""            # why this event never reached a verdict
        for txt in texts:
            # The texts list is as long as the press search returns, and each
            # entry costs up to two model calls -- ~25 calls per event on a
            # normal day. THIS is the loop that made the named per-run ceiling
            # leak: the outer loop checked the budget once per event, so the
            # last event could overshoot by a whole event's worth of calls
            # (measured 2026-08-07: $0.0196 against a $0.015 ceiling; still
            # $0.0166 on 2026-08-11). It now checks the clock per text, and the
            # budget per CALL -- inside spend.metered_call, which is the only
            # boundary that bounds the overshoot to one call.
            if past_deadline():
                unread = "wall-clock deadline reached mid-event"
                print(f"  deadline reached mid-event for {company}; the row stays "
                      f"untagged and is re-read next run")
                break
            quote = _ai_quote(company, txt)
            if quote is None:            # not asked: budget, not a finding
                unread = "spend ceiling reached mid-event"
                break
            agrees = _second_pass_agrees(company, quote) if quote else False
            if agrees is None:
                unread = "spend ceiling reached mid-event"
                quote = ""
                break
            if quote and agrees:
                break
            quote = ""
        if unread and not quote:
            # No verdict was reached for this event. Do not count it as checked
            # and do not print a keep-untagged decision: nothing was decided.
            checked -= 1
            deferred = len(events) - checked
            truncated = truncated or (f"{unread}; {deferred} event(s) undecided")
            print(f"  undecided      {company}: stopped before a verdict "
                  f"(budget or deadline); re-read next run")
            break
        if not quote:
            print(f"  keep-untagged  {company} ({row.get('job_count')}): no employer AI quote found")
            continue
        status = _upgrade(rid, quote)
        upgraded += 1 if status in ("would-upgrade", "upgraded") else 0
        print(f"  {status:14} {company} ({row.get('job_count')}): \"{quote[:90]}\"")
        time.sleep(0.5)
    print(f"{'TRUNCATED' if truncated else 'done'}: {checked} checked, {upgraded} "
          f"{'would upgrade' if not LIVE else 'upgraded'} with an employer AI quote"
          + (f", {deferred} deferred ({truncated})" if deferred else "")
          + f" ({time.monotonic() - STARTED_AT:.0f}s)")
    spend.record_job_run(items=checked, changed=upgraded, truncated=truncated)
    return 0


if __name__ == "__main__":
    sys.exit(main())
