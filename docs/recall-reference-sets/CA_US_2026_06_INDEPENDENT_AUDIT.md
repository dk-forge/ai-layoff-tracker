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

## Addendum — 2026-07-18 root-cause investigation of the HealthCare Partners type discrepancy

Investigator: Claude Opus 4.8 (read-only investigation pass; no tracker data,
draft rows, or match decisions were changed).

### What the two datasets actually say

The official PDF was re-retrieved from the fixed URL; SHA-256
(`c4239543ffcf87e406005c99b2282f757cbd0e4f7b102f3ea4bdaa33aeabc4df`) and byte
size (754,005) again match the sealed values. The full 22-page report contains
exactly five HealthCare Partners rows, all on the P19 table page, all with
notice date 06/01/2026:

| Received | Company | County | Count | Type | Worksite | Effective |
| --- | --- | --- | ---: | --- | --- | --- |
| 06/01/2026 | HealthCare Partners Medical Group, P.C. | Los Angeles | 1 | Layoff Permanent | 450 East Huntington Drive, Arcadia CA 91006 | 08/28/2026 |
| 06/01/2026 | HealthCare Partners Medical Group, P.C. | Los Angeles | 4 | Layoff Permanent | 11600 Indian Hills Road, Los Angeles CA 91345 | 08/28/2026 |
| 06/01/2026 | HealthCare Partners Medical Group, P.C. | Los Angeles | 2 | Layoff Permanent | 3565 Del Amo Boulevard, Torrance CA 90505 | 08/28/2026 |
| 06/02/2026 | HealthCare Partners Medical Group, P.C. | Los Angeles | 1 | **Closure Permanent** | 1120 W Washington Blvd., Los Angeles CA 90015 | 08/28/2026 |
| 06/02/2026 | HealthCare Partners Group, P.C. | Los Angeles | 1 | Layoff Permanent | 420 W. Rowland Street, Covina CA 91723 | 08/28/2026 |

The sampled reference row `ca-warn-2026-06-p19-first-01` (received 06/01,
1 employee, Layoff / Permanent) is the **Arcadia** row. The draft
transcription is correct.

