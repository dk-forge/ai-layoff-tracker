#!/usr/bin/env python3
"""The US WARN adjudication sheet — one block per CANDIDATE ROW, never per event.

WHY THE PER-ROW RULE IS THE WHOLE DESIGN
----------------------------------------
On 2026-08-12 the SEC sheet pooled the flags of several proposed rows into one
summary line. Gold event `DOW INC.` had two proposed rows, 149592 (138 jobs,
sourced to news) and 149616 (the correct 4,500). The pooled line read

    COUNT differs by -4362: we hold 138, the filing states 4500; SOURCE is
    'news', not the 8-K; ... 2 different tracker rows are proposed

— every clause of which describes 149592 — and a reviewer reading it rejected
the event. We held the Dow 4,500 all along; the sheet hid it.

So in this sheet **no line ever describes more than one candidate row**. The
index table has one line per (reference event, candidate row) pair, each
carrying only its own flags. An event with three candidates gets three lines,
and a reviewer who accepts the event names the row id they accepted.

WHAT IT DOES NOT DO
-------------------
It does not decide, rank by desirability, or recommend. Flags are statements of
fact about one pair. Ordering is by how much there is to look at.

The reference side is carried from the manifest, labelled `notice_says_*`, and
every block prints the STATE's own source URL and row locator so the reviewer
checks the notice rather than this file. Where the state publishes a per-notice
document (FL and TN link the employer's own letter) that link is the citation.
The tracker side is re-fetched live on every run, because live data moves.

READ-ONLY. Public /query GETs. No key, no model, no write to anything live.

USAGE
    python3 railway/warn_adjudication_pack.py --write
"""
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_reference_set as W                                    # noqa: E402
from recall_goldset import format_interval                        # noqa: E402

PACK_PATH = W.REF_DIR / "us-warn-adjudication-queue.json"
SHEET_PATH = W.REF_DIR / "us-warn-adjudication-queue.md"

HARD, SOFT = 100, 1
# Flag substrings that mean "these may be two different things". Weighted so a
# candidate carrying one sorts to the bottom whatever else is true of it.
HARD_MARKS = ("matches neither", "not a WARN-tier row", "differs from the published")


def _weight(cand):
    return sum(HARD if any(h in f for h in HARD_MARKS) else SOFT
               for f in cand["flags"])


def _live_rows(event):
    """Re-fetch this event's candidate rows as the endpoint serves them NOW.

    ONE request per event, not one per row, and it goes through the event's own
    query terms because **`/query` has no `id` filter**. An earlier version
    passed `id=` and, since an unknown parameter is simply ignored, got back the
    state's most recent rows and reported "the endpoint no longer serves this
    row id" for every candidate in the sheet. A refetch that cannot find what it
    is looking for must not be rendered as evidence that the row is gone.
    """
    found = {}
    for term in event.get("query_terms") or []:
        q = urllib.parse.urlencode({"company": term, "state": event["state"],
                                    "from": event["match_window"][0],
                                    "to": event["match_window"][1],
                                    "per_page": 200, "cb": W._cachebust()})
        try:
            payload = W._api("query?" + q) or {}
        except Exception as exc:                                   # noqa: BLE001
            return {"__error__": f"{type(exc).__name__}: {exc}"}
        for row in payload.get("data") or []:
            found[row.get("id")] = row
        time.sleep(0.15)
    return found


