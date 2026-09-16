# US WARN reference set, wave 2 — written before any number was measured

Companion to [`US-WARN-REFERENCE-SET-DEFINITION.md`](US-WARN-REFERENCE-SET-DEFINITION.md),
which governs. Everything that document fixes — the window, the date it is
counted on, the collapse rule, the matching rule, the two tiers, the
adjudication gate, the miss buckets, the sample size, the refusal to rank cells
of 25 — is **inherited unchanged and imported as code, not copied as prose**.
This file records only what is new: which states, why those, what each state's
publication does differently, and what that costs.

Written and committed **before** the first frame was fetched and before the
first tracker query, on purpose, as both predecessors were. If a later commit
changes anything here, the git history says so and the number is re-derived,
not patched.

---

## 1. The gap this closes, and it is the one wave 1 named itself

Wave 1's own §2 states the limit in its own words: the four eligible states were
CA, TX, FL and TN, and *"there is no Midwest state and no Northeast state in the
set"*. It did not choose that. NY, PA, IL, OH, MI, NJ and MA were each excluded
by the format of their own publication on 2026-08-13, and the document said the
honest expectation was therefore that **its measured figure is an optimistic
bound on national WARN recall**.

That is a stated bias with no measurement behind it. This wave exists to put a
number on the half of the country wave 1 could not see. It re-probes exactly the
four largest excluded states — **NY, IL, OH, PA** — and admits the ones that
now pass wave 1's own eligibility rule, unaltered.

**It is not a re-run and it is not an improvement of wave 1.** Wave 1's frozen
set, its manifest, its adjudications and its 99/100 are untouched by this work,
and a test asserts it.

---

## 2. Which states, and the live re-probe that decided it

**The eligibility rule is wave 1's, verbatim.** A state is included if and only
if its official state WARN publication is (a) reachable under a plain browser
User-Agent and permitted by `robots.txt`; (b) statically machine-readable — a
document or a documented open-data API, not a JavaScript-only application, not a
proprietary BI extract, not an undocumented internal endpoint; (c) complete over
the window in one document or one date-bounded query, so the frame can be
enumerated **chronologically** rather than discovered by searching; (d) per
notice, publishes employer, an absolute headcount, and a notice or received
date.

The candidate list is not re-derived: it is wave 1's own excluded list, walked in
its own employment order, stopping at the four largest. Every verdict below is
from a **live probe on 2026-09-16**, not from wave 1's 2026-08-13 verdict and
not from an assumption.

| # | State | Official publication probed on 2026-09-16 | 2026-08-13 | 2026-09-16 |
|---|---|---|---|---|
| 3 | NY | `dol.ny.gov/warn-dashboard` | out (b) | **out (b)** |
| 5 | **PA** | `pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices` | out (b) | **IN** |
| 6 | **IL** | `illinoisworknet.com/LayoffRecovery/Pages/ArchivedWARNReports.aspx` | out (b) | **IN** |
| 7 | **OH** | `dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/<year>_warn_notice.csv` | out (a) | **IN, with a disclosed independence cost — §5** |

Three states, not four. **The set is `IL, OH, PA` and it is named that way** in
its id, so nothing downstream can quietly imply New York is in it.

### New York is out, and the evidence is fresher than wave 1's

`dol.ny.gov/warn-notices` still 301s to `legacy-warn-notices`, whose database is
frozen at 2025-04-01 — the page says so in its own words — and **2025-04-01 is
three months before this window opens**, so the legacy list contains zero
in-window notices. The current list is a Tableau Public embed
(`public.tableau.com/views/WorkerAdjustmentRetrainingNotificationWARN/WARN`).

Wave 1 recorded that the workbook itself downloaded as a 2.5 MB `.twb` holding
two `.hyper` extracts, readable only with `tableauhyperapi` — a dependency this
repo will not add to a hash-pinned lock installed into runners holding two API
keys, for a reference set. **On 2026-09-16 that path is worse, not better: the
`.twb` download returns HTTP 404.** What remains is the dashboard's own
in-page download, which is the `vizql` bootstrap route — an undocumented
internal API, excluded by criterion (b) as it was in August.

