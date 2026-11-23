# Public blog read budget

Anonymous `AiLayoffTracker/1.0` reads of asktherecruiter.com/blog pages share a
one-hour disk cache and per-URL process lock. A pending marker is written before
network access. Failures also spend the budget, so retries cannot multiply load.
Cache-busting parameters do not create a new budget; real filters still do.
Redirects are checked one hop at a time by buffered clients. Streaming probes
retain their original size limits and transport, spend the budget and fail
explicitly on repetition rather than inventing an empty cached response.

The common requests retry helper, safe fetcher, link checker, page-weight check,
ops page reads and pinned endpoint probe use this budget. Challenge-cookie
replays are disabled for these public page reads. SSRF checks and DNS pinning
remain in their original callers. No network request is made by the unit tests.

## Scope and operations

The cache is under `~/.cache/alt-public-pages`, or `ALT_BLOG_CACHE_DIR` when set.
It must be private to the worker owner and retained between runs. Workers sharing
that directory share the cap. Separate machines with separate filesystems do not;
operators must use a shared persistent directory or a single worker before
claiming a cross-machine cap. This PR does not change production configuration.

Authenticated requests, WordPress API/admin routes, browser-user-agent probes,
writes and third-party source collection are unchanged. Ingestion intentionally
uses fresh keyed API responses to avoid reprocessing old batches. Extending the
cap to those reads needs an ingestion freshness decision. The static parity
checker's separate manual-job cache is not unified by this change.

Private headers and secret query parameters are excluded. Public cached responses
never retain Set-Cookie headers. Request headers and raw URLs are not written to
the cache. Transport representations use separate variants within the same URL
budget: a variant mismatch stops the read rather than sending a second request.

## Validation and rollback

Run `cd railway && python -m unittest tests.test_blog_read_cache
 tests.test_collector_backoff tests.test_ssrf_safe_fetch tests.test_endpoint_check
 tests.test_deploy_reaches_readers -q` on one line. The tests use fake transports,
a temporary cache and an injected clock, including the exact hourly boundary.
Revert the change to restore the previous clients. No deployment or host changes
are part of this PR.
