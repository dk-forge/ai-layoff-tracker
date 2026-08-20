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
gathered, a failing invariant is a wrong number already published), **a workflow
is red, or a job has DEFERRED three times running** (`[4d]` — a call the host
never answered exits 0 and is counted, but three in a row is not an outage; →
RUNBOOK "a job is DEFERRING"). Exit 3 = something could not be checked from this environment, so that
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
emails is how an alert channel gets filtered.

**A LIVE-DATA failure is deduped by INCIDENT, not by branch.** The scope is
`workflow:branch` for a code failure — a test that fails on one branch only is
that branch's defect and must not hide inside main's alarm. A `data_integrity`
invariant with `reads_live_data` reads asktherecruiter.com, not the checkout, so
every branch sees the same one wrong number and the branch that noticed is
noise. Those raise and clear under a branch-free `<workflow>:live.data` scope,
keyed on `live_data_identity()` — the invariant label plus the slice labels,
read from data_integrity's OWN registries so a rename cannot silently return it
to one email per branch. On 2026-08-10/11 one open incident mailed six times in
seven hours; the numbers were never the cause and widening the normaliser would
have bought nothing (TECHLOG 2026-08-11). Do not broaden this to non-live
failures, and do not collapse two slices or two invariants into one key.

**OPERATIONAL MAIL LEFT THE HOST ON 2026-08-19. It goes through Resend now.**
`/alert` was a route on the host it reports about. On 2026-07-31 Bluehost 504'd
under `/blog/` twice (~6 min in the afternoon, ~7 min at night), in the sibling
tracker the alerter failed four times saying "HTTP 504 from /alert" — mute at
exactly the moment it was needed — and the host went down twice more on
2026-08-19. `railway/opsmail.py` (stdlib, Resend, `RESEND_API_KEY`) now carries
CI alerts, the RECOVERED notices, the weekly `health_digest.py` and
`ci_noise_report.py`. **The alarm no longer depends on the thing it monitors.**
It also splits the budget: the reader digest keeps Brevo's 300/day and
`digest_transport.py` is untouched, because a bad afternoon of red CI must not
be able to eat the allowance the readers depend on. Sender identity is
deliberately operational (`OPS_MAIL_FROM`), never the digest's From name.

**The open/resolved ledger moved with it, into `railway/alert_state.json`, and
THE CLAIM IS COMMITTED BEFORE THE SEND.** That ordering is the whole reason this
is not a downgrade. A server-side option's read-modify-write window was
milliseconds; a committed file read at checkout and pushed 30 seconds later is
not, and two runners that both read "nothing is open" would both mail. `git push`
to main is the compare-and-swap: the loser re-derives, finds the cause open and
goes quiet. Resend's `Idempotency-Key` is a second guard on the same transition.
Everything dedup promised still holds and is pinned by
`tests/test_ops_mail_split.py`: one cause is one email, RECOVERED fires once, a
live-data incident is one alarm across branches, two slices stay two alarms, and
the 14-day STILL FAILING window is unchanged. `ops_status.py [4b2]` prints what
is currently being SUPPRESSED, which no session could read while it lived in a
WordPress option. Do not "simplify" this by writing the ledger after the send,
and do not let the drain re-rule a held alert (it calls `ci_alert.deliver`, never
`post_alert`, or the ledger would swallow the alert as a duplicate of itself).

The outbox survives all of it, because a relay can be down too. Three rules
still:
- **An undeliverable alert is HELD, not lost.** `railway/ci_alert.py` retries
  transient failures in-run, then writes it to `railway/alert_outbox.json`
  (committed). `alert-drain.yml` delivers it every 30 minutes — and an empty
  outbox makes **no request at all**, which is why that tick is free.
- **A delivery failure is NOT a red run.** Holding exits 0. The only non-zero
  left is "could neither deliver NOR hold". **Do not restore the old `exit 1` on
  a failed POST**: that is what let one outage manufacture red runs which
  manufacture alerts which also fail. `ops_status.py [4b]` shows what is held.
- **The unattended host watch lives in the SIBLING repo**, on purpose: both
  trackers share one Bluehost account, so `host-watch.yml` over there probes it
  every 15 minutes and opens ONE GitHub issue per sustained outage. A second
  identical watchdog here would double the load and send two emails per outage.
  This repo's own check is `ops_status.py [1]`, at session start, and it is
  independent of the sibling.

