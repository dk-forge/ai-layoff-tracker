---
version: 2.20.345
type: fix
area: frontend
date: 2026-11-19
---
The site menu's script loads again on company, country, state, industry and digest pages, where it used to fail with a console error. The date button that read "Last quarter" now reads "Last 90 days", which is the window it has always shown. The header's sign-up link on tracker pages now carries the tracker's own tag, and a brief database error while filtering quickly is retried instead of shown.
