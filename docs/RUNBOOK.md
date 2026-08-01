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
| company-watchlist | daily + manual | Sweeps big employers with no current-year entry; targeted news search → extractor → poster. Auto-grows via `WATCHLIST_INDEX_URLS`. Inputs: dry_run |
| supplemental-news | daily 14:05 UTC + manual | NewsData.io + Marketaux + Finnhub (non-English/EU news). Dormant per key. Inputs: dry_run |
| distress-watchlist | weekly Tue + manual | CourtListener bankruptcy + Companies House insolvency → distressed names → watchlist news search. Dormant per key. Inputs: dry_run |
| foreign-filings | daily 13:30 UTC + manual | EDINET (JP) + OpenDART (KR) filing bodies → extractor (guards reject non-layoffs). Dormant per key. Low yield by design. Inputs: dry_run |
| recall-precision | weekly Mon 16:10 UTC + manual | **The only place the recall claim can FAIL.** Re-runs the frozen SEC Item 2.05 gold set (57 events) against live data, **commits** `railway/recall_measurement.json`, and exits 2 below `recall_goldset.MATCHED_FLOOR`; also measures count precision (exits 2 when the Wilson 95% lower bound drops under 80%) and AI-attribution precision. Every rate is printed **with its interval**. Needs `contents: write` for the commit. Inputs: RP_PRECISION_SAMPLE |
| data-integrity | daily 17:30 UTC + manual | **Is the published data CORRECT?** Runs `railway/data_integrity.py` — the live invariants (known duplicate events must count once) shared with `tests/test_dedup_live.py` — and writes the verdict to the health ledger as `data_integrity`. Scheduled 50 min AFTER reconcile-supersets so it sees that pass's result. Exit 2 = failing, exit 3 = could not verify (never a silent pass) |
| health-digest | Mondays 12:00 UTC + manual | **Autonomy tripwire.** Reads source-health ledger; fails RED and **emails info@asktherecruiter.com** (via `/alert`) when a source goes STALE or degrades, **or when a live data-integrity check is failing** (subject leads "WRONG NUMBER LIVE"). Weekly is the backstop only — the fast paths are `ops_status.py` [3] and the daily data-integrity run. Email body carries a paste-ready Claude fix instruction. Inputs: dry_run |
| tracker-diff | dormant BY DESIGN (owner decision 2026-07-28) | Optional gap-chase against a private feed. Competitor tracking is handled by the LOCAL benchmark instead; this loop is not needed, exits green on schedule, and nobody should be asked to enable it |

The advisory DeepSeek spot-check inside `data-quality` retries temporary
network/model failures and writes an explicit warning to the Actions summary
without failing the whole report. A failed attempted automatic correction still
fails loudly, because that is a data-changing operation.

Secrets (repo → Settings → Actions): `WP_API_KEY` (from wp-admin → Tools → AI Layoff
Tracker), `OPENROUTER_API_KEY`, `FTP_USER`/`FTP_PASSWORD`/`FTP_HOST`, `NEWSAPI_KEY`,
`GCP_BIGQUERY_CREDENTIALS_JSON`.
Railway env: `OPENROUTER_API_KEY`, `WP_API_KEY`, `WP_SITE_URL=https://asktherecruiter.com/blog`.
Optional Railway env: `PRESS_RELEASE_FEEDS` (JSON array of reviewed official company RSS/Atom feeds; see `.env.example`).

**Dormant-source keys** (each collector runs only when its key is present; add in
repo → Settings → Actions → Secrets, exact name):
| Secret | Activates | Status / notes |
|---|---|---|
| `NEWSDATA_API_KEY` | supplemental-news (NewsData.io) | Free tier caps `q` at 100 chars; endpoint is `/api/1/latest` |
| `MARKETAUX_API_KEY` | supplemental-news (Marketaux) | Search syntax uses `|` for OR, not the word "OR" |
| `FINNHUB_API_KEY` | supplemental-news (Finnhub) | Ticker-based; reuses `seed_data/earnings_tickers.csv` |
| `COURTLISTENER_API_KEY` | distress-watchlist (US bankruptcy) | Only "In re <Debtor>" petition captions kept |
| `COMPANIES_HOUSE_API_KEY_UK` | distress-watchlist (UK insolvency) | HTTP Basic (key as username) |
| `EDINET_API_KEY_JP` | foreign-filings (Japan) | Low yield; extractor guards protect quality |
| `OPENDART_API_KEY_KR` | foreign-filings (Korea) | Low yield; `list_disclosures` needs (start,end) dates |
| ~~`FMP_API_KEY`~~ | (dropped) | Transcripts are paid-only (HTTP 402) — earnings ingest removed |

