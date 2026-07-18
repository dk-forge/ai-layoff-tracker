# California WARN June 2026: independent audit (unpublished)

Status: **blocked - no recall result has been calculated or posted.**

This is an independent source-and-candidate audit of the fixed twelve-row
California WARN sample in
[`ca-us-2026-06.warn-draft.json`](ca-us-2026-06.warn-draft.json). It is not a
reviewed benchmark manifest and is not an input to the public recall endpoint.

Audit time: `2026-07-18T05:52:03Z`  
Audit actor: Codex independent audit pass  
Tracker read endpoint: `GET /blog/wp-json/layoffs/v1/query` and
`GET /blog/wp-json/layoffs/v1/event/{row_id}/sources`

## Official-document verification

The official California EDD PDF was retrieved once from the fixed public URL
in the draft. Its SHA-256 was independently recomputed as
`c4239543ffcf87e406005c99b2282f757cbd0e4f7b102f3ea4bdaa33aeabc4df`, matching
the sealed draft; it was 754,005 bytes and 22 PDF pages. The table pages
carrying PDF text markers P19 and P20 (physical PDF pages 20 and 21) were
visually reviewed. All twelve draft transcriptions match the official rows for
company/site, county, notice/received/effective date, count, and stated
layoff/closure type.

## Candidate lookup results

Each public tracker candidate below is a California WARN canonical event with
the same company, count, effective date, and official CA WARN landing-page
source. This is **not** a completed match decision: current retained tracker
source excerpts omit the notice date, county, and worksite address, and point
to the CA WARN landing page rather than the specific closed-report PDF. The
protocol requires source-level confirmation of the same underlying notice.

| Reference row | Candidate event ID | Public row ID | Result of independent comparison |
| --- | ---: | ---: | --- |
| `ca-warn-2026-06-p19-first-01` | 392 | 26517 | **Unresolved:** same company/count/effective date, but tracker says `Closure / Permanent`; official row says `Layoff / Permanent`. |
| `ca-warn-2026-06-p19-first-02` | 393 | 26518 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p19-first-03` | 497 | 26622 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p19-last-01` | 432 | 26557 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p19-last-02` | 445 | 26570 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p19-last-03` | 446 | 26571 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-first-01` | 433 | 26558 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-first-02` | 379 | 26504 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-first-03` | 413 | 26538 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-last-01` | 468 | 26593 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-last-02` | 376 | 26501 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |
| `ca-warn-2026-06-p20-last-03` | 382 | 26507 | Provisional candidate; company/count/effective date/type align, but notice/site evidence is absent from retained tracker source. |

## Publication decision

Do not alter the sealed draft's pending decisions, calculate a numerator or
percentage, or post to `/benchmarks/recall`.

Publication remains blocked for three independent reasons:

1. The HealthCare Partners one-job record has a type discrepancy that needs a
   source-preserving correction or an explicit no-match conclusion.
2. For all twelve candidates, the retained tracker report does not itself
   preserve enough notice/site context to complete the protocol's same-notice
   check against the fixed PDF.
3. The required independent publication reviewer has not checked every final
   decision. This audit deliberately records no `matched` or `not_matched`
   decisions, so it cannot serve as that review.

The appropriate next step is to preserve an official-report citation (or
source excerpt containing the notice date and worksite) on each candidate,
resolve the one type discrepancy without overwriting source evidence, then
perform the protocol's separate matching and publication-review passes.

## Addendum — 2026-07-18 transcription review corrected the selection

Reviewer: Claude Opus 4.8 independent transcription review pass (distinct from
the Codex audit above and from any future matching editor).

The review re-retrieved the official PDF (SHA-256 and byte size matched the
sealed values) and confirmed all twelve draft transcriptions field-by-field,
consistent with the audit above. It additionally inspected rendered page
images at the three page boundaries, which the text-layer review above did
not, and found the draft selection deviated from the pre-committed positional
rule in all three places:

- Leggett & Platt (2026-06-15, 125, Closure/Permanent) is the fully contained
  last June-notice row of P19 and was omitted; ServiceNow is fourth-from-last.
- Uber Technologies, Inc. (2026-06-12 notice, 3, Layoff/Permanent) is the
  fully contained first June-notice row of P20 and was omitted.
- Ballast Point Brewing Company (2026-06-29 notice, 19, Closure/Permanent) is
  the fully contained last June-notice row of P20 and was omitted.

Because no match decision existed, the manifest selection was corrected to
conform to the rule before any matching pass. Consequences for this audit:

1. The candidate rows recorded above for `p19-last-01` (ServiceNow, event
   432 / row 26557), `p20-first-03` (Blue Diamond Growers, event 413 / row
   26538) and `p20-last-01` (Dignity Health CHMC, event 468 / row 26593)
   refer to companies no longer in the sample; the remaining candidate rows
   now correspond to shifted slot IDs. Treat the whole table as historical
   context, not a shortlist for the corrected sample.
2. The three newly added reference rows have had **no tracker lookup of any
   kind**, so their pre-lookup independence is intact.
3. The HealthCare Partners type-discrepancy finding (official
   `Layoff / Permanent` vs tracker `Closure / Permanent`) still stands and
   still requires a source-preserving resolution.

Publication remains blocked pending the separate matching pass and the
independent publication review.
