# US WARN reference set, wave 2 — what it measured

Companion to [`US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md`](US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md),
which was committed before any of this existed, and through it to
[`US-WARN-REFERENCE-SET-DEFINITION.md`](US-WARN-REFERENCE-SET-DEFINITION.md),
which governs. Where this document and either of those disagree, they are right
and this one is a bug.

Frames assembled and measured **2026-09-16** against the live public read API.
Reference set `us-warn-il-oh-pa-2025-07_2026-06`. Cost: **$0.00** — no model was
called; the enumeration, the matching and the classification are deterministic
code and read-only GETs.

**Every figure below is GENERATED**, by `railway/warn_recall_pooled.py`, out of
the committed measurement files. Nothing in the block is typed, and
`railway/tests/test_warn_recall_pooled.py` fails if what is committed here
disagrees with what those files compute. Re-render with:

```bash
python3 railway/warn_recall_pooled.py --render
```

---

## 1. The one sentence that may honestly be said first

**Wave 2's published figure is a FLOOR, and it says so: 58 of 75 primary events
(77.3%, Wilson 95% CI [66.7%, 85.3%]) and 4 of 6 in the large-event census.**
Every one of those is an `accept` in
`railway/warn_recall_adjudications_wave2.json` naming a row the frozen matching
rule itself proposed. It is the conservative number and it is the only one that
may be quoted.

It is a floor because **six further events are confirmed held and cannot be
recorded**. Two reviewers adjudicated all 81 events independently and both
identified exactly these six as matched in our data but not proposable by the
frozen rule, naming identical tracker rows:

| Reference event | State | Stratum | Notice | Row(s) we hold |
|---|---|---|---|---|
| `warn-il-2025-08-05-claires-stores` | IL | primary | 46 | 137973 |
| `warn-il-2026-04-13-gerresheimer-moulded-glass-chicago` | IL | primary | 172 | 135563 |
| `warn-oh-2026-04-28-gxo-logistics-supply-chain` | OH | primary | 102 | 135258 |
| `warn-oh-2026-05-01-first-brands-cuyahoga-4` | OH | primary | 110 | 136059 |
| `warn-pa-2026-01-01-miller-s-ale-house` | PA | primary | 49 | 135782 |
| `warn-il-2026-02-05-franciscan-alliance` | IL | census | 1,864 | 136173 + 136174 |

Counting those six, the reviewers' own verdict is **63 of 75 primary and 5 of 6
census**. That is an editor figure, not the published one, and the two must
never be blended or averaged. **The floor is what is published; this paragraph
is what makes it honest.**

### The two conventions, named

| | what it counts | where it lives | may be published |
|---|---|---|---|
| **Machine-recordable floor** | accepts naming a row the frozen pack proposed | `railway/warn_recall_adjudications_wave2.json`, mirrored into the manifest and the generated block below | **yes — this is the figure** |
| **Reviewer verdict** | the floor plus the six confirmed-but-unproposable matches | `us-warn-il-oh-pa-2025-07_2026-06.review.agent-b-2026-09-16.json` | no — quoted only as "the floor understates by six" |

Both reviewers' cells, side by side, each labelled with its convention:

| Cell | Floor (published) | Reviewer verdict (A and B agree) |
|---|---|---|
| IL primary | 20/25 = 80.0% [60.9%, 91.1%] | 22/25 = 88.0% [70.0%, 95.8%] |
| OH primary | 23/25 = 92.0% [75.0%, 97.8%] | 25/25 = 100.0% [86.7%, 100.0%] |
| PA primary | 15/25 = 60.0% [40.7%, 76.6%] | 16/25 = 64.0% [44.5%, 79.8%] |
| **wave 2 primary pooled** | **58/75 = 77.3% [66.7%, 85.3%]** | 63/75 = 84.0% [74.1%, 90.6%] |
| wave 2 large census | 4/6 = 66.7% [30.0%, 90.3%] | 5/6 = 83.3% [43.6%, 97.0%] |
| **pooled SEVEN states (waves 1+2)** | **157/175 = 89.7% [84.3%, 93.4%]** | 162/175 = 92.6% [87.7%, 95.6%] |

