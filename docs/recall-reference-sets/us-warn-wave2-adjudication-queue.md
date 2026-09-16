# US WARN reference set — adjudication sheet

Built `2026-09-16T10:30:40Z` from a measurement taken `2026-09-16T10:30:33Z`. **Rebuild it before deciding** (`python3 railway/warn_adjudication_pack.py --write`) — it reads live data and live data moves.

Reference set: `us-warn-il-oh-pa-2025-07_2026-06`. Definition: [`docs/recall-reference-sets/US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md`](../../docs/recall-reference-sets/US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md). Nothing in this set is published anywhere, and nothing in it touches the SEC Item 2.05 figure.

**65 events are pending** across both strata, carrying 78 candidate rows between them. 16 event(s) have no candidate row at all and are dealt with first, below, because they are a different question.

## The range, before you start

The primary sample is 75 events. 0 are editor-confirmed today. Of the 61 pending, **47** have a proposed row that agrees on count, on date basis and on employer name and is proposed for no other notice; **5** agree on count and date basis but we store a shorter employer string than the state publishes; **9** have something else to read. **14** has no proposed row.

Four arithmetics. They are arithmetic, not targets, and none of them is a prediction about how the entries below should go:

- every pending event accepted, and the event with no candidate row resolved in our favour too: **75/75 = 100.0%  (Wilson 95% CI [95.1%, 100.0%], width 4.9%)**
- every pending event accepted, the event with no candidate row not: **61/75 = 81.3%  (Wilson 95% CI [71.1%, 88.5%], width 17.5%)**
- only the events whose proposed row agrees on count, on date basis and on employer name, and is not also proposed for another notice: **47/75 = 62.7%  (Wilson 95% CI [51.4%, 72.7%], width 21.4%)**
- nothing accepted (the figure as it stands today): **0/75 = 0.0%  (Wilson 95% CI [0.0%, 4.9%], width 4.9%)**

The 500-plus census is reported separately and is never pooled with the sample, so deciding a census event does not move any of the four figures above.

## The event with no candidate row: Claires Stores, Inc. (IL)

`warn-il-2025-08-05-claires-stores` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-05**, effective 2025-08-04..2025-08-04
- **46** affected across 1 published row(s)
  - Claires Stores, Inc. — 46 — Hoffman Estates, IL 60192 — effective 2025-08-04 — `2025-08 monthly report, data row 2`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Aug%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-07-06 .. 2026-09-09

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-08-05-claires-stores \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2025-08-05-claires-stores \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Zeco Systems, Inc. (IL)

`warn-il-2025-08-18-zeco-systems` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-18**, effective 2025-10-31..2025-10-31
- **6** affected across 1 published row(s)
  - Zeco Systems, Inc. — 6 — Los Angeles, CA 90021 — effective 2025-10-31 — `2025-08 monthly report, data row 6`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Aug%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-07-19 .. 2026-09-22

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-08-18-zeco-systems \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2025-08-18-zeco-systems \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Adare Pharmaceuticals, Inc. (IL)

`warn-il-2025-12-01-adare-pharmaceuticals` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-01**, effective 2026-02-02..2026-02-02
- **21** affected across 1 published row(s)
  - Adare Pharmaceuticals, Inc. — 21 — Aurora, IL 60502 — effective 2026-02-02 — `2025-12 monthly report, data row 2`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Dec%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-11-01 .. 2027-01-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-12-01-adare-pharmaceuticals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2025-12-01-adare-pharmaceuticals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Gerresheimer Moulded Glass Chicago Inc. (IL)

`warn-il-2026-04-13-gerresheimer-moulded-glass-chicago` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-13**, effective 2026-09-30..2026-09-30
- **172** affected across 1 published row(s)
  - Gerresheimer Moulded Glass Chicago Inc. — 172 — Chicago Heights, IL 60411 — effective 2026-09-30 — `2026-04 monthly report, data row 4`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/April2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-03-14 .. 2027-05-18

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-04-13-gerresheimer-moulded-glass-chicago \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2026-04-13-gerresheimer-moulded-glass-chicago \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: GXO Logistics Supply Chain, Inc (OH)

`warn-oh-2026-04-28-gxo-logistics-supply-chain` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-28**, effective 2026-05-02..2026-05-02
- **102** affected across 1 published row(s)
  - GXO Logistics Supply Chain, Inc — 102 — West Jefferson/Madison — effective 2026-05-02 — `2026 CSV, data row 28`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-03-29 .. 2027-06-02

**What we hold — row `143143` (event `115978`)**

| | the state's notice | our row `143143` |
|---|---|---|
| employer | GXO Logistics Supply Chain, Inc | GXO Logistics |
| count | 102 | 192 |
| notice date | 2026-04-28 | (we store none) |
| effective date | 2026-05-02..2026-05-02 | 2024-01-15 |
| state | OH | OH |
| source | https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv | `warn` / `OH WARN notice` |
| the URL we cite | — | <https://jfs.ohio.gov/static/warn/WARN%202023/GXO.pdf> |

- count: DIFFERS by +90 — we hold 192, the notice totals 102 across rows of 102
- dates: our 2024-01-15 is neither the notice date (-834 days) nor a published effective date (-838 days from 2026-05-02)
- inside the rule's match window: **no**

> Layoff at GXO Logistics in Groveport. 192 employees affected, effective 2024-01-15. Filed under the OH WARN Act.

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-04-28-gxo-logistics-supply-chain \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids 143143
python3 railway/warn_adjudicate.py --reject warn-oh-2026-04-28-gxo-logistics-supply-chain \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids 143143
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Fourth Street Barbecue, Inc. (PA)

`warn-pa-2025-10-01-fourth-street-barbecue` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-01**, effective 2025-10-09..2025-10-09
- **252** affected across 1 published row(s)
  - Fourth Street Barbecue, Inc. — 252 — Washington; 3 Arentzen Boulevard, Charleroi, PA  15022 — effective 2025-10-09 — `2025 > October > accordion item 80`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-10>
- the rule's match window: 2025-09-01 .. 2026-11-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-10-01-fourth-street-barbecue \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-10-01-fourth-street-barbecue \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: DuBois Logistics, LLC (PA)

`warn-pa-2025-11-01-dubois-logistics` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-01**, effective 2026-01-31..2026-01-31
- **110** affected across 1 published row(s)
  - DuBois Logistics, LLC — 110 — Clearfield; 891 Beaver Drive, DuBois, PA  15801 — effective 2026-01-31 — `2025 > November > accordion item 68`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11>
- the rule's match window: 2025-10-02 .. 2026-12-06

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-11-01-dubois-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-11-01-dubois-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Adare Pharmaceuticals, Inc. (PA)

`warn-pa-2025-12-01-adare-pharmaceuticals` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-01**, effective 2026-03-01..2026-03-01
- **137** affected across 1 published row(s)
  - Adare Pharmaceuticals, Inc. — 137 — Philadelphia; 1100 Orthodox Street, Philadelphia, PA  19124 — effective 2026-03-01 — `2025 > December > accordion item 62`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12>
- the rule's match window: 2025-11-01 .. 2027-01-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-12-01-adare-pharmaceuticals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-12-01-adare-pharmaceuticals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: S&S Activewear (PA)

`warn-pa-2025-12-01-s-s-activewear` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-01**, effective 2025-12-04..2025-12-04
- **128** affected across 1 published row(s)
  - S&S Activewear — 128 — York; 600 Industrial Drive, Lewisberry, PA  17339 — effective 2025-12-04 — `2025 > December > accordion item 63`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12>
- the rule's match window: 2025-11-01 .. 2027-01-05

**What we hold — row `139254` (event `24010`)**

| | the state's notice | our row `139254` |
|---|---|---|
| employer | S&S Activewear | S&S Activewear |
| count | 128 | 218 |
| notice date | 2025-12-01 | (we store none) |
| effective date | 2025-12-04..2025-12-04 | 2025-04-09 |
| state | PA | PA |
| source | https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12 | `warn` / `PA WARN notice` |
| the URL we cite | — | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- count: DIFFERS by +90 — we hold 218, the notice totals 128 across rows of 128
- dates: our 2025-04-09 is neither the notice date (-236 days) nor a published effective date (-239 days from 2025-12-04)
- inside the rule's match window: **no**

> Closing at S&S Activewear. 218 employees affected, effective 2025-04-09. Filed under the PA WARN Act.

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-12-01-s-s-activewear \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids 139254
python3 railway/warn_adjudicate.py --reject warn-pa-2025-12-01-s-s-activewear \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids 139254
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Miller’s Ale House (PA)

`warn-pa-2026-01-01-miller-s-ale-house` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-01**, effective 2026-03-30..2026-03-30
- **49** affected across 1 published row(s)
  - Miller’s Ale House — 49 — Philadelphia; 9495 East Roosevelt Boulevard — effective 2026-03-30 — `2026 > January > accordion item 56`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-01>
- the rule's match window: 2025-12-02 .. 2027-02-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-01-01-miller-s-ale-house \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-01-01-miller-s-ale-house \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: BPM Limited (PA)

`warn-pa-2026-02-01-bpm` — stratum `primary`, size band `M`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-01**, effective 2026-03-29..2026-03-29
- **248** affected across 1 published row(s)
  - BPM Limited — 248 — Chester; **UPDATED TO REVISE AFFECTED TOTAL** — effective 2026-03-29 — `2026 > February > accordion item 48`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-02>
- the rule's match window: 2026-01-02 .. 2027-03-08

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-02-01-bpm \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-02-01-bpm \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Dometic (PA)

`warn-pa-2026-05-01-dometic` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-01**, effective 2026-09-21..2026-09-21
- **89** affected across 1 published row(s)
  - Dometic — 89 — Montgomery; 640 North Lewis Road, Limerick, PA  19468 — effective 2026-09-21 — `2026 > May > accordion item 26`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-05>
- the rule's match window: 2026-04-01 .. 2027-06-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-05-01-dometic \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-05-01-dometic \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Juvenile Justice Center of Philadelphia (PA)

`warn-pa-2026-05-01-juvenile-justice-center-of` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-01**, effective 2026-04-30..2026-04-30
- **17** affected across 1 published row(s)
  - Juvenile Justice Center of Philadelphia — 17 — Philadelphia; 100 West Coulter Street, Philadelphia, PA 19144 — effective 2026-04-30 — `2026 > May > accordion item 29`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-05>
- the rule's match window: 2026-04-01 .. 2027-06-05

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-05-01-juvenile-justice-center-of \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-05-01-juvenile-justice-center-of \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: American Expediting Logistics, LLC (PA)

`warn-pa-2026-06-01-american-expediting-logistics` — stratum `primary`, size band `S`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-06-01**, effective 2026-06-04..2026-06-04
- **86** affected across 1 published row(s)
  - American Expediting Logistics, LLC — 86 — Delaware; 1400 North Providence Road, Suite 410, Media, PA  19063 — effective 2026-06-04 — `2026 > June > accordion item 19`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-06>
- the rule's match window: 2026-05-02 .. 2027-07-06

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-06-01-american-expediting-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-06-01-american-expediting-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Amazon Fresh (IL)

`warn-il-2026-01-28-amazon-fresh` — stratum `large_census`, size band `L`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-28**, effective 2026-04-28..2026-04-28
- **1,545** affected across 10 published row(s)
  - Amazon Fresh — 132 — Naperville, IL 60564 — effective 2026-04-28 — `2026-01 monthly report, data row 2`
  - Amazon Fresh — 134 — Schaumburg, IL 60173 — effective 2026-04-28 — `2026-01 monthly report, data row 3`
  - Amazon Fresh — 179 — Morton Grove, IL 60053 — effective 2026-04-28 — `2026-01 monthly report, data row 4`
  - Amazon Fresh — 220 — Oak Lawn, IL 60453 — effective 2026-04-28 — `2026-01 monthly report, data row 5`
  - Amazon Fresh — 132 — Bloomingdale, IL 60108 — effective 2026-04-28 — `2026-01 monthly report, data row 6`
  - Amazon Fresh — 173 — Norridge, IL 60706 — effective 2026-04-28 — `2026-01 monthly report, data row 7`
  - Amazon Fresh — 155 — North Riverside, IL 60546 — effective 2026-04-28 — `2026-01 monthly report, data row 8`
  - Amazon Fresh — 118 — Naperville, IL 60563 — effective 2026-04-28 — `2026-01 monthly report, data row 9`
  - Amazon Fresh — 170 — Tinley Park, IL 60477 — effective 2026-04-28 — `2026-01 monthly report, data row 10`
  - Amazon Fresh — 132 — Arlington Heights, IL 60004 — effective 2026-04-28 — `2026-01 monthly report, data row 11`
- source: <https://www.illinoisworknet.com/_layouts/15/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Jan2026MonthlyWARNReport.xlsx>
- the rule's match window: 2025-12-29 .. 2027-03-04

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-01-28-amazon-fresh \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2026-01-28-amazon-fresh \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The event with no candidate row: Franciscan Alliance, Inc. (IL)

`warn-il-2026-02-05-franciscan-alliance` — stratum `large_census`, size band `L`, currently `not_matched`. **This is its own decision, not a row in the list below.** The matching rule proposes nothing for it, so there is no candidate to accept or reject in the ordinary way; what follows is every row we hold for this employer at ANY date, fetched with no window applied.

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-05**, effective 2026-04-01..2026-04-01
- **1,864** affected across 2 published row(s)
  - Franciscan Alliance, Inc. — 1535 — Olympia Fields, IL 60461 — effective 2026-04-01 — `2026-02 monthly report, data row 7`
  - Franciscan Alliance, Inc. — 329 — Chicago Heights, IL 60411 — effective 2026-04-01 — `2026-02 monthly report, data row 8`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-01-06 .. 2027-03-12

**No row of any kind, at any date, for this employer.**

