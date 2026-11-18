---
version: 2.20.339
type: fix
area: conversion, finish line
date: 2026-11-18
---
- Conversion: every routed tracker page (methodology, sources, press, editions, reports, state-of-layoffs, publisher tools, US WARN registry, AI quotes, tracker health, country/state/industry pages) now gets the phone sign-up bar, and the standalone corrections and update logs carry the UTM-tagged "Check my resume" line (utm_campaign=public_log). The weekly finish line (run 44386250165) found no visible sign-up route at 390px on 11 pages and none at all on the two logs. Pinned in test_atr_signup_cta.py.
- Finish line check: links with non-ASCII characters (country=Türkiye, Polish and Arabic employer names) are percent-encoded like a browser does, instead of being reported broken with status 0; a 429 from our own host pacing the crawler is retried with a back-off, and a lasting 429 is still reported. Both were false "broken link" results; the pages answer 200. Tests in test_finish_line.py.
- Issue filer: finish_line_issue.py copied from asktherecruiter-sandbox PR #4352 (lists open issues instead of searching, tries the next token on a 422, pages through every issue and fails on an incomplete scan, logs GitHub's own error), with its tests.
