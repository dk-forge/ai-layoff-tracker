# Autonomous data-quality programme

This document is the handoff for the tracker’s next maintainer. It describes
the intended operating standard: source-first, automatically maintained,
explicit about coverage, and reproducible by journalists and researchers.

## Non-negotiable definitions

An **event** is one identifiable layoff announcement, filing, or execution.
A **source report** is a document describing that event. One event may have
many reports; totals must count the canonical event once, not every report.

The event/source-report store enforces this distinction prospectively: an exact
or fuzzy duplicate joins the existing canonical event as a retained source
report rather than becoming a second counted row or being discarded. Legacy
rows are migrated in resumable batches; source reports removed before this
store existed cannot be reconstructed without re-discovering them.
Progress is public at `GET /integrity-status`, including canonical rows still
awaiting migration and the total retained source-report count.
All normal Python ingest paths intentionally post evidence-bearing duplicates
to the server; client-side pre-dedup must never discard a second source before
it can join the canonical event.

`country` means where the affected jobs are located. `employer_country` means
the employer’s HQ/domicile when evidence supports it. Never use one as a proxy
for the other.

AI attribution is a causal classification, not a keyword hit:

| Value | Counts in AI-primary benchmark? | Meaning |
|---|---:|---|
| `primary_cause` | Yes | AI/automation is stated as the main cause of the cuts. |
| `contributing_cause` | No, keep separate | AI is one stated cause among several. |
| `selection_or_operations` | No | AI selected/managed workers; it is not stated as the cause. |
| `context_only` | No | AI investment or strategy appears in the story but is not causal. |
| `explicitly_denied` | No | Source says the cuts were not due to AI. |
| `unknown` | No | Evidence is insufficient. |

Only an exact source quote may support `primary_cause` or
`contributing_cause`. The extractor rejects a claimed quote unless it appears
in the supplied source passage.

## Autonomous publication policy

The system—not a human queue—runs the daily operation.

1. Collect from government/regulatory filings, reviewed company feeds, and
   discovery news.
2. Extract structured facts with a model and deterministic guards.
3. Attach evidence, confidence and publication status.
4. Canonicalise and deduplicate before counting.
5. Publish high-confidence evidence-backed rows; retain ambiguous discoveries
   as `provisional` and exclude them from benchmark headline totals.
6. Re-run recent overlapping windows daily and historical windows weekly.
7. Record every automatic correction and preserve source links.

The legacy AI worker runs a small daily batch. It fetches the original linked
source, re-runs only the AI-causation classification, and updates the row only
when an evidence quote can be checked against that fetched text. It does not
delete the row, alter its count/date, suppress its source, or convert a failed
fetch into a negative finding. Unreadable links remain `legacy_unreviewed` and
are retried on a future run.

The historical global-news sweep independently rotates through one 14-day
GDELT window each day, beginning at 2015. It calls the same extraction and
deduplication safeguards as live ingestion, so a rerun is safe. A daily window
is deliberately bounded to 10 model candidates: it gives the system a finite,
inspectable recovery cycle rather than an uncontrolled repeating scan of all
historical news.
Source-query retries are bounded as well; an exhausted GDELT retry budget marks
the source degraded and fails the run rather than silently returning zero.
The scheduled job also has a ten-minute extraction budget; it stops safely and
resumes in a later rotating window rather than overlapping the next run.

Humans may improve rules or source connectors, but do not need to adjudicate
routine events. A connector that breaks must fail loudly and be marked degraded
rather than silently creating a coverage hole.

## Source registry

`railway/source_registry.py` is the single registry for market status,
benchmark availability, local search vocabulary, and intended sources. It is
not a declaration of complete coverage. Before a market is promoted to
`structured_official` or `reconciled`, add:

- a concrete collector;
- source licensing/terms notes;
- fixture-based parsing tests;
- last-success/row-count health checks;
- public methodology wording;
- a documented fallback when the source is unavailable.

Priority connectors: official company IR/newsroom feeds, SEC 6-K/foreign
issuer disclosures, SEDAR+, UK RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews,
SGXNet, SENS, DART and country-specific labor notices where public.

`railway/sources/press_releases.py` is intentionally opt-in. Configure only
reviewed company-controlled RSS/Atom feeds in `PRESS_RELEASE_FEEDS`; do not
turn a generic press-release wire into a primary source without confirming
terms and publisher identity.

## Challenger reconciliation (United States)

The comparable metric is:

`U.S.-based employer + announced cuts + AI primary cause + announcement month
+ canonical event`

Do not compare Challenger’s number against all US job-location records or all
AI mentions. Each month persist a reconciliation record containing:

- Challenger report URL and published AI total;
- tracker query/version used;
- tracker comparable total and variance;
- confirmed missing events;
- excluded events and reason;
- duplicate clusters resolved;
- count/date disagreements;
- remaining unexplained difference.

Success target: three finalized consecutive months within ±10%, with all
high-impact events source-linked and no unresolved duplicate in the benchmark
set. Challenger does not publish an event-level public database, so an exact
match is neither expected nor a reason to alter data without evidence.

`railway/challenger_reconcile.py` and the monthly
`challenger-reconcile` workflow fetch the latest official Challenger job-cuts
report, extract its YTD AI figure, and compare the strict tracker query. A
threshold miss fails loudly; it is a discovery/reclassification signal, never
permission to force the tracker total.

## Regression and operational checks

Run before every deployment:

```bash
python3 -m unittest railway/tests/test_extractor_guards.py
python3 -m py_compile railway/extractor.py railway/source_registry.py railway/sources/*.py
```

Also run PHP lint in a PHP-enabled environment and verify the public endpoints
with a cache-buster after deployment. Test the tracker at 320, 375, 390, 414,
768 and desktop widths. Page-level horizontal overflow is a release blocker;
the table may scroll only inside its own scroll container.

### Source health

Every live or historical collector reports `ok` or `degraded`, its raw-entry count, a short
error detail and timestamp to the public `GET /source-health` endpoint. This
is a coverage-status signal, not a claim that a source returned every event.
An empty successful response is explicitly represented as `ok` with zero
entries; an exception is `degraded`. The visible status must be monitored by
the operations workflow before any market is described as continuously covered.

## Public methodology requirements

The site must always say:

- source-linked coverage, not complete worldwide coverage;
- what each source tier means;
- country/market coverage status and exclusions;
- announcement vs filed/executed distinction;
- AI causal taxonomy;
- range/revision/dedup policy;
- correction and dataset-version policy;
- source links and evidence quotes are retained in exports and API responses.

## Remaining implementation roadmap

The current rollout adds evidence fields, safe AI guards, the source registry,
an opt-in company-feed collector, per-collector health snapshots, and a daily
historical AI-evidence reassessment worker. The next architectural milestone is
a separate canonical-event/source-report table, then per-market connectors from
the priority list above. Do not relabel legacy rows as `primary_cause` merely
from an old boolean; re-run them against source evidence.
