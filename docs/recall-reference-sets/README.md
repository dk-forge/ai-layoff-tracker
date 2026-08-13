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

## United Kingdom (2025-07 → 2026-06)

`UK-REFERENCE-SET-DEFINITION.md` is the **definition, written and committed
before any UK number existed**, and it should be read before the manifest. It
records what was tested and what each route actually returns, because the
headline UK finding is a negative one and negatives rot fast if only their
conclusion is kept:

- **HR1**, the UK's statutory advance notification of collective redundancies,
  is the closest analogue to Item 2.05 in scope and is **published as monthly
  aggregates only**. Employer-level release has been refused under FOIA
  s43(2)/s43(3), including a neither-confirm-nor-deny for a single named
  company. Northern Ireland and Scotland are not loopholes.
- **The FCA National Storage Mechanism** is the only complete index of UK
  regulatory announcements, it does support free text over document content,
  and its `robots.txt` carries `User-agent: ClaudeBot / Disallow: /`. It was
  not enumerated and its search API was not probed.
- **The Gazette** is fully usable and carries no headcounts. **LSE** has no
  free-text search over announcement bodies. **BBC** and **Guardian** forbid the
  enumeration in robots/terms and are both domains we already collect.

So there is **no UK equivalent of EDGAR full-text search**, and the UK set is
therefore a **different event type from the US set**, enumerated from a
different kind of frame. That is stated rather than disguised.

Two rules, the same two the SEC set carries:

1. **It is never posted to `/benchmarks/recall`.** Internal regression
   reference, one author, `publication_status` says so and the test asserts it.
2. **Its number is not "our UK recall".** It describes one frame over one
   twelve-month window, with the biases the manifest lists.

`railway/recall_uk_goldset.py` measures it and **imports** the interval, the
prefix matcher and the alias/window rule from `recall_goldset.py` — one
definition, so a second copy of the Xperi/Experian bug cannot appear. It ships
with **no floor armed**, which judges to UNKNOWN rather than PASS: a floor set
by the same run that produced the number is a rubber stamp, not a tripwire.

`railway/uk_recall_probe.py` answers the question worth more than the
percentage — *which stage dropped this event* — and makes no model call, so the
model half of the last stage is UNKNOWN until someone authorises the spend.

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

## US state WARN set (CA/TX/FL/TN, 2025-07 → 2026-06)

`us-warn-ca-tx-fl-tn-2025-07_2026-06.goldset.json` is the **fourth kind of file**
here and the first one to measure a source family other than SEC EDGAR. Its
definition —
[`US-WARN-REFERENCE-SET-DEFINITION.md`](US-WARN-REFERENCE-SET-DEFINITION.md) —
was committed **before the first tracker query**, in its own commit, and its
results are in [`US-WARN-RESULTS-2026-08.md`](US-WARN-RESULTS-2026-08.md).

It exists because the SEC set can only see **public companies that file 8-Ks**.
It has no state dimension, no industry dimension and no private employers.
State WARN notices are mandatory disclosure, already inside the pipeline, and
cover exactly the employers Item 2.05 cannot.

| | SEC Item 2.05 | US WARN |
|---|---|---|
| Frame | one regulator index | four separate state publications |
| Enumerated from | EDGAR full-text search | a fiscal-year PDF, a Socrata dataset, two HTML tables |
| Unit | one filing | one (state, employer, notice date) — several notices for one action collapse |
| Denominator | 57 | 100 primary + a 33-event large-event census |
| Stratified by | nothing | state and event size |
| Editor-confirmed | 56 of 57 | **0 of 100 — nothing is adjudicated** |
| Machine upper bound | — | 99 of 100 |
| Read by | `recall_goldset.py`, `data_integrity`, CI | `warn_reference_set.py` only |

Four rules about it:

1. **It never touches the SEC figure.** `railway/recall_measurement.json`,
   `railway/recall_adjudications.json`, the SEC manifest and `MATCHED_FLOOR` are
   not written by anything in this set, and
   `railway/tests/test_warn_reference_set.py` asserts no module here can even
   name them outside a docstring.
2. **It is never posted to `/benchmarks/recall`.** One author, no three-actor
   chain, same rule as the SEC set.
3. **Its 99 of 100 is not recall.** Nothing is adjudicated; the editor-confirmed
   figure is zero and the queue is
   [`us-warn-adjudication-queue.md`](us-warn-adjudication-queue.md). Every line
   of that sheet describes exactly one candidate row, named by its id, because on
   2026-08-12 a pooled line lost the SEC set a correct Dow acceptance — and a row
   with nothing wrong is SAID to have nothing wrong, which is the other half of
   that failure. The sheet states the range before the first decision: 100/100 if
   everything including Wood Group is accepted, 99/100 if Wood Group is not,
   67/100 if only the events agreeing on count, date basis AND employer name are
   (and whose row is not also proposed for another notice),
   and 0/100 as it stands. **Wood Group has no candidate row and is a section of
   its own above the index, not a row in a list of ninety-nine.**
4. **It cannot speak for the Midwest or the Northeast.** NY, PA, IL, OH, GA, NC,
   NJ, MI and MA were excluded because their own WARN lists are JavaScript-only,
   a proprietary BI extract, or 404. VA and MD were excluded because their
   `robots.txt` asks agents like this one not to read them, and the convenient
   source does not get an exception. See the definition, §2.

Rebuild: `python3 railway/warn_reference_set.py --build`, then `--measure`, then
`python3 railway/warn_adjudication_pack.py --write`. No model is called; the cost
is $0.00.
