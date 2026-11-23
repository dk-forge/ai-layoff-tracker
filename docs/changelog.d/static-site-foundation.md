---
title: Static tracker migration audit and offline snapshot contract
date: 2026-11-22
type: feat
area: static-site
files: railway/static_site.py, railway/static_site_assets, .github/workflows/static-site.yml, docs/STATIC_MIGRATION.md, docs/STATIC_SNAPSHOT.md
tests: Offline builder and preview tests, workflow and test-group contracts, browser checks at 390px and 1280px
rollback: Revert this build-only change; the deployed WordPress site is unchanged
env: none
---

Adds the public-route and data-dependency audit and a strict offline snapshot
compiler. Missing sitemap pages, metadata, assets or unmigrated active content
block output. Production parity is not established: the real public-page/SEO
snapshot, independent publisher and remaining interactive features are missing.
The Actions job builds review artifacts only. There is no deployment or DNS change.

A build-only preview now reads checksum-pinned public GitHub backups and emits
reviewed source rows under recorded company slugs. Every preview page is
non-indexable and has a tracked match CTA. PR and backup-completion builds
upload dist as a review artifact. This is a preview subset, not production
sitemap or SEO parity, and does not replace the WordPress data publisher.

Recorded percent-encoded WordPress company slugs now retain their public URLs
without double encoding. Preview paths use the shared safety validator and reject
encoded separators, controls, traversal and duplicate decoded destinations.
