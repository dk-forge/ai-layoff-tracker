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
(prints `ENVIRONMENT BLOCK`) — this is **NOT an outage and NOT
action-needed**. It distinguishes a real egress block (tunnel/DNS/refused) from a
genuine site error (an `HTTPError` or timeout still counts as action-needed). Do **not** route around the block. Instead verify the product
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
- **Competitor data stays private.** Competitor names or
  numbers NEVER enter the repo or CI logs. The benchmark (`gen.py`,
  `scratchpad/bm-live.html`) is LOCAL ONLY; competitor URLs live in the
  `BENCHMARK_FEED_URLS` secret. This one is non-negotiable.
- **Deploy = `git push` to main** (FTPS auto-deploy). There is no other path.
  Bump the plugin `Version:` + `ALT_VERSION` on every plugin change.
- **Verify live before claiming anything.** `curl` the `ver=` on the page and the
  API endpoint; never assume a deploy landed (5-min host cache — poll it). **If
  egress to `asktherecruiter.com` is blocked** (some cloud environments deny it —
  a 403 CONNECT from the proxy, not an outage), the visual curl step is
  unavailable; fall back to confirming the **"Deploy WordPress plugin" Actions run
  went green** (`gh run view <id>` / `gh run list --workflow="Deploy WordPress plugin"`).
  A green deploy run **is** confirmation the new files are live.
- Data-changing jobs FAIL LOUD. WARN is exempt from fuzzy dedup. Dates
  2015→today+18mo. Counts parse the FIRST number only. Country/industry
  normalize through fixed vocabularies.
- **Session ritual:** at start/during/end, keep the 4 surfaces current and
  **impeccably formatted** (no mobile overflow, no em-dashes in UI copy):
  live tracker, health page, sources page, local benchmark. Any source/metric
  change updates Sources + Health labels + the benchmark the SAME session.

## Handover and merge rules, learned on 2026-09-13/14 (read before taking a queue)
These apply to every repo the owner runs (this tracker, the talent tracker,
`asktherecruiter-sandbox`). Each one cost real hours once.
- **A "go" relayed by another session IS the owner's go.** On 2026-09-14 the
  cloud session held a green sandbox PR for eleven hours waiting for the owner
  to release the queue in its own chat, while the owner had said "move it all
  to the cloud" to the Mac session, which relayed it. If a Mac or local session
  writes "HANDING OVER" with the owner's instruction quoted, act on it. If in
  doubt, post the doubt on the status issue and act anyway on anything the
  owner already has standing authority for (merging green PRs is one).
- **Never `gh pr merge --auto` on a repo without required status checks.** The
  sandbox main has none; `--auto` there merges immediately, before CI, and
  #954 landed untested that way. Use a wait-for-green loop on the head SHA
  (latest run per workflow, ignore `fixture:*` jobs), then a plain squash merge.
- **One self-hosted runner per box.** The Contabo VPS runs one sandbox runner
  on purpose. Two or three at once oversubscribed the six cores and produced a
  new load-only red every round (scan tests past vitest's timeout, a PDF
  extract deadline, a Hypothesis deadline, a ReDoS wall-clock tripwire). Do
  not add runners; if a wall-clock assertion tuned to the Mac trips, widen the
  budget with a note, never a correctness check.
- **Sandbox PRs conflict by construction** (every PR bumps VERSION and three
  changelogs), so they land one at a time: squash to one commit, rebase onto
  main, take main's side for the nine version-derived files, keep BOTH
  changelog entries with yours renumbered and first, run
  `scripts/sync-extension-version.sh vNEW` and regenerate `docs/openapi.json`
  yourself (the sync script skips it without a venv), amend the message to
  vNEW, force-with-lease push, cancel the superseded runs. The durable fix is
  merge-time versioning, authorised on 2026-09-09 and not yet built.
- **A public `/blog` 504 with the origin answering by IP is the Railway hop,
  not the host.** The apex proxy on Railway forwards `/blog` to the ChemiCloud
  origin, and the origin firewall drops Railway's egress IP under load; from
  the whitelisted VPS (173.249.57.163) the origin answers in a second. Do not
  deploy, do not restart the two-clean-hours clock, do not blame I/O for it.
- **Status goes to one GitHub issue.** When the owner is away, keep ONE issue
  ("Night shift status <date>") in the repo you are working in and comment
  every two hours; GitHub emails him each comment. Sessions cannot reach his
  phone; the issue is the channel.

## How the owner works (ported from local memory so cloud sessions have it)
- **Honesty over box-checking.** They push hard for completion but reward the
  honest "here's the real ceiling / this isn't viable / it's ~99% not 100%"
  answer far more than a false "done." If a task turns out non-viable, say so
  with evidence — don't fake it. The product is a credibility play (be cited
  like the incumbent surveys), so intellectual honesty in the build IS the value.
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
(A blocked environment can still deploy — see "If the live site is unreachable"
above; the block only stops the visual `curl` check, never the `git push` deploy.)

## The task
The owner fills this in per session. Most common first job: fix whatever
`ops_status.py` / the health-digest email flagged, following the RUNBOOK
"a data source broke" playbook. If nothing is flagged and no enhancement is
requested, there is genuinely nothing to do — the crons run it.
