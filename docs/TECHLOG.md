# Tech Log

Chronological record of what was built, why, what broke, and how it was fixed.
Newest first within each section. **Keep this updated:** every deploy gets a line;
every incident gets an entry in the Incident Log with root cause + the guard added.

---

## Version history (plugin `ALT_VERSION` = git commits on main)

All 2026-07-14 → 07-15 unless noted. One intense build day + hardening day.

| Ver | What |
|---|---|
| 2.9.0–2.10.1 (Jul 15–16) | **World regions + coverage maximum + SEO pack.** 10 region tabs (adds Canada-first ordering, Latin America, Middle East, Africa; Europe 8→44 countries incl. Russia/Greenland/Balkans/Caucasus, Asia→29, Oceania) with complete on-page region→country documentation rendered from the config; empty-region tabs scope honestly (inject missing country options — Africa tab used to silently show world rows); region selections collapse to one chip; red empty-state; bold narrative numbers; one-row toolbar; mobile fixes (search box was 320px tall — flex-basis became height). **Coverage:** GDELT query de-AI'd (the AI clause excluded ALL general worldwide layoffs from the pipeline — root cause of thin Europe), weekly backfill windows (monthly truncated at the 250-article cap); EDGAR plural terms (+~90-130 filings/90d); custom WARN collectors for MA (Akamai HTTP/2 + Chrome fingerprint via httpx)/MN (Radware-walled; Wayback CDX discovery + seed PDFs)/NC (Drupal CSV)/NV (master PDFs + city vocabulary) = **41 WARN states, the obtainable ceiling**; **Eurofound ERM importer** — official EU27+Norway+UK per-company restructuring announcements, 7,125 job-loss events / 4.56M jobs since 2015, license authorizes reuse with attribution, dedup by factsheet id so Eurofound revisions update in place, daily 12:30 UTC sync. **SEO:** FAQPage JSON-LD + server-rendered FAQ with live numbers (crawler/LLM-visible without JS), Dataset schema enriched (spatialCoverage, dateModified, variableMeasured, layoff-tracker alternateNames). **Recall benchmark #1 (2026-07-15): 14.3%** (5/35 June–July reference events) — the honest baseline before the fixes above; re-measure after sweeps land. |
| 2.8.0–2.8.2 (Jul 15) | **Editorial correction layer + super-test fixes.** `/edit` endpoint + `edit-entries` workflow (field corrections pin the row `edited=1`, suppress the original source hash, survive daily purge+reimport); suppression list honored by `/add`+`/bulk`+upsert, recorded by `/trash`; real calendar-date validation (2026-03-32 → MySQL zero date); `sources` filter matches source_type too (sources=news was silently 0); `/facets` exposes sources vocab; live worked-example figure; `edited` flag public in `/query`. Data corrections from the 51-agent super test: 8 Florida STATE-SIDE TEST rows removed (fake "AT&T" 78,788 was our #1 entry; collector now skips test-named rows), 10 SEC-extraction non-events removed (dollar figures/percentages/boilerplate/wrong-date dupes), country resolved for 88 hidden rows (Oracle 30K → Multiple countries, BBC 2K → UK; world top-countries gap now 0), Ideal US Talent RI 9,891 → 2 (cross-state double count). FL WARN source URL moved (old path 404s for 2,612 rows; fixed for next import). 2.8.1 lesson: `/edit` initially reported success while every `$wpdb->update` silently failed — fail-loudly check added. |
| 2.7.0–2.7.3 (Jul 15) | **Region tabs + narrative**: 7 colored WSJ-style tabs (World/USA/Europe/UK/Asia/Australia/Canada) driving the country filter, hash deep-links (`#usa`), TrueUp-style auto-updating narrative ("Today, Jul 15: so far in 2026, N verified layoffs … In 2025, …") scoped per tab; "How our numbers compare to other trackers" panel (Challenger/WSJ/TrueUp/Layoffs.fyi/BLS/ONS/Eurostat links + why we differ); daily numbers-snapshot ping added to the data-quality workflow. 2.7.1 fixed a table-killing crash (date-column render signature missing `row` — every draw threw, UI showed "no layoffs match"). 2.7.2 honest empty-region hint. 2.7.3 stopped deleting Autoptimize caches on deploy (CF-cached-410 incident, below). |
| 2.6.0+ (Jul 15) | **The coverage marathon**: Announced tier live (announcement-stage cuts as a separate source-linked headline — the Challenger-comparable number with receipts). Custom collectors for ALL 8 broken states (TX Socrata JSON, FL REACT export, GA TCSG ajax, OH DAM CSV, MI Sitecore JSON, CO Google Sheets, ID/LA text PDFs) = +5,719 notices/~682K jobs. Parser unlocks for IL/PA (+1,841) and IA/MD/OR/SC/WI (+3,272) — all were schema quirks, not empty states. Non-English world outlets added (Le Monde, Nikkei, Globo...), English-only restriction dropped. Worked disclaimer example on-page (443,600 announced vs ~96,000 verified, H1-26). **37 WARN states / 42 states overall / 34,424 layoffs / 4.8M jobs.** HI+OK publish no counts (excluded per methodology); MO/NM publish nothing. |
| 2.2.2 | `/trash` resolves public API entry ids; executed the three editorial removals (posts 6499/6179/6516) — totals recomputed to 22,688 layoffs / 2.97M jobs |
| 2.2.1 | Ingest-safety HIGHs from 2nd audit: purge only after successful scrape + only with states=all + ≥5K threshold; date-shaped count values rejected; future WARN data no longer dropped from trend charts; REST nocache headers suppressed on public GETs (unblocks CF edge cache); `/trash` editorial endpoint + workflow; contact-page creation lock; JS races/popover/timezone fixes; docs/ created |
| 2.2.0 | API micro-cache (5-min transients keyed by params + `alt_data_ver`); journalist card light restyle; corrections log reset to launch state |
| 2.1.3 | Trend zero-fill honors multi-select periods (Apr–Jul selection → Apr 0 · May 0 · Jun x · Jul 0) |
| 2.1.0–2.1.2 | `/contact` page: auto-created, topic dropdown, honeypot + server-side math challenge + rate limit, mails info@; creation retries (deploy race); styled to match the main ATR app (cream/tan/olive) |
| 2.0.1–2.0.3 | **WARN count parser fix (first number, not concatenated digits)** + `/bulk-purge` clean reload; "upcoming" tag on future-effective filings; "all causes" stat label; public corrections log; link-precision labels ("(list)" vs exact); weekly data-quality anomaly report |
| 2.0.0 | Multi-select EVERYTHING (years/quarters/months/industry/country/state/sources/reasons as checkbox dropdowns; comma-list API params; AND across dimensions); color-coded filter chips per dimension; clickable date-range control; "layoffs" wording |
| 1.9.0–1.9.3 | Charts on top (compact grid, ⤢ expand); always-visible filter bar; GDELT added to the DAILY cron (worldwide press every run); controls moved above charts; January zero-fill; 14 fixes from 1st adversarial audit; WARN links for all states + per-notice where published; byline; date-sanity cleanup (typo'd 2050 filings) |
| 1.8.0–1.8.2 | Tracker redesign (search, quick views, live-updated pill); sticky count row; "Where the cuts are" AI-share bars; country/industry normalization (canonical "United States", fixed industry taxonomy); full-dataset CSV/JSON exports; daily WARN cron 15:00 UTC |
| 1.7.0–1.7.3 | **Server-side re-architecture**: `wp_alt_layoffs` indexed table; `/query` `/aggregate` `/facets` `/bulk`; front-end fully server-side (scales 100K+ rows); US `state` field; WARN source ('warn' tier, no LLM); nationwide import (per-state subprocess + keyword column parsing) |
| 1.6.x | Cross-outlet dedupe endpoint + fuzzy guard; country merge (US/USA/United States); charts on tracker page; multi-color bars; click-to-filter cross-filtering; reactive stats; auto cache-flush on version bump |
| 1.4–1.5 | Full-width layout (theme 645px cap override); credibility pack (methodology, permalinks, citation box); GDELT backfill source; curated AI seed |
| ≤1.3 | Initial: Railway pipeline (EDGAR+NewsAPI → DeepSeek → WP), CPT + REST + DataTables/Chart.js front-end, exports, RSS, SEO JSON-LD, FTPS auto-deploy |

## Data milestones
- 2026-07-15 (end of day): **34,424 layoffs · 4.8M jobs · 42 US states (37 WARN) · 18 countries**
- 2026-07-15 (morning): **~22,700 layoffs · ~3.1M jobs · 25 US states · 13 countries · 2015→present**
- Worldwide GDELT backfill (2023→now): +53 verified (23 AI-cited); India 106K jobs, UK 73K, +Spain/China
- Nationwide WARN: 25 states via warn-scraper; TX/FL/GA/OH/MI/CO/ID/LA unobtainable (upstream scraper breakage / state sites), IA/MD/MO/NM/OK/OR/SC/WI return no data
- Editorial removals 2026-07-15 (via `/trash`, pre-launch): post 23083 "Coal India 73,800" (a *by-2050 projection*, violates methodology), posts 274 & 23100 (Amazon retrospective summary articles double-counting the Oct-2025 30K and 2022-23 27K cuts)

---

## Incident log (root cause → guard now in place)

| Incident | Root cause | Standing guard |
|---|---|---|
| RI showed 98,912-worker notice (real: 9,891) | Count parser stripped ALL non-digits: "9,891 … (2 from RI)" → 98912 | `_count` parses FIRST number only; date-shaped values → 0; single-notice cap 100K; weekly anomaly report flags ≥5K notices |
| NJ row parsed as 2.4 **trillion** jobs | Multi-county list "240 (Passaic), 417 (Bergen)…" digit-concatenated | Same first-number fix (→ 240, the lower bound) |
| Visible range said "…– Dec 31, 2050" | State filing typo (also "3030-03-30") | Import window 2015→today+18mo; `/cleanup` NULLs implausible dates |
| Nationwide WARN run imported only 4 states | Single `warn-scraper all` process hit the 30-min timeout (CA alone is 17K rows) | Per-state subprocess with 420s timeout each |
| KY/MI/OH/FL/GA scrapers crashed | Missing `pyquery` dependency | In requirements.txt (TX/FL/GA/OH/MI/CO/ID/LA remain upstream-broken — see RUNBOOK) |
| VT parsed 0 rows | Every state names CSV columns differently | Keyword-based column matching; count-column excludes address/site/county headers |
| Import lost ~1,000 rows, workflow showed GREEN | One `/bulk` batch got an HTTP 500; script only printed it | Importer exits non-zero on ANY failed batch; maintenance curls use `--fail-with-body` |
| Purge could wipe table then scrape fail → EMPTY site (audit-caught before it happened) | Purge ran before scrape | Purge only after scrape succeeds, only with `states=all`, only if ≥5,000 notices scraped |
| Contact page 404 after deploy | Version-gated hook fired MID-FTP-upload (contact.php not landed), never retried | Creation retries until page verified; transient lock vs concurrent-init duplicates |
| Changes deployed but site showed old design | FTP deploys skip WP updater hooks → WP-Super-Cache/Autoptimize never flushed | `alt_flush_caches_on_deploy`: version bump auto-flushes page+asset caches, creates/upgrades the DB table |
| Railway POSTs got 406 | Host ModSecurity blocks `python-requests` UA | Descriptive User-Agent on EVERY request to the WP host |
| Railway POSTs got 403 "Just a moment" | Cloudflare Bot Fight Mode | Owner disabled Bot Fight Mode |
| Pipeline posted to wrong site | `WP_SITE_URL` pointed at apex domain (a separate Railway app) | `/blog` hardcoded in workflows; documented everywhere |
| Amazon ×5 / Intel ×2 duplicate entries inflating totals | Multiple outlets, same event | md5 exact hash + fuzzy same-company-±30d guard + `/dedupe` cluster collapse (WARN exempt) |
| "US/USA/United States" as 3 countries; "IT" vs "Information Technology"; "Global"/"India and US" buckets | Freeform LLM extraction | Normalizers at every entry point + `/cleanup`; "Multiple countries" bucket (no double counting); Trinidad-class "and"-countries whitelisted |
| Cache-Control conflict killed CDN caching | WP core appends `no-cache, no-store` to REST responses | `rest_send_nocache_headers` filtered off for anonymous public GETs (v2.2.1) |
| Charts hid future-dated WARN cuts | Zero-fill capped series at current month | Cap applies to fill only, never below real data |
| Table dead ("No layoffs match") while narrative showed 2,368 — every draw crashed | v2.6.0 announced-badge referenced `row` in the date column render, but the callback signature was `(d, t)`; the ReferenceError was swallowed by the ajax `.catch` | Signature fixed `(d, t, row)` (v2.7.1). Diagnosis pattern for "silent" table failures: wrap `settings.ajax` in the console to capture the real stack — see RUNBOOK |
| Every visitor served a dead 0-byte script for what would have been 24h | Deploy flush deleted Autoptimize aggregates; a request in the regeneration window got a 410 with `max-age=86400`, and **Cloudflare cached the 410** for the exact `?ver=` URL | Deploy no longer deletes AO caches (content-hashed filenames self-invalidate; v2.7.3). Recovery lever if it ever recurs: bump `ALT_VERSION` — new `?ver=` = new CF cache key |

## Audits (multi-agent adversarial reviews — run one after every significant change set)
- **2026-07-15 super test #3** (51 agents, 7 suites + adversarial verify): 16 confirmed / 6 refuted. Standouts: Florida's own WARN export contains staff TEST rows (fake AT&T 78,788 topped the tracker — parser was faithful, source was dirty); 99 news/SEC rows had no country (38K jobs incl. Oracle 30K invisible to region tabs); Ideal US Talent company-wide total under RI; FL source page moved (2,612 dead links); zero-date row from "2026-03-32"; sources=news silently 0; stale worked example (−83%). All fixed same day (v2.8.0–2.8.2 + edit/trash workflows). Refuted claims (don't re-flag): /stats "two data stores" (definitional), announced tier all-zero (expected, just launched), Technology-2026 undercount (WARN rows carry no industry — documented).
- **2026-07-14 audit #1** (v1.8.x diff): 16 confirmed findings (country-delimiter dead code, industry 'tech' swallowing biotech/fintech, search surviving Reset, CSV formula gap, admin-bar offsets, silent workflow failures…) — all fixed in v1.9.1.
- **2026-07-15 audit #2** (v1.9.3–v2.1.2 diff): 24 confirmed (4 HIGH: purge-before-scrape, purge+partial-states, date-shaped counts, future-data chart drop) — HIGHs + quick wins fixed in v2.2.1; accepted-risk items documented in RUNBOOK.
- **2026-07-15 live pre-ingest test** (5 suites): filters 38/38 checks over 2,133 validated rows ✓; exports byte-perfect (22,691 = CSV = JSON = API) ✓; all 27 state links live ✓; found Coal India/Amazon editorial removals; measured WARN link precision (~98% state-list pages — inherent, labeled "(list)" in UI); perf: 1.2s WP-bootstrap floor per API hit, ~8 req/s origin ceiling, page HTML cached at 0.4s.

## Infrastructure changes by the owner (outside this repo)
- 2026-07-14: Cloudflare Bot Fight Mode OFF (was blocking the pipeline)
- 2026-07-15: Cloudflare Cache Rule added for `/blog/wp-json/layoffs/v1/*` GETs. ⚠ Set **Browser TTL = Respect origin** (a 5-day browser TTL was initially observed) and Edge TTL ≈ 5 min.
