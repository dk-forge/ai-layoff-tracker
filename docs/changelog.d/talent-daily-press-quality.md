---
version: 2.20.313
type: fix
area: email
date: 2026-11-11
---
- digest-talent-briefing.php: neutral marker for lines with no country, no "leading" region when unrecorded signals outnumber it, uncounted announced plans folded into one line, employer-activity count said once.
- postal-address.json + postal-address.php + railway/postal_address.py: one postal-address config read by every email (account-mail, press-list, subscribe, subscriber-prefs, digest layout, email theme).
- Tests: test_digest_talent_press_quality.py, test_postal_address.py, test_email_theme.py extended.
