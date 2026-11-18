---
version: 2.20.341
type: fix
area: api
date: 2026-11-18
---
Clicking filters quickly no longer makes the tracker's data requests fail. Rapid clicks are now combined into one request with your final filters, a request that a newer click replaces is cancelled, and the server computes each uncached view only once at a time, with a short "busy, retry" reply (retried automatically) instead of an error when it is overloaded.
