---
title: Static tracker migration audit and offline snapshot contract
date: 2026-11-22
type: feat
area: static-site
files: railway/static_site.py, railway/static_site_assets, .github/workflows/static-site.yml, docs/STATIC_MIGRATION.md, docs/STATIC_SNAPSHOT.md
tests: Seven offline builder tests, workflow and test-group contracts, synthetic browser checks at 390px and 1280px
rollback: Revert this build-only change; the deployed WordPress site is unchanged
env: none
---

Adds the public-route and data-dependency audit and a strict offline snapshot
compiler. Missing sitemap pages, metadata, assets or unmigrated active content
block output. Production parity is not established: the real public-page/SEO
snapshot, independent publisher and remaining interactive features are missing.
The Actions job builds review artifacts only. There is no deployment or DNS change.
