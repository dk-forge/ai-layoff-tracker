---
title: Balance related-post titles on blog articles
version: 2.20.361
type: fix
area: accessibility
date: 2026-11-23
files: wordpress-plugin/ai-layoff-tracker/assets/blog-reading.css, wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php, railway/tests/test_blog_related_titles.py
tests: Offline Chromium cascade regression at 390px and 1280px, including theme and non-article controls
rollback: Revert the scoped CSS rule and publish a new plugin patch version
env: No runtime configuration changes
---

Related-post titles use balanced wrapping on individual blog articles. The
override is scoped to the WordPress post-template titles. Theme wrapping on
other page types is retained. Local fixture checks do not verify live pages.
