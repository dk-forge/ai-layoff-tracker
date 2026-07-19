# Promotion review: Japan (EDINET) and South Korea (OpenDART)

Status 2026-07-18: **pending review — not live.** Discovery probes report
health twice daily; the evidence-only document stages below exist and are
fixture-tested, but **nothing downloads on a schedule, nothing is classified,
and nothing posts an event**. This page lists exactly what a human/agent
reviewer must approve before either market can flow events, per the admission
rule in [OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md](OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md).

## What is already built (this change)

| Piece | Where |
|---|---|
| Discovery list clients + twice-daily health probes | `railway/sources/edinet.py`, `railway/sources/opendart.py`, `railway/cron.py` |
| Evidence-only document stages (official `type=1` and `document.xml` endpoints; 50 MB archive / 800 K char bounds; classified, secret-free errors; returns candidates-with-excerpts, never events) | `edinet.fetch_document_evidence`, `opendart.fetch_document_evidence` |
| Reviewable two-tier JA/KO layoff vocabulary with researched provenance and observed false-positive evidence | `railway/sources/layoff_language.py` |
| Seven bounded excerpts of real 2025–2026 public filings (5 positive, 2 near-miss negative) with full provenance | `railway/tests/fixtures/official_filings_manifest.json` + `edinet_jp_*` / `opendart_kr_*` fixtures |
| 27 offline tests proving the detector flags/refuses correctly, the stages parse/refuse bodies safely, and the probe windows track each market's publication schedule | `railway/tests/test_layoff_language_fixtures.py`, `test_edinet_document_stage.py`, `test_opendart_document_stage.py` |
| Probe-window fix: probes now request the newest *complete* local filing day (EDINET submissions close 17:15 JST; DART reception closes 19:00 KST) instead of always "yesterday", so the 22:00-local run sees same-day filings and the 07:00-local run re-checks them | `latest_complete_list_date` in both source modules |

## What the reviewer must approve before events flow

1. **Extraction quality on the fixtures.** Run
   `python3 -m unittest tests.test_layoff_language_fixtures -v` in `railway/`,
   then read each fixture and its excerpts. Confirm the five positives
   describe real workforce events (Kookmin Bank: 550 employees, 2026-01-20;
   LB Semicon: 76 employees, 2025; Japan Display: solicited retirements with
   1,483 domestic applicants; Sanken/Yamagata Sanken: subsidiary solicitation
   resolved 2026-05-07; Sankyo Tateyama: board resolution 2026-01-08) and
   that both negatives (debt-ratio/statute 구조조정 noise; 構造改革
   governance boilerplate) stay refused.
2. **Vocabulary sign-off.** The tier decisions are argued in
   `layoff_language.py`'s docstring; the debatable calls are: 早期退職 is
   strong (it can also name a standing early-retirement scheme), リストラ and
   구조조정 are context-only, and bare 감원 is context with a boundary guard.
   Expansions need new fixture evidence in the manifest.
3. **Scope of the scheduled document stage.** Decide which listed document
   types are scanned (Japan: extraordinary/annual/semiannual reports, e.g.
   EDINET `docTypeCode` 180/120/160 — verify codes against the current EDINET
   specification; Korea: 주요사항보고 and periodic/registration reports), the
   per-run download cap, and confirm each API's documented request quota
   before any backfill.
4. **Translation handling.** The existing DeepSeek-V3 extractor
   (`railway/extractor.py`) reads any language — worldwide GDELT ingest
   already relies on that. Before promotion, spot-check it on the five
   positive fixtures and confirm: `job_count` picks the workforce number
   (550/76/1,483), never the adjacent monetary figures (백만원/百万円
   amounts appear in the same sentences); dates like `2026년 01월 20일` and
   `2026年１月８日` parse to ISO; `ai_language` stays in the original
   language; and company names resolve consistently (Latin listing name vs
   희망퇴직/日本語 filer name) so dedup hashes stay stable.
5. **Cursor + health before "live".** The document stage must get a
   persisted replay cursor (advance only after a fully successful run — the
   `next_cursor_after_success` pattern) and its own source-health ids
   (e.g. `edinet_jp` list probe stays, plus per-run document-stage health)
   reporting `running`/`ok`/`degraded` **before** the public page names the
   source live (admission rule gate 5). Data jobs must fail loudly
   (non-zero exit on any failed batch).
6. **Event lifecycle.** One real event produces several filings (Japan
   Display appears in an extraordinary report, a semiannual report and an
   annual report in these fixtures alone). The connector must post
   corroborating source reports onto one canonical event via the existing
   WordPress dedup, not three events; WARN-style dedup exemptions do NOT
   apply here.
7. **Registry move last.** `railway/source_registry.py` still lists JP/KR as
   `discovery_only`. Move EDINET/DART into `live_sources` only in the same
   change that ships the scheduled connector, workflow, and public
   methodology text.

## How to re-verify this package offline

```bash
cd railway
python3 -m unittest discover -s tests            # full suite
python3 -m unittest tests.test_layoff_language_fixtures -v
```

Fixture provenance (official viewer URLs, filing numbers, retrieval date) is
in `railway/tests/fixtures/official_filings_manifest.json`. No API key was
used to build the fixtures; excerpts came from the official public viewers.
