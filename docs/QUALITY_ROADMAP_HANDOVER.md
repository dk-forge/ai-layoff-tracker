# Quality roadmap handover

Last updated: 2026-07-18 (plugin 2.18.28 adds source-linked January–June 2026 monthly and cumulative Challenger reconciliation history, keeps the announcement reference month separate from report-publication month, and treats an expected coverage gap as a visible alert rather than a repository failure; source/authentication/parse/write errors remain failures and a manual threshold gate remains available. Plugin 2.18.27 adds a copyable US national/state widget builder, frozen quarterly JSON/CSV appendices, a discovery-only OpenDART metadata client, and the recall publication independence gate; 2.18.26 corrects public failed/running collector wording so an unavailable query is never displayed as “0 found”; 2.18.25 fixes the first quarterly report page render before publication hand-off; 2.18.24 integrates the guarded company-directory, immutable quarterly-report and separate WARN-transparency foundations; 2.18.23 adds public 7/30/90-day collector-run history windows; 2.18.22 makes the ledger self-heal an FTP schema-upload race and makes manual catch-ups fail loudly on a health-write failure; 2.18.21 adds the ledger; 2.18.20 expands bounded, duplicate-safe NewsAPI discovery with a separate AI/automation announcement query; the EDINET discovery-only metadata client, Companies House identity foundation and recall draft are documented; evidence-hash backfill runs twice daily at 1,000). This is the continuation brief for the AI Layoff
Tracker quality, transparency and research-product roadmap. Read
`ARCHITECTURE.md`, `TECHLOG.md` and `RUNBOOK.md` first; this document records
the active programme and its non-negotiable safeguards.

## Product standard

The tracker aims to be a globally useful, source-linked research database. It
must never claim complete worldwide coverage or alter totals to imitate
Challenger, Gray & Christmas. Challenger is the US announcement benchmark—not
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
  Challenger comparator and rotates its result page daily, so unreadable
  sources cannot starve smaller candidates. This is a priority order only:
  domicile, announcement date and AI-primary status still require exact source
  evidence. Manual runs can select 1–50 deliberately.
- First manual run `29563662072` succeeded: checked 10, enriched 3, unsupported
  or unreadable 7. A Moneycontrol page returned HTTP 403; this stays visible as
  inaccessible evidence and must not be bypassed.

### Benchmark rule

`railway/challenger_reconcile.py` now passes `date_basis=announcement` to the
strict US-employer/AI-primary/announcement query. Rows without an exact
source-supported public announcement date are excluded; never substitute their
effective layoff date. The strict metric can legitimately be zero while
enrichment is still early. That is an honest coverage signal, not a reason to
inflate it.

The initial retained June 2026 record reports 101,743 YTD AI-attributed cuts;
the strict tracker comparator is 0 while announcement-date/domicile enrichment
is early. Plugin 2.18.28 backfills the official January–June 2026 reference
months (7,624; 4,680; 15,341; 21,490; 38,579; 14,029) and their retained YTD
figures, each linked to the original Challenger release. The scheduled worker
adds the next official feed item automatically. It records the same-month and
cumulative strict query URLs, figures and coverage gaps. A large gap is a
visible `coverage_alert`, not a failed processing job; authentication, fetch,
parse and record-write errors still fail loudly. An optional manual
`fail_on_gap` workflow input preserves the old threshold-gate behavior when an
operator deliberately needs CI enforcement.

## Active and pending work

1. **Finish context enrichment and maintain the monthly Challenger panel.**
   - Persisted reconciliation records live at
     `GET /blog/wp-json/layoffs/v1/benchmarks/challenger` and on the tracker
     page. New records retain the official report month, strict qualifying
     figure, official report URL and a coverage gap—never an "accuracy" claim.
   - Do not display a percentage as “accuracy” or copy Challenger's total.
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
python3 -m py_compile railway/extractor.py railway/enrich_context.py railway/challenger_reconcile.py
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
