---
version: vNEXT
type: fix
area: sources
date: 2026-11-11
---
- sources/edgar: `MAX_PAGES_PER_KEYWORD` 3 -> 50 (a ceiling; paging still stops at the EFTS total). Month-sized `edgar-history-sweep.yml` ranges dropped every filing past the 30th per keyword and form.
- Tests: test_edgar_keyword_paging.py (+2).