So: **New York, the third-largest labour market in the United States, still
publishes no machine-readable WARN list to anyone without a BI tool**, and this
wave cannot say anything about our New York coverage. That is a finding about a
publisher, not about us, and it is reported as one. It is not worked around, and
in particular the `vizql` route is not called, because a set assembled through an
undocumented internal endpoint is not reproducible by a reviewer and would fail
the protocol even if it worked.

### Why PA and IL flipped, and why OH did

None of the three flipped because a rule was softened. Each flipped because the
probe went somewhere wave 1's probe did not.

- **PA — wave 1 probed a URL that no longer exists.** Its verdict was recorded
  against `pa.gov/.../workforce-development/warn-requirements/warn-notices`,
  which returns 404. The live page, found from `pa.gov`'s own published sitemap,
  is under `workforce-development-**home**/`, and it is **fully server-side
  rendered**: 2023 through 2026, grouped by year and month, one accordion item
  per notice carrying employer, site address, county, `# AFFECTED` and
  `EFFECTIVE DATE`. Wave 1's "the table is populated client-side; a plain fetch
  sees headers or nothing" was true of the page it fetched and is not true of
  this one. **A 404 is not evidence about a publisher, and treating it as one
  cost this set a state for a month.**
- **IL — the listing is a dashboard; the RECORD is a monthly spreadsheet.**
  Wave 1 probed `dceo.illinois.gov/workforcedevelopment/warn.html`, whose search
  UI is an iframe into an application, and stopped there. That page links
  Illinois workNet, which publishes **`<Month> <Year> Monthly WARN Report`, one
  XLSX per month since 1999**, and all twelve months of this window exist. It
  is a document, it is chronological by construction, and it carries `COMPANY
  NAME`, `WARN RECEIVED DATE`, `FIRST LAYOFF DATE` and `# WORKERS AFFECTED` per
  row plus the department's own `Total Layoff Events` / `Total Impacted` footer,
  which this set uses as an arithmetic check on its own parse.
- **OH — the agency's index pages are still 404; the agency's data files are
  not.** Every `jfs.ohio.gov` path this project knows returns 404 to a plain
  browser UA on 2026-09-16, exactly as on 2026-07-18 and 2026-08-13. That is a
  real, month-old, unreported breakage of Ohio's own WARN index and it is
  reported again here. The per-year CSVs on Ohio's asset host
  (`dam.assets.ohio.gov`) do resolve, carry `Company`, `Date Received`,
  `Potential Number Affected`, `Layoff Date(s)` and a per-notice PDF `URL`, and
  are the same files the agency's pages link when they are up. Ohio is
  therefore **IN on criterion (b) — a static document — while remaining OUT on
  (a) for its index**, and the consequence for independence is in §5 rather than
  being glossed here.

### The bias this creates, stated before the number

Wave 1 had no Midwest and no Northeast. Wave 2 adds **two Midwest states (IL,
OH) and one Mid-Atlantic state (PA)** and still has **no New England state and
no New York**. Combined, the seven measured states are CA, TX, FL, TN, IL, OH,
PA. That is a materially better frame than four and it is still not a national
sample: MA, NJ, MI, GA, NC, WA, VA and MD remain out, several of them because
their publisher asked agents like this one not to read them (VA, MD) and the
rest on format.

**The pooled seven-state figure is still not "our WARN recall" and still not a
population-weighted national estimate.** It is the mean of seven state samples
with equal weight, reported beside a notice-volume-weighted estimate, exactly as
wave 1 reports four.

---

## 3. The window, and the date each state's window is counted on

**2025-07-01 to 2026-06-30, counted on the notice date** — identical to wave 1
and to the SEC Item 2.05 set, so all three describe the same twelve months.

Wave 1's rule is *the earliest state-published date that represents the filing
itself*: the employer's own notice date where the state publishes it, the
state's own received or posted date where that is all the state publishes. All
three new states fall on the second half of that rule, and one of them is
coarser than any state in wave 1. **Both facts are disclosed here rather than
smoothed over.**

| State | Published date used | Granularity | Note |
|---|---|---|---|
| IL | `WARN RECEIVED DATE` | day | The department's own received date. The employer's notice date is not published. |
| OH | `Date Received` | day | The agency's own received date. |
| PA | the **month heading** the notice is filed under | **month** | PA publishes no per-notice date at all except the effective date. |

