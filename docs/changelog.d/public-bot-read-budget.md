---
title: Limit public tracker bot reads and budget authenticated API reads
date: 2026-11-23
files:
  - railway/authenticated_blog_reads.py
  - railway/blog_read_cache.py
  - railway/http_retry.py
  - railway/safe_fetch.py
  - railway/endpoint_check.py
  - railway/link_check.py
  - railway/ops_status.py
  - railway/page_weight.py
tests:
  - railway/tests/test_authenticated_blog_reads.py
  - railway/tests/test_blog_read_cache.py
  - railway/tests/test_collector_backoff.py
  - railway/tests/test_ssrf_safe_fetch.py
  - railway/tests/test_endpoint_check.py
rollback: Revert this change to restore uncached public reads.
env: No production configuration changed. Shared workers need the same private cache directory.
---
Only public blog pages share a one-hour attempt budget. Authenticated API reads
are fresh and independent of that cap, with bounded exponential retries and a
200-attempt per-worker budget (ALT_AUTH_READ_BUDGET can override the limit).
A counter-only report separates authenticated API and public blog traffic.
Workers need a shared private persistent cache to coordinate across machines.
