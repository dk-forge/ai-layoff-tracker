# July / August 2026 US accuracy audit

**Measured 2026-09-16** against the live aggregate and query endpoints, US only,
plugin 2.20.195. Every figure below is reproducible from the public API; nothing
here was hand-counted.

No comparator is named anywhere in this document. Where a second series is
referred to it is "an independent public series", and its figures live only in
the gitignored local benchmark.

---

## 1. The signal

| Month | ours, `date_basis=notice` | ours, `date_basis=announced` | an independent public series |
|---|---|---|---|
| July 2026 | 56,023 jobs / 287 events | 86,035 / 354 | 33,429 |
| August 2026 | 41,688 / 325 | 41,138 / 302 | 52,881 |

Ours falls July to August; the other series rises. Changing the date basis does
not reconcile it, so it is not a basis artefact.

**Both a real defect and a real difference of population are present, and they
point in opposite directions.** Two July rows are provably wrong and worth
26,000 jobs between them. The rest of the divergence is not a defect at all: it
is what happens when a WARN-dominated series is compared against an
announcement-dominated one.

---

## 2. What our number is actually made of

Neither month is what a reader would guess from the headline.

| | July (announced basis) | August (announced basis) |
|---|---|---|
| WARN rows | 313 rows / 39,649 jobs | 263 rows / 25,762 jobs |
| news rows | 29 rows / 23,589 jobs | 32 rows / 10,285 jobs |
| 8-K rows | 8 rows / 22,753 jobs | 7 rows / 5,091 jobs |
| federal RIF rows | 4 rows / 44 jobs | 0 |
| **total** | **354 / 86,035** | **302 / 41,138** |

**88% of July's rows and 87% of August's are state WARN notices.** Only 10 July
rows and 6 August rows are flagged `announced` — that is, corporate
announcements of the kind an announcement-based series is built from
(`announced_jobs`: 14,474 in July, 5,123 in August).

This matters more than any single correction. A WARN notice is a legally
required filing about a specific worksite, filed on the employer's own schedule;
a corporate announcement is a company telling the press a number. The two
populations overlap but neither contains the other, and their month-to-month
shapes are driven by different things. A month-over-month **direction**
disagreement between them is expected and is not by itself evidence of a defect
on either side.

---

## 3. Hypothesis A — July over-count. CONFIRMED, 26,000 jobs.

### A1. A third party's number attributed to the filer — 20,000 jobs

**Row 176990**, `Aeternum Health, Inc.`, 20,000 jobs, source_type `8K`,
`layoff_date` 2026-07-07, verification level `gold`.
Source: `https://www.sec.gov/Archives/edgar/data/764630/000149315226032365/form8-k.htm`

**This company laid off nobody.** The 20,000 is read out of a regulatory
**risk-factor** paragraph describing the **US Department of Health and Human
Services'** March 2025 restructuring. The filing was read directly for this
audit. The paragraph runs:

> "on March 27, 2025, the U.S. Department of Health and Human Services (HHS) …
> announced that it intends to reduce our workforce by approximately 10,000
> full-time employees … which in combination will result in a reduction of force
> by 20,000 employees."

