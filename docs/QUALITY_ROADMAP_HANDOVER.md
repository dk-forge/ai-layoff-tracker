# Quality roadmap handover

Last updated: 2026-07-20 (plugin 2.19.68). Read this block first if
you are a new agent (Codex or otherwise) taking over. The authoritative
real-time record is `git log` (every change is one commit with a detailed
message + a version bump); this block is the human summary.

## 2026-07-20 session (2.19.44 → 2.19.68) — SHIPPED + LIVE

**Reports & UX.** Report build-out: weekly (`?period=YYYY-Www`), quarterly
(`?period=YYYY-Qn`), Year-in-Review, archive index (`?view=archive`),
prev/next nav, two-box headline (Overall verified + AI-attributed + % of
total), PDF (print CSS) + PNG (lazy html2canvas) export, New York/ET
timestamps. ALL competitor comparison removed from reports (ours-only).
Share-per-chart (deep link reproducing filters) + Embed-per-chart
(frame-safe `?alt_chart_embed` route; never frames the tracker, per the
anti-clickjacking rule). Map uncapped (`map_states`=60/`map_countries`=260 in
/aggregate, was top-24) + global-total caption, then two-layer red(AI)/blue(all)
bubbles + legend + click-to-drill. AI-broad reason-filter fix ("AI-linked
(broad)" checkbox now emits `ai_broad=1`, matching the card).

**Data coverage.** New state importers `railway/sources/warn_new_states.py`
(MS/WV/HI/NM), wired UN-GATED into `warn_import.py` (daily cron); validated
live 2026-07-20 (MS 129 / WV 24 / NM 11; HI 0 = image scans). MS+WV added to
`STATE_WARN_URL` (map 42→44). CA history backfill `railway/ca_backfill.py` +
`ca-backfill.yml` RAN LIVE (7,108 EDD annual-PDF notices; CA now ~21,900).
Closure filter (WARN importers tag reason `closure`; vocab in cpt.php/db.php +
JS filter). Weekly cross-check `railway/tracker_crosscheck.py` +
`tracker-crosscheck.yml` (Tuesdays) vs `railway/seed_data/crosscheck_checklist.csv`
— reports gaps + news-queries, never writes. Wayback archival
`railway/archive_sources.py` + `archive-sources.yml` (Mondays).
AR/WY/NH/MO documented as no-public-register (SEC+news only).

**Brand / SEO.** Competitor names (Challenger/layoffs.fyi/TrueUp) removed from
ALL public surfaces AND the whole repo (538→0). Benchmark subsystem renamed
`challenger`→`survey` across railway+workflows+WP (route `/benchmarks/survey`,
option `alt_survey_benchmarks`, files `survey_reconcile.py` +
`survey-reconcile.yml`); functional `challengergray.com` scrape URLs preserved.
Press page "Ready-to-use soundbites" library (grouped YTD + month + per-region;
cached `alt_press_sb_groups`), TOC, cleaned tables. Schema.org JSON-LD
(`alt_dataset_jsonld()` Dataset + FAQPage) on tracker/press/report for
AI-answer-engine citation. `/blog/llms.txt` route exists but a generic static
llms.txt wins — owner must add the tracker section to the root file. Sources
page: accurate gap table + hyperlinked outlets + dynamic counts.

## OPEN / IN FLIGHT (2026-07-20)
1. **d3 interactive map** — an agent is building a d3-geo proportional-symbol
   map (zoom/pan, hover, labels, click-to-drill, red/blue) to replace
   chartjs-chart-geo (no zoom). NOT deployed; lead reviews + deploys + verifies.
2. **State-enrichment for AI rows** (task_395dc30c, separate session) — root
   cause: 33,826 US AI-broad jobs are stateless (news/SEC name company+country,
   not state) + WARN carries no AI signal, so `state=CA` AI views badly
   undercount (shows 8k/0-strict). Fix: infer state from HQ registry / article
   text, conservative, dispatch-only backfill.

## OPTIONAL / NOT STARTED
- JSON-LD renders twice (WP shortcode quirk) — cosmetic; engines dedupe.
- OK importer (Salesforce portal, harder); HI stays 0 until HI publishes counts.
- Grow cross-check checklist; Europe-aggregate + weekly soundbite groups.

---


**2.19.14 (2026-07-19): role-impact extraction is live** (built as 2.18.87 on a task branch, shipped in 2.19.14). Fixed 10-category
role vocabulary (shared verbatim between `alt_role_categories()` and
`extractor.ROLE_CATEGORIES`), `role_categories`/`roles_evidence` columns,
keyed blank-fill-only `/enrich-roles` (never pins, never touches
counts/dates/sources/AI; `unknown` = "checked, source doesn't say" and is
excluded from every public surface), `roles_missing=1` query filter, daily
bounded `enrich-roles.yml` worker (04:23 UTC, batch 40, deadline 900s,
largest events first, reads ONLY already-stored row text — zero external
fetches), `/aggregate` `top_roles` + `totals.roles_known_entries/jobs`, and
the tracker's "Roles most impacted" card (AI-vs-all via the orange AI-share
segment; honest coverage subtitle). Keyword-derivable stated-roles rows fill
instantly at upsert and via the next `/cleanup` run — POST /cleanup once
after this deploy to backfill legacy stated-roles rows. Guard tests:
`railway/tests/test_role_enrichment_guards.py`.


you are a new agent (Codex or otherwise) taking over.

