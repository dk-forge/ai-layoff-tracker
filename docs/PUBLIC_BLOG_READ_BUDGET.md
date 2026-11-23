# Tracker bot read budget

Only anonymous public pages under asktherecruiter.com/blog spend the one-hour
per-URL disk budget. REST APIs, admin, login, cron and XML-RPC are outside that
public-page scope. An atomic pending marker and process lock prevent concurrent
reads and repeat attempts after a failure. Cache-busting parameters cannot mint
a new budget. Real filters and page numbers identify different URLs.

## Authenticated API reads

Authenticated reads never consult or modify the public hourly cache. Every call
gets a fresh response, including repeated reads of the same URL. Credentials in
headers, query parameters, URL credentials, requests auth options and session
credentials or cookies select this separate policy. Bodies and credentials are
never persisted by this policy. Existing fresh edge-cache query parameters stay
in place.

Each Python worker invocation has a separate authenticated request budget of
200 actual attempts, including retries. ALT_AUTH_READ_BUDGET can set a positive
per-run limit; this is a policy default, not a measured traffic count. A new
invocation starts a new budget. Budget exhaustion fails explicitly before sending
a request. It does not return an old batch or claim a successful read.

Authenticated 429 and 5xx responses get bounded exponential backoff, with at most
three attempts for a direct read. Retry-After seconds are honored up to 60 seconds.
Existing retry helpers own their retry loop instead of nesting another one.
Every attempt, including a helper retry, spends the same per-run allowance.
Writes keep their existing behavior.

At process exit, the stderr `WordPress read traffic` JSON summary separates
`authenticated_api` requests, retries and budget refusals from `public_blog`
origin requests, cache hits and cap refusals. It contains counters only, with no
URLs, keys or response bodies. It is a per-worker report, not a cross-host total.

## Public cache and coverage

Public responses drop Set-Cookie. Buffered clients check redirects hop by hop.
Streaming and pinned probes retain their original transport and read cap;
repeated probes fail instead of receiving fake fresh observations. Requests and
urllib use separate representation variants in one URL budget. Browser-user-agent
public probes also obey the cap. No stale response replaces a transport failure.

The common retry/host-call helpers, direct Python clients, public checks and
explicit workflow GETs use the policy. External hosts are unaffected. The CLI
reads keys from a named environment variable, removes stale output before reading
and exits 75 on an exhausted public or authenticated budget. Quarterly creation
stops on a limited read instead of mistaking it for a missing report.

## Worker coordination

The public cache defaults to ~/.cache/alt-public-pages. ALT_BLOG_CACHE_DIR can
point to an existing private persistent directory. Workers sharing it share the
hourly cap; independent filesystems do not. A single worker or shared persistent
cache is required for a global public cap across machines. This change does not
configure or deploy storage. Authenticated budgets are per invocation, not hourly
and not shared across independent workers.

## Validation and rollback

Offline tests use temporary caches, fake transports and injected clocks. They
prove the exact hourly boundary, concurrent workers, failed attempts, fresh
authenticated reads after a spent public cap, exponential backoff, per-run budget
exhaustion, separate counters and CLI output cleanup. No test sends live traffic.

Revert this change to restore the original clients. No production configuration,
deployment, DNS, email send or paid-service call is part of the change.
