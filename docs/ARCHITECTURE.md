# Architecture

```
                         ┌────────────────────────────────────────────────┐
  SOURCES                │  INGEST (railway/ — Python, GitHub Actions)    │
  ────────               │                                                │
  SEC EDGAR 8-K/6-K ────►│ cron.py (Railway cron 12:00 & 22:00 UTC)       │
  NewsAPI ──────────────►│   EDGAR + NewsAPI + GDELT(36h worldwide)       │
  GDELT (worldwide press)│   → extractor.py (DeepSeek-V3 via OpenRouter)  │──POST /add──┐
  Company IR/newsroom RSS│   → evidence quote + causal AI class           │             │
                         │                                                │             │
  State WARN sites ─────►│ warn_import.py (GH cron daily 15:00 UTC)       │──POST /bulk─┤
  (~25 states via        │   warn-scraper → keyword column parsing        │             │
   warn-scraper)         │   NO LLM — filings are already structured      │             │
                         └────────────────────────────────────────────────┘             │
                                                                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────────┐
  │  WORDPRESS PLUGIN (Bluehost, install at /blog; Cloudflare in front)                  │
  │                                                                                      │
  │  wp_alt_layoffs (custom indexed table — THE query surface, holds everything)         │
  │  layoffs CPT posts (rich entries only: SEC/news/curated → permalink pages)           │
  │      └── mirrored into the table on save (alt_db_sync_post)                          │
  │                                                                                      │
  │  REST layoffs/v1:                                                                    │
  │   PUBLIC  /query /aggregate /facets /reconciliation /source-health(GET) /source-runs /integrity-status /quality-status /review-queue /announcement-lifecycle-candidates /reports/quarterly /benchmarks/* ← 5-min micro-cache (transients, alt_data_ver) │
  │   PUBLIC  /all /stats /company/{name} (legacy, CPT-backed) · /claims (jobless-claims backdrop, macro context) │
  │   KEYED   /add /check-duplicate /dedupe /migrate /bulk /bulk-purge /cleanup /source-health(POST) /alert(emails owner on breakage) │
  │           /reclassify /enrich-context /enrich-roles /source-health /event-migrate /reconcile-supersets(dedup) /claims-ingest /trash │
  │   PUBLIC /event/{layoff-row-id}/sources (all retained reports for one event)          │
  │           (header: X-Layoff-API-Key; key: wp-admin → Tools → AI Layoff Tracker)      │
  │                                                                                      │
  │  Front-end (assets/layoffs.js): DataTables serverSide → /query; charts+stats →       │
  │  /aggregate; dropdowns → /facets. All filters are multi-select; chart bars toggle    │
  │  filters; chips are color-coded per dimension.                                       │
  └──────────────────────────────────────────────────────────────────────────────────────┘
```

## Repo layout
```
wordpress-plugin/ai-layoff-tracker/
  ai-layoff-tracker.php      plugin bootstrap: version, enqueues, SEO JSON-LD, deploy hooks
  includes/db.php            fast table, /query /aggregate /facets /bulk /bulk-purge /cleanup /migrate, micro-cache
  includes/api.php           /add /dedupe /stats /all + normalizers (country/industry/state) + dedup guards
  includes/cpt.php           CPT + allowed source/verification tiers (gold|warn|silver|bronze)
  includes/contact.php       /contact page auto-creation + form handler (mails info@) + spam defenses
  includes/company-directory.php reviewed canonical-company route; source-linked pages only
  includes/export.php        CSV/JSON streaming exports (full table, chunked)
  includes/shortcodes.php    [alt_tracker] [alt_stats_bar] [alt_dashboard] [alt_contact] ...
  templates/page-tracker.php the main page markup (stats → filters → charts → table)
  assets/layoffs.js|css      the entire front-end
railway/
  cron.py                    2×daily ingest (EDGAR + Google News + NewsAPI + GDELT 36h) + source health; fails loud if a cycle posts 0 with failures
  sources/google_news.py     FREE keyless layoff-headline discovery (Google News RSS) — leads the news sweep (NewsAPI is effectively dead)
  sources/claims.py          Keyless FRED puller (national ICSA/CCSA + 50 states) for the /claims macro backdrop; claims_import.py POSTs it daily
  extractor.py               DeepSeek prompt + post-processing; source-quote guard and AI causal taxonomy
  source_registry.py         Market status, discovery vocabulary and explicit live-vs-candidate source coverage
  sources/press_releases.py  Opt-in official company IR/newsroom RSS/Atom collector
  survey_reconcile.py        Monthly like-for-like US AI-announcement benchmark check
  reclassify_legacy_ai.py    Daily bounded source-evidence reassessment of legacy AI flags
  reason_backfill.py         Daily bounded reason-tag backfill from STORED excerpts (fixed vocabulary; WARN excluded)
  enrich_roles.py            Daily bounded role-category extraction from ALREADY-STORED row text (no fetches)
  canonical_event_migrate.py Resumable legacy event/source-report migration (no LLM)
  historical-news-sweep.yml  Daily rotating 14-day historical GDELT recovery window
  announcement-lifecycle-review.yml Daily read-only exact-match lifecycle lead summary
  sources/{edgar,gdelt,newsapi,warn,companies_house}.py
  warn_import.py             nationwide WARN → /bulk (batches of 1000; WARN_PURGE for clean reload); drift tripwires for new + legacy custom scrapers
  company_watchlist.py       Daily targeted sweep of big employers with no current-year entry (news → extractor → poster); auto-grows via WATCHLIST_INDEX_URLS
  supplemental_news.py       DORMANT: NewsData.io + Marketaux + Finnhub non-English/EU news (per-key)
  distress_watchlist.py      DORMANT: CourtListener bankruptcy + Companies House insolvency → watchlist news search (per-key)
  foreign_filings_ingest.py  DORMANT: EDINET JP + OpenDART KR filing bodies → extractor (guards reject non-layoffs)
  recall_precision.py        Weekly recall (gold set) + count precision + AI-attribution precision (quote-rate)
  health_digest.py           Weekly autonomy tripwire: reads health ledger, emails owner via /alert on STALE/degraded source
  sources/{edinet,opendart,cvm_br,layoff_language}.py   JP/KR/BR filing clients + JP/KR layoff vocabulary
  backfill.py gdelt_backfill.py news_catchup.py seed_ai.py   one-off runners
.github/workflows/           see RUNBOOK for the full table
docs/                        this documentation
```

