#!/usr/bin/env python3
"""Diagnostic: where does a UK reference event die in our pipeline?

DRY RUN ONLY. Posts nothing, writes no row, reports no source health, spends no
model money. It is the UK counterpart of `edgar_recall_probe.py` and it answers
the question that is worth more than the percentage: for an event we KNOW
happened and KNOW was published with a headcount, which stage dropped it?

    no_source        the discovery layer never saw an article about it at all.
                     GDELT's public ArtList, asked with OUR OWN discovery
                     vocabulary over the event's window, returns nothing for
                     this employer. Nothing downstream could have run.
    walked_not_read  GDELT returned articles, but none of them is on a
                     TRUSTED_DOMAIN, so `_fetch_trusted` never fetched one.
                     The event was inside the index we walk and outside the
                     list we read.
    fetched_rejected a trusted-domain article exists and was fetchable, and the
                     event's stated headcount does NOT survive into the text
                     window the extractor is given. `_count_in_text` cannot
                     pass, so the deterministic guard would reject it whatever
                     the model said.
    extracted_dropped  everything above holds and the headcount IS in the
                     window: the drop, if there is one, happened in the model
                     or in a guard downstream of it. THIS PROBE DOES NOT CALL
                     THE MODEL, so this stage is reported as the deterministic
                     evidence only and the model half is UNKNOWN.
    stored_unmatched the tracker holds a plausible row and the reference set's
                     alias/window rule did not join them. A naming problem, not
                     a collection problem.

WHY NO MODEL CALL. `edgar_recall_probe.py` calls the real model on purpose,
because for SEC filings the question "would the extractor accept this text?" is
genuinely a model question and the corpus is small. Here the honest answer is
that the money has to be authorised first: see the run banner. Until it is,
`extracted_dropped` resolves to UNKNOWN, which is a real answer and not a pass.

Env: none required. GDELT's public API needs no key.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126 Safari/537.36")
TRACKER_UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
TRACKER_BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"

NO_SOURCE = "no_source"
WALKED_NOT_READ = "walked_not_read"
FETCHED_REJECTED = "fetched_rejected"
EXTRACTED_DROPPED = "extracted_dropped"
STORED_UNMATCHED = "stored_unmatched"
UNKNOWN = "unknown"


def _load_pipeline():
    """Import the REAL collector and extractor, or say why we could not.

    Imported lazily and defensively: this probe must be runnable from a
    checkout without `requests` installed, in which case the GDELT half still
    works (stdlib urllib) and only the trusted-domain list and the count guard
    come from a fallback that is LOUDLY reported rather than silently assumed.
    """
    try:
        from sources.gdelt import TRUSTED_DOMAINS, _is_trusted     # noqa: N813
    except Exception as exc:                                       # noqa: BLE001
        return None, None, None, f"{type(exc).__name__}: {exc}"
    # extractor pulls in the model client, which a read-only diagnostic has no
    # business requiring. Its count guard is a bonus, not a precondition, and
    # its absence is reported rather than papered over.
    try:
        import extractor
        count_in_text = extractor._count_in_text
    except Exception:                                              # noqa: BLE001
        count_in_text = None
    return TRUSTED_DOMAINS, _is_trusted, count_in_text, None


def _gdelt(query, start, end, max_records=75):
    params = {"query": query, "mode": "ArtList", "format": "json",
              "maxrecords": max_records, "sortby": "datedesc",
              "startdatetime": start.strftime("%Y%m%d%H%M%S"),
              "enddatetime": end.strftime("%Y%m%d%H%M%S")}
    url = GDELT_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                body = r.read()
            return json.loads(body).get("articles", []) or [], None
        except Exception as exc:                                   # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
            time.sleep(3 * (attempt + 1))
    return None, err            # None = UNKNOWN, never an empty result


def _domain(article):
    return (article.get("domain") or "").lower()


def _loose_tracker_probe(event):
    """Is a plausible row already stored under a name the strict rule cannot join?

    THE PREFIX RULE IS RIGHT AND IT IS ALSO A MISS-MAKER. `name_matches` demands
    that the stored company name START with every alias token, which is what
    stops Xperi matching Experian. It also means the reference set's "University
    of Dundee" cannot reach our stored "Dundee University", and calling that a
    collection failure would be a lie about where the event died.

    So: ask the public API for the event's most distinctive token and report any
    row inside the match window. THIS IS A DIAGNOSTIC, NOT A MATCH. Nothing it
    finds is counted, and nothing it finds is written back to the manifest —
    both would be the machine promoting its own recall through the side door.
    An editor decides, from the adjudication pack, exactly as everywhere else.
    """
    import re
    words = [w for w in re.split(r"[^A-Za-z]+", event["employer"]) if len(w) > 3]
    skip = {"university", "college", "hospice", "limited", "holdings", "group",
            "trust", "plc", "company", "services", "chemical", "energy", "steel"}
    token = next((w for w in words if w.lower() not in skip), words[0] if words else "")
    if not token:
        return []
    # The API's `company=` filter is a substring LIKE, so a single token dredges
    # the whole table: "Well" returned Wells Fargo, Wellpath, Chartwells and a
    # Finnish wellbeing services county; "East" returned nine US WARN notices.
    # Constraining to United Kingdom rows is what makes the output readable, and
    # it can only ever REMOVE candidates, never add one.
    url = TRACKER_BASE + "query?" + urllib.parse.urlencode(
        {"company": token, "country": "United Kingdom", "country_basis": "any",
         "per_page": 100})
    req = urllib.request.Request(url, headers={"User-Agent": TRACKER_UA,
                                               "Accept": "application/json"})
    lo, hi = event["match_window"]
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = (json.loads(r.read()) or {}).get("data") or []
    except Exception:                                              # noqa: BLE001
        return None                                                 # UNKNOWN
    out = []
    for row in rows:
        when = (row.get("layoff_date") or row.get("announcement_date") or "")[:10]
        if lo <= when <= hi:
            out.append({"event_id": row.get("event_id"), "company": row.get("company_name"),
                        "job_count": row.get("job_count"), "layoff_date": when,
                        "source": row.get("source_name")})
    return out


def classify(event, is_trusted, count_in_text, tracker_rows=None, skip_gdelt=False):
    """Name the stage that dropped one reference event. No model call.

    `skip_gdelt` runs the TRACKER half only. GDELT's public endpoint rate-limits
    a burst of thirty-odd queries into a wall of 429s, and a probe that answers
    UNKNOWN thirty times has told you nothing while looking busy. The tracker
    half is the actionable half — it separates "we never had it" from "we have
    it under another name" — so it is allowed to run on its own, and the
    discovery stages then report UNKNOWN with the reason attached rather than
    defaulting to `no_source`, which would be a lie about where the event died.
    """
    aliases = event.get("employer_aliases") or []
    lo, hi = event["match_window"]
    start = datetime.strptime(lo, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(hi, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # GDELT's public window is 2017->present and it rate-limits long spans, so
    # ask a tighter window than the match window: 30 days either side of the
    # announcement is what a twice-daily cron plus the rotating monthly sweep
    # would actually have covered.
    anchor = datetime.strptime(event["announcement_date"], "%Y-%m-%d").replace(
        tzinfo=timezone.utc)
    start = max(start, anchor - timedelta(days=30))
    end = min(end, anchor + timedelta(days=30))

    # THE TRACKER HALF FIRST. It is cheap, it never rate-limits, and it answers
    # the question that changes what you do next: is this event absent, or
    # present under a name the join cannot reach?
    if tracker_rows:
        return {"stage": STORED_UNMATCHED, "tracker_rows": tracker_rows}

    loose = _loose_tracker_probe(event)
    if loose is None:
        return {"stage": UNKNOWN, "why": "the tracker API could not be read"}
    if loose:
        return {"stage": STORED_UNMATCHED, "loose_name_candidates": loose,
                "why": ("a row exists inside the match window under a name the strict "
                        "prefix rule cannot join. NOT counted, and not written back — "
                        "an editor decides")}

    if skip_gdelt:
        return {"stage": UNKNOWN,
                "why": ("nothing is stored under any name in the window, and the "
                        "discovery half was not run (UK_PROBE_SKIP_GDELT). Which of "
                        "no_source / walked_not_read / extracted_dropped applies is "
                        "UNMEASURED, not no_source")}

    primary = aliases[0]
    query = f'"{primary}" (layoffs OR redundancies OR "job cuts" OR "job losses")'
    articles, err = _gdelt(query, start, end)
    if articles is None:
        return {"stage": UNKNOWN, "why": f"GDELT unreachable: {err}"}

    if not articles:
        return {"stage": NO_SOURCE, "gdelt_articles": 0,
                "why": "GDELT ArtList returned nothing for this employer in the window"}

    trusted = [a for a in articles if is_trusted(_domain(a))]
    if not trusted:
        return {"stage": WALKED_NOT_READ, "gdelt_articles": len(articles),
                "domains": sorted({_domain(a) for a in articles})[:8],
                "why": "GDELT indexed it; no article is on a TRUSTED_DOMAIN"}

    return {"stage": EXTRACTED_DROPPED, "gdelt_articles": len(articles),
            "trusted_articles": len(trusted),
            "trusted_domains": sorted({_domain(a) for a in trusted})[:8],
            "model_stage": UNKNOWN,
            "why": ("a trusted-domain article exists in the window. Whether the "
                    "headcount survived the text budget and the model is UNKNOWN "
                    "from this probe — it makes no model call")}


def main(argv=None):
    argv = argv or sys.argv[1:]
    manifest_path = argv[0] if argv else str(
        HERE.parent / "docs" / "recall-reference-sets"
        / "uk-hansard-2024-07_2026-06.goldset.json")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _, is_trusted, count_in_text, import_error = _load_pipeline()
    if import_error:
        print(f"could not import the real pipeline ({import_error}) — every stage "
              f"below would be a guess. UNKNOWN, not a pass.")
        return 3

    measurement = json.loads(
        (HERE / "recall_uk_measurement.json").read_text(encoding="utf-8"))
    missed = {m["id"] for m in measurement.get("missed_events") or []}
    held = {c["id"]: c["tracker_event_ids"]
            for c in measurement.get("candidates_needing_adjudication") or []}

    import os
    skip_gdelt = os.environ.get("UK_PROBE_SKIP_GDELT", "") in ("1", "true", "yes")
    if skip_gdelt:
        print("UK_PROBE_SKIP_GDELT=1 — tracker half only. Every event that is not "
              "stored resolves to UNKNOWN, not to no_source.")

    tally, out = {}, []
    for event in manifest["reference_events"]:
        if event["reference_row_id"] not in missed:
            continue
        verdict = classify(event, is_trusted, count_in_text,
                           tracker_rows=held.get(event["reference_row_id"]),
                           skip_gdelt=skip_gdelt)
        tally[verdict["stage"]] = tally.get(verdict["stage"], 0) + 1
        out.append({"id": event["reference_row_id"], "employer": event["employer"],
                    "announcement_date": event["announcement_date"], **verdict})
        print(f"  {verdict['stage']:18s} {event['announcement_date']} "
              f"{event['employer'][:38]:38s} {verdict.get('why', '')[:60]}", flush=True)
        time.sleep(0.3 if skip_gdelt else 2.0)   # GDELT throttles; be a good citizen

    print("\nWHERE THE MISSES DIED")
    for stage, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"  {n:4d}  {stage}")
    (HERE / "uk_recall_probe_result.json").write_text(
        json.dumps({"probed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "tally": tally, "events": out}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
