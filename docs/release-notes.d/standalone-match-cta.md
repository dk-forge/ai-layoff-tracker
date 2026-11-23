---
title: Standalone tracker page keeps a tracked free-match CTA
date: 2026-11-23
type: fix
area: growth
files: templates/page-widget.php, assets/widget.css, docs/TRACKER_LAUNCH_FIXES.md
tests: Rendered PHP regression, existing tracker launch regression tests, phone and desktop checks
rollback: Revert this change.
env: none
---
The standalone state widget now keeps a named, UTM-tagged link to the free
match check on phone and desktop. Existing source attribution and figures
are retained. The launch review records the already merged code fixes and
separates the remaining operator settings from code. No deployment occurs.

The publisher-generated iframe now reserves 280px so its CTA stays fully
visible without inner scrolling. The actual builder output is measured at
320px, 390px and desktop width.
