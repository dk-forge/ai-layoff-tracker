# Runbook — operations & troubleshooting

## Deploy
Push to `main` → `.github/workflows/deploy-plugin.yml` FTPS-uploads
`wordpress-plugin/ai-layoff-tracker/` to the Bluehost install at `/blog`.
**Always bump `Version:` AND `ALT_VERSION`** in `ai-layoff-tracker.php` — that
cache-busts assets and fires `alt_flush_caches_on_deploy` (page-cache flush +
DB-table dbDelta) on the first PHP request. To trip it immediately:
```bash
curl -s "https://asktherecruiter.com/blog/?bump=$RANDOM" -o /dev/null
```
Rollback = `git revert` + push (there is no other rollback path; FTP is the only door).

## GitHub workflows (Actions tab)
| Workflow | Trigger | Purpose / inputs |
|---|---|---|
| deploy-plugin | push to main | FTPS deploy of the plugin |
| warn-import | daily 15:00 UTC + manual | WARN sweep. Inputs: states (`all` or `CA,NY`), min_employees, start, limit, **purge** (needs states=all, refuses if scrape <5K) |
| gdelt-backfill | manual | Worldwide news for a date range (costs OpenRouter credits) |
| backfill | manual | EDGAR 8-K historical range |
| news-catchup / seed-ai | manual | Recent-news top-up / curated seed |
| dedupe | manual | Collapse cross-outlet duplicate clusters (WARN exempt) |
| cleanup | manual | Re-normalize country/industry + NULL implausible dates across table+posts |
| migrate | manual | Re-mirror all CPT posts into the fast table |
| trash-entries | manual | **Editorial removal** (post_ids/row_ids + required reason). Log it in TECHLOG + site corrections log |
| data-quality | Mondays 16:00 UTC + manual | Anomaly report: WARN notices ≥5K, same-company multi-state filings, weak links — READ THIS WEEKLY |

Secrets (repo → Settings → Actions): `WP_API_KEY` (from wp-admin → Tools → AI Layoff
Tracker), `OPENROUTER_API_KEY`, `FTP_USER`/`FTP_PASSWORD`/`FTP_HOST`.
Railway env: `OPENROUTER_API_KEY`, `WP_API_KEY`, `WP_SITE_URL=https://asktherecruiter.com/blog`.

## "X is broken" playbooks

**Page shows an old design / changes not visible**
1. It's almost always cache. Hard-refresh (Cmd+Shift+R). 2. Confirm what the server
sends: `curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head`.
3. If server is stale, trip the flush URL above (works only if the version was bumped).
4. Autoptimize is NOT flushed on deploy (by design since v2.7.3 — content-hashed
filenames self-invalidate). If an AO asset looks stale, the version bump alone fixes it.

**White screen / HTTP 500 anywhere**
A PHP fatal from the latest deploy. `git revert` the last plugin commit, push, trip flush.
Balance-check PHP before deploying (see CLAUDE.md); there is no staging environment.

**API returns stale numbers**
Micro-cache holds 5 min. Any write bumps `alt_data_ver`; manual bump: run the `cleanup`
workflow. Browser-side: check the Cloudflare cache rule's Browser TTL (must be
"Respect origin" — origin sends `max-age=60`).

**Charts empty / filters dead in the browser**
Check the three endpoints directly (`/facets`, `/aggregate`, `/query?per_page=1` with
`?cb=$RANDOM`). If they're fine it's front-end: browser console; JS is
`assets/layoffs.js` (single file, no build step). DataTables/Chart.js load from cdnjs —
a CDN block kills the table (status message says so).

**Table says "No layoffs match" but the API returns rows** (the v2.7.1 crash class)
A render-callback exception is swallowed by the ajax `.catch` and shown as a data
problem. Capture the real stack in the console before touching anything:
```js
var dt = jQuery('#alt-table').DataTable().settings()[0];
var orig = dt.ajax; dt.ajax = function(d, cb, s) {
  return orig(d, function(json){ try { cb(json); } catch(e) { console.error('RENDER CRASH', e); } }, s);
};
jQuery('#alt-table').DataTable().ajax.reload();
```

