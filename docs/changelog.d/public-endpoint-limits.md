---
title: Rate limit public tracker endpoints by peer and user
date: 2026-11-23
files: wordpress-plugin/ai-layoff-tracker/includes/public-rate-limits.php; wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php
tests: railway/tests/test_public_rate_limits.py; repository suite
rollback: Revert this PR; deactivate first to clear its cleanup event and counter rows.
env: No production configuration changed. Existing MySQL or MariaDB named locks are required.
---
Public REST callbacks, downloads and form actions share IP and signed-in-user
quotas before service work. Excess requests get 429 and Retry-After; unavailable
counter storage stops work with 503. Salted counters survive response-cache flushes
and expire through scheduled cleanup. Normal tracker CTAs and signed consent
withdrawal paths remain. No deployment or live-host verification was performed.
