---
version: 2.20.301
type: fix
area: seo
date: 2026-11-09
---
The blog index and its paginated pages (/blog/, /blog/page/2/ and so on) now declare themselves as their canonical URL, with any tracking query string removed. They previously pointed at /blog/blog/, a page that does not exist, which Search Console reported as "Duplicate without user-selected canonical".
