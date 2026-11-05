---
version: 2.20.298
type: fix
area: ingest
date: 2026-11-05
---
- spend.py: `remaining` now uses OpenRouter `/auth/key` `limit_remaining` when present, falling back to `limit - usage`. The key has a resetting limit (usage $93.60 lifetime, limit $15, limit_remaining $15), so `limit - usage` read -$78.60 and turned paid reads OFF on every ingest run since at least 2026-10-28 (0 posted per night). Tests: monthly-reset key stays ON; limit_remaining 0 still degrades.
