---
title: Limit public tracker bot page reads
date: 2026-11-23
files:
  - railway/blog_read_cache.py
  - railway/http_retry.py
  - railway/safe_fetch.py
  - railway/endpoint_check.py
  - railway/link_check.py
  - railway/ops_status.py
  - railway/page_weight.py
tests:
  - railway/tests/test_blog_read_cache.py
  - railway/tests/test_collector_backoff.py
  - railway/tests/test_ssrf_safe_fetch.py
  - railway/tests/test_endpoint_check.py
rollback: Revert this change to restore uncached public reads.
env: No production configuration changed. Shared workers need the same private cache directory.
---
Public page clients share cached responses and a one-hour attempt budget.
Authenticated ingestion reads and independent worker caches remain outside this cap.
