---
version: 2.20.356
type: fix
area: data integrity, dedup
date: 2026-11-19
---
- Dedup (dk-forge/todo#2791): `alt_reconcile_supersets` gains pass (2b), news-vs-news across company keys. One event filed under two employer names ("KLM" / "Air France-KLM", 5,000 each on 2026-11-05) is now counted once before publish: exact same count (>= 100), layoff dates within 2 days (the live invariant's window), and a conservative name rule mirrored from `entity_resolution.same_entity` (one key contained in the other with a distinctive token, or an initialism). WARN stays exempt. Primary: AI-flagged, else earliest date, else lowest id. The five live pairs (11,050 excess jobs) were corrected through `adjudicate-row.yml`; over the top 1,000 rows of the last year the pass also marks two smaller pairs (Robinhood 290, Komatsu 265) and nothing else. Tests in railway/tests/test_cross_alias_dedupe.py, including parity of the weak-token list and window with the Python side.
