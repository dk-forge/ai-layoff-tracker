"""Dry-run planner and PRICE for the dormant local-language news collector.

This is the instrument that answers the only question that decides whether the
collector is ever armed: what would it cost per day, per country.

It fetches the Google News editions exactly as production would, runs the REAL
production filter (sources.local_news.relevance, the real aggregator rule, the
real raw-dict builder), and then STOPS. No LLM call is made, nothing is posted,
no row is written. What it reports is:

    editions   reachable / unreachable  (a missing edition is a FINDING, not a
               failure -- several of these markets may have no national Google
               News edition at all, and that is the diagnosis for them)
    fetched    RSS items the queries returned
    agg        excluded as a compiled layoff tally rather than reporting
    dropped    no country evidence -> never allowed to cost anything
    kept       candidates that WOULD reach the gate and the extractor
    $/day      kept * runs-per-day * measured cost per candidate

COST BASIS. The per-candidate figure is measured from this repo's own committed
spend ledger, not guessed: railway/spend_jobs.json / the per-source breakdown
report google_news's real dollars, LLM calls and items over the trailing window.
Every candidate pays for a gate call, and the fraction that the gate passes also
pays for an extraction call. Pass --cost-per-item to override with a figure you
have measured yourself; the default is printed with its provenance so a reader
can see which number is doing the work.

USAGE

    # price everything, no network writes, nothing armed
    python3 railway/local_news_dryrun.py --all

    # one market, verbose, showing what survived and why
    python3 railway/local_news_dryrun.py --countries Switzerland --show 10

    # plan only, no network at all (proves the table parses and the filter runs)
    python3 railway/local_news_dryrun.py --all --offline

Arming is a SEPARATE, deliberate act and this script never performs it. See
railway/local_news_ingest.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sources import local_news as ln            # noqa: E402
from sources import local_news_markets as mk    # noqa: E402

RUNS_PER_DAY = 2      # matches the twice-daily cadence of the news path

# Fallback used only when the ledger cannot be read; the real default is
# measured in _measured_cost_per_item() below.
FALLBACK_COST_PER_ITEM = 0.000315


def _measured_cost_per_item():
    """(cost, provenance) per candidate that reaches the LLM stages.

    Read from the repo's own committed spend ledger so the price quoted here is
    this project's measured cost, not a list price.
    """
    ledger = Path(__file__).resolve().parent / "spend_jobs.json"
    try:
        data = json.loads(ledger.read_text())
    except Exception as exc:
        return FALLBACK_COST_PER_ITEM, f"fallback (could not read spend_jobs.json: {exc})"
    best = None
    for entry in _iter_entries(data):
        by_source = entry.get("by_source") or entry.get("sources") or {}
        row = by_source.get("google_news") if isinstance(by_source, dict) else None
        if not isinstance(row, dict):
            continue
        cost = _num(row.get("cost") or row.get("usd") or row.get("dollars"))
        items = _num(row.get("items") or row.get("candidates"))
        if cost and items:
            best = (cost, items)
    if best:
        cost, items = best
        return cost / items, (f"measured from spend_jobs.json google_news "
                              f"(${cost:.4f} over {int(items)} candidates)")
    return FALLBACK_COST_PER_ITEM, ("fallback: no google_news per-source breakdown in "
                                    "spend_jobs.json; ops_status [2a] is the live figure")


def _iter_entries(data):
    if isinstance(data, list):
        for e in data:
            if isinstance(e, dict):
                yield e
    elif isinstance(data, dict):
        for v in data.values():
            if isinstance(v, dict):
                yield v
            elif isinstance(v, list):
                for e in v:
                    if isinstance(e, dict):
                        yield e


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _fetch(url):
    req = urllib.request.Request(url, headers=ln.UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:                       # noqa: BLE001
        raise RuntimeError(f"{type(e).__name__}: {e}") from e


def run(countries, show=0, offline=False, cost_per_item=None, runs_per_day=RUNS_PER_DAY):
    basis = "supplied on the command line"
    if cost_per_item is None:
        cost_per_item, basis = _measured_cost_per_item()

    print(f"cost basis: ${cost_per_item:.6f} per candidate reaching the LLM "
          f"stages -- {basis}")
    print(f"cadence:    {runs_per_day} run(s)/day\n")

    if offline:
        print("OFFLINE plan (no network). Editions and query counts only.\n")
        print(f"{'country':<22}{'tier':>5}{'editions':>10}{'queries':>9}"
              f"{'anchors':>9}{'publishers':>12}")
        for c in countries:
            m = mk.BY_COUNTRY[c]
            print(f"{c:<22}{m.tier:>5}{len(m.editions):>10}"
                  f"{sum(len(e.queries) for e in m.editions):>9}"
                  f"{len(m.anchors):>9}{len(m.publishers):>12}")
        return 0

    print(f"{'country':<22}{'ed ok':>7}{'fetch':>7}{'agg':>5}{'drop':>6}"
          f"{'kept':>6}{'$/day':>9}{'$/mo':>8}")
    print("-" * 70)
    total_day = 0.0
    per_country = {}
    for c in countries:
        rows, stats = ln.pull_local_news(countries=[c], fetch=_fetch)
        st = stats[c]
        m = mk.BY_COUNTRY[c]
        planned = sum(len(e.queries) for e in m.editions)
        ed_ok = planned - st["errors"]
        day = st["kept"] * runs_per_day * cost_per_item
        total_day += day
        per_country[c] = {"kept": st["kept"], "fetched": st["fetched"],
                          "dropped": st["dropped"], "aggregator": st["aggregator"],
                          "errors": st["errors"], "day": day,
                          "queries": planned, "tier": m.tier}
        print(f"{c:<22}{ed_ok:>4}/{planned:<2}{st['fetched']:>7}"
              f"{st['aggregator']:>5}{st['dropped']:>6}{st['kept']:>6}"
              f"{day:>9.4f}{day * 30:>8.2f}")
        if show:
            for r in rows[:show]:
                print(f"      [{r.get('_why','')}] {r['raw_text'][:96]}")
    print("-" * 70)
    print(f"{'TOTAL':<22}{'':>7}{'':>7}{'':>5}{'':>6}"
          f"{sum(v['kept'] for v in per_country.values()):>6}"
          f"{total_day:>9.4f}{total_day * 30:>8.2f}")

    print("\nUNREACHABLE / EMPTY EDITIONS (a diagnosis, not a failure):")
    none_found = True
    for c, v in per_country.items():
        if v["errors"] or v["fetched"] == 0:
            none_found = False
            why = (f"{v['errors']} query error(s)" if v["errors"]
                   else "edition answered but returned no items")
            print(f"  {c:<22} {why}")
    if none_found:
        print("  none -- every planned query reached an edition and it answered")

    # NOT "candidates per dollar": cost is exactly proportional to candidates
    # kept, so that ratio is the same constant for every country and ranks
    # nothing. The honest discriminator available WITHOUT arming is FILTER
    # PRECISION -- what share of everything the market's own queries returned
    # actually looked like that market's news. A market whose queries return
    # 400 items of which 14 are local is buying mostly noise; one returning 300
    # of which 256 are local is buying mostly signal.
    #
    # This is a PROXY, not a yield. True yield is stored rows per dollar and
    # cannot be measured until something is armed, because only the extractor
    # decides whether a candidate is a real event. Do not quote it as a hit rate.
    print("\nFILTER PRECISION (share of returned items that looked local).")
    print("A PROXY for quality, not a measured yield: stored rows per dollar")
    print("cannot be known until a market is armed.\n")
    print(f"  {'country':<22}{'kept':>6}{'fetched':>9}{'precision':>11}{'$/day':>9}")
    ranked = sorted(per_country.items(),
                    key=lambda kv: -((kv[1]["kept"] / kv[1]["fetched"])
                                     if kv[1]["fetched"] else 0))
    for c, v in ranked:
        prec = (v["kept"] / v["fetched"]) if v["fetched"] else 0.0
        print(f"  {c:<22}{v['kept']:>6}{v['fetched']:>9}{prec:>10.0%}{v['day']:>9.4f}")

    print("\nZERO-YIELD MARKETS (queries answered, nothing looked local):")
    zeros = [c for c, v in per_country.items() if v["fetched"] and not v["kept"]]
    for c in zeros:
        print(f"  {c:<22} {per_country[c]['fetched']} items returned, 0 local")
    if not zeros:
        print("  none")

    print("\nNOTHING WAS ARMED, no LLM call was made, no row was written.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--countries", default="",
                    help="comma-separated country names; default is --all")
    ap.add_argument("--all", action="store_true", help="every market in the table")
    ap.add_argument("--tier", type=int, default=0, help="only this tier")
    ap.add_argument("--show", type=int, default=0,
                    help="print N surviving candidates per country")
    ap.add_argument("--offline", action="store_true",
                    help="plan only; make no network request at all")
    ap.add_argument("--cost-per-item", type=float, default=None,
                    help="override the measured per-candidate cost, in dollars")
    ap.add_argument("--runs-per-day", type=int, default=RUNS_PER_DAY)
    args = ap.parse_args(argv)

    if args.countries:
        wanted, unknown = [], []
        for n in args.countries.split(","):
            n = n.strip()
            if not n:
                continue
            hit = next((c for c in mk.COUNTRIES if c.lower() == n.lower()), None)
            (wanted if hit else unknown).append(hit or n)
        if unknown:
            print(f"unknown country/countries: {unknown}", file=sys.stderr)
            return 2
    elif args.tier:
        wanted = [m.country for m in mk.MARKETS if m.tier == args.tier]
    elif args.all:
        wanted = list(mk.COUNTRIES)
    else:
        print("give --all, --tier N or --countries A,B", file=sys.stderr)
        return 2
    return run(wanted, show=args.show, offline=args.offline,
               cost_per_item=args.cost_per_item, runs_per_day=args.runs_per_day)


if __name__ == "__main__":
    raise SystemExit(main())
