# What a US WARN reference event IS — written before any number was measured

This document was committed **before** the first tracker query, on purpose, as
`UK-REFERENCE-SET-DEFINITION.md` was. Everything below — the states, the window,
the date the window is counted on, what collapses into one event, the sample
size, the strata, the matching rule and the stated biases — is fixed here and
is not revised after seeing a result. If a later commit changes any of it, the
git history says so and the number must be re-derived, not patched.

---

## 1. The gap this closes

US recall is measured at **53 of 57, 93.0%**, over SEC Form 8-K filings carrying
structured item code 2.05. That set is excellent at what it does and it can only
see one kind of employer: **a US public company that files 8-Ks**. It has no
industry dimension, no state dimension, and no private employers at all. It
produces exactly one number.

Meanwhile the tracker ingests US state WARN notices at volume — `warn_import.py`
plus `sources/warn.py` and `sources/warn_custom.py`, a daily 11:00 ET cron over
roughly 48 states — and **has never measured what fraction of them it holds**.
WARN is mandatory disclosure by statute, it is already inside the pipeline, and
it covers exactly the private employers Item 2.05 cannot see. That makes it the
highest-value unmeasured slice available.

**This is a different KIND of claim from the SEC set, and the difference is not
cosmetic.** The SEC set asks "does the tracker hold the events its own primary
regulator source publishes?" — a question about one collector reading one index.
This set asks the same question of a *different* collector over a *federated*
corpus of fifty separate state publications with fifty different formats, and
the answer is allowed to differ per state. It is designed so that it does.

---

## 2. Which states, and why those four

**Selection rule, fixed before any tracker query.** Walk the US states in
descending order of total nonfarm employment. Include a state if and only if its
**official state WARN publication** satisfies all four of:

- **(a) reachable** under a plain browser User-Agent and permitted by
  `robots.txt`;
- **(b) statically machine-readable** — a document or a documented open-data
  API. Not a JavaScript-only application, not a proprietary BI extract, not an
  undocumented internal endpoint;
- **(c) complete over the window** in one document or one date-bounded query, so
  the frame can be enumerated **chronologically** rather than discovered by
  searching;
- **(d) per notice, publishes employer, an absolute headcount, and a notice or
  received date.**

Stop at four included states. Every excluded state is recorded with the property
it failed. Every verdict below is from a **live probe on 2026-08-13**, not from
an assumption.

| # | State | Official publication probed | Verdict |
|---|---|---|---|
| 1 | **CA** | EDD archived FY report `warn-report-for-7-1-25-to-6-30-26.pdf` | **IN** |
| 2 | **TX** | TWC open data, `data.texas.gov/resource/8w53-c4f6.json` | **IN** |
| 3 | NY | `dol.ny.gov/warn-dashboard` | **out (b)** |
| 4 | **FL** | `reactwarn.floridajobs.org/WarnList/Records?year=` | **IN** |
| 5 | PA | `pa.gov/.../warn-requirements/warn-notices` | out (b) |
| 6 | IL | `dceo.illinois.gov/workforcedevelopment/warn.html` | out (b) |
| 7 | OH | `jfs.ohio.gov/.../current-public-notices-of-layoffs-and-closures` | out (a) |
| 8 | GA | `tcsg.edu/warn-public-view/` | out (b) |
| 9 | NC | `commerce.nc.gov/data-tools-reports/...` | out (a) |
| 10 | NJ | `nj.gov/labor/employer-services/warn/` | out (b) |
| 11 | MI | `michigan.gov/leo/.../warn-notices` | out (b) |
| 12 | MA | `mass.gov/info-details/worker-adjustment-...` | out (a) |
| 13 | VA | `virginiaworks.gov/warn-notices` | **out (a) — robots** |
| 14 | WA | `esd.wa.gov/.../warn-layoff-and-closure-database` | out (b) |
| 15 | AZ | `azjobconnection.gov/search/warn_lookups` | out (a) — HTTP 400 |
| 16 | **TN** | `tn.gov/workforce/.../reports.html` | **IN** |

