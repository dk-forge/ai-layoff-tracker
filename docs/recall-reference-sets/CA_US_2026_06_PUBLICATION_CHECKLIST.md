# California WARN June 2026 — recall publication gate

Status: **blocked — no recall metric may be posted yet.**
Transcription review: **complete with a selection correction (2026-07-18).**
Matching pass and independent publication review: **open.**

The source is suitable for a *manual reference sample*: California EDD
publicly links its closed FY 2025–26 WARN report at
<https://edd.ca.gov/siteassets/files/jobs_and_training/warn/warn-report-for-7-1-25-to-6-30-26.pdf>.
The retained draft manifest is
[`ca-us-2026-06.warn-draft.json`](ca-us-2026-06.warn-draft.json), whose
retrieved-document SHA-256 is
`c4239543ffcf87e406005c99b2282f757cbd0e4f7b102f3ea4bdaa33aeabc4df`.

This would measure only a fixed twelve-notice sample from California WARN
notices dated June 1–30, 2026. It cannot be described as United States,
California-all-layoffs, WARN-compliance, or country-completeness recall.

## Required before any tracker lookup

- [x] A second editor compares every one of the twelve manifest rows with the
  official PDF location, company/site, county, notice/received/effective
  dates, count and closure/layoff type. *(Done 2026-07-18 by the Claude
  independent review pass: document re-retrieved, SHA-256 and byte size
  matched the sealed values, and every field of the twelve transcribed rows
  matched the official PDF.)*
- [x] The editor records their identity and UTC review time in each row, and
  confirms the fixed document-position selection rule has not changed.
  *(Identity and UTC time recorded in every row. The rule text is unchanged,
  but its application was found wrong at all three page boundaries: rendered-
  page inspection shows Leggett & Platt (last row of P19), Uber Technologies
  (first row of P20) and Ballast Point Brewing (last row of P20) are fully
  contained June-notice rows that the draft omitted. Because no match decision
  existed, the selection was corrected to conform to the pre-committed rule:
  ServiceNow, Blue Diamond Growers and Dignity Health (California Hospital
  Medical Center) leave the sample; the three omitted rows enter it. The three
  added rows have had no tracker lookup, preserving their pre-lookup
  independence.)*
- [x] The reviewed pre-lookup manifest is committed with the official URL and
  hash intact. It contains no tracker IDs, match decisions, numerator or
  percentage at this stage. *(Committed 2026-07-18; `publication_status` is
  `transcription_reviewed_pending_match_and_publication_review`.)*

## Required matching rule

- [ ] A matching editor then examines tracker canonical records and retained
  source reports. A match requires the same underlying California notice,
  supported by company/site plus count/date context and the official source;
  a same-company news story is insufficient.
- [ ] Every reference row receives exactly one `matched` or `not_matched`
  decision, a canonical event ID only for `matched`, notes explaining the
  evidence, and a matching-editor identity/time.
- [ ] Do not substitute the WARN effective date for notice date when deciding
  the reference period. Effective date is match context only.

## Required publication review

- [ ] An editor independent of the matching pass checks all twelve decisions,
  row count, period boundary and numerator arithmetic.
- [ ] Commit a reviewed manifest at a stable public GitHub URL. It must retain
  all no-match rows and state `independent_manual_sample` as its basis.
- [ ] Only after those checks may the API-key holder post the bounded
  numerator/denominator to `/benchmarks/recall` with that committed manifest
  URL. The public label must say “California WARN sample recall, June 2026”
  and “not a completeness or accuracy measure.”

## Permission boundary

California EDD makes the report publicly available and the project uses only
manual factual transcription with a source citation. The State's web policy
does not state an automated/commercial bulk-reuse licence. This is therefore
permitted for a small source-linked comparison only; do not convert it into a
scraper, redistribute the PDF, or treat it as permission for a live connector.

## Current blocker

The transcription review is complete and the manifest now conforms to its
pre-committed selection rule. The remaining blockers are the source-level
canonical matching pass and the independent publication review, which must be
performed by a reviewer distinct from the 2026-07-18 transcription pass. Two
prior findings also remain open: the earlier candidate audit's HealthCare
Partners type discrepancy, and the fact that retained tracker source excerpts
do not yet carry notice-date/worksite context (see the audit addendum).
Because three sample rows changed in the selection correction, the earlier
audit's candidate table is partially stale and must not be treated as a
match shortlist for the corrected sample. The denominator, numerator and
sample-recall percentage are **still not known and must not be inferred from
current WARN import counts**.