**Pennsylvania's month-only basis is exactly sufficient here and would not be in
general, and the reason matters.** The window's boundaries are 1 July and 30
June — both month boundaries. A notice listed under "July 2025" is unambiguously
in the window and one under "June 2026" is unambiguously in it, so **no PA event
can straddle the frame boundary and none has to be guessed across it**. That is
a property of this window, not of PA's publication; a mid-month window would
have made PA ineligible under (d) and it would have been recorded as such.

For PA the reference `notice_date` is therefore set to the **first day of the
listed month**, which is the earliest date consistent with what the state
published, and the §6 matching window is applied to it unchanged. Since that
window runs notice−30d to notice+400d, anchoring at the first of the month
**widens** the near side by at most 30 days and shortens the far side by at most
30 — and the far side has 400 days of slack for an effective date that trails by
60 to 90. The direction of the approximation is recorded because it is not
symmetric.

PA's page also carries a per-item CMS `repo:modifyDate`, which is a day-level
timestamp of when the department last edited that entry. It is captured into
each event as supplementary evidence and **is not used as the window basis**: a
modify date moves when an entry is corrected, and a date that moves cannot
define a frozen frame.

---

## 4. What counts as ONE event

**Wave 1 §4, unchanged, and imported rather than restated:**
`warn_reference_set.collapse_key_name`, `aliases_for`, `query_terms_for`,
`size_band` and `build_events` are called from wave 1's module. There is no
second copy of the collapse rule in this repo and a test asserts the wave-2
module defines none.

One reference event is one `(state, four-token normalised employer name, notice
date)` triple; component rows are retained; the same employer on a different
notice date, or in a different state, is a different event. Exclusions are
recorded with reasons: rescinded/cancelled/withdrawn, no absolute headcount,
no identifiable employer, notice date outside the window.

Two shape notes about the new states, recorded now because they affect the
denominator:

- **IL files one row per site in the same way CA and FL do** (`Compass Group`
  appears four times in July 2025 under four `DBA` site names, one received
  date). The collapse rule handles it; the `DBA` column is retained on each
  component row so a reviewer can see what collapsed.
- **PA's month grouping means every event in a month shares a notice date.**
  Two genuinely separate PA filings by the same employer in the same month
  therefore collapse into one reference event. That **shrinks the PA
  denominator** and, per wave 1's own reasoning about over-collapsing, can only
  **inflate** PA's measured recall. It is disclosed here and PA's collapsed
  multi-row event count is reported in the manifest so the size of the effect is
  visible rather than assumed.

---

## 5. Independence, per state, including where it is weakest

Wave 1's rule: the reference set is enumerated from a source independent of our
own collection, barred from our database, our repo, our registry, our site, and
from any competitor or commercial listing. No commercial layoff service
populates a row here and none is named in this repo. Its four mitigations apply:
a different document where one exists, a different parser in every case, a
different (chronological) order, and a selection rule fixed before the first
query.

**Per state, honestly:**

- **IL — strongest of the three.** Our Illinois collector does not read these
  monthly spreadsheets. The frame is a different document, from a different
  host, in a different format, parsed by a stdlib XLSX reader written for this
  measurement.
- **PA — strong on document, weak on nothing in particular.** The frame is the
  department's own HTML listing, parsed by code written for this measurement
  that imports nothing from `sources/`.
- **OH — WEAKEST, and this is the one to read.** The frame is **the same two
  CSV files `sources/warn_custom.fetch_oh` fetches**, reached by the same stable
  DAM path, because Ohio's index pages are 404 and there is no second document.
  So for Ohio this set is independent of our **parser, our cleaning, our
  ordering, our unit and our matching**, and is **not independent of our input
  file**. That is the same disclosure wave 1 made about Texas's Socrata dataset,
  and it is weaker here than there because Texas's dataset is a documented open
  API discoverable by anyone while Ohio's CSV path currently is not.
  **The mitigation, and it is a real one:** each Ohio CSV row carries a `URL` to
  the employer's own notice PDF on the state's asset host. For every Ohio event
  drawn into the sample, that PDF is fetched and the employer, the headcount and
  the received date are **transcription-verified against the state's own primary
  notice** before any tracker query exists. A transcription that disagrees with
  the CSV is recorded on the event and the event goes to the queue flagged, not
  corrected silently. That does not make the frame independent — a notice absent
  from the CSV is still absent — and it is not claimed to.

