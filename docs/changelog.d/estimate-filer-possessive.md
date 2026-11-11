---
version: vNEXT
type: fix
area: sources
date: 2026-11-11
---
- headcount_estimate.workforce_percent(text, company=None): also reads the FILER's own possessive ("of Workday's current workforce", "reduce Workday's workforce by 3%"); another name's possessive is still refused. estimate_for_filing passes raw_entry company_name. Found on Workday 8-K 0001327811-26-000048 (2026-09-29), dropped as percent-only with no estimate.
- Tests: test_headcount_estimate.py (+3, incl. FICO 0001193125-26-415732 positions sentence).
