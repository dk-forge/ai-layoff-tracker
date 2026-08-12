#!/usr/bin/env python3
"""Measure what the models actually charged, and stop a runaway before it empties
the account.

    python3 railway/spend.py             # report
    python3 railway/spend.py --degrade   # exit 0, switch PAID reads off when over
    python3 railway/spend.py --enforce   # exit 1 when over the monthly allowance

Ported from the sibling tracker's spend.py (2026-08-02). Every design choice
below was learned there the hard way, or here on 2026-07-28..08-02 when the
OpenRouter ACCOUNT fell $71.86 -> $22.92 in seven days with no brake of any kind
in this repo.

WHY THIS EXISTS AT ALL
----------------------
`openrouter_balance_check.py` reads a BALANCE. A balance answers "how much is
left", never "what did that run cost" or "is this run expensive". It also reads
whichever key the runtime holds, so the Railway cron -- which carries its OWN
OpenRouter key and is the only scheduled process on Railway -- was invisible to
it. This module measures spend at the point it is incurred, so both keys report.

THE CEILING DEGRADES, IT DOES NOT HALT
--------------------------------------
Most of what this tracker collects costs nothing. WARN, SEC/EDGAR structured
fields, ERM and every state scraper derive their fields from a column and call
no model; the seen-URL pre-check, the server-side dedup and the whole WordPress
side are free. Halting all of that to protect a budget none of it spends is a
self-inflicted outage, and it is exactly what happened in the sibling on
2026-07-30: `--enforce` stopped the WHOLE collect job at 90% of the allowance
and every job went red for the rest of the month.

So `--degrade` is what the collecting jobs run. It never fails the job. When the
month's spend is past the ceiling it sets ALT_PAID_READS=off, `extractor.py`
refuses every paid call, and each deferred candidate returns UNMARKED.

"UNMARKED" IS NOT A PROMISE, IT IS A PROPERTY OF THIS PIPELINE
-------------------------------------------------------------
`seen_urls.filter_already_seen` drops a URL only when the SITE already holds it
(a row or a retained source report). A deferred candidate writes no row, so its
URL never enters the record, so the next run pulls it again and extracts it.
Deferral costs depth for the rest of the month, never coverage. Nothing here has
to remember anything for that to hold.

MONTH-TO-DATE IS A DELTA, NEVER A LIFETIME FIGURE
-------------------------------------------------
OpenRouter's /auth/key `usage` is cumulative for the life of the key and never
resets. Enforcing a MONTHLY allowance directly against it means the guard trips
permanently the moment lifetime spend crosses one month's budget -- at a few
dollars a month, autonomous collection dies forever in month three and shows up
only as red runs. That bug shipped in the sibling (audit 2026-07-28, finding 5).
So month-to-date is `lifetime_now - snapshot_taken_at_month_start`, and the
snapshot is COMMITTED (railway/spend_month.json) so it survives an ephemeral
runner.

The snapshot is keyed by a fingerprint of the API key, never the key: two keys
(GitHub Actions and Railway) bill the same account and each needs its own
month-start. A fingerprint is a one-way hash prefix, so this file is safe to
commit and safe to print.

WHY THERE IS ALSO A PER-RUN CEILING
-----------------------------------
Railway has no git and no persistent volume, so a container CAN read the
committed snapshot it was deployed with but CANNOT write a new one. Where the
snapshot cannot be refreshed, month-to-date is UNKNOWN -- and UNKNOWN is not a
pass. The brake that still works there needs no durable state at all: this
module meters the CURRENT PROCESS exactly, from the token counts OpenRouter
returns on every response, and refuses further paid calls once one run has spent
RUN_CEILING_USD. That bounds the worst case whatever the month-to-date says, and
it is what makes the Railway cron guardable at all.

The per-run meter is exact, not an estimate: `record_usage()` is fed
`response.usage` from each completion and priced at the model's published rate.
That is also what makes "cost per stored row" answerable -- see run_summary().
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

KEY_URL = "https://openrouter.ai/api/v1/auth/key"
MODELS_URL = "https://openrouter.ai/api/v1/models"
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# The budget the owner set. Kept here rather than in a secret so it is reviewable
# in a diff -- it is a policy, not a credential.
#
# INTERIM. It is not yet a measured statement about what full coverage costs on
# this tracker; it is a ceiling low enough that the 2026-07-28..08-02 burn
# ($6.45-$7.00/day, i.e. ~$200/month) could not have happened under it.
#
# WHY $18 AND NOT $20 (owner's decision, 2026-08-12)
# -------------------------------------------------
# This tracker's OpenRouter key carries its OWN $20/month PROVIDER limit (the
# sibling tracker has a separate key with a separate $20). Two caps therefore
# exist, and only one of them can be the one that binds:
#
#   * the PROVIDER cap is a HARD STOP. It does not degrade. When it is reached
#     the next paid call returns 402 at whatever arbitrary point the run had
#     got to — mid-batch, mid-candidate — and the job's own accounting of what
#     it did and did not reach is whatever it happened to be at that instant.
#   * the POLICY cap here is a GRACEFUL STOP. Crossing it switches paid reads
#     off, leaves every free collector running, and returns each deferred
#     candidate UNMARKED so a later run reads it. The stop is disclosed, the
#     run is recorded as TRUNCATED, and no coverage is lost.
#
# Setting the policy cap EQUAL to the provider cap means our own guard can
# never fire first: the provider hard-stops us instead, and we trade a clean
# disclosed degradation for a failed call. So the policy cap sits $2 below the
# provider cap, and the 90% STOP_AT_FRACTION line ($16.20) sits $3.80 below it.
# That gap is the whole point of the number — if the provider limit moves,
# move this one to stay under it, do not match it.
#
# Raised 10.0 -> 18.0 because $10 was the cap actually binding: on 2026-08-12
# the sibling tracker's collect run printed "the monthly spend allowance was
# already exhausted ($10.08 of ...)" and degraded, so the provider headroom
# above $10 was unreachable. See docs/TECHLOG.md 2026-08-12.
MONTHLY_ALLOWANCE_USD = 18.0

# Stop with headroom left, so a long batch cannot overshoot mid-run.
STOP_AT_FRACTION = 0.9

# MEASURED, not modelled: what the free-standing ingest costs per month, from
# record_usage() on real Railway cron runs (~$0.09/run x 2/day). Every ladder
# below is written against this number, so it lives here as a constant rather
# than as a sentence in three comments and a magic `- 3.0` in a test. If ingest
# is re-measured, this is the ONE place to change, and the ladder test moves
# with it.
MEASURED_INGEST_USD_PER_MONTH = 5.1

# Per-run ceiling: the backstop that works without durable state (see the module
# docstring). The measured Railway cron run costs ~$0.09, so this is ~2x
# headroom on a normal run, and it caps the 2x/day cron at ~$12/month even in
# the total absence of a month-to-date reading.
#
# THIS IS A FLAT NUMBER, NOT A FRACTION OF THE ALLOWANCE (2026-08-12). It used
# to be `MONTHLY_ALLOWANCE_USD * 0.02`, which quietly made the state-free brake
# on the single largest consumer a function of the policy cap: raising the
# allowance 10 -> 18 would have widened this from $0.20 to $0.36, i.e. the
# unguardable-by-month Railway cron would have been free to spend ~$21/month —
# more than the whole allowance — with nothing in the diff saying so. A brake
# sized from a MEASURED run cost must not move when a budget moves.
RUN_CEILING_USD = float(os.environ.get("ALT_RUN_CEILING_USD", 0.20))

# The environment variable a degraded run sets. Read by extractor.py, which is
# the only module in this repo that can spend.
PAID_READS_ENV = "ALT_PAID_READS"

# WHY THE NAMED CEILING USED TO BE A LABEL (fixed 2026-08-11)
# ----------------------------------------------------------
# JOB_RUN_CEILINGS_USD below names a per-run ceiling for each paid job. Until
# today the ONLY route from that table to the brake was `apply_job_ceiling()`,
# which runs inside `spend.py --degrade` and writes ALT_RUN_CEILING_USD to
# $GITHUB_ENV for the STEPS THAT FOLLOW. So the named number bound only when a
# separate workflow step had run, succeeded, and been able to write that file.
# Anywhere else — a local run, a `python ai_evidence_sweep.py` by hand, a guard
# step whose $GITHUB_ENV write failed (which that function catches and prints),
# the Railway cron — the job silently got the $0.20 GLOBAL default instead:
# 13x ai-evidence-sweep's named $0.015. ops_status.py read the table and
# reported the job as over "its named ceiling", which was true, and the reason
# was that nothing in the job's own process had ever heard of it.
#
# `effective_run_ceiling_usd()` closes that: the ceiling is resolved IN THE
# JOB'S PROCESS, from the same table, every time it is checked. The env var
# keeps working and still wins, because an explicit operator override must not
# be silently re-tightened.

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "spend_month.json")

# ---------------------------------------------------------------------------
# Per-job budget shares — ONE table, and the arithmetic behind it
# ---------------------------------------------------------------------------
#
# Each scheduled LLM job gets a NAMED per-run ceiling. The `--degrade` step
# looks up the job (from GITHUB_WORKFLOW_REF, so no workflow needs an
# argument), writes ALT_RUN_CEILING_USD for the steps that follow, and the
# existing in-process brake (`paid_reads_enabled`) enforces it mid-run: the
# job DEGRADES at its ceiling — deferred candidates return on a later run —
# it never halts and never reddens.
#
# THE LADDER, honestly (2026-08-02). Three kinds of number, labelled:
#   MEASURED  main ingest (Railway cron): ~$0.09/run x 2/day = ~$5.1/month,
#             from record_usage() on real runs. The account-level burn
#             ($6.99/day, 2026-07-26..08-02) is NOT this repo's figure: it
#             includes the sibling tracker and the since-fixed backfill
#             re-read parasite (~$4/day).
#   COUNTED   per-job daily volumes, from the 2026-08-02 Actions run logs:
#             dedupe-llm 60 clusters; ai-evidence-sweep 20 checks;
#             enrich-roles 40; reason-backfill 40 model reads;
#             industry-backfill 200 rows x 2 confirm calls; reclassify <=5;
#             company-watchlist 143 queued, deadline after 40 companies,
#             0 posted; supplemental-news ~55 candidates for 2 stored;
#             hi-warn 34 notices; news-catchup ~113/week; process-tips 0.
#   MODELLED  DeepSeek prices x typical call sizes (extract ~3.1K in/250 out
#             = ~$0.0011; classify ~500 in/20 out = ~$0.00015; dedupe cluster
#             ~1.2K in/100 out = ~$0.0004). Small jobs at today's volumes
#             model to ~$0.20-0.28/day (~$6-8.5/month) — which does NOT fit
#             $5/month on top of a $5.1 ingest, and does not even fit $10.
#
# So the ceilings below are set to make the INTERIM allowance hold, and
# `test_spend_ledger.test_the_worst_case_sum_fits_beside_the_measured_ingest`
# is the arithmetic in a test: sum(ceiling x runs-per-month) must fit inside
# MONTHLY_ALLOWANCE_USD - MEASURED_INGEST_USD_PER_MONTH. The three jobs whose
# modelled appetite exceeds their share — industry-backfill,
# company-watchlist, supplemental-news — run THROTTLED against it: each
# already resumes where it stopped, so a ceiling slows the queue drain, it
# never loses coverage. That is a stated throttle, not a silent cut.
#
# THE LADDER AT $18 (2026-08-12), stated so the next reader can check it:
#   allowance                                            $18.00
#   less MEASURED ingest (the Railway cron)              -$5.10
#   = budget the named ceilings may claim                $12.90
#   claimed by the table below, worst case               $11.10
#   spare                                                 $1.80
# At $10 that budget was $4.90 and the table already claimed $6.60, so the
# ladder was over-subscribed before this change and the test said so the
# moment its reserve stopped being a literal `- 3.0` (see the test).
#
# WHAT $18 BOUGHT: edgar-history-sweep finally has a named ceiling. It is a
# DAILY paid job that had never been in this table, because naming it at $10
# was impossible in either direction — at its $0.200 global default it claims
# $6.00/month on a $4.90 budget, and even at its measured cost it does not
# close the gap. Sized from MEASUREMENT, not from the default: three
# authorised runs on 2026-08-11 cost $0.6012 for 1,762 candidates, all
# `complete: true`, none truncated; per SINGLE MONTH-WINDOW (which is what the
# daily rotation runs — the three were multi-month range dispatches) that is
# $0.0907 to $0.1115. $0.150 is ~35% above the dearest window observed, and it
# is a TIGHTENING of the $0.200 it silently ran under before, not a loosening.
#
# THE $5/MONTH TARGET is documented here and NOT yet enforced: it requires
# (a) the ingest funnel port (dedup-before-LLM + headline gate on the cron's
# news path, the sibling's cost-funnel template) taking MEASURED ingest to
# ~$3.5/month, and (b) small jobs at ~$1.5/month: dedupe-llm and
# ai-evidence-sweep at 3x/week, company-watchlist weekly, supplemental-news
# gated on the pre-extract dedup. Flip MONTHLY_ALLOWANCE_USD to 5.0 only
# after (a) is measured, not before.
#
# Keys are workflow file basenames (sans .yml). A job not listed here keeps
# the global RUN_CEILING_USD default. `railway-cron` is deliberately absent:
# Railway runs no --degrade step and the cron keeps the default ceiling, so
# free ingest is untouched by this table.
JOB_RUN_CEILINGS_USD = {
    # job id                 per-run $   cadence      basis for the number
    "dedupe-llm":              0.025,  # daily    MODELLED 60 x $0.0004
    "ai-evidence-sweep":       0.015,  # daily    MODELLED 20 x ~$0.0008
    "enrich-context":          0.005,  # daily    COUNTED ~1-25 small reads
    "enrich-roles":            0.010,  # daily    MODELLED 40 x ~$0.0003
    "reason-backfill":         0.005,  # daily    MODELLED 40 x $0.00015
    "industry-backfill":       0.025,  # daily    THROTTLE of MODELLED $0.06
    "reclassify-legacy-ai":    0.005,  # daily    COUNTED <=5 reads
    "company-watchlist":       0.030,  # daily    THROTTLE of MODELLED $0.055
    "supplemental-news":       0.030,  # daily    THROTTLE of MODELLED $0.06
    "data-quality":            0.005,  # daily    COUNTED ~2 calls
    "process-tips":            0.010,  # daily    COUNTED usually 0 tips
    "hi-warn-import":          0.015,  # daily    COUNTED few new notices
    "hi-warn-dryrun":          0.015,  # manual   same probe, dry
    "foreign-filings":         0.020,  # dormant  cron commented out
    "edgar-history-sweep":     0.150,  # daily    MEASURED, see note below
    "news-catchup":            0.150,  # weekly   MODELLED ~113 x $0.0011
    "distress-watchlist":      0.050,  # weekly   COUNTED small sweep
    "source-verification-audit": 0.200,  # monthly  bigger sampled audit
}

# The committed per-job ledger. One entry per (job, run): what it cost, how
# many items it touched, what it stored or changed. Jobs only PRINT their
# SPEND_LEDGER_V1 line; `--harvest` (run by the daily balance job, the only
# workflow that commits) is the file's single writer, collecting those lines
# out of the day's run logs. One commit a day instead of one push per job.
LEDGER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "spend_jobs.json")
LEDGER_MARKER = "SPEND_LEDGER_V1"
LEDGER_KEEP_DAYS = 60

# Published prices, USD per token, as a floor under a failed price lookup. These
# are only a FALLBACK: prices are fetched live from the keyless /models endpoint
# so a provider price change cannot silently make the meter lie. Fetched
# 2026-08-02. Over-pricing is the safe direction to be wrong (the guard trips
# early), so the fallback is deliberately not rounded down.
FALLBACK_PRICES = {
    "deepseek/deepseek-chat": (0.0000002574, 0.0000010287),
    # The pre-extraction gate's default model (extractor.GATE_MODEL). Price
    # from the sibling tracker's committed OpenRouter snapshot ($0.10/M in,
    # $0.40/M out); the live /models fetch overrides this whenever reachable.
    "google/gemini-2.5-flash-lite": (0.0000001, 0.0000004),
}
_DEFAULT_PRICE = (0.0000010, 0.0000030)  # unknown model: assume dearer than DeepSeek

_price_cache: dict[str, tuple[float, float]] = {}
_prices_fetched = False

# The current process's exact meter.
_run = {"cost_usd": 0.0, "calls": 0, "prompt_tokens": 0,
        "completion_tokens": 0, "cached_prompt_tokens": 0}
_run_ceiling_tripped = False

# Per-source attribution for the meter. cron.py (and any batch caller) names
# the collector whose candidate is about to be extracted; record_usage() then
# books each call under that name as well as into the run total. Before this
# existed, the Railway cron's spend was ONE number per run, so "which source
# is the money going to" was unanswerable — the 2026-08 measurement had to
# attribute ~$0.5/day by subtracting every OTHER consumer from a balance.
_meter_tag = None
_by_tag: dict[str, dict] = {}


def set_meter_context(tag: str | None) -> None:
    """Attribute subsequent record_usage() calls to `tag` (a collector name,
    e.g. 'gdelt'). None clears the context; untagged calls book under
    'untagged' so the breakdown always sums to the run total."""
    global _meter_tag
    _meter_tag = (tag or "").strip() or None


def run_breakdown() -> dict[str, dict]:
    """{tag: {cost_usd, calls, kept, dropped}} for this process. The kept/
    dropped counts are gate outcomes booked via record_gate_outcome()."""
    return {t: dict(v) for t, v in _by_tag.items()}


def _tag_bucket(tag: str) -> dict:
    return _by_tag.setdefault(tag, {"cost_usd": 0.0, "calls": 0,
                                    "kept": 0, "dropped": 0})


def record_gate_outcome(kept: bool, tag: str | None = None) -> None:
    """Count a gate keep/drop under the active (or given) source tag."""
    bucket = _tag_bucket(tag or _meter_tag or "untagged")
    bucket["kept" if kept else "dropped"] += 1


def annotate_tag(tag: str, **counts) -> None:
    """Attach integer counts (items=, stored=, ...) to a source tag so the
    per-run record can say what each collector's spend bought."""
    bucket = _tag_bucket(tag)
    for k, v in counts.items():
        if v is not None:
            bucket[k] = int(v)


