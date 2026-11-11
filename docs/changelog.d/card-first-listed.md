---
version: 2.20.308
type: feature
area: cards
date: 2026-11-11
---
- layoffs.js: `cardListed(row)` renders `<time class="alt-card-listed">First listed <date></time>` in the card foot between card-when and card-src, from the API's `created_at` (UTC date). Null, empty or malformed `created_at` renders nothing: no fallback to the source date.
- docs/card-contract.json 1.1.0: optional foot child `card-listed` (byte-identical copy in talent-intelligence-tracker). Digest updated in test_card_contract.py and TECHLOG.
- Tests: test_card_first_listed.py (node), test_card_contract.py.
