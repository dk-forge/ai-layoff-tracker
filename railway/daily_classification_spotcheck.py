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

import adjudication_panel as panel
import ops_notify
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

#: The alarm scope for held relabels. A resolve clears every open key beginning
#: `<scope>:`, so this prefix must not collide with another alerter's keys.
HOLD_ALERT_SCOPE = "relabel-hold"

# --------------------------------------------------------------------------
# The three-model adjudication panel (railway/adjudication_panel.py), armed
# ONLY on the HELD-RELABEL path.
# --------------------------------------------------------------------------
# WHAT ARMING CHANGES. Today a confirmed relabel that `screen()` cannot apply
# unattended (>= 5,000 jobs, an unreadable size, or off a guarded worldwide
# country label) is HELD and mailed to the owner as a bare notice. When the
# panel is armed, each such held relabel is routed to THREE independent models
# (Google + DeepSeek + OpenAI, see adjudication_panel.PANEL_MODELS) that must
# each APPROVE/REJECT and QUOTE the row's own evidence, and the verdict routes:
#
#   AUTO_APPLY  (unanimous, every vote cited, size KNOWN and < 5,000 jobs)
#               -> applied through the SAME sanctioned /edit correction path
#               `screen()`'s small fixes use, so it suppresses the old dedup
#               hash, pins the row, and is disclosed in the public corrections
#               log. This RESCUES a small relabel that was held only for the
#               guarded-label rule but that three citing models agree on.
#   REJECT      (any model rejected) -> logged for audit, NOT applied, NOT
#               mailed. A bad suggestion the panel killed is noise, not an
#               action item (the DOGE case).
#   HOLD        (a split, a non-citing approve, a headline-mover >= 5,000 even
#               at a citing 3-0, an unreadable size, or a panel error) -> NOT
#               applied; the owner gets a PANEL-VETTED one-click notice with the
#               3-0/2-1 tally and each model's cited reason, replacing today's
#               bare held email.
#
# A headline-mover (>= 5,000 jobs) NEVER auto-applies, at any tally: the panel
# itself returns HOLD for it. The magnitude bound is unchanged and is still
# re-checked by guard_edits at the moment of the write.
#
# COST. The panel fires ONLY on a held relabel, which is a rare, already
# contested event: the spot-check samples 30 rows/run and holds a handful/day
# (often zero). Each held relabel costs exactly THREE metered calls (one per
# model), all under spend's "panel" tag. A run that holds nothing spends
# nothing here. There is no per-row fan-out: volume is bounded by the caller,
# never by the size of the corpus.
#
# TODO (ai-causation): adjudication_panel.adjudicate_ai_causation() exists but
# is deliberately NOT wired here. ai_explicit is a higher-volume phase and must
# gain conflict/impact gating (fire only on a contested call, never on every
# row) before it can be armed, or it would put three calls behind every
# classification. Leave it dormant until that gate exists.

#: The kill switch. DORMANT BY DEFAULT: a newly-armed PAID loop that writes to
#: the public site ships off, exactly like a new source (CLAUDE.md, "Ship
#: key-gated sources DORMANT"). When OFF the script keeps today's behaviour
#: (hold + bare email, no panel, no panel spend). To ARM, set ALT_PANEL_ARMED
#: to 1/on/true/yes in the workflow env; to DISABLE again, remove that one line
#: (or set it to off). The parent verifies the armed loop against the real held
#: queue (see --dry-run-armed) BEFORE flipping this on.
PANEL_ARMED_DEFAULT = False


def panel_armed():
    raw = (os.environ.get("ALT_PANEL_ARMED") or "").strip().lower()
    if not raw:
        return PANEL_ARMED_DEFAULT
    return raw in {"1", "on", "true", "yes"}


class Deadline(Exception):
    """Raised by SIGALRM wherever execution happens to be."""


#: Set by the SIGALRM handler the instant the wall-clock budget is spent, and
#: never cleared. `signal.alarm` is one-shot: once it has fired there is no
#: second interrupt coming, so a caller that swallows the first Deadline and
#: tries again would run that retry with no protection at all. This flag is
#: what stands in for the alarm on every attempt after the first.
_deadline_message = None


def arm_deadline(seconds):
    def ring(signum, frame):
        global _deadline_message
        _deadline_message = f"wall-clock deadline ({seconds}s) reached"
        raise Deadline(_deadline_message)
    signal.signal(signal.SIGALRM, ring)
    signal.alarm(max(1, int(seconds)))