def _get_json(url: str, api_key: str | None = None, timeout: int = 30):
    """Stdlib-only GET. `requests` is not guaranteed present in every runtime
    that imports this module (ops_status.py is stdlib-only by rule, and the
    local test env has no `requests`), and a spend guard that cannot be imported
    is a spend guard that is not enforced."""
    headers = {"User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Prices and the exact in-process meter
# --------------------------------------------------------------------------

def _load_prices() -> None:
    """Fetch published per-token prices once per process. Keyless endpoint."""
    global _prices_fetched
    if _prices_fetched:
        return
    _prices_fetched = True
    try:
        data = _get_json(MODELS_URL).get("data") or []
    except Exception as exc:  # network, proxy block, schema change
        print(f"spend: could not fetch live model prices ({exc}); "
              f"using the committed fallback table")
        return
    for m in data:
        pricing = m.get("pricing") or {}
        try:
            _price_cache[m.get("id")] = (float(pricing.get("prompt")),
                                         float(pricing.get("completion")))
        except (TypeError, ValueError):
            continue


def price_for(model: str) -> tuple[float, float]:
    """(prompt, completion) USD per token for `model`, live if reachable."""
    _load_prices()
    if model in _price_cache:
        return _price_cache[model]
    return FALLBACK_PRICES.get(model, _DEFAULT_PRICE)


def record_usage(model, usage) -> float:
    """Meter one completion and return what it cost.

    `usage` is the `response.usage` object OpenRouter returns on every call, so
    this is the charged token count, not an estimate from prompt length. Any
    failure to read it is charged at zero rather than raising: a meter must
    never be able to break the pipeline it measures.
    """
    try:
        if isinstance(usage, dict):
            # Raw urllib callers (dedupe_llm, the spot-check, the audit) hold
            # the parsed JSON, not an SDK object. Same charged counts.
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            completion_tokens = int(usage.get("completion_tokens") or 0)
            charged = usage.get("cost")
            details = usage.get("prompt_tokens_details") or {}
            cached = details.get("cached_tokens") if isinstance(details, dict) else 0
        else:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            charged = getattr(usage, "cost", None)
            details = getattr(usage, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    except (TypeError, ValueError, AttributeError):
        return 0.0
    try:
        cached = int(cached or 0)
    except (TypeError, ValueError):
        cached = 0
    # Prefer the CHARGED figure when the response carries one. Callers that
    # send OpenRouter `usage: {include: true}` get `usage.cost` back — the
    # credits actually debited, provider discounts and prompt-cache hits
    # included — which the local price table can only approximate (it prices
    # every prompt token at the full input rate, so a provider-cached static
    # preamble is over-billed by the meter while the account is billed less).
    # A meter that can read the bill must not estimate it. The fallback stays
    # the token-price product: over-pricing is the safe direction to be wrong,
    # so a response without `cost` can trip the guard early, never late.
    cost = None
    try:
        if charged is not None and float(charged) >= 0:
            cost = float(charged)
    except (TypeError, ValueError):
        cost = None
    if cost is None:
        p_rate, c_rate = price_for(model)
        cost = prompt_tokens * p_rate + completion_tokens * c_rate
    _run["cost_usd"] += cost
    _run["calls"] += 1
    _run["prompt_tokens"] += prompt_tokens
    _run["completion_tokens"] += completion_tokens
    _run["cached_prompt_tokens"] += cached
    bucket = _tag_bucket(_meter_tag or "untagged")
    bucket["cost_usd"] += cost
    bucket["calls"] += 1
    # So a retry of this same logical run starts from what it has already spent
    # instead of from zero. See _run_state_path().
    _persist_run_cost()
    return cost


def run_cost_usd() -> float:
    return _run["cost_usd"]


def run_summary(rows_stored: int | None = None) -> str:
    """One line answering 'was this run expensive', including cost per stored
    row when the caller knows how many rows it stored.

    Cost per stored row is the number that makes a run judgeable: 100 calls that
    store 40 rows and 100 calls that store 0 rows cost the same and are not the
    same event. `backfill.py` firing ~5,150 calls/day for ~234 useful rows was
    invisible for exactly as long as nobody divided one by the other.
    """
    parts = [f"LLM spend this run: ${_run['cost_usd']:.4f} over {_run['calls']} call(s)",
             f"{_run['prompt_tokens']:,} prompt + {_run['completion_tokens']:,} completion tokens"]
    if rows_stored is not None:
        if rows_stored > 0:
            parts.append(f"{rows_stored} row(s) stored, "
                         f"${_run['cost_usd'] / rows_stored:.4f} per stored row")
        else:
            parts.append("0 rows stored, so every cent of this run bought nothing")
    return " | ".join(parts)


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def effective_run_ceiling_usd(job: str | None = None) -> float:
    """This run's per-run ceiling, resolved in THIS process.

    Precedence, highest first:
      1. ALT_RUN_CEILING_USD in the environment -- an explicit operator (or
         `apply_job_ceiling`) override. Never silently re-tightened.
      2. JOB_RUN_CEILINGS_USD[current job] -- the NAMED ceiling, which is now
         a brake wherever the job runs and not only where a guard step ran.
      3. RUN_CEILING_USD -- the global default, which is what `railway-cron`
         keeps by deliberately not being in the table.
    """
    override = (os.environ.get("ALT_RUN_CEILING_USD") or "").strip()
    if override:
        try:
            return float(override)
        except ValueError:
            pass  # unparseable override: fall through rather than run uncapped
    named = JOB_RUN_CEILINGS_USD.get(job or current_job())
    return float(named) if named is not None else RUN_CEILING_USD


def paid_reads_enabled() -> bool:
    """False when paid model calls must not be made right now.

    Three independent reasons, any one sufficient:
      * ALT_PAID_READS=off   -- a `--degrade` step decided the month is spent.
      * this run has already spent its per-run ceiling (see
        effective_run_ceiling_usd) -- the state-free brake.
      * the MONTH is spent, measured here rather than inherited from a step
        that may not have run -- see month_gate().

    Checked by extractor.py at the top of every paid function, and by the five
    scripts that build their own client.
    """
    global _run_ceiling_tripped
    if (os.environ.get(PAID_READS_ENV, "").strip().lower() == "off"):
        note_truncated("paid reads were switched off for this run "
                       "(ALT_PAID_READS=off)")
        return False
    # Measured against the LOGICAL run (this process + earlier attempts of the
    # same run), so a shell retry loop cannot buy itself a fresh ceiling.
    spent = logical_run_cost_usd()
    ceiling = effective_run_ceiling_usd()
    if spent >= ceiling:
        if not _run_ceiling_tripped:
            _run_ceiling_tripped = True
            print(f"::warning::spend: this run has spent ${spent:.4f}, "
                  f"at or past the ${ceiling:.3f} per-run ceiling for "
                  f"'{current_job()}'. Paid extraction is OFF for the rest of "
                  f"this run. Free ingest continues; deferred candidates are "
                  f"unmarked and return on a later run. This run is TRUNCATED "
                  f"and is recorded as such.")
        note_truncated(f"per-run ceiling ${ceiling:.3f} reached after "
                       f"${spent:.4f}")
        return False
    blocked, why = month_gate()
    if blocked:
        note_truncated(why)
        return False
    return True


# --------------------------------------------------------------------------
# A truncated run is not a clean run
# --------------------------------------------------------------------------
#
# PASS / FAIL / UNKNOWN are three states in this repo, and "the job exited 0"
# is not evidence that the job finished its work. A run stopped by its ceiling,
# by the monthly cap, or by a wall-clock deadline has left work undone, and the
# ledger it writes has to say so -- otherwise a throttled job and a job with
# nothing to do produce identical records, and the $/row it reports is computed
# over an amount of work nobody can name.
_truncation: str | None = None


def note_truncated(reason: str) -> None:
    """Record that this run stopped short. First reason wins (it is the cause;
    everything after it is a consequence). Never raises."""
    global _truncation
    try:
        if _truncation is None and reason:
            _truncation = str(reason)[:300]
    except Exception:  # noqa: BLE001 — bookkeeping must not break the job
        pass


def run_truncation() -> str | None:
    """Why this run stopped early, or None if it ran to completion."""
    return _truncation


def reset_run_meter() -> None:
    """Test-only: clear the process meter."""
    global _run_ceiling_tripped, _carried_usd, _meter_tag, _truncation
    _run.update({"cost_usd": 0.0, "calls": 0, "prompt_tokens": 0,
                 "completion_tokens": 0, "cached_prompt_tokens": 0})
    _run_ceiling_tripped = False
    _carried_usd = None
    _meter_tag = None
    _truncation = None
    _by_tag.clear()


# --------------------------------------------------------------------------
# The per-run ceiling has to survive a retry
# --------------------------------------------------------------------------
#
# Several data jobs wrap their script in a shell retry:
#
#     for attempt in 1 2 3; do python industry_backfill.py && exit 0; ...
#
# That is the right call for reliability -- a transient OpenRouter 5xx at row
# 190 of 200 should not page anybody. But each attempt is a NEW PROCESS, and
# the per-run meter lived only in that process's memory. So the ceiling reset
# on every attempt, and a job that failed twice could spend 3x its named
# ceiling with the brake reporting nothing wrong. The failure path was the
# most expensive path in the repo and it was the one nothing was watching.
#
# The fix is a small file in the runner's temp dir, keyed by run and attempt,
# holding what this logical run has already spent. It is best-effort in both
# directions: if it cannot be read the job runs with a fresh meter (the old
# behaviour, never worse), and if it cannot be written nothing raises. A meter
# must never break the job it measures.
_carried_usd: float | None = None


def _run_state_path() -> str | None:
    """Where this logical run's carried spend lives, or None if there is no
    durable scratch space (a dev machine, or Railway, which has neither)."""
    explicit = (os.environ.get("ALT_RUN_SPEND_FILE") or "").strip()
    if explicit:
        return explicit
    run_id = (os.environ.get("GITHUB_RUN_ID") or "").strip()
    tmp = (os.environ.get("RUNNER_TEMP") or "").strip()
    if not (run_id and tmp):
        return None
    attempt = (os.environ.get("GITHUB_RUN_ATTEMPT") or "1").strip()
    job = current_job()
    return os.path.join(tmp, f"alt_run_spend_{run_id}_{attempt}_{job}.json")


def carried_run_cost_usd() -> float:
    """What earlier attempts of this same logical run already spent."""
    global _carried_usd
    if _carried_usd is not None:
        return _carried_usd
    _carried_usd = 0.0
    path = _run_state_path()
    if path:
        try:
            with open(path) as fh:
                _carried_usd = float(json.load(fh).get("cost_usd") or 0.0)
        except (OSError, ValueError, TypeError, AttributeError):
            _carried_usd = 0.0  # unreadable: fall back to a fresh meter
    return _carried_usd


def _persist_run_cost() -> None:
    path = _run_state_path()
    if not path:
        return
    try:
        with open(path, "w") as fh:
            json.dump({"cost_usd": round(logical_run_cost_usd(), 8)}, fh)
    except (OSError, TypeError, ValueError):
        pass  # best effort; never break the job


def logical_run_cost_usd() -> float:
    """This process's spend PLUS what earlier attempts of the same run spent.

    This, not run_cost_usd(), is what the per-run ceiling is measured against.
    """
    return carried_run_cost_usd() + _run["cost_usd"]


# --------------------------------------------------------------------------
# The per-job ledger
# --------------------------------------------------------------------------

def current_job() -> str:
    """The job id this process runs as: ALT_JOB if set, else the workflow
    file's basename (GITHUB_WORKFLOW_REF is 'owner/repo/.github/workflows/
    dedupe-llm.yml@refs/...'), else 'local'. No workflow needs to pass its
    own name for attribution to work."""
    explicit = (os.environ.get("ALT_JOB") or "").strip()
    if explicit:
        return explicit
    ref = os.environ.get("GITHUB_WORKFLOW_REF") or ""
    base = ref.split("@")[0].rsplit("/", 1)[-1]
    if base.endswith((".yml", ".yaml")):
        return base.rsplit(".", 1)[0]
    return "local"


def _load_ledger() -> dict:
    try:
        with open(LEDGER_PATH) as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"v": 1, "entries": []}


def _merge_ledger_entries(ledger: dict, new_entries: list[dict]) -> int:
    """Upsert entries keyed by (job, run_id-or-date, attempt). Returns how
    many were actually new. Trims to LEDGER_KEEP_DAYS so the committed file
    stays a ledger, not an archive."""
    def _key(e):
        return (e.get("job"), str(e.get("run_id") or e.get("date")),
                str(e.get("attempt") or ""))
    seen = {_key(e) for e in ledger["entries"]}
    added = 0
    for e in new_entries:
        if not isinstance(e, dict) or not e.get("job") or not e.get("date"):
            continue
        if _key(e) in seen:
            continue
        seen.add(_key(e))
        ledger["entries"].append(e)
        added += 1
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=LEDGER_KEEP_DAYS)).strftime("%Y-%m-%d")
    ledger["entries"] = sorted(
        (e for e in ledger["entries"] if str(e.get("date", "")) >= cutoff),
        key=lambda e: (str(e.get("date")), str(e.get("job"))))
    return added


