# Runbook — operations & troubleshooting

## Deploy
Push to `main` → `.github/workflows/deploy-plugin.yml` FTPS-uploads
`wordpress-plugin/ai-layoff-tracker/` to the Bluehost install at `/blog`.
**Always bump `Version:` AND `ALT_VERSION`** in `ai-layoff-tracker.php` — that
cache-busts assets and fires `alt_flush_caches_on_deploy` (page-cache flush +
DB-table dbDelta) on the first PHP request. To trip it immediately:
```bash
curl -s "https://asktherecruiter.com/blog/?bump=$RANDOM" -o /dev/null
```
The deployment first PHP-lints every plugin file, then verifies a cache-busted
public tracker API response after FTPS completes. A failed live verification is
an actionable deployment alert; do not assume an FTP success alone means the
plugin loaded.
Rollback = `git revert` + push (there is no other rollback path; FTP is the only door).

## GitHub workflows (Actions tab)
| Workflow | Trigger | Purpose / inputs |
|---|---|---|
| deploy-plugin | push to main | FTPS deploy of the plugin |
| warn-import | daily 15:00 UTC + manual | WARN sweep. Inputs: states (`all` or `CA,NY`), min_employees, start, limit, **purge** (needs states=all, refuses if scrape <5K) |
| gdelt-backfill | manual | Worldwide news for a date range (costs OpenRouter credits) |
| backfill | manual | EDGAR 8-K historical range |
| news-catchup / seed-ai | manual | Recent-news top-up / curated seed |
| dedupe | manual | Collapse cross-outlet duplicate clusters (WARN exempt) |
| cleanup | manual | Re-normalize country/industry + NULL implausible dates across table+posts |
| migrate | manual | Re-mirror all CPT posts into the fast table |
| trash-entries | manual | **Editorial removal** (post_ids/row_ids + required reason). Log it in TECHLOG + site corrections log |
| data-quality | Mondays 16:00 UTC + manual | Anomaly report: WARN notices ≥5K, same-company multi-state filings, weak links — READ THIS WEEKLY |
| survey-reconcile | monthly + manual | Compares the strict US AI-primary announcement metric against the latest official announcement-survey report; fails if variance exceeds 10% |
| reclassify-legacy-ai | daily + manual | Re-reads linked sources for a bounded batch of legacy AI flags; never deletes rows |
| reason-backfill | daily 04:40 UTC + manual | Tags untagged non-WARN rows from their STORED excerpt only (fixed vocabulary; ERM template rows map from Eurofound's recorded type, freeform rows via DeepSeek). Writes via /edit (pins rows). Inputs: model_batch, deterministic_cap, dry_run |
| enrich-roles | daily 04:23 UTC + manual | Bounded role-category extraction from already-stored row text (roles/excerpt/quotes, no external fetches); fills only blank role_categories, marks evidence-silent rows `unknown` so the queue drains |
| historical-news-sweep | daily + manual | Rotates through one 14-day global GDELT history window per day; dedup makes retries safe |
| announcement-lifecycle-review | daily + manual | Read-only summary of exact-count, source-supported announcement-to-later-record candidates; never auto-merges or changes sources |
| quarterly-report | 7th day after quarter close + manual | Stores an immutable, server-generated State of Layoffs snapshot; accepts only quarter id/status, never client totals or editorial claims |
| canonical-event-migrate | daily + manual | Resumable no-LLM conversion of legacy rows into canonical events with retained source reports |
| company-watchlist | daily + manual | Sweeps big employers with no current-year entry; targeted news search → extractor → poster. Auto-grows via `WATCHLIST_INDEX_URLS`. Inputs: dry_run |
| supplemental-news | daily 14:05 UTC + manual | NewsData.io + Marketaux + Finnhub (non-English/EU news). Dormant per key. Inputs: dry_run |
| distress-watchlist | weekly Tue + manual | CourtListener bankruptcy + Companies House insolvency → distressed names → watchlist news search. Dormant per key. Inputs: dry_run |
| foreign-filings | daily 13:30 UTC + manual | EDINET (JP) + OpenDART (KR) filing bodies → extractor (guards reject non-layoffs). Dormant per key. Low yield by design. Inputs: dry_run |
| recall-precision | weekly Mon 16:10 UTC + manual | **The only place the recall claim can FAIL.** Re-runs the frozen SEC Item 2.05 gold set (57 events) against live data, **commits** `railway/recall_measurement.json`, and exits 2 below `recall_goldset.MATCHED_FLOOR`; also measures count precision (exits 2 when the Wilson 95% lower bound drops under 80%) and AI-attribution precision. Every rate is printed **with its interval**. Needs `contents: write` for the commit. Inputs: RP_PRECISION_SAMPLE |
| data-integrity | daily 17:30 UTC + manual | **Is the published data CORRECT?** Runs `railway/data_integrity.py` — the live invariants (known duplicate events must count once) shared with `tests/test_dedup_live.py` — and writes the verdict to the health ledger as `data_integrity`. Scheduled 50 min AFTER reconcile-supersets so it sees that pass's result. Exit 2 = failing, exit 3 = could not verify (never a silent pass) |
| health-digest | Mondays 12:00 UTC + manual | **Autonomy tripwire.** Reads source-health ledger; fails RED and **emails info@asktherecruiter.com** (via `/alert`) when a source goes STALE or degrades, **or when a live data-integrity check is failing** (subject leads "WRONG NUMBER LIVE"). Weekly is the backstop only — the fast paths are `ops_status.py` [3] and the daily data-integrity run. Email body carries a paste-ready Claude fix instruction. Inputs: dry_run |
| digest-send | daily 13:10 UTC + manual | **The email digest's sending half.** Pulls the due recipients from the keyed `/digest-recipients`, relays through the transport chosen by `DIGEST_TRANSPORT`, records counts to `digest_mailer`. **DORMANT: `dryrun` by default, so it prints the exact email and sends nothing, exit 0.** Arming it is three owner steps, see "The email digest: arming the sender". Inputs: dry_run, freq, limit |
| tracker-diff | dormant BY DESIGN (owner decision 2026-07-28) | Optional gap-chase against a private feed. Competitor tracking is handled by the LOCAL benchmark instead; this loop is not needed, exits green on schedule, and nobody should be asked to enable it |

The advisory DeepSeek spot-check inside `data-quality` retries temporary
network/model failures and writes an explicit warning to the Actions summary
without failing the whole report. A failed attempted automatic correction still
fails loudly, because that is a data-changing operation.

Secrets (repo → Settings → Actions): `WP_API_KEY` (from wp-admin → Tools → AI Layoff
Tracker), `OPENROUTER_API_KEY`, `FTP_USER`/`FTP_PASSWORD`/`FTP_HOST`, `NEWSAPI_KEY`,
`GCP_BIGQUERY_CREDENTIALS_JSON`.
Railway env: `OPENROUTER_API_KEY`, `WP_API_KEY`, `WP_SITE_URL=https://asktherecruiter.com/blog`.
Optional Railway env: `PRESS_RELEASE_FEEDS` (JSON array of reviewed official company RSS/Atom feeds; see `.env.example`).

**Dormant-source keys** (each collector runs only when its key is present; add in
repo → Settings → Actions → Secrets, exact name):
| Secret | Activates | Status / notes |
|---|---|---|
| `NEWSDATA_API_KEY` | supplemental-news (NewsData.io) | Free tier caps `q` at 100 chars; endpoint is `/api/1/latest` |
| `MARKETAUX_API_KEY` | supplemental-news (Marketaux) | Search syntax uses `|` for OR, not the word "OR" |
| `FINNHUB_API_KEY` | supplemental-news (Finnhub) | Ticker-based; reuses `seed_data/earnings_tickers.csv` |
| `COURTLISTENER_API_KEY` | distress-watchlist (US bankruptcy) | Only "In re <Debtor>" petition captions kept |
| `COMPANIES_HOUSE_API_KEY_UK` | distress-watchlist (UK insolvency) | HTTP Basic (key as username) |
| `EDINET_API_KEY_JP` | foreign-filings (Japan) | Low yield; extractor guards protect quality |
| `OPENDART_API_KEY_KR` | foreign-filings (Korea) | Low yield; `list_disclosures` needs (start,end) dates |
| ~~`FMP_API_KEY`~~ | (dropped) | Transcripts are paid-only (HTTP 402) — earnings ingest removed |

Every dormant source ships DORMANT and exits clean when its key is absent, so
adding a key is the only step to activate it. First run each in `dry_run=1` and
read the diagnostics (they log the raw API status) before trusting live output.

## "X is broken" playbooks

**A collector is RETURNING NOTHING** (digest subject `SOURCE RETURNING NOTHING`)
The digest exits 2 and the email leads with what the source is worth, plus the
candidate routes for it. That listing comes from `railway/source_value.py`,
which is the file to read first and the file to update when you learn something.

**Check DISCOVERY before the parser.** A collector returning 0 has usually lost
the step that FINDS its documents, not the step that reads them. On 2026-08-13
`warn_quebec` reported "parser returned 0, check PDF layout" for days while the
parser was perfect: it discovered its PDFs by scraping one HTML landing page,
and that page returned links to a laptop but not to a GitHub runner. The message
accused the only component that was working.

**Do this, in order.**
1. **Run the collector locally and read what it says**, e.g.
   `cd railway && python3 sources/quebec.py 4`. If it works locally but not in
   CI, the difference is the network path, not the code: a WAF, a bot wall or a
   geo-block on the runner's IP. Confirm from the workflow log
   (`gh run view <id> --log | grep -i <source>`) rather than guessing.
2. **Find a route that needs no HTML.** This is the durable fix and the one the
   owner asks for. In order of preference: a constructible URL pattern (Quebec's
   `CDN_TEMPLATE`), an open-data/CKAN endpoint, an RSS feed, a Wayback snapshot.
   Keep the original route too, since it is what catches a change to the naming
   pattern; make the two a UNION, not a fallback.
3. **Audit against the source's OWN declared totals** if it publishes any. The
   Quebec PDFs print `Total - Nombre d'avis`, so the collector can report "83 of
   the 84 this document declares" instead of a bare count. Every thin-parse
   defect found that day was invisible until that comparison existed.
4. **Record what you learned in `source_value.py`** — the worth line and the
   routes. The next breakage should arrive with candidates attached.

**Do NOT** answer a zero by lowering an expectation or by marking the source
soft-degraded. And do not add a source to `zero_is_outage` unless a zero is
genuinely impossible for it: a bankruptcy watchlist that found nothing this week
found nothing, and a false alarm costs more trust than a missed one costs data.

**A WARN state COLLAPSED against its own history**
The health page shows `warn_custom_legacy` degraded with
`Custom WARN state(s) collapsed vs their own history`, naming states as
`OH=61 (floor 787)`.

**What it means.** That state's scraper still answered — it just answered with
a fraction of the state. This is the failure a `== 0` tripwire cannot see, and
it is the common one: on 2026-08-13 Ohio's JFS pages became unreachable to the
scraper and `fetch_oh()` fell through to a single fallback CSV, returning 61 of
787 notices with every guard green.

**Do this, in order.**
1. **Open the state's page in a browser first.** A government site that 404s to
   an automated probe and 200s to a browser is a soft bot-block, not a dead
   page — Ohio does exactly this. `curl` and a hand-probe will lie to you.
   Compare with the scraper's own UA:
   ```bash
   python3 -c "import urllib.request as u;print(u.urlopen(u.Request('<URL>',headers={'User-Agent':'Mozilla/5.0'})).status)"
   ```
2. **Run the one scraper** and count what it returns:
   ```bash
   cd railway && python3 -c "from sources.warn_custom import fetch_oh; print(len(fetch_oh()))"
   ```
3. **Fix the scraper**, not the floor. If the agency moved its pages, repoint
   the module's `_XX_WARN_BASE`, and check whether
   `sources/warn.py::STATE_WARN_URL` needs the same move — that map is
   generated into the plugin's `warn-state-urls.php` and published as the
   "State WARN list" link beside every row, so a stale entry there is a **404
   shipped to readers**, not just an ingest problem. After editing it run
   `python generate_warn_urls.py` (a parity test enforces this).
4. **Only then consider the floor.** `railway/warn_state_baselines.json`
   ratchets UP only and never lowers itself, by design — a floor that relaxes
   toward a collapse is the self-widening clock that let the headline guards
   erase an open incident by waiting. If the state's archive genuinely shrank
   (the agency dropped old years), lower that state's number **in a reviewed
   commit that says why**. Never lower one to silence an alert you have not
   explained.

**A first run says the floors are UNKNOWN.** `no per-state floors yet — partial
collapse is UNDETECTABLE this run` means the ledger has not been seeded for
that tier. That is UNKNOWN, not a pass; the next full sweep seeds it.

**There are THREE tiers, and each has its own floors:** `generic` (the open
warn-scraper states), `legacy_custom` (`warn_custom.CUSTOM_STATES`) and
`new_custom` (`warn_new_states.NEW_CUSTOM_STATES` — MS/WV/NM/WA/KS/AL). The
third tier had no floors at all until 2026-08-13: its only tripwire was a hard
zero, so a state there could lose 90% of its archive and `warn_custom_states`
would still report ok. If you add a tier, give it floors in the same commit —
an unfloored tier is indistinguishable from a healthy one on the health page.

**The ratchet skips the drifted state, not the tier.** Do not "simplify" it back
to `if not drift: ratchet(...)`. That gate is why the ledger sat empty: one
permanently broken state (Idaho's landing page today) withheld the floor from
every healthy state in its tier, forever, and a tier with no floors detects
nothing but a hard zero. A collapsed state must teach nothing; its healthy
siblings must still record.

**Seeding by hand is allowed, and only in one direction.** A floor seeded LOW is
harmless — the ratchet raises it on the next healthy run. A floor seeded HIGH
cries wolf on every run until someone edits it. So seed from counts you actually
measured, never from an estimate, and never from a run you have not eyeballed.

**Rolling-window states are EXEMPT from the ratchet (AZ, DE, ME, VT).** Their
portals publish a rolling window, not an archive — AZ read 307, 299, 58, 76 on
four consecutive days (TECHLOG 2026-08-14) — so a high-water floor there is a
false alarm the mechanism manufactures itself. `ROLLING_WINDOW_STATES` in
`railway/warn_import.py` is never ratcheted AND is dropped on ledger load, so
do not hand-seed them into `warn_state_baselines.json`; the entry is dead on
read. They are watched by hard-zero detection behind the peer gate. If one
needs a partial-collapse floor, set it deliberately via `WARN_GENERIC_BASELINE`
— that path is honoured because it is a human judgment, not the ratchet. If a
state's portal changes publishing model (rolling ↔ archive), move it in or out
of `ROLLING_WINDOW_STATES` in a reviewed commit that cites measured counts.

**A job is DEFERRING (and what three in a row means)**
`ops_status.py` section `[4d]` listed a job as deferred, or a workflow run
printed `DEFERRED: <job> could not reach the host`.

> **FIRST: is the job called `test-job`, and did you read it off a run
> ANNOTATION rather than off `[4d]`?** Then nothing is deferring.
> `test-job` is the fixture name in `railway/tests/test_host_call_deferral.py`,
> and until 2026-08-14 those PASSING tests printed their subject's `::error::`
> lines, which GitHub turns into red annotations on the `Tests` run. A session
> spent a night hunting the three items the host had refused; the "three" was
> the fixture body `{"ok": false, "failed": 3}`. `[4d]` and
> `railway/deferral_ledger.json` are the only sources of truth for what is
> deferred. If an annotation like that appears again, the leak is the defect —
> see `railway/tests/test_no_annotation_leaks.py`.

**What it means.** The job never got an answer from the WordPress host — a
transport error, or a transient status (502/503/504 and friends) that survived
every in-run retry. Nothing was read and nothing was written. The run exits 0
because a host that never answered is not a job that failed: `/alert` is a route
on that same host, so a red run here fires an alerter that cannot deliver, which
is how one six-minute Bluehost window on 2026-07-31 manufactured red runs in the
sibling tracker and four failed alerts on top of them.

**It is not a pass either.** That is what section `[4d]` is for. The deferral is
counted in `railway/deferral_ledger.json` (committed, because state about the
host cannot live on the host), and the count is per job and consecutive.

| What you see | What to do |
|---|---|
| One job, `x1` | Nothing. Check `[1]` in the same run — if the live tracker was unreachable too, the host had a bad few minutes and the next scheduled run picks it up. |
| Several jobs, `x1`, same window | A host outage. The sibling repo's `host-watch.yml` opens one issue on a sustained one. Still nothing to do here. |
| One job, `x3` or more | **A human is needed.** The run went red on the third and mailed you. |

**Three in a row is not an outage.** These jobs run daily, so `x3` means the
host was reachable by every other job for three days and this one still never
got an answer. Look for a cause that is specific to this job, in this order:

1. **Is the route still there?** `curl -sS -o /dev/null -w '%{http_code}\n'` the
   URL in the workflow. A 404 would be a FAILURE, not a deferral, so a 404 in
   your hand means the URL never resolved at all in the run — check the host
   part of it, and whether egress from the runner is the actual problem.
2. **Is it a timeout rather than an outage?** A job whose response grew past
   `--timeout` (default 90s) defers forever while every other job is fine. Raise
   the timeout in the workflow, or bound the response (`per_page`, `detail=`).
3. **Is the host rate-limiting or ModSecurity-blocking this specific call?**
   Reproduce with the exact `User-Agent` (`AiLayoffTracker/1.0 (+…)`), which
   `host_call.py` always sends.

**Once fixed**, just let it run — the next successful call clears the streak and
commits the resolution. To clear it by hand:
`python3 railway/deferral_ledger.py record --job <job> --state success`.
`python3 railway/deferral_ledger.py status` prints the same thing `[4d]` does,
and exits 2 when something has hit three.

**What a deferral never covers.** A real answer from the host is still a red run
on the FIRST occurrence: a wrong key (401/403), a missing route (404), any
non-transient status, and a 2xx body that reports its own failed batch. None of
those gets better by waiting, and softening them was never the point.

**Converting another workflow to defer** is per job and is not automatic. The
bar is: re-running it tomorrow must be equivalent to running it today. The first
two cleared it for different reasons — `reconcile-supersets` is a clean-slate
recompute (resets every mark, then re-marks), and `announcement-lifecycle-review`
writes nothing at all. A job that appends, advances a cursor, or spends money on
work it would have to redo does NOT clear it, and should keep failing loudly.

**The Python workers (converted 2026-08-12).** Those two shell out to
`host_call.py` per call. The enrichment and backfill workers make many calls
interleaved with model work, so they use the SAME machinery as a library:
`host_call.get_json` / `post_json` raise `host_call.Deferred` when the host
never answered and raise loudly on a settled refusal, and `host_call.defer()` /
`clear()` do the identical ledger bookkeeping. Their workflows each end with the
`commit-deferral-ledger` step, and `railway/tests/test_job_deferrals.py` asserts
that pairing — a worker that records a deferral into a ledger nobody commits is
the silently green job this whole mechanism exists to prevent.

| Job | Defers when | Stays loud when |
|---|---|---|
| `enrich-roles`, `enrich-context`, `reclassify-legacy-ai` | any host call in the run never answered | anything else; the queue is server-side and nothing is marked until the closing POST |
| `claims-import` | `/claims-ingest` never answered | the endpoint refuses; FRED being empty is a separate, older fail-soft |
| `employer-domicile-backfill` | any call never answered | `/enrich-context` is a blank-fields-only idempotent fill, so a partial batch is not a state |
| `survey-reconcile` | any call never answered | each record is an upsert keyed by reference month |
| `archive-backfill`, `canonical-event-migrate` | the host never answered **before the first batch landed** | after that it is the existing batch cap by another name: stop, say so, resume next run |
| `reason-backfill` | page one of the SCAN never answered | once `/edit` has written a chunk the run did real work; the rest is reported as `unwritten` |
| `erm-import` | **no** `/bulk` batch reached the host at all | some batches landed and some did not — a partly applied bulk import is exactly what the fail-loud rule protects |

Three left deliberately alone: `source_health` and `historical_news_sweep` were
already tolerant (each had re-derived its OWN copy of the transient set; both
now import `http_retry.TRANSIENT`, and a test forbids a third copy), and a
telemetry write never decides a job's outcome, so health notes retry but never
defer. The one exception is a `running` note published as a PRECONDITION — that
used to hard-raise, which made the health ledger's own availability a
precondition for the job; `source_health.require_running_note` now defers when
the host never answered and still raises when it refused the write.
**The month's budget is spent - what happens now**
`ops_status.py [2a]` shows month-to-date at or past the stop line, or a job log
carries `::warning::spend: the $7.00 monthly cap is spent`.

**What stops.** Paid model calls, and only those. `spend.month_gate()` returns
blocked, `paid_reads_enabled()` returns False, and every paid call site in the
repo routes through it: `extractor.py`'s six paid functions, `_get_client()`
itself, and the five scripts that build their own OpenAI client
(`ai_evidence_sweep`, `process_tips`, `source_verification_audit`,
`daily_classification_spotcheck`, `dedupe_llm`).

**What keeps running.** Everything that does not call a model, which is most of
what this tracker collects: WARN scrapers, SEC/EDGAR structured fields, ERM, the
seen-URL pre-check, all server-side dedup, every WordPress surface. A deferred
candidate writes no row, so its URL never enters the record, so the next run
pulls it again. **This costs depth for the rest of the month, never coverage.**

**Nothing goes red.** A budget stop is a decision, not a failure. Jobs exit 0
and record a TRUNCATED ledger entry (`complete: false` plus the reason), so the
stop is visible in `railway/spend_jobs.json` rather than looking like a quiet
day.

| What you see | What it means | What to do |
|---|---|---|
| `the $7.00 monthly cap is spent: $6.xx used` | MEASURED month-to-date at the 90% stop line | Nothing is broken. Either wait for the 1st (the balance job takes the new month-start snapshot and paid reads resume by themselves), or take the owner the cut-list in `[2a]` and change `MONTHLY_ALLOWANCE_USD` - **a budget change is the owner's call, never a session's**. If the owner does raise it: the key carries a **$20 PROVIDER limit**, and the policy cap must stay strictly under it. At parity our graceful degrade never fires and the provider hard-stops a run mid-call instead. Raise the provider limit first, then this |
| `month-to-date for 2026-08 is UNKNOWN (no-baseline...)` | No committed month-start for this key here | UNKNOWN, not a pass, and not a fault. The per-run ceiling is what is enforcing. Check the daily `openrouter-balance-check` workflow is green - it is the one job that commits `railway/spend_month.json` |
| `this run is TRUNCATED, not complete` | The run stopped at its per-run ceiling or its deadline | Expected under throttle. What it did not reach is **deferred, not decided** - do not read its counts as a full pass over the queue |
| A job spent past its ceiling in `[2a]` | The brake leaked | This is a defect, not a budget question. **First check WHICH ceiling the line names**: since 2026-08-14 each ledger entry carries `ceiling_usd`, the ceiling that run actually ran under, so a dispatch with an authorised `ALT_RUN_CEILING_USD` override is judged against its own number. A line ending "(its named ceiling; that run recorded none)" is an entry written before that field existed - read the run's own log before treating it as overshoot. **If it is real**: every paid call must go through `spend.metered_call()`, which checks the brake immediately before the request and meters immediately after. A job that overshoots by more than ONE call's cost has a call site outside it, or a `make_call` that loops or retries internally - that puts several charges behind one gate read, which is the once-per-item defect wearing a different hat. `tests/test_spend_brake_granularity.py` holds both halves |
| `[2a]` prints a **"not judged"** block | The run recorded no ceiling and its job has no named one, so nothing could be compared | **UNKNOWN, not an overshoot and not a pass** — do not treat it either way. It is deliberately not an ACTION item. `railway-cron` is the only job that has ever appeared here: it is absent from `JOB_RUN_CEILINGS_USD` on purpose (it keeps the global `RUN_CEILING_USD`), and until 2026-08-15 the Railway road dropped the recorded ceiling at both ends. **The Railway ledger entry travels through THREE hand-written field lists** — `record_job_run()` builds it, `db.php`'s `add_spend_run` whitelist stores it, `spend.harvest_railway_runs()` reads it back — and a field missing from either of the last two is dropped with no error anywhere. `tests/test_spend_ceiling_is_recorded.py` fails if they disagree. If this block names a job whose entries are all recent, that test should already be red; if it names only old entries, they age out of the 14d window on their own |

**A BACKFILL IS SLOWED, NOT STOPPED — and that is a different message.**
Since 2026-08-13 every paid job is either COMMITTED (staying current: collect,
WARN, SEC, GDELT, news, health, integrity) or DISCRETIONARY (catching up: the
`backfill_*` family, the enrichment sweeps, `ab-extraction-models`), listed in
`spend.COMMITTED_JOBS` / `spend.DISCRETIONARY_JOBS`.

| What you see | What it means | What to do |
|---|---|---|
| `'edgar-history-sweep' is THROTTLED to $0.06 of its $0.150 named ceiling (41% of normal)` | The month is lean. The rationer shared what is left across the discretionary jobs | **Nothing.** The sweep still runs, sweeps less, and resumes where it stopped. Do NOT raise the ceiling to "unblock" it - the throttle is the budget working |
| `'edgar-history-sweep' is SKIPPED this run. NO HEADROOM...` | The committed path's projection has claimed the whole remaining allowance | **Nothing is broken and the job exits 0.** Catch-up work waits for the 1st. If it is skipping every day and coverage matters more than the ceiling, that is a **priced decision for the owner**, not a session's edit |
| `the $X override for 'job' is CLAMPED to $Y` | A `run_ceiling_usd` dispatch input asked for more than the month has left | Expected. The override still works up to the headroom. Six unclamped dispatches are what cost $0.884 in 26 hours on 2026-08-12/13 |

**Do not answer a throttle by reclassifying a backfill as COMMITTED.** That
moves it in front of the collectors, which is the exact failure this split
exists to prevent. The lever is `MONTHLY_ALLOWANCE_USD`, and it is the owner's.

**Do not "fix" a budget stop by making the coverage smaller.** Costs and
coverage are the same dial here. Slowing a QUEUE-DRAINING job (industry-backfill,
reason-backfill, enrich-roles, enrich-context, reclassify-legacy-ai) only drains
a backlog slower and cannot miss anything. Slowing a DISCOVERY job
(supplemental-news, company-watchlist, distress-watchlist, ai-evidence-sweep,
news-catchup) is a real chance of noticing an event later or not at all. That
second trade is the owner's to make - `earned_skip()` refuses to make it
automatically, and so should you.

**A deploy is not reaching readers**
`ops_status.py` section `[1b]` said `FAIL`, or the deploy workflow's "Verify the
deploy has reached READERS" step went red. The symptom is that the site is
correct to anyone who checks it and wrong to everyone who reads it.

First, understand why every other check will disagree with this one. A reader
requests the bare URL, `https://asktherecruiter.com/blog/ai-layoff-tracker/`,
with no query string. That is the only key a shared cache holds an entry for.
Every check that appends `?cb=`, `?deploy_check=` or anything else is asking for
a key nothing has cached, so the **origin** answers it, every time, correctly.
Those checks confirm the plugin is installed. They say nothing about what is
being served.

1. **Look at the reader's surface, on purpose.**
   ```bash
   python3 railway/reader_freshness.py
   curl -s -D- -o /tmp/p.html \
     -A 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36' \
     'https://asktherecruiter.com/blog/ai-layoff-tracker/' \
     | grep -iE 'x-cache-status|cf-cache-status|age|cache-control'
   grep -o 'ver=[0-9.]*' /tmp/p.html | head -1
   ```
   Compare that `ver=` against `/wp-json/layoffs/v1/status`, which is
   deliberately no-store and therefore the origin's own answer.

   **And read the build stamp, which is the half a version number cannot tell
   you.** The page carries `<!-- alt-build ver=X build=Y -->`, emitted by
   `alt_template()` from a hash of the plugin's own files at render time, and
   `/status` reports the same hash for the bytes on disk now:
   ```bash
   grep -o 'alt-build ver=[0-9.]* build=[0-9a-f]*' /tmp/p.html
   curl -s -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' \
     'https://asktherecruiter.com/blog/wp-json/layoffs/v1/status'
   ```
   Same version, different build, is the **2.20.21 shape**: a page rendered
   while FTPS was still uploading, so the file carrying `ALT_VERSION` had landed
   and a template had not, and the page cache stored the result. That page is
   at the ORIGIN (WP Super Cache), which is the one layer a deploy can purge:
   bump the version and let `alt_flush_caches_on_deploy()` fire. Confirm with
   the `--resolve` command in step 2 before assuming which layer holds it.

2. **Establish which layer is stale.** There are three, and they fail
   differently:

   | Layer | Header it sets | Can a deploy purge it? |
   |---|---|---|
   | Cloudflare | `cf-cache-status` | No. There is no Cloudflare API token in this repo's secrets, on purpose. |
   | Railway proxy (fronts `/blog`) | `x-cache-status` | No. Different app, not this repo. |
   | Bluehost + WP Super Cache | none of the above | Yes, `alt_flush_caches_on_deploy()` |

   To see the origin alone, bypass the two you cannot purge:
   ```bash
   curl -s -k --resolve 'asktherecruiter.com:443:50.87.170.37' \
     -A 'Mozilla/5.0 ...' 'https://asktherecruiter.com/blog/ai-layoff-tracker/' \
     | grep -o 'ver=[0-9.]*' | head -1
   ```
   If the origin is correct and the reader's view is not, the fault is above the
   origin and **no PHP cache flush will reach it**. That was the whole of the
   2026-08-05 incident.

3. **The lifetime is the only lever we hold.** Because neither shared cache can
   be purged from here, how long a reader can be behind is set entirely by the
   page's own `Cache-Control`, in two places that must agree:
   `alt_public_page_cache_headers()` in `includes/shortcodes.php` and the page
   `<If>` block in `includes/htaccess.php` (Apache's block runs last and wins,
   so if they disagree the PHP one is decorative). `railway/tests/
   test_deploy_reaches_readers.py` pins them together.

4. **Do not add `stale-while-revalidate` back to the page.** It is latency
   optimisation paid for in staleness we cannot purge, and the windows of the
   two chained caches **add** rather than overlap. `stale-if-error` gives the
   outage protection people actually want from it and only applies when the
   origin is failing.

5. **Do not answer this by disabling caching.** The API edge cache was measured
   working (same URL twice: MISS then HIT) and is a real speed win on a shared
   host that 504s under load. The page and the API are tuned separately for that
   reason.

**A data-integrity check is failing (START HERE — this outranks a broken source)**
`ops_status.py` section [3] said `FAILING`, or a red `Live data-integrity check`
run, or an email subject beginning "WRONG NUMBER LIVE". **Do this before any
source-staleness item.** A stale collector means data we have not gathered yet; a
failing integrity check means the live tracker, the press page and the public API
are serving a **wrong number to readers right now**.

The invariants live in `railway/data_integrity.py` (`INVARIANTS`) and are shared
verbatim with `railway/tests/test_dedup_live.py` — one definition, so the guard
and the dashboard can never disagree. Each says a known duplicate event must
count **once**.

1. **See it.** `python3 railway/data_integrity.py` — prints each check, the
   observed number, its bound and what a breach means. No keys, no deps.
2. **Do not "fix" the bound.** The bounds are tripwires set just above a value a
   specific double-counting bug produces. Raising one to whatever the site
   currently says silences the alarm and keeps the wrong number. If you believe a
   bound is genuinely wrong, that is a deliberate, documented change with the
   reasoning written into the `Invariant`.
3. **Find which dedup pass broke.** The `regression` string on the failing
   invariant names it: news-vs-news exact-count, news-vs-WARN superset, or
   within-WARN revision. All three live in `alt_reconcile_supersets()` in
   `wordpress-plugin/ai-layoff-tracker/includes/db.php`.
4. **Inspect what the reconciler sees.** Dispatch `reconcile-supersets.yml` with
   `dry_run` + `detail=1` (and `probe=<employer>` to dump the rows it loads for
   one company). Compare `jobs_before` / `jobs_excluded` / `jobs_after`; a
   non-zero `changes` on a quiet day is drift.
5. **Fix, deploy, re-verify live.** Bump `Version:` + `ALT_VERSION`, push, wait
   for the deploy run matching your SHA, then re-run step 1. Do not trust a green
   tick — the data can regress with no commit at all (that is how the 2026-07-30
   Spirit defect appeared: a running all-time WARN sum crossed a threshold).
6. **If it says UNKNOWN, not FAILING**, nothing was verified — that is not a
   pass. Re-run somewhere with network access to `asktherecruiter.com`.

**Closing a headline incident (the only way a movement FAIL ends)**

A FAILING `headline_movement` slice opens a sticky incident in
`railway/headline_incidents.json`, and from then on that slice reports FAIL
because the incident is open — not because today's arithmetic still says so.
That is deliberate. Every input the movement formula uses drifts in the
forgiving direction while an incident sits: `floor = move_floor * span` grows
with the elapsed span, `allowance = |Δentries| * base_mean * mean_factor` grows
with every later arrival however unrelated, and a baseline pinned past
`MAX_BASELINE_AGE_DAYS` used to age into a recordable UNKNOWN. Together those
gave the open US incident a scheduled self-erase on **2026-08-22** with no human
in the loop. Now: time does not close an incident, later rows do not close an
incident, a stale baseline does not close an incident, and neither does deleting
the ledger (an unreadable ledger is UNKNOWN-and-suppressed, never a pass).

See what is open: `python3 railway/data_integrity.py --incidents`.

Close it only once you can name the cause and the rows:

```bash
python3 railway/data_integrity.py --close-incident us_all_time --reviewed-by "<who>" --reason "<what you found, at least 40 characters of finding>" --rows "4411,4412" --replacement-jobs 6975000 --replacement-entries 43359
```

All five are required and the command writes nothing if any is missing. The row
IDs are the real bar: if you cannot name the rows the move was made of, the
cause has not been found and the incident is not resolved. The replacement
baseline is the figure **you assert is correct**, typed out — adopting whatever
the live API answers at closing time is the same laundering with a person
standing next to it. On success, commit BOTH `railway/headline_incidents.json`
and `railway/headline_baseline.json`; the guard is armed against your figure
from the next run.

**`headline_containment` says UNJUDGED — the pair is not one observation**

The detail reads "the two baselines come from DIFFERENT recorder runs" (or
"carries no recorder-run stamp"). That is UNKNOWN, not a pass and not a
breach: each baseline entry carries `recorded_in`, the recorder run that wrote
it, and the check subtracts two slices only when both stamps match. Anything
applied to the data between two runs — a signed-off correction is the measured
case — otherwise sits inside their difference and gets reported as a re-scoring
that never happened (2026-08-14: -53,476 jobs asserted every run while the US
slice had not moved a job).

**Do nothing.** It clears itself on the next `data-integrity.yml` run, which
records the whole containment group together under one stamp. If it does NOT
clear, something in the group is being held — read the recorder's notes
(`python3 railway/data_integrity.py --record-baseline` output, or the workflow log) for
`HELD WITH ITS PAIR`, find the member that cannot advance, and resolve that:
usually an open incident, closed the normal way above. Never hand-edit
`railway/headline_baseline.json`, and never re-add a skew tolerance — a window
cannot be sized for a human correction, which is the bound that failed.

**`recall_floor` is the one invariant that works the other way round.** Every
other check asks whether a published number is WRONG; this one asks whether a
number is MISSING, and it is the only one that reads a committed file rather
than the live API (re-measuring is ~60 requests, and ops_status is on the
critical path of every session's first command).

- **FAILING** means the tracker has LOST events an editor confirmed it held —
  the gold set is frozen, so this is never sampling noise. The detail names the
  events. Check the last `/bulk-purge`, the last `reconcile-supersets` run, and
  whether an employer was renamed (the match is a token-prefix on company name,
  so "Alector LLC" -> "Alector Inc" is fine but a rebrand is not). Fix the cause;
  do not lower `MATCHED_FLOOR`.
- **UNKNOWN** means the measurement is missing or older than 9 days, which means
  `recall-precision.yml` has stopped. Check that workflow before anything else,
  then `python3 railway/recall_goldset.py --write` and commit.
- **The 42% it reports is not a claim.** It is recall against ONE source family
  (US public companies filing 8-K Item 2.05 with an explicit count) over ONE
  twelve-month window at n=57, interval [30%, 55%]. Never quote it as "our
  recall", and never post it to `/benchmarks/recall` — that endpoint is reserved
  for a sample that has been through the three-reviewer chain in
  `docs/RECALL_BENCHMARK_PROTOCOL.md`, and this set has not.

**Which check failed, and what each one wants you to do**

The registry holds two kinds of check. The first four are **named-event
tripwires** (Coinbase, Spirit, Tyson, AT&T): steps 1-6 above are written for
those. The other three are **shape guards** — they know no event names and cover
the row that has not gone wrong yet. Their playbooks differ:

- **`headline_concentration` — one row is carrying a published number.**
  The detail names the row: share, job count, company and row id. Open that row
  and check it against its own source. Historically this shape has been a count
  misparse (RI 9,891 stored as 98,912), a state TEST notice (AT&T 78,788), or a
  projection filed as an event (Coal India 73,800 "by 2050"). If the row is
  WRONG: `apply-correction.yml` or `trash-rows.yml`, and disclose it in the
  corrections log. If the row is genuinely that big and genuinely correct, that
  is the one case for widening the bound — change `max_share` on that `Headline`
  with the reasoning in the code, and add the new live reading to
  `test_headline_guards.test_every_shipped_headline_has_headroom_over_its_live_reading`.
- **`headline_movement` — a published total moved and no row explains it.**
  The detail gives the before/after, the change in entry count, and what the
  rows that changed could have carried. Δentries near zero with jobs moving is
  the signal: something re-scored rows that were already published. Check, in
  this order, the last `reconcile-supersets` run (its `changes` count on a quiet
  day is drift), any `bulk-purge` / re-import, and `data-corrections`. The
  baseline is `railway/headline_baseline.json`; **do not hand-edit it to clear
  the alarm** — the recorder already refuses to advance a failing slice, because
  recording a bad number makes it tomorrow's normal.
  **If it reads "less than one ingest cycle", that is UNKNOWN, not a failure and
  not a pass.** The baseline is written once a day; a push-time run that lands
  part way through a cycle is comparing against a batch, not a day, and since
  2026-08-02 the check declines to render the plausibility verdict there (see
  `MIN_CYCLE_SPAN_DAYS`). The recorder refuses to advance over that reading too.
  Wait for the 17:30 UTC run, which spans a whole cycle and judges it in full.
  A headline of zero and a headline moving on Δentries == 0 still FAIL at any
  span, so the defect class this guard exists for is not affected.
- **`dedup_denominator_scoped` — the structural guard came off.**
  Offline and instant: it asserts that `alt_reconcile_supersets()` in db.php
  still cannot compute a sum of its own, that its denominator can only come from
  `alt_dedup_window()`, and that `alt_dedup_subset_verdict()` still throws when
  handed anything not window-scoped. A failure means someone reintroduced an
  inline share comparison or a local sum. That is the exact 2026-07-30 shape;
  restore the helpers rather than re-fixing the arithmetic.

**"Not watching yet" is not "fine".** If `ops_status` prints `NOT WATCHING YET`
or a check reads PENDING, the guard is armed in the code but has nothing to read:
either the deployed plugin predates the field (wait for a green Deploy run) or
the first baseline has not been written (`python3 railway/data_integrity.py
--record-baseline`, or wait for the 17:30 UTC job). Exit code 3, never 0.

**If a shape guard proves noisy in its first weeks:** raise its `move_floor` and
write down why, in the commit message and in TECHLOG. Do not delete the check and
do not fit the bound to whatever today's move happened to be. **And before you
touch a floor, check whether the noise is a bound problem at all**: the 2026-08-02
`headline_movement` noise was a TIMING problem (a push-time read taken inside a
five-hour backfill), and raising the floor would have bought quiet at every hour
of the day for a defect the floor was correctly sized to catch. `max_share` bounds
were measured against live readings; `move_floor` values were reasoned from the
failure modes, because until `headline_baseline.json` existed nothing had ever
recorded this site's day-over-day deltas.

**A data source broke — you got a "data source(s) need attention" email (START HERE)**
The weekly `health-digest` emails info@asktherecruiter.com when a collector goes
STALE (stopped reporting) or degraded (usually a scraper returning 0 because a
third-party site changed its layout). The email names the source and includes a
paste-ready instruction.

**First, rule out an environment egress block (30 seconds).** If you landed here
because `ops_status.py` said the live tracker / health endpoint is "UNREACHABLE",
check whether it printed `ENVIRONMENT BLOCK` / exited 3 — that means THIS cloud
environment's network policy denies `asktherecruiter.com` (a proxy 403/tunnel
CONNECT that never reaches the site). That is NOT a broken source and this
playbook does not apply; you can still deploy (see docs/CLOUD-SESSION.md). A real
source breakage is flagged as `STALE`/`DEGRADED` per-source (exit 2), or arrives
by the health-digest email. Only then continue below. To fix:
1. **Identify the collector.** Source id → file:
   - `warn_custom_states` / `warn_custom_legacy` → a state scraper in `railway/sources/warn_new_states.py` or `railway/sources/warn_custom.py` (the email/detail names the state code).
   - `warn_us` → `railway/sources/warn.py` (the open `warn-scraper` lib) + `railway/warn_import.py`.
   - `gdelt` → `railway/sources/gdelt.py`; `google_news` → `railway/sources/google_news.py`; `news_catchup` → `railway/news_catchup.py` (weekly; uses `sources/newsapi.py`, whose twice-daily `newsapi` collector identity is RETIRED); `edgar` → `railway/sources/edgar.py`; `eurofound_erm` → `railway/erm_import.py`.
   - `supplemental_news` → `railway/supplemental_news.py`; `company_watchlist` → `railway/company_watchlist.py`; distress/foreign → `railway/distress_watchlist.py` / `railway/foreign_filings_ingest.py`.
2. **Confirm the breakage.** Run that workflow with `dry_run=1` (Actions tab → the workflow → Run workflow) and read the log. A `0 notices`/`HTTP 4xx`/`::warning::` line confirms drift.
3. **Re-recon the site.** `curl` the state's official WARN URL (from the Sources page or `warn.py`/`warn_new_states.py`) and diff the HTML/PDF structure against what the parser expects (selectors, table columns, download links). State sites redesign a couple times a year — the fix is almost always updating the parse selectors or the fetch URL.
4. **Fix + verify.** Update the parser, `python3 -m py_compile` it, re-run `dry_run=1`, confirm sane company/count/date rows, then let the scheduled run post live. Dedup makes re-runs safe (WARN is hash-idempotent).
5. **If a state has genuinely gone dark** (site retired, data now confidential): move it to the gap-states list in `templates/page-sources.php` with an honest reason, and add its code to `_BENIGN_STATES` in `railway/health_digest.py` so it stops alerting.
Transient degradeds (`gdelt_historical` HTTP 429) self-retry and are excluded from the email (SOFT_DEGRADED) — no action needed.

**Page shows an old design / changes not visible**
1. It's almost always cache. Hard-refresh (Cmd+Shift+R). 2. Confirm what the server
sends: `curl -s "https://asktherecruiter.com/blog/ai-layoff-tracker/?cb=$RANDOM" | grep -o 'ver=[0-9.]*' | head`.
3. If server is stale, trip the flush URL above (works only if the version was bumped).
4. Autoptimize is NOT flushed on deploy (by design since v2.7.3 — content-hashed
filenames self-invalidate). If an AO asset looks stale, the version bump alone fixes it.

**Company directory page is missing or should not be indexed**
1. Unknown, pending or ambiguous `/company-layoffs/{slug}/` paths must return 404; do not add a freeform alias to make one resolve.
2. Confirm the reviewed registry row has the intended stable slug, canonical company key, display name and review status. A raw dedup key alone is not an identity decision.
3. Confirm every displayed canonical event retains at least one valid source URL. Approved records need two or more such events to index; otherwise use the reviewed `noindex` status.
4. A versioned deployment rebuilds the directory rewrite rule once after its template is present. Verify a known reviewed slug, an unknown slug (404), and the resulting robots directive after deploy.

**White screen / HTTP 500 anywhere**
A PHP fatal from the latest deploy. `git revert` the last plugin commit, push, trip flush.
Balance-check PHP before deploying (see CLAUDE.md); there is no staging environment.
If EVERY URL 500s (not just plugin pages), also suspect `/blog/.htaccess`: remove the
`# BEGIN AI Layoff Tracker` block over FTP (the plugin's writer canary-probes and
rolls back on its own, but a half-written file from an unrelated crash cannot).

**API returns stale numbers**
Micro-cache holds 5 min. Any write bumps `alt_data_ver`; manual bump: run the `cleanup`
workflow. Browser-side: check the Cloudflare cache rule's Browser TTL (must be
"Respect origin" — origin sends `max-age=300` on the API since the `.htaccess`
override; browsers may serve up to 5-min-old numbers by design).

**Duplicate Cache-Control returns (API/page sends `public, max-age=…` AND `no-cache, no-store…`)**
Bluehost's Apache injects the no-store trio after PHP's headers on every PHP response;
the plugin overrides it with a marked block in the WP root `.htaccess` (managed by
`includes/htaccess.php`, self-healing on init, canary-probed, auto-rolls-back on 5xx).
1. Check state: option `alt_htaccess_state` (`status: verified|failed`, `reason: write|probe`).
2. Check the file: the `# BEGIN AI Layoff Tracker` block must exist in `/blog/.htaccess`
   (view over FTP). If the host or another plugin rewrote the file, the init hook
   restores the block within 12h; to force it now, delete transient `alt_htaccess_ok`
   and option `alt_htaccess_state`, then hit any page.
3. If `status: failed` with `reason: probe`, a write made the site 5xx and was rolled
   back — the block only re-attempts on the next `ALT_VERSION` bump. Investigate before
   bumping (Apache error log via cPanel).
4. Verify with GET, not HEAD: `curl -sS -D - -o /dev/null -A 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)' ".../aggregate?cb=$RANDOM" | grep -i cache-control`
   must show exactly ONE header. `cf-cache-status` on HEAD always reads DYNAMIC
   (Cloudflare serves cached GETs only) — that alone is not a failure signal.
5. If the trio ever comes back at a layer `.htaccess` can't reach (front proxy),
   fallback: Cloudflare Response Header Transform Rule setting Cache-Control for
   `/blog/wp-json/layoffs/v1/*` (owner action, document in TECHLOG infra section).

**Charts empty / filters dead in the browser**
Check the three endpoints directly (`/facets`, `/aggregate`, `/query?per_page=1` with
`?cb=$RANDOM`). If they're fine it's front-end: browser console; JS is
`assets/layoffs.js` (single file, no build step). DataTables/Chart.js load from cdnjs —
a CDN block kills the table (status message says so).

**Table says "No layoffs match" but the API returns rows** (the v2.7.1 crash class)
A render-callback exception is swallowed by the ajax `.catch` and shown as a data
problem. Capture the real stack in the console before touching anything:
```js
var dt = jQuery('#alt-table').DataTable().settings()[0];
var orig = dt.ajax; dt.ajax = function(d, cb, s) {
  return orig(d, function(json){ try { cb(json); } catch(e) { console.error('RENDER CRASH', e); } }, s);
};
jQuery('#alt-table').DataTable().ajax.reload();
```

**Page loads but nothing boots — 0 API requests, table stuck "Loading…"**
The aggregated JS itself is dead. Find the `autoptimize_single_*.js` URL in the page
source and curl it: a 410/404 with `cf-cache-status: HIT` means Cloudflare cached a
missing-file response (24h `max-age`). Origin is usually fine (verify with an extra
`&cfbust=$RANDOM` param, which changes the CF cache key). **Recovery: bump ALT_VERSION
and deploy** — the new `?ver=` is a new CF cache key; never wait out the TTL. Root cause
was deleting AO caches on deploy — removed in v2.7.3, do not reintroduce.

**Import workflow red**
Read the run log. `batch N FAILED: 500` = transient host error → re-run without purge
(idempotent upsert fills gaps). `purge refused` = scrape came back too small — the guard
protecting the table; investigate the states, don't override. Repeated 401 = WP_API_KEY
rotated (wp-admin Tools page ↔ GitHub secret must match).

**A state stopped importing / "no output file for XX"**
Two collector families: `warn-scraper` states (upstream lib — check
https://github.com/biglocalnews/warn-scraper/issues , bump the pin in
`railway/requirements.txt`) and OUR custom collectors in
`railway/sources/warn_custom.py` for TX/FL/GA/OH/MI/CO/ID/LA (state sites change;
fix the collector — each has its endpoint documented inline; GA needs a fresh nonce
per run, CO discovers per-year Google Sheets, ID/LA parse text PDFs).
No-data states (2026-07, not bugs): HI + OK publish no usable counts; MO/NM publish
nothing; MA/MN/NC/NV need custom scrapers nobody has written yet.

**A published number is wrong**
1. Verify against the primary source link. 2. Fix the CAUSE first (parser/normalizer —
else the next import re-creates it). 3. Remove/correct data: single entries →
`trash-entries` workflow; systematic WARN issue → fix parser, then `warn-import` with
`states=all, purge=true`; normalization issue → `cleanup`. 4. **Disclose**: dated entry
in the site's corrections log (templates/page-tracker.php) + TECHLOG. Counts are part of
the dedup hash — corrected counts need the purge path, plain re-import duplicates.

**A label relabel was HELD (you got "N label relabel(s) HELD for review, not applied")**

The daily classification spot-check (`railway/daily_classification_spotcheck.py`,
run by `data-quality.yml` at 15:00 UTC) proposed a country or industry relabel,
its second pass agreed, and it **refused to apply it** because the row is at or
above `AUTO_APPLY_MAX_JOBS` (5,000) or because it moves a row off a guarded
country label like `Multiple countries`. **Nothing was written.** The same mail
lists the row id, the old and new label, the job count and the model's reason,
and the run summary in Actions says the same.

**Doing nothing is a legitimate outcome and is usually the right one.** This
mail exists because on 2026-08-08 that exact suggestion, applied unattended, put
92,000 jobs into the published US headline for four days (TECHLOG 2026-08-12;
`docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md` section 8). A model asked
whether "Citigroup" belongs under "Multiple countries" answers from the
company's nationality, not from where the jobs were cut.

To act on one:

1. **Read the row's own source**, not the model's reason. The mail names the
   company; `curl -s "$API/query?company=<name>&per_page=50"` gives the excerpt
   and `source_url` for it (`/query` filters by company, not by id). For an ERM row the
   excerpt states the country it was **imported** with, which is the fact that
   settles it (`railway/erm_provenance_check.py` reads exactly that).
2. **Only if the source disagrees with the stored label**, dispatch `Apply a
   signed-off correction` (`apply-correction.yml`) with `apply=false`, read the
   dry run, then `apply=true`. That dispatch **is** the human sign-off, and the
   reason you type is appended verbatim to the public corrections log, so write
   it as public copy.
3. **If you decide the stored label is right**, do nothing. `/alert` dedupes by
   the exact set of held ids, so you get one mail per distinct backlog and a
   `STILL FAILING` reminder once a fortnight, never one a day. It clears itself
   the first day the model stops proposing it.

The backlog is **recomputed from live rows every run**, not stored, so there is
no queue to drain and nothing is lost if a mail fails to send. That also means
an unread hold cannot rot into a stale to-do: if it stops being proposed, it
stops being raised.

**An announced plan may have later executed / been filed**
1. Inspect the public `/announcement-lifecycle-candidates` queue. It is only a narrow, read-only lead: exact company/count/country plus a source-evidenced announcement date and a later record within 365 days.
2. Compare every retained source report for both events; confirm the scope, geography and timeline describe the same underlying cut.
3. Only then use the keyed `/merge-events` route with an editorial reason. Never merge from company name or an LLM suggestion alone. The merge keeps every source report.

**Announcement-survey reconciliation fails**
1. Do not change the tracker total to match the benchmark. The comparison is only valid for US-based employers,
   announced cuts, AI-primary cause and canonical events.
2. Open the uploaded `survey-reconciliation` artifact. Record the announcement-survey report URL, tracker query and
   variance in the monthly reconciliation log.
3. Re-run recent GDELT/news/IR overlapping windows, then classification/dedup audits. Missing, duplicate,
   date/count and definition differences must remain separately identifiable.
4. If the official announcement-survey site changes its markup, update `railway/survey_reconcile.py` with a regression
   fixture; do not replace it with a guessed hard-coded total.

**Quarterly report needs correction or rerun**
1. Do not overwrite a published report. Quarterly report ids are immutable so that journalists can reproduce what was published.
2. Check the public report JSON, its `dataset_revision`, source-health snapshot and the current `/quality-status` revision.
3. The report page automatically says when live data have changed since its snapshot. Correct underlying event data through the normal source-preserving correction path; do not alter historical report facts.
4. If a materially corrected replacement is necessary, create an explicitly versioned follow-up report and document its relationship to the original. Do not silently reuse the same quarter id.
5. The report JSON/CSV appendix is derived only from the stored immutable snapshot. If it differs from the page, treat that as a release defect; never regenerate an old appendix from the current live aggregate.

**Contact form not delivering**
Mails go via `wp_mail()` to info@asktherecruiter.com — confirm the mailbox exists in
Bluehost. Form errors surface as `?alt_error=` codes (spam|rate|fields|mail|expired).
Spam getting through → tighten in `includes/contact.php` or add Cloudflare Turnstile
(needs owner-registered keys). Accepted risk (audit #2): math captcha & fill-time check
deter only dumb bots; the honeypot does the real work; rate limit is per-IP 3/hour.

**Site slow / traffic spike**
Per-request floor is ~1.2s WP bootstrap on shared hosting; origin ceiling ≈8 req/s.
Mitigations, in order: (1) Cloudflare cache rule serving the API from edge (check
`cf-cache-status: HIT` on `/aggregate`); (2) page HTML is already super-cached (~0.4s);
(3) if sustained, upgrade hosting — the plugin itself scales (indexed table, micro-cache).

**The coverage comparison is stale**
`ops_status.py` section `[6]` printed `STALE`, or `python3
railway/benchmark_freshness.py` exited 2.

**What it means.** The coverage figure against the independent national survey
is the number a journalist tests first, and it is the one figure in this system
whose other half cannot be automated: that half is competitor data and may not
enter the repo, a secret, a workflow log or any public page. So the comparison
is refreshed by hand in the local-only `scratchpad/bm-live.html`, and the only
thing a machine can watch is **how old it is**. A date is not a figure and names
nobody. That is the whole of what `[6]` checks, and it is deliberately a smaller
claim than "the coverage number is monitored".

Two things can put it in `STALE`:
- **The oldest comparator-side input is 15+ days old** (two missed Mondays of
  the local weekly claim check — one missed Monday only shows `DUE`). The
  *oldest* input governs, not the freshest: a weekly check that confirms one
  cell while a hand-maintained one sits untouched for a month has not refreshed
  the ratio, it has refreshed part of it.
- **A hand-written ratio claim predates the last denominator re-check.** This is
  the one that matters and it is why the section exists. On 2026-08-12 the
  weekly check had moved the denominator on 2026-08-10 while the paragraph
  carrying the headline percentage was still the one typed on 2026-07-27. The
  percentage was correct when written, was never recomputed, and was quoted for
  sixteen days. Nothing in the system could see it.

**Do this.**
1. Run `python3 railway/benchmark_freshness.py`. It prints the dates: which
   inputs are old, and which quoted claims stand on a superseded figure.
2. Open `scratchpad/bm-live.html` **locally**. Re-verify the flagged
   comparator-side inputs by hand against their own published sources.
3. **Recompute every percentage the check flagged, and restamp it with today's
   date.** A claim keeps its old stamp until someone recomputes it — do not
   restamp without recomputing, which converts a stale number into a stale
   number that looks fresh.
4. Re-run the check. Cells with no machine-readable claim page stay
   hand-maintained by design; they simply have to be re-entered on the cadence.

**Never** fix this by widening `COMPARATOR_STALE_DAYS`, and never move the
figures into the repo, a secret, or an Actions log to make them checkable. The
constraint is the owner's standing decision, reconfirmed 2026-08-12, and the
staleness signal is what was built *because of* it, not in spite of it.

## How to ADD a new source (the pattern every collector follows)
Never write to the DB directly. Every source produces "raw entries" and hands
them to the shared pipeline, so it inherits dedup + entity-alias + country/
industry normalization + verbatim-count guard + AI-attribution + quote gate for
free. Steps:
1. **Write a collector** in `railway/` (or `railway/sources/`). Fetch with a
   browser-ish `User-Agent` and a `timeout=`. For each candidate build a raw
   dict with AT MINIMUM `raw_text` (the extractor reads ONLY this and returns
   None if empty — the #1 bug that made a whole source silently post nothing),
   plus `source_type`, `source_name`, `verification_level`, `source_url`.
   Mirror `sources/newsapi.py`'s dict shape exactly.
2. **Route through the guards**: `from extractor import extract_layoff_data`
   then `from wp_poster import post_to_wordpress`. `ex = extract_layoff_data(raw)`;
   if `ex`, `post_to_wordpress(ex)`. That's it — never assemble a row yourself.
   (WARN-style structured feeds that already have company/count/date skip the LLM
   and bulk-upsert via `/bulk`; see `warn_import.py`.)
3. **Ship it DORMANT** if it needs a key: read `os.environ.get("YOUR_KEY")` and
   return early when absent. Add diagnostic logging of the raw API status so the
   first `dry_run=1` reveals shape/auth problems (see `supplemental_news.py`).
4. **Report health**: call `report_source_health(name, "ok"|"degraded", posted, detail)`
   so it appears in the ledger and the weekly digest. Add a matching label in
   `assets/health.js` `meta{}` and, if it's a real public source, a row on
   `templates/page-sources.php`.
5. **Add a workflow** in `.github/workflows/` (copy `supplemental-news.yml`):
   pass the key + `OPENROUTER_API_KEY` + `WP_API_KEY` + `WP_SITE_URL`, set
   `PYTHONUNBUFFERED: '1'`, a `timeout-minutes`, and a `dry_run` input. Add a
   wall-clock deadline in the script if it does per-item news searches (they can
   exceed the job timeout — see `distress_watchlist.py`).
6. Document it: add a row to the workflow table + dormant-key table above, and a
   TECHLOG entry.

## How to FINE-TUNE (env knobs, no code change)
- **Extraction quality**: the AI rubric + guards live in `railway/extractor.py`
  (`_count_in_text` verbatim guard, the timeline/subset prompt). AI precision is
  measured weekly by `recall-precision` (AI-attribution quote-rate); `reclassify-
  legacy-ai` (bump `batch`) downgrades vague legacy AI tags.
- **Coverage breadth**: GDELT segment rotation is `SEGMENT_TERMS` in
  `sources/gdelt.py` (`GDELT_SEGMENT_QUERIES` per run); European sweep toggles
  with `GDELT_EURO_SWEEP`. Watchlist size/window: `WATCHLIST_BATCH`,
  `WATCHLIST_DAYS_BACK`; auto-grow with `WATCHLIST_INDEX_URLS`.
- **Dormant-source limits**: `DISTRESS_MAX`/`DISTRESS_DEADLINE_SECONDS`,
  `FOREIGN_MAX`, `RECLASSIFY_BATCH`, `RP_PRECISION_SAMPLE`.
- **Alert sensitivity**: `railway/health_digest.py` — `MAX_AGE_DAYS` (per-source
  staleness window), `SOFT_DEGRADED` (transient sources that don't email),
  `_BENIGN_STATES` (no-register states that shouldn't alert).
- **Country filter meaning**: `country_basis=any` (table/exports, employer-HQ
  inclusive) vs strict job-location (headline stats). Set in `assets/layoffs.js`.

## How to ENHANCE (bigger moves + their honest ceilings)
- **US WARN**: 48 states + DC already scraped; AR/NH/WY have no public register.
  This lever is maxed.
- **Europe**: per-company data is Eurofound ERM (running) + multilingual news;
  NL/FR/DE publish NO public per-company register (confidential) — not buildable.
- **Benchmark refresh** (survey baselines in the private `gen.py`/`bm-live.html`):
  MUST stay local — competitor names/numbers may never enter the public repo or
  GitHub logs (standalone-brand rule; competitor URLs go in `BENCHMARK_FEED_URLS`
  secret only). A cloud cron would leak them.
- **New-source discovery**: event-gap discovery is automatable (`tracker-diff`,
  needs `BENCHMARK_FEED_URLS`); discovering brand-new source *types* is a human
  judgment call, not a cron.
- **Autonomy ceiling**: ~99%. The irreducible human sliver = repairing a scraper
  when a third-party site redesigns (now auto-detected + emailed), refreshing the
  private benchmark, and novel-source judgment. Do not claim "100% automated".

## Quarterly source-verification audit (the accuracy claim)

What it produces: the number we publish in the FAQ ("How do you check your own
accuracy?"). Run it fresh every quarter, never reuse a seed.

1. Pull the pool from the public `/query` API and draw a **stratified random**
   sample (30 rows/year x warn/news/erm/8K; oversample 8-K, there are few).
   Record the seed. A fresh-model auditor is worth it: it has no memory of why
   a row was built the way it was, which is the whole point.
2. The auditor OPENS every row's `source_url` and grades company + count + date
   against what the page actually says. Verdicts: PASS, WRONG-NUMBER,
   WRONG-DATE, WRONG-COMPANY, DEAD-LINK, REGISTER-LEVEL (the register rolled
   over and no longer exposes the row - an access limitation, NOT a data
   error, report it separately), UNVERIFIABLE.
3. **Re-verify every proposed numeric change YOURSELF before applying it.**
   This is not ceremony. In audit #1 the auditor graded Dow 3,700 as WRONG
   because the cited article headlines 4,500; the row was right (3,700 is the
   net-new portion, the other 800 is a separate retained row, and Eurofound
   records the event as "3,700 - 4,500"). Applying that "fix" would have
   double-counted 800 jobs. **A deliberately reconciled net-new row always
   looks wrong to an auditor reading only the headline figure** - so read the
   row's excerpt for a reconciliation note, and check whether the difference is
   already retained as its own row, before you believe the finding.
4. Apply what survives via the dispatch-only corrections path (dry run first):

```bash
gh workflow run apply-correction.yml -f ids=70289 -f action=trash -f reason="audit #N: <why>" -f verify_company=Starbucks -f apply=false
```

   `trash` when the source supports no count at all; `edit` when a field is
   wrong. Both suppress the original hash so the nightly re-scrape cannot
   resurrect the row, and both append to the PUBLIC corrections log
   automatically. Re-run with `apply=true` once the dry run shows the right row.
5. **Also run `python3 railway/erm_provenance_check.py`** (read-only, keyless).
   It reads the country each ERM row was IMPORTED with back out of its own
   excerpt and reports every row that no longer agrees, which is how three
   already-published Eurofound rows were caught silently re-scored to "United
   States" on 2026-08-11 (docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md
   section 8). A sample audit cannot find this class; it is 3 rows in 19,494.
   Unreadable excerpts are reported as UNCHECKED, never as clean.
6. Update the published accuracy figure in the FAQ and log the audit in
   TECHLOG under "## Audits". Report register-level rows separately from real
   errors, and say what you could NOT verify.

## Monthly coverage audit (the gap-closing loop)

The daily pipeline collects; this loop finds what the pipeline is BLIND to. Run
it monthly. It is the only reliable way to discover a structural blind spot,
because a blind spot by definition does not show up in our own data.

**Step 1 - research the thin sectors.** Dispatch one agent per weak sector (use
the private benchmark to pick them). Brief each with these NON-NEGOTIABLE rules,
which exist because looser ones produce unusable rows:
- an EXACT headcount (reject ranges, "hundreds", percentage-only)
- a date inside the target window
- a NAMED source: major outlet, official company release, or an SEC filing
- NO layoff aggregators as sources (some of their figures are provably fabricated)
- the agent must OPEN the article to confirm number + date. Search snippets
  routinely misdate 2025 events into 2026.

**Step 2 - DEDUPE BEFORE YOU SEED. This is the step that matters.** In the
2026-07 run, 36 of 69 researched events were ALREADY in the tracker (58% of
auto/food, 79% of tech). Seeding blind would have double-counted every one.
Query `/query?company=<name>` per candidate and compare. Two traps:
- **Window too narrow.** A +/-75 day window marked Oracle 21,000 as NEW; we held
  it 77 days away at a different date basis. ALWAYS re-check any big candidate
  against EVERY row for that company in the year, not just a date window.
- **Announced vs executed.** If we already hold a company's WARN execution
  slices (Meta 2,212 + 1,395 + ...), seeding the company-wide announcement
  (Meta 8,000) counts the same people twice. Skip it, or use the announced tier
  deliberately - never mix them.

**Step 3 - seed the survivors** via `seed_data/<name>.json` +
`backfill-seed.yml` (dry_run=1 first). It is idempotent and dedup-guarded
server-side, which caught one more duplicate the client check missed.

**Step 4 - THE PART PEOPLE SKIP: diff the SOURCES, not just the events.**
Tabulate the `source_name` of everything you had to seed. In 2026-07 that single
table was the most valuable output of the whole audit: we already held every
national-wire story, and every event we MISSED ran only in a state business
journal or a vertical trade publication (NJBIZ alone carried 4 of 29). Seven of
those ten outlets were not in the allowlist at all. The events were a symptom;
the allowlist was the disease. Add the missing outlets to `TRUSTED_DOMAINS` so
next month the pipeline catches them automatically - that converts a manual
backfill into a permanent capability.

**Step 5 - re-measure and record.** Before/after by month and by sector, into
TECHLOG. If a sector barely moves, ask whether the data is present but
UNLABELLED before going to find more of it: in 2026-07, 96% of US rows carried
no industry (72% of job volume), so the by-industry view under-reported reality
far more than collection did.

**What this loop can NEVER close (stop trying):**
- Receiptless categories (buyouts, contract loss, bankruptcy, federal/DOGE) -
  the announcement survey gets these by ASKING employers; we require a document.
- Announcement-vs-effective date basis - a definitional difference, not a gap.
- Employers who withhold headcounts. In H1 2026 media, only one US event had a
  public number; the rest deliberately withheld. That cell cannot go green.

## Adjudicating the SEC Item 2.05 gold set (the only way recall moves)

`recall_goldset.measure()` counts an event only where the manifest says
`matched`. When a collector fix makes the tracker acquire a row for a
not-matched gold event, the run reports it under
`candidates_needing_adjudication` and does NOT count it - "a machine must not
promote its own recall". The published figure moves when a person decides, and
this is how.

**1. Rebuild the evidence, do not trust the last build.**
```bash
python3 railway/recall_adjudication_pack.py --write
```
Read-only. Re-fetches every proposed row from the public `/query` and every
filing from SEC EDGAR, and writes
`docs/recall-reference-sets/sec-item-205-adjudication-queue.{json,md}`. Nothing
in it is copied from `match_notes` or `count_evidence`: the manifest is the
thing being audited, so its own strings are quoted for comparison and never
relied on.

**2. Read the sheet** (`...-adjudication-queue.md`). One block per pending
event: the filing's own sentence stating the count, our stored row, whether the
counts and the dates agree, and every flag worth a second look. It is ordered by
how much there is to CHECK, not by how likely an accept is - the first entries
are the ones where nothing disagrees, which makes them fast to verify and says
nothing about whether they are right. There is no recommended answer anywhere in
it, deliberately.

Two things the sheet will show you that are not errors:
- **A date that disagrees on one basis only.** `announcement_date` is the filing
  basis and `layoff_date` is the effective basis. An effective date months after
  the filing is normal (`Koppers`, `Molson Coors`, `Hormel` all sit on
  `2025-12-31`/`2026-12-31`) and is not a mismatch of fact.
- **A count that is the filing's OTHER number.** Goodyear's 8-K states 600 gross
  and 400 net in one sentence; we hold 400 and the gold set holds 600. The sheet
  quotes the sentence twice rather than picking.

**3. Record each decision.** One command per event, and it writes the manifest
and the ledger together:
```bash
python3 railway/recall_adjudicate.py --queue          # what is pending
python3 railway/recall_adjudicate.py --show <ref_id>  # one evidence block, raw
python3 railway/recall_adjudicate.py --accept <ref_id> \
    --reviewed-by 'Name' --reason 'what in the filing and the row decided it' \
    --event-ids 149909
python3 railway/recall_adjudicate.py --reject <ref_id> \
    --reviewed-by 'Name' --reason '...' --event-ids 149625
```
`--event-ids` takes every value until the next flag, so `--event-ids 149625
149911` records both. A blank reviewer or a blank reason is REFUSED with nothing
written. Re-running the same decision writes nothing and exits 0; a DIFFERENT
decision is refused until you revert.

**4. Changed your mind: revert, never re-edit.**
```bash
python3 railway/recall_adjudicate.py --revert <ref_id> \
    --reviewed-by 'Name' --reason 'why the first reading was wrong'
```
Restores the event byte for byte from the ledger's snapshot and appends the
reversal. It never deletes the decision it reverses; both readings stay on the
record.

**5. Commit the manifest AND `railway/recall_adjudications.json`**, then
re-measure:
```bash
python3 railway/recall_goldset.py --write
```
That is the run that moves the published figure, and only accepted events move
it.

**Never hand-edit `match_decision`.** `recall_adjudicate.py --verify` fails on
any `matched` event that carries neither an `adjudication` block nor membership
in the 24 an editor decided on 2026-08-01, and
`tests/test_recall_adjudication.py` runs it against the committed files - so a
hand-promoted event reddens CI instead of quietly raising the coverage claim.

**`MATCHED_FLOOR` is not touched by an adjudication.** It is the tripwire for
losing events we hold, and moving it in the same breath as raising the numerator
turns it into a rubber stamp. Raise it, if at all, in a separate change with the
reasoning in TECHLOG.

## Adjudicating the US WARN reference set

Same gate, same four properties, a different set. `warn_reference_set.measure()`
counts an event only where the manifest says `matched`, so the 99/100 and the
33/33 it reports are a MACHINE UPPER BOUND and must never be quoted as recall.
This is how a person turns some of it into a number.

**The mechanism is shared with the SEC set on purpose.** Both recorders are
`railway/adjudication_ledger.py` plus a profile; the first WARN recorder had its
own copy and got three of the four properties wrong (it appended a ledger entry
on every invocation, it had no `--revert`, and it had no `--verify`). Two
adjudication tools that drift apart is a worse outcome than one slightly awkward
one. Fix a property once, in the core, and both sets get it.

**1. Rebuild the evidence, do not trust the last build.**
```bash
python3 railway/warn_adjudication_pack.py --write
```
Read-only, no key, no model, ~500 public `/query` GETs. Writes
`docs/recall-reference-sets/us-warn-adjudication-queue.{json,md}`.

**2. Read the sheet.** For each event it puts the state's own notice and our row
side by side: employer, notice date, published effective date(s), affected
count, source document, our row id, our count, our date, our `source_type` and
the URL we cite. Then whether the counts match exactly and **by how much they
differ if not**, and which **date basis** the row agrees on.

Two things it shows that are NOT errors:
- **A row date months from the notice date.** WARN publishes a notice date and
  an effective date; we store the effective one in `layoff_date`. A gap between
  them is the other basis, not a mismatch, and the sheet names the basis rather
  than calling either wrong.
- **A stored employer name shorter than the published one.** Three of the four
  states glue the site address into the employer cell (`Spirit Airlines Miami
  International Airport located at 4200 NW 42nd Avenue MIAMI, FL, 33142`). We
  store `Spirit Airlines`. That is a naming artifact of the state's file.

**Every line of the sheet describes exactly ONE row, named by its id.** An event
with four candidates gets one index line for the row the rule proposes first,
carrying only that row's evidence, and the ids of the other three beside it
carrying none of theirs; each of those gets its own block below. That is the Dow
failure written as a layout rule - on 2026-08-12 a pooled line described a
co-proposed row and a correct row was rejected because of it.

**3. Record each decision.** Network-free, and it names ROW ids, not event ids:
```bash
python3 railway/warn_adjudicate.py --queue          # what is pending
python3 railway/warn_adjudicate.py --show <ref_id>  # one evidence block, raw
python3 railway/warn_adjudicate.py --accept <ref_id> \
    --reviewed-by 'Name' --reason 'what in the notice and the row decided it' \
    --row-ids 137699
python3 railway/warn_adjudicate.py --reject <ref_id> \
    --reviewed-by 'Name' --reason '...' --row-ids 137699
python3 railway/warn_adjudicate.py --revert <ref_id> \
    --reviewed-by 'Name' --reason 'why the first reading was wrong'
python3 railway/warn_adjudicate.py --verify
```
`--row-ids` takes every value until the next flag. A blank reviewer or reason is
REFUSED with nothing written. The same decision twice writes once. A DIFFERENT
decision is refused until you revert, and a revert restores the event byte for
byte including the `adjudicated_*` mirror fields.

**4. Commit the manifest AND `railway/warn_recall_adjudications.json`**, then
re-measure:
```bash
python3 railway/warn_reference_set.py --measure
```

**Never hand-edit `match_decision`.** `--verify` fails on any `matched` event
with no named decision behind it, across BOTH the sample and the 500-plus
census, and `tests/test_warn_adjudication.py` runs it against the committed
files.

**This set cannot move the SEC figure and must not be made able to.** Different
manifest, different ledger, different measurement file. One test drives a real
WARN decision and then asserts `recall_measurement.json`,
`recall_adjudications.json` and the SEC manifest are byte-identical afterwards;
another asserts no WARN module can even name them.

**The sample and the census are never pooled.** 100 systematic events and 33
large-cut census events are two figures. Deciding a census event moves the
census figure and nothing else.

## The email digest: arming the sender

The signup half has been live and complete for a while: double opt-in, token
confirm links, one-click unsubscribe, a 30-day retention purge and a keyed
counts-only `/subscriber-stats` route. What did not exist until 2.20.51 was
anything that reliably puts a digest on the wire. `wp_mail` on shared hosting
is the weakest link in a delivery chain, so the digest now goes out through a
real relay, driven by `digest-send.yml` -> `railway/digest_send.py`.

**It is DORMANT and cannot send.** With no transport secret the job resolves to
the dry-run transport, prints the exact messages it would have sent, and exits
0. That is a state, not a failure, and it must never be made a red run.

### The three things only the owner can do

Nothing sends until all three are done. Steps 1 and 2 are unavoidable with any
provider: SPF and DKIM are how deliverability works, and a From address on an
unverified domain lands in spam whoever relays it.

1. **Create the Resend account** at resend.com and add the sending domain
   `asktherecruiter.com`. **Decide open and click tracking deliberately**, and
   see "Open and click tracking" below: as of 2026-08-16 it is ON in Brevo by
   the owner's decision, and three strings in the product say so. Nothing in
   this repo can read that dashboard setting, so the copy is coupled to it by
   hand and has to be changed by hand.
2. **Add the DNS records at the registrar.** Resend shows the exact values:
   a DKIM `TXT` record on a `resend._domainkey` subdomain, an SPF `TXT` record
   on a `send` subdomain, and an MX record on that same subdomain for bounce
   feedback. Verification usually completes within an hour of propagation.
   Take care not to replace an existing SPF record on the root domain; the
   records Resend asks for sit on the `send` subdomain and do not collide.
3. **Add `RESEND_API_KEY` as a repository secret** (Settings, Secrets and
   variables, Actions), then change `DIGEST_TRANSPORT` in
   `.github/workflows/digest-send.yml` from `dryrun` to `resend`.

Then run the workflow by hand once with `dry_run: 1` and read the rendered
email, then once with `dry_run` blank and `limit: 1` before letting the
schedule take over.

### Open and click tracking

**State as of 2026-08-16: ON, in Brevo, by the owner's decision.** Brevo
injects its open pixel and rewrites every link at the relay, after
`digest_send.py` has handed the message over.

Our own message still embeds no image, no pixel, no `url()` and no remote
fetch of any kind. `digest_transport.assert_message_is_clean` enforces that
and **must not be weakened to match the copy**. Keeping the two separate is
what makes this reversible: because the tracking is entirely the provider's,
changing provider removes it, instead of sending somebody back through our
templates unpicking pixels we baked in.

**This copy is coupled to a setting nobody in this repo can read.** If the
owner ever turns tracking back off, these have to change back together, and a
half-done change leaves the email honest and the signup form lying:

| Where | What it says now |
|---|---|
| `railway/digest_layout.py`, `TRACKING_SENTENCES` | "Our mail provider records whether you open this email and which links you follow. We read it to see which sections are worth keeping. Unsubscribing stops the email and the measuring together." |
| `railway/digest_transport.py`, `tracking_note()` | the run-log line naming what is believed to be on |
| `includes/subscribe.php`, the signup form intro | **OUTSTANDING at 2.20.72**, still says "no tracking pixels" |
| `includes/subscribe.php`, the privacy note under the form | **OUTSTANDING at 2.20.72**, still says "no tracking pixel, so we cannot tell whether you opened an email" |
| `includes/subscribe.php`, the file's own docblock | **OUTSTANDING at 2.20.72**, same claim in a comment |

The footer is covered by `tests/test_digest_email_layout.py`,
`TheTrackingSentenceIsTrue`, which asserts the old promise is gone from both
body parts, that both say plainly what is measured, and that our message still
carries nothing that fetches. There is no equivalent test on the form copy
yet, which is why the three rows above are marked outstanding rather than
assumed done.

### The email design has one rule: it must survive a forward

`railway/digest_layout.py` owns everything about how the message looks. The
site still composes every figure and every entry through its own endpoints,
and the layout module is not allowed to derive one.

**Gmail and most webmail delete `<head>` and every `<style>` block when a
message is forwarded or quoted.** A digest read by recruiters and journalists
gets forwarded constantly, so a design that lives in a stylesheet is a design
that exists only in the first inbox it reaches. Everything is therefore inline
on the element, the message carries no style block at all, and the layout is
nested presentational tables because Outlook on Windows draws mail with Word,
which has no flexbox, no grid and no CSS positioning. The width is
`width="100%"` capped by `max-width:600px`, so it is fluid on a phone with no
media query, because media queries die on a forward too.

`tests/test_digest_email_layout.py` deletes the head and every style block and
asserts the message is byte for byte the same one. If you add a style block,
a class, a media query or a flexbox rule, that test fails and it is right.
`assert_message_is_clean` in `digest_transport.py` already refuses `<style>`
outright, along with every tag or attribute that fetches from a server, so
there is no image, no pixel and no CSS `url()` to add either. Do not weaken
that check to make a design fit.

Two things this cannot check from a runner: how Outlook 2016 and Gmail's own
renderers actually draw it, and how a client that inverts the message treats
the palette. The palette is checked for 4.5:1 upright AND inverted by
arithmetic, and every colour is declared rather than inherited, but a real
client test is an owner step with a real inbox.

### Changing provider is one variable

`DIGEST_TRANSPORT` is the whole switch, and the seam lives in
`railway/digest_transport.py`.

| value | what it uses | what it needs |
|---|---|---|
| `dryrun` | nothing. Prints the message. | nothing. The default |
| `resend` | Resend's HTTP API | `RESEND_API_KEY` |
| `smtp` | any SMTP relay: Brevo, SES-SMTP, Postmark, Mailgun | `DIGEST_SMTP_HOST`, `DIGEST_SMTP_USER`, `DIGEST_SMTP_PASSWORD`, optional `DIGEST_SMTP_PORT` |

The `smtp` path is the reason there is no Brevo client and no SES client:
nearly every provider speaks SMTP, so switching to one is four secrets and no
code. SES's own HTTP API is deliberately not built. It would need AWS request
signing to reach a service that SES-SMTP already reaches, and speculative code
nobody has run is not a saving.

### What it costs, and the honest caveat

**Provider pricing moves. Re-check before deciding anything on these numbers.**
Read on the dates given, from the providers' own pricing pages.

| provider | free tier | paid | verified |
|---|---|---|---|
| Resend | 3,000 emails/month, **capped at 100 per day** | Pro $20/month for 50,000 | 2026-08-14, resend.com/pricing |
| Amazon SES | $200 of new-account AWS credit, 12 months | **$0.10 per 1,000** a la carte, no monthly minimum. Essentials $0.16 per 1,000 | 2026-08-14, aws.amazon.com/ses/pricing |
| Brevo | a daily-capped free tier, widely quoted at 300/day | tiered monthly | NOT verified from this session; the pricing page did not render. Check it yourself before relying on it |

Read that as: **at any list size this tracker has now, every free tier is free,
and the choice does not matter yet.** Two things would change it.

- **Resend's 100 per day cap bites before its 3,000 per month cap does.** A
  daily digest to 150 confirmed subscribers exceeds the free plan on day one
  while using 4,500 of a 3,000 monthly allowance. Watch the daily number in
  `ops_status.py [4c]`, not the monthly one.
- **SES is roughly 10 to 20 times cheaper per email at volume**, and that is
  the reason to move, once the volume exists. It costs an AWS account and a
  written request to leave the SES sandbox, which is a real afternoon. Do it
  when the bill justifies it, and reach it through `DIGEST_TRANSPORT=smtp`.

At $0.10 per 1,000, a weekly digest to 1,000 subscribers is about **$0.005 per
send and $0.02 a month**. The relay is not going to be what this project spends
money on.

### Bounces and complaints

`POST /wp-json/layoffs/v1/digest-webhook` handles them. It is not key gated,
because a provider cannot send our key. It **fails closed when no credential is
configured**, and it supports **two providers at once, chosen by what the
request carries** rather than by a setting, so a migration does not need a code
change and cannot silently stop processing bounces because somebody forgot to
flip a variable.

| provider | how it authenticates | what you configure |
|---|---|---|
| Brevo | a shared token in a request header. **Brevo does not sign webhooks** | `ALT_DIGEST_BREVO_WEBHOOK_TOKEN` |
| Resend | Svix HMAC signature over the body | `ALT_DIGEST_WEBHOOK_SECRET` |

A **hard** bounce sets the row to `bounced`; a **spam complaint** or an
unsubscribe sets it to `unsubscribed`. Both stop sending at once and both carry
`unsubscribed_at`, so the 30-day retention purge erases them on the same
promise as any other departure. A **soft** bounce changes nothing: dropping
someone because their inbox was full for an hour is data loss dressed up as
hygiene. `blocked` also changes nothing, on purpose - that is Brevo refusing to
send to an address on ITS blocklist, which is a consequence of an earlier
suppression and not new evidence about the mailbox.

#### Arming it under Brevo

**Read this first: Brevo does not sign its webhooks.** No HMAC, no signing
header, no JWT (checked against Brevo's own "Secure webhook calls" page,
2026-08-15). There is nothing to verify the body against, so the endpoint
cannot be as strong as the Resend path is, and that is the provider's property
rather than a gap in this code. The strongest thing Brevo offers is a shared
secret in a header, which is what this uses. Treat that token as a password:
it is replayable by anyone who ever sees one request, and TLS is doing all of
the confidentiality work.

1. **Generate a long random token** and put it in `wp-config.php`:
   `define('ALT_DIGEST_BREVO_WEBHOOK_TOKEN', '<48+ random chars>');`
2. **Create the webhook in Brevo**, Transactional, URL
   `https://asktherecruiter.com/blog/wp-json/layoffs/v1/digest-webhook`, and
   subscribe to `hardBounce`, `softBounce`, `spam`, `unsubscribed`, `blocked`
   and `invalid`. Brevo spells events one way when you SUBSCRIBE (`hardBounce`)
   and another way in the payload it then DELIVERS (`hard_bounce`); both
   spellings resolve, so do not be alarmed by the mismatch.
3. **Attach the token.** Either the webhook's bearer token
   (`"auth": {"type": "bearer", "token": "<token>"}`) or a custom header named
   `X-Alt-Webhook-Token`. **If the bearer token 401s, switch to the custom
   header** - Apache with PHP as CGI strips `Authorization` before PHP ever
   sees it, and on this host that is a live possibility. A wrong token and a
   stripped header produce the identical 401, which is exactly why both are
   accepted.
4. **Never put the token in the URL**, though most guides suggest it. Bluehost
   logs the full request line, so a secret in a path or query string is written
   permanently to a file we do not control. A test enforces this.
5. **Leave `batched` OFF.** Brevo's batched payload shape is not documented;
   all three plausible shapes are accepted here defensively, but none of them
   has been seen from a real delivery.

Optional extra hardening, not built and not checked: allowlist Brevo's
published sending CIDR ranges at the host. Their list is behind a page that
returned 403 to the session that wrote this, so it is a suggestion rather than
a verified step.

To rotate the token: change it in Brevo first, then in `wp-config.php`. The gap
between the two drops bounces for its duration, which is harmless and
self-correcting.

Until the webhook is armed, bounce handling is UNKNOWN rather than working, and
`ops_status.py [4c]` will report `bounced 0` because nothing has told us
otherwise. That is a real gap, not a passing check. **A 200 from the endpoint
is not proof it works either** - the honest test is to send to Brevo's own
bounce simulator address and then read the subscriber row.

### Two senders, one list

The built-in `wp_mail` cron still exists and still works. It stands down
automatically whenever the external relay has claimed a tier within
`ALT_DIGEST_CLAIM_HOURS` (36), and it resumes by itself if the relay stops
running. Independently of that lease, **both senders read one definition of
who is due** (`alt_digest_due_rows`), which excludes anyone already sent to
inside the current period. So even two senders racing in the same minute cannot
put two copies in one inbox. Do not add a recipient query anywhere else.

### The digest is sending nothing, or the wrong thing

- **`digest_mailer` is STALE in `ops_status.py [2]`** (3-day ceiling): the
  sender stopped completing. Check `digest-send.yml`'s last run, then the WP
  cron, and remember the health row is stamped on COMPLETION so a fatal
  mid-run leaves it stale on purpose.
- **A section is missing from the email**: that is the design. The site's own
  `/aggregate` composed nothing for that period, so the digest omits it rather
  than printing a zero it cannot stand behind. Check the endpoint before
  changing the sender.
- **A run printed `REFUSED to send`**: composition produced a message that
  breaks the published privacy note (an image, a remote fetch, a missing
  unsubscribe header). That is a defect in this repo, never a provider
  problem, and it is not retried. Fix the composer.

## The blog reading surface (and how to move it out of this plugin)

**What ships today.** `wordpress-plugin/ai-layoff-tracker/assets/blog-reading.css`
plus `includes/blog-typography.php`. The include gates on `is_singular('post')`
and every selector in the stylesheet is additionally scoped `body.single-post`,
so nothing it does can reach the tracker, the health page, the sources page or a
`layoffs` permalink.

**Say the awkward part when asked.** This is a tracker-named plugin styling the
site's ARTICLES. It lives here only because the plugin's FTPS deploy is this
project's only write channel to asktherecruiter.com. It is not where it belongs.

**Moving it to its proper home** (needs wp-admin, so a human does it):

1. Appearance > Editor > Styles > the pencil icon > **Additional CSS**.
2. Paste the contents of `assets/blog-reading.css`, minus the `body.single-post`
   scoping if you prefer, though leaving it is harmless and safer.
3. Add the two `@font-face` rules that `alt_blog_reading_font_css()` builds,
   pointing at the active theme's own Vollkorn files.
4. Delete `includes/blog-typography.php`, drop its `is_readable` block from
   `ai-layoff-tracker.php`, delete `assets/blog-reading.css`, and delete
   `railway/tests/test_blog_reading_surface.py` (its fixture describes CSS that
   would no longer be in this repo). Bump the version and deploy.

A child theme is the better home still, because Additional CSS is also
database-held and therefore invisible to every grep, which is the exact property
that made the two defects in TECHLOG 2026-08-15 so hard to find.

**Three stylesheets fight for this page and NONE of them is on the filesystem.**
When something on a post looks wrong and no file explains it, walk the CSSOM
rather than grepping:

```js
for (const s of document.styleSheets) {
  const n = s.ownerNode;
  console.log(s.href || 'INLINE<' + n.tagName + '#' + n.id + '.' + n.className + '>');
}
```

The three that matter, by id:

| id | Where it is stored | What it does to articles |
|---|---|---|
| `wp-block-library-inline-css` | a `wp_add_inline_style('wp-block-library', ...)`, so a WPCode PHP snippet or the theme's functions | `.entry-content p/h2/h3` sizes AND `margin: x 0 y !important`, which is what un-centres the headings |
| `global-styles-inline-css` | Site Editor > Styles > Additional CSS, in the `wp_global_styles` post | under 782px, zeroes the `.alignfull` negative margins, so the gutters stack to 78px |
| `wpcode-css-snippet` (class, no id) | WPCode plugin, `wpcode` CPT rows | pins `max-width:100%!important` on containers and on `blockquote` |

**If a heading goes flush-left again**, something re-introduced a `margin`
shorthand on a constrained child. Never answer it by widening the column;
`test_blog_reading_surface.py` fails on the shorthand in our own file and
`test_every_heading_shares_the_paragraph_left_edge` fails on the rendered
result.

**If the phone column collapses again**, re-measure the ancestor chain before
changing anything:

```bash
python3 railway/reader_freshness.py     # first: is the reader even on this build
```

then walk `getBoundingClientRect()` and `paddingLeft` from a paragraph up to
`body`. Three paddings that do not cancel is the signature.

## Research pointers
- WARN scraping: https://github.com/biglocalnews/warn-scraper (Big Local News)
- GDELT DOC 2.0 API: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ (keyless; ~gentle rate limits, 429s happen)
- SEC EDGAR full-text search: https://efts.sec.gov/LATEST/search-index?q= (declare a User-Agent per SEC policy)
- Extraction model: `google/gemini-2.5-flash-lite` via OpenRouter (openai SDK, `base_url` override) — see `railway/extractor.py`.
  Classification is PINNED separately to `deepseek/deepseek-chat` (`OPENROUTER_CLASSIFY_MODEL`); it no longer follows `OPENROUTER_MODEL`.
  Swapped 2026-08-07 against the news-path gold set (`docs/recall-reference-sets/news-corroborated-2026-08.goldset.json`), 30/30 at 0.388x cost.
  NOTE: if `OPENROUTER_MODEL` is pinned in the Railway environment, the code default does NOT reach the main cron - change it there too.
- Comparable trackers for editorial judgment: technology-sector trackers (crowdsourced), announcement-survey monthly reports, WARN databases by ProPublica/USA Today

## Accepted risks / known limitations (documented, not bugs)
- ~98% of WARN links are state LIST pages — most states publish no per-notice URL
  (UI labels these "(list)"; AZ/KS/DE/ME/KY link per-notice).
- Multi-state remote employers file overlapping counts in several states (disclosed in
  methodology; Monday report flags them).
- WARN filings carry no industry/reason → industry/reason charts reflect SEC+news entries.
- Year/quarter/month SQL uses non-sargable date functions — fine at ~100K rows, revisit
  if the table grows 10×.
- `is_user_logged_in`-gated REST nocache suppression means logged-in admins always see
  fresh (uncached) API data; anonymous visitors may be ≤60s behind.
- FTP deploys upload files in place (no atomic swap on Bluehost), so each deploy has a
  ~30–60s window where a PHP-hitting request can 500 on a truncated file. Supercached
  HTML shields most anonymous traffic; a 500 observed right after a push is this window,
  not an outage — re-check after the deploy run goes green before reverting anything.

## The self-healer (draft PRs from red CI — what it may and may never do)

`.github/workflows/self-heal.yml` listens for every workflow completing, and
when one fails on **main** with a NEW, code-shaped cause, it asks Claude (the
pinned `anthropics/claude-code-action`) to reproduce the failure from the run's
log, diagnose it, and open a **DRAFT pull request** with a test-verified fix.
A second, adversarial pass then reviews the draft — re-derives the failure,
tries to break the fix — and posts its verdict as a PR comment.

**The healer MERGES ITS OWN DRAFT when every condition holds** (owner
authorization, 2026-08-14: "a human clicks merge — I want you to click merge,
I'm okay with that"). The click is delegated; the conditions are not, and
every one resolves UNKNOWN to "stay a draft":
1. the forbidden-path guard job passed;
2. the adversarial reviewer's machine-readable verdict is **exactly**
   `SELF-HEAL-REVIEW-VERDICT: LOOKS SOUND` — absent, ambiguous, or any other
   verdict keeps the draft;
3. the diff is source/test files only — **never** `.github/` and never
   anything in `self_heal.FORBIDDEN`;
4. the merged preview runs the offline suite and introduces **no failure main
   does not already have**. That is the honest form of "green except the
   documented live-data reds": a standing red fails both runs and subtracts
   out; anything new blocks the merge.

A blocked merge is a decision, not a failure — the job stays green, comments
on the PR, and leaves the draft for a human.

**What it will never do** (enforced in three layers: the gate in
`railway/self_heal.py`, the action's tool allowlist, and the `guard` job that
diffs the branch after the fact and goes red on a violation):
- never merges, never pushes to main, never dispatches or re-runs a workflow;
- never touches `railway/spend.py`, `railway/headline_incidents.json`,
  `railway/alert_outbox.json`, either hash-pinned lock, `docs/HANDOFF.md`, or
  `self-heal.yml` itself (`self_heal.FORBIDDEN` is the one list);
- never heals the known-expected reds: live-data invariant FAILs (a human
  closes those with `--close-incident`; ci_alert has already emailed them),
  self-timeouts (already mailed as CI SELF-TIMEOUT), host-outage-shaped
  failures, branch/PR reds (they have an author), or the alert workflows
  themselves. The classification is REUSED from `ci_alert.py` — one
  definition, so a failure cannot be healed and classified needs-a-human at
  the same time.

**Budget is structural:** one healer at a time (concurrency group), one open
PR per cause fingerprint (the branch name is the ledger), hard ceiling of 3
open healer PRs.

**To arm it:** add the `CLAUDE_CODE_OAUTH_TOKEN` repository secret (Settings →
Secrets and variables → Actions). Until then every run gates, prints what it
would have done, and exits green with a notice naming the secret.

**To turn the AUTO-MERGE off and keep the drafts** (the one-line kill
switch): set the repository variable `SELF_HEAL_AUTOMERGE_DISABLED=true`
(Settings → Secrets and variables → Actions → Variables). The healer keeps
diagnosing, drafting and reviewing; the click returns to you.

**To disable the whole healer:** set the repository variable
`SELF_HEAL_DISABLED=true` (same page), or delete the workflow file.

**When a heal breaks something** — every auto-merge is ONE squash commit, and
`docs/HEALING-LOG.md` is the revert index (date, workflow, run URL, cause,
PR, merge SHA, files, reviewer verdict; newest first). Revert with
`git revert <merge sha>` from that entry. `docs/TECHLOG.md` carries the
narrative for the same heal under the same date. Both are written
best-effort, AFTER the merge, and can never fail a heal — so an empty stretch
in the log is not proof nothing merged; cross-check
`git log --grep 'self-heal: auto-merged'` on main.

**To test the gate:** `gh workflow run self-heal.yml -f run_id=<a past run id>`
— or locally, `python3 railway/self_heal.py gate --run-id <id> --workflow
"<name>" --conclusion failure`. The gate is offline-tested in
`railway/tests/test_self_heal.py`, including the forbidden-path guard's
red-on-violation exit.
