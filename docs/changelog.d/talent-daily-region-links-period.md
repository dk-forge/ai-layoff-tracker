---
version: 2.20.297
type: fix
area: digest
date: 2026-11-05
---
- Talent daily (digest-talent-briefing.php): the "By region" line now comes from `alt_talent_region_lead`, which ranks the regions Notes prints by count (it used to take the first region of the fixed `alt_briefing_region_order`), never leads with "Not recorded" or the catch-all, names every tied region, and adds the runner-up.
- Each hiring line links "Open roles" to the employer's verified job board when the window holds an `ats_boards` row for the same `company_key` (`alt_talent_job_boards`); no row, no link.
- "In context" line names its window (same since..until as the hiring list) and says "distinct employers", since `companies` is `COUNT(DISTINCT company_key)`.
- Tests: test_digest_talent_daily_lead_links_period.py.