**Page loads but nothing boots — 0 API requests, table stuck "Loading…"**
The aggregated JS itself is dead. Find the `autoptimize_single_*.js` URL in the page
source and curl it: a 410/404 with `cf-cache-status: HIT` means Cloudflare cached a
missing-file response (24h `max-age`). Origin is usually fine (verify with an extra
`&cfbust=$RANDOM` param, which changes the CF cache key). **Recovery: bump ALT_VERSION
and deploy** — the new `?ver=` is a new CF cache key; never wait out the TTL. Root cause
was deleting AO caches on deploy — removed in v2.7.3, do not reintroduce.

**Import workflow red**
Read the run log. `batch N FAILED: 500` = transient host error → re-run without purge
(idempotent upsert fills gaps). `purge refused` = scrape came back too small — the guard
protecting the table; investigate the states, don't override. Repeated 401 = WP_API_KEY
rotated (wp-admin Tools page ↔ GitHub secret must match).

**A state stopped importing / "no output file for XX"**
Two collector families: `warn-scraper` states (upstream lib — check
https://github.com/biglocalnews/warn-scraper/issues , bump the pin in
`railway/requirements.txt`) and OUR custom collectors in
`railway/sources/warn_custom.py` for TX/FL/GA/OH/MI/CO/ID/LA (state sites change;
fix the collector — each has its endpoint documented inline; GA needs a fresh nonce
per run, CO discovers per-year Google Sheets, ID/LA parse text PDFs).
No-data states (2026-07, not bugs): HI + OK publish no usable counts; MO/NM publish
nothing; MA/MN/NC/NV need custom scrapers nobody has written yet.

**A published number is wrong**
1. Verify against the primary source link. 2. Fix the CAUSE first (parser/normalizer —
else the next import re-creates it). 3. Remove/correct data: single entries →
`trash-entries` workflow; systematic WARN issue → fix parser, then `warn-import` with
`states=all, purge=true`; normalization issue → `cleanup`. 4. **Disclose**: dated entry
in the site's corrections log (templates/page-tracker.php) + TECHLOG. Counts are part of
the dedup hash — corrected counts need the purge path, plain re-import duplicates.

**Contact form not delivering**
Mails go via `wp_mail()` to info@asktherecruiter.com — confirm the mailbox exists in
Bluehost. Form errors surface as `?alt_error=` codes (spam|rate|fields|mail|expired).
Spam getting through → tighten in `includes/contact.php` or add Cloudflare Turnstile
(needs owner-registered keys). Accepted risk (audit #2): math captcha & fill-time check
deter only dumb bots; the honeypot does the real work; rate limit is per-IP 3/hour.

**Site slow / traffic spike**
Per-request floor is ~1.2s WP bootstrap on shared hosting; origin ceiling ≈8 req/s.
Mitigations, in order: (1) Cloudflare cache rule serving the API from edge (check
`cf-cache-status: HIT` on `/aggregate`); (2) page HTML is already super-cached (~0.4s);
(3) if sustained, upgrade hosting — the plugin itself scales (indexed table, micro-cache).

## Research pointers
- WARN scraping: https://github.com/biglocalnews/warn-scraper (Big Local News)
- GDELT DOC 2.0 API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ (keyless; ~gentle rate limits, 429s happen)
- SEC EDGAR full-text search: https://efts.sec.gov/LATEST/search-index?q= (declare a User-Agent per SEC policy)
- Extraction model: `deepseek/deepseek-chat` via OpenRouter (openai SDK, `base_url` override) — see `railway/extractor.py`
- Comparable trackers for editorial judgment: layoffs.fyi (crowdsourced), Challenger Gray monthly reports, WARN databases by ProPublica/USA Today

## Accepted risks / known limitations (documented, not bugs)
- ~98% of WARN links are state LIST pages — most states publish no per-notice URL
  (UI labels these "(list)"; AZ/KS/DE/ME/KY link per-notice).
- Multi-state remote employers file overlapping counts in several states (disclosed in
  methodology; Monday report flags them).
- WARN filings carry no industry/reason → industry/reason charts reflect SEC+news entries.
- Year/quarter/month SQL uses non-sargable date functions — fine at ~100K rows, revisit
  if the table grows 10×.
- `is_user_logged_in`-gated REST nocache suppression means logged-in admins always see
  fresh (uncached) API data; anonymous visitors may be ≤60s behind.
