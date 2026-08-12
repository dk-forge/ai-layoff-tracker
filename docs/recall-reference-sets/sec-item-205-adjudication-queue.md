# SEC Item 2.05 gold set — adjudication sheet

Built `2026-08-12T18:21:01Z` from a measurement taken `2026-08-12T18:18:59Z`. **Rebuild it before deciding** (`python3 railway/recall_adjudication_pack.py --write`) — it reads live data and live data moves.

**29 events are pending.** Published today: 24 of 57.

Three arithmetics, so the range is known before the first decision. They are arithmetic, not targets, and the middle two are not predictions about how the entries below should go:

- every pending event accepted: **53/57 = 93.0%  (Wilson 95% CI [83.3%, 97.2%], width 13.9%)**
- the 4 with a hard discrepancy rejected, the rest accepted: **49/57 = 86.0%  (Wilson 95% CI [74.7%, 92.7%], width 18.0%)**
- only the 13 where every fact lines up accepted: **37/57 = 64.9%  (Wilson 95% CI [51.9%, 76.0%], width 24.1%)**

Nothing here is pre-ticked and nothing here recommends. Each block states what the filing says, what we hold, and where the two disagree. Ordering is by how much there is to look at: the entries with no discrepancy come first because they are quick to CHECK, not because they are right to accept.

Record a decision (see `railway/recall_adjudicate.py --help`):

```
python3 railway/recall_adjudicate.py --accept <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --event-ids <id> [<id> ...]
python3 railway/recall_adjudicate.py --reject <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --event-ids <id> [<id> ...]
```

