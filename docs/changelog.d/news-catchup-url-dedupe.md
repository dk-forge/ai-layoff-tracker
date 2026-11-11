---
version: vNEXT
type: fix
area: sources
date: 2026-11-11
---
- news_catchup: `unique_candidates()` keeps one entry per source_url across NewsAPI and the dated Google News windows, then the shared `seen_urls.filter_already_seen` pre-check drops URLs the site already holds, before any extraction spend. Found on run 42993859950, which paid for one URL three times and hit its $0.150 ceiling before the late-October days.
- Tests: test_news_catchup_dedupe.py (+4).
