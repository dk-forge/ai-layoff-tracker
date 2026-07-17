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

- Plugin version **2.16.9**, deployed from commit `ce20951`.
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

## Active and pending work

1. **Finish context enrichment and publish a monthly Challenger panel.**
   - Persisted reconciliation records now live at
     `GET /blog/wp-json/layoffs/v1/benchmarks/challenger`; add an on-page
     monthly table with official report URL, definition, coverage gap and
     diagnostic broader number.
   - Do not display a percentage as “accuracy” or copy Challenger's total.
   - Current monthly workflow produces an artifact but no public table yet.

2. **Measured recall by country/period.**
   - Publish recall samples, reference-event set, methodology and confidence.
   - Never claim country completeness. The historical baseline is 5/35 (14.3%)
     for the documented June–July reference sample before subsequent changes;
     remeasure before using it publicly as a current figure.

3. **High-impact review queue and durable source evidence.**
   - Queue very large events, AI-primary claims, and multi-country events.
   - Preserve source URL, retained excerpt/evidence and content hash/snapshot
     metadata where permitted. A hash of a short excerpt is not a source-page
     archive; label it accurately.

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
