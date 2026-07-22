# Session handoff baton

Gated coordination so **cloud and local sessions never collide** on this repo
(we hit real git conflicts + version-bump races running two at once). Exactly
**one session holds the baton at a time**. `ops_status.py` prints the current
holder, so the start-of-session ritual surfaces it automatically.

## Baton
- **STATUS:** FREE
- **HOLDER:** —
- **SINCE:** 2026-07-21
- **WORKING ON:** —

## Protocol (every session follows this)
1. **Read this file first** (ops_status.py shows it). If **STATUS = HELD** by
   another session, do NOT edit — wait or coordinate with the owner. If **FREE**,
   claim it: set STATUS = HELD, HOLDER = `<cloud|local>`, SINCE = `<date>`,
   WORKING ON = `<one line>`, then `git commit` + `git push`. **If the push is
   REJECTED**, another session claimed first — `git pull --rebase`, re-read the
   baton, and back off.
2. **Work.** Commit + push as you go (`git pull --rebase` on any rejection).
   Bump the plugin `Version:` + `ALT_VERSION` only if you changed plugin files.
3. **Release when done:** set STATUS = FREE, clear HOLDER, add a dated line to
   the LOG below (what you did + what's next for the other session), commit + push.
4. **Emergencies / stale baton:** if a baton has been HELD > 24h with no commits
   from that holder, it's stale — the owner may tell you to take it; note the
   takeover in the log.

The push itself is the real gate: git rejects the second concurrent push, so
whoever lands the "claim" commit first wins and the other must rebase and see
the baton is taken.

## Handoff log (newest first — what each session did + what's next)
- 2026-07-21 local: self-growing watchlist — new public /companies endpoint (distinct captured names, cached) + company_watchlist self-grows from it (WATCHLIST_SELF_GROW). Monitored universe now compounds with every capture. **Next:** point WATCHLIST_INDEX_URLS at S&P500/Russell CSVs; build GLEIF/SEC alias feed.
- 2026-07-21 local (Claude Code): added prominent public 'Why our number is lower' journalist callout on the tracker page (competitor-free). **Next:** point COMPETITOR_FEED_URLS at the layoffs.fyi export to auto-run the gap-chase.
- 2026-07-21 local (Claude Code): removed the dead public competitor-benchmark block from health.js (FYI/Challenger/history numbers were in the served JS source, never rendered — no PHP container). Benchmark stays private (bm-live.html). **Next:** CA WARN backfill once egress allowlisted.
- 2026-07-21 local (Claude Code): built the handoff baton + env-equip kit
  (`docs/ENVIRONMENT-SETUP.md`, `scripts/setup_test_db.sh`,
  `railway/gen_synthetic_snapshot.py`) + wired the baton into `ops_status.py`.
  **Next:** a cloud session with egress + the test DB can do the CA WARN
  backfill, self-host the chart libs, and the `/aggregate` query-fold perf work.
