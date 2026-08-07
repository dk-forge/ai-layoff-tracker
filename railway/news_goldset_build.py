#!/usr/bin/env python3
"""Assemble a NEWS-path answer key that nobody typed.

    python3 railway/news_goldset_build.py            # print what it would build
    python3 railway/news_goldset_build.py --write    # freeze the manifest

WHY A SECOND GOLD SET EXISTS
----------------------------
`ab_extraction_models.py` scored four extraction models against the SEC Item
2.05 gold set and found `google/gemini-2.5-flash-lite` level with the incumbent
at 0.388x the price. The swap was not made, for one honest reason: that corpus
is SEC filings, and the NEWS path is higher volume, messier and was unmeasured.
A model that reads a 10-K-shaped disclosure well is not thereby known to read a
Thai broadcaster's layoff story well. This module builds the corpus that closes
that gap.

WHERE THE ANSWER COMES FROM, AND WHY IT IS NOT A HAND LABEL
-----------------------------------------------------------
Every count here is DERIVED from agreement between sources this tracker already
holds, never typed by an editor and never taken from a single extraction:

  CROSS-OUTLET.   The server's /add path attaches a duplicate report to the
      canonical event instead of discarding it (`alt_event_register_report_for_
      layoff`), so `/event/{id}/sources` is a list of every outlet that reported
      the same employer's cut. An item qualifies when at least TWO INDEPENDENT
      outlets each left a stored evidence sentence carrying the SAME headcount
      verbatim.
  OFFICIAL RECORD. When one of those reports is a state WARN notice, a
      Eurofound ERM record or an SEC 8-K, the corroboration is a filing rather
      than a second newsroom. WARN and ERM never touch the LLM at all
      (`warn_import.py` bulk-upserts), so on that side the number is a legal
      filing, not an extraction.

THE VERBATIM CHECK IS THE PRODUCTION GUARD, IMPORTED
----------------------------------------------------
Event membership alone is NOT corroboration of a count. `alt_fuzzy_dupe_exists`
attaches any report for the same employer within +/-30 days whatever number it
carries, and it is right to: that is how a follow-up story keeps its link. So on
the Zillow 500 event, three outlets say 500 and a fourth says "layoffs hit 91
jobs in Washington state" -- one event, two different numbers. Every candidate
corroborator therefore has to pass `extractor._count_in_text` and
`extractor._percent_only_mention` on its OWN stored evidence, the same two
guards production uses before it will store a headcount. They are imported, not
restated, so this cannot drift from what the pipeline does.

WHAT IT CANNOT SUPPORT, SAID PLAINLY
------------------------------------
This corpus is drawn from rows the tracker ALREADY STORED. It therefore measures
"on an item the pipeline captured and a second source confirms, does a candidate
model recover the same number" -- and it says nothing about the items the
incumbent dropped. It is not a recall measurement and must never be quoted as
one. `recall_goldset.py` is the module that answers the other question, and it
enumerates its corpus from a regulator index precisely because a corpus drawn
from your own output cannot.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
# ModSecurity on the host blocks the default python UA (CLAUDE.md, iron rules).
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

OUT_PATH = (Path(__file__).resolve().parent.parent / "docs" / "recall-reference-sets"
            / "news-corroborated-2026-08.goldset.json")

# Publisher-identity helpers. The suffix list is the tail of a hostname, not a
# public-suffix implementation: it only has to be good enough to make
# "bbc.co.uk" and "bbc.com" the same newsroom, and being WRONG here in the
# direction of "these are the same outlet" only ever costs corpus size.
_HOST_TAIL = {
    "com", "co", "uk", "net", "org", "in", "io", "eu", "news", "au", "ca", "de",
    "fr", "es", "it", "br", "jp", "nz", "ie", "il", "sg", "za", "ph", "my", "pl",
    "cz", "ro", "hu", "tr", "mx", "ar", "cl", "dk", "se", "no", "fi", "nl", "be",
    "ch", "at", "pt", "tw", "hk", "th", "vn", "id", "ae", "ng", "ke", "us",
    "info", "biz", "gov",
}
# A Google News item link is a redirect, so its host identifies Google rather
# than the newsroom; the outlet name in the feed is the only identity available.
_OPAQUE_HOSTS = {"news.google.com", "web.archive.org"}
_WAYBACK = re.compile(r"^https?://web\.archive\.org/web/[^/]+/(https?://.*)$", re.I)

OFFICIAL_TYPES = {"warn", "erm", "8k"}


def unwrap_archive_url(url):
    """The original document URL inside a Wayback snapshot URL, or the input."""
    m = _WAYBACK.match(url or "")
    return m.group(1) if m else (url or "")


def outlet_key(source_name, source_url):
    """One newsroom, one key: the registrable-ish label of its host, else its name.

    Independence is the whole load-bearing property of a cross-outlet answer
    key, and the two fields disagree constantly -- the same newsroom arrives as
    "geekwire.com" on the row and as "GeekWire" on the report, because one came
    from a domain and the other from an RSS <source> element.
    """
    host = urllib.parse.urlparse(unwrap_archive_url(source_url)).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    if host and host not in _OPAQUE_HOSTS:
        labels = [l for l in host.split(".") if l]
        while len(labels) > 1 and labels[-1] in _HOST_TAIL:
            labels.pop()
        return labels[-1]
    name = re.sub(r"[^a-z0-9]+", "", (source_name or "").lower())
    return name[3:] if name.startswith("the") and len(name) > 6 else name


def outlets_are_independent(a, b):
    """False when either key is a prefix of the other, or either is empty.

    A prefix test, not equality: "inman.com" and "Inman Real Estate News"
    reduce to "inman" and "inmanrealestatenews", and counting those as two
    newsrooms would let one outlet corroborate itself -- which is the single
    way this answer key could be quietly worthless.
    """
    if not a or not b:
        return False
    return not (a == b or a.startswith(b) or b.startswith(a))


def _normalised(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def is_syndicated_copy(a, b, prefix=120):
    """True when two evidence sentences are the same sentence.

    Wire copy and aggregator reprints run the originating outlet's paragraph
    verbatim, so two source reports can carry two outlet names and one
    observation. That is not corroboration, it is the same sentence counted
    twice, and it is the failure mode a cross-outlet answer key has to refuse
    by construction rather than by hoping it does not happen. Observed on the
    first item this builder produced: a Singapore HR site reprinting a Straits
    Times paragraph about Dyson, word for word.
    """
    x, y = _normalised(a), _normalised(b)
    if not x or not y:
        return False
    return x[:prefix] == y[:prefix] or x in y or y in x


def evidence_carries_count(count, text):
    """The two production guards, imported. A number that only ever appears as
    a percentage is not a headcount, and a number that is not in the text at all
    is not evidence of anything."""
    import extractor
    if not count or not text:
        return False
    if extractor._percent_only_mention(count, text):
        return False
    return bool(extractor._count_in_text(count, text))


def corroborating_outlets(row, reports):
    """Every outlet whose STORED evidence carries this row's headcount verbatim.

    The row's own excerpt counts as one outlet (the primary). The answer key
    needs two, so a row whose only count-carrying evidence is its own is not in
    the corpus.
    """
    primary = outlet_key(row.get("source_name"), _primary_url(row))
    found, seen = [], set()
    if evidence_carries_count(row.get("job_count"), row.get("excerpt") or ""):
        found.append({"kind": "primary", "source_type": row.get("source_type"),
                      "outlet": primary, "source_name": row.get("source_name"),
                      "source_url": row.get("source_url"),
                      "count_evidence": row.get("excerpt")})
        seen.add(primary)
    for rep in reports:
        stype = (rep.get("source_type") or "").lower()
        key = outlet_key(rep.get("source_name"), rep.get("source_url"))
        if not evidence_carries_count(row.get("job_count"), rep.get("excerpt") or ""):
            continue
        # An official filing is independent of the newsroom by construction; a
        # second newsroom has to prove it is not the first one again.
        if stype not in OFFICIAL_TYPES and not outlets_are_independent(primary, key):
            continue
        if key in seen:
            continue
        # An official filing and a news story never share wording, so the
        # syndication test only applies between newsrooms.
        if stype not in OFFICIAL_TYPES and any(
                is_syndicated_copy(rep.get("excerpt"), f["count_evidence"])
                for f in found if f["kind"] != "official_record"):
            continue
        seen.add(key)
        found.append({"kind": "official_record" if stype in OFFICIAL_TYPES else "cross_outlet",
                      "source_type": stype, "outlet": key,
                      "source_name": rep.get("source_name"),
                      "source_url": rep.get("source_url"),
                      "count_evidence": rep.get("excerpt"),
                      "observed_at": rep.get("observed_at")})
    return found


def _primary_url(row):
    """The row's own document URL, seeing through a Google News redirect to the
    publisher URL the archiver resolved."""
    url = row.get("source_url") or ""
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "news.google.com" and row.get("archived_url"):
        return unwrap_archive_url(row["archived_url"])
    return url


def window_plan(row):
    """(window_source, url) -- which bytes, if any, this row's model input can be
    rebuilt from.

    THE PRODUCTION NEWS PATH KEEPS NO COPY OF WHAT IT FED THE MODEL. `raw_text`
    is built in the collector, read by the extractor and dropped; the row stores
    the model's chosen excerpt, which is its OUTPUT. So the window is rebuilt the
    way `ab_extraction_models.py` rebuilds an SEC window -- by re-reading the
    document through the collector's own window builder -- and the only question
    is whether a faithful document still exists to read.

      wayback_article  the row came from the GDELT/press path, which fetched the
          article and windowed it, and a Wayback snapshot of that same URL is
          held. Frozen bytes, so the corpus does not drift under the harness.
      unrecoverable_headline_window  the row came from Google News RSS, whose
          model input was the feed item's title and snippet. The feed is a
          rolling window and the redirect link does not carry the item text, so
          those bytes are GONE. Substituting the full article would be feeding
          the model a different window than production did and calling the
          result a measurement of production. EXCLUDED, and reported.
      no_frozen_snapshot  a publisher URL with no archived copy. A live re-fetch
          would measure today's page, which is not the page that was read.
    """
    url = row.get("source_url") or ""
    host = urllib.parse.urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "news.google.com":
        return ("unrecoverable_headline_window", None)
    if not row.get("archived_url"):
        return ("no_frozen_snapshot", None)
    return ("wayback_article", row["archived_url"])


# ---------------------------------------------------------------------------
# Collection. Read-only GETs against the public API; no key, nothing written.
# ---------------------------------------------------------------------------

def _default_fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _get(path, fetch, **params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    last = None
    for attempt in range(3):
        try:
            return fetch(url)
        except Exception as exc:               # a host 504 is not a data answer
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{path}: {last}")


def collect(fetch=None, per_page=200, sleep=0.0):
    """Every stored news row, plus the source reports of the ones that have any."""
    fetch = fetch or _default_fetch
    rows, page = [], 1
    while True:
        payload = _get("query", fetch, sources="news", per_page=per_page, page=page)
        rows.extend(payload.get("data") or [])
        if not payload.get("data") or len(rows) >= int(payload.get("total") or 0):
            break
        page += 1
    reports = {}
    for row in rows:
        if not row.get("additional_sources"):
            continue
        reports[row["id"]] = (_get(f"event/{row['id']}/sources", fetch).get("sources") or [])
        if sleep:
            time.sleep(sleep)
    return rows, reports


def assemble(rows, reports):
    """(reference_events, excluded_rows) from already-fetched data. Pure."""
    events, excluded = [], []
    for row in rows:
        corr = corroborating_outlets(row, reports.get(row["id"]) or [])
        if len(corr) < 2:
            continue
        window_source, window_url = window_plan(row)
        item = {
            "reference_row_id": f"news-corr-{row['id']}",
            "layoff_row_id": row["id"],
            "event_id": row.get("event_id"),
            "company_name": row.get("company_name"),
            "stated_job_count": row.get("job_count"),
            "country": row.get("country") or "",
            "layoff_date": row.get("layoff_date") or "",
            "announcement_date": row.get("announcement_date") or "",
            "source_type": row.get("source_type"),
            "primary_outlet": outlet_key(row.get("source_name"), _primary_url(row)),
            "primary_source_url": row.get("source_url"),
            "window_source": window_source,
            "frozen_window_url": window_url,
            "corroboration": corr,
            "corroboration_kinds": sorted({c["kind"] for c in corr}),
        }
        if window_source == "wayback_article":
            events.append(item)
        else:
            excluded.append({k: item[k] for k in
                             ("reference_row_id", "layoff_row_id", "company_name",
                              "stated_job_count", "window_source", "primary_source_url")})
    events.sort(key=lambda e: e["layoff_row_id"])
    excluded.sort(key=lambda e: e["layoff_row_id"])
    return events, excluded


def manifest(events, excluded, assembled_at=None):
    return {
        "manifest_version": 1,
        "reference_set_id": "news-corroborated-2026-08",
        "publication_status": "internal_model_comparison_reference_not_a_recall_measurement",
        "reference_basis": "cross_source_corroboration_of_already_stored_rows",
        "scope": ("Stored rows with source_type 'news' whose headcount is carried "
                  "verbatim by the stored evidence of at least two independent "
                  "outlets, or by one outlet and one official filing (state WARN, "
                  "Eurofound ERM or SEC 8-K), and whose model input can be rebuilt "
                  "from a frozen Wayback snapshot of the article the collector read."),
        "assembled_at": assembled_at or date.today().isoformat(),
        "assembled_by": ("railway/news_goldset_build.py against the public read-only "
                         "API. No count, company or country in this file was typed by "
                         "a human, and no model was called to produce it."),
        "how_it_was_assembled": [
            "1. ENUMERATION. Every stored row with source_type 'news', paged from "
            "/query. No search terms, no ranking, no sampling: the whole population.",
            "2. CORROBORATION. For each row that carries any additional source, "
            "/event/{id}/sources returns every report the server retained for that "
            "canonical event. An outlet corroborates only when its OWN stored "
            "evidence sentence carries the row's headcount verbatim, checked by "
            "extractor._count_in_text and extractor._percent_only_mention -- the "
            "same two guards production runs before storing a count.",
            "3. INDEPENDENCE, TWICE. Outlet identity is the registrable label of "
            "the report's host, or its feed name when the link is a Google News "
            "redirect. Two outlets count as one when either key is a prefix of "
            "the other, so 'inman.com' cannot corroborate 'Inman Real Estate News'. "
            "Two DISTINCT outlets still count as one observation when their stored "
            "evidence is the same sentence, because wire copy and aggregator "
            "reprints run the originating paragraph verbatim. An official filing "
            "(warn/erm/8k) is independent of a newsroom by construction and skips "
            "both tests.",
            "4. WINDOW. The production news path stores no copy of the text it fed "
            "the model, so the model input is rebuilt by re-reading the article "
            "through sources.gdelt._fetch_article, the collector's own window "
            "builder. Only rows with a Wayback snapshot of the publisher URL enter "
            "the set; see `excluded_rows` for the rest and why.",
        ],
        "why_this_is_and_is_not_independent": (
            "Independent of any single extraction: two sources had to state the "
            "same number, and for the official-record items one of them is a legal "
            "filing that never passes through an LLM (WARN and ERM are bulk-upserted "
            "by warn_import.py). NOT independent of the tracker's capture: every row "
            "here is a row the incumbent model already extracted successfully, so "
            "the set cannot see the events the pipeline missed."),
        "what_it_can_and_cannot_support": (
            "It supports 'on a corroborated news event the pipeline captured, does "
            "this model recover the same headcount from the same window'. It is not "
            "a recall measurement, it is not a precision measurement over all news, "
            "and it must never be quoted as either. The denominator is small enough "
            "that a difference of one or two items is not a difference; read the "
            "per-item disagreements, which the harness prints before any percentage."),
        "answer_key_rule": {
            "count": "the row's stored job_count, required to appear verbatim in the "
                     "stored evidence of at least two independent outlets",
            "company": "the row's stored company_name, from the same merged event",
            "country": "the row's stored country. RECORDED BUT NOT SCORED: the "
                       "source-report table stores no country, so the second outlet "
                       "corroborates the company and the count, not the country. "
                       "Scoring a field the key cannot support would be inventing a "
                       "number.",
        },
        "reference_events": events,
        "excluded_rows": excluded,
        "excluded_rows_note": (
            "unrecoverable_headline_window: the row came from Google News RSS, whose "
            "model input was the feed item's headline and snippet. That text is not "
            "stored and the redirect link does not carry it, so the row is excluded "
            "rather than scored against a window production never used. "
            "no_frozen_snapshot: a publisher URL with no archived copy, where a live "
            "re-fetch would measure today's page instead of the page that was read."),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="freeze the manifest to docs/recall-reference-sets/")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    rows, reports = collect()
    print(f"{len(rows)} stored news rows; {len(reports)} carry additional sources")
    events, excluded = assemble(rows, reports)
    kinds = {}
    for e in events:
        for k in e["corroboration_kinds"]:
            kinds[k] = kinds.get(k, 0) + 1
    print(f"{len(events)} corroborated rows with a rebuildable frozen window "
          f"({', '.join(f'{k}={v}' for k, v in sorted(kinds.items()))})")
    reasons = {}
    for e in excluded:
        reasons[e["window_source"]] = reasons.get(e["window_source"], 0) + 1
    for reason, n in sorted(reasons.items()):
        print(f"  excluded {n:>3}  {reason}")
    if not args.write:
        print("\n(dry run: pass --write to freeze the manifest)")
        return 0
    Path(args.out).write_text(json.dumps(manifest(events, excluded), indent=1,
                                         ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
