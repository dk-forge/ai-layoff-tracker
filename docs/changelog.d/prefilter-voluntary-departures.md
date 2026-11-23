---
version: vNEXT
type: fix
area: sources
date: 2026-11-23
---
- sources/google_news_prefilter.py: the free headline prefilter now also keeps "cutting 1,000 others" and "voluntary departures / redundancies / exits / buyouts" headlines, which named no workforce noun (Renault, 2026-11-17). Tests in test_google_news_prefilter.py.
