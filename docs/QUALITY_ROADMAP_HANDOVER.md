# Quality roadmap handover

Last updated: 2026-07-17. This is the continuation brief for the AI Layoff
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

- Plugin version **2.17.4** is live from commit `37c0b97` (deployment run
  `29585680862`); the public Challenger panel and retained reconciliation
  endpoint were verified after the standard schema/cache initialization.
- Public quality endpoint:
  `GET /blog/wp-json/layoffs/v1/quality-status`.
  It exposes dataset revision, disclosed corrections, source health, canonical
  integrity and openly labelled workstream states.
- Integrity migration is complete: **43,897 canonical events** and **43,950
  retained source reports** at the last verification.
- Daily deep dedupe preserves every report on the surviving canonical event;
  the cluster queue rotates so small duplicate pairs cannot starve behind large
  clusters.
- Mobile page-overflow containment is deployed; tables alone may scroll
  horizontally on narrow screens.
- Legacy AI-evidence reassessment runs daily with a 10-record scheduled batch
  after a 25-record batch reached GitHub Actions' 20-minute ceiling.
- Historical GDELT recovery fails loudly and is publicly degraded on external
  HTTP 429s. Do not conceal the condition or use prohibited scraping.

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
  batch is **5** because the first ten-record smoke test took 19m22s. Manual
  runs can select 1–50 deliberately.
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
   - Current monthly workflow produces an artifact but no public table yet.

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
     Backfill legacy report hashes in bounded batches. Preserve source URL,
     retained excerpt/evidence and content hash/snapshot metadata where
     permitted. A hash of a short excerpt is not a source-page archive; label
     it accurately.

4. **Dataset release ledger and monthly change report.**
   - Add immutable revision records and report additions, corrections, merges
     and removals. Current `/quality-status` exposes *disclosed corrections*
     only; it deliberately does not invent historical addition counts because
     legacy rows lack immutable ingest timestamps.

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
