---
version: 2.20.298
type: fix
area: sources
date: 2026-11-05
---
- Texas WARN (sources/warn_custom.py): `_tx_xlsx_links` always tries the current and previous year at TWC's stable workbook URL, so the edge challenge on the HTML page no longer leaves Texas on the dataset frozen since 2026-07-07. Real 2026 workbook fixture added.
- regional_feeds: Jeune Afrique retired (HTTP 403 address block on every VPS run since at least 2026-10-06). Catalogue row moved to refused; sources page and country-coverage.json regenerated.
- Tests: test_tx_warn_workbook.py, test_regional_feeds.py.
