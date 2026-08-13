#!/usr/bin/env python3
"""The US WARN adjudication sheet — one line per CANDIDATE ROW, never per event.

WHY THE PER-ROW RULE IS THE WHOLE DESIGN
----------------------------------------
On 2026-08-12 the SEC sheet pooled the flags of several proposed rows into one
summary line. Gold event `DOW INC.` had two proposed rows, 149592 (138 jobs,
sourced to news) and 149616 (the correct 4,500). The pooled line read

    COUNT differs by -4362: we hold 138, the filing states 4500; SOURCE is
    'news', not the 8-K; ... 2 different tracker rows are proposed

— every clause of which describes 149592 — and a reviewer reading it rejected
the event. We held the Dow 4,500 all along; the sheet hid it.

So in this sheet **no line ever describes more than one candidate row.** Every
line names the row it is about by id. The index carries the ONE row the rule
proposes first for each event, with only that row's evidence on the line, and
the id of every other row in the window beside it WITHOUT any of their flags,
so nothing is invisible and nothing is conflated. Each of those other rows then
gets its own block, with its own flags, in the event's section below.

A row with nothing wrong is SAID to have nothing wrong. "No discrepancy found"
is a fact about a row, and leaving it blank is how a clean row starts looking
like an unexamined one.

WHAT IT DOES NOT DO
-------------------
It does not decide, rank by desirability, or recommend. Every field is a
statement of fact about one pair: what the state published, what we hold,
whether the counts are equal and by how much they differ if not, and which
date basis the row agrees with. There is no "recommended" column and no
pre-ticked box, because the gate is the editor's and a sheet that recommends has
moved it.

ORDERING IS BY HOW MUCH THERE IS TO READ, NOT BY HOW LIKELY AN ACCEPT IS. An
event whose one proposed row agrees on count, on date basis and on name is fast
to CHECK; that is why it comes first, and it may still be wrong.

THE EVENTS WITH NO CANDIDATE ROW ARE NOT BURIED. An event the rule proposes
nothing for cannot be a row in a list of ninety-nine near-identical accepts: it
is a different question, so it is a section of its own, above the index, with
every row we hold for that employer AT ANY DATE fetched live and shown.

READ-ONLY. Public /query GETs. No key, no model, no write to anything live.

USAGE
    python3 railway/warn_adjudication_pack.py            # dry run, nothing written
    python3 railway/warn_adjudication_pack.py --write    # write the pack + the sheet
    python3 railway/warn_adjudication_pack.py --rerender # re-render the sheet only, no fetch
"""
import json
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_reference_set as W                                    # noqa: E402
from recall_goldset import format_interval                        # noqa: E402

PACK_PATH = W.REF_DIR / "us-warn-adjudication-queue.json"
SHEET_PATH = W.REF_DIR / "us-warn-adjudication-queue.md"

# How much there is to read about ONE row. Never how likely it is to be right.
CLEAN = "clean"                  # count exact, date on a published basis, name and source agree
NAME_DIFFERS = "name_differs"    # everything above, but we store a shorter employer string
LOOK_TWICE = "look_twice"        # count, source or state does not line up
RANK = {CLEAN: 0, NAME_DIFFERS: 1, LOOK_TWICE: 2}