Two decisions are available and this file states neither as preferred:

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-02-05-franciscan-alliance \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
python3 railway/warn_adjudicate.py --reject warn-il-2026-02-05-franciscan-alliance \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <row id>
```

Accepting it is a statement that the row above IS this notice and that the matching rule's window missed it. Rejecting it is a statement that it is not, or that it cannot be told apart. The window was deliberately not widened to catch it, so **no decision here changes the rule** — the rule is frozen in the definition document and changing it is a separate, evidenced amendment.

---

## The index

**Every line below describes exactly ONE candidate row, named by its id.** An event with four candidates does not get four clauses on one line: it gets one line for the row the rule proposes first, carrying only that row's evidence, and the ids of the others beside it carrying none of theirs. Each of those rows has its own block in the section below. That is not a formatting preference — on 2026-08-12 a pooled summary line on the SEC sheet described a co-proposed row and a correct Dow row was rejected because of it.

Ordering is by how much there is to read, not by how likely an accept is. The events where every field lines up come first because they are quick to CHECK.

Nothing here is pre-ticked, and no line states a preferred outcome.

| # | the notice | notified | our row | count | dates | look twice — this row only | other rows in window |
|---:|---|---:|---|---|---|---|---|
| 1 | [Compass Group](#1-il-compass-group) (IL, 2025-07-14) | 73 | `138181` (event 111016) | **27** = one published row, exact (notice total 73) | 2025-07-14 = notice date | nothing — row `138181` lines up on every field checked | none |
| 2 | [Carolina Therapeutic Services](#2-il-carolina-therapeutic-services) (IL, 2025-09-26) | 27 | `137546` (event 110381) | **27** = notice total, exact | 2025-09-26 = published effective date | nothing — row `137546` lines up on every field checked | none |
| 3 | [Chartwells at DePaul University](#3-il-chartwells-at-depaul-university) (IL, 2025-10-01) | 138 | `137443` (event 110278) | **138** = notice total, exact | 2025-10-01 = notice date | nothing — row `137443` lines up on every field checked | none |
| 4 | [PharmaCann, Inc.](#4-il-pharmacann--inc) (IL, 2025-11-14) | 82 | `137008` (event 109843) | **82** = notice total, exact | 2025-11-14 = notice date | nothing — row `137008` lines up on every field checked | none |
| 5 | [Alton Steel, Inc.](#5-il-alton-steel--inc) (IL, 2026-01-27) | 253 | `136291` (event 109126) | **253** = notice total, exact | 2026-01-27 = notice date | nothing — row `136291` lines up on every field checked | none |
| 6 | [Alverno Laboratories (at Franciscan Health O](#6-il-alverno-laboratories--at-franciscan-health-olympia) (IL, 2026-02-02) | 66 | `136195` (event 109030) | **66** = notice total, exact | 2026-02-02 = notice date | nothing — row `136195` lines up on every field checked | none |
| 7 | [Aspira Inc. of Illinois](#7-il-aspira-inc--of-illinois) (IL, 2026-03-06) | 57 | `135973` (event 108808) | **57** = notice total, exact | 2026-03-06 = notice date | nothing — row `135973` lines up on every field checked | none |
| 8 | [Trinity Christian College](#8-il-trinity-christian-college) (IL, 2026-03-20) | 107 | `135845` (event 108680) | **107** = notice total, exact | 2026-03-20 = notice date | nothing — row `135845` lines up on every field checked | none |
| 9 | [KLEO Community Family Life Center](#9-il-kleo-community-family-life-center) (IL, 2026-04-29) | 65 | `135340` (event 108175) | **65** = notice total, exact | 2026-04-29 = notice date | nothing — row `135340` lines up on every field checked | none |
| 10 | [MDMartin LLC](#10-il-mdmartin-llc) (IL, 2026-05-19) | 160 | `135119` (event 107954) | **160** = notice total, exact | 2026-05-19 = notice date | nothing — row `135119` lines up on every field checked | none |
| 11 | [Quality Built, LLC](#11-oh-quality-built--llc) (OH, 2025-07-07) | 1 | `138286` (event 111121) | **1** = notice total, exact | 2025-07-03 = published effective date | nothing — row `138286` lines up on every field checked | none |
| 12 | [Sarepta Therapeutics, Inc.](#12-oh-sarepta-therapeutics--inc) (OH, 2025-07-16) | 80 | `138133` (event 110968) | **80** = notice total, exact | 2025-07-18 = published effective date | nothing — row `138133` lines up on every field checked | none |
| 13 | [First Student](#13-oh-first-student) (OH, 2025-08-18) | 39 | `137882` (event 110717) | **39** = notice total, exact | 2025-08-20 = published effective date | nothing — row `137882` lines up on every field checked | none |
| 14 | [FedEx Supply Chain, Inc](#14-oh-fedex-supply-chain--inc) (OH, 2025-08-28) | 56 | `137188` (event 110023) | **56** = notice total, exact | 2025-10-31 = published effective date | nothing — row `137188` lines up on every field checked | none |
| 15 | [Augusta Sportswear, Inc.](#15-oh-augusta-sportswear--inc) (OH, 2025-10-08) | 58 | `136264` (event 109099) | **58** = notice total, exact | 2026-01-30 = published effective date | nothing — row `136264` lines up on every field checked | none |
| 16 | [Nordstrom Credit Operations](#16-oh-nordstrom-credit-operations) (OH, 2025-11-19) | 1 | `136221` (event 109056) | **1** = notice total, exact | 2026-02-01 = published effective date | nothing — row `136221` lines up on every field checked | none |
| 17 | [PK Management](#17-oh-pk-management) (OH, 2025-12-04) | 67 | `136220` (event 109055) | **67** = notice total, exact | 2026-02-01 = published effective date | nothing — row `136220` lines up on every field checked | none |
| 18 | [Double Tree Cleveland](#18-oh-double-tree-cleveland) (OH, 2026-01-06) | 66 | `136284` (event 109119) | **66** = notice total, exact | 2026-01-28 = published effective date | nothing — row `136284` lines up on every field checked | none |
| 19 | [Turf Care Supply Corp.](#19-oh-turf-care-supply-corp) (OH, 2026-01-12) | 46 | `136036` (event 108871) | **46** = notice total, exact | 2026-02-28 = published effective date | nothing — row `136036` lines up on every field checked | none |
| 20 | [Fresenius USA Manufacturing](#20-oh-fresenius-usa-manufacturing) (OH, 2026-01-29) | 54 | `135598` (event 108433) | **54** = notice total, exact | 2026-04-10 = published effective date | nothing — row `135598` lines up on every field checked | none |
| 21 | [Astrion](#21-oh-astrion) (OH, 2026-02-09) | 61 | `135005` (event 107840) | **61** = notice total, exact | 2026-05-31 = published effective date | nothing — row `135005` lines up on every field checked | none |
| 22 | [Lowe's Companies](#22-oh-lowe-s-companies) (OH, 2026-02-16) | 17 | `135485` (event 108320) | **17** = notice total, exact | 2026-04-19 = published effective date | nothing — row `135485` lines up on every field checked | none |
| 23 | [Parsec, LLC](#23-oh-parsec--llc) (OH, 2026-02-23) | 115 | `135293` (event 108128) | **115** = notice total, exact | 2026-05-01 = published effective date | nothing — row `135293` lines up on every field checked | none |
| 24 | [Ten Sixty Logistics LLC](#24-oh-ten-sixty-logistics-llc) (OH, 2026-03-19) | 125 | `135765` (event 108600) | **125** = notice total, exact | 2026-03-31 = published effective date | nothing — row `135765` lines up on every field checked | none |
| 25 | [Technicote Inc dba Beontag](#25-oh-technicote-inc-dba-beontag) (OH, 2026-03-25) | 53 | `135079` (event 107914) | **53** = notice total, exact | 2026-05-24 = published effective date | nothing — row `135079` lines up on every field checked | none |
| 26 | [Venture Solutions/Taylor Technology Services](#26-oh-venture-solutions-taylor-technology-services) (OH, 2026-04-22) | 60 | `134735` (event 107570) | **60** = notice total, exact | 2026-06-22 = published effective date | nothing — row `134735` lines up on every field checked | none |
| 27 | [Pioneer Cladding & Glazing Systems, Inc.](#27-oh-pioneer-cladding---glazing-systems--inc) (OH, 2026-06-10) | 43 | `134191` (event 107026) | **43** = notice total, exact | 2026-08-09 = published effective date | nothing — row `134191` lines up on every field checked | none |
| 28 | [ACC Premiere](#28-pa-acc-premiere) (PA, 2025-07-01) | 67 | `137598` (event 23930) | **67** = notice total, exact | 2025-09-19 = published effective date | nothing — row `137598` lines up on every field checked | none |
| 29 | [Century Therapeutics, LLC](#29-pa-century-therapeutics--llc) (PA, 2025-07-01) | 72 | `138208` (event 23957) | **72** = notice total, exact | 2025-07-11 = published effective date | nothing — row `138208` lines up on every field checked | none |
| 30 | [Air Products and Chemicals, Inc.](#30-pa-air-products-and-chemicals--inc) (PA, 2025-09-01) | 14 | `136970` (event 23894) | **14** = notice total, exact | 2025-11-17 = published effective date | nothing — row `136970` lines up on every field checked | none |
| 31 | [HMS Host (located within the Philadelphia In](#31-pa-hms-host--located-within-the-philadelphia-internat) (PA, 2025-09-01) | 13 | `137230` (event 23906) | **13** = notice total, exact | 2025-10-27 = published effective date | nothing — row `137230` lines up on every field checked | none |
| 32 | [Trujacodi Delivery Express](#32-pa-trujacodi-delivery-express) (PA, 2025-09-01) | 42 | `137652` (event 23933) | **42** = notice total, exact | 2025-09-12 = published effective date | nothing — row `137652` lines up on every field checked | none |
| 33 | [Peraton, Inc.](#33-pa-peraton--inc) (PA, 2025-10-01) | 153 | `136768` (event 23885) | **153** = notice total, exact | 2025-12-13 = published effective date | nothing — row `136768` lines up on every field checked | none |
| 34 | [Vifor Pharma, Inc.](#34-pa-vifor-pharma--inc) (PA, 2025-10-01) | 55 | `136851` (event 23891) | **55** = notice total, exact | 2025-12-01 = published effective date | nothing — row `136851` lines up on every field checked | none |
| 35 | [Amazon Fresh](#35-pa-amazon-fresh) (PA, 2026-01-01) | 983 | `135412` (event 23810) | **983** = notice total, exact | 2026-04-28 = published effective date | nothing — row `135412` lines up on every field checked | none |
| 36 | [Post Consumer Brands, LLC](#36-pa-post-consumer-brands--llc) (PA, 2026-02-01) | 11 | `135281` (event 23807) | **11** = notice total, exact | 2026-05-01 = published effective date | nothing — row `135281` lines up on every field checked | none |
| 37 | [Federal Express Corporation](#37-pa-federal-express-corporation) (PA, 2026-03-01) | 63 | `135251` (event 23806) | **63** = notice total, exact | 2026-05-02 = published effective date | nothing — row `135251` lines up on every field checked | none |
| 38 | [PharmaCann, Inc.](#38-pa-pharmacann--inc) (PA, 2026-03-01) | 60 | `135113` (event 23796) | **60** = notice total, exact | 2026-05-20 = published effective date | nothing — row `135113` lines up on every field checked | none |
| 39 | [Advantest, Inc.](#39-pa-advantest--inc) (PA, 2026-04-01) | 55 | `134613` (event 23783) | **55** = notice total, exact | 2026-06-30 = published effective date | nothing — row `134613` lines up on every field checked | none |
| 40 | [LNS Chipblaster](#40-pa-lns-chipblaster) (PA, 2026-04-01) | 67 | `133970` (event 23769) | **67** = notice total, exact | 2026-09-30 = published effective date | nothing — row `133970` lines up on every field checked | none |
| 41 | [Winston Brands, Inc.](#41-il-winston-brands--inc) (IL, 2025-10-23) | 163 | `137259` (event 110094) | **90** = one published row, exact (notice total 163) | 2025-10-23 = notice date | nothing — row `137259` lines up on every field checked | `137258` |
| 42 | [Premier Healthcare Solutions DBA Contigo Hea](#42-oh-premier-healthcare-solutions-dba-contigo-health) (OH, 2025-10-27) | 175 | `176837` (event 149570) | **175** = notice total, exact | 2026-01-16 = published effective date | nothing — row `176837` lines up on every field checked | `136620` |
| 43 | [JeniusBank SMBC Manubank](#43-oh-jeniusbank-smbc-manubank) (OH, 2026-01-08) | 2 | `135932` (event 108767) | **2** = notice total, exact | 2026-03-10 = published effective date | nothing — row `135932` lines up on every field checked | `134233` |
| 44 | [Saks & Company LLC Beachwood](#44-oh-saks---company-llc-beachwood) (OH, 2026-03-06) | 70 | `135219` (event 108054) | **70** = notice total, exact | 2026-05-06 = published effective date | nothing — row `135219` lines up on every field checked | `135579` |
| 45 | [Advanced Specialty Hospitals of Toledo](#45-oh-advanced-specialty-hospitals-of-toledo) (OH, 2026-04-09) | 116 | `134903` (event 107738) | **116** = notice total, exact | 2026-06-08 = published effective date | nothing — row `134903` lines up on every field checked | `175819` |
| 46 | [Pottstown Hospital](#46-pa-pottstown-hospital) (PA, 2025-11-01) | 131 | `136561` (event 23877) | **131** = notice total, exact | 2026-01-01 = published effective date | nothing — row `136561` lines up on every field checked | `176699` |
| 47 | [GIANT Company, LLC](#47-pa-giant-company--llc) (PA, 2025-12-01) | 204 | `136136` (event 23847) | **128** = one published row, exact (notice total 204) | 2026-02-13 = published effective date | nothing — row `136136` lines up on every field checked | `136049`, `135665` |
| 48 | [Fervalue USA LLC](#48-il-fervalue-usa-llc) (IL, 2025-10-08) | 72 | `137334` (event 110169) | **72** = notice total, exact | 2025-10-08 = notice date | we store the employer as 'Fervalue USA, LLC'; the state publishes it as 'Fervalue USA LLC' | none |
| 49 | [Consolidated Hospitality Supplies](#49-il-consolidated-hospitality-supplies) (IL, 2025-11-05) | 45 | `137082` (event 109917) | **45** = notice total, exact | 2025-11-05 = notice date | we store the employer as 'Consolidated Hospitality Supplies, LLC'; the state publishes it as 'Consolidated Hospitality Supplies' | none |
| 50 | [Heartland Human Care Services](#50-il-heartland-human-care-services) (IL, 2026-04-01) | 240 | `135690` (event 108525) | **120** = one published row, exact (notice total 240) | 2026-04-01 = notice date | we store the employer as 'Heartland Human Care Services (ICRC)'; the state publishes it as 'Heartland Human Care Services' | none |
| 51 | [Optum Services, Inc.](#51-il-optum-services--inc) (IL, 2026-06-05) | 98 | `134921` (event 107756) | **98** = notice total, exact | 2026-06-05 = notice date | we store the employer as 'Optum Services, Inc'; the state publishes it as 'Optum Services, Inc.' | none |
| 52 | [Vistra Corp. - Baldwin Power Plant](#52-il-vistra-corp----baldwin-power-plant) (IL, 2026-05-04) | 304 | `135231` (event 108066) | **99** = one published row, exact (notice total 304) | 2026-05-04 = notice date | we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant' | `135230`, `135229` |
| 53 | [Penske Logistics LLC](#53-il-penske-logistics-llc) (IL, 2025-09-05) | 37 | `137667` (event 110502) | **37** = notice total, exact | 2025-09-09, neither basis (+4 d from notice) | our 2025-09-09 is neither the notice date (+4 days) nor a published effective date (-56 days from 2025-11-04) | none |
| 54 | [Rising Pharma Holdings](#54-il-rising-pharma-holdings) (IL, 2025-09-15) | 86 | `137637` (event 110472) | **99** vs 86, off by +13 | 2025-09-15 = notice date | DIFFERS by +13 — we hold 99, the notice totals 86 across rows of 86 | none |
| 55 | [Everest Insurance](#55-il-everest-insurance) (IL, 2025-12-22) | 37 | `136700` (event 109535) | **38** vs 37, off by +1 | 2025-12-22 = notice date | DIFFERS by +1 — we hold 38, the notice totals 37 across rows of 37 | none |
| 56 | [Walgreens](#56-il-walgreens) (IL, 2026-02-10) | 469 | `175785` (event 148617) | **628** vs 469, off by +159 | 2026-02-19, neither basis (+9 d from notice) | our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event; DIFFERS by +159 — we hold 628, the notice totals 469 across rows of 416, 52, 1; our 2026-02-19 is neither the notice date (+9 days) nor a published effective date (+9 days from 2026-02-10) | none |
| 57 | [First Brands Group, LLC (Albion Air Facility](#57-il-first-brands-group--llc--albion-air-facility) (IL, 2026-02-23) | 642 | `136187` (event 109022) | **389** vs 642, off by -253 | 2026-02-03, neither basis (-20 d from notice) | DIFFERS by -253 — we hold 389, the notice totals 642 across rows of 114, 48, 435, 45; our 2026-02-03 is neither the notice date (-20 days) nor a published effective date (-20 days from 2026-02-23) | none |
| 58 | [TOPS Products](#58-oh-tops-products) (OH, 2025-09-24) | 207 | `136862` (event 109697) | **207** = notice total, exact | 2025-12-01, neither basis (+68 d from notice) | our 2025-12-01 is neither the notice date (+68 days) nor a published effective date (-487 days from 2027-04-02) | none |
| 59 | [Weaber, Inc.](#59-pa-weaber--inc) (PA, 2025-07-01) | 145 | `137844` (event 23942) | **46** vs 145, off by -99 | 2025-08-25, neither basis (+55 d from notice) | DIFFERS by -99 — we hold 46, the notice totals 145 across rows of 145; our 2025-08-25 is neither the notice date (+55 days) nor a published effective date (-1 days from 2025-08-26) | none |
| 60 | [First Brands Group Cuyahoga 4](#60-oh-first-brands-group-cuyahoga-4) (OH, 2026-05-01) | 110 | `175799` (event 148624) | **256** vs 110, off by +146 | 2026-04-30, neither basis (-1 d from notice) | our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event; DIFFERS by +146 — we hold 256, the notice totals 110 across rows of 110; our 2026-04-30 is neither the notice date (-1 days) nor a published effective date (+62 days from 2026-02-27); row `175799` is also proposed for 1 other reference event(s) — warn-oh-2026-02-27-first-brands-darke — and at most one of them can be it | `135331` |
| 61 | [First Brands Group Darke](#61-oh-first-brands-group-darke) (OH, 2026-02-27) | 302 | `135331` (event 108166) | **302** = notice total, exact | 2026-04-30 = published effective date | row `135331` is also proposed for 1 other reference event(s) — warn-oh-2026-05-01-first-brands-cuyahoga-4 — and at most one of them can be it | `136086`, `175799` |
| 62 | [Crothall and Morrison Healthcare](#62-pa-crothall-and-morrison-healthcare) (PA, 2025-11-01) | 795 | `136211` (event 23857) | **795** = notice total, exact | 2026-02-01 = published effective date | nothing — row `136211` lines up on every field checked | none |
| 63 | [Liberty Home Choices](#63-pa-liberty-home-choices) (PA, 2026-03-01) | 615 | `135077` (event 23794) | **615** = notice total, exact | 2026-05-24 = published effective date | nothing — row `135077` lines up on every field checked | none |
| 64 | [JBS Souderton](#64-pa-jbs-souderton) (PA, 2026-06-01) | 1,485 | `134165` (event 23773) | **1,485** = notice total, exact | 2026-08-14 = published effective date | nothing — row `134165` lines up on every field checked | none |
| 65 | [Ideal US Talent Worker OpCo LLC](#65-il-ideal-us-talent-worker-opco-llc) (IL, 2026-05-04) | 1,395 | `135233` (event 108068) | **1,395** = notice total, exact | 2026-05-04 = notice date | we store the employer as 'Ideal US Talent Systems Worker Opco LLC'; the state publishes it as 'Ideal US Talent Worker OpCo LLC' | none |

## Recording a decision

Separate program, network-free, and it refuses a decision with no name, no reason or no row id on it. Running the same decision twice records it once; a different decision on an already-decided event is refused and told to revert first; `--revert` restores the event exactly, including a key that was absent.

```
python3 railway/warn_adjudicate.py --accept <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...
python3 railway/warn_adjudicate.py --reject <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...' --row-ids <tracker_row_id> ...
python3 railway/warn_adjudicate.py --revert <reference_row_id> \
    --reviewed-by 'Your Name' --reason '...'