def _write_ledger(ledger: dict) -> bool:
    try:
        with open(LEDGER_PATH, "w") as fh:
            json.dump(ledger, fh, indent=1, sort_keys=True)
            fh.write("\n")
        return True
    except OSError:
        return False


def record_job_run(items: int | None = None, stored: int | None = None,
                   changed: int | None = None, job: str | None = None,
                   run_id: str | None = None, truncated: str | None = None) -> dict:
    """Close out this run's ledger entry: exact metered cost + what it bought.

    Called once at the end of each LLM job. Never raises — a ledger must not
    be able to break the job it measures. It only PRINTS: the SPEND_LEDGER_V1
    line in the run log is the record, and the daily `--harvest` re-reads it
    into the committed railway/spend_jobs.json. `items` is
    what the run looked at, `stored` what it posted as new rows, `changed`
    what it edited/merged in place. None means the job did not count that —
    recorded as UNKNOWN, never guessed at zero.
    """
    entry = {
        "job": job or current_job(),
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"),
        "cost_usd": round(_run["cost_usd"], 6),
        "calls": _run["calls"],
        "prompt_tokens": _run["prompt_tokens"],
        "completion_tokens": _run["completion_tokens"],
        "items": items,
        "stored": stored,
        "changed": changed,
    }
    # A run stopped early is not a run that finished. `complete` is always
    # written, both ways, so a reader never has to infer completeness from the
    # absence of a field (an absent field means an old entry, which is UNKNOWN,
    # not a pass).
    if truncated:
        note_truncated(truncated)
    entry["truncated"] = run_truncation()
    entry["complete"] = entry["truncated"] is None
    if _run["cached_prompt_tokens"]:
        entry["cached_prompt_tokens"] = _run["cached_prompt_tokens"]
    # Per-source attribution, when the caller tagged its calls (the Railway
    # cron does). One tag means the breakdown adds nothing over the total.
    breakdown = {}
    for t, v in _by_tag.items():
        row = {k: (round(val, 6) if k == "cost_usd" else int(val))
               for k, val in v.items() if isinstance(val, (int, float))}
        breakdown[t] = row
    if len(breakdown) > 1 or any(v.get("kept") or v.get("dropped")
                                 for v in breakdown.values()):
        entry["sources"] = breakdown
    run_id = run_id or os.environ.get("GITHUB_RUN_ID")
    if run_id:
        entry["run_id"] = run_id
        entry["attempt"] = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    try:
        rows_known = stored if stored is not None else changed
        print(run_summary(rows_known))
        if entry["truncated"]:
            print(f"::warning::spend: this run is TRUNCATED, not complete — "
                  f"{entry['truncated']}. What it did not reach is deferred to "
                  f"the next run, not decided. Do not read its counts as a "
                  f"full pass over the queue.")
        print(f"{LEDGER_MARKER} {json.dumps(entry, sort_keys=True)}")
        # Deliberately NO file write here: the committed ledger has exactly
        # one writer (`--harvest`, in the balance job). A job-side write would
        # be lost on the ephemeral runner anyway, and on a dev machine or in
        # the test suite it would dirty the committed file with 'local' rows.
    except Exception as exc:  # noqa: BLE001 — meter must never break the job
        try:
            print(f"spend: could not record the job ledger entry ({exc})")
        except Exception:
            pass
    return entry