**2.19.7 (2026-07-19): reason-tag backfill is live.** A daily bounded job
(`railway/reason_backfill.py` + `reason-backfill.yml`, 04:40 UTC, health key
`reason_backfill`) tags the ~7,400 untagged non-WARN rows from their STORED
excerpts only, fixed vocabulary, written through /edit (rows get pinned;
WARN excluded because WARN notices state no reasons). ERM template rows map
deterministically from Eurofound's recorded restructuring type (~4,876
taggable; Closure/Bankruptcy/etc. honestly stay untagged); ~120 freeform news
rows go through DeepSeek with a local employer-quote gate on `ai_automation`.
At the default caps (400 deterministic + 40 model rows/day) the backlog
clears in ~2 weeks; watch the `reason_backfill` line on the health page and
the Reasons chart, which will grow a large ERM-fed Restructuring bar.

**2.18.72 (2026-07-19): employer-domicile basis is live.** `/aggregate` and
`/query` accept `country_basis=employer` (country filter matches evidenced
`employer_country`, falling back to job location ONLY where domicile is
blank) and `ai_broad=1` (row filter matching the ai_broad aggregate
definition). A curated registry of deterministic public HQ facts
(`railway/seed_data/employer_domicile.json`; ambiguous domiciles like
Airbus/Shell/Nordea-pre-2018/Schlumberger deliberately absent, plus offline
tests) backfilled 251 blank-domicile 'Multiple countries' rows via
`/enrich-context` (run 29695840127; `employer-domicile-backfill.yml` is
idempotent and re-runnable — re-run it after new multi-country events land,
or grow the registry). Live effect on US 2026: total 347,415 (job-location)
→ 406,692 employer basis (92% of the announcement survey's 443,604); AI-broad 57,156 (56%)
→ 114,278 (112% of the survey's 101,743). The tracker announcement-survey charts have
an orange "US-employer basis (survey-comparable)" line; the health
benchmark race table has employer-basis total/AI rows. The strict
comparator's gates are UNCHANGED; `/enrich-context` now takes an optional
`reason` so curated batches are honestly labelled in the corrections trail.
Candidate follow-up: the year-by-year benchmark history table still uses
job-location US cells; consider employer basis there once pre-2026 domicile
coverage is meaningful.

**IMMEDIATE NEXT ACTION (recorded 2026-07-19 ~01:15 UTC):** seed the four
named June events via the R9 curated path (`seed_data/ai_layoffs.json` +
`seed-ai.yml`; idempotent, exact quote + URL required): GitLab 350 [AI],
Rackspace 750 [AI], Rivian 300, SAS Institute 300 — verified URLs are in
docs/COVERAGE_GAP_CLOSURE_PLAN.md (2026-06 row). Nine BigQuery sweep
passes over the June windows all succeeded (429 era over) but their
headlines lack the title vocabulary, so sweeps won't catch them; seeding
is the designed mechanism. Also queue: re-supply the truncated Southern
Africa newspaper section; CourtListener wiring when the key lands.

**NEWEST (2026-07-19 00:18 UTC):** `GCP_BIGQUERY_CREDENTIALS_JSON` is live in
GitHub secrets and VERIFIED working (credential smoke run 29666728674:
dry-run against `gdelt-bq.gdeltv2.gkg_partitioned` authenticated, 0 bytes
billed). BUILT AND VERIFIED 2026-07-19 00:52 UTC: sources/gdelt_bq.py queries
gdelt-bq.gdeltv2.gkg_partitioned (SourceCommonName column — no V2 prefix;
LIMIT must be literal; partition filter + 30GB bytes cap). Policy: sweeps
set GDELT_PREFER_BQ=1; live pulls try the public API first and fall back
to BigQuery on abandonment. First verified run: 900 articles, no rate
limits (June 3-9 window that had failed 4x on 429s). Secret is in BOTH
Railway and GitHub. Also fixed: historical-news-sweep.yml had DUPLICATE
GDELT_QUERY_* env keys, which GitHub's parser rejects — this had broken
EVERY sweep dispatch; pyyaml does not catch duplicate keys, so validate
workflows with actionlint or grep for dupes. CourtListener key + LSE
RNS licence + Denmark Jobindsats key remain pending user actions (outreach
drafts in docs/outreach/).

**LATEST (2.18.33-2.18.35 + railway):**
- **FIRST RECALL BENCHMARK PUBLISHED: 91.67% (11/12), United States,
  June 2026** — via the new `recall-benchmark-publish.yml` workflow, which
  recomputes the sample from the committed manifest, refuses any manifest
  not `publication_reviewed_ready_to_retain`, and pins the public
  `reference_set_url` to the commit SHA. The three-actor chain (transcription
  reviewer → matching editor → publication reviewer) was executed by three
  distinct agent passes; the publication reviewer independently re-derived
  the positional selection from the sealed PDF (SHA-256 verified) and
  re-checked all 12 match decisions against the live API. The one no-match
  (HealthCare Partners Arcadia) is real and root-caused (see below).
- **HCP root cause (audit addendum has full detail):** CA WARN rows hash on
  company+effective_date+jobs+city+state, warn-scraper leaves CA city blank,
  and notice type is not a schema field — so two same-day 1-employee HCP
  notices (Arcadia Layoff vs Washington Blvd Closure) collapsed into one
  row, last-write-wins. Fix path is recorded in the addendum; it needs a
  hash-input change = dedup-hash migration (bulk-purge + re-import), so do
  NOT hot-patch it casually.
- **Rotating segmented discovery** (railway/sources/gdelt.py + newsapi.py):
  each run adds a few narrow country/state/industry/AI-phrase queries chosen
  by deterministic daily rotation (full matrix every ~6-9 days). Only the
  broad query is health-bearing. Env: GDELT_SEGMENT_QUERIES (default 4),
  NEWSAPI_SEGMENT_QUERIES (default 2), 0 disables.
- **TRUSTED_DOMAINS 207 → 240** with the four-region research sweep's papers
  of record (allowlist-only).
- **Brazil CVM discovery client** (railway/sources/cvm_br.py + offline-
  fixture tests): keyless, ODbL-attributed, discovery-only; NOT cron-wired
  yet — wire a health probe like edinet_jp/opendart_kr when promoting.
- **Mobile fixes (2.18.33/34):** minmax(0,1fr) grids (bare 1fr blowout was
  clipping the health page on iPhone), Easy-TOC suppressed on plugin
  surfaces via its filters + :has() CSS fallback, and plugin surfaces go
  full-viewport-width under 700px (theme padding stacked to ~220px content
  on a 375px phone).
- **Announcement-survey four-line comparison is live end-to-end** with plausibility
  floors on the fail-soft all-cuts parser (a YTD below its own month or a
  total under 5,000 stores null, never a wrong benchmark figure). Stored
  months now carry survey_total_jobs_month for Jan-Jun (YTD null for
  Jan-Mar where old wording defeats the parser — acceptable).
- **Gap-closure execution (late 2026-07-18):** R2+R8 corrections all
  EXECUTED and live-verified (Intuit 17→3,000 AI-denied; Meta Mar 100→700;
  Dow 3,700 contributing_cause + US domicile; Lucid merged; Oracle merged
  and converged on 21,000 — net −29,000 honesty correction). Three parser
  incidents fixed with regression tests: CT WARN dead parser
  (affected_company as count column), IL revised-count preference, extractor
  percent-of-workforce guard. Nationwide WARN purge-reload dispatched with
  the fixed parser. R4 outlet additions landed (16 trade/regional). R5
  historical sweep windows running sequentially (GDELT public-API 429s
  abandon some windows — re-run those windows later; each reports
  gdelt_historical health honestly). reclassify-legacy-ai ceiling raised to
  45 min (20 min cancelled batches >6). New `data-corrections.yml` executes
  reviewed keyed correction sequences (endpoint allowlist; the /add
  attach-branch full-row-overwrites unpinned fuzzy-matched rows — pin
  first). Deferred: Oracle 10-K report attach + verbatim Mar-31
  announcement evidence; Microsoft R10 policy call; R9 curated seeds.
- **User asks recorded:** segmented searches per country/state/industry
  must keep running (done — see rotation above); everything autonomous with
  zero manual steps; US first, then Europe, then Asia.

**2.18.32 — what shipped and why.**
1. *Company-directory autopilot.* Keyed POST `/company-directory/autopilot`
   auto-admits unmapped company keys with >=3 source-linked canonical events
   through the SAME `alt_company_directory_admit_mappings()` validator as
   manual review. Safety gates added after an adversarial multi-agent diff
   review CONFIRMED these defects pre-deploy (all fixed): (a) generic-name
   blocklist also matches in `alt_company_key` normalized space, so
   'Unknown Company'-style variants cannot slip past the exact-match list;
   (b) the display name must be the SINGLE agreed name across the qualifying
   canonical source-linked rows (prevents titling a page with the wrong
   employer when distinct companies share a normalized key); (c) unadmittable
   keys are parked as `review_status='pending'` directory rows so they stop
   occupying the ORDER-BY-supported candidate window forever (pending rows
   never render publicly); (d) `run_token` idempotency: a workflow gateway
   retry replays the stored response instead of admitting a second batch.
   Weekly cron: `.github/workflows/company-directory-autopilot.yml`
   (Tuesdays 14:20 UTC, dispatchable, passes `run_token: gh-<run_id>`).
2. *Company sitemap.* WP core sitemaps are DISABLED on production (the SEO
   plugin serves `/blog/sitemap_index.xml`; `/blog/wp-sitemap.xml` is 404),
   so a core sitemap provider would silently never render — the plugin now
   serves `/company-layoffs-sitemap.xml` itself (rewrite + template_redirect
   in `includes/company-directory.php`) and appends it to the active SEO
   plugin's index via BOTH `wpseo_sitemap_index` and
   `rank_math/sitemap/index` filters (same dual-hook pattern as the file's
   robots/canonical/title filters).
3. *Announcement-survey four-line comparison.* `survey_reconcile.py` now also
   parses the survey's headline TOTAL announced cuts (fail-soft: a parse
   miss prints a warning and stores null — the AI figures remain
   fail-loudly) and computes the strict announced-US tracker comparator
   without the AI gate (`strict_all` group). New nullable benchmark fields:
   `survey_total_jobs_month/ytd`,
   `tracker_announced_us_employer_jobs_month/ytd` (+ query URLs). The
   tracker page charts show four labeled series (Announcement-survey/AskTheRecruiter
   x AI/all-cuts, dashed = all-cuts pair) with a visible legend; the
   comparison table adds the all-cuts month columns. Monthly cron updates
   everything automatically; a manual `survey-reconcile.yml` dispatch
   backfills the new fields for already-recorded months.
4. */aggregate* monthly `series` rows now carry `verified_jobs`,
   `announced_jobs`, `ai_verified_jobs`, `ai_announced_jobs` alongside the
   legacy `jobs`/`ai_jobs`. Jobs-per-month chart plots Verified with a
   dashed Announced line; the cumulative AI chart plots verified-AI vs
   announced-AI lines. Stat cards: the share card reads
   "<value>% — of Verified job cuts are AI-attributed"; both announced
   cards say "dated in the selected period" (announced plans carry future
   effective dates, so a year filter includes future-dated plans for that
   year).
5. *Evidence-hash backlog: DONE.* `remaining` hit 0 on 2026-07-18 after
   sequential bounded runs (37,424 -> 0 in one day). The Features card is
   now Active. `evidence-hash-backfill.yml` retries transient gateway
   errors (000/502/503/504/520/521/522/524, 4 attempts, 45s) before failing
   loudly — the shared host intermittently 522s even when the bounded write
   landed; both endpoints process "whatever is still pending" so re-POST is
   safe there (the autopilot endpoint instead uses run_token, because it is
   NOT naturally idempotent).
6. *Context enrichment:* 12 manual batch-9 passes all succeeded today on
   top of the daily job; announcement-date evidence is what moves the
   strict announcement-survey comparator (Coinbase 700 already moved the diagnostic
   YTD from 0 -> 700).

**User priorities (2026-07-18, explicit):** US data quality first — target
is the strict comparator within 5-10% of the announcement survey — then worldwide;
regional order after the US: Europe (all countries), then Asia, then the
rest. Everything must run unattended: collectors (Railway 2x daily), WARN
daily, autopilot weekly, announcement-survey reconciliation monthly, quarterly report, bounded
hash/enrichment jobs daily, years/facets/widget dropdowns all derive from
data — no manual steps. The user must never need to remind or trigger
anything.

**Why June 2026 US shows 0 AI-attributed:** genuinely no June-dated US
event carries an explicit AI attribution yet (the 13 AI+US 2026 events date
to Jan/Feb/Mar/Apr/May/Jul). The announcement survey's June AI figure is 14,029 — that
delta is the recall+classification gap the enrichment/classification/recall
workstreams exist to close; do not fabricate attributions to fill it.

Earlier same day, plugin 2.18.31: the public stats bar is two
rows of four cards — Verified, Explicitly AI-attributed, Announced, and the
new Announced-AI number (`/aggregate` now returns
`ai_announced_jobs`/`ai_announced_entries`), plus AI-share-of-Verified,
Companies, Industries, Countries; each subset card states which parent
number it belongs to and the event-count sublines were removed. The health
page labels every collector with its country/region and collection method
in both tables. `cron.py` runs health-visible discovery probes for Japan
EDINET (`edinet_jp`) and South Korea OpenDART (`opendart_kr`) — official
filing lists only, nothing ingested, explicitly not a coverage claim — and
`warn_import.py` now reports `warn_us` source health so the largest US
source is visible in collector operations. Earlier same day, plugin 2.18.30: the company directory is live —
a keyed `/company-directory` writer with a public GET listing and the
`company-directory.yml` admission workflow enforce the two-event
source-linked threshold server-side, and the first six reviewed mappings
(Microsoft, Meta, Meta Platforms, Intel, Amazon, Salesforce) render at
`/company-layoffs/{slug}/`; the first five reviewed company IR feeds (Intel,
SAP, Cisco, Salesforce, Micron) are admitted through the versioned
`railway/reviewed_feeds.json` registry with per-feed failure isolation;
GDELT pacing is patient (5s delay, five attempts, 40s base backoff) to
convert 429 degraded runs into ok runs without extra request volume; the
CA June 2026 recall sample passed its independent transcription review with
a rule-conformance correction, and the legacy evidence-hash backlog is being
finished through sequential bounded runs. Earlier: plugin 2.18.28 adds source-linked January–June 2026 monthly and cumulative announcement-survey reconciliation history, keeps the announcement reference month separate from report-publication month, and treats an expected coverage gap as a visible alert rather than a repository failure; source/authentication/parse/write errors remain failures and a manual threshold gate remains available. Plugin 2.18.27 adds a copyable US national/state widget builder, frozen quarterly JSON/CSV appendices, a discovery-only OpenDART metadata client, and the recall publication independence gate; 2.18.26 corrects public failed/running collector wording so an unavailable query is never displayed as “0 found”; 2.18.25 fixes the first quarterly report page render before publication hand-off; 2.18.24 integrates the guarded company-directory, immutable quarterly-report and separate WARN-transparency foundations; 2.18.23 adds public 7/30/90-day collector-run history windows; 2.18.22 makes the ledger self-heal an FTP schema-upload race and makes manual catch-ups fail loudly on a health-write failure; 2.18.21 adds the ledger; 2.18.20 expands bounded, duplicate-safe NewsAPI discovery with a separate AI/automation announcement query; the EDINET discovery-only metadata client, Companies House identity foundation and recall draft are documented; evidence-hash backfill runs twice daily at 1,000). This is the continuation brief for the AI Layoff
Tracker quality, transparency and research-product roadmap. Read
`ARCHITECTURE.md`, `TECHLOG.md` and `RUNBOOK.md` first; this document records
the active programme and its non-negotiable safeguards.

