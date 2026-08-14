# US WARN reference set — what it measured

Companion to [`US-WARN-REFERENCE-SET-DEFINITION.md`](US-WARN-REFERENCE-SET-DEFINITION.md),
which was committed before any of this existed. Every choice reported here was
fixed there first; where this document and that one disagree, that one is right
and this one is a bug.

Measured **2026-08-13** against the live public read API; **adjudicated
2026-08-14** by the owner (reviewer `Dakotta`) and re-measured the same day.
Reference set `us-warn-ca-tx-fl-tn-2025-07_2026-06`. Cost: **$0.00** — no model
was called, the enumeration and the matching are deterministic code and
read-only GETs.

---

## 1. The headline, stated the only way it may honestly be stated

| | |
|---|---|
| **Editor-confirmed recall** | **99 of 100 = 99.0%**, Wilson 95% CI **[94.6%, 99.8%]** |
| **Machine upper bound** | 99 of 100 = 99.0% — the editor's figure met the ceiling; nothing was promoted past it |
| **Large-event census** (500+, separate stratum, never pooled) | **32 of 33 = 97.0%**, Wilson 95% CI [84.7%, 99.5%] |
| **Notice-volume weighted** | 99.4% |
| **Unreachable** | 0 |

**Adjudicated 2026-08-14.** The owner signed off every event where the machine
proposed a matching row, with reviewer name `Dakotta`, through
`railway/warn_adjudicate.py` — 131 accepts and 2 rejects across both strata,
each with the row id it names and a reason built from that event's own evidence
(what the count matched exactly or by how much it differed, and which published
date basis the row agreed on). The full record is
`railway/warn_recall_adjudications.json`; `--verify` passes and
`tests/test_warn_adjudication.py` runs it in CI.

**The two rejects are the same defect and it is ours, documented:** when a
state publishes two identical notices on one day — same employer, same count,
same effective date, same state — our `dedup_hash`
(`warn + company + date + jobs + state`) collapses them into ONE stored row,
and one row may not count for two reference events. SMBC MANUBANK filed several
identical one-worker Florida notices on 2026-01-08 (Bradenton and Marco Island
are both in the sample; the stored row's excerpt names Bonita Springs, a third
site) — the row was claimed for Marco Island, the notice appearing first in
Florida's own list, and Bradenton is the primary sample's one miss. Spirit
Airlines filed two identical 796-worker Orlando notices on 2026-05-04 (Orlando
International and the MCO Inflight & Operations Center) — the row was claimed
for Orlando International and the OOC notice is the census's one miss.

**Wood Group was accepted, and the anomaly is recorded on the accept.** We hold
row `140104` — 180 jobs, exactly the notice total, `layoff_date` 2025-01-05
exactly as TWC's own record publishes — and the 317-day gap between that layoff
date and the same record's 2025-11-18 notice date is the Texas record's own
inconsistency, noted in the accept reason as a recorded source anomaly. The
matching window was not widened to reach it; the mechanism recorded the
decision through the no-candidate path.

**Why the editor's figure met the machine's ceiling here when it fell well
short of it on the SEC set** — structural, not lucky: on the SEC set the
machine's loose rule scored 31 against the editor's 24 because it was matching
an 8-K against *a news story about something else*. Here the reference row and
the tracker row are the same species — a state WARN notice — and every accepted
row matches on **state, date window, and a job count identical to a published
row of that notice** (103 of the 131 accepts on the notice total, 28 on one
published component row), which is very nearly the `dedup_hash`
(`warn + company + date + jobs + state`) itself. The events that needed the
most reading were the multi-site notices with several candidates, and those
resolved by count and published effective date.

---

## 2. By state, and why these cells may not be ranked

| State | machine any | Wilson 95% CI | frame | frame jobs |
|---|---|---|---|---|
| CA | 25/25 = 100.0% | [86.7%, 100%] | 812 events | 80,673 |
| TX | 24/25 = 96.0% | [80.5%, 99.3%] | 166 events | 25,299 |
| FL | 25/25 = 100.0% | [86.7%, 100%] | 140 events | 21,599 |
| TN | 25/25 = 100.0% | [86.7%, 100%] | 62 events | 8,900 |