def parse_ledger_lines(text: str) -> list[dict]:
    """Pull SPEND_LEDGER_V1 entries out of raw log text. Actions prefixes
    every line with a timestamp, so match the marker anywhere in the line."""
    out = []
    for line in text.splitlines():
        idx = line.find(LEDGER_MARKER)
        if idx < 0:
            continue
        payload = line[idx + len(LEDGER_MARKER):].strip()
        try:
            e = json.loads(payload)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("job") and e.get("date"):
            out.append(e)
    return out


# How many 100-run pages `list_runs_in_window` will read before giving up and
# saying so. This repo produced 414 completed runs in a 2-day window on
# 2026-08-04, so 2 pages (the old, unpaginated behaviour) covered under seven
# hours of it. 10 pages = 1,000 runs is several times the observed volume and
# still bounded, so a runaway cannot turn the daily balance job into a
# thousand-request crawl.
HARVEST_MAX_PAGES = max(1, int(os.environ.get("ALT_HARVEST_MAX_PAGES", "10")))


def list_runs_in_window(api, repo: str, since: str) -> tuple[list[dict], bool]:
    """Every completed workflow run created since `since`, following pagination.

    Returns (runs, complete). `complete` is False when the page cap stopped us
    before the window ran out, so the caller can report the gap instead of
    quietly under-counting.

    WHY THIS IS A FUNCTION. It used to be one unpaginated call asking for
    `per_page=100`, and the GitHub API answers newest-first. Measured on
    2026-08-04: the 2-day window held 414 completed runs, so the single page
    reached back only to 13:14 that same day. The daily balance job harvests at
    13:00 UTC, so the only jobs that ever landed in railway/spend_jobs.json were
    the ones that ran in the few hours before it. Every afternoon job -- the
    expensive half of the schedule -- emitted its SPEND_LEDGER_V1 line into a
    log nobody read.

    The damage was not a missing file. It was that $0.0269 of a measured
    $0.1644 day appeared in the ledger (16%), so the tracker looked an order of
    magnitude cheaper than it was, and every attempt to explain the balance
    from the ledger came up short and got written off as unattributable.
    """
    runs: list[dict] = []
    for page in range(1, HARVEST_MAX_PAGES + 1):
        batch = (api(f"/repos/{repo}/actions/runs?created=>{since}"
                     f"&status=completed&per_page=100&page={page}")
                 or {}).get("workflow_runs") or []
        runs.extend(batch)
        if len(batch) < 100:
            return runs, True
    return runs, False


