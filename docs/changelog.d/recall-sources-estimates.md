---
version: vNEXT
type: feat
area: sources
date: 2026-11-05
---
- sources/google_news.py: `WIRE_QUERIES`, two free Google News RSS sweeps on the US edition (Business Wire, PR Newswire and GlobeNewswire via `site:`, plus workforce-reduction phrasing), behind the free title prefilter and inside the existing `MAX_ITEMS` cap. Explicit-query callers are unchanged.
- sources/google_news_prefilter.py: keeps "reduction in force", "workforce reduction" and "reduce its workforce" headlines.
- headcount_estimate.py (new) and extractor.finalize_extraction: a percent-only 8-K becomes a labelled estimate, pct x employees from the filer's latest 10-K (SEC XBRL dei:EntityNumberOfEmployees, else the 10-K human capital sentence), with formula, source and the filing's own sentence. Confidence capped at 60, review_status provisional. No 10-K count means the filing stays refused.
- wp_poster.py: estimate rows title "~N jobs (estimate)" and send `job_count_is_estimate` and `headcount_estimate` meta.
- Tests: test_google_news_wire_queries.py, test_headcount_estimate.py.
