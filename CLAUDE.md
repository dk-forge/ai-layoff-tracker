# AI Layoff Tracker — orientation for Claude Code

Live tracker of verified layoffs (SEC 8-K filings, US state WARN notices, worldwide
news via GDELT), flagging the ones companies explicitly attribute to AI.

- **Live site:** https://asktherecruiter.com/blog/ai-layoff-tracker/
- **Contact page (corrections):** https://asktherecruiter.com/blog/contact/ → mails info@asktherecruiter.com
- **Public API base:** `https://asktherecruiter.com/blog/wp-json/layoffs/v1/`

## Read these before changing anything
| Doc | What it holds |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System map: components, data flow, endpoints, DB schema, filter semantics |
| [docs/TECHLOG.md](docs/TECHLOG.md) | Chronological log of every change + every incident and its root cause |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Ops playbooks: deploy, caches, imports, "X is broken → do Y" |

## The 60-second mental model
1. **`wordpress-plugin/ai-layoff-tracker/`** — a WP plugin on Bluehost (install lives at `/blog`).
   Front-end is fully server-side: the browser calls `/query` (table), `/aggregate` (charts+stats),
   `/facets` (dropdowns). Data lives in a custom indexed table `wp_alt_layoffs` (scales to 100K+ rows);
   rich entries also exist as `layoffs` CPT posts for permalink pages.
2. **`railway/`** — Python ingest. Cron 2×/day (EDGAR + NewsAPI + GDELT worldwide) → DeepSeek-V3
   extraction via OpenRouter → POST `/add`. WARN notices skip the LLM: `warn_import.py` scrapes
   states via `warn-scraper` and bulk-upserts via `/bulk` (daily 11AM ET GitHub cron).
3. **`.github/workflows/`** — deploy (FTPS on push to main) + all data jobs (see RUNBOOK).
4. **Self-running loop:** every source (news, WARN, SEC, ERM, + dormant ones — supplemental
   news, distress/bankruptcy, foreign filings) funnels into the SAME `extract_layoff_data`
   → `post_to_wordpress` pipeline, so all guards apply once. `report_source_health(...)`
   feeds a ledger; the weekly **`health_digest.py`** emails info@asktherecruiter.com (via the
   keyed `/alert` endpoint) when a scraper breaks, with a **paste-ready fix instruction**.
   So the human loop is: get email → paste one line here → fix the one scraper. Full
   "add a source / tune it / fix a breakage" guide is in **docs/RUNBOOK.md**.

## Iron rules learned the hard way (details in TECHLOG)
- Every network request to the WP host MUST send a browser-ish `User-Agent` (ModSecurity blocks `python-requests`; use `AiLayoffTracker/1.0 (+https://asktherecruiter.com)`).
- `WP_SITE_URL` is `https://asktherecruiter.com/blog` — never the bare domain (root is a separate Railway app).
- FTP deploys bypass WP hooks: version bumps trigger cache-flush/table-migration on first request (`alt_flush_caches_on_deploy`), and anything that must exist (like the contact page) needs a **retry-until-verified** hook, not a one-shot on version bump (deploys race mid-upload).
- Never trust freeform extracted values: countries/industries normalize through fixed vocabularies (`alt_normalize_country`/`alt_normalize_industry`); counts parse the FIRST number only; dates outside 2015→today+18mo are rejected.
- WARN entries are EXEMPT from fuzzy/cross-outlet dedup (companies legally file several notices close together).
- Changing an entry's job count changes its dedup hash → corrections need `/bulk-purge` + full re-import, not plain upsert.
- Data-changing jobs must FAIL LOUDLY (non-zero exit on any failed batch; `curl --fail-with-body` in workflows).
- Bump the plugin `Version:` + `ALT_VERSION` on EVERY deploy — it cache-busts assets and triggers the flush.
- **Never write a row directly.** A new source builds a raw dict and calls `extract_layoff_data` → `post_to_wordpress`. The raw dict MUST set `raw_text` (the extractor reads ONLY that and returns None if empty — the bug that made supplemental news silently post zero). Mirror `sources/newsapi.py`. Ship key-gated sources DORMANT with dry-run diagnostics. See RUNBOOK "add a new source".
- **Competitor data stays private** (standalone brand): never put Challenger/layoffs.fyi/TrueUp names or numbers in the repo or GitHub logs. Benchmark refresh (`gen.py`/`bm-live.html`) runs LOCAL only; competitor URLs go in the `COMPETITOR_FEED_URLS` secret.
- **Country filter**: `country_basis=any` (table/exports) unions job-location OR employer-HQ so US-HQ global cuts show under a US filter; headline stats stay strict job-location. Don't "fix" the discrepancy — it's intentional and documented.
- **Don't claim "100% automated."** It's ~99%; the honest sliver is scraper repairs (auto-detected + emailed), private-benchmark refresh, and novel-source judgment.

## Verify a change is actually live
```bash
curl -s "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate?cb=$RANDOM" | python3 -m json.tool | head
curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head -3
```
