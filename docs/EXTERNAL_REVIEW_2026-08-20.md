# External adversarial review — 2026-08-20

**Audience:** Claude / repository owner  
**Scope:** `dk-forge/ai-layoff-tracker` and `dk-forge/talent-intelligence-tracker`  
**Review posture:** a wrong published number is worse than missing data; a visible failure is better than a false green.

## Review boundary

This review used fresh public checkouts, not an older local checkout:

- `ai-layoff-tracker` at `014f9eed7d95c7c9e9a1507c245719b9b267f0e6` (2026-08-20 17:58 UTC)
- `talent-intelligence-tracker` at `587772e5a99f4f5d1c1a0898ba49c087fe2013ec` (2026-08-20 23:11 UTC)

I did not change application code or data. This is the only file I added.

I inspected repository code, committed ledgers/databases, tests, and operational reports. I did **not** inspect Railway secrets or runtime variables, query the live WordPress APIs, read private GitHub Actions logs, or live-test every state/country endpoint. Where those boundaries matter, the result below is **UNKNOWN** rather than inferred.

## Executive verdict

Claude's code is generally good: it is unusually explicit about data provenance, corrections, cost controls, source health, and failure containment. The codebase also contains strong regression tests and thoughtful comments explaining previous incidents. I would keep Claude as the implementing programmer.

It is not yet bulletproof enough for citation-grade numbers. The largest remaining risk is not coding style. It is a repeated semantic gap: several guards prove that a job ran, a count is nonzero, or an aggregate reconciles, but do not prove that the underlying fact belongs in that aggregate. That permits a wrong number or incomplete collection to look healthy.

The highest-cost confirmed finding is in the talent tracker: its committed database marks at least **$3.444 billion** of obvious company spending/capex as published funding. The live site's current state is **UNKNOWN** because I did not call its API, but the repository's published-state database says these rows were sent to WordPress.

For the layoff tracker, the most urgent exposures are:

1. Google News is not enforcing the trusted-domain promise before extraction/publication.
2. WARN freshness can report healthy for months or years after collection stops because it measures future effective layoff dates, and its exception path can still say every state is publishing new notices.
3. GDELT's broad-query failure is visible, but failures of its additional rotating queries silently reduce coverage and are not durably replayed.

## Severity and ranking

- **P0 — stop publication/recompute:** confirmed wrong aggregate or a mechanism that is currently publishing a known-wrong number.
- **P1 — correctness/false-green exposure:** can publish an inadmissible number, or can say healthy while material collection is unverified.
- **P2 — material coverage/cost/reliability:** loses data or money but is less likely to make a presently published number false.
- **P3 — optimization/tidiness:** only after the above.

| Rank | Severity | Repo | Finding | Actual cost |
|---:|:---:|---|---|---|
| 1 | **P0** | Talent | Published “Money raised” includes at least $3.444B of company spending/capex | Confirmed aggregate contamination in the committed published-state DB |
| 2 | **P1** | Layoff | Google News has no trusted-domain admission gate despite the public same-standard claim | An untrusted publisher can supply a counted layoff claim |
| 3 | **P1** | Layoff | WARN freshness can be false-green and can claim freshness after the check itself throws | A stopped state collector can look healthy |
| 4 | **P1** | Talent | Czech ARES stores a future office-effective date as `published_date` | Wrong chronology and period attribution |
| 5 | **P1** | Layoff | GDELT secondary queries fail open without a durable replay queue; cap saturation is not measured | Silent country/language coverage loss |
| 6 | **P1** | Layoff | Country canonicalization splits or misclassifies valid country names | Country totals can be wrong while worldwide total remains plausible |
| 7 | **P2** | Talent | Collector status can be `ok` while large portions are budget-deferred; measured recall is low | The product looks healthier/more complete than it is |
| 8 | **P2** | Talent | A stale backfill ticket can move a cursor backward | Repeated work, duplicate fetching, spend, and misleading completeness |
| 9 | **P2** | Talent | Cost contracts disagree and current projection exceeds the configured allowance | Budget surprises and eventual coverage throttling |

