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
The digest index and dated editions now place a tracked free match check near
the top. Each page identifies its campaign and includes standalone styling
for the link. The existing email sign-up line remains at the bottom.
