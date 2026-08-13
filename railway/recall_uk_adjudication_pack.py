#!/usr/bin/env python3
"""Build the sheet a human adjudicates the UK set from. Records no recommendation.

The UK measurement's numerator is zero by construction: nothing is adjudicated,
so `measure()` reports every tracker row it found under
`candidates_needing_adjudication` and counts none of them. This module turns
that list into something a person can actually work through, and it copies the
one design constraint the US pack learned on 2026-08-12:

    **it records no recommendation, and it does not quote the manifest's own
    match_notes at the person auditing the manifest** — a pre-ticked sheet moves
    the gate from the human to the machine while leaving the machine's
    fingerprints off it.

Two artefacts per row, both primary and both re-read at build time: the ORIGINAL
PUBLISHER's own count sentence as the manifest recorded it verbatim from the
source, and OUR row exactly as the public `/query` serves it today.

    python3 railway/recall_uk_adjudication_pack.py          # print
    python3 railway/recall_uk_adjudication_pack.py --write  # write the .md
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
QUEUE_MD = (REPO_ROOT / "docs" / "recall-reference-sets"
            / "uk-adjudication-queue.md")
BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


def _rows_for(aliases):
    """Every row the public API returns for these aliases, keyed by event_id.

    `/query` has no `event_id` filter — passing one is silently IGNORED and the
    endpoint answers with the whole table, which is how a sheet ends up quoting
    a stranger's row at the reviewer. So the lookup goes through the same
    `company=` filter `measure()` uses and the event_id is applied here.
    """
    out = {}
    for alias in aliases or []:
        url = BASE + "query?" + urllib.parse.urlencode(
            {"company": alias, "country_basis": "any", "per_page": 100})
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                for row in (json.loads(r.read()) or {}).get("data") or []:
                    out.setdefault(row.get("event_id"), row)
        except Exception as exc:                               # noqa: BLE001
            out.setdefault("_error", {"_error": f"{type(exc).__name__}: {exc}"})
    return out


def build(manifest, measurement):
    events = {e["reference_row_id"]: e for e in manifest["reference_events"]}
    lines = [
        "# UK reference set — adjudication queue",
        "",
        "**Nothing here is decided and nothing here is counted.** The UK figure is "
        "0 of N editor-confirmed, and it stays there until a person decides each row "
        "below. That gate is the point: on the US set the machine's alias+window rule "
        "scored 31 where the editor scored 24, having accepted a WARN notice filed ten "
        "weeks early and an Italian composites maker for HP Inc.",
        "",
        "For each row: does OUR row represent the SAME UNDERLYING EVENT as the "
        "employer's own announcement? A similar company name and a nearby date are not "
        "enough. No recommendation is offered below, deliberately.",
        "",
    ]
    for cand in measurement.get("candidates_needing_adjudication") or []:
        event = events.get(cand["id"], {})
        lines += [
            f"## {event.get('employer', cand['id'])} — announced "
            f"{event.get('announcement_date')}",
            "",
            f"- **reference id**: `{cand['id']}`",
            f"- **the publisher says**: {event.get('stated_job_count')} — "
            f"\"{event.get('count_evidence', '')}\"",
            f"- **published by**: {event.get('publisher')} "
            f"({event.get('citation_type')}) — {event.get('official_source_url')}",
            f"- **match window**: {event.get('match_window')}",
            "",
            "| our row | company | job_count | layoff_date | source | url |",
            "|---|---|---|---|---|---|",
        ]
        rows = _rows_for(event.get("employer_aliases"))
        for event_id in cand.get("new_tracker_event_ids") or []:
            row = rows.get(event_id) or rows.get("_error") or {}
            if row.get("_error") or not row:
                lines.append(f"| {event_id} | (could not read: "
                             f"{row.get('_error', 'not returned by /query')}) | | | | |")
                continue
            lines.append(
                f"| {event_id} | {row.get('company_name')} | {row.get('job_count')} | "
                f"{row.get('layoff_date')} | {row.get('source_name')} | "
                f"{row.get('source_url')} |")
        lines += ["", "**Decision:** _____________  **Reviewer:** _____________  "
                       "**Reason:** _____________", ""]
    if not (measurement.get("candidates_needing_adjudication") or []):
        lines += ["_No tracker row satisfies the alias/window rule for any event in the "
                  "set. There is nothing to adjudicate, and that is itself the finding._",
                  ""]
    return "\n".join(lines)


def main(argv=None):
    argv = argv or sys.argv[1:]
    import recall_uk_goldset
    manifest = recall_uk_goldset.load_manifest()
    measurement = recall_uk_goldset.load_measurement()
    if measurement is None:
        print("no UK measurement written yet — run recall_uk_goldset.py --write first")
        return 3
    text = build(manifest, measurement)
    if "--write" in argv:
        QUEUE_MD.write_text(text + "\n", encoding="utf-8")
        print(f"written: {QUEUE_MD}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
