---
version: vNEXT
type: fix
area: sources
date: 2026-11-11
---
- News catch-up (railway/news_catchup.py) now also reads each day of its lookback through dated Google News RSS (`after:`/`before:`, US edition, free title prefilter, 40 items per day). The 2026-11-05 benchmark's no-row misses were all announced inside the 2026-09-29 to 2026-11-05 ingest gap, which NewsAPI's relevance-capped catch-up could not read back. `window_start`/`window_end` inputs on `news-catchup.yml` replay a past gap.
- Tests: test_google_news_dated_window.py (+7); test_news_catchup_health.py keeps the run offline.
