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
# INTERIM. $10/month is the owner's current interim number for the sibling
# tracker, adopted here unchanged until told otherwise. It is not yet a measured
# statement about what full coverage costs on this tracker; it is a ceiling low
# enough that the 2026-07-28..08-02 burn ($6.45-$7.00/day, i.e. ~$200/month)
# could not have happened under it.
MONTHLY_ALLOWANCE_USD = 10.0

# Stop with headroom left, so a long batch cannot overshoot mid-run.
STOP_AT_FRACTION = 0.9

# Per-run ceiling: the backstop that works without durable state (see the module
# docstring). 2% of the allowance. The measured Railway cron run costs ~$0.09,
# so this is ~2x headroom on a normal run, and it caps the 2x/day cron at
# ~$12/month even in the total absence of a month-to-date reading.
RUN_CEILING_USD = float(os.environ.get("ALT_RUN_CEILING_USD",
                                       MONTHLY_ALLOWANCE_USD * 0.02))

# The environment variable a degraded run sets. Read by extractor.py, which is
# the only module in this repo that can spend.
PAID_READS_ENV = "ALT_PAID_READS"

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
# So the ceilings below are set to make the $10 INTERIM allowance hold:
# ingest $5.1 MEASURED + small jobs capped at ~$0.175/day of dailies
# (~$5.25/month worst case) + ~$1.1/month of weekly/monthly jobs. The three
# jobs whose modelled appetite exceeds their share — industry-backfill,
# company-watchlist, supplemental-news — run THROTTLED against it: each
# already resumes where it stopped, so a ceiling slows the queue drain, it
# never loses coverage. That is a stated throttle, not a silent cut.
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
}
_DEFAULT_PRICE = (0.0000010, 0.0000030)  # unknown model: assume dearer than DeepSeek

_price_cache: dict[str, tuple[float, float]] = {}
_prices_fetched = False

# The current process's exact meter.
_run = {"cost_usd": 0.0, "calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
_run_ceiling_tripped = False


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
        else:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0
    p_rate, c_rate = price_for(model)
    cost = prompt_tokens * p_rate + completion_tokens * c_rate
    _run["cost_usd"] += cost
    _run["calls"] += 1
    _run["prompt_tokens"] += prompt_tokens
    _run["completion_tokens"] += completion_tokens
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

def paid_reads_enabled() -> bool:
    """False when paid model calls must not be made right now.

    Two independent reasons, either sufficient:
      * ALT_PAID_READS=off  -- a `--degrade` step decided the month is spent.
      * this process has already spent RUN_CEILING_USD -- the state-free brake.

    Checked by extractor.py at the top of every paid function.
    """
    global _run_ceiling_tripped
    if (os.environ.get(PAID_READS_ENV, "").strip().lower() == "off"):
        return False
    if _run["cost_usd"] >= RUN_CEILING_USD:
        if not _run_ceiling_tripped:
            _run_ceiling_tripped = True
            print(f"::warning::spend: this run has spent ${_run['cost_usd']:.4f}, "
                  f"at or past the ${RUN_CEILING_USD:.2f} per-run ceiling. Paid "
                  f"extraction is OFF for the rest of this run. Free ingest "
                  f"continues; deferred candidates are unmarked and return on a "
                  f"later run.")
        return False
    return True


def reset_run_meter() -> None:
    """Test-only: clear the process meter."""
    global _run_ceiling_tripped
    _run.update({"cost_usd": 0.0, "calls": 0, "prompt_tokens": 0,
                 "completion_tokens": 0})
    _run_ceiling_tripped = False


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
                   changed: int | None = None, job: str | None = None) -> dict:
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
    run_id = os.environ.get("GITHUB_RUN_ID")
    if run_id:
        entry["run_id"] = run_id
        entry["attempt"] = os.environ.get("GITHUB_RUN_ATTEMPT") or "1"
    try:
        rows_known = stored if stored is not None else changed
        print(run_summary(rows_known))
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
        runs = _api(f"/repos/{repo}/actions/runs?created=>{since}"
                    f"&status=completed&per_page=100").get("workflow_runs") or []
    except Exception as exc:
        print(f"harvest: could not list runs ({exc}) — ledger NOT updated")
        return 0
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
    ledger = _load_ledger()
    added = _merge_ledger_entries(ledger, found)
    if added and not _write_ledger(ledger):
        print("harvest: found entries but could not write the ledger file")
        return 0
    print(f"harvest: {scanned} job log(s) read, {len(found)} ledger line(s) "
          f"seen, {added} new entr{'y' if added == 1 else 'ies'} committed-ready "
          f"in railway/spend_jobs.json")
    return added


# --------------------------------------------------------------------------
# Month-to-date
# --------------------------------------------------------------------------

def key_fingerprint(api_key: str) -> str:
    """A short, one-way, non-reversible label for a key. Safe to commit, safe to
    print, and it is what lets the Actions key and the Railway key each carry
    their own month-start in one committed file."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]


def fetch_key_state(api_key: str) -> dict:
    return _get_json(KEY_URL, api_key).get("data") or {}


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
    args = parser.parse_args()

    if args.harvest:
        harvest()
        return 0  # bookkeeping must never redden CI; failures printed above

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
