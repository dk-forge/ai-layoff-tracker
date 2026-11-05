---
version: 2.20.298
type: fix
area: ops
date: 2026-11-05
---
- New `railway/ingest_yield.py`, run by a new `yield` job in `ingest-silence.yml`: mails the owner once per incident (ops_notify dedupe_key) when paid reads are OFF because the OpenRouter key is at its limit, or when railway-cron posted 0 events on 2+ consecutive nights with more than 100 candidates pulled. Mail names the key by its public tail only, and a RECOVERED notice follows on clear.
- `ingest-silence.yml`: permissions moved per job (`check` keeps issues: write, `yield` gets contents: write for the alert ledger claim).
- Tests: test_ingest_yield.py; test_ops_sender.py maps ingest_yield.py to ingest-silence.yml.