Details on the exclusions, because "out" is a claim and needs evidence:

- **NY** — the live list is a Tableau Public visualization. The workbook
  downloads (`.twb`, 2.5 MB, permitted by `public.tableau.com/robots.txt`) and
  contains **two `.hyper` extracts**, a proprietary format needing
  `tableauhyperapi` — a dependency this repo may not add on a whim, because
  `railway/requirements.lock` is hash-pinned and a reference set is not a reason
  to widen the install surface of a runner holding two API keys. The embed page
  carries no session id, so the `vizql` bootstrap route is an undocumented
  internal API and is not used. `dol.ny.gov/warn-notices` 301s to
  `legacy-warn-notices`, the database frozen 2025-04-01, which does not cover
  the window. **New York is the third-largest labour market in the country and
  its current WARN list is not machine-readable by anyone without a BI tool.**
- **PA, IL, GA, NJ, MI** — the page returns HTTP 200 and the notice rows are not
  in it. The table is populated client-side; a plain fetch sees headers or
  nothing.
- **OH, NC** — every documented path to the agency's own WARN listing returned
  **404** on 2026-08-13, including the archive-page pattern
  `sources/warn_custom.fetch_oh` builds and the `dam.assets.ohio.gov` fallback
  it keeps for exactly this failure. That is a separate finding and it is
  reported separately; it is not evidence about recall.
- **MA** — HTTP 403 to a plain UA.
- **VA — out on an explicit publisher instruction, and this one hurt.**
  `virginiaworks.gov` publishes a static HTML table of 1,121 notices with
  Company, Notice Date, Impact Date, Employees Affected, Location and Notice
  Type, **plus its own CSV export**. On the content test it is the best source in
  this document. `https://www.virginiaworks.gov/robots.txt` names, each with
  `Disallow: /`: `GPTBot`, `ChatGPT-User`, `CCBot`, `anthropic-ai`,
  **`ClaudeBot`**, **`Claude-Web`**, `Google-Extended`, `Bytespider`,
  `PerplexityBot` and others, then allows Googlebot, Bingbot, DuckDuckBot and
  Applebot by name and gives `*` a crawl-delay. That is not an accident of
  configuration; it is a publisher deciding which kinds of agent may read it, and
  this one is named twice. Running as `AiLayoffTracker/1.0` would formally fall
  under `*` — **and renaming the agent to evade a block aimed at the agent is not
  a reading of robots.txt this project is willing to make.** That is the same
  call the UK reference set made about the FCA's National Storage Mechanism, for
  the same reason, and it has to be the same call when the blocked source is the
  convenient one. *One CSV was fetched during eligibility probing, before the
  robots file was read. It was deleted unread of any row, it populates nothing,
  and it is recorded here rather than quietly forgotten.*
- **MD** — static HTML, per-year archive, Notice Date + NAICS + Company +
  Location + Total Employees + Effective Date + Type. Excellent content, and
  `dllr.state.md.us/robots.txt` carries
  `Content-Signal: ai-train=no, search=yes, ai-input=no`. `ai-input=no` is an
  explicit request that the content not be used as input to an AI system, which
  is what building this frame would be. **Out**, on the same principle as VA and
  as the BBC in the UK document. It is named here so that "why not MD" has an
  answer that is not hindsight.
- **AZ** — HTTP 400 to a plain UA on the documented WARN lookup path.
- **TN** — in, with one disclosed variance, see §3.

### The bias this creates, stated before the number

The four states are **CA, TX, FL, TN** — West, Southwest, Southeast, Midsouth.
**There is no Midwest state and no Northeast state in the set**,
and that is not a sampling choice: NY, PA, IL, OH, MI, NJ and MA were all
excluded by their own publication format. The consequence is direct and must not
be glossed: **this set cannot say anything about our WARN coverage in the
industrial Midwest or the Northeast.** If anything, the excluded states are the
ones where our own collectors are most likely to be struggling — a JS-only page
is hard for the tracker's scraper for the same reason it is hard for this
enumeration — so the honest expectation is that **the measured figure is an
optimistic bound on national WARN recall**, and it is labelled that way.