`docs/OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md` is the evidence-backed admission
log for proposed country-specific sources. It is intentionally separate from
the live-source registry: publicly searchable does not automatically mean
automatable or licensed for reuse.

## Data semantics (the parts that bite)
- **Verification tiers:** `gold`=SEC EDGAR 8-K/6-K, `warn`=state WARN notice, `silver`=press release/Eurofound ERM, `bronze`=news.
- **Market registry:** a named official system is a *candidate* until it has a stable public interface, a tested connector and source-health reporting. Only `live_sources` are coverage claims; all other countries remain discovery-only.
- **Dedup:** exact = md5(company+date+count). Fuzzy = same normalized company within ±30 days blocks
  a second *news* entry. The daily deep scan rotates through all bounded candidate clusters (with exact-count
  repeats prioritized), and merges confirmed reports into one canonical event while retaining every source link.
  **WARN is exempt from fuzzy + cluster dedup** — its hash also includes city+state.
- **Superset dedup** (`alt_reconcile_supersets`, `superset_of` column, daily `reconcile-supersets.yml`): the fuzzy
  ±30-day rule misses cross-channel + far-apart duplicates, which double-count job TOTALS. Three passes mark the
  smaller side of an overlap as a subset of the same event's primary row: (1) a company-wide news/announced total
  sitting on top of its own site-level WARN rows; (2) news-vs-news with the EXACT same count within ~150 days (an
  announcement + later coverage — e.g. Coinbase 700 twice); (3) within-WARN same-state exact-count (≥100) refiled
  revisions (Tyson 1,761 Amarillo). Aggregate job SUMs use `superset_of = 0` (headline/bars/monthly), so an event
  counts ONCE; the row LIST still shows every member (no lost site detail). Self-maintaining (daily), reversible
  (unmark). Live guard: `railway/tests/test_dedup_live.py`.
- **Countries:** canonical "United States"/"United Kingdom"; regions & multi-country phrases
  ("Global", "Europe", "India and US") → **"Multiple countries"** (splitting would double-count).
  Real "and"-countries (Trinidad and Tobago…) are whitelisted first.
- **Industries:** fixed ~19-value taxonomy via keyword rules; order matters (biotech/fintech/edtech
  must match before the bare 'tech' keyword); keywords ≤4 chars match on word boundaries only.
- **Counts:** first number in the field ("9,891 Remote Workers (2 from RI)" → 9,891; "60-80" → 60);
  any single notice >100,000 rejected as a parse error.
- **Dates:** valid window 2015-01-01 → today+18 months (WARN files up to ~a year ahead). Future
  effective dates get an "upcoming" tag in the UI. `/cleanup` NULLs implausible dates.
- **WARN quirks:** filings carry NO industry/reason (industry charts reflect SEC/news entries);
  remote/multi-state employers file in several states with overlapping counts (shown as-filed,
  disclosed in methodology; the weekly data-quality report flags them).
- **AI attribution:** AI-primary, contributing, operational/selection, context-only, explicit-denial and
  unknown are distinct classifications. A primary/contributing classification is accepted only when the
  claimed exact quote exists in the supplied source passage. `country` is job location; `employer_country`
  is employer domicile/HQ when stated.
- **Metadata and citation completeness:** `/integrity-status` discloses blank industry rows, blank US affected-job
  state rows, and canonical events without a linked retained-source report. These are measurable enrichment backlogs,
  not permission to infer values: WARN notices often
  omit industry, and a national announcement remains state-unspecified unless a source identifies affected
  job locations. Employer HQ/domicile and office footprint must never be used as job-state substitutes.
- **Announcement-survey comparison:** the on-page country filter is job location, not employer domicile. The monthly
  strict comparator uses US employer domicile + announcement stage + AI-primary + canonical events. A separate
  visible US-job-location/any-AI figure is diagnostic only and is never represented as survey-comparable.