def _d(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def count_check(event, jobs):
    """Do the counts match exactly, and if not, by how much. Facts only."""
    components = [c["job_count"] for c in event["component_rows"]]
    total = event["stated_job_count"]
    delta = None if not isinstance(jobs, int) or not isinstance(total, int) \
        else jobs - total
    matches_component = jobs in components
    matches_total = jobs == total
    if matches_total and len(components) == 1:
        verdict = f"exact — {jobs:,}, the whole notice"
    elif matches_total:
        verdict = (f"exact — {jobs:,}, the sum the state published across "
                   f"{len(components)} rows")
    elif matches_component:
        verdict = (f"exact — {jobs:,} is one of the {len(components)} rows the state "
                   f"published under this notice (total {total:,})")
    else:
        verdict = (f"DIFFERS by {delta:+,} — we hold {jobs}, the notice totals {total:,} "
                   f"across rows of {', '.join(str(c) for c in components)}")
    return {
        "exact": bool(matches_component or matches_total),
        "matches_a_published_component_row": bool(matches_component),
        "matches_the_notice_total": bool(matches_total),
        "delta_vs_notice_total": delta,
        "notice_total": total,
        "published_component_counts": components,
        "verdict": verdict,
    }


def date_check(event, row_date):
    """Which date basis the row agrees with.

    WARN publishes two dates for one notice and this repo stores the EFFECTIVE
    one in `layoff_date`. A row whose date is months from the notice date is
    therefore not a mismatch by itself — it is the other basis — so both
    distances are stated and neither is called wrong here.
    """
    row_d, notice_d = _d(row_date), _d(event["notice_date"])
    published = sorted({c["effective_date"] for c in event["component_rows"]
                        if c.get("effective_date")})
    lo, hi = _d(event.get("effective_date_min")), _d(event.get("effective_date_max"))
    on_effective = str(row_date)[:10] in published
    on_notice = bool(row_d and notice_d and row_d == notice_d)
    in_range = bool(row_d and lo and hi and lo <= row_d <= hi)
    d_notice = (row_d - notice_d).days if row_d and notice_d else None
    d_eff = (row_d - lo).days if row_d and lo else None
    if on_effective:
        basis = "effective"
        verdict = (f"agree on the EFFECTIVE basis — our {row_date} is a date the state "
                   f"published as effective for this notice; the notice date "
                   f"{event['notice_date']} is {abs(d_notice)} day(s) "
                   f"{'earlier' if d_notice >= 0 else 'later'}")
    elif on_notice:
        basis = "notice"
        verdict = (f"agree on the NOTICE basis — our {row_date} is the notice date; the "
                   f"state published effective {'/'.join(published) or '(none)'}")
    elif in_range:
        basis = "within_published_effective_range"
        verdict = (f"our {row_date} falls inside the notice's published effective range "
                   f"{event['effective_date_min']}..{event['effective_date_max']} but is "
                   f"not one of the published dates themselves")
    else:
        basis = "neither"
        verdict = (f"our {row_date} is neither the notice date ({d_notice:+d} days) nor a "
                   f"published effective date ({d_eff:+d} days from "
                   f"{event.get('effective_date_min')})"
                   if d_notice is not None and d_eff is not None else
                   f"our {row_date} matches neither published basis")
    return {
        "basis": basis,
        "row_date": str(row_date)[:10],
        "notice_date": event["notice_date"],
        "published_effective_dates": published,
        "days_from_notice_date": d_notice,
        "days_from_earliest_effective_date": d_eff,
        "verdict": verdict,
    }


def classify(candidate, counts, dates):
    """How much there is to read about THIS row. Three words, no verdict."""
    reasons = []
    if not str(candidate.get("source_type") or "").lower().startswith("warn"):
        reasons.append(f"our row is sourced to {candidate.get('source_type')!r}, not to a "
                       f"WARN notice, so it is not the state's own record of this event")
    if not counts["exact"]:
        reasons.append(counts["verdict"])
    if not candidate.get("state"):
        reasons.append("our row carries no state, so the state test could not be applied")
    if dates["basis"] == "neither":
        reasons.append(dates["verdict"])
    if reasons:
        return LOOK_TWICE, reasons
    if candidate.get("name_differs_from_published"):
        return NAME_DIFFERS, [candidate["name_differs_from_published"]]
    return CLEAN, []


def _query(event, windowed=True):
    """Rows the endpoint serves for this event's own query terms, RIGHT NOW.

    ONE request per term, not one per row, and it goes through the event's own
    query terms because **`/query` has no `id` filter**. An earlier version
    passed `id=` and, since an unknown parameter is simply ignored, got back the
    state's most recent rows and reported "the endpoint no longer serves this
    row id" for every candidate in the sheet. A refetch that cannot find what it
    is looking for must not be rendered as evidence that the row is gone.
    """
    found = {}
    for term in event.get("query_terms") or []:
        params = {"company": term, "state": event["state"], "per_page": 200,
                  "cb": W._cachebust()}
        if windowed:
            params["from"], params["to"] = event["match_window"]
        try:
            payload = W._api("query?" + urllib.parse.urlencode(params)) or {}
        except Exception as exc:                                   # noqa: BLE001
            return {"__error__": f"{type(exc).__name__}: {exc}"}
        for row in payload.get("data") or []:
            found[row.get("id")] = row
        time.sleep(0.15)
    return found


def _name_note(event, stored_name):
    published = event["employer_published"]
    if W.clean_published_name(stored_name).lower() == published.lower():
        return None
    return (f"we store the employer as {stored_name!r}; the state publishes it as "
            f"{published!r}")


def build_pack(manifest=None, measurement=None, refetch=True):
    """The pack. Pure given the two documents and the fetcher, so tests can drive it."""
    if manifest is None:
        manifest = json.loads(W.MANIFEST_PATH.read_text(encoding="utf-8"))
    if measurement is None:
        measurement = json.loads(W.WARN_MEASUREMENT_PATH.read_text(encoding="utf-8"))
    by_id = {e["reference_row_id"]: e
             for e in manifest["reference_events"] + manifest["large_event_census"]}

    entries, no_candidate = [], []
    for stratum in ("primary", "large_census"):
        for result in measurement["results"][stratum]:
            ev = by_id[result["id"]]
            if result["match_decision"] == "matched":
                continue
            if not result["candidates"]:
                rows = _query(ev, windowed=False) if refetch else {}
                error = rows.pop("__error__", None) if isinstance(rows, dict) else None
                no_candidate.append(_no_candidate_entry(ev, stratum, rows, error))
                continue
            live = _query(ev) if refetch else {}
            error = live.pop("__error__", None)
            candidates = []
            for cand in result["candidates"]:
                counts = count_check(ev, cand["job_count"])
                dates = date_check(ev, cand["row_date"])
                enriched = dict(cand)
                enriched["name_differs_from_published"] = _name_note(
                    ev, cand["company_name"])
                look, reasons = classify(enriched, counts, dates)
                now = live.get(cand["tracker_row_id"])
                candidates.append({
                    "tracker_row_id": cand["tracker_row_id"],
                    "tracker_event_id": cand["tracker_event_id"],
                    "tier": cand["tier"],
                    "company_name": cand["company_name"],
                    "job_count": cand["job_count"],
                    "row_date": cand["row_date"],
                    "state": cand["state"],
                    "source_type": cand["source_type"],
                    "source_name": cand["source_name"],
                    "source_url": cand["source_url"],
                    "count_check": counts,
                    "date_check": dates,
                    "name_note": enriched["name_differs_from_published"],
                    "look": look,
                    # Every reason names THIS row and no other. Nothing in this
                    # list may mention another candidate.
                    "look_twice_reasons": reasons,
                    "measurer_flags": cand["flags"],
                    "live_now": ({k: now.get(k) for k in
                                  ("company_name", "job_count", "layoff_date",
                                   "announcement_date", "state", "source_type",
                                   "source_name", "source_url", "excerpt")}
                                 if now else
                                 {"refetch_error": error or "not returned by a re-query "
                                                            "of this event's own terms"}),
                })
            candidates.sort(key=lambda c: (RANK[c["look"]], c["tier"] != "exact",
                                           c["row_date"]))
            lead = candidates[0]
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
                "machine_tier": result["machine_tier"],
                "lead_row_id": lead["tracker_row_id"],
                "lead_look": lead["look"],
                "other_row_ids": [c["tracker_row_id"] for c in candidates[1:]],
                "candidates": candidates,
            })
    _mark_rows_claimed_twice(entries)
    entries.sort(key=lambda e: (e["stratum"] != "primary", RANK[e["lead_look"]],
                                len(e["other_row_ids"]), e["state"],
                                e["notice_says_date"]))
    no_candidate.sort(key=lambda e: (e["stratum"] != "primary", e["state"],
                                     e["notice_says_date"]))
    return manifest, measurement, entries, no_candidate