## Product standard

The tracker aims to be a globally useful, source-linked research database. It
must never claim complete worldwide coverage or alter totals to imitate
the announcement survey. The announcement survey is the US announcement benchmark—not
a global gold standard—and the public tracker must make scope differences
visible.

Every counted event needs a source. A canonical event may retain several
source reports. Deduplication must merge reports, never discard them. Model
output is evidence-assisted, not an independent fact check: exact source
quotes, fixed vocabularies, deterministic date/count guards, and source links
remain the publication standard.

## Live, verified foundation

- Public operations page: `/blog/ai-layoff-tracker/ai-tracker-health/` renders
  current source health, safe last-attempt detail, static cadence/scope,
  integrity, evidence backlog, review queue, workstreams, benchmark state and
  a plain-language Features list. The Features list labels released, in-progress,
  pending-review and planned capabilities; it must never replace the live
  collector/error status above it or imply global completeness.
  It reads public APIs dynamically. Plugin 2.18.21 begins an append-only
  collector-run ledger (time, source, status, raw candidate volume and safe
  detail); it never reconstructs legacy activity or treats raw candidates as
  accepted events.
  The permitted Eurofound European Restructuring Monitor (ERM) import also
  writes its own `running`, `ok`, or `degraded` health state. It is an
  announcement-stage, source-linked EU27+Norway (and historical UK) source,
  with Eurofound factsheet links and attribution—not a claim of complete
  European coverage.

