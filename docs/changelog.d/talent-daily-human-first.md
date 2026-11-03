---
version: 2.20.294
type: fix
area: digest
date: 2026-11-03
---
- Talent daily (digest-talent-briefing.php): new `alt_talent_render_daily`; subject metric "Who's hiring: <employer> <plan> + N more"; announced plans and open listings ranked only within their own type (`alt_talent_hiring_by_type`); top 5 lines then one "See all N hiring signals" link; region table replaced by one line and a link, detail under Notes; window label "Latest hiring signals (<dates>)".
- Footer (subscribe.php `alt_digest_footer_blocks`, digest_layout.py `FOOTER_BLOCKS`, `tracking_sentences`): shorter wording, forward-this line dropped, resume promo one line.
- Tests: test_digest_talent_daily_human_first.py; footer tests updated to the new wording.