def harvest(days: int = 2) -> int:
    """Collect the last `days` of SPEND_LEDGER_V1 lines from Actions run logs
    into the committed ledger. Run by the daily balance job — the ONE
    workflow that commits — so per-job attribution costs one commit a day,
    not one per job. Exit-0 discipline belongs to the caller; this returns
    how many new entries landed, and prints what it could not do rather than
    raising: a bookkeeping harvester must never redden CI.
    """
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not (token and repo):
        print("harvest: GH_TOKEN/GITHUB_TOKEN or GITHUB_REPOSITORY missing — "
              "the per-job ledger was NOT updated this run (UNKNOWN, not a pass)")
        return 0

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D102
            return None

    _plain = urllib.request.build_opener(_NoRedirect)

    def _api(path: str, raw: bool = False):
        req = urllib.request.Request(
            f"https://api.github.com{path}",
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "User-Agent": USER_AGENT})
        try:
            with _plain.open(req, timeout=60) as resp:
                body = resp.read()
        except urllib.error.HTTPError as err:
            # The /logs endpoint answers 302 to short-lived blob storage.
            # Follow it WITHOUT the Authorization header: the blob host
            # rejects GitHub bearer tokens with a 401 (measured 2026-08-02;
            # `gh api` strips auth on redirect for the same reason).
            if err.code not in (301, 302, 303, 307, 308):
                raise
            loc = err.headers.get("Location")
            if not loc:
                raise
            with urllib.request.urlopen(
                    urllib.request.Request(loc, headers={"User-Agent": USER_AGENT}),
                    timeout=60) as resp:
                body = resp.read()
        return body.decode("utf-8", "replace") if raw else json.loads(body)

    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    wanted = set(JOB_RUN_CEILINGS_USD)
    found: list[dict] = []
    scanned = 0
    try:
        runs, complete = list_runs_in_window(_api, repo, since)
    except Exception as exc:
        print(f"harvest: could not list runs ({exc}) — ledger NOT updated")
        return 0
    if not complete:
        # The window was NOT fully read. Say so: a ledger that silently covers
        # part of the day reads exactly like a cheap day. That is the bug this
        # function shipped with (see list_runs_in_window).
        print("::warning::harvest: the run window was truncated at "
              f"{HARVEST_MAX_PAGES} pages, so the ledger for this window is "
              "INCOMPLETE (UNKNOWN, not a pass). Raise HARVEST_MAX_PAGES or "
              "harvest more often.")
    for run in runs:
        path = str(run.get("path") or "")
        job_id = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        if job_id not in wanted:
            continue
        try:
            jobs = _api(f"/repos/{repo}/actions/runs/{run['id']}/jobs").get("jobs") or []
            for j in jobs:
                text = _api(f"/repos/{repo}/actions/jobs/{j['id']}/logs", raw=True)
                found.extend(parse_ledger_lines(text))
                scanned += 1
        except Exception as exc:
            # One unreadable run must not lose the rest of the day.
            print(f"harvest: skipped run {run.get('id')} ({job_id}): {exc}")
    railway_rows = harvest_railway_runs()
    found.extend(railway_rows)
    ledger = _load_ledger()
    added = _merge_ledger_entries(ledger, found)
    if added and not _write_ledger(ledger):
        print("harvest: found entries but could not write the ledger file")
        return 0
    print(f"harvest: {scanned} job log(s) read, {len(found)} ledger line(s) "
          f"seen ({len(railway_rows)} from the Railway cron via /tracker-meta), "
          f"{added} new entr{'y' if added == 1 else 'ies'} committed-ready "
          f"in railway/spend_jobs.json")
    return added


def harvest_railway_runs() -> list[dict]:
    """Pull the Railway cron's per-run spend records out of the keyed
    /tracker-meta endpoint, as ledger entries.

    The Railway cron cannot commit and its logs are not readable from here,
    so its SPEND_LEDGER_V1 print was a record nobody could collect — the
    ledger's one structural blind spot, called out (as a blind spot, honestly)
    in unattributed_report(). cron.py now ALSO posts each run's record to
    /tracker-meta (`add_spend_run`), and this reads them back into the same
    committed ledger the Actions jobs use, so `railway-cron` gets a $/day and
    $/row row in ops_status [2a] instead of living inside a remainder.

    Fail-soft and loud: missing env or an HTTP error returns [] and says the
    railway rows are UNKNOWN this harvest — never an exception, and never
    silence."""
    site = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    wp_key = (os.environ.get("WP_API_KEY") or "").strip()
    if not (site and wp_key):
        print("harvest: WP_SITE_URL/WP_API_KEY not set — Railway cron rows NOT "
              "harvested this run (UNKNOWN, not a pass)")
        return []
    try:
        req = urllib.request.Request(
            f"{site}/wp-json/layoffs/v1/tracker-meta",
            data=json.dumps({}).encode("utf-8"),
            headers={"User-Agent": USER_AGENT,
                     "Content-Type": "application/json",
                     "X-Layoff-API-Key": wp_key},
            method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"harvest: could not read /tracker-meta ({exc}) — Railway cron "
              f"rows NOT harvested this run (UNKNOWN, not a pass)")
        return []
    out = []
    for rec in (meta.get("spend_runs") or []) if isinstance(meta, dict) else []:
        if not isinstance(rec, dict) or not rec.get("date"):
            continue
        entry = {k: rec.get(k) for k in
                 ("job", "date", "cost_usd", "calls", "prompt_tokens",
                  "completion_tokens", "cached_prompt_tokens", "items",
                  "stored", "changed", "run_id", "sources", "gate_mode",
                  "gate_false_drops", "truncated", "complete")
                 if rec.get(k) is not None}
        entry.setdefault("job", "railway-cron")
        out.append(entry)
    return out