- Plugin version **2.18.28** is the next `main` deployment. Each
  deployment passes a pre-upload PHP syntax lint and a post-upload cache-busted
  public tracker API verification. The retained-excerpt hash backfill is live;
  live integrity is the source of truth rather than this narrative snapshot.
- Public quality endpoint:
  `GET /blog/wp-json/layoffs/v1/quality-status`.
  It exposes dataset revision, disclosed corrections, source health, canonical
  integrity and openly labelled workstream states.
- Integrity migration is complete: **43,892 canonical events** and **43,974
  retained source reports** at the latest verification. Bulk imports
  now attach canonical events immediately; if a run lands during the prior
  deployment's migration interval, run/await canonical-event migration before
  calling the graph complete.
- Daily deep dedupe preserves every report on the surviving canonical event;
  the cluster queue rotates so small duplicate pairs cannot starve behind large
  clusters.
- Mobile page-overflow containment is deployed; tables alone may scroll
  horizontally on narrow screens.
- Legacy AI-evidence reassessment runs daily with a five-record scheduled batch
  and a 15-minute between-row deadline after a later 10-record pass reached
  GitHub Actions' 20-minute ceiling. A bounded partial pass resumes safely;
  a fully unreadable attempted batch still fails visibly.
- Historical GDELT recovery is publicly degraded on external HTTP 429s. Its
  seven-day cursor advances only after a successful window and honors bounded
  Retry-After/backoff delays, so a rate-limited window is retried rather than
  skipped. A known upstream 429 completes the GitHub workflow as a visible
  deferred condition; code, authentication and write failures still fail
  loudly. Do not conceal the condition or use prohibited scraping.

