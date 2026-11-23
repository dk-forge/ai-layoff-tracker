# Tracker bot read budget

Every AiLayoffTracker/1.0 GET or HEAD to asktherecruiter.com/blog, including
keyed API reads, spends the same one-hour per-URL disk budget. An atomic pending
marker and a process lock prevent concurrent reads and repeat attempts after a
failure. Cache-busting and credential query parameters cannot mint a new budget.
Real filters and page numbers still identify different URLs.

Anonymous public page responses are cached. API, authenticated and token-bearing
responses are never persisted or replayed: another read in the hour is explicitly
limited. This can defer overlapping ingestion jobs. It does not give ingestion an
old batch to process again. Keyed reads keep a fresh edge-cache query parameter
for the first permitted request; that parameter does not evade the hourly cap.

The cache stores hashes, timing and response state. Private bodies, raw URLs and
credentials are not written. Public responses drop Set-Cookie. Buffered clients
check redirects hop by hop. Streaming and pinned probes retain their original
transport and read cap, and repeated probes fail instead of getting fake content.
Requests and urllib clients keep separate representation variants in one URL
budget. No stale response is substituted after a transport failure.

## Coverage

The common retry/host-call helpers, direct host-capable Python clients, public
page checks and explicit workflow GETs use the budget. The workflow CLI reads keys
from the named environment variable, never command-line values. It removes an old
output before reading and exits 75 on a spent budget. Quarterly snapshot creation
stops on a limited read instead of mistaking it for a missing report. POST, PUT,
PATCH and DELETE behavior is unchanged. External sources and browser-user-agent
probes are outside the AiLayoffTracker bot policy.

## Worker coordination

The default directory is ~/.cache/alt-public-pages. ALT_BLOG_CACHE_DIR can point
to an existing private persistent directory. Workers sharing it share the cap;
independent filesystems do not. A single worker or shared persistent cache is
required for a global cap across machines. This PR does not configure or deploy
that storage. The manual static-parity workflow is a separate PR and must share
this budget before both checks are operated on the same worker.

## Validation and rollback

The new tests use temporary caches, fake transports and an injected clock,
including the exact hourly boundary, concurrent workers, failed attempts,
authenticated batch refusal and workflow output cleanup. A runtime netblock test
proves the cache contracts send no live traffic. Existing reporting tests retain
their assertions while injecting the new transport boundary.

Revert this change to restore the original clients. No production configuration,
deployment, DNS, email send or paid-service call is part of the change.