Wilson 95% score intervals throughout. The seven-state pooled row uses **equal
allocation** — 25 events per state regardless of how many notices that state
publishes — so it is the mean of seven state samples and **not** a
population-weighted national estimate. **These cells are not ranked and must not
be**; each is 25 events and its interval is roughly 15 to 35 points wide.

### One event the reviewers genuinely disagreed about, and how it was settled

`warn-il-2026-02-23-first-brands` (First Brands Group, Albion Air Facility, IL,
642 workers) was the only substantive disagreement in 81 events, and a diff of
the two ledgers **could not see it**: both ledgers record `reject`, for opposite
reasons. Reviewer A ruled it MISSED; reviewer B ruled it MATCHED on row 136396.

**Ruled a MISS for every published figure** (owner, 2026-09-16). Row 136396 is
real — `First Brands Group (Champion Laboratories, Inc.-multiple sites)`, 642 =
exactly 114 + 48 + 435 + 45, Albion, IL WARN — and Champion Laboratories is the
Albion employer. It is excluded because it is dated **2026-01-15**, 39 days
before the notice date and outside the frozen rule's window, which is the
protocol's cross-period exclusion. The rule is frozen so that a match this
tempting cannot be admitted by an editor with the answer already in view: a
published number must not depend on a judgement made after the fact.

**It is excluded by the window rule, not for absence of evidence, and it is OFF
the chase worklist** — we almost certainly hold this event, so sending anyone to
find it would waste the effort. That is the one place the published figure and
the worklist are allowed to differ, and this paragraph is why.

After that ruling the two reviewers agree, per event, on all 81. The set has
**13 misses**.

---

## 2. The figures

<!-- BEGIN DERIVED: warn_recall_pooled.py -->

<!-- Generated by railway/warn_recall_pooled.py from the committed
     measurement files. Do not edit by hand: every number in this
     block is recomputed, and tests/test_warn_recall_pooled.py
     fails if what is committed here disagrees with them. -->

### Per state

| State | Wave | Frame (events) | Editor-confirmed | Machine upper bound |
|---|---|---|---|---|
| CA | wave 1 | 812 | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) |
| FL | wave 1 | 140 | 24/25 = 96.0%  (Wilson 95% CI [80.5%, 99.3%], width 18.8%) | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) |
| IL | wave 2 | 103 | 20/25 = 80.0%  (Wilson 95% CI [60.9%, 91.1%], width 30.3%) | 20/25 = 80.0%  (Wilson 95% CI [60.9%, 91.1%], width 30.3%) |
| OH | wave 2 | 81 | 23/25 = 92.0%  (Wilson 95% CI [75.0%, 97.8%], width 22.7%) | 23/25 = 92.0%  (Wilson 95% CI [75.0%, 97.8%], width 22.7%) |
| PA | wave 2 | 79 | 15/25 = 60.0%  (Wilson 95% CI [40.7%, 76.6%], width 35.9%) | 15/25 = 60.0%  (Wilson 95% CI [40.7%, 76.6%], width 35.9%) |
| TN | wave 1 | 62 | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) |
| TX | wave 1 | 166 | 25/25 = 100.0%  (Wilson 95% CI [86.7%, 100.0%], width 13.3%) | 24/25 = 96.0%  (Wilson 95% CI [80.5%, 99.3%], width 18.8%) |

**These cells are not ranked and must not be.** Each is 25 events and carries a Wilson interval roughly 14 points wide even at the ceiling; both definitions committed in advance to not ranking on cells this size.

### Pooled

| Basis | Figure |
|---|---|
| Editor-confirmed, equal allocation, ALL measured states | 157/175 = 89.7%  (Wilson 95% CI [84.3%, 93.4%], width 9.1%) |
| Editor-confirmed, ADJUDICATED sets only (wave 1, wave 2) | 157/175 = 89.7%  (Wilson 95% CI [84.3%, 93.4%], width 9.1%) |
| Machine upper bound, equal allocation | 157/175 = 89.7%  (Wilson 95% CI [84.3%, 93.4%], width 9.1%) |
| Machine upper bound, notice-volume weighted | 0.9547 |

Allocation is **equal, not proportional**: every state contributes 25 events regardless of how many notices it publishes, so the pooled figure is the mean of the state samples and **not** a population-weighted national estimate. The volume-weighted row is beside it for exactly that reason.