## Newly live: evidence-only context enrichment

Commit `4290ab6` added this layer; `a698c06`/`ce20951` made announcement-date
benchmarking live.

- Schema fields: `announcement_date`, `announcement_evidence`,
  `employer_country`, and `employer_country_evidence`.
- Ingest only keeps announcement date/domicile if an exact source quote is
  present in the supplied source passage.
- `POST /enrich-context` only fills **blank** fields and requires at least a
  non-trivial evidence quote. It cannot update job count, effective layoff
  date, stage, source URL, or AI classification.
- `railway/enrich_context.py` re-fetches linked pages, calls the narrow context
  prompt, validates returned quotes locally, and reports health as
  `context_enrichment`.
- `.github/workflows/enrich-context.yml` runs daily at 03:41 UTC. Its scheduled
  batch is **5** because the first ten-record smoke test took 19m22s. It now
  prioritises announced, AI-tagged US job-location candidates by count for the
  announcement-survey comparator and rotates its result page daily, so unreadable
  sources cannot starve smaller candidates. This is a priority order only:
  domicile, announcement date and AI-primary status still require exact source
  evidence. Manual runs can select 1–50 deliberately.
- First manual run `29563662072` succeeded: checked 10, enriched 3, unsupported
  or unreadable 7. A Moneycontrol page returned HTTP 403; this stays visible as
  inaccessible evidence and must not be bypassed.

### Benchmark rule

`railway/survey_reconcile.py` now passes `date_basis=announcement` to the
strict US-employer/AI-primary/announcement query. Rows without an exact
source-supported public announcement date are excluded; never substitute their
effective layoff date. The strict metric can legitimately be zero while
enrichment is still early. That is an honest coverage signal, not a reason to
inflate it.

The initial retained June 2026 record reports 101,743 YTD AI-attributed cuts;
the strict tracker comparator is 0 while announcement-date/domicile enrichment
is early. Plugin 2.18.28 backfills the official January–June 2026 reference
months (7,624; 4,680; 15,341; 21,490; 38,579; 14,029) and their retained YTD
figures, each linked to the original announcement-survey release. The scheduled worker
adds the next official feed item automatically. It records the same-month and
cumulative strict query URLs, figures and coverage gaps. A large gap is a
visible `coverage_alert`, not a failed processing job; authentication, fetch,
parse and record-write errors still fail loudly. An optional manual
`fail_on_gap` workflow input preserves the old threshold-gate behavior when an
operator deliberately needs CI enforcement.

## Active and pending work

1. **Finish context enrichment and maintain the monthly announcement-survey panel.**
   - Persisted reconciliation records live at
     `GET /blog/wp-json/layoffs/v1/benchmarks/survey` and on the tracker
     page. New records retain the official report month, strict qualifying
     figure, official report URL and a coverage gap—never an "accuracy" claim.
   - Do not display a percentage as “accuracy” or copy the announcement survey's total.
   - The current monthly records are public through the endpoint, tracker-page
     monthly and cumulative charts/table, and health page. The worker retains
     the real announcement reference month separately from the later report
     publication month, so comparisons cannot be visually shifted a month.
     The workflow artifact remains the detailed operational audit trail.
   - The endpoint returns one authoritative retained record per official
     report month. Earlier setup entries without `report_month` remain stored
     for audit but cannot appear as a misleading duplicate publication.
   - NewsAPI now makes two bounded, URL-deduplicated queries per collection:
     broad layoff coverage plus a separate AI/automation announcement query.
     It remains licensed-news discovery, not a direct company announcement
     census; extraction and source-evidence rules remain unchanged.

2. **Measured recall by country/period.**
   - Public protocol: `docs/RECALL_BENCHMARK_PROTOCOL.md`; endpoint:
     `GET /blog/wp-json/layoffs/v1/benchmarks/recall`. The protected writer
     rejects any record without a public reference-set URL, single country and
     closed period, stated basis, and bounded numerator/denominator.
   - Never claim country completeness. The historical 5/35 (14.3%) June–July
     baseline predates the later source and deduplication changes, so it is
     intentionally not published as current; remeasure from an independent,
     documented reference set first.
   - California WARN June 2026 sample status (2026-07-18): the independent
     transcription review is complete — every field of the twelve rows was
     verified against the official EDD PDF (hash-matched), and a selection
     error at three page boundaries (Leggett & Platt, Uber Technologies,
     Ballast Point omitted despite being fully contained rows) was corrected
     to conform to the pre-committed positional rule before any match
     decision. Remaining gates: the canonical matching pass and the
     independent publication review, by a reviewer distinct from the
     transcription pass; the earlier audit's candidate table is partially
     stale and is context only. No numerator/denominator exists yet.

