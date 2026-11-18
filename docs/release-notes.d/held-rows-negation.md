---
version: 2.20.342
type: fix
area: data-integrity
date: 2026-11-18
---
- Held rows: a row a guard cannot decide is stored as an unpublished (pending) post with a held_reason. It never reaches the table, totals, feeds, sitemaps or the seen-URL check. Keyed GET /held lists the queue; POST /held/{id} releases (publishes, after re-running the duplicate checks) or trashes (and suppresses the hash).
- review-held.yml (daily, railway/review_held.py) puts each held row to the two referees; agreement releases or trashes, anything else stays held and turns the run red.
- Negation guard (railway/negation_guard.py): any denial or negation cue in the count's own sentence holds the row ("not related to 60,000 job cuts", "denies cutting 500 jobs", "confirmed no layoffs"). It never drops or publishes on its own. Follow-up to row 183489 (Microsoft 60,000), trashed on 2026-11-18.
- Tracker board footnote: when the headline (whole calendar year) and the YTD column (to today) differ, it states the gap, computed from the headline's verified total minus the board's own YTD cell, both by filing date.