python3 railway/warn_adjudicate.py --verify
```

---

## 1. Compass Group (IL)

`warn-il-2025-07-14-compass` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-14**, effective 2025-08-28..2025-08-28
- **73** affected across 4 published row(s)
  - Compass Group — 15 — Aurora, IL 60506 — effective 2025-08-28 — `2025-07 monthly report, data row 2`
  - Compass Group — 10 — Kankakee, IL 60901 — effective 2025-08-28 — `2025-07 monthly report, data row 3`
  - Compass Group — 21 — Park Ridge, IL 60068 — effective 2025-08-28 — `2025-07 monthly report, data row 4`
  - Compass Group — 27 — Joliet, IL 60435 — effective 2025-08-28 — `2025-07 monthly report, data row 5`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/July%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-06-14 .. 2026-08-18

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138181` — event `111016` — tier `exact`

| | the state's notice | our row `138181` |
|---|---|---|
| employer | Compass Group | Compass Group |
| count | 73 | 27 |
| notice date | 2025-07-14 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-08-28..2025-08-28 | 2025-07-14 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/July%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 27 is one of the 4 rows the state published under this notice (total 73)
- **dates**: agree on the NOTICE basis — our 2025-07-14 is the notice date; the state published effective 2025-08-28
- **employer name**: matches the state's published string
- **live now**: Compass Group — 27 — 2025-07-14 — `warn`

  > Layoff at Compass Group in Joliet. 27 employees affected, effective 2025-07-14. Filed under the IL WARN Act.

- **nothing to look twice at on row `138181`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-07-14-compass \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138181>
python3 railway/warn_adjudicate.py --reject warn-il-2025-07-14-compass \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138181>
```

---

## 2. Carolina Therapeutic Services (IL)

`warn-il-2025-09-26-carolina-therapeutic-services` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-26**, effective 2025-09-26..2025-09-26
- **27** affected across 1 published row(s)
  - Carolina Therapeutic Services — 27 — Chicago, IL 60639                 Chicago, IL 60653                    Chicago, IL 60647 — effective 2025-09-26 — `2025-09 monthly report, data row 3`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-08-27 .. 2026-10-31

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137546` — event `110381` — tier `exact`

| | the state's notice | our row `137546` |
|---|---|---|
| employer | Carolina Therapeutic Services | Carolina Therapeutic Services |
| count | 27 | 27 |
| notice date | 2025-09-26 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-09-26..2025-09-26 | 2025-09-26 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 27, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-09-26 is a date the state published as effective for this notice; the notice date 2025-09-26 is 0 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Carolina Therapeutic Services — 27 — 2025-09-26 — `warn`

  > Layoff at Carolina Therapeutic Services in Chicago. 27 employees affected, effective 2025-09-26. Filed under the IL WARN Act.

- **nothing to look twice at on row `137546`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-09-26-carolina-therapeutic-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137546>
python3 railway/warn_adjudicate.py --reject warn-il-2025-09-26-carolina-therapeutic-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137546>
```

---

## 3. Chartwells at DePaul University (IL)

`warn-il-2025-10-01-chartwells-at-depaul-university` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-01**, effective 2025-11-30..2025-11-30
- **138** affected across 1 published row(s)
  - Chartwells at DePaul University — 138 — Chicago, IL 60614 — effective 2025-11-30 — `2025-10 monthly report, data row 3`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-09-01 .. 2026-11-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137443` — event `110278` — tier `exact`

| | the state's notice | our row `137443` |
|---|---|---|
| employer | Chartwells at DePaul University | Chartwells at DePaul University |
| count | 138 | 138 |
| notice date | 2025-10-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-11-30..2025-11-30 | 2025-10-01 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 138, the whole notice
- **dates**: agree on the NOTICE basis — our 2025-10-01 is the notice date; the state published effective 2025-11-30
- **employer name**: matches the state's published string
- **live now**: Chartwells at DePaul University — 138 — 2025-10-01 — `warn`

  > Layoff at Chartwells at DePaul University in Chicago. 138 employees affected, effective 2025-10-01. Filed under the IL WARN Act.

- **nothing to look twice at on row `137443`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-10-01-chartwells-at-depaul-university \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137443>
python3 railway/warn_adjudicate.py --reject warn-il-2025-10-01-chartwells-at-depaul-university \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137443>
```

---

## 4. PharmaCann, Inc. (IL)

`warn-il-2025-11-14-pharmacann` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-14**, effective 2026-01-13..2026-01-13
- **82** affected across 1 published row(s)
  - PharmaCann, Inc. — 82 — Dwight, IL 60420 — effective 2026-01-13 — `2025-11 monthly report, data row 6`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Nov%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-10-15 .. 2026-12-19

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137008` — event `109843` — tier `exact`

| | the state's notice | our row `137008` |
|---|---|---|
| employer | PharmaCann, Inc. | PharmaCann, Inc. |
| count | 82 | 82 |
| notice date | 2025-11-14 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-13..2026-01-13 | 2025-11-14 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Nov%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 82, the whole notice
- **dates**: agree on the NOTICE basis — our 2025-11-14 is the notice date; the state published effective 2026-01-13
- **employer name**: matches the state's published string
- **live now**: PharmaCann, Inc. — 82 — 2025-11-14 — `warn`

  > Layoff at PharmaCann, Inc. in Dwight. 82 employees affected, effective 2025-11-14. Filed under the IL WARN Act.

- **nothing to look twice at on row `137008`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-11-14-pharmacann \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137008>
python3 railway/warn_adjudicate.py --reject warn-il-2025-11-14-pharmacann \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137008>
```

---

## 5. Alton Steel, Inc. (IL)

`warn-il-2026-01-27-alton-steel` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-27**, effective 2026-01-31..2026-01-31
- **253** affected across 1 published row(s)
  - Alton Steel, Inc. — 253 — Alton, IL 62002 — effective 2026-01-31 — `2026-01 monthly report, data row 1`
- source: <https://www.illinoisworknet.com/_layouts/15/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Jan2026MonthlyWARNReport.xlsx>
- the rule's match window: 2025-12-28 .. 2027-03-03

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136291` — event `109126` — tier `exact`

| | the state's notice | our row `136291` |
|---|---|---|
| employer | Alton Steel, Inc. | Alton Steel, Inc. |
| count | 253 | 253 |
| notice date | 2026-01-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-31..2026-01-31 | 2026-01-27 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/15/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Jan2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 253, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-01-27 is the notice date; the state published effective 2026-01-31
- **employer name**: matches the state's published string
- **live now**: Alton Steel, Inc. — 253 — 2026-01-27 — `warn`

  > Layoff at Alton Steel, Inc. in Alton. 253 employees affected, effective 2026-01-27. Filed under the IL WARN Act.

- **nothing to look twice at on row `136291`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-01-27-alton-steel \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136291>
python3 railway/warn_adjudicate.py --reject warn-il-2026-01-27-alton-steel \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136291>
```

---

## 6. Alverno Laboratories (at Franciscan Health Olympia Fields) (IL)

`warn-il-2026-02-02-alverno-laboratories` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-02**, effective 2026-04-01..2026-04-01
- **66** affected across 1 published row(s)
  - Alverno Laboratories (at Franciscan Health Olympia Fields) — 66 — Olympia Fields, IL 60461 — effective 2026-04-01 — `2026-02 monthly report, data row 1`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-01-03 .. 2027-03-09

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136195` — event `109030` — tier `exact`

| | the state's notice | our row `136195` |
|---|---|---|
| employer | Alverno Laboratories (at Franciscan Health Olympia Fields) | Alverno Laboratories (at Franciscan Health Olympia Fields) |
| count | 66 | 66 |
| notice date | 2026-02-02 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-01..2026-04-01 | 2026-02-02 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 66, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-02-02 is the notice date; the state published effective 2026-04-01
- **employer name**: matches the state's published string
- **live now**: Alverno Laboratories (at Franciscan Health Olympia Fields) — 66 — 2026-02-02 — `warn`

  > Layoff at Alverno Laboratories (at Franciscan Health Olympia Fields) in Olympia Fields. 66 employees affected, effective 2026-02-02. Filed under the IL WARN Act.

- **nothing to look twice at on row `136195`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-02-02-alverno-laboratories \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136195>
python3 railway/warn_adjudicate.py --reject warn-il-2026-02-02-alverno-laboratories \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136195>
```

---

## 7. Aspira Inc. of Illinois (IL)

`warn-il-2026-03-06-aspira-of-illinois` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-06**, effective 2026-04-03..2026-04-03
- **57** affected across 1 published row(s)
  - Aspira Inc. of Illinois — 57 — Chicago, IL 60618 — effective 2026-04-03 — `2026-03 monthly report, data row 1`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-02-04 .. 2027-04-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135973` — event `108808` — tier `exact`

| | the state's notice | our row `135973` |
|---|---|---|
| employer | Aspira Inc. of Illinois | Aspira Inc. of Illinois |
| count | 57 | 57 |
| notice date | 2026-03-06 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-03..2026-04-03 | 2026-03-06 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 57, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-03-06 is the notice date; the state published effective 2026-04-03
- **employer name**: matches the state's published string
- **live now**: Aspira Inc. of Illinois — 57 — 2026-03-06 — `warn`

  > Layoff at Aspira Inc. of Illinois in Chicago. 57 employees affected, effective 2026-03-06. Filed under the IL WARN Act.

- **nothing to look twice at on row `135973`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-03-06-aspira-of-illinois \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135973>
python3 railway/warn_adjudicate.py --reject warn-il-2026-03-06-aspira-of-illinois \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135973>
```

---

## 8. Trinity Christian College (IL)

`warn-il-2026-03-20-trinity-christian-college` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-20**, effective 2026-05-04..2026-05-04
- **107** affected across 1 published row(s)
  - Trinity Christian College — 107 — Palos Heights, IL 60463 — effective 2026-05-04 — `2026-03 monthly report, data row 9`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-02-18 .. 2027-04-24

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135845` — event `108680` — tier `exact`

| | the state's notice | our row `135845` |
|---|---|---|
| employer | Trinity Christian College | Trinity Christian College |
| count | 107 | 107 |
| notice date | 2026-03-20 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-04..2026-05-04 | 2026-03-20 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 107, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-03-20 is the notice date; the state published effective 2026-05-04
- **employer name**: matches the state's published string
- **live now**: Trinity Christian College — 107 — 2026-03-20 — `warn`

  > Layoff at Trinity Christian College in Palos Heights. 107 employees affected, effective 2026-03-20. Filed under the IL WARN Act.

- **nothing to look twice at on row `135845`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-03-20-trinity-christian-college \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135845>
python3 railway/warn_adjudicate.py --reject warn-il-2026-03-20-trinity-christian-college \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135845>
```

---

## 9. KLEO Community Family Life Center (IL)

`warn-il-2026-04-29-kleo-community-family-life` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-29**, effective 2026-06-30..2026-06-30
- **65** affected across 1 published row(s)
  - KLEO Community Family Life Center — 65 — Chicago, IL 60613 — effective 2026-06-30 — `2026-04 monthly report, data row 8`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/April2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-03-30 .. 2027-06-03

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135340` — event `108175` — tier `exact`

| | the state's notice | our row `135340` |
|---|---|---|
| employer | KLEO Community Family Life Center | KLEO Community Family Life Center |
| count | 65 | 65 |
| notice date | 2026-04-29 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-06-30..2026-06-30 | 2026-04-29 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/April2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 65, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-04-29 is the notice date; the state published effective 2026-06-30
- **employer name**: matches the state's published string
- **live now**: KLEO Community Family Life Center — 65 — 2026-04-29 — `warn`

  > Layoff at KLEO Community Family Life Center in Chicago. 65 employees affected, effective 2026-04-29. Filed under the IL WARN Act.

- **nothing to look twice at on row `135340`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-04-29-kleo-community-family-life \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135340>
python3 railway/warn_adjudicate.py --reject warn-il-2026-04-29-kleo-community-family-life \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135340>
```

---

## 10. MDMartin LLC (IL)

`warn-il-2026-05-19-mdmartin` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-19**, effective 2026-07-18..2026-07-18
- **160** affected across 1 published row(s)
  - MDMartin LLC — 160 — Matteson, IL 60443 — effective 2026-07-18 — `2026-05 monthly report, data row 5`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-04-19 .. 2027-06-23

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135119` — event `107954` — tier `exact`

| | the state's notice | our row `135119` |
|---|---|---|
| employer | MDMartin LLC | MDMartin LLC |
| count | 160 | 160 |
| notice date | 2026-05-19 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-07-18..2026-07-18 | 2026-05-19 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 160, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-05-19 is the notice date; the state published effective 2026-07-18
- **employer name**: matches the state's published string
- **live now**: MDMartin LLC — 160 — 2026-05-19 — `warn`

  > Layoff at MDMartin LLC in Matteson. 160 employees affected, effective 2026-05-19. Filed under the IL WARN Act.

- **nothing to look twice at on row `135119`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-05-19-mdmartin \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135119>
python3 railway/warn_adjudicate.py --reject warn-il-2026-05-19-mdmartin \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135119>
```

---

## 11. Quality Built, LLC (OH)

`warn-oh-2025-07-07-quality-built` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-07**, effective 2025-07-03..2025-07-03
- **1** affected across 1 published row(s)
  - Quality Built, LLC — 1 — Cincinnati/Hamilton — effective 2025-07-03 — `2025 CSV, data row 30`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-06-07 .. 2026-08-11

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138286` — event `111121` — tier `exact`

| | the state's notice | our row `138286` |
|---|---|---|
| employer | Quality Built, LLC | Quality Built, LLC |
| count | 1 | 1 |
| notice date | 2025-07-07 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-07-03..2025-07-03 | 2025-07-03 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/QualityBuiltLLC.pdf> |

- **count**: exact — 1, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-07-03 is a date the state published as effective for this notice; the notice date 2025-07-07 is 4 day(s) later
- **employer name**: matches the state's published string
- **live now**: Quality Built, LLC — 1 — 2025-07-03 — `warn`

  > Layoff at Quality Built, LLC in Cincinnati. 1 employees affected, effective 2025-07-03. Filed under the OH WARN Act.

- **nothing to look twice at on row `138286`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-07-07-quality-built \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138286>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-07-07-quality-built \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138286>
```

---

## 12. Sarepta Therapeutics, Inc. (OH)

`warn-oh-2025-07-16-sarepta-therapeutics` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-16**, effective 2025-07-18..2025-07-18
- **80** affected across 1 published row(s)
  - Sarepta Therapeutics, Inc. — 80 — Columbus/Franklin — effective 2025-07-18 — `2025 CSV, data row 26`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-06-16 .. 2026-08-20

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138133` — event `110968` — tier `exact`

| | the state's notice | our row `138133` |
|---|---|---|
| employer | Sarepta Therapeutics, Inc. | Sarepta Therapeutics, Inc. |
| count | 80 | 80 |
| notice date | 2025-07-16 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-07-18..2025-07-18 | 2025-07-18 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/SareptaTherapeuticsInc.pdf> |

- **count**: exact — 80, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-07-18 is a date the state published as effective for this notice; the notice date 2025-07-16 is 2 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Sarepta Therapeutics, Inc. — 80 — 2025-07-18 — `warn`

  > Layoff at Sarepta Therapeutics, Inc. in Columbus. 80 employees affected, effective 2025-07-18. Filed under the OH WARN Act.

- **nothing to look twice at on row `138133`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-07-16-sarepta-therapeutics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138133>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-07-16-sarepta-therapeutics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138133>
```

---

## 13. First Student (OH)

`warn-oh-2025-08-18-first-student` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-18**, effective 2025-08-20..2025-08-20
- **39** affected across 1 published row(s)
  - First Student — 39 — Cincinnati/Hamilton — effective 2025-08-20 — `2025 CSV, data row 23`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-07-19 .. 2026-09-22

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137882` — event `110717` — tier `exact`

| | the state's notice | our row `137882` |
|---|---|---|
| employer | First Student | First Student |
| count | 39 | 39 |
| notice date | 2025-08-18 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-08-20..2025-08-20 | 2025-08-20 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/FirstStudent2.pdf> |

- **count**: exact — 39, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-08-20 is a date the state published as effective for this notice; the notice date 2025-08-18 is 2 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: First Student — 39 — 2025-08-20 — `warn`

  > Layoff at First Student in Cincinnati. 39 employees affected, effective 2025-08-20. Filed under the OH WARN Act.

- **nothing to look twice at on row `137882`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-08-18-first-student \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137882>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-08-18-first-student \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137882>
```

---

## 14. FedEx Supply Chain, Inc (OH)

`warn-oh-2025-08-28-fedex-supply-chain` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-08-28**, effective 2025-10-31..2025-10-31
- **56** affected across 1 published row(s)
  - FedEx Supply Chain, Inc — 56 — Lima/Allen — effective 2025-10-31 — `2025 CSV, data row 20`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-07-29 .. 2026-10-02

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137188` — event `110023` — tier `exact`

| | the state's notice | our row `137188` |
|---|---|---|
| employer | FedEx Supply Chain, Inc | FedEx Supply Chain, Inc |
| count | 56 | 56 |
| notice date | 2025-08-28 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-10-31..2025-10-31 | 2025-10-31 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/FedExSupplyChainInc.pdf> |