def summary(text):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as out:
            out.write(text + "\n")
    print(text)


def request_json(url, payload=None, headers=None, attempts=3, timeout=120):
    """A Deadline must reach main() as a Deadline, not as a RuntimeError.

    `metered_call` (railway/spend.py, out of bounds for this script to change)
    retries anything it does not recognise by exception class NAME, and a
    bare `except Exception` here used to convert the SIGALRM's Deadline into a
    RuntimeError before metered_call ever saw it -- so the retry it issued ran
    a brand-new urlopen with the one-shot alarm already spent and nothing left
    to bound it. This is the hang measured on 2026-08-19 (run 32269578659): the
    step ran 9m49s against a 360s deadline.

    Two changes close it: Deadline is re-raised untouched instead of being
    folded into `last`, and every attempt (including one a caller outside this
    function retries) checks `_deadline_message` BEFORE opening a socket, so a
    retry issued after the deadline has already rung costs nothing and hangs
    on nothing.
    """
    headers = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(attempts):
        if _deadline_message:
            raise Deadline(_deadline_message)
        try:
            data = json.dumps(payload).encode() if payload is not None else None
            if data is not None:
                headers = {"Content-Type": "application/json", **headers}
            req = urllib.request.Request(url, data=data, headers=headers)
            return json.load(urllib.request.urlopen(req, timeout=timeout))
        except Deadline:
            raise
        except Exception as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(str(last))


def first_json_object(content):
    """The FIRST complete JSON object in a model reply. Raises ValueError if none.

    The old reader sliced from the first '{' to the LAST '}' and handed the
    whole span to json.loads. That is correct for one object wrapped in prose
    and wrong for two: a reply of `{...}\\n{...}` slices to both objects and
    json.loads answers `Extra data: line 1 column 178 (char 177)`. That is the
    exact string that reddened "Data quality report (anomaly flags)" on
    2026-08-14 (run 31815799989) — a valid correction was selected, and the
    parser threw it away because the model had appended a second object after
    it. `response_format=json_object` is requested but not guaranteed.

    raw_decode reads ONE value and reports where it stopped, so trailing
    objects, trailing prose and code-fence tails all stop mattering. It is
    still NOT a permissive reader: a reply with no object, or whose first
    object is malformed, raises exactly as before. Do not "fix" a future
    parse failure by concatenating or repairing what came back — a second
    object is the model answering twice, and the first answer is the one the
    prompt asked for.
    """
    start = content.find("{")
    if start < 0:
        raise ValueError("no JSON object in the reply")
    return json.JSONDecoder().raw_decode(content, start)[0]


def ask_model(prompt):
    """One metered model call. Raises spend.PaidReadsOff if the brake is on.

    main() checks the brake once, before the sample is drawn, and this function
    is called TWICE per run (the flag pass and the confirm pass). One check
    cannot bound two calls, so the gate goes through spend.metered_call, where
    it is re-read per REQUEST.

    `attempts=1` INSIDE the lambda and `attempts=2` on metered_call is the
    whole point of this edit (2026-08-18). It used to read `attempts=2` inside,
    which put the second POST behind the first gate read and metered only
    whichever attempt came back: a run at its ceiling bought a call it had not
    checked for, and a timed-out-but-billed completion was charged to nobody.
    Same resilience, one request per gate read, every request counted.
    """
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    response = spend.metered_call(
        "deepseek/deepseek-chat",
        lambda: request_json(
            "https://openrouter.ai/api/v1/chat/completions",
            {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": prompt}],
             "response_format": {"type": "json_object"}},
            # This is an advisory daily sample, not a batch job. Keep its outage
            # budget bounded so a slow provider cannot hold the whole report open.
            {"Authorization": "Bearer " + key}, attempts=1, timeout=45,
        ),
        attempts=2, retry_sleep=5.0,
        what="a classification spot-check question")
    try:
        content = response["choices"][0]["message"]["content"]
        return first_json_object(content)
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
    """Tell the owner, through the one door operational mail leaves by.

    THIS USED TO ARRIVE AS THE NEWSLETTER. It POSTed to the site's `/alert`
    route, which calls bare `wp_mail()`, which the Brevo plugin rewrites to the
    SUBSCRIBER relay identity. So a notice saying "92,000 jobs are one
    unattended edit away from the published US headline" reached the owner from
    `newsletter@asktherecruiter.com` under the reader newsletter's display
    name. `ops_notify` gives it the operational From and the shared subject
    prefix instead, so it sorts with the alarms rather than with the mail he
    subscribed to.

    The dedup shape is unchanged: one open cause per set of held ids, cleared
    by `clear_hold_alert()`. `alert_state.decide()` mirrors what the endpoint
    did, so this is the same ruling read from a committed ledger.

    Failure to deliver is NOT a failed run and never reddens CI (the 2026-07-31
    rule: an outage must not manufacture red runs). Nothing is lost by a failed
    send either, because the backlog is recomputed from live rows on the next
    daily run and re-raised.
    """
    if not ops_notify.configured():
        summary("_The held relabels could not be mailed: RESEND_API_KEY is not "
                "configured. They are listed above and will be re-raised tomorrow._")
        return
    ids = ".".join(sorted(str(f["id"]) for f, _ in held))
    if not ops_notify.notify(
            f"{len(held)} label relabel(s) HELD for review, not applied",
            _hold_body(held, jobs_by_id, names_by_id),
            dedupe_key=f"{HOLD_ALERT_SCOPE}:{ids}"[:160],
            what="held-relabel notice"):
        summary("_The held relabels could not be mailed. They are listed above "
                "and are re-derived on tomorrow's run._")


