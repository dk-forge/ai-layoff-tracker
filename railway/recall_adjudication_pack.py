#!/usr/bin/env python3
"""Build the adjudication pack: one evidence block per candidate, from primary sources.

WHY THIS IS A SCRIPT AND NOT A PASTED TABLE
-------------------------------------------
`recall_goldset.measure()` reports which gold events have newly acquired a
tracker row and refuses to count them: "a machine must not promote its own
recall". The decision is the editor's. What the editor needs in order to make
29 of them quickly is not the manifest's own opinion — the manifest is the thing
being corrected — but the two primary artefacts side by side:

    * the FILING's own sentence stating the count, fetched from SEC EDGAR here;
    * OUR row as the public `/query` endpoint currently serves it.

Both are re-fetched every time this runs. Nothing in the pack is copied from
`match_notes`, from `count_evidence` or from any earlier measurement, because a
sheet that quotes the manifest at the person auditing the manifest is a sheet
that can only ever agree with itself. The manifest's own strings ARE carried,
clearly labelled `manifest_says_*`, so a disagreement between the manifest and
the filing is visible rather than hidden.

WHAT IT DOES NOT DO
-------------------
It does not decide, rank by desirability, or recommend. `flags` are statements
of fact about the pair ("the count differs by -200", "the URL is a different
accession") and the ordering is by how much there is to look at, not by how
likely an accept is. Recording a decision is `recall_adjudicate.py`, a separate,
network-free module, for the same reason `close_incident` refuses to re-read the
site it is about.

READ-ONLY. Public `/query` GETs and SEC EDGAR GETs. No key, no model, no write
to anything live; the only file written is the committed pack.

USAGE
    python3 railway/recall_adjudication_pack.py            # print a summary
    python3 railway/recall_adjudication_pack.py --write    # write the pack + sheet
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import recall_goldset as rg

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
PACK_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
             / "sec-item-205-adjudication-queue.json")
SHEET_PATH = PACK_PATH.with_suffix(".md")

# SEC asks automated readers to identify themselves with a contact address.
# This is the project's published contact, the same one the health digest mails.
SEC_UA = "AiLayoffTracker/1.0 (info@asktherecruiter.com)"

# A stored announcement_date this far from the filing date is called out. Not a
# verdict: this repo distinguishes the FILING basis (announcement_date) from the
# EFFECTIVE basis (layoff_date), and an effective date months after the filing
# is normal and correct. Five days covers a filing that follows a Friday board
# action or a press release by a weekend; beyond that the editor should look.
ANNOUNCEMENT_SKEW_DAYS = 5

# Flags that mean "two different things may have been matched", weighted so they
# sort to the bottom whatever else is true of the row.
HARD = 100
SOFT = 1


def _get(url, ua, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": ua,
                                               "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def strip_html(raw):
    """The filing as readable text. Deliberately crude and lossy in one direction
    only: it may join sentences, it never invents characters."""
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    for bad, good in ((" ", " "), ("’", "'"), ("‘", "'"),
                      ("“", '"'), ("”", '"'), ("—", " - "),
                      ("–", "-")):
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip()


def sentences_with_count(text, n):
    """Every sentence of the filing that states the number `n`.

    The number must not be part of a longer number: a bare `re.search("400")`
    finds 2,400 and 4,003 and reports the filing as stating a count it does not
    state. That is the same class of error `_count_in_text` exists to refuse.
    """
    if n is None:
        return []
    forms = {str(n), f"{n:,}"}
    out = []
    for sent in re.split(r"(?<=[.;])\s+(?=[A-Z(\"])", text):
        if any(re.search(r"(?<![\d,.])" + re.escape(f) + r"(?![\d,.])", sent)
               for f in forms):
            out.append(sent.strip())
    return out


def accession_of(url):
    """The 18-digit EDGAR accession embedded in an Archives path, or None."""
    m = re.search(r"/(\d{18})/", (url or "").replace("-", ""))
    return m.group(1) if m else None


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def fetch_rows(manifest, fetch=None, sleep=None):
    """Every live row reachable from any gold alias, keyed by tracker event id.

    Deduplicated by ROW id: an event with two aliases returns the same rows
    twice, and a pair counted twice reads as two independent corroborations.
    """
    fetch = fetch or (lambda u: _get(u, rg.UA))
    sleep = time.sleep if sleep is None else sleep
    by_event, failures = {}, []
    for ev in manifest["reference_events"]:
        for alias in ev.get("employer_aliases") or []:
            url = rg.BASE + "query?" + urllib.parse.urlencode(
                {"company": alias, "per_page": 100, "cb": rg._cachebust()})
            try:
                payload = json.loads(fetch(url)) or {}
            except Exception as exc:                          # noqa: BLE001
                failures.append(f"{alias}: {type(exc).__name__}: {exc}")
                continue
            for row in payload.get("data") or []:
                by_event.setdefault(row.get("event_id"), {})[row.get("id")] = row
            sleep(0.15)
    return ({eid: [rows[i] for i in sorted(rows)] for eid, rows in by_event.items()},
            failures)


def fetch_filings(events, fetch=None, sleep=None):
    """The filing text and its count sentences, per gold event."""
    fetch = fetch or (lambda u: _get(u, SEC_UA))
    sleep = time.sleep if sleep is None else sleep
    out = {}
    for ev in events:
        url = ev["official_source_url"]
        try:
            text = strip_html(fetch(url))
        except Exception as exc:                              # noqa: BLE001
            out[ev["reference_row_id"]] = {
                "url": url,
                "unreadable": f"{type(exc).__name__}: {exc}",
                "count_sentences": None}
            sleep(0.4)
            continue
        out[ev["reference_row_id"]] = {
            "url": url,
            "chars": len(text),
            "count_sentences": sentences_with_count(text, ev.get("stated_job_count")),
            "text": text}
        sleep(0.4)
    return out


def collapsed_duplicates(manifest):
    """{accession of a filing the manifest collapsed: the accession it duplicates}.

    The gold set already recorded, in 2026-08-01, that some announcements were
    filed twice. A row citing the SECOND accession is citing the same event by
    the manifest's own finding, and saying only "a different accession" about it
    would send the editor to re-derive a fact the manifest already holds.
    """
    out = {}
    for dup in manifest.get("collapsed_duplicate_filings") or []:
        decision = str(dup.get("decision") or "")
        if decision.startswith("duplicate_of:"):
            out[(dup.get("accession") or "").replace("-", "")] = \
                decision.split(":", 1)[1].replace("-", "")
    return out


def compare(event, rows, filing, also_claimed_by, duplicates=None):
    """One gold event against the rows proposed for it. Facts only, no verdict."""
    duplicates = duplicates or {}
    gold_acc = accession_of(event["official_source_url"])
    filed = _date(event["filing_date"])
    stated = event.get("stated_job_count")
    text = (filing or {}).get("text") or ""
    out = []
    for row in rows:
        flags, weight = [], 0
        count = row.get("job_count")
        delta = None if count is None or stated is None else count - stated
        our_sentences = []
        if delta:
            flags.append(f"COUNT differs by {delta:+d}: we hold {count}, "
                         f"the filing states {stated}")
            weight += HARD
            our_sentences = sentences_with_count(text, count)
            if our_sentences:
                flags.append("the filing states our number too - read both sentences")
        if row.get("source_type") != "8K":
            flags.append(f"SOURCE is {row.get('source_type')!r}, not the 8-K")
            weight += HARD
        row_acc = accession_of(row.get("source_url"))
        if not row_acc:
            flags.append("the URL we cite is not an EDGAR archive path")
            weight += HARD
        elif gold_acc and row_acc != gold_acc:
            if duplicates.get(row_acc) == gold_acc:
                flags.append(
                    "the URL we cite is a different accession, and the gold set's own "
                    "`collapsed_duplicate_filings` records it as the same announcement "
                    "filed twice - not a different event by the manifest's own finding")
                weight += SOFT
            else:
                flags.append("the URL we cite is a DIFFERENT accession than the gold filing")
                weight += HARD
        name_tokens = rg._tokens(row.get("company_name"))
        if not any(rg._tokens(a) == name_tokens for a in event["employer_aliases"]):
            flags.append("NAME matches by prefix, not exactly: we hold "
                         f"{row.get('company_name')!r} against alias(es) "
                         + ", ".join(repr(a) for a in event["employer_aliases"]))
            weight += SOFT
        announced, effective = _date(row.get("announcement_date")), _date(row.get("layoff_date"))
        d_ann = (announced - filed).days if announced and filed else None
        d_eff = (effective - filed).days if effective and filed else None
        if d_ann is None:
            flags.append("we hold no announcement_date, so the FILING basis cannot be "
                         "compared; only the effective date is available")
            weight += SOFT
        elif abs(d_ann) > ANNOUNCEMENT_SKEW_DAYS:
            flags.append(f"ANNOUNCEMENT date is {d_ann:+d} days from the filing date")
            weight += SOFT if abs(d_ann) <= 45 else HARD
        for other in also_claimed_by.get(row.get("event_id"), []):
            if other != event["reference_row_id"]:
                flags.append(f"this SAME tracker event {row.get('event_id')} is also "
                             f"proposed for gold event {other}")
                weight += HARD
        out.append({
            "tracker_event_id": row.get("event_id"),
            "tracker_row_id": row.get("id"),
            "company_name": row.get("company_name"),
            "job_count": count,
            "count_delta": delta,
            "layoff_date": row.get("layoff_date"),
            "announcement_date": row.get("announcement_date"),
            "days_announcement_minus_filing": d_ann,
            "days_effective_minus_filing": d_eff,
            "source_type": row.get("source_type"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "cites_the_gold_accession": bool(row_acc and gold_acc and row_acc == gold_acc),
            "verification_level": row.get("verification_level"),
            "permalink": row.get("permalink"),
            "our_excerpt": row.get("excerpt"),
            "filing_sentences_stating_our_count": our_sentences,
            "flags": flags,
            "weight": weight,
        })
    if len(out) > 1:
        for rec in out:
            rec["flags"].append(f"{len(out)} different tracker rows are proposed for "
                                f"this one gold event - at most one can be it")
            rec["weight"] += HARD
    return out


def build(measurement=None, manifest=None, rows_by_event=None, filings=None):
    """The pack. Pure, given the three fetched inputs, so the tests can drive it."""
    manifest = manifest or rg.load_manifest()
    measurement = measurement or rg.measure()
    by_id = {e["reference_row_id"]: e for e in manifest["reference_events"]}
    candidates = measurement["candidates_needing_adjudication"]

    also_claimed_by = {}
    for cand in candidates:
        for eid in cand["new_tracker_event_ids"]:
            also_claimed_by.setdefault(eid, []).append(cand["id"])

    if rows_by_event is None:
        rows_by_event, _ = fetch_rows(manifest)
    if filings is None:
        filings = fetch_filings([by_id[c["id"]] for c in candidates])

    entries = []
    for cand in candidates:
        event = by_id[cand["id"]]
        filing = filings.get(cand["id"]) or {}
        rows = [r for eid in cand["new_tracker_event_ids"]
                for r in rows_by_event.get(eid, [])]
        compared = compare(event, rows, filing, also_claimed_by,
                           collapsed_duplicates(manifest))
        entries.append({
            "reference_row_id": event["reference_row_id"],
            "filer": event["filer"],
            "cik": event["cik"],
            "accession": event["accession"],
            "filing_date": event["filing_date"],
            "stated_job_count": event.get("stated_job_count"),
            "official_source_url": event["official_source_url"],
            "employer_aliases": event["employer_aliases"],
            "match_window": event["match_window"],
            "current_match_decision": event.get("match_decision"),
            "filing_says": filing.get("count_sentences"),
            "filing_unreadable": filing.get("unreadable"),
            "manifest_says_count_evidence": event.get("count_evidence"),
            "manifest_says_match_notes": event.get("match_notes"),
            "proposed_tracker_event_ids": cand["new_tracker_event_ids"],
            "rows": compared,
            "weight": sum(r["weight"] for r in compared),
            "flag_count": sum(len(r["flags"]) for r in compared),
        })
    # Least to look at first. Weight, not desirability: a zero-weight entry is
    # one where every fact lines up, which is quick to CHECK, not right to accept.
    entries.sort(key=lambda e: (e["weight"], e["filing_date"]))

    # THE MISSES THAT ARE NOT IN THE QUEUE. Carried in the pack because the first
    # question anyone asks of "29 of 33 recovered" is "and the other four?", and
    # answering it from memory is how a recovered event keeps being called a
    # permanent miss. Every row here matches an alias by the prefix rule with NO
    # window applied, which is deliberately wider than the matching rule: the
    # point is to show what the tracker holds for that employer at any date.
    every_row = [r for rows in rows_by_event.values() for r in rows]
    pending_ids = {c["id"] for c in candidates}
    not_in_queue = []
    for miss in measurement.get("missed_events") or []:
        if miss["id"] in pending_ids:
            continue
        event = by_id[miss["id"]]
        blocked = event.get("excluded_name_prefixes") or []
        held = [r for r in every_row
                if any(rg.name_matches(a, r.get("company_name"))
                       for a in event["employer_aliases"])
                and not any(rg.name_matches(b, r.get("company_name")) for b in blocked)]
        not_in_queue.append({
            "reference_row_id": miss["id"],
            "filer": event["filer"],
            "filing_date": event["filing_date"],
            "stated_job_count": event.get("stated_job_count"),
            "official_source_url": event["official_source_url"],
            "current_match_decision": event.get("match_decision"),
            "manifest_says_match_notes": event.get("match_notes"),
            "already_rejected_event_ids": event.get("rejected_candidate_event_ids") or [],
            "rows_for_this_employer_at_any_date": sorted(
                ({"tracker_event_id": r.get("event_id"),
                  "company_name": r.get("company_name"),
                  "job_count": r.get("job_count"),
                  "layoff_date": r.get("layoff_date"),
                  "announcement_date": r.get("announcement_date"),
                  "source_type": r.get("source_type"),
                  "source_url": r.get("source_url")} for r in held),
                key=lambda r: (str(r["layoff_date"]), r["tracker_event_id"])),
        })
    not_in_queue.sort(key=lambda m: m["filing_date"])
    return {
        "note": ("Evidence pack for the human adjudication of gold events that have newly "
                 "acquired a tracker row. Rebuilt by railway/recall_adjudication_pack.py "
                 "from the live /query endpoint and from SEC EDGAR. It records evidence and "
                 "records NO recommendation. Decisions are made with "
                 "railway/recall_adjudicate.py, which writes the manifest and the ledger."),
        "reference_set_id": manifest.get("reference_set_id"),
        "built_at": rg._utc_now_iso(),
        "measured_at": measurement.get("measured_at"),
        "reference_events": measurement.get("reference_events"),
        "matched_today": measurement.get("matched"),
        "pending": len(entries),
        "if_all_pending_accepted": rg.format_interval(
            (measurement.get("matched") or 0) + len(entries),
            measurement.get("reference_events") or 0),
        "entries": entries,
        "not_in_queue": not_in_queue,
    }


# ---------------------------------------------------------------------------
# The sheet. Markdown, and the reason is that the decision is recorded in this
# repo by a command in this repo: a sheet the editor reads in the same checkout,
# beside the terminal they type into, costs no context switch and diffs against
# the next rebuild. A hosted page would read no better and could not be diffed.
# ---------------------------------------------------------------------------
def _quote(s):
    return "> " + " ".join((s or "").split())


def own_flags(row):
    """The row's OWN discrepancies, minus the one every row in a contested entry carries."""
    return [f for f in row["flags"] if "different tracker rows" not in f]