- **count**: exact — 56, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-10-31 is a date the state published as effective for this notice; the notice date 2025-08-28 is 64 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: FedEx Supply Chain, Inc — 56 — 2025-10-31 — `warn`

  > Layoff at FedEx Supply Chain, Inc in Lima. 56 employees affected, effective 2025-10-31. Filed under the OH WARN Act.

- **nothing to look twice at on row `137188`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-08-28-fedex-supply-chain \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137188>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-08-28-fedex-supply-chain \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137188>
```

---

## 15. Augusta Sportswear, Inc. (OH)

`warn-oh-2025-10-08-augusta-sportswear` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-08**, effective 2026-01-30..2026-01-30
- **58** affected across 1 published row(s)
  - Augusta Sportswear, Inc. — 58 — Sidney/Shelby — effective 2026-01-30 — `2025 CSV, data row 13`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-09-08 .. 2026-11-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136264` — event `109099` — tier `exact`

| | the state's notice | our row `136264` |
|---|---|---|
| employer | Augusta Sportswear, Inc. | Augusta Sportswear, Inc. |
| count | 58 | 58 |
| notice date | 2025-10-08 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-30..2026-01-30 | 2026-01-30 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/AugustaSportswearInc.pdf> |

- **count**: exact — 58, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-01-30 is a date the state published as effective for this notice; the notice date 2025-10-08 is 114 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Augusta Sportswear, Inc. — 58 — 2026-01-30 — `warn`

  > Layoff at Augusta Sportswear, Inc. in Sidney. 58 employees affected, effective 2026-01-30. Filed under the OH WARN Act.

- **nothing to look twice at on row `136264`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-10-08-augusta-sportswear \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136264>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-10-08-augusta-sportswear \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136264>
```

---

## 16. Nordstrom Credit Operations (OH)

`warn-oh-2025-11-19-nordstrom-credit-operations` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-19**, effective 2026-02-01..2026-02-01
- **1** affected across 1 published row(s)
  - Nordstrom Credit Operations — 1 — Pickerington/Fairfield — effective 2026-02-01 — `2025 CSV, data row 7`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-10-20 .. 2026-12-24

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136221` — event `109056` — tier `exact`

| | the state's notice | our row `136221` |
|---|---|---|
| employer | Nordstrom Credit Operations | Nordstrom Credit Operations |
| count | 1 | 1 |
| notice date | 2025-11-19 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-01..2026-02-01 | 2026-02-01 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1763665597/jfs.ohio.gov/warn/WARN%202025/NordstromCreditOperations.pdf> |

- **count**: exact — 1, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-02-01 is a date the state published as effective for this notice; the notice date 2025-11-19 is 74 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Nordstrom Credit Operations — 1 — 2026-02-01 — `warn`

  > Layoff at Nordstrom Credit Operations in Pickerington. 1 employees affected, effective 2026-02-01. Filed under the OH WARN Act.

- **nothing to look twice at on row `136221`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-11-19-nordstrom-credit-operations \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136221>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-11-19-nordstrom-credit-operations \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136221>
```

---

## 17. PK Management (OH)

`warn-oh-2025-12-04-pk-management` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-04**, effective 2026-02-01..2026-02-01
- **67** affected across 1 published row(s)
  - PK Management — 67 — Richmond Heights/Cuyahoga — effective 2026-02-01 — `2025 CSV, data row 4`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-11-04 .. 2027-01-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136220` — event `109055` — tier `exact`

| | the state's notice | our row `136220` |
|---|---|---|
| employer | PK Management | PK Management |
| count | 67 | 67 |
| notice date | 2025-12-04 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-01..2026-02-01 | 2026-02-01 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1764957000/jfs.ohio.gov/warn/WARN%202025/PKManagement.pdf> |

- **count**: exact — 67, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-02-01 is a date the state published as effective for this notice; the notice date 2025-12-04 is 59 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: PK Management — 67 — 2026-02-01 — `warn`

  > Layoff at PK Management in Richmond Heights. 67 employees affected, effective 2026-02-01. Filed under the OH WARN Act.

- **nothing to look twice at on row `136220`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-12-04-pk-management \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136220>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-12-04-pk-management \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136220>
```

---

## 18. Double Tree Cleveland (OH)

`warn-oh-2026-01-06-double-tree-cleveland` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-06**, effective 2026-01-28..2026-01-28
- **66** affected across 1 published row(s)
  - Double Tree Cleveland — 66 — Cleveland/Cuyahoga — effective 2026-01-28 — `2026 CSV, data row 66`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2025-12-07 .. 2027-02-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136284` — event `109119` — tier `exact`

| | the state's notice | our row `136284` |
|---|---|---|
| employer | Double Tree Cleveland | Double Tree Cleveland |
| count | 66 | 66 |
| notice date | 2026-01-06 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-28..2026-01-28 | 2026-01-28 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1767803703/jfs.ohio.gov/warn/WARN%202026/DoubleTreeClevelandCrescentHotelsResorts.pdf> |

- **count**: exact — 66, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-01-28 is a date the state published as effective for this notice; the notice date 2026-01-06 is 22 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Double Tree Cleveland — 66 — 2026-01-28 — `warn`

  > Layoff at Double Tree Cleveland in Cleveland. 66 employees affected, effective 2026-01-28. Filed under the OH WARN Act.

- **nothing to look twice at on row `136284`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-01-06-double-tree-cleveland \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136284>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-01-06-double-tree-cleveland \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136284>
```

---

## 19. Turf Care Supply Corp. (OH)

`warn-oh-2026-01-12-turf-care-supply` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-12**, effective 2026-02-28..2026-02-28
- **46** affected across 1 published row(s)
  - Turf Care Supply Corp. — 46 — Martins Ferry/Belmont — effective 2026-02-28 — `2026 CSV, data row 60`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2025-12-13 .. 2027-02-16

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136036` — event `108871` — tier `exact`

| | the state's notice | our row `136036` |
|---|---|---|
| employer | Turf Care Supply Corp. | Turf Care Supply Corp. |
| count | 46 | 46 |
| notice date | 2026-01-12 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-28..2026-02-28 | 2026-02-28 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1768499755/jfs.ohio.gov/warn/WARN%202026/TurfCareSupplyCorp.pdf> |

- **count**: exact — 46, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-02-28 is a date the state published as effective for this notice; the notice date 2026-01-12 is 47 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Turf Care Supply Corp. — 46 — 2026-02-28 — `warn`

  > Layoff at Turf Care Supply Corp. in Martins Ferry. 46 employees affected, effective 2026-02-28. Filed under the OH WARN Act.

- **nothing to look twice at on row `136036`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-01-12-turf-care-supply \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136036>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-01-12-turf-care-supply \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136036>
```

---

## 20. Fresenius USA Manufacturing (OH)

`warn-oh-2026-01-29-fresenius-manufacturing` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-29**, effective 2026-04-10..2026-04-10
- **54** affected across 1 published row(s)
  - Fresenius USA Manufacturing — 54 — Oregon/Lucas — effective 2026-04-10 — `2026 CSV, data row 58`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2025-12-30 .. 2027-03-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135598` — event `108433` — tier `exact`

| | the state's notice | our row `135598` |
|---|---|---|
| employer | Fresenius USA Manufacturing | Fresenius USA Manufacturing |
| count | 54 | 54 |
| notice date | 2026-01-29 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-10..2026-04-10 | 2026-04-10 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1769797238/jfs.ohio.gov/warn/WARN%202026/FreseniusUSAManufacturing.pdf> |

- **count**: exact — 54, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-04-10 is a date the state published as effective for this notice; the notice date 2026-01-29 is 71 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Fresenius USA Manufacturing — 54 — 2026-04-10 — `warn`

  > Layoff at Fresenius USA Manufacturing in Oregon. 54 employees affected, effective 2026-04-10. Filed under the OH WARN Act.

- **nothing to look twice at on row `135598`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-01-29-fresenius-manufacturing \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135598>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-01-29-fresenius-manufacturing \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135598>
```

---

## 21. Astrion (OH)

`warn-oh-2026-02-09-astrion` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-09**, effective 2026-05-31..2026-05-31
- **61** affected across 1 published row(s)
  - Astrion — 61 — Beavercreek/Greene — effective 2026-05-31 — `2026 CSV, data row 55`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-01-10 .. 2027-03-16

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135005` — event `107840` — tier `exact`

| | the state's notice | our row `135005` |
|---|---|---|
| employer | Astrion | Astrion |
| count | 61 | 61 |
| notice date | 2026-02-09 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-31..2026-05-31 | 2026-05-31 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1770735265/jfs.ohio.gov/warn/WARN%202026/Astrion.pdf> |

- **count**: exact — 61, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-31 is a date the state published as effective for this notice; the notice date 2026-02-09 is 111 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Astrion — 61 — 2026-05-31 — `warn`

  > Layoff at Astrion in Beavercreek. 61 employees affected, effective 2026-05-31. Filed under the OH WARN Act.

- **nothing to look twice at on row `135005`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-02-09-astrion \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135005>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-02-09-astrion \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135005>
```

---

## 22. Lowe's Companies (OH)

`warn-oh-2026-02-16-lowe-s-companies` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-16**, effective 2026-04-19..2026-04-19
- **17** affected across 1 published row(s)
  - Lowe's Companies — 17 — Unknown/Unknown — effective 2026-04-19 — `2026 CSV, data row 52`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-01-17 .. 2027-03-23

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135485` — event `108320` — tier `exact`

| | the state's notice | our row `135485` |
|---|---|---|
| employer | Lowe's Companies | Lowe's Companies |
| count | 17 | 17 |
| notice date | 2026-02-16 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-19..2026-04-19 | 2026-04-19 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1771342002/jfs.ohio.gov/warn/WARN%202026/LowesCompanies.pdf> |

- **count**: exact — 17, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-04-19 is a date the state published as effective for this notice; the notice date 2026-02-16 is 62 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Lowe's Companies — 17 — 2026-04-19 — `warn`

  > Layoff at Lowe's Companies in Unknown. 17 employees affected, effective 2026-04-19. Filed under the OH WARN Act.

- **nothing to look twice at on row `135485`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-02-16-lowe-s-companies \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135485>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-02-16-lowe-s-companies \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135485>
```

---

## 23. Parsec, LLC (OH)

`warn-oh-2026-02-23-parsec` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-23**, effective 2026-05-01..2026-05-01
- **115** affected across 1 published row(s)
  - Parsec, LLC — 115 — Columbus/Franklin — effective 2026-05-01 — `2026 CSV, data row 50`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-01-24 .. 2027-03-30

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135293` — event `108128` — tier `exact`

| | the state's notice | our row `135293` |
|---|---|---|
| employer | Parsec, LLC | Parsec, LLC |
| count | 115 | 115 |
| notice date | 2026-02-23 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-01..2026-05-01 | 2026-05-01 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1771873177/jfs.ohio.gov/warn/WARN%202026/ParsecLLC.pdf> |

- **count**: exact — 115, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-01 is a date the state published as effective for this notice; the notice date 2026-02-23 is 67 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Parsec, LLC — 115 — 2026-05-01 — `warn`

  > Layoff at Parsec, LLC in Columbus. 115 employees affected, effective 2026-05-01. Filed under the OH WARN Act.

- **nothing to look twice at on row `135293`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-02-23-parsec \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135293>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-02-23-parsec \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135293>
```

---

## 24. Ten Sixty Logistics LLC (OH)

`warn-oh-2026-03-19-ten-sixty-logistics` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-19**, effective 2026-03-31..2026-03-31
- **125** affected across 1 published row(s)
  - Ten Sixty Logistics LLC — 125 — Etna/Licking — effective 2026-03-31 — `2026 CSV, data row 39`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-02-17 .. 2027-04-23

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135765` — event `108600` — tier `exact`

| | the state's notice | our row `135765` |
|---|---|---|
| employer | Ten Sixty Logistics LLC | Ten Sixty Logistics LLC |
| count | 125 | 125 |
| notice date | 2026-03-19 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-03-31..2026-03-31 | 2026-03-31 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1774022043/jfs.ohio.gov/warn/WARN%202026/Ten_Sixty_Logistics.pdf> |

- **count**: exact — 125, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-03-31 is a date the state published as effective for this notice; the notice date 2026-03-19 is 12 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Ten Sixty Logistics LLC — 125 — 2026-03-31 — `warn`

  > Layoff at Ten Sixty Logistics LLC in Etna. 125 employees affected, effective 2026-03-31. Filed under the OH WARN Act.

- **nothing to look twice at on row `135765`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-03-19-ten-sixty-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135765>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-03-19-ten-sixty-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135765>
```

---

## 25. Technicote Inc dba Beontag (OH)

`warn-oh-2026-03-25-technicote-dba-beontag` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-25**, effective 2026-05-24..2026-05-24
- **53** affected across 1 published row(s)
  - Technicote Inc dba Beontag — 53 — Trotwood/Montgomery — effective 2026-05-24 — `2026 CSV, data row 38`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-02-23 .. 2027-04-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135079` — event `107914` — tier `exact`

| | the state's notice | our row `135079` |
|---|---|---|
| employer | Technicote Inc dba Beontag | Technicote Inc dba Beontag |
| count | 53 | 53 |
| notice date | 2026-03-25 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-24..2026-05-24 | 2026-05-24 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1774539368/jfs.ohio.gov/warn/WARN%202026/TechnicoteIncdbaBeontag.pdf> |

- **count**: exact — 53, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-24 is a date the state published as effective for this notice; the notice date 2026-03-25 is 60 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Technicote Inc dba Beontag — 53 — 2026-05-24 — `warn`

  > Layoff at Technicote Inc dba Beontag in Trotwood. 53 employees affected, effective 2026-05-24. Filed under the OH WARN Act.

- **nothing to look twice at on row `135079`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-03-25-technicote-dba-beontag \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135079>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-03-25-technicote-dba-beontag \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135079>
```

---

## 26. Venture Solutions/Taylor Technology Services (OH)

`warn-oh-2026-04-22-venture-solutions-taylor-technology` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-22**, effective 2026-06-22..2026-06-22
- **60** affected across 1 published row(s)
  - Venture Solutions/Taylor Technology Services — 60 — Grove City/Franklin — effective 2026-06-22 — `2026 CSV, data row 32`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-03-23 .. 2027-05-27

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134735` — event `107570` — tier `exact`

| | the state's notice | our row `134735` |
|---|---|---|
| employer | Venture Solutions/Taylor Technology Services | Venture Solutions/Taylor Technology Services |
| count | 60 | 60 |
| notice date | 2026-04-22 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-06-22..2026-06-22 | 2026-06-22 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1776886905/jfs.ohio.gov/warn/WARN%202026/VentureSolutionsInc_TaylorTechnologyServices.pdf> |

- **count**: exact — 60, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-06-22 is a date the state published as effective for this notice; the notice date 2026-04-22 is 61 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Venture Solutions/Taylor Technology Services — 60 — 2026-06-22 — `warn`

  > Layoff at Venture Solutions/Taylor Technology Services in Grove City. 60 employees affected, effective 2026-06-22. Filed under the OH WARN Act.

- **nothing to look twice at on row `134735`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-04-22-venture-solutions-taylor-technology \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134735>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-04-22-venture-solutions-taylor-technology \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134735>
```

---

## 27. Pioneer Cladding & Glazing Systems, Inc. (OH)

`warn-oh-2026-06-10-pioneer-cladding-glazing-systems` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-06-10**, effective 2026-08-09..2026-08-09
- **43** affected across 1 published row(s)
  - Pioneer Cladding & Glazing Systems, Inc. — 43 — Mason/Warren — effective 2026-08-09 — `2026 CSV, data row 22`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-05-11 .. 2027-07-15

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134191` — event `107026` — tier `exact`

| | the state's notice | our row `134191` |
|---|---|---|
| employer | Pioneer Cladding & Glazing Systems, Inc. | Pioneer Cladding & Glazing Systems, Inc. |
| count | 43 | 43 |
| notice date | 2026-06-10 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-08-09..2026-08-09 | 2026-08-09 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1781208658/jfs.ohio.gov/warn/WARN%202026/PioneerCladding_GlazingSystemsInc.pdf> |

- **count**: exact — 43, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-08-09 is a date the state published as effective for this notice; the notice date 2026-06-10 is 60 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Pioneer Cladding & Glazing Systems, Inc. — 43 — 2026-08-09 — `warn`

  > Layoff at Pioneer Cladding & Glazing Systems, Inc. in Mason. 43 employees affected, effective 2026-08-09. Filed under the OH WARN Act.

- **nothing to look twice at on row `134191`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-06-10-pioneer-cladding-glazing-systems \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134191>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-06-10-pioneer-cladding-glazing-systems \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134191>
```

---

## 28. ACC Premiere (PA)

`warn-pa-2025-07-01-acc-premiere` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-01**, effective 2025-09-19..2025-09-19
- **67** affected across 1 published row(s)
  - ACC Premiere — 67 — Lycoming; 948 Plaza Drive, Suite 1 — effective 2025-09-19 — `2025 > July > accordion item 99`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07>
- the rule's match window: 2025-06-01 .. 2026-08-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137598` — event `23930` — tier `exact`

| | the state's notice | our row `137598` |
|---|---|---|
| employer | ACC Premiere | ACC Premiere |
| count | 67 | 67 |
| notice date | 2025-07-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-09-19..2025-09-19 | 2025-09-19 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 67, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-09-19 is a date the state published as effective for this notice; the notice date 2025-07-01 is 80 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: ACC Premiere — 67 — 2025-09-19 — `warn`

  > Layoff at ACC Premiere. 67 employees affected, effective 2025-09-19. Filed under the PA WARN Act.

