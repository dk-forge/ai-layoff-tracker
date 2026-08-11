# Forensic enumeration: the US headline step of 2026-08-08

> **SUPERSEDED IN PART, 2026-08-11.** Section 4 below reports the affected row
> IDs as UNKNOWN. They are now known: **114335, 113529, 64351.** Section 5's
> "which mutation did it" is answered too. See
> [section 8](#8-resolution-2026-08-11-the-rows-are-named-and-the-published-us-figure-is-wrong)
> at the end, which was written after a recomputation of the live corpus and
> does not depend on `updated_at`. Sections 1 to 7 are left exactly as they were
> written on 2026-08-10, including the UNKNOWNs, because a forensic record that
> is quietly rewritten once the answer arrives is not a record.

**Status:** enumeration only. **No data row was changed, no threshold, bound or
invariant was adjusted, and nothing was done to make the failing check green.**
This document records what changed, what did not, and which of the review's
claims the evidence supports.

**Scope of the failure.** `data_integrity.MovementInvariant`, slice
`us_all_time` (`country=United States`, `country_basis=any`), reported on
2026-08-10:

    +93,210 over 3.0d on +18 entries (6,968,670 -> 7,061,880)

The invariant compares the live `/aggregate` totals for each watched headline
against the committed observation in `railway/headline_baseline.json`, which
`data-integrity.yml` records once a day and deliberately refuses to advance over
a FAILING slice. That refusal is why the US baseline is pinned at
2026-08-07T18:23:51Z while the other two slices advanced to 2026-08-09, and why
the reported span keeps growing (1.0d, then 2.0d, then 3.0d) for one single
underlying step.

---

## 1. Every watched headline, old and new counted status

Sources: the committed baselines (`git log railway/headline_baseline.json`,
commits `4028cec`, `7ed66d8`, `806ba8d`) and the `Live data-integrity check`
run logs (`31206696356`, `31270755440`, `31327886921`). The 2026-08-10 column is
a live read of `/aggregate` with a cache buster, taken for this investigation.

| Headline slice | 2026-08-07 18:23Z | 2026-08-08 17:58Z | 2026-08-09 18:00Z | 2026-08-10 live |
|---|---|---|---|---|
| `ai_all_time` (`ai=1`) | 215,065 / 99 | 215,065 / 99 | 215,065 / 99 | 215,065 / 99 |
| `worldwide_all_time` (no filter) | 20,392,202 / 63,574 | 20,405,466 / 63,595 | 20,406,155 / 63,601 | 20,407,113 / 63,602 |
| `us_all_time` (`country_basis=any`) | 6,968,670 / 43,341 | 7,061,356 / 43,356 | 7,061,881 / 43,360 | 7,061,880 / 43,359 |
| `worldwide_recent_90d` | 316,728 | 324,159 | 323,844 | movement not watched |

Verdicts as recorded by the runs: 2026-08-07 `headline_movement` PASS for all
three watched slices (US read `+4,680 jobs over 2.0d`, floor 39,445).
2026-08-08 and 2026-08-09 FAIL, US only; AI and worldwide PASS on both days.

The 90-day slice carries `watch_movement=False` by design (a sliding window is
not comparable day over day), so it has no movement status to report. It is
listed for completeness because it is the fourth entry in `HEADLINES`.

### The step is one step, not a drift

| Interval | US (`basis=any`) | Worldwide | US entries | Worldwide entries |
|---|---|---|---|---|
| 08-07 -> 08-08 | **+92,686** | +13,264 | +15 | +21 |
| 08-08 -> 08-09 | +525 | +689 | +4 | +6 |
| 08-09 -> 08-10 | -1 | +958 | -1 | +1 |

Everything happened inside one ingest cycle, 2026-08-07T18:23:51Z to
2026-08-08T17:58:25Z. The two later days are ordinary.

---

## 2. The asymmetry is CONFIRMED, and it is arithmetic, not inference

The US slice is a subset of the worldwide slice: `worldwide_all_time` has no
country filter at all, so every row counted into US is also counted into
worldwide. Over the step interval the US headline rose 92,686 while the
worldwide headline rose 13,264. **79,422 jobs entered the published US figure
without entering the corpus.** Over the full 08-07 to 08-10 span the same figure
is 78,299 (93,210 minus 14,911).

No genuinely new event can do that. Either rows already in the corpus began
being counted as US, or an offsetting mass left the non-US population in the
same window. Both are re-scoring of already-published rows, which is exactly the
class `MovementInvariant` exists to catch. The guard is behaving correctly and
the number it is complaining about is a wrong number already published.

---

## 3. The leading hypothesis is REFUTED as the cause of this step

The review proposed that existing rows gained a US `employer_country`, entering
the US slice through the inclusive `country_basis=any` union (job location OR
employer domicile). Measured live on 2026-08-10:

| Population | Jobs | Entries |
|---|---|---|
| US, `country_basis=any` (the published headline) | 7,061,880 | 43,359 |
| US, strict job location (`country=United States`) | 6,192,930 | 43,233 |
| **Union-only** (`employer_country=United States` AND `country != United States`) | **868,950** | **126** |
| All rows with `employer_country=United States` | 1,079,511 | 156 |

The union-only set is 126 rows. Their `employer_country_evidence` fields:

- 107 rows carrying **815,982** jobs are stamped
  `Curated employer-domicile registry (2026-07-19)`.
- 19 rows carrying 52,968 jobs carry free-text extractor evidence set at
  ingest, or none.
- **Zero rows carry evidence dated inside the incident window.**

Their job-location labels are `Multiple countries`, `France`, `China`, `Spain`
and `Canada`.

Two further facts close it:

- The `Employer-domicile curated backfill` workflow
  (`.github/workflows/employer-domicile-backfill.yml`), the only job whose
  purpose is to write `employer_country` in bulk, **has never run** —
  `gh run list --workflow=employer-domicile-backfill.yml` returns nothing.
- The one job in the window that does write domicile evidence,
  `Enrich announcement and domicile evidence` (run **31239836897**,
  2026-08-08T04:36Z), reported `"changed": 0` in its own spend ledger line.

So the domicile union did not grow in the window. The move is inside the strict
job-location US population, not in the union that sits on top of it. The
review's named rows do not survive either: **DOGE row 70043, 60,000 jobs, was
already the largest row in the US headline on 2026-08-07** (the concentration
block that day reads `0.86% (60,000 of 6,968,670), row 70043`), so it did not
newly enter. Oracle row 70257, 21,000, is the largest row in `ai_all_time`,
whose total did not move at all across the whole period.

---

## 4. Row IDs whose counted status changed: UNKNOWN

**This is the part of the assignment that cannot be answered from outside the
database, and it is reported as UNKNOWN rather than inferred.**

`wp_alt_layoffs` carries `updated_at` (db.php schema), but no public endpoint
exposes it, none of `/query`'s 35 returned fields includes it, and `/query`'s
sort whitelist is `layoff_date, job_count, company, country, state, industry` —
there is no way to ask the live API "which rows changed since Friday". The
`/dataset-releases` ledger records only totals per release
(`canonical_rows`, `canonical_events`, `source_reports`), explicitly "snapshot
only", and its most recent entry predates the step (2026-08-07T05:38Z, plugin
2.20.2). No Wayback capture of the tracker page exists for 2026-08-05 to
2026-08-11. Nothing in the repository stores a per-row snapshot.

