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
The deployment first PHP-lints every plugin file, then verifies a cache-busted
public tracker API response after FTPS completes. A failed live verification is
an actionable deployment alert; do not assume an FTP success alone means the
plugin loaded.
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
| survey-reconcile | monthly + manual | Compares the strict US AI-primary announcement metric against the latest official announcement-survey report; fails if variance exceeds 10% |
| reclassify-legacy-ai | daily + manual | Re-reads linked sources for a bounded batch of legacy AI flags; never deletes rows |
| reason-backfill | daily 04:40 UTC + manual | Tags untagged non-WARN rows from their STORED excerpt only (fixed vocabulary; ERM template rows map from Eurofound's recorded type, freeform rows via DeepSeek). Writes via /edit (pins rows). Inputs: model_batch, deterministic_cap, dry_run |
| enrich-roles | daily 04:23 UTC + manual | Bounded role-category extraction from already-stored row text (roles/excerpt/quotes, no external fetches); fills only blank role_categories, marks evidence-silent rows `unknown` so the queue drains |
| historical-news-sweep | daily + manual | Rotates through one 14-day global GDELT history window per day; dedup makes retries safe |
| announcement-lifecycle-review | daily + manual | Read-only summary of exact-count, source-supported announcement-to-later-record candidates; never auto-merges or changes sources |
| quarterly-report | 7th day after quarter close + manual | Stores an immutable, server-generated State of Layoffs snapshot; accepts only quarter id/status, never client totals or editorial claims |
| canonical-event-migrate | daily + manual | Resumable no-LLM conversion of legacy rows into canonical events with retained source reports |

The advisory DeepSeek spot-check inside `data-quality` retries temporary
network/model failures and writes an explicit warning to the Actions summary
without failing the whole report. A failed attempted automatic correction still
fails loudly, because that is a data-changing operation.

Secrets (repo → Settings → Actions): `WP_API_KEY` (from wp-admin → Tools → AI Layoff
Tracker), `OPENROUTER_API_KEY`, `FTP_USER`/`FTP_PASSWORD`/`FTP_HOST`.
Railway env: `OPENROUTER_API_KEY`, `WP_API_KEY`, `WP_SITE_URL=https://asktherecruiter.com/blog`.
Optional Railway env: `PRESS_RELEASE_FEEDS` (JSON array of reviewed official company RSS/Atom feeds; see `.env.example`).

## "X is broken" playbooks

**Page shows an old design / changes not visible**
1. It's almost always cache. Hard-refresh (Cmd+Shift+R). 2. Confirm what the server
sends: `curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head`.
3. If server is stale, trip the flush URL above (works only if the version was bumped).
4. Autoptimize is NOT flushed on deploy (by design since v2.7.3 — content-hashed
filenames self-invalidate). If an AO asset looks stale, the version bump alone fixes it.

**Company directory page is missing or should not be indexed**
1. Unknown, pending or ambiguous `/company-layoffs/{slug}/` paths must return 404; do not add a freeform alias to make one resolve.
2. Confirm the reviewed registry row has the intended stable slug, canonical company key, display name and review status. A raw dedup key alone is not an identity decision.
3. Confirm every displayed canonical event retains at least one valid source URL. Approved records need two or more such events to index; otherwise use the reviewed `noindex` status.
4. A versioned deployment rebuilds the directory rewrite rule once after its template is present. Verify a known reviewed slug, an unknown slug (404), and the resulting robots directive after deploy.

**White screen / HTTP 500 anywhere**
A PHP fatal from the latest deploy. `git revert` the last plugin commit, push, trip flush.
Balance-check PHP before deploying (see CLAUDE.md); there is no staging environment.
If EVERY URL 500s (not just plugin pages), also suspect `/blog/.htaccess`: remove the
`# BEGIN AI Layoff Tracker` block over FTP (the plugin's writer canary-probes and
rolls back on its own, but a half-written file from an unrelated crash cannot).

**API returns stale numbers**
Micro-cache holds 5 min. Any write bumps `alt_data_ver`; manual bump: run the `cleanup`
workflow. Browser-side: check the Cloudflare cache rule's Browser TTL (must be
"Respect origin" — origin sends `max-age=300` on the API since the `.htaccess`
override; browsers may serve up to 5-min-old numbers by design).