- **nothing to look twice at on row `137598`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-07-01-acc-premiere \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137598>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-07-01-acc-premiere \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137598>
```

---

## 29. Century Therapeutics, LLC (PA)

`warn-pa-2025-07-01-century-therapeutics` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-01**, effective 2025-07-11..2025-07-11
- **72** affected across 1 published row(s)
  - Century Therapeutics, LLC — 72 — Philadelphia; 25 North 38 th  Street, Philadelphia, PA 19104 — effective 2025-07-11 — `2025 > July > accordion item 96`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07>
- the rule's match window: 2025-06-01 .. 2026-08-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `138208` — event `23957` — tier `exact`

| | the state's notice | our row `138208` |
|---|---|---|
| employer | Century Therapeutics, LLC | Century Therapeutics, LLC |
| count | 72 | 72 |
| notice date | 2025-07-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-07-11..2025-07-11 | 2025-07-11 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 72, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-07-11 is a date the state published as effective for this notice; the notice date 2025-07-01 is 10 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Century Therapeutics, LLC — 72 — 2025-07-11 — `warn`

  > Layoff at Century Therapeutics, LLC. 72 employees affected, effective 2025-07-11. Filed under the PA WARN Act.

- **nothing to look twice at on row `138208`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-07-01-century-therapeutics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138208>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-07-01-century-therapeutics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 138208>
```

---

## 30. Air Products and Chemicals, Inc. (PA)

`warn-pa-2025-09-01-air-products-and-chemicals` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-01**, effective 2025-11-17..2025-11-17
- **14** affected across 1 published row(s)
  - Air Products and Chemicals, Inc. — 14 — Lehigh; 7331 William Avenue, Suite 300, Allentown, PA  18106 — effective 2025-11-17 — `2025 > September > accordion item 87`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09>
- the rule's match window: 2025-08-02 .. 2026-10-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136970` — event `23894` — tier `exact`

| | the state's notice | our row `136970` |
|---|---|---|
| employer | Air Products and Chemicals, Inc. | Air Products and Chemicals, Inc. |
| count | 14 | 14 |
| notice date | 2025-09-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-11-17..2025-11-17 | 2025-11-17 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 14, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-11-17 is a date the state published as effective for this notice; the notice date 2025-09-01 is 77 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Air Products and Chemicals, Inc. — 14 — 2025-11-17 — `warn`

  > Layoff at Air Products and Chemicals, Inc.. 14 employees affected, effective 2025-11-17. Filed under the PA WARN Act.

- **nothing to look twice at on row `136970`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-09-01-air-products-and-chemicals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136970>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-09-01-air-products-and-chemicals \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136970>
```

---

## 31. HMS Host (located within the Philadelphia International Airport) (PA)

`warn-pa-2025-09-01-hms-host` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-01**, effective 2025-10-27..2025-10-27
- **13** affected across 1 published row(s)
  - HMS Host (located within the Philadelphia International Airport) — 13 — Philadelphia; Starbucks, 8500 Essington Avenue, Philadelphia, PA  19153 — effective 2025-10-27 — `2025 > September > accordion item 90`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09>
- the rule's match window: 2025-08-02 .. 2026-10-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137230` — event `23906` — tier `exact`

| | the state's notice | our row `137230` |
|---|---|---|
| employer | HMS Host (located within the Philadelphia International Airport) | HMS Host (located within the Philadelphia International Airport) |
| count | 13 | 13 |
| notice date | 2025-09-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-10-27..2025-10-27 | 2025-10-27 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 13, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-10-27 is a date the state published as effective for this notice; the notice date 2025-09-01 is 56 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: HMS Host (located within the Philadelphia International Airport) — 13 — 2025-10-27 — `warn`

  > Layoff at HMS Host (located within the Philadelphia International Airport). 13 employees affected, effective 2025-10-27. Filed under the PA WARN Act.

- **nothing to look twice at on row `137230`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-09-01-hms-host \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137230>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-09-01-hms-host \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137230>
```

---

## 32. Trujacodi Delivery Express (PA)

`warn-pa-2025-09-01-trujacodi-delivery-express` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-01**, effective 2025-09-12..2025-09-12
- **42** affected across 1 published row(s)
  - Trujacodi Delivery Express — 42 — Philadelphia; 2900 Grant Avenue, Philadelphia, PA  19114 — effective 2025-09-12 — `2025 > September > accordion item 89`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09>
- the rule's match window: 2025-08-02 .. 2026-10-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137652` — event `23933` — tier `exact`

| | the state's notice | our row `137652` |
|---|---|---|
| employer | Trujacodi Delivery Express | Trujacodi Delivery Express |
| count | 42 | 42 |
| notice date | 2025-09-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-09-12..2025-09-12 | 2025-09-12 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-09> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 42, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-09-12 is a date the state published as effective for this notice; the notice date 2025-09-01 is 11 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Trujacodi Delivery Express — 42 — 2025-09-12 — `warn`

  > Closure at Trujacodi Delivery Express. 42 employees affected, effective 2025-09-12. Filed under the PA WARN Act.

- **nothing to look twice at on row `137652`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-09-01-trujacodi-delivery-express \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137652>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-09-01-trujacodi-delivery-express \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137652>
```

---

## 33. Peraton, Inc. (PA)

`warn-pa-2025-10-01-peraton` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-01**, effective 2025-12-13..2025-12-13
- **153** affected across 1 published row(s)
  - Peraton, Inc. — 153 — Cumberland; 1250 Camp Hill Bypass, Camp Hill, PA  17011 — effective 2025-12-13 — `2025 > October > accordion item 77`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-10>
- the rule's match window: 2025-09-01 .. 2026-11-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136768` — event `23885` — tier `exact`

| | the state's notice | our row `136768` |
|---|---|---|
| employer | Peraton, Inc. | Peraton, Inc. |
| count | 153 | 153 |
| notice date | 2025-10-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-12-13..2025-12-13 | 2025-12-13 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-10> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 153, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-12-13 is a date the state published as effective for this notice; the notice date 2025-10-01 is 73 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Peraton, Inc. — 153 — 2025-12-13 — `warn`

  > Layoff at Peraton, Inc.. 153 employees affected, effective 2025-12-13. Filed under the PA WARN Act.

- **nothing to look twice at on row `136768`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-10-01-peraton \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136768>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-10-01-peraton \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136768>
```

---

## 34. Vifor Pharma, Inc. (PA)

`warn-pa-2025-10-01-vifor-pharma` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-01**, effective 2025-12-01..2025-12-01
- **55** affected across 1 published row(s)
  - Vifor Pharma, Inc. — 55 — Montgomery; 1000 First Avenue, Suite 300, King of Prussia, PA  19406 — effective 2025-12-01 — `2025 > October > accordion item 82`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-10>
- the rule's match window: 2025-09-01 .. 2026-11-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136851` — event `23891` — tier `exact`

| | the state's notice | our row `136851` |
|---|---|---|
| employer | Vifor Pharma, Inc. | Vifor Pharma, Inc. |
| count | 55 | 55 |
| notice date | 2025-10-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-12-01..2025-12-01 | 2025-12-01 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-10> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 55, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2025-12-01 is a date the state published as effective for this notice; the notice date 2025-10-01 is 61 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Vifor Pharma, Inc. — 55 — 2025-12-01 — `warn`

  > Layoff at Vifor Pharma, Inc.. 55 employees affected, effective 2025-12-01. Filed under the PA WARN Act.

- **nothing to look twice at on row `136851`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-10-01-vifor-pharma \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136851>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-10-01-vifor-pharma \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136851>
```

---

## 35. Amazon Fresh (PA)

`warn-pa-2026-01-01-amazon-fresh` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-01**, effective 2026-04-28..2026-04-28
- **983** affected across 1 published row(s)
  - Amazon Fresh — 983 — Bucks, Delaware, Montgomery and Philadelphia; 555 Spring Garden St Philadelphia, PA 19123 (approx. 205 employees affected) — effective 2026-04-28 — `2026 > January > accordion item 49`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-01>
- the rule's match window: 2025-12-02 .. 2027-02-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135412` — event `23810` — tier `exact`

| | the state's notice | our row `135412` |
|---|---|---|
| employer | Amazon Fresh | Amazon Fresh |
| count | 983 | 983 |
| notice date | 2026-01-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-28..2026-04-28 | 2026-04-28 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-01> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 983, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-04-28 is a date the state published as effective for this notice; the notice date 2026-01-01 is 117 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Amazon Fresh — 983 — 2026-04-28 — `warn`

  > Layoff at Amazon Fresh. 983 employees affected, effective 2026-04-28. Filed under the PA WARN Act.

- **nothing to look twice at on row `135412`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-01-01-amazon-fresh \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135412>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-01-01-amazon-fresh \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135412>
```

---

## 36. Post Consumer Brands, LLC (PA)

`warn-pa-2026-02-01-post-consumer-brands` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-01**, effective 2026-05-01..2026-05-01
- **11** affected across 1 published row(s)
  - Post Consumer Brands, LLC — 11 — Columbia; 6650 Low Street, Bloomsburg, PA  17815 — effective 2026-05-01 — `2026 > February > accordion item 42`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-02>
- the rule's match window: 2026-01-02 .. 2027-03-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135281` — event `23807` — tier `exact`

| | the state's notice | our row `135281` |
|---|---|---|
| employer | Post Consumer Brands, LLC | Post Consumer Brands, LLC |
| count | 11 | 11 |
| notice date | 2026-02-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-01..2026-05-01 | 2026-05-01 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-02> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 11, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-01 is a date the state published as effective for this notice; the notice date 2026-02-01 is 89 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Post Consumer Brands, LLC — 11 — 2026-05-01 — `warn`

  > Layoff at Post Consumer Brands, LLC. 11 employees affected, effective 2026-05-01. Filed under the PA WARN Act.

- **nothing to look twice at on row `135281`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-02-01-post-consumer-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135281>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-02-01-post-consumer-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135281>
```

---

## 37. Federal Express Corporation (PA)

`warn-pa-2026-03-01-federal-express` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-01**, effective 2026-05-02..2026-05-02
- **63** affected across 1 published row(s)
  - Federal Express Corporation — 63 — Luzerne; 1000 Sathers Drive, Pittston, PA  18640 — effective 2026-05-02 — `2026 > March > accordion item 37`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03>
- the rule's match window: 2026-01-30 .. 2027-04-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135251` — event `23806` — tier `exact`

| | the state's notice | our row `135251` |
|---|---|---|
| employer | Federal Express Corporation | Federal Express Corporation |
| count | 63 | 63 |
| notice date | 2026-03-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-02..2026-05-02 | 2026-05-02 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 63, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-02 is a date the state published as effective for this notice; the notice date 2026-03-01 is 62 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Federal Express Corporation — 63 — 2026-05-02 — `warn`

  > Closing at Federal Express Corporation. 63 employees affected, effective 2026-05-02. Filed under the PA WARN Act.

- **nothing to look twice at on row `135251`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-03-01-federal-express \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135251>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-03-01-federal-express \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135251>
```

---

## 38. PharmaCann, Inc. (PA)

`warn-pa-2026-03-01-pharmacann` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-01**, effective 2026-05-20..2026-05-20
- **60** affected across 1 published row(s)
  - PharmaCann, Inc. — 60 — Lackawanna; 111 Life Science Drive, Olyphant, PA 18447 — effective 2026-05-20 — `2026 > March > accordion item 40`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03>
- the rule's match window: 2026-01-30 .. 2027-04-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135113` — event `23796` — tier `exact`

| | the state's notice | our row `135113` |
|---|---|---|
| employer | PharmaCann, Inc. | PharmaCann, Inc. |
| count | 60 | 60 |
| notice date | 2026-03-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-20..2026-05-20 | 2026-05-20 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 60, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-20 is a date the state published as effective for this notice; the notice date 2026-03-01 is 80 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: PharmaCann, Inc. — 60 — 2026-05-20 — `warn`

  > Closing at PharmaCann, Inc.. 60 employees affected, effective 2026-05-20. Filed under the PA WARN Act.

- **nothing to look twice at on row `135113`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-03-01-pharmacann \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135113>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-03-01-pharmacann \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135113>
```

---

## 39. Advantest, Inc. (PA)

`warn-pa-2026-04-01-advantest` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-01**, effective 2026-06-30..2026-06-30
- **55** affected across 1 published row(s)
  - Advantest, Inc. — 55 — Lehigh; 1660 East Race Street, Allentown, PA 18109 — effective 2026-06-30 — `2026 > April > accordion item 31`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-04>
- the rule's match window: 2026-03-02 .. 2027-05-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134613` — event `23783` — tier `exact`

| | the state's notice | our row `134613` |
|---|---|---|
| employer | Advantest, Inc. | Advantest, Inc. |
| count | 55 | 55 |
| notice date | 2026-04-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-06-30..2026-06-30 | 2026-06-30 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-04> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 55, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-06-30 is a date the state published as effective for this notice; the notice date 2026-04-01 is 90 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Advantest, Inc. — 55 — 2026-06-30 — `warn`

  > Layoff at Advantest, Inc.. 55 employees affected, effective 2026-06-30. Filed under the PA WARN Act.

- **nothing to look twice at on row `134613`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-04-01-advantest \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134613>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-04-01-advantest \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134613>
```

---

## 40. LNS Chipblaster (PA)

`warn-pa-2026-04-01-lns-chipblaster` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-01**, effective 2026-09-30..2026-09-30
- **67** affected across 1 published row(s)
  - LNS Chipblaster — 67 — Crawford; 13605 South Mosiertown Road, Meadville, PA  16335 — effective 2026-09-30 — `2026 > April > accordion item 33`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-04>
- the rule's match window: 2026-03-02 .. 2027-05-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `133970` — event `23769` — tier `exact`

| | the state's notice | our row `133970` |
|---|---|---|
| employer | LNS Chipblaster | LNS Chipblaster |
| count | 67 | 67 |
| notice date | 2026-04-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-09-30..2026-09-30 | 2026-09-30 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-04> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 67, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-09-30 is a date the state published as effective for this notice; the notice date 2026-04-01 is 182 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: LNS Chipblaster — 67 — 2026-09-30 — `warn`

  > Closing at LNS Chipblaster. 67 employees affected, effective 2026-09-30. Filed under the PA WARN Act.

- **nothing to look twice at on row `133970`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-04-01-lns-chipblaster \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 133970>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-04-01-lns-chipblaster \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 133970>
```

---

## 41. Winston Brands, Inc. (IL)

`warn-il-2025-10-23-winston-brands` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-23**, effective 2025-12-15..2025-12-15
- **163** affected across 2 published row(s)
  - Winston Brands, Inc. — 73 — Elk Grove Village, IL 60007 — effective 2025-12-15 — `2025-10 monthly report, data row 12`
  - Winston Brands, Inc. — 90 — Melrose Park, IL 60163 — effective 2025-12-15 — `2025-10 monthly report, data row 13`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-09-23 .. 2026-11-27

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137259` — event `110094` — tier `exact`

| | the state's notice | our row `137259` |
|---|---|---|
| employer | Winston Brands, Inc. | Winston Brands, Inc. |
| count | 163 | 90 |
| notice date | 2025-10-23 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-12-15..2025-12-15 | 2025-10-23 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 90 is one of the 2 rows the state published under this notice (total 163)
- **dates**: agree on the NOTICE basis — our 2025-10-23 is the notice date; the state published effective 2025-12-15
- **employer name**: matches the state's published string
- **live now**: Winston Brands, Inc. — 90 — 2025-10-23 — `warn`

  > Layoff at Winston Brands, Inc. in Melrose Park. 90 employees affected, effective 2025-10-23. Filed under the IL WARN Act.

- **nothing to look twice at on row `137259`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `137258` — event `110093` — tier `exact`

| | the state's notice | our row `137258` |
|---|---|---|
| employer | Winston Brands, Inc. | Winston Brands, Inc. |
| count | 163 | 73 |
| notice date | 2025-10-23 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-12-15..2025-12-15 | 2025-10-23 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 73 is one of the 2 rows the state published under this notice (total 163)
- **dates**: agree on the NOTICE basis — our 2025-10-23 is the notice date; the state published effective 2025-12-15
- **employer name**: matches the state's published string
- **live now**: Winston Brands, Inc. — 73 — 2025-10-23 — `warn`

  > Layoff at Winston Brands, Inc. in Elk Grove Village. 73 employees affected, effective 2025-10-23. Filed under the IL WARN Act.

- **nothing to look twice at on row `137258`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-10-23-winston-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137259 137258>
python3 railway/warn_adjudicate.py --reject warn-il-2025-10-23-winston-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137259 137258>
```

---

## 42. Premier Healthcare Solutions DBA Contigo Health (OH)

`warn-oh-2025-10-27-premier-healthcare-solutions-dba` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-27**, effective 2026-01-16..2026-01-16
- **175** affected across 1 published row(s)
  - Premier Healthcare Solutions DBA Contigo Health — 175 — Summit/Hudson — effective 2026-01-16 — `2025 CSV, data row 10`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-09-27 .. 2026-12-01

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `176837` — event `149570` — tier `exact`

