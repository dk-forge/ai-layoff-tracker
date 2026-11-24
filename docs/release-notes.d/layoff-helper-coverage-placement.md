---
title: Layoff tracker helper coverage and link placement
date: 2026-11-24
files: railway/dmarc_report.py, railway/tests/test_dmarc_report.py, railway/tests/test_industry_propagate.py, railway/tests/test_deduplicator_unit.py, railway/tests/test_cta_placement.py, wordpress-plugin/ai-layoff-tracker/includes/atr-signup-cta.php
tests: New offline unittest cases and PHP harness; CI runs them, not run locally.
rollback: Revert this change.
env: none
---

Cover local aggregate-report formats and return states, industry propagation thresholds and write batches, and fail-open diagnostic lookup with fake credentials and requests. Correct the report return-code docstring. Resume match links now distinguish inline, sticky, hero and widget placements without changing their destination or existing campaigns. Public facet content tags remain unchanged.
