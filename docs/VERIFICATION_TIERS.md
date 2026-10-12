# Verification tiers: verified, reported, measured

Owner-approved names (2026-10-11). One rule, in
`wordpress-plugin/ai-layoff-tracker/includes/trust-tiers.php`
(`alt_trust_tier()` for PHP rows, `alt_trust_tier_sql()` for filters and
aggregates). Pinned by `railway/tests/test_trust_tiers.py`.

| Tier | Meaning |
|---|---|
| **verified** | An official primary document: SEC 8-K, state WARN notice, federal RIF record, other government or regulatory filing. |
| **reported** | News or press coverage, including GDELT, outlets, company press releases and Eurofound ERM. |
| **measured** | Our own measurement (job-board scans). **A measured item is never a layoff event**, so no row in `wp_alt_layoffs` can be measured. |

## Rule

`verified` if `source_type` is official (`8K`, `warn`, `federal_rif`,
`filing`, case-insensitive) **and** `verification_level` is not `bronze`.
Everything else is `reported`. The level can only downgrade, never upgrade:
a `news` row that carries `gold` stays reported. The tier is derived, never
stored, so it cannot drift from the row.

## Every value the code writes

`source_type` (allow-list `alt_allowed_source_types()` in `includes/cpt.php`,
plus `filing` written by `railway/foreign_filings_ingest.py`):

| source_type | Written by | Tier |
|---|---|---|
| `8K` | `railway/sources/edgar.py` | verified |
| `warn` | `sources/warn.py`, `warn_custom.py`, `warn_mn_letters.py`, `quebec.py`, `wup_mazowieckie.py` | verified |
| `federal_rif` | `sources/federal_layoffs.py` (OPM EHRI) | verified |
| `filing` | `railway/foreign_filings_ingest.py` | verified (see caveat) |
| `press_release` | `sources/press_releases.py` | reported |
| `erm` | `railway/erm_import.py` (Eurofound, curated from press) | reported |
| `news` | `gdelt.py`, `google_news.py`, `newsapi.py`, `regional_feeds.py`, `national_feeds.py`, `local_news.py`, `supplemental_news.py`, `process_tips.py` | reported |
| empty / unknown | legacy rows | reported |

`verification_level` (allow-list `alt_allowed_verification_levels()`):

| level | Usual source_type | Effect on tier |
|---|---|---|
| `gold` | `8K`, `filing`, `warn` (MN letters) | none (cannot upgrade a non-official type) |
| `warn` | `warn`, `federal_rif` | none |
| `silver` | `press_release`, `erm` | none |
| `bronze` | `news` | forces reported, even on an official type |

## Caveat found while mapping

`filing` is not in `alt_allowed_source_types()`, so `/bulk` and `/add` coerce
it to `news` while keeping `gold`. Those foreign regulatory filings are
therefore stored as `news`/`gold` and show as **reported** (conservative).
Adding `filing` to the allow-list would make them verified; that is a
separate data change (needs a re-import) and is not done here.

## Where it shows

- `/query`: every row carries `tier`; filter with `tier=verified` or
  `tier=verified,reported`.
- `/aggregate`: filter with `tier=`; opt-in block `include=tiers` returns jobs
  per tier in the same row shape as `source_types`.
- `/facets`: `tiers` lists the tiers present.
- Tracker cards: a plain-text "Verified" / "Reported" badge with an
  accessible name stating the basis.