**What none of this is independent of: our design.** Our WARN collectors read
these same agencies. This measures whether the pipeline captures what its own
primary sources publish, not whether the tracker sees layoffs the state never
heard about. Same caveat as wave 1, same words, same reason.

---

## 6. The matching rule

**Wave 1 §6, unchanged and imported:** `warn_reference_set.candidates_for` and
`recall_goldset.name_matches` are called directly. Token-prefix alias match on
`company_name`; row state equals the reference state when the row carries one;
`notice_date − 30d ≤ row date ≤ notice_date + 400d` on `layoff_date` falling
back to `announcement_date`; `exact` when a WARN-tier row additionally carries
the notice total or one component row's count, `loose` otherwise.

**The adjudication gate applies and is not softened.** Every candidate,
including every `exact` one, ships as a proposal with `match_decision:
not_matched`. **The editor-confirmed numerator starts at zero by construction**
and stays there until a reviewer signs each decision through
`railway/warn_adjudicate.py`, exactly as wave 1's did before 2026-08-14. The
machine's proposal is reported separately and labelled an upper bound, and
**must never be quoted as recall**.

A query that could not be completed, or an event for which no alias could be
derived, is **UNKNOWN**. It is not a miss, it is excluded from both numerator
and denominator, and it is listed by id with its reason.

---

## 7. The sample

Per state, the in-window frame is sorted ascending by `(notice_date, employer)`
and sampled systematically: interval `k = floor(N/n)`, start `seed mod k`, seed a
fixed function of the state code, recorded so the draw cannot be re-rolled.
**n = 25 per state, 3 states, 75 reference events.** Size bands S (1–99),
M (100–499), L (500+) on the summed affected headcount of the notice — **event
size, not employer size**. Every L event in all three frames is censused as a
supplementary stratum, measured, and **reported on its own, never pooled** into
the primary figure.

**These cells will not be used to rank states**, here or against wave 1's four.
A cell of 25 carries a Wilson interval roughly 14 points wide even at the
ceiling. Every figure is published with its Wilson interval attached.

---

## 8. Miss classification

Wave 1 §8's six buckets, unchanged: `no_source`, `walked_not_read`,
`fetched_rejected`, `extracted_dropped`, `stored_unmatched`, `UNKNOWN`. Every
unmatched event gets exactly one, with a one-line cause, so the result is a
worklist rather than a score. `UNKNOWN` is a verdict and not a bucket of
convenience.

**No code in the collection pipeline is changed in the commit that produces this
number.**

---

## 9. What this set may and may not be used for

- **Internal reference set**, single author, `publication_status` says so. It is
  **not** posted to `/benchmarks/recall`, which requires the three-actor review
  chain in [`../RECALL_BENCHMARK_PROTOCOL.md`](../RECALL_BENCHMARK_PROTOCOL.md).
- It **does not touch** `railway/recall_measurement.json`,
  `railway/recall_adjudications.json`, `MATCHED_FLOOR`, the SEC manifest, **or
  wave 1's own manifest, adjudications and measurement**. Tested, not asserted.
- Its number is **not "our recall"**. It describes three states' WARN
  notifications over one twelve-month window, on an equal-allocation sample of
  75 plus a large-event census, with no New York in it.
- **No model is called.** Enumeration, matching and classification are
  deterministic code and read-only GETs. Spend: **$0.00**.
- **Every published figure is derived from the committed measurement files by
  `railway/warn_recall_pooled.py` and never typed.** The results document's
  figure block is generated; `railway/tests/test_warn_recall_pooled.py` fails if
  a committed figure disagrees with what the measurement files compute, on the
  precedent of `tests/test_cadence_is_derived.py`.

---

## 10. Reproducing it

```bash
python3 railway/warn_reference_set_wave2.py --build     # re-enumerate the frames, redraw the sample
python3 railway/warn_reference_set_wave2.py --measure   # frozen set vs the live read API
python3 railway/warn_reference_set_wave2.py --pack      # per-row adjudication sheet
python3 railway/warn_recall_pooled.py --render          # regenerate every derived figure block
```

The frames are fetched live from the three agencies each time; a state that has
edited its own published list since assembly shows as a frame drift and is
reported, not silently absorbed.
