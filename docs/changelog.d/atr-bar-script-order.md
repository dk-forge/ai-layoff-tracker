---
version: 2.20.333
type: fix
area: growth
date: 2026-11-17
---
- Phone sign-up bar (2.20.332) never appeared: its markup printed at wp_footer 20, after WordPress printed atr-bar.js, so the script found no bar. Markup now at priority 5 and the script waits for DOMContentLoaded. Test: test_atr_signup_cta.py.
