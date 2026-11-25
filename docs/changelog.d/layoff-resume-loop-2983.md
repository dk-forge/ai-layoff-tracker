---
title: Layoff-to-resume line on company pages and in the daily and weekly digest
date: 2026-11-24
files: wordpress-plugin/ai-layoff-tracker/includes/atr-signup-cta.php, wordpress-plugin/ai-layoff-tracker/templates/page-company-directory.php, wordpress-plugin/ai-layoff-tracker/includes/digest-briefing.php, wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, railway/tests/test_layoff_resume_loop.py, railway/tests/test_atr_signup_cta.py, railway/tests/fixtures/digest_compose_harness.php
tests: Tests written first for the copy, the accessible link text and the full UTM set on company pages and on the daily and weekly digest (HTML and text), monthly excluded, relay UTM tagger leaves the tags alone
rollback: Revert this change; the company page returns to its previous resume line
env: none
---

Growth experiment 1 (todo#2983). Every company page and the daily and weekly digest carry one line: "Laid off from <company>? Check your resume against open jobs, free.", linked to /resume-score with utm_campaign=layoff-resume-loop, utm_medium company-page or digest-email, and utm_content set to the company slug. On company pages it replaces the earlier "Affected by a layoff at <company>?" line. In the digest it names the employer at the top of "Biggest cuts". Pushed, not deployed.
