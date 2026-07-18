# Challenger gap closure plan — January–June 2026

Written 2026-07-18 by the per-month Challenger gap deep-research workflow
(the "in flight" item recorded in `docs/QUALITY_ROADMAP_HANDOVER.md`).
Inputs: six per-month deep-research passes (verified missing events with
source URLs), a Challenger, Gray & Christmas methodology review, and the
live benchmark baseline. Companion docs: `QUALITY_ROADMAP_HANDOVER.md`
(product standard and safeguards), `RECALL_BENCHMARK_PROTOCOL.md`,
`ARCHITECTURE.md`.

**Baseline at time of writing (2026-07-18):**

| Metric | Value |
|---|---|
| Challenger AI-attributed cuts, Jan–Jun 2026 YTD | 101,743 |
| Challenger total announced cuts, Jan–Jun 2026 YTD | 443,604 |
| Tracker strict comparator (US-domicile employer, AI-primary, evidenced announcement date) | 0 → 700 (Coinbase moved first) |
| Tracker AI+US holdings lacking announcement-date/domicile/causation evidence | 47,677 jobs |
| Tracker announced-US (job-location) YTD | 55,828 |

The strict comparator's near-zero is an evidence-backlog artifact, not an
absence of data: the enrichment and reassessment jobs are draining the
47,677 backlog. This plan sequences that drain, the named-event ingests,
and the corrections, and quantifies exactly how far they can and cannot go.

---

## 1. Per-month reconciliation table

"Tracker holdings" lists the strict-comparator-relevant rows already
present. "Named missing events" are individually verified against the
linked source; AI-flagged items are marked **[AI]**. Fix codes (R1–R10)
are defined in section 3.