3. **High-impact review queue and durable source evidence.**
   - A live, read-only triage queue is available at
     `GET /blog/wp-json/layoffs/v1/review-queue`. It identifies very large
     (5,000+), source-quoted AI-primary and multi-country events, exposes each
     record's retained-source count and makes no automatic editorial change.
     Review remains a human decision and any correction must preserve sources
     and enter the corrections trail.
   - `announcement-lifecycle-review.yml` runs daily at 17:15 UTC and can be
     run manually. It reads the deliberately narrow public candidate queue and
     writes a bounded count plus its safeguards to the Actions summary. It has
     no credentials and no write path: candidate presence is never an automatic
     merge decision or a reason to alter totals or source reports.
   - New source reports carry SHA-256 hashes of their retained evidence excerpt.
     Twice-daily `evidence-hash-backfill.yml` backfills a bounded 1,000 legacy
     hashes per run from the already-retained excerpt only. A controlled
     production batch completed 1,000 in about 1.4 seconds on 2026-07-17; the
     two schedules have a concurrency guard so runs never overlap. The workflow validates its
     returned progress payload and writes the updated/remaining counts to the
     GitHub Actions summary; progress is public in `/integrity-status`.
     Preserve source URL, retained excerpt/evidence and content hash/snapshot
     metadata where permitted. A hash of a short excerpt is not a source-page
     archive; label it accurately.
   - `/integrity-status` now separately reports canonical events with and
     without at least one linked retained-source report. Do not use the raw
     source-report count to imply every event is cited. The bounded link
     backfill can restore a missing event-graph link only from the existing
     canonical-row URL; it never fetches a source or changes a fact. The
     endpoint exposes up to five already-public canonical-row samples for a
     remaining gap so it can be corrected from evidence rather than guessed.
     If a sampled row is structurally blank with no company, date or source,
     remove it through the correction workflow and clean its orphaned event
     graph; do not invent missing evidence.

4. **Dataset release ledger and monthly change report.**
   - Public `GET /blog/wp-json/layoffs/v1/dataset-releases` snapshots begin at
     ledger inception and record revision plus canonical rows/events/reports.
     It deliberately does not invent historical addition counts; corrections,
     removals and merges remain disclosed through `/quality-status`.
   - Plugin 2.18.10 adds a rolling public change panel to the health page. It
     combines the release ledger window with the real rolling 30-day correction
     trail and current source-health state. It calls total movement “net change”
     rather than claiming it is a count of gross additions.

5. **Free, permitted source expansion.**
   - Maintain `docs/OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md` and
     `railway/source_registry.py`.
   - Canada SEDAR+, UK RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews, SGXNet, SENS,
     DART and TASE are candidates, not live connectors. Promote only after a
     stable permitted interface, fixture tests, evidence retention and source
     health reporting exist.
   - No paid subscriptions are planned. Do not sign up for, scrape around,
     or misrepresent licensed/permissioned sources. Reviewed public company IR
     RSS/Atom feeds are the preferred expansion path.
   - **Credential status, 2026-07-17:** the owner reports these free keys are
     present in both GitHub Actions secrets and Railway environment variables:
     Japan EDINET (`EDINET_API_KEY_JP`), South Korea OpenDART
     (`OPENDART_API_KEY_KR`), and UK Companies House
     (`COMPANIES_HOUSE_API_KEY_UK`). Never record, expose or request their
     values in chat, code, commits, logs, fixtures or documentation.
   - EDINET registration can reject the login flow with a Japanese
     "non-standard operation" message if pop-ups/cookies are blocked or a
     bookmarked B2C page is used. Start only from
     `https://api.edinet-fsa.go.jp/api/auth/index.aspx?mode=1` in a fresh
     browser session; the owner resolved this by allowing pop-ups.
   - Do not activate a collector merely because a key exists: each needs
     fixtures, rate/error handling, source retention and a source-health entry
     first. EDINET/OpenDART are future official-disclosure connectors;
     Companies House is employer-identity enrichment, not a UK layoff feed.
   - `.github/workflows/official-connector-credential-smoke.yml` is a manual,
     read-only credential check. It queries EDINET list metadata, OpenDART list
     status and one Companies House record without downloading/publishing
     filings or logging secret values. Passing it proves access only, not that
     a connector is live or permitted for automated data reuse.
   - Credential smoke run `29605524613` passed on 2026-07-17 against the three
     configured GitHub secrets. This validates read-only access only; no filing
     was stored, published or added to source-health coverage.
   - Highest no-credential expansion is a versioned registry of reviewed,
     company-owned newsroom/IR RSS or Atom feeds. Do not treat generic wire
     feeds as official, and document terms/domain ownership before admission.
   - The reviewed-feed collector now fails closed: each configured entry must
     have an HTTPS feed URL on its recorded owner domain, an HTTPS terms URL,
     and a manual review date. With no reviewed entries, `press_releases` is
     visibly degraded with an explicit no-registry detail rather than being
     presented as a live zero-result official feed. This is an admission gate,
     not a new national connector or coverage claim.
   - A bounded Companies House identity adapter exists for an already-known
     exact company number. It returns the official public profile URL and a
     separately labelled registered-office country candidate only. It has no
     name search, event-write or automatic domicile/job-location enrichment
     path, and remains a review aid rather than a live collector.
   - An inactive EDINET daily-document-list client exists at
     `railway/sources/edinet.py`. It uses the official metadata endpoint only,
     never downloads a filing, writes an event or changes source health, and
     advances a future cursor only after a complete matching daily result.
     Before activation, add a persisted replay cursor, Japanese-language
     document/evidence fixtures, an evidence-only body stage and health
     reporting. It remains `discovery_only` until then.

