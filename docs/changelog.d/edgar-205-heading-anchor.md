---
version: 2.20.299
type: fix
area: ingest
date: 2026-11-05
---
- sources/edgar.py: the 8-K reading window now anchors on the Item 2.05 heading ("Item 2.05 Costs Associated with Exit ...") instead of the first "item 2.05" match, which in HubSpot's 2026-10-06 8-K was a forward reference inside Item 2.02, ~1,200 characters early. A longer preamble would have pushed the headcount out of the 3,000-character window. Test: railway/tests/test_edgar_item_205_anchor.py.