**These four cells are not ranked and must not be.** A cell of 25 carries an
interval about 14 points wide even at the ceiling; the definition committed in
advance to not ranking on cells this size, for the same reason the UK set's
author refused to rank metros on 8-to-16-event cells. What the table supports is
"no state in the set is visibly worse than the others", and nothing finer.

Allocation is **equal, not proportional** — 25 from California's 812-event frame
and 25 from Tennessee's 62 — so the pooled 99/100 is the mean of four state
samples with equal weight. The notice-volume-weighted estimate, using each
state's own frame size as the weight, is **99.4%**. The two agree, which is the
uninteresting outcome and worth saying anyway: when equal and proportional
allocation disagree, the disagreement is the finding, and here there is none.

## 3. By event size

| Band | affected workers | machine any | Wilson 95% CI |
|---|---|---|---|
| S | 1–99 | 57/57 = 100.0% | [93.7%, 100%] |
| M | 100–499 | 35/36 = 97.2% | [85.8%, 99.5%] |
| L | 500+ | 7/7 = 100.0% | [64.6%, 100%] |
| **L census** (all 33 in-frame 500+ events, separate stratum) | | **32/33 = 97.0%** | [84.7%, 99.5%] |

This is **event size, not employer size**. WARN publishes how many workers a
notice affects and does not publish how large the employer is; a 60-person
notice from a national retailer is in band S. No claim is made here about small
*employers*.

The L band inside the primary sample is 7 events and its interval is 35 points
wide — useless on its own, which is exactly why the definition committed in
advance to censusing the large events separately. The census is the number to
read for large events: **32 of 33** after adjudication — the one miss is the
second of Spirit's two identical 796-worker Orlando notices, whose row our
dedup hash collapsed into the first — and it is reported apart from the primary
figure rather than pooled into it, because pooling a census with a systematic
sample double-counts the events in both and silently reweights the result.

---

## 4. The miss classification — worth more than the percentage

After adjudication there are **two** unmatched events across both strata — one
per stratum — and both are the same documented design decision, not a
collection failure.

| Bucket | Count | |
|---|---:|---|
| `no_source` | 0 | |
| `walked_not_read` | 0 | |
| `fetched_rejected` | 0 | |
| `extracted_dropped` | 0 | |
| `stored_unmatched` | **2** | SMBC MANUBANK Bradenton, FL, 2026-01-08, 1 worker (primary); Spirit Airlines MCO Inflight & Operations Center, FL, 2026-05-04, 796 workers (census) |
| `UNKNOWN` | 0 | |

**Both misses are the dedup hash counting identical sibling notices once.**
`dedup_hash` is `warn + company + date + jobs + state`; when a state publishes
two notices that agree on all four, the second upsert lands on the first's row.
The reference set's unit is the notified action, so each identical sibling is a
distinct event, and the one stored row may be claimed for only one of them. The
adjudication claimed it, both times, for the notice appearing first in the
state's own list, and recorded the sibling as the resulting miss — reasons and
row ids are in `railway/warn_recall_adjudications.json`.

**Wood Group, the measurement's original one miss, is now matched — and the
anomaly is on the record rather than smoothed over.** We hold tracker row
`140104`: Texas, 180 jobs, source `warn`, company `Wood Group USA Inc.` — the
notice, exactly. Its `layoff_date` is **2025-01-05**, which is what the TWC
dataset publishes as this notice's layoff date, **ten months before the
2025-11-18 notice date on the same record**. The matching rule's window is
notice−30 days to notice+400 days, so the row falls outside it and the rule
proposed nothing. The rule was not widened to catch it: the window was fixed in
the definition before the first query, and widening it after seeing which event
it excluded is precisely the tuning this exercise forbids. The owner accepted
the event on 2026-08-14 on the evidence that the row IS the notice (count exact,
date exactly as TWC publishes it), with the 317-day notice-date inconsistency
recorded in the accept reason as the Texas record's own anomaly.