---

## Finding 1 — P0: “Money raised” contains company spending/capex

### Evidence

The current committed `data/talent_intel.db` contains these current rows with non-null `published_at` and `funding_amount_usd`:

| Row | Amount | Headline |
|---:|---:|---|
| 32970 | $1,500,000,000 | Nvidia to invest $1.5b in SB Energy |
| 23198 | $750,000,000 | Resilience and Lilly invest $750M to scale Cincinnati medicine output |
| 23156 | $721,000,000 | AUO commits US$721M to TGV, glass core and CPO expansion |
| 17225 | $250,000,000 | Semiconductor Major Marvell To Invest $250 Mn in India, Double Headcount |
| 17509 | $100,000,000 | Spain's Konecta is investing USD 100 mn to build its AI hub out of Cairo |
| 17574 | $50,000,000 | Simplex inaugurates second factory with $50 million investment |
| 31533 | $32,000,000 | 2A united states investing $32 million in Auburn expansion, creating 50 jobs |
| 18076 | $30,000,000 | Anheuser-Busch Investing $30M in Jacksonville Facilities... |
| 19609 | $10,000,000 | Caterpillar announces $10M workforce investment... |
| 32162 | $1,000,000 | UMAMI invests $1 million in new AI-powered learning platform |
| **Lower bound** | **$3,444,000,000** | Only the ten unambiguous examples above |

There are additional questionable published rows—fund closes, investment commitments, project financing, and public/private placements—but I excluded them from the lower bound because their correct taxonomy requires source-level adjudication.

The design explains the escape:

- `pipeline/capital_event.py` says capex, AUM, and fund closes are handled by `guardrails.NOT_A_COMPANY_ROUND`.
- `pipeline/guardrails.py` applies that veto to large-number quarantine/corroboration paths; it is not a universal positive eligibility rule for every `funding_amount_usd`.
- Below the amount threshold, a parsed amount can therefore enter the public funding aggregate without proving that the named company **received** financing.
- The operational “published figures” guards pass because the stored and published arithmetic reconciles. They do not test semantic eligibility.

### Required correction

Use a positive rule, not an ever-growing negative regex:

> A value may contribute to “Money raised” only when source evidence says the named company is the recipient of a financing event—raised, closed, received, or secured a round/financing—or when an allowed structured filing establishes that relationship.

Capex, investment by the company, acquisition consideration, fund size, AUM, commitments to a region, debt repayment, project cost, grants to another entity, and public-market offering proceeds outside the chosen product definition must not enter `funding_amount_usd`. They can remain as typed capital events in a separate field if useful.

### Safe repair sequence

1. Freeze changes to the public funding aggregate or place new ambiguous amounts in quarantine.
2. Add a `funding_eligibility`/capital-event type with `eligible`, `ineligible`, and `unknown`; default `unknown` must not count.
3. Re-adjudicate every currently published row with non-null `funding_amount_usd`, not only rows above a magnitude threshold.
4. Create revisions that clear the ineligible values; recompute and reconcile all public totals.
5. Record the aggregate change as a correction, not as funding activity.

### Acceptance tests

- The ten rows above contribute $0 to “Money raised.”
- “Investor X invests $N in Company Y” assigns the financing to Y, never automatically to X.
- “Company X invests $N in a factory/data center/hub/workforce” never counts as money raised by X.
- All published nonzero funding values have stored, quoted evidence naming the recipient and event type.
- A database-wide semantic audit, not just top-N guardrails, returns zero ineligible published values.

**Live-site status:** **UNKNOWN.** The repo DB marks these rows published; the live WordPress aggregate was not queried in this review.

---

## Finding 2 — P1: Google News violates the public trusted-outlet contract

### Evidence

