# AI Layoff Tracker — orientation for Claude Code

Live tracker of verified layoffs (SEC 8-K filings, US state WARN notices, worldwide
news via GDELT), flagging the ones companies explicitly attribute to AI.

- **Live site:** https://asktherecruiter.com/blog/ai-layoff-tracker/
- **Contact page (corrections):** https://asktherecruiter.com/blog/contact/ → mails info@asktherecruiter.com
- **Public API base:** `https://asktherecruiter.com/blog/wp-json/layoffs/v1/`

## Start here (every session, especially cloud/remote)
Run `python3 railway/ops_status.py` first — read-only, stdlib-only, no keys. It prints the
live version, triages source health (what's broken + what to do), reports the
**live data-integrity verdict**, shows **any workflow that is currently RED with
its actual failing assertion** `[4]`, and lists the 4 surfaces. Exit 0 = healthy and
verified; exit 2 = a human is needed — either a source broke (→ RUNBOOK "a data
source broke"), **a data-integrity check is FAILING** (→ RUNBOOK "a data-integrity
check is failing", and do that one FIRST: a stale source is data we have not
gathered, a failing invariant is a wrong number already published), **or a workflow
is red**. Exit 3 = something could not be checked from this environment, so that
part is **UNKNOWN, not clear** — never treat a run that could not check as a pass.
Section `[4]` needs the `gh` CLI; without it (or without auth) it prints UNKNOWN
and exits 3 rather than implying green.

**Red CI now emails the owner** and does not wait to be noticed:
`.github/workflows/ci-alert.yml` listens for EVERY workflow completing and runs
`railway/ci_alert.py`, which extracts the real failing assertion and POSTs it to
the keyed `/alert`. It is deduped **by cause, not by run** (numbers normalised out
before hashing, open/resolved state held in the endpoint), and it mails
**RECOVERED once** on the next green run. Do not "fix" the quiet on a repeat — the
Spirit assertion reddened CI eight times in one afternoon, and eight identical
emails is how an alert channel gets filtered. **Cloud/remote sessions:** read [docs/CLOUD-SESSION.md](docs/CLOUD-SESSION.md) — it is the fully self-contained operating guide (local memories don't travel to the cloud; that doc carries everything). ops_status.py also prints the **handoff baton** — if another session HOLDS it, do NOT edit ([docs/HANDOFF.md](docs/HANDOFF.md)).

## Read these before changing anything
| Doc | What it holds |
|---|---|
| [docs/HANDOFF.md](docs/HANDOFF.md) | **Gated session baton** — one editor at a time (cloud ↔ local). Claim before editing, release when done; ops_status.py shows the holder |
| [docs/CLOUD-SESSION.md](docs/CLOUD-SESSION.md) | Self-contained operate-from-a-cloud-session guide (rules + owner's working style + what a session can/can't do) |
| [docs/ENVIRONMENT-SETUP.md](docs/ENVIRONMENT-SETUP.md) | Equip a cloud session fully: which hosts to allowlist + a throwaway test DB for proving SQL changes |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System map: components, data flow, endpoints, DB schema, filter semantics |
| [docs/TECHLOG.md](docs/TECHLOG.md) | Chronological log of every change + every incident and its root cause |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Ops playbooks: deploy, caches, imports, "X is broken → do Y", add/tune/enhance a source |

## The 60-second mental model
1. **`wordpress-plugin/ai-layoff-tracker/`** — a WP plugin on Bluehost (install lives at `/blog`).
   Front-end is fully server-side: the browser calls `/query` (table), `/aggregate` (charts+stats),
   `/facets` (dropdowns). Data lives in a custom indexed table `wp_alt_layoffs` (scales to 100K+ rows);
   rich entries also exist as `layoffs` CPT posts for permalink pages.
2. **`railway/`** — Python ingest. Cron 2×/day (EDGAR + NewsAPI + GDELT worldwide) → DeepSeek-V3
   extraction via OpenRouter → POST `/add`. WARN notices skip the LLM: `warn_import.py` scrapes
   states via `warn-scraper` and bulk-upserts via `/bulk` (daily 11AM ET GitHub cron).
3. **`.github/workflows/`** — deploy (FTPS on push to main) + all data jobs (see RUNBOOK).
4. **Self-running loop:** every source (news, WARN, SEC, ERM, + dormant ones — supplemental
   news, distress/bankruptcy, foreign filings) funnels into the SAME `extract_layoff_data`
   → `post_to_wordpress` pipeline, so all guards apply once. `report_source_health(...)`
   feeds a ledger; the weekly **`health_digest.py`** emails info@asktherecruiter.com (via the
   keyed `/alert` endpoint) when a scraper breaks, with a **paste-ready fix instruction**.
   So the human loop is: get email → paste one line here → fix the one scraper. Full
   "add a source / tune it / fix a breakage" guide is in **docs/RUNBOOK.md**.

## Session ritual — the 4 surfaces (CHECK AT START, DURING, AND END of EVERY session)
Any session (Claude **or** ChatGPT) must keep these four live, correct, and
**impeccably formatted** — verify at the **start** (baseline), **during** (after any
data / UI / source change), and **end** (final pass). Never close a session without
the end check.
1. **Live tracker** — https://asktherecruiter.com/blog/ai-layoff-tracker/ — renders, numbers current, **zero visual/mobile overflow** (bar-list names ellipsize, tables scroll inside their own container).
2. **Health page** — https://asktherecruiter.com/blog/ai-layoff-tracker/ai-tracker-health/ — if any source is `degraded`/`stale`, investigate before finishing (see RUNBOOK "a data source broke").
3. **Sources page** — https://asktherecruiter.com/blog/ai-layoff-tracker/sources/ — must list **exactly** the live collectors; update it the SAME session you add/remove/block a source, and add its friendly label to `assets/health.js` `meta{}`.
4. **Private benchmark** — `scratchpad/bm-live.html` (**LOCAL only, never commit** — competitor names stay off the repo). Refresh the vs-competitor read; every comparison table shows **ours + theirs side-by-side**; add a column/row when a new dimension exists.

**Hard bars:** (a) any source/metric change updates Sources + Health labels + the benchmark in the **same** session; (b) formatting is non-negotiable — aligned tables, no horizontal bleed (especially mobile), consistent copy, **no em-dashes in UI copy**; (c) **verify live** (`curl` the `ver=` + the page/endpoint) before claiming any surface is updated — never assume a deploy landed.

## Iron rules learned the hard way (details in TECHLOG)
- Every network request to the WP host MUST send a browser-ish `User-Agent` (ModSecurity blocks `python-requests`; use `AiLayoffTracker/1.0 (+https://asktherecruiter.com)`).
- `WP_SITE_URL` is `https://asktherecruiter.com/blog` — never the bare domain (root is a separate Railway app).
- FTP deploys bypass WP hooks: version bumps trigger cache-flush/table-migration on first request (`alt_flush_caches_on_deploy`), and anything that must exist (like the contact page) needs a **retry-until-verified** hook, not a one-shot on version bump (deploys race mid-upload).
- Never trust freeform extracted values: countries/industries normalize through fixed vocabularies (`alt_normalize_country`/`alt_normalize_industry`); counts parse the FIRST number only. Date bounds differ by path: the LLM path (`extractor.py`) nulls any `layoff_date` before 2015 (news/SEC have no reliable pre-2015 supply anyway); the server WARN/bulk path (`alt_db_valid_date`) accepts back to year 2000, so historical state-WARN + ERM data legitimately populates 2002→2014. Upper bound is today+~3yr (future-dated WARN effective dates), not +18mo.
- WARN entries are EXEMPT from fuzzy/cross-outlet dedup (companies legally file several notices close together).
- Changing an entry's job count changes its dedup hash → corrections need `/bulk-purge` + full re-import, not plain upsert.
- Data-changing jobs must FAIL LOUDLY (non-zero exit on any failed batch; `curl --fail-with-body` in workflows).
- Bump the plugin `Version:` + `ALT_VERSION` on EVERY deploy — it cache-busts assets and triggers the flush.
- **Never write a row directly.** A new source builds a raw dict and calls `extract_layoff_data` → `post_to_wordpress`. The raw dict MUST set `raw_text` (the extractor reads ONLY that and returns None if empty — the bug that made supplemental news silently post zero). Mirror `sources/newsapi.py`. Ship key-gated sources DORMANT with dry-run diagnostics. See RUNBOOK "add a new source".
- **Competitor data stays private** (standalone brand): never put competitor names or numbers in the repo or GitHub logs. Competitor tracking lives ENTIRELY in the local benchmark (`gen.py` reads only our own `agg_*.json`; the competitor figures are maintained by hand in `scratchpad/bm-live.html`). **No secret is involved and none is needed.** The `COMPETITOR_FEED_URLS`/`COMPETITOR_COMPANIES` secrets power a SEPARATE, OPTIONAL automated loop (`tracker-diff`) that is **dormant by the owner's decision (2026-07-28)** — it exits green on its schedule and costs nothing. **Do not ask the owner to add those secrets.**
- **Country filter**: `country_basis=any` (table/exports) unions job-location OR employer-HQ so US-HQ global cuts show under a US filter; headline stats stay strict job-location. Don't "fix" the discrepancy — it's intentional and documented.
- **Source health is not data integrity.** "Did the collector run?" and "is what it produced correct?" are different questions, and for months only the first was on the dashboard. Live invariants live in `railway/data_integrity.py` and are imported by the test, ops_status and the digest — ONE definition. Never let a check resolve to a silent pass: PASS / FAIL / **UNKNOWN** are three distinct states and absence of a signal is not a pass.
- **Retiring a source takes THREE steps**, and skipping the third silently voids the second: (1) drop it from `cron.py`, (2) add it to `alt_retired_sources()` in db.php, (3) **stop every remaining path that posts health under that id**. `alt_retired_sources()` deliberately refuses to mask a row whose last run postdates the retirement, so one forgotten weekly job keeps a retired collector looking live forever. Also: a staleness ceiling must match the job's REAL cadence — a 2-day ceiling on a weekly job is permanent noise that hides real breakage.
- **Don't claim "100% automated."** It's ~99%; the honest sliver is scraper repairs (auto-detected + emailed), private-benchmark refresh, and novel-source judgment.

## Verify a change is actually live
```bash
curl -s "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate?cb=$RANDOM" | python3 -m json.tool | head
curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head -3
```
**Waiting on a deploy?** Match the **commit SHA**, never "the latest run". A
`gh run list -L 1` right after a push returns the run for the PREVIOUS commit
(yours is still queueing), so a wait loop exits instantly and you verify the old
build. Filter on your SHA:

```bash
SHA=$(git rev-parse HEAD); until gh run list --workflow='Deploy WordPress plugin' -L 5 --json headSha,status -q ".[] | select(.headSha==\"$SHA\") | .status" | grep -q completed; do sleep 20; done
```

Also: the page cache can serve the PREVIOUS version's `<head>` to anything that
requests the bare URL (crawlers do). A version bump flushes it since 2.19.138,
but the CDN edge still holds a copy for a few minutes; add a random query string
when you need the origin's truth.

**Egress-blocked cloud session?** If these curls fail with a proxy 403/tunnel CONNECT (some cloud environments deny `asktherecruiter.com` — `ops_status.py` prints `ENVIRONMENT BLOCK` / exit 3, NOT a source outage), the visual check is unavailable but the deploy still works: `git push` → GitHub Actions "Deploy WordPress plugin" FTPS-uploads server-side. Confirm via a green deploy run (`gh run list --workflow="Deploy WordPress plugin"`) — that green run **is** proof it's live. Full detail in [docs/CLOUD-SESSION.md](docs/CLOUD-SESSION.md).
