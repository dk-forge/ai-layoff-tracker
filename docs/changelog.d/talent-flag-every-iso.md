---
version: 2.20.300
type: fix
area: digest
date: 2026-11-09
---
- Talent daily (digest-talent-briefing.php): the line flag now comes from the stored ISO2 code via new `alt_digest_iso2_flag()` (digest-regions.php), so every assigned code renders a flag, not only codes whose name is a key of the region table. User-assigned codes and non-codes still get none.
- Tests: test_digest_iso2_flag.py (new), every code in subscribe.php's ISO2 table.
