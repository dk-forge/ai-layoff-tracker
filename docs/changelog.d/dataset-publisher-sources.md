---
title: Name the layoff Dataset publisher and link its sources
date: 2026-11-24
files: wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, railway/tests/test_dataset_publisher_2932.py
tests: Tests written first for both Dataset publishers, source links, unchanged creator and version agreement; tests not run locally, CI runs them
rollback: Revert this schema change before any later deployment
env: none
---

Both layoff Dataset emitters name Ask The Recruiter Research as publisher and link the existing sources page. Creator and Article schema nodes are unchanged. Pushed, not deployed.