| | the state's notice | our row `176837` |
|---|---|---|
| employer | Premier Healthcare Solutions DBA Contigo Health | Premier Healthcare Solutions DBA Contigo Health |
| count | 175 | 175 |
| notice date | 2025-10-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-16..2026-01-16 | 2026-01-16 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/PremierHealthcareSolutionsDBAContigo.pdf> |

- **count**: exact — 175, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-01-16 is a date the state published as effective for this notice; the notice date 2025-10-27 is 81 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Premier Healthcare Solutions DBA Contigo Health — 175 — 2026-01-16 — `warn`

  > Layoff at Premier Healthcare Solutions DBA Contigo Health in Summit. 175 employees affected, effective 2026-01-16. Filed under the OH WARN Act.

- **nothing to look twice at on row `176837`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `136620` — event `109455` — tier `exact`

| | the state's notice | our row `136620` |
|---|---|---|
| employer | Premier Healthcare Solutions DBA Contigo Health | Premier Healthcare Solutions DBA Contigo Health |
| count | 175 | 175 |
| notice date | 2025-10-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-16..2026-01-16 | 2025-12-31 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/PremierHealthcareSolutionsDBAContigo.pdf> |

- **count**: exact — 175, the whole notice
- **dates**: our 2025-12-31 is neither the notice date (+65 days) nor a published effective date (-16 days from 2026-01-16)
- **employer name**: matches the state's published string
- **live now**: Premier Healthcare Solutions DBA Contigo Health — 175 — 2025-12-31 — `warn`

  > Layoff at Premier Healthcare Solutions DBA Contigo Health in Summit. 175 employees affected, effective 2025-12-31. Filed under the OH WARN Act.

- **LOOK TWICE at row `136620`:** our 2025-12-31 is neither the notice date (+65 days) nor a published effective date (-16 days from 2026-01-16)

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-10-27-premier-healthcare-solutions-dba \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 176837 136620>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-10-27-premier-healthcare-solutions-dba \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 176837 136620>
```

---

## 43. JeniusBank SMBC Manubank (OH)

`warn-oh-2026-01-08-jeniusbank-smbc-manubank` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-01-08**, effective 2026-03-10..2026-03-10
- **2** affected across 1 published row(s)
  - JeniusBank SMBC Manubank — 2 — Unknown/Unknown — effective 2026-03-10 — `2026 CSV, data row 63`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2025-12-09 .. 2027-02-12

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135932` — event `108767` — tier `exact`

| | the state's notice | our row `135932` |
|---|---|---|
| employer | JeniusBank SMBC Manubank | JeniusBank SMBC Manubank |
| count | 2 | 2 |
| notice date | 2026-01-08 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-03-10..2026-03-10 | 2026-03-10 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1767988814/jfs.ohio.gov/warn/WARN%202026/JeniusBankManubankSMBC.pdf> |

- **count**: exact — 2, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-03-10 is a date the state published as effective for this notice; the notice date 2026-01-08 is 61 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: JeniusBank SMBC Manubank — 2 — 2026-03-10 — `warn`

  > Layoff at JeniusBank SMBC Manubank in Unknown. 2 employees affected, effective 2026-03-10. Filed under the OH WARN Act.

- **nothing to look twice at on row `135932`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `134233` — event `107068` — tier `exact`

| | the state's notice | our row `134233` |
|---|---|---|
| employer | JeniusBank SMBC Manubank | JeniusBank SMBC Manubank |
| count | 2 | 2 |
| notice date | 2026-01-08 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-03-10..2026-03-10 | 2026-08-03 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1781208657/jfs.ohio.gov/warn/WARN%202026/JeniusBankSMBCManubank2.pdf> |

- **count**: exact — 2, the whole notice
- **dates**: our 2026-08-03 is neither the notice date (+207 days) nor a published effective date (+146 days from 2026-03-10)
- **employer name**: matches the state's published string
- **live now**: JeniusBank SMBC Manubank — 2 — 2026-08-03 — `warn`

  > Layoff at JeniusBank SMBC Manubank in Unknown. 2 employees affected, effective 2026-08-03. Filed under the OH WARN Act.

- **LOOK TWICE at row `134233`:** our 2026-08-03 is neither the notice date (+207 days) nor a published effective date (+146 days from 2026-03-10)

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-01-08-jeniusbank-smbc-manubank \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135932 134233>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-01-08-jeniusbank-smbc-manubank \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135932 134233>
```

---

## 44. Saks & Company LLC Beachwood (OH)

`warn-oh-2026-03-06-saks-beachwood` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-06**, effective 2026-05-06..2026-05-06
- **70** affected across 1 published row(s)
  - Saks & Company LLC Beachwood — 70 — Beachwood/Cuyahoga — effective 2026-05-06 — `2026 CSV, data row 43`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-02-04 .. 2027-04-10

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135219` — event `108054` — tier `exact`

| | the state's notice | our row `135219` |
|---|---|---|
| employer | Saks & Company LLC Beachwood | Saks & Company LLC Beachwood |
| count | 70 | 70 |
| notice date | 2026-03-06 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-06..2026-05-06 | 2026-05-06 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1773064650/jfs.ohio.gov/warn/WARN%202026/SaksCompanyLLCBeachwood.pdf> |

- **count**: exact — 70, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-06 is a date the state published as effective for this notice; the notice date 2026-03-06 is 61 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Saks & Company LLC Beachwood — 70 — 2026-05-06 — `warn`

  > Layoff at Saks & Company LLC Beachwood in Beachwood. 70 employees affected, effective 2026-05-06. Filed under the OH WARN Act.

- **nothing to look twice at on row `135219`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `135579` — event `108414` — tier `loose`

| | the state's notice | our row `135579` |
|---|---|---|
| employer | Saks & Company LLC Beachwood | Saks & Company LLC Columbus |
| count | 70 | 41 |
| notice date | 2026-03-06 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-06..2026-05-06 | 2026-04-11 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1770832754/jfs.ohio.gov/warn/WARN%202026/SaksCompanyLLC.pdf> |

- **count**: DIFFERS by -29 — we hold 41, the notice totals 70 across rows of 70
- **dates**: our 2026-04-11 is neither the notice date (+36 days) nor a published effective date (-25 days from 2026-05-06)
- **employer name**: we store the employer as 'Saks & Company LLC Columbus'; the state publishes it as 'Saks & Company LLC Beachwood'
- **live now**: Saks & Company LLC Columbus — 41 — 2026-04-11 — `warn`

  > Layoff at Saks & Company LLC Columbus in Columbus. 41 employees affected, effective 2026-04-11. Filed under the OH WARN Act.

- **LOOK TWICE at row `135579`:** DIFFERS by -29 — we hold 41, the notice totals 70 across rows of 70
- **LOOK TWICE at row `135579`:** our 2026-04-11 is neither the notice date (+36 days) nor a published effective date (-25 days from 2026-05-06)

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-03-06-saks-beachwood \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135219 135579>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-03-06-saks-beachwood \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135219 135579>
```

---

## 45. Advanced Specialty Hospitals of Toledo (OH)

`warn-oh-2026-04-09-advanced-specialty-hospitals-of` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-09**, effective 2026-06-08..2026-06-08
- **116** affected across 1 published row(s)
  - Advanced Specialty Hospitals of Toledo — 116 — Toledo/Lucas — effective 2026-06-08 — `2026 CSV, data row 33`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-03-10 .. 2027-05-14

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134903` — event `107738` — tier `exact`

| | the state's notice | our row `134903` |
|---|---|---|
| employer | Advanced Specialty Hospitals of Toledo | Advanced Specialty Hospitals of Toledo |
| count | 116 | 116 |
| notice date | 2026-04-09 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-06-08..2026-06-08 | 2026-06-08 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1775847051/jfs.ohio.gov/warn/WARN%202026/AdvancedSpecialtyHospitalsofToledo.pdf> |

- **count**: exact — 116, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-06-08 is a date the state published as effective for this notice; the notice date 2026-04-09 is 60 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Advanced Specialty Hospitals of Toledo — 116 — 2026-06-08 — `warn`

  > Layoff at Advanced Specialty Hospitals of Toledo in Toledo. 116 employees affected, effective 2026-06-08. Filed under the OH WARN Act.

- **nothing to look twice at on row `134903`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `175819` — event `148634` — tier `loose`

| | the state's notice | our row `175819` |
|---|---|---|
| employer | Advanced Specialty Hospitals of Toledo | Advanced Specialty Hospital of Toledo |
| count | 116 | 116 |
| notice date | 2026-04-09 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-06-08..2026-06-08 | 2026-04-14 |
| state | OH | OH |
| source | the state's own publication | `news` / `Spectrum News 1` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://spectrumnews1.com/oh/columbus/news/2026/04/14/advanced-specialty-hospital-of-toledo> |

- **count**: exact — 116, the whole notice
- **dates**: our 2026-04-14 is neither the notice date (+5 days) nor a published effective date (-55 days from 2026-06-08)
- **employer name**: we store the employer as 'Advanced Specialty Hospital of Toledo'; the state publishes it as 'Advanced Specialty Hospitals of Toledo'
- **live now**: Advanced Specialty Hospital of Toledo — 116 — 2026-04-14 — `news`

  > Per a WARN notice filed with the state, the LTACH facility will close May 1 and 116 employees will be let go, with all terminations permanent as of June 8.

- **LOOK TWICE at row `175819`:** our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event
- **LOOK TWICE at row `175819`:** our 2026-04-14 is neither the notice date (+5 days) nor a published effective date (-55 days from 2026-06-08)

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-04-09-advanced-specialty-hospitals-of \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134903 175819>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-04-09-advanced-specialty-hospitals-of \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134903 175819>
```

---

## 46. Pottstown Hospital (PA)

`warn-pa-2025-11-01-pottstown-hospital` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-01**, effective 2026-01-01..2026-01-01
- **131** affected across 1 published row(s)
  - Pottstown Hospital — 131 — Montgomery; 1600 East High Street, Pottstown, PA  19464 — effective 2026-01-01 — `2025 > November > accordion item 69`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11>
- the rule's match window: 2025-10-02 .. 2026-12-06

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136561` — event `23877` — tier `exact`

| | the state's notice | our row `136561` |
|---|---|---|
| employer | Pottstown Hospital | Pottstown Hospital |
| count | 131 | 131 |
| notice date | 2025-11-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-01..2026-01-01 | 2026-01-01 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 131, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-01-01 is a date the state published as effective for this notice; the notice date 2025-11-01 is 61 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Pottstown Hospital — 131 — 2026-01-01 — `warn`

  > Layoff at Pottstown Hospital. 131 employees affected, effective 2026-01-01. Filed under the PA WARN Act.

- **nothing to look twice at on row `136561`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `176699` — event `149432` — tier `loose`

| | the state's notice | our row `176699` |
|---|---|---|
| employer | Pottstown Hospital | Pottstown Hospital, LLC. |
| count | 131 | 160 |
| notice date | 2025-11-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-01..2026-01-01 | 2026-09-28 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: DIFFERS by +29 — we hold 160, the notice totals 131 across rows of 131
- **dates**: our 2026-09-28 is neither the notice date (+331 days) nor a published effective date (+270 days from 2026-01-01)
- **employer name**: we store the employer as 'Pottstown Hospital, LLC.'; the state publishes it as 'Pottstown Hospital'
- **live now**: Pottstown Hospital, LLC. — 160 — 2026-09-28 — `warn`

  > Layoff at Pottstown Hospital, LLC.. 160 employees affected, effective 2026-09-28. Filed under the PA WARN Act.

- **LOOK TWICE at row `176699`:** DIFFERS by +29 — we hold 160, the notice totals 131 across rows of 131
- **LOOK TWICE at row `176699`:** our 2026-09-28 is neither the notice date (+331 days) nor a published effective date (+270 days from 2026-01-01)

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-11-01-pottstown-hospital \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136561 176699>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-11-01-pottstown-hospital \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136561 176699>
```

---

## 47. GIANT Company, LLC (PA)

`warn-pa-2025-12-01-giant` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-01**, effective 2026-02-13..2026-02-27
- **204** affected across 2 published row(s)
  - GIANT Company, LLC — 76 — Lancaster; 235 North Reservoir Street, Lancaster, PA  17602 — effective 2026-02-27 — `2025 > December > accordion item 58`
  - GIANT Company, LLC — 128 — Philadelphia; 3501 Island Avenue, Philadelphia, PA  19153 — effective 2026-02-13 — `2025 > December > accordion item 59`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12>
- the rule's match window: 2025-11-01 .. 2027-01-05

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136136` — event `23847` — tier `exact`

| | the state's notice | our row `136136` |
|---|---|---|
| employer | GIANT Company, LLC | GIANT Company, LLC |
| count | 204 | 128 |
| notice date | 2025-12-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-13..2026-02-27 | 2026-02-13 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 128 is one of the 2 rows the state published under this notice (total 204)
- **dates**: agree on the EFFECTIVE basis — our 2026-02-13 is a date the state published as effective for this notice; the notice date 2025-12-01 is 74 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: GIANT Company, LLC — 128 — 2026-02-13 — `warn`

  > Closing at GIANT Company, LLC. 128 employees affected, effective 2026-02-13. Filed under the PA WARN Act.

- **nothing to look twice at on row `136136`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `136049` — event `23839` — tier `exact`

| | the state's notice | our row `136049` |
|---|---|---|
| employer | GIANT Company, LLC | GIANT Company, LLC |
| count | 204 | 76 |
| notice date | 2025-12-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-13..2026-02-27 | 2026-02-27 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 76 is one of the 2 rows the state published under this notice (total 204)
- **dates**: agree on the EFFECTIVE basis — our 2026-02-27 is a date the state published as effective for this notice; the notice date 2025-12-01 is 88 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: GIANT Company, LLC — 76 — 2026-02-27 — `warn`

  > Closing at GIANT Company, LLC. 76 employees affected, effective 2026-02-27. Filed under the PA WARN Act.

- **nothing to look twice at on row `136049`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

### row `135665` — event `23821` — tier `loose`

| | the state's notice | our row `135665` |
|---|---|---|
| employer | GIANT Company, LLC | The GIANT Company, LLC. |
| count | 204 | 105 |
| notice date | 2025-12-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-13..2026-02-27 | 2026-04-03 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-12> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: DIFFERS by -99 — we hold 105, the notice totals 204 across rows of 76, 128
- **dates**: our 2026-04-03 is neither the notice date (+123 days) nor a published effective date (+49 days from 2026-02-13)
- **employer name**: we store the employer as 'The GIANT Company, LLC.'; the state publishes it as 'GIANT Company, LLC'
- **live now**: The GIANT Company, LLC. — 105 — 2026-04-03 — `warn`

  > Closing at The GIANT Company, LLC.. 105 employees affected, effective 2026-04-03. Filed under the PA WARN Act.

- **LOOK TWICE at row `135665`:** DIFFERS by -99 — we hold 105, the notice totals 204 across rows of 76, 128
- **LOOK TWICE at row `135665`:** our 2026-04-03 is neither the notice date (+123 days) nor a published effective date (+49 days from 2026-02-13)

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-12-01-giant \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136136 136049 135665>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-12-01-giant \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136136 136049 135665>
```

---

## 48. Fervalue USA LLC (IL)

`warn-il-2025-10-08-fervalue` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-10-08**, effective 2026-01-01..2026-01-01
- **72** affected across 1 published row(s)
  - Fervalue USA LLC — 72 — Chicago, IL 60628 — effective 2026-01-01 — `2025-10 monthly report, data row 4`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-09-08 .. 2026-11-12

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137334` — event `110169` — tier `exact`

| | the state's notice | our row `137334` |
|---|---|---|
| employer | Fervalue USA LLC | Fervalue USA, LLC |
| count | 72 | 72 |
| notice date | 2025-10-08 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-01..2026-01-01 | 2025-10-08 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Oct%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 72, the whole notice
- **dates**: agree on the NOTICE basis — our 2025-10-08 is the notice date; the state published effective 2026-01-01
- **employer name**: we store the employer as 'Fervalue USA, LLC'; the state publishes it as 'Fervalue USA LLC'
- **live now**: Fervalue USA, LLC — 72 — 2025-10-08 — `warn`

  > Layoff at Fervalue USA, LLC in Chicago. 72 employees affected, effective 2025-10-08. Filed under the IL WARN Act.

- **LOOK TWICE at row `137334`:** we store the employer as 'Fervalue USA, LLC'; the state publishes it as 'Fervalue USA LLC'

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-10-08-fervalue \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137334>
python3 railway/warn_adjudicate.py --reject warn-il-2025-10-08-fervalue \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137334>
```

---

## 49. Consolidated Hospitality Supplies (IL)

`warn-il-2025-11-05-consolidated-hospitality-supplies` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-05**, effective 2026-01-04..2026-01-04
- **45** affected across 1 published row(s)
  - Consolidated Hospitality Supplies — 45 — Vernon Hills, IL 60061        Lake Bluff, IL 60044 — effective 2026-01-04 — `2025-11 monthly report, data row 1`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Nov%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-10-06 .. 2026-12-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137082` — event `109917` — tier `exact`

