"""Resilient daily classification spot-check for the data-quality workflow.

This is an advisory audit. Temporary API/model failures are written clearly to
the Actions summary but do not invalidate the otherwise successful data-quality
report. Any attempted automatic correction that fails still exits non-zero:
data-changing work must fail loudly.

WHY BIG RELABELS ARE NO LONGER APPLIED UNATTENDED
-------------------------------------------------
Half this script's sample is `sort=job_count&dir=desc` — the fifteen largest
rows in the corpus, i.e. the rows selected by construction for maximum headline
leverage. Until 2026-08-12 every confirmed label change on them went straight
through `/edit` with no magnitude bound, no cap and no human.

On 2026-08-08 (run 31264210709) that re-scored 114335 Citigroup 52,000, 113529
General Motors 47,000 and 64351 Cinemaworld 45,000 from "Multiple countries" to
"United States". It added 92,000 jobs to the published US headline on the
`country_basis=any` basis and 144,000 on the strict job-location basis, left the
worldwide total untouched — a re-scoring moves a row between labels without
adding anything to the corpus — and stood on the live site for four days.
Full forensics: docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md section 8.

Two properties make that systematic rather than unlucky:

* **The bait is permanent.** Asked whether "Citigroup" or "General Motors"
  belongs under "Multiple countries", a model reasons from the company's
  nationality rather than from where the jobs were cut. The same top-fifteen
  sample holds Philips, VW Group, Lufthansa, UBS and HSBC, every one of them
  legitimately "Multiple countries" for a famous national company. Tomorrow's
  sample will bait it again.
* **The second pass is not a second opinion.** The "two independent LLM passes"
  this script used to advertise, in its run summary AND in the reason it wrote
  to the PUBLIC corrections log, were the same `ask_model` called twice with the
  same model. A shared prior survives both, so double confirmation gives no
  protection against exactly this class of error. That wording was wrong and is
  gone; what remains is described as what it is, a repeat.

So the write is now bounded, and the bound is enforced by `guard_edits` in the
function that POSTs rather than by the screening step alone. Anything the bound
catches is HELD: named in the run summary, and mailed to the owner through the
same cause-keyed `/alert` route the CI alerter and the weekly health digest use.

WHY THIS QUEUE CANNOT ROT
-------------------------
The project's own rule is that a queue nobody drains is the same as no fix.
This one is not a store — it is recomputed from live data every run. A held
relabel that the owner never acts on is re-derived tomorrow from the same rows
and re-raised, so nothing can be silently lost by a failed POST or a lost
runner. `/alert` dedupes by cause (the exact set of held row ids), so the owner
gets one mail per distinct backlog plus a fortnightly reminder, not one a day;
and a run that holds nothing posts `resolve_scope` so a drained backlog stops
reminding. Operator instructions: docs/RUNBOOK.md, "a label relabel was HELD".
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

#: A confirmed relabel on a row of this many jobs or more is HELD for a human,
#: never applied unattended.
#:
#: Not an arbitrary number: it is the line THIS SAME WORKFLOW already draws.
#: data-quality.yml's anomaly report surfaces "single WARN notices with unusually
#: large headcounts (>= 5,000)" precisely because a row that size deserves human
#: eyes. A row the job flags for a human to read is not a row an unattended model
#: may relabel two steps later in the same job.
#:
#: It also disposes of the sampling problem without changing the sampling. The
#: `sort=job_count&dir=desc` half of the sample is the fifteen biggest rows in
#: the corpus; on 2026-08-11 the smallest of them was 35,000. So the bound
#: removes auto-apply from the size-selected half entirely, while the
#: `sort=layoff_date` half keeps fixing ordinary small rows. Reading the big
#: rows is still valuable — flagging them is how the incident would have been
#: FOUND. It is the writing that had no business being unattended.
AUTO_APPLY_MAX_JOBS = int(os.environ.get("ALT_SPOTCHECK_AUTO_APPLY_MAX_JOBS", "5000"))

#: Country labels a relabel is never auto-applied AWAY from, at any size.
#:
#: Separate from the magnitude bound and not redundant with it. "Multiple
#: countries" is the specific label the nationality bias misreads: the model
#: sees an American company and answers "United States" without noticing that
#: the label describes where the jobs were, not who the employer is. The bias
#: does not switch off below 5,000 jobs; it is just cheaper when it is wrong.
#: ERM's importer maps Eurofound's `World` to this label, so these are exactly
#: the rows the 2026-08-08 step moved.
GUARDED_COUNTRY_LABELS = {"multiple countries", "worldwide", "global",
                          "multiple", "various", "europe", "european union"}

#: The `/alert` scope for held relabels. The endpoint clears every open key
#: beginning `<scope>:` on a resolve, so this prefix must not collide with
#: another alerter's keys.
HOLD_ALERT_SCOPE = "relabel-hold"


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


def hold_reason(flag, jobs):
    """Why this confirmed relabel must NOT be applied unattended, or None.

    `jobs` is the row's job count as the sample reported it, or None when the
    row was never in the sample (a model can return an id it invented). None is
    UNKNOWN, and UNKNOWN is not "small enough to edit" — the same PASS / FAIL /
    UNKNOWN rule the data-integrity checks follow.
    """
    if jobs is None:
        return ("its job count is UNKNOWN (the id was not in this run's sample), "
                "so the size of the edit could not be measured")
    try:
        jobs = int(jobs)
    except (TypeError, ValueError):
        return f"its job count ({jobs!r}) could not be read as a number"
    if jobs >= AUTO_APPLY_MAX_JOBS:
        return (f"it carries {jobs:,} jobs, at or above the {AUTO_APPLY_MAX_JOBS:,}-job "
                f"bound for an unattended edit")
    if (flag.get("field") == "country"
            and str(flag.get("current", "")).strip().lower() in GUARDED_COUNTRY_LABELS):
        return (f"it moves a row off \"{flag.get('current')}\", the label a model "
                f"misreads as the employer's nationality (the 2026-08-08 defect)")
    return None


def screen(confirmed, jobs_by_id):
    """Split confirmed relabels into (edits to apply, [(flag, why held)])."""
    edits, held = [], []
    for f in confirmed:
        why = hold_reason(f, jobs_by_id.get(f["id"]))
        if why:
            held.append((f, why))
        else:
            edits.append({"id": f["id"], "fields": {f["field"]: f["suggested"]}})
    return edits, held


def guard_edits(edits, jobs_by_id):
    """Re-check the bound in the function that WRITES. Raises on a violation.

    Deliberately duplicates `screen`. A bound computed in one place and trusted
    in another is one refactor away from being reported and not enforced, which
    is indistinguishable from the defect this closes. This is the last thing
    that runs before the POST, and it fails loudly: a data-changing call that
    cannot vouch for its own payload must not go out.

    It re-checks the MAGNITUDE bound only. That is the part derivable from the
    payload alone: an edit carries the row id and the new value, not the old
    label, so the guarded-label rule cannot be re-derived here and stays owned
    by `screen`. Magnitude is the rule that moved the headline.
    """
    for e in edits:
        jobs = jobs_by_id.get(e["id"])
        why = hold_reason({"id": e["id"], "field": "", "current": "",
                           "suggested": ""}, jobs)
        if why:
            raise RuntimeError(
                f"refusing to apply an out-of-bounds edit to row {e['id']}: {why}")


def _hold_body(held, jobs_by_id, names_by_id=None):
    names_by_id = names_by_id or {}
    lines = ["The daily classification spot-check confirmed label changes that it "
             "did NOT apply, because they are too large to make unattended.\n"]
    for f, why in held:
        jobs = jobs_by_id.get(f["id"])
        lines.append(
            f"HELD row {f['id']} {names_by_id.get(f['id'], '')} "
            f"({f.get('field')}): \"{f.get('current')}\" -> "
            f"\"{f.get('suggested')}\", "
            + (f"{int(jobs):,} jobs" if isinstance(jobs, int) else "job count UNKNOWN")
            + f". Not applied because {why}. Model's stated reason: {f.get('why', '')}")
    lines.append(
        "\nNothing was written. To act on one, read docs/RUNBOOK.md "
        '"a label relabel was HELD": check the row against its own source, then '
        "either apply it through the apply-correction workflow (which is a human "
        "sign-off and writes the public corrections log) or ignore this mail. "
        "\nIgnoring it is safe and is often right: on 2026-08-08 the same "
        "suggestion, applied unattended, put 92,000 jobs into the published US "
        "headline for four days.")
    return "\n".join(lines)


def post_hold_alert(held, jobs_by_id, names_by_id=None):
    """Tell the owner through the route that already reaches him.

    Failure to deliver is NOT a failed run and never reddens CI (the 2026-07-31
    rule: an outage must not manufacture red runs). Nothing is lost by a failed
    POST either, because the backlog is recomputed from live rows on the next
    daily run and re-raised.
    """
    key = os.environ.get("WP_API_KEY", "")
    if not key:
        summary("_The held relabels could not be mailed: WP_API_KEY is not "
                "configured. They are listed above and will be re-raised tomorrow._")
        return
    ids = ".".join(sorted(str(f["id"]) for f, _ in held))
    try:
        request_json(API + "alert", {
            "subject": f"{len(held)} label relabel(s) HELD for review, not applied",
            "body": _hold_body(held, jobs_by_id, names_by_id),
            "dedupe_key": f"{HOLD_ALERT_SCOPE}:{ids}"[:160],
        }, {"X-Layoff-API-Key": key}, attempts=2, timeout=45)
    except Exception as exc:
        summary(f"_The held relabels could not be mailed (`{exc}`). They are listed "
                f"above and are re-derived on tomorrow's run._")


def clear_hold_alert():
    """A run that held nothing clears whatever was open.

    Only called when the screening actually ran to completion. A run that could
    not reach the model does not know the backlog is empty, and silence is not a
    clear signal.
    """
    key = os.environ.get("WP_API_KEY", "")
    if not key:
        return
    try:
        request_json(API + "alert", {
            "subject": "label relabel backlog is clear",
            "body": "Today's classification spot-check held no relabel for review.",
            "resolve_scope": HOLD_ALERT_SCOPE,
        }, {"X-Layoff-API-Key": key}, attempts=2, timeout=45)
    except Exception as exc:
        print(f"could not post the relabel-hold recovery: {exc}")


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
        # The sizes as the API reported them, keyed by id. This is the ONLY
        # source of magnitude for the bound below: a job count the model echoed
        # back inside a flag is model output, not a reading of the corpus, and
        # must never be what decides whether an edit is small enough to apply.
        jobs_by_id = {r["id"]: r["jobs"] for r in sample}
        names_by_id = {r["id"]: r["company"] for r in sample}
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
        clear_hold_alert()
        return 0
    try:
        # NOT an independent verification, whatever this prompt says to the
        # model: it is the same model, called a second time. Kept because a
        # repeat still catches a one-off parse or attention slip; described
        # honestly because calling it independence is what made 92,000 wrong
        # jobs look double-checked.
        confirm_prompt = ("Re-check these proposed label corrections for a layoff tracker. "
                          "For each, answer whether the SUGGESTED value is clearly more accurate than CURRENT. "
                          "For a country label, judge WHERE THE JOBS WERE CUT, not where the company is "
                          "headquartered: a worldwide restructuring at an American company is not United States. "
                          'Reply STRICT JSON {"confirm":[{"id":..,"agree":true|false}]}.\n\n'
                          + json.dumps(label_flags, ensure_ascii=False))
        agreed = {item["id"] for item in ask_model(confirm_prompt).get("confirm", []) if item.get("agree")}
        confirmed = [f for f in label_flags if f["id"] in agreed]
        if not confirmed:
            summary("No proposed label changes were confirmed by the second pass.")
            clear_hold_alert()
            return 0

        edits, held = screen(confirmed, jobs_by_id)

        if held:
            summary(f"**{len(held)} confirmed relabel(s) HELD for review, not applied.** "
                    f"A relabel is never applied unattended on a row of "
                    f"{AUTO_APPLY_MAX_JOBS:,} jobs or more, on a row whose size this run "
                    f"could not read, or off a worldwide country label "
                    f"(docs/RUNBOOK.md, \"a label relabel was HELD\"):")
            for f, why in held:
                jobs = jobs_by_id.get(f["id"])
                summary(f"- HELD row {f['id']} {names_by_id.get(f['id'], '')} `{f.get('field')}` "
                        f"\"{f.get('current')}\" -> \"{f.get('suggested')}\" "
                        + (f"({int(jobs):,} jobs)" if isinstance(jobs, int) else "(jobs UNKNOWN)")
                        + f" — {why}")
            post_hold_alert(held, jobs_by_id, names_by_id)
        else:
            clear_hold_alert()

        if not edits:
            return 0
        key = os.environ.get("WP_API_KEY", "")
        if not key:
            raise RuntimeError("WP_API_KEY is not configured; refusing to apply corrections")
        # The bound, re-checked in the function that writes. See guard_edits.
        guard_edits(edits, jobs_by_id)
        result = request_json(API + "edit", {
            "edits": edits,
            "reason": ("Automated classification audit: a label mismatch flagged by a model "
                       "and re-checked by a second pass of the same model (DeepSeek). Applied "
                       "only to entries below " + f"{AUTO_APPLY_MAX_JOBS:,}" + " jobs; larger "
                       "relabels are held for a person to review."),
        }, {"X-Layoff-API-Key": key}, attempts=3, timeout=90)
        applied = result.get("edited", [])
        summary(f"**Auto-applied {len(applied)} re-checked label fix(es)** on entries below "
                f"{AUTO_APPLY_MAX_JOBS:,} jobs — disclosed in the public corrections log.")
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