# --------------------------------------------------------------------------
# Cost per stored row — the tracked metric
# --------------------------------------------------------------------------
#
# run_summary() answers "was THIS run expensive". It cannot answer "is this job
# getting worse", because a single run has nothing to be worse than. The ledger
# can, and until now nothing read it back.
#
# Two questions, both answered from committed data so a regression is a number
# in a diff rather than a surprise on the balance:
#   * $/row per job over a window  -- the funnel metric.
#   * BOUGHT NOTHING streaks       -- consecutive runs that spent and stored or
#                                     changed nothing. Measured 2026-08-03/04:
#                                     company-watchlist $0.0606 over 101 calls
#                                     for 0 rows, two days running.
#
# `rows` is stored + changed. A job that edits rows in place (industry-backfill,
# reason-backfill) buys something real; counting only `stored` would call it
# waste. An entry that recorded NEITHER is UNKNOWN and is excluded from the
# rate, never silently treated as zero.

def job_row_costs(ledger: dict | None = None, days: int = 14) -> dict[str, dict]:
    """Per-job {cost, rows, calls, runs, usd_per_row, barren_streak} over `days`.

    `usd_per_row` is None when the window recorded no row counts at all, which
    is UNKNOWN and must not be printed as a rate. `barren_streak` counts the most
    recent consecutive runs that cost something and bought nothing.
    """
    if ledger is None:
        ledger = _load_ledger()
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    out: dict[str, dict] = {}
    entries = [e for e in (ledger.get("entries") or [])
               if isinstance(e, dict) and str(e.get("date") or "") >= cutoff]
    for e in sorted(entries, key=lambda x: (str(x.get("date")), str(x.get("run_id") or ""))):
        job = e.get("job")
        if not job:
            continue
        agg = out.setdefault(job, {"cost": 0.0, "rows": 0, "calls": 0, "runs": 0,
                                   "rows_known": False, "barren_streak": 0})
        agg["cost"] += float(e.get("cost_usd") or 0.0)
        agg["calls"] += int(e.get("calls") or 0)
        agg["runs"] += 1
        stored, changed = e.get("stored"), e.get("changed")
        if stored is None and changed is None:
            continue  # UNKNOWN: this run did not count rows
        agg["rows_known"] = True
        rows = int(stored or 0) + int(changed or 0)
        agg["rows"] += rows
        if rows == 0 and float(e.get("cost_usd") or 0.0) > 0:
            agg["barren_streak"] += 1
        else:
            agg["barren_streak"] = 0
    for agg in out.values():
        agg["usd_per_row"] = (agg["cost"] / agg["rows"]
                              if agg["rows_known"] and agg["rows"] > 0 else None)
    return out


def row_cost_report(days: int = 14, ledger: dict | None = None) -> str:
    """Human-readable $/row table. Used by ops_status and the weekly digest."""
    stats = job_row_costs(ledger=ledger, days=days)
    if not stats:
        return (f"cost per stored row: no ledger entries in the last {days} day(s) "
                f"— UNKNOWN, not a pass")
    lines = [f"cost per stored row (last {days} day(s), from railway/spend_jobs.json):",
             f"  {'job':<28}{'runs':>5}{'calls':>8}{'cost':>10}{'rows':>7}  $/row"]
    total_cost = total_rows = 0.0
    for job in sorted(stats, key=lambda j: -stats[j]["cost"]):
        s = stats[job]
        total_cost += s["cost"]
        total_rows += s["rows"]
        if s["usd_per_row"] is None:
            if not s["rows_known"]:
                rate = "UNKNOWN (no row count)"
            elif s["cost"] <= 0:
                # Found nothing AND cost nothing. That is a job working as
                # designed (process-tips on a day with no tips), not waste.
                rate = "no spend"
            else:
                rate = "BOUGHT NOTHING"
        else:
            rate = f"${s['usd_per_row']:.4f}"
        lines.append(f"  {job:<28}{s['runs']:>5}{s['calls']:>8}"
                     f"{s['cost']:>10.4f}{s['rows']:>7}  {rate}")
        if s["barren_streak"] >= BARREN_STREAK_ALERT:
            lines.append(f"      ^ {s['barren_streak']} consecutive run(s) that spent "
                         f"and bought nothing")
    lines.append(f"  {'TOTAL':<28}{'':>5}{'':>8}{total_cost:>10.4f}{int(total_rows):>7}  "
                 + (f"${total_cost / total_rows:.4f}" if total_rows else "n/a"))
    lines.extend(unattributed_report(days=days, ledger=ledger))
    return "\n".join(lines)


BALANCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "openrouter_balance_history.json")


def unattributed_report(days: int = 14, ledger: dict | None = None) -> list[str]:
    """What the ACCOUNT lost, minus what the ledger can name.

    The ledger sees the GitHub Actions jobs (log harvest) and, since the
    funnel port, the Railway cron (harvest_railway_runs reads its per-run
    records back out of the keyed /tracker-meta endpoint). Before that read
    existed, the cron's SPEND_LEDGER_V1 line went into a Railway log nothing
    collected — a structural blind spot, and while it was unnamed the daily
    balance and the ledger simply disagreed and the difference got called
    'unattributable'.

    Naming the remainder does not attribute it. It turns 'the numbers do not
    add up' into a number that can be watched, and makes it obvious when the
    gap grows. It is a REMAINDER, never a measurement of any one job, and it is
    labelled that way wherever it prints.

    The account is shared with the sibling tracker, so this figure is an upper
    bound on what is unattributed HERE, not a statement about this repo alone.
    """
    try:
        with open(BALANCE_PATH) as fh:
            series = json.load(fh)
        series = [p for p in series if isinstance(p, dict) and p.get("balance") is not None]
        series.sort(key=lambda p: str(p.get("date")))
    except (OSError, ValueError, TypeError):
        return ["  unattributed: UNKNOWN — could not read the balance history"]
    if len(series) < 2:
        return ["  unattributed: UNKNOWN — fewer than two balance readings"]
    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    window = [p for p in series if str(p.get("date")) >= cutoff]
    if len(window) < 2:
        window = series[-2:]
    # A balance can go UP when the account is topped up. A top-up is not a
    # refund, so only count the days the balance fell.
    drop = 0.0
    for prev, cur in zip(window, window[1:]):
        delta = float(prev["balance"]) - float(cur["balance"])
        if delta > 0:
            drop += delta
    named = sum(s["cost"] for s in job_row_costs(ledger=ledger, days=days).values())
    gap = drop - named
    out = [f"  account balance fell ${drop:.4f} over {window[0]['date']}..{window[-1]['date']}; "
           f"the ledger names ${named:.4f}"]
    if drop <= 0:
        return out + ["  unattributed: UNKNOWN — the balance did not fall in this window"]
    out.append(f"  UNATTRIBUTED REMAINDER ${gap:.4f} ({100 * gap / drop:.0f}% of the fall). "
               f"This is a remainder, not a measurement of any job. It contains any "
               f"sibling-tracker spend on the same account, plus any Railway cron runs "
               f"not yet harvested from /tracker-meta (see harvest_railway_runs).")
    return out


# A job that spends and stores nothing this many runs running is reported. Not
# a failure and not an automatic throttle: some jobs (process-tips) legitimately
# find nothing most days and cost $0.00 doing it, which is why the streak only
# counts runs that actually SPENT.
BARREN_STREAK_ALERT = 3


# --------------------------------------------------------------------------
# Earned cadence
# --------------------------------------------------------------------------
#
# The funnel rule is that a source which has produced nothing in N runs earns a
# slower schedule and a productive one earns a faster one. The part that matters
# for this repo is WHICH jobs may be slowed without costing coverage.
#
# A QUEUE-DRAINING job walks a backlog and resumes where it stopped
# (industry-backfill, reason-backfill, enrich-roles, enrich-context). Running it
# less often drains the queue slower. It cannot miss anything, because the queue
# is still there next run. Slowing one is a throughput decision.
#
# A DISCOVERY job goes looking for events in the outside world
# (supplemental-news, company-watchlist, distress-watchlist, ai-evidence-sweep,
# news-catchup). Running it less often is a real chance of noticing an event
# later, or of a short-lived page being gone by the time we look. That is a
# coverage tradeoff and it is the owner's to make, not this module's.
#
# So the earned lane applies to queue-draining jobs ONLY. Discovery jobs are
# listed here so the report can name what a decision about them would buy, and
# `earned_skip` refuses to slow them whatever the ledger says.
QUEUE_DRAINING_JOBS = frozenset({
    "industry-backfill", "reason-backfill", "enrich-roles", "enrich-context",
    "reclassify-legacy-ai",
})

# A queue-draining job that bought nothing for this many consecutive PAID runs
# has an empty or nearly empty queue. It goes to the slow lane until it produces
# again, at which point the streak resets and it is back to full cadence the
# very next run.
EARNED_SLOW_AFTER_BARREN_RUNS = 5