`railway/sources/google_news.py` reads the RSS publisher name but does not parse and enforce the publisher URL against the GDELT allowlist. It stores the Google News redirect as `source_url`. I found no downstream server-side trusted-domain admission gate before the item can be extracted and posted.

The public sources template says Google News uses the “same trusted-outlet standard” and describes discovery as coming from a reviewed allowlist, never the open web. The implementation does not establish that claim.

The existing verbatim-number check is useful but insufficient. It proves a number occurred in the text; it does not prove that the publisher is admissible, independent, or reliable.

### Cost

This is a correctness boundary, not merely a disclosure wording issue. Any outlet indexed by Google News can become the evidentiary basis for a counted layoff if the remaining extraction checks pass.

### Required correction

- Move the 705-domain policy into one shared module used by GDELT, Google News, tests, and the public disclosure generator.
- Parse the RSS `<source url="...">`, normalize its hostname, and enforce admission **before** any paid extraction.
- Treat missing, malformed, redirect-only, or unknown publisher identity as rejected/held, with telemetry—not accepted.
- Store publisher identity separately from the durable article receipt/redirect.
- Add adversarial tests for lookalike subdomains, redirects, URL shorteners, malformed IDNs, missing `<source>`, and syndication/wire exceptions.

The domain gate should reduce model spend as well as correctness risk.

---

## Finding 3 — P1: WARN stale data can look healthy

### 3A. Freshness uses the wrong date for collector health

`railway/source_freshness.py` and `railway/warn_import.py` assess recency from `layoff_date`, which is usually the effective layoff date. WARN notices commonly describe future layoffs. The code itself documents the consequence: a future date delays the alarm.

The committed `railway/source_state.json` illustrates the blind window. Examples include:

- North Carolina max effective date: 2027-12-31
- Nevada: 2028-08-25
- Ohio: 2027-07-01
- Louisiana: 2027-03-31

On 2026-08-20, those future effective dates can keep `days_dark` at zero even if the corresponding collector stops now. A stale cached page can therefore continue to look healthy until the future effective date passes.

### 3B. The freshness check can throw and the terminal status can still say “ok”

`warn_import.py` initializes `_dark` and `_unknown_fresh`, runs the freshness assessment inside a broad exception handler, prints a warning if it fails, and continues. The final success detail can still say that every state is publishing new notices because the empty lists look clean.

That is a direct false-success path: “freshness was not checked” is converted into “every state passed.”

### 3C. Missing baseline evidence can also degrade to apparent success

`load_state_baselines()` warns and returns an empty mapping when the baseline ledger is absent/malformed. That removes the per-state row floors. A nonzero combined result can then finish successfully even though the state-level drift proof was unavailable.

### Required correction

Separate these concepts:

- **Notice freshness:** newest notice/received/registration/publication date observed from the source.
- **Effective horizon:** newest planned layoff date; useful for the product, never evidence that the source is currently updating.
- **Fetch freshness:** last successful fetch plus content fingerprint/ETag/Last-Modified.
- **Completeness proof:** per-state count floors/schema checks.

Use a tri-state health contract. `PASS` requires that all required checks actually ran and passed. Any exception, unreadable ledger, or unavailable date basis must produce `UNKNOWN` or `DEGRADED`; never silently inherit empty “passed” collections.

Where a notice date is not available, use observed-new-row/fingerprint history and report `UNKNOWN` rather than substituting a future effective date.

### Acceptance tests

- A state whose newest effective date is in 2028 but whose source content has not changed for its cadence threshold becomes stale in 2026.
- A freshness exception cannot produce source status `ok` or text claiming every state is publishing.
- Missing/malformed baseline and source-state ledgers produce `unknown/degraded` and a nonzero operational alarm.
- A collector returning byte-identical stale content is detected even when parsing still returns many rows.
- The public health surface distinguishes “fetch succeeded,” “content changed,” and “new notices observed.”

### 50-state review boundary

The repository has substantial defenses: explicit state coverage, custom and generic scraper tiers, count floors, generic-drift checks, bulk-post rejection handling, and source-state reporting. Focused WARN/freshness tests passed in this checkout.