---

## 3. The window, and the date it is counted on

**2025-07-01 to 2026-06-30, counted on the NOTICE DATE** — the date the employer
notified the state, as the state itself publishes it: `Notice Date` in CA,
`notice_date` in TX, `State Notification Date` in FL.

**Tennessee is the one variance and it is disclosed rather than smoothed over.**
TN publishes `Date of Posting` — the date the department posted the notice — and
does not publish the employer's own notice date in the list. So for TN the window
is counted on the posting date. The rule is therefore, precisely: *the earliest
state-published date that represents the filing itself* — the employer's notice
date where the state publishes it, the state's own received/posted date where
that is all the state publishes. California publishes both and lets the size of
the substitution be measured rather than assumed: on the first page of its FY
report the notice-to-processed lag is 0 to 1 day. That lag is reported for the
whole CA frame in the manifest, and it is the best available evidence for how
much TN's substitution moves an event across the window boundary.

Three reasons, and the third is the one that decided it:

1. It is **the same twelve months as the SEC Item 2.05 set**, so for once two of
   this project's reference sets describe the same period and may legitimately
   be compared. The UK set could not do this and said so.
2. It is the **analogue of the SEC set's `file_date`**: the moment the
   disclosure exists and becomes discoverable. Recall is about what we captured
   from what was published, so the clock should start when it was published.
3. California's archived WARN report is published on a **fiscal year that is
   exactly 1 July to 30 June**. The largest state in the set publishes a closed,
   immutable document whose boundaries are the window's boundaries. Choosing any
   other window would have meant assembling CA's frame from a rolling file that
   changes twice a week.

**WARN has two dates and this repo already distinguishes them, so the choice has
teeth.** `sources/warn.py::_entry` stores the **effective date** as
`layoff_date`; `alt_db_valid_date` on the server accepts back to 2000 on the
WARN/bulk path while the LLM path (`extractor.py`) nulls anything before 2015.
So the reference set counts on one date and the tracker stores another, and the
matching rule in §6 has to bridge that gap explicitly rather than by luck. An
event notified in June 2026 with an effective date in October 2026 is **in this
set** and its tracker row carries a 2026-10 `layoff_date`.

The window closed six weeks before this set was assembled. That is deliberate
slack: a notice filed in late June 2026 has had six weeks to be scraped, posted
and deduped. It is not enough slack for a state that publishes on a quarterly
lag, and no state in the set does.

---

## 4. What counts as ONE event

CLAUDE.md: *"WARN entries are EXEMPT from fuzzy/cross-outlet dedup (companies
legally file several notices close together)."* That rule is about not merging
things. It means the unit of a reference set **has to be defined and cannot be
assumed**, because the pipeline deliberately does not impose one.

**A reference event is one `(state, normalised employer name, notice date)`
triple.**

- Several published rows sharing all three — the same employer notifying the
  same state on the same day for several sites, floors or job titles — are **one
  reference event**, and its `stated_job_count` is the **sum** of those rows.
  This is the exact case CLAUDE.md exempts from dedup: one corporate action, as
  the state itself received it, on one day.
- The **same employer on a different notice date is a different event**, even
  days apart. The state processed a distinct filing; our own `dedup_hash`
  (`warn + company + date + jobs + state`) treats it as distinct; and collapsing
  them would let one held row excuse an arbitrary number of missed ones.
- The **same employer in a different state is a different event.** State is in
  the dedup hash and in the notice.

Normalisation for the collapse is **applied to the state's published name
only**. It does not use `warn_import._clean_company` or
`warn_import._strip_site_address`, because those functions are part of the thing
being measured: if the reference set normalised employer names the way our
importer does, a defect in that function would cancel itself out and score as a
match.

