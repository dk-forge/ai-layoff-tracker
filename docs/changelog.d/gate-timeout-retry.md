---
version: vNEXT
type: fix
area: ingestion
date: 2026-11-11
---
A slow or unreachable AI provider no longer raises a false alarm during the nightly run. The first-look layoff check retries up to three times, then keeps the item for full review and logs a warning, so no layoff is dropped.