| | the state's notice | our row `137082` |
|---|---|---|
| employer | Consolidated Hospitality Supplies | Consolidated Hospitality Supplies, LLC |
| count | 45 | 45 |
| notice date | 2025-11-05 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-01-04..2026-01-04 | 2025-11-05 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Nov%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 45, the whole notice
- **dates**: agree on the NOTICE basis — our 2025-11-05 is the notice date; the state published effective 2026-01-04
- **employer name**: we store the employer as 'Consolidated Hospitality Supplies, LLC'; the state publishes it as 'Consolidated Hospitality Supplies'
- **live now**: Consolidated Hospitality Supplies, LLC — 45 — 2025-11-05 — `warn`

  > Layoff at Consolidated Hospitality Supplies, LLC in Vernon Hills. 45 employees affected, effective 2025-11-05. Filed under the IL WARN Act.

- **LOOK TWICE at row `137082`:** we store the employer as 'Consolidated Hospitality Supplies, LLC'; the state publishes it as 'Consolidated Hospitality Supplies'

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-11-05-consolidated-hospitality-supplies \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137082>
python3 railway/warn_adjudicate.py --reject warn-il-2025-11-05-consolidated-hospitality-supplies \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137082>
```

---

## 50. Heartland Human Care Services (IL)

`warn-il-2026-04-01-heartland-human-care-services` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-04-01**, effective 2026-03-31..2026-03-31
- **240** affected across 2 published row(s)
  - Heartland Human Care Services — 120 — Chicago, IL 60653 — effective 2026-03-31 — `2026-03 monthly report, data row 2`
  - Heartland Human Care Services (International Children's Reception Center) — 120 — Chicago, IL 60653 — effective 2026-03-31 — `2026-04 monthly report, data row 5`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-03-02 .. 2027-05-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135690` — event `108525` — tier `exact`

| | the state's notice | our row `135690` |
|---|---|---|
| employer | Heartland Human Care Services | Heartland Human Care Services (ICRC) |
| count | 240 | 120 |
| notice date | 2026-04-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-03-31..2026-03-31 | 2026-04-01 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/March2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 120 is one of the 2 rows the state published under this notice (total 240)
- **dates**: agree on the NOTICE basis — our 2026-04-01 is the notice date; the state published effective 2026-03-31
- **employer name**: we store the employer as 'Heartland Human Care Services (ICRC)'; the state publishes it as 'Heartland Human Care Services'
- **live now**: Heartland Human Care Services (ICRC) — 120 — 2026-04-01 — `warn`

  > Layoff at Heartland Human Care Services (ICRC) in Chicago. 120 employees affected, effective 2026-04-01. Filed under the IL WARN Act.

- **LOOK TWICE at row `135690`:** we store the employer as 'Heartland Human Care Services (ICRC)'; the state publishes it as 'Heartland Human Care Services'

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-04-01-heartland-human-care-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135690>
python3 railway/warn_adjudicate.py --reject warn-il-2026-04-01-heartland-human-care-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135690>
```

---

## 51. Optum Services, Inc. (IL)

`warn-il-2026-06-05-optum-services` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-06-05**, effective 2026-08-06..2026-08-06
- **98** affected across 1 published row(s)
  - Optum Services, Inc. — 98 — Moline, IL 61265 — effective 2026-08-06 — `2026-06 monthly report, data row 3`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=/DownloadPrint/June2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-05-06 .. 2027-07-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134921` — event `107756` — tier `exact`

| | the state's notice | our row `134921` |
|---|---|---|
| employer | Optum Services, Inc. | Optum Services, Inc |
| count | 98 | 98 |
| notice date | 2026-06-05 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-08-06..2026-08-06 | 2026-06-05 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=/DownloadPrint/June2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 98, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-06-05 is the notice date; the state published effective 2026-08-06
- **employer name**: we store the employer as 'Optum Services, Inc'; the state publishes it as 'Optum Services, Inc.'
- **live now**: Optum Services, Inc — 98 — 2026-06-05 — `warn`

  > Layoff at Optum Services, Inc in Moline. 98 employees affected, effective 2026-06-05. Filed under the IL WARN Act.

- **LOOK TWICE at row `134921`:** we store the employer as 'Optum Services, Inc'; the state publishes it as 'Optum Services, Inc.'

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-06-05-optum-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134921>
python3 railway/warn_adjudicate.py --reject warn-il-2026-06-05-optum-services \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134921>
```

---

## 52. Vistra Corp. - Baldwin Power Plant (IL)

`warn-il-2026-05-04-vistra` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2027-10-05..2028-02-01
- **304** affected across 3 published row(s)
  - Vistra Corp. - Baldwin Power Plant — 122 — Baldwin, IL 62217 — effective 2028-02-01 — `2026-05 monthly report, data row 9`
  - Vistra Corp. - Kincaid Power Plant — 99 — Kincaid, IL 62540 — effective 2028-01-04 — `2026-05 monthly report, data row 10`
  - Vistra Corp. - Newton Power Plant — 83 — Newton, IL 62448 — effective 2027-10-05 — `2026-05 monthly report, data row 11`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-04-04 .. 2027-06-08

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135231` — event `108066` — tier `exact`

| | the state's notice | our row `135231` |
|---|---|---|
| employer | Vistra Corp. - Baldwin Power Plant | Vistra Corp. |
| count | 304 | 99 |
| notice date | 2026-05-04 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2027-10-05..2028-02-01 | 2026-05-04 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 99 is one of the 3 rows the state published under this notice (total 304)
- **dates**: agree on the NOTICE basis — our 2026-05-04 is the notice date; the state published effective 2027-10-05/2028-01-04/2028-02-01
- **employer name**: we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'
- **live now**: Vistra Corp. — 99 — 2026-05-04 — `warn`

  > Layoff at Vistra Corp. in Kincaid. 99 employees affected, effective 2026-05-04. Filed under the IL WARN Act.

- **LOOK TWICE at row `135231`:** we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'

### row `135230` — event `108065` — tier `exact`

| | the state's notice | our row `135230` |
|---|---|---|
| employer | Vistra Corp. - Baldwin Power Plant | Vistra Corp. |
| count | 304 | 83 |
| notice date | 2026-05-04 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2027-10-05..2028-02-01 | 2026-05-04 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 83 is one of the 3 rows the state published under this notice (total 304)
- **dates**: agree on the NOTICE basis — our 2026-05-04 is the notice date; the state published effective 2027-10-05/2028-01-04/2028-02-01
- **employer name**: we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'
- **live now**: Vistra Corp. — 83 — 2026-05-04 — `warn`

  > Layoff at Vistra Corp. in Newton. 83 employees affected, effective 2026-05-04. Filed under the IL WARN Act.

- **LOOK TWICE at row `135230`:** we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'

### row `135229` — event `108064` — tier `exact`

| | the state's notice | our row `135229` |
|---|---|---|
| employer | Vistra Corp. - Baldwin Power Plant | Vistra Corp. |
| count | 304 | 122 |
| notice date | 2026-05-04 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2027-10-05..2028-02-01 | 2026-05-04 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 122 is one of the 3 rows the state published under this notice (total 304)
- **dates**: agree on the NOTICE basis — our 2026-05-04 is the notice date; the state published effective 2027-10-05/2028-01-04/2028-02-01
- **employer name**: we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'
- **live now**: Vistra Corp. — 122 — 2026-05-04 — `warn`

  > Layoff at Vistra Corp. in Baldwin. 122 employees affected, effective 2026-05-04. Filed under the IL WARN Act.

- **LOOK TWICE at row `135229`:** we store the employer as 'Vistra Corp.'; the state publishes it as 'Vistra Corp. - Baldwin Power Plant'

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-05-04-vistra \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135231 135230 135229>
python3 railway/warn_adjudicate.py --reject warn-il-2026-05-04-vistra \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135231 135230 135229>
```

---

## 53. Penske Logistics LLC (IL)

`warn-il-2025-09-05-penske-logistics` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-05**, effective 2025-11-04..2025-11-04
- **37** affected across 1 published row(s)
  - Penske Logistics LLC — 37 — Naperville, IL 60540 — effective 2025-11-04 — `2025-09 monthly report, data row 7`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-08-06 .. 2026-10-10

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137667` — event `110502` — tier `exact`

| | the state's notice | our row `137667` |
|---|---|---|
| employer | Penske Logistics LLC | Penske Logistics LLC |
| count | 37 | 37 |
| notice date | 2025-09-05 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-11-04..2025-11-04 | 2025-09-09 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 37, the whole notice
- **dates**: our 2025-09-09 is neither the notice date (+4 days) nor a published effective date (-56 days from 2025-11-04)
- **employer name**: matches the state's published string
- **live now**: Penske Logistics LLC — 37 — 2025-09-09 — `warn`

  > Layoff at Penske Logistics LLC in Naperville. 37 employees affected, effective 2025-09-09. Filed under the IL WARN Act.

- **LOOK TWICE at row `137667`:** our 2025-09-09 is neither the notice date (+4 days) nor a published effective date (-56 days from 2025-11-04)

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-09-05-penske-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137667>
python3 railway/warn_adjudicate.py --reject warn-il-2025-09-05-penske-logistics \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137667>
```

---

## 54. Rising Pharma Holdings (IL)

`warn-il-2025-09-15-rising-pharma` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-15**, effective 2025-11-15..2025-11-15
- **86** affected across 1 published row(s)
  - Rising Pharma Holdings — 86 — Decatur, IL 62522 — effective 2025-11-15 — `2025-09 monthly report, data row 9`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-08-16 .. 2026-10-20

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137637` — event `110472` — tier `loose`

| | the state's notice | our row `137637` |
|---|---|---|
| employer | Rising Pharma Holdings | Rising Pharma Holdings, Inc. |
| count | 86 | 99 |
| notice date | 2025-09-15 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-11-15..2025-11-15 | 2025-09-15 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Sep%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: DIFFERS by +13 — we hold 99, the notice totals 86 across rows of 86
- **dates**: agree on the NOTICE basis — our 2025-09-15 is the notice date; the state published effective 2025-11-15
- **employer name**: we store the employer as 'Rising Pharma Holdings, Inc.'; the state publishes it as 'Rising Pharma Holdings'
- **live now**: Rising Pharma Holdings, Inc. — 99 — 2025-09-15 — `warn`

  > Layoff at Rising Pharma Holdings, Inc. in Decatur. 99 employees affected, effective 2025-09-15. Filed under the IL WARN Act.

- **LOOK TWICE at row `137637`:** DIFFERS by +13 — we hold 99, the notice totals 86 across rows of 86

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-09-15-rising-pharma \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137637>
python3 railway/warn_adjudicate.py --reject warn-il-2025-09-15-rising-pharma \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137637>
```

---

## 55. Everest Insurance (IL)

`warn-il-2025-12-22-everest-insurance` — currently `not_matched`, stratum `primary`, size band `S`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-12-22**, effective 2026-03-31..2026-03-31
- **37** affected across 1 published row(s)
  - Everest Insurance — 37 — Chicago, IL 60606 — effective 2026-03-31 — `2025-12 monthly report, data row 5`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Dec%202025%20Monthly%20WARN%20Report.xlsx>
- the rule's match window: 2025-11-22 .. 2027-01-26

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136700` — event `109535` — tier `loose`

| | the state's notice | our row `136700` |
|---|---|---|
| employer | Everest Insurance | Everest Insurance |
| count | 37 | 38 |
| notice date | 2025-12-22 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-03-31..2026-03-31 | 2025-12-22 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Dec%202025%20Monthly%20WARN%20Report.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: DIFFERS by +1 — we hold 38, the notice totals 37 across rows of 37
- **dates**: agree on the NOTICE basis — our 2025-12-22 is the notice date; the state published effective 2026-03-31
- **employer name**: matches the state's published string
- **live now**: Everest Insurance — 38 — 2025-12-22 — `warn`

  > Layoff at Everest Insurance in Chicago. 38 employees affected, effective 2025-12-22. Filed under the IL WARN Act.

- **LOOK TWICE at row `136700`:** DIFFERS by +1 — we hold 38, the notice totals 37 across rows of 37

```
python3 railway/warn_adjudicate.py --accept warn-il-2025-12-22-everest-insurance \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136700>
python3 railway/warn_adjudicate.py --reject warn-il-2025-12-22-everest-insurance \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136700>
```

---

## 56. Walgreens (IL)

`warn-il-2026-02-10-walgreens` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-10**, effective 2026-02-10..2026-02-10
- **469** affected across 3 published row(s)
  - Walgreens — 416 — Deerfield, IL 60015 — effective 2026-02-10 — `2026-02 monthly report, data row 13`
  - Walgreens — 52 — Chicago, IL 60607 — effective 2026-02-10 — `2026-02 monthly report, data row 14`
  - Walgreens — 1 — Danville, IL 61834 — effective 2026-02-10 — `2026-02 monthly report, data row 15`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-01-11 .. 2027-03-17

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `175785` — event `148617` — tier `loose`

| | the state's notice | our row `175785` |
|---|---|---|
| employer | Walgreens | Walgreens |
| count | 469 | 628 |
| notice date | 2026-02-10 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-10..2026-02-10 | 2026-02-19 |
| state | IL | IL |
| source | the state's own publication | `news` / `Bloomberg` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx> | <https://www.bloomberg.com/news/articles/2026-02-19/walgreens-cuts-hundreds-of-workers-after-private-equity-buyout> |

- **count**: DIFFERS by +159 — we hold 628, the notice totals 469 across rows of 416, 52, 1
- **dates**: our 2026-02-19 is neither the notice date (+9 days) nor a published effective date (+9 days from 2026-02-10)
- **employer name**: matches the state's published string
- **live now**: Walgreens — 628 — 2026-02-19 — `news`

  > Walgreens cut 628 jobs across Illinois and Texas via WARN filings, including corporate roles in Deerfield, Chicago and Danville and 159 at a Houston distribution center, months after Sycamore Partners' buyout.

- **LOOK TWICE at row `175785`:** our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event
- **LOOK TWICE at row `175785`:** DIFFERS by +159 — we hold 628, the notice totals 469 across rows of 416, 52, 1
- **LOOK TWICE at row `175785`:** our 2026-02-19 is neither the notice date (+9 days) nor a published effective date (+9 days from 2026-02-10)

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-02-10-walgreens \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 175785>
python3 railway/warn_adjudicate.py --reject warn-il-2026-02-10-walgreens \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 175785>
```

---

## 57. First Brands Group, LLC (Albion Air Facility) (IL)

`warn-il-2026-02-23-first-brands` — currently `not_matched`, stratum `primary`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-23**, effective 2026-02-23..2026-02-23
- **642** affected across 4 published row(s)
  - First Brands Group, LLC (Albion Air Facility) — 114 — Albion, IL 62806 — effective 2026-02-23 — `2026-02 monthly report, data row 3`
  - First Brands Group, LLC (Albion Distribution Center) — 48 — Albion, IL 62806 — effective 2026-02-23 — `2026-02 monthly report, data row 4`
  - First Brands Group, LLC (Albion Oil Facility) — 435 — Albion, IL 62806 — effective 2026-02-23 — `2026-02 monthly report, data row 5`
  - First Brands Group, LLC (Albion Shared Services) — 45 — Albion, IL 62806        Fairfield, IL 62837 — effective 2026-02-23 — `2026-02 monthly report, data row 6`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-01-24 .. 2027-03-30

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136187` — event `109022` — tier `loose`

| | the state's notice | our row `136187` |
|---|---|---|
| employer | First Brands Group, LLC (Albion Air Facility) | First Brands Group, LLC (Midwest Distribution Center) |
| count | 642 | 389 |
| notice date | 2026-02-23 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-23..2026-02-23 | 2026-02-03 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/Feb2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: DIFFERS by -253 — we hold 389, the notice totals 642 across rows of 114, 48, 435, 45
- **dates**: our 2026-02-03 is neither the notice date (-20 days) nor a published effective date (-20 days from 2026-02-23)
- **employer name**: we store the employer as 'First Brands Group, LLC (Midwest Distribution Center)'; the state publishes it as 'First Brands Group, LLC (Albion Air Facility)'
- **live now**: First Brands Group, LLC (Midwest Distribution Center) — 389 — 2026-02-03 — `warn`

  > Layoff at First Brands Group, LLC (Midwest Distribution Center) in McHenry. 389 employees affected, effective 2026-02-03. Filed under the IL WARN Act.

- **LOOK TWICE at row `136187`:** DIFFERS by -253 — we hold 389, the notice totals 642 across rows of 114, 48, 435, 45
- **LOOK TWICE at row `136187`:** our 2026-02-03 is neither the notice date (-20 days) nor a published effective date (-20 days from 2026-02-23)

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-02-23-first-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136187>
python3 railway/warn_adjudicate.py --reject warn-il-2026-02-23-first-brands \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136187>
```

---

## 58. TOPS Products (OH)

`warn-oh-2025-09-24-tops-products` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-09-24**, effective 2027-04-02..2027-04-02
- **207** affected across 1 published row(s)
  - TOPS Products — 207 — Logan/Hocking — effective 2027-04-02 — `2025 CSV, data row 16`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv>
- the rule's match window: 2025-08-25 .. 2026-10-29

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136862` — event `109697` — tier `exact`

| | the state's notice | our row `136862` |
|---|---|---|
| employer | TOPS Products | TOPS Products |
| count | 207 | 207 |
| notice date | 2025-09-24 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2027-04-02..2027-04-02 | 2025-12-01 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2025_warn_notice.csv> | <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202025/TOPSProducts.pdf> |