The public tracker (`/query?company=HealthCare Partners&state=CA`) holds only
**four** rows: 26517 (event 392, Medical Group, 1, excerpt "Closure
Permanent…"), 26518 (event 393, Medical Group, 4, "Layoff Permanent…"),
26519 (event 394, Medical Group, 2, "Layoff Permanent…"), 26520 (event 395,
Group P.C., 1, "Layoff Permanent…"). `/event/26517/sources` retains a single
CA WARN source report whose excerpt is the "Closure Permanent" text (evidence
hash `943194583e62148b216737ac1ca2ff083b5c47929458554162c5366eaa87e8fe`).

### Root cause: two official notices hash-collided into one tracker row

Five official rows became four tracker rows because the two 1-employee
Medical Group notices (Arcadia, Layoff Permanent; Washington Blvd, Closure
Permanent) collapsed into the single row 26517. Mechanism, verified in code:

1. `railway/sources/warn.py` builds the WARN dedup hash as
   `md5("warn" + company + effective_date + jobs + city + state)` (the
   `hash_input` assignment, ~line 266). No worksite address, county, received
   date, or layoff/closure type participates.
2. For current-fiscal-year California rows, the upstream `warn-scraper` CA
   collector parses EDD's Excel workbook and emits columns `county, notice_date,
   received_date, effective_date, company, layoff_or_closure, num_employees,
   address` — it never populates the `city` column (only legacy PDF-era rows
   have it). So `city` is empty for every current CA row (visible in the live
   excerpts: none contain the "in {city}" clause), and the intended
   city discriminator documented in ARCHITECTURE.md ("its hash also includes
   city+state") is vacuous for CA. Both 1-employee notices therefore produce
   the identical hash `md5("warnhealthcare partners medical group, p.c.2026-08-281CA")`.
3. The layoff/closure type is not a schema field at all: `warn.py` reads it
   into `kind` (header match on "closure") and bakes it only into the excerpt
   string, so the type survives solely as prose evidence.
4. `alt_db_upsert()` (`wordpress-plugin/ai-layoff-tracker/includes/db.php`,
   the `$existing` branch) does a full-row `UPDATE` when an incoming entry's
   dedup hash matches a non-edited row — last write wins. The Washington Blvd
   closure notice was processed after the Arcadia layoff notice, so its
   "Closure Permanent" excerpt overwrote the Arcadia one. The single retained
   source report on row 26517 carries only the Closure excerpt.

### Verdict

- **The draft transcription is right** and needs no change: the sampled
  official row is Layoff / Permanent.
- **The tracker row 26517 is not a mis-scrape** — its "Closure Permanent"
  text is a faithful copy of a *different, equally real* official notice
  (Washington Blvd). The defect is conflation: one tracker row silently
  represents two distinct site notices, the Arcadia layoff notice has no
  distinct record or retained evidence anywhere, and the company's aggregate
  count is understated by 1.
- Consequently row 26517, as evidenced, describes the Washington Blvd closure
  notice, **not** the sampled Arcadia notice. Under the current data the
  honest matching-pass outcome for `ca-warn-2026-06-p19-first-01` is
  `not_matched` (a recall miss), unless the correction below lands first.

### Source-preserving correction path (not executed; no data was changed)

A type-only edit of row 26517 via the `/edit` endpoint (`edit-entries`
workflow) is the **wrong** fix, for three reasons: (a) the type lives only in
the excerpt/retained evidence, and rewriting "Closure" to "Layoff" would
falsify the genuine evidence of the Washington Blvd closure notice; (b)
`/edit` pins `edited=1` and suppresses the original hash, permanently
blocking imports from ever splitting the row into the two real notices; (c)
it still leaves one row representing two notices, so the sample row remains
substantively unmatched.

The correct fix is at ingest, and because it changes dedup hashes it must
follow the purge-and-reload rule (CLAUDE.md: hash-affecting corrections need
`/bulk-purge` + full re-import, never plain upsert — a plain re-import would
duplicate essentially every California row):

1. **Code change** in `railway/sources/warn.py`: add a worksite discriminator
   to `hash_input` — capture `address = _match(rl, ["address"])` and use
   `city or address` in the hash (city stays first so states with real city
   columns keep their existing hashes where possible; CA rows gain the
   address). Recommended in the same change, because it directly clears this
   audit's blocking reason #2: include the worksite and notice date in the
   generated excerpt (e.g. "Closure Permanent at {company}, {address}. …
   Notice dated {notice_date}, effective {date}."), so retained WARN evidence
   can satisfy the protocol's same-notice check.
2. **Reload** via the existing GitHub workflow `warn-import.yml` ("WARN
   notice import (US states)"), manual `workflow_dispatch` with inputs
   `states: all`, `purge: 1` (other inputs default). That runs
   `railway/warn_import.py`, which POSTs the keyed `/bulk-purge` endpoint
   (deletes table-only WARN rows) and then re-POSTs everything through the
   keyed `/bulk` endpoint in 1,000-row batches. Built-in guardrails already
   enforce safety: purge refuses to run unless `WARN_STATES=all` and the
   fresh scrape returned >= 5,000 notices, and any rejected batch fails the
   workflow loudly.
3. **Expected result**: the tracker gains distinct rows for the Arcadia
   1-employee Layoff notice and the Washington Blvd 1-employee Closure
   notice (plus previously collided rows in other CA companies, if any).
   All WARN row ids and event ids are reissued by the purge, so every
   candidate id recorded in this audit becomes historical; the matching pass
   must re-run its lookups afterwards. `ca-warn-2026-06-p19-first-01` should
   then match the new Arcadia row cleanly on company, count, effective date,
   type, and (with the excerpt improvement) worksite and notice date.

No draft field, tracker row, or match decision was modified by this
investigation. Publication remains blocked as stated above.
