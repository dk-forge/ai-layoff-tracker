# California WARN June 2026 — recall publication gate

Status: **blocked — no recall metric may be posted yet** (only the stable-URL
commit and the keyed POST by the API-key holder remain).
Transcription review: **complete with a selection correction (2026-07-18).**
Matching pass: **complete (2026-07-18, independent matching editor).**
Independent publication review: **complete (2026-07-18, third distinct
reviewer). Verified figures: reference_events = 12, matched_events = 11.**

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

- [x] A matching editor then examines tracker canonical records and retained
  source reports. A match requires the same underlying California notice,
  supported by company/site plus count/date context and the official source;
  a same-company news story is insufficient. *(Done 2026-07-18 by the Claude
  independent matching editor pass, distinct from the 2026-07-18 transcription
  reviewer: all twelve rows were independently looked up on the public
  `GET /query` API with company-name variants and `state=CA`; retained source
  excerpts were inspected via `GET /event/{row_id}/sources` where
  disambiguation mattered, and the same-company Mercury News story
  (event 43790) was treated as insufficient. The official PDF was re-retrieved
  once to disambiguate the five same-day HealthCare Partners notices; SHA-256
  and byte size matched the sealed values.)*
- [x] Every reference row receives exactly one `matched` or `not_matched`
  decision, a canonical event ID only for `matched`, notes explaining the
  evidence, and a matching-editor identity/time. *(Done 2026-07-18: eleven
  rows are `matched_canonical_event` with unique canonical IDs and per-row
  `matching_evidence` query URLs; one row — p19-first-01, HealthCare Partners
  Medical Group P.C., 1, Layoff/Permanent, Arcadia — is
  `no_matching_tracker_event`, because the tracker's only same-name count-1
  candidate (event 392) is, per its retained Closure-type source excerpt and
  the official report, the distinct 06/02-received 1120 W Washington Blvd
  Closure notice. This resolves the earlier audit's event-392 type-discrepancy
  finding as a different underlying notice rather than a transcription error.
  No numerator, denominator or percentage was computed in this pass.)*
- [x] Do not substitute the WARN effective date for notice date when deciding
  the reference period. Effective date is match context only. *(Confirmed
  2026-07-18: the reference period stayed defined by official notice dates;
  effective dates and counts were used only as same-notice match context, and
  cross-period rows returned by the queries were excluded.)*

## Required publication review

- [x] An editor independent of the matching pass checks all twelve decisions,
  row count, period boundary and numerator arithmetic. *(Done 2026-07-18 by a
  Claude independent publication-review pass, a third actor distinct from both
  the transcription reviewer and the matching editor. The official PDF was
  independently re-retrieved — SHA-256 and byte size matched the sealed
  values — and the fixed positional selection was re-derived from scratch:
  June-notice rows occur only on P19/P20, and the first-three/last-three
  fully contained June rows on each page are exactly the twelve manifest rows
  (ServiceNow, Blue Diamond Growers and Dignity Health CHMC are correctly the
  fourth rows outside the windows). All twelve match decisions were re-checked
  against the live public API: the eleven `matched` decisions resolve to
  eleven distinct canonical events with identical employer/count/effective
  date/type, and the one no-match (p19-first-01, HealthCare Partners Arcadia)
  was re-confirmed — event 392's retained source excerpt is the distinct
  Washington Blvd Closure notice, and the tracker holds four rows against
  five official notices. The same-underlying-event rule was re-checked in
  both directions on the hardest case (Uber: sampled 06/12 count-3 notice vs
  the three 06/03 notices → separate events 464/465/466). Period boundary:
  all twelve notice dates in 2026-06-01..2026-06-30. Arithmetic verified:
  denominator 12, numerator 11. `GET /benchmarks/recall` was empty and no
  numerator/percentage is recorded anywhere in the repository. The manifest's
  `publication_status` is now `publication_reviewed_ready_to_retain` with a
  full `publication_review` block.)*
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

All three review passes are complete (2026-07-18, by three distinct actors:
transcription reviewer, matching editor, publication reviewer). The reviewed
figures are reference_events = 12, matched_events = 11. The publication
reviewer weighed the known limitation that retained tracker WARN excerpts do
not carry notice-date/worksite context: for the eleven matches, employer plus
count plus effective date plus type was unique within the period in every
case (verified against the official PDF in both directions for the Uber
case), and the one ambiguous constellation (HealthCare Partners) was resolved
to a no-match, the conservative direction. The remaining steps are purely
mechanical and reserved to the API-key holder:

1. Commit the reviewed manifest so it is reachable at a stable public GitHub
   URL (it retains the no-match row and states `independent_manual_sample`
   as its basis).
2. POST the bounded figures to `/benchmarks/recall` with that URL (see the
   manifest's `publication_review.remaining_steps_for_key_holder` for the
   exact fields). The public label must say "California WARN sample recall,
   June 2026" and "not a completeness or accuracy measure."

Until both steps happen, no recall number exists publicly; do not infer one
from WARN import counts.
