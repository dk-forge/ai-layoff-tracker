---
version: 2.20.306
type: feat
area: api, transparency
date: 2026-11-10
---
New public pages /ai-layoff-tracker/corrections/ and /ai-layoff-tracker/update-log/ (plus /layoff-logs-sitemap.xml). `/query` rows now carry `created_at` (first listed, ISO 8601 UTC): a new nullable `wp_alt_layoffs.created_at` column stamped once on insert, falling back to the backing post's GMT date, else null. The 2.20.304 note said every API row carried `created_at`; only the entry-page path did.
