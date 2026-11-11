---
version: 2.20.310
type: fix
area: data
date: 2026-11-11
---
New layoffs published since 10 November now appear in the searchable table and the API again. A database column added in 2.20.306 never reached the live table, so new entries were published as pages but left out of search. The table now checks every column on each update and repairs one that is missing, and a failed save is logged instead of ignored. Entries with no real employer name, such as "Unknown", are now refused.