Consequently the requested table of row IDs with old and new `country`, old and
new `employer_country` and job count **cannot be produced from the public
surfaces**, and no per-row verdict is offered for it. Producing it needs one of:
a `SELECT id, country, employer_country, job_count FROM wp_alt_layoffs WHERE
updated_at BETWEEN '2026-08-07 18:23:51' AND '2026-08-08 17:58:25'` against the
Bluehost DB, or a new read-only endpoint exposing `updated_at`. Either is a
change to code or a credentialed action, both out of scope here.

---

## 5. Which mutation did it: NOT ESTABLISHED, but the field is narrowed

Every workflow that completed between the two readings was checked, and its own
output read. No commit touched `wordpress-plugin/` or `railway/` in the window
(the only commits are the baseline and the OpenRouter balance chore), so the
filter semantics themselves did not change; the last plugin change, `c43f535`
of 2026-08-06, is archive cadence and does not touch country filtering.

| Run | Workflow | Its own reported effect |
|---|---|---|
| 31239674865 | Reclassify legacy AI evidence | changed 0 |
| 31239836897 | Enrich announcement and domicile evidence | changed 0 |
| 31241155543 | Extract affected-role categories | updated 5 (roles only) |
| 31241599412 | Reason-tag backfill | edited 400 (`reason_tags` only) |
| 31241856790 | Industry backfill | 28 rows (`industry` only) |
| 31242849294 | EDGAR history sweep | 0 posted, 181 non-events |
| 31243797897 | Historical global news sweep | 1 posted |
| 31245744248 | Canonical event migration | processed 0, canonical_repaired 0 |
| 31260373742 | ERM import | 4 events, 593 jobs |
| **31260416534** | **WARN notice import (US states)** | **41,565 upserted from 41,591 notices** |
| 31262464401 | Supplemental news ingest | no rows reported |
| 31263135122 | Cross-source dedup (LLM) | merged 3 rows (176812, 384, 176953) |
| 31267924611 | AI evidence sweep | 2 rows |
| 31268331822 | Hawaii WARN OCR import | 34 upserted |
| 31268589521 | Superset dedup reconciliation | **changes 0** (members 402, jobs_excluded 105,513) |