I did **not** live-query all state sites, so the current correctness of each individual parser is **UNKNOWN**. The systemic false-green paths above are confirmed from code and ledgers and should be fixed before a fresh 50-state endpoint certification. Once fixed, run a state matrix that records HTTP result, parse count, newest notice date, newest effective date, content fingerprint change, baseline comparison, and final tri-state verdict.

---

## Finding 4 — P1: Czech ARES writes an effective date into `published_date`

The talent schema and documentation distinguish source publication/registration date from event effective date. `collectors/czechia_ares.py` instead stores the office-change date as `published_date`, while ARES supplies a separate registration date. Its tests explicitly preserve this behavior.

The current DB includes a published ARES row saying an officer “left office ... on 2 September 2026” with:

- `published_date = 2026-09-02`
- `published_at = 2026-07-31`

The future effective date is legitimate evidence. Calling it the publication date is not. It can distort chronology, source freshness, newest-item ordering, and period summaries.

### Required correction

- Set `published_date` to the registry/filing/registration date.
- Set `effective_date` to the office-change date.
- Preserve the effective date in the headline and evidence.
- Migrate existing ARES rows through normal revisions.
- Add an invariant: a published row's `published_date` cannot be materially in the future; future `effective_date` is allowed.

---

## Finding 5 — P1: GDELT is no longer one query, but partial failure remains silent

### Correction to the premise

Current main does **not** run only one global DOC API query. `pull_gdelt_between()` now runs:

- one broad 36-hour query;
- four rotating segment queries by default;
- two rotating native-language queries;
- two rotating euphemism queries;
- one theme query; and
- one rotating European-language query.

That is up to eleven DOC API queries per live cycle, subject to environment settings.

### Is the 250-record cap binding?

**UNKNOWN for current production.**

The repository records historical saturation and comments explicitly say global mega-stories can push smaller items below `maxrecords=250`, but there is no production metric that records returned count, oldest returned timestamp, or cap saturation by query/window.

A live spot probe on 2026-08-20 did not settle it: two requests returned non-JSON responses and one returned HTTP 429. That supports the availability concern but does not measure saturation. Do not claim the current cap is or is not binding until telemetry exists.

### Is one global query the wrong shape?

**Yes as a sole discovery shape; current code already partially agrees.** A globally ranked top-250 stream optimizes for the largest stories and languages, not country recall. However, adding 150 country queries per run would likely worsen rate limiting. The right shape is bounded, deficit-weighted partitions with durable replay—not one mega-query and not an unbounded country fan-out.

### BigQuery caveat

Historical workflows prefer BigQuery when credentials are available, but live Railway credentials/configuration are **UNKNOWN**. The BigQuery implementation says it removes the DOC API cap, yet its SQL has `LIMIT 900` and no deterministic `ORDER BY`. At saturation, that is an arbitrary sample rather than a complete window.

Use deterministic ordering and partition/page until a window is demonstrably unsaturated. A hard `LIMIT 900` must be reported as a cap, not as cap removal.

---

## Finding 6 — P1: GDELT retries do not protect every query window

`QUERY_ATTEMPTS` defaults to five and honors 429 backoff. On exhaustion:

- The **broad** query raises (or tries BigQuery) and `cron.py` marks GDELT degraded. That failure is not silent at the source-health level.
- The rotating segment/native/euphemism/theme/language queries log their error and continue. Their loss is not reflected in source health and they have no persistent retry ledger.

The live cron asks for `now - 36h` on each run; that overlap is not a durable cursor. A failed run may be recovered by the next run, but after roughly three consecutive 12-hour failures the earliest hours can fall outside the next window. A failed rotating query is worse because that narrow query may not rotate back for days.

### Are whole days being lost to production 429s?

**UNKNOWN.** The code permits permanent loss, and the live probe encountered a 429, but private run logs/metrics were not inspected. The broad failure is visible; secondary-query loss is presently silent.

