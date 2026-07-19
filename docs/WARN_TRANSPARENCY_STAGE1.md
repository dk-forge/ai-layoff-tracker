# WARN transparency — stage 1: adjudication-evidence groundwork

Stage 1 of the separate WARN transparency register (foundation:
[WARN_TRANSPARENCY_DATASET.md](WARN_TRANSPARENCY_DATASET.md), guarded by
`railway/tests/test_warn_transparency_guards.py`). It adds two things:

1. **A compliance-evidence builder** — `railway/warn_transparency_evidence.py`,
   an offline module that computes notice-gap days by pure arithmetic on
   officially recorded WARN dates and queues *candidates* for editorial review.
2. **A public read-only endpoint design** (spec only; no PHP in this stage).

The foundation's invariant is unchanged and load-bearing: **no employer is ever
labeled non-compliant.** The WARN Act's exceptions are legally legitimate, only
courts adjudicate them, and this dataset presents "notice gap in days +
statutory context" — never a verdict.

## 1. The compliance-evidence builder

Input: WARN rows that record **both** an official notice date and an official
effective (affected) date, plus the official source URL. Output: a JSON build
with `methodology` (full cited statutory context), `candidates`, and `excluded`
counts.

Rules, each pinned by an offline test in
`railway/tests/test_warn_transparency_evidence.py`:

- **Pure arithmetic.** `notice_gap_days = effective_date − notice_date` in
  calendar days, the same semantics as the register writer's PHP
  (`floor((affected − notice) / DAY)`). Nothing else is computed.
- **Gaps below 60 days become `short_notice_candidate`** — a timing
  observation queued for human review, with the official source URL retained
  as evidence and a fixed statutory-context note attached. It is explicitly
  not a violation label and never becomes one automatically.
- **Gaps of 60+ days become `notice_recorded_60_plus_days`**, matching the
  register's existing timing label semantics (exactly 60 is 60-plus).
- **Missing dates stay excluded, never imputed.** A row missing either date,
  or carrying a non-ISO / implausible date (outside 2015-01-01..2028-12-31,
  the same window `railway/sources/warn.py` enforces), is counted in
  `excluded` and dropped. Ambiguous formats (`03/06/2026`, `TBD`, prose) are
  refused rather than interpreted.
- **Effective-before-notice rows are excluded**, not treated as short notice:
  they are either source data errors or lawful after-the-fact notices under
  29 U.S.C. § 2102(b)(3), and the register's timing labels (whose writer
  rejects negative intervals) cannot hold them. Human review only.
- **Amended/revised notices use the earliest notice date.** Rows sharing
  (state, employer, effective date) collapse to one candidate on the earliest
  recorded notice date — the first service of notice is what the statute
  times — and the evidence URL cites the filing that recorded that date. All
  recorded dates are kept in `amended_notice_dates`.
- **No candidate without an official source URL.**
- **Offline and write-free.** Stdlib only; no network, no LLM, no API key.
  Posting anything to the keyed `/warn-transparency` writer remains a manual
  editorial act after a human has checked the source — automation may compute
  arithmetic on recorded dates, but may never infer dates, exceptions,
  compliance, or liability.

CLI (local files only):

```bash
python3 railway/warn_transparency_evidence.py rows.json out.json
```

## 2. Public read-only endpoint (design — do not implement yet)

`GET /wp-json/layoffs/v1/warn-transparency/notice-gaps`

- **Read-only, keyless, public.** Backed by the existing
  `wp_alt_warn_transparency` table only — never joined to layoff tables or
  aggregate endpoints, and its numbers never enter layoff/AI totals, charts,
  or exports (foundation invariant).
- **Rows served:** register records whose `assessment_status` is one of the
  three timing labels and which have both `notice_date` and `affected_date`.
  The response adds a server-computed `notice_gap_days` per record using the
  identical arithmetic (`floor((affected − notice) / DAY)`). Records missing
  either date are omitted from this view, never backfilled.
