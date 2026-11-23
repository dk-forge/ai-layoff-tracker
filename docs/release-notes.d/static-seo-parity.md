---
title: Check static tracker URL and SEO parity
date: 2026-11-23
type: test
area: static-site
files: railway/static_parity.py, railway/static_parity_html.py, .github/workflows/static-parity.yml, docs/STATIC_PARITY.md
tests: Offline parity, cache and workflow contracts; full repository CI
rollback: Revert the checker and build-only comparison workflow.
env: none
---
A report now compares every discovered ALT sitemap URL with its static HTML,
including concrete 301 mappings, SEO fields and the tracked free-match CTA.
Missing, different, unreachable and unvisited pages fail the gate. A manual
read-only CI job keeps the report on failure and reuses cached live reads.
No deployment, DNS change or production parity claim is made by this change.