### By event size, pooled

| Band | Affected workers | Editor-confirmed | Machine upper bound |
|---|---|---|---|
| S | 1-99 | 96/104 = 92.3%  (Wilson 95% CI [85.6%, 96.1%], width 10.5%) | 97/104 = 93.3%  (Wilson 95% CI [86.8%, 96.7%], width 9.9%) |
| M | 100-499 | 53/62 = 85.5%  (Wilson 95% CI [74.7%, 92.2%], width 17.5%) | 52/62 = 83.9%  (Wilson 95% CI [72.8%, 91.0%], width 18.2%) |
| L | 500+ | 8/9 = 88.9%  (Wilson 95% CI [56.5%, 98.0%], width 41.5%) | 8/9 = 88.9%  (Wilson 95% CI [56.5%, 98.0%], width 41.5%) |

### The frames, before any matching

| State | Wave | In-window events | Frame jobs | Months covered | Notice dates | Multi-row events |
|---|---|---|---|---|---|---|
| CA | wave 1 | 812 | 80,673 | 12 | 2025-07-01 to 2026-06-30 | 180 |
| FL | wave 1 | 140 | 21,599 | 12 | 2025-07-01 to 2026-06-30 | 28 |
| IL | wave 2 | 103 | 17,261 | 12 | 2025-07-07 to 2026-06-30 | 9 |
| OH | wave 2 | 81 | 8,839 | 12 | 2025-07-07 to 2026-06-29 | 0 |
| PA | wave 2 | 79 | 12,421 | 12 | 2025-07-01 to 2026-06-01 | 2 |
| TN | wave 1 | 62 | 8,900 | 12 | 2025-07-02 to 2026-06-24 | 0 |
| TX | wave 1 | 166 | 25,299 | 12 | 2025-07-02 to 2026-06-23 | 16 |

A frame that stops early is a smaller denominator and not a recall result, which is why the month coverage and the notice-date range are printed beside every cell.

**wave 1: 173 published rows excluded**, each recorded in the manifest with its reason: 173 notice date outside the window.

**wave 2: 303 published rows excluded**, each recorded in the manifest with its reason: 3 no_absolute_headcount_published; 300 notice date outside the window.


This is **event size, not employer size**. WARN publishes how many workers a notice affects and not how large the employer is.

### Large-event census, reported apart and never pooled

| Set | Editor-confirmed | Machine upper bound |
|---|---|---|
| wave 1 | 32/33 = 97.0%  (Wilson 95% CI [84.7%, 99.5%], width 14.8%) | 33/33 = 100.0%  (Wilson 95% CI [89.6%, 100.0%], width 10.4%) |
| wave 2 | 4/6 = 66.7%  (Wilson 95% CI [30.0%, 90.3%], width 60.3%) | 4/6 = 66.7%  (Wilson 95% CI [30.0%, 90.3%], width 60.3%) |

Pooling a census with a systematic sample double-counts the events in both and silently reweights the result, so it is not done.

### Why the wave-2 misses are misses

| Cause | Events |
|---|---|
| `stored_unmatched` | 5 |
| `UNKNOWN` | 11 |

`UNKNOWN` is a verdict. `walked_not_read`, `fetched_rejected` and `extracted_dropped` are statements about a collector's own output, which a public read cannot see, so a miss that cannot be placed stays UNKNOWN rather than being guessed into one of them.

**Unreachable / UNKNOWN events excluded from every numerator and denominator above: 0.**

Measured at: wave 1 2026-08-14T19:57:05Z; wave 2 2026-09-16T12:31:23Z.

<!-- END DERIVED: warn_recall_pooled.py -->

---

## 3. What the frames look like, before any matching

**The frame table is in the generated block above**, beside the figures, and it
is generated for the same reason they are. The first draft of this section typed
it by hand and got two of the six Pennsylvania cells wrong — frame jobs and the
excluded-row split — within an hour of the frame being rebuilt. That is the
whole argument for deriving it, made accidentally.

All seven frames cover **all twelve months** of the window, so no state's cell
is a short frame wearing a recall figure. Every excluded row is in the manifest
with its own reason and its own source locator; nothing was silently dropped.

