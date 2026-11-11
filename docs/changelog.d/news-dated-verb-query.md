---
version: vNEXT
type: fix
area: sources
date: 2026-11-11
---
- google_news: third dated query base `DATED_VERB_QUERY` ("jobs (cut OR cuts OR cutting OR axe OR slash OR slashes OR eliminate)"); `pull_google_news_day` caps each query at `WINDOW_DAY_MAX` instead of the whole day, so the first base no longer stops the later ones. Found on the 2026-11-08 benchmark misses Fiserv, NatWest, Flutter, GSK and the Dutch government, all present in Google News for their day but never returned by the two noun-form bases.
- Tests: test_google_news_dated_window.py (+2, 1 restated for the per-query cap).
