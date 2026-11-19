Self-hosted, pinned copies of the map's dependencies (todo#1881 item 7).
They were loaded from cdn.jsdelivr.net with floating majors (`world-atlas@2`,
`us-atlas@3`), so an ad-blocker, a corporate proxy, a region that blocks the CDN
or a CDN blip blanked the map or showed "Map data could not be loaded".

| File | Package | Licence | sha256 |
|---|---|---|---|
| d3.min.js | d3@7.9.0 | ISC | f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539 |
| topojson-client.min.js | topojson-client@3.1.0 | ISC | 25cd02ae486cc5063e0215a4e4cfb15de83700c87ac48bac4d57dc6aaf3ebb89 |
| countries-50m.json | world-atlas@2.0.2 (Natural Earth, public domain) | ISC | 04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394 |
| states-10m.json | us-atlas@3.0.1 (US Census Bureau, public domain) | ISC | d76b391ccfa8bff601d51e3e3da5d43a89fa46cd5caca72ce731b383be5596d0 |

Upgrade by replacing a file, updating this table and the pin test
(railway/tests/test_map_selfhost.py).
