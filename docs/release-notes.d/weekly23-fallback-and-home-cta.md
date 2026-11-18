---
version: 2.20.336
type: fix
area: extraction, conversion
date: 2026-11-18
---
- Extraction (WEEKLY-23, AI-LAYOFF-TRACKER-5): when the primary model ends in upstream 429s or its rate-limit breaker is open, full extraction makes ONE metered call to a second model (`OPENROUTER_FALLBACK_MODEL`, default google/gemini-2.5-flash, the alternative measured 30/30 on the extraction gold set; empty turns it off) instead of dropping the candidate. Other errors never fall back. Tests in railway/tests/test_metered_call_rate_limit.py and test_extraction_model_choice.py.
- Conversion: the main tracker page now carries the UTM-tagged "Check my resume" line under the hero (utm_campaign=tracker_home) and the phone sticky bar, so the flagship page has a tracked sign-up path on phone and desktop (CLAUDE.md conversion rule). Pinned in test_atr_signup_cta.py.
