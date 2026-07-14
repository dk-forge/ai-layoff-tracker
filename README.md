# AI Layoff Tracker

Tracks verified AI-related and general layoffs from SEC 8-K filings and credible
news sources, and publishes them on `asktherecruiter.com` as a filterable table,
charts, a dedicated AI-displacement page, CSV/JSON exports, and an RSS feed.

**WordPress is the database** — there is no Supabase or external DB.

```
Railway Cron (2x daily)
  → Pull: SEC EDGAR 8-K full-text search + NewsAPI.org
  → DeepSeek-V3 via OpenRouter (deepseek/deepseek-chat): extract + classify + tag
  → Deduplication check (Railway pre-check + authoritative server-side re-check)
  → POST to WordPress REST API → Custom Post Type "layoffs"
  → WordPress displays: filterable table + charts + dedicated pages
```

## Repository layout

```
railway/                      Python pipeline deployed to Railway
  cron.py                     entry point (also runnable locally)
  sources/edgar.py            SEC EDGAR 8-K puller (gold verification)
  sources/newsapi.py          NewsAPI puller (bronze verification)
  extractor.py                DeepSeek-V3 (OpenRouter) extraction + classification
  deduplicator.py             pre-check against WP before posting
  wp_poster.py                POSTs entries to the WP REST API
  railway.toml                cron schedule (single service, "0 14,22 * * *" UTC)
wordpress-plugin/ai-layoff-tracker/
  ai-layoff-tracker.php       main plugin file (activation, assets, admin page)
  includes/cpt.php            "layoffs" CPT + meta fields
  includes/api.php            layoffs/v1 REST endpoints
  includes/shortcodes.php     all shortcodes
  includes/export.php         CSV + JSON downloads
  includes/rss.php            /feed/layoffs RSS feed
  assets/layoffs.css|js       DataTables + Chart.js front-end
  templates/                  markup rendered by the shortcodes
```

## Deployment

### 1. WordPress plugin

```bash
cd wordpress-plugin
zip -r ai-layoff-tracker.zip ai-layoff-tracker/
```

Upload via Bluehost cPanel File Manager to `/public_html/wp-content/plugins/`
(or wp-admin → Plugins → Add New → Upload), then **activate**.

Activation automatically:

- registers the `layoffs` custom post type and flushes rewrite rules
- registers the `/feed/layoffs` RSS feed
- **generates the pipeline API key** — no theme-editor code needed

### 2. Get the API key

wp-admin → **Tools → AI Layoff Tracker** shows the key (and a regenerate
button). Alternatively define `AI_LAYOFF_API_KEY` in `wp-config.php`; the
constant overrides the stored option.

### 3. Railway environment variables

Railway dashboard → Project → Variables (see `.env.example`):

```
OPENROUTER_API_KEY=   OpenRouter API key (extraction runs on DeepSeek-V3)
NEWSAPI_KEY=          NewsAPI.org key
WP_SITE_URL=https://asktherecruiter.com
WP_API_KEY=           ← paste from step 2
EDGAR_USER_AGENT=AiLayoffTracker contact@asktherecruiter.com
```

`EDGAR_USER_AGENT` is not optional — SEC rejects requests without a
descriptive User-Agent containing contact info.

### 4. Deploy Railway

```bash
cd railway/
railway up
```

`railway.toml` schedules one cron service at `0 14,22 * * *` UTC
(9 AM + 5 PM Eastern **during EST**; during daylight saving these fire at
10 AM / 6 PM local — switch to `0 13,21 * * *` if you prefer the reverse
trade-off).

### 5. Create WordPress pages

wp-admin → Pages → Add New:

| Page Title | Slug | Shortcodes |
|---|---|---|
| AI Layoff Tracker | `/ai-layoffs` | `[alt_stats_bar]` `[alt_tracker]` |
| Dashboard | `/ai-layoffs/dashboard` | `[alt_dashboard]` |
| AI Displacement | `/ai-layoffs/ai-tracker` | `[alt_stats_bar]` `[alt_ai_tracker]` |
| Data Export | `/ai-layoffs/data` | `[alt_export_buttons]` |