Every dormant source ships DORMANT and exits clean when its key is absent, so
adding a key is the only step to activate it. First run each in `dry_run=1` and
read the diagnostics (they log the raw API status) before trusting live output.

## "X is broken" playbooks

**A data-integrity check is failing (START HERE — this outranks a broken source)**
`ops_status.py` section [3] said `FAILING`, or a red `Live data-integrity check`
run, or an email subject beginning "WRONG NUMBER LIVE". **Do this before any
source-staleness item.** A stale collector means data we have not gathered yet; a
failing integrity check means the live tracker, the press page and the public API
are serving a **wrong number to readers right now**.

The invariants live in `railway/data_integrity.py` (`INVARIANTS`) and are shared
verbatim with `railway/tests/test_dedup_live.py` — one definition, so the guard
and the dashboard can never disagree. Each says a known duplicate event must
count **once**.

1. **See it.** `python3 railway/data_integrity.py` — prints each check, the
   observed number, its bound and what a breach means. No keys, no deps.
2. **Do not "fix" the bound.** The bounds are tripwires set just above a value a
   specific double-counting bug produces. Raising one to whatever the site
   currently says silences the alarm and keeps the wrong number. If you believe a
   bound is genuinely wrong, that is a deliberate, documented change with the
   reasoning written into the `Invariant`.
3. **Find which dedup pass broke.** The `regression` string on the failing
   invariant names it: news-vs-news exact-count, news-vs-WARN superset, or
   within-WARN revision. All three live in `alt_reconcile_supersets()` in
   `wordpress-plugin/ai-layoff-tracker/includes/db.php`.
4. **Inspect what the reconciler sees.** Dispatch `reconcile-supersets.yml` with
   `dry_run` + `detail=1` (and `probe=<employer>` to dump the rows it loads for
   one company). Compare `jobs_before` / `jobs_excluded` / `jobs_after`; a
   non-zero `changes` on a quiet day is drift.
5. **Fix, deploy, re-verify live.** Bump `Version:` + `ALT_VERSION`, push, wait
   for the deploy run matching your SHA, then re-run step 1. Do not trust a green
   tick — the data can regress with no commit at all (that is how the 2026-07-30
   Spirit defect appeared: a running all-time WARN sum crossed a threshold).
6. **If it says UNKNOWN, not FAILING**, nothing was verified — that is not a
   pass. Re-run somewhere with network access to `asktherecruiter.com`.