### Required correction

Create a small durable work ledger keyed by query family, query/partition, start, and end:

- queued → attempted → complete/partial/failed;
- retry failed windows across later runs;
- record expected query slots, successful slots, HTTP status, returned count, oldest/newest item, and whether the cap was reached;
- mark source health `partial/degraded` if any required slot fails;
- bisect saturated time windows (for example, 36h → two 18h windows → smaller as needed) until unsaturated or explicitly partial.

This adds reliability without adding model cost.

---

## Finding 7 — P1: country canonicalization splits and misclassifies countries

### Correction to the premise

`alt_normalize_country()` does create an ASCII comparison key, but on a miss it returns the original raw string. Therefore `Türkiye` does **not** become the stored literal `trkiye`; it remains `Türkiye`, while `Turkey` remains `Turkey`. The resulting defect is a split canonical identity.

A direct function probe produced:

| Input | Current result | Failure |
|---|---|---|
| Türkiye | Türkiye | Separate from Turkey |
| Turkey | Turkey | Separate from Türkiye |
| Côte d'Ivoire | Côte d'Ivoire | Separate from Ivory Coast |
| Ivory Coast | Ivory Coast | Separate from Côte d'Ivoire |
| Curaçao | Curaçao | Separate from Curacao |
| São Tomé and Príncipe | Multiple countries | Valid single country misclassified |
| Trinidad & Tobago | Multiple countries | Valid single country misclassified |
| Bosnia & Herzegovina | Multiple countries | Valid single country misclassified |
| Congo, Democratic Republic of the | Multiple countries | Valid single country misclassified |
| Micronesia, Federated States of | Multiple countries | Valid single country misclassified |

The causes are ASCII-only comparison, ampersand handling, and blanket comma/slash/`&`/`+`/“and” multi-country heuristics applied before a closed canonical lookup.

### Current published damage

**UNKNOWN.** The defect is confirmed, but the committed measurement did not establish that every bad variant currently has live rows. Treat it as a correctness exposure and run a migration inventory before changing totals.

### Required correction

- Use a closed ISO-3166-backed canonical table plus explicit historical/common aliases.
- Normalize Unicode (NFKD/transliteration) and punctuation before lookup.
- Resolve a complete canonical single-country name before applying multi-country separators.
- On a miss, return `UNKNOWN`/hold for review; do not publish arbitrary raw labels as a new country identity.
- Inventory and merge existing aliases through logged corrections.
- Generate tests over all ISO names plus known aliases, diacritics, comma-form official names, and ampersands.

---

## Finding 8 — P2: the international news path is structurally under-built

### Is it under-built outside the EU and US?

**Yes, structurally.** WARN and Eurofound are high-volume official registers. The remaining global path is a capped/rationed discovery sampler: GDELT partitions, Google News rotations, and a limited number of direct feeds. It cannot provide comparable recall for roughly 150 non-register countries without a stronger country-level discovery contract.

The supplied figures—85% of jobs from ERM/WARN, 182 countries configured, 72 with rows—were not independently reproduced from the current checkout, so those exact percentages/counts remain **UNKNOWN in this review**. They are consistent with the architecture, but should not be repeated publicly without a fresh generated measurement.

### Cheapest safe improvement

Do not begin with more LLM calls or 150 GDELT queries. In order:

1. Enforce the Google News domain gate before paid extraction; spend the saved budget on admissible candidates.
2. Add the durable GDELT query/window ledger and saturation metrics.
3. Prioritize by measured deficit: every country gets its first admissible candidate before a well-covered country gets its next one.
4. Add one vetted direct RSS/feed for each highest-value missing non-EU/US country, starting with countries that have high labor-market size and reliable national business press.
5. Apply deterministic headline and verbatim-headcount extraction first; use the model only for borderline classification.
6. Publish coverage tiers: official-register coverage, vetted-news coverage, and discovery-only/no-current-evidence. “Worldwide” must not imply uniform recall.
7. Maintain country-stratified held-out recall sets so improvement means measured recall, not just more rows.

