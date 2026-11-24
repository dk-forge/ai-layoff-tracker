---
title: Evaluation bookkeeping coverage
date: 2026-11-24
files: railway/tests/test_eval_haiku55.py, railway/tests/test_uk_recall_probe.py
tests: Eleven new unittest methods; CI runs them. Not run locally under BOARD.md.
rollback: Revert the new test file and fragments.
env: none
---

Finish the coverage batch with synthetic stratified samples, explicit gold labels, usage counters and result summaries. No model client or paid-call path is invoked. The recall diagnostic also distinguishes known rows, missing sources and unreadable or unrun lookups using fake responses. Existing code, tests, limits and dependencies are unchanged.