# In the slow lane, run one day in N.
EARNED_SLOW_EVERY_N_DAYS = 3


def earned_skip(job: str | None = None, today: str | None = None,
                ledger: dict | None = None) -> tuple[bool, str]:
    """(skip, why) — should this queue-draining job sit today's run out?

    Never returns True for a discovery job, and never for a job with no ledger
    history: absence of evidence is not evidence of an empty queue.
    """
    job = job or current_job()
    if job not in QUEUE_DRAINING_JOBS:
        return False, (f"{job} is not a queue-draining job, so earned cadence "
                       f"does not apply (slowing it would be a coverage decision)")
    stats = job_row_costs(ledger=ledger).get(job)
    if not stats or stats["runs"] == 0:
        return False, f"{job} has no ledger history yet, so cadence stays as scheduled"
    streak = stats["barren_streak"]
    if streak < EARNED_SLOW_AFTER_BARREN_RUNS:
        return False, (f"{job} bought rows within the last {EARNED_SLOW_AFTER_BARREN_RUNS} "
                       f"paid run(s) (barren streak {streak}), so it keeps full cadence")
    day = today or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    ordinal = datetime.date.fromisoformat(day).toordinal()
    if ordinal % EARNED_SLOW_EVERY_N_DAYS == 0:
        return False, (f"{job} is in the slow lane (barren streak {streak}) and today "
                       f"is its 1-in-{EARNED_SLOW_EVERY_N_DAYS} run")
    return True, (f"{job} has spent and bought nothing for {streak} consecutive run(s), "
                  f"so it has earned a 1-in-{EARNED_SLOW_EVERY_N_DAYS} cadence until it "
                  f"produces again. Its queue is not lost: the next run resumes where "
                  f"this one would have started.")


# --------------------------------------------------------------------------
# Month-to-date
# --------------------------------------------------------------------------

def key_fingerprint(api_key: str) -> str:
    """A short, one-way, non-reversible label for a key. Safe to commit, safe to
    print, and it is what lets the Actions key and the Railway key each carry
    their own month-start in one committed file."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def fetch_key_state(api_key: str, timeout: int = 15) -> dict:
    """The key's live state. The timeout is short on purpose: the monthly gate
    calls this in-line before a job's first paid call, and a budget lookup must
    never be able to hang a data job. An unanswered lookup is UNKNOWN."""
    return _get_json(KEY_URL, api_key, timeout=timeout).get("data") or {}


def month_delta(lifetime_used: float, fingerprint: str) -> tuple[float | None, str, bool]:
    """(spent_this_month, month, persisted).

    `persisted` False means the snapshot could not be written, so the returned
    figure describes only the part of the month since this process started. The
    caller must then report UNKNOWN, not a pass -- an unwritable snapshot is a
    measurement we do not have, and absence of a signal is not absence of spend.
    """
    month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    try:
        with open(SNAPSHOT_PATH) as fh:
            snap = json.load(fh) or {}
    except (OSError, ValueError):
        snap = {}
    if not isinstance(snap, dict):
        snap = {}

    entry = snap.get(fingerprint)
    fresh = (not isinstance(entry, dict)
             or entry.get("month") != month
             or not isinstance(entry.get("usage_at_start"), (int, float)))

    if not fresh:
        return max(0.0, lifetime_used - float(entry["usage_at_start"])), month, True

    snap[fingerprint] = {"month": month, "usage_at_start": lifetime_used}
    try:
        with open(SNAPSHOT_PATH, "w") as fh:
            json.dump(snap, fh, indent=1, sort_keys=True)
            fh.write("\n")
    except OSError:
        # Read-only or ephemeral filesystem (Railway). Enforce on the in-memory
        # value and tell the truth about it.
        return 0.0, month, False
    return 0.0, month, True


# --------------------------------------------------------------------------
# The monthly cap, as a STOP rather than a report
# --------------------------------------------------------------------------
#
# The $10/month hard cap used to reach a job only through ALT_PAID_READS, which
# `spend.py --degrade` writes to $GITHUB_ENV in a step before the job. That is a
# real mechanism and it stays, but it has three holes: it needs that step to
# have run, it needs the $GITHUB_ENV write to have succeeded (the failure is
# caught and printed, then the job spends as normal), and it cannot cover a
# process the step does not precede -- which is the Railway cron, the single
# largest consumer.
#
# So the job also asks, itself, once per process, through the same
# `paid_reads_enabled()` every paid call site in this repo already calls. One
# place knows month-to-date against the allowance.
#
# THE READ IS NON-MUTATING, ON PURPOSE. `month_delta()` ARMS a baseline when it
# finds none and returns 0.0 as a persisted figure. On an ephemeral runner that
# write is discarded, so a lost or not-yet-committed snapshot would make every
# job of the day read "$0.00 spent this month" -- a confident zero derived from
# no evidence, which is precisely the shape of bug this file exists to refuse.
# The gate therefore READS the committed snapshot only. No snapshot for this
# month means month-to-date is UNKNOWN here, and UNKNOWN is reported as UNKNOWN.
#
# UNKNOWN DOES NOT HALT. Halting every collector because a bookkeeping file
# could not be read would take the free 95% of this pipeline down to protect a
# budget it does not spend -- the self-inflicted outage the module docstring
# describes. Under UNKNOWN the per-run ceiling is what enforces, and the fact
# that the month was not measured is printed and recorded.
_month_gate: tuple[bool, str] | None = None


def reset_month_gate() -> None:
    """Test-only: forget this process's cached monthly verdict."""
    global _month_gate
    _month_gate = None


def month_to_date_usd(api_key: str) -> tuple[float | None, str, str]:
    """(spent_this_month, month, basis) WITHOUT arming anything.

    basis is one of:
      "measured"  -- a committed month-start exists for this key and month
      "no-baseline" -- none exists here, so month-to-date is UNKNOWN
      "unreadable"  -- the snapshot file could not be read/parsed
    """
    month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    try:
        with open(SNAPSHOT_PATH) as fh:
            snap = json.load(fh) or {}
    except OSError:
        return None, month, "no-baseline"
    except ValueError:
        return None, month, "unreadable"
    if not isinstance(snap, dict):
        return None, month, "unreadable"
    entry = snap.get(key_fingerprint(api_key))
    if (not isinstance(entry, dict) or entry.get("month") != month
            or not isinstance(entry.get("usage_at_start"), (int, float))):
        return None, month, "no-baseline"
    try:
        # Short timeout on purpose: this runs once, in-line, before the first
        # paid call of a job. A budget lookup must not be able to hang a data
        # job -- an unanswered lookup is UNKNOWN, and UNKNOWN keeps the free
        # collectors running under the per-run ceiling.
        used = float(fetch_key_state(api_key).get("usage") or 0)
    except Exception as exc:  # network, proxy block, schema change
        return None, month, f"unreadable ({exc})"
    return max(0.0, used - float(entry["usage_at_start"])), month, "measured"


def month_gate() -> tuple[bool, str]:
    """(blocked, why) — is the month's budget spent? Cached per process.

    `blocked` True means no further PAID call may be made in this process. It is
    only ever True on a MEASURED figure: an unmeasurable month is UNKNOWN and
    says so in `why`.
    """
    global _month_gate
    if _month_gate is None:
        try:
            _month_gate = _evaluate_month_gate()
        except Exception as exc:  # noqa: BLE001 — a guard must not break the job
            _month_gate = (False, f"month-to-date is UNKNOWN — the monthly gate "
                                  f"could not run ({exc}). Not a pass; the "
                                  f"per-run ceiling is what is enforcing.")
    return _month_gate


def _evaluate_month_gate() -> tuple[bool, str]:
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return False, ("month-to-date is UNKNOWN — no OPENROUTER_API_KEY in this "
                       "runtime, so nothing about the month could be measured. "
                       "Not a pass.")
    spent, month, basis = month_to_date_usd(key)
    if spent is None:
        return False, (f"month-to-date for {month} is UNKNOWN ({basis}: no "
                       f"committed month-start for this key here). Not a pass; "
                       f"the per-run ceiling is what is enforcing.")
    stop_at = MONTHLY_ALLOWANCE_USD * STOP_AT_FRACTION
    if spent >= stop_at:
        msg = (f"the ${MONTHLY_ALLOWANCE_USD:.2f} monthly cap is spent: "
               f"${spent:.4f} used in {month}, at or past the "
               f"{int(STOP_AT_FRACTION * 100)}% stop line (${stop_at:.2f}). "
               f"Paid reads are OFF for the rest of {month}. Every free "
               f"collector keeps running; deferred candidates are UNMARKED and "
               f"are read on a later run.")
        print(f"::warning::spend: {msg}")
        return True, msg
    return False, (f"${spent:.4f} of ${MONTHLY_ALLOWANCE_USD:.2f} spent in "
                   f"{month} (measured)")


