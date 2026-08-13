# SEC Item 2.05 gold set — adjudication sheet

Built `2026-08-13T06:06:41Z` from a measurement taken `2026-08-13T06:05:08Z`. **Rebuild it before deciding** (`python3 railway/recall_adjudication_pack.py --write`) — it reads live data and live data moves.

**3 events are pending.** Published today: 53 of 57.

Three arithmetics, so the range is known before the first decision. They are arithmetic, not targets, and the middle two are not predictions about how the entries below should go:

- every pending event accepted: **56/57 = 98.2%  (Wilson 95% CI [90.7%, 99.7%], width 9.0%)**
- the 1 with a hard discrepancy rejected, the rest accepted: **55/57 = 96.5%  (Wilson 95% CI [88.1%, 99.0%], width 11.0%)**
- only the 0 where every fact lines up accepted: **53/57 = 93.0%  (Wilson 95% CI [83.3%, 97.2%], width 13.9%)**

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
| 1 | [CODEXIS, INC.](#1-codexis-inc) | 2025-11-06 | 46 | 149951 | one note to read — we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available |
| 2 | [PLAYSTUDIOS, Inc.  (MYPS, MYPSW)](#2-playstudios-inc-myps-mypsw) | 2026-03-16 | 177 | 149954 | one note to read — we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available |
| 3 | [HP INC](#3-hp-inc) | 2025-11-25 | 4,000 | 4953 | **two things may be conflated** — SOURCE is 'news', not the 8-K; the URL we cite is not an EDGAR archive path |

---

## 1. CODEXIS, INC.

`sec-205-0001193125-25-269716` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | CODEXIS, INC. | CODEXIS, INC. (event 149951, row 177218) |
| job count | **46** | **46** |
| date | 2025-11-06 (EDGAR file date) | announced (none), effective 2025-11-06 |
| source | 8-K Item 2.05, accession 0001193125-25-269716 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1200375/000119312525269716/d80118d8k.htm> | <https://www.sec.gov/Archives/edgar/data/1200375/000119312525269716/d80118dex991.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The filing's primary document does not state 46 anywhere. Open the URL above; the count may live in an exhibit.

**Our row 177218 (event 149951) says:**

> In November 2025, Codexis eliminated 46 positions, or approximately 24% of its workforce. The company expects to recognize an additional expense of approximately $3.5 million in the fourth quarter of 2025.

- count matches the filing exactly
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'Codexis eliminated 46 positions'
- `match_notes`: Codexis rows exist but are 2023 events.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001193125-25-269716 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149951
python3 railway/recall_adjudicate.py --reject sec-205-0001193125-25-269716 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149951
```

---

## 2. PLAYSTUDIOS, Inc.  (MYPS, MYPSW)

`sec-205-0001823878-26-000018` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | PLAYSTUDIOS, Inc.  (MYPS, MYPSW) | PLAYSTUDIOS, Inc. (event 149954, row 177221) |
| job count | **177** | **177** |
| date | 2026-03-16 (EDGAR file date) | announced (none), effective 2026-03-16 |
| source | 8-K Item 2.05, accession 0001823878-26-000018 | 8K |
| URL | <https://www.sec.gov/Archives/edgar/data/1823878/000182387826000018/myps-20260310.htm> | <https://www.sec.gov/Archives/edgar/data/1823878/000182387826000018/myps-03162026xex991.htm> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> The filing's primary document does not state 177 anywhere. Open the URL above; the count may live in an exhibit.

**Our row 177221 (event 149954) says:**

> More recently, the Company initiated a second stage of its Reinvention plans consisting of a comprehensive refactoring of the business, which includes: • Closing 4 of its 9 studios, • Eliminating 177 positions, • Consolidating products and development teams, • Unifying select technologies and tools, • Reducing cost of sales, and • Cutting back on marketing spend.

- count matches the filing exactly
- effective date is +0 days from the filing date (the effective basis, which is a different question)
- we cite the gold set's own filing, accession for accession
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'Eliminating 177 positions'
- `match_notes`: No PLAYSTUDIOS row in the tracker at any date.

```
python3 railway/recall_adjudicate.py --accept sec-205-0001823878-26-000018 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149954
python3 railway/recall_adjudicate.py --reject sec-205-0001823878-26-000018 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 149954
```

---

## 3. HP INC

`sec-205-0000047217-25-000068` — currently `not_matched`

| | the gold event (SEC) | what we hold |
|---|---|---|
| company | HP INC | HP (event 4953, row 31078) |
| job count | **4,000** | **4,000** |
| date | 2025-11-25 (EDGAR file date) | announced (none), effective 2025-11-26 |
| source | 8-K Item 2.05, accession 0000047217-25-000068 | news |
| URL | <https://www.sec.gov/Archives/edgar/data/47217/000004721725000068/hpq-20251125.htm> | <https://timesofindia.indiatimes.com/technology/tech-news/hp-makes-it-official-to-cut-thousands-of-jobs-due-to-ai-says-two-years-ago-we-started-/articleshow/125581294.cms> |

**The filing's own words** (fetched from EDGAR when this sheet was built):

> Of the $650 million, HP expects to incur approximately $400 million in labor costs related to workforce reductions of approximately 4,000 - 6,000 employees by the end of fiscal 2028.


**Our row 31078 (event 4953) says:**

> Tech giant HP is set to eliminate between 4,000 to 6,000 jobs by 2028, a move driven by organizational restructuring and the integration of artificial intelligence.

- count matches the filing exactly
- effective date is +1 days from the filing date (the effective basis, which is a different question)
- **LOOK TWICE:** SOURCE is 'news', not the 8-K
- **LOOK TWICE:** the URL we cite is not an EDGAR archive path
- **LOOK TWICE:** we hold no announcement_date, so the FILING basis cannot be compared; only the effective date is available

The manifest's current words, for comparison with the filing above (the manifest is the thing being corrected, so it is quoted, not relied on):

- `count_evidence`: 'workforce reductions of approximately 4,000 - 6,000 employees'; lower bound per extractor.py's range rule.
- `match_notes`: CORRECTED 2026-08-12: the previous note, 'No HP Inc row after 2017', was false and was an artefact of these aliases, not a finding about the data. Each alias is used verbatim as the live API's company= SUBSTRING filter, and 'HP ' with a trailing space cannot match a company whose stored name IS 'HP': measured live, company='HP Inc' returns 3 rows and company='HP ' returns 18, neither containing the row, while company='HP' returns 60 and does. Alias 'HP' added; exclusion is excluded_name_prefixes' job and the prefix rule name_matches already accepted the bare 'HP' token for both existing aliases. 'hp composites' added there too, because 'hpc' never blocked 'HP Composites' (its tokens are ['hp', 'composites'], so the 'hpc' token prefix cannot match it) - it was held out only by rejected_candidate_event_ids, where it also remains. Verified live: the added alias yields exactly one fresh candidate, tracker event 4953.

```
python3 railway/recall_adjudicate.py --accept sec-205-0000047217-25-000068 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 4953
python3 railway/recall_adjudicate.py --reject sec-205-0000047217-25-000068 \
    --reviewed-by 'NAME' --reason 'WHY' --event-ids 4953
```

---

## The misses that are NOT in this queue

1 of the 4 unmatched gold events have acquired no row that the alias-and-window rule proposes. There is nothing to decide about them here; they are listed because the first question anyone asks of a recovery count is what happened to the rest. Every row shown matches the employer alias at ANY date, which is wider than the matching rule on purpose.

### WABASH NATIONAL Corp — 270, filed 2026-01-05

`sec-205-0000879526-26-000003` — `not_matched` — <https://www.sec.gov/Archives/edgar/data/879526/000087952626000003/wnc-20260105.htm>

| tracker event | company as we hold it | count | effective | announced | source |
|---|---|---:|---|---|---|
| 144268 | Wabash National | 790 | 2009-05-01 | 2009-05-01 | warn |
| 1466 | Wabash National LP | 6 | 2026-03-06 | 2026-01-05 | warn |
| 1467 | Wabash National LP | 94 | 2026-03-06 | 2026-01-05 | warn |

Previously rejected for this event: [1467, 1466].

- `match_notes`: The filing idles Little Falls, Minnesota and Goshen, Indiana. The only in-window Wabash rows are CA WARN (94+6), a different site.

