"""Resilient daily classification spot-check for the data-quality workflow.

This is an advisory audit. Temporary API/model failures are written clearly to
the Actions summary but do not invalidate the otherwise successful data-quality
report. Any attempted automatic correction that fails still exits non-zero:
data-changing work must fail loudly.
"""
import json
import os
import signal
import sys
import time
import urllib.request
import spend

API = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: Wall-clock budget for this whole script, in seconds. The SCRIPT owns its
#: deadline (the Wayback archiver's pattern): it finishes cleanly with what it
#: has and says what it skipped, instead of running into the workflow's
#: timeout-minutes and being cancelled mid-step.
#:
#: Why a wall clock and not the per-call `timeout=`: urlopen's timeout bounds
#: each SOCKET operation, not the call. A server that sends headers and then
#: trickles — an LLM endpoint grinding through a long completion is exactly
#: this shape — never leaves any single read hanging 45 seconds, so the call
#: runs unbounded. That is what cancelled the data-quality job at its
#: 10-minute ceiling on 2026-07-29, 2026-08-03 and 2026-08-05 (run
#: 31021670125): a healthy run of this script takes under 30 seconds, and the
#: cancelled ones sat in this step for 9m40s and were still going.
#:
#: Sized from measurement: healthy runs of the WHOLE data-quality job take
#: 0.6-0.9 min, of which this script is ~10-30 s. 360 s is more than ten
#: times the healthy runtime — room for a slow provider, not for a hang —
#: and together with the ~40 s of earlier steps it keeps the job's worst
#: case near 7 minutes, comfortably inside the workflow's 10-minute ceiling.
DEADLINE_SECONDS = int(os.environ.get("ALT_SPOTCHECK_DEADLINE", "360"))


class Deadline(Exception):
    """Raised by SIGALRM wherever execution happens to be."""


def arm_deadline(seconds):
    def ring(signum, frame):
        raise Deadline(f"wall-clock deadline ({seconds}s) reached")
    signal.signal(signal.SIGALRM, ring)
    signal.alarm(max(1, int(seconds)))

def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as out:
            out.write(text + "\n")
    print(text)


def request_json(url, payload=None, headers=None, attempts=3, timeout=120):
    headers = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(attempts):
        try:
            data = json.dumps(payload).encode() if payload is not None else None
            if data is not None:
                headers = {"Content-Type": "application/json", **headers}
            req = urllib.request.Request(url, data=data, headers=headers)
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(str(last))


def ask_model(prompt):
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    response = request_json(
        "https://openrouter.ai/api/v1/chat/completions",
        {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": prompt}],
         "response_format": {"type": "json_object"}},
        # This is an advisory daily sample, not a batch job. Keep its outage
        # budget bounded so a slow provider cannot hold the whole report open.
        {"Authorization": "Bearer " + key}, attempts=2, timeout=45,
    )
    spend.record_usage(response.get("model") or "deepseek/deepseek-chat",
                       response.get("usage"))
    try:
        content = response["choices"][0]["message"]["content"]
        content = content[content.find("{"):content.rfind("}") + 1]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("model returned no usable JSON: " + str(exc))


def main():
    # Spend guard: this script builds its own OpenRouter client, so
    # extractor.py's gate does not cover it. Skip cleanly (exit 0) rather than
    # failing — a deferred classification spot-check is re-run on its next
    # schedule, and reddening CI over a budget decision is noise.
    arm_deadline(DEADLINE_SECONDS)
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling) — skipping the classification spot-check "
              "this run; it resumes on the next schedule")
        return 0
    try:
        newest = request_json(API + "query?sort=layoff_date&dir=desc&per_page=15")
        biggest = request_json(API + "query?sort=job_count&dir=desc&per_page=15")
        rows = newest.get("data", []) + biggest.get("data", [])
        sample = [{"id": r["id"], "company": r["company_name"], "industry": r["industry"],
                   "country": r["country"], "jobs": r["job_count"], "excerpt": (r.get("excerpt") or "")[:200]}
                  for r in rows if r.get("industry")]
        if not sample:
            summary("## Classification spot-check\nNo classified entries available for this run.")
            return 0
        prompt = ("You are auditing a layoff tracker's classifications. For each entry, judge whether "
                  "the industry and country labels match the company and excerpt. Reply STRICT JSON: "
                  '{"flags":[{"id":<id>,"field":"industry|country","current":"...","suggested":"...","why":"..."}]} '
                  "— empty flags list if everything is reasonable. Only flag CLEAR mismatches, not debatable ones.\n\n"
                  + json.dumps(sample, ensure_ascii=False))
        flags = ask_model(prompt).get("flags", [])
    except Deadline as exc:
        # Finish cleanly with what we have and say what was skipped: the
        # advisory audit is re-run on its next schedule, and an audit that was
        # SKIPPED-and-said-so is a different thing from a job cancelled at the
        # workflow ceiling with no summary at all.
        summary("## Classification spot-check — skipped at its own deadline\n"
                "The data-quality report completed; the advisory audit stopped itself (`"
                + str(exc) + "`) rather than run into the workflow ceiling. "
                "It resumes on the next schedule.")
        return 0
    except Exception as exc:
        summary("## Classification spot-check — temporarily unavailable\n"
                "The data-quality report completed, but the advisory model audit did not run after retries: `" + str(exc) + "`.")
        return 0

    summary(f"## Classification spot-check — {len(flags)} flag(s) from {len(sample)} sampled entries")
    label_flags = [f for f in flags if f.get("field") in ("industry", "country") and f.get("id") and f.get("suggested")]
    if not label_flags:
        return 0
    try:
        confirm_prompt = ("Independently verify these proposed label corrections for a layoff tracker. "
                          "For each, answer whether the SUGGESTED value is clearly more accurate than CURRENT. "
                          'Reply STRICT JSON {"confirm":[{"id":..,"agree":true|false}]}.\n\n'
                          + json.dumps(label_flags, ensure_ascii=False))
        agreed = {item["id"] for item in ask_model(confirm_prompt).get("confirm", []) if item.get("agree")}
        edits = [{"id": f["id"], "fields": {f["field"]: f["suggested"]}} for f in label_flags if f["id"] in agreed]
        if not edits:
            summary("No proposed label changes were independently confirmed.")
            return 0
        key = os.environ.get("WP_API_KEY", "")
        if not key:
            raise RuntimeError("WP_API_KEY is not configured; refusing to apply corrections")
        result = request_json(API + "edit", {
            "edits": edits,
            "reason": "Automated classification audit: label mismatch flagged and independently confirmed by two LLM passes (DeepSeek)",
        }, {"X-Layoff-API-Key": key}, attempts=3, timeout=90)
        applied = result.get("edited", [])
        summary(f"**Auto-applied {len(applied)} double-confirmed label fix(es)** — disclosed in the public corrections log.")
        return 0
    except Exception as exc:
        summary("## Classification spot-check — correction failure\n"
                "A correction was selected but could not be applied: `" + str(exc) + "`.")
        return 1


if __name__ == "__main__":
    code = main()
    # The sample size varies by path here, so items is left UNKNOWN rather
    # than guessed; the metered cost and call count are exact either way.
    try:
        spend.record_job_run()
    except Deadline:
        # Bookkeeping caught by the tail end of the wall clock: the audit
        # itself finished, and a metering row deferred to the next run is not
        # an action item.
        print("::notice::spend.record_job_run deferred: the script's wall-clock deadline rang during bookkeeping")
    sys.exit(code)