def _mark_rows_claimed_twice(entries):
    """One tracker row proposed for two DIFFERENT reference events.

    Spirit Airlines filed several Florida notices on 2026-05-04 and we hold one
    row per site, so the same row can lead two reference events. At most one of
    them can be it, and an editor who accepts both has counted one row twice.

    This does NOT break the per-row rule. The statement added to a row names
    OTHER REFERENCE EVENTS, never another candidate row, and it is added to
    every row it is true of rather than summarised on one of them.
    """
    claims = {}
    for entry in entries:
        for cand in entry["candidates"]:
            claims.setdefault(cand["tracker_row_id"], set()).add(
                entry["reference_row_id"])
    for entry in entries:
        for cand in entry["candidates"]:
            others = sorted(claims[cand["tracker_row_id"]] - {entry["reference_row_id"]})
            if not others:
                continue
            cand["also_proposed_for"] = others
            cand["look_twice_reasons"].append(
                f"row `{cand['tracker_row_id']}` is also proposed for "
                f"{len(others)} other reference event(s) — {', '.join(others)} — and "
                f"at most one of them can be it")
            cand["look"] = LOOK_TWICE
        entry["candidates"].sort(key=lambda c: (RANK[c["look"]], c["tier"] != "exact",
                                                c["row_date"]))
        lead = entry["candidates"][0]
        entry["lead_row_id"] = lead["tracker_row_id"]
        entry["lead_look"] = lead["look"]
        entry["other_row_ids"] = [c["tracker_row_id"] for c in entry["candidates"][1:]]


