---
title: Offline railway helper coverage
date: 2026-11-24
files: railway/tests/test_gen_synthetic_snapshot.py, railway/tests/test_generate_warn_urls.py, railway/tests/test_hi_warn_dryrun.py, railway/tests/test_laya_eval.py, railway/tests/test_local_news_dryrun.py, railway/tests/test_monthly_us_comparison.py, railway/tests/test_nc_warn_check.py, railway/tests/test_recall_uk_adjudication_pack.py, railway/tests/test_static_parity_html.py, railway/tests/test_tracker_crosscheck.py
tests: 51 new unittest methods; CI runs the existing suite. Not run locally under BOARD.md.
rollback: Revert these new test files and fragments.
env: none
---

Add direct unit coverage for ten previously uncovered railway helper and diagnostic modules. All inputs are synthetic, model calls and public reads are mocked, and temporary files stay local to the test. Application code, existing tests, limits and dependencies are unchanged. No live calls or deployment.
