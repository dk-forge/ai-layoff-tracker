---
version: vNEXT
type: fix
area: ops
date: 2026-11-05
---
- railway/ingest_yield.py: the "Paid reads OFF" alert no longer says SEC rows keep running. SEC/EDGAR 8-K rows need a paid model read (as corrected in spend.py by #600); the model-free sources are WARN, ERM and the state scrapers. Test: `TheAlertText.test_the_free_sources_named_are_the_model_free_ones`.
