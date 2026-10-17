# Coverage & Quality Roadmap

Distilled from a multi-agent research pass (2026-07-22). Actionable specs for
extending the tracker toward survey-class quality, adding federal-workforce
coverage, and building a historical (1995 to present) by-state view. Competitor
names are deliberately absent per the house rule; keep them out of the repo.

## 1. Federal-workforce RIF source (OPM EHRI) — build DORMANT

**Why:** 2025-26 US federal RIFs are a major story we don't track as a dedicated
source. OPM's EHRI "Federal Workforce Data" is an authoritative, keyless, open
API with an explicit RIF code. It's a WARN-class structured source (no AI
language): skip the LLM, bulk-upsert like `warn_import.py`.

- **API:** `https://data.opm.gov/api/v1/files/separations` (keyless). Metadata is
  JSON; file bodies are **Parquet** (needs `pyarrow`/`pandas` — verify
  `railway/requirements.txt`). Params: `current=true`, `month`, `year`.
- **Filter:** rows where separation-type == `SH` (RIF) OR nature-of-action code
  == `356`. Group by `(agency, YYYYMM[, duty_station_state])` -> COUNT(*).
- **Entry dict** (mirror `sources/warn.py` 294-327): `source_type='federal_rif'`,
  `company_name=<agency display name>`, `job_count=<group count>`,
  `layoff_date="{yyyy}-{mm}-01"`, `country='United States'`,
  `industry='Government'`, `ai_explicit=False`, `verification_level='warn'`,
  `reason_tags=['government','rif']`,
  `source_url='https://data.opm.gov/explore-data/analytics/workforce-changes'`.
- **Dedup hash EXCLUDES job_count** (unlike WARN): `md5(f"fedrif{agency}{yyyymm}{state or 'US'}")`.
  OPM revises months (v1->v2->v3); a count-excluding hash upserts the revision in
  place. (Verify the `/bulk` upsert overwrites job_count on hash match.)
- **Attribution:** agency = company; national-only rows for v1 (per-state opt-in
  `FEDERAL_RIF_BY_STATE=1` later — never emit both national AND per-state for one
  RIF). `ai_explicit=False` so RIFs never inflate the AI count.
- **Gating (dormant):** `FEDERAL_RIF_ENABLED=1` to activate; `FEDERAL_RIF_DRY=1`
  dry-run. Runner `railway/federal_rif_import.py` clones `warn_import.py`
  (`post_bulk`, loud-fail, non-zero exit). Workflow `federal-rif-import.yml`
  monthly (`0 14 5 * *`) + dispatch.
- **Registry parity (same session):** `ops_status.py` `MAX_AGE['federal_rif']=35`
  (monthly); `assets/health.js` meta label; Sources page row; `bm-live.html`.

**Cross-check ONLY (never ingest):** CNN federal-firings tracker, GovExec RIF
Watch, Wikipedia 2025 federal mass layoffs (also a seed list), WSJ tracker,
Partnership for Public Service "Federal Harms Tracker" (downstream of OPM).

## 2. Survey-parity roadmap (ranked by impact/effort)

The incumbent survey = a monthly US job-cut ANNOUNCEMENT report; quality = rich REASON
(~15 categories) + ~28-sector INDUSTRY dimensions + YTD/YoY + a HIRING
counterpart. Our model already matches its announcement basis (we're faster:
continuous vs monthly). Gaps:

1. **Reason vocab expansion (High impact / Low effort).** Add to
   `extractor.ALLOWED_REASON_TAGS` + `classify_reason_tags` + the WP reason facet
   + keep Python<->PHP parity (`test_reason_backfill_guards`): `bankruptcy`
   (evidence-hardened via the dormant `distress_watchlist.py`), `contract_loss`,
   `tariffs`, `demand_downturn`, `government`/`doge`, `seasonal`. Run
   `reason_backfill.py` over history.
2. **Monthly report object (Med/Low-Med).** Add `/reports/monthly` cloning the
   `/reports/quarterly` immutable-snapshot machinery; surface YTD + YoY from
   `/aggregate`. Makes us survey-*quotable*.
3. **Hiring / job-creation series (High/Med).** (a) BLS JOLTS "Hires" via the
   free `api.bls.gov/publicAPI/v2` (public domain); (b) capture "plans to hire N"
   news via the existing pipeline with a `record_type=hiring` flag (dormant +
   dry-run). Biggest net-new differentiator.
4. **Industry taxonomy 19 -> ~28 (Med/Low).** Extend `alt_industry_rules()`
   (order-sensitive) + `industry_backfill.py`; add **Warehousing**, Apparel,
   Chemical, Construction, Utility, Legal. Re-run backfill.
5. **Government cut signal (High/Med).** USAspending.gov API (contract
   terminations -> `contract_loss`), OPM RIF (item 1), agency press releases.
6. **Broaden the announcement net (Med/Med).** Activate `supplemental_news.py`,
   expand `company_watchlist.py` `WATCHLIST_INDEX_URLS`, add trade-press RSS.
7. **WARN reason/industry cross-enrich (Med/Med).** When a WARN row matches a
   news/SEC record carrying reason/industry, propagate with provenance (never
   infer from HQ).

## 3. Historical "layoffs by state over time (1995 to 2026)" view

**Honest floor is ~1995, not 1988** (WARN Act took effect Feb 1989; no digital
notices pre-~1995). Eras use DIFFERENT units, so the view LAYERS/TOGGLES series,
never merges them.

