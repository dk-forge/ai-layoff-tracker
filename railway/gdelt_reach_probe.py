#!/usr/bin/env python3
"""MANUAL, $0 reach probe: what does the broad worldwide query actually return?

WHY A SEPARATE ENTRY POINT
--------------------------
`gdelt_reach` records the real ingest run, but that run happens on Railway's
cron and cannot be triggered from a session or a workflow. The one number the
open question turns on -- **does the broad query hit `maxrecords`?** -- needs no
article fetch, no extractor and no model, so it does not need to wait for a
cron slot either.

WHAT IT COSTS, EXACTLY
----------------------
$0.00. It makes **ONE** GDELT request (the broad query, the same window shape
production uses), fetches **no** article, calls **no** model, writes **no** row
and posts **no** health note. It is the query half of `pull_gdelt_between` and
nothing else.

WHY THERE IS NO WORKFLOW FOR IT, AND MUST NOT BE
------------------------------------------------
GDELT is a free, shared, aggressively rate-limited endpoint. Production already
queries it on a schedule; a second scheduled caller would compete with the
collector it is meant to measure and could manufacture the very 429s it is
looking for. Run it by hand when you want a reading. If it is ever wanted on a
cadence, the answer is to read the numbers the real run now publishes to
`/source-runs`, not to add a second caller.

    python3 railway/gdelt_reach_probe.py            # the live 36h window
    python3 railway/gdelt_reach_probe.py --hours 6  # a narrower window

A 429 IS A RESULT, NOT A FAILURE
--------------------------------
If the probe is abandoned after its retries, that is the finding -- from THIS
egress address, at THIS moment. It is NOT evidence about production, which
runs from a different network and whose real answer is in `/source-runs`. The
exit code says which happened: 0 measured, 3 could not measure.
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

import gdelt_reach


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hours", type=float, default=36.0,
                    help="window size; production uses 36")
    ap.add_argument("--max-records", type=int, default=250,
                    help="production uses 250 — the cap under test")
    args = ap.parse_args(argv)

    from sources import gdelt as gdelt_src

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=args.hours)
    gdelt_reach.reset()
    reach = gdelt_reach.current()

    print(f"probe: broad query, {args.hours:g}h window, maxrecords={args.max_records}")
    articles, rate_limited, error = gdelt_src._query_window(
        gdelt_src.QUERY, start, end, args.max_records, "broad")

    if articles is None:
        print(f"probe: WINDOW ABANDONED (rate_limited={rate_limited}): {error}")
        print("probe: UNMEASURED from this address. This says nothing about "
              "production — read /source-runs?source=gdelt for that.")
        return 3

    # The allowlist gate, WITHOUT the article fetch. Mirrors _fetch_trusted's
    # ordering exactly so the two agree; duplicated here rather than called
    # because _fetch_trusted fetches, and a probe that fetches is not free.
    seen = set()
    for a in articles:
        url = a.get("url")
        dom = gdelt_src._domain(a)
        if not url:
            reach.note(dom, "empty_text")
        elif url in seen:
            reach.note(dom, "duplicate_url")
        elif not gdelt_src._is_trusted(dom):
            reach.note(dom, "not_allowlisted")
        else:
            seen.add(url)
            # NOT "kept": this probe never fetched the article, so it cannot
            # know whether the publisher would have served it. `kept` in a real
            # run means fetched and non-empty. Calling it kept here would
            # overstate reach by exactly the fetch-failure rate.
            reach.note(dom, "already_ingested")

    for line in reach.report_lines():
        print(line)
    t = reach.totals()
    print()
    if t["capped"]:
        print(f"probe: THE CAP IS BINDING — the query returned exactly "
              f"{args.max_records} over {args.hours:g}h, sorted newest-first. "
              f"Everything below the cut was never offered.")
    else:
        print(f"probe: the cap is NOT binding — {t['returned']} returned "
              f"against a ceiling of {args.max_records}. Whatever is missing, "
              f"maxrecords did not remove it.")
    print("probe: 'already_ingested' above is the allowlist-PASSED count. This "
          "probe does not fetch, so it cannot report `kept`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
