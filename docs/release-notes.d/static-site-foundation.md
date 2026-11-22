---
title: Static tracker migration audit and offline snapshot contract
date: 2026-11-22
type: feat
area: static-site
files: railway/static_site.py, railway/static_site_assets, .github/workflows/static-site.yml, docs/STATIC_MIGRATION.md, docs/STATIC_SNAPSHOT.md
tests: Nine offline builder tests, workflow and test-group contracts, synthetic browser checks at 390px and 1280px
rollback: Revert this build-only change; the deployed WordPress site is unchanged
env: none
---

The migration audit identifies the WordPress data and features still needed
for an exact static replacement. An offline compiler and coverage guards are
ready for a reviewed public snapshot. Synthetic tests prove the compiler
contract only; they do not prove coverage of the live sitemap. Live serving,
newsletter delivery and the WordPress host are unchanged.
