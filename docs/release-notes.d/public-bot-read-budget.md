---
title: Limit all tracker bot blog reads
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
All bot blog reads share a one-hour attempt budget, including authenticated APIs.
Public pages can be cached. Private responses are never persisted or replayed.
Workers need a shared private persistent cache to coordinate across machines.