def build_pack(refetch=True):
    manifest = json.loads(W.MANIFEST_PATH.read_text(encoding="utf-8"))
    measurement = json.loads(W.WARN_MEASUREMENT_PATH.read_text(encoding="utf-8"))
    by_id = {e["reference_row_id"]: e
             for e in manifest["reference_events"] + manifest["large_event_census"]}
    entries = []
    for stratum in ("primary", "large_census"):
        for result in measurement["results"][stratum]:
            if not result["candidates"] or result["match_decision"] == "matched":
                continue
            ev = by_id[result["id"]]
            live_by_id = _live_rows(ev) if refetch else {}
            error = live_by_id.pop("__error__", None)
            candidates = []
            for cand in result["candidates"]:
                live = live_by_id.get(cand["tracker_row_id"])
                if live is None:
                    live = {"refetch_error": error or
                            "not returned by a re-query of this event's own terms"}
                candidates.append({
                    **cand,
                    "weight": _weight(cand),
                    "live_now": {k: live.get(k) for k in
                                 ("company_name", "job_count", "layoff_date",
                                  "announcement_date", "state", "source_type",
                                  "source_name", "source_url", "refetch_error")},
                })
            candidates.sort(key=lambda c: (c["weight"], c["row_date"]))
            entries.append({
                "reference_row_id": ev["reference_row_id"],
                "stratum": stratum,
                "state": ev["state"],
                "notice_says_employer": ev["employer_published"],
                "notice_says_date": ev["notice_date"],
                "notice_says_job_count": ev["stated_job_count"],
                "notice_says_effective": [ev["effective_date_min"], ev["effective_date_max"]],
                "notice_published_rows": ev["component_rows"],
                "official_source_url": ev["official_source_url"],
                "size_band": ev["size_band"],
                "match_window": ev["match_window"],
                "candidates": candidates,
                "min_weight": min(c["weight"] for c in candidates),
            })
    entries.sort(key=lambda e: (e["min_weight"], e["state"], e["notice_says_date"]))
    return manifest, measurement, entries


def _arithmetic(measurement, entries):
    prim = measurement["results"]["primary"]
    n = len(prim)
    confirmed = sum(1 for r in prim if r["match_decision"] == "matched")
    pending_ids = {e["reference_row_id"] for e in entries if e["stratum"] == "primary"}
    all_accept = confirmed + len(pending_ids)
    exact_only = confirmed + sum(1 for r in prim if r["id"] in pending_ids
                                 and r["machine_tier"] == "exact")
    clean_only = confirmed + sum(
        1 for e in entries if e["stratum"] == "primary" and e["min_weight"] <= SOFT * 2)
    return [
        ("every pending candidate accepted", all_accept, n),
        ("only the exact-tier candidates accepted", exact_only, n),
        ("only the candidates where every fact lines up", clean_only, n),
        ("nothing accepted (today's published figure)", confirmed, n),
    ]


def write_pack():
    manifest, measurement, entries = build_pack()
    PACK_PATH.write_text(json.dumps({
        "note": ("Adjudication queue for the US WARN reference set. Every flag is "
                 "attributed to the ONE candidate row it describes; no line in the "
                 "sheet summarises more than one row. See the module docstring for "
                 "why. Nothing here is a decision."),
        "reference_set_id": manifest["reference_set_id"],
        "definition_document": manifest["definition_document"],
        "built_at": W._utc_now(),
        "measured_at": measurement["measured_at"],
        "pending_events": len(entries),
        "pending_candidate_rows": sum(len(e["candidates"]) for e in entries),
        "entries": entries,
    }, indent=2) + "\n", encoding="utf-8")
    SHEET_PATH.write_text(render_sheet(manifest, measurement, entries), encoding="utf-8")
    print(f"pack written:  {PACK_PATH}")
    print(f"sheet written: {SHEET_PATH}")
    print(f"{len(entries)} events pending, "
          f"{sum(len(e['candidates']) for e in entries)} candidate rows")
    return entries


def _anchor(idx, entry):
    slug = "".join(c if c.isalnum() else "-" for c in
                   entry["notice_says_employer"].lower())[:50].strip("-")
    return f"#{idx}-{entry['state'].lower()}-{slug}"


