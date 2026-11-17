---
version: 2.20.332
type: feature
area: growth
date: 2026-11-17
---
- Employer index (/company-layoffs/) and every company page carry one line near the top linking to the free AskTheRecruiter match check (/resume-score), tagged utm_source=layoff_tracker&utm_medium=cta&utm_campaign=directory|company_entry. Owner request 2026-11-17.
- Phones (600px and below, where the legacy header CSS hides "Adapt my resume"): a closable sticky bar "Adapt my resume, free" on those pages only (utm_campaign=sticky_bar). 44px targets, pads the page so content is never covered, no motion under prefers-reduced-motion, close remembered per browser.
- Tests: test_atr_signup_cta.py.