def clear_hold_alert():
    """A run that held nothing clears whatever was open.

    Only called when the screening actually ran to completion. A run that could
    not reach the model does not know the backlog is empty, and silence is not a
    clear signal.
    """
    if not ops_notify.configured():
        return
    ops_notify.resolve(
        HOLD_ALERT_SCOPE,
        "label relabel backlog is clear",
        "Today's classification spot-check held no relabel for review.",
        what="relabel-hold recovery")


# --------------------------------------------------------------------------
# The armed held-relabel loop (panel_armed() only)
# --------------------------------------------------------------------------
def _panel_evidence(f, evidence_by_id):
    """The row's real evidence for the panel: source name/url + the excerpt the
    models must quote from. Falls back to the flag's own excerpt (if any) so a
    row that carried no stored source still gets its text in front of the panel.
    """
    ev = dict(evidence_by_id.get(f["id"]) or {})
    if not ev.get("excerpt"):
        ev["excerpt"] = str(f.get("excerpt") or "")
    return {"source_name": ev.get("source_name", ""),
            "url": ev.get("url", ""),
            "excerpt": ev.get("excerpt", "")}


def adjudicate_held(held, jobs_by_id, names_by_id, evidence_by_id, adjudicate=None):
    """Route each HELD relabel through the three-model panel.

    Returns (applied, still_held, rejected):
      applied     [(flag, PanelVerdict)] unanimous+citing under the bound, with
                  a KNOWN numeric size -> safe to auto-apply via /edit.
      still_held  [(flag, PanelVerdict|None)] the owner decides; a panel-vetted
                  one-click notice is mailed. A None verdict is a panel error on
                  that item (an error is not a judgement, so it holds).
      rejected    [(flag, PanelVerdict)] a model said no; logged, not mailed.

    spend.PaidReadsOff PROPAGATES (CLAUDE.md): a panel that could not afford
    every vote has reached no verdict, so the caller leaves every relabel HELD
    and applies nothing from the panel. `adjudicate` is injectable so the tests
    never build a client, touch the network, or spend.
    """
    adj = adjudicate or panel.adjudicate_relabel
    applied, still_held, rejected = [], [], []
    for f, _why in held:
        rid = f["id"]
        jobs = jobs_by_id.get(rid)
        size_known = isinstance(jobs, int)
        row = {"company": names_by_id.get(rid, ""),
               "job_count": jobs if size_known else 0}
        evidence = _panel_evidence(f, evidence_by_id)
        try:
            verdict = adj(row, f.get("field"), f.get("current"),
                          f.get("suggested"), evidence)
        except spend.PaidReadsOff:
            # Undecided: let it stop the whole loop. The caller holds everything.
            raise
        except Exception as exc:
            # A panel that errored on one item has NOT judged it. Hold it, do
            # not drop it, and carry the reason so the notice can say why.
            still_held.append(({**f, "_panel_error": str(exc)}, None))
            continue
        if verdict.verdict == panel.AUTO_APPLY and size_known:
            # AUTO_APPLY already implies the panel saw a sub-5,000 size (it holds
            # every headline-mover). The extra size_known guard means an
            # unreadable-size row can never be auto-applied on a job_count the
            # panel defaulted to 0.
            applied.append((f, verdict))
        elif verdict.verdict == panel.REJECT:
            rejected.append((f, verdict))
        else:
            # HOLD_FOR_REVIEW, or an AUTO_APPLY whose size we could not read.
            still_held.append((f, verdict))
    return applied, still_held, rejected