### What the misses were on the earlier runs, and why that matters more

The measured figure moved **79 → 86 → 99** across three runs, and **both moves
were defects in the measurement harness. No line of the pipeline was changed at
any point.** This is recorded here rather than quietly overwritten because a
reference set that reports only its final number is asking to be trusted.

- **Run 1 (79/100).** `aliases_for` stripped the address from Florida's glued
  employer names with `_CITY_ST_ZIP.sub("")`, whose greedy `[A-Za-z .'-]+` head
  matched the employer too. **Fourteen events came out with an empty alias list,
  so no query was sent for them at all — and all fourteen scored as misses.** A
  query that was never sent is UNKNOWN; the run should have said so and did not.
- **Run 2 (86/100).** Sixteen misses remained and **eleven of them were the same
  class of defect one layer down.** `/query?company=` is a substring LIKE
  against the stored name, and the aliases were punctuation-stripped
  reconstructions. `Mattel Inc` is not a substring of `Mattel, Inc.`; nor
  `Raley s` of `Raley's`, `Frito Lay` of `Frito-Lay, Inc`, `Albertsons 4286` of
  `Albertsons #4286`, `Saks Company LLC` of `Saks & Company LLC`, `Parsec LLC`
  of `Parsec, LLC`. **Every employer whose published name carries a comma, an
  apostrophe, a hyphen, an ampersand or a `#` was unfindable by construction**,
  and the row was sitting in the table the whole time. Retrieval and matching
  are now separate objects: query terms are literal leading substrings of the
  published name, and the match test is unchanged.
- **Run 3, partial.** A burst of host 503s made ten consecutive Texas events
  UNKNOWN. Correctly not scored as misses; `_api` now retries so a six-minute
  Bluehost wobble cannot delete a tenth of the sample.

**Two of the three run-to-run movements were an instrument that could not see,
and every one of them pointed the same way: a broken measurement understates
coverage and looks like a finding.** That is the same shape as the SEC set,
where most of the apparent 57.9% gap turned out to be `stored_unmatched` — events
we already held and had never adjudicated. It is now two for two, and the general
lesson is that on this project a surprising recall gap should be assumed to be
the measurement until the measurement has been attacked.

---

## 5. Is US WARN coverage better or worse than the SEC slice?

**Not distinguishable on these numbers, and the interesting answer is not the
comparison.** The SEC set moved to **56 of 57 = 98.2%** on 2026-08-13, hours
before this was measured. Both figures are now editor-confirmed over the same
twelve months, and their intervals sit almost on top of each other.

| | SEC Item 2.05 | US WARN (CA/TX/FL/TN) |
|---|---|---|
| Window | 2025-07-01 .. 2026-06-30 | **the same** |
| Denominator | 57 | 100 + a 33-event census |
| Editor-confirmed | **56/57 = 98.2%** [90.7%, 99.7%] | **99/100 = 99.0%** [94.6%, 99.8%] (adjudicated 2026-08-14) |
| Machine upper bound | 31/57 at first measure | 99/100 — the confirmed figure met it |
| Remaining miss | 1 (Wabash — a derived count `_count_in_text` refuses) | 1 primary + 1 census (identical sibling notices, dedup-hash collapse) |
| Employers covered | US public companies filing 8-Ks | **any employer over the WARN threshold, private included** |

**Anyone quoting "WARN 99 vs SEC 98" is quoting noise.** Two samples of 100 and
57 whose intervals overlap across nine points cannot separate a two-point
difference. What the two sets support jointly is a different and stronger claim:
**on both of its two primary-source paths, over the same twelve months, this
tracker is missing about one event in each set, and in both cases the remaining
miss is a documented design decision rather than a hole.**

**The structural difference is still real and still worth stating**, because it
predicts where each path will break next rather than where it stands today:

- A WARN notice arrives as a **table row with the employer, the count, the state
  and the dates already separated**. `warn_import.py` skips the LLM entirely,
  bulk-upserts through `/bulk`, and is idempotent by a `dedup_hash` computed from
  those very fields. There is no extraction step to lose anything at, and the
  daily cron re-reads the whole published list, so a transient failure self-heals
  on the next run.
- An 8-K Item 2.05 is **a document that has to be read**. The count lives in a
  sentence, the sentence has to be found, the model has to return it, and a
  filing whose only figure is a percentage or a retained headcount is correctly
  dropped. Every one of those steps is a place to lose an event, and the SEC
  set's own history is a catalogue of them.

So the honest comparison is not a percentage at all. It is: **the WARN path has
no extraction step to lose an event at, and the SEC path is a document that has
to be read — so the SEC number is the one that will move when a model, a fetch
depth or a count guard changes, and the WARN number is the one that will move
when a state changes its website.** The SEC set spent a year climbing from 42.1%
to 98.2% by fixing extraction. Nothing equivalent was ever needed here, and
nobody knew that until today.

### The coincidence that is not a coincidence

The SEC set's own last defect, closed hours before this measurement, was
**exactly the class of defect this one had twice**: its alias `HP ` was used
verbatim as the API's substring filter and could not match a company stored as
`HP`, so a 4,000-job event the tracker had held since November scored as a miss.
Here it was `Mattel Inc` against `Mattel, Inc.` and ten more like it.

Two independent reference sets, on the same day, both found that **their largest
apparent coverage gap was the substring semantics of `/query?company=`**. That is
now a pattern rather than an anecdote, and it belongs in the protocol: a
reference set that constructs its query terms instead of taking them verbatim
from the source will under-report, and it will under-report in the direction that
looks like a finding.

### The part of the sentence that must not be dropped

**99% is coverage of the states this set could measure, and the states it could
measure are the ones whose lists are machine-readable.** The eligibility walk in
the definition excluded **NY, PA, IL, OH, GA, NC, NJ, MI, MA** — every one of
them either a JavaScript-only page, a proprietary BI extract, or a 404 — plus
**VA and MD**, which publish beautifully and ask agents like this one not to read
them. That is the entire Midwest and the entire Northeast. **This set cannot say
anything about our WARN recall there, and the definition said so before the
number existed.**

What can be said, from our own data rather than from an independent frame, is a
**presence bound**: WARN rows held with an effective date in 2025-07 .. 2027-09,
by state.

    CA 1778   TX 235   FL 218   TN 71        <- the four measured
    NJ 163    NY 138   IL 137   OH 133       <- measured by nobody
    NC 130    GA 112   MI 63    PA 73   MA 97
    WA 181    MD 179   OR 111   VA 87   IA 73

    zero rows in the window: OK, AR, WV, NH, WY

Those are **counts we hold, not recall** — no independent denominator exists for
them and none of them is verified by this set. Two things follow that are worth
a session each:

1. **The unmeasurable states are collecting.** NY, PA, IL, OH, GA, NC, NJ, MI and
   MA all hold three-figure row counts in the window, so the collectors reach
   them by routes this enumeration could not. Whether those routes are *complete*
   is unknown and this set cannot make it known.
2. **Five states hold zero.** OK, AR, WV, NH and WY. Four of the five (NH, AR,
   OK, WY) are already named as open work by the session holding the handoff
   baton, which is corroboration rather than a new finding — but a state at zero
   is not a recall problem, it is a missing collector, and no recall figure will
   ever show it.

### And one thing the walk found that has nothing to do with recall

**Ohio's and North Carolina's official WARN pages returned 404 on every
documented path on 2026-08-13**, including the archive-page pattern
`sources/warn_custom.fetch_oh` builds and the `dam.assets.ohio.gov` fallback it
keeps for exactly this failure. We hold 133 OH and 130 NC rows in the window, so
something is reaching them — but the paths in the code are dead, and a collector
whose discovery pages 404 while its fallback still resolves is one deploy away
from silently freezing. `report_source_health` reports the WARN import as one
source, so a single state going dark inside it does not surface.

