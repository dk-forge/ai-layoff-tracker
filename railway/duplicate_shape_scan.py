#!/usr/bin/env python3
"""A SECOND duplicate detector that reads no company name at all.

WHY A SECOND ONE EXISTS
-----------------------
Every defence the tracker had against a double-counted headline sat inside
`dedupe_llm.candidate_clusters`: the exact-hash gate, the same-company window,
the pair-window widening, the model adjudication. All of them are downstream of
BUCKETING, and bucketing is a company-name key. A pair that never becomes a
candidate is never compared, never judged, never logged and never counted, at
zero cost, forever. Three ways that happened, all found live on 2026-09-09:

  * NAME VARIANTS. "Volkswagen", "Volkswagen (VW)" and "Grupo Volkswagen" made
    three buckets, so a 50,000-job event reported twice was never proposed as a
    pair. `bucket_key()` was widened the same day and now collapses those.
  * DATELESS ROWS. `dedupe_llm.days_between` returns 9999 for a blank
    `layoff_date`, and every window gate compares against a day count, so a row
    with no date can NEVER cluster with anything, whatever its name and however
    wide the bucket. Row 176988 (Grupo Volkswagen, 60,000, no date) is live in
    the headline and is structurally unreachable by that path.
  * THE MOVEMENT GUARD. `data_integrity`'s headline movement invariant reasons
    about NET entry count, so a repair of eight rows plus six arrivals reads as
    "-2 entries" and sizes its allowance from that. It fires on the repair, not
    on the damage.

A guard that shares its target's blind spot is worthless (docs/TECHLOG.md, and
the iron rule that came out of 2026-09-02). So this asks a DIFFERENT QUESTION,
and it must never be folded back into the dedup job.

THE KEY, AND WHY IT CANNOT FAIL THE WAY NAME BUCKETING FAILED
--------------------------------------------------------------
    (country compatibility, job_count within COUNT_RATIO, date gap <= WINDOW)

There is no company string in it. Not normalised, not bucketed, not compared.
The three fields it reads are exactly the three the published headline sums
over, so a spelling, a typo, an acronym, a parent/subsidiary label, a
translation or a ticker cannot remove a pair from consideration -- there is
nothing for a name to be wrong IN. The name is carried into the OUTPUT only,
where a human reads it to adjudicate; it is never an input to membership.
That is the whole point: `bucket_key` fails when two rows for one event are
SPELLED differently, and this key fails only when two rows for one event carry
different NUMBERS, which is a disjoint failure mode. On the live corpus it
immediately surfaces pairs no name key can ever reach: "Golman Sachs" against
"Goldman Sachs" (a typo, 3,200, same day), "LAUSD" against "Los Angeles
Unified School District", "JLR" against "Tata Motors' JLR", "IBM" against
"International Business Machines".

IT REPORTS. IT NEVER MERGES.
No /merge-events, no /bulk-purge, no /add, no write of any kind. The output is
a worklist and every finding is UNKNOWN pending the owner's adjudication -- a
suspected duplicate is not a proven one, and two genuinely distinct 5,000-job
rounds in one country in one month are an ordinary false positive here. This
module has no API key path and no model call; it costs $0.00 per run.

THE SWEEP IS PACED AND SMALL.
Parallel page walks of /query once tripped the host's bot challenge and blocked
this machine's IP for hours. So: one request at a time, PAGE_PAUSE seconds
apart, TOP_ROWS/200 requests total, and the sweep ABORTS at the first response
that is not decodable JSON rather than retrying into a wall.

WHY THE TOP N BY job_count. The headline is a sum, so a duplicate's damage is
its job_count. The 1,000 largest rows carry the overwhelming majority of the
overstatement risk, and scanning them is 5 requests rather than 330. A
duplicate below the floor is invisible to this module, and that is stated in
its own output rather than left to be assumed.

    python3 railway/duplicate_shape_scan.py            # full worklist
    python3 railway/duplicate_shape_scan.py --top 2000 # deeper, slower sweep
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import date

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1"
# ModSecurity blocks `python-requests`; this is the project's required agent.
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: How many of the largest rows to read. 5 pages at the server's 200 cap.
TOP_ROWS = 1000
PER_PAGE = 200
#: Seconds between page requests. One sweep at a time, never in parallel.
PAGE_PAUSE = 1.5

#: Two counts this close are the same NUMBER differently rounded or differently
#: sourced, not two plans. Measured on the live top-1,000: 0.98 yields 67 dated
#: suspects, 0.95 yields 486 and drowns the real ones.
COUNT_RATIO = 0.98
#: Day gap at which two near-identical counts stop being one re-reported event.
#: Deliberately far TIGHTER than dedupe_llm's windows (120/365/1095 days), and
#: for the opposite reason: dedupe_llm has a company name pinning identity and
#: can afford three years, this has only the numbers and would report the whole
#: corpus at that width. 30 days holds every re-report cycle the live data
#: shows (a wire story, its follow-ups, the 8-K and the ERM record) while the
#: count of suspects stays a worklist a human can finish.
WINDOW_DAYS = 30

#: A country value that identifies nothing, so it is compatible with anything.
#: Same set dedupe_llm.pair_can_be_same_event uses, for the same reason.
UNKNOWN_COUNTRIES = {"", "unknown", "multiple countries", "world", "worldwide"}

#: Federal RIF rows are agency-month AGGREGATES: two rows for one agency are
#: distinct observations by construction, never a re-report.
EXCLUDED_SOURCE_TYPES = {"federal_rif"}

#: A WARN-against-WARN pair is not a finding. Companies legally file several
#: notices for one action, and the iron rule exempts WARN from fuzzy dedup. A
#: WARN row against a NEWS or 8-K row IS kept: that is the superset case.
WARN = "warn"

#: Neighbour band for a dateless row. Wider than COUNT_RATIO because a dateless
#: row has no second axis to be checked on, so the hint list is deliberately
#: generous -- it is an adjudication aid, not a verdict. 0.75 matches the
#: job-count ratio dedupe_llm itself requires before a pair may be judged.
DATELESS_NEIGHBOUR_RATIO = 0.75
MAX_NEIGHBOURS = 5

#: Below this share of dated rows, a source_type is treated as one that simply
#: does not carry dates (Eurofound ERM's historical records are ~70% dateless),
#: and its dateless rows are reported as a BULK COUNT rather than as individual
#: anomalies. Above it, every dateless row is an anomaly and goes on the queue.
#: The rates are DERIVED from the scanned rows and printed, never hardcoded --
#: a source_type that starts or stops carrying dates moves itself.
DATE_BEARING_MIN_SHARE = 0.5
#: Too few rows to fit a rate. Report them individually: over-reporting a
#: handful is honest, calling them systemic on no evidence is not.
DATE_BEARING_MIN_ROWS = 20


class SweepAborted(Exception):
    """The host stopped answering with data. Not a finding, not a pass."""


# ---------------------------------------------------------------------------
# reading


def _http_fetch(params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(
        f"{BASE}/query?{query}",
        headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError as exc:
        # An HTML body where JSON was asked for is a bot challenge or an error
        # page. Stop the sweep here rather than walking into it.
        raise SweepAborted(f"non-JSON response from /query ({exc})") from exc


def fetch_top_rows(fetch=None, top=TOP_ROWS, per_page=PER_PAGE, pause=PAGE_PAUSE):
    """The `top` largest rows the HEADLINE COUNTS, newest-largest first.

    `exclude_supersets=1` is deliberate: /aggregate sums `superset_of = 0`, so
    scanning anything else would report rows the headline never counted. The
    detector reads the same population the number it protects is made of.

    Returns (rows, complete). `complete` is False when the sweep stopped short
    of `top` rows with more available -- that is reduced coverage, reported as
    such, never silently treated as "nothing found down there".
    """
    fetch = fetch or _http_fetch
    rows, page, total = [], 1, 0
    while len(rows) < top:
        payload = fetch({"sort": "job_count", "dir": "desc",
                         "per_page": per_page, "page": page,
                         "exclude_supersets": 1}) or {}
        try:
            total = int(payload.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        batch = list(payload.get("data") or [])
        if not batch:
            break
        rows += batch
        if len(rows) >= total:
            break
        page += 1
        if len(rows) < top and pause:
            time.sleep(pause)
    # `complete` is a real reading, not a decoration: it is true only when the
    # sweep holds every row it ASKED for. A response that serves fewer rows than
    # its own `total` claims, or one with no total at all, leaves coverage
    # UNKNOWN, and a short sweep must say so rather than let its floor be read
    # as "nothing found below here".
    complete = bool(total) and len(rows) >= min(top, total)
    return rows[:top], complete


# ---------------------------------------------------------------------------
# the key


def row_date(row):
    """The row's layoff date, or None. None is a STATE, never a big number.

    `dedupe_llm.days_between` answers 9999 here, which every window gate then
    reads as "too far apart" -- the silent unreachability this module exists to
    make visible. Nothing in this file substitutes a number for a missing date.
    """
    text = str((row or {}).get("layoff_date") or "")[:10]
    try:
        return date(*map(int, text.split("-")))
    except Exception:
        return None


def _country(row):
    return str((row or {}).get("country") or "").strip().lower()


def countries_compatible(a, b):
    """True when nothing in the country fields RULES the pair out."""
    ca, cb = _country(a), _country(b)
    return ca in UNKNOWN_COUNTRIES or cb in UNKNOWN_COUNTRIES or ca == cb


def same_country_strictly(a, b):
    ca, cb = _country(a), _country(b)
    return ca == cb and ca not in UNKNOWN_COUNTRIES


def count_ratio(a, b):
    try:
        x, y = int(a.get("job_count") or 0), int(b.get("job_count") or 0)
    except Exception:
        return 0.0
    hi = max(x, y)
    return (min(x, y) / hi) if hi > 0 else 0.0


def eligible(row):
    """A row this scan may consider at all."""
    if not isinstance(row, dict):
        return False
    if str(row.get("source_type") or "").lower() in EXCLUDED_SOURCE_TYPES:
        return False
    try:
        return int(row.get("job_count") or 0) > 0
    except Exception:
        return False


def pair_is_suspect(a, b, ratio=COUNT_RATIO, window=WINDOW_DAYS):
    """The whole key. Reads country, job_count and layoff_date. No name."""
    if str(a.get("source_type") or "").lower() == WARN \
            and str(b.get("source_type") or "").lower() == WARN:
        return False
    ev_a, ev_b = a.get("event_id"), b.get("event_id")
    if ev_a and ev_b and ev_a == ev_b:
        return False          # already one event; nothing to adjudicate
    if count_ratio(a, b) < ratio:
        return False
    if not countries_compatible(a, b):
        return False
    da, db = row_date(a), row_date(b)
    if da is None or db is None:
        return False          # dateless rows are a SECTION, not a pair
    return abs((da - db).days) <= window


# ---------------------------------------------------------------------------
# the scan


class Report:
    """What one sweep saw. Every field is a fact, none of them is a verdict."""

    def __init__(self, scanned, complete, pairs, dateless_queue,
                 date_rates, bulk_dateless, smallest_count):
        self.scanned = scanned
        self.complete = complete
        self.pairs = pairs                      # dated near-identical shapes
        self.dateless_queue = dateless_queue    # unreachable rows, per row
        self.date_rates = date_rates            # source_type -> (rows, dateless)
        self.bulk_dateless = bulk_dateless      # source_type -> count
        self.smallest_count = smallest_count    # the floor this sweep reached

    @property
    def findings(self):
        return len(self.pairs) + len(self.dateless_queue)


def _neighbours(row, rows, ratio=DATELESS_NEIGHBOUR_RATIO, limit=MAX_NEIGHBOURS):
    """Rows a dateless row COULD be a re-report of, best evidence first.

    A strict country match outranks a wildcard one ("Multiple countries"
    matches everything and therefore evidences little), then closeness of
    count. These are hints for a human, never a claim.
    """
    out = []
    for other in rows:
        if other is row or other.get("id") == row.get("id"):
            continue
        if not countries_compatible(row, other):
            continue
        r = count_ratio(row, other)
        if r < ratio:
            continue
        out.append((not same_country_strictly(row, other), -r, other))
    out.sort(key=lambda t: (t[0], t[1], str(t[2].get("id"))))
    return [t[2] for t in out[:limit]]


def scan(rows, complete=True, ratio=COUNT_RATIO, window=WINDOW_DAYS):
    """Every suspicion the shape key can raise over `rows`. Pure, no network."""
    usable = [r for r in rows if eligible(r)]

    pairs = []
    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            if pair_is_suspect(a, b, ratio=ratio, window=window):
                gap = abs((row_date(a) - row_date(b)).days)
                size = max(int(a.get("job_count") or 0), int(b.get("job_count") or 0))
                pairs.append({"gap_days": gap, "job_count": size, "a": a, "b": b})
    # Tightest date gap first, then biggest headline impact: the pairs most
    # likely to be one event, and most expensive if they are, read first.
    pairs.sort(key=lambda p: (p["gap_days"], -p["job_count"],
                              str(p["a"].get("id")), str(p["b"].get("id"))))

    date_rates = {}
    for row in usable:
        st = str(row.get("source_type") or "") or "(none)"
        seen, dateless = date_rates.get(st, (0, 0))
        date_rates[st] = (seen + 1, dateless + (1 if row_date(row) is None else 0))

    bearing = set()
    for st, (seen, dateless) in date_rates.items():
        if seen < DATE_BEARING_MIN_ROWS:
            bearing.add(st)     # too few to fit a rate: report, never assume
        elif (seen - dateless) / seen >= DATE_BEARING_MIN_SHARE:
            bearing.add(st)

    queue, bulk = [], {}
    for row in usable:
        if row_date(row) is not None:
            continue
        st = str(row.get("source_type") or "") or "(none)"
        if st in bearing:
            queue.append({"row": row, "neighbours": _neighbours(row, usable)})
        else:
            bulk[st] = bulk.get(st, 0) + 1
    queue.sort(key=lambda q: (-int(q["row"].get("job_count") or 0),
                              str(q["row"].get("id"))))

    floor = min((int(r.get("job_count") or 0) for r in usable), default=0)
    return Report(len(usable), complete, pairs, queue, date_rates, bulk, floor)


# ---------------------------------------------------------------------------
# output


def _label(row):
    name = str(row.get("company_name") or "?")
    country = str(row.get("country") or "").strip() or "?"
    when = str(row.get("layoff_date") or "").strip() or "no date"
    return (f"{row.get('id')} {name!r} {int(row.get('job_count') or 0):,} "
            f"[{country}] {when} {row.get('source_type') or '?'}")


def summary_lines(report, max_pairs=5, max_dateless=5):
    """The compact read for ops_status. Loud on findings, honest on coverage."""
    out = []
    if not report.scanned:
        out.append("    UNKNOWN: the sweep read no rows. Nothing was checked.")
        return out
    out.append(f"    scanned the {report.scanned:,} largest rows the headline counts "
               f"(down to {report.smallest_count:,} jobs)")
    if not report.complete:
        out.append("    the sweep stopped short of the rows it asked for, so coverage "
                   "below that floor is UNKNOWN")
    if report.pairs:
        out.append(f"    {len(report.pairs)} near-identical (country, job_count, "
                   f"<={WINDOW_DAYS}d) shape(s), UNKNOWN and needing adjudication:")
        for p in report.pairs[:max_pairs]:
            out.append(f"      {p['gap_days']:>2}d apart  {p['job_count']:>7,}  "
                       f"{p['a'].get('id')} vs {p['b'].get('id')}  "
                       f"{str(p['a'].get('company_name'))[:26]!r} / "
                       f"{str(p['b'].get('company_name'))[:26]!r}")
        if len(report.pairs) > max_pairs:
            out.append(f"      ... and {len(report.pairs) - max_pairs} more")
    else:
        out.append("    no near-identical dated shapes in the scanned window")
    if report.dateless_queue:
        out.append(f"    {len(report.dateless_queue)} DATELESS row(s) from date-bearing "
                   f"sources, unreachable by dedup FOREVER:")
        for item in report.dateless_queue[:max_dateless]:
            out.append(f"      {int(item['row'].get('job_count') or 0):>7,}  "
                       f"{item['row'].get('id')}  "
                       f"{str(item['row'].get('company_name'))[:26]!r} "
                       f"[{item['row'].get('country') or '?'}]")
        if len(report.dateless_queue) > max_dateless:
            out.append(f"      ... and {len(report.dateless_queue) - max_dateless} more")
    else:
        out.append("    no dateless rows from date-bearing sources in the window")
    if report.bulk_dateless:
        bulk = ", ".join(f"{n:,} {st}" for st, n in sorted(report.bulk_dateless.items()))
        out.append(f"    ({bulk} dateless row(s) not queued: that source does not carry "
                   f"dates at all)")
    out.append("    -> a suspicion is NOT a duplicate. This never merges anything; the "
               "owner adjudicates.")
    out.append("    -> full worklist: python3 railway/duplicate_shape_scan.py")
    return out


def worklist_lines(report):
    """The full report, for a human working the queue."""
    out = [f"DUPLICATE SHAPE SCAN: {report.scanned:,} largest rows "
           f"(floor {report.smallest_count:,} jobs)", ""]
    out.append(f"[A] NEAR-IDENTICAL DATED SHAPES  ratio>={COUNT_RATIO}, "
               f"gap<={WINDOW_DAYS}d, compatible country  ({len(report.pairs)})")
    for p in report.pairs:
        out.append(f"  {p['gap_days']:>2}d  {p['job_count']:>7,}")
        out.append(f"        A  {_label(p['a'])}")
        out.append(f"        B  {_label(p['b'])}")
    if not report.pairs:
        out.append("  (none)")
    out.append("")
    out.append(f"[B] DATELESS ROWS FROM DATE-BEARING SOURCES  ({len(report.dateless_queue)})")
    out.append("    A blank layoff_date makes dedupe_llm.days_between answer 9999, so these")
    out.append("    rows can never cluster with anything. They need a human, not a job.")
    for item in report.dateless_queue:
        out.append(f"  {_label(item['row'])}")
        for nb in item["neighbours"]:
            out.append(f"        could be? {_label(nb)}")
    if not report.dateless_queue:
        out.append("  (none)")
    out.append("")
    out.append("[C] DATE COVERAGE BY SOURCE (derived from this sweep, never hardcoded)")
    for st, (seen, dateless) in sorted(report.date_rates.items()):
        share = 100.0 * (seen - dateless) / seen if seen else 0.0
        out.append(f"  {st:<16} {seen:>5,} rows  {dateless:>5,} dateless  "
                   f"{share:5.1f}% dated")
    out.append("")
    out.append("[D] WHAT THIS SWEEP COULD NOT SEE")
    out.append(f"  * anything below {report.smallest_count:,} jobs (raise --top to go deeper)")
    out.append("  * two reports of one event whose counts differ by more than "
               f"{100 * (1 - COUNT_RATIO):.0f}% and that both carry dates")
    out.append("  * WARN-against-WARN pairs (companies legally file several notices)")
    out.append("  * rows already folded by /reconcile-supersets (the headline "
               "does not count them)")
    if not report.complete:
        out.append("  * PART OF THE REQUESTED WINDOW: the sweep stopped short, "
                   "so coverage is UNKNOWN.")
    out.append("")
    out.append("NOTHING HERE IS A VERDICT. Every line is UNKNOWN pending the owner's")
    out.append("adjudication, and this module writes nothing to the live site.")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", type=int, default=TOP_ROWS,
                    help=f"how many of the largest rows to scan (default {TOP_ROWS})")
    ap.add_argument("--window", type=int, default=WINDOW_DAYS)
    args = ap.parse_args(argv)
    try:
        rows, complete = fetch_top_rows(top=args.top)
    except SweepAborted as exc:
        print(f"SWEEP ABORTED: {exc}")
        print("This is UNKNOWN, not a pass: nothing was checked. Do not retry in a "
              "loop, because a bot challenge is answered by waiting, not by more requests.")
        return 3
    except Exception as exc:  # noqa: BLE001
        print(f"UNKNOWN: could not read /query ({exc}). Nothing was checked.")
        return 3
    report = scan(rows, complete=complete, window=args.window)
    print("\n".join(worklist_lines(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
