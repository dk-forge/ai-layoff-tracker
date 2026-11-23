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

The migration audit identifies the WordPress data and features still needed
for an exact static replacement. An offline compiler and coverage guards are
ready for a reviewed public snapshot. Synthetic tests prove the compiler
contract only; they do not prove coverage of the live sitemap. Live serving,
newsletter delivery and the WordPress host are unchanged.

A build-only preview now reads checksum-pinned public GitHub backups and emits
reviewed source rows under recorded company slugs. Every preview page is
non-indexable and has a tracked match CTA. PR and backup-completion builds
upload dist as a review artifact. This is a preview subset, not production
sitemap or SEO parity, and does not replace the WordPress data publisher.
