# WARN transparency register

This is a separate, source-evidenced research register. It is **not** a
measure of layoffs, AI-related layoffs, WARN compliance rates, or legal
liability. Its records never enter tracker headline totals, charts, exports,
or AI statistics.

## Permitted labels

- `notice_recorded_60_plus_days` — a primary notice records dates at least 60
  calendar days apart. This is a timing observation, not legal advice.
- `short_notice_exception_stated` — a primary source records a shorter
  interval and explicitly states an exception or basis. This does not decide
  whether the exception applies legally.
- `short_notice_unresolved` — a primary source records a shorter interval but
  the register has no adjudication. It is explicitly not a violation label.
- `court_adjudicated_warn_violation` — a court order, judgment, or settlement
  source is retained. Only this label can use the word “violation.”

## Admission safeguards

Every record requires a state, employer, source URL, named source and a
non-trivial evidence excerpt. Date labels require source-evidenced notice and
affected dates; the API verifies their stated 60-day threshold. An exception
needs explicit exception evidence. A court label also requires an adjudication
URL and evidence excerpt.

The register is manual/editorial. No automation may infer notice dates,
exceptions, legal compliance, or liability. Corrections preserve sources. A
SHA-256 hash protects the retained excerpt only; it is not an archive of a
source page.

## Stage 1: compliance-evidence builder

[WARN_TRANSPARENCY_STAGE1.md](WARN_TRANSPARENCY_STAGE1.md) adds an offline
builder (`railway/warn_transparency_evidence.py`) that computes notice-gap
days by pure arithmetic on officially recorded notice/effective dates. Pure
arithmetic on recorded fields is permitted; inference and imputation remain
banned — rows missing either date are excluded, never guessed, and
amended/revised notices use the earliest recorded notice date. Gaps under 60
days are queued as `short_notice_candidate` timing observations with the
official source URL as evidence and statutory context attached (60-day rule,
faltering-company / unforeseeable-business-circumstances / natural-disaster
exceptions, judicial-only enforcement). Candidates are editorial-review
inputs, not register records: a human verifies the source before any keyed
write, and no builder output ever labels an employer non-compliant.