---

## Finding 9 — P2: talent collectors can look `ok` while rationed

Running `ops_status.py` against the current committed talent DB returned exit 2 with 11 action items. The report included:

- worldwide recall: 37/169 = 21.9%;
- US recall: 22/51 = 43.1%;
- 77 of 132 worldwide misses described as “walked never read” because of budget;
- 30 misses attributed to feed depth/cadence and 16 to publishers not wired;
- Google News: 1,009 found, 59 stored, 160 budget-deferred, status `ok`;
- national press: 10,977 found, 53 stored, 129 budget-deferred, status `ok`;
- the autonomy tripwire stale by roughly 452 hours against a 168-hour limit;
- 1,260 promised archive URLs absent and only 58.1% of in-scope items archived;
- GDELT backfill stopped roughly 424 hours with no queue, plus stalled Google News backfills.

Some budget deferral is intentional, not a scraper failure. It should still be represented as `partial/rationed`, not `ok`, because `ok` currently conflates transport success with coverage success. A journalist-facing product needs both states.

The arithmetic guards all reported `ok`, demonstrating Finding 1's core problem: aggregate reconciliation is not semantic validation.

### Required correction

Give every collector separate statuses for:

- transport/parsing;
- admission/validation;
- budget processing completeness;
- backlog age;
- measured recall;
- publication reconciliation.

Only a deliberately defined conjunction should produce overall `healthy`. A green workflow with deferred candidates or an expired backfill must not imply complete discovery.

---

## Finding 10 — P2: a stale backfill ticket can rewind the cursor

`pipeline/backfill_slices.py` rereads current state before recording a result, but it tests only whether `next_cursor` differs from the current cursor. It does not prove monotonic progress.

A focused reproduction advanced a job from `2026-01-01` to `2026-01-05`, then recorded a stale ticket whose `next_cursor` was `2026-01-03`. The stale result was accepted with `advanced=True`, and the stored cursor moved backward to January 3.

The handover notes an unlanded cursor-index repair; current main still lacks it.

### Required correction

- Compare cursor ordinals using the job's unit semantics; accept only strictly forward progress.
- Make duplicate/replayed results idempotent no-ops.
- Reject and record stale tickets rather than mutating state.
- Add concurrent/out-of-order tests for day, quarter, page, and slice cursors.

This is primarily a cost/completeness defect, not a confirmed wrong-number defect.

---

## Finding 11 — P2: the talent cost contract has drifted

The current operational report showed approximately $2.41 over seven days and a $10.34 30-day projection against an $8 configured allowance. The README still describes roughly $0.60/month, while a workflow comment references $5/month.

The exact external bill is **UNKNOWN**; repository telemetry is not a provider invoice. The internal contract is nonetheless inconsistent.

Use one machine-readable monthly ceiling and generate workflow comments, status output, and public/operator documentation from it. Separate hard spend cap, expected spend, and recent projection. Budget exhaustion must degrade coverage status visibly rather than only suppress work.

---

## Direct answers to the five questions

### 1. Is the GDELT cap binding, and is one global query the wrong shape?

- **Cap binding now:** **UNKNOWN.** There is no saturation telemetry; the live spot check was inconclusive.
- **One global query:** wrong as the sole shape, but the premise is stale—current main adds up to ten secondary queries. Those additions are useful but not durably tracked.
- **Best next step:** instrument count/oldest-time/cap, durably replay windows, and bisect saturated time windows; use deficit-weighted partitions.

### 2. Are five attempts silently losing whole days to 429?

- **Actual production loss:** **UNKNOWN** without Actions/Railway history.
- **Possible by design:** yes. Broad-query exhaustion is surfaced as degraded, but secondary-query exhaustion is silently skipped. The rolling 36-hour overlap is not a durable cursor and can lose old hours after repeated failures.

