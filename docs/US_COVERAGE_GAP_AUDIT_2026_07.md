# US coverage-gap audit — July 2026

Compiled 2026-07-18 by a three-angle parallel audit (state WARN completeness
against live tracker counts, metro business press, layoff-adjacent official
notice types) plus synthesis. Trivial items were executed the same day
(MS/ND states, IL citation URL, 33 metro press domains, EDGAR item-2.05
keyword); the remainder are ranked builds below.

# Coverage expansion — ranked action list (synthesis of 3 audits, 2026-07-18)

Synthesized from: the 50-state WARN completeness audit, the metro business-press allowlist sweep, and the layoff-adjacent notice-type research. Baseline: 33,989 WARN rows. Total recoverable backlog across items below: **~6,500–11,000 rows (+19–32%)** plus forward-recall gains from press and 8-K changes.

## 1. Top 10 additions, ranked by recoverable-volume-per-effort

| # | Action | Mechanism | Verified URL | Volume / payoff | Effort |
|---|--------|-----------|--------------|-----------------|--------|
| 1 | Add `"MS"` and `"ND"` to `ALL_STATES` (`railway/sources/warn.py:189`) — same omission class the file's own comment warns about (HI/IL/PA) | warn-scraper already ships `ms.py` + `nd.py`; two-token edit | https://mdes.ms.gov/information-center/warn-information/ (quarterly PDFs); https://www.jobsnd.com "WARN Notices 2015 to present.pdf" (full history) | ~300–500 rows | Trivial |
| 2 | Fix IL fallback URL in `STATE_WARN_URL` (`warn.py:35`): `dceo.illinois.gov/aboutdceo/reportsrequiredbystatute/warnreports.html` → `dceo.illinois.gov/workforcedevelopment/warn.html` | 1-line URL fix (old path 404s; IL rows without per-row links cite a dead page) | https://dceo.illinois.gov/workforcedevelopment/warn.html | 0 rows, fixes ~1,630 rows' citations | Trivial — bundle with #1 |
| 3 | Metro/city business-press allowlist block (~33 domains: bizjournals.com, 5 live Crain's, ajc.com, inquirer.com, freep.com, geekwire.com, metro NPRs, etc.) | Paste the ready-made block from the metro research into `TRUSTED_DOMAINS` (`railway/sources/gdelt.py:35`); allowlist-only, never crawl; bot-blocked fetches drop out harmlessly like existing wsj/bloomberg entries | All domains verified HTTP 200 (except noted bot-blockers, accepted per existing posture) | Forward recall: metro outlets report local layoffs before national press | Trivial (paste + deploy) |
| 4 | SEC 8-K Item 2.05 targeting: add `"Item 2.05"` to `KEYWORDS` (`railway/sources/edgar.py:30`) and read `_source.items` in the hit loop (`edgar.py:~155`, currently discarded) to tag/verify exit-cost disclosures | EFTS phrase query is a verified perfect item proxy (17/17); no server-side `items=` filter exists | https://efts.sec.gov/LATEST/search-index with `q="Item 2.05"` | Recovers the 25% of Item 2.05 8-Ks the 12 keywords miss (~4/mo forward, more via backfill window); LLM extractor already discards non-layoff exit costs | Small |
| 5 | OH archive backfill: extend `fetch_oh` (`railway/sources/warn_custom.py:150`) from current+prev-year DAM CSVs to the per-year archive pages back to 2015 | Existing `fetch_oh` custom parser, widened | https://jfs.ohio.gov (e.g. `.../2024-Public-Notices-of-Layoffs-and-Closures`) | ~1,500–2,500 rows (56 held vs 3,338 known since 1996) | Medium |
| 6 | NY history backfill: new `fetch_ny_history` collector for the retired database (plain HTML year pages, 2023/2024 archives + Jan–Apr 2025); also test whether the Tableau full-data export reaches further back | New `warn_custom.py` parser (warn-scraper's `ny.py` only exports the post-Apr-2025 Tableau dashboard) | https://dol.ny.gov/warn-notices (retired DB); https://dol.ny.gov/warn-dashboard (current) | ~1,500–5,000 rows — largest single gap (120 NY rows ever vs NJ's 1,182) | Medium |
| 7 | LA + NC year-range extension: `fetch_la` (`warn_custom.py:305`) starts at 2025 though older per-year PDFs sit on the same page; `fetch_nc` (`warn_custom.py:334`) fetches current+prev year only | Widen year loops in two existing custom parsers | https://www.laworks.net (Downloads_WFD.asp per-year PDFs); https://www.commerce.nc.gov (year pages → CSV) | Several hundred rows combined | Low |
| 8 | MI archive backfill: `fetch_mi` (`warn_custom.py:190`) caps at the Sitecore search's ~500 recent results; reuse the same Sitecore JSON API pattern with the archive/annual-list item ids (site 403s generic fetchers, so the API pattern is the only door) | Existing Sitecore-JSON custom parser, extra item ids | https://www.michigan.gov/leo | ~1,000+ rows | Medium |
| 9 | Broken-collector repairs, NM + HI: NM domain moved (`dws.state.nm.us` → `dws.nm.gov`; per-year PDFs at a trivial URL pattern); HI restructured into per-year subpages (2019→2026) that the old single-page scraper reads as 0 PDFs | Two small `warn_custom.py` collectors replacing silent-zero warn-scraper states | https://www.dws.nm.gov/Portals/0/DM/Business/{year}_WARN.pdf; https://labor.hawaii.gov/wdc/real-time-warn-updates/ | Few hundred rows combined; restores two dark states | Low (NM) / Medium (HI) |
| 10 | CO archive backfill: `fetch_co` (`warn_custom.py:224`) reads only 2025/2026 Google-Sheets workbooks (27 rows vs ~100+/yr expected); parse the archived CDLE year workbooks/PDFs | Existing custom parser, extended to archive workbooks | https://cdle.colorado.gov (layoff-warn-list) | ~Several hundred rows | Low–Medium |

**Next in line (just below the cut):** CT history + hardened headers (~1,000 rows, F5 bot wall on the JSON doc library — medium-hard); WV new per-notice-PDF collector (state currently at zero; company+date in filenames); OR Socrata `ijbz-jpx8` sub-WARN "Large Layoff 10+" client (clone the `fetch_tx` Socrata pattern; needs a facility-name-quality guard and a freshness check vs the ccwd portal already ingested — https://data.oregon.gov/resource/ijbz-jpx8.json). Also: PA recon — 211 rows is implausibly low for a top-5 state; verify whether the DLI page is current-notices-only before building anything.

## 2. Not worth adding (and why)

- **MO WARN** — jobs.mo.gov now behind an Incapsula JS challenge; ~1,000–1,500 rows but no bot-wall-capable path tonight; report collector health as degraded and revisit.
- **OK WARN** — moved to Salesforce Experience Cloud (aura API); high effort for moderate volume; defer.
- **AR, NH, WY, PR** — no public WARN source exists (WY barred by Wyo. Stat. § 9-2-2607; others records-request only); permanently out of scope.
- **Bankruptcy claims agents** (Kroll, Omni, Verita/KCC, Stretto) — 403s, robots.txt AI-denials, or unverifiable terms; not permitted. PACER is paid.
- **Federal RIF notices** — no event-level feed exists anywhere; OPM data is aggregate only.
- **Rapid-response/dislocated-worker lists** (MD, WI, OR) — already folded into the WARN pages the existing collectors ingest; no separate machine-readable event list exists in any state (Socrata/CKAN sweeps came back empty).
- **State open-data portals other than OR/TX** — data.ny.gov, data.wa.gov, etc. publish no WARN dataset; data.virginia.gov's "WARN" is a federated copy of the Texas dataset.
- **Metro-press skips** — newsobserver.com (Raleigh covered by wral.com), sacbee.com (low corporate volume + hard bot-block), baltimoresun.com (Banner is stronger), indystar.com (ibj.com stronger), orlandosentinel.com (bizjournals covers it), gothamist/whyy/laist/cpr (metros already covered), sfstandard.com (SF already triple-covered; revisit only on recall gaps), Crain's 2016 nine-city brands (newsletters, not sites).
- **theinformation.com** — already in `TRUSTED_DOMAINS`; keep, never scrape (hard paywall).
- **`railway/sources/newsapi.py` domains string** — deliberately small query-side list; leave alone.

## 3. Sequencing

**Pure code — do tonight (no new fixtures):**
- #1 MS/ND `ALL_STATES` + #2 IL URL fix (one commit in `warn.py`).
- #3 metro allowlist block into `gdelt.py:35` (block is paste-ready in the metro research).
- #4 `"Item 2.05"` keyword + read `_source.items` in `edgar.py`.
- #7 LA/NC year-loop widening (parsers and formats already proven on the same pages).
- PA recon (read-only check of the DLI page vs history expectations).

**Needs fixture/test build (real parsers against saved page/PDF samples):**
- #5 OH archive, #6 NY retired-DB, #8 MI Sitecore archive, #9 NM+HI rebuilds, #10 CO archive; next-tier CT, WV, OR Socrata. Backfill mechanics for all of these: flow through the existing `/bulk` upsert (WARN entries are dedup-exempt by design; unchanged rows re-upsert harmlessly), and jobs must fail loudly per the iron rules.

**Blocked on permission / user decision:**
- CourtListener RECAP API token (free signup — same class as the Denmark Jobindsats decision in `docs/COUNTRY_SOURCE_RESEARCH_2026_07.md`); corroboration-only source, low urgency since bankruptcy layoffs co-surface via WARN + 8-K.
- PACER (paid) — out under no-purchase rules.

Key files: `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/warn.py` (ALL_STATES line 189, IL URL line 35), `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/warn_custom.py` (CUSTOM_STATES line 577; fetch_oh 150, fetch_mi 190, fetch_co 224, fetch_la 305, fetch_nc 334), `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/gdelt.py` (TRUSTED_DOMAINS line 35), `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/edgar.py` (KEYWORDS line 30, hit loop ~155).

---

# Appendix A — full state-by-state WARN audit

US STATE WARN COMPLETENESS AUDIT — 2026-07-18
Tracker WARN total: 33,989 rows (aggregate cross-check: per-state sum = 33,989 exactly; every row has a state). "Latest" = max layoff_date (effective date, may be future). Raw sweep data: /private/tmp/claude-501/-Users-dakotta-Projects-atr-layoff-tracker/ba147524-a963-4ed2-b8af-b361ece2fe32/scratchpad/warn_state_counts.tsv

STATE-BY-STATE TABLE

| St | Rows | Latest | Mechanism | Portal / format | Verdict | Fix type |
|----|------|--------|-----------|-----------------|---------|----------|
| AL | 259 | 2026-07-16 | warn-scraper | madeinalabama.com/warn-list/ (HTML) | healthy | — |
| AK | 52 | 2026-09-04 | warn-scraper | jobs.alaska.gov/RR/WARN_notices.htm (HTML) | plausible (small state) | — |
| AZ | 318 | 2026-06-29 | warn-scraper | azcommerce.com/arizona-warn-notices (HTML) | healthy | — |
| AR | 0 | — | none | none — DWS has no public list (records request only, per layoffdata.com) | no coverage | no-public-source |
| CA | 16,332 | 2026-12-30 | warn-scraper | edd.ca.gov WARN report (XLSX, FY pages to 2014) | healthy + current (313 rows since 6/15) | — |
| CO | 27 | 2026-09-11 | custom (Google Sheets xlsx) | cdle.colorado.gov layoff-warn-list | SUSPICIOUSLY THIN — only 2025/2026 workbooks; ~100+/yr expected | custom-parser (archive workbooks/PDFs) |
| CT | 24 | 2026-08-28 | warn-scraper (JSON doc library) | dolpublicdocumentlibrary.ct.gov (JSON→PDF). Endpoint now returns "Request Rejected" (F5 bot wall) to curl | THIN — history gap ~1,000 rows; feed bot-wall risk | custom-parser-needed |
| DE | 34 | 2026-06-29 | warn-scraper | joblink.delaware.gov/search/warn_lookups | plausible (tiny state) | — |
| DC | 140 | 2026-09-06 | warn-scraper | does.dc.gov WARN page (HTML) | healthy | — |
| FL | 2,606 | 2026-10-03 | custom (REACT POST→HTML) | reactwarn.floridajobs.org | healthy + current (70 rows since 6/15) | — |
| GA | 268 | 2026-07-15 | custom (WP admin-ajax) | tcsg.edu/warn-public-view/ | healthy | — |
| HI | 0 | — | warn-scraper (BROKEN) | labor.hawaii.gov/wdc/real-time-warn-updates/ — restructured into per-year subpages ("2026 WARN Notices"… back to 2019); scraper parses old single-page layout, gets 0 PDFs | broken collector | custom-parser (per-year HTML+PDF links) |
| ID | 134 | 2026-08-26 | custom (PDF) | labor.idaho.gov cumulative PDF | healthy | — |
| IL | 1,630 | 2026-07-15 | warn-scraper (IEBS xlsx export) | apps.illinoisworknet.com/iebs export; NOTE: STATE_WARN_URL fallback (dceo.illinois.gov/aboutdceo/…/warnreports.html) now 404s → moved to dceo.illinois.gov/workforcedevelopment/warn.html | healthy; fix fallback URL | 1-line URL fix |
| IN | 573 | 2026-06-30 | warn-scraper | in.gov/dwd/warn-notices/ | healthy | — |
| IA | 303 | 2026-12-31 | warn-scraper | iowaworkforcedevelopment.gov (HTML) | healthy | — |
| KS | 140 | 2026-05-01 | warn-scraper | kansasworks.com/search/warn_lookups | healthy | — |
| KY | 118 | 2026-08-17 | warn-scraper | kcc.ky.gov (XLSX) | healthy | — |
| LA | 32 | 2027-03-31 | custom (per-year PDFs) | laworks.net Downloads_WFD.asp — collector starts at 2025; older per-year PDFs exist on same page | thin by design — history gap | custom-parser (extend year range) |
| ME | 49 | 2026-06-02 | warn-scraper | joblink.maine.gov/search/warn_lookups | plausible (small state) | — |
| MD | 1,021 | 2026-09-04 | warn-scraper | dllr.state.md.us/employment/warn.shtml | healthy | — |
| MA | 352 | 2026-12-31 | custom (httpx/h2 CSV+XLSX) | mass.gov WARN weekly CSV + FY XLSX | healthy | — |
| MI | 87 | 2026-05-30 | custom (Sitecore search JSON) | michigan.gov/leo (p=500 recent only); milmi.org/warn 301s to same page; site 403s generic fetchers | THIN — history gap ~1,000+ | custom-parser (archive/annual lists) |
| MN | 64 | 2026-03-28 | custom (DEED PDFs via CDX) | mn.gov/deed monthly/annual PDFs (2023+) | thin — pre-2023 history gap | custom-parser (older reports) |
| MS | 0 | — | NOT in ALL_STATES; upstream warn-scraper HAS ms.py | mdes.ms.gov/information-center/warn-information/ (quarterly PDFs, live, HTTP 200) | missed supported state | scraper-supported (add "MS") |
| MO | 0 | — | warn-scraper (BROKEN) | jobs.mo.gov/warn/{year} (2019+) now behind Incapsula bot wall (JS challenge, 980-byte shell) | broken collector, ~1,000-1,500 rows | custom-parser-needed (bot wall) |
| MT | 41 | 2026-03-30 | warn-scraper | wsd.dli.mt.gov WARN page | plausible (small state) | — |
| NE | 627 | 2026-06-26 | warn-scraper | dol.nebraska.gov (HTML) | healthy | — |
| NV | 143 | 2028-08-25 | custom (yearly print-PDFs) | detr.nv.gov/Page/WARN (2022+) | healthy-ish; pre-2022 gap; note 2028 effective date outlier | optional backfill |
| NH | 0 | — | none | none — NHES posts no list; public-records requests only | no coverage | no-public-source |
| NJ | 1,182 | 2026-11-04 | warn-scraper | nj.gov/labor WARN | healthy | — |
| NM | 0 | — | warn-scraper (BROKEN) | domain moved dws.state.nm.us→dws.nm.gov; per-year PDFs live at dws.nm.gov/Portals/0/DM/Business/{year}_WARN.pdf | broken collector, small volume | custom-parser (trivial URL pattern) |
| NY | 120 | 2026-09-01 | warn-scraper (Tableau CSV export) | dol.ny.gov/warn-dashboard (post-4/2025 only); retired database dol.ny.gov/warn-notices holds 1/2025-4/2025 + 2023/2024 year archives (HTML) | SEVERELY THIN — current flow OK (53 rows since 6/15) but ~3,000-5,000 historical notices missing | custom-parser (retired DB year pages) |
| NC | 53 | 2027-12-31 | custom (Drupal→CSV) | commerce.nc.gov year pages — collector fetches current+prev year only | thin by design — history gap | custom-parser (extend year range) |
| ND | 0 | — | NOT in ALL_STATES; upstream warn-scraper HAS nd.py | jobsnd.com "WARN Notices 2015 to present.pdf" (live, HTTP 200, full history) | missed supported state | scraper-supported (add "ND") |
| OH | 56 | 2026-09-13 | custom (DAM CSV) | jfs.ohio.gov — collector reads current+prev-year CSVs only; per-year archive pages exist (e.g. 2024-Public-Notices…); layoffdata shows 3,338 OH notices since 1996 | SEVERELY THIN — ~1,500-2,500 missing since 2015 | custom-parser (archive year pages) |
| OK | 0 | — | warn-scraper (BROKEN) | old oklahoma.gov/oesc/...warn-notices.html 404s; moved to employoklahoma.gov/Participants/s/warnnotices (Salesforce Experience Cloud, JS) | broken collector | custom-parser-needed (Salesforce aura API) |
| OR | 678 | 2026-09-30 | warn-scraper | ccwd.hecc.oregon.gov/Layoff/WARN | healthy | — |
| PA | 211 | 2026-09-30 | warn-scraper | pa.gov DLI WARN page | SUSPECT — top-5 layoff state with only 211 rows vs NJ 1,182 / IL 1,630; likely current-notices-only page | verify + likely custom-parser (history) |
| PR | 0 | — | none | none — trabajo.pr.gov publishes no WARN list (federal WARN applies; records aggregators use FOIA) | no coverage | no-public-source |
| RI | 83 | 2026-08-28 | warn-scraper | dlt.ri.gov WARN | plausible (small state) | — |
| SC | 542 | 2026-11-01 | warn-scraper | scworks.org layoff-notification-reports | healthy | — |
| SD | 44 | 2026-06-29 | warn-scraper | dlr.sd.gov warn_notices.aspx | plausible (small state) | — |
| TN | 706 | 2026-08-31 | warn-scraper | tn.gov workforce reports | healthy | — |
| TX | 2,348 | 2026-09-30 | custom (Socrata JSON) | data.texas.gov/resource/8w53-c4f6 — latest upstream notice_date 2026-06-23 (~3.5 wk lag is the dataset's own cadence) | healthy; tracker matches source | — |
| UT | 193 | 2026-10-30 | warn-scraper | jobs.utah.gov warnnotices.html | healthy | — |
| VT | 42 | 2026-06-17 | warn-scraper | vermontjoblink.com/search/warn_lookups | plausible (small state) | — |
| VA | 825 | 2026-11-30 | warn-scraper | vec.virginia.gov/warn-notices | healthy | — |
| WA | 910 | 2026-12-31 | warn-scraper | esd.wa.gov WARN | healthy | — |
| WV | 0 | — | none (no upstream scraper) | workforcewv.org/job-seeker/layoffs-downsizing/warn-listing/ — live, per-notice PDFs 2021-2026, most recent July 2026 (Conduent) | public source exists, uncovered | custom-parser-needed (PDF links; company+date in filenames) |
| WI | 622 | 2026-10-31 | warn-scraper | dwd.wisconsin.gov WARN | healthy | — |
| WY | 0 | — | none | none — WARN notices not public by statute (Wyo. Stat. § 9-2-2607) | no coverage possible | no-public-source |

BIG-STATE STALENESS (rows since 2026-06-15 / verdict): CA 313 — current (EDD FY2025-26 report is the live file). NY 53 — current flow, catastrophic history gap (see above). TX 20 — current; matches Socrata upstream whose own latest notice_date is 2026-06-23. FL 70 — current. IL 10 — current-ish (IEBS revises rows in place; low add-count expected), but the IL fallback source_url 404s.

TOP 5 CONCRETE FIXES BY RECOVERABLE VOLUME

1. NY history backfill (~1,500-5,000 rows) — warn-scraper's ny.py only exports the post-April-2025 Tableau dashboard; the tracker holds 120 NY rows ever. Parse the retired database at dol.ny.gov/warn-notices (plain HTML, Jan-Apr 2025 + 2023/2024 year archive sections) as a fetch_ny_history custom collector; also test whether the Tableau workbook's full-data export reaches further back than the default view.
2. OH archive backfill (~1,500-2,500 rows) — fetch_oh in railway/sources/warn_custom.py reads only current+previous-year DAM CSVs (56 rows total). Extend it to the per-year archive pages (e.g. jfs.ohio.gov/.../2024-Public-Notices-of-Layoffs-and-Closures) and their linked CSVs/tables back to 2015.
3. MO recovery (~1,000-1,500 rows) — jobs.mo.gov/warn/{year} (2019+) is now behind an Incapsula JS challenge, so warn-scraper's mo.py silently yields nothing. Needs a bot-wall-capable fetch or an alternate official export; treat as custom-parser-needed (hard) and report source health as degraded meanwhile.
4. MI + CT history (~1,000+ rows each) — MI: fetch_mi caps at the Sitecore search's ~500 recent results (87 kept); michigan.gov hosts archived/annual WARN lists (site 403s generic fetchers — reuse the Sitecore API pattern with other item ids). CT: 24 rows; the dolpublicdocumentlibrary.ct.gov JSON feed warn-scraper uses now bot-rejects plain clients and carries little history — needs hardened headers plus a legacy warnreports backfill. CO belongs in this tier too (27 rows; parse the archived CDLE year workbooks/PDFs).
5. One-line ALL_STATES addition: "MS" and "ND" (~300-500 rows) — upstream warn-scraper already ships ms.py (mdes.ms.gov quarterly PDFs, live) and nd.py (jobsnd.com single PDF, full 2015-present history); both codes are simply missing from ALL_STATES in railway/sources/warn.py (the same class of omission the file's own comment warns about for HI/IL/PA). Cheapest fix in the audit.

Bonus, near-zero cost: fix the IL fallback URL in STATE_WARN_URL (dceo.illinois.gov/aboutdceo/reportsrequiredbystatute/warnreports.html → dceo.illinois.gov/workforcedevelopment/warn.html — old path 404s, so IL rows without per-row links cite a dead page), and add WV as a small custom collector (public per-notice PDFs, currently zero coverage). PA (211 rows) warrants a follow-up recon: volume is implausibly low for a top-5 state. Genuinely unfixable: AR, NH, WY (statute), PR — no public WARN source exists.

Key files: /Users/dakotta/Projects/atr-layoff-tracker/railway/sources/warn.py (ALL_STATES at line 189, STATE_WARN_URL IL at line 35), /Users/dakotta/Projects/atr-layoff-tracker/railway/sources/warn_custom.py (fetch_oh line 150, fetch_mi line 190, fetch_co line 224, fetch_la line 305, fetch_nc line 334).

---

# Appendix B — layoff-adjacent notice types

# Layoff-adjacent official notice types — automation research (2026-07-18)

All URLs below were fetched and verified live today unless noted. No signups, no scraping of prohibited sources. Verification via keyless GETs with descriptive User-Agents (Socrata discovery API, SEC EFTS/data.sec.gov, CourtListener, robots.txt reads).

## Summary

| # | Source class | Verdict | Best target |
|---|---|---|---|
| 1 | Rapid-response / dislocated-worker lists | mostly already covered; 2 gap states needs-build | WV (new), MS (new, low-value) |
| 2 | Open-data-portal WARN datasets | **automatable-now (1 new)** | Oregon Socrata `ijbz-jpx8` |
| 3 | SEC 8-K Item 2.05 | **automatable-now** (small `edgar.py` change) | EFTS `_source.items` + phrase query |
| 4 | Bankruptcy mass layoffs | claims agents not-permitted; CourtListener RECAP needs-build | CourtListener REST API v4 |
| 5 | Federal RIF notices | no event-level feed exists; aggregate needs-build at best | data.opm.gov (ex-FedScope) |

---

## 1. State rapid-response / dislocated-worker event lists

**Key structural finding:** in most states, non-WARN dislocation notices are folded into the *same* list the existing WARN collectors already ingest, so this category is largely not new coverage:
- Maryland's list is explicitly "WARN **and Other Dislocation Notices**" (https://labor.maryland.gov/employment/warn.shtml, 200) — already ingested via warn-scraper (MD).
- Wisconsin DWD publishes all "Layoff Notices and Updates Filed with DWD" incl. non-WARN (https://dwd.wisconsin.gov/dislocatedworker/warn/, 200 to curl; 403 to some fetchers) — already ingested (WI).
- Oregon's list is literally the "Rapid Response Activity Tracking System" (https://ccwd.hecc.oregon.gov/Layoff/) and includes sub-WARN "Large Layoff — 10 or more workers" events — already ingested (OR), and see §2.
- DOL ETA Rapid Response is a services program, not a data product (https://www.dol.gov/agencies/eta/layoffs, 200).

**Genuine gaps found (states absent from both `railway/sources/warn.py` ALL_STATES and `warn_custom.py` CUSTOM_STATES):**

| State | Interface | Verdict |
|---|---|---|
| **West Virginia** | https://workforcewv.org/job-seeker/layoffs-downsizing/warn-listing/ (200) — public list, but one PDF per notice, filename = company + date, no table/CSV | **needs-build** — per-PDF parser, same class as ID/LA collectors |
| **Mississippi** | https://mdes.ms.gov/information-center/warn-information/ (200) — quarterly WARN PDF reports (employer, county, NAICS) | **needs-build** — quarterly lag makes it low-value; PDF parser |
| New Hampshire | Notices exist only via public-records request; nhes.nh.gov WARN path 403s | **not automatable** — no public interface |
| Arkansas | https://dws.arkansas.gov/workforce-services/employers/dislocated-worker-services/ (200) — services page only, no notice list | **not automatable** — no public list |

No state was found publishing a machine-readable rapid-response *event* list separate from its WARN page (Socrata catalog queries for "rapid response layoff" = 0 results; "dislocated worker" hits are program-participant stats, e.g. Ramsey County MN).

## 2. State open-data-portal WARN datasets

Method: Socrata discovery API (`https://api.us.socrata.com/api/catalog/v1`) with `q=WARN`, `q=Worker Adjustment and Retraining Notification`, `q=layoff`, both globally and per-domain (data.ny.gov, data.wa.gov, data.iowa.gov, opendata.maryland.gov, data.delaware.gov, data.nj.gov, data.illinois.gov, data.pa.gov, data.mo.gov, data.colorado.gov, data.ct.gov), plus CKAN `package_search` on data.virginia.gov, data.ca.gov, opendata.hawaii.gov.

| Portal | Result | Verdict |
|---|---|---|
| **data.oregon.gov** | **NEW: dataset `ijbz-jpx8` "WARN"** — verified JSON API `https://data.oregon.gov/resource/ijbz-jpx8.json`; schema `warn, company_name, city, state, layoff_date, laid_off, layoff_type, received_date`; rows updated 2026-05-14; includes sub-WARN "Large Layoff - 10 or more workers" type. Landing: https://data.oregon.gov/business/WARN/ijbz-jpx8 | **automatable-now** — clone of the `fetch_tx` Socrata pattern in `warn_custom.py`. Caveat: some `company_name` values are facility-only ("Coburg Facility", "Prineville, OR Facility") — needs a name-quality guard; also verify freshness vs the ccwd.hecc.oregon.gov portal warn-scraper already reads (dataset lagged ~2mo at check time) |
| data.texas.gov | `8w53-c4f6` (updated 2026-07-07) | already consumed by `fetch_tx` |
| data.ny.gov | **No WARN/layoff dataset exists** (both queries empty). NY remains dol.ny.gov/warn-notices via warn-scraper | n/a |
| data.wa.gov | No WARN/layoff dataset (only flood-warning hits) | n/a |
| data.virginia.gov | Only a federated *copy of the Texas* dataset ("WARN Notices -TX") | n/a |
| All other portals checked | Nothing | n/a |

## 3. SEC 8-K Item 2.05 (highest-signal finding)

Current state of `/Users/dakotta/Projects/atr-layoff-tracker/railway/sources/edgar.py`: EFTS full-text phrase search (12 keywords) over forms 8-K/6-K. **Item numbers are not targeted and not read.**

Verified facts (all against `https://efts.sec.gov/LATEST/search-index`, UA per SEC fair-access):
1. **EFTS already returns the item tags**: every hit's `_source.items` lists 8-K item numbers, e.g. `["2.05","7.01","9.01"]`. `edgar.py` (`pull_edgar_filings_between`, ~lines 154–180) reads `ciks`/`adsh`/`display_names`/`file_date` and discards `items`.
2. **No server-side item filter**: an `items=2.05` query param is silently ignored (identical totals across `items=2.05/5.02/1.03/none`, verified).
3. **Phrase search is a perfect item proxy**: `q="Item 2.05"` and `q="Costs Associated with Exit or Disposal Activities"` each returned 17/17 hits carrying the 2.05 tag for 2026-06-17→07-17.
4. **Quantified gap**: of 16 unique Item 2.05 8-Ks in that 30-day window, the current 12 keywords catch 12 — **4 missed (25%)**: accessions `0000106640-26-000052`, `0001001250-26-000031`, `0001171843-26-004333`, `0001628280-26-044501`. Volume is ~16–17/month — trivially within existing rate limits.
5. Corroborating API: `https://data.sec.gov/submissions/CIK##########.json` exposes per-filing `items` (verified on CIK 0000050863).

**Verdict: automatable-now.** Add `"Item 2.05"` (or the heading phrase) to `KEYWORDS`, and read `_source.items` to (a) stop missing keyword-less 2.05 filings and (b) tag/verify entries as explicit exit-cost disclosures. Note: Item 2.05 covers exit/disposal *costs* generally (plant closures, lease exits), not only layoffs — the existing LLM extractor's non-event discard already handles that.

## 4. US bankruptcy-related mass layoffs

- **PACER**: paid — **pending** per project rules (no purchases).
- **Claims-agent sites** — checked today, all are per-case document viewers with **no structured feed**:
  - Kroll Restructuring (`restructuring.ra.kroll.com`): CloudFront **403 to non-browser clients** → **not-permitted**.
  - Omni (`omniagentsolutions.com/robots.txt`): Content-Signal `ai-train=no, use=reference`, explicit Disallow for ClaudeBot/GPTBot etc. → hostile to automated reuse → **not-permitted**.
  - KCC: rebranded to Verita (`veritaglobal.net`); robots.txt 404, terms page 404 → terms unverifiable → do not ingest.
  - Stretto (`cases.stretto.com`): 200 but no robots.txt, no feed → nothing to build on.
- **Permitted path: CourtListener / RECAP REST API v4** (Free Law Project) — verified working **anonymously**: `https://www.courtlistener.com/api/rest/v4/search/?q="mass layoff"&type=r` returned 1,514 dockets. Docs: https://www.courtlistener.com/help/api/rest/ (→ wiki.free.law). **Verdict: needs-build** — first-day-declaration/docket search for headcount language; higher rate limits require a free API token, which is a signup → user decision (same class as Denmark Jobindsats in `docs/COUNTRY_SOURCE_RESEARCH_2026_07.md`).
- Practical note: bankruptcy mass layoffs almost always co-surface via WARN filings and 8-Ks already ingested — this is a corroboration source, not a primary gap.

## 5. Federal RIF notices (post-2025)

- **No public event-level feed exists.** RIF notices go to employees, unions, and *state dislocated-worker units* — which means federal RIFs partially surface in the state WARN/dislocation lists already ingested (states log federal-agency notices in the same lists). OPM publishes only policy/guidance: https://www.opm.gov/policy-data-oversight/workforce-restructuring/reductions-in-force-rif/ (200). A 2026 proposed RIF rule exists on federalregister.gov (doc 2026-04377; site bot-walls curl, content unverified here).
- **FedScope has moved**: `fedscope.opm.gov` now redirects to **https://data.opm.gov/** — a Blazor server app, *not* Socrata/CKAN (CKAN API probe returned nothing). Quarterly separations data (with a RIF separation category) exists there but no documented machine API was found. **Verdict: needs-build at best**, as a Challenger-style aggregate reconciliation series (pattern: `challenger_reconcile.py`), and only after a manual interface/licence check of data.opm.gov's download endpoints.
- Event-level federal RIF coverage remains **news-fallback-only** (plus court dockets via §4's CourtListener when RIFs are litigated).

---

### Recommended build order
1. **`edgar.py` Item 2.05 upgrade** (automatable-now, ~1-line keyword add + `items` field read; closes a measured 25% miss rate on the single highest-signal US source).
2. **Oregon Socrata collector** (automatable-now, existing `fetch_tx` pattern; add facility-name guard + freshness comparison vs current OR scrape).
3. **WV PDF collector** (needs-build; new state coverage, ID/LA pattern).
4. **CourtListener RECAP probe** (needs-build; key decision is user's).
5. MS quarterly PDFs / data.opm.gov aggregates — low priority, lag-heavy.