---

## 6. Honest biases, restated after the number

Stated in the definition before measuring; nothing below is hindsight.

- **No Midwest, no Northeast.** Not a sampling choice — those states' own
  publications are not machine-readable. The direction of the resulting bias is
  named and not guessed: a JS-only page is hard for our scraper for the same
  reason it was hard for this enumeration, so **99% is an optimistic bound on
  national WARN recall.**
- **Not independent of our design.** Our collectors read these same agencies. The
  set is independent of our *selection*, our *ordering* and our *parsing* — a
  different California document, a chronological re-sort, a parser that imports
  nothing from `sources/warn*.py` — and it is the same caveat the SEC set carries
  about EDGAR.
- **Tennessee's window is counted on a posting date**, not the employer's notice
  date, because that is all TN publishes. California publishes both and lets the
  substitution be sized rather than assumed: median lag **1 day**, mean 2.85,
  max 161 over 1,582 rows.
- **The unit is a notified corporate action**, not a published table row: 2,365
  published rows collapse to 1,180 events on (state, employer, notice date). A
  ten-site filing is one event we hold or do not, rather than ten chances to be
  70% right. **This figure is therefore not comparable to a row-level ratio.**
- **The four-token collapse key could over-collapse**, and over-collapsing
  inflates recall. Every component row of every collapsed event is in the
  manifest so the collapse can be audited rather than trusted.
- **One author.** This has not been through the three-actor review chain in
  `docs/RECALL_BENCHMARK_PROTOCOL.md`, it is not posted to `/benchmarks/recall`,
  and nothing in it moved the published SEC figure — `railway/recall_measurement
  .json`, `railway/recall_adjudications.json`, the SEC manifest and
  `MATCHED_FLOOR` are untouched, and `tests/test_warn_reference_set.py` asserts
  no module here can reach them.

---

## 7. How the adjudication went, recorded after the fact

The steps this section used to prescribe were followed on 2026-08-14, in order:

1. The pack was rebuilt from live data (`warn_adjudication_pack.py --write`,
   132 pending events, 714 candidate rows, 1 with no candidate row).
2. The owner decided the set with reviewer name `Dakotta`: **131 accepts and 2
   rejects**, every one recorded through `warn_adjudicate.py` with the row id it
   names and a reason drawn from that event's own evidence block — what the
   count matched (the notice total, or one published component row of it, and by
   how much it differed if not), and which published date basis the row agreed
   on (effective in 121 cases; the notice/posting date in 11, all Tennessee,
   where that is what the state publishes).
3. The shared-row events (Amazon, KBR, SMBC Manubank, Spirit — employers that
   filed several notices close together) resolved without double-claiming: each
   accept names a distinct row, pinned by count and published effective date.
   Two events could not be given a distinct row because the state published
   identical sibling notices and our dedup hash stores them once; those two are
   the set's misses, rejected with the collapse named in the reason.
4. **Wood Group was accepted through the no-candidate path** — which the
   recorder refused until the same day: `adjudication_ledger.pack_entry` scanned
   only the pack's `entries` list, so the one decision the sheet's own
   no-candidate section asked for was Refused as "not in the adjudication pack".
   Fixed in the shared core (both recorders get it), with the unknown-row-id
   guard intact and tests in `tests/test_warn_adjudication.py`.
5. `--verify` passes; the set was re-measured the same day. **The SEC figure did
   not move**: `railway/recall_measurement.json`,
   `railway/recall_adjudications.json` and the SEC manifest are byte-identical,
   as the tests assert.

**The figure now stands at 99/100 = 99.0% (Wilson 95% CI [94.6%, 99.8%])
editor-confirmed on the primary sample, and 32/33 = 97.0% ([84.7%, 99.5%]) on
the large-event census, never pooled.**