def render_sheet(manifest, measurement, entries):
    out = []
    a = out.append
    a("# US WARN reference set — adjudication sheet")
    a("")
    a(f"Built `{W._utc_now()}` from a measurement taken `{measurement['measured_at']}`. "
      "**Rebuild it before deciding** (`python3 railway/warn_adjudication_pack.py "
      "--write`) — it reads live data and live data moves.")
    a("")
    a(f"Reference set: `{manifest['reference_set_id']}`. Definition: "
      f"[`{manifest['definition_document']}`](../../{manifest['definition_document']}). "
      f"Nothing in this set is published to `/benchmarks/recall` and nothing in it "
      f"touches the SEC Item 2.05 figure.")
    a("")
    a(f"**{len(entries)} events are pending**, carrying "
      f"{sum(len(e['candidates']) for e in entries)} candidate rows between them.")
    a("")
    a("The arithmetics, so the range is known before the first decision. They are "
      "arithmetic, not targets, and none of them is a prediction about how the "
      "entries below should go:")
    a("")
    for label, k, n in _arithmetic(measurement, entries):
        a(f"- {label}: **{format_interval(k, n)}**")
    a("")
    a("**Every line below describes exactly ONE candidate row.** An event with "
      "three candidates has three lines, each carrying only its own flags. That is "
      "not a formatting preference: on 2026-08-12 a pooled summary line on the SEC "
      "sheet described a co-proposed row and a correct Dow row was rejected because "
      "of it.")
    a("")
    a("| # | state | notice | notified | candidate row | tier | what is there to "
      "look at, for THIS ROW ONLY |")
    a("|---:|---|---|---:|---|---|---|")
    for i, e in enumerate(entries, 1):
        for cand in e["candidates"]:
            a(f"| {i} | {e['state']} | [{_md(e['notice_says_employer'])[:44]}]"
              f"({_anchor(i, e)}) {e['notice_says_date']} | "
              f"{e['notice_says_job_count']:,} | `{cand['tracker_row_id']}` "
              f"(event {cand['tracker_event_id']}) | {cand['tier']} | "
              f"{_md('; '.join(cand['flags']))} |")
    a("")
    a("Recording a decision is a separate, network-free step:")
    a("")
    a("```")
    a("python3 railway/warn_adjudicate.py --accept <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...")
    a("python3 railway/warn_adjudicate.py --reject <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...")
    a("```")
    a("")
    a("---")
    a("")
    for i, e in enumerate(entries, 1):
        a(f"## {i}. {_md(e['notice_says_employer'])} ({e['state']})")
        a("")
        a(f"`{e['reference_row_id']}` — currently `not_matched`, "
          f"stratum `{e['stratum']}`, size band `{e['size_band']}`")
        a("")
        a("**What the state published** (open the source and check it; do not take "
          "this file's word for it):")
        a("")
        a(f"- notice date **{e['notice_says_date']}**, effective "
          f"{e['notice_says_effective'][0]}..{e['notice_says_effective'][1]}")
        a(f"- **{e['notice_says_job_count']:,}** affected across "
          f"{len(e['notice_published_rows'])} published row(s)")
        for row in e["notice_published_rows"]:
            a(f"  - {_md(str(row['employer_published']))} — {row['job_count']} — "
              f"{row.get('location') or 'no location published'} — "
              f"`{row.get('source_locator')}`")
        a(f"- source: <{e['official_source_url']}>")
        a(f"- the rule's match window: {e['match_window'][0]} .. {e['match_window'][1]}")
        a("")
        a(f"**{len(e['candidates'])} candidate row(s).** Each block below is one row "
          f"and says nothing about any other.")
        a("")
        for cand in e["candidates"]:
            a(f"### row `{cand['tracker_row_id']}` — event `{cand['tracker_event_id']}`"
              f" — tier `{cand['tier']}`")
            a("")
            live = cand["live_now"]
            if live.get("refetch_error"):
                a(f"- **re-fetch failed**: {live['refetch_error']} — this row could not "
                  f"be confirmed live, which is UNKNOWN, not a reason to reject")
            a(f"- stored name: `{_md(str(cand['company_name']))}`")
            a(f"- stored count **{cand['job_count']}**, date `{cand['row_date']}`, "
              f"state `{cand['state']}`, source `{cand['source_type']}` / "
              f"`{cand['source_name']}`")
            if live and not live.get("refetch_error"):
                a(f"- live now: `{_md(str(live.get('company_name')))}` — "
                  f"{live.get('job_count')} — {live.get('layoff_date')} — "
                  f"`{live.get('source_type')}`")
            if cand.get("source_url"):
                a(f"- our cited source: <{cand['source_url']}>")
            a("- flags for this row:")
            for f in cand["flags"]:
                a(f"  - {_md(f)}")
            a("")
        a("---")
        a("")
    return "\n".join(out) + "\n"


def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--write" in argv:
        write_pack()
        return 0
    _, _, entries = build_pack(refetch=False)
    print(f"{len(entries)} events pending, "
          f"{sum(len(e['candidates']) for e in entries)} candidate rows "
          f"(dry run, nothing written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
