# Auditor's pack

An index of everything an outside reviewer needs to check this tracker's
published claims, with the exact commands to re-run each measurement. Nothing
in this file is new machinery: every item below already runs on a schedule and
already publishes its result; this page only maps where each piece lives.

The live site links here from the methodology page ("Audit this tracker"):
https://asktherecruiter.com/blog/ai-layoff-tracker/methodology/

## 0. Ground rules an auditor should know first

- Every published row links to its primary source (SEC filing, state WARN
  register, Eurofound ERM factsheet, or a named news outlet), so row-level
  verification needs no cooperation from us.
- PASS / FAIL / UNKNOWN are three distinct states everywhere in this repo. A
  check that could not run reports UNKNOWN, never a silent pass
  (`railway/data_integrity.py` enforces this).
- Requests to the live host must send a browser-ish User-Agent
  (`AiLayoffTracker/1.0 (+https://asktherecruiter.com)`); the host's WAF
  rejects default library agents.

## 1. Recall: the gold set and its protocol

The tracker publishes a measured, intervaled coverage figure instead of an
asserted one. It is a frozen-set regression measurement over one source family
and one window; it must not be quoted as "our recall" (the protocol explains
why).

| Asset | Path |
|---|---|
| Publication protocol (what may and may not be claimed) | `docs/RECALL_BENCHMARK_PROTOCOL.md` |
| Reference sets, selection rules, per-event adjudications | `docs/recall-reference-sets/` (start at its `README.md`) |
| SEC Item 2.05 gold set (57 events, 2025-07..2026-06) | `docs/recall-reference-sets/sec-item-205-us-2025-07_2026-06.goldset.json` |
| Measurement runner (recall + precision, Wilson intervals) | `railway/recall_precision.py` |
| Committed measurement the site renders | `railway/recall_measurement.json` (render copy: `wordpress-plugin/ai-layoff-tracker/data/recall-measurement.json`) |
| Regression floor wired into CI | `MATCHED_FLOOR` in `railway/recall_goldset.py`, enforced via `railway/data_integrity.py` |
| Weekly re-measurement workflow | `.github/workflows/recall-precision.yml` |
| Independent EDGAR-side probe | `railway/edgar_recall_probe.py` (`.github/workflows/edgar-recall-probe.yml`) |

Re-run (reads the public API; no keys):

```bash
python3 railway/recall_precision.py
```

Known limits, stated in the manifest itself: one editor adjudicated the 57
match decisions; the set covers public US SEC filers only; the machine matcher
is never allowed to promote its own recall (new candidates print `ADJUDICATE`
and are not counted).

## 2. Live data-integrity invariants

One definition, imported by three consumers (test, ops triage, digest), so the
invariants cannot fork:

| Asset | Path |
|---|---|
| The invariants | `railway/data_integrity.py` |
| Live test harness | `railway/tests/test_dedup_live.py` |
| CI schedule | `.github/workflows/data-integrity.yml` |
| Session triage (prints the live verdict) | `railway/ops_status.py`, section [3] |

Re-run against the live site (read-only, stdlib only, no keys):

```bash
python3 railway/ops_status.py
```

Exit 0 means healthy and verified; exit 2 means a check is failing; exit 3
means something could not be checked from your environment and is UNKNOWN,
not passing.

## 3. Offline test suite and SQL replay

```bash
cd railway
python3 -m unittest discover -s tests -p "test_*.py"
```

This is the same invocation CI runs (`.github/workflows/tests.yml`), ~713+
tests. Tests that need optional third-party packages (for example `requests`)
report errors when run without them; CI installs the full set.

To prove a query rewrite changes no published number, load a synthetic
snapshot (never production data, no real companies) into a throwaway DB and
run old vs new SQL against it:

```bash
python3 railway/gen_synthetic_snapshot.py --rows 20000 --out synthetic_snapshot.sql
bash scripts/setup_test_db.sh
```

See `docs/ENVIRONMENT-SETUP.md` for the throwaway-DB details.

## 4. Monthly source-audit sampling

`railway/source_verification_audit.py` re-opens a deterministic stratified
random sample of already-published rows each month (seed = year*100+month, so
any month's sample is reproducible), re-reads each row's own cited source and
tallies pass / mismatch / unverifiable. It is read-only by design: a mismatch
is routed to the corrections process, never auto-edited. The result is
published whether flattering or not, on the health ledger and as the "Latest
audit result" line in the methodology's self-audit section.

- Workflow: `.github/workflows/source-verification-audit.yml`
- Published result: https://asktherecruiter.com/blog/ai-layoff-tracker/ai-tracker-health/
- Re-running it yourself needs an OpenRouter key (it asks a model whether each
  source supports its row); the sampling and tally logic are auditable in the
  file without one.

## 5. Corrections log and provenance

- Public log (every /edit and /trash appends; entries have stable anchors):
  https://asktherecruiter.com/blog/ai-layoff-tracker/#alt-corrections
- Machine-readable: https://asktherecruiter.com/blog/wp-json/layoffs/v1/quality-status
  (dataset revision, 30-day disclosed-change counts, collector health).
- Writer: `alt_log_correction()` in
  `wordpress-plugin/ai-layoff-tracker/includes/db.php`; disclosure is
  structural (the log renders from the same trail the write path appends to).
- Provenance: the log page prints a computed origin line
  (`alt_corrections_provenance()`), classifying entries only by explicit
  markers in their own recorded text; entries with no marker are reported as
  unrecorded, never assigned an origin.

## 6. WARN notice-gap arithmetic

The methodology page's "WARN notice periods, measured" section is pure date
arithmetic on state-recorded notice and effective dates
(`alt_warn_notice_gap_stats()` in `includes/db.php`), with exclusions counted
and the statutory exceptions stated. The offline stage-1 builder with the same
semantics, runnable on any row dump:

```bash
python3 railway/warn_transparency_evidence.py rows.json
```

Its non-negotiable invariants (no verdicts, no imputation) are guarded by
`railway/tests/test_warn_transparency_guards.py` and documented in
`docs/WARN_TRANSPARENCY_STAGE1.md`.

## 7. Generated public claims (drift-proof by test)

Several public statements are generated from the code that runs, and a test
fails CI if either side moves alone:

| Public claim | Generator | Drift guard |
|---|---|---|
| "Next update" times | `railway/generate_ingest_schedule.py` (from `railway/railway.toml`) | `railway/tests/test_ingest_schedule.py` |
| Country/outlet scan table | `railway/generate_country_table.py` (from the GDELT allowlist) | regenerate and `git diff --exit-code` |
| Per-jurisdiction "what qualifies" table | `railway/generate_jurisdiction_table.py` (from the WARN state lists and source docstrings) | `railway/tests/test_jurisdiction_table.py` |

## 8. The data itself

- Full CSV/JSON exports (filtered or complete) from the tracker page; the
  export carries source URLs so every row is checkable.
- API: `GET /blog/wp-json/layoffs/v1/query`, `/aggregate`, `/facets` (public,
  keyless, read-only).
- License: CC BY 4.0 with attribution to asktherecruiter.com, so replicating
  our numbers independently is not just permitted but intended.

## What is NOT independently verifiable today

Stated so the gap is visible rather than implied away:

- The recall gold set has a single adjudicating editor (recorded in the
  manifest); a second editor is the named next step.
- The monthly source audit's model judgment step needs an API key, so an
  outside reviewer can reproduce the sample and the protocol but not the
  exact model verdicts without one.
- Corrections before the machine-written log began (2026-07-15 seed entries)
  carry prose descriptions but no structured origin field; the provenance
  line counts them as unrecorded.
