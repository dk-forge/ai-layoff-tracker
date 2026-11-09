---
version: 2.20.303
type: fix
area: seo
date: 2026-11-09
---
- includes/digest-public-archive.php: the digest routes (including `^layoff-digest-sitemap\.xml$`) now register on `init` priority 1, not 2. Rank Math's catch-all `*-sitemap.xml` rule is added on init:1 and 'top' rules match in insertion order, so the digest sitemap was shadowed and 404'd while sitemap_index.xml listed it.
- Test: railway/tests/test_sitemap_route_priority.py asserts every self-served sitemap rule registers on init priority 1.