def contested_summary(rows):
    """Per-ROW attribution for an entry where several rows contest one filing.

    The flags of two rows must never be pooled into one sentence. On 2026-08-12
    the Dow entry's summary line read "we hold 138, the filing states 4500;
    SOURCE is 'news'; the URL we cite is not an EDGAR archive path" — every word
    true of row 149592 and none of it true of row 149616, which held the 4,500
    and cited the gold accession. The detail block said so; the line above it,
    which is what a reader scans 29 times, described the entry by its worst row
    and the event was rejected as a miss we do not hold. A row with nothing
    against it is stated as such, by id, and is never summarised away.
    """
    parts = []
    for row in rows:
        eid = row.get("tracker_event_id")
        own = own_flags(row)
        if own:
            parts.append(f"row {eid}: " + "; ".join(f.split(":")[0] for f in own))
        else:
            parts.append(f"row {eid}: NO discrepancy — count, dates, name and "
                         "accession all line up")
    return (f"**{len(rows)} rows contest this filing, at most one is it** — "
            + " | ".join(parts))


def tier(entry):
    """A description of HOW MUCH there is to check, never of what to conclude.

    Three words, and they are about the reading, not the outcome: an entry where
    every fact lines up is fast to verify and may still be wrong; an entry where
    two rows contest one filing is slow to verify and may still be right.
    """
    if len(entry["rows"]) > 1:
        return contested_summary(entry["rows"])
    if entry["weight"] >= HARD:
        return ("**two things may be conflated** — " +
                "; ".join(f for r in entry["rows"] for f in r["flags"]
                          if f.startswith(("COUNT", "SOURCE", "the URL", "this SAME"))
                          or "different tracker rows" in f)[:180])
    if entry["weight"]:
        return ("one note to read — " +
                "; ".join(f.split(":")[0] for r in entry["rows"] for f in r["flags"])[:120])
    return "every fact lines up — count, dates, name, accession"


