# California WARN June 2026 — recall publication gate

Status: **blocked — no recall metric may be posted yet.**

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

- [ ] A second editor compares every one of the twelve manifest rows with the
  official PDF location, company/site, county, notice/received/effective
  dates, count and closure/layoff type.
- [ ] The editor records their identity and UTC review time in each row, and
  confirms the fixed document-position selection rule has not changed.
- [ ] The reviewed pre-lookup manifest is committed with the official URL and
  hash intact. It contains no tracker IDs, match decisions, numerator or
  percentage at this stage.

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

The manifest is intentionally pre-lookup and has no completed independent
transcription review or source-level canonical match review. Therefore the
denominator, numerator and sample-recall percentage are **not yet known and
must not be inferred from current WARN import counts**.