# --------------------------------------------------------------------------
# Degrade / report
# --------------------------------------------------------------------------

def degrade(over: bool) -> None:
    """Switch paid reads off for the rest of the job, and say so.

    Sets the variable in this process (so an in-process caller such as cron.py
    is covered) and appends it to $GITHUB_ENV (so later steps of the same
    Actions job are covered).
    """
    if not over:
        print("\n  Paid reads: ON. Within the allowance.")
        return

    os.environ[PAID_READS_ENV] = "off"
    print("\n  DEGRADED: paid reads are OFF.")
    print("  WARN, SEC/EDGAR structured fields, ERM, every state scraper, the")
    print("  seen-URL pre-check and all server-side dedup keep running: none of")
    print("  them call a model. Candidates that would have cost money defer")
    print("  UNMARKED, so a later run reads them. This costs depth for the rest")
    print("  of the month, never coverage.")

    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        return
    try:
        with open(github_env, "a") as fh:
            fh.write(f"{PAID_READS_ENV}=off\n")
    except OSError as exc:
        # Loud, and still exit 0. A job that could not write the flag spends as
        # before, which is the old behaviour and the safe direction to fail: the
        # per-run ceiling and the key's own hard cap are still underneath it.
        print(f"  COULD NOT SET {PAID_READS_ENV} for later steps: {exc} — those "
              f"steps will spend as normal; the per-run ceiling still applies")


def apply_job_ceiling() -> None:
    """Give the steps after the guard THIS job's named per-run ceiling.

    Looks the job up in JOB_RUN_CEILINGS_USD and writes ALT_RUN_CEILING_USD to
    GITHUB_ENV (and this process) so the job step's own import of spend.py
    enforces it via the existing state-free brake. An explicit
    ALT_RUN_CEILING_USD already in the environment wins — an operator
    override must not be silently re-tightened. Jobs not in the table keep
    the global default, which is how the Railway cron stays untouched.

    Since 2026-08-11 this is a CONVENIENCE, not the enforcement path: the job's
    own process resolves the same table through `effective_run_ceiling_usd()`,
    so the named ceiling binds whether or not this step ran or its $GITHUB_ENV
    write succeeded. Exporting it keeps the number visible in the step log and
    in `env` for anything that reads it directly.
    """
    job = current_job()
    ceiling = JOB_RUN_CEILINGS_USD.get(job)
    if ceiling is None:
        print(f"  per-job ceiling: none named for '{job}' — global "
              f"${RUN_CEILING_USD:.2f} default applies")
        return
    if os.environ.get("ALT_RUN_CEILING_USD"):
        print(f"  per-job ceiling: ALT_RUN_CEILING_USD already set "
              f"(${float(os.environ['ALT_RUN_CEILING_USD']):.3f}) — override kept, "
              f"table value ${ceiling:.3f} for '{job}' not applied")
        return
    os.environ["ALT_RUN_CEILING_USD"] = str(ceiling)
    print(f"  per-job ceiling: '{job}' gets ${ceiling:.3f} this run "
          f"(railway/spend.py JOB_RUN_CEILINGS_USD); at the ceiling the job "
          f"degrades and resumes next run, it does not halt")
    github_env = os.environ.get("GITHUB_ENV")
    if not github_env:
        return
    try:
        with open(github_env, "a") as fh:
            fh.write(f"ALT_RUN_CEILING_USD={ceiling}\n")
    except OSError as exc:
        print(f"  COULD NOT SET ALT_RUN_CEILING_USD for later steps: {exc} — "
              f"the global ${RUN_CEILING_USD:.2f} default still applies there")


def main() -> int:
    parser = argparse.ArgumentParser(description="Report and enforce LLM spend.")
    parser.add_argument("--enforce", action="store_true",
                        help="exit non-zero when the allowance is exhausted")
    parser.add_argument("--degrade", action="store_true",
                        help="always exit 0; switch paid reads off when over the "
                             "allowance, leaving the free collectors running")
    parser.add_argument("--harvest", action="store_true",
                        help="collect SPEND_LEDGER_V1 lines from recent Actions "
                             "run logs into railway/spend_jobs.json; always exit 0")
    parser.add_argument("--rows", action="store_true",
                        help="print cost per stored row per job from the committed "
                             "ledger; always exit 0")
    parser.add_argument("--cadence", action="store_true",
                        help="print whether this job has earned a slower cadence "
                             "(queue-draining jobs only); always exit 0")
    args = parser.parse_args()

    if args.harvest:
        harvest()
        print()
        print(row_cost_report())
        return 0  # bookkeeping must never redden CI; failures printed above

    if args.rows:
        print(row_cost_report())
        return 0

    if args.cadence:
        skip, why = earned_skip()
        print(f"earned cadence: {why}")
        # A cadence decision is data for the workflow step that follows, never
        # an exit code: a job must not go red for being thrifty.
        github_out = os.environ.get("GITHUB_OUTPUT")
        if github_out:
            try:
                with open(github_out, "a") as fh:
                    fh.write(f"skip={'true' if skip else 'false'}\n")
            except OSError as exc:
                print(f"  could not write the cadence output ({exc}); the job runs "
                      f"as scheduled, which is the safe direction")
        return 0

    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    print("=" * 60)
    print("LLM SPEND")
    print("=" * 60)

    if not key:
        # UNKNOWN, not a pass. Say so and do not degrade on no evidence.
        print("  UNKNOWN: OPENROUTER_API_KEY is not set in this runtime, so")
        print("  nothing about spend could be measured here. This is not a")
        print("  statement that spend is within budget.")
        print(f"  monthly allowance   ${MONTHLY_ALLOWANCE_USD:,.2f} (policy, in railway/spend.py)")
        if args.degrade:
            apply_job_ceiling()  # the per-run brake needs no key
        return 0 if args.degrade else (1 if args.enforce else 0)

    try:
        d = fetch_key_state(key)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  UNKNOWN: could not read OpenRouter key state ({exc}).")
        print("  Spend was NOT measured. Treat this as unchecked, not as clear.")
        if args.degrade:
            apply_job_ceiling()  # the per-run brake needs no key
        # A monitoring job must not redden CI over its own bookkeeping.
        return 0

    used = float(d.get("usage") or 0)
    limit = d.get("limit")
    remaining = (float(limit) - used) if limit is not None else None
    fp = key_fingerprint(key)
    spent_this_month, month, persisted = month_delta(used, fp)

    print(f"  key                 …{fp}  (fingerprint, not the key)")
    print(f"  spent on this key   ${used:,.4f} (lifetime)")
    if persisted:
        print(f"  spent in {month}     ${spent_this_month:,.4f}")
    else:
        print(f"  spent in {month}     UNKNOWN — the month-start snapshot could not")
        print("                      be written here (read-only/ephemeral runtime),")
        print("                      so only the per-run ceiling is enforcing.")
    if limit is None:
        print("  key limit           none set  <- a runaway run has no backstop")
    else:
        print(f"  key limit           ${float(limit):,.2f}")
        print(f"  remaining on key    ${remaining:,.4f}")
    print(f"  monthly allowance   ${MONTHLY_ALLOWANCE_USD:,.2f} (policy, in railway/spend.py)")
    print(f"  per-run ceiling     ${RUN_CEILING_USD:,.2f}")

    problems = []
    if limit is None:
        problems.append("no hard cap on this key — set one in the OpenRouter dashboard")
    elif remaining is not None and remaining <= 0:
        problems.append("key limit reached: paid calls will fail with 402")
    elif remaining is not None and remaining < 1:
        problems.append(f"under $1 left on this key (${remaining:.2f})")

    over = persisted and spent_this_month >= MONTHLY_ALLOWANCE_USD * STOP_AT_FRACTION
    if over:
        problems.append(
            f"this month's spend ${spent_this_month:.2f} is at or past "
            f"{int(STOP_AT_FRACTION * 100)}% of the ${MONTHLY_ALLOWANCE_USD:.0f} allowance")
    if not persisted:
        problems.append(
            "month-to-date is UNKNOWN in this runtime — do not read this run as "
            "proof the month is within budget")

    print()
    for p in problems:
        print(f"  ACTION NEEDED: {p}")
    if not problems:
        print("  Within budget.")

    # Degradation first: when both flags are given the softer one wins, so a
    # workflow that gains --degrade without losing --enforce cannot go red by
    # accident.
    if args.degrade:
        degrade(over)
        apply_job_ceiling()
        return 0
    if args.enforce and over:
        print("\nSTOPPING: spend ceiling reached. Paid collection will not run.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
