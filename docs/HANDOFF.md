# Session handoff baton

Gated coordination so **cloud and local sessions never collide** on this repo
(we hit real git conflicts + version-bump races running two at once). Exactly
**one session holds the baton at a time**. `ops_status.py` prints the current
holder, so the start-of-session ritual surfaces it automatically.

## Baton
- **STATUS:** FREE
- **HOLDER:** —
- **SINCE:** 2026-07-21
- **WORKING ON:** —

## Protocol (every session follows this)
1. **Read this file first** (ops_status.py shows it). If **STATUS = HELD** by
   another session, do NOT edit — wait or coordinate with the owner. If **FREE**,
   claim it: set STATUS = HELD, HOLDER = `<cloud|local>`, SINCE = `<date>`,
   WORKING ON = `<one line>`, then `git commit` + `git push`. **If the push is
   REJECTED**, another session claimed first — `git pull --rebase`, re-read the
   baton, and back off.
2. **Work.** Commit + push as you go (`git pull --rebase` on any rejection).
   Bump the plugin `Version:` + `ALT_VERSION` only if you changed plugin files.
3. **Release when done:** set STATUS = FREE, clear HOLDER, add a dated line to
   the LOG below (what you did + what's next for the other session), commit + push.
4. **Emergencies / stale baton:** if a baton has been HELD > 24h with no commits
   from that holder, it's stale — the owner may tell you to take it; note the
   takeover in the log.

The push itself is the real gate: git rejects the second concurrent push, so
whoever lands the "claim" commit first wins and the other must rebase and see
the baton is taken.

## Handoff log (newest first — what each session did + what's next)
- 2026-07-25 local (Claude Code) #3: **IndexNow + final retirement fix**, 2.19.201→204, deployed green. (a) Retirement guard compared the last run to a rolling 2-day window, so a freshly retired source un-retired itself for 2 days (ops_status went red on 'newsapi degraded' whose last run predated the retirement) — entries now carry retired_on and only a run NEWER than that counts as reactivation. (b) **IndexNow live**: pushes data changes to Bing (powers ChatGPT search) + Yandex the moment the dataset changes, throttled to once/day, non-blocking, fired from alt_flush_caches via a new alt_data_written action; submits the 6 public surfaces. Key is MINTED SERVER-SIDE and stored in the DB — never in this public repo (the protocol asks that only the owner + engines know it; an earlier commit hardcoded one, now abandoned/unused). Key file served at /blog/<key>.txt; Option-2 scope means it can only claim /blog/* URLs, which is exactly where every tracker page lives. (c) Owner-only IndexNow panel on the health page (admin capability check, verified invisible to the public) showing the key, key-file URL, last submission result and one-click per-URL submission links. **OWNER ACTIONS unchanged + one new:** disable Rank Math's LLMs.txt so ours serves; verify in Bing Webmaster Tools (the IndexNow key + links are on the health page when logged in) and Google Search Console.
- 2026-07-25 local (Claude Code) #2: **360 ADVERSARIAL PASS + PERF**, 2.19.199→200, all green, verified live. Three parallel audits found 4 breaks-now bugs (all fixed): google_news' GLOBAL cap starved the company-chase + euphemism queries at cap 150 (company queries now FIRST + per-query slice); the map's AI-dot floor could exceed its blue bubble; vocab_hit substring-matched ('RIF' in 'tariff') so the missed-vocabulary learning was inert; the euphemism terms were segments (AND-ed with base vocabulary) so pure doublespeak could never match — now standalone on the native rotation. Also: weaning gauge records competitor spellings (was counting chased companies as independent), retirement keeps REAL timestamps + un-masks reactivated sources, date_basis share links round-trip (a 'notice date' link showed recipients DIFFERENT numbers), one Dataset JSON-LD per page. PERF: layoffs.js 82.7→44.9KB gzip (deploy-pipeline minify; repo keeps source), d3+topojson (~95KB) lazy-load on map reveal, API no-store stripped for claims/reconciliation/quality-status, assets immutable, preconnect. **Found a deploy bug:** the flush cleared every cache except the htaccess guard, so header changes lagged up to 12h — fixed, verified applied. **OWNER ACTIONS (only these):** (1) disable Rank Math's LLMs.txt in WP admin so OUR tracker llms.txt serves (currently overridden by a generic resume-content file); (2) verify in Bing Webmaster Tools (powers ChatGPT search) + Google Search Console, submit sitemap. **Next for any session:** watch the first learning email (vocab + outlet·country candidates) and paste adoptions back; consider branch protection on main if a collaborator is ever added; the remaining ~2,650 unclassified-industry rows are LLM-disagreement rows that stay honestly blank by design (hourly cloud sprint is self-limiting, costs nothing when idle).
- 2026-07-25 local (Claude Code): FULL-AUDIT + LEARNING-MACHINE session, 2.19.193→198, all green + verified live. (1) CI unbroken: fake sources.* stubs in two warn tests leaked and shadowed real modules for the whole suite — requests-only stubs now, 267 tests green. (2) Retirements self-heal: alt_retired_sources() in db.php coerces newsapi/edinet_jp/opendart_kr/cvm_br to benign 'retired' on /source-health (never re-alarms); public copy synced everywhere. (3) Tracker narrative: 3 labeled chart chapters (Where/Trending/Who+why), map full-width with 4px-floor AI dots (was invisibly proportional), claims overlay on-by-default, announced un-stacked, 'AI-attributed'=strict everywhere, colorblind chips fixed, health page de-jargoned, no prose em-dashes. (4) NEW 'Jobless claims by US state' card (DOL, grey, context-only, auto-updates weekly; layoff cards relabeled to disambiguate). (5) WEANING machine in tracker_diff + keyed /tracker-meta: daily INDEPENDENT recall (have minus ever-chase-resolved), learn-from-wins (outlet · country tagged; allowlist candidates), missed-vocabulary capture (invisible-headline email to owner with paste-back line), earned Mondays-only cadence at ≥90% for 21d. (6) Euphemism vocabulary (base 42→48 + paired noisy segments), dedup near-count floor 1000→250, Google News throttled 150. (7) Cost: owner set key cap $50; steady ~$5-10/mo; industry tail draining via sequential dispatches. Private bm refreshed (LOCAL): US 97% basis-any / H1 80% / tech 103% of the live tech tracker. **Next:** watch the first learning email land (vocab + outlet·country candidates) and paste back any adoptions; consider the second tech tracker's gap (74%) via startup-press allowlist growth; TX/GA/WA/MI are the biggest state gaps vs the announcement survey.
- 2026-07-21 local: honest 'Data last updated' timestamps on report/press/sources from alt_last_write (real last-ingest time, NOT page-load). Fixed report's misleading DateTime('now') stamp. Sources notes its list changes on deploys, not daily. **Next (BIG): investigate WARN gap — WARNTracker 775,892 vs our 239,450 (31%) on the same source.**
- 2026-07-21 local: self-growing watchlist — new public /companies endpoint (distinct captured names, cached) + company_watchlist self-grows from it (WATCHLIST_SELF_GROW). Monitored universe now compounds with every capture. **Next:** point WATCHLIST_INDEX_URLS at S&P500/Russell CSVs; build GLEIF/SEC alias feed.
- 2026-07-21 local (Claude Code): added prominent public 'Why our number is lower' journalist callout on the tracker page (competitor-free). **Next:** point COMPETITOR_FEED_URLS at the tech-event tracker export to auto-run the gap-chase.
- 2026-07-21 local (Claude Code): removed the dead public competitor-benchmark block from health.js (competitor/history numbers were in the served JS source, never rendered — no PHP container). Benchmark stays private (bm-live.html). **Next:** CA WARN backfill once egress allowlisted.
- 2026-07-21 local (Claude Code): built the handoff baton + env-equip kit
  (`docs/ENVIRONMENT-SETUP.md`, `scripts/setup_test_db.sh`,
  `railway/gen_synthetic_snapshot.py`) + wired the baton into `ops_status.py`.
  **Next:** a cloud session with egress + the test DB can do the CA WARN
  backfill, self-host the chart libs, and the `/aggregate` query-fold perf work.
