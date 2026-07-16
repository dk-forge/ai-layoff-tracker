"""Resilient daily classification spot-check for the data-quality workflow.

This is an advisory audit. Temporary API/model failures are written clearly to
the Actions summary but do not invalidate the otherwise successful data-quality
report. Any attempted automatic correction that fails still exits non-zero:
data-changing work must fail loudly.
"""
import json
import os
import sys
import time
import urllib.request

API = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


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
    try:
        content = response["choices"][0]["message"]["content"]
        content = content[content.find("{"):content.rfind("}") + 1]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("model returned no usable JSON: " + str(exc))


def main():
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
    sys.exit(main())
