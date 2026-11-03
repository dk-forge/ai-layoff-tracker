---
version: 2.20.295
type: fix
area: digest
date: 2026-11-03
---
- subscribe.php `alt_digest_compose_articles`: branded Career Insights (ALT_CAREER_INSIGHTS), featured read plus two secondary reads, count caption and house standfirst removed; keyword-soup excerpts fall back to the post's first real sentence (`alt_digest_excerpt_is_keyword_soup`, `alt_digest_first_real_sentence`).
- Cadence: `freq_articles` defaults to weekly for new signups (`alt_digest_articles_freq_from_post`); confirmed readers keep their stored value on resubmission (`alt_digest_keep_articles_freq`). No migration.
- digest_layout.py: articles-only masthead reads "Career Insights from AskTheRecruiter".
- Tests: test_digest_career_insights.py; caption tests retired.
