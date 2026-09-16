# What a Spain (Illes Balears) reference event IS — written before any number was measured

This document is committed **before** the register is enumerated, as
`UK-REFERENCE-SET-DEFINITION.md` and `US-WARN-REFERENCE-SET-DEFINITION.md` were,
and for the same reason: the frame, the window, the eligibility rule, the
matching rule and the stated biases must be fixed while they can still be
chosen honestly. If a later commit changes any of it, the git history says so
and the number is re-derived, not patched.

**No number appears in this document, and none was seen before writing it.**
Nothing was fetched: the session that wrote this has no outbound HTTP (see §8).
Every fact below is read out of this repository's own committed registers —
`railway/country_coverage.py` (the `PER_EMPLOYER_REGISTERS` entry for Illes
Balears, `verified_from_file: 2026-08-19`) and `railway/erm_import.py`.

---

## 1. Why this set exists, and why it is the only European one

The merged assessment of 2026-09-15 (`docs/TECHLOG.md`, PR #361) found that
"European event-recall" is a category error for five of six requested countries.
The only denominator that supports the word **recall** is one that enumerates
**identifiable events**. A labour ministry publishes a periodic count of
affected workers or of procedures with no identities attached; our stored total
over that is *share of the official total*, and `country_coverage.py` forbids
printing such a share beside the Item 2.05 band.

Naming the employer is what turns a total into a set of events. By this
repository's own survey, **four jurisdictions on earth do it**: US state WARN
units, Quebec, Mazowieckie, and the Illes Balears. Balears is the only one in
Europe. That is the entire reason this set is possible and the other five
countries' are not.

Corroboration is recorded rather than assumed: ASEDIE's 2026 infomediary report
finds eleven Spanish autonomous communities publish ERE/ERTE datasets and that
**only Baleares includes the NIF or razón social**. Euskadi — the best near-miss
— was settled by downloading `eres_cae.csv`: sixteen columns, employer present
only as a masked CIF on 216 of 216 rows, zero unmasked. Euskadi is not one
un-redaction away from being a register; the name is not in the publication.

## 2. The source

**Dataset:** *Expedients Regulació Ocupació (ERO i ERTO) Illes Balears*
**Catalogue:** `https://intranet.caib.es/opendatacataleg/dataset/expedients-regulacio-ocupacio-ero-erto-illes-balears`
**Licence:** CC-BY 4.0 — attribution required in any published figure.
**Verified from the file, not from the catalogue page:** 2026-08-19.
**Shape:** 49 columns, 3,817 rows. `EMPRESA` is populated on every row.

Columns this set uses: `EMPRESA`, `NIF`, `DATA PRESENTACIO`, `MUNICIPI`,
`ILLA`, `NUM. TOTAL TREBALLADORS`, `TREBALLADORS AFECTATS INICIAL`,
`CODI CNAE 09`, `CAUSES`, `MESURA`.

## 3. Eligibility — and it removes most of the file

Three filters apply, in this order. Each one exists because including the rows
it removes would manufacture misses that say nothing about this tracker.

**(a) `MESURA` must be `EXTINCIO`.** The register mixes collective dismissal
with short-time work. The split is `SUSPENSIO` 1,747 / `RED. JOR.` 971 / blank
740 / `EXTINCIO` 359. **Only `EXTINCIO` is a collective dismissal**; the rest is
the ERTE near-miss that recurs across Spain. A tracker of layoffs is not wrong
to be absent from a short-time-work row, so those rows are not part of the
frame.

**(b) `DATA PRESENTACIO` must fall in 2015-01-01 .. 2022-12-31.**
Two independent bounds meet here and the window is their intersection:

- *Upper.* The companion 2023–2025 file is ERTO-only and the catalogue marks the
  dataset **"No s'actualitza"**. Named dismissal rows effectively stop at 2022.
- *Lower.* `erm_import.py` documents `ERM_MODE=full` as "entire history
  **>= 2015-01-01**". Europe reaches this tracker mainly through the European
  Restructuring Monitor, and our ERM backfill does not go behind 2015. A 2009
  Balearic dismissal is outside what any collector we run was ever asked to
  hold, so counting it as a miss would measure our backfill boundary, not our
  coverage. The separate date-bound rule points the same way: the LLM path
  (`extractor.py`) nulls any `layoff_date` before 2015.

**(c) The event must clear ERM's own inclusion threshold.** `erm_import.py`
documents it: **>= 100 jobs, or >= 10% of a 250+ site** — "small events are
absent by design (disclosed in the tracker methodology)". Concretely, a row is
eligible when `TREBALLADORS AFECTATS INICIAL >= 100`, **or**
`NUM. TOTAL TREBALLADORS >= 250` and
`TREBALLADORS AFECTATS INICIAL / NUM. TOTAL TREBALLADORS >= 0.10`.

Holding a tracker to account for an event its declared threshold excludes is not
a recall measurement, it is a category error of the same family as §1.

**Expect (a)–(c) to leave a small frame.** 359 `EXTINCIO` rows span 2008–2022
before any filter; (b) and (c) both cut into that. **This is stated now, before
counting, so that a small n is not a disappointment to be engineered around
later.** If the eligible frame is small the interval will be wide, the wide
interval is the honest result, and it is reported as such. The frame is **not**
widened afterwards by relaxing (a), (b) or (c) to obtain a tighter number — that
is the one move this document exists to prevent.

## 4. One event

One event per `(NIF, DATA PRESENTACIO)`. `NIF` rather than `EMPRESA` because a
fiscal identifier is stable across the spelling, accent and legal-form variants
that a company-name key collapses wrongly. Where `NIF` is absent, the key falls
back to `(collapsed EMPRESA, DATA PRESENTACIO)` and the row is flagged
`key: name_fallback` so a reviewer can see which rows carry the weaker key.

If the register lists several rows for one employer on one presentation date,
they are one event and the affected count is the sum.

## 5. Census, not sample

Given §3, the eligible frame is expected to be small enough to enumerate
completely. **Take every eligible row.** There is then no sampling error and no
seed to defend — the only uncertainty is binomial, from the size of the frame
itself.

If the eligible frame exceeds 200 events, draw a systematic sample of 200 with a
seed recorded in the manifest, ordered by `DATA PRESENTACIO` then `NIF`.

## 6. Matching, and who decides

The tracker is consulted **only** to decide matched / missed / UNKNOWN, never to
assemble the frame. A set assembled by first searching this tracker measures
nothing.

**Nothing in this set is adjudicated by a machine.** Every event ships
`match_decision: not_matched`, exactly as the US WARN and UK sets do, so the
editor-confirmed numerator starts at zero by construction. The machine's
proposal is reported beside it as an explicit **upper bound**, split into
`exact` and `loose` tiers so a reviewer can see which tier carries the number.
The precedent is recorded and is not flattering to the machine: on the US set
the machine's loose rule scored 31 where the editor scored 24.

A candidate is proposed when the employer name matches under
`recall_goldset.name_matches` **and** the tracker row's date falls within the
match window of `DATA PRESENTACIO`. Job count is reported as a flag, never as a
match criterion — a register's *initial* affected count and a later reported
figure differ legitimately.

`UNKNOWN` is a third state and is never folded into either of the others: it is
recorded when the tracker cannot be queried, or when a row's key is ambiguous.
Absence of a signal is not a pass.

## 7. Stated biases, before the number

- **`in_tracker: False` — and this is the most important line in the document.**
  The register records that we do **not** ingest Balears. So a miss here does not
  mean a collector we run failed; it means our general net (ERM, plus news) did
  not independently pick the event up. That is a **weaker and different claim**
  than the US WARN set makes, and the published wording must say so. This set
  cannot be quoted as "recall of our Spanish collector", because there is no
  Spanish collector.
- **The window is historical.** Any figure from this set describes **2015–2022**
  and is not a statement about current coverage. A recall figure over a closed
  historical window is a legitimate thing to want; it is not the same claim as a
  current one and must never be displayed as one.
- **One island region, not Spain.** Balears is roughly 1% of Spanish employment
  and is tourism-weighted (`CODI CNAE 09` will show it). The result does not
  generalise to Spain and the country page must not imply that it does.
- **Direction of bias is not asserted.** A small, tourism-heavy region may be
  covered better (concentrated local press) or worse (outside the
  trusted-domain list) than the tracker's average. This document does not guess
  which, and neither should the write-up.

## 8. What has NOT been done, and by whom it can be

**Nothing has been fetched.** The session that wrote this document has no
outbound HTTP at all — `dol.ny.gov`, `data.texas.gov`, `openrouter.ai` and
`example.com` alike return `Tunnel connection failed: 403 Forbidden`; only
`api.github.com` answers. So the register has not been downloaded, the frame has
not been enumerated, and the tracker has not been queried, in this session.

Execution therefore needs a session with egress. What it must do, in order:

1. Download the dataset from the CC-BY catalogue URL in §2 under the project UA.
2. Apply §3 (a)(b)(c) and §4 and report the frame size **before** querying the
   tracker.
3. Build the manifest with every row `not_matched`, per §6.
4. Query the live API for candidates; write the measurement file separately from
   every existing one, as `warn_reference_set.py` does, so no module can reach
   the published SEC figure.
5. Hand the queue to the owner. **The editor decides the rows.**

Wilson 95% intervals throughout (`recall_goldset.wilson`), and the country page
derives the figure from the committed file rather than having it typed — the
cadence lesson of 2026-08-14 applies to measurements too.

## 9. If the honest answer turns out to be "too small to publish"

That is a legitimate result and is recorded rather than papered over. A frame of
a dozen events yields an interval so wide that the point estimate carries no
information, and publishing it beside the Item 2.05 band would imply a
comparability that does not exist. In that case the finding to publish is the
one this document already establishes without any number: **Europe has exactly
one per-employer dismissal register, it stops in 2022, and we do not ingest it.**