**`recall_floor` is the one invariant that works the other way round.** Every
other check asks whether a published number is WRONG; this one asks whether a
number is MISSING, and it is the only one that reads a committed file rather
than the live API (re-measuring is ~60 requests, and ops_status is on the
critical path of every session's first command).

- **FAILING** means the tracker has LOST events an editor confirmed it held —
  the gold set is frozen, so this is never sampling noise. The detail names the
  events. Check the last `/bulk-purge`, the last `reconcile-supersets` run, and
  whether an employer was renamed (the match is a token-prefix on company name,
  so "Alector LLC" -> "Alector Inc" is fine but a rebrand is not). Fix the cause;
  do not lower `MATCHED_FLOOR`.
- **UNKNOWN** means the measurement is missing or older than 9 days, which means
  `recall-precision.yml` has stopped. Check that workflow before anything else,
  then `python3 railway/recall_goldset.py --write` and commit.
- **The 42% it reports is not a claim.** It is recall against ONE source family
  (US public companies filing 8-K Item 2.05 with an explicit count) over ONE
  twelve-month window at n=57, interval [30%, 55%]. Never quote it as "our
  recall", and never post it to `/benchmarks/recall` — that endpoint is reserved
  for a sample that has been through the three-reviewer chain in
  `docs/RECALL_BENCHMARK_PROTOCOL.md`, and this set has not.

**Which check failed, and what each one wants you to do**

The registry holds two kinds of check. The first four are **named-event
tripwires** (Coinbase, Spirit, Tyson, AT&T): steps 1-6 above are written for
those. The other three are **shape guards** — they know no event names and cover
the row that has not gone wrong yet. Their playbooks differ:

- **`headline_concentration` — one row is carrying a published number.**
  The detail names the row: share, job count, company and row id. Open that row
  and check it against its own source. Historically this shape has been a count
  misparse (RI 9,891 stored as 98,912), a state TEST notice (AT&T 78,788), or a
  projection filed as an event (Coal India 73,800 "by 2050"). If the row is
  WRONG: `apply-correction.yml` or `trash-rows.yml`, and disclose it in the
  corrections log. If the row is genuinely that big and genuinely correct, that
  is the one case for widening the bound — change `max_share` on that `Headline`
  with the reasoning in the code, and add the new live reading to
  `test_headline_guards.test_every_shipped_headline_has_headroom_over_its_live_reading`.
- **`headline_movement` — a published total moved and no row explains it.**
  The detail gives the before/after, the change in entry count, and what the
  rows that changed could have carried. Δentries near zero with jobs moving is
  the signal: something re-scored rows that were already published. Check, in
  this order, the last `reconcile-supersets` run (its `changes` count on a quiet
  day is drift), any `bulk-purge` / re-import, and `data-corrections`. The
  baseline is `railway/headline_baseline.json`; **do not hand-edit it to clear
  the alarm** — the recorder already refuses to advance a failing slice, because
  recording a bad number makes it tomorrow's normal.
- **`dedup_denominator_scoped` — the structural guard came off.**
  Offline and instant: it asserts that `alt_reconcile_supersets()` in db.php
  still cannot compute a sum of its own, that its denominator can only come from
  `alt_dedup_window()`, and that `alt_dedup_subset_verdict()` still throws when
  handed anything not window-scoped. A failure means someone reintroduced an
  inline share comparison or a local sum. That is the exact 2026-07-30 shape;
  restore the helpers rather than re-fixing the arithmetic.

**"Not watching yet" is not "fine".** If `ops_status` prints `NOT WATCHING YET`
or a check reads PENDING, the guard is armed in the code but has nothing to read:
either the deployed plugin predates the field (wait for a green Deploy run) or
the first baseline has not been written (`python3 railway/data_integrity.py
--record-baseline`, or wait for the 17:30 UTC job). Exit code 3, never 0.

**If a shape guard proves noisy in its first weeks:** raise its `move_floor` and
write down why, in the commit message and in TECHLOG. Do not delete the check and
do not fit the bound to whatever today's move happened to be. `max_share` bounds
were measured against live readings; `move_floor` values were reasoned from the
failure modes, because until `headline_baseline.json` existed nothing had ever
recorded this site's day-over-day deltas.

**A data source broke — you got a "data source(s) need attention" email (START HERE)**
The weekly `health-digest` emails info@asktherecruiter.com when a collector goes
STALE (stopped reporting) or degraded (usually a scraper returning 0 because a
third-party site changed its layout). The email names the source and includes a
paste-ready instruction.

**First, rule out an environment egress block (30 seconds).** If you landed here
because `ops_status.py` said the live tracker / health endpoint is "UNREACHABLE",
check whether it printed `ENVIRONMENT BLOCK` / exited 3 — that means THIS cloud
environment's network policy denies `asktherecruiter.com` (a proxy 403/tunnel
CONNECT that never reaches the site). That is NOT a broken source and this
playbook does not apply; you can still deploy (see docs/CLOUD-SESSION.md). A real
source breakage is flagged as `STALE`/`DEGRADED` per-source (exit 2), or arrives
by the health-digest email. Only then continue below. To fix:
1. **Identify the collector.** Source id → file:
   - `warn_custom_states` / `warn_custom_legacy` → a state scraper in `railway/sources/warn_new_states.py` or `railway/sources/warn_custom.py` (the email/detail names the state code).
   - `warn_us` → `railway/sources/warn.py` (the open `warn-scraper` lib) + `railway/warn_import.py`.
   - `gdelt` → `railway/sources/gdelt.py`; `google_news` → `railway/sources/google_news.py`; `news_catchup` → `railway/news_catchup.py` (weekly; uses `sources/newsapi.py`, whose twice-daily `newsapi` collector identity is RETIRED); `edgar` → `railway/sources/edgar.py`; `eurofound_erm` → `railway/erm_import.py`.
   - `supplemental_news` → `railway/supplemental_news.py`; `company_watchlist` → `railway/company_watchlist.py`; distress/foreign → `railway/distress_watchlist.py` / `railway/foreign_filings_ingest.py`.