def render_sheet(pack):
    L = []
    a = L.append
    a("# SEC Item 2.05 gold set — adjudication sheet")
    a("")
    a(f"Built `{pack['built_at']}` from a measurement taken `{pack['measured_at']}`. "
      f"**Rebuild it before deciding** (`python3 railway/recall_adjudication_pack.py --write`) "
      "— it reads live data and live data moves.")
    a("")
    a(f"**{pack['pending']} events are pending.** Published today: "
      f"{pack['matched_today']} of {pack['reference_events']}.")
    a("")
    a("Three arithmetics, so the range is known before the first decision. They are "
      "arithmetic, not targets, and the middle two are not predictions about how the "
      "entries below should go:")
    a("")
    matched, total = pack["matched_today"], pack["reference_events"]
    clean = sum(1 for e in pack["entries"] if e["weight"] == 0)
    hard = sum(1 for e in pack["entries"] if e["weight"] >= HARD)
    a(f"- every pending event accepted: **{rg.format_interval(matched + pack['pending'], total)}**")
    a(f"- the {hard} with a hard discrepancy rejected, the rest accepted: "
      f"**{rg.format_interval(matched + pack['pending'] - hard, total)}**")
    a(f"- only the {clean} where every fact lines up accepted: "
      f"**{rg.format_interval(matched + clean, total)}**")
    a("")
    a("Nothing here is pre-ticked and nothing here recommends. Each block states what the "
      "filing says, what we hold, and where the two disagree. Ordering is by how much there "
      "is to look at: the entries with no discrepancy come first because they are quick to "
      "CHECK, not because they are right to accept.")
    a("")
    a("Record a decision (see `railway/recall_adjudicate.py --help`):")
    a("")
    a("```")
    a("python3 railway/recall_adjudicate.py --accept <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --event-ids <id> [<id> ...]")
    a("python3 railway/recall_adjudicate.py --reject <reference_row_id> \\")
    a("    --reviewed-by 'Your Name' --reason '...' --event-ids <id> [<id> ...]")
    a("```")
    a("")
    a("| # | gold event | filed | stated | proposed rows | what is there to look at |")
    a("|---:|---|---|---:|---|---|")
    for i, e in enumerate(pack["entries"], 1):
        a(f"| {i} | [{e['filer']}](#{i}-{re.sub(r'[^a-z0-9]+', '-', e['filer'].lower()).strip('-')}) "
          f"| {e['filing_date']} | {e['stated_job_count']:,} "
          f"| {', '.join(str(x) for x in e['proposed_tracker_event_ids'])} "
          f"| {tier(e)} |")
    a("")
    a("---")
    a("")
    for i, e in enumerate(pack["entries"], 1):
        a(f"## {i}. {e['filer']}")
        a("")
        a(f"`{e['reference_row_id']}` — currently `{e['current_match_decision']}`")
        a("")
        a("| | the gold event (SEC) | what we hold |")
        a("|---|---|---|")
        rows = e["rows"]
        first = rows[0] if rows else {}
        a(f"| company | {e['filer']} | "
          + " <br> ".join(f"{r['company_name']} (event {r['tracker_event_id']}, "
                          f"row {r['tracker_row_id']})" for r in rows) + " |")
        a(f"| job count | **{e['stated_job_count']:,}** | "
          + " <br> ".join(f"**{r['job_count']:,}**" if isinstance(r["job_count"], int)
                          else str(r["job_count"]) for r in rows) + " |")
        a(f"| date | {e['filing_date']} (EDGAR file date) | "
          + " <br> ".join(f"announced {r['announcement_date'] or '(none)'}, "
                          f"effective {r['layoff_date'] or '(none)'}" for r in rows) + " |")
        a("| source | 8-K Item 2.05, accession " + e["accession"] + " | "
          + " <br> ".join(f"{r['source_type']}" for r in rows) + " |")
        a(f"| URL | <{e['official_source_url']}> | "
          + " <br> ".join(f"<{r['source_url']}>" for r in rows) + " |")
        a("")
        a("**The filing's own words** (fetched from EDGAR when this sheet was built):")
        a("")
        if e.get("filing_unreadable"):
            a(f"> UNREADABLE: {e['filing_unreadable']} — the filing could not be fetched, so "
              "the count is UNVERIFIED here. Open the URL above before deciding.")
        elif not e["filing_says"]:
            a(f"> The filing's primary document does not state {e['stated_job_count']:,} "
              "anywhere. Open the URL above; the count may live in an exhibit.")
        else:
            for s in e["filing_says"]:
                a(_quote(s))
                a("")
        a("")
        for r in rows:
            a(f"**Our row {r['tracker_row_id']} (event {r['tracker_event_id']}) says:**")
            a("")
            a(_quote(r["our_excerpt"] or "(no excerpt stored)"))
            a("")
            for s in r["filing_sentences_stating_our_count"]:
                a(f"The filing also states our {r['job_count']:,}:")
                a("")
                a(_quote(s))
                a("")
            if r["count_delta"] == 0:
                a("- count matches the filing exactly")
            if r["days_announcement_minus_filing"] == 0:
                a("- announcement date is the filing date")
            elif r["days_announcement_minus_filing"] is not None:
                a(f"- announcement date is {r['days_announcement_minus_filing']:+d} days "
                  "from the filing date")
            if r["days_effective_minus_filing"] is not None:
                a(f"- effective date is {r['days_effective_minus_filing']:+d} days from the "
                  "filing date (the effective basis, which is a different question)")
            if r["cites_the_gold_accession"]:
                a("- we cite the gold set's own filing, accession for accession")
            for f in r["flags"]:
                a(f"- **LOOK TWICE:** {f}")
            if not r["flags"]:
                a("- no discrepancy found by this build")
            a("")
        a("The manifest's current words, for comparison with the filing above (the manifest "
          "is the thing being corrected, so it is quoted, not relied on):")
        a("")
        a(f"- `count_evidence`: {e['manifest_says_count_evidence']}")
        a(f"- `match_notes`: {e['manifest_says_match_notes']}")
        a("")
        a("```")
        ids = " ".join(str(x) for x in e["proposed_tracker_event_ids"])
        a(f"python3 railway/recall_adjudicate.py --accept {e['reference_row_id']} \\")
        a(f"    --reviewed-by 'NAME' --reason 'WHY' --event-ids {ids}")
        a(f"python3 railway/recall_adjudicate.py --reject {e['reference_row_id']} \\")
        a(f"    --reviewed-by 'NAME' --reason 'WHY' --event-ids {ids}")
        a("```")
        a("")
        a("---")
        a("")

    a("## The misses that are NOT in this queue")
    a("")
    a(f"{len(pack.get('not_in_queue') or [])} of the "
      f"{pack['reference_events'] - pack['matched_today']} unmatched gold events have "
      "acquired no row that the alias-and-window rule proposes. There is nothing to decide "
      "about them here; they are listed because the first question anyone asks of a "
      "recovery count is what happened to the rest. Every row shown matches the employer "
      "alias at ANY date, which is wider than the matching rule on purpose.")
    a("")
    for m in pack.get("not_in_queue") or []:
        a(f"### {m['filer']} — {m['stated_job_count']:,}, filed {m['filing_date']}")
        a("")
        a(f"`{m['reference_row_id']}` — `{m['current_match_decision']}` — "
          f"<{m['official_source_url']}>")
        a("")
        if m["rows_for_this_employer_at_any_date"]:
            a("| tracker event | company as we hold it | count | effective | announced | source |")
            a("|---|---|---:|---|---|---|")
            for r in m["rows_for_this_employer_at_any_date"]:
                a(f"| {r['tracker_event_id']} | {r['company_name']} | {r['job_count']} "
                  f"| {r['layoff_date'] or '(none)'} | {r['announcement_date'] or '(none)'} "
                  f"| {r['source_type']} |")
        else:
            a("**No row of any kind, at any date, for this employer.**")
        a("")
        if m["already_rejected_event_ids"]:
            a(f"Previously rejected for this event: {m['already_rejected_event_ids']}.")
            a("")
        a(f"- `match_notes`: {m['manifest_says_match_notes']}")
        a("")
    return "\n".join(L) + "\n"


def main(argv=None):
    argv = argv or sys.argv[1:]
    try:
        pack = build()
    except Exception as exc:                                  # noqa: BLE001
        print(f"could not build the adjudication pack ({exc}) — UNKNOWN, not an empty queue")
        return 3
    print(f"ADJUDICATION PACK — {pack['pending']} pending, "
          f"{pack['matched_today']} of {pack['reference_events']} matched today")
    for i, e in enumerate(pack["entries"], 1):
        print(f"  {i:2d}. {e['filing_date']} {e['filer'][:34]:34s} "
              f"{e['stated_job_count']:>6,}  {e['flag_count']} discrepanc"
              f"{'y' if e['flag_count'] == 1 else 'ies'}")
    if "--write" in argv:
        PACK_PATH.write_text(json.dumps(pack, indent=1, sort_keys=True) + "\n",
                             encoding="utf-8")
        SHEET_PATH.write_text(render_sheet(pack), encoding="utf-8")
        print(f"  written: {PACK_PATH}")
        print(f"  written: {SHEET_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
