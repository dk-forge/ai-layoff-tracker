---
version: 2.20.357
type: fix
area: data-integrity
date: 2026-11-19
---
Four countries that recently appeared in the data (Bahamas, Bolivia, Malawi, Samoa) are now acknowledged in the per-country coverage register as dated outstanding work (no disclosure regime asserted until the law is read), which turns the live data-integrity check green again. Seven countries that were showing under "Other" in the digest's region grouping (Afghanistan, Bahamas, Jamaica, Malawi, Mauritius, Palestine, Samoa) now sit in their world region. A new unit test fails in CI whenever a country in the data is missing from the register or the region table, so the next new country is caught before the live check.