### 3. What else does ASCII-stripping country normalization break?

It creates canonical splits for diacritics and aliases, and the later separator heuristic misclassifies valid single-country names containing `and`, `&`, or comma-form official names. Confirmed examples are listed in Finding 7.

### 4. Does Google News lack the claimed domain gate?

**Yes.** The current implementation does not enforce the shared trusted-domain standard before extraction/publication. This is a correctness boundary and disclosure mismatch.

### 5. Is the news path under-built for the other countries, and what is the cheapest fix?

**Yes, structurally.** Exact current 85%/182/72 metrics were not independently reproduced. The cheapest safe fix is admission gating plus a durable, measured, deficit-weighted discovery queue, followed by a small number of vetted direct feeds—not more indiscriminate paid extraction.

---

## Recommended implementation order for Claude

Keep the repairs small, separately deployable, and reversible.

### Phase 0 — stop wrong aggregates

1. Quarantine new ambiguous talent funding values.
2. Audit/revise published `funding_amount_usd` rows and recompute totals.
3. Fix ARES date semantics and add the future-publication invariant.

**Release gate:** no published funding amount lacks positive recipient/event evidence; live aggregate matches corrected DB; correction log explains the change.

### Phase 1 — close false-green paths

1. Make WARN freshness/baseline checks tri-state and fail closed to `unknown/degraded`.
2. Change WARN health to notice/fetch/content freshness, not effective-date horizon.
3. Enforce the shared Google News trusted-domain gate before extraction.
4. Make GDELT health partial if any planned query slot fails.

**Release gate:** injected exceptions, missing ledgers, stale unchanged content, and failed secondary queries cannot produce `healthy`.

### Phase 2 — prevent silent coverage loss

1. Add the GDELT durable query-window ledger, saturation metrics, and time-window bisection.
2. Expose budget-deferred/rationed collectors as partial.
3. Prevent backfill cursor rewind.
4. Canonicalize countries with a closed ISO/alias table and run a logged data migration.

**Release gate:** replay/recovery tests prove every failed window remains queued; no canonical country has multiple public identities.

### Phase 3 — improve worldwide recall within budget

1. Country-deficit scheduling and one vetted feed at a time.
2. Cheap deterministic prefilter/extraction before model calls.
3. Country-stratified recall evaluation and published coverage tiers.
4. One generated cost contract with hard ceiling, expectation, and projection.

**Release gate:** recall gains are measured on held-out country sets and stay within the chosen monthly cap.

---

## Verification performed

- Fresh public revisions pinned above.
- Focused layoff unit tests: **102 passed** across country/state classification, source freshness, generic WARN drift, and news goldset modules.
- Focused talent unit tests: **92 passed** across Czech ARES, capital-event classification, and published-figure guards.
- Direct PHP probes of `alt_normalize_country()` confirmed the country cases above.
- Direct SQLite queries confirmed the ten published funding rows and the $3.444B lower bound.
- A focused backfill-state reproduction confirmed cursor rewind.
- Talent `ops_status.py` was run against the current committed DB and returned exit 2.
- A live GDELT spot probe encountered malformed/non-JSON responses and an HTTP 429; it did not establish cap saturation.

The passing tests are evidence of a solid testing culture, but several currently encode the undesired behavior (ARES date semantics) or test arithmetic without semantic eligibility (funding guards). The next tests should assert the product claim, not only the current implementation.

## Explicit UNKNOWNs

- Whether the ten talent rows are still present in the live WordPress aggregate at the moment this is read.
- The exact corrected “Money raised” total after adjudicating all published rows.
- Current Railway GDELT environment variables and whether BigQuery credentials are available for live runs.
- Current GDELT saturation rate and exact number of windows/items lost to 429.
- Live correctness of each individual US state WARN parser.
- Freshly generated proof of the supplied 85% / 182-country / 72-country figures.
- Actual provider invoice cost versus repository-estimated spend.

These unknowns should become measured fields or release checks rather than assumptions.
