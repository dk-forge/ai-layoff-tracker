---
title: Plain resume wording on tracker signup surfaces
date: 2026-11-25
files: wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, wordpress-plugin/ai-layoff-tracker/templates/page-chart-embed.php, wordpress-plugin/ai-layoff-tracker/includes/digest-sections.php, railway/tests/test_resume_cta.py, railway/tests/test_digest_sections.py
tests: Copy assertions and source guard written first; tests not run locally, CI runs them.
rollback: Revert this copy change and its tests.
env: none
---

Tracker next-step lines, chart embeds and the talent digest use plain resume wording. The tool name reads Ask The Recruiter. Link destinations and tracking values are unchanged.