| # | gold event | filed | stated | proposed rows | what is there to look at |
|---:|---|---|---:|---|---|
| 1 | [Cibus, Inc.](#1-cibus-inc) | 2025-07-23 | 34 | 149909 | every fact lines up — count, dates, name, accession |
| 2 | [BEYOND MEAT, INC.](#2-beyond-meat-inc) | 2025-08-06 | 44 | 149919 | every fact lines up — count, dates, name, accession |
| 3 | [Sight Sciences, Inc.](#3-sight-sciences-inc) | 2025-08-27 | 43 | 149918 | every fact lines up — count, dates, name, accession |
| 4 | [GREEN DOT CORP](#4-green-dot-corp) | 2025-09-03 | 240 | 149755 | every fact lines up — count, dates, name, accession |
| 5 | [SPRUCE POWER HOLDING CORP](#5-spruce-power-holding-corp) | 2025-09-24 | 40 | 149756 | every fact lines up — count, dates, name, accession |
| 6 | [Bolt Biotherapeutics, Inc.](#6-bolt-biotherapeutics-inc) | 2025-10-02 | 20 | 149632 | every fact lines up — count, dates, name, accession |
| 7 | [Cardlytics, Inc.](#7-cardlytics-inc) | 2025-10-02 | 90 | 149634 | every fact lines up — count, dates, name, accession |
| 8 | [Xperi Inc.](#8-xperi-inc) | 2025-11-05 | 250 | 149598 | every fact lines up — count, dates, name, accession |
| 9 | [Gemini Space Station, Inc.](#9-gemini-space-station-inc) | 2026-02-05 | 200 | 149908 | every fact lines up — count, dates, name, accession |
| 10 | [GoPro, Inc.](#10-gopro-inc) | 2026-04-07 | 145 | 149629 | every fact lines up — count, dates, name, accession |
| 11 | [Vertex, Inc.](#11-vertex-inc) | 2026-04-28 | 170 | 149630 | every fact lines up — count, dates, name, accession |
| 12 | [Koppers Holdings Inc.](#12-koppers-holdings-inc) | 2026-05-08 | 85 | 149641 | every fact lines up — count, dates, name, accession |
| 13 | [AUTOLIV INC](#13-autoliv-inc) | 2026-05-11 | 2,200 | 149638 | every fact lines up — count, dates, name, accession |
| 14 | [ALLURION TECHNOLOGIES, INC.  (ALUR, ALUR-WT)](#14-allurion-technologies-inc-alur-alur-wt) | 2025-08-07 | 70 | 149917 | one note to read — NAME matches by prefix, not exactly |
| 15 | [KALA BIO, Inc.](#15-kala-bio-inc) | 2025-09-29 | 19 | 149633 | one note to read — the URL we cite is a different accession, and the gold set's own `collapsed_duplicate_filings` records it as the same an |
| 16 | [MOLSON COORS BEVERAGE CO  (TAP, TAP-A)](#16-molson-coors-beverage-co-tap-tap-a) | 2025-10-20 | 400 | 149635 | one note to read — NAME matches by prefix, not exactly |
| 17 | [TScan Therapeutics, Inc.](#17-tscan-therapeutics-inc) | 2025-11-03 | 66 | 149600 | one note to read — NAME matches by prefix, not exactly |
| 18 | [HORMEL FOODS CORP /DE/](#18-hormel-foods-corp-de) | 2025-11-04 | 250 | 149597 | one note to read — NAME matches by prefix, not exactly |
| 19 | [HYSTER-YALE, INC.](#19-hyster-yale-inc) | 2025-11-19 | 575 | 149596 | one note to read — we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available |
| 20 | [NEWELL BRANDS INC.](#20-newell-brands-inc) | 2025-12-01 | 900 | 149613 | one note to read — NAME matches by prefix, not exactly |
| 21 | [Domtar CORP](#21-domtar-corp) | 2025-12-08 | 350 | 149611 | one note to read — ANNOUNCEMENT date is -6 days from the filing date |
| 22 | [Elanco Animal Health Inc](#22-elanco-animal-health-inc) | 2025-12-09 | 300 | 149612 | one note to read — NAME matches by prefix, not exactly |
| 23 | [reAlpha Tech Corp.](#23-realpha-tech-corp) | 2026-05-06 | 21 | 149640 | one note to read — NAME matches by prefix, not exactly |
| 24 | [SOBR Safe, Inc.](#24-sobr-safe-inc) | 2026-05-13 | 11 | 149637 | one note to read — ANNOUNCEMENT date is -6 days from the filing date |
| 25 | [Kezar Life Sciences, Inc.](#25-kezar-life-sciences-inc) | 2025-11-07 | 31 | 149595 | one note to read — NAME matches by prefix, not exactly; we hold no announcement_date, so the FILING basis cannot be compared; only the effe |
| 26 | [EnerSys](#26-enersys) | 2026-03-25 | 474 | 149625 | **two things may be conflated** — this SAME tracker event 149625 is also proposed for gold event sec-205-0001289308-25-000025 |
| 27 | [GOODYEAR TIRE & RUBBER CO /OH/](#27-goodyear-tire-rubber-co-oh) | 2026-03-20 | 600 | 149624 | **two things may be conflated** — COUNT differs by -200: we hold 400, the filing states 600 |
| 28 | [DOW INC.](#28-dow-inc) | 2026-01-29 | 4,500 | 149592, 149616 | **two things may be conflated** — COUNT differs by -4362: we hold 138, the filing states 4500; SOURCE is 'news', not the 8-K; the URL we cite is not an EDGAR archive path; 2 different tracker rows are proposed for  |
| 29 | [EnerSys](#29-enersys) | 2025-07-22 | 575 | 149625, 149911 | **two things may be conflated** — COUNT differs by -101: we hold 474, the filing states 575; the URL we cite is a DIFFERENT accession than the gold filing; this SAME tracker event 149625 is also proposed for gold e |

---

## 1. Cibus, Inc.

`sec-205-0001193125-25-163439` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Cibus, Inc. | Cibus, Inc. (event 149909, row 177176) |
| job count | **34** | **34** |
| date | 2025-07-23 (EDGAR file date) | announced 2025-07-23, effective 2025-07-23 |
| source | 8-K Item 2.05, accession 0001193125-25-163439 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1705843/000119312525163439/d946086d8k.htm> | <https://www.sec.gov/Archives/edgar/data/1705843/000119312525163439/d946086d8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> (the "Company" or "Cibus") approved a reduction in workforce of approximately 34 full-time employees as a pivotal step in implementing the Company's previously announced streamlined business focus, prioritizing its nearest-term and currently funded commercial opportunities.


**Our row 177176 (event 149909) says:**

> On July 21, 2025, the Board of Directors of Cibus, Inc. (the “Company” or “Cibus”) approved a reduction in workforce of approximately 34 full-time employees as a pivotal step in implementing the Company’s previously announced streamlined business focus, prioritizing its nearest-term and currently funded commercial opportunities.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction in workforce of approximately 34 full-time employees'
- `match_notes`: No Cibus row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-163439 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149909
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-163439 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149909
```

---

## 2. BEYOND MEAT, INC.

`sec-205-0001655210-25-000149` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | BEYOND MEAT, INC. | BEYOND MEAT, INC. (event 149919, row 177186) |
| job count | **44** | **44** |
| date | 2025-08-06 (EDGAR file date) | announced 2025-08-06, effective 2025-08-06 |
| source | 8-K Item 2.05, accession 0001655210-25-000149 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1655210/000165521025000149/bynd-20250806.htm> | <https://www.sec.gov/Archives/edgar/data/1655210/000165521025000149/bynd-20250806.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> On August 6, 2025, management of the Company approved a plan to reduce the Company's current workforce in North America by approximately 44 employees, representing approximately 6% of the Company's total global workforce.


**Our row 177186 (event 149919) says:**

> On August 6, 2025, management of the Company approved a plan to reduce the Company’s current workforce in North America by approximately 44 employees, representing approximately 6% of the Company’s total global workforce. This decision was based on cost-reduction initiatives intended to reduce cost of goods sold and operating expenses.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce ... workforce in North America by approximately 44 employees'
- `match_notes`: No Beyond Meat row in the tracker at any date (a q= search returns only Bed Bath & Beyond).

```
python3 railway/recall_adjudicate.py --accept sec-205-0001655210-25-000149 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149919
python3 railway/recall_adjudicate.py --reject sec-205-0001655210-25-000149 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149919
```

---

## 3. Sight Sciences, Inc.

`sec-205-0001531177-25-000007` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Sight Sciences, Inc. | Sight Sciences, Inc. (event 149918, row 177185) |
| job count | **43** | **43** |
| date | 2025-08-27 (EDGAR file date) | announced 2025-08-27, effective 2025-08-27 |
| source | 8-K Item 2.05, accession 0001531177-25-000007 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1531177/000153117725000007/sght-20250827.htm> | <https://www.sec.gov/Archives/edgar/data/1531177/000153117725000007/sght-20250827.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> Pursuant to the Plan, the Company intends to (a) reduce its headcount by 43 employees, or approximately 20% of its global workforce, and (b) reduce its operating expenses, principally by (i) delaying certain research and development project spend while prioritizing near term pipeline projects, (ii) reducing its selling, general, and administrative operating expenses by implementing measures to limit marketing, travel, and administrative costs, and (iii) not backfilling certain open and planned headcount.


**Our row 177185 (event 149918) says:**

> On August 27, 2025, Sight Sciences, Inc. (the “Company”) informed its employees that it is implementing a targeted plan, commencing immediately, intended to reduce operating expenses, improve cost efficiencies, and better align its operating structure for long-term, profitable growth (the “Plan”). Pursuant to the Plan, the Company intends to (a) reduce its headcount by 43 employees, or approximately 20% of its global workforce...

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce its headcount by 43 employees'
- `match_notes`: No Sight Sciences row. The company= filter returns only 'Insight Behavioral' / 'Insights Training', different employers.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001531177-25-000007 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149918
python3 railway/recall_adjudicate.py --reject sec-205-0001531177-25-000007 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149918
```

---

## 4. GREEN DOT CORP

`sec-205-0001386278-25-000069` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | GREEN DOT CORP | GREEN DOT CORP (event 149755, row 177022) |
| job count | **240** | **240** |
| date | 2025-09-03 (EDGAR file date) | announced 2025-09-02, effective 2025-12-31 |
| source | 8-K Item 2.05, accession 0001386278-25-000069 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1386278/000138627825000069/gdot-20250902.htm> | <https://www.sec.gov/Archives/edgar/data/1386278/000138627825000069/gdot-20250902.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> This action will impact up to approximately 240 employees, representing approximately 22% of the Company's global workforce.


**Our row 177022 (event 149755) says:**

> On September 2, 2025, Green Dot Corporation (the “Company”) announced a plan to exit the Company's operational activities in China by the end of 2025 as a means of reducing complexity and promoting long-term structural improvements for its business. This action will impact up to approximately 240 employees, representing approximately 22% of the Company’s global workforce.

- count matches the filing exactly
- announcement date is -1 days from the filing date
- effective date is +119 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'impact up to approximately 240 employees' (ceiling)
- `match_notes`: Only Green Dot row is a 2020 event.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001386278-25-000069 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149755
python3 railway/recall_adjudicate.py --reject sec-205-0001386278-25-000069 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149755
```

---

## 5. SPRUCE POWER HOLDING CORP

`sec-205-0001628280-25-042593` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | SPRUCE POWER HOLDING CORP | SPRUCE POWER HOLDING CORP (event 149756, row 177023) |
| job count | **40** | **40** |
| date | 2025-09-24 (EDGAR file date) | announced 2025-09-24, effective 2025-09-24 |
| source | 8-K Item 2.05, accession 0001628280-25-042593 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1772720/000162828025042593/spru-20250924.htm> | <https://www.sec.gov/Archives/edgar/data/1772720/000162828025042593/spru-20250924.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The reduction in force is expected to affect approximately 40 employees and contractors, representing approximately 19% of the Company's workforce, who were informed of the reduction in force on September 24, 2025.


**Our row 177023 (event 149756) says:**

> The reduction in force is expected to affect approximately 40 employees and contractors, representing approximately 19% of the Company’s workforce, who were informed of the reduction in force on September 24, 2025.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'affect approximately 40 employees and contractors'
- `match_notes`: No Spruce Power row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001628280-25-042593 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149756
python3 railway/recall_adjudicate.py --reject sec-205-0001628280-25-042593 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149756
```

---

## 6. Bolt Biotherapeutics, Inc.

`sec-205-0001193125-25-228293` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Bolt Biotherapeutics, Inc. | Bolt Biotherapeutics, Inc. (event 149632, row 176899) |
| job count | **20** | **20** |
| date | 2025-10-02 (EDGAR file date) | announced 2025-10-01, effective 2025-10-01 |
| source | 8-K Item 2.05, accession 0001193125-25-228293 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1641281/000119312525228293/bolt-20251001.htm> | <https://www.sec.gov/Archives/edgar/data/1641281/000119312525228293/bolt-20251001.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The restructuring plan includes a reduction of the Company's current workforce by approximately 20 employees, or approximately 50% of the Company's workforce.


**Our row 176899 (event 149632) says:**

> The restructuring plan includes a reduction of the Company’s current workforce by approximately 20 employees, or approximately 50% of the Company’s workforce.

- count matches the filing exactly
- announcement date is -1 days from the filing date
- effective date is -1 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction of the Company's current workforce by approximately 20 employees'
- `match_notes`: Bolt Biotherapeutics rows exist but are 2024 events, outside the window.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-228293 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149632
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-228293 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149632
```

---

## 7. Cardlytics, Inc.

`sec-205-0001666071-25-000135` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Cardlytics, Inc. | Cardlytics, Inc. (event 149634, row 176901) |
| job count | **90** | **90** |
| date | 2025-10-02 (EDGAR file date) | announced 2025-10-01, effective 2025-10-02 |
| source | 8-K Item 2.05, accession 0001666071-25-000135 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1666071/000166607125000135/cdlx-20251001.htm> | <https://www.sec.gov/Archives/edgar/data/1666071/000166607125000135/cdlx-20251001.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> (the "Company") committed to a plan to reduce its workforce by approximately 90 full-time employees, representing approximately 24% of the Company's current workforce (the "Plan").


**Our row 176901 (event 149634) says:**

> On October 1, 2025, Cardlytics, Inc. (the “Company”) committed to a plan to reduce its workforce by approximately 90 full-time employees, representing approximately 24% of the Company’s current workforce (the “Plan”). The Plan is intended to optimize the Company’s cost structure and is part of a broader cost-reduction initiative that also includes measures beyond full-time employee reductions.

- count matches the filing exactly
- announcement date is -1 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 8-K body: 'reduce its workforce by approximately 90 full-time employees'. The attached release says ~120 including contractors.
- `match_notes`: No Cardlytics row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001666071-25-000135 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149634
python3 railway/recall_adjudicate.py --reject sec-205-0001666071-25-000135 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149634
```

---

## 8. Xperi Inc.

`sec-205-0001193125-25-266980` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Xperi Inc. | Xperi Inc. (event 149598, row 176865) |
| job count | **250** | **250** |
| date | 2025-11-05 (EDGAR file date) | announced 2025-11-05, effective 2025-11-05 |
| source | 8-K Item 2.05, accession 0001193125-25-266980 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1788999/000119312525266980/xper-20251101.htm> | <https://www.sec.gov/Archives/edgar/data/1788999/000119312525266980/xper-20251101.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> On November 1, 2025, the Company approved a restructuring plan (the "Restructuring Plan") that will result in a reduction of approximately 250 employees globally and impacts all business and functional areas.


**Our row 176865 (event 149598) says:**

> On November 1, 2025, the Company approved a restructuring plan (the “Restructuring Plan”) that will result in a reduction of approximately 250 employees globally and impacts all business and functional areas.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction of approximately 250 employees globally'
- `match_notes`: No Xperi row. The company= filter returns only Experian, a different employer.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-266980 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149598
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-266980 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149598
```

---

## 9. Gemini Space Station, Inc.

`sec-205-0002055592-26-000008` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Gemini Space Station, Inc. | Gemini Space Station, Inc. (event 149908, row 177175) |
| job count | **200** | **200** |
| date | 2026-02-05 (EDGAR file date) | announced 2026-02-05, effective 2026-02-05 |
| source | 8-K Item 2.05, accession 0002055592-26-000008 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/2055592/000205559226000008/gemi-20260205.htm> | <https://www.sec.gov/Archives/edgar/data/2055592/000205559226000008/gemi-20260205.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Plan is expected to include a reduction in force of up to 200 global employees, including employees in Europe, the United States, and Singapore, and representing approximately 25% of the Company's total global workforce as of February 4, 2026.


**Our row 177175 (event 149908) says:**

> On February 4, 2026, Gemini Space Station, Inc. (“Gemini,” the “Company,” “we,” or “us”) approved a plan to exit and wind down its operations in the United Kingdom, the European Union and other European jurisdictions, and Australia as part of a broader initiative to reduce operating expenses and support the Company’s path to profitability (the “Plan”). The Plan is expected to include a reduction in force of up to 200 global employees, including employees in Europe, the United States, and Singapore, and representing approximately 25% of the Company’s total global workforce as of February 4, 2026.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction in force of up to 200 global employees' (ceiling)
- `match_notes`: No Gemini Space Station row. The company= filter returns only Capgemini, a different employer.

```
python3 railway/recall_adjudicate.py --accept sec-205-0002055592-26-000008 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149908
python3 railway/recall_adjudicate.py --reject sec-205-0002055592-26-000008 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149908
```

---

## 10. GoPro, Inc.

`sec-205-0001628280-26-024066` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | GoPro, Inc. | GoPro, Inc. (event 149629, row 176896) |
| job count | **145** | **145** |
| date | 2026-04-07 (EDGAR file date) | announced 2026-04-07, effective 2026-04-07 |
| source | 8-K Item 2.05, accession 0001628280-26-024066 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1500435/000162828026024066/gpro-20260407.htm> | <https://www.sec.gov/Archives/edgar/data/1500435/000162828026024066/gpro-20260407.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Restructuring Plan is anticipated to entail a global reduction in force of approximately 145 employees, representing approximately 23% of the Company's ending first quarter headcount of 631 employees (the "Reduction in Force").


**Our row 176896 (event 149629) says:**

> On April 7, 2026, GoPro, Inc. (the “Company”) announced that the Board of Directors (the “Board”) of the Company approved a restructuring plan (the “Restructuring Plan”) in order to reduce operating costs and drive stronger operating leverage. The Restructuring Plan is anticipated to entail a global reduction in force of approximately 145 employees, representing approximately 23% of the Company’s ending first quarter headcount of 631 employees (the “Reduction in Force”).

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'global reduction in force of approximately 145 employees' (631 is the ENDING headcount, not the cut)
- `match_notes`: GoPro rows exist but stop at 2018.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001628280-26-024066 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149629
python3 railway/recall_adjudicate.py --reject sec-205-0001628280-26-024066 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149629
```

---

## 11. Vertex, Inc.

`sec-205-0001104659-26-050407` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Vertex, Inc. | Vertex, Inc. (event 149630, row 176897) |
| job count | **170** | **170** |
| date | 2026-04-28 (EDGAR file date) | announced 2026-04-28, effective 2026-04-28 |
| source | 8-K Item 2.05, accession 0001104659-26-050407 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1806837/000110465926050407/tm2612960d1_8k.htm> | <https://www.sec.gov/Archives/edgar/data/1806837/000110465926050407/tm2612960d1_8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Plan includes a reduction in force of approximately 170 employees, representing approximately 9% of the Company's global workforce as of April 27, 2026.


**Our row 176897 (event 149630) says:**

> The Plan includes a reduction in force of approximately 170 employees, representing approximately 9% of the Company’s global workforce as of April 27, 2026.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction in force of approximately 170 employees'
- `match_notes`: No row for Vertex, Inc. The similarly named rows are Vertex Pharmaceuticals and Vertex Aerospace, different employers.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001104659-26-050407 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149630
python3 railway/recall_adjudicate.py --reject sec-205-0001104659-26-050407 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149630
```

---

## 12. Koppers Holdings Inc.

`sec-205-0001315257-26-000036` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Koppers Holdings Inc. | Koppers Holdings Inc. (event 149641, row 176908) |
| job count | **85** | **85** |
| date | 2026-05-08 (EDGAR file date) | announced 2026-05-08, effective 2026-12-31 |
| source | 8-K Item 2.05, accession 0001315257-26-000036 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1315257/000131525726000036/kop-20260507.htm> | <https://www.sec.gov/Archives/edgar/data/1315257/000131525726000036/kop-20260507.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The conditional decision, which is pending negotiations and consultation with the union, was driven by challenging market conditions over the past decade, including unit operating costs outpacing our ability to capture higher pricing, reduced raw material supply from North American steel manufacturers, and increased capital requirements and, if finalized, will affect approximately 85 employees.


**Our row 176908 (event 149641) says:**

> On May 8, 2026, the Company announced that it has made a conditional decision to discontinue distillation and chemical manufacturing operations at its facility in Stickney, Illinois, subject to the satisfaction of any bargaining obligations that might exist with the union that represents certain employees at that facility. The conditional decision, which is pending negotiations and consultation with the union, was driven by challenging market conditions over the past decade, including unit operating costs outpacing our ability to capture higher pricing, reduced raw material supply from North American steel manufacturers, and increased capital requirements and, if finalized, will affect approximately 85 employees.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +237 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'will affect approximately 85 employees' (1,850 is the company-wide headcount in the About boilerplate)
- `match_notes`: The filing concerns Stickney, Illinois. The only in-window Koppers row is SC WARN 66 dated 2026-04-21, a different site and before the announcement.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001315257-26-000036 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149641
python3 railway/recall_adjudicate.py --reject sec-205-0001315257-26-000036 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149641
```

---

## 13. AUTOLIV INC

`sec-205-0001193125-26-216107` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | AUTOLIV INC | Autoliv Inc (event 149638, row 176905) |
| job count | **2,200** | **2,200** |
| date | 2026-05-11 (EDGAR file date) | announced 2026-05-08, effective 2026-05-11 |
| source | 8-K Item 2.05, accession 0001193125-26-216107 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1034670/000119312526216107/alv-20260506.htm> | <https://www.sec.gov/Archives/edgar/data/1034670/000119312526216107/alv-20260506.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> In addition, Autoliv estimates that there will be a reduction of approximately 2,200 employees in Türkiye upon completion.


**Our row 176905 (event 149638) says:**

> Management determined that manufacturing capacity in the EMEA region exceeds future demand. As a result of the closures, Autoliv estimates that there will be a reduction of approximately 2,200 employees in Türkiye upon completion.

- count matches the filing exactly
- announcement date is -3 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- no discrepancy found by this build

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction of approximately 2,200 employees in Turkiye'
- `match_notes`: Autoliv rows exist but the newest dated one is 2019; nothing represents the 2,200-employee Turkiye closure.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-26-216107 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149638
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-26-216107 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149638
```

---

## 14. ALLURION TECHNOLOGIES, INC.  (ALUR, ALUR-WT)

`sec-205-0000950170-25-104347` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | ALLURION TECHNOLOGIES, INC.  (ALUR, ALUR-WT) | ALLURION TECHNOLOGIES, INC. (event 149917, row 177184) |
| job count | **70** | **70** |
| date | 2025-08-07 (EDGAR file date) | announced 2025-08-05, effective 2025-08-07 |
| source | 8-K Item 2.05, accession 0000950170-25-104347 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1964979/000095017025104347/alur-20250804.htm> | <https://www.sec.gov/Archives/edgar/data/1964979/000095017025104347/alur-20250804.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Restructuring Plan includes a reduction in force of approximately 70 employees, or approximately 65% of its workforce, which the Company expects to substantially complete by the end of the third quarter of 2025.


**Our row 177184 (event 149917) says:**

> On August 5, 2025, the Company announced a strategic restructuring plan adopted by the Company’s board of directors on July 23, 2025 (the “Restructuring Plan”). In connection with the Restructuring Plan, the Company is focusing on low-dose GLP-1 combination therapy, muscle mass maintenance, and U.S. market entry, in combination with other cost-saving measures. The Restructuring Plan includes a reduction in force of approximately 70 employees, or approximately 65% of its workforce, which the Company expects to substantially complete by the end of the third quarter of 2025.

- count matches the filing exactly
- announcement date is -2 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'ALLURION TECHNOLOGIES, INC.' against alias(es) 'Allurion'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction in force of approximately 70 employees'
- `match_notes`: No Allurion row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0000950170-25-104347 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149917
python3 railway/recall_adjudicate.py --reject sec-205-0000950170-25-104347 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149917
```

---

## 15. KALA BIO, Inc.

`sec-205-0001104659-25-094125` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | KALA BIO, Inc. | KALA BIO, Inc. (event 149633, row 176900) |
| job count | **19** | **19** |
| date | 2025-09-29 (EDGAR file date) | announced 2025-09-28, effective 2025-10-02 |
| source | 8-K Item 2.05, accession 0001104659-25-094125 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1479419/000110465925094125/tm2527340d1_8k.htm> | <https://www.sec.gov/Archives/edgar/data/1479419/000110465925096071/tm2527808d1_8ka.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> In connection with such decisions, the Board approved a reduction in the Company's workforce by approximately 19 employees, or approximately 51% (the "Reduction").


**Our row 176900 (event 149633) says:**

> In connection with such decisions, the Board approved a reduction in the Company’s workforce by approximately 19 employees, or approximately 51% (the 'Reduction').

- count matches the filing exactly
- announcement date is -1 days from the filing date
- effective date is +3 days from the filing date (the effective basis, which is a different question)
- **LOOK TWICE:** the URL we cite is a different accession, and the gold set's own `collapsed_duplicate_filings` records it as the same announcement filed twice - not a different event by the manifest's own finding

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction in the Company's workforce by approximately 19 employees'
- `match_notes`: No KALA BIO row. The company= filter returns only Estonian/Lithuanian fish processors.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001104659-25-094125 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149633
python3 railway/recall_adjudicate.py --reject sec-205-0001104659-25-094125 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149633
```

---

## 16. MOLSON COORS BEVERAGE CO  (TAP, TAP-A)

`sec-205-0001104659-25-100648` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | MOLSON COORS BEVERAGE CO  (TAP, TAP-A) | Molson Coors Beverage Company (event 149635, row 176902) |
| job count | **400** | **400** |
| date | 2025-10-20 (EDGAR file date) | announced 2025-10-20, effective 2025-12-31 |
| source | 8-K Item 2.05, accession 0001104659-25-100648 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/24545/000110465925100648/tm2529052d1_8k.htm> | <https://www.sec.gov/Archives/edgar/data/24545/000110465925100648/tm2529052d1_8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The restructuring involves the planned elimination of approximately 400 salaried positions across the Company's Americas business by the end of December 2025, estimated at approximately 9% of its Americas business salaried workforce, including hundreds of salaried positions that were already open from role prioritization efforts put in place earlier this year and those who may be granted voluntary severance as part of this restructuring.


**Our row 176902 (event 149635) says:**

> On October 20, 2025, Molson Coors Beverage Company (the “Company”) announced a corporate restructuring plan designed to create a leaner, more agile Americas organization while advancing its ability to reinvest in the business and position the Company for future growth. The restructuring involves the planned elimination of approximately 400 salaried positions across the Company’s Americas business by the end of December 2025, estimated at approximately 9% of its Americas business salaried workforce.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +72 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'Molson Coors Beverage Company' against alias(es) 'Molson Coors'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'elimination of approximately 400 salaried positions'
- `match_notes`: Molson Coors rows exist (2020, 2025-01) but none represents the October 2025 400-position Americas restructuring.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001104659-25-100648 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149635
python3 railway/recall_adjudicate.py --reject sec-205-0001104659-25-100648 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149635
```

---

## 17. TScan Therapeutics, Inc.

`sec-205-0001193125-25-261612` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | TScan Therapeutics, Inc. | TScan Therapeutics, Inc. (event 149600, row 176867) |
| job count | **66** | **66** |
| date | 2025-11-03 (EDGAR file date) | announced 2025-11-03, effective 2025-11-03 |
| source | 8-K Item 2.05, accession 0001193125-25-261612 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1783328/000119312525261612/d873161d8k.htm> | <https://www.sec.gov/Archives/edgar/data/1783328/000119312525261612/d873161d8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> Pursuant to such strategy, the Company also implemented a workforce reduction of approximately 30% of the Company's workforce, or 66 roles.

> On November 3, 2025, the Company issued a press release announcing its alignment with the Food & Drug Administration on the pivotal study design for TSC-101, the Company's strategic decision to prioritize clinical development of its heme program, while pausing further enrollment in its solid tumor Phase 1 trial and focusing preclinical efforts on in vivo engineering for solid tumors and target discovery in autoimmunity, as well as a workforce reduction of approximately 30%, or 66 employees.

> Strategic Prioritization • The strategic prioritization is expected to produce annual cost savings of $45.0 million in 2026 and 2027, and will impact approximately 30% of the Company's workforce, or 66 employees.


**Our row 176867 (event 149600) says:**

> Pursuant to such strategy, the Company also implemented a workforce reduction of approximately 30% of the Company’s workforce, or 66 roles.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'TScan Therapeutics, Inc.' against alias(es) 'TScan'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'workforce reduction of approximately 30% ... or 66 roles'
- `match_notes`: No TScan row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-261612 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149600
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-261612 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149600
```

---

## 18. HORMEL FOODS CORP /DE/

`sec-205-0000048465-25-000053` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | HORMEL FOODS CORP /DE/ | HORMEL FOODS CORP /DE/ (event 149597, row 176864) |
| job count | **250** | **250** |
| date | 2025-11-04 (EDGAR file date) | announced 2025-11-04, effective 2025-12-31 |
| source | 8-K Item 2.05, accession 0000048465-25-000053 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/48465/000004846525000053/hrl-20251104.htm> | <https://www.sec.gov/Archives/edgar/data/48465/000004846525000053/hrl-20251104.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> As part of the plan, the Company expects to eliminate approximately 250 corporate and sales roles, with most of the related employee departures to occur by December 31, 2025.


**Our row 176864 (event 149597) says:**

> The restructuring includes a voluntary early retirement program for certain groups of employees, the closing of certain open roles, involuntary role reductions, and making select changes to benefit programs. As part of the plan, the Company expects to eliminate approximately 250 corporate and sales roles, with most of the related employee departures to occur by December 31, 2025.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +57 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'HORMEL FOODS CORP /DE/' against alias(es) 'Hormel'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'eliminate approximately 250 corporate and sales roles'
- `match_notes`: The only in-window Hormel row is GA WARN 135 dated 2025-08-25, ten weeks BEFORE the announcement and a plant action, not the 250 corporate/sales roles.

```
python3 railway/recall_adjudicate.py --accept sec-205-0000048465-25-000053 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149597
python3 railway/recall_adjudicate.py --reject sec-205-0000048465-25-000053 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149597
```

---

## 19. HYSTER-YALE, INC.

`sec-205-0001173514-25-000133` — currently `ambiguous_not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | HYSTER-YALE, INC. | Hyster-Yale, Inc. (event 149596, row 176863) |
| job count | **575** | **575** |
| date | 2025-11-19 (EDGAR file date) | announced (none), effective 2025-11-19 |
| source | 8-K Item 2.05, accession 0001173514-25-000133 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1173514/000117351425000133/hy-20251113.htm> | <https://www.sec.gov/Archives/edgar/data/1173514/000117351425000133/hy-20251113.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> This action will reduce the Company's global workforce by approximately 575 employees.


**Our row 176863 (event 149596) says:**

> On November 13, 2025, the Board of Directors of Hyster-Yale, Inc. (the 'Company') approved a restructuring plan that furthers progress toward the Company's cost reduction initiatives in response to current economic and industry dynamics. This action will reduce the Company's global workforce by approximately 575 employees.

- count matches the filing exactly
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce the Company's global workforce by approximately 575 employees'
- `match_notes`: IL WARN events 149251 (90) + 108571 (76) dated 2026-03-31 could be execution of the global 575 plan announced 2025-11-19, but the filing names no site, so the same-underlying-event test cannot be met. Resolved in the conservative direction, as the CA WARN protocol does.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001173514-25-000133 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149596
python3 railway/recall_adjudicate.py --reject sec-205-0001173514-25-000133 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149596
```

---

## 20. NEWELL BRANDS INC.

`sec-205-0001193125-25-303185` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | NEWELL BRANDS INC. | Newell Brands Inc. (event 149613, row 176880) |
| job count | **900** | **900** |
| date | 2025-12-01 (EDGAR file date) | announced 2025-11-26, effective 2025-12-01 |
| source | 8-K Item 2.05, accession 0001193125-25-303185 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/814453/000119312525303185/nwl-20251126.htm> | <https://www.sec.gov/Archives/edgar/data/814453/000119312525303185/nwl-20251126.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Company plans to reduce its professional and clerical headcount by approximately 10% globally (approximately 900 employees) and to close approximately twenty Company-operated retail locations in connection with the Plan.


**Our row 176880 (event 149613) says:**

> The Company plans to reduce its professional and clerical headcount by approximately 10% globally (approximately 900 employees) and to close approximately twenty Company-operated retail locations in connection with the Plan.

- count matches the filing exactly
- announcement date is -5 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'Newell Brands Inc.' against alias(es) 'Newell'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce its global workforce by over 900 employees'
- `match_notes`: Newell rows exist but stop at 2024-03.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-303185 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149613
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-303185 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149613
```

---

## 21. Domtar CORP

`sec-205-0001193125-25-311445` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Domtar CORP | Domtar Corporation (event 149611, row 176878) |
| job count | **350** | **350** |
| date | 2025-12-08 (EDGAR file date) | announced 2025-12-02, effective 2025-12-08 |
| source | 8-K Item 2.05, accession 0001193125-25-311445 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1381531/000119312525311445/d30819d8k.htm> | <https://www.sec.gov/Archives/edgar/data/1381531/000119312525311445/d30819d8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The announcement will affect approximately 350 employees.


**Our row 176878 (event 149611) says:**

> On December 2, 2025, Domtar Corporation (“Domtar”) announced that it will permanently close operations at its Crofton, British Columbia, facility. The announcement will affect approximately 350 employees.

- count matches the filing exactly
- announcement date is -6 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** ANNOUNCEMENT date is -6 days from the filing date

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'The announcement will affect approximately 350 employees'
- `match_notes`: Domtar rows stop at 2020; the 2025-09-25 'Resolute Forest Products US Inc. / Domtar' row is a different, earlier event.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-311445 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149611
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-311445 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149611
```

---

## 22. Elanco Animal Health Inc

`sec-205-0001104659-25-119486` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Elanco Animal Health Inc | Elanco Animal Health Incorporated (event 149612, row 176879) |
| job count | **300** | **300** |
| date | 2025-12-09 (EDGAR file date) | announced 2025-12-05, effective 2025-12-09 |
| source | 8-K Item 2.05, accession 0001104659-25-119486 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1739104/000110465925119486/tm2533048d1_8k.htm> | <https://www.sec.gov/Archives/edgar/data/1739104/000110465925119486/tm2533048d1_8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Restructuring Plan will result in a global headcount reduction of approximately 300 employees, plus an approximate 300 employees whose positions will be replaced with positions in growth areas or in lower-cost geographies.


**Our row 176879 (event 149612) says:**

> The Restructuring Plan will result in a global headcount reduction of approximately 300 employees, plus an approximate 300 employees whose positions will be replaced with positions in growth areas or in lower-cost geographies.

- count matches the filing exactly
- announcement date is -4 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'Elanco Animal Health Incorporated' against alias(es) 'Elanco'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'global headcount reduction of approximately 300 employees' eliminated; a further ~300 roles are shifted, not cut ('600 roles impacted').
- `match_notes`: Elanco rows exist (2020, 2024) but none represents the December 2025 plan.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001104659-25-119486 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149612
python3 railway/recall_adjudicate.py --reject sec-205-0001104659-25-119486 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149612
```

---

## 23. reAlpha Tech Corp.

`sec-205-0001213900-26-052921` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | reAlpha Tech Corp. | reAlpha Tech Corp. (event 149640, row 176907) |
| job count | **21** | **21** |
| date | 2026-05-06 (EDGAR file date) | announced 2026-05-06, effective 2026-05-06 |
| source | 8-K Item 2.05, accession 0001213900-26-052921 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1859199/000121390026052921/ea0289539-8k_realpha.htm> | <https://www.sec.gov/Archives/edgar/data/1859199/000121390026052921/ea0289539-8k_realpha.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> Pursuant to the Plan, among others, the Company is expected to reduce its global headcount by approximately 21 full-time employees, in addition to a number of consultants, temporary workers and independent contractors, collectively representing approximately 25% of the Company's global workforce.

> The information provided under this Item 7.01 of this Form 8-K, including Exhibit 99.1 attached hereto, is being furnished and shall not be deemed "filed" for the purposes of Section 18 of the Securities Exchange Act of 1934, as amended (the "Exchange Act"), or otherwise subject to the liabilities of that section, nor shall it be deemed incorporated by reference in any filing under the Securities Act of 1933, as amended, or the Exchange Act except as shall be expressly set forth by specific reference in such filing. 1 Forward-Looking Statements This Form 8-K contains "forward-looking statements" within the meaning of the federal securities laws, including Section 27A of the Securities Act and Section 21E of the Exchange Act.


**Our row 176907 (event 149640) says:**

> Pursuant to the Plan, among others, the Company is expected to reduce its global headcount by approximately 21 full-time employees, in addition to a number of consultants, temporary workers and independent contractors, collectively representing approximately 25% of the Company’s global workforce.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'reAlpha Tech Corp.' against alias(es) 'reAlpha'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce its global headcount by approximately 21 full-time employees'
- `match_notes`: No reAlpha row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001213900-26-052921 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149640
python3 railway/recall_adjudicate.py --reject sec-205-0001213900-26-052921 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149640
```

---

## 24. SOBR Safe, Inc.

`sec-205-0001477932-26-003057` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | SOBR Safe, Inc. | SOBR Safe, Inc. (event 149637, row 176904) |
| job count | **11** | **11** |
| date | 2026-05-13 (EDGAR file date) | announced 2026-05-07, effective 2026-05-13 |
| source | 8-K Item 2.05, accession 0001477932-26-003057 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1425627/000147793226003057/sobr_8k.htm> | <https://www.sec.gov/Archives/edgar/data/1425627/000147793226003057/sobr_8k.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> Under the restructuring plan, the Company is reducing its workforce by 11 employees (approximately 70%).


**Our row 176904 (event 149637) says:**

> Under the restructuring plan, the Company is reducing its workforce by 11 employees (approximately 70%). The Company expects that the workforce reduction will decrease its annual operating costs by approximately $1.6 million.

- count matches the filing exactly
- announcement date is -6 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** ANNOUNCEMENT date is -6 days from the filing date

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reducing its workforce by 11 employees'
- `match_notes`: No SOBR Safe row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001477932-26-003057 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149637
python3 railway/recall_adjudicate.py --reject sec-205-0001477932-26-003057 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149637
```

---

## 25. Kezar Life Sciences, Inc.

`sec-205-0001628280-25-050671` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | Kezar Life Sciences, Inc. | Kezar Life Sciences, Inc. (event 149595, row 176862) |
| job count | **31** | **31** |
| date | 2025-11-07 (EDGAR file date) | announced (none), effective 2025-11-06 |
| source | 8-K Item 2.05, accession 0001628280-25-050671 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1645666/000162828025050671/kzr-20251106.htm> | <https://www.sec.gov/Archives/edgar/data/1645666/000162828025050671/kzr-20251106.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> (the "Company") implemented a restructuring plan pursuant to which the Company will reduce its workforce by approximately 31 employees, or approximately 70%.


**Our row 176862 (event 149595) says:**

> On November 6, 2025, Kezar Life Sciences, Inc. (the 'Company') implemented a restructuring plan pursuant to which the Company will reduce its workforce by approximately 31 employees, or approximately 70%.

- count matches the filing exactly
- effective date is -1 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'Kezar Life Sciences, Inc.' against alias(es) 'Kezar'
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce its workforce by approximately 31 employees'
- `match_notes`: No Kezar row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001628280-25-050671 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149595
python3 railway/recall_adjudicate.py --reject sec-205-0001628280-25-050671 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149595
```

---

## 26. EnerSys

`sec-205-0001289308-26-000009` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | EnerSys | EnerSys (event 149625, row 176892) |
| job count | **474** | **474** |
| date | 2026-03-25 (EDGAR file date) | announced 2026-03-25, effective 2026-03-25 |
| source | 8-K Item 2.05, accession 0001289308-26-000009 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1289308/000128930826000009/ens-20260325.htm> | <https://www.sec.gov/Archives/edgar/data/1289308/000128930826000009/ens-20260325.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> In addition, EnerSys estimates that there will be a reduction of approximately 474 employees upon completion.


**Our row 176892 (event 149625) says:**

> On March 25, 2026, EnerSys announced a plan to close its facility in Tijuana, Mexico, which focused on manufacturing lead acid batteries. In connection with this restructuring plan, which is estimated to be substantially complete by December 2027, EnerSys plans to sell the land and buildings and possibly the plant and equipment to other parties. In addition, EnerSys estimates that there will be a reduction of approximately 474 employees upon completion.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** this SAME tracker event 149625 is also proposed for gold event sec-205-0001289308-25-000025

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction of approximately 474 employees upon completion'
- `match_notes`: Only EnerSys row is the undated ERM Bulgaria record; nothing represents the Tijuana closure.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001289308-26-000009 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149625
python3 railway/recall_adjudicate.py --reject sec-205-0001289308-26-000009 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149625
```

---

## 27. GOODYEAR TIRE & RUBBER CO /OH/

`sec-205-0001628280-26-020222` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | GOODYEAR TIRE & RUBBER CO /OH/ | The Goodyear Tire & Rubber Company (event 149624, row 176891) |
| job count | **600** | **400** |
| date | 2026-03-20 (EDGAR file date) | announced 2026-03-16, effective 2026-03-20 |
| source | 8-K Item 2.05, accession 0001628280-26-020222 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/42582/000162828026020222/gt-20260316.htm> | <https://www.sec.gov/Archives/edgar/data/42582/000162828026020222/gt-20260316.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The proposed restructuring actions would lead to a reduction of approximately 600 positions across multiple countries within EMEA, while also creating approximately 200 new roles to support the organization moving forward, resulting in an overall net reduction of approximately 400 positions.


**Our row 176891 (event 149624) says:**

> The proposed restructuring actions would lead to a reduction of approximately 600 positions across multiple countries within EMEA, while also creating approximately 200 new roles to support the organization moving forward, resulting in an overall net reduction of approximately 400 positions.

The filing also states our 400:

> The proposed restructuring actions would lead to a reduction of approximately 600 positions across multiple countries within EMEA, while also creating approximately 200 new roles to support the organization moving forward, resulting in an overall net reduction of approximately 400 positions.

- announcement date is -4 days from the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** COUNT differs by -200: we hold 400, the filing states 600
- **LOOK TWICE:** the filing states our number too - read both sentences
- **LOOK TWICE:** NAME matches by prefix, not exactly: we hold 'The Goodyear Tire & Rubber Company' against alias(es) 'Goodyear'

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduction of approximately 600 positions across ... EMEA' (net 400 after ~200 new roles)
- `match_notes`: Goodyear rows exist, but the in-window ones are an Ohio WARN (85) and a later 2026-07-21 8-K (1,750). Neither is the March 2026 EMEA 600-position plan.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001628280-26-020222 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149624
python3 railway/recall_adjudicate.py --reject sec-205-0001628280-26-020222 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149624
```

---

## 28. DOW INC.

`sec-205-0001751788-26-000009` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | DOW INC. | Dow (event 149592, row 176859) <br> Dow Inc. (event 149616, row 176883) |
| job count | **4,500** | **138** <br> **4,500** |
| date | 2026-01-29 (EDGAR file date) | announced (none), effective 2026-08-01 <br> announced 2026-01-29, effective 2026-01-29 |
| source | 8-K Item 2.05, accession 0001751788-26-000009 | news <br> 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1751788/000175178826000009/dow-20260126.htm> | <https://news.google.com/rss/articles/CBMigwJBVV95cUxQR2FRbDROY1NxbG9pd0tkWGx3MG9sOGVWQ3MwejFNRFNUaTRGQnZmS3J3UjJqdUZjWVpQbHFGeUNjeE5jRkNmYnN6U3cwdW9Nck5CbW45QTFMTTlzdUEwWERWam00cS1QcGV0aFpjaG1EZFpLaXQxTjFtdUJXTXdXeGtURjEwbzVJbUFrampYdmoxR2ZVZ2xZRlBBeGY2V3BVTm1leGdXeUc1SDRYWGdDOXpKUE9CWnBOQkVkUkFHUGRYVFBHNDNzdWMtN0JVbmpSSWZ6SmxYVlc5MFpDNWlINTlHUlJrdFRwWGN5T1VrWnB5Um1lMnFVZ1Jod0dkUTY4cmhR?oc=5> <br> <https://www.sec.gov/Archives/edgar/data/1751788/000175178826000009/dow-20260126.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> On January 26, 2026, the Company's Board of Directors approved certain severance and related benefit costs for a workforce reduction of approximately 4,500 roles globally related to Transform to Outperform.

> The Company anticipates ~$1.1-1.5 billion in one-time costs associated with Transform to Outperform, including ~$600-800 million in severance for ~4,500 Dow roles and ~$500-700 million in other one-time costs.


**Our row 176859 (event 149592) says:**

> The Provincial Council claims European protection for the chemical hub in Tarragona in the face of 138 layoffs at Dow.

- effective date is +184 days from the filing date (the effective basis, which is a different question)
- **LOOK TWICE:** COUNT differs by -4362: we hold 138, the filing states 4500
- **LOOK TWICE:** SOURCE is 'news', not the 8-K
- **LOOK TWICE:** the URL we cite is not an EDGAR archive path
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available
- **LOOK TWICE:** 2 different tracker rows are proposed for this one gold event - at most one can be it

**Our row 176883 (event 149616) says:**

> On January 26, 2026, the Company’s Board of Directors approved certain severance and related benefit costs for a workforce reduction of approximately 4,500 roles globally related to Transform to Outperform.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** 2 different tracker rows are proposed for this one gold event - at most one can be it

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'workforce reduction of approximately 4,500 roles globally'
- `match_notes`: The in-window Dow rows are separate European site records (ERM 138/605/110, June 2026) and a different employer (Dow Jones). None represents the 4,500-role global plan.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001751788-26-000009 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149592 149616
python3 railway/recall_adjudicate.py --reject sec-205-0001751788-26-000009 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149592 149616
```

---

## 29. EnerSys

`sec-205-0001289308-25-000025` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | EnerSys | EnerSys (event 149625, row 176892) <br> EnerSys (event 149911, row 177178) |
| job count | **575** | **474** <br> **575** |
| date | 2025-07-22 (EDGAR file date) | announced 2026-03-25, effective 2026-03-25 <br> announced 2025-07-22, effective 2025-07-22 |
| source | 8-K Item 2.05, accession 0001289308-25-000025 | 8K <br> 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1289308/000128930825000025/ens-20250722.htm> | <https://www.sec.gov/Archives/edgar/data/1289308/000128930826000009/ens-20260325.htm> <br> <https://www.sec.gov/Archives/edgar/data/1289308/000128930825000025/ens-20250722.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The Plan is expected to reduce EnerSys' non-production global workforce by approximately 11%, or approximately 575 employees, and is focused primarily on corporate and management positions.


**Our row 176892 (event 149625) says:**

> On March 25, 2026, EnerSys announced a plan to close its facility in Tijuana, Mexico, which focused on manufacturing lead acid batteries. In connection with this restructuring plan, which is estimated to be substantially complete by December 2027, EnerSys plans to sell the land and buildings and possibly the plant and equipment to other parties. In addition, EnerSys estimates that there will be a reduction of approximately 474 employees upon completion.

- announcement date is +246 days from the filing date
- effective date is +246 days from the filing date (the effective basis, which is a different question)
- **LOOK TWICE:** COUNT differs by -101: we hold 474, the filing states 575
- **LOOK TWICE:** the URL we cite is a DIFFERENT accession than the gold filing
- **LOOK TWICE:** ANNOUNCEMENT date is +246 days from the filing date
- **LOOK TWICE:** this SAME tracker event 149625 is also proposed for gold event sec-205-0001289308-26-000009
- **LOOK TWICE:** 2 different tracker rows are proposed for this one gold event - at most one can be it

**Our row 177178 (event 149911) says:**

> On July 22, 2025, EnerSys announced a reduction in force plan (the "Plan") as part of EnerSys' strategic restructuring plan under its new leadership to better align resources with current business priorities and long-term objectives. The Plan is expected to reduce EnerSys' non-production global workforce by approximately 11%, or approximately 575 employees, and is focused primarily on corporate and management positions.

- count matches the filing exactly
- announcement date is the filing date
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** 2 different tracker rows are proposed for this one gold event - at most one can be it

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'reduce ... global workforce by approximately 11%, or approximately 575 employees'
- `match_notes`: Only EnerSys row is an undated ERM record for Bulgaria (400). Nothing represents the 575-employee July 2025 plan.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001289308-25-000025 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149625 149911
python3 railway/recall_adjudicate.py --reject sec-205-0001289308-25-000025 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149625 149911
```

---

## The misses that are NOT in this queue

4 of the 33 unmatched gold events have acquired no row that the alias-and-window rule proposes. There is nothing to decide about them here; they are listed because the first question anyone asks of a recovery count is what happened to the rest. Every row shown matches the employer alias at ANY date, which is wider than the matching rule on purpose.

### CODEXIS, INC. — 46, filed 2025-11-06

`sec-205-0001193125-25-269716` — `not_matched` — <https://www.sec.gov/Archives/edgar/data/1200375/000119312525269716/d80118d8k.htm>

| tracker event | company as we hold it | count | effective | announced | source |
|---|---|---:|---|---|---|
| 5973 | Codexis, Inc. | 28 | 2023-09-30 | 2023-07-20 | warn |
| 5974 | Codexis, Inc. | 31 | 2023-09-30 | 2023-07-20 | warn |

- `match_notes`: Codexis rows exist but are 2023 events.

### HP INC — 4,000, filed 2025-11-25

`sec-205-0000047217-25-000068` — `not_matched` — <https://www.sec.gov/Archives/edgar/data/47217/000004721725000068/hpq-20251125.htm>

| tracker event | company as we hold it | count | effective | announced | source |
|---|---|---:|---|---|---|
| 82197 | HP Pelzer | 103 | (none) | (none) | erm |
| 89419 | HP Foods | 125 | (none) | (none) | erm |
| 92581 | HP Deutschland | 1100 | (none) | (none) | erm |
| 92654 | HP - Compaq | 165 | (none) | (none) | erm |
| 92670 | HP - Compaq | 325 | (none) | (none) | erm |
| 92691 | HP - Compaq | 1580 | (none) | (none) | erm |
| 92692 | HP - Compaq | 1206 | (none) | (none) | erm |
| 92704 | HP - Compaq | 5900 | (none) | (none) | erm |
| 92830 | HP - Compaq | 15000 | (none) | (none) | erm |
| 139513 | HP Inc. | 74 | 2016-01-22 | (none) | warn |
| 40739 | HP Inc. | 3000 | 2016-10-14 | (none) | erm |
| 40498 | HP Inc | 500 | 2017-02-08 | (none) | erm |
| 35397 | HP Composites | 100 | 2025-09-05 | (none) | erm |

Previously rejected for this event: [35397].

- `match_notes`: No HP Inc row after 2017. The only in-window candidate, 'HP Composites', is a different company.

### WABASH NATIONAL Corp — 270, filed 2026-01-05

`sec-205-0000879526-26-000003` — `not_matched` — <https://www.sec.gov/Archives/edgar/data/879526/000087952626000003/wnc-20260105.htm>

| tracker event | company as we hold it | count | effective | announced | source |
|---|---|---:|---|---|---|
| 144268 | Wabash National | 790 | 2009-05-01 | 2009-05-01 | warn |
| 1466 | Wabash National LP | 6 | 2026-03-06 | 2026-01-05 | warn |
| 1467 | Wabash National LP | 94 | 2026-03-06 | 2026-01-05 | warn |

Previously rejected for this event: [1467, 1466].

- `match_notes`: The filing idles Little Falls, Minnesota and Goshen, Indiana. The only in-window Wabash rows are CA WARN (94+6), a different site.

### PLAYSTUDIOS, Inc.  (MYPS, MYPSW) — 177, filed 2026-03-16

`sec-205-0001823878-26-000018` — `not_matched` — <https://www.sec.gov/Archives/edgar/data/1823878/000182387826000018/myps-20260310.htm>

**No row of any kind, at any date, for this employer.**

- `match_notes`: No PLAYSTUDIOS row in the tracker at any date.

