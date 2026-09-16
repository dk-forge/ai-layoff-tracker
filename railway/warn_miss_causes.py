#!/usr/bin/env python3
"""Why each unmatched WARN reference event is unmatched — the worklist half.

READ docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md §8 FIRST.
It fixes the six buckets and it fixes that `UNKNOWN` is a verdict and not a
bucket of convenience.

WHY THIS IS A SEPARATE MODULE FROM THE MEASUREMENT
--------------------------------------------------
Because it is allowed to ask questions the measurement is not. The §6 matching
rule is deliberately strict — a token-PREFIX alias, the state, a date window —
and the number it produces is only meaningful while it stays strict. Diagnosis
needs a looser question ("is there ANY row in this state, in this window,
carrying exactly this notice's headcount?"), and asking that question inside
`measure()` would be indistinguishable from widening the rule until the number
improved.

So: **nothing in this module can move a numerator.** It writes its own file, it
never touches a manifest or a measurement, and a test asserts both. Its output
is a cause per miss and a worklist, which the definition says is worth more than
the percentage.

WHAT IT CAN AND CANNOT SEPARATE, SAID UP FRONT
-----------------------------------------------
From public read-only GETs it can tell **`stored_unmatched`** — we hold the row
and the strict rule did not find it — from "we hold nothing for this notice",
and for the first it can name the row and the reason the strict rule missed it.

It CANNOT separate `walked_not_read` from `fetched_rejected` from
`extracted_dropped`, because all three are statements about a collector's own
output and this measurement does not have it. Those land in `UNKNOWN` with the
narrowing recorded on the line, which is what an honest worklist entry looks
like. Do NOT answer a pile of UNKNOWNs by guessing between the three.

No model is called. Cost: $0.00.

USAGE
    python3 railway/warn_miss_causes.py --classify   # probe and write the causes file
    python3 railway/warn_miss_causes.py              # summarise the committed file
"""
import json
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_reference_set as W                                     # noqa: E402
import warn_reference_set_wave2 as V                               # noqa: E402

CAUSES_PATH = Path(__file__).resolve().parent / "warn_recall_miss_causes.json"

# §8's vocabulary, and nothing else may be written into `cause`.
BUCKETS = ("no_source", "walked_not_read", "fetched_rejected",
           "extracted_dropped", "stored_unmatched", "UNKNOWN")


def _relaxed_terms(event):
    """The distinctive tokens of the published name, longest first.

    This is a DIAGNOSTIC retrieval, never a match test. It exists because four
    of the first sixteen misses turned out to be rows we hold under a different
    published name -- `Claires Stores, Inc.` stored as `Claire's - Hoffman
    Estates`, `Gerresheimer Moulded Glass Chicago Inc.` stored as `GERRESHEIMER
    GLASS INC.` -- which a leading-token-prefix alias can never reach and which
    a human spots in one look.
    """
    toks = V._distinctive_tokens(event["employer_published"])
    ordered = sorted(toks, key=len, reverse=True)
    seen, out = set(), []
    for tok in ordered[:2]:
        for cand in (tok, tok[:6]):
            # A TRUNCATED PREFIX AS WELL AS THE WHOLE TOKEN, because
            # `/query?company=` is a substring LIKE and the state's spelling of
            # a name is not ours: Illinois publishes `Claires Stores, Inc.` and
            # we store `Claire's - Hoffman Estates`, so the token `Claires`
            # finds nothing while `Claire` finds it at the published headcount.
            # This is retrieval for DIAGNOSIS. The hit still has to carry a
            # count the notice published, in this state, inside this notice's
            # own window, from a WARN-tier row -- so a short prefix widens what
            # is looked at and not what counts as found.
            if len(cand) >= 5 and cand.lower() not in seen:
                seen.add(cand.lower())
                out.append(cand)
    return out[:4]


def _counts(event):
    out = {event["stated_job_count"]}
    out |= {c["job_count"] for c in event["component_rows"] if c.get("job_count")}
    return {n for n in out if n}


def probe(event):
    """Rows in this state and window whose count equals a published count."""
    hits, errors = [], []
    for term in _relaxed_terms(event):
        params = {"company": term, "state": event["state"],
                  "from": event["match_window"][0], "to": event["match_window"][1],
                  "per_page": 200, "cb": W._cachebust()}
        try:
            payload = W._api("query?" + urllib.parse.urlencode(params)) or {}
        except Exception as exc:                                   # noqa: BLE001
            errors.append(f"{term}: {type(exc).__name__}: {exc}")
            continue
        for row in payload.get("data") or []:
            hits.append(row)
        time.sleep(0.2)
    wanted = _counts(event)
    exact = [r for r in hits
             if r.get("job_count") in wanted
             and "warn" in str(r.get("source_type") or "").lower()]
    return exact, hits, errors


