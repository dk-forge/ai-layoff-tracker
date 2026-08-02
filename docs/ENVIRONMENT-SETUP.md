# Equipping a cloud session to go the full distance

A default cloud/sandbox session is **egress-blocked** and has **no test DB**, so
it can't verify live, fetch external data, or safely rewrite number-computing
SQL. Neither wall affects the live product (the GitHub Actions crons have full
access and run everything) — they only limit hands-on dev in a session. Knock
both down and a cloud session can do essentially all remaining engineering.

## Wall 1 — network egress (allowlist these hosts)
Set in the Claude Code web environment config (code.claude.com → your
environment → network policy). **Scope to these specific hosts — do NOT open
egress fully.**

| Host | Why |
|---|---|
| `asktherecruiter.com` | Verify live (curl `ver=`, the API, the 4 surfaces); the "verify live" ritual |
| `api.github.com`, `github.com` | Already reachable; `gh` CLI + push (deploy) |
| `edd.ca.gov` | CA WARN annual-PDF backfill source |
| `cdnjs.cloudflare.com`, `cdn.jsdelivr.net` | Self-host the chart/table JS libs (DataTables, Chart.js) instead of CDN |
| `newsdata.io`, `api.marketaux.com`, `finnhub.io` | Dry-run the supplemental news providers |
| `openrouter.ai` | DeepSeek extraction (only if running ingest from the session, not just the cron) |

Leave everything else blocked. `ops_status.py` detects a still-blocked host and
exits 3 with guidance (not a false outage).

## Wall 2 — a throwaway test database
For any change that rewrites `/aggregate` / `/query` SQL (e.g. folding ~20
per-request queries into 2), a session must PROVE the numbers are byte-identical
before shipping — which needs a DB to diff against. Provision one in the session:

```bash
bash scripts/setup_test_db.sh          # provisions MySQL + schema + synthetic rows
python3 railway/gen_synthetic_snapshot.py --rows 20000   # (re)load synthetic data
```

The snapshot is **synthetic** (generated fake companies/counts/dates) — never a
copy of production, so no real data or PII leaves anywhere. Test flow: run the
old aggregate SQL and the new one against this DB and assert every total matches
before you ship. See `scripts/setup_test_db.sh` header for the exact diff harness.

## The sliver that stays human even fully equipped (by design)
- **Secrets/credentials** — a session never reads or sets API keys /
  `BENCHMARK_FEED_URLS` / `BENCHMARK_COMPANIES`. Security boundary, not a gap.
- **Editorial + novel-source judgment + the competitor-data-stays-local rule** —
  the credibility calls. This is the ~1% the docs already name; keep it human.

## Session coordination
Two sessions on one repo collide. Follow `docs/HANDOFF.md` — one baton, one
editor at a time. `ops_status.py` prints who holds it.
