# Recall reference-set manifests

This directory holds reproducible input manifests for the country-period
recall protocol in `../RECALL_BENCHMARK_PROTOCOL.md`. A manifest is not a
tracker import and never creates, edits or deletes a layoff event.

## Publication rule

Only publish a recall measurement after all of the following are true:

1. The manifest has one country and one closed period.
2. Every row was assembled independently of the tracker and retains an
   openly reviewable primary/reference URL, company, relevant event date and
   stated job count.
3. An editor has recorded a same-event canonical match or a documented
   non-match for every row. A similar article or company name is not enough.
4. A reviewer has checked the row count, country/period boundary and every
   match decision.
5. The committed manifest has a stable public GitHub URL. Only then may its
   bounded numerator and denominator be posted to
   `/benchmarks/recall`.

Do not post a percentage from a template, a partial manifest, an opaque
publisher corpus, a paywalled dataset, or a reference set assembled by first
searching this tracker. Recall is a sample measurement, not a completeness or
accuracy claim.

## California June 2026 template

`ca-us-2026-06.template.json` reserves the first candidate scope: United
States, California notices, 1–30 June 2026. The candidate reference document
is the California Employment Development Department's FY 2025–26 public WARN
report. It exposes employer, notice/effective dates and affected-worker counts,
but the template deliberately contains **no event rows, matches, denominator,
numerator or recall result**.

Before converting it to a published manifest, copy the template to a new
non-template filename, add one independently transcribed row per selected
official notice, record the source row/page location, and have a second editor
perform the matching review. Keep the selection rule fixed before any tracker
lookup—for example, a reproducible systematic sample over the official June
notice rows. Do not silently exclude no-match rows.

This is a United States country-period sample with a clearly disclosed
California source scope. It does not measure all United States layoffs or all
California layoffs outside the relevant WARN requirements.

## California June 2026 draft

`ca-us-2026-06.warn-draft.json` is a source-cited, pre-lookup draft based on
the same closed EDD report. It is deliberately marked
`draft_pending_independent_review`: no tracker lookup, match decision,
denominator, numerator or recall percentage is present. It records the
retrieved source hash and a fixed document-position selection rule so a second
editor can verify the original transcription before any matching begins.

The EDD report is publicly linked by the agency. This project uses it only for
a small manual, source-linked factual reference sample; the State's site terms
do not supply an explicit automated/commercial bulk-reuse licence. Do not turn
this draft into a scraper or republish the official PDF.

## SEC Item 2.05 internal regression set (2025-07 → 2026-06)

`sec-item-205-us-2025-07_2026-06.goldset.json` is a **different kind of file**
from the California manifest above, and the difference is the whole reason it is
allowed to exist without the three-reviewer chain:

| | California WARN June 2026 | SEC Item 2.05 2025-07..2026-06 |
|---|---|---|
| Purpose | a **public** country-period benchmark | an **internal** regression tripwire |
| Endpoint | `/benchmarks/recall` after the review gate | none, ever |
| Review | three distinct actors, complete | one session, stated in the manifest |
| Denominator | 12 | 57 |
| Read by | the public read endpoint | `railway/recall_goldset.py`, `data_integrity.recall_floor`, CI |

It is enumerated from the filer's own structured item code in SEC EDGAR — a
primary regulator index, not an aggregator and not a competitor list — with a
selection rule fixed before any tracker query, and a control query in every
month of the window returned zero item-2.05 filings the first query missed. Full
method, per-row count evidence and per-row match decisions are inside the file.

Two rules about it:

1. **It is never posted to `/benchmarks/recall`.** Its `publication_status` says
   so and `tests/test_recall_goldset.py` asserts it. The public endpoint is
   reserved for a sample that has cleared the independence gate; this one has
   one author.
2. **Its number is not "our recall".** 24 of 57 with a Wilson 95% interval of
   [30%, 55%] describes one source family over one window. It is a floor to
   detect loss, not a coverage claim.

## Corroborated news set (2026-08)

`news-corroborated-2026-08.goldset.json` is a **third kind of file** again, and
the distinction matters more here than anywhere else in this directory: it is
not a recall reference at all. It exists to answer "which extraction model
should we pay for", it is read only by `railway/ab_extraction_models.py`, and
its `publication_status` is
`internal_model_comparison_reference_not_a_recall_measurement`.

The reason it cannot measure recall is structural rather than procedural. Every
row in it is a row the tracker ALREADY STORED, so the set is blind by
construction to the events the pipeline missed, which is exactly the quantity
recall is. A corpus drawn from your own output can tell you whether a different
model reads the same document the same way. It can never tell you what neither
model was shown.

What it can support: two independent sources each left a stored evidence
sentence carrying the same headcount verbatim (45 items corroborated by a
second newsroom, 26 by a state WARN notice, a Eurofound ERM record or an SEC
8-K, some by both). Nothing in the file was typed by an editor;
`railway/news_goldset_build.py` derives all of it from the public read-only
API, and `railway/tests/test_news_goldset.py` holds the derivation rules.

Rebuild it with `python3 railway/news_goldset_build.py --write`. A rebuild
later will find MORE items, because the tracker keeps storing rows; that is a
new frozen set, not a correction of this one, and a model comparison must not
straddle two of them.
