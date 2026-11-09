---
version: 2.20.299
type: feat
area: digest
date: 2026-11-09
---
- Talent daily (digest-talent-briefing.php): glance box at the top (hiring signals, employer-activity signals, biggest announced plan, leading region) with the window in its heading; the separate dateline is gone.
- The three signal types are defined one line each under the box, and the "reported signals, most not independently verified" caveat moved next to it from Notes.
- Compact list shows up to 10 hiring signals (was 5) and says "N featured, see all M" when some are left out.
- Context line now reads "Separately, M employer-activity signals from E employers." (non-hiring signals and their distinct employers).
- Subject format and the consent footer are unchanged.
- Tests: test_digest_talent_daily_glance.py (new); human_first and lead_links_period updated to the 2026-11-06 owner spec.