def _panel_vote_lines(verdict):
    """Each model's vote, cited quote and reason, for the run log and the mail."""
    if verdict is None:
        return ["    (the panel errored on this row and reached no verdict)"]
    lines = []
    marks = {True: "APPROVE", False: "REJECT", None: "NO-VOTE"}
    for vote in verdict.votes:
        cite = "cited" if vote.cited else "did NOT cite"
        lines.append(f"    [{marks[vote.approve]}] {vote.model} ({cite}): "
                     f"{vote.reason}")
        if vote.cited_quote:
            lines.append(f"        quote: {vote.cited_quote}")
        if vote.error:
            lines.append(f"        error: {vote.error}")
    return lines


def _one_click_command(f, company):
    """The pre-vetted apply-correction command the owner runs to accept a held
    relabel. It goes through apply_correction.py -> /edit, the SAME sanctioned
    path (suppresses the old dedup hash, pins the row, writes the public
    corrections log). No raw UPDATE, ever.
    """
    fields = json.dumps({f.get("field"): f.get("suggested")}, ensure_ascii=False)
    verify = f' --verify-company "{company}"' if company else ""
    return (f"python3 railway/apply_correction.py --ids {f['id']} "
            f"--action edit --fields '{fields}' "
            f'--reason "panel-reviewed relabel"{verify} --apply')


def log_panel_decisions(applied, rejected):
    """Write the panel's applied and rejected decisions to the run log. A
    rejected suggestion is auditable here (its verdict and every vote) but is
    not mailed: a bad suggestion the panel killed is not an action item.

    Calls the module-level `summary` by name (not a default-bound reference) so
    a test that patches `summary` sees these lines too.
    """
    for f, verdict in applied:
        summary(f"- PANEL AUTO_APPLY row {f['id']} `{f.get('field')}` "
                f"\"{f.get('current')}\" -> \"{f.get('suggested')}\" "
                f"(tally {verdict.approve_tally}, unanimous and every vote cited)")
        for line in _panel_vote_lines(verdict):
            summary(line)
    for f, verdict in rejected:
        summary(f"- PANEL REJECT row {f['id']} `{f.get('field')}` "
                f"\"{f.get('current')}\" -> \"{f.get('suggested')}\" "
                f"(tally {verdict.approve_tally}); not applied, not mailed.")
        for line in _panel_vote_lines(verdict):
            summary(line)


def _panel_hold_body(still_held, jobs_by_id, names_by_id=None):
    names_by_id = names_by_id or {}
    lines = ["The daily classification spot-check ran each held relabel past the "
             "three-model adjudication panel. The changes below were NOT applied: "
             "the panel did not clear them for an unattended write. Each carries "
             "the panel's tally, every model's cited reason, and a one-click "
             "command to apply it through the corrections path.\n"]
    for f, verdict in still_held:
        rid = f["id"]
        jobs = jobs_by_id.get(rid)
        company = names_by_id.get(rid, "")
        tally = verdict.approve_tally if verdict is not None else "no verdict"
        head = (f"HELD row {rid} {company} ({f.get('field')}): "
                f"\"{f.get('current')}\" -> \"{f.get('suggested')}\", "
                + (f"{int(jobs):,} jobs" if isinstance(jobs, int) else "job count UNKNOWN")
                + f". Panel tally: {tally}.")
        if verdict is not None and verdict.is_headline_mover:
            head += " Headline-mover (>= 5,000 jobs): never auto-applied."
        if f.get("_panel_error"):
            head += f" Panel error: {f['_panel_error']}."
        lines.append(head)
        lines.extend(_panel_vote_lines(verdict))
        lines.append("  To apply it (writes the public corrections log):")
        lines.append("    " + _one_click_command(f, company))
        lines.append("")
    lines.append("Ignoring this mail is safe and is often right: on 2026-08-08 an "
                 "unattended relabel of this shape put 92,000 jobs into the "
                 "published US headline for four days.")
    return "\n".join(lines)