---

## 4. Two defects this measurement found in ITSELF before it found anything about the tracker

Both are recorded because a reference set that only reports its result is
asking to be believed.

### 4.1 Pennsylvania's year headings are not all the same element, and the wrong parse read as a coverage finding

PA renders the year heading as
`<h2 class="cmp-accordion__main-heading--large">2025</h2>` for 2026 and 2025 and
as a **bare `<h2>2024</h2>`** for 2024 and 2023. The first parse matched only the
classed form, so **every 2024 and 2023 notice inherited `year = 2025`**: PA's
in-window frame filled to 147 events with notices from one and two years
earlier, and the measurement came back at **PA 36%**.

It looked like a coverage finding. It was not. The "missed" rows were in the
table with the published headcount exactly right — CVS Health 157, The AMES
Companies 57, Sodexo 83, Joriki 226, Fulton Bank 3 — each stored against an
effective date in 2023 or 2024, because that is when those notices actually
were. **A frame that is wrong in a way that reads as a result is worse than a
frame that fails**, and nothing in the pipeline would have caught it.

What caught it was the field the definition had already decided to capture as
evidence and not as a basis: PA's per-item CMS `repo:modifyDate`. An entry filed
under "August 2025" whose CMS record was authored on 2024-09-19 cannot be an
August 2025 notice. That is now a guard —
`warn_reference_set_wave2._pa_year_month_is_sane` — which raises when a month
bucket's **median** authored date sits more than 120 days before the month it is
filed under. One-sided on purpose: an entry may be edited long after its month,
and cannot be authored long before it. After the fix PA's in-window frame is
**79 events** and the bound is 64%.

### 4.2 The Ohio transcription check called 17 of 25 notices "disagrees" and every one was the checker's own blind spot

The definition promised that each sampled Ohio event would be
transcription-verified against the employer's own notice PDF, since Ohio's frame
is the same file our collector reads. The first version of that check had two
states — agrees, or disagrees — and reported 17 disagreements.

A WARN notice is a **letter**. The employer is very often only in a letterhead
image, and the total headcount is very often only the sum of a per-job-title
table. Neither appearing in the extractable text is **not** a disagreement, and
some of those PDFs have no text layer at all, where an empty read is not a zero.
The check now has four states and reports:

| Status | Notices |
|---|---|
| `confirmed` — employer token and headcount both in the notice's own text | 8 |
| `partially_confirmed` — one of the two | 9 |
| `not_stated_in_text` — neither, and the notice has a text layer | 5 |
| `not_verified` — no text layer, no link, or the fetch failed | 3 |

**No transcription disagreement was found.** 17 of 25 carry at least partial
confirmation from the employer's own notice, and the other 8 are honest
UNKNOWNs about the notice rather than findings about the frame.

---

## 5. The misses, as a worklist

**13 events are misses.** Twelve are chaseable; the thirteenth
(`warn-il-2026-02-23-first-brands`, 642) is excluded by the window rule and is
deliberately **not** on this list, for the reason given in §1.

### The two worth doing first

- **Amazon Fresh, Illinois — the largest miss in the set.** Ten Illinois store
  closings totalling **1,545 workers**, notice 2026-01-28, held in no form: an
  `Amazon` query in IL returns only a 2024 fulfillment-centre row. The
  **Pennsylvania sibling of the same programme IS held** (row 135412, 983
  workers), so this is not an employer the pipeline cannot see — it is one state
  of one programme going missing while another state of it lands. That
  asymmetry is the lead.
- **Adare Pharmaceuticals, missed in BOTH states.** Aurora IL, 21 workers,
  effective 2026-02-02, and Philadelphia PA, 137 workers, effective 2026-03-01.
  A nationwide `Adare` query returns **nothing at all**, so the employer is
  absent from the tracker entirely rather than mis-stored.

The remaining ten are single-notice gaps: Zeco Systems (IL, 6), Weaber (PA,
145), Fourth Street Barbecue (PA, 252), DuBois Logistics (PA, 110), S&S
Activewear (PA, 128), BPM (PA, 248), Dometic (PA, 89), Juvenile Justice Center
(PA, 17), American Expediting Logistics (PA, 86).