6. **Research/distribution products, after core data work.**
   - A minimal, noindex iframe widget foundation now exists at
     `/blog/?alt_tracker_widget=1&tracker_year=YYYY&state=CA`. It is intentionally
     limited to the US national or state view and uses the public aggregate
     endpoint. It links to the exact filtered tracker view and explicitly says
     it is source-linked rather than complete. Publishers choose whether and
     how to add a separate attribution link; do not promise a backlink or
     create metro variants from this foundation. The public health page now
     provides a copyable, scope-validated iframe snippet; it emits iframe code
     only and leaves any optional external attribution attributes to publishers.
     Do not begin metro widgets
     until metro geography is reliable. Link each widget to its exact filtered
     tracker view and methodology; publishers control backlink attributes.
   - Company-directory foundation: `/blog/company-layoffs/{slug}/` resolves
     only through the reviewed `alt_company_directory` identity registry; it
     never turns a freeform company name or a raw dedup key into a public page.
     The registry initially has no published mappings. A page requires retained
     source-linked canonical events and shows every retained source link. Only
     two-or-more-event reviewed records may be indexed; reviewed one-event
     records are `noindex,follow`, and unknown/pending/ambiguous slugs are 404.
     Avoid generated narrative, inferred identity/industry/geography, and thin
     SEO prose. The route is deliberately uncached at page level; its bounded
     data cache is salted by `alt_data_ver` so writes invalidate it safely.
   - Quarterly-report foundation: `POST /reports/quarterly` accepts only a
     calendar-quarter id and server-generates an immutable snapshot using the
     tracker aggregate path. It retains query manifest, verified/announced
     separation, source health, integrity and dataset revision. The public
     HTML report is accessible and printable; it compares frozen and live
     revision numbers rather than rewriting history. A PDF/data appendix is a
     later rendering convenience, not the source of record.
   - `.github/workflows/quarterly-report.yml` runs after each completed
     quarter, and may be manually invoked. It submits no totals or prose; a
     degraded source remains a visible coverage gap in the stored snapshot.
   - The report page exposes a readable JSON appendix and downloadable JSON/CSV
     appendices. They are shaped exclusively from the immutable stored snapshot
     (aggregate tables and time series only), never regenerated from current
     data and never presented as a raw event export.
     It may publish on AskTheRecruiter automatically; third-party syndication
     requires permission.
   - WARN transparency is a separate future dataset. Never call an employer a
     WARN violator without an adjudicated court/settlement source. Use labels
     such as `notice recorded: 60+ days`, `short notice: exception stated`,
     `short notice: unresolved`, and `court-adjudicated WARN violation`.
     Never add these indicators to layoff or AI totals.

## Operational commands

```bash
# Relevant tests (PHP is not installed locally)
python3 -m unittest railway/tests/test_extractor_guards.py
python3 -m py_compile railway/extractor.py railway/enrich_context.py railway/survey_reconcile.py
node --check wordpress-plugin/ai-layoff-tracker/assets/layoffs.js
git diff --check

# Live checks (always use this UA; host blocks generic Python requests)
curl -sS -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' \
  'https://asktherecruiter.com/blog/wp-json/layoffs/v1/quality-status?cb=1'
curl -sS -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' \
  'https://asktherecruiter.com/blog/wp-json/layoffs/v1/integrity-status?cb=1'
```

`WP_SITE_URL` is always `https://asktherecruiter.com/blog`. Every plugin deploy
must increment both the plugin header `Version:` and `ALT_VERSION`; FTPS bypasses
normal WordPress update hooks, so the version bump triggers schema/caching
initialization. Preserve the user-owned untracked `AGENTS.md`.

## User authority and communication

The user authorized repo-controlled implementation, commits, pushes and live
deployment, and does not want paid subscriptions. Do not request routine
check-ins. Notify only for material deployments, operational failures,
external permission/licensing requirements, or a decision that materially
changes methodology. Be candid: ongoing monitoring is automated; unbuilt
roadmap items are not already “running” merely because they are in this file.

## Work-backwards audit protocol (first run 2026-07-19 — repeat monthly)

An 8-agent web-research sweep compiles the largest publicly reported layoff
events of the year (AI and general, by region/sector slice) and checks every
one against the public /query API, returning missing / present-but-not-AI /
count-differs lists. First run: 91 events checked, 21 announcement-stage
events seeded via the data-corrections workflow, 2 AI reclassifications
(employer-explicit quotes only). Key structural finding: WARN captures
execution slices while announcement-level corporate events go missing —
GDELT phrasing favors "layoff" over earnings-call "restructuring" language.
Follow-ups in priority order: (1) Oregon WARN collector (Intel 2,392 absent),
(2) add earnings-call/restructuring phrasings to the GDELT segment rotation,
(3) re-run this audit monthly from the scheduled session and seed misses the
same way (script + step-builder pattern in the 2026-07-19 session).

## Aggregator diff backlog (2026-07-19 browser sweep, owner-authorized)

