"""Autonomously re-check legacy AI flags against their linked sources.

The worker fetches only rows that were previously tagged AI and remain
``legacy_unreviewed``. It never removes a record or changes the original
source/count/date. A fetched source is reclassified only after DeepSeek returns
an exact evidence quote for any causal AI claim; inaccessible sources remain
plainly marked legacy/unreviewed for a later retry.

Env: WP_SITE_URL, WP_API_KEY, OPENROUTER_API_KEY.
Optional: RECLASSIFY_BATCH (default 5). The scheduled batch is deliberately
small because each row may require a slow publisher fetch and a model call.
RECLASSIFY_DEADLINE_SECONDS (default 900) stops safely between rows so an
unreachable publisher or model cannot consume the GitHub Actions hard limit.

SAFE TO DEFER: the queue is `legacy_unreviewed` rows on the server, a row stays
queued until it is written, and the batch is re-derived from scratch each run.
"""
import html
import os
import re
import sys
import time

import requests

import host_call
from extractor import (
    classify_ai_evidence, spend_deferral_count, spend_deferred_since,
)
import spend

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "reclassify-legacy-ai"

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(100, int(os.environ.get("RECLASSIFY_BATCH", "5"))))
DEADLINE_SECONDS = max(60, min(1100, int(os.environ.get("RECLASSIFY_DEADLINE_SECONDS", "900"))))


def clean_html(content):
    text = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", content)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


# HTTP statuses that can NEVER succeed on a retry: the page is gone, or the
# publisher bot-walls automated reads. That is a permanent property of that URL,
# not a breakage of this job -- so these must not trip the "everything failed"
# alarm below. (moneycontrol.com 403s every run, which turned a healthy job red
# daily and emailed the owner a false alarm.)
PERMANENT_HTTP = {401, 403, 404, 410}
# The "everything failed" alarm needs a MEANINGFUL sample. A batch can legitimately
# contain 1-2 attemptable rows, and one transient miss there is noise, not an
# outage - a genuinely broken fetcher fails across many rows and still trips this.
MIN_ATTEMPTED_FOR_ALARM = 3


def fetch_text(url):
    if not url.startswith(("http://", "https://")):
        return ""
    response = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    response.raise_for_status()
    return clean_html(response.content[:2_000_000].decode(response.encoding or "utf-8", errors="replace"))


def api_get(path, params=None):
    return host_call.get_json(f"{SITE}/wp-json/layoffs/v1/{path}", params=params,
                              headers={"User-Agent": UA}, timeout=60)


def post_updates(items):
    return host_call.post_json(
        f"{SITE}/wp-json/layoffs/v1/reclassify", {"items": items},
        headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
    )


def main():
    """Deferral boundary. The host never answering is not this job failing."""
    try:
        code = _run()
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    host_call.clear(JOB)
    return code


def _run():
    if not (SITE and KEY and os.environ.get("OPENROUTER_API_KEY")):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1
    data = api_get("query",{"ai": "1", "review_status": "legacy_unreviewed", "per_page": BATCH, "page": 1, "sort": "id", "dir": "asc"})
    rows = data.get("data", [])
    if not rows:
        print("No legacy AI rows pending reclassification")
        return 0
    updates, unreadable, model_failures, blocked, empty = [], 0, 0, 0, 0
    deferred = 0
    started_at = time.monotonic()
    checked = 0
    for row in rows:
        # This worker changes no source or event fact. Stopping before a new
        # row is therefore safe and lets the next daily run resume the queue.
        if time.monotonic() - started_at >= DEADLINE_SECONDS:
            print(f"Reached RECLASSIFY_DEADLINE_SECONDS={DEADLINE_SECONDS}; stopping safely after {checked} row(s)")
            break
        if not spend.paid_reads_enabled():
            # Budget stop, not an outage: these rows were never read, they are
            # unmarked, and a later run reads them. Counting them as model
            # failures is what let a thrifty run exit 1 and page the owner.
            deferred = len(rows) - checked
            print(f"paid reads are OFF for budget: deferring the remaining "
                  f"{deferred} row(s) unread to a later run")
            break
        checked += 1
        try:
            text = fetch_text(row.get("source_url") or "")
            if not text:
                # 200 but nothing extractable (JS-rendered or paywalled shell).
                # A property of the page, not a failure of this job.
                empty += 1
                continue
            before = spend_deferral_count()
            result = classify_ai_evidence(text)
            if not result and spend_deferred_since(before):
                # Nobody read this row. Not checked, not failed.
                checked -= 1
                deferred = len(rows) - checked
                print(f"paid reads went off mid-row: deferring {deferred} "
                      f"unread row(s) to a later run")
                break
            if not result:
                model_failures += 1
                continue
            updates.append({"id": row["id"], **result})
            time.sleep(0.25)
        except requests.HTTPError as exc:
            code = getattr(exc.response, "status_code", None)
            if code in PERMANENT_HTTP:
                blocked += 1
                print(f"blocked id {row['id']}: HTTP {code} (publisher blocks automated reads; skipped)")
            else:
                unreadable += 1
                print(f"unreadable id {row['id']}: {exc}")
        except Exception as exc:
            unreadable += 1
            print(f"unreadable id {row['id']}: {exc}")
    if updates:
        result = post_updates(updates)
        print(f"reclassified={len(result.get('updated', []))} rejected={len(result.get('rejected', []))}")
    print(f"checked={checked} queued={len(updates)} blocked={blocked} empty={empty} "
          f"unreadable={unreadable} model_failures={model_failures} "
          f"deferred_on_spend={deferred}")
    if deferred:
        spend.note_truncated(f"{deferred} row(s) left unread: paid reads were "
                             f"off for budget")
        print(f"::notice::reclassify-legacy-ai SKIPPED {deferred} row(s) for "
              f"budget. Nobody read them, they are UNMARKED, and a later run "
              f"reads them. This run exits 0.")
    spend.record_job_run(items=checked, changed=len(updates))
    # A total failure should be visible in Actions rather than silently looking
    # like a successful historical clean-up.
    # Fail only on a REAL breakage: nothing written AND every row we could
    # actually attempt failed transiently. Publisher-blocked rows are excluded,
    # because a batch that happens to contain only bot-walled URLs is not an
    # outage and must not page the owner. Neither is a budget stop: `checked`
    # counts only rows a model was actually ASKED about, so deferred rows never
    # reach this arithmetic.
    attempted = checked - blocked - empty
    return 1 if (not updates and attempted >= MIN_ATTEMPTED_FOR_ALARM
                 and unreadable + model_failures == attempted) else 0


if __name__ == "__main__":
    sys.exit(main())