- **count**: exact — 207, the whole notice
- **dates**: our 2025-12-01 is neither the notice date (+68 days) nor a published effective date (-487 days from 2027-04-02)
- **employer name**: matches the state's published string
- **live now**: TOPS Products — 207 — 2025-12-01 — `warn`

  > Layoff at TOPS Products in Logan. 207 employees affected, effective 2025-12-01. Filed under the OH WARN Act.

- **LOOK TWICE at row `136862`:** our 2025-12-01 is neither the notice date (+68 days) nor a published effective date (-487 days from 2027-04-02)

```
python3 railway/warn_adjudicate.py --accept warn-oh-2025-09-24-tops-products \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136862>
python3 railway/warn_adjudicate.py --reject warn-oh-2025-09-24-tops-products \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136862>
```

---

## 59. Weaber, Inc. (PA)

`warn-pa-2025-07-01-weaber` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-07-01**, effective 2025-08-26..2025-08-26
- **145** affected across 1 published row(s)
  - Weaber, Inc. — 145 — Lebanon; 25 Keystone Drive, Lebanon, PA  17042 — effective 2025-08-26 — `2025 > July > accordion item 95`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07>
- the rule's match window: 2025-06-01 .. 2026-08-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `137844` — event `23942` — tier `loose`

| | the state's notice | our row `137844` |
|---|---|---|
| employer | Weaber, Inc. | Weaber, Inc. |
| count | 145 | 46 |
| notice date | 2025-07-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2025-08-26..2025-08-26 | 2025-08-25 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-07> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: DIFFERS by -99 — we hold 46, the notice totals 145 across rows of 145
- **dates**: our 2025-08-25 is neither the notice date (+55 days) nor a published effective date (-1 days from 2025-08-26)
- **employer name**: matches the state's published string
- **live now**: Weaber, Inc. — 46 — 2025-08-25 — `warn`

  > Closing at Weaber, Inc.. 46 employees affected, effective 2025-08-25. Filed under the PA WARN Act.

- **LOOK TWICE at row `137844`:** DIFFERS by -99 — we hold 46, the notice totals 145 across rows of 145
- **LOOK TWICE at row `137844`:** our 2025-08-25 is neither the notice date (+55 days) nor a published effective date (-1 days from 2025-08-26)

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-07-01-weaber \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137844>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-07-01-weaber \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 137844>
```

---

## 60. First Brands Group Cuyahoga 4 (OH)

`warn-oh-2026-05-01-first-brands-cuyahoga-4` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-01**, effective 2026-02-27..2026-02-27
- **110** affected across 1 published row(s)
  - First Brands Group Cuyahoga 4 — 110 — Cleveland/Cuyahoga — effective 2026-02-27 — `2026 CSV, data row 25`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-04-01 .. 2027-06-05

**2 candidate row(s).** Each block below is one row and says nothing about any other.

### row `175799` — event `148624` — tier `loose`

| | the state's notice | our row `175799` |
|---|---|---|
| employer | First Brands Group Cuyahoga 4 | First Brands Group |
| count | 110 | 256 |
| notice date | 2026-05-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-27..2026-02-27 | 2026-04-30 |
| state | OH | OH |
| source | the state's own publication | `news` / `Spectrum News 1` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://spectrumnews1.com/oh/cleveland/news/2026/03/02/first-brands-group-laying-off-1-000-employees-ohio> |

- **count**: DIFFERS by +146 — we hold 256, the notice totals 110 across rows of 110
- **dates**: our 2026-04-30 is neither the notice date (-1 days) nor a published effective date (+62 days from 2026-02-27)
- **employer name**: we store the employer as 'First Brands Group'; the state publishes it as 'First Brands Group Cuyahoga 4'
- **live now**: First Brands Group — 256 — 2026-04-30 — `news`

  > First Brands Group will close its Cleveland corporate office at 127 Public Square on April 30, 2026, affecting 256 employees, with the company citing its Chapter 11 bankruptcy.

- **LOOK TWICE at row `175799`:** our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event
- **LOOK TWICE at row `175799`:** DIFFERS by +146 — we hold 256, the notice totals 110 across rows of 110
- **LOOK TWICE at row `175799`:** our 2026-04-30 is neither the notice date (-1 days) nor a published effective date (+62 days from 2026-02-27)
- **LOOK TWICE at row `175799`:** row `175799` is also proposed for 1 other reference event(s) — warn-oh-2026-02-27-first-brands-darke — and at most one of them can be it

### row `135331` — event `108166` — tier `loose`

| | the state's notice | our row `135331` |
|---|---|---|
| employer | First Brands Group Cuyahoga 4 | First Brands Group Darke |
| count | 110 | 302 |
| notice date | 2026-05-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-27..2026-02-27 | 2026-04-30 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1772219472/jfs.ohio.gov/warn/WARN%202026/FirstBrandsGroupDarke.pdf> |

- **count**: DIFFERS by +192 — we hold 302, the notice totals 110 across rows of 110
- **dates**: our 2026-04-30 is neither the notice date (-1 days) nor a published effective date (+62 days from 2026-02-27)
- **employer name**: we store the employer as 'First Brands Group Darke'; the state publishes it as 'First Brands Group Cuyahoga 4'
- **live now**: First Brands Group Darke — 302 — 2026-04-30 — `warn`

  > Layoff at First Brands Group Darke in Greenville. 302 employees affected, effective 2026-04-30. Filed under the OH WARN Act.

- **LOOK TWICE at row `135331`:** DIFFERS by +192 — we hold 302, the notice totals 110 across rows of 110
- **LOOK TWICE at row `135331`:** our 2026-04-30 is neither the notice date (-1 days) nor a published effective date (+62 days from 2026-02-27)
- **LOOK TWICE at row `135331`:** row `135331` is also proposed for 1 other reference event(s) — warn-oh-2026-02-27-first-brands-darke — and at most one of them can be it

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-05-01-first-brands-cuyahoga-4 \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 175799 135331>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-05-01-first-brands-cuyahoga-4 \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 175799 135331>
```

---

## 61. First Brands Group Darke (OH)

`warn-oh-2026-02-27-first-brands-darke` — currently `not_matched`, stratum `primary`, size band `M`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-02-27**, effective 2026-04-30..2026-04-30
- **302** affected across 1 published row(s)
  - First Brands Group Darke — 302 — Greenville/Darke — effective 2026-04-30 — `2026 CSV, data row 46`
- source: <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv>
- the rule's match window: 2026-01-28 .. 2027-04-03

**3 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135331` — event `108166` — tier `exact`

| | the state's notice | our row `135331` |
|---|---|---|
| employer | First Brands Group Darke | First Brands Group Darke |
| count | 302 | 302 |
| notice date | 2026-02-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-30..2026-04-30 | 2026-04-30 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1772219472/jfs.ohio.gov/warn/WARN%202026/FirstBrandsGroupDarke.pdf> |

- **count**: exact — 302, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-04-30 is a date the state published as effective for this notice; the notice date 2026-02-27 is 62 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: First Brands Group Darke — 302 — 2026-04-30 — `warn`

  > Layoff at First Brands Group Darke in Greenville. 302 employees affected, effective 2026-04-30. Filed under the OH WARN Act.

- **LOOK TWICE at row `135331`:** row `135331` is also proposed for 1 other reference event(s) — warn-oh-2026-05-01-first-brands-cuyahoga-4 — and at most one of them can be it

### row `136086` — event `108921` — tier `loose`

| | the state's notice | our row `136086` |
|---|---|---|
| employer | First Brands Group Darke | First Brands Group Cuyahoga |
| count | 302 | 146 |
| notice date | 2026-02-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-30..2026-04-30 | 2026-02-23 |
| state | OH | OH |
| source | the state's own publication | `warn` / `OH WARN notice` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://dam.assets.ohio.gov/image/upload/v1771966685/jfs.ohio.gov/warn/WARN%202026/FirstBrandsGroup.pdf> |

- **count**: DIFFERS by -156 — we hold 146, the notice totals 302 across rows of 302
- **dates**: our 2026-02-23 is neither the notice date (-4 days) nor a published effective date (-66 days from 2026-04-30)
- **employer name**: we store the employer as 'First Brands Group Cuyahoga'; the state publishes it as 'First Brands Group Darke'
- **live now**: First Brands Group Cuyahoga — 146 — 2026-02-23 — `warn`

  > Layoff at First Brands Group Cuyahoga in Cleveland. 146 employees affected, effective 2026-02-23. Filed under the OH WARN Act.

- **LOOK TWICE at row `136086`:** DIFFERS by -156 — we hold 146, the notice totals 302 across rows of 302
- **LOOK TWICE at row `136086`:** our 2026-02-23 is neither the notice date (-4 days) nor a published effective date (-66 days from 2026-04-30)

### row `175799` — event `148624` — tier `loose`

| | the state's notice | our row `175799` |
|---|---|---|
| employer | First Brands Group Darke | First Brands Group |
| count | 302 | 256 |
| notice date | 2026-02-27 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-04-30..2026-04-30 | 2026-04-30 |
| state | OH | OH |
| source | the state's own publication | `news` / `Spectrum News 1` |
| the URL we cite | <https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/2026/2026-warn-notice.csv> | <https://spectrumnews1.com/oh/cleveland/news/2026/03/02/first-brands-group-laying-off-1-000-employees-ohio> |

- **count**: DIFFERS by -46 — we hold 256, the notice totals 302 across rows of 302
- **dates**: agree on the EFFECTIVE basis — our 2026-04-30 is a date the state published as effective for this notice; the notice date 2026-02-27 is 62 day(s) earlier
- **employer name**: we store the employer as 'First Brands Group'; the state publishes it as 'First Brands Group Darke'
- **live now**: First Brands Group — 256 — 2026-04-30 — `news`

  > First Brands Group will close its Cleveland corporate office at 127 Public Square on April 30, 2026, affecting 256 employees, with the company citing its Chapter 11 bankruptcy.

- **LOOK TWICE at row `175799`:** our row is sourced to 'news', not to a WARN notice, so it is not the state's own record of this event
- **LOOK TWICE at row `175799`:** DIFFERS by -46 — we hold 256, the notice totals 302 across rows of 302
- **LOOK TWICE at row `175799`:** row `175799` is also proposed for 1 other reference event(s) — warn-oh-2026-05-01-first-brands-cuyahoga-4 — and at most one of them can be it

```
python3 railway/warn_adjudicate.py --accept warn-oh-2026-02-27-first-brands-darke \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135331 136086 175799>
python3 railway/warn_adjudicate.py --reject warn-oh-2026-02-27-first-brands-darke \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135331 136086 175799>
```

---

## 62. Crothall and Morrison Healthcare (PA)

`warn-pa-2025-11-01-crothall-and-morrison-healthcare` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2025-11-01**, effective 2026-02-01..2026-02-01
- **795** affected across 1 published row(s)
  - Crothall and Morrison Healthcare — 795 — Philadelphia; 3400 Spruce Street, Philadelphia, PA  19104 (Penn Medicine) — effective 2026-02-01 — `2025 > November > accordion item 65`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11>
- the rule's match window: 2025-10-02 .. 2026-12-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `136211` — event `23857` — tier `exact`

| | the state's notice | our row `136211` |
|---|---|---|
| employer | Crothall and Morrison Healthcare | Crothall and Morrison Healthcare |
| count | 795 | 795 |
| notice date | 2025-11-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-02-01..2026-02-01 | 2026-02-01 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2025-11> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 795, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-02-01 is a date the state published as effective for this notice; the notice date 2025-11-01 is 92 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Crothall and Morrison Healthcare — 795 — 2026-02-01 — `warn`

  > Layoff at Crothall and Morrison Healthcare. 795 employees affected, effective 2026-02-01. Filed under the PA WARN Act.

- **nothing to look twice at on row `136211`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2025-11-01-crothall-and-morrison-healthcare \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136211>
python3 railway/warn_adjudicate.py --reject warn-pa-2025-11-01-crothall-and-morrison-healthcare \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 136211>
```

---

## 63. Liberty Home Choices (PA)

`warn-pa-2026-03-01-liberty-home-choices` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-03-01**, effective 2026-05-24..2026-05-24
- **615** affected across 1 published row(s)
  - Liberty Home Choices — 615 — Philadelphia; 112 North 8 th  Street, Suite 600, Philadelphia, PA  19107 — effective 2026-05-24 — `2026 > March > accordion item 39`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03>
- the rule's match window: 2026-01-30 .. 2027-04-05

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135077` — event `23794` — tier `exact`

| | the state's notice | our row `135077` |
|---|---|---|
| employer | Liberty Home Choices | Liberty Home Choices |
| count | 615 | 615 |
| notice date | 2026-03-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-05-24..2026-05-24 | 2026-05-24 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-03> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 615, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-05-24 is a date the state published as effective for this notice; the notice date 2026-03-01 is 84 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: Liberty Home Choices — 615 — 2026-05-24 — `warn`

  > Closing at Liberty Home Choices. 615 employees affected, effective 2026-05-24. Filed under the PA WARN Act.

- **nothing to look twice at on row `135077`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-03-01-liberty-home-choices \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135077>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-03-01-liberty-home-choices \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135077>
```

---

## 64. JBS Souderton (PA)

`warn-pa-2026-06-01-jbs-souderton` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-06-01**, effective 2026-08-14..2026-08-14
- **1,485** affected across 1 published row(s)
  - JBS Souderton — 1485 — Montgomery; 249 Allentown Road, Souderton, PA  18964 — effective 2026-08-14 — `2026 > June > accordion item 17`
- source: <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-06>
- the rule's match window: 2026-05-02 .. 2027-07-06

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `134165` — event `23773` — tier `exact`

| | the state's notice | our row `134165` |
|---|---|---|
| employer | JBS Souderton | JBS Souderton |
| count | 1,485 | 1485 |
| notice date | 2026-06-01 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-08-14..2026-08-14 | 2026-08-14 |
| state | PA | PA |
| source | the state's own publication | `warn` / `PA WARN notice` |
| the URL we cite | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices#2026-06> | <https://www.pa.gov/agencies/dli/programs-services/workforce-development-home/warn-requirements/warn-notices> |

- **count**: exact — 1,485, the whole notice
- **dates**: agree on the EFFECTIVE basis — our 2026-08-14 is a date the state published as effective for this notice; the notice date 2026-06-01 is 74 day(s) earlier
- **employer name**: matches the state's published string
- **live now**: JBS Souderton — 1485 — 2026-08-14 — `warn`

  > Closure at JBS Souderton. 1,485 employees affected, effective 2026-08-14. Filed under the PA WARN Act.

- **nothing to look twice at on row `134165`** — count, date basis, employer name, state and source all line up. That is a fact about this row, not a verdict on it.

```
python3 railway/warn_adjudicate.py --accept warn-pa-2026-06-01-jbs-souderton \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134165>
python3 railway/warn_adjudicate.py --reject warn-pa-2026-06-01-jbs-souderton \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 134165>
```

---

## 65. Ideal US Talent Worker OpCo LLC (IL)

`warn-il-2026-05-04-ideal-talent-worker-opco` — currently `not_matched`, stratum `large_census`, size band `L`

**What the state published** (open the source and check it; do not take this file's word for it):

- notice date **2026-05-04**, effective 2026-07-01..2026-07-01
- **1,395** affected across 1 published row(s)
  - Ideal US Talent Worker OpCo LLC — 1395 — Minneapolis, MN 55425 — effective 2026-07-01 — `2026-05 monthly report, data row 4`
- source: <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx>
- the rule's match window: 2026-04-04 .. 2027-06-08

**1 candidate row(s).** Each block below is one row and says nothing about any other.

### row `135233` — event `108068` — tier `exact`

| | the state's notice | our row `135233` |
|---|---|---|
| employer | Ideal US Talent Worker OpCo LLC | Ideal US Talent Systems Worker Opco LLC |
| count | 1,395 | 1395 |
| notice date | 2026-05-04 | (we do not store a WARN notice date; our date is the effective one) |
| effective date | 2026-07-01..2026-07-01 | 2026-05-04 |
| state | IL | IL |
| source | the state's own publication | `warn` / `IL WARN notice` |
| the URL we cite | <https://www.illinoisworknet.com/_layouts/download.aspx?SourceUrl=https://www.illinoisworknet.com/DownloadPrint/May2026MonthlyWARNReport.xlsx> | <https://dceo.illinois.gov/workforcedevelopment/warn.html> |

- **count**: exact — 1,395, the whole notice
- **dates**: agree on the NOTICE basis — our 2026-05-04 is the notice date; the state published effective 2026-07-01
- **employer name**: we store the employer as 'Ideal US Talent Systems Worker Opco LLC'; the state publishes it as 'Ideal US Talent Worker OpCo LLC'
- **live now**: Ideal US Talent Systems Worker Opco LLC — 1395 — 2026-05-04 — `warn`

  > Layoff at Ideal US Talent Systems Worker Opco LLC in Bloomington. 1,395 employees affected, effective 2026-05-04. Filed under the IL WARN Act.

- **LOOK TWICE at row `135233`:** we store the employer as 'Ideal US Talent Systems Worker Opco LLC'; the state publishes it as 'Ideal US Talent Worker OpCo LLC'

```
python3 railway/warn_adjudicate.py --accept warn-il-2026-05-04-ideal-talent-worker-opco \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135233>
python3 railway/warn_adjudicate.py --reject warn-il-2026-05-04-ideal-talent-worker-opco \
    --reviewed-by 'NAME' --reason 'WHY' --row-ids <pick from: 135233>
```

---