A browser agent read a technology-sector tracker (full Airtable incl. their per-row AI flag),
its AI-layoffs view (all 99 of their 2026 AI events) and a second sector tracker,
then checked 150 entries against /query: 23 present, 16 count-differs, 111
missing (98 companies absent entirely). Their headline numbers for calibration:
the first sector tracker's 2026 tech cuts 121,326 (AI: 95,829); the second sector tracker's 2026: 167,720.
Structural causes and fixes shipped same day: international tech press added
to the allowlist (inc42, techinasia, skift; calcalistech/globes/betakit were
already in), 19 sector trade outlets, 8 corporate-announcement GDELT segments,
and the ai_linked broad tier. REMAINING BACKLOG for scheduled sessions:
verify-at-source and seed the largest absentees (TikTok Dublin 300 AI,
Thomson Reuters 500, CorroHealth 800, Wix 1000, ZoomInfo 600, Autodesk 1000,
OpenText 400, Tokopedia 450, Paytm 400, Groupon 400, MyHeritage 75-vs-500
count conflict, and the ~85 smaller companies in the agent's diff_final.json).
POLICY REMINDER: their rows are leads only; every seed must cite the
underlying named-outlet article, never the aggregator.

## Verified benchmark histories (researched 2026-07-19, on the health page)

Announcement-survey annual US totals from their own year-end reports: 2019: 592,556 ·
2020: 2,304,755 (COVID) · 2021: 321,970 · 2022: 363,824 · 2023: 721,677 (AI
4,247; AI reason code began May 2023) · 2024: 761,358 (AI 12,742 — their
printed Sept-2024 YTD, confirmed exact by Dec-2025 cumulative arithmetic:
71,825 - 54,836 - 4,247 = 12,742) · 2025: 1,206,374 (AI 54,836).
A technology-sector tracker (worldwide tech, began Mar 2020, per their year pages): 2020:
80,998 · 2021: 15,823 · 2022: 165,269 · 2023: 265,660 · 2024: 152,922 ·
2025: 122,606 · 2026 snapshot 2026-07-18: 121,326 (AI 95,829).
These render in health.js BENCH_HISTORY with live ATR columns; update the
constants when re-verified, with the as-of date.

## Historical-year backfill (added 2026-07-19; 2025 EXECUTED same day)

**2025 run complete (see TECHLOG audit entry for full detail).** Outcome:
US 2025 moved 726,686 → 670,658 (55.6% of the announcement survey). The old 60% was
inflated: ~152K of double counting (UPS ×2 + superseded April stage, HHS ×4
+ its own sub-slices, IRS ×2, Microsoft program overlap, Intel wrong-year
phantom, Recruit ×3, more) was merged/corrected, and 34 verified missing
events were seeded (+97,582 US, incl. Rite Aid 24.5K, Joann 19K, VA 30K,
SSA 7K). ai_broad US 2025 is now 52,259 = 95% of the announcement survey's 54,836 (the
old 128,759/235% rode on dup rows). 14 AI reclassifications applied
(Salesforce primary_cause with the Benioff "agentic layer" verbatim;
Microsoft/Meta-600/IBM honestly downgraded to ai_linked).

**Key methodology finding: 90% of the announcement survey's 2025 total is not honestly
reachable.** ~250–300K of their total is voluntary federal separations
(75K deferred-resignation acceptances + attrition-heavy agency programs).
The DRP 75K is deliberately NOT seeded: those acceptances are already
inside seeded agency totals (VA 30K quotes its attrition/DRP composition).
Treat the residual gap as a documented composition difference, like the
AI-column note below.

**PENDING owner action:** dispatch trash-entries.yml for phantom rows
70461 (Meta "8,000" lawsuit-allegation extraction, AI-flagged), 70769
(Benzinga BLS commentary "5,000"), 70083 (DOGE 10K cross-agency aggregate
overlapping VA/NOAA/IRS rows) → a further −23,000 honesty correction.
The in-session dispatch was permission-blocked.

**Next: 2024 (63% row), same protocol.** Known 2024 leads from this run:
Intel 2024 keeper is row 301 (its Dec-2024 TheHindu-newsletter dup 70471
was already merged); watch for the same announcement-survey-roundup-article
extraction pattern that duplicated UPS. ERM-vs-US-news group overlaps
(Intel 24.5K ERM, Microsoft 9K ERM Jul-2025, TCS) remain documented skips
per the Telia/Nissan precedent — a cross-source group-event reconciler is
the eventual fix, not row deletion.

## Roles-impacted chart: required disclaimer (2026-07-19)

Role-level data exists ONLY where the source stated it. The chart MUST carry
a short, plain caveat so readers never assume it covers every counted job.
Required wording (or equivalent, keep it one line): "Only cuts whose reports
named the affected roles — a sample of the total, not a breakdown of it."

## Roles-impacted chart placement (2026-07-19)

Place the roles chart in the AI story cluster: directly after "AI intensity
by industry" and before "Cumulative AI-attributed cuts", so the reading order
is: how much is AI (share trend), which industries (intensity), WHICH JOBS
(roles), then the running total. Card sub must carry the sample disclaimer
already specified. No em dashes in its copy.

## Roles in the daily narrative (2026-07-19, owner request)

Once the roles backfill ships, the narrative headline box adds the roles
dimension: append to the '{year} so far' row (or as its own row) a short
'most-affected roles: X · Y' fragment computed from the same stage=verified
aggregates, only when role coverage in the view is meaningful (>=20% of jobs
tagged); otherwise omit the fragment entirely. Same plain-language style,
no em dashes, and the roles chart's sample disclaimer applies.

## AI exposure vs reality page (spec'd 2026-07-19, blocked on roles landing)

Separate analysis page at /ai-layoff-tracker/ai-exposure/ comparing predicted
occupation-level AI exposure (published O*NET-derived exposure scores such as
the Felten/Raj/Seamans AIOE dataset, plus BLS 10-year employment projections)
against our OBSERVED role-level cut shares from the roles extraction. Hard
rules: projections NEVER enter the tracker's stat cards or totals; the page
carries a prominent projections-vs-observed disclaimer; sources attributed
with as-of dates; data stored as versioned JSON refreshed annually (both
sources update yearly). The unique output: where reality diverges from the
exposure predictions. Task chip exists (owner-startable).