> **AMENDMENT, 2026-08-13, before any frame was built and before any tracker
> query.** The first draft of this section said the normalisation would be
> "case-fold, collapse whitespace, strip a trailing corporate suffix". Inspecting
> the four publications showed that is not enough to make the unit work, and a
> unit that does not work is worse than a slightly less minimal one:
>
> - California writes the **site into the employer cell** — `Blue Shield of
>   California - Oakland`, `Blue Shield of California - Town Center, Building B`,
>   `Blue shield of California - Long Beach`, all notified on the same day.
> - Texas does the same with a street — `Stearns Lending, LLC - Corporate Dr.`
> - Florida **glues the full street address on** — `Railcrew Xpress 1718-1 North
>   McDuff AvenueJACKSONVILLE, FL, 32254`.
>
> Under the minimal rule none of those collapse, and a ten-site notice would have
> entered the frame as ten events. So the collapse key is: unescape entities,
> case-fold, collapse whitespace, **cut at a street-address or city/ST/ZIP
> pattern**, **cut a trailing ` - <site qualifier>` or ` (<site>)`**, drop
> corporate suffixes, then take **the first four remaining tokens**.
>
> Four tokens, not one or two, because the risk runs one way: over-collapsing
> shrinks the denominator and lets one held row excuse several missed ones, which
> **inflates recall**. Four is short enough to unify a site list and long enough
> that two different employers rarely share it. Every component row of every
> collapsed event is written into the manifest so a reviewer can check the
> collapse itself rather than trust it.
>
> The address-cutting regex resembles `warn_import._strip_site_address` in intent.
> It is independently written and lives in `railway/warn_reference_set.py`, and —
> this is the part that matters — **it is used only for the collapse key. The
> aliases that are actually queried are derived from the state's full published
> name.** So if our importer's own cleaning is broken, this set still sees it.

**Consequence for the number, stated up front.** This unit makes recall a
question about *notified corporate actions*, not about *published table rows*.
A ten-site Walmart filing is one event we either hold or do not, rather than ten
chances to be 70% right. That is the harder and more meaningful denominator, and
it makes this figure **not** comparable to a row-level "how many WARN rows do we
have" ratio.

### Exclusions, recorded with reasons rather than dropped

- A row the state marks **rescinded, cancelled or withdrawn** is excluded. It is
  a layoff that did not happen; `warn_import._RESCINDED_RX` drops those on the
  way in, so counting them would score a documented and correct design decision
  as a miss. (An audit already found 23 such rows carrying 5,050 phantom jobs.)
- A row with **no absolute headcount**, or a headcount of 0, is excluded — the
  same bar the SEC set applied to percent-only 8-Ks.
- A row with **no identifiable employer** is excluded.
- A row whose notice date is **outside the window** is excluded. It is not
  "found late"; it is out of frame.

Every exclusion is written into the manifest with its reason and its source
locator. Silently dropping no-match rows is the failure mode
`docs/recall-reference-sets/README.md` names explicitly.

---

## 5. Independence, and the sharper trap in this one

The rule: a reference set is enumerated from a source **independent of our own
collection** — barred from our database, our repo, our registry, our site, and
from any competitor or commercial listing. The owner reconfirmed the
competitor-listing bar on 2026-08-12; no commercial layoff service populates a
row here and none is named in this repo.

**Here the trap is sharper than usual and it deserves its own paragraph.** We
already scrape most of these states. Fetching the same page our scraper fetches
is *not* independence if we take it in the same order, through the same parser,
with the same cleaning. Four things are done about that:

1. **A different document where one exists.** California's frame is the EDD's
   **archived fiscal-year PDF**. Our CA collector reads `warn_report1.xlsx`, a
   rolling spreadsheet refreshed every Tuesday and Thursday that at the time of
   writing contains only FY 2026-27. The reference frame and the collector's
   input are two different files, published separately by the same agency.
2. **A different parser, in every case.** The frame is extracted by code written
   for this measurement and living in `railway/warn_reference_set.py` — a
   stdlib-only PDF text extractor with coordinates, a stdlib CSV/HTML reader —
   and it imports nothing from `sources/warn.py` or `sources/warn_custom.py`.
   Where a state's shape is identical for both (TX Socrata), the manifest says
   so plainly rather than implying otherwise.