**Cloud/remote sessions:** read [docs/CLOUD-SESSION.md](docs/CLOUD-SESSION.md) — it is the fully self-contained operating guide (local memories don't travel to the cloud; that doc carries everything). ops_status.py also prints the **handoff baton** — if another session HOLDS it, do NOT edit ([docs/HANDOFF.md](docs/HANDOFF.md)).

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
2. **`railway/`** — Python ingest. Cron 2×/day (EDGAR + NewsAPI + GDELT worldwide) → LLM
   extraction via OpenRouter → POST `/add`. The extraction model is
   `google/gemini-2.5-flash-lite` (swapped 2026-08-07 on a news-path gold set,
   30/30 at 0.388x the incumbent's cost). `OPENROUTER_CLASSIFY_MODEL` pins
   `deepseek/deepseek-chat` for context, domicile, reason tags, industry and
   roles. **It does NOT govern AI causation**, and this doc said it did until
   2026-08-13. `ai_explicit` is set in two places (`extractor.py:946` and
   `classify_ai_evidence()` at :592) and both deliberately use `MODEL`, with the
   comment "AI-causation is correctness-critical". The consequence is real: the
   2026-08-07 swap to flash-lite was validated on a news-EXTRACTION gold set and
   moved the AI-causation classifier with it. The env var is also set in no
   workflow, so it runs on its default everywhere. **That coupling is now
   MEASURED and the answer is UNKNOWN, leaning benign** (2026-08-18,
   `railway/ab_ai_causation.py`, $0.0527): against an independent referee the
   candidate and the pre-swap incumbent are indistinguishable (88.0% vs 87.5%,
   overlapping intervals) and flash-lite does NOT over-call AI -- it flags 35 of
   200 against the incumbent's 40, and none of the 50 plain negatives.
   **The owner adjudicated 27 of the 34 open rows on 2026-08-19, and the verdict
   is STILL UNKNOWN.** Gold coverage is 193 of 200; production flash-lite reads
   precision 78.5% (CI 57.2-91.6%) and recall 78.1% (CI 56.3-91.5%), the
   pre-swap incumbent 75.8% / 88.1%, on intervals that overlap almost entirely.
   Seven rows carry no label: 107375 (General Motors, the "AI skills swap" that
   no rubric settles) and six the speaker ruling reached but nobody flagged, all
   parked in `ai-causation-2026-08.adjudications.json` under `rec:` with the
   reasons in `_still_parked`. Seven unlabelled rows is a legitimate UNKNOWN;
   **do not round it to a pass and do not move a production model on it.** Quote
   the harness, never a hand-measured projection: the recommendations file's
   own 199-row estimate of 80.9% / 72.6% does not reproduce (69.5% / 78.1%).
   `python3 railway/ab_ai_causation.py --rescore` folds new rulings in and
   spends nothing.
   **The speaker question is ruled and no longer derived:** `ai_explicit`
   requires THE EMPLOYER to have attributed the cuts to AI, a report counts when
   it quotes or reports the employer saying it, and a journalist's own
   characterisation is the broad `ai_linked` tier. Stated for readers in
   methodology `#m-ai`, asked for in `ai_causation_prompt()` and `SYSTEM_PROMPT`
   rule 2, described in `alt_allowed_ai_causation()`. WARN notices skip the LLM: `warn_import.py` scrapes
   states via `warn-scraper` and bulk-upserts via `/bulk` (daily 9AM ET GitHub cron, `0 13 * * *`).
3. **`.github/workflows/`** — deploy (FTPS on push to main) + all data jobs (see RUNBOOK).
4. **Self-running loop:** every source (news, WARN, SEC, ERM, + dormant ones — supplemental
   news, distress/bankruptcy, foreign filings) funnels into the SAME `extract_layoff_data`
   → `post_to_wordpress` pipeline, so all guards apply once. `report_source_health(...)`
   feeds a ledger; the weekly **`health_digest.py`** emails info@asktherecruiter.com (via
   Resend since 2026-08-19, not the host it reports on) when a scraper breaks, with a
   **paste-ready fix instruction**.
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
   **Its AGE is now checked, its contents still are not and cannot be.** The refresh stays manual because the data may not leave this machine, but `railway/benchmark_freshness.py` (= `ops_status.py [6]`) reads **dates only** out of that file and goes STALE when the comparator side is 15+ days old or when a hand-written percentage predates the last time the figure under it moved — the defect that let a 2026-07-27 coverage figure be quoted for sixteen days after its denominator changed. It prints ages and never a name or a number, by shape rather than by care; `tests/test_benchmark_freshness.py` holds that. Do NOT answer a STALE by widening the ceiling or by moving the figures somewhere checkable → RUNBOOK "the coverage comparison is stale".

**Hard bars:** (a) any source/metric change updates Sources + Health labels + the benchmark in the **same** session; (b) formatting is non-negotiable — aligned tables, no horizontal bleed (especially mobile), consistent copy, **no em-dashes in UI copy**; (c) **verify live** (`curl` the `ver=` + the page/endpoint) before claiming any surface is updated — never assume a deploy landed.

## Iron rules learned the hard way (details in TECHLOG)
- Every network request to the WP host MUST send a browser-ish `User-Agent` (ModSecurity blocks `python-requests`; use `AiLayoffTracker/1.0 (+https://asktherecruiter.com)`).
- `WP_SITE_URL` is `https://asktherecruiter.com/blog` — never the bare domain (root is a separate Railway app).
- FTP deploys bypass WP hooks: version bumps trigger cache-flush/table-migration on first request (`alt_flush_caches_on_deploy`), and anything that must exist (like the contact page) needs a **retry-until-verified** hook, not a one-shot on version bump (deploys race mid-upload).
- Never trust freeform extracted values: countries/industries normalize through fixed vocabularies (`alt_normalize_country`/`alt_normalize_industry`); counts parse the FIRST number only. Date bounds differ by path: the LLM path (`extractor.py`) nulls any `layoff_date` before 2015 (news/SEC have no reliable pre-2015 supply anyway); the server WARN/bulk path (`alt_db_valid_date`) accepts back to year 2000, so historical state-WARN + ERM data legitimately populates 2002→2014. Upper bound is today+~3yr (future-dated WARN effective dates), not +18mo.
- WARN entries are EXEMPT from fuzzy/cross-outlet dedup (companies legally file several notices close together).
- Changing an entry's job count changes its dedup hash → corrections need `/bulk-purge` + full re-import, not plain upsert.
- Data-changing jobs must FAIL LOUDLY (non-zero exit on any failed batch; `curl --fail-with-body` in workflows).
- Bump the plugin `Version:` + `ALT_VERSION` on EVERY deploy — it cache-busts assets and triggers the flush. **Two sessions can bump to the SAME number and git will merge both cleanly**, which happened twice on 2026-08-19; `.github/workflows/version-collision.yml` now fails the second merge and prints the number to use (RUNBOOK "two merges claimed one plugin version").
- **Never make a paid model call outside `spend.metered_call()`.** It is the gate
  AND the meter: it reads the per-run brake immediately before the request and
  meters immediately after, so a caller cannot spend without checking and cannot
  check without metering. The `make_call` you hand it must perform exactly ONE
  request — a callable that loops or retries internally puts several charges
  behind one gate read, which is the once-per-item defect that let a run
  overshoot its ceiling by 36 calls (2026-08-11). **Retry ONLY via
  `metered_call(attempts=N, retry_sleep=S)`**, which runs gate read -> request
  -> meter on every attempt; never wrap a loop or an `attempts=` of your own
  inside the callable. It raises `spend.PaidReadsOff`; a budget stop is
  UNDECIDED, never a verdict, and never a red run.
  **A retry you did not write still counts, and this is how it arrives.** Every
  paid client must set `max_retries=0`: the OpenAI SDK defaults to 2 and
  re-POSTs on 408/409/429/5xx and any connection error from INSIDE your
  callable. Six scripts carried that default until 2026-08-19. A retried 429 is
  usually free, but a **timeout is not** - the client stops waiting, the model
  keeps generating, and OpenRouter bills a completion that no ledger entry, no
  ceiling and no cost-per-row figure has ever seen. That is worse than an
  overshoot, because an overshoot is at least measured.
  `tests/test_one_request_per_metered_call.py` fails on a paid client built
  without `max_retries=0` and on a metered callable that retries itself.
- **Never write a row directly.** A new source builds a raw dict and calls `extract_layoff_data` → `post_to_wordpress`. The raw dict MUST set `raw_text` (the extractor reads ONLY that and returns None if empty — the bug that made supplemental news silently post zero). Mirror `sources/newsapi.py`. Ship key-gated sources DORMANT with dry-run diagnostics. See RUNBOOK "add a new source".
- **Competitor data stays private** (standalone brand): never put competitor names or numbers in the repo or GitHub logs. Competitor tracking lives ENTIRELY in the local benchmark (`gen.py` reads only our own `agg_*.json`; the competitor figures are maintained by hand in `scratchpad/bm-live.html`). **No secret is involved and none is needed.** The `BENCHMARK_FEED_URLS`/`BENCHMARK_COMPANIES` secrets power a SEPARATE, OPTIONAL automated loop (`tracker-diff`) that is **dormant by the owner's decision (2026-07-28)** — it exits green on its schedule and costs nothing. **Do not ask the owner to add those secrets.**
- **The learning loop is armed; the chase is not. They are the same file.**
  `tracker_diff.py --learn` runs daily inside `tracker-diff.yml` and needs no
  secret, because its reference universe is our OWN GDELT query *before* the
  `TRUSTED_DOMAINS` gate — layoff coverage our net could see and does not read.
  It stores no row, calls no model ($0.00/run, `ALT_PAID_READS=off` and no
  OpenRouter key in scope) and fetches no page, so no robots.txt or paywall is
  ever touched. It emits **rules, not a score**: a phrasing to add, an outlet to
  review, a country or language we do not cover, mailed paste-ready → RUNBOOK
  "a tracker learning email arrived". The trending number is **independent
  recall** (`railway/tracker_learning_state.json`, committed): of the
  announcements a run could judge, the share we already held unaided.
  **Every name it reads leaves through exactly one sink** (`_email_rules`, the
  owner's inbox). stdout, the health ledger and the committed file are held
  nameless BY CONSTRUCTION — `assert_nameless` is an allowlist of numbers, ISO
  dates and frozen label words, so a name cannot be spelled by anything public,
  and `tests/test_tracker_learning_leak.py` poisons a whole run to prove it.
  Never "improve" this by logging a subject for debugging; that test will fail,
  and it is supposed to. The earned cadence steps down to Mondays after three
  runs with no rule — do not answer a quiet loop by lowering `RULE_FLOOR`.
- **A curated digest is a recall probe and a worklist, never a source.**
  `railway/curated_probe.py` is the hand-fed sibling of the learning loop: the
  owner drops pasted items into `scratchpad/recall-worklist.txt` (gitignored)
  and runs it. Same machine, different reference universe — GDELT can only
  surface outlets GDELT indexes, and a domain expert's roundup is where the
  OUTLET class of miss actually shows up. Judgement is IMPORTED from
  `tracker_diff`, never copied, so "did we hold this?" has one definition.
  $0.00/run: our own `/query` plus, for inaccessible items only, one Google News
  RSS query. **"Paywalled" is NOT "unreachable"** — the source stays unread and
  goes to the refusal ledger, then the EVENT is chased in the open press, which
  resolves to `recoverable` (wire the ACCESSIBLE outlet — the common case),
  `vocabulary_gap`, or `unreachable`, the only closed finding. Recovery reads the
  news INDEX and takes outlet identity from its `<source>` element, so **no
  content request reaches any outlet** and no robots.txt, paywall or bot wall is
  engaged; a test pins that no request is built from an item's URL. **There is no
  workflow and there must not be** — a runner that can read the worklist is the
  leak. stdout and `railway/curated_probe_state.json` are nameless by
  construction (`assert_nameless`, an allowlist); every name goes to the
  gitignored local report and the owner's inbox, and unlike the learning loop the
  named half never touches stdout. Watch TWO numbers: `curated_recall_pct`
  should climb, `taught_pct` (dependence) should fall. Do not widen the recall
  denominator to make it look better — it admits only items with a parseable
  headcount and employer, and folding the rest in is what made the first version
  read 73.3% on rows we demonstrably held. → RUNBOOK "you have items from a
  curated digest".
- **Country filter**: `country_basis=any` (table/exports) unions job-location OR employer-HQ so US-HQ global cuts show under a US filter; headline stats stay strict job-location. Don't "fix" the discrepancy — it's intentional and documented.
- **"The collector ran" is not "the collector brought back anything new."**
  Every WARN tripwire was a COUNT floor until 2026-08-19, and a collector
  re-reading a FROZEN archive returns its whole history every run, clears the
  floor, and reports healthy forever. Kansas looked green for 110 days while
  publishing nothing; MI 81, MN 49, IN 29. `railway/source_freshness.py` judges
  each source against ITS OWN history through two gates that must both agree:
  Poisson rarity AND the source's own 90th-percentile publication gap times
  1.25. Neither is redundant - cadence is what stops Texas firing on a nine-day
  lull and what makes Mississippi's quarterly silence ordinary without a
  hard-coded exemption; rarity is what stops North Dakota firing at 216
  legitimate days.
  **QUIET AND BROKEN ARE DIFFERENT STATES, and the first cut got that wrong.**
  It called Kansas dark; an audit found the register holds 910 rows and we were
  missing nothing - Kansas had simply not filed since May. The certainty came
  from the denominator, 33/yr averaged over all history against 12.5/yr over the
  trailing year, which is the difference between "impossible" and a 2.3% event.
  So the RATE is fitted over the trailing 365 days (rates drift), the CADENCE
  keeps 1095 days (burstiness does not, and gaps need samples), both are
  reported so a slowdown reads as itself, and there are two thresholds:
  `ALPHA_DARK = 0.01` opens an incident and emails, `ALPHA_QUIET = 0.05` is
  advisory and is never emailed as a breakage. On the six states a measurement
  called dark, only MI and MN survive as broken; KS and IN are QUIET. **Do not answer a dark
  source by widening a threshold or by writing UNAVAILABLE into
  `railway/source_state.json`** - both are in `self_heal.py` FORBIDDEN, and a
  healer may fix the collector but never the judge. The ledger is three states:
  HEALTHY / BROKEN / **UNAVAILABLE, which only a human sets**, with a reviewer,
  a reason and a date. A BROKEN source never ages out. → RUNBOOK "a collector
  went dark".
- **A source that never reports at all does not show up green. It does not show
  up.** Every guard here iterates the health ledger, so absence read as "no
  problem" rather than "never looked at". `railway/source_inventory.py` builds
  the inventory from what SHOULD exist (56 US jurisdictions; the `meta{}`
  registry in `assets/health.js`) and diffs it against the live ledger;
  `ops_status [2c]` prints it. On 2026-08-19 two declared collectors had NEVER
  reported: `earnings_ingest` and `digest_weekly`.
- **Source health is not data integrity.** "Did the collector run?" and "is what it produced correct?" are different questions, and for months only the first was on the dashboard. Live invariants live in `railway/data_integrity.py` and are imported by the test, ops_status and the digest — ONE definition. Never let a check resolve to a silent pass: PASS / FAIL / **UNKNOWN** are three distinct states and absence of a signal is not a pass.
  **The email digest is the same lesson in a fourth state.** Its relay credential was rejected for three days while every scheduled run was green, because the credential was only ever exercised by a real delivery and nobody was due — so `0 sent of 0 eligible` was true, complete, and said nothing. Every run now does a LOGIN with no message after it (`Transport.verify()`), and the `digest_mailer` health row carries `credential=<STATE>`, read at session start by `ops_status [4c]`. Four states, not two: **ABSENT** (nothing armed) is green, **REJECTED** is a red run a human clears by rotating a secret, **UNKNOWN** (relay unreachable) is never a pass and never a fault. Do not collapse ABSENT into REJECTED — a missing key must stay a state — and do not read a 4xx or a dropped connection as REJECTED, which would send the owner to rotate a working secret.
- **A headline FAIL is closed by a human, never by the calendar.** A failing
  `headline_movement` slice opens a sticky incident in
  `railway/headline_incidents.json`, and that slice reports FAIL until someone
  closes it with `--close-incident` (reviewer + reason + **the affected row IDs**
  + an explicit replacement baseline). It exists because two individually correct
  guards agreed to erase the open US incident on 2026-08-22: the recorder pins a
  failing slice's baseline, and a baseline past `MAX_BASELINE_AGE_DAYS` used to
  age into a recordable UNKNOWN. Two other clocks widen the same way — `floor =
  move_floor * span` and `allowance = |Δentries| * base_mean * mean_factor` — so
  waiting was never neutral. Never close one by editing either JSON by hand.
- **A containment pair is ONE observation or it is nothing.** `headline_containment`
  subtracts two committed baselines, so that difference is only a complement if
  both readings describe the same instant. Every baseline entry carries
  `recorded_in` (the recorder run that wrote it) and the pair is judged only when
  both stamps match; different or missing stamps read **UNKNOWN naming both**,
  never a pass. `record_baseline` holds the whole connected component of the
  containment graph whenever any member cannot advance, so a straddle cannot be
  built. This replaced `MAX_PAIR_SKEW_DAYS = 1.0`, a window sized on "ordinary
  drift is a few thousand jobs" that a 42,000-job signed correction walked
  straight through on 2026-08-14, leaving a -53,476 artifact and 14 days of red
  CI with nothing to close. Do not answer a UNJUDGED pair with a new tolerance.
- **Retiring a source takes THREE steps**, and skipping the third silently voids the second: (1) drop it from `cron.py`, (2) add it to `alt_retired_sources()` in db.php, (3) **stop every remaining path that posts health under that id**. `alt_retired_sources()` deliberately refuses to mask a row whose last run postdates the retirement, so one forgotten weekly job keeps a retired collector looking live forever. Also: a staleness ceiling must match the job's REAL cadence — a 2-day ceiling on a weekly job is permanent noise that hides real breakage.
- **Don't claim "100% automated."** It's ~99%; the honest sliver is scraper repairs (auto-detected + emailed), private-benchmark refresh, and novel-source judgment.

## Dependencies are hash-pinned. Never `pip install` a name.

`railway/requirements.txt` (and `requirements-min.txt`) are the human-edited
INPUTS: floors, for a resolver to read. `railway/requirements.lock` and
`requirements-min.lock` are the resolved outputs, exact versions, every package
hash-pinned transitively, and they are what every workflow installs, with
`--require-hashes` so pip refuses anything the lock did not vouch for.

This is not hygiene. Twenty-odd workflows used to run a bare `pip install
requests` in a runner holding `WP_API_KEY` and `OPENROUTER_API_KEY`, unattended,
twice a day, with nobody reading what the resolver picked. One malicious release
of any transitive dependency lands with both keys and nothing in any log looks
wrong.

Two locks, because a health job should not pay to install pdfplumber and
google-cloud-bigquery. `requirements-min.lock` is openai + requests; everything
else uses the full lock. `tests/test_dependency_pinning.py` fails on a bare
install, on a lock with an unhashed pin, on a workflow naming a lock that does
not exist, and on the two locks disagreeing about a shared package.

**The ritual when a dependency changes:**

```bash
python3 -m venv /tmp/lock && /tmp/lock/bin/pip install pip-tools
cd railway
/tmp/lock/bin/pip-compile --generate-hashes --strip-extras \
    --output-file=requirements.lock requirements.txt
/tmp/lock/bin/pip-compile --generate-hashes --strip-extras \
    --output-file=requirements-min.lock requirements-min.txt
```

Then **read the diff**. A lock refresh nobody read is the unpinned state with
extra steps. `Tests` runs on every push and installs from the lock, so a lock
that does not resolve on the runner goes red there rather than in a data job at
2am. `pip install --upgrade pip` is banned for the same reason the lock exists:
it is an unverified download into the same runner, immediately before the
verified one.

## Verify a change is actually live
```bash
curl -s "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate?cb=$RANDOM" | python3 -m json.tool | head
curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head -3
```
**Those two commands prove the ORIGIN is updated. They cannot prove a reader
sees it, and for months nothing did.** `?cb=` is a cache key nothing holds an
entry for, so the origin always answers it. A reader requests the BARE url, and
that is the one key the shared caches in front of `/blog` (Cloudflare over a
Railway proxy, neither purgeable from this repo) do hold. On 2026-08-05 that gap
served a superseded build to every reader and crawler for 18 minutes while every
check in the repo read green. So also run:
```bash
python3 railway/reader_freshness.py     # bare URL, browser UA, no cache buster
```
It is `ops_status.py` section `[1b]` and a required step of the deploy workflow.
A mismatch it cannot date resolves to UNKNOWN, never to a pass.
**And a version number is not the content.** That check compared version to
version until 2.20.33, so it passed a page that carried the NEW version string
around the OLD body: on 2.20.21 an FTPS upload landed `ai-layoff-tracker.php`
before `page-tracker.php`, the reader check's own bare-URL request cached that
render, and readers had it for 25 minutes with everything green. Every plugin
surface now emits `<!-- alt-build ver=X build=Y -->`, a hash of the plugin's own
files taken at render time (`includes/build-stamp.php`), and `/status` reports
the same hash cache-immune. PASS needs both to agree; same version with a
different build is a FAULT, not a pass. The deploy's wait polls `/status` FIRST
and does not touch the bare URL until the origin is coherent, so the check
cannot be the request that caches a raced page. Don't "fix" a stamp mismatch by
widening the window (240s, sized from the 470s measured on 2026-08-05 scaled to
today's `s-maxage=60`) - it means a mid-upload render is sitting in a cache.
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
