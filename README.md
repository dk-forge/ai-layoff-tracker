# AI Layoff Tracker

A continuously updated, source-linked tracker of verified layoffs worldwide —
flagging the ones companies explicitly attribute to AI. Every entry links to a
primary source: a SEC 8-K filing, a US state WARN notice, or a named news
outlet with the exact quote.

**Live:** https://asktherecruiter.com/blog/ai-layoff-tracker/
**API:** `https://asktherecruiter.com/blog/wp-json/layoffs/v1/` (public, no key needed for reads)
**Corrections:** https://asktherecruiter.com/blog/contact/ → info@asktherecruiter.com

Current scale: ~34,500 verified events · ~4.8M jobs · 42 US states (37 with
WARN coverage) · 22 countries · 2015→present, refreshed daily.

## Why another layoff tracker

Three kinds of trackers measure three different things. Government statistics
(BLS JOLTS) count every separation with no event detail. Announcement surveys
(the WSJ tracker and technology-sector trackers) count corporate *intentions* the day
they're announced. This tracker counts what has a **verifiable document or
quoted primary source behind it** — a documented floor, where every number is
clickable back to a filing or named outlet. Announcement-stage cuts are also
tracked, but as their own labeled tier ("Announced"), never mixed into the
verified totals. Full methodology, a worked example computed live from the
API, and links to every comparable tracker are on the live page.

**Editorial integrity is enforced in code:** corrections are applied through
audited workflows, corrected rows carry a public `edited: true` flag, removed
entries are hash-suppressed so daily re-imports cannot resurrect them, and
every correction to published figures is disclosed in the on-page corrections
log.

## Architecture

```
┌─ Railway cron (2×/day) ── SEC EDGAR 8-K search + NewsAPI + GDELT (worldwide,
│                           multilingual) → DeepSeek-V3 extraction via
│                           OpenRouter → dedup checks → POST /add
├─ GitHub Actions (daily) ─ WARN notices, all obtainable states: warn-scraper
│                           (Big Local News) + custom collectors for TX/FL/GA/
│                           OH/MI/CO/ID/LA → no LLM → POST /bulk (purge+reload)
└─ WordPress plugin ─────── custom indexed table wp_alt_layoffs (100K+ rows);
                            server-side /query /aggregate /facets; region tabs,
                            charts, exports; 5-min micro-cache + Cloudflare edge
```

WordPress is the database — there is no external DB. Rich entries also exist
as `layoffs` CPT posts for permalink pages; bulk WARN rows live only in the
table.

## Data quality and coverage

The tracker is source-linked, not a claim of complete worldwide coverage.
New model-extracted records carry an evidence quote, causal AI classification,
confidence and publication status; a claimed AI cause is rejected unless its
quote appears in the supplied source passage. `country` records job location
and `employer_country` records employer domicile when stated. The country
source registry, autonomous publication policy, reconciliation definition and
Claude handoff are in [docs/AUTONOMOUS_DATA_QUALITY.md](docs/AUTONOMOUS_DATA_QUALITY.md).

The U.S. AI-primary announcement metric is reconciled monthly against the
latest public announcement-survey report. It is a diagnostic for missing or duplicated
events, never a reason to force the tracker total to match a benchmark.

## Repository layout

```
wordpress-plugin/ai-layoff-tracker/   the site (deployed by FTPS on push to main)
  includes/db.php                     fast table + /query /aggregate /facets + keyed endpoints
  includes/api.php                    /add + normalizers (country/industry/state vocabularies)
  assets/layoffs.js                   entire front-end (no build step)
  templates/page-tracker.php          the tracker page incl. methodology + corrections log
railway/                              Python ingest
  cron.py                             news pipeline entry point (Railway, 2×/day)
  warn_import.py                      WARN pipeline entry point (GitHub Actions, daily)
  sources/                            edgar, newsapi, gdelt, warn, warn_custom (8 custom state collectors)
  extractor.py                        DeepSeek-V3 extraction + classification + guardrails
.github/workflows/                    deploy + all data jobs + editorial tools (trash/edit, audited)
docs/ARCHITECTURE.md                  system map: components, data flow, schema, filter semantics
docs/TECHLOG.md                       every change + every incident and its root cause
docs/RUNBOOK.md                       ops playbooks: deploy, caches, imports, "X broke → do Y"
```

## Public API

| Endpoint | Purpose |
|---|---|
| `GET /query` | Paginated rows. Filters: `years, quarters, months, industry, country, state, sources, reasons, stage, ai, company, keyword, q, from, to, min_jobs`; `sort`, `dir`, `page`, `per_page` |
| `GET /aggregate` | Filtered totals + monthly series + top industries/countries/states + reason breakdown + largest events |
| `GET /facets` | Distinct filter values + date range (for building UIs) |

Same filters power the CSV/JSON export buttons on the page. Data is free to
use with attribution to **asktherecruiter.com** (CC BY 4.0).

Write endpoints (`/add /bulk /edit /trash /cleanup /dedupe /bulk-purge
/migrate`) require the `X-Layoff-API-Key` header and fail closed; they are
called only from the audited GitHub workflows.

## Data guardrails (learned the hard way — details in docs/TECHLOG.md)

- Countries/industries normalize through fixed vocabularies; freeform LLM
  values are never trusted.
- Counts parse the FIRST number only (a fused "9,891 … (2 from RI)" once
  became 98,912); dates must be real calendar dates in 2015→today+18mo.
- WARN entries are exempt from fuzzy dedup (companies legally file several
  notices close together); news entries get exact-hash + same-company ±30d
  fuzzy guards + cross-outlet cluster collapse.
- State WARN feeds are not trusted blindly: Florida's official export
  contained staff *test rows* (a fake 78,788-worker notice); the collector
  skips them and the removal is suppression-listed.
- Data jobs FAIL LOUDLY: non-zero exit on any failed batch, `--fail-with-body`
  on maintenance curls.
- A daily data-quality workflow flags anomalies (≥5K-worker notices,
  multi-state same-company filings) and posts a daily numbers snapshot.

## Running your own

See `docs/RUNBOOK.md` for operations and `.env.example` for configuration.
Short version: install the WordPress plugin (activation creates the table and
API key), set the Railway/Actions env vars (`OPENROUTER_API_KEY`,
`NEWSAPI_KEY`, `WP_SITE_URL`, `WP_API_KEY`, `EDGAR_USER_AGENT` — the SEC
requires a descriptive User-Agent with contact info), and the crons do the
rest. Steady-state cost is a few dollars a month: the data sources (EDGAR,
WARN, GDELT) are free; only news extraction touches a paid LLM
(deepseek/deepseek-chat, ~100–200 calls/day).

## License

Code: [MIT](LICENSE). Data published by the live tracker: CC BY 4.0 with
attribution to asktherecruiter.com.
