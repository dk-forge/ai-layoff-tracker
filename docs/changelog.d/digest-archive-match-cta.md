---
title: Digest archive pages carry a tracked free match check line
date: 2026-11-24
version: 2.20.365
type: fix
area: growth
files: wordpress-plugin/ai-layoff-tracker/includes/digest-public-archive.php, railway/tests/test_digest_public_archive.py, wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, wordpress-plugin/ai-layoff-tracker/data/update-log.json
tests: PHP CTA harness, campaign and copy guards, optional-helper fallback, source ordering and standalone styles; tests not run locally, CI runs them
rollback: Revert this PR.
env: none
---
Add a guarded CTA helper for the standalone digest pages, with separate hub
and edition campaigns, an underlined link and a minimum 24px link height.
New tests cover the shared helper output, fallback, placement, styling and
copy. Existing email sign-up, archive filters and indexing behavior remain.