- **Response shape:**

  ```json
  {
    "methodology": {
      "scope": "…separate register, not layoff/AI totals…",
      "legal_safeguard": "…a short interval is not labelled a violation…",
      "statutory_context": { "notice_requirement": "…29 U.S.C. § 2102(a)…",
                             "recognized_exceptions": { "faltering_company": "…",
                               "unforeseeable_business_circumstances": "…",
                               "natural_disaster": "…" },
                             "reduced_notice_duty": "…§ 2102(b)(3)…",
                             "burden_of_proof": "…20 C.F.R. § 639.9…",
                             "enforcement": "…29 U.S.C. § 2104; 20 C.F.R. § 639.1(d)…",
                             "state_law_caveat": "…", "disclaimer": "…" },
      "statutory_notice_days": 60
    },
    "records": [ { "state": "CA", "employer": "…",
                   "assessment_status": "short_notice_unresolved",
                   "notice_date": "2026-01-05", "affected_date": "2026-02-20",
                   "notice_gap_days": 46,
                   "source_name": "…", "source_url": "…",
                   "evidence_excerpt": "…", "evidence_hash": "…" } ],
    "generated_at": "…", "total": 0
  }
  ```

- **Never present:** any field named or valued `violation` outside the
  court-adjudicated status; compliance rates; percentages of "violators";
  employer rankings by gap. Sorting is by `created_at`/`id` (as the existing
  GET does), not by gap size — a leaderboard of short gaps would be an implied
  verdict.
- **Filters:** optional `state` (2-letter, validated), optional
  `status` (must be one of the three timing labels; the court label is served
  by the existing `/warn-transparency` GET with its adjudication evidence and
  is out of scope for this arithmetic view).
- **Paging:** `limit` (default 100, max 500) and `offset`; same bounds
  discipline as the existing register GET.
- **Caching:** salted by `alt_data_ver` like other bounded data caches, so
  keyed writes invalidate it safely.
- **Failure mode:** if the table is unavailable, return an explicit error —
  never an empty list presented as "no records" (same principle as the
  collector-health "unavailable is not 0" rule).

Implementation lands in a later stage with a plugin `Version:`/`ALT_VERSION`
bump per deploy rules; the guard tests should then be extended to statically
assert the endpoint never emits the word "violation" for timing rows.

## 3. Statutory context (verified 2026-07-18)

All statutory quotations are from the U.S. Code and CFR as published at
law.cornell.edu (LII); statutory text is public domain.

- **The 60-day requirement — 29 U.S.C. § 2102(a):** an employer "shall not
  order a plant closing or mass layoff until the end of a 60-day period after
  the employer serves written notice" to affected employees or their
  representative, the State dislocated-worker unit, and the chief elected
  official of the local government.
- **Faltering company — 29 U.S.C. § 2102(b)(1); 20 C.F.R. § 639.9(a):**
  applies to plant *closings* only. The employer must have been actively
  seeking capital or business which, if obtained, would have enabled it to
  avoid or postpone the shutdown, and must have reasonably and in good faith
  believed that giving notice would have precluded obtaining it.
- **Unforeseeable business circumstances — 29 U.S.C. § 2102(b)(2)(A);
  20 C.F.R. § 639.9(b):** the closing or mass layoff was "caused by business
  circumstances that were not reasonably foreseeable" when notice would have
  been required (e.g., sudden termination of a major contract, an
  unanticipated dramatic downturn).
- **Natural disaster — 29 U.S.C. § 2102(b)(2)(B); 20 C.F.R. § 639.9(c):** no
  notice is required when the closing or layoff "is due to any form of
  natural disaster" (flood, earthquake, drought, storm); the employer must
  show direct causation.
- **Reduced notice still requires notice — 29 U.S.C. § 2102(b)(3):** an
  employer relying on an exception "shall give as much notice as is
  practicable" together with "a brief statement of the basis for reducing
  the notification period."
- **Burden of proof — 20 C.F.R. § 639.9:** "the employer bears the burden of
  proof that conditions for the exceptions have been met."
- **Enforcement is judicial only — 29 U.S.C. § 2104; 20 C.F.R. § 639.1(d):**
  WARN is enforced through civil actions in U.S. district courts brought by
  employees, their representatives, or local governments; liability is back
  pay and benefits for up to 60 days (with credits and a good-faith reduction
  provision) plus up to $500/day owed to a local government. The Department
  of Labor has no enforcement standing and issues no compliance
  determinations.

**Why this forbids verdicts:** a sub-60-day gap on the face of official
filings is compatible with fully lawful conduct under § 2102(b), the employer
has not been heard, and the only body that can decide otherwise is a court.
Some states also run mini-WARN laws with different thresholds and longer
notice periods, so the federal 60-day arithmetic says nothing about state-law
obligations. The dataset therefore presents the recorded gap and this
statutory context, and stops there.
