---
version: 2.20.349
type: fix
area: reliability
date: 2026-11-19
---
The layoffs map no longer depends on an outside content network: its drawing library and map outlines are now served from this site at fixed versions. If the map still cannot load, you see the same figures as a table instead of an empty box.
