# Quality roadmap handover

Last updated: 2026-07-17 (operations verified after the 2.18.1 deploy). This is the continuation brief for the AI Layoff
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
  integrity, evidence backlog, review queue, workstreams and benchmark state.
  It reads public APIs dynamically; historical per-run telemetry begins only
  once the append-only run ledger is deployed, never reconstructed from legacy
  rows.

- Plugin version **2.18.1** is live from commit `2877251` (deployment run
  `29614434464`). That deployment passed a pre-upload PHP syntax lint and a
  post-upload cache-busted public tracker API verification. The retained-excerpt
  hash backfill is live; integrity after
  the latest successful deep dedupe is 43,892 canonical rows/events and 43,971
  retained source reports, with no migration backlog.
- Public quality endpoint:
  `GET /blog/wp-json/layoffs/v1/quality-status`.
  It exposes dataset revision, disclosed corrections, source health, canonical
  integrity and openly labelled workstream states.
- Integrity migration is complete: **43,892 canonical events** and **43,971
  retained source reports** at the latest verification. Bulk imports
  now attach canonical events immediately; if a run lands during the prior
  deployment's migration interval, run/await canonical-event migration before
  calling the graph complete.
- Daily deep dedupe preserves every report on the surviving canonical event;
  the cluster queue rotates so small duplicate pairs cannot starve behind large
  clusters.
- Mobile page-overflow containment is deployed; tables alone may scroll
  horizontally on narrow screens.
- Legacy AI-evidence reassessment runs daily with a 10-record scheduled batch
  after a 25-record batch reached GitHub Actions' 20-minute ceiling.
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

First retained public record (2026-07-17): official June Challenger report
records 101,743 YTD AI-attributed cuts; strict tracker comparator is 0 while
announcement-date/domicile enrichment is early. This is a disclosed coverage
gap, not a data correction. The workflow uses `pipefail`; threshold misses must
be red in Actions while retaining the public record.

## Active and pending work

1. **Finish context enrichment and maintain the monthly Challenger panel.**
   - Persisted reconciliation records live at
     `GET /blog/wp-json/layoffs/v1/benchmarks/challenger` and on the tracker
     page. New records retain the official report month, strict qualifying
     figure, official report URL and a coverage gap—never an "accuracy" claim.
   - Do not display a percentage as “accuracy” or copy Challenger's total.
   - The current monthly record is public through the endpoint, tracker-page
     comparison table, and health page. The workflow artifact remains the
     detailed operational audit trail.

2. **Measured recall by country/period.**
   - Public protocol: `docs/RECALL_BENCHMARK_PROTOCOL.md`; endpoint:
     `GET /blog/wp-json/layoffs/v1/benchmarks/recall`. The protected writer
     rejects any record without a public reference-set URL, single country and
     closed period, stated basis, and bounded numerator/denominator.
   - Never claim country completeness. The historical 5/35 (14.3%) June–July
     baseline predates the later source and deduplication changes, so it is
     intentionally not published as current; remeasure from an independent,
     documented reference set first.

3. **High-impact review queue and durable source evidence.**
   - A live, read-only triage queue is available at
     `GET /blog/wp-json/layoffs/v1/review-queue`. It identifies very large
     (5,000+), source-quoted AI-primary and multi-country events, exposes each
     record's retained-source count and makes no automatic editorial change.
     Review remains a human decision and any correction must preserve sources
     and enter the corrections trail.
   - New source reports carry SHA-256 hashes of their retained evidence excerpt.
     Daily `evidence-hash-backfill.yml` backfills a bounded 500 legacy hashes per
     run from the already-retained excerpt only. The workflow validates its
     returned progress payload and writes the updated/remaining counts to the
     GitHub Actions summary; progress is public in `/integrity-status`.
     Preserve source URL, retained excerpt/evidence and content hash/snapshot
     metadata where permitted. A hash of a short excerpt is not a source-page
     archive; label it accurately.

4. **Dataset release ledger and monthly change report.**
   - Public `GET /blog/wp-json/layoffs/v1/dataset-releases` snapshots begin at
     ledger inception and record revision plus canonical rows/events/reports.
     It deliberately does not invent historical addition counts; corrections,
     removals and merges remain disclosed through `/quality-status`.

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

6. **Research/distribution products, after core data work.**
   - Build state/national embeddable widgets first. Do not begin metro widgets
     until metro geography is reliable. Link each widget to its exact filtered
     tracker view and methodology; publishers control backlink attributes.
   - Build company directory pages under `/blog/company-layoffs/{slug}/` only
     for source-linked, substantive canonical-company records. Avoid thin or
     invented SEO prose; `noindex` low-value pages.
   - Automate an HTML-first, accessible quarterly “State of Layoffs” report
     plus PDF/data appendix. Findings must be template/query-backed, report the
     dataset revision and coverage limits, and include a “what changed” section.
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