| Month | Challenger AI | Challenger total | Tracker holdings (relevant) | Named missing events (jobs — source) | Month fix |
|---|---|---|---|---|---|
| **2026-01** | 7,624 | 108,435 | UPS 30,000; Dell 11,000; Pinterest 705 [AI]; Salesforce 1,000; 128 Amazon facility-level WARN rows (no announcement event); Dow only as a 3,700-job multi-country ERM row (no AI flag) | Amazon 16,000 — [CNBC](https://www.cnbc.com/2026/01/28/amazon-layoffs-anti-bureaucracy-ai.html); Dow 4,500 **[AI]** — [CBS](https://www.cbsnews.com/news/dow-job-cuts-layoffs-4500-ai-artificial-intelligence-automation/); Nike 775 (automation, not AI) — [CNBC](https://www.cnbc.com/2026/01/26/nike-to-lay-off-775-employees-at-us-distribution-centers.html); Noridian Healthcare 143 — [KVRR](https://www.kvrr.com/2026/01/15/noridian-healthcare-announced-over-140-layoffs-across-their-company/); North Star Health Alliance 100 — [WWNY](https://www.wwnytv.com/2026/01/19/north-star-lay-off-100-employees/); Hennepin Healthcare 100 — [MPR](https://www.mprnews.org/story/2026/01/26/hennepin-healthcare-cuts-100-positions-and-5-medical-programs); Valley Medical Group 41 — [Recorder](https://recorder.com/2026/01/27/valley-medical-group-cuts/) | R3 sweep windows Jan 14–20 and Jan 26–Feb 1 (after R4); Dow correction is R2 (**count change 3,700→4,500 + US domicile + AI flag = /bulk-purge + re-import**); healthcare micro-events via R9 curated seed (outlets not allowlisted, some 403) |
| **2026-02** | 4,680 | 48,307 | Oracle 20,000 [AI]; Block 4,000 [AI, 'Multiple countries']; Meta 1,500 [AI]; Salesforce 1,000 [AI, 'Multiple countries']; Angi 350 [AI]; Washington Post, Walgreens, Expedia, Riot, Workday, Tyson, Verizon, Kroger etc. via WARN; **zero Feb rows carry an announcement_date** | The Cigna Group 2,000 — [Healthcare Dive](https://www.healthcaredive.com/news/cigna-layoffs-2000-workers-worldwide/811844/); CVS Health/Aetna 313 — [Westfair](https://westfaironline.com/fairfield/cvs-health-aetna-to-lay-off-an-additional-300-employees/) (CT WARN filing the scrape missed); Hazel Health 135 — [Xtalks](https://xtalks.com/healthcare-layoffs-2026-a-running-roundup-4622/); Baystate Health 117 — [Xtalks](https://xtalks.com/healthcare-layoffs-2026-a-running-roundup-4622/) | AI line needs **no ingestion** — it needs R1 announcement-date/domicile enrichment (Block/Salesforce US domicile evidence) and R8 Oracle reconciliation; healthcare adds via R3 window Feb 4–10 + R9; investigate the missed CT WARN filing (mostly-remote workforce, only 17 in-state) |
| **2026-03** | 15,341 | 60,620 | Atlassian 1,600 [AI]; Amazon 100 [AI]; Meta 100 [AI, **undercount — should be ~700**]; HSBC 20,000 [AI, UK — excluded from US comparator]; Oracle's Mar 31 mass termination held as the 30,000 row dated 2026-04-06; Dell 11,000 (dated Jan; Challenger booked it in March); SSA, Morgan Stanley, Epic Games, SK Battery, Saks etc. present | Capital One 1,139 — [Sun-Times](https://chicago.suntimes.com/work/2026/03/05/capital-one-laying-off-warn-1700-employees-riverwoods-discover) (also an un-ingested IL WARN); IGT 700 — [Fox5 Vegas](https://www.fox5vegas.com/2026/03/24/slot-machine-maker-igt-announces-700-layoffs-worldwide/); Meta correction +600 **[AI]** — [CNBC](https://www.cnbc.com/2026/03/25/meta-layoffs-reality-labs-facebook.html); Eidos Montreal 124 (Canada, non-Challenger) — [Game Developer](https://www.gamedeveloper.com/business/embracer-has-laid-off-124-employees-at-eidos-montreal) | Meta 100→~700 is R2 (/bulk-purge + re-import); Capital One + IGT via R3 windows Mar 5–11 and Mar 24–30 (after R4); investigate the Riverwoods IL WARN ingest miss; Oracle month-booking handled by R8 |
| **2026-04** | 21,490 | 83,387 | Oracle 30,000 [AI, dated 2026-04-06]; Snap 1,000 [AI] + CA WARN; Meta 8,000 [AI, dated 2026-05-01 — April announcement]; Nike 1,400; Starbucks 1,000; ~30-notice Amazon WARN wave (~8,000); ~110 further April WARN rows; **no April row carries an announcement_date** | Microsoft 8,750 voluntary-retirement ceiling — [TechCrunch](https://techcrunch.com/2026/04/23/microsoft-offers-buyout-for-up-to-7-of-u-s-employees/) (needs R10 voluntary-program policy first); Walt Disney 1,000 — [WSWS](https://www.wsws.org/en/articles/2026/04/21/ixom-a21.html) (AP wire timed out); Condé Nast 300 **[AI]** — [WSWS](https://www.wsws.org/en/articles/2026/04/21/ixom-a21.html) / [TheWrap memo](https://www.thewrap.com/media-platforms/journalism/conde-nast-ends-self-magazine/) | R1 announcement-date evidence moves Meta 8,000 into April; Disney + Condé Nast via R3 window Apr 14–20; Microsoft only after the R10 policy call; the Government bucket (9,149) has no citable single announcement — permanent residual (section 3b) |
| **2026-05** | 38,579 | 97,006 | Meta 8,000 [AI — migrates to April on announcement basis]; Cloudflare 1,100 [AI]; Coinbase 700 [AI]; Freshworks 500 [AI]; Arctic Wolf 250 [AI]; Spirit Airlines 7,068 WARN; **Intuit held as 17 jobs — "17% of workforce" mis-parse** | Cisco 4,000 **[AI]** — [TechCrunch](https://techcrunch.com/2026/05/14/cisco-cuts-nearly-4000-jobs-to-spend-more-on-ai-reports-record-quarterly-revenue/); PayPal 4,760 **[AI]** — [TechCrunch](https://techcrunch.com/2026/05/05/paypal-says-its-becoming-a-technology-company-again-that-means-ai/); Intuit ~3,000 **[AI]** (correction of the 17-job row) — [CNBC](https://www.cnbc.com/2026/05/20/intuit-intu-q3-earnings-report-2026-company-cutting-17percent-of-staff.html); GM ~500 **[AI-partial]** — [CNBC](https://www.cnbc.com/2026/05/11/gm-layoffs.html); Groupon 400 **[AI]** — [Fast Company](https://www.fastcompany.com/91548945/groupon-layoffs-today-jobs-slashed-ai-native-pivot-stock-rises); LinkedIn 875 (explicitly NOT AI-driven per Reuters sources) — [TechRepublic](https://www.techrepublic.com/article/news-linkedin-layoffs-may-2026/); Fidelity 800 — [Boston.com](https://www.boston.com/news/business/2026/05/11/fidelity-reorganizes-its-workplace-with-new-hires-and-a-few-cuts/); Takeda 4,500 global / ~634 US — [Fierce Pharma](https://www.fiercepharma.com/pharma/takeda-slimming-down-new-era-plots-4500-layoffs-latest-restructuring-drive); Wix 1,000 **[AI]** (Israel — outside US comparator) — [HCAMag](https://www.hcamag.com/ca/news/general/wix-axes-20-of-its-workforce-as-ai-layoffs-reshape-global-tech/576995); Webflow ~140 **[AI]** (analyst estimate — R10 policy) — [FinalRound](https://www.finalroundai.com/blog/webflow-layoffs-2026) | Intuit is R2 (17→~3,000, /bulk-purge + re-import); seven US ingests via R3 windows May 5–11, May 12–18, May 26–Jun 1 (after R4); Wix/Webflow per R10 policy; Takeda: record announced plan with the US-portion evidence quoted |
| **2026-06** | 14,029 | 45,849 | 430 US June-effective WARN entries (pipeline healthy); only 6 news/SEC-sourced June events; **zero June events AI-flagged**; Lucid 1,500 duplicated as 'Lucid'/'Lucid Motors'; Oracle America 1,177 June WARN; Cisco 471 + Salesforce 86 WARN follow-throughs | GitLab 350 **[AI]** — [TechCrunch](https://techcrunch.com/2026/06/03/gitlab-cuts-14-of-staff-as-it-scales-its-platform-to-serve-ai-workloads/); Rackspace 750 **[AI]** — [San Antonio Report](https://sanantonioreport.org/rackspace-750-workers-pivots-infrastructure-ai-san-antonio/); Rivian 300 — [Electrek](https://electrek.co/2026/06/16/rivian-layoffs-r2-launch-profitability/); SAS Institute 300 — [WRAL](https://www.wral.com/business/technology/sas-cuts-300-jobs-across-the-company-june-2026/); Oracle 21,000 June 22 10-K — [Forbes](https://www.forbes.com/sites/maryroeloffs/2026/06/23/ai-cost-21000-jobs-at-oracle-this-year-and-more-layoffs-could-be-coming/) — **lifecycle evidence ONLY, never a new event (double-count)** | Four ingests via R3 windows Jun 3–9, Jun 10–16, Jun 25–28; Oracle 10-K attaches as R8 attribution/lifecycle evidence; Lucid dup is R2 (merge preserving both reports); **check collector health for early-to-mid June — the news/LLM ingest nearly flatlined** |

Verified out-of-month traps (do not "fix" by moving them): Alameda Health
System 296 (announced 2025-12-23), Oak Street Health 219 (WARN 2025-11-07),
Block ~4,000 (February, not January), Cisco ~4,000 (May 13, not February
despite multiple aggregators), Wix (May, not March), Snap (April),
Mastercard (April), Dow (January).

---

## 2. Quantified projection — how close each month can actually get

Assumptions, stated once: (a) every named missing event above is ingested;
(b) every existing AI+US holding gains exact-quote announcement-date,
domicile and causation evidence (the R1/R7 drain completes); (c) the
comparator stays on a consistent **announcement-date basis** — an event
counts in exactly one month, so Meta's 8,000 (announced April, effective
May 20) counts in April, not May; (d) automation-only attributions (Nike)
and non-US domiciles (HSBC, Wix) stay off the AI line, matching both the
tracker's standard and Challenger's separate automation bucket.

The Oracle problem must be stated before any arithmetic: the tracker holds
Oracle twice (20,000 dated Feb + 30,000 dated Apr = 50,000), while Oracle's
own June 22 10-K discloses 21,000 actual reductions over 12 months and
Challenger appears to have spread Oracle across its March and April AI
figures. Scenario A below reconciles Oracle to a **single 21,000 plan
booked at the March 31 announcement** (the honest, company-disclosed
number). Scenario B keeps the tracker's current 50,000 (knowingly ~29,000
overcounted). Neither scenario matches Challenger month-by-month, because
Challenger's per-company booking is unpublished and unauditable.

### AI line, per month (Scenario A — Oracle reconciled to 21,000 in March)

| Month | Arithmetic | Projected | Challenger AI | Coverage | Unexplained residual |
|---|---|---|---|---|---|
| Jan | Pinterest 705 + Dow 4,500 | **5,205** | 7,624 | 68.3% | 2,419 (unnamed small AI announcements) |
| Feb | Meta 1,500 + Block 4,000 + Salesforce 1,000 + Angi 350 | **6,850** | 4,680 | 146.4% — **overshoot** | booking wedge: Challenger did not count Oracle or the full Block/Meta/Salesforce plans in Feb |
| Mar | Oracle 21,000 + Atlassian 1,600 + Meta 700 + Amazon 100 | **23,400** | 15,341 | 152.5% — **overshoot** | Challenger booked only part of Oracle in March; split unknowable (no per-entry list) |
| Apr | Meta 8,000 + Snap 1,000 + Condé Nast 300 | **9,300** | 21,490 | 43.3% | ~12,190 — Challenger's April includes an Oracle portion + unnamed plans |
| May | Cisco 4,000 + PayPal 4,760 + Intuit 3,000 + GM 500 + Groupon 400 + Cloudflare 1,100 + Coinbase 700 + Freshworks 500 + Arctic Wolf 250 | **15,210** | 38,579 | 39.4% | ~23,369 — Challenger named NO May companies; its corpus of unnamed announcements dominates |
| Jun | GitLab 350 + Rackspace 750 | **1,100** | 14,029 | 7.8% | 12,929 — no public June AI announcements of size exist; structural |
| **YTD** | sum | **61,065** | **101,743** | **60.0%** | ~40,678 |

Scenario B (Oracle kept at the tracker's current 50,000): YTD = 90,065 =
88.5% — but only by carrying a known ~29,000 overcount against Oracle's own
disclosure. **Do not choose Scenario B to look closer to Challenger.** The
correct posture is Scenario A plus a documented residual.

Cross-checks on the arithmetic: monthly Challenger AI figures sum to their
published YTDs (7,624+4,680=12,304; +15,341=27,645; +21,490=49,135;
+38,579=87,714; +14,029=101,743 — all match the official releases). If May
were measured on effective-date basis instead, Meta's 8,000 lands there
(23,210 = 60.2%) but April drops to 1,300 (6.0%) — the jobs can only be
counted once; single-month percentages are therefore less meaningful than
the YTD line, and the public comparison should keep saying so.

### All-cuts line

Named missing events total 53,365 jobs (21,659 Jan + 2,565 Feb + 2,439 Mar
+ 10,050 Apr + 14,952 May + 1,700 Jun), of which 8,750 is the
policy-dependent Microsoft voluntary program (44,615 without it). Projected
announced-US: 55,828 + 53,365 ≈ **109,193 vs Challenger's 443,604 ≈ 25%**.
Full announcement-date evidencing of existing announced holdings raises
this further by an unknown amount, but no amount of named-event ingestion
sums an event ledger to a plans index (see 3b). The four-line chart's
visible gap is the honest presentation.

### What the projection says about priorities

1. The single biggest mover is not ingestion — it is **evidence** on rows
   already held (Feb/Mar/Apr are dominated by Oracle/Meta/Block/Salesforce
   rows that exist today but fail the strict filter for lack of
   announcement-date/domicile evidence). R1/R7 before everything.
2. The named-event ingests move May most (+12,660 AI) and June least
   (+1,100 AI vs a 14,029 target). June cannot be closed with public
   artifacts; say so publicly rather than stretch.
3. Two months will **overshoot** once evidenced. That is expected and must
   be presented as the booking wedge, never "fixed" by trimming tracker
   data to match Challenger.

---

## 3. Ranked fix list, mapped to existing mechanisms

Ordered by (jobs moved into the strict comparator) ÷ (effort/risk). All
mechanisms already exist; nothing here requires new architecture.

**R1 — Drain the announcement-date/domicile evidence backlog.**
Mechanism: `railway/enrich_context.py` via `enrich-context.yml`
(`CONTEXT_ENRICH_MODE=challenger_priority`, manual batches 1–50; scheduled
batch is 5). Moves up to 47,677 AI+US held jobs toward the strict
comparator with zero new ingestion — the largest lever by an order of
magnitude. Evidence rules are non-negotiable: exact source quotes only;
403-blocked evidence stays visibly inaccessible (Moneycontrol precedent).

**R2 — The four dedup-hash corrections** (job-count changes ⇒
`/bulk-purge` + full re-import, never plain upsert; each enters the public
corrections trail):
1. Intuit 17 → ~3,000 (LLM parsed "17% of workforce" as 17 jobs — also add
   a percent-of-workforce guard test to `railway/tests/test_extractor_guards.py`);
2. Meta 2026-03-25: 100 → ~700 (Reality Labs round, Challenger-named);
3. Dow: 3,700 multi-country ERM row → 4,500, US domicile, AI-flagged (CBS
   quote), retaining the ERM report on the canonical event;
4. Lucid / Lucid Motors twin 1,500-job rows: merge preserving both source
   reports (dedup merges reports, never discards).

**R3 — Targeted historical sweep windows for the named events.**
Mechanism: `railway/historical_news_sweep.py` with
`HISTORICAL_START_OVERRIDE`/`HISTORICAL_END_OVERRIDE` (1–7-day windows;
cursor untouched under override). `railway/news_catchup.py`
(`NEWS_DAYS_BACK`≤28) cannot reach any of these months from July — it is
the mechanism for *future* month-close sweeps, not this backfill.
Concrete windows: 2026-01-14→01-20; 2026-01-26→02-01; 2026-02-04→02-10;
2026-02-12→02-18; 2026-03-05→03-11; 2026-03-24→03-30; 2026-04-14→04-20;
2026-04-23→04-29 (Microsoft, only after R10); 2026-05-05→05-11;
2026-05-12→05-18; 2026-05-26→06-01; 2026-06-03→06-09; 2026-06-10→06-16;
2026-06-25→06-28. Events with coverage on already-allowlisted outlets
(CNBC, TechCrunch, CBS: Amazon, Dow, Nike, Cisco, PayPal, Intuit, GM,
GitLab, Meta, Microsoft) should recover from these windows alone — their
original miss was GDELT 429 throttling / window coverage, not the
allowlist.

**R4 — Outlet allowlist expansion (run BEFORE the R3 windows).**
Verified 2026-07-18: **none** of the outlets that carried the missed
coverage are in `TRUSTED_DOMAINS` (`railway/sources/gdelt.py`,
`railway/sources/newsapi.py`) — healthcaredive.com, paymentsdive.com,
chicago.suntimes.com, wral.com, mprnews.org, boston.com, techrepublic.com,
electrek.co, gamedeveloper.com, sanantonioreport.org, fox5vegas.com,
fiercepharma.com, westfaironline.com, kvrr.com, wwnytv.com, recorder.com,
xtalks.com all score 0. A re-swept window drops their URLs at the domain
gate. Add the reviewed, reputable trade/regional subset (allowlist-only,
same review standard as the 207→240 expansion). Healthcare is the
motivating sector: Challenger's January healthcare figure was 17,107
against ~400 in named events — Healthcare Dive, Fierce Pharma and the
regional outlets above are the sector-targeted recall lever.

**R5 — Re-run the R3 windows after R4 lands**, so the newly allowlisted
domains actually admit the recovered URLs. Order matters.

**R6 — IR-feed admissions to prevent recurrence.** Mechanism:
`railway/reviewed_feeds.json` registry (fail-closed) feeding the
`press_releases` collector. Intel, SAP, Cisco, Salesforce, Micron are
admitted; the missed-event pattern argues for adding reviewed newsroom/IR
feeds for the serial announcers: Amazon (aboutamazon.com — the Jan 16,000
was a first-party blog post), Microsoft, Oracle, Meta, PayPal, UPS.
Document terms and domain ownership per the admission gate.

**R7 — Continue legacy AI reassessment** (`railway/reclassify_legacy_ai.py`,
daily bounded batches) for the causation-evidence third of the 47,677
backlog. Same non-negotiables as R1.

**R8 — Oracle lifecycle reconciliation** (largest single overcount risk:
±29,000 on the AI line). Mechanism: the read-only review queue
(`/review-queue`, `announcement-lifecycle-review.yml`) surfaces it; the
human correction preserves all source reports and enters the corrections
trail. Attach the June 22 10-K as attribution/lifecycle evidence on the
existing Feb/Apr events; converge on one canonical plan figure (the
company-disclosed 21,000 unless better evidence emerges). Never import the
10-K figure as a new June event.

**R9 — Curated seed path for sweep-unreachable events.** Mechanism:
`railway/seed_ai.py` + `seed_data/ai_layoffs.json` (idempotent, exact
quote + real URL required per record; extend with a non-AI seed file as
needed). For the small healthcare events whose only coverage is on
micro-market or 403-blocked outlets: Noridian 143, North Star 100,
Hennepin 100, Valley Medical 41, Hazel Health 135, Baystate 117,
CVS/Aetna 313. Human-curated entry from a verified public page is
permitted; automated scraping of blocked sites is not.

**R10 — Three policy decisions to document before importing** (each is a
methodology note, not a code change):
1. *Voluntary programs* (Microsoft's 8,750 eligible-pool ceiling; >30%
   uptake reported July 6): Challenger counts buyouts; decide whether the
   tracker records the announced ceiling with a voluntary label, records
   confirmed acceptances only, or excludes — and say which on the
   methodology page.
2. *Analyst-estimated counts* (Webflow ~140, undisclosed by the company):
   the current standard requires a source-supported count; exclude, or
   admit only with the estimate explicitly labeled.
3. *Automation vs AI* (Nike 775): keep the AI flag off — mirrors
   Challenger's own separate "Technological Update" bucket and keeps the
   AI line honest.

Also investigate two ingest misses as bugs, not data entry: the Capital
One Riverwoods IL WARN and the CVS/Aetna CT WARN (mostly-remote workforce,
17 in-state — likely a threshold/format edge in `warn_import.py`'s state
coverage), and the early-to-mid June news-collector flatline (only 6
news-sourced June events; check the collector-run ledger for that window).

### 3b. What genuinely cannot be matched — the permanent, explained residual

Per the methodology review, the following must be **documented residual**,
presented via the existing `coverage_alert` and the four-line chart, and
never chased:

1. **Unit of account.** Challenger counts announcement-time *plans*
   (multi-year plans booked in full, attrition and buyouts included, never
   revised downward); the tracker counts source-linked *events*. An event
   ledger cannot sum to a plans index by construction (Econbrowser: the
   series Granger-causes JOLTS layoffs — it is a leading sentiment
   indicator, not a ledger).
2. **The unnamed-announcement corpus.** Challenger publishes no
   company-level list; in months where it names nobody (May, June) most of
   its AI figure is unauditable. June's 12,929 unexplained residual and
   May's ~23,369 are structural. January healthcare (17,107 vs ~400
   named) is the sector-level version.
3. **Estimate-derived categories.** Government/DOGE-style figures built
   from directives and media estimates (~26% of Challenger's 2025 total)
   have no per-event artifact. April 2026's Government 9,149 has no
   citable announcement; federal RIFs file no WARN.
4. **Reason inheritance and HQ booking.** Challenger applies one stated
   reason to a whole plan and books undisclosed-location (including
   global) cuts to HQ state — Cigna's "worldwide" 2,000 and Takeda's
   4,500-global/634-US illustrate why identical events produce different
   US numbers under the two methods.

The honest reconciliation frame stays: report both numbers; explain the
wedge as (plans − realized events) + (estimates without artifacts) +
(buyouts/attrition) + (reason-inheritance on full plan sizes).

---

## 4. Do-not-do list

1. **Never copy, interpolate, or tune toward Challenger's numbers** in
   tracker data. Challenger figures live only in labeled benchmark records
   source-linked to the official release (`/benchmarks/challenger`).
2. **Never fabricate or soften AI attributions.** June US AI = 0 stays 0
   until exact-quote evidence exists. The gap is the finding.
3. **No prohibited access:** no scraping or automation-bypass of
   403-blocked or paywalled sources (Becker's, Fierce sites, CNBC/NBC/
   GeekWire 403 pages, Hartford Business Journal, TheStreet, Bloomberg
   paywall), no CAPTCHA circumvention, no paid subscriptions (NewsAPI
   production tier included). Blocked evidence stays visibly inaccessible;
   use accessible alternates or R9 human curation.
4. **No plain upserts on count changes** — the dedup hash includes job
   count; corrections go through `/bulk-purge` + re-import with a
   corrections-trail entry (Intuit, Meta, Dow, Lucid).
5. **Do not import Oracle's June 22 disclosure (21,000) as a new event** —
   it is cumulative attribution evidence for the existing Feb/Apr events.
6. **Do not book Cisco's ~4,000 in February** (aggregator error; verified
   May 13) and do not "move" the verified out-of-month events listed under
   the table in section 1.
7. **Never substitute effective dates for missing announcement dates** in
   the strict comparator (benchmark rule); a legitimate zero beats an
   inflated match.
8. **Do not publish an "accuracy" percentage** against Challenger or imply
   the residual is closable; scope differences stay visible.
9. **Do not let dedup collapse announcement events into their WARN
   follow-throughs** (or vice versa) in ways that discard reports; WARN
   entries remain exempt from fuzzy/cross-outlet dedup.
10. **Do not overwrite 'Multiple countries' rows (Block, Salesforce) by
    hand** — US domicile enters only through evidence-quoted
    `employer_country` enrichment (R1), never assertion.