**Duplicate Cache-Control returns (API/page sends `public, max-age=…` AND `no-cache, no-store…`)**
Bluehost's Apache injects the no-store trio after PHP's headers on every PHP response;
the plugin overrides it with a marked block in the WP root `.htaccess` (managed by
`includes/htaccess.php`, self-healing on init, canary-probed, auto-rolls-back on 5xx).
1. Check state: option `alt_htaccess_state` (`status: verified|failed`, `reason: write|probe`).
2. Check the file: the `# BEGIN AI Layoff Tracker` block must exist in `/blog/.htaccess`
   (view over FTP). If the host or another plugin rewrote the file, the init hook
   restores the block within 12h; to force it now, delete transient `alt_htaccess_ok`
   and option `alt_htaccess_state`, then hit any page.
3. If `status: failed` with `reason: probe`, a write made the site 5xx and was rolled
   back — the block only re-attempts on the next `ALT_VERSION` bump. Investigate before
   bumping (Apache error log via cPanel).
4. Verify with GET, not HEAD: `curl -sS -D - -o /dev/null -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' ".../aggregate?cb=$RANDOM" | grep -i cache-control`
   must show exactly ONE header. `cf-cache-status` on HEAD always reads DYNAMIC
   (Cloudflare serves cached GETs only) — that alone is not a failure signal.
5. If the trio ever comes back at a layer `.htaccess` can't reach (front proxy),
   fallback: Cloudflare Response Header Transform Rule setting Cache-Control for
   `/blog/wp-json/layoffs/v1/*` (owner action, document in TECHLOG infra section).

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

**An announced plan may have later executed / been filed**
1. Inspect the public `/announcement-lifecycle-candidates` queue. It is only a narrow, read-only lead: exact company/count/country plus a source-evidenced announcement date and a later record within 365 days.
2. Compare every retained source report for both events; confirm the scope, geography and timeline describe the same underlying cut.
3. Only then use the keyed `/merge-events` route with an editorial reason. Never merge from company name or an LLM suggestion alone. The merge keeps every source report.

**Announcement-survey reconciliation fails**
1. Do not change the tracker total to match the benchmark. The comparison is only valid for US-based employers,
   announced cuts, AI-primary cause and canonical events.
2. Open the uploaded `survey-reconciliation` artifact. Record the announcement-survey report URL, tracker query and
   variance in the monthly reconciliation log.
3. Re-run recent GDELT/news/IR overlapping windows, then classification/dedup audits. Missing, duplicate,
   date/count and definition differences must remain separately identifiable.
4. If the official announcement-survey site changes its markup, update `railway/survey_reconcile.py` with a regression
   fixture; do not replace it with a guessed hard-coded total.

**Quarterly report needs correction or rerun**
1. Do not overwrite a published report. Quarterly report ids are immutable so that journalists can reproduce what was published.
2. Check the public report JSON, its `dataset_revision`, source-health snapshot and the current `/quality-status` revision.
3. The report page automatically says when live data have changed since its snapshot. Correct underlying event data through the normal source-preserving correction path; do not alter historical report facts.
4. If a materially corrected replacement is necessary, create an explicitly versioned follow-up report and document its relationship to the original. Do not silently reuse the same quarter id.
5. The report JSON/CSV appendix is derived only from the stored immutable snapshot. If it differs from the page, treat that as a release defect; never regenerate an old appendix from the current live aggregate.

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
- Comparable trackers for editorial judgment: technology-sector trackers (crowdsourced), announcement-survey monthly reports, WARN databases by ProPublica/USA Today

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
- FTP deploys upload files in place (no atomic swap on Bluehost), so each deploy has a
  ~30–60s window where a PHP-hitting request can 500 on a truncated file. Supercached
  HTML shields most anonymous traffic; a 500 observed right after a push is this window,
  not an outage — re-check after the deploy run goes green before reverting anything.