def post_panel_hold_alert(still_held, jobs_by_id, names_by_id=None):
    """Mail the owner a PANEL-VETTED one-click notice, through the one door
    operational mail leaves by. Same dedup shape and scope as the bare notice
    (one open cause per set of held ids, cleared by clear_hold_alert), so the
    only thing that changed is that the mail now carries the panel's reasoning.
    """
    if not still_held:
        return
    if not ops_notify.configured():
        summary("_The panel-held relabels could not be mailed: RESEND_API_KEY is "
                "not configured. They are listed above and will be re-raised "
                "tomorrow._")
        return
    ids = ".".join(sorted(str(f["id"]) for f, _ in still_held))
    if not ops_notify.notify(
            f"{len(still_held)} label relabel(s) HELD by the panel, not applied",
            _panel_hold_body(still_held, jobs_by_id, names_by_id),
            dedupe_key=f"{HOLD_ALERT_SCOPE}:{ids}"[:160],
            what="panel-vetted held-relabel notice"):
        summary("_The panel-held relabels could not be mailed. They are listed "
                "above and are re-derived on tomorrow's run._")


def _dry_run_armed():
    """Show what the ARMED held-relabel loop WOULD do against the real held
    queue, writing nothing and emailing nothing.

    Reviewable and reversible: it runs the same two model passes and the same
    panel the live run would, then PRINTS apply/hold/reject per row with each
    model's tally and cited reason. It never POSTs /edit and never sends mail,
    so the parent can show the owner the decisions before flipping ALT_PANEL_ARMED
    on. It DOES make real metered model calls (flagging, confirmation, and three
    panel votes per held relabel), so it needs OPENROUTER_API_KEY and spends a
    few cents; a budget stop just prints UNDECIDED and exits 0.
    """
    print("=" * 72)
    print("ARMED HELD-RELABEL LOOP - DRY RUN (real queue, no writes, no mail)")
    print(f"panel models: {', '.join(panel.PANEL_MODELS)}")
    print("=" * 72)
    if not spend.paid_reads_enabled():
        print("paid reads are OFF (spend ceiling): cannot run the model passes.")
        return 0
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set: cannot make the model calls. Set it "
              "to preview real decisions.")
        return 0
    try:
        newest = request_json(API + "query?sort=layoff_date&dir=desc&per_page=15")
        biggest = request_json(API + "query?sort=job_count&dir=desc&per_page=15")
        rows = newest.get("data", []) + biggest.get("data", [])
        sample = [{"id": r["id"], "company": r["company_name"], "industry": r["industry"],
                   "country": r["country"], "jobs": r["job_count"],
                   "excerpt": (r.get("excerpt") or "")[:200]}
                  for r in rows if r.get("industry")]
        jobs_by_id = {r["id"]: r["jobs"] for r in sample}
        names_by_id = {r["id"]: r["company"] for r in sample}
        evidence_by_id = {r["id"]: {
            "source_name": (r.get("source_name") or r.get("source_type") or ""),
            "url": (r.get("source_url") or ""), "excerpt": (r.get("excerpt") or "")}
            for r in rows if r.get("id")}
        if not sample:
            print("no classified entries in this run's sample.")
            return 0
        prompt = ("You are auditing a layoff tracker's classifications. For each entry, judge whether "
                  "the industry and country labels match the company and excerpt. Reply STRICT JSON: "
                  '{"flags":[{"id":<id>,"field":"industry|country","current":"...","suggested":"...","why":"..."}]} '
                  "— empty flags list if everything is reasonable. Only flag CLEAR mismatches, not debatable ones.\n\n"
                  + json.dumps(sample, ensure_ascii=False))
        flags = ask_model(prompt).get("flags", [])
        label_flags = [f for f in flags if f.get("field") in ("industry", "country")
                       and f.get("id") and f.get("suggested")]
        if not label_flags:
            print("no label mismatches flagged; nothing to adjudicate.")
            return 0
        confirm_prompt = ("Re-check these proposed label corrections for a layoff tracker. "
                          "For each, answer whether the SUGGESTED value is clearly more accurate than CURRENT. "
                          "For a country label, judge WHERE THE JOBS WERE CUT, not where the company is "
                          "headquartered: a worldwide restructuring at an American company is not United States. "
                          'Reply STRICT JSON {"confirm":[{"id":..,"agree":true|false}]}.\n\n'
                          + json.dumps(label_flags, ensure_ascii=False))
        agreed = {i["id"] for i in ask_model(confirm_prompt).get("confirm", []) if i.get("agree")}
        confirmed = [f for f in label_flags if f["id"] in agreed]
        edits, held = screen(confirmed, jobs_by_id)
        print(f"\nsmall fixes screen() would auto-apply (no panel): "
              f"{[e['id'] for e in edits]}")
        if not held:
            print("no HELD relabels this run; the panel would not fire.")
            return 0
        print(f"\n{len(held)} HELD relabel(s) -> the panel:")
        applied, still_held, rejected = adjudicate_held(
            held, jobs_by_id, names_by_id, evidence_by_id)
        for label, bucket in (("AUTO_APPLY (would write via /edit)", applied),
                              ("HOLD (would email one-click)", still_held),
                              ("REJECT (logged, not applied, not mailed)", rejected)):
            print(f"\n== {label}: {len(bucket)} ==")
            for f, verdict in bucket:
                tally = verdict.approve_tally if verdict is not None else "no verdict"
                jobs = jobs_by_id.get(f["id"])
                print(f"  row {f['id']} {names_by_id.get(f['id'], '')} "
                      f"`{f.get('field')}` \"{f.get('current')}\" -> "
                      f"\"{f.get('suggested')}\" "
                      + (f"({int(jobs):,} jobs)" if isinstance(jobs, int) else "(jobs UNKNOWN)")
                      + f"  tally={tally}")
                for line in _panel_vote_lines(verdict):
                    print("  " + line)
        print("\n(DRY RUN: nothing was written and no mail was sent.)")
        return 0
    except spend.PaidReadsOff as exc:
        print(f"UNDECIDED (budget stop, no verdict): {exc}")
        return 0