**Every miss cause stays `UNKNOWN`, per the protocol.** Whether a given one is
`walked_not_read`, `fetched_rejected` or `extracted_dropped` is a statement about
a collector's own output, which a public read cannot see. They are not guessed
into one of the three.

**One thing the evidence does rule out: a collection outage.** The held WARN
series for all three states is continuous across every month from 2025-06 to
today, with no empty month inside the judged span. So these are scattered
per-notice gaps, not a dark window — a materially different worklist.

---

## 5b. Defects both reviewers logged, carried as FINDINGS and not fixed here

Recorded so they are not rediscovered. None is fixed by this measurement; the
two that are one line are noted as such.

1. **Ohio's amendment marker is stored in `company_name`.** Rows 135258 and
   136059 literally begin with the word `UPDATE`
   (`UPDATE GXO Logistics Supply Chain, Inc`). The wave-2 definition cuts that
   marker on the *reference* side precisely so it cannot manufacture a miss;
   `sources/warn_custom.fetch_oh` does not cut it on the *storage* side, so it
   is in the public row. A real tracker data-quality defect, not a matching-rule
   limit.
2. **U+2019 is a different character from U+0027.** Pennsylvania publishes
   `Miller’s Ale House`; we store `Miller's Ale House`. `/query?company=` does
   not bridge them, so the published spelling retrieves nothing at all.
3. **An amended effective date creates a SECOND row.** TOPS is held as 136862
   and 176824; Premier as 136620 and 176837. One notice, two rows, because the
   amendment changed the effective date.
4. **`/query?company=` is whole-word, not substring.** This makes
   `warn_miss_causes.py`'s 6-character prefixes **inert** — a prefix like
   `Gerres` matches nothing, so a probe built on them cannot find what it is
   looking for and reports absence.
5. **Walgreens' 469-job Illinois notice is held only as a NEWS row**, with no
   WARN row behind it.
6. **Compass Group is held as 1 of 4 components** — row 138181 carries 27 of the
   notice's 73; the Aurora 15, Kankakee 10 and Park Ridge 21 components are not
   held. Partial capture of a multi-site notice.
7. **Two reference-frame doubts, RECORDED AND NOT EDITED**, because a reference
   set is not repaired by the reviewer who is measuring against it:
   - *Heartland Human Care Services (IL, stated 240).* Two 120-worker component
     rows share employer, Chicago 60653, count, effective date 2026-03-31 and
     received date 2026-04-01, appearing in two consecutive monthly reports.
     They read as **one notice counted twice**. Our row matches its component
     exactly.
   - *BPM Limited (PA, January 148 and February 248).* The February entry's
     location text is `**UPDATED TO REVISE AFFECTED TOTAL**`, so it is an
     amendment of the January notice and the frame holds one closure as two
     events. We hold neither, so it is a miss either way.

Both doubts are for the reference-set owner. Neither changes a figure above.

---

## 6. What this set may and may not be used for

- **Internal reference set, single author.** `publication_status` says so. It is
  **not** posted to `/benchmarks/recall`, which requires the three-actor review
  chain in [`../RECALL_BENCHMARK_PROTOCOL.md`](../RECALL_BENCHMARK_PROTOCOL.md).
- It touches **nothing** of the SEC Item 2.05 set and **nothing** of wave 1:
  not their manifests, not their measurements, not `MATCHED_FLOOR`. Tested, not
  asserted.
- Its numbers are **not "our WARN recall"**. Seven states now have a measured
  cell; **New York is not one of them**, and neither is any New England state,
  and MA, NJ, MI, GA, NC, WA, VA and MD remain out.
- **No model was called. $0.00.**

---

## 7. Reproducing it

```bash
python3 railway/warn_reference_set_wave2.py --build     # re-enumerate, redraw the sample
python3 railway/warn_reference_set_wave2.py --measure   # frozen set vs the live read API
python3 railway/warn_reference_set_wave2.py --pack      # per-row adjudication sheet
python3 railway/warn_miss_causes.py --classify          # a cause per unmatched event
python3 railway/warn_recall_pooled.py --render          # regenerate every figure above
```

The frames are fetched live from the three agencies each time; a state that has
edited its own published list since assembly shows as a frame drift and is
reported, not silently absorbed.