2. **Confirm the breakage.** Run that workflow with `dry_run=1` (Actions tab → the workflow → Run workflow) and read the log. A `0 notices`/`HTTP 4xx`/`::warning::` line confirms drift.
3. **Re-recon the site.** `curl` the state's official WARN URL (from the Sources page or `warn.py`/`warn_new_states.py`) and diff the HTML/PDF structure against what the parser expects (selectors, table columns, download links). State sites redesign a couple times a year — the fix is almost always updating the parse selectors or the fetch URL.
4. **Fix + verify.** Update the parser, `python3 -m py_compile` it, re-run `dry_run=1`, confirm sane company/count/date rows, then let the scheduled run post live. Dedup makes re-runs safe (WARN is hash-idempotent).
5. **If a state has genuinely gone dark** (site retired, data now confidential): move it to the gap-states list in `templates/page-sources.php` with an honest reason, and add its code to `_BENIGN_STATES` in `railway/health_digest.py` so it stops alerting.
Transient degradeds (`gdelt_historical` HTTP 429) self-retry and are excluded from the email (SOFT_DEGRADED) — no action needed.

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

## How to ADD a new source (the pattern every collector follows)
Never write to the DB directly. Every source produces "raw entries" and hands
them to the shared pipeline, so it inherits dedup + entity-alias + country/
industry normalization + verbatim-count guard + AI-attribution + quote gate for
free. Steps:
1. **Write a collector** in `railway/` (or `railway/sources/`). Fetch with a
   browser-ish `User-Agent` and a `timeout=`. For each candidate build a raw
   dict with AT MINIMUM `raw_text` (the extractor reads ONLY this and returns
   None if empty — the #1 bug that made a whole source silently post nothing),
   plus `source_type`, `source_name`, `verification_level`, `source_url`.
   Mirror `sources/newsapi.py`'s dict shape exactly.
2. **Route through the guards**: `from extractor import extract_layoff_data`
   then `from wp_poster import post_to_wordpress`. `ex = extract_layoff_data(raw)`;
   if `ex`, `post_to_wordpress(ex)`. That's it — never assemble a row yourself.
   (WARN-style structured feeds that already have company/count/date skip the LLM
   and bulk-upsert via `/bulk`; see `warn_import.py`.)
3. **Ship it DORMANT** if it needs a key: read `os.environ.get("YOUR_KEY")` and
   return early when absent. Add diagnostic logging of the raw API status so the
   first `dry_run=1` reveals shape/auth problems (see `supplemental_news.py`).
4. **Report health**: call `report_source_health(name, "ok"|"degraded", posted, detail)`
   so it appears in the ledger and the weekly digest. Add a matching label in
   `assets/health.js` `meta{}` and, if it's a real public source, a row on
   `templates/page-sources.php`.
5. **Add a workflow** in `.github/workflows/` (copy `supplemental-news.yml`):
   pass the key + `OPENROUTER_API_KEY` + `WP_API_KEY` + `WP_SITE_URL`, set
   `PYTHONUNBUFFERED: '1'`, a `timeout-minutes`, and a `dry_run` input. Add a
   wall-clock deadline in the script if it does per-item news searches (they can
   exceed the job timeout — see `distress_watchlist.py`).
6. Document it: add a row to the workflow table + dormant-key table above, and a
   TECHLOG entry.

## How to FINE-TUNE (env knobs, no code change)
- **Extraction quality**: the AI rubric + guards live in `railway/extractor.py`
  (`_count_in_text` verbatim guard, the timeline/subset prompt). AI precision is
  measured weekly by `recall-precision` (AI-attribution quote-rate); `reclassify-
  legacy-ai` (bump `batch`) downgrades vague legacy AI tags.
- **Coverage breadth**: GDELT segment rotation is `SEGMENT_TERMS` in
  `sources/gdelt.py` (`GDELT_SEGMENT_QUERIES` per run); European sweep toggles
  with `GDELT_EURO_SWEEP`. Watchlist size/window: `WATCHLIST_BATCH`,
  `WATCHLIST_DAYS_BACK`; auto-grow with `WATCHLIST_INDEX_URLS`.
- **Dormant-source limits**: `DISTRESS_MAX`/`DISTRESS_DEADLINE_SECONDS`,
  `FOREIGN_MAX`, `RECLASSIFY_BATCH`, `RP_PRECISION_SAMPLE`.
- **Alert sensitivity**: `railway/health_digest.py` — `MAX_AGE_DAYS` (per-source
  staleness window), `SOFT_DEGRADED` (transient sources that don't email),
  `_BENIGN_STATES` (no-register states that shouldn't alert).
- **Country filter meaning**: `country_basis=any` (table/exports, employer-HQ
  inclusive) vs strict job-location (headline stats). Set in `assets/layoffs.js`.

## How to ENHANCE (bigger moves + their honest ceilings)
- **US WARN**: 48 states + DC already scraped; AR/NH/WY have no public register.
  This lever is maxed.
- **Europe**: per-company data is Eurofound ERM (running) + multilingual news;
  NL/FR/DE publish NO public per-company register (confidential) — not buildable.
- **Benchmark refresh** (survey baselines in the private `gen.py`/`bm-live.html`):
  MUST stay local — competitor names/numbers may never enter the public repo or
  GitHub logs (standalone-brand rule; competitor URLs go in `COMPETITOR_FEED_URLS`
  secret only). A cloud cron would leak them.
- **New-source discovery**: event-gap discovery is automatable (`tracker-diff`,
  needs `COMPETITOR_FEED_URLS`); discovering brand-new source *types* is a human
  judgment call, not a cron.
- **Autonomy ceiling**: ~99%. The irreducible human sliver = repairing a scraper
  when a third-party site redesigns (now auto-detected + emailed), refreshing the
  private benchmark, and novel-source judgment. Do not claim "100% automated".

## Quarterly source-verification audit (the accuracy claim)

What it produces: the number we publish in the FAQ ("How do you check your own
accuracy?"). Run it fresh every quarter, never reuse a seed.

1. Pull the pool from the public `/query` API and draw a **stratified random**
   sample (30 rows/year x warn/news/erm/8K; oversample 8-K, there are few).
   Record the seed. A fresh-model auditor is worth it: it has no memory of why
   a row was built the way it was, which is the whole point.
2. The auditor OPENS every row's `source_url` and grades company + count + date
   against what the page actually says. Verdicts: PASS, WRONG-NUMBER,
   WRONG-DATE, WRONG-COMPANY, DEAD-LINK, REGISTER-LEVEL (the register rolled
   over and no longer exposes the row - an access limitation, NOT a data
   error, report it separately), UNVERIFIABLE.
3. **Re-verify every proposed numeric change YOURSELF before applying it.**
   This is not ceremony. In audit #1 the auditor graded Dow 3,700 as WRONG
   because the cited article headlines 4,500; the row was right (3,700 is the
   net-new portion, the other 800 is a separate retained row, and Eurofound
   records the event as "3,700 - 4,500"). Applying that "fix" would have
   double-counted 800 jobs. **A deliberately reconciled net-new row always
   looks wrong to an auditor reading only the headline figure** - so read the
   row's excerpt for a reconciliation note, and check whether the difference is
   already retained as its own row, before you believe the finding.
4. Apply what survives via the dispatch-only corrections path (dry run first):

```bash
gh workflow run apply-correction.yml -f ids=70289 -f action=trash -f reason="audit #N: <why>" -f verify_company=Starbucks -f apply=false
```

   `trash` when the source supports no count at all; `edit` when a field is
   wrong. Both suppress the original hash so the nightly re-scrape cannot
   resurrect the row, and both append to the PUBLIC corrections log
   automatically. Re-run with `apply=true` once the dry run shows the right row.
5. Update the published accuracy figure in the FAQ and log the audit in
   TECHLOG under "## Audits". Report register-level rows separately from real
   errors, and say what you could NOT verify.

## Monthly coverage audit (the gap-closing loop)

The daily pipeline collects; this loop finds what the pipeline is BLIND to. Run
it monthly. It is the only reliable way to discover a structural blind spot,
because a blind spot by definition does not show up in our own data.

**Step 1 - research the thin sectors.** Dispatch one agent per weak sector (use
the private benchmark to pick them). Brief each with these NON-NEGOTIABLE rules,
which exist because looser ones produce unusable rows:
- an EXACT headcount (reject ranges, "hundreds", percentage-only)
- a date inside the target window
- a NAMED source: major outlet, official company release, or an SEC filing
- NO layoff aggregators as sources (some of their figures are provably fabricated)
- the agent must OPEN the article to confirm number + date. Search snippets
  routinely misdate 2025 events into 2026.

**Step 2 - DEDUPE BEFORE YOU SEED. This is the step that matters.** In the
2026-07 run, 36 of 69 researched events were ALREADY in the tracker (58% of
auto/food, 79% of tech). Seeding blind would have double-counted every one.
Query `/query?company=<name>` per candidate and compare. Two traps:
- **Window too narrow.** A +/-75 day window marked Oracle 21,000 as NEW; we held
  it 77 days away at a different date basis. ALWAYS re-check any big candidate
  against EVERY row for that company in the year, not just a date window.
- **Announced vs executed.** If we already hold a company's WARN execution
  slices (Meta 2,212 + 1,395 + ...), seeding the company-wide announcement
  (Meta 8,000) counts the same people twice. Skip it, or use the announced tier
  deliberately - never mix them.

**Step 3 - seed the survivors** via `seed_data/<name>.json` +
`backfill-seed.yml` (dry_run=1 first). It is idempotent and dedup-guarded
server-side, which caught one more duplicate the client check missed.

**Step 4 - THE PART PEOPLE SKIP: diff the SOURCES, not just the events.**
Tabulate the `source_name` of everything you had to seed. In 2026-07 that single
table was the most valuable output of the whole audit: we already held every
national-wire story, and every event we MISSED ran only in a state business
journal or a vertical trade publication (NJBIZ alone carried 4 of 29). Seven of
those ten outlets were not in the allowlist at all. The events were a symptom;
the allowlist was the disease. Add the missing outlets to `TRUSTED_DOMAINS` so
next month the pipeline catches them automatically - that converts a manual
backfill into a permanent capability.

**Step 5 - re-measure and record.** Before/after by month and by sector, into
TECHLOG. If a sector barely moves, ask whether the data is present but
UNLABELLED before going to find more of it: in 2026-07, 96% of US rows carried
no industry (72% of job volume), so the by-industry view under-reported reality
far more than collection did.

**What this loop can NEVER close (stop trying):**
- Receiptless categories (buyouts, contract loss, bankruptcy, federal/DOGE) -
  the announcement survey gets these by ASKING employers; we require a document.
- Announcement-vs-effective date basis - a definitional difference, not a gap.
- Employers who withhold headcounts. In H1 2026 media, only one US event had a
  public number; the rest deliberately withheld. That cell cannot go green.

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
