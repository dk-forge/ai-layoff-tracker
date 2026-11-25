---
title: Placement tags on tracker signup links
date: 2026-11-25
files: wordpress-plugin/ai-layoff-tracker/includes/atr-signup-cta.php, wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, railway/tests/test_atr_signup_cta.py
tests: Inline and sticky placement, optional sanitized content, and single facet value; tests not run locally, CI runs them.
rollback: Revert the optional content argument and its two callers.
env: none
---

Inline signup links carry the inline placement, and the tracker phone bar carries sticky_bar. Existing callers that omit the optional argument keep their current URL. Blog and facet placement values remain unchanged.