def _no_candidate_entry(ev, stratum, rows, error):
    """An event the rule proposes nothing for, with what we hold at ANY date.

    The DATE is widened and the NAME is not. `/query?company=` is a substring
    LIKE, so this event's own term `Wood` returns `Oakwood Worldwide` once the
    window stops excluding it; the rule's own `name_matches` token-prefix test is
    therefore still applied here. Widening both at once produces a section full
    of other employers, which reads as evidence and is not.
    """
    keep = [r for r in (rows or {}).values()
            if any(W.name_matches(a, r.get("company_name") or "")
                   for a in ev["employer_aliases"])]
    held = []
    for row in sorted(keep, key=lambda r: str(r.get("layoff_date"))):
        held.append({
            "tracker_row_id": row.get("id"),
            "tracker_event_id": row.get("event_id"),
            "company_name": row.get("company_name"),
            "job_count": row.get("job_count"),
            "layoff_date": row.get("layoff_date"),
            "announcement_date": row.get("announcement_date") or None,
            "state": row.get("state"),
            "source_type": row.get("source_type"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "excerpt": row.get("excerpt"),
            "count_check": count_check(ev, row.get("job_count")),
            "date_check": date_check(ev, row.get("layoff_date")),
            "in_the_match_window": bool(
                _d(row.get("layoff_date"))
                and _d(ev["match_window"][0]) <= _d(row.get("layoff_date"))
                <= _d(ev["match_window"][1])),
        })
    return {
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
        "query_terms": ev.get("query_terms") or [],
        "rows_for_this_employer_at_any_date": held,
        "refetch_error": error,
    }


# ---------------------------------------------------------------------------
# The range, stated before the first decision.
# ---------------------------------------------------------------------------
def arithmetic(measurement, entries, no_candidate):
    """Four arithmetics over the 100-event primary sample.

    Arithmetic, not targets, and none of them is a prediction about how the
    entries should go. The owner should know the spread before spending
    attention on it.
    """
    prim = measurement["results"]["primary"]
    n = len(prim)
    confirmed = sum(1 for r in prim if r["match_decision"] == "matched")
    pending = [e for e in entries if e["stratum"] == "primary"]
    clean = sum(1 for e in pending if e["lead_look"] == CLEAN)
    named = sum(1 for e in pending if e["lead_look"] == NAME_DIFFERS)
    unresolved = len([e for e in no_candidate if e["stratum"] == "primary"])
    return {
        "denominator": n,
        "editor_confirmed_today": confirmed,
        "pending_events": len(pending),
        "lead_clean": clean,
        "lead_name_differs": named,
        "lead_look_twice": len(pending) - clean - named,
        "no_candidate_events": unresolved,
        "rows": [
            ("every pending event accepted, and the event with no candidate row "
             "resolved in our favour too", confirmed + len(pending) + unresolved, n),
            ("every pending event accepted, the event with no candidate row not",
             confirmed + len(pending), n),
            ("only the events whose proposed row agrees on count, on date basis and "
             "on employer name, and is not also proposed for another notice",
             confirmed + clean, n),
            ("nothing accepted (the figure as it stands today)", confirmed, n),
        ],
    }


# ---------------------------------------------------------------------------
# The sheet.
# ---------------------------------------------------------------------------
def _md(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _anchor(idx, entry):
    slug = "".join(c if c.isalnum() else "-" for c in
                   entry["notice_says_employer"].lower())[:50].strip("-")
    return f"#{idx}-{entry['state'].lower()}-{slug}"


def _count_cell(cand):
    c = cand["count_check"]
    if c["matches_the_notice_total"]:
        return f"**{cand['job_count']:,}** = notice total, exact"
    if c["matches_a_published_component_row"]:
        return (f"**{cand['job_count']:,}** = one published row, exact "
                f"(notice total {c['notice_total']:,})")
    if c["delta_vs_notice_total"] is None:
        return f"**{cand['job_count']}** vs {c['notice_total']:,} — not comparable"
    return (f"**{cand['job_count']}** vs {c['notice_total']:,}, "
            f"off by {c['delta_vs_notice_total']:+,}")


def _date_cell(cand):
    d = cand["date_check"]
    if d["basis"] == "effective":
        return f"{d['row_date']} = published effective date"
    if d["basis"] == "notice":
        return f"{d['row_date']} = notice date"
    if d["basis"] == "within_published_effective_range":
        return f"{d['row_date']} inside published effective range"
    if d["days_from_notice_date"] is None:
        return f"{d['row_date']}, neither basis"
    return (f"{d['row_date']}, neither basis "
            f"({d['days_from_notice_date']:+d} d from notice)")


def _look_cell(cand):
    if cand["look"] == CLEAN:
        return f"nothing — row `{cand['tracker_row_id']}` lines up on every field checked"
    # Joined with a separator, and every one of these describes the SAME row.
    # Without it two facts about one row read as one run-on sentence, which is
    # how the pooled line looked in the first place.
    return "; ".join(_md(r) for r in cand["look_twice_reasons"])


def render_sheet(manifest, measurement, entries, no_candidate, arith, built_at):
    out = []
    a = out.append
    a("# US WARN reference set — adjudication sheet")
    a("")
    a(f"Built `{built_at}` from a measurement taken `{measurement['measured_at']}`. "
      "**Rebuild it before deciding** (`python3 railway/warn_adjudication_pack.py "
      "--write`) — it reads live data and live data moves.")
    a("")
    a(f"Reference set: `{manifest['reference_set_id']}`. Definition: "
      f"[`{manifest['definition_document']}`](../../{manifest['definition_document']}). "
      "Nothing in this set is published anywhere, and nothing in it touches the SEC "
      "Item 2.05 figure.")
    a("")
    a(f"**{len(entries)} events are pending** across both strata, carrying "
      f"{sum(len(e['candidates']) for e in entries)} candidate rows between them. "
      f"{len(no_candidate)} event(s) have no candidate row at all and are dealt with "
      "first, below, because they are a different question.")
    a("")

    a("## The range, before you start")
    a("")
    a(f"The primary sample is {arith['denominator']} events. "
      f"{arith['editor_confirmed_today']} are editor-confirmed today. Of the "
      f"{arith['pending_events']} pending, **{arith['lead_clean']}** have a proposed row "
      f"that agrees on count, on date basis and on employer name and is proposed for "
      f"no other notice; "
      f"**{arith['lead_name_differs']}** agree on count and date basis but we store a "
      f"shorter employer string than the state publishes; **{arith['lead_look_twice']}** "
      f"have something else to read. "
      f"**{arith['no_candidate_events']}** has no proposed row.")
    a("")
    a("Four arithmetics. They are arithmetic, not targets, and none of them is a "
      "prediction about how the entries below should go:")
    a("")
    for label, k, n in arith["rows"]:
        a(f"- {label}: **{format_interval(k, n)}**")
    a("")
    a("The 500-plus census is reported separately and is never pooled with the sample, "
      "so deciding a census event does not move any of the four figures above.")
    a("")

    # ---- the events with no candidate row, first and on their own -----------
    for entry in no_candidate:
        a(_render_no_candidate(entry))

    a("## The index")
    a("")
    a("**Every line below describes exactly ONE candidate row, named by its id.** An "
      "event with four candidates does not get four clauses on one line: it gets one "
      "line for the row the rule proposes first, carrying only that row's evidence, "
      "and the ids of the others beside it carrying none of theirs. Each of those rows "
      "has its own block in the section below. That is not a formatting preference — on "
      "2026-08-12 a pooled summary line on the SEC sheet described a co-proposed row and "
      "a correct Dow row was rejected because of it.")
    a("")
    a("Ordering is by how much there is to read, not by how likely an accept is. The "
      "events where every field lines up come first because they are quick to CHECK.")
    a("")
    a("Nothing here is pre-ticked, and no line states a preferred outcome.")
    a("")
    a("| # | the notice | notified | our row | count | dates | look twice — this row only "
      "| other rows in window |")
    a("|---:|---|---:|---|---|---|---|---|")
    for i, e in enumerate(entries, 1):
        lead = e["candidates"][0]
        others = (", ".join(f"`{r}`" for r in e["other_row_ids"])
                  if e["other_row_ids"] else "none")
        a(f"| {i} | [{_md(e['notice_says_employer'])[:44]}]({_anchor(i, e)}) "
          f"({e['state']}, {e['notice_says_date']}) | {e['notice_says_job_count']:,} "
          f"| `{lead['tracker_row_id']}` (event {lead['tracker_event_id']}) "
          f"| {_count_cell(lead)} | {_date_cell(lead)} | {_look_cell(lead)} "
          f"| {others} |")
    a("")
    a("## Recording a decision")
    a("")
    a("Separate program, network-free, and it refuses a decision with no name, no "
      "reason or no row id on it. Running the same decision twice records it once; a "
      "different decision on an already-decided event is refused and told to revert "
      "first; `--revert` restores the event exactly, including a key that was absent.")
    a("")
    a("```")
    a("python3 railway/warn_adjudicate.py --accept <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...")
    a("python3 railway/warn_adjudicate.py --reject <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...")
    a("python3 railway/warn_adjudicate.py --revert <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...'")
    a("python3 railway/warn_adjudicate.py --verify")
    a("```")
    a("")
    a("---")
    a("")
    for i, e in enumerate(entries, 1):
        out.extend(_render_entry(i, e))
    return "\n".join(out) + "\n"


def _render_no_candidate(entry):
    L = []
    a = L.append
    a(f"## The event with no candidate row: {_md(entry['notice_says_employer'])} "
      f"({entry['state']})")
    a("")
    a(f"`{entry['reference_row_id']}` — stratum `{entry['stratum']}`, size band "
      f"`{entry['size_band']}`, currently `not_matched`. **This is its own decision, not "
      "a row in the list below.** The matching rule proposes nothing for it, so there is "
      "no candidate to accept or reject in the ordinary way; what follows is every row "
      "we hold for this employer at ANY date, fetched with no window applied.")
    a("")
    a("**What the state published** (open the source and check it; do not take this "
      "file's word for it):")
    a("")
    a(f"- notice date **{entry['notice_says_date']}**, effective "
      f"{entry['notice_says_effective'][0]}..{entry['notice_says_effective'][1]}")
    a(f"- **{entry['notice_says_job_count']:,}** affected across "
      f"{len(entry['notice_published_rows'])} published row(s)")
    for row in entry["notice_published_rows"]:
        a(f"  - {_md(str(row['employer_published']))} — {row['job_count']} — "
          f"{row.get('location') or 'no location published'} — effective "
          f"{row.get('effective_date')} — `{row.get('source_locator')}`")
    a(f"- source: <{entry['official_source_url']}>")
    a(f"- the rule's match window: {entry['match_window'][0]} .. "
      f"{entry['match_window'][1]}")
    a("")
    if entry.get("refetch_error"):
        a(f"**The live query failed**: {entry['refetch_error']}. That is UNKNOWN, not "
          "evidence that we hold nothing. Do not decide this event on this build.")
        a("")
    elif not entry["rows_for_this_employer_at_any_date"]:
        a("**No row of any kind, at any date, for this employer.**")
        a("")
    for row in entry["rows_for_this_employer_at_any_date"]:
        a(f"**What we hold — row `{row['tracker_row_id']}` (event "
          f"`{row['tracker_event_id']}`)**")
        a("")
        a("| | the state's notice | our row `%s` |" % row["tracker_row_id"])
        a("|---|---|---|")
        a(f"| employer | {_md(entry['notice_says_employer'])} "
          f"| {_md(row['company_name'])} |")
        a(f"| count | {entry['notice_says_job_count']:,} | {row['job_count']} |")
        a(f"| notice date | {entry['notice_says_date']} | "
          f"{row['announcement_date'] or '(we store none)'} |")
        a(f"| effective date | {entry['notice_says_effective'][0]}"
          f"..{entry['notice_says_effective'][1]} | {row['layoff_date']} |")
        a(f"| state | {entry['state']} | {row['state']} |")
        a(f"| source | {_md(entry['official_source_url'])} | `{row['source_type']}` / "
          f"`{row['source_name']}` |")
        a(f"| the URL we cite | — | <{row['source_url']}> |")
        a("")
        a(f"- count: {_md(row['count_check']['verdict'])}")
        a(f"- dates: {_md(row['date_check']['verdict'])}")
        a(f"- inside the rule's match window: "
          f"**{'yes' if row['in_the_match_window'] else 'no'}**")
        a("")
        a("> " + _md(row["excerpt"] or "(no excerpt stored)"))
        a("")
    a("Two decisions are available and this file states neither as preferred:")
    a("")
    a("```")
    ids = " ".join(str(r["tracker_row_id"])
                   for r in entry["rows_for_this_employer_at_any_date"]) or "<row id>"
    a(f"python3 railway/warn_adjudicate.py --accept {entry['reference_row_id']} \\")
    a(f"    --reviewed-by 'NAME' --reason 'WHY' --row-ids {ids}")
    a(f"python3 railway/warn_adjudicate.py --reject {entry['reference_row_id']} \\")
    a(f"    --reviewed-by 'NAME' --reason 'WHY' --row-ids {ids}")
    a("```")
    a("")
    a("Accepting it is a statement that the row above IS this notice and that the "
      "matching rule's window missed it. Rejecting it is a statement that it is not, or "
      "that it cannot be told apart. The window was deliberately not widened to catch "
      "it, so **no decision here changes the rule** — the rule is frozen in the "
      "definition document and changing it is a separate, evidenced amendment.")
    a("")
    a("---")
    a("")
    return "\n".join(L)


def _render_entry(i, e):
    L = []
    a = L.append
    a(f"## {i}. {_md(e['notice_says_employer'])} ({e['state']})")
    a("")
    a(f"`{e['reference_row_id']}` — currently `not_matched`, stratum `{e['stratum']}`, "
      f"size band `{e['size_band']}`")
    a("")
    a("**What the state published** (open the source and check it; do not take this "
      "file's word for it):")
    a("")
    a(f"- notice date **{e['notice_says_date']}**, effective "
      f"{e['notice_says_effective'][0]}..{e['notice_says_effective'][1]}")
    a(f"- **{e['notice_says_job_count']:,}** affected across "
      f"{len(e['notice_published_rows'])} published row(s)")
    for row in e["notice_published_rows"]:
        a(f"  - {_md(str(row['employer_published']))} — {row['job_count']} — "
          f"{row.get('location') or 'no location published'} — effective "
          f"{row.get('effective_date')} — `{row.get('source_locator')}`")
    a(f"- source: <{e['official_source_url']}>")
    a(f"- the rule's match window: {e['match_window'][0]} .. {e['match_window'][1]}")
    a("")
    a(f"**{len(e['candidates'])} candidate row(s).** Each block below is one row and "
      "says nothing about any other.")
    a("")
    for cand in e["candidates"]:
        a(f"### row `{cand['tracker_row_id']}` — event `{cand['tracker_event_id']}` — "
          f"tier `{cand['tier']}`")
        a("")
        a("| | the state's notice | our row `%s` |" % cand["tracker_row_id"])
        a("|---|---|---|")
        a(f"| employer | {_md(e['notice_says_employer'])} "
          f"| {_md(cand['company_name'])} |")
        a(f"| count | {e['notice_says_job_count']:,} | {cand['job_count']} |")
        a(f"| notice date | {e['notice_says_date']} | (we do not store a WARN notice "
          "date; our date is the effective one) |")
        a(f"| effective date | {e['notice_says_effective'][0]}"
          f"..{e['notice_says_effective'][1]} | {cand['row_date']} |")
        a(f"| state | {e['state']} | {cand['state']} |")
        a(f"| source | the state's own publication | `{cand['source_type']}` / "
          f"`{cand['source_name']}` |")
        a(f"| the URL we cite | <{e['official_source_url']}> | "
          f"<{cand['source_url']}> |")
        a("")
        a(f"- **count**: {_md(cand['count_check']['verdict'])}")
        a(f"- **dates**: {_md(cand['date_check']['verdict'])}")
        if cand["name_note"]:
            a(f"- **employer name**: {_md(cand['name_note'])}")
        else:
            a("- **employer name**: matches the state's published string")
        live = cand["live_now"]
        if live.get("refetch_error"):
            a(f"- **re-fetch**: {_md(live['refetch_error'])} — this row could not be "
              "confirmed live, which is UNKNOWN, not a reason to reject")
        else:
            a(f"- **live now**: {_md(str(live.get('company_name')))} — "
              f"{live.get('job_count')} — {live.get('layoff_date')} — "
              f"`{live.get('source_type')}`")
            if live.get("excerpt"):
                a("")
                a("  > " + _md(live["excerpt"]))
                a("")
        if cand["look"] == CLEAN:
            a(f"- **nothing to look twice at on row `{cand['tracker_row_id']}`** — count, "
              "date basis, employer name, state and source all line up. That is a fact "
              "about this row, not a verdict on it.")
        else:
            for reason in cand["look_twice_reasons"]:
                a(f"- **LOOK TWICE at row `{cand['tracker_row_id']}`:** {_md(reason)}")
        a("")
    a("```")
    ids = " ".join(str(c["tracker_row_id"]) for c in e["candidates"])
    a(f"python3 railway/warn_adjudicate.py --accept {e['reference_row_id']} \\")
    a(f"    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: {ids}>")
    a(f"python3 railway/warn_adjudicate.py --reject {e['reference_row_id']} \\")
    a(f"    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: {ids}>")
    a("```")
    a("")
    a("---")
    a("")
    return L


def rerender():
    """Rewrite the .md from the committed .json, fetching nothing.

    A wording or layout fix to the sheet should not cost 500 requests to the
    host it reports on, and re-fetching would silently change the evidence
    underneath a formatting change - two edits in one diff, one of them
    unreviewed. The evidence is whatever the last --write recorded, and the
    header still carries that build's timestamp so a stale sheet says so.
    """
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    manifest = {"reference_set_id": pack["reference_set_id"],
                "definition_document": pack["definition_document"]}
    measurement = {"measured_at": pack["measured_at"]}
    SHEET_PATH.write_text(
        render_sheet(manifest, measurement, pack["entries"], pack["no_candidate"],
                     pack["arithmetic"], pack["built_at"]),
        encoding="utf-8")
    print(f"sheet re-rendered from {PACK_PATH.name} (nothing fetched): {SHEET_PATH}")


def write_pack():
    built_at = W._utc_now()
    manifest, measurement, entries, no_candidate = build_pack()
    arith = arithmetic(measurement, entries, no_candidate)
    PACK_PATH.write_text(json.dumps({
        "note": ("Adjudication queue for the US WARN reference set. Every statement is "
                 "attributed to the ONE candidate row it describes, by id; no line in "
                 "the sheet summarises more than one row. See the module docstring for "
                 "why. Nothing here is a decision and no field states a preferred "
                 "outcome."),
        "reference_set_id": manifest["reference_set_id"],
        "definition_document": manifest["definition_document"],
        "built_at": built_at,
        "measured_at": measurement["measured_at"],
        "pending_events": len(entries),
        "pending_candidate_rows": sum(len(e["candidates"]) for e in entries),
        "events_with_no_candidate_row": len(no_candidate),
        "arithmetic": arith,
        "entries": entries,
        "no_candidate": no_candidate,
    }, indent=2) + "\n", encoding="utf-8")
    SHEET_PATH.write_text(
        render_sheet(manifest, measurement, entries, no_candidate, arith, built_at),
        encoding="utf-8")
    print(f"pack written:  {PACK_PATH}")
    print(f"sheet written: {SHEET_PATH}")
    print(f"{len(entries)} events pending, "
          f"{sum(len(e['candidates']) for e in entries)} candidate rows, "
          f"{len(no_candidate)} with no candidate row")
    return entries


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if "--write" in argv:
        write_pack()
        return 0
    if "--rerender" in argv:
        rerender()
        return 0
    _, measurement, entries, no_candidate = build_pack(refetch=False)
    arith = arithmetic(measurement, entries, no_candidate)
    print(f"{len(entries)} events pending, "
          f"{sum(len(e['candidates']) for e in entries)} candidate rows, "
          f"{len(no_candidate)} with no candidate row (dry run, nothing written)")
    for label, k, n in arith["rows"]:
        print(f"  {format_interval(k, n):48s}  {label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
