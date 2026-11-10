---
version: 2.20.306
type: feat
area: transparency
date: 2026-11-10
---
The corrections log and an update log now have their own pages, at /ai-layoff-tracker/corrections/ and /ai-layoff-tracker/update-log/, so a correction or a change can be cited by URL. Every row from the /query API now carries created_at, the time the tracker first listed it, for rows read from the main table as well as entry pages. Rows listed before this release show it when their entry page records it and null otherwise.