The trap is the word **"our"**: the filing quotes HHS's own press language
verbatim, so "our workforce" is HHS's workforce, and the extractor bound it to
the registrant. The registrant is a micro-cap shell (52m shares, negative
shareholders' equity, $10,000/month of consulting fees) with no workforce of
this order.

Three independent things are wrong in one row, and each is checkable without
judgement:

1. **The employer is wrong.** The cuts are a federal agency's, not the filer's.
2. **The count is unsupported for this event.** Rule 3 of the adjudication
   rules: a count the source does not state *for this event* is unsupported.
3. **The date is wrong, and the row says so itself.** The stored
   `announcement_date` is 2025-03-27 — 467 days before its own `layoff_date` of
   2026-07-07. The row contradicts itself in its own fields.

It is also, in substance, a fourth error: HHS reductions are already carried
under the `federal_rif` source type, so this row double counts a population we
already hold.

**20,000 jobs — 23.2% of the entire published July US headline — in one row.**

### A2. One article counted twice under two spellings — 6,000 jobs

**Rows 177161** (`Los Angeles Unified School District`) and **176442** (`LAUSD`).
Both store exactly 6,000 jobs. Both cite **the same Google News article URL,
character for character**. Both are `news`, one day apart (2026-07-21 and
2026-07-22), both `bronze`, and they carry different `event_id`s (149894 and
149191), so the superset machinery never joined them and `/aggregate` sums both.

There is no judgement in this one. It is one article, one number, two rows.

**Why nothing caught it.** Every existing dedup defence buckets on a company
name first, so "Los Angeles Unified School District" and "LAUSD" make two
buckets and the pair is never proposed, never compared, never judged — at zero
cost, forever. `duplicate_shape_scan.py` was written for exactly this class and
names LAUSD in its own docstring, but it reports and never merges, and this pair
was still live. `headline_concentration` cannot see it either: each row is 7% of
the July headline, individually unremarkable.

### A3 and A4 — real, but NOT closed here

Two further rows are wrong or probably wrong. Neither is resolved in this audit,
and neither is counted in the 26,000.

**Row 134521, `Ideal US Talent Systems Worker OpCo LLC`, 9,891 jobs, state RI —
11.5% of the July headline.** Its own excerpt reads "Layoff at … **in
Minneapolis, MN**. 9,891 employees affected … Filed under the RI WARN Act." A
sibling row, **26778**, carries the *same* source URL and the *same* excerpt text
but a `job_count` of **2**. The two rows contradict each other about one register
line.

This shape is already known: `test_headline_guards.py` opens by naming
"RI 98,912 (a '9,891 … (2 from RI)' misparse)" as an incident the shape guards
were written from. **The misparse it names is still live, at 9,891, in the
published July number.** Resolving which of 9,891 and 2 the RI register actually
states needs the register read, which is a judgement call and belongs in the
two-model adjudication. Until then it is **UNKNOWN and must not be rounded into
a correction.**

**Rows 70479 (`Meta`, news, 1,400, WA) and 134376 (`Meta Platforms, Inc`, WARN,
1,395, King County WA)** — same employer, same state, same day, counts 0.4%
apart. This is the news-over-WARN superset case that `superset_of` exists for,
and it was not joined; roughly 1,400 jobs are double counted. Distinguishing "the
news report is the superset of this WARN filing" from "these are two disclosures"
is a judgement call. **Adjudicate, do not assume.**

### July, before and after

| | jobs | note |
|---|---|---|
| published (announced basis) | **86,035** | as live on 2026-09-16 |
| less row 176990 (Aeternum / HHS) | −20,000 | unambiguous, verified against the primary filing |
| less one LAUSD copy | −6,000 | unambiguous, identical article URL |
| **after the proven corrections** | **60,035** | entries 354 → 352 |
| *less the Meta WA superset, if adjudicated as one event* | *−1,395* | *not applied* |
| *less the RI misparse, if adjudicated* | *up to −9,889* | *not applied* |

**The two bases are not affected equally, and this is worth stating carefully.**
Row 176990 is *not* in the `notice`-basis July set at all: on that basis it is
dated by its `announcement_date` of 2025-03-27 and lands in March **2025**. So
on the `notice` basis only the LAUSD duplicate applies, taking **56,023 →
50,023** (entries 287 → 286).

That asymmetry is itself a finding. The same row is simultaneously a 20,000-job
July event on one published basis and a March-2025 event on the other, because
its two date fields describe two different things — which is what a row whose
number was lifted from a third party's press language looks like from the
outside.

Hypothesis A therefore explains **26,000 jobs of the July announced figure with
certainty (6,000 of the notice figure), and up to 37,284 announced if both open
questions resolve against the stored values.**

---

## 4. Hypothesis B — August under-count. NOT MEASURED. UNKNOWN.

This is an honest UNKNOWN, not a negative result, and it should not be reported
as one.

Both named instruments were tried and neither can answer a **retrospective**
question:

- **`tracker_diff.py --learn`** reads a GDELT window anchored to *now* and capped
  at 168 hours by `TRACKER_LEARN_WINDOW_HOURS`. It cannot reach August. Run on
  2026-09-16 it answered `cadence quiet` — the earned cadence has stepped down to
  Mondays, which is the shipped behaviour after three ruleless runs. **Do not
  answer a quiet loop by lowering `RULE_FLOOR`** or by widening the window knob to
  reach a month the machine was not built to re-read.
- **`curated_probe.py`** needs a hand-fed worklist in
  `scratchpad/recall-worklist.txt`, which only the owner can supply, and it has
  no workflow by design — a runner that could read the worklist is the leak.

What can be said from the corpus, as shape rather than as a number: August
carries **6 rows flagged `announced`, worth 5,123 jobs**, against July's 10 rows
and 14,474. If August genuinely held more large corporate announcements than
July, that is where they would be, and they are not there. That is *consistent*
with an under-count, and it is not evidence of one. Nothing here establishes a
single named August miss.

**To close this properly:** the owner pastes an August roundup into
`scratchpad/recall-worklist.txt` and runs `curated_probe.py` per the RUNBOOK.
That is $0.00, stores no row, calls no model, and produces a named,
cause-classified miss list (`recoverable` / `vocabulary_gap` / `unreachable`).
It is the only instrument that answers this question, and it needs a human to
start it.

---

## 5. So are the two series comparable?

**Partly, and not in the way the table implies.**

After the two proven corrections, July stands at 60,035 against an independent
33,429. Ours remains the larger number, which is expected: 88% of our July rows
are WARN filings, and an announcement-based series does not count a WARN notice
as an announcement at all. A series that includes WARN should be *higher* than
one that does not, in most months.

August is the opposite: 41,138 against 52,881, with only six announced-corporate
rows all month. That direction is the one that should worry us, and it is exactly
the direction Hypothesis B predicts. We could not test it.

**The honest summary: one real over-count of 26,000 jobs in July, a possible
under-count in August that we have not measured, and a genuine
population difference underneath both that no correction will remove.** The two
series should never be presented as measuring the same thing.

---

## 6. The guard

`data_integrity.DuplicateArticleInvariant` (`duplicate_article_rows`) asserts
that **no two rows cite the same article for the same job_count under different
event ids**, over the largest rows of a trailing 180-day window, read from the
same superset-deduped population the headline sums.

The key is `(source_url, job_count)` and **it holds no company name**, which is
the whole point: a spelling cannot remove a pair from consideration when there is
nothing for a spelling to be wrong in.

`job_count` is in the key rather than being a second test, because one article
genuinely can be the cited source for several different facts — the OPM
workforce-changes portal is one URL behind four federal agencies with four
different counts. Requiring the count to match too is what separates "one page,
several facts" from "one fact, stored twice".

Register-style source types (`warn`, `federal_rif`) are excluded outright: one CA
WARN register URL is the `source_url` of 129 unrelated July rows, so grouping on
it means nothing.

**Measured on the live corpus:** over the 656 US rows of July and August 2026 it
reports **exactly one group — the LAUSD pair — and no false positives.** Against
the live 180-day window it reads FAIL today, naming both rows, with a floor of
550 jobs printed in its own sentence so its reach is never mistaken for the whole
corpus. The sweep is **one request**; it never page-walks the live host.

Missing data is never a pass: an unreachable endpoint, a 503 deploy window, an
empty page and an undecodable body are four separate UNKNOWNs.

It is delegated in `test_dedup_live.InvariantCoverage.DELEGATED` rather than
claimed by a live assertion, for the same reason `country_identity` is: **it is
failing live on purpose**, and a live claim would redden every push over a data
defect a correction clears and a unit suite cannot act on. The daily
`data-integrity.yml` reading is where that belongs.

---

## 7. What still needs a human

1. **Apply the two proven corrections.** The spec is
   `railway/correction_specs/2026-09-16-july-us-overcount.json`. Both are
   `trash` actions through `apply_correction.py`, which suppresses the dedup
   hash so the nightly re-scrape cannot resurrect them. Needs `WP_API_KEY`.
   Expected result: July announced 86,035 → 60,035 (entries 354 → 352), notice
   56,023 → 50,023 (entries 287 → 286).
2. **Adjudicate the two open rows** (134521 RI misparse, 70479/134376 Meta WA)
   through `adjudicate_row.py`'s two referees. Apply only on agreement; list
   disagreement for the owner. Both are UNKNOWN until then.
3. **Feed `curated_probe.py` an August worklist** to close Hypothesis B.
4. **Watch `announced_jobs`.** Six announced rows in a month is either a very
   quiet month or a hole in news discovery, and nothing currently distinguishes
   those two.