3. **A different order.** The frame is re-sorted **chronologically by notice
   date** and sampled systematically along that axis. State pages publish
   newest-first and our scrapers consume them in that order; a set that inherited
   it would over-sample exactly the rows a "most recent N" pull is most likely
   to have caught.
4. **The selection rule was fixed before the first tracker query**, in this file,
   in a commit that precedes the measurement commit.

**What this set is NOT independent of: our design.** Our WARN collectors read
these same agencies. So this measures *whether the pipeline captures what its
own primary sources publish* — not whether the tracker sees layoffs the state
never heard about. That is the identical caveat the SEC set carries about EDGAR,
and it is stated here in the same words for the same reason.

---

## 6. The matching rule, fixed before the first query

Queries go to the public read API (`/query?company=`), read-only GETs, browser
User-Agent, cache-busted.

**Aliases** are derived mechanically from the state's published employer name:
the cleaned full name, and its leading 2 and 3 tokens. Comparison uses
`recall_goldset.name_matches` — a **token-prefix**, not a substring, because
the API's `company=` filter is a substring LIKE and a containment test scored
Experian as Xperi and Dow Jones as Dow on 2026-08-01.

**A candidate row must satisfy all of:**

- alias token-prefix match on `company_name`;
- the row's `state` equals the reference state, when the row carries one;
- `notice_date − 30 days ≤ row date ≤ notice_date + 400 days`, where the row date
  is `layoff_date` falling back to `announcement_date`.

The window is wide and lopsided **on purpose**: our WARN rows store the
**effective** date, which typically trails the notice by 60–90 days and
sometimes by much more (a future-dated plant closure). Thirty days of slack on
the near side absorbs a state that publishes a received date a little after the
employer's own notice date. A narrow symmetric window would have manufactured
misses out of a date-field mismatch that §3 already identified.

**Two tiers, and neither one is a match.**

- **`exact`** — a candidate that additionally carries the same `job_count` as the
  reference event or as one of its component rows, from a WARN-tier source. This
  is close to the `dedup_hash` identity itself and it is expected to survive
  adjudication at near 100%.
- **`loose`** — alias, state and window only.

**THE ADJUDICATION GATE APPLIES AND IT IS NOT SOFTENED HERE.** Every candidate,
including every `exact` one, ships as `candidates_needing_adjudication` with
`match_decision: not_matched`. The editor-confirmed numerator therefore **starts
at zero by construction**, exactly as the SEC set stood on 2026-08-12 before the
owner decided the 29 and exactly as the UK set stands now. The machine's
proposal is reported **separately, as an upper bound**, and it is never written
into a numerator. On the SEC set the machine's loose rule scored 31 where the
editor scored 24; there is no reason to assume it is kinder here, and the
`exact`/`loose` split exists so a reviewer can see which of the two is doing the
work before believing either.

The adjudication sheet is built the way `recall_adjudication_pack.py` builds
one, **with the defect fixed on 2026-08-12 designed out from the start**: that
sheet pooled the flags from several proposed rows into one summary line, and a
reviewer reading a pooled line rejected a correct Dow row because the summary
described a *co-proposed* row. **Every flag in this sheet is attributed to the
single row it came from**, and no line in it describes more than one candidate.

---

## 7. The sample: size, strata, and what the cells can carry

**Primary sample.** Per state, the in-window frame is sorted ascending by
`(notice_date, employer, source row order)` and sampled **systematically**:
interval `k = floor(N/n)`, start index `seed mod k`, where the seed is a fixed
function of the state code, recorded in the manifest so the draw is reproducible
and was not re-rolled. **n = 25 per state, 4 states, 100 reference events.**

**Allocation is equal, not proportional, and that has a consequence.** 25 from
California and 25 from Virginia means the pooled figure is **not** a
population-weighted national estimate — it is the mean of four state samples
with equal weight. Both are reported: the equal-allocation pooled figure (which
is what the per-state cells add up to) and a **notice-volume-weighted** estimate
using each state's own in-window frame size as the weight. Where they disagree,
the disagreement is the interesting part and neither is quietly preferred.

