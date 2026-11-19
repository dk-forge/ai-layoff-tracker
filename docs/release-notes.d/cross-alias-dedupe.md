---
version: 2.20.356
type: fix
area: data accuracy
date: 2026-11-19
---
A layoff reported under two names for the same employer (for example "KLM" and "Air France-KLM", 5,000 jobs each on the same day) is now counted once. Five such events had added 11,050 jobs to the total; they have been corrected and the check now runs before every update.