Per-company pages: `[alt_company_history company="amazon"]`.

### 6. Test the pipeline

```bash
cd railway/
OPENROUTER_API_KEY=... NEWSAPI_KEY=... WP_SITE_URL=... WP_API_KEY=... \
EDGAR_USER_AGENT="AiLayoffTracker you@example.com" python cron.py
```

Then verify:

- `GET https://asktherecruiter.com/wp-json/layoffs/v1/stats` returns counts
- `GET .../wp-json/layoffs/v1/all` returns the entries
- the `/ai-layoffs` page renders the table

## REST API

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/wp-json/layoffs/v1/add` | `X-Layoff-API-Key` header | Railway posts new entries (201 created, 409 duplicate) |
| GET | `/wp-json/layoffs/v1/check-duplicate?hash=` | `X-Layoff-API-Key` header | Dedup pre-check |
| GET | `/wp-json/layoffs/v1/all` | Public | Full dataset for journalists + the front-end |
| GET | `/wp-json/layoffs/v1/stats` | Public | Aggregates (cached 5 min) |
| GET | `/wp-json/layoffs/v1/company/{name}` | Public | Company history |

Auth fails **closed**: if no key is configured server-side, authenticated
routes return 503 rather than accepting empty keys.

## Verification levels & reason tags

- `gold` = SEC 8-K filing · `silver` = official press release · `bronze` = credible news outlet
- Reason tags (model-assigned from source text only): `ai_automation`,
  `possible_ai`, `revenue_decline`, `restructuring`, `merger_acquisition`,
  `offshoring`, `product_discontinuation`, `cost_reduction`, `macroeconomic`
- `ai_explicit` is true **only** when the source explicitly names
  AI/automation/robotics as a reason; `ai_language` stores the exact phrase.

## Deduplication

`dedup_hash = md5(lowercase(company_name) + layoff_date + job_count)`,
computed in `extractor.py`. Railway pre-checks `/check-duplicate` (fails open
by design — better a duplicate than a missed entry) and `/add` re-checks
server-side (fails closed with 409), so the pair is race-safe.

Known limitation: the same event reported with a *different* job count (e.g.
"about 9,000" vs "9,150", or a company revising a number) produces a different
hash and a second entry. Periodic manual review of near-duplicates in wp-admin
is recommended.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Every `/add` returns 403 | `WP_API_KEY` doesn't match wp-admin key — or the host strips the `X-Layoff-API-Key` header (some Apache/mod_security setups do). Test with `curl -H "X-Layoff-API-Key: ..."` directly against the site. |
| Every `/add` returns 503 | No key configured — reactivate the plugin or set `AI_LAYOFF_API_KEY` in wp-config.php. |
| EDGAR returns nothing | Missing/blank `EDGAR_USER_AGENT`, or genuinely no matching 8-Ks in the window. |
| NewsAPI returns nothing | Free tier delays articles ~24h; the puller looks back 2 days to compensate. 429 = daily quota exhausted. |
| Charts/table blank, "CDN blocked" | DataTables/Chart.js load from cdnjs; a CSP or ad-blocker can block them. Self-host the two libraries in `assets/` if needed. |
| `/feed/layoffs` is 404 | Rewrite rules stale — deactivate/reactivate the plugin or re-save Settings → Permalinks. |
| Cron ran but nothing posted | Check Railway logs: every skip/failure is logged with a reason (non-event, no job count, duplicate, HTTP status from WP). |

## Costs

- OpenRouter: ~100–200 extraction calls/day on deepseek/deepseek-chat — very small
- NewsAPI: free tier OK to start; $449/mo for real-time global coverage
- Railway: hobby plan is sufficient (two short cron runs/day)