- **Announcement lifecycle candidates:** a read-only queue can surface an exact-count, same-company,
  same-job-location-country announcement followed within 365 days by a later non-announced record. It is
  deliberately an editorial lead, never an auto-merge rule; confirmation uses retained sources and the
  existing keyed source-preserving merge path.
- **Quarterly reports:** `POST /reports/quarterly` accepts only a calendar-quarter id and computes immutable
  source-scoped snapshots through the same aggregate query path used by the tracker. It never accepts client
  totals or model-written findings. The public report retains its query parameters, source health, integrity
  and dataset revision; the HTML page discloses when live data have since changed.
- **Link precision:** most states publish one list page, not per-notice URLs. UI labels list-page
  links "(list)"; exact per-notice links (VT etc.) display plain.
- **Company directory:** `/company-layoffs/{slug}/` resolves only through a reviewed identity registry.
  Raw `company_key` is a dedup aid, not a legal-entity assertion. Directory rows require canonical events
  with retained source URLs; low-value reviewed records are noindex and unknown/pending keys are 404.

## Filter model (front-end ⇄ API)
Multi-select params, comma-joined: `years, quarters, months, industry, country, state, sources,
reasons` (+ `from,to,q,company,keyword,min_jobs,ai`). Dimensions AND together; values within a
dimension OR. Slicer charts call /aggregate ignoring their own dimension (`except`) so you can
always see what to pivot to. `alt_data_ver` (wp option) salts the micro-cache; every write bumps it.

### The param list above is exact, and getting it wrong FAILS SILENTLY (two ways)
Note the naming is not internally consistent — `years/quarters/months/sources/reasons/roles` are
plural while `industry/country/state/employer_country` are singular, even though every one of them
accepts a comma-joined list. So the plural of a singular one is a natural guess, and it is wrong.
There is no `args` schema on the public routes, so WordPress accepts unknown params without
complaint. Measured against production 2026-07-30, `/query` total on an unfiltered call = **63,671**:

| Request | total | What happened |
|---|---|---|
| `?state=NV` | 15 | correct |
| `?states=NV` | **63,671** | param name not recognised → filter dropped, **everything** returned |
| `?industries=Technology` | **63,671** | same (`?industry=Technology` → 3,993) |
| `?countries=US` | **63,671** | same |
| `?state=nv` | 15 | values are case-insensitive |
| `?state=Nevada` | **0** | value shape wrong (2-letter codes only) → **nothing** returned |
| `?country=US` / `?country=USA` | **0** | same (`?country=United States` → 43,378; full names, not ISO codes) |

Both failure modes are dangerous in opposite directions and neither raises: **a bad param NAME
over-reports** (you get the whole corpus and may read it as one state's), **a bad param VALUE
under-reports** (0 rows reads as "no layoffs there"). This has already bitten once — TECHLOG records
a press-page evidence-ladder deep link built on `ai_primary=1`, a param the front-end ignores, so the
link advertised a filtered view and served an unfiltered one.

**Decision (2026-07-30): the plurals are NOT accepted as aliases.** Aliasing `states/countries/
industries` would fix the one guess someone happened to report while leaving the `state=Nevada` → 0
case and every other typo just as silent, and it would permanently carry two public names for one
filter — against the project's "normalise through fixed vocabularies, nothing freeform" rule. The
fix that actually closes the class is for `/query` and `/aggregate` to echo what they applied (an
additive `applied_filters` key, plus the received-but-unrecognised names), so a caller can see the
filter was dropped instead of trusting a number. That is not built yet; until it is, this table is
the contract. `tests/test_filter_param_contract.py` pins it to the code.

## Caching layers
Request chain for `/blog/*` (observed 2026-07-19): **Cloudflare → Railway root app (reverse-proxies
/blog) → Bluehost Apache** (`x-railway-*` headers + base64 `host-header: shared.bluehost.com` on
/blog responses; origin reachable directly via the Bluehost IP that `mail.asktherecruiter.com`
resolves to, with `curl --resolve`).

1. Page HTML: WP-Super-Cache (+ Autoptimize) — flushed automatically on version bump.
2. API JSON: 5-min transients keyed by params+alt_data_ver; `alt_api_cached` sends
   `Cache-Control: public, max-age=300, s-maxage=300, stale-while-revalidate=600`
   (the `nocache_headers` filter swap uses `max-age=60`).
3. Cloudflare: Cache Rule (added 2026-07-15 by owner) edge-caches `/blog/wp-json/layoffs/v1/*` GETs.
   ⚠ Ensure the rule's Browser TTL = "Respect origin" (a 5-day browser TTL was observed initially).
   HEAD requests are never edge-cached (`cf-cache-status: DYNAMIC` is normal on HEAD; verify with GET).
4. Browser: works only because `includes/htaccess.php` maintains a mod_headers block in the WP root
   `.htaccess` that strips the duplicate `no-cache, no-store` Cache-Control (+Pragma+Expires) that
   Bluehost's Apache appends to every PHP response after PHP's own headers (v2.19.16; see TECHLOG).
