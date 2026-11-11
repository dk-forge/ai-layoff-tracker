---
version: 2.20.315
type: fix
area: email
date: 2026-11-11
---
- subscribe.php: alt_digest_fit_preheader trims a trailing full stop from the lead before adding its own (talent daily 2026-11-11 preheader ended "Bordeaux)..").
- Tests: test_preheader_one_full_stop.py (new, runs the real PHP).