**Strata.** Every event carries its state and its **event size band**, banded on
the *summed affected headcount of the notice*:

| Band | Affected workers |
|---|---|
| S | 1–99 |
| M | 100–499 |
| L | 500+ |

**This is event size, not employer size.** WARN publishes how many workers a
notice affects; it does not publish how large the employer is. A 60-person
notice from a 200,000-employee retailer lands in S. The manifest says `size_band`
and never `employer_size`, and no claim is made about small *employers*.

**Large events get a census, reported separately.** L events are rare, so a
100-event systematic sample would leave that cell at two or three and unable to
carry an interval. Every L event in all four states' in-window frames is
therefore enumerated as a **supplementary stratum** and measured, and it is
**reported on its own and never pooled into the primary figure** — pooling a
census with a systematic sample would double-count the L events that fall in
both and silently reweight the result.

**What the cells can carry, decided now so it cannot be decided by the result.**
A per-state cell of 25 gives a Wilson 95% interval roughly ±17 points near the
middle. That is enough to say "this state is not obviously the same as that one"
only when the point estimates are more than about thirty points apart. **These
cells will not be used to rank the four states**, for the same reason the UK
set's author refused to rank metros on 8-to-16-event cells. Every figure is
published with its Wilson interval attached and no figure is quoted to the
nearest percent from a cell of 25.

---

## 8. Miss classification — the part worth more than the percentage

Every unmatched reference event is classified, as the talent gap map does, into
exactly one of:

| Bucket | Meaning |
|---|---|
| `no_source` | no collector in this pipeline covers that state's publication at all |
| `walked_not_read` | the collector covers the state, but this notice was never in a page or file it fetched |
| `fetched_rejected` | fetched, then dropped by a guard before extraction (rescinded regex, name-cleaning, bounds) |
| `extracted_dropped` | parsed into an entry, then lost at the post/upsert boundary |
| `stored_unmatched` | the tracker holds a row for it that the §6 rule did not find (alias, state or date-window failure) |
| `UNKNOWN` | it cannot be placed on the evidence available |

**`UNKNOWN` is a verdict, not a bucket of convenience.** A miss whose cause
cannot be evidenced from a collector's own output goes there and stays there. On
the SEC set, most of the apparent 57.9% gap turned out to be
`stored_unmatched` — events we already held and had never adjudicated. Expect
the same shape here and do not tune anything toward it: **no code in the
pipeline is changed in the commit that produces this number.**

---

## 9. What this set may and may not be used for

- It is an **internal reference set**, like the SEC one. `publication_status`
  says so. It is **not** posted to `/benchmarks/recall`, which is reserved for a
  sample that has cleared the three-actor review chain in
  `docs/RECALL_BENCHMARK_PROTOCOL.md`. This one has one author.
- It **does not touch the published SEC figure.**
  `railway/recall_measurement.json`, `railway/recall_adjudications.json`,
  `MATCHED_FLOOR` and the SEC manifest are not modified by this work, and that
  is verified rather than asserted.
- Its number is **not "our recall"**. It describes four states' WARN
  notifications over one twelve-month window, with no Midwest and no Northeast in
  it, on an equal-allocation sample of 100 plus a large-event census.
- **No model is called.** The enumeration, the matching and the classification
  are deterministic code and public read-only GETs. The spend against the $18
  monthly allowance is **$0.00**.

---

## 10. Reproducing it

```bash
python3 railway/warn_reference_set.py --build     # re-enumerate the frame, redraw the sample
python3 railway/warn_reference_set.py --measure   # re-run the frozen set against the live API
python3 railway/warn_reference_set.py --pack      # rebuild the per-row adjudication sheet
```

The frame is fetched live from the four agencies each time; a state that has
edited its own published list since assembly will show as a frame drift and is
reported, not silently absorbed.
