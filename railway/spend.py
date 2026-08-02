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
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    except (TypeError, ValueError):
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Report and enforce LLM spend.")
    parser.add_argument("--enforce", action="store_true",
                        help="exit non-zero when the allowance is exhausted")
    parser.add_argument("--degrade", action="store_true",
                        help="always exit 0; switch paid reads off when over the "
                             "allowance, leaving the free collectors running")
    args = parser.parse_args()

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
        return 0 if args.degrade else (1 if args.enforce else 0)

    try:
        d = fetch_key_state(key)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"  UNKNOWN: could not read OpenRouter key state ({exc}).")
        print("  Spend was NOT measured. Treat this as unchecked, not as clear.")
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
        return 0
    if args.enforce and over:
        print("\nSTOPPING: spend ceiling reached. Paid collection will not run.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
