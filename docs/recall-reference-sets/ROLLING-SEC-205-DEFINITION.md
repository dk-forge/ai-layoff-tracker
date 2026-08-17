# Rolling SEC Item 2.05 recall — reference-set definition

**Written before the first figure it produced was quoted anywhere.** This is the
selection rule, the matching rule and the honest limits of
`railway/rolling_recall.py`. Anyone may repeat it; that is the point of it.

## What problem this exists for

The owner's three stated goals — match a US benchmark, cover the world, be a
top-three tracker — are all percentages, and until 2026-08-17 none of them was
measurable on a schedule. The only coverage comparison in existence was a
hand-maintained local file, 24 days stale, that cannot be automated and depends
on a source whose `robots.txt` disallows AI agents. So "we cover X%" was an
opinion, and it was the one claim that could damage the project if it were
wrong.

There is a frozen, hand-adjudicated SEC Item 2.05 gold set
(`sec-item-205-us-2025-07_2026-06.goldset.json`), and it is excellent at the job
it was built for: it detects whether the tracker has **lost** events an editor
confirmed it held. It cannot say what coverage is **now**, because its window
closed on 2026-06-30 and extending it costs a human afternoon.

This set re-enumerates the universe every week instead.

## Why this denominator, and why it is unusual

Nearly all recall measurement has to sample, because the true universe of events
is unknowable. SEC Item 2.05 is the rare exception.

Every US public company recording a material charge for exit or disposal
activities files a Form 8-K carrying the structured item code **2.05** in its
SGML header. EDGAR full-text search enumerates those for any period, exactly,
free and without a key. The denominator is therefore not a sample of the
universe — for this slice it **is** the universe.

That makes the resulting figure falsifiable by anyone who repeats the query,
which is the only kind of coverage figure worth publishing.

## Selection rule

1. **Window.** `WINDOW_MONTHS` (12) whole calendar months, ending at the last
   month that closed at least `SETTLE_DAYS` (45) before the run date. The window
   advances a whole month every month.

   The settle lag is a *fairness* rule. A filing made last Tuesday that we do not
   yet hold is ingest latency, not a coverage gap; counting it as a miss would
   measure the clock. Note the lag does **not** clear
   `backfill.rotating_month`, which re-verifies every month of the last twelve
   within 120 days — so the figure is a lower bound in that respect too, because
   the sweep is still working on the newest months of any window.

2. **Enumeration.** EDGAR full-text search
   (`efts.sec.gov/LATEST/search-index`), `forms=8-K`, one calendar month per
   request, query `"Item 2.05"`. A hit is kept **only when the response's
   structured `items` array contains `2.05`** — the code the filer put in the
   header, never a text match. The text query is a retrieval handle and nothing
   more.

   The enumeration must be complete or the denominator is a lie, and a truncated
   denominator **inflates** recall. Any month exceeding `MAX_HITS_PER_MONTH`
   raises, and any transport fault makes the whole slice UNKNOWN. This is the
   same failure mode as the pagination cap that hid 33 gold events for a year
   (TECHLOG 2026-08-01); it warned back then, and it asserts now.

   *Control:* the same twelve months enumerated this way on 2026-08-17 returned
   **215 accessions — byte-for-byte the same count the hand-assembled manifest
   recorded for the same window in a separate exercise on 2026-08-01.**

3. **Scope, in three states, never two.** The Item 2.05 section of the primary
   document is parsed by `sec_205_deterministic_probe.py`, which imports
   `extractor.py`'s own `_count_in_text` and `_percent_only_mention`, so a
   number this set calls "stated" is stated according to the same function the
   production path uses.

   | state | rule | counted |
   |---|---|---|
   | `in_scope` | the section states an absolute headcount and the parser resolved it unambiguously | denominator |
   | `out_of_scope` | the section states a percentage or a retained headcount only, **or** states no headcount and the accession carries no EX-99 exhibit | excluded, and reported |
   | `undecidable` | two distinct headcounts (the parser declines rather than choosing or summing), no headcount but an EX-99 exhibit exists, or the document could not be fetched | **UNKNOWN** — excluded from numerator *and* denominator, listed by name |

   **The parser does not read exhibits, on purpose.** Over EX-99.1
   press-release bodies it read GitLab's "2021 Employee Stock Purchase Plan" as
   a headcount of 2021 for a 350-person cut. The Item 2.05 heading anchor is the
   hypothesis, not a convenience. So a filing whose count lives only in the
   exhibit is UNKNOWN, and an honest UNKNOWN is worth more than a wrong
   denominator. Do not "improve" the undecidable share by parsing exhibits.

   Measured over 2025-07..2026-06: 215 enumerated, 45 in scope, 111 out of
   scope, 59 undecidable (27%). `MAX_UNDECIDABLE_SHARE` is 0.40; above it the
   slice reports UNKNOWN rather than a band.

## Matching rule, and why the result is a band

There is no editor in this loop. On 2026-08-01 the loose alias/window matcher
scored 31 of 57 against an editor's 24 — twelve points of recall the machine
awarded itself, on a Hormel Georgia WARN filed ten weeks before the announcement
it was meant to represent, an Italian composites maker for HP Inc, and Dow Jones
for Dow. CLAUDE.md's rule stands: **a machine must not promote its own recall.**

