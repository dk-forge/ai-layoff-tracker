# Closing the receiptless categories — execution-ready plan

Status: **PLAN ONLY. Not yet implemented.** Authored 2026-07-24 from a
readiness audit. Nothing here has been armed. The high-value first step (SEC
8-K Item 2.05 tagging) is safe to implement without owner input; everything that
adds an API key or LLM cost is an **owner decision** (marked ⚑) and must not be
armed unattended (see CLAUDE.md "Ship key-gated sources DORMANT").

The 5 categories that currently lack a strong primary-source receipt:
Contract Loss, M&A, Buyouts, Bankruptcy, Federal/DOGE.

## Current state (verified 2026-07-24)

- **EDGAR** (`sources/edgar.py`) runs EFTS phrase search over 8-K/6-K. `"item
  2.05"` is already a keyword, so exit-cost 8-Ks are pulled today, but the
  collector **discards `_source.items`** (the 8-K item-code array). Reading it is
  a tagging/verification win, not a volume mechanism. Items 2.01/1.02/1.03 are
  not targeted. No `edgar_items.py` scaffold exists.
- **Federal RIF** (`sources/federal_layoffs.py` + `federal_rif_import.py`,
  monthly cron) is **armed** (keyless, `/bulk` path, no LLM). Verify recent runs
  succeed — data.opm.gov reportedly migrated to a Blazor app (audit §5).
- **Distress → bankruptcy** (`distress_watchlist.py`, weekly cron) is **dormant
  per-source** — skips a source whose key is unset. ⚑ needs `COURTLISTENER_API_KEY`
  and/or `COMPANIES_HOUSE_API_KEY_UK`. Filing = lead generator (no headcount);
  it runs a targeted news query → extractor → post. `DISTRESS_DRY=1` dry-run.
- **Foreign filings** (`foreign_filings_ingest.py`, daily) **dormant per-market**.
  ⚑ needs `EDINET_API_KEY_JP`, `OPENDART_API_KEY_KR`. `FOREIGN_DRY=1` dry-run.
- **`bankruptcy` reason_tag does NOT exist.** Vocabulary (mirrored in
  `extractor.py` ALLOWED_REASON_TAGS, `cpt.php` alt_allowed_reason_tags(),
  `layoffs.js` REASON_LABELS): ai_automation, revenue_decline, restructuring,
  merger_acquisition, offshoring, product_discontinuation, cost_reduction,
  macroeconomic, possible_ai, closure. Only M&A maps (→ merger_acquisition).

## Dedup safety (verified)

Main hash = `md5(company + layoff_date + job_count)`; federal hash excludes
count. **reason_tags are NOT in either hash.** Server upsert field-updates any
non-`edited` row on hash-match, so adding a tag + re-import updates in place —
**no bulk-purge needed.** The ONLY purge trigger is a `job_count` change; nothing
below changes job_count.

## Ordered plan (by value)

**Step 0 — vocabulary (bundle WITH the source that populates it, not before —
empty filter options look broken).** Add `bankruptcy`, `contract_loss`,
`federal_workforce` to all three mirrored files + the extractor prompt/schema.
Bump ALT_VERSION, deploy, verify `/facets` + Reason chip. Not hash-changing.

**Rank 1 — SEC 8-K Item 2.05 items-array read (SAFE to implement now).**
`edgar.py` `pull_edgar_filings_between` + `search_company_filings`: read
`source.get("items")` into the candidate dict; when it contains `"2.05"`, stamp a
verified exit-cost tag and keep the hit even without a keyword excerpt. No env
flag (EDGAR is live), no new cost, tag-only → no purge. Verify against audit
accessions `0000106640-26-000052`, `0001001250-26-000031`,
`0001171843-26-004333`, `0001628280-26-044501`.

**Rank 2 — 8-K item sweep for M&A / Contract Loss / Bankruptcy receipts.**
Same file. Item 2.01 → `merger_acquisition`; 1.02 → `contract_loss`; 1.03 →
`bankruptcy` (SEC receipt for public-company bankruptcy). Most carry no
headcount → discarded by the count/quote gates, so they corroborate + tag when a
count is present. ⚑ Gate noisier 1.02/2.01 behind `EDGAR_ITEM_SWEEP=1`, ship
dormant, measure candidate volume + LLM cost before arming.

**Rank 3 — Private-company bankruptcy: arm `distress_watchlist.py`.** ⚑ Ensure
`COURTLISTENER_API_KEY` secret set (free token). First run `workflow_dispatch`
with `DISTRESS_DRY=1`. Stamp posted rows with `bankruptcy` provenance. Update
Sources page + health.js `meta{}` same session.

**Rank 4 — Federal/DOGE.** (a) Verify `federal-rif-import.yml` succeeds
(data.opm.gov migration risk). (b) Add `federal_workforce` to `_entry()`
reason_tags — confirm `/bulk` field-updates on hash-match before relying on
in-place tagging. (c) ⚑ FPDS/SAM.gov contractor terminations = build
distress-style (contract → news → extractor), lower priority, no documented
machine API.

**Rank 5 — M&A:** no separate build; covered by `merger_acquisition` +
Rank 2's Item 2.01.

**Rank 6 — Buyouts:** an open **policy** question (count buyout ceilings?), not an
engineering gap. Already partly caught by existing EDGAR keywords. A `buyout`
tag + extractor guidance if wanted; no new source.

## Owner decisions needed (⚑) before arming anything beyond Rank 1
1. Add `COURTLISTENER_API_KEY` secret? (free; enables private-co bankruptcy)
2. Add `EDINET_API_KEY_JP` / `OPENDART_API_KEY_KR`? (JP/KR filings)
3. Accept the LLM cost of the Item 1.02/2.01 sweep after a dry-run volume check?

Reference: `docs/US_COVERAGE_GAP_AUDIT_2026_07.md` §3/§4/§5 has the verified-live
groundwork and matches the owner's original source proposal.