def _summarize_bare_hold(held, jobs_by_id, names_by_id):
    """Today's held-relabel run-log lines (used when the panel is dormant, or
    when the panel could not afford a verdict). Kept as one function so the
    armed and dormant paths cannot drift apart in what they tell the log."""
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
        # The row's own evidence, for the adjudication panel (armed path only).
        # The FULL excerpt (not the 200-char sample truncation) plus the stored
        # source, so each model votes on the real text and quotes from it. Built
        # off `rows`, not `sample`, so it is populated whether or not the panel
        # is armed and costs nothing when it is not.
        evidence_by_id = {
            r["id"]: {
                "source_name": (r.get("source_name") or r.get("source_type") or ""),
                "url": (r.get("source_url") or ""),
                "excerpt": (r.get("excerpt") or ""),
            }
            for r in rows if r.get("id")
        }
        if not sample:
            summary("## Classification spot-check\nNo classified entries available for this run.")
            return 0
        prompt = ("You are auditing a layoff tracker's classifications. For each entry, judge whether "
                  "the industry and country labels match the company and excerpt. Reply STRICT JSON: "
                  '{"flags":[{"id":<id>,"field":"industry|country","current":"...","suggested":"...","why":"..."}]} '
                  "— empty flags list if everything is reasonable. Only flag CLEAR mismatches, not debatable ones.\n\n"
                  + json.dumps(sample, ensure_ascii=False))
        flags = ask_model(prompt).get("flags", [])
    except spend.PaidReadsOff as exc:
        summary("## Classification spot-check — deferred by the spend ceiling\n"
                "The data-quality report completed; the advisory model audit was "
                "NOT run (`" + str(exc) + "`). Nothing was judged, so nothing here "
                "is a finding about the corpus. It resumes on the next schedule.")
        return 0
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

        # The armed held-relabel loop. DORMANT by default: `held` is emailed as
        # today's bare notice and the panel never runs (no calls, no spend).
        panel_edits, panel_reason = [], ""
        if held and panel_armed():
            try:
                applied, still_held, rejected = adjudicate_held(
                    held, jobs_by_id, names_by_id, evidence_by_id)
            except spend.PaidReadsOff as exc:
                # UNDECIDED: the panel could not afford every vote. Apply nothing
                # from it and HOLD every relabel with today's bare notice; the
                # backlog is re-derived and re-adjudicated on the next run. A
                # budget stop is never an apply and never a crash.
                summary("**Panel adjudication deferred by the spend ceiling** (`"
                        + str(exc) + "`): every relabel is HELD, none auto-applied.")
                _summarize_bare_hold(held, jobs_by_id, names_by_id)
                post_hold_alert(held, jobs_by_id, names_by_id)
            else:
                summary(f"**Adjudication panel ran on {len(held)} held relabel(s):** "
                        f"{len(applied)} AUTO_APPLY, {len(still_held)} HELD for "
                        f"review, {len(rejected)} REJECT.")
                log_panel_decisions(applied, rejected)
                if still_held:
                    post_panel_hold_alert(still_held, jobs_by_id, names_by_id)
                else:
                    # Nothing left for a human: clear any open hold so a drained
                    # backlog stops reminding (same contract as today).
                    clear_hold_alert()
                panel_edits = [{"id": f["id"], "fields": {f["field"]: f["suggested"]}}
                               for f, _v in applied]
                panel_reason = ("Automated classification audit, adjudicated by a "
                                "three-model citing panel (unanimous approve, every "
                                "vote quoting the row's source). Applied only to "
                                "entries below " + f"{AUTO_APPLY_MAX_JOBS:,}" + " jobs; "
                                "larger relabels are held for a person to review.")
        elif held:
            _summarize_bare_hold(held, jobs_by_id, names_by_id)
            post_hold_alert(held, jobs_by_id, names_by_id)
        else:
            clear_hold_alert()

        # ---- writes: both edit sets go through the sanctioned /edit path ----
        if not edits and not panel_edits:
            return 0
        key = os.environ.get("WP_API_KEY", "")
        if not key:
            raise RuntimeError("WP_API_KEY is not configured; refusing to apply corrections")

        if edits:
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

        if panel_edits:
            # The panel-approved relabels, through the SAME /edit path (dedup-hash
            # suppression + public corrections log). guard_edits stays the last
            # magnitude check: a headline-mover that reached here is refused at
            # the write, panel verdict or not.
            guard_edits(panel_edits, jobs_by_id)
            result = request_json(API + "edit", {
                "edits": panel_edits, "reason": panel_reason,
            }, {"X-Layoff-API-Key": key}, attempts=3, timeout=90)
            applied = result.get("edited", [])
            summary(f"**Panel auto-applied {len(applied)} relabel(s)** cleared by a unanimous "
                    f"citing three-model panel — disclosed in the public corrections log.")
        return 0
    except spend.PaidReadsOff as exc:
        # Exit 0, not 1: the ceiling stopping the SECOND pass means the flags
        # were never confirmed, so nothing is applied and nothing is wrong. A
        # budget decision must not redden CI.
        summary("## Classification spot-check — confirmation deferred by the spend ceiling\n"
                f"{len(label_flags)} proposed label change(s) were flagged but NOT "
                "confirmed (`" + str(exc) + "`), so none were applied. A single-pass "
                "flag is not a finding. The next run re-samples.")
        clear_hold_alert()
        return 0
    except Deadline as exc:
        # Same reasoning as the PaidReadsOff branch above: the SECOND pass is
        # what stopped, so nothing was confirmed and nothing was applied. Exit
        # 0, not 1 -- a self-imposed deadline is the script finishing cleanly
        # with what it had, not a correction failure.
        summary("## Classification spot-check — confirmation skipped at its own deadline\n"
                f"{len(label_flags)} proposed label change(s) were flagged but the "
                "confirmation pass did not finish (`" + str(exc) + "`) before the "
                "script's own wall-clock deadline. Nothing was confirmed, so nothing "
                "was applied. It resumes on the next schedule.")
        clear_hold_alert()
        return 0
    except Exception as exc:
        summary("## Classification spot-check — correction failure\n"
                "A correction was selected but could not be applied: `" + str(exc) + "`.")
        return 1


if __name__ == "__main__":
    # --dry-run-armed previews the armed held-relabel loop against the real
    # queue, writing nothing and mailing nothing (see _dry_run_armed). It is the
    # gated review step: run it, show the owner the apply/hold/reject decisions,
    # then arm live by setting ALT_PANEL_ARMED=1 in the workflow.
    if "--dry-run-armed" in sys.argv[1:]:
        raise SystemExit(_dry_run_armed())
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
