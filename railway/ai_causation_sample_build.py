#!/usr/bin/env python3
"""Freeze the CORPUS the AI-causation classifier will be scored on.

    python3 railway/ai_causation_sample_build.py            # print what it would build
    python3 railway/ai_causation_sample_build.py --write    # freeze the sample

WHY THIS EXISTS
---------------
On 2026-08-07 the extraction model moved to `google/gemini-2.5-flash-lite`,
validated 30/30 on a news-EXTRACTION gold set at 0.388x the incumbent's cost.
`MODEL` also governs AI CAUSATION: `extract_layoff_data` sets `ai_explicit` from
the causation label it returns, and `classify_ai_evidence()` re-reads it on the
daily sweep, and BOTH deliberately use `MODEL` rather than `CLASSIFY_MODEL`
because "AI-causation is correctness-critical". So the swap moved the classifier
behind the single most load-bearing field in the product, and the measurement
that authorised it looked only at headcounts. Nothing has measured the thing the
tracker is named after.

This module builds the corpus. It makes NO model call and costs nothing.
`ab_ai_causation.py` labels and scores it.

THE SAMPLING FRAME IS THE ROWS A MODEL ACTUALLY DECIDED
-------------------------------------------------------
64,245 rows are stored; 62,307 of them are WARN notices and Eurofound ERM
records, which never touch an LLM at all (`warn_import.py` bulk-upserts them,
`ai_explicit` is 0 by construction). Sampling those would measure nothing and
would make the corpus look four hundred times more reassuring than it is. The
frame is therefore the FREE-TEXT paths only — news, SEC 8-K, press release —
1,938 rows, of which 96 carry `ai_explicit = 1`.

THREE STRATA, AND THE MIDDLE ONE IS THE POINT
----------------------------------------------
  A  POSITIVES     `ai_explicit = 1`. Answers precision: of the rows the
                   tracker publishes as AI-attributed, how many are.
  B  HARD NEGATIVES `ai_explicit = 0` and the stored text mentions AI or
                   automation ANYWAY. This is where classifier error lives. A
                   model that says yes whenever an article says "AI" fails here
                   and nowhere else, and a uniform random sample of 1,938 rows
                   would contain almost none of them.
  C  PLAIN NEGATIVES `ai_explicit = 0`, no AI language in the stored text. The
                   control: a classifier that has started hallucinating
                   attributions shows up here.

A stratified sample is not a random one, so the sample's raw precision/recall is
NOT the population's. Every stratum's POPULATION size is frozen alongside it so
the scorer can reweight, and the scorer reports the per-stratum rates too.

WHAT THE MODEL IS SHOWN, AND THE LIMIT THAT PUTS ON THE ANSWER
---------------------------------------------------------------
The stored `excerpt`, and nothing else. That is the text this tracker HOLDS.
`reason_backfill.py`, `enrich_roles.py` and `industry_backfill.py` all read
exactly it, and `classify_ai_evidence()` reads a passage of the same shape.

Two consequences, and both belong in any sentence quoting a number from this
corpus:

  * The excerpt is the EXTRACTION MODEL'S OWN OUTPUT — the passage it chose as
    confirming the layoff. On an AI-attributed row it will usually be a passage
    containing the AI phrase, because that is what the prompt asks for. So this
    corpus is STRONG on precision (does a model claim AI where the text does not
    support it) and WEAK on recall (it cannot show an attribution that was never
    captured into an excerpt in the first place). Stratum B is the partial
    answer to that: those excerpts DO carry AI language and production said no.
  * `ai_language` and `reason_tags` are recorded as REVIEW METADATA and are
    never put in a labelling prompt. They are the stored answer; handing a
    candidate the answer inside its own prompt is the defect the 2026-08-07 news
    gold set had to rebuild windows from Wayback to avoid.

THE SAMPLE IS FROZEN AND COMMITTED so the next model swap is scored against the
same rows and not against a fresh draw that happens to be kinder.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
# ModSecurity on the host blocks the default python UA (CLAUDE.md, iron rules).
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

OUT_PATH = (Path(__file__).resolve().parent.parent / "docs" / "recall-reference-sets"
            / "ai-causation-2026-08.sample.json")

# The free-text paths. WARN and ERM are excluded because no model ever read
# them; see the module docstring.
FRAME_SOURCES = "news,8K,press_release"

# Target sizes. ~200 total, deliberately NOT proportional: stratum A is 5% of
# the frame and would contribute ~10 rows to a proportional draw, which cannot
# support a precision interval worth printing.
TARGET = {"A_positive": 70, "B_hard_negative": 80, "C_plain_negative": 50}

# Word-boundary AI/automation language. `/query?keyword=AI` is a SQL LIKE
# '%AI%', which matches "maintenance", "Air", "retail" and returns 5,322 rows —
# a substring match is not a mention. This regex is applied here, in Python,
# over the same stored text the labellers will read.
AI_MENTION = re.compile(
    r"\b("
    r"a\.?i\.?"
    r"|artificial[\s-]+intelligence"
    r"|machine[\s-]+learning"
    r"|automation|automated|automating|automate"
    r"|algorithm(?:s|ic)?"
    r"|chatbot(?:s)?|bots?"
    r"|robot(?:s|ic|ics|isation|ization)?"
    r"|gen(?:erative)?[\s-]*ai"
    r"|large[\s-]+language[\s-]+model(?:s)?|llms?"
    r"|copilot|chatgpt|openai"
    r"|digital[\s-]+transformation"
    r")\b",
    re.IGNORECASE,
)

# The minimum stored text worth asking a model about. Below this there is no
# document to read and a verdict would measure the sampler, not the classifier.
MIN_TEXT_CHARS = 40


def _get(path, **params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_frame(page_size=200, max_pages=40):
    """Every free-text row, paged. Returns (rows, total_reported)."""
    rows, page, total = [], 1, None
    while page <= max_pages:
        data = _get("query", sources=FRAME_SOURCES, per_page=page_size,
                    page=page, sort="id", dir="asc")
        total = data.get("total") if total is None else total
        batch = data.get("data") or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return rows, total


def stratum_of(row):
    """A / B / C, or None when the row carries no readable document."""
    text = (row.get("excerpt") or "").strip()
    if len(text) < MIN_TEXT_CHARS:
        return None
    if row.get("ai_explicit"):
        return "A_positive"
    return "B_hard_negative" if AI_MENTION.search(text) else "C_plain_negative"


def _rank(row):
    """A stable, seed-free draw order.

    A hash of the row id, not `random.sample`: this file is committed and the
    next person to re-derive it must get the same rows out of the same frame
    without having to trust that a seed and a Python version travelled with it.
    """
    return hashlib.sha256(f"ai-causation-2026-08:{row.get('id')}".encode()).hexdigest()


def build(rows):
    buckets = {k: [] for k in TARGET}
    skipped_no_text = 0
    for row in rows:
        stratum = stratum_of(row)
        if stratum is None:
            skipped_no_text += 1
            continue
        buckets[stratum].append(row)
    population = {k: len(v) for k, v in buckets.items()}
    items = []
    for stratum, target in TARGET.items():
        chosen = sorted(buckets[stratum], key=_rank)[:target]
        for row in chosen:
            items.append({
                "id": row.get("id"),
                "event_id": row.get("event_id"),
                "stratum": stratum,
                "company_name": row.get("company_name"),
                "source_type": row.get("source_type"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "layoff_date": row.get("layoff_date"),
                "job_count": row.get("job_count"),
                # THE DOCUMENT. Everything below this line is review metadata
                # and never enters a labelling prompt.
                "text": (row.get("excerpt") or "").strip(),
                "stored": {
                    "ai_explicit": bool(row.get("ai_explicit")),
                    "ai_causation": row.get("ai_causation"),
                    "ai_language": row.get("ai_language"),
                    "reason_tags": row.get("reason_tags"),
                    "review_status": row.get("review_status"),
                },
            })
    return items, population, skipped_no_text


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="freeze the sample to docs/recall-reference-sets/")
    args = ap.parse_args(argv)

    rows, total = fetch_frame()
    print(f"frame: {len(rows)} row(s) fetched of {total} reported "
          f"for sources={FRAME_SOURCES}")
    if total and len(rows) < total:
        print(f"::warning::only {len(rows)} of {total} frame rows were read; "
              f"the sample would be drawn from a truncated frame. NOT writing.")
        return 3

    items, population, skipped = build(rows)
    drawn = {k: sum(1 for i in items if i["stratum"] == k) for k in TARGET}
    print(f"skipped for no readable stored text (<{MIN_TEXT_CHARS} chars): {skipped}")
    for stratum in TARGET:
        print(f"  {stratum:18s} population {population[stratum]:5d} "
              f"-> drawn {drawn[stratum]:3d} (target {TARGET[stratum]})")
    print(f"  {'TOTAL':18s} population {sum(population.values()):5d} "
          f"-> drawn {len(items):3d}")

    short = [s for s in TARGET if drawn[s] < TARGET[s]]
    if short:
        print(f"::notice::strata below target (the frame simply holds fewer "
              f"rows than asked for): {', '.join(short)}. That is a smaller "
              f"corpus, not a failure — the intervals will be wider and will "
              f"say so.")

    manifest = {
        "version": 1,
        "name": "ai-causation-2026-08",
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": ("Did the 2026-08-07 swap of OPENROUTER_MODEL to "
                     "google/gemini-2.5-flash-lite degrade AI causation? The "
                     "extraction gold set that authorised the swap measured "
                     "headcounts only."),
        "frame": {
            "sources": FRAME_SOURCES,
            "rows_in_frame": total,
            "excluded": ("warn and erm rows: no LLM ever reads them, so "
                         "ai_explicit is 0 by construction"),
            "min_text_chars": MIN_TEXT_CHARS,
            "skipped_no_text": skipped,
        },
        "document": ("the row's stored `excerpt` only. It is the extraction "
                     "model's own chosen passage, which makes this corpus "
                     "strong on precision and weak on recall — see the module "
                     "docstring of railway/ai_causation_sample_build.py."),
        "strata_population": population,
        "strata_drawn": drawn,
        "items": items,
    }
    if not args.write:
        print("\n(dry run; pass --write to freeze)")
        return 0
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"\nwrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