The reconciler is exonerated by its own output: `changes: 0`. The previous day's
run (31202583390, 2026-08-07T17:30Z, before the baseline was taken) reported
`changes: 2` and `jobs_excluded: 108,513`; the 3,000-job difference between the
two exclusion totals is an order of magnitude too small and moves US and
worldwide together in any case.

The only writer in the window with the necessary mass is the **daily WARN
import, run 31260416534**, which upserts all 41,565 US WARN notices every day.
It is US-only by construction, which fits the US side of the asymmetry. It does
**not** by itself explain the worldwide side: a WARN row entering the corpus
raises worldwide by the same amount it raises US, so for worldwide to have risen
only 13,264 something must also have removed roughly 79,000 jobs from the non-US
population in the same window, and no run in the table reports doing that.
Whether that is a second, unlogged effect of the same upsert (a changed job
count changes a row's dedup hash, per CLAUDE.md, and re-keys the row) or a
separate event is **UNKNOWN** and is precisely what the `updated_at` query in
section 4 would settle.

---

## 6. Verdicts

Per-row verdicts (a)/(b)/(c) cannot be issued without the row list; see
section 4. What the evidence does support:

**On the step itself — no verdict yet, but not (c).** Nothing was intentionally
redefined: no code changed, no bound moved, no correction run executed. It is
(a) WRONG DATA or a mechanical re-keying, and it is live on the site now. It is
not a deliberate definition change.

**On the 126 union-only rows — (b) CORRECT DATA UNDER A MISLEADING LABEL, and
this is a real finding independent of the incident.** 868,950 jobs, **12.3% of
the published "United States jobs, all time" figure of 7,061,880**, come from
126 rows whose job location is recorded as `Multiple countries`, `France`,
`China`, `Spain` or `Canada`. Each row keeps its true country label, and the
union is documented in CLAUDE.md and in `db.php` as intentional. Both things are
true at once: the rows are right, the mechanism is deliberate, and a reader
seeing "United States jobs" is not told that an eighth of it is jobs located
elsewhere at US-domiciled employers. That is a labelling decision, not a data
defect, and CLAUDE.md's "don't fix the discrepancy" is about the filter
semantics, not about whether the surface says which basis it used.

---

## 7. What the owner should decide

Three separate decisions, in this order.

1. **Get the row list.** Nothing else can be settled without it. Either run the
   `updated_at` window query against the Bluehost DB directly, or add a
   read-only endpoint that exposes `updated_at` so this class of question is
   answerable from the public surface next time. Until then the movement guard
   is correctly red and should stay red.
2. **Then correct, having seen the rows** — not before. The guard is doing its
   job; the baseline recorder is correctly refusing to launder the number. Do
   not advance the baseline, do not raise `move_floor`, do not widen
   `mean_factor`.
3. **Separately, decide the label.** The union question is not the incident and
   should not be bundled into fixing it. The options are to relabel the headline
   so it states its basis, to publish the strict job-location figure
   (6,192,930) alongside it, or to leave it and accept that 12.3% of the US
   figure is non-US job locations. This is the owner's call, and the number
   above is what it costs either way.

---

*Compiled 2026-08-10. Read-only. Live figures taken from
`/wp-json/layoffs/v1/aggregate` and `/query` with cache busters; run figures from
GitHub Actions logs by run ID; historical headline figures from committed
`railway/headline_baseline.json` revisions. No row, threshold, bound or
invariant was modified.*

---

## 8. Resolution, 2026-08-11: the rows are named, and the published US figure is wrong

Written by a later session that was asked one different question. Not "what
changed" — that was settled as unrecoverable, because `updated_at` postdates the
window — but **"is the number published today correct?"**, answered by
recomputing the US slice from the corpus instead of by inspecting history. The
recomputation is what named the rows.

### 8.1 What the live figures are, and that they are internally exact

Read 2026-08-11 with cache busters. Every figure below is `/aggregate` unless
it says `/query`.

| Basis | Jobs | Entries |
|---|---|---|
| Worldwide, all time (no country filter) | 20,407,420 | 63,605 |
| US, `country_basis=any` — **the basis `us_all_time` watches** | 7,061,960 | 43,360 |
| US, strict job location (`country=United States`) | 6,193,010 | 43,234 |
| Union-only (in `any`, not in strict) | 868,950 | 126 |

The published number is an exact function of the rows, and four independent
paths say so:

- **Row by row.** Walking `/query` for the `any` slice returns 43,755 rows
  summing to **7,162,028**. 395 of those rows are superset members, which
  `/aggregate` excludes: **7,162,028 − 100,068 = 7,061,960**, the published
  figure, to the job.
- **The same walk worldwide** returns 64,007 rows summing to 20,512,933, an
  excess of **105,513 over 402 rows** — which is exactly what the reconciler's
  own run log reports (`members 402, jobs_excluded 105,513`). The two numbers
  were produced by different code on different days and agree.
- **The country partition.** `top_countries["United States"]` computed over the
  worldwide slice is 6,193,010, identical to the strict US total computed with
  the country filter applied. And 6,193,010 + 868,950 = 7,061,960.
- **The source-type partition** sums to the total exactly on all three slices.

**Containment holds on both bases**, at row identity and not merely
arithmetically: every one of the 43,755 US ids appears in the 64,007 worldwide
ids, 7,061,960 ≤ 20,407,420, and 43,360 ≤ 63,605.

So the published figure is a faithful computation of the corpus. That is a
different claim from the corpus being right, and it is not the finding.

### 8.2 The finding: three ERM rows contradict their own source

`erm_import.py` builds each row's excerpt as

```python
excerpt = f"{rtype} at {company} ({country}): {jobs:,} announced job losses. ..."
```

so **every ERM row carries, in its own published text, the country it was
imported with**, written once and never rewritten. Comparing that to the
`country` column asks "has this row been re-scored since import?" with no
history table and no timestamp — and answers it for rows that changed long
before the schema learned to record when.

Across all **19,494** live ERM rows, exactly **three** disagree:

| id | Company | Jobs | Imported as | Stored now | `edited` | Eurofound factsheet says |
|---|---|---|---|---|---|---|
| 114335 | Citigroup | 52,000 | Multiple countries | **United States** | true | [67409](https://apps.eurofound.europa.eu/restructuring-events/detail/67409): Country **World** |
| 113529 | General Motors | 47,000 | Multiple countries | **United States** | true | [68252](https://apps.eurofound.europa.eu/restructuring-events/detail/68252): Country **World** |
| 64351 | Cinemaworld | 45,000 | Multiple countries | **United States** | true | [102392](https://apps.eurofound.europa.eu/restructuring-events/detail/102392): Country **World**, units in United Kingdom, United States |

Three facts close it. The importer has mapped `World` to `Multiple countries`
since the day it was written (`COUNTRY_FIX`, commit `c5c404d`), so it never
produced these values. All three rows carry `edited: true`, so they were
rewritten through `/edit` after publication. And every other ERM `World` row in
the corpus is still labelled `Multiple countries` — Bank of America 114131 and
110920, 30,000 each, sit beside them untouched.

**144,000 jobs are counted as physically located in the United States that the
cited source records as worldwide.**

### 8.3 The same three rows are the 2026-08-08 step

Their arithmetic is the asymmetry section 2 measured, and it fits without a
free parameter. Two of the three carry no `employer_country`; Citigroup's is
already `United States`, so Citigroup sits in the `any` slice under either
label and only the strict slice sees its 52,000.

| | strict US | `any` US | worldwide |
|---|---|---|---|
| Effect of the three re-scorings | +144,000 | **+92,000** | **0** |
| Observed 08-07 → 08-08 | not recorded | **+92,686** | **+13,264** |
| Residual, i.e. ordinary ingest | — | +686 | +13,264 |

A re-scoring moves a row between country labels without adding anything to the
corpus, which is precisely how the US headline could rise 92,686 while the
superset it belongs to rose 13,264. The 79,422 the earlier pass could not place
is not a quantity in the data at all: it is 92,000 of re-scoring minus the
12,578 of that day's non-US ingest, which is why searching the corpus for it
finds nothing. Nothing in today's data is anywhere near it — the closest slices
are South Carolina at 80,788 and WARN-dated-2008 at 81,319, and neither is it.

The check on the whole story: correcting the three rows leaves the `any`
headline at **6,969,960**, against a pre-step baseline of **6,968,670** captured
2026-08-07T18:23:51Z. **+1,290 over four days**, against a floor of 20,000 a
day. The step disappears.

### 8.4 Verdict: (a) the published figure is WRONG

Not "annoying", not "unexplained". The US headline overstates by **92,000 jobs
on the published `country_basis=any` basis** and by **144,000 on the strict
job-location basis**, and the worldwide total is unaffected, because the rows
are in the corpus either way.

**The incident stays OPEN.** It is not closed by naming the cause; it is closed
when the correction has landed and the recomputation agrees. Do not advance the
baseline, do not widen `move_floor`, `mean_factor` or `max_share`.

### 8.5 The correction, ready to run

A country relabel, not a count change, so the dedup hash is unaffected and no
purge-and-reimport is needed. `/edit` suppresses the original hash so the
nightly re-scrape cannot revert it, and **appends the reason verbatim to the
PUBLIC corrections log** - which is why the reason below is written as public
copy rather than as a note to ourselves.

Dispatch `Apply a signed-off correction` (`.github/workflows/apply-correction.yml`)
with `apply=false` first, read the dry run, then again with `apply=true`:

```bash
gh workflow run apply-correction.yml \
  -f ids=114335,113529,64351 \
  -f action=edit \
  -f 'fields={"country": "Multiple countries"}' \
  -f verify_company=Citigroup \
  -f reason="Three Eurofound entries returned to Multiple countries, 144,000 jobs. Citigroup, General Motors and Cinemaworld are recorded by the European Restructuring Monitor as worldwide restructurings, and were imported that way. All three had since been relabeled as United States job locations, which counted 144,000 worldwide job losses in our United States location total and 92,000 in the United States headline. The worldwide total is unchanged, because the entries were always in it." \
  -f apply=false
```

This session did not run it with `apply=true`. The workflow's own governance is
that the dispatch IS the human sign-off, and a 92,000-job change to a published
headline is not a session's to sign.

**After it lands**, in one pass:

1. Verify: `/aggregate?country=United States&country_basis=any` should read
   **6,969,960** plus whatever ingest has arrived since, strict should read
   **6,049,010** plus the same, and worldwide should be unchanged by the edit.
2. `python3 railway/erm_provenance_check.py` should report **0 contradictions
   and 0 unreadable**.
3. Check the public corrections log rendered the reason cleanly, and add a
   hand-written entry with its own anchor only if the automatic one reads badly
   in context.
4. Wire `erm_provenance_check` into `data_integrity.INVARIANTS`, now that it is
   green for the right reason.
5. Only then close the incident, with the verified figures as the replacement
   baseline and `--rows 114335,113529,64351`.

### 8.6 Why nothing is being written to the corrections log in this change

The log states what HAS been corrected. Until the dispatch runs, nothing has
been, and a log entry that lands ahead of its own correction is a false
statement on a page whose whole claim is that nothing is quietly edited. The
reason text in 8.5 becomes that entry automatically when the edit is applied.

### 8.7 What now makes this class self-detecting

`railway/erm_provenance_check.py`, read-only, no keys: it reads the imported
country back out of each ERM excerpt and reports every row that no longer
agrees with it. It found these three from nothing but public endpoints, and it
would have found them on the day.

It is **not** wired into `data_integrity.INVARIANTS` yet, on purpose: it fails
right now, correctly, and adding a live check that goes red before its own
defect is fixed manufactures the alert noise the ledger exists to avoid. Wire it
in the session that applies the correction, when it is green for the right
reason.

Its limits are real. It sees ERM only, because ERM is the one importer that
writes its country into the excerpt; it cannot see a re-scoring that also
rewrote the excerpt; and it says a row disagrees with its own provenance, not
when it started to. The general answer to "when" is `/changed-rows`, which is
live and instrumented from 2026-08-10 onward and could not see this window.

---

*Section 8 compiled 2026-08-11. Read-only: no row was written, no bound moved,
no baseline advanced, and the incident was left open. Live figures from
`/aggregate` and a full walk of `/query` with cache busters; the Eurofound
factsheets read directly from apps.eurofound.europa.eu.*