| Dataset | Years | Unit | Format | License |
|---|---|---|---|---|
| Cleveland Fed openICPSR #155161 (Advance Layoff Notice Data from WARN) | ~1995->present | affected workers, state-month | CSV | free acct + DUA, attribute Cleveland Fed |
| BLS Mass Layoff Statistics (MLS) | Apr 1995 - May 2013 | mass-layoff events / claimants, state+NAICS | LABSTAT / BLS API | public domain |
| State WARN archives (our live scrapers) | ~2000/2002->present | per-notice | HTML/PDF/XLSX | public records |

**Build:** `railway/sources/historical_warn.py` (openICPSR CSV -> `/bulk`, tier
`warn`, provenance `historical_backfill=1`; WARN is dedup-exempt so no collision;
fail loud). `railway/sources/bls_mls.py` -> a NEW aggregate-only table
`wp_alt_historical_series` (MLS is pre-aggregated, not events). Endpoint: add
`group_by=state,year` + `basis` (`warn_affected` | `mls_events`) to `/aggregate`.
Front-end: choropleth mode + year slider + WARN/MLS layer toggle (d3 + US atlas
already loaded). Verify openICPSR reuse terms before shipping; cite Cleveland Fed
+ BLS.

## 4. Labour data roadmap: early-warning view + next free sources (owner ask 2026-10-05)

Moved here from GitHub issue #478 on 2026-10-17 (GitHub holds live work only;
plans live in the repo). The issue text is preserved in full, then the status
as of the move. Agent work throughout; no owner action is needed.

**Owner ask (2026-10-05):** more free labour sources to power stories. Build
order (after FRED + QWI land):

1. Indeed Hiring Lab postings into ALT, plus an early-warning view per
   industry/state: postings, WARN notices, FRED weekly claims and QWI
   separations on one timeline. Label it cooling/stable/heating from the
   official numbers only, with no claim that AI caused it.
2. BLS OEWS (occupation employment + wages by metro): which occupations AI
   exposure studies flag, and how big they are locally.
3. O*NET task data + published AI-exposure scores (e.g. Eloundou et al. 2023,
   open): an exposure score per occupation, joined to OEWS.
4. BLS Employment Projections (10-yr growth by occupation): "growing vs
   shrinking" next to exposure.
5. Census Business Formation Statistics: new-business applications (where
   laid-off workers go).
6. DOL unemployment insurance claims by state (weekly, ETA 539): a state-level
   early warning.
7. Eurostat job vacancies + LFS: EU depth beyond OECD.
8. SEC 8-K Item 2.05 (restructuring costs) via EDGAR full-text search:
   company-level layoff disclosures with $ amounts.
9. BLS CES hours + earnings by industry: hours cut before headcount.

Narrative templates: "postings fell X% before layoffs in <industry>",
"most-exposed occupations in <metro>", "who gets hired back (QWI by age/sex)",
"restructuring charges this quarter".

**Standing requirement (owner, 2026-10-05):** every source in this plan ships
with (a) a row on the public Sources page (name, publisher, coverage, update
frequency, licence/attribution, link) and (b) an entry in the source register
doc, in the same PR, plus a render test that the row is present.

**Status at the move (2026-10-17, from the code on main and TECHLOG):**

| # | Item | State | Where |
|---|---|---|---|
| 1 | Indeed Hiring Lab postings | shipped 2.20.254, live 2026-10-14 | `railway/indeed_import.py`, `/reference/indeed_postings`, `indeed-import.yml` |
| 1 | Early-warning view (claims + QWI, labels from official numbers) | shipped 2.20.227 | `includes/early-warning.php` |
| 1 | **Postings on the early-warning timeline** | OPEN: needs a sector to industry map | `includes/early-warning.php` reads no postings yet |
| 2 | BLS OEWS | shipped 2.20.229 | `railway/ai_exposure_import.py`, `includes/ai-exposure.php` |
| 3 | O*NET + published AI-exposure scores joined to OEWS | shipped 2.20.229 | same |
| 4 | BLS Employment Projections | shipped 2.20.229 | same |
| 5 | Census Business Formation Statistics | shipped 2.20.262 (rollup of 2.20.259) | `railway/bfs_import.py`, `bfs-import.yml` |
| 6 | State weekly UI claims | PARTIAL: all 50 states + DC via FRED (`railway/claims_import.py`); **nothing reads DOL ETA 539 directly** | OPEN |
| 7 | Eurostat job vacancies + unemployment | shipped 2.20.262 (rollup of 2.20.260) | `railway/eurostat_import.py`, `eurostat-import.yml` |
| 8 | SEC 8-K Item 2.05 restructuring $ amounts as a dataset | OPEN: 8-K filings are a layoff source, the $ series is not built | TECHLOG 2026-08-01 holds the recall analysis |
| 9 | BLS CES hours + earnings | shipped 2.20.262 (rollup of 2.20.261) | `railway/ces_import.py` |

Open work, in order: postings on the early-warning timeline (item 1, sector to
industry map); ETA 539 read directly (item 6); 8-K Item 2.05 restructuring
charges as a series (item 8). Each is a collector, a plugin endpoint, a
Sources-page row, a register entry and a render test, per the standing
requirement.

## Priority order
Highest-ROI, safest first: reason-vocab (2.1) and industry taxonomy (2.4) are
cheap vocab bumps; federal RIF dormant scaffold (1) is high-value and low-risk
(posts nothing until flipped); monthly report (2.2) makes us quotable; hiring
series (2.3) and historical view (3) are the big differentiators.
