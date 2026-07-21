# Operating this repo from a cloud / remote session

A cloud Claude (or ChatGPT) session has the repo but **not** the owner's local
memories, so everything it needs is here and in the repo. The tracker itself
runs 24/7 on GitHub Actions crons — a session is for **development and repair**,
not for "running" it.

## Start every session with ONE command
```
python3 railway/ops_status.py
```
Read-only, no deps, no keys. It prints the live version, triages source health
(what's degraded/stale and what to DO), and lists the four surfaces. Exit 0 =
healthy, nothing to do. Exit 2 = a source needs a human → go to the RUNBOOK
"a data source broke (START HERE)" playbook.

Then read `CLAUDE.md` (mental model + iron rules) and `docs/RUNBOOK.md` (fix /
add / tune / enhance any source). `docs/ARCHITECTURE.md` = system map;
`docs/TECHLOG.md` = change history.

### If the live site is unreachable (egress-blocked cloud environments)
Some cloud/sandbox environments block outbound traffic to `asktherecruiter.com`
(a `403` on the proxy CONNECT). `ops_status.py` detects this and exits **3**
("CANNOT REACH … network egress policy") — this is **NOT an outage and NOT
action-needed**. Do **not** route around the block. Instead verify the product
via **GitHub Actions**, which is reachable: `gh run list --limit 15`. If today's
`Deploy WordPress plugin`, `WARN notice import`, `ERM import`, `Supplemental
news`, and the other crons are green, the pipeline is healthy — a `cancelled`
run is a concurrency-supersede, not a failure. The "verify live" half of the
ritual simply can't run from a blocked environment; report that plainly. Ask the
owner to allowlist `asktherecruiter.com` if cloud sessions should verify the live
surfaces directly.

**IMPORTANT — you CAN still update the live site while egress-blocked.** Deploying
does not require reaching `asktherecruiter.com`: `git push` to main triggers the
"Deploy WordPress plugin" GitHub Actions workflow, which FTPS-uploads to the host
**server-side**. You only need GitHub (reachable). So edit the plugin, bump
`Version:` + `ALT_VERSION`, push, then confirm the deploy landed with
`gh run view <deploy-run-id> --log` (a green "Deploy WordPress plugin" run = the
new files are live). The only thing the block prevents is the final visual
`curl ver=` check — the green deploy run is reliable confirmation in its place.

## Standing rules (self-contained — these do NOT rely on local memory)
- **Never write a DB row directly.** A source builds a raw dict (MUST set
  `raw_text` — the extractor reads only that and drops the row if empty) and
  calls `extract_layoff_data` → `post_to_wordpress`. Mirror `sources/newsapi.py`.
  Ship key-gated sources DORMANT with dry-run diagnostics.
- **Competitor data stays private.** Challenger / layoffs.fyi / TrueUp names or
  numbers NEVER enter the repo or CI logs. The benchmark (`gen.py`,
  `scratchpad/bm-live.html`) is LOCAL ONLY; competitor URLs live in the
  `COMPETITOR_FEED_URLS` secret. This one is non-negotiable.
- **Deploy = `git push` to main** (FTPS auto-deploy). There is no other path.
  Bump the plugin `Version:` + `ALT_VERSION` on every plugin change.
- **Verify live before claiming anything.** `curl` the `ver=` on the page and the
  API endpoint; never assume a deploy landed (5-min host cache — poll it).
- Data-changing jobs FAIL LOUD. WARN is exempt from fuzzy dedup. Dates
  2015→today+18mo. Counts parse the FIRST number only. Country/industry
  normalize through fixed vocabularies.
- **Session ritual:** at start/during/end, keep the 4 surfaces current and
  **impeccably formatted** (no mobile overflow, no em-dashes in UI copy):
  live tracker, health page, sources page, local benchmark. Any source/metric
  change updates Sources + Health labels + the benchmark the SAME session.

## How the owner works (ported from local memory so cloud sessions have it)
- **Honesty over box-checking.** They push hard for completion but reward the
  honest "here's the real ceiling / this isn't viable / it's ~99% not 100%"
  answer far more than a false "done." If a task turns out non-viable, say so
  with evidence — don't fake it. The product is a credibility play (be cited
  like Challenger), so intellectual honesty in the build IS the value.
- **Name the manual sliver.** ~99% autonomous; the irreducible human part is
  repairing a scraper when a site redesigns (auto-detected + emailed), the
  private-benchmark refresh, and novel-source judgment. Never claim 100%.
- **Verify live, be thorough, fix audit findings immediately.**

## What a cloud session CAN and CANNOT do
CAN: read/edit/push code (push = deploy), dispatch workflows via `gh` (dry-run
first), curl to verify, run `ops_status.py` / `recall_precision.py` (read-only).
CANNOT: type any password/credential (FTP/API keys stay in GitHub secrets — if a
task needs one, ask the owner to add it); post competitor data publicly; deploy
except via git push. For a live, credibility-critical product, prefer bounded,
well-scoped changes and dry-run before pushing — commits are the review trail.

## The task
The owner fills this in per session. Most common first job: fix whatever
`ops_status.py` / the health-digest email flagged, following the RUNBOOK
"a data source broke" playbook. If nothing is flagged and no enhancement is
requested, there is genuinely nothing to do — the crons run it.