So two tiers are reported, and the figure is the interval between them:

- **CONFIRMED** — the employer names align (token-prefix, in either direction),
  the tracker row's date falls within [filing − 90d, filing + 270d] on the
  `notice` basis, **and the row's `job_count` equals the headcount stated in the
  filing.** The count is the discriminator every 2026-08-01 false positive
  failed.
- **PROPOSED** — names and window only. The loose rule, which over-accepts by
  design; it is the upper end.

Retrieval is a **separate object** from matching. `/query?company=` is a
substring LIKE, and the stored name may be longer than the filer name
("Starbucks Corporation" vs `STARBUCKS CORP`) or shorter ("ZoomInfo" vs
`ZoomInfo Technologies Inc.`); both were observed in a single calibration run.
Retrieval therefore sends the shortest distinctive leading run of the name and
the prefix rule decides afterwards. A row that cannot be read — including one
buried past the page budget — is **unreachable**, never absent.

## Calibration: the band is scored against the editor, not asserted

`python3 railway/rolling_recall.py --calibrate` runs the matcher over the 57
hand-adjudicated events. Run 2026-08-17:

| | count |
|---|---|
| editor-matched events reaching CONFIRMED | 53 |
| editor-matched events reaching PROPOSED | 2 |
| editor-matched events scored ABSENT | **0** |
| editor-**rejected** candidates reaching CONFIRMED | **0** |
| unreachable | 1 |

Zero false positives means the lower end is a genuine lower bound. Zero
upper-bound misses means the upper end is a genuine upper bound. Re-run this
whenever either rule is touched; `railway/tests/test_rolling_recall.py` pins the
logic it validated.

## What this figure can and cannot support

It describes **US public companies filing 8-K Item 2.05 with a headcount stated
in the primary document**, over one rolling twelve-month window.

It says nothing about private employers, non-US employers, WARN-only events or
news-only events. **It must never be quoted as "the tracker's recall."** The
honest label is the long one: *recall against enumerated SEC Item 2.05 filings
with a stated headcount, [window], n=[denominator]*.

Two further limits, stated rather than buried:

- **The denominator is the machine-decidable subset**, 45 of 215 enumerated
  filings. Filings whose count is unambiguous in the primary document may well
  be easier for the pipeline than those whose count hides in an exhibit, so this
  figure plausibly *overstates* recall over the full Item 2.05 corpus. The 59
  undecidable filings are listed by name in the measurement so the size of that
  blind spot is always visible.
- **The first window is a swept window.** After the 2026-08-01 forensics found
  that the rotating sweep had never returned to recent months, about $1.01 of
  model time was spent deliberately sweeping exactly these twelve months. A high
  figure over 2025-07..2026-06 is partly a measurement of that repair. The
  number becomes more informative as the window advances into months nobody
  targeted — which it does by itself, one month at a time.

## The slice that is not measurable, and why that is a result

`state_warn_official_totals` is declared and reports **NOT MEASURABLE**, with
its assessment date, rather than being left out.

We ingest every state's WARN listing, so our own collectors can never be that
denominator. The independent denominator would be a state's own published period
total, separate from the row listing. Seventeen states plus the federal DOL were
checked on 2026-08-17:

- **No national aggregate exists.** US DOL neither maintains a WARN database nor
  requires notices be sent to it; BLS Mass Layoff Statistics ended in 2013.
- **Wisconsin** publishes exactly the right figure — a state-computed annual
  affected-worker total for closed calendar years — and its `robots.txt` sets
  `Disallow: /` for ClaudeBot, GPTBot, CCBot, Google-Extended and others. This
  project does not rename an agent to get around a block aimed at the agent (the
  same reading that kept the FCA National Storage Mechanism out of the UK set).
  **Refused. It is the one real loss.**
- **Washington's** annual legislative report carries both counts and is
  fetchable, but its periods are ad hoc and change between editions ("as of
  Nov. 21, 2024"; "Sept 18, 2024 through Nov 19, 2025"), the figures are
  narrative prose in a PDF, and one state is a thin denominator.
- **Maryland** signals `ai-input=no`. **Massachusetts** and **DOL** return 403 to
  non-browser clients. **New York's** dashboard is a Tableau embed with no
  documented export. North Carolina, Illinois, Ohio, California, Texas,
  Michigan, New Jersey, Pennsylvania, Colorado, Georgia, Virginia, Oregon,
  Minnesota and South Carolina publish rows only, or a moving year-to-date total
  on the same page as the rows.

The assessment expires after `WARN_ASSESSMENT_MAX_AGE_DAYS` (183) and the slice
then reports UNKNOWN, because a standing "not measurable" nobody revisits is a
stale claim wearing a permanent exemption.

## Nothing here is published to a reader-facing page

By decision, not by omission. A coverage figure on a public page is a promise,
and the owner should make it deliberately. The measurement lands in
`railway/rolling_recall_measurement.json`, in `ops_status.py [3c]` and in the
weekly digest. What to claim from it is a separate decision.
