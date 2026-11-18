---
version: 2.20.340
type: fix
area: data-integrity
date: 2026-11-18
---
- Referee rule 6 now names denials ("not related to 60,000 job cuts", "denies layoffs", "no layoffs planned") as not cuts. The extraction-time negation guard follows in its own PR. Row 183489 (Microsoft 60,000, 2026-11-13, a Syracuse.com outage headline) was trashed by two-referee adjudication (run 44414877612).
- Monthly/quarterly report hero and press summary name their basis (effective date), which is why October reads 81,061 there and 88,265 on the filing-basis board.
- Largest-entry cells without a record page link to a real period+company filter URL, never href="#".
- Dataset dateModified is the last data write (alt_last_write), never the render clock; omitted when unknown.
- Sign-up CTA: one utm_source=ai-layoff-tracker, utm_medium=referral; the "Affected by a layoff? Check my resume" block added to the ai-quotes hero and every report hero (utm_campaign ai_quotes / report_month / report_quarter / report_week / report_year).