def classify_event(event, result):
    """One bucket and one line, from evidence this module actually has."""
    exact, near, errors = probe(event)
    if errors and not near:
        return {
            "cause": "UNKNOWN",
            "line": ("the diagnostic probe could not complete (" + errors[0]
                     + "), so nothing was established -- a query that did not "
                       "run is UNKNOWN, never a cause"),
            "evidence": {"probe_errors": errors},
        }
    if exact:
        row = sorted(exact, key=lambda r: str(r.get("layoff_date")))[0]
        return {
            "cause": "stored_unmatched",
            "line": (f"we hold row {row.get('id')} in {event['state']} inside this "
                     f"notice's own match window carrying {row.get('job_count')} "
                     f"jobs, which the notice publishes; the strict rule missed it "
                     f"because we store the employer as "
                     f"{(row.get('company_name') or '')!r} and the state publishes "
                     f"{event['employer_published']!r}, and the alias test is a "
                     f"token PREFIX"),
            "evidence": {
                "tracker_row_id": row.get("id"),
                "tracker_event_id": row.get("event_id"),
                "stored_company_name": row.get("company_name"),
                "stored_job_count": row.get("job_count"),
                "stored_layoff_date": row.get("layoff_date"),
                "stored_source_type": row.get("source_type"),
                "relaxed_terms": _relaxed_terms(event),
            },
        }
    return {
        "cause": "UNKNOWN",
        "line": ("no row in this state carries any published count of this notice "
                 "inside its own match window, so we appear not to hold it; "
                 "WHICH of walked_not_read / fetched_rejected / extracted_dropped "
                 "applies cannot be established from public reads, because all "
                 "three are statements about the collector's own output"),
        "evidence": {
            "relaxed_terms": _relaxed_terms(event),
            "rows_seen_by_the_relaxed_probe": len(near),
            "published_counts_looked_for": sorted(_counts(event)),
        },
    }


def state_coverage(manifest, measurement):
    """Per state: does the frame's month coverage have a hole in what we hold?

    A CONTIGUOUS held series RULES OUT a collection outage and is the reason
    every no-row miss below reads as a per-notice gap rather than a dark month.
    A hole would be the opposite finding and would be the headline.
    """
    out = {}
    for st in manifest["states"]:
        months = {}
        params = {"state": st, "from": "2025-06-01", "to": "2027-12-31",
                  "per_page": 200, "cb": W._cachebust()}
        try:
            payload = W._api("query?" + urllib.parse.urlencode(params)) or {}
        except Exception as exc:                                   # noqa: BLE001
            out[st] = {"status": "UNKNOWN", "why": f"{type(exc).__name__}: {exc}"}
            continue
        rows = [r for r in (payload.get("data") or [])
                if "warn" in str(r.get("source_type") or "").lower()]
        for r in rows:
            months[str(r.get("layoff_date"))[:7]] = months.get(
                str(r.get("layoff_date"))[:7], 0) + 1
        # A MONTH THAT HAS NOT HAPPENED YET IS NOT A HOLE. WARN rows store the
        # EFFECTIVE date, so a state's series runs years into the future on a
        # handful of plant closures; judging the span out to the last of those
        # made Ohio read `HOLE` on five empty 2027 months and would have sent a
        # reader looking for an outage that is a future-dated closure.
        horizon = date.today().strftime("%Y-%m")
        span = sorted(m for m in months if "2025-06" <= m <= horizon)
        empty = [] if not span else [
            m for m in _month_span(span[0], span[-1]) if m not in months]
        out[st] = {
            "warn_rows_seen": len(rows),
            "page_was_full": len(payload.get("data") or []) >= 200,
            "months_with_rows": len(months),
            "span_judged": [span[0], span[-1]] if span else None,
            "months_beyond_today_not_judged": sorted(
                m for m in months if m > date.today().strftime("%Y-%m")),
            "empty_months_inside_the_span": empty,
            "verdict": ("continuous -- no collection outage in this span"
                        if not empty else
                        "HOLE -- read this before any per-notice cause"),
        }
        time.sleep(0.5)
    return out


def _month_span(first, last):
    y, m = (int(x) for x in first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def classify(manifest_path=V.MANIFEST_PATH, measurement_path=V.MEASUREMENT_PATH):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    measurement = json.loads(Path(measurement_path).read_text(encoding="utf-8"))
    by_id = {e["reference_row_id"]: e
             for e in manifest["reference_events"] + manifest["large_event_census"]}
    causes = []
    for stratum in ("primary", "large_census"):
        for result in measurement["results"][stratum]:
            if result["candidates"]:
                continue                   # the rule proposed something; not a miss
            ev = by_id[result["id"]]
            verdict = classify_event(ev, result)
            causes.append({
                "id": result["id"], "stratum": stratum, "state": ev["state"],
                "employer_published": ev["employer_published"],
                "notice_date": ev["notice_date"],
                "stated_job_count": ev["stated_job_count"],
                "size_band": ev["size_band"],
                "official_source_url": ev["official_source_url"],
                **verdict,
            })
            print(f"  {ev['state']} {ev['notice_date']} "
                  f"{ev['employer_published'][:34]:34s} -> {verdict['cause']}")
    tally = {b: sum(1 for c in causes if c["cause"] == b) for b in BUCKETS}
    out = {
        "note": ("Cause per unmatched event for the US WARN wave-2 reference set. "
                 "DIAGNOSTIC ONLY: nothing here is a match decision, nothing here "
                 "feeds a numerator, and the relaxed probe this module uses is NOT "
                 "the matching rule. The buckets are the definition's §8 and "
                 "UNKNOWN is a verdict."),
        "reference_set_id": manifest["reference_set_id"],
        "definition_document": manifest["definition_document"],
        "classified_at": W._utc_now(),
        "cause_counts": tally,
        "state_coverage_evidence": state_coverage(manifest, measurement),
        "causes": causes,
        "cost_usd": 0.0,
    }
    CAUSES_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"\ncauses written: {CAUSES_PATH}")
    print("  " + ", ".join(f"{k}={v}" for k, v in tally.items() if v))
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if "--classify" in argv:
        classify()
        return 0
    if CAUSES_PATH.exists():
        data = json.loads(CAUSES_PATH.read_text(encoding="utf-8"))
        print(json.dumps(data["cause_counts"], indent=2))
        for c in data["causes"]:
            print(f"{c['state']} {c['notice_date']} {c['employer_published'][:34]:34s} "
                  f"{c['cause']}")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
