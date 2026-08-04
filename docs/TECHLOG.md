# Tech Log

Chronological record of what was built, why, what broke, and how it was fixed.
Newest first within each section. **Keep this updated:** every deploy gets a line;
every incident gets an entry in the Incident Log with root cause + the guard added.

---

## 2026-08-04 - public-accuracy batch of four: one owner per coverage count, an honest country-scan figure, the last doubled /blog/, and a real social card (2.19.261)

Four audit-confirmed defects, all of them numbers or links a reader could
check, fixed in one version.

**1. Every coverage count now has ONE owner.** The same two claims were being
computed in three places and all three disagreed on the live page.
`alt_live_numbers()` ran its own `COUNT(DISTINCT state)` over EVERY row and
got 50, which the FAQ then attributed to WARN notices, a source that had
produced nothing in three of those states; that 50 shipped inside the FAQPage
JSON-LD, so a wrong number was in structured data, not just prose. The
methodology block said "48 US states and DC" from `count(alt_state_warn_urls())`,
whose 48 keys already include DC, so DC was counted twice and a 48th state was
invented. The coverage ribbon said 47, from `alt_coverage_counts()`, the only
one of the three that measured what the sentence claimed. Now
`alt_coverage_counts()` owns both figures, `alt_live_numbers()` delegates to it,
and `alt_warn_states_phrase()` renders the claim ("46 US states and DC") so no
surface reassembles the DC arithmetic again. Same pass: the country count now
excludes the "Multiple countries" bucket, which is a placeholder for events we
could not localise and not a place (58 -> 57). A fourth stale figure went with
them: the health table's United States row said "WARN notices, 44
jurisdictions", typed into an offline generator that cannot read live data, so
it now names the registers without a count.

**2. "203 countries" was an 11 percent overcount.** `generate_country_table.py`
reads gdelt.py's own allowlist comments, and the US metro block labels its
lines with the outlet or the state ("# Tampa Bay Times", "# Oklahoma - Tulsa
World"). Twenty-one of those became country ROWS, plus 2 grouping rows, so a
figure journalists quote read 203 when the honest answer is 180 countries and
territories. The count is now whitelisted against real country and territory
names; US states and US metro outlets fold into the United States row (which
went from 1 outlet to 25, where they always belonged), and the two grouping
rows are listed but never counted. An unrecognised name UNDERstates reach
rather than inflating it and the generator prints it, so an omission is
visible instead of silent. `railway/tests/test_country_scope.py` fails if a US
state or metro outlet is ever counted as a country again, if any counted row is
not a real country, or if the committed partials drift from the generator. The
same regeneration also fixed drift nobody would have caught: the generator
still emitted "NewsAPI" while the committed partial had been hand-corrected to
"Google News", so the next routine re-run would have quietly restored a dead
collector's name to a public page. The test pins that too.

**3. The last doubled /blog/.** `single-layoff.php` built
`home_url('/blog/ai-layoff-tracker/')`, but `home_url()` already ends in
`/blog`, so roughly 1,800 entry pages sent their main internal link through a
301 to `/blog/blog/...`. Verified live before the fix. It was the only such
call left in either repo.

**4. og:image and frozen Article metadata.** Every page served the 512x512
site-icon crop as og:image while declaring `twitter:card=summary_large_image`,
so every share asked for a wide card and got a favicon tile. There is now a
real 1200x630 card (`assets/social-card.png`, source HTML beside it, rendered
with headless Chrome) carrying the tracker's name and its promise, and no
figures, so it can never go stale. It is applied through Rank Math's per-page
filters and gated on `alt_is_tracker_surface()`: ONE WordPress install serves
both trackers and the whole blog, the bad image is the SITE-WIDE Rank Math
fallback, and changing that default would have restyled the sibling tracker and
every article. The Article node was likewise frozen at 2026-07-14 with author
Person "admin" while the Dataset node beside it was live-dated and the copy
says "updated daily" four times; `dateModified` (and og:updated_time) now
derive from `alt_last_write`, the timestamp of the last actual write to the
table, and the page is attributed to the site's Organization node rather than a
WordPress login name. With no recorded write it changes nothing rather than
inventing a date.

---

## 2026-08-03 - caught live, post-deploy, by reading the page: single-date states scored as zero notice (2.19.257)

The notice-gap section's first live render showed nine states at "median 0
days, 100% shorter than 60" (IN, AZ, KS, UT, DE, VT, ME, SD, MT). That is not
nine states of employers giving no notice: sources/warn.py falls back to the
notice/received column for layoff_date when a state publishes only one date,
and stores the same value in announcement_date, so for single-date states the
gap is structurally 0 and measures nothing. Fix: rows whose two stored dates
are identical are now a counted exclusion (same_date_ambiguous) with the
reason stated on the page, the histogram takes announcement_date <
layoff_date only, and the copy notes the resulting shorter-than-60 share is
conservative (a real same-day notice is excluded, not counted against the
employer). The transient key now includes ALT_VERSION so a deploy can never
serve a cached stats array of the previous shape. Guard test pins the
exclusion.

## 2026-08-03 - external-credibility batch: jurisdiction comparability, measured WARN notice gaps, an auditor's pack, and disclosure (2.19.256)

Owner-approved batch from an external credibility review. Four pieces, all
derived-not-typed:

1. **Cross-jurisdiction comparability table** (`#m-jurisdictions` on the
   methodology page). A reader comparing a Texas total with a France total is
   comparing two legal definitions of "a record", and nothing said so.
   `railway/generate_jurisdiction_table.py` derives a per-jurisdiction "what
   qualifies here" table from the collectors' own configs: the covered WARN
   jurisdictions parse from the three real state lists **via the AST, not a
   regex** (a lazy regex died on `table[0]` inside a list comment and silently
   dropped an entire state list, under-reporting coverage 48 -> 20 on the
   first run); ERM's inclusion floor and 2002 history floor parse out of
   erm_import.py's own docstring; the federal 60-day figure imports from
   warn_transparency_evidence.STATUTORY_NOTICE_DAYS. Thresholds not encoded
   in the repo (per-state mini-WARN, Quebec, Mazowieckie) print UNKNOWN,
   never a guessed number. Drift-guarded by
   `tests/test_jurisdiction_table.py` (committed partial must equal
   regeneration, same pattern as the ingest schedule). Every country and
   state facet page now carries a one-line "definitions differ by
   jurisdiction" caveat linking to the section.
2. **WARN notice periods, measured** (`#m-notice-gap`).
   `alt_warn_notice_gap_stats()` computes the recorded notice gap
   (announcement_date -> layoff_date on US WARN rows, the fields
   sources/warn.py already stores) as a (state, gap) histogram: exact
   medians and share-shorter-than-60-days per state and overall, missing or
   reversed dates excluded AND counted, 6h transient keyed on alt_data_ver.
   Copy is descriptive by construction: the statutory exceptions
   (29 U.S.C. 2102(b); 20 C.F.R. 639.9) and court-only enforcement
   (29 U.S.C. 2104) are stated beside the numbers, and a static guard test
   bans verdict words ("violation", "non-compliant", ...) from the section.
   Distinct from, and unrelated to, the editorial WARN transparency
   register; states under 25 datable notices fold into overall only.
3. **Auditor's pack**: `docs/AUDIT.md` indexes what already exists (gold set
   + protocol, data_integrity invariants, monthly source-audit sampling,
   corrections log, synthetic-snapshot SQL replay, drift-proof generated
   claims) with exact offline commands, plus a stated "not independently
   verifiable today" list. Linked from the methodology self-audit section.
4. **Disclosure + corrections provenance**: a "Who runs this" methodology
   section (prose flagged DRAFT FOR OWNER REVIEW in a PHP comment; the
   business-practice sentences came from the owner's brief, nothing about
   funding is claimed because nothing is derivable); and the corrections log
   now opens with a computed origin line (`alt_corrections_provenance()`):
   entries classify as internal-audit/automated or external-report ONLY on
   explicit markers in their own stored text, ambiguous or markerless
   entries count as unrecorded, never assigned.

## 2026-08-03 - the spend-ledger harvest never landed: read-only GITHUB_TOKEN, and a warning nobody read

`railway/spend_jobs.json` stayed `{"entries": []}` on main for a day after
the per-job ledger shipped (12305ef), so every question the ledger exists to
answer (which job burns what, per stored row) had no data. Diagnosis, from
the 2026-08-03 04:46 UTC dispatch run of "OpenRouter low-balance alert":

- The unproven half was fine: `spend.py --harvest` DID read the day's run
  logs with `github.token` ("1 job log(s) read, 1 ledger line(s) seen");
  `actions: read` is in the default token grant.
- The push was the failure: `remote: Permission to ... denied to
  github-actions[bot]`, HTTP 403, three times. The workflow had NO
  `permissions:` block and the repo default token is read-only; the other
  self-committing workflows (alert-drain, ci-alert, data-integrity,
  recall-precision) all declare `contents: write`, this one never did.
- Nobody saw it because the commit step deliberately swallows push failures
  (a monitoring job must not redden CI over its own bookkeeping), so seven
  consecutive green runs each dropped their reading on the floor. The
  swallow stays (it is correct); the permission is fixed instead. Note the
  daily balance history was ALSO never landing, for the same reason.

Fix: `permissions: {contents: write, actions: read}` on the workflow;
`actions: read` listed explicitly because an explicit block replaces the
defaults the harvest was silently relying on. Proven by dispatching the job
once and watching `spend_jobs.json` gain entries on origin/main.

**Deferred to the next session, on purpose (2026-08-03):** the cadence
decisions task #65 conditioned on harvest data were left unmade because one
day of entries is not a trend: (a) confirm ai-evidence-sweep is cheap
post-NewsAPI-fix; (b) if company-watchlist's measured cost per stored row is
effectively infinite (repeated 0 posted), move its cron to weekly with the
reasoning in the workflow header and the ops_status ceiling table updated;
(c) funnel-port TODO: when the cost-funnel template (dedup-before-LLM,
headline-only gate, per-language prefilter, earned cadence) ports to this
tracker, **supplemental-news** must be in the ported set; do not build its
gate piecemeal before the port. Judge (a)/(b) on several days of
`spend_jobs.json`, not the first harvest.

---

## 2026-08-02 — the owner's shared design, layoff half: signal board, editorial hero, coverage ribbon, freshness panel, palette (2.19.253)

Adopts the owner's shared design artifact (audience-spec ADDENDUM 2026-08-02):
the complaint driving it was "too much text"; the answer is colored,
tappable numbers where paragraphs stood.

- **THE SIGNAL BOARD** evolves the daily strip in place (same `#alt-narrative`
  container, same stage=verified aggregate plumbing, Copy-as-post kept): rows
  Workers / Verified layoffs / Explicitly AI-attributed / Largest event x
  columns Today / This week / This month / YTD. Heat is scaled WITHIN each
  row; every numeric cell click-filters the page through the existing
  `.alt-nfilter` + URL machinery (the hrefs are real `?from/to/years` URLs so
  the cells work without JS); Largest-event cells link to the entry permalink
  (new additive `permalink` key on the aggregate `leaders` block), falling
  back to the company filter. One legend ("less/more"), ONE footnote. The
  "Today and this month identical" collapse survives as equal-column styling
  (`.alt-sb-eq`), not duplicate columns. Server-rendered numbers ride the
  bootstrap payload's new `board` block, computed through the SAME cached
  aggregate handler with `include=leaders` (totals + one leaders query per
  period, 30-min transient shared with the JS repaint's own fetches); the JS
  board consumes the boot block only when every period's params match
  (takeBoot rule), so a timezone rollover falls back to a live fetch.
- **EDITORIAL HERO**: serif thesis ("Every layoff here is verified. That is
  the whole point."), the floor banner's trust sentence folded in, two
  buttons (Search the record -> scrolls/focuses the search box, plain anchor
  without JS; How we count -> methodology). The old floor banner and the
  lead paragraph's scan-scope sentence are gone from the fold.
- **FRESHNESS PANEL** top-right of the hero: hosts the existing Roo status
  header ([alt_stats_bar] now yields on the page that renders [alt_tracker]
  — shared markup via alt_render_status_header()), the cron-derived
  next-update line (#alt-next-top moved here, still JS-refreshed to ET),
  four big stats from the same bootstrap totals as the tiles, and the "No
  figure appears unless its source states it" line.
- **COVERAGE RIBBON**: "Covering <first record> to <today> · N countries ·
  N US states" fully derived (alt_coverage_counts grew a `first` MIN-date,
  isset-guarded against the pre-`first` transient) + Sources / How complete,
  measured (anchors to the recall paragraph, now id=alt-recall-measured;
  in-page anchors inside closed <details> now open the ancestor chain) /
  Corrections / sibling-tracker links.
- **PALETTE**: warm paper ground on the dashboard wrap, ink-navy headings and
  board ticks, ochre reserved for emphasis figures (non-AI tile values,
  freshness stats, citeline stat), muted blue heat cells. Semantic direction
  colors and the interactive blue accent unchanged.
- Above-the-fold words: 289 rendered before (162 server + ~105 JS strip +
  header) -> 257 after, all server-rendered now (the no-JS reader gains the
  board numbers the strip never gave them). Verified at 375px and 1280px
  with zero horizontal overflow before push.

## 2026-08-02 — strip columns are width-aware (2.19.252)

The 2.19.251 two-column strip row left a ~130px value column at 375px:
word-per-line wrap and the nowrap "(n · loc)" unit bleeding past the card edge
(verified broken live before fixing). Flex columns now apply only at >=700px;
below that the label stacks above a full-width value. Verified live at 375px
(stacked, no overflow, document scrollWidth == clientWidth) and 1280px (flex
columns, "(31,000 · US)" wraps indented inside the value column).

---

## 2026-08-02 — owner follow-ups: strip wrap fix, pills back to dropdowns, trend explainer in plain language, places card (2.19.251)

- **Daily-strip wrap bug**: "largest: Internal Revenue Service (31,000 · US)"
  wrapped so the parenthetical landed orphaned at far-left under the label
  gutter. `.alt-nrow` is now a two-column flex row (label gutter + value
  column, value wraps INSIDE its column), and the "(n · loc)" parenthetical is
  one unbreakable `.alt-nowrap` unit; company names may still wrap at 375px.
- **Sources + Roles pills reversed to compact checkbox dropdowns** in the
  filter grid (owner: the strips ate half the bar). Same element IDs, so URL
  state, chips, chart taps and Reset all unchanged; the pill renderer stays,
  template-driven, for any future `data-pills` cell. Multi-select audit: every
  categorical filter (years, quarters, months, industries, countries, states,
  reasons, roles, sources) already accepts comma lists end to end. Single by
  API design and NOT faked client-side: company (LIKE substring), keyword,
  search, min jobs, from/to.
- **"Jobs cut per month" caption rewritten**: two visible sentences (what a
  bar is, what a tap does); future-dated caveat, announced-line note,
  whole-record strip mechanics and overlay axis all moved behind a per-card
  (i). The jobless-claims overlay paragraph is now one plain sentence.
- **New "Browse the record: top places" card** fills the grid slot beside
  Roles: server-rendered from the memoised `alt_facet_index()` (zero extra
  queries), rows link to the permanent /country-layoffs/ and /state-layoffs/
  pages, labeled "whole record, not affected by the filters above" (the same
  filter-exempt labeling as the jobless-claims card — making it filter-scoped
  would put three grouped COUNTs on every filter tap, which the opt-in
  facet_counts block exists to avoid). The requested second chart ("AI share,
  month by month") already exists as "AI share of verified cuts, monthly"
  (alt-chart-ai-share-trend) and was not duplicated.

---

## 2026-08-02 — audience UX: server-rendered headline tiles, first-screen cite line, cron-derived next-update, linkable corrections (2.19.250)

**WHAT (per the audience display spec, layoff half).**
- **Stat tiles server-render real numbers.** The flagship page's whole pitch is
  citability, and the tiles shipped as "…" until JS ran — crawlers and
  copy-pasting journalists got dots. page-tracker.php now fills every tile
  value + period stamp from the SAME cached bootstrap aggregate
  (`alt_tracker_bootstrap_payload`, zero extra queries); the arithmetic mirrors
  `renderStats()` exactly and JS re-renders on load, so the two cannot
  disagree. Deep-linked filtered views keep the placeholder (no bootstrap by
  design) and JS fills from the live filtered aggregate.
- **First-screen cite line** (Eurostat pattern: headline + dateline + next
  release on one screen): verified total, as-of date, Cite/CSV/JSON/API links
  (the CSV/JSON `-top` pair is kept filter-honoring by `updateExportLinks`),
  and the next collection time.
- **Next-update is DERIVED from the real cron, never typed.** New
  `railway/generate_ingest_schedule.py` parses `railway/railway.toml`
  `cronSchedule` into `data/ingest-schedule.json`; `alt_ingest_schedule()` /
  `alt_next_ingest_utc()` / `alt_ingest_times_label()` (db.php) read it, the
  header's "Live · updated" label renders from it (the old typed
  "9 AM & 6 PM ET" was DST-wrong half the year — the cron is UTC-fixed), and
  layoffs.js `nextPullET()` now reads `altData.ingest` instead of a hardcoded
  `[13, 22]`. `tests/test_ingest_schedule.py` fails the build if the JSON
  drifts from railway.toml or a typed hour list reappears in JS. Missing file
  = render nothing (same contract as recall-measurement.json).
- **Corrections log entries are linkable**: per-entry `id="log-<date>-<n>"`
  anchors (numbered on the append-ordered array so anchors never shift) plus a
  visible `#` link, and the framing paragraph compressed per the spec.
- **The 700-outlet source table left the tracker page** (it sat between the
  charts and the FAQ/cite block); one line + link to the Sources page, which
  keeps the full generated directory.
- **Tile-row hygiene**: the broad AI measure moved OUT of the addable-tile row
  into its own strip (same element IDs, JS unchanged), and the two
  caveat-paragraph captions compressed to tile face + `(i)` disclosure
  (`details.alt-stat-i`, expands in place, no overlay to bleed on mobile).
- **Wording per spec**: self-audit paragraph cut to one line + methodology
  link (the double-pass/dedup detail already lives there), jobless-claims
  explainer shortened, map legend now says "tap a bubble to filter, tap the
  map to zoom", bookmark-this-view note on the filter prompt, and a
  hiring-signals cross-link to the talent tracker after the stats.
- NOT changed: Roles Most Impacted bars were already wired to `alt-f-roles`
  (2.19.221, b01daed) — the spec's audit predated that fix; verified live.

---

## 2026-08-02 — the archive promise, printed with a real date and pinned by an invariant (2.19.248)

**WHAT.** Every listing surface now shows, per row with a source URL: the
permanent Wayback link when archived, otherwise "No archive snapshot yet. We
re-check weekly; next check by <date>." — the date DERIVED from the real
schedule (daily archive-backfill at 05:25 UTC, 72h pending retry, 7d
unavailable re-check), never typed. One sentence, two renderers: db.php
`alt_archive_note_html()` (company pages, facet pages, entry permalinks) and
layoffs.js `archiveCell`/`archivePendingTitle` (tracker cards).
`railway/tests/test_archive_promise.py` pins the PHP constants, the JS mirror,
the workflow cron and the sentence to each other.

**THE PROMISE CAN FAIL, WHICH IS THE POINT.** `/archive-coverage` now reports
`queued` and `oldest_unarchived_checked_at`, and a new
`data_integrity.ArchiveRecheckInvariant` (key `archive_recheck_cadence`) FAILS
when the oldest un-archived attempt exceeds 10 days = 7 (promise) + 1
(daily-run granularity) + 2 (slack). Wired into the existing INVARIANTS
registry — test, ops_status and digest all pick it up; UNKNOWN (build predates
the fields) is pending, never a pass.

**TWO DEFECTS FOUND WHILE MAKING THE DATE TRUE.** (1) The candidate query
ordered newest-layoff-date-first, so when more than one 500-batch was due, the
freshly restamped top slice cycled every 72h and everything below starved
forever — ordering is now never-checked first, then oldest-attempt first.
(2) One 500-URL batch per run cannot re-check a ~4,000-URL pending pool inside
a week (needs ~1,300/day); archive_backfill.py now pages through batches up to
ARCHIVE_BACKFILL_LIMIT (1,500) per run, deadline 1800s -> 2400s. The
archive-backfill.yml note claiming "pending never re-enter the candidate list"
was an hourly-sprint measurement artifact and is corrected in place.

**ALSO: the methodology's typed "24 of 57 / 42%" is now rendered.** The tracker
page's measured-completeness paragraph reads
`data/recall-measurement.json` (a render copy recall_precision.py writes beside
the canonical railway/recall_measurement.json, only when a figure moves), with
the Wilson interval computed in PHP (`alt_wilson_interval`). File missing ->
paragraph omitted, never a stale number. The caveats stay attached; per
docs/RECALL_BENCHMARK_PROTOCOL.md this figure remains labeled a one-family
floor, not "our recall". Coverage line (archived / queued / pending /
unavailable, live counts) added to the methodology and health pages via
`alt_archive_coverage_line_html()`.

**DAILY STRIP (same deploy).** Label/value gap is now a real space (copied text
read "Today1,366 workers"); "Today" and "This month" collapse to one
"Today and this month" line when their figures are identical (1st of the
month); "largest:" entries carry location from the row's own fields (state for
US, country otherwise), including in the Copy-as-post text.

---
## 2026-08-02 — a weekly CI-noise report over the alert layer (no plugin change)

**WHY.** The 7-day run audit (2026-07-26..08-02, both trackers) split every
non-green run into (a) real-and-alerted-once, (b) noise, (c) latent. This
repo came out largely clean — the earlier structural fixes are holding: 15
Tests reds were push-CI catching real defects during active dev (correct), 3
were CI-alert self-tests, 1 historical-sweep failure alerted once, and 3
cancelled scheduled runs were one-offs (one, EDGAR history sweep 2026-07-28,
was a zero-job concurrency displacement — invisible in the UI). The sibling
was NOT clean: 180 red drain ticks for a handful of already-reported items.
Nothing was WATCHING the shape of the week in either repo; per-run dedup
cannot see "the same cause reddened nine runs".

**WHAT.** `railway/ci_noise_report.py` + `ci-noise-report.yml` (Mondays 12:20
UTC, after the health digest): reads the week's run list, groups failures by
`ci_alert.extract_cause` (the SAME extractor as the email, normalised the
same way), counts repeat reds (n-1 per cause; the FIRST red of a cause is
signal and counts zero) and zero-job cancellations, and POSTs ONE summary to
the keyed `/alert` ONLY when noise > 0. A quiet week posts nothing. UNKNOWN
stays a third state: no `gh` exits 3, never "quiet"; an unknown job count is
never read as zero; an undeliverable report is HELD in the outbox like any
alert. Guards in `railway/tests/test_ci_noise_report.py` (18 tests), incl.
"first red of a cause is never noise" so this can never become pressure to
silence a real alarm.

## 2026-08-02 — per-job spend attribution: the ledger, the named ceilings, and the job that ignored the guard

**WHY.** The only cost signal was a daily account balance plus a whole-process
meter. Neither could attribute a cent to any of the dozen small daily LLM jobs,
so "$5/month" was a hope, not a property. Now every LLM job closes with
`spend.record_job_run(...)`, which prints one `SPEND_LEDGER_V1` JSON line
(job, date, exact metered cost from OpenRouter's usage object, calls, items,
stored/changed). Runners are ephemeral, so `spend.py --harvest` — run by the
daily balance job, the ONE workflow that commits — re-reads those lines out of
the day's run logs into the committed `railway/spend_jobs.json` (60-day
retention, idempotent by (job, run_id, attempt)). One commit a day, instead of
a dozen pushes a day each rebuilding Railway and re-running the test suite.
`ops_status.py [2a]` renders the per-job table ($/day, $/run, $/row, share of
ceiling) from the committed file; a job with no metered run prints UNKNOWN,
never a guess, and an empty ledger is exit-3 UNKNOWN, not a pass.

**NAMED CEILINGS.** `spend.JOB_RUN_CEILINGS_USD` gives each job a per-run
ceiling; the guard step resolves the job from GITHUB_WORKFLOW_REF and writes
`ALT_RUN_CEILING_USD` to GITHUB_ENV, so the existing state-free brake enforces
it — degrade mid-run, resume next run, never halt. The ladder is in the table's
docstring with MEASURED/COUNTED/MODELLED labels: ingest ~$5.1/mo MEASURED,
small jobs MODELLED at ~$6-8.5/mo unthrottled, so the interim $10 holds only
with industry-backfill, company-watchlist and supplemental-news explicitly
THROTTLED (each already resumes where it stopped). The $5 target is documented
as requiring the ingest cost-funnel port first — not pretended.

**THE HOLE FOUND BY MEASURING THE PREMISE.** The brief said every small job
"runs under the guard". `dedupe_llm.py` was not: its workflow ran the degrade
step, the flag landed in GITHUB_ENV, and the script — its own raw urllib
client — never read it and never metered. A spent month still bought ~60
cluster reviews/day (~$0.02/day MODELLED). It now gates on
`paid_reads_enabled()` (before the loop and per cluster) and meters every
response. Three more self-client scripts (ai_evidence_sweep, the daily
spot-check, the monthly source audit) gated but did not meter — the per-run
ceiling was blind to their spend; all meter now, and dict-shaped `usage`
objects are charged, not silently zeroed.

**MEASURED IN SITU, not asserted:** a read-only `--harvest` against the real
repo listed the day's runs and read 6 job logs (the 401-on-redirect trap —
GitHub's /logs endpoint 302s to blob storage, which rejects the bearer token —
is fixed by following the redirect without the Authorization header, same as
`gh api`). 673 offline tests green, 27 new in `tests/test_spend_ledger.py`,
including the arithmetic guard: the named ceilings' worst-case monthly sum
must leave the measured ingest room inside the allowance, so widening a
ceiling without redoing the ladder is a red test.

## 2026-08-02 — an invariant that went quiet on its own: it HEALED, and that is the bug

**WHAT HAPPENED.** `data_integrity.headline_movement` reddened the Tests run for
the 2.19.246 deploy (SHA `73b2606`, 2026-08-02T03:33:07Z):

    Worldwide jobs, all time: +63,899 jobs over 1.0d on +16 entries
    (20,186,665 -> 20,250,564). The rows that changed carry at most 61,211 and
    the largest single row is 60,000, so NO ROW EXPLAINS THIS.

Twenty minutes later the same check passed (SHA `11bc4ce`, 03:53:31Z) with no
intervention. A guard that goes quiet on its own is the failure mode this repo
has written rules against three times, so the two readings had to be told apart:
did the defect HEAL, or did the BASELINE move over it?

**IT HEALED. The baseline did not move, and here is the proof.** The committed
`railway/headline_baseline.json` blob is byte-identical in both checkouts —
`git rev-parse 73b2606:railway/headline_baseline.json 11bc4ce:...` returns
`039a0fad` for both. `record_baseline` had not run in between at all: the file's
whole history is four commits (`7e76754`, `413a8b8`, `f83e1e2` at 08-01T17:51Z,
`7ffb81c` at 08-02T17:51Z), and the 08-02 write advanced worldwide_all_time from a
run that reported success. The refusal-to-advance rule has no hole on this path;
`record_baseline` skips any slice whose per-slice state is FAIL, and
`MovementInvariant` is the only writer of `ctx.observations`.

**WHAT ACTUALLY MOVED WAS THE SAMPLING POINT.** `Historical backfill (EDGAR)` ran
02:39:27Z -> 07:40:04Z. Both reads landed inside that five-hour writer. The
arithmetic reproduces exactly: prior 20,186,665 jobs / 63,319 entries gives a mean
of 318.809 jobs per row, times `mean_factor` 12 times 16 arrived entries = 61,211
— the allowance in the message, to the job. So at 03:33 the 16 rows that had
arrived carried 3,994 jobs each, judged against a model built from the STANDING
population's 319-job mean; by 03:53 more rows had landed and the ratio fell back
inside. It missed the one-row clause by 899 jobs too (63,899 vs 60,000 x 1.05).

**THE DEFECT, STATED PROPERLY.** A baseline is captured once a day by
data-integrity.yml at 17:30 UTC. That is the pairing the check is calibrated for:
two readings a whole ingest cycle apart, so the rows between them are a day's
worth of rows. But tests.yml runs the same LIVE check on every push, at any hour,
and therefore routinely compares part of a cycle against the end of the previous
one. A partial cycle is not a small day — the rows inside it are whichever
collector is mid-batch, and collectors differ by an order of magnitude in jobs
per row (state WARN in the hundreds, EDGAR and news in the thousands). The
verdict became a function of where in a batch the sampler landed. That is a race
with the writers, not a finding about the data.

**THE FIX (and what it deliberately is not).** `MIN_CYCLE_SPAN_DAYS = 0.95`.
Below that span the plausibility verdict is not rendered: UNKNOWN, `pending`, a
third state and never a pass, and `record_baseline` now refuses to advance over
it exactly as it refuses over a FAIL (`_out(..., suppressed=True)` — otherwise the
fix would have opened the very laundering hole it was protecting). The daily run
spans a whole cycle by construction and keeps its full FAIL power. What keeps its
FAIL at ANY span, because no later arrival undoes it: a headline of zero, and a
headline moving while the row population stands still (Δentries == 0) — which is
the mass-re-mark / bad-purge class this guard was actually built for.

**`move_floor` was NOT touched.** Raising it would have fitted the bound to one
afternoon's move and bought quiet at every hour of the day for defects the floor
is correctly sized to catch. The noise was a timing problem, not a bound problem,
and RUNBOOK now says to check which before reaching for a floor.

**Tests that fail on the old code:**
`test_headline_guards.Movement.test_the_2026_08_02_partial_cycle_reading_is_unknown_not_a_failure`
(the incident's own numbers, FAIL -> UNKNOWN) and
`test_the_recorder_refuses_to_advance_over_a_suppressed_verdict`. Pinned
alongside: `test_a_headline_moving_on_no_new_rows_still_fails_inside_a_partial_cycle`,
`test_a_zero_headline_still_fails_inside_a_partial_cycle`, and
`test_a_full_cycle_keeps_the_full_verdict`, so the quiet cannot spread.

**Still UNKNOWN.** Which rows the EDGAR backfill posted between 17:51Z and 03:33Z
was not reconstructed — the live API exposes no created-at filter and re-reading
filings costs money the spend guard has rationed. The timing correlation and the
exact arithmetic reproduction are what settle it; the row-level ledger does not.

---

## 2026-08-02 — the spend guard, and what the Railway cron actually costs

**THE ACCOUNT HAD NO BRAKE AND NO METER.** Between 2026-07-26 and 2026-08-02 the
shared OpenRouter balance fell $71.86 -> $22.92, ~$6.45/day, about three days of
runway for both trackers. This repo had no monthly allowance, no month-to-date
measurement and no degrade mode — only `openrouter_balance_check.py`, which
reports a BALANCE. A balance answers "how much is left" and can never answer
"what did that run cost" or "did that money buy anything".

**THE SUSPECT WAS WRONG, AND THE MEASUREMENT SAYS SO.** The working hypothesis
was that ~$4.8/day was `railway/cron.py`, invisible because it runs on Railway
under its own key. It is not. Measured from live `/source-runs` telemetry (4 cron
runs), one run pulls google_news 150 + gdelt 78.5 + edgar 21 + press 0 = ~250 raw
entries, and `seen_urls.filter_already_seen` removes ~60% of them before any
model call. Each surviving entry is exactly ONE `extract_layoff_data` call whose
prompt is bounded at 5,962 chars of system prompt + ~130 header + a 3,000-char
`RAW_TEXT_LIMIT`, i.e. ~2,400 input tokens, ~250 output, ~$0.00082 at DeepSeek-V3's
published $0.2574/$1.0287 per M. So:

    ~100 calls/run -> ~$0.09/run -> ~$0.17/day -> ~$5/month
    250 calls/run  -> ~$0.22/run -> ~$0.44/day  (upper bound, dedup fully failed)

The cron cannot reach $4.8/day; its own caps forbid it. The dominant consumer was
`backfill.py` behind `edgar-history-sweep.yml`, which has NO seen-URL pre-check
(only `gdelt_backfill.py` does) and whose `BACKFILL_LIMIT` caps POSTS, not calls.
Telemetry: 5,044 filings on 07-28 and 4,190 on 07-29 across 13 and 22 runs, i.e.
~$4.4/day and ~$3.7/day, against balance drops of $11.11 and $10.50 those days.
That workflow's own header had already priced it at "~$3.80/day burned for zero
additional rows" and it was reverted to a daily cron in 126adca. **A per-key split
of the remainder is still UNKNOWN**: the keys live in GitHub/Railway secrets, so
no session can attribute the account balance between them. The guard below fixes
that going forward by metering at the point of spend.

**WHAT SHIPPED: `railway/spend.py`**, ported from the sibling tracker, plus the
wiring that makes it cover everything.

- **Month-to-date is a DELTA from a committed month-start snapshot** of the key's
  lifetime usage (`railway/spend_month.json`, committed by the daily balance
  job). OpenRouter's `usage` never resets; enforcing a monthly allowance directly
  against it trips the guard permanently once lifetime spend passes one month's
  budget. That bug shipped in the sibling and killed collection silently. The
  snapshot is keyed by a one-way 12-hex fingerprint, never the key, so the
  Actions key and the Railway key each carry their own month-start in one file
  that is safe to commit.
- **It degrades, it does not halt.** `--degrade` sets `ALT_PAID_READS=off` and
  always exits 0. WARN, SEC/EDGAR structured fields, ERM and every state scraper
  derive their fields from a column and call no model; halting them to protect a
  budget none of them spends is a self-inflicted outage, which is exactly what
  `--enforce` caused in the sibling on 2026-07-30. No collecting workflow uses
  `--enforce`, and a test pins that.
- **Deferred candidates come back.** Every gated function returns `None`, which
  is already each caller's "retry later, row stays queued" value, and
  `seen_urls` drops a URL only when the SITE already holds it. A deferred
  candidate writes no row, so it is re-pulled. Deferral is never an exception:
  an exception would land in a caller's failure counter and could trip cron.py's
  loud "posted 0 with N failures" exit, turning a budget decision into a red
  data job.
- **A per-run ceiling that needs no stored state** ($0.20, 2% of the allowance).
  Railway has no persistent volume, so the month-start snapshot cannot be
  refreshed there and month-to-date is UNKNOWN — which is reported as UNKNOWN,
  not as a pass. The brake that still works meters the CURRENT PROCESS exactly,
  from the `usage` object OpenRouter returns on every completion, and that same
  meter is what makes cost-per-stored-row answerable.
- **The allowance is $10/month, INTERIM**, a policy constant in the diff with the
  reasoning beside it, not a secret. It matches the owner's current interim
  number for the sibling.

**COVERAGE.** 26 paid workflows now run the guard; four scripts that build their
own OpenAI client (`ai_evidence_sweep`, `process_tips`,
`source_verification_audit`, `daily_classification_spotcheck`) gate themselves
because `extractor.py`'s gate cannot reach them; `classification-audit.yml`'s
inline script reads the flag from the environment. `cron.py` runs a spend
preflight before collecting and prints what the run cost and what it bought.

**ops_status.py [2a] RUN COST** reads the two committed ledgers — no key, no
network — and reports $/day, runway and $ per stored row. The balance job now
records the live row count next to each balance reading so that division is
possible at all. On the first run it correctly said: burn $6.45/day, ~$194/month
against a $10 allowance, ~3.6 days of runway.

---

## 2026-08-01 — the trend card shows a trajectory again (2.19.246, 2.19.247)

**THE DEFECT WAS THE DEFAULT SCOPE, not the chart.** The tracker opens filtered
to the current calendar year, so "Jobs cut per month" opened with the months of
that year and nothing else: eight points on 1 August, five in May, one on
1 January. `renderTrend()` already had to switch its point markers back on below
three points or the card rendered as an empty box, which is the same defect
noticed and worked around rather than fixed. With the jobless-claims bars behind
it, the flagship trend read as a bar chart with a curve laid over it, on a table
holding 296 charted months.

**WHAT SHIPPED: a whole-record trajectory strip inside the same card**, under the
chart, showing every month held under the current non-period filters, with the
charted window shaded on it. The Chart.js chart above is deliberately NOT changed
to draw all 296 months: it is the filtered view, it says so, tapping a month
scopes the page, and drawing months the filter excludes would put it at odds with
the filter chips two inches above it. The question the strip answers is the one
the reader actually has, which is where the slice they are looking at sits on the
record.

**THE TECHNIQUE IS THE SIBLING TALENT TRACKER'S**, not a new one
(`tit_trend_svg()` in its shortcodes.php). Its trend card had the same problem for
the same reason, a chart in a card narrower than its own axis labels, and the
answer was to take the TEXT out of the drawing: axis values and the two dates are
HTML beside the SVG so they stay CSS pixels at every width, the SVG holds geometry
only, grid and lines carry `vector-effect="non-scaling-stroke"` so a 2px line is
2px in a 190px card and in a 700px expanded one, and the endpoint dots are a
SECOND svg with no viewBox so their radius is a real pixel rather than an ellipse
stretched by `preserveAspectRatio="none"`.

**NOTHING IS INTERPOLATED, and that is the one rule the strip exists to keep.**
The Chart.js path runs its series through `fillMonths()`, which substitutes
`{jobs: 0}` for a month with no rows. Defensible inside a dense selected year;
not defensible over 296 months, where it would publish a month we hold nothing
for as a month in which nobody was laid off. The strip breaks its path at those
months instead, never draws a slope across them, and prints the count underneath,
because a broken line on its own does not tell a reader whether the break was
meant. A one-month run is emitted as a zero-length line so the round cap renders
it as a dot; a bare moveto draws nothing and the month would vanish silently.

**THE AXIS IS ZERO-BASED AND THE PEAK IS NAMED, which is one decision.** Over the
full record Mar 2020 (709,906 verified cuts) is about seventy times the median
month, so a true zero-based axis leaves two decades reading as a low band under
one tower. That IS the shape of this dataset and rescaling to hide it would be
the lie. What a reader cannot do is tell whether a flat-looking stretch is a
quiet market or a broken chart, so the tallest month is named in the caption,
which costs the drawing nothing.

**COST: two SQL statements, and not on the cold render.** The whole-record series
is a second `/aggregate` asking `include=series` only, which is one grouped
monthly SUM plus the totals row the endpoint will not let a caller drop, against
the ~31 statements the default runs (measured 8.1s for `country=United States`,
19.0s with `sourced=1`). It is fetched only once the card nears the viewport, and
the card sits ~9,600px down the page, so a visitor who never scrolls to the trend
pays nothing and the first paint is untouched. With NO period filter set the
chart above already IS the whole record, so the strip hides itself and makes no
request at all. `include=series` measured 2.2s live against the default
aggregate's 8.1s+; a failure hides the strip, because a trend that could not be
drawn must not become a trend drawn wrong. No new block was added to
`alt_aggregate_default_blocks()`.

**VERIFIED, not asserted:** five cases rendered in a browser at the real mobile
column width (219px) before the deploy, against live production series data, and
each one changed something: a single-month scope band was under a pixel wide and
invisible until the marker got a floor; the "shaded band" sentence printed with
no band drawn when the charted window fell on months a filtered view holds
nothing for; and the sparse-history case is what showed the lone-month dots
working. 19 new offline tests, two of which were made to fail by hand (a zero
substituted for a gap, and a dropped `include`).

**THREE MORE DEFECTS IN THE SAME CARD, FOUND BY OPENING IT AT 375px AFTER THE
DEPLOY, NONE OF THEM THIS FEATURE (2.19.247).** The card is ~177px of canvas at
that width, and Chart.js does two things there that no test and no curl can
see. (1) It caps how much of a small canvas an axis may claim and then draws a
label wider than the cap PAST the canvas edge rather than shrinking it: the left
axis rendered as **"0,000" and "0,000"** with the leading digits gone. Numeric
axes now use a compact form below 420px of box, and only where the chart is
still on the DEFAULT formatter, so the percent axes are untouched. (2) The
right-hand claims axis TITLE was drawn rotated on top of its own tick labels
with its first words clipped off the edge; it is dropped at that width, where
the legend and the note under the chart both already name the series. (3) The
legend neither wraps nor truncates, so **"Announced plans (not yet in the
verified floor)" rendered as "ounced plans (not yet in the verifie"**; the two
long labels shorten below 420px and keep their full wording everywhere else,
because the distinction the long one draws is the reason that line exists.
`narrowChartBox()` is the single definition of "narrow", and a clientWidth of 0
means NOT LAID OUT rather than narrow, falling back to the viewport: the first
version read 0 as narrow and shipped abbreviated labels to a 718px desktop card,
which is what checking the wide case caught. Also fixed: the strip's two caption
`<p>` elements rendered at **16.8px against the 12.5px heading above them**,
because the theme sets `.entry-content p` with `!important`; same high
specificity plus `!important` override the stylesheet already uses for
`.alt-sb-actions`.

**UNVERIFIED:** the private benchmark (`scratchpad/bm-live.html`) was not
refreshed. `data_integrity.headline_movement` was FAILING live when this
session started (+63,899 jobs over a day on rows carrying at most 61,211) and it
reddened the `Tests` run for the 2.19.246 push, which is a live-data assertion
and not this change: the strip adds no rows and alters no aggregate arithmetic.
It was passing again (8/8 verified) about an hour later without intervention,
which is worth someone's attention rather than a shrug, because an invariant
that clears itself either healed or moved.

**ALSO NOT VERIFIED THE WAY IT SHOULD BE:** the browser pane here reports
`document.visibilityState = "hidden"`, so **IntersectionObserver never
delivers** and every lazy-gated card on this page (the map, the conversion
chart, and now this strip) stays unbuilt in it. The strip was therefore rendered
against the DEPLOYED minified bundle, the deployed stylesheet, the live page's
own markup and live series JSON, served from localhost with
`IntersectionObserver` removed so the documented no-IO fallback runs. That
exercises the drawing, the CSS and the data end to end; what it does NOT
exercise is the observer wiring itself, which is copied from the map and
conversion cards already in production.

---

## 2026-08-01 — where the missing SEC Item 2.05 filings actually go (no plugin change)

The gold-set measurement earlier today said 24 of 57 (42.1%, Wilson 95% CI
[30.2%, 55.0%]). It said HOW MANY we miss. This entry is the follow-up that
says WHERE they are lost, because the obvious answers were all wrong and each
one was refuted by a measurement rather than by an argument.

**The framing fact nobody had looked at.** Of the 24 events scored `matched`,
exactly ONE — Ultragenyx, 2026-02-12 — reads "sourced from this very 8-K". The
other 23 matched through WARN, ERM or news. So the 42.1% is carried almost
entirely by other collectors, and the SEC path contributes ~2% of it. Rows with
`source_type=8K` per year, straight off `/query`:

| 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 219 | 30 | 10 | 7 | 115 | **4** | **8** |

Zero in eleven of the twelve gold months; 1 in 2026-04; 6 in 2026-07. All the
while `edgar` reported `ok` twice a day with 17-50 candidate documents, and
`ops_status.py` printed ALL CLEAR. This is the "source health is not data
integrity" split in CLAUDE.md, and it is the sharpest example we have: **the
collector was healthy and the collector was producing almost nothing.**

**Candidate 1 — the `MAX_PAGES_PER_KEYWORD = 3` cap — is not it.** Measured
against live EFTS, no hypothesis:

| window shape | (keyword, form, window) probes | cap binds |
|---|---|---|
| 12 monthly windows (history-sweep shape) | 432 | 12.0% — 23.6% on 8-K |
| 8 two-day windows (daily-cron shape) | 288 | **0%** |
| keyword `item 2.05`, 8-K, each gold month | 12 | **0%** (busiest month 27 hits vs a cap of 30) |

Then the direct test: replay the production search over every one of the 33
misses, in both window shapes, capped and uncapped. **33 of 33 reachable under
the cap in both shapes. 0 lost to the cap. 0 UNKNOWN.** The cap does discard
945 hits/year on high-volume generic phrases (`layoffs`, `restructuring plan`),
which is worth revisiting on cost/coverage grounds — but not one of these
filings is lost there, and raising it would have "fixed" nothing.

**Candidate 2 — the extractor discarding them as non-events — is not it
either.** `railway/edgar_recall_probe.py` (new, dry run, manual dispatch only)
rebuilds each miss's raw dict through the real collector and runs the real
extraction with the real gate functions imported from `extractor.py`. Result:

```
  29  accepted            <- would post today
   3  model_returned_no_job_count
   1  count_not_verbatim_in_window
```

**29 of 33 are accepted by the pipeline as it stands**, and 28 of those recover
the filing's exact stated headcount. The model is not throwing these away. All
four drops share one cause and it is not judgment — the stated count was outside
the text the extractor reads:

* **EnerSys 2026-03-25 (474)** — "approximately 474 employees", 1,756 characters
  after the Item 2.05 heading. Inside the 3000-char window `edgar.py` built on
  purpose; outside the 2000-char truncation `extractor.py` applied. Fixed below.
* **Codexis (46), PLAYSTUDIOS (177)** — the count is nowhere in the stripped
  primary document; it lives in the EX-99.1 exhibit. A known limit, not fixed
  today, recorded so it is not rediscovered as a mystery.
* **Wabash National (270)** — the gold set's 270 is the SUM of four separately
  stated components ("3 salaried and 53 hourly" + "21 salaried and 193 hourly").
  Our extractor refuses derived counts by design. **This one is working
  correctly and must not be "fixed"** — weakening `_count_in_text` to admit it
  would re-open the exact hole that published Intuit as 17 jobs.

**Candidate 3 — the window and the schedule — is where it breaks, but not in
the half we expected.** The daily cron is fine: `days_back=1` at 13:00 and 22:00
UTC gives every calendar day two independent covering windows, and the run
ledger shows two `ok` runs a day with no missing day. The broken half is the
**rotating history sweep**, which is the only path by which a past month is ever
searched again:

```
2025-07..2025-10   last swept 2026-02-25..28   (154-157 days ago)
2025-11, 2025-12   last swept 2025-12-09/10    (234-235 days ago)
2026-01..2026-06   NEVER swept in a 3-year lookback; next due 2027-07
```

`months[now.toordinal() % len(months)]` is not a cycle over that array, because
`len(months)` grows by one every calendar month and the newest months sit at the
top — exactly where the moving wrap-point keeps jumping past them. Only **8.5%**
of runs (80 of 944 simulated) landed on a month from the last twelve. The
workflow header promised "every past and current-year month keeps getting
re-verified and any gap self-fills". That was false for the entire recent past,
and it had never been asserted anywhere.

**What this does and does not explain.** 10 of the 33 misses are reachable ONLY
through keywords added on 2026-07-18 (`item 2.05` targeting) and 2026-07-20
(restructuring/headcount phrases). For those ten the chain is complete: the net
widened, the daily cron only ever looks two days back, and the sweep that was
supposed to replay the improvement over past months never returned to them. The
other 23 were reachable with the older keyword list too, and **why they were not
ingested at the time is not established** — this repo's git history begins
2026-07-14, so the code that ran during the gold period is not available to
inspect, and guessing would be worse than saying so. What is established is that
the recovery path was structurally absent in every case: nothing re-searches a
month once it has scrolled out of the 2-day window.

**Fixes shipped.**
1. `backfill.rotating_month()` replaces the modulo walk. One run in three
   re-verifies a month from the last twelve; the rest walk the whole history,
   both indexed from the NEWEST end so a month joining the rotation perturbs
   ancient history instead of the recent past. Still purely date-keyed, so the
   once-a-day cadence rule and its test still hold. Measured over a 120-day
   window: recent months re-verified 12 of 12, against 0 of 12 before.
2. `extractor.RAW_TEXT_LIMIT` (3000, was a bare `2000` at the call site) now
   covers the largest window any collector builds. `sources/gdelt.py` builds the
   same 3000-char window, so this had been silently cutting the news path too,
   not just SEC.

**Guards added, both of which fail on the old code (checked, not assumed):**
`tests/test_extractor_text_budget.py` pins the extraction budget as a ceiling
over every collector's declared window, and pins the truncation to the named
constant so a pasted literal cannot restore the bug.
`tests/test_rotating_cron_cadence.py` gains
`RotatingWindowReachesRecentMonthsTests`, which fails unless every month of the
last twelve was re-verified within 120 days — while still asserting the deep
history keeps being walked, so "recency priority" cannot quietly become
"recency only".

**The floor is NOT raised in this entry.** `recall_goldset.MATCHED_FLOOR` stays
at 20. Recall is measured against what is actually published, and none of these
filings are published yet — the fixes change what the pipeline WILL do, not what
the data currently holds. Raising the floor on the strength of a replay would be
exactly the kind of unearned number this repo keeps writing incident entries
about. It moves when a re-measurement moves, and not before.

---

## 2026-08-01 — the recall claim becomes measurable, and able to fail (no plugin change)

**What was wrong.** `railway/recall_precision.py` had printed a recall
percentage since it was written and `main()` ended in `return 0` whatever it
printed. There was no threshold anywhere, so a coverage collapse could not
redden CI, could not reach `ci_alert.py`, and could not appear in `ops_status`.
That is the "a check that resolves to a silent pass" failure this repo forbids,
one level above the bug `data_integrity.py` exists to catch.

It was also measuring something weaker than it sounded. `seed_data/recall_goldset.csv`
is 40 hand-listed companies from a research sweep — Amazon, Microsoft, Meta,
Oracle, Volkswagen — matched by asking whether that company appears **anywhere**
in our data **that year**. Company-presence-in-a-year is not event recall, and a
set made of the year's most-reported cuts cannot fall far. Its 80% is a smoke
test, not a coverage figure. It is kept, still printed, now labelled for what it
is, and carries no threshold. Nothing was deleted or weakened.

**The gold set, and why it is independent.** Every SEC Form 8-K filed
2025-07-01..2026-06-30 whose **structured** `items` array carries code 2.05
(Costs Associated with Exit or Disposal Activities) — the code the filer put in
the SGML header, not a text match: 215 accessions. The enumeration was
re-pulled month by month with an independent query ("exit or disposal
activities") and it returned **zero** item-2.05 filings the first query had
missed, in all twelve months; two further controls added nothing. Every document
of every filing was fetched from `www.sec.gov/Archives` and the 64 with a
number-plus-employee-noun sentence were read by hand. A filing enters the set
only if it states an **absolute** count of affected employees. Five were excluded
for stating only a percentage, a retained headcount or a pre-action total —
Intel's "end the year with a core workforce of about 75,000" is the remaining
staff, Atara's "15" is who is kept, Geron's "260" is the pre-cut total — because
`extractor.py` rejects derived counts by design and scoring a documented design
decision as a miss would be measuring the wrong thing. Two accessions were the
same announcement filed twice and were collapsed. **57 events.** Primary
regulator index, no aggregator, no competitor list, selection rule fixed before
any tracker query. It is *not* independent of the tracker's design: an EDGAR
collector already reads this corpus, so it measures whether the pipeline
captures what its own primary source publishes.

**THE MEASUREMENT: 24 of 57 = 42.1%, Wilson 95% CI [30.2%, 55.0%].** The
interval is the honest form. n=57 supports "well under half" and supports no
figure to the nearest percent, and it describes ONE source family (US public
companies filing Item 2.05 with an explicit count) over ONE window. It says
nothing about private employers, non-US employers, WARN-only or news-only
events, and must never be quoted as "the tracker's recall". Also measured, with
intervals for the first time: count precision **38/39 = 97.4% [86.8%, 99.5%]**
(56/57 on a wider draw), AI-attribution precision **53/53 = 100% [93.2%, 100%]**
— which is exactly why the interval matters, because 53 observations are not
certainty.

**The misses are not a source outage.** `ops_status.py` was ALL CLEAR with the
EDGAR collector healthy while HP's 4,000-6,000, Newell's 900, Autoliv's 2,200
Türkiye, Molson Coors' 400, Elanco's 300, Domtar's 350, GoPro's 145 and Beyond
Meat's 44 were absent from the published data, each disclosed in an 8-K the
tracker's own collector reads. `sources/edgar.py` caps at
`MAX_PAGES_PER_KEYWORD = 3` (30 hits per keyword per form) and prints a warning
when a keyword matches more; that is one candidate cause and is left for a
follow-up, not fixed here.

**THE MACHINE MUST NOT PROMOTE ITS OWN RECALL.** The deterministic alias/window
matcher scored **31** of 57 against the editor's **24** — twelve points of
inflation. It had accepted a Hormel Georgia WARN filed ten weeks *before* the
announcement it was meant to represent, an Italian composites maker for HP Inc,
Dow Jones for Dow, and an Ohio WARN for a plan explicitly scoped to EMEA. So the
numerator counts only editor-confirmed events; a row that newly satisfies the
rule for a not-matched event is printed as `ADJUDICATE` and never counted. The
rejected candidates are recorded per row so they do not resurface every week.
Separately, the live `company=` filter is a substring LIKE and it returned
Experian for Xperi, Capgemini for Gemini, Insight Behavioral for Sight Sciences
and a Baltic fish processor for KALA BIO — hence a token-**prefix** match, with
a test naming all four pairs.

**The threshold, and why it is a count and not the interval's lower bound.**
`recall_goldset.MATCHED_FLOOR = 20 of 57`. Two different questions were on the
table and mixing them is the scope error `plausibility_ratio()` refuses: the
Wilson bound describes uncertainty about the **population**, while the gold set
is **frozen** and re-measured, so between runs the denominator cannot move and
the numerator changes only on real gain or loss. There is no sampling noise to
absorb. Twenty is four events below today's 24 — enough headroom that a company
rename breaking one alias or a dedup merge does not redden CI, few enough that a
collector regression or a bad purge-reload does. Precision is the opposite case
(the sample IS redrawn each run), so its floor is on the **Wilson lower bound at
0.80**, which trips at six bad rows in 57: about one false alarm every 200 runs
if the true rate is 98%. A 0.85 floor would trip at four and fire ~1.5 times a
year for nothing, and eight identical emails is how an alert channel gets
filtered.

**Wiring.** New stdlib-only `railway/recall_goldset.py` holds the bound, the
Wilson helper, the matcher and `judge()` — one definition, read by
`recall_precision.py`'s exit code, by `data_integrity.RecallFloorInvariant`
(registered in `INVARIANTS`, so `ops_status` [3] renders it and
`tests/test_dedup_live.py` asserts it) and by the tests. `recall-precision.yml`
now commits `railway/recall_measurement.json` and exits non-zero on a breach, so
`ci_alert.py` mails the real assertion. The invariant is the only one that reads
a committed file rather than the live API, because re-measuring is ~60 requests
against a host that 504'd twice on 2026-07-31 and `ops_status` is the first
command of every session: the cost is that a regression surfaces within a
**week**, which is the cadence the job actually runs at, and the staleness
ceiling (9 days) matches it.

**Three states, kept apart.** An event whose lookup fails is UNREACHABLE, never
a miss; above 6 of 57 unreachable the whole measurement is UNKNOWN. A missing or
stale measurement is UNKNOWN. A host outage cannot manufacture a recall
regression — the same rule `ci_alert.py` learned on 2026-07-31.

**Not published.** The set is `internal_regression_reference_not_published_to_benchmarks_recall`
and a test asserts it. `/benchmarks/recall` stays reserved for the California
sample that cleared the three-reviewer independence gate.

**Verified:** 24 offline tests green in `tests/test_recall_goldset.py`; full
`railway/tests` green apart from the known `test_archive_backfill` missing-
`requests` failure; `ops_status.py` ALL CLEAR exit 0 with **8** data-integrity
checks; `python3 railway/data_integrity.py` prints the new line with its
interval. **Unverified:** the weekly workflow's commit step has not run in
Actions yet (its git push loop is untested in situ); the ~60-request measurement
has only been run from one machine, so its behaviour under a Bluehost 504 is
proven by unit test, not in the field; and no second editor has reviewed the 57
match decisions.

---

## 2.19.233 — one company page per employer (the gate was never the problem)

**What was wrong.** 29 employers had a page against ~41k distinct employer names
in the table, and 17 of the 24 largest employers by event count had none (Boeing:
324 events, no page). The audit of 2026-07-28 had already named the cause and it
is worth repeating because it is the opposite of the obvious diagnosis: **the
indexability gate was sound, the THROUGHPUT was the defect.** The autopilot
considered only keys with >=3 source-linked events and admitted at most 25 a
week, so the backlog grew faster than the indexer drained it. Nothing was
misconfigured; the mechanism could not finish, and had no way to say so.

**What changed.**
- The indexer floor drops to ONE source-linked canonical event, which is the
  floor for a page EXISTING. `review_status` now records which side of the
  indexability floor the employer falls on: `approved` (indexable, sitemapped)
  at >= 2 such events, `noindex` (page renders, stays out of search) at one.
  Zero is a real floor: with no retained source URL there is nothing to link to.
- **Resumable.** Each call returns `next_cursor` + `complete`; the workflow loops
  until the server says complete. Ordering is by `company_key`, not by event
  count, because admitting a row removes it from the candidate set and an ORDER
  BY on a count that moves under ingest skips employers silently.
- The page's rows now come through `alt_api_query_compute()` instead of its own
  SQL. That is not tidying: it is how the page had become **the one surface that
  never learned about supersets.** `/aggregate`, the report pages and the press
  page all append `superset_of = 0`; this did not, so a reconciled rollup row and
  the per-site rows it absorbed were both listed AND both summed into the page
  total. Three filters were added to the shared builder to make that possible:
  `company_key` (exact identity), `sourced=1` (canonical row of an event that
  retains a source URL) and `exclude_supersets=1`.
- **Meta description, and a Dataset node** on indexable pages only, `isPartOf`
  the tracker's dataset so it reads as a slice rather than a rival dataset with
  the same name. Company pages had no description at all (audit item 4).
- **The 1,798 orphan entry permalinks now have a path.** The company page links
  each entry, and each entry links back up to its employer. They were indexable
  and linked from nowhere.

**Three defects found while doing it, none of them the assignment.**
1. `alt_db_where()` was not alias-safe. Every existing filter uses bare column
   names, which bind under any alias, so it had never mattered; a correlated
   filter must name the outer row, and MySQL **hides the real table name once an
   alias is given**, so `sourced=1` on `/conversion` (`FROM $table a`) would have
   been an unknown-column 500. `$alias` is now a parameter and that one caller
   passes it.
2. The autopilot's docstring said it picked "the most frequently reported company
   name"; the code took whatever row a `SELECT DISTINCT` returned first. Now
   actually modal, ties to the shorter name. Related: it **parked any key whose
   rows disagreed on the name**, which denied a page to precisely the large,
   heavily-reported employers pages are most useful for. Spelling variants are
   what `company_key` exists to collapse; the page prints each row's own reported
   name, so the variants stay visible.
3. Company pages set `DONOTCACHEPAGE` + `nocache_headers()` unconditionally.
   Invisible at 29 URLs; at one per employer it makes every crawler hit an origin
   request on a shared host that returned 504 twice on 2026-07-31. It never
   bought freshness either, since the data sits in a 5-minute transient
   regardless. Rendered pages are now cacheable for 10 minutes; a MISS is still
   uncacheable, because that slug becomes real the moment the indexer admits it.

**2.19.234, the same day: the fix that could not reach the employers it was for.**
Dropping the "qualifying events disagree on the company name" park was correct
but inert on its own. A parked key already had a `pending` directory row, the
candidate query treated ANY directory row as "already mapped", and so the
employers the old rule had caught stayed invisible forever. That set is not
random: it is the largest employers, because scale is what produces name
variants. Boeing files as "Boeing", "Boeing Co", "Boeing Company", "The Boeing
Company" and two misspellings, so its 324 events bought it a pending row and no
page, and `/company-layoffs/boeing/` was a 404 AFTER the coverage work landed.
Only `approved`/`noindex` counts as mapped now. The identity sanity gate still
runs on every reconsidered key, so this promotes nothing that could not be
admitted fresh. **The general lesson: when you retire an admission rule, the
records it already rejected do not re-enter the funnel by themselves.**

**Also:** the sitemap query ran one correlated COUNT per approved directory row
(fine at 29, a timeout at thousands) and is now a single grouped join; the public
`/company-directory` listing is paged (it returned one row per page in one
response); the health page publicly claimed a "three or more" threshold while the
gate was two.

---

## THE RESULT CARD CONTRACT (canonical spec, shared with the sibling tracker)

**Machine-readable copy:** `docs/card-contract.json`
**sha256:** `5ce62ea8d11073b132af83696e222f0a2c4184fba646c5f0adcb9c06f7493af2`
**Contract version:** 1.0.0, adopted 2026-07-31.

That file is **byte-identical** in `dk-forge/ai-layoff-tracker` and
`dk-forge/talent-intelligence-tracker`. This section and the section of the same
name in the sibling's TECHLOG are the human copy of it, and the digest above is
how you tell whether the copy you are reading is current.

### Why a contract and not shared code

The two trackers render the same kind of fact: an employer, a place, a
direction, an evidence tier, an amount, a headline, a source. The owner
screenshotted the talent tracker's list, liked it, and asked for the layoff
tracker's to match. By the time an agent looked, the talent tracker had already
changed its own labels, so neither side could say which design was current.

**The mismatch was not the defect. The inability to say which one was current
was the defect.** Matching the pixels once would have fixed nothing; they had
already drifted once and would drift again.

Shared code was considered and rejected. Different repos, different tables,
different REST namespaces, different plugins, different deploy paths, different
languages on the server side (one renders the first paint in PHP, the other
inlines a bootstrap and renders in JS). A shared library across that boundary
buys a smaller problem at the price of a much worse one: a coupled release
cycle, and a change to one product's card blocked on the other product's deploy.

What is shared is the **contract**, and what enforces it is a build that goes
red when one side wanders.

### The card

Every class below is a **suffix**. Each product renders it with its own prefix:
suffix `card-rail` is `alt-card-rail` here and `tit-card-rail` in the sibling. A
product may put extra classes on the same element (its own colour and state
classes); the contract class must be present.

```
<ol|ul class="{p}-cards">
  <li class="{p}-card">
    <div class="{p}-card-rail">            who, and where
      <span class="{p}-card-employer">     serif
      <span class="{p}-card-industry">     optional; ABSENT when unknown, never blank
      <span class="{p}-card-where">        location, or "Location not stated" in {p}-card-nowhere
    </div>
    <div class="{p}-card-body">
      <div class="{p}-card-badges">        direction, evidence, amount, then the product's own
        <span class="{p}-card-dir">
        <span class="{p}-card-ev">
        <span class="{p}-card-amt">        ONLY when there is an amount
      </div>
      <a|span class="{p}-card-h">          the fact, one line; link colour only when it links
      <p class="{p}-card-rt">              our plain-English read, visually separated
      <div class="{p}-card-foot">
        <time class="{p}-card-when">       or "Date not stated" in {p}-card-nowhere
        <span class="{p}-card-src">        publisher, outbound; archived copy SECOND, never instead
      </div>
    </div>
  </li>
</ol>
```

### The words

| Stored | Label |
|---|---|
| `hiring` | Adding Roles |
| `displacement` | Cutting Roles |
| `comp_shift` | Pay Change |
| `neutral` | Headcount Not Stated |

The **keys are each product's own and are not shared**; the four strings are.
The talent tracker reads them off its `signal_direction` column. The layoff
tracker has no such column and derives its key: a record naming a headcount is
`displacement`, a record naming none is `neutral`. `hiring` and `comp_shift`
never occur there, because everything it holds is a cut. They are absent, never
renamed, never reused for something else.

**Why this vocabulary.** "Adding Roles" replaced "Hiring up" in the talent
tracker after the owner asked what "hiring up" meant, which is a fair question
about a phrase nobody says: "up" was doing the work of "the source told us
headcount is going up". "Cutting Roles" is its opposite in the same shape, where
"Cutting back" could have meant costs, hours or investment. "Headcount Not
Stated" replaced "Other change", which told a reader nothing: it is the bucket
for a record whose source says nothing about headcount at all, and naming it
that way is truer to the rule that neither product infers a direction its source
did not state. That reasoning stands, so the layoff tracker adopted it rather
than the reverse.

**Why Title Case here specifically.** The general house rule is sentence case,
and it still governs every label outside these four. These four are the
exception on the record: the owner has asked for Title Case three times, the
talent tracker's `tests/php/render_dashboard.php` enforces it on its display
labels, and the decision that created this contract quoted the four strings in
Title Case. Changing that is a contract change, not a tidy-up.

**Evidence labels stay each product's own**, because the evidence really is
different (`SEC filing / WARN notice / Press release / News` against
`Official Filing / News Report / Unconfirmed`). What the contract fixes is the
**slot**: second badge, always present, always carrying words and never colour
alone.

**Shared verbatim:** "Location not stated", "Date not stated". Said out loud,
never left blank, never guessed.

**The amount badge is omitted when there is no amount.** It is not a pill
reading "count not stated" or "no funding stated": the direction badge has
already said so, and two badges saying one thing was the duplicate this contract
removed.

### Accessibility, pinned because both products already paid for it

- Anything that opens more detail is a real `<button type=button aria-expanded>`,
  never a click handler on the row. The layoff tracker's expander was a
  mouse-only `<tr>` click; it is a button and stays one.
- **No `aria-label` over visible text.** An aria-label on an element that
  already has text replaces that text for a screen reader; the talent tracker
  shipped longer, invisible, differently worded labels over its visible ones.
  Inside a card an aria-label is allowed only on an element with no text of its
  own, and today no element in either card qualifies.
- `title=` is a supplement. Nothing a reader needs lives only there.
- Source links: `target="_blank"` with `rel` containing `noopener`.

### 375px

The rail stacks above the body and nothing else changes. Nothing inside a card
sets a fixed width or a min-width; long values wrap with
`overflow-wrap: anywhere`. **Do not validate this with
`scrollWidth === innerWidth`** — that passes on a clipped page, an
`overflow-x: clip` on a narrow ancestor guillotined the talent tracker's hero
headline in 1.37.0, and the layoff tracker's theme ships an inline
`html,body{overflow-x:hidden}` that makes the comparison meaningless there too.
Both test suites therefore check the **cause** (no pinned widths, wrapping on
the free-text fields) rather than the symptom.

### What stops it drifting again

Three mechanisms, and each covers what the others cannot.

1. **`test_card_contract` in each repo**, offline, on every push. Reads the
   contract and asserts that the markup that repo actually renders satisfies it:
   every required class, the badge order, the region reading order, the label
   maps parsed out of the source, the two a11y rules, the mobile rules. It
   cannot see the sibling.
2. **The digest, recorded twice per repo** — in the test and in this section.
   An accidental edit to the contract fails the test. A deliberate edit means
   updating the digest, which is the moment you are told this is a two-repo
   change.
3. **`.github/workflows/card-contract.yml` in each repo**, which fetches the
   sibling's copy of `docs/card-contract.json` and goes red while the two
   differ. This is the only mechanism that can see across the repo boundary,
   which is why it needs a network and lives in CI rather than in the offline
   suite. Both repos are public, so it needs no token.

**Changing the card is a four-step job and you cannot do three of them and
ship:** edit the contract, update the digest in the test and here, change the
markup, copy the contract into the sibling. Miss the last step and both repos go
red until somebody finishes.

---

## Version history (plugin `ALT_VERSION` = git commits on main)

All 2026-07-14 → 07-15 unless noted. One intense build day + hardening day.

| Ver | What |
| 2.19.235 (Jul 31) | **Guardrails so one bad row cannot move a headline number again — and so the Spirit comparison becomes unwritable rather than merely fixed.** Every incident in the log below is the same story: one row, or one bad comparison, moves a number the site publishes as fact, and nothing between ingest and the front page catches it. The four live invariants that existed were **named-event tripwires** — Coinbase, Spirit, Tyson, AT&T — each written after the event it names, and silent about the row that lands tomorrow. Three SHAPE guards now sit in the same registry (`railway/data_integrity.py`, one definition, imported by the test, ops_status and the digest — no second parallel set). **(1) `headline_concentration`: no single row may carry a published headline.** `/aggregate` gains a `concentration` block computed with `$where_dd` — the SAME WHERE, params and superset-deduped population as `totals.jobs` — carrying the largest single counted row AND the headline it contributes to, in one response. The co-scoping is the mechanism, not a detail: a consumer cannot accidentally measure a row against a differently-scoped denominator, which is the Spirit defect one level up. Bounds are shares, measured with headroom over the live reading and pinned by a test: trailing-90-day worldwide 20% (live 3.44%), AI all-time 25% (live 9.85%), worldwide all-time 1% (0.30%), US all-time 2% (0.86%). Against the trailing-90-day slice the RI 98,912 misparse reads 34%, the AT&T 78,788 TEST notice 27%, Coal India's by-2050 projection 25% — and a real 50,000-job announcement reads 17% and passes. **(2) `headline_movement`: no headline may move in a way the rows do not explain.** Day-over-day against `railway/headline_baseline.json` (committed, because the data changes without a commit and a runner-local baseline resets every night). A move passes if it is under the floor, or the rows that arrived OR LEFT can carry it, or one ARRIVING row that is itself inside its concentration bound is the whole move. Otherwise FAIL. The binding condition is Δentries ≈ 0 with jobs moving — a total re-scoring rows already published. The recorder **refuses to advance a FAILING slice**: recording it would make the defect tomorrow's normal, which is the guard laundering the bug instead of catching it. **(3) `dedup_denominator_scoped`: the wrong denominator is now unwritable.** 2.19.227 corrected the arithmetic but left the company's whole WARN history one variable away from the comparison. `alt_dedup_window()` is now the only thing in pass (1) that can produce a sum, and its constructor IS the window filter — there is no argument that yields an unwindowed total, no default window, and a window wider than `ALT_DEDUP_MAX_WINDOW_DAYS` (200) is rejected as an all-time sum in disguise. The ≥50% verdict lives only in `alt_dedup_subset_verdict()`, which **throws** on any denominator that did not come from the window. Pass (1) owns no `+=` and no share comparison; a static guard asserts exactly that, and fails if either returns. Proved behaviour-identical to the inline version over 5,469 randomised company groups / 3,914 marks, zero mismatches. In Python the same rule is a type: `Scope`/`Quantity` with `share_of()` (same scope required, unbounded fine) and `plausibility_ratio()` (same scope required, unbounded denominator raises `UnboundedDenominator`). **Three states throughout, and a fourth word for one of them:** an UNKNOWN that this environment cannot answer yet — a deployed build predating the field, a baseline not yet written — is marked PENDING. It is still UNKNOWN on the dashboard, still UNKNOWN on the ledger, and the daily workflow still exits non-zero on it; PENDING only lets the unit suite skip rather than redden every push for the two minutes an FTPS deploy takes. `ops_status` prints `NOT WATCHING YET` and exits 3. `Report.one_line()` now renders a shape guard's real assertion instead of `= None`, so `ci_alert.py` mails the cause and not a shrug. 41 new offline tests. **Honest ceiling, stated because it matters:** the movement guard catches step changes, not the Spirit defect itself — a 4,000-job un-match on one company on a normal ingest day is inside the daily noise at headline scale, and a bound tight enough to see it would fire every day. That drift is what the per-company invariants and the reconciler's own `changes` diff are for. |
| 2.19.227 (Jul 30) | **Superset dedup pass (1) is windowed on both sides, and SEC 8-K rows enter the dedup for the first time.** Live defect: Spirit US-2026 went 7,069 → 11,069, the May-5 news 4,000 stacking on the May-2 WARN sites, red on three CI runs. The pass established "same event" with a ±45-day proximity check but then tested plausibility (`news ≥ 50% of WARN`) and marked members against the company's **all-time** WARN sum. That sum only grows, so every match sat on a fuse — Spirit's margin had been **38 jobs** (4,000 vs half of 7,923) and the day the all-time sum reached 8,922 the half-bar moved to 4,461 and the news row silently started counting. The same bug ran in the other direction too: when a news total exceeded the all-time sum it marked WARN rows from **unrelated years** as members of that one event. Both sides now use only the rows inside the window (Spirit: 6,109 jobs of near WARN vs the 4,000 news total → news is the subset, 7,069 restored). **Second defect found in the same function:** `in_array($st, ['news','erm','8k','press_release'], true)` against EDGAR's `source_type = '8K'` (uppercase, as written by `sources/edgar.py` and as matched by the `'8K'` literals elsewhere in db.php) never fired, so **no SEC filing had ever participated in superset dedup** and an 8-K company-wide total stacked on its own WARN sites permanently. Comparison is now case-folded. Third change, diagnostic: the endpoint's response gains `changes` (marks that differ from what is already stored) and `detail=1` lists them — the daily run had been reporting three totals that drifted 668 → 543 → 534 → 519 members over four days with nothing to say which pairs had quietly stopped matching. |
| | **Applied, with the size of it stated plainly: the fix moves the headline UP by ~53,400 jobs, and most of that is not Spirit.** The dry-run diff across the whole table: **89 companies change. 64 of them (60,367 jobs) were double-counting** a news or 8-K total on top of their own WARN sites — United Airlines 18,038, Spirit Airlines 5,128, American Airlines 4,362, Meta 3,969, Spirit AeroSystems 3,896, Walmart 2,824, Tesla 2,688, Bed Bath & Beyond 1,766, Hertz 1,624. **43 of them (113,786 jobs) had the opposite defect and are now restored**, because the old all-time denominator let one news total swallow WARN rows from years it had nothing to do with. The worst case is the clearest: **Boeing's real October-2024 announcement of 17,000 was itself marked as a subset of a single WARN row and counted zero**, while unrelated Boeing WARN notices counted instead. Also restored: Amazon 16,951, Tesla 14,000, Microsoft 12,098, Meta 11,000, Intel 7,987, Cisco 5,600. Live headline 20,111,915 → 20,166,034; `members_marked` 519 → 438; `jobs_excluded` 160,598 → 107,179. Spirit US-2026 **11,069 → 7,069** and all four live guards green. |
| 2.19.228-229 (Jul 30) | **`probe=<employer>` on the reconcile endpoint, and a truncation the diff was hiding.** Working out why one row was not being marked meant inferring `company_key` from the outside for an hour — through `COUNT(DISTINCT company_key)` in an aggregate response — because nothing exposed what the reconciler actually loads. `probe` now dumps it: every input row for an employer with its id, its `company_key`, and the mark it gets. It immediately showed the thing the inference could not: Spirit's TX and BWI and O'Hare notices key as `spirit airlines dfw may 2026`, `spirit airlines bwi`, `spirit airlines at o hare airport` — **rows that look like the same employer but never meet, because the WARN filer wrote a site name into the company field.** (Not fixed here; it is an entity-resolution job, and it makes those sites count separately rather than wrongly.) 2.19.229 raises the `detail` list cap 500 → 2000 and makes the workflow print `listing N of M (truncated)`: at 576 changes the 500-row cap silently dropped the Spirit news row from the diff and **made a working fix look broken** for two deploys. A bounded diagnostic must say when it is bounding. |
| 2.19.226 (Jul 30) | **The results table becomes a list of cards, and DataTables is removed entirely.** Owner ask, looking at the sibling talent tracker's results list: "why can't we have the cards look just like this exactly? And we have the source link and wayback link for both?" No code shared with the sibling (standing rule) — its markup and stylesheet were read, then equivalents written in `alt-` classes. |
| | **CORRECTION TO THE BRIEF, and the most important line here: the sort was NOT client-side.** The working assumption handed to this session was that DataTables pulled rows into the browser and sorted them there, so "largest cuts" only ever ordered the loaded page — a real defect worth writing up. **It is not what the code did.** The instance was `serverSide: true` (layoffs.js:2178) and its `ajax` callback mapped the clicked column to `p.sort`/`p.dir` and posted them to `/query`, where `alt_api_query_compute` (db.php:3520-3546) does the `ORDER BY` and the `LIMIT/OFFSET` against the whole filtered set. **So sorting has always ordered all 63,670 events, and no reader has ever been shown a wrong "largest cuts" view.** Nothing needed fixing; DataTables was drawing the pager and the sortable headers and nothing else. That is exactly why it could be deleted without replacing any capability — and why no `docs/TECHLOG.md` incident entry was written for a defect that does not exist. |
| | **What the removal actually bought.** The two cdnjs enqueues are gone (`ai-layoff-tracker.php` 822-834), and with them **the last render-blocking stylesheet on the flagship page** — the open perf item from the 2026-07-28 SEO audit (#9 item 6). Measured on the wire: `jquery.dataTables.min.css` 2,067 B **render-blocking, cross-origin**, `jquery.dataTables.min.js` 29,230 B, both now zero, along with one DNS+TCP+TLS handshake that sat on the critical path. jQuery went with it: those **six** call sites were the only ones in a 4,000-line file, so `alt-js` no longer declares it as a dependency (the theme still loads it for `jquery.sticky-kit`, so it is not a byte saving, but this plugin no longer pins it). Our own assets moved **+945 B gzip of JS, -179 B gzip of CSS** (the card renderer is bigger than the column definitions it replaced), so the net page saving is ~31 KB of transfer and one blocking request. `$(fn)` became a `readyState` check, because the script is deferred and DOMContentLoaded may already have fired by the time it runs. |
| | **Scale never needed solving, and deliberately was not.** One page of cards exists at a time (25 by default, 10/25/50/100 selectable), fetched by `loadRows()` from the same paginated endpoint, so a card being taller than a table row is irrelevant against 63,670 events. **No client-side virtualisation** — that would be the same mistake in a new shape. The `#alt-sort` select already existed and is now the only sort UI; `setSort()` no longer has to name a column INDEX, which had quietly coupled the sort options to the table's column order. Removing the header sort also removed a dead option: `verification_level` was in the JS `sortFields` array but **not** in the PHP `$sortable` allowlist, so clicking the Source header silently fell back to `layoff_date`. |
| | **The card.** A left rail (employer in the display serif, industry, location, or "Location not stated") beside a body: badge row, the fact, our plain-English read of it, then the footer. The badges are the sibling's three, mapped onto this product — the stated/not-stated pair is **AI-attributed / Cause not stated**, the evidence badge is the existing verification tier, and the money badge's analogue is **the job count**, which is the number a reader scans for and the one thing the table genuinely did better. `--alt-serif` is the sibling's identical system-serif stack: no webfont, zero bytes, zero requests. **Blue only ever means clickable**, so the headline is a link to the entry's own page when it has one and plain ink when it does not — which incidentally starts closing #9 item 2, since those 1,798 permalinks were returned by `/query` and rendered nowhere at all. |
| | **Source link AND archived copy, on every card, never a swap.** `archivedCellLink()` now renders the sibling's exact shape — ` · archived`, quieter ink, `title="A copy saved by the Internet Archive, for when the publisher's own page has moved or gone"` — so the two products say the same thing the same way. What is ours and not the sibling's is the **pending state**: a row whose source has not been captured yet says so and says when it was last checked, instead of showing nothing and letting a reader assume we did not bother. Asserted in the harness below, not eyeballed: on 25 live rows every card carried a publisher link, every card carried either an archived link or the dated pending note, and **the archived link was never the first link in the footer**. |
| | **Accessibility went forward, not back.** The old expander was a click handler on `<tr>` — mouse only, no `aria`, no focus ring, and the 2.19.222 note records that changing a table's `display` had already dropped the implicit table roles on phones, so the card layout had no cell-to-header association anyway. It is now a real `<button aria-expanded>` inside each card, keyboard reachable, with the whole-card click kept as a mouse convenience. The list is an `<ol>` because the order IS the content ("newest first", "largest cuts"); `aria-busy` tracks loading; the pager marks the current page with `aria-current="page"`. Card and detail links now set their own colour and `:focus-visible` ring, which they had been inheriting from the deleted `table.dataTable a` rule. |
| | **Verified by driving the real `layoffs.js` in jsdom against real `/query` payloads** (`scratchpad/cardtest.js`, 44 assertions, all green): zero fetches on the default first paint (`ALT_BOOTSTRAP` still consumed — `queryParams()` builds the same four keys the old ajax callback did, so `takeBoot` still matches); "Largest cuts" sends `sort=job_count&dir=desc&page=1`; Next sends `page=2&per_page=25`; **`country_basis=any` on the results list and NOT on `/aggregate`**, so the documented split is intact; exports still carry the filters and the inclusive basis and still relabel to "filtered"; the chips bar still renders; the empty state renders with a reset and hides the pager; and injected `<img>`/`<script>`/`javascript:` payloads render as literal text with no element created and no link built. Also `php -l` clean on all four PHP files, `node --check` + terser + clean-css clean. |
| | **NOT verified: how any of it looks.** No browser in this session, so the card at 375px, the wrapping of the badge row, and the absence of horizontal bleed are unverified by sight. jsdom does no layout, so it cannot answer this, and the `scrollWidth === innerWidth` check is not evidence either — a clipped page passes it precisely because clipping achieves it by destroying content. The CSS is built for it (single column below 700px, `min-width:0` on both grid children, `overflow-wrap:anywhere` on the employer and headline, every strip wraps rather than scrolls) but that is an argument, not a measurement. **The owner is checking it by eye.** |
| | **The sibling was NOT modified** (standing instruction: read it, never write to it). Recording what that leaves open: its `archive_url` support shipped in its 1.43.0 and is in its live 1.55.0 code, but a fetch of its live results list found **zero** archived links rendered, matching its own TECHLOG note that every archiving run so far was a dry run. So "both products show an archived copy" is true of this one and true of the sibling's CODE, but not yet true of the sibling's PAGE. That is a change to that product for whoever holds its baton. |
| | **Also worth knowing: the brief's description of the sibling's card did not match the sibling.** It described a serif employer name, an industry line, a money badge and a blue headline with an arrowed source link. The live talent tracker (checked by curl, 1.55.0) renders an uppercase sans eyebrow, no industry field at all, no per-row money badge, an ink-coloured headline, and a source cell whose separator is a middot with no arrow. Its money badge and its left-rail card shape live on *other* surfaces (the at-a-glance matrix, and the company-profile timeline). Built to the sibling's real results card plus the brief's rail and job-count badge; the differences are called out here rather than silently resolved either way. |
| 2.19.225 (Jul 30) | **Cost-truth pass on the three sprint crons, and two number-guard defects of the sibling's exact shape.** Suite **314 -> 334**, `ops_status.py` exit 0 before and after. Committed locally, NOT pushed and NOT deployed. Baton was FREE and is left FREE. |
| | **THE CRON BUG WAS REAL BUT NOT WHERE THE PUNCH LIST THOUGHT.** Of the three "still hourly against their own revert instructions", **two were pure waste and one is genuinely earning its cadence** — the difference is *where the cursor lives*, and that distinction is the whole lesson. **`edgar-history-sweep` reverted to `20 5 * * *`.** `backfill.rotating_window()` picks its month with `months[now.toordinal() % len(months)]`, and `datetime.toordinal()` is the ordinal of the **DATE** — the hour is not in it. So hourly never meant 24x progress and never could: every run inside a UTC day sweeps the identical window. Proven three ways: (a) calling the real function across all 24 hours of 2026-07-29 returns one window (2020-09); (b) the live logs — the 22:40Z and 23:41Z runs both swept 2020-09 and both pulled the same **194 filings**, the 00:51Z and 02:04Z runs both swept 2020-10 and both pulled the same **274**; (c) the walker sat at 2020-03 on Jul 23 and 2020-09 on Jul 29 — **6 months in 6 days, exactly one per day, after a week of hourly.** The header's "hourly finishes in ~4 days" was arithmetic on a cursor that does not work that way; the true figure is ~76 days at any cadence. And `backfill.py` has **no seen-URL pre-check** (only `gdelt_backfill.py` imports `seen_urls`), so all 194/274 filings are re-extracted every run at the FULL prompt (SYSTEM_PROMPT 5,962 chars ~= 1,490 tokens + `raw_text[:2000]` ~= 500, `max_tokens=1000`). **22 scheduled runs/day x ~230 filings = ~5,060 extraction calls where ~230 do all the work.** ~4,830 wasted calls/day ~= 10.0M input + 1.0M output tokens ~= **$3.80/day** at deepseek-chat list ($0.27/M in, $1.10/M out). |
| | **The measured spend says the same thing independently.** OpenRouter key cap remaining, from the daily balance-check logs: 07-26 22:13 **$26.80** -> 07-27 13:48 **$22.69** ($6.33/day) -> 07-28 13:33 **$15.36** ($7.40/day) -> 07-29 13:34 **$9.80** ($5.57/day). The 07-28 industry-drain revert was supposed to return the pipeline to its projected **~$5-10 per MONTH**; the day after it, spend was **$5.57/day — 17-28x the projection.** The edgar sweep is ~68% of that. |
| | **`archive-backfill` reverted to `25 5 * * *`.** Its sprint has closed and the logs say so: three consecutive runs handed out **0, 2 and 7** candidate URLs against a per-run limit of **1,500**, and coverage sat flat at **21,110/25,029 distinct source URLs (84.3%)**. No LLM is involved, so the cost was only ~20 min/day of Actions minutes on a 9-second no-op; the only thing hourly bought was a new row's Wayback copy landing within an hour instead of a day. **Recorded while measuring, not fixed here:** the 3,965 URLs marked `pending` never re-enter the candidate list (distinct grew 25,020 -> 25,029 while `archived` moved 21,108 -> 21,110 and `pending` grew 3,963 -> 3,965), so a Save-Page-Now request that never confirms is stuck forever and **coverage cannot climb past ~84% by cadence at all.** That needs a re-check of pending rows, which does not exist. |
| | **`historical-news-sweep` LEFT HOURLY, deliberately, with the evidence written into the file.** Its cursor is server-side and success-anchored (`/historical-gdelt-cursor`), so it advances one 7-day window **per RUN** — the 00:00Z run took 2019-07-21..27 and the 01:05Z run took 2019-07-28..08-03. Cadence maps 1:1 to progress here, unlike edgar. Cursor at 2019-08-04 leaves 2,552 days = **365 windows: ~17 days hourly, ~365 days at one/day.** Cost is bounded by `BACKFILL_MAX_ARTICLES=10`, so <=230 calls/day ~= **$0.18/day** to close a year of history. **The 2026-07-28 "self-limiting when empty is FALSE" warning genuinely does not apply**: that warning is about rows whose two classifier passes disagree and write no marker, so they re-queue forever; this cursor is monotonic and persisted and never revisits a completed window. **Its header was wrong in three ways and is corrected:** it claimed "one rotating 14-day window per day" (`WINDOW_DAYS = 7`, and hourly), it claimed "a hard ceiling of 500 model candidates" (the binding cap is 10), and its `end` dispatch input said **"max 14 days after start" when the script raises at >= 7** — a by-the-book manual dispatch was a guaranteed `RuntimeError`. |
| | **Net: ~$3.80/day of LLM spend (~$114/month) and ~40 min/day of Actions minutes removed, with zero loss of coverage or freshness.** New `tests/test_rotating_cron_cadence.py` (7 tests) asserts the property rather than the symptom: it proves `rotating_window` is date-keyed, then fails any workflow in `DATE_KEYED_WORKFLOWS` whose cron can fire twice in a calendar day, and separately pins the deliberate hourly exception so a later tidy-up cannot "fix" it. It caught its own author twice while being written. |
| | **NUMBER-GROUNDING: the sibling's `\s*`-spans-a-newline defect IS here — one function above where the punch list pointed.** The verbatim guard itself (`_count_in_text`) is **sound** and was left alone: it matches `re.escape`d literals fenced by three zero-width lookarounds, contains no `\s` at all, and its separator class is explicit characters with no newline in it. The defect is in **`_percent_only_mention` (extractor.py:250)**, the gate one line ABOVE the verbatim check, whose `\b{n}\s*(%\|percent\b)` did span newlines. Reproduced: `'Employees affected: 17\nPercent of workforce: 3'` -> `_count_in_text(17)` is **True** (the 17 is verbatim, right there) while `_percent_only_mention(17)` was **True**, so the record was discarded as a mis-parsed percentage. That is precisely the sibling's failure — a figure verbatim in the source read as invented. Now `[^\S\r\n]{0,2}`: whitespace that is not a line break, and at most two of it. The Intuit misread the guard exists for ("cut 17% of its staff", "laying off 17 percent of employees", "17 % of the workforce") still rejects; genuine small headcounts still pass. |
| | **A second, quieter instance of the same class in `_count_in_text`.** `sep` (the lookahead that stops "12" matching inside "12 500") listed **U+202F** but `variants` never generated it, so `12 000` written with the **narrow no-break space — the standard French/Swiss/Canadian grouping, and what Word and many CMSs emit** — failed the verbatim check and the record died with the number plainly present. U+2009 (thin space) was in neither. Both added to `variants`; adding them exposed the mirror asymmetry (`sep` lacked U+2009, so "12" was accepted out of "12 500") and that is fixed too. **All six separators now round-trip both ways** — dot, comma, space, U+00A0, U+202F, U+2009 each accept the grouped number AND block the prefix misread. Derived numbers still rejected unchanged (`10% of 40,000`->4000, `$500,000`->500, `12,500`->12). New `WhitespaceShapeGuardTests` (6 tests): every fixture in the two pre-existing tables was a single line of ASCII spaces, so **neither guard had ever been exercised against a newline, tab, CR or typographic space** — which is exactly where the sibling's bug lived. |
| | **BLOCKED-HOST LIST: the premise was wrong — this repo has no blocklist of any kind.** Every host gate here is an **allowlist**; there is no blocked-host, denylist or aggregator-exclusion list anywhere in `railway/` or the plugin, and storage-side validation is `esc_url_raw()` only. So there is nothing for `finance.yahoo.com` to be added to, and **it already clears no gate**: absent from `gdelt.TRUSTED_DOMAINS` (705), from `newsapi.TRUSTED_DOMAINS` (52), and therefore from the tips allowlist. **No change made — inventing a blocklist to hold one host would be building a mechanism this project does not have.** `news.crunchbase.com` confirmed still **ALLOWED** (gdelt.py:55) with its rationale intact — an editorial newsroom, not a crowdsourced tracker — so the over-blocking mistake was not repeated. Two things found while checking and left for a decision: **`benzinga.com` IS on the trusted list** (gdelt.py:47) even though TECHLOG records a phantom row that had to be removed because it was Benzinga commentary on a BLS print; and **`google_news.py` has no host gate at all**, so anything that channel surfaces (Yahoo Finance, MSN, and the like) becomes a bronze candidate — the real syndication exposure, and much larger than one hostname. |
| | **`?states=NV`: documented, deliberately NOT aliased — and the investigation found a live defect next to it.** Measured against production (unfiltered `/query` total **63,671**): `?state=NV` -> 15, `?states=NV` -> **63,671**, `?industries=Technology` -> **63,671**, `?countries=US` -> **63,671**, and separately `?state=Nevada` -> **0**, `?country=US` -> **0** (`?country=United States` -> 43,378). **Two silent failure modes pointing opposite ways: a bad param NAME over-reports the whole corpus, a bad param VALUE under-reports to nothing.** Aliasing the plurals fixes the one guess someone happened to report while leaving `state=Nevada` -> 0 and every other typo just as silent, and permanently carries two public names for one filter against the project's fixed-vocabulary rule — so the contract is documented in ARCHITECTURE.md "Filter model" with the measured table, and the real fix (an additive `applied_filters` echo) is named there as the next step rather than shipped unreviewed. **The defect found on the way: `alt_export_is_filtered()` kept its own copy of the filter-name list and had drifted SIX params behind `alt_db_where()`** (`ai_primary`, `employer_country`, `review_status`, `context_missing`, `industry_missing`, `roles_missing`), so a CSV or JSON export narrowed by any of them downloaded as `ai-layoff-tracker-<date>.csv` — **the filename that means "the whole dataset", on a partial extract, on a journalist-facing product.** New single `alt_filter_param_names()` in db.php, read by export.php behind the FTP-race `function_exists` guard. New `tests/test_filter_param_contract.py` (7 tests) parses `alt_db_where` and fails if a filter is read but undeclared, declared but never read, or if the mid-deploy fallback copy rots. |
| | **SHORTCODE SELF-GUARD: REFUSED, and the refusal is now written at the guard site.** Not deferred for time — the obvious fix is *known to break this page*. The tracker is `[alt_tracker]` in `post_content`, so it renders through `the_content` and is fully exposed to pre-passes (no plugin template escapes it; `Template Name:` appears in none of the 17 templates). A first-render-wins guard was tried here in three commits on 2026-07-23: **e277e8b (2.19.164)** shipped a `define()` once-flag set before the emit and the tracker never appeared live, because a non-visible `the_content` pass claimed the single emit into discarded output; **2a4b260 (2.19.165)** fixed it the obvious way with `!doing_action('wp_head')` and set-after-echo and was **still broken**; **cd88c00 (2.19.167)** reverted both, because **this theme renders post content during `wp_head` and that pass's output is what reaches the body.** So `doing_action`/`did_action('wp_head')` are inverted here, and `in_the_loop()`/`is_main_query()` are untested against such a theme — there is no discriminator I can prove. The hazard is also measured **absent**: 0 duplicate element IDs across all 9 public pages in raw HTML and 0 in the live DOM. Prophylaxis against an absent hazard, carrying a failure mode present on this exact template, is a bad trade. **What would settle it, and the only thing that can** (the HTML cannot distinguish "rendered once" from "rendered twice, first discarded"): deploy a counter that OBSERVES and never suppresses — increment per shortcode call, record `current_filter()` and `did_action('wp_head')` at each, emit the tally as an HTML comment on `shutdown`, load the page, read the number. 1 means a guard is safe; 2+ also names which pass came first, the fact every attempt so far has lacked. Also noted at the site: the existing cross-guard sets its flag on **entry** to `alt_tracker`, not after a successful emit, so it carries a milder form of the same hazard and must not be copied to a shortcode that shares a page. |
| | **Verification of the three 07-29 substring fixes: all three PRESENT and TESTED** (23 tests in `test_domain_and_place_guards.py`, all green). `process_tips._OFFICIAL_RX` is **deleted** — the gate is now structural (`_is_official_host` matches whole host labels; `_OFFICIAL_WARN_HOSTS` is derived from `STATE_WARN_URL` so it cannot drift), with `warnerbros.com`, `notreal.com/fake.gov/x`, `fake.gov.evil.com` and `example.com/?q=edgar` all asserted rejected. `tracker_diff._covered_by_allowlist` judges the two win-key shapes separately instead of substring-matching. **Correction to the punch list: the NV parser is in `railway/sources/warn_custom.py`, not `warn_new_states.py` or `warn_import.py`** — `_nv_place_split` now splits city from county and `fetch_nv` counts and PRINTS unplaced notices, turning a silent ceiling into an observable one. **Row 173507 (`Spirit Airlines Las Vegas/RenoClark/Washoe`, 999 jobs) deliberately NOT touched** — trashing it must happen AFTER the owner pushes the parser fix, or the 9 AM ET NV import cannot recreate it and the record vanishes silently instead of being re-imported correctly. Left for the owner, in that order. |
| | **Also left alone on purpose:** no dormant cron armed (`foreign-filings.yml` still retired, and the new cadence test asserts its commented-out schedule is not read as live); no database-writing workflow dispatched; nothing pushed or deployed; nothing submitted to Search Console. **Two residual looseness items found but not fixed, both low severity:** `process_tips` trusts any two-letter TLD under a `gov.` label, so a registrable `gov.<cc>` outside gov.uk/gov.au would clear the auto-publish gate; and `_count_in_text`'s year trap includes `by` in its dateword list while its noun window cannot cross a word, so a legitimate "reduce headcount by 2000" is rejected. |
| 2.19.222 → 2.19.224 (Jul 29) | **Design port from the sibling talent tracker: phone cards, pill strips, Title Case. Re-implemented in `alt-` classes, no shared code.** Owner approved the same treatment on both trackers and separately confirmed the two products MUST NOT share code, so nothing was imported or copied; the sibling's stylesheet was read for the patterns and the reasoning, then equivalents were written here. **2.19.222 — the feed becomes a three-band card below 860px.** Nine columns side-scrolled inside `.alt-table-scroll` on a phone, which stops the page bleeding but not the employer name getting one word of width. Each row is now a card: WHO (employer, quiet eyebrow), HOW BIG (job count, headline), ON WHAT EVIDENCE (one line — verification tier, AI flag and reasons on ONE tag row, then date, place, source). 14px between cards. 860px deliberately matches the sibling. **Three things a future session needs:** (a) the bands are keyed to `alt-cell-*` classes the column definitions set, never nth-child — keyed to position they would be a coincidence of today's column order; (b) changing a table's `display` drops the implicit table roles, and DataTables 1.10.21 sets `role="grid"` + `role="row"` but **never `role="gridcell"`** (verified against the shipped minified file), so what survives is a grid of rows containing nothing — hence the job count's unit is REAL text (`.alt-jobs-unit`, hidden on desktop) not a CSS `::after`, and thead is CLIPPED not `display:none`; (c) the row detail now passes a class to `row.child()` (DT 1.10 puts it on both the `<tr>` and its `<td>`), because the only other handle is `td[colspan]` — which ALSO matches the empty-table cell, hence the matching `:not(.alt-row-detail)` on the empty-state rule. **2.19.223 — Sources and Roles come out from behind the chevron as pill strips.** Evidence tier is what this tracker rests on and it was a 160px dropdown whose summary truncated ("SEC filing (8-K/6-K) +1" says a filter is on, not which). Roles is what the roles chart writes (2.19.221), so the chart-applied filter had no legible home. **DELIBERATELY NOT EVERYWHERE:** the other eleven controls keep their checkbox dropdowns — 51 countries or 50 states as pills is a wall, and the dropdowns already solved the sibling's actual defect (native `<select multiple>` scroll boxes, which this plugin has not had visible since the `alt-dd` layer shipped). **The state architecture was the risk and it is untouched:** the pill layer hangs off exactly the two hooks `alt-dd` already uses — `cell._altDdRender` and a `change` listener on the select — and adds none of its own, so the querystring, chips bar, exports, quick views, click-to-filter and sessionStorage keep reading and writing the select with no knowledge of the pills. Toggling reuses `toggleMultiFilter`, the same helper a chart bar uses. No-JS still gets the native select. Proved by extracting `initPillGroup`/`toggleMultiFilter`/`escapeHtml` VERBATIM into a harness: two taps select two options and fire exactly two change events, a third deselects, and an external write to the select followed by `_altDdRender()` (what `restoreFiltersFromUrl`, `clearFilters` and a chart tap all do) re-renders the pills to match. Phone sizing: two points of type smaller below 560px fits two role pills per row, 5 rows instead of 8, so every option stays visible and nothing scrolls sideways — the sibling scrolls its long strip in its own box, which was rejected here because hiding options behind a swipe is the failing pills exist to fix. **2.19.224 — Title Case on every control label**, plus `Min job count` → `Minimum Job Count` and `Keyword in excerpt` → `Keyword in Excerpt` (the two that read as database columns). **Deliberately untouched:** the vocabulary option text — `/aggregate` keys `top_roles` by LABEL and `ROLE_SLUG_BY_LABEL` derives from layoffs.js's mirror of `alt_role_categories()`, so title-casing those is a two-file data join and any cached aggregate served across the deploy window would silently kill click-to-filter on that chart; the date-basis sentences; and the narrative chart-grid headings (editorial voice, not field labels — the same line the sibling drew). No question-form field labels existed to replace. Every changed string is keyed by something else (`data-qv`, option `value`) or overwritten by JS at runtime; `data-dd` turns out to be a selector hook whose value nothing reads. **Not verified live:** committed locally only, not pushed and not deployed — the reviewing session deploys. What IS verified: the exact markup the column renderers emit, rendered against the real stylesheet at 390px and 1280px (cards at 390 with the page body exactly 390 and no element overflowing its container; desktop table unchanged), the pill harness above, `php -l` on both PHP files, `node --check` on layoffs.js, and the 276-test railway suite at its pre-existing baseline (one error, `test_archive_backfill` cannot import `requests` locally; CI installs it). |
| (no ship) 2026-07-29 | **2.19.221's one honest gap closed: click-to-filter driven in a real browser.** #10 shipped it having never exercised a click. Now verified live end to end: a click on **Sales & marketing** filtered the page and wrote `?years=2026&roles=sales_marketing`; the visible Roles dropdown updated to match, so a reader can see WHY the page narrowed rather than finding it mysteriously filtered; `aria-pressed` read `true` on the active bar; a second click on a DIFFERENT chart **stacked** rather than overwrote (`&company=Salesforce`), which is the behaviour you want; a second click on each toggled it off and left a completely clean, param-free URL. Confirmed **123 bar buttons with zero disabled** — before 2.19.221 three whole charts were dead buttons. **Measurement gotcha worth keeping:** reading `aria-pressed` immediately after `.click()` returns the STALE node, because the card re-renders; the reference must be re-queried. The first read said `false` and was simply wrong. **No code shipped** — this entry records that a previously-unverified claim is now verified, which is the only reason the claim should be trusted. |
| (audit) 2026-07-29 | **Link-rot infrastructure confirmed RUNNING, not assumed.** `Broken-link check` (daily, 10 AM ET) green; `Source-archive backfill` green and running hourly; `Archive WARN sources to Wayback` (Mondays 08:00 UTC) present. Worth writing down because the sibling talent tracker has **none of the three** and is now having them ported — if a future session is asked to build link checking here, it already exists. **Do not replace any of this with a WordPress broken-link-checker plugin:** those crawl post CONTENT, and this tracker's source links live in the custom `wp_alt_layoffs` table, so such a plugin would check almost nothing while reporting a clean bill of health. That is the exact false-healthy failure class this project keeps finding. Also verified this session: `ops_status.py` **ALL CLEAR**, 33 sources OK, three retired foreign-filing probes correctly marked retired, and **zero failed workflow runs** across the last 25 on this repo. |
| 2.19.221 (Jul 28) | **Click-to-filter on every chart (parity with the talent tracker).** Owner ask: "on the talent intelligence one we can click on things on the graphs and it filters the full page." Most of it already existed here (industries / US states / countries / largest cuts / repeat layoffs / the reasons doughnut); the gaps were **three bar lists that rendered as `disabled` buttons** and **no address-bar sync**. Now: **Roles most impacted** -> `roles` (the aggregate keys `top_roles` by LABEL while the filter takes SLUGS, so a new `ROLE_SLUG_BY_LABEL` map derived from `ROLE_LABELS` translates back - verified byte-for-byte against `alt_role_categories()` in api.php); **By data source** -> `sources` carrying the raw `source_type` (`erm`/`news`/`8K`/`press_release`/`federal_rif`), which db.php already accepts alongside the verification tiers (`verification_level IN (...) OR source_type IN (...)`) - all six values proven to filter live before shipping; **AI intensity by industry** -> `industry`. New `ensureOption()` (ported idiom) adds the option to the dropdown when a chart shows a value /facets never listed (a source_type, an employer-HQ-only country) so a tap can never silently do nothing, and is ALSO applied in `restoreFiltersFromUrl()` - without it a shared `?sources=news` link silently dropped the filter for the recipient. The two monthly canvas charts (**Jobs cut per month**, **AI share monthly**) get `onClick` -> `pickMonth()`, which writes the SAME Years + Months controls the dropdowns write (so the chips, exports and URL all show it); canvas has no focusable parts, so those dropdowns ARE the keyboard route. Map bubbles now **toggle** through `toggleMultiFilter` instead of overwriting `writeControl` (a second tap clears, and the country path is the dropdown's path - `country_basis=any` stays on the table only, headline stats stay strict job-location, untouched). **Address-bar sync** (`syncUrlFromFilters` in `refreshAll`): `replaceState` with the same querystring the per-card share buttons already build, so a chart tap can just be copied out of the URL bar; the default view (this year, nothing else) keeps a clean param-free URL, which is deliberate - it keeps the crawled URL and the `ALT_BOOTSTRAP` zero-fetch first paint intact. Added a **Company** chip (the largest-cuts and repeat-layoffs charts write that text box and there was no visible X to undo them) and `.alt-barrow:focus-visible` (every bar row is a real `<button>` and was tabbable but drew no ring at all). **Not verified: the actual clicking** - no browser in the session; deploy + `ver=` confirmed only. |
| 2.19.210 (Jul 27) | **Deploy-truth probe.** `/status` now returns `version` = `ALT_VERSION` (endpoint is `Cache-Control: no-store`, so it reports the version the LIVE server is actually EXECUTING - cache-immune, unlike the `ver=` in cached page HTML or Cloudflare-cached assets). Added because the 2.19.209 admin fix "looked the same" after a hard reload + a Cloudflare purge, which points at the new PHP not running (wrong dir or OPcache) rather than a CSS problem. `curl /wp-json/layoffs/v1/status` now diagnoses which. **INCIDENT (root cause + fix):** every deploy since ~2.19.208 reported "success" but the live site never changed. The `/status` probe proved the running version was stale; a read-only FTP listing then showed the real plugin at `./wp-content/plugins/ai-layoff-tracker/` was untouched (mtime unchanged) while a stray `./b22ccf66...e1cf/` dir had appeared. Cause: the `WP_PLUGIN_REMOTE_DIR` secret was mis-set to a 64-char hex string (no slashes), so the guard's `dirname` x3 math resolved to `.` (wp-config.php found -> guard PASSED) while `mirror` CREATED that hex folder and dumped the plugin there. Fix: `deploy-plugin.yml` now HARDCODES `REMOTE_DIR=wp-content/plugins/ai-layoff-tracker` (drops the fragile secret) AND the guard now additionally requires an EXISTING `ai-layoff-tracker.php` at REMOTE_DIR (proves we are overwriting the installed plugin, not inventing a folder) - the check that would have caught this. Orphan hex dir deleted. Verified: `/status` now returns `version:2.19.210`. Also shipped in 2.19.209: scoped `admin_head-edit.php` CSS floor fixing the wp-admin Posts-list Title column (Complianz + Rank Math columns had crushed it). |
| 2.19.209 (Jul 27) | **Fix wp-admin Posts list (edit.php) squeezed-Title layout.** Two other plugins each add a wide admin column to the Posts list - Complianz ("Website Scan") and Rank Math ("SEO Details"). Under the core `table-layout:auto` they stole all the horizontal width and crushed the **Title** column until every post title wrapped one word (then one character) per line - the "posts page formatting broke" the owner saw. Ruled the tracker out first: its own asset enqueue is `wp_enqueue_scripts` (front end only), it registers no admin columns, and wp-admin core CSS loads fine (wp-login + load-styles both 200). Fix is a scoped `admin_head-edit.php` CSS injection in the plugin (`alt_fix_posts_list_column_widths`): a hard `min-width:220px` FLOOR on `.column-title` (the robust lever - the browser can never shrink below a min-width even when other columns demand space) + normal word-break, plus a `max-width` cap on the two heavy plugin columns. Scoped to the Posts-list screen ONLY, so it cannot touch the front end or any other admin page; pure CSS, no markup. Verify live: `ver=2.19.209` + reload wp-admin/edit.php - titles read on one line. |
| 2.19.208 (Jul 26) | **Structured per-entry Source block + honest Wayback pending copy.** The row-detail Source was one dot-joined run-on line (`primary · state list · archived`); it is now separate labelled boxes — **Primary source / State WARN list / Permanent report / Archived copy / Verification** — via new `srcRow()` + `archiveCell()` helpers and `.alt-src-row` CSS (a `--alt-surface-2` box with `--alt-border`, responsive `flex-wrap`). Every row now carries an EXPLICIT "Archived copy" row: the permanent Wayback link, or the truthful pending note *"Waiting to be crawled by the Internet Archive. Last checked <date>. We re-check every week until it is captured."* — accurate, because `alt_api_archive_candidates` retries `pending` URLs every backfill run and `unavailable` ones weekly forever. No em-dashes (house rule). `node --check` clean. Verify live: `ver=2.19.208` + open any row's Source block. Benchmark wayback-progress table is the paired follow-up slice. |
| 2.19.199 → 2.19.200 + railway (Jul 25, 360 pass) | **360 adversarial review + perf.** Three parallel audits (diff review, share/deep-link, performance) found FOUR breaks-now bugs, all fixed: (1) `google_news` MAX_ITEMS is a GLOBAL cap and broad sweeps ran FIRST, so at the new 150 cap the company-targeted chase queries (the whole point of tracker_diff's press path) and the fresh euphemism sweep NEVER fired — company queries now go first + every query gets a per-query slice; (2) the map's 4px AI-dot floor could EXCEED its own blue bubble on small totals (red over blue contradicts the "sits inside" legend) — capped at parent radius; (3) `vocab_hit` used substring matching so 'RIF' matched inside 'tariff' and 'sacked' inside 'ransacked' — nearly every headline false-hit, silently suppressing the missed-vocabulary signal — word-boundary regex now; (4) the 16 euphemism terms were added as GDELT SEGMENTS, which AND the base layoff vocabulary in front, so pure doublespeak ('delayering the management structure') could never match — they now run STANDALONE on the native-terms rotation (2/run), and SEGMENT_TERMS shrank back so pre-existing segments regain cadence. CORRECTNESS: weaning gauge now also records the COMPETITOR-list spelling on a resolve (norm mismatch made every chased company count as independently found); learning email fires on outlet suggestions too (was vocab-gated, and vocab was inert); retired-source coercion keeps the REAL checked_at (forging "checked just now" on a transparency page) and skips coercion when a source POSTed within 2 days (a deliberate reactivation is never masked) — ops_status + health_digest treat retired as never-stale; /tracker-meta actually bounds resolved (500) + wins (300); claims-by-state labels a state lagging the headline month. SHARE/DEEP-LINKS: `ai_broad` no longer clobbers co-selected reasons; **date_basis now round-trips** (read + embed allowlist + boot-skip) — a shared "notice date" link silently showed the recipient effective-basis numbers, i.e. DIFFERENT totals; filtered-export filename covers roles/ai_broad/date_basis; share tooltip states data is live (no as-of snapshot exists; reports are the frozen artifacts). ONE Dataset JSON-LD per page (two competing blocks made answer engines pick at random). PERF (measured): layoffs.js **82.7KB→44.9KB gzip** via a deploy-pipeline minify step (repo keeps readable source; minifier failure fails the deploy loudly); **d3+topojson (~95KB gzip) lazy-inject on map reveal** — they served only the below-the-fold map and were defeating the atlas lazy-load; .htaccess strips the host no-store from claims/reconciliation/quality-status (quality-status cost 2.2-2.9s cold and refetched every view), fingerprinted assets go max-age=1y immutable, preconnect to both CDNs, ALT_BOOTSTRAP excluded from Autoptimize's base64 inflation. **DEPLOY BUG found while verifying:** the version-bump flush cleared every cache EXCEPT `alt_htaccess_ok`, so header-rule changes sat unapplied up to 12h behind their own deploy — now dropped on bump (verified live: all three header fixes applied). Public copy: the "removals always require a human" claim now names its one automated exception (double-checked duplicate control, every merge disclosed) instead of being contradicted by our own corrections log. |
| 2.19.193 → 2.19.198 + railway (Jul 24-25) | **Audit-everything + learning-machine session.** CI: the 15 red Tests runs were order-dependent test pollution — test_warn_{generic_drift,sanitize} installed fake `sources.*` modules that persisted in sys.modules and shadowed the real warn_custom for every test loaded after (OH/LA/NC parsers "vanished"); both now stub ONLY `requests` (suite 267 green; the same trap is documented in both files). RETIREMENTS made self-healing: declarative `alt_retired_sources()` in db.php — `/source-health` GET coerces newsapi + edinet_jp/opendart_kr/cvm_br to a benign fresh-timestamped `retired` state so they can never re-alarm as degraded/stale; health.js sinks them to the bottom with a muted pill; ops_status prints `(retired)`; NewsAPI dropped from cron's collector loop (code kept, re-enable by restoring the tuple row); ALL public copy synced (methodology/sources/tracker/health/country-table: NewsAPI→Google News everywhere; the JP/KR/BR probes no longer described as "Active"). DEDUP: near-count wide-window floor 1000→250 (mid-size same-event re-reports rounded differently across outlets months apart now reach the LLM; 60-cluster/day cap keeps cost flat). DISCOVERY: corporate-euphemism recall — low-noise soften-speak (rightsizing, workforce optimization/rebalancing, job eliminations, voluntary separation, organizational simplification) into the always-on base (cap 42→48); NOISY cost/efficiency doublespeak + industry euphemisms (store rationalization, capacity reduction, service-line consolidation) as rotating GDELT segments PAIRED with a headcount word so extraction volume stays inside the ~$5-10/mo budget; one euphemism sweep in Google News (budget-neutral under MAX_ITEMS, itself throttled 300→150). CHART/UX (from 3 parallel audit agents + owner live review): tracker chart grid restructured into three labeled narrative chapters (Where the cuts are / How it is trending / Who is cutting, and why — full-width header rows, dense flow removed so cards can't cross sections); map full-width with the trend; **map AI-dot fix** — strictly proportional radius made 37k AI jobs a ~3px dot inside a 38px bubble ("AI not showing on map"), red dots now floor at 4px; claims overlay ON by default with plain-English note; announced UN-stacked to a dashed line (no misread of amber edge as verified); terminology unified (**AI-attributed** = strict everywhere; "AI-linked" reserved for broad; silver tier = "Press release" on both pages); colorblind chip pairs separated by lightness (green #14532a, gold #6e5807, teal #0b6a76); FAQ's hardcoded self-audit stats (60/58/98.3%) replaced with live-audit pointer; health page de-jargoned + reordered (collectors above roadmap); em-dash purged from prose (cell-placeholder `—` kept deliberately). NEW CARD (owner ask): "Jobless claims by US state" — DOL initial claims, latest month, all states, GREY bars, explicitly context-only/unaffected-by-filters, auto-updates from the weekly FRED import; layoff cards relabeled "Layoffs by US state / by country" so the two universes can't be confused. **WEANING (learning machine):** tracker_diff now measures INDEPENDENT RECALL daily (have MINUS ever-chase-resolved — the "we don't need them" number), learns from WINS (outlet + COUNTRY tagged, `inc42.com · India`; repeat winners not in the allowlist ranked as adoption candidates), captures MISSED VOCABULARY (a resolved win matching no discovery term = wording invisible to the broad sweep; headlines emailed owner-only with a paste-back line), and steps the chase down to Mondays-only once independence holds ≥90% for 21 recorded days (any dip snaps back daily; TRACKER_DIFF_FORCE_CHASE=1 overrides). State in new keyed `/tracker-meta` (WP option alt_tracker_meta: resolved map, win counts, 180-day history) — names never in repo/logs. 15 new tests; weaning env constants live at top-of-file because test_tracker_diff_sitemap exec's the _norm..run slice bare. COST: owner set the OpenRouter key cap to $50 (worst-case breaker; steady state ~$5-10/mo). Industry tail (~2,650 LLM-only rows) drained via sequential 200-row dispatches (~$0.50 one-time). Private bm refreshed (LOCAL): US 97% of the announcement survey (basis-any), H1 80%, tech 103% of the live tech tracker. |
| 2.19.160 → 2.19.163 + railway (Jul 23-24 overnight) | **Cost-truth + close-the-history night.** COST: the ~\$15/day OpenRouter burn decomposed into (1) industry-backfill at 8x/day x 4 shards x 2 passes with the FULL ~1,400-token extraction SYSTEM_PROMPT on every one-label call (~80% wasted input on ~12.8k calls/day) - narrow calls (industry/roles/reason/context) now use a ~25-token MINI_SYSTEM + swappable OPENROUTER_CLASSIFY_MODEL, correctness-critical calls (full extraction, AI-causation) keep the full prompt; (2) the ingest re-extracting the SAME URL ~3x on overlapping 36h windows - new keyed POST /seen-urls (main rows + source reports) lets cron.py skip exact re-reads BEFORE the LLM, FAIL-OPEN (4 tests), ~60% of daily extraction volume, and makes higher cadence for freshness nearly free; (3) out-of-credits 402s burned full batches then paged 8x/day - extractor now raises CreditsExhaustedError on the first 402 (circuit breaker), the three paging jobs exit 0 with an actionable 'top up' health state. Cheap-model A/Bs on live drain rows: gemini-2.5-flash-lite 74% agreement REJECTED; deepseek-v4-flash (post-cutoff, verified in the live catalog; the suggested 2.0-flash-001 slug is deprecated, and NO deepseek :free routes exist) 82% on a noisy sample - queued for a judged A/B post-close, not flipped mid-sprint. Steady-state projection ~\$5-10/mo, verified by the private cost card (per-KEY usage isolated from the shared account; runway = min(account balance, key cap) - the \$30 key cap with \$9.65 left would have re-402'd right after top-up; raised to \$70). CLOSE-THE-HISTORY: the 'always more to pull' feeling was two walkers metering one window/day (GDELT 494 x 7d left at cursor 2017-01, EDGAR 76 months at 2020-03) - both now hourly with concurrency guards (self-idle at the present; ~3wk / ~4d to close); industry drain sprinted (20,955 blank rows, ~\$4 total at the new token cost; first-run labels spot-verified clean). Future-date ceiling added (~today+3y) in alt_db_valid_date + extractor - a misread 'by 2050' can no longer plant a phantom series spike. DISCOVERY: sampled-first category digging (agent, ~\$0.02) - state-name queries measured 0/25 usable (never wire), gov queries redundant (WARN was AHEAD of press), the real finds were second events at already-tracked companies (watchlist event-level recheck queued) + a merger-integration segment queued; segments gained adjacent-automation phrasings (AI agents/agentic/genAI/chatbots/robots/automated); NEW native-language STANDALONE query sweep (segments AND the English base, which native originals can't co-match) - 14 precision-selected terms across 9 languages closing the euphemism-translation gap (sv varsel->'notice', it esuberi->'surpluses'), with SE/PL/PT papers-of-record added to the trusted list so native hits survive the trust gate; tracker_diff stop-list widened (cities/countries/topics/numeric slugs). PRESS (2.19.162-163): journalist-first rewrite - the repeated 60-word caveat now appears ONCE as the positioning callout ('Nothing is estimated'), every statement/soundbite carries 'See the rows behind this number' deep-linked via verified front-end params (the old evidence-ladder link used ai_primary=1 which the front-end IGNORES - silently unfiltered); press transients now version-scoped (fixed keys served hour-stale arrays after deploys). PRIVATE bm-live: live ingest-log panel (run-ledger feed, 24h per-source strip, CSV export, observed row-deltas) + cost card; stale competitor constants refreshed (the tech-tracker figure was 64% overstated, showing us 'behind' at 43% when the verified live read is AHEAD at 107%); page-render ReferenceError fixed (silent catch left tables on 'loading...' - failures now render visibly). REPO: public-repo brand scrub (competitor names in 8 tracked docs/tests -> neutral descriptors; test guard needles fragment-assembled). Monthly self-audit stratification fixed (erm mapped to bronze = news, so ERM was never audited); tips allowlist lstrip('www.') bug mangled every w-domain (wsj->sj) - always-queued instead of auto-publish. All-workflow bump to checkout@v5/setup-python@v6 (Node 24 deprecation warnings gone). |
| 2.19.144 (Jul 23) | **Circular AI share lines fixed + tier vocabulary reconciled.** With an AI filter active the stat cards read "**100% of verified cuts were blamed on AI by the employer**" and the broad card silently equalled the specific total while its own caption promised it would be larger. Cause: the filter makes the denominator the numerator. The API was correct throughout (unfiltered broad 120,050 vs specific 87,935); only the captions lied, and that 100% screenshotted out of context is simply false. Share lines are now suppressed with an explanation whenever an AI filter is active, including the quick-view `ai_broad`/`ai_primary` routes (guard reads `currentParams()`, not just the checkbox). Verified live in-browser BOTH ways: filtered shows the explanation, unfiltered shows 11% verified-AI share and broad 120,050 > specific 87,935. **Naming decision: adapt, do not rename.** Tier 1/2/3 (attribution strength) and verified/announced (execution stage) are ORTHOGONAL axes over the same rows, and they reconcile exactly: Tier 1 + Tier 2 = 43,160 = the verified-AI box to the job, and Tier 3 is precisely the specific->broad gap. So no third vocabulary was minted; the ladder gained a "Where it appears on the tracker" column mapping each tier onto the existing public card labels (which are already citable), plus an explicit "these are not a second set of numbers" reconciliation. |
| 2.19.138-142 (Jul 23) | **Cleanup sweep + press-citability push.** DATA: a full 62,958-row scan found 23 RESCINDED/CANCELLED WARN notices carrying **5,050 phantom jobs** (a withdrawn notice is a layoff that did not happen), 11 rows with raw HTML in the employer name (Wisconsin wraps a footnote INSIDE the cell), 395 with the site address glued into the name (fragments company identity: 'Walmart (1345 Crossman Ave.)' never groups with 'Walmart'), plus HTML entities, repeated 'Update:' markers, and 4 rows whose employer cell was literally '.' or ','. All handled by ONE sanitizer at the import boundary (covers all 48 states + every state added later, instead of 48 drifting copies), shipped with 10 tests including the Cancer-vs-cancelled trap and 'must not truncate a legitimate name with digits'. 23 rows trashed via the corrections path; LA/CA re-import cleaned 1,073 names. INFRA: deploy now flushes the PAGE cache - Bing had indexed a 2.19.128 <head> (old meta description) long after 2.19.136 shipped, because crawlers request the bare URL and got WP Super Cache's stale HTML while only transients were cleared. WORKFLOWS: industry-backfill was failing DAILY because one page of its ~140-page scan 500s under host load and raise_for_status() aborted the run BEFORE any work (which is why the backlog never drained); now retries transients, continues with the pages it has, still raises on page 1 or a real 403/404. GDELT historical: a persistent upstream 429 now stops gracefully (cursor is success-anchored, nothing half-written) instead of failing red against a ledger that already calls it expected-transient. Backfill sharded into 4 matrix shards striding DISJOINT pages: 4x throughput at the SAME total request load (host load caused the 500s, so fanning out beats multiplying). Propagate weekly->daily. PUBLIC ACCURACY: every surface claimed the dataset 'spans 2015 to the present' and stamped temporalCoverage 2015-01-01, but it reaches back to **2002** (18,280 pre-2015 events) - we were understating our own coverage by 13 years; now derived from MIN(layoff_date). PRESS: new **AI evidence ladder** (Tier 1 = AI named as THE cause / Tier 2 = among causes / Tier 3 = AI-linked, never merged upward) built from the ai_causation values already stored, each with a live count and a working preset view; and **press statements** - weekly/monthly/YTD paragraph-length pitches with the maths done and the filtered view that reproduces each claim, rolling into a 12-month + 6-year archive. UI: date-basis is now a real segmented switch; bar lists got a visible scrollbar (they already scrolled, the invisible bar made rankings read as complete). |
| 2.19.136 (Jul 23) | **Poland's Mazovia becomes the THIRD jurisdiction with a WARN-grade public register we read directly** (after US states and Quebec). A survey of all 16 Polish voivodeship labour offices (WUPs) found exactly ONE publishing employer-NAMED collective-redundancy notifications: WUP Warszawa (Mazowieckie, ~16-17% of Polish employment, Warsaw-HQ heavy), via monthly "Zwolnienia grupowe na Mazowszu" press posts; Bialystok publishes per-notification but ANONYMIZED rows (no names -> unusable), the rest aggregates or nothing, so no 16-office framework is justified. New `sources/wup_mazowieckie.py`: DETERMINISTIC parse (no LLM - keeps the "structured registers are imported with no AI processing" claim true), items anchored on Polish legal-form suffixes (Sp. z o.o./S.A./sp.k./S.K.A.), count from "N osob", effective date from "do konca <month-genitive> <year>" (genitive month map), skip-don't-guess with a skipped counter. Parser validated against the live March-2026 post to EXACT ground truth (BAT 48 / 2026-04-30, Amerplast 29 / 2026-07-31, Bank Nowy 3 / 2026-09-30) - and the test caught a real bug: a lazy-body lookahead silently dropped the FINAL list item (Bank Nowy) because the post's closing paragraphs sat between it and end-of-text; rewritten to slice between anchors. Wired into warn_import.py after the Quebec block (fail-isolated, WARN_SKIP_WUP_MAZOWIECKIE opt-out, health id `warn_mazowieckie`, 0-new-notices months are OK not degraded since the register is monthly); monitors + health.js label added; sources page gains the glance row and the "only US states and Quebec" narrative is corrected; the global-authorities partial's Poland row flips from "Confidential filing" to the Mazovia named-register truth. |
| 2.19.135 (Jul 23) | **SERP meta description: live rounded numbers via Rank Math's filter, evidence-first.** Research pass (live competitor snippets + Ahrefs 20k / Portent 30k rewrite studies + Backlinko CTR data + Google's snippet docs) found every data-page competitor winning our head terms leads with verb + live figure + current year + freshness cue, while ours was the only one with none; Google truncates by pixels (~155 desktop / ~120 mobile), rewrites ~65% of descriptions but keeps ones that match on-page content, and explicitly ENCOURAGES programmatic page-specific descriptions for data sites. Implementation: extracted `alt_live_numbers()` from `alt_faq_items()` so the FAQ and the description quote the SAME hour-cached figures (body-match = fewer rewrites); `alt_tracker_meta_description()` feeds Rank Math's frontend/OG/twitter description filters (ONE tag on the page - the 2.19.133 duplicate-OG lesson) on the main tracker page only. Copy: "Layoff tracker, updated daily: {jobs}+ jobs cut in {year}, {ai}+ tied to AI. Every number links to an SEC filing, WARN notice, or news report. Free." Figures round DOWN (nearest 10k/1k) so the claim can never overstate or go stale upward; STRICT ai_jobs only (matches the public verified-AI framing, not the broad lens); early-year guard (<50k jobs or <5k AI) falls back to the static field; 149-152 chars at all realistic widths with both numbers inside the mobile window. Verified live: 149 chars, real figures, exactly one og:description, matching. This also resolved the "meta description too long" SEO-tool error (the old field was 184 chars). ALSO: earlier fixes this night surfaced two page-truth bugs on the sources page - the country-table parser only understood one comment style (106 of 705 outlets missing from the public table, AP/BBC/Al Jazeera among them; 2.19.132) and the renderer capped rows at 14 with a bare "+N more" (rest now ship in a collapsed details block, all 705 crawlable; 2.19.134). CI note: the reclassify guard-test went red for four pushes because the code change shipped without its test - the 1f89aa4 lesson repeated; fixed in da1c9da and the watch-Deploy-not-Tests habit is the thing to correct. |
| Ops (Jul 23) | **H1-2026 gap closure: 28 seeded events, and the discovery that the sector gap was a TAGGING problem, not a coverage problem.** Ran three research passes (healthcare, automotive+food, tech+media) for US H1-2026 events with a firm public headcount and a named source. 69 candidates found; a live dedupe against the tracker showed **36 were already held** (58% of auto/food, 79% of tech) - seeding blind would have double-counted every one. Also excluded **Oracle 21,000** (we hold it at 2026-04-06 id 70257; the candidate's 2026-06-22 date sat 77 days away, just outside the first dedupe window and only caught on a wider re-check - it would have recreated the exact Oracle duplicate reported earlier in the session) and **Meta 8,000 / Cisco 4,000**, whose WARN execution slices we already hold, so the announcement total would count the same people twice. Seeded the remaining 29 via backfill_seed.py (28 posted, 1 caught by the SERVER-side dedup guard, 0 failed): H1 2026 284,908 -> 293,098 jobs (+8,190), every month up. **The bigger find:** sampling showed **96% of US rows carry no industry (72% of sampled job volume)**, because every structured WARN notice arrives without one - so most volume counted toward NO sector. That, not missing events, is why the by-industry view read healthcare 8% / automotive 16% while the overall US total sat near the benchmark. Full scan measured **42,028 untagged rows**. Added `industry_propagate.py` + a weekly workflow: a deterministic, LLM-free fill that gives a blank row the SAME company's existing label (majority-vote; a company whose tagged rows disagree is skipped, never guessed), writing through /industry-backfill so it inherits blank-only + closed-vocabulary validation. Filled 1,693 rows. The other ~40k have no tagged sibling and need the classifier, which was set to 40 rows/day (~1,000 days to drain, i.e. never) - raised to 4x200/day, and fixed a second bug found doing it: scheduled runs were still pinned to 40 by an `|| '40'` env fallback even after the input default changed, so the schedule would have silently ignored the increase. Net sector movement: Technology +102,659, Retail +23,538, Healthcare +13,031, Food +12,535, Media +10,354, Telecom +6,082. Lesson: when a comparison looks like a collection gap, check whether the data is present but unlabelled before going to find more of it. |
| Ops (Jul 23) | **NC WARN parser: misaligned rows now rejected deliberately, and NC re-joins the count-fallback.** Follow-up to the fallback probe, which had shown NC firing 188 times with wild counts (5604, 2035) on rows whose company cell was a bare number. **Measured first:** a new `railway/nc_warn_check.py` + manual `nc-warn-check` workflow run `fetch_nc()` and report the row count plus any row whose company is empty / a bare number / has no two consecutive letters. Baseline was **1151 rows, 0 suspect** — proving NC's OUTPUT was already clean and the misaligned rows were being dropped only INCIDENTALLY (their count parses to 0, so `_entry` rejected them). That accident was exactly why a count-fallback was dangerous there: rescuing the count resurrected the garbage row. Root causes: `_nc_grid_entries` persists the header column-map across pages (2022+ files only carry the header on page 1), so a later summary/continuation row is indexed with a stale map; and `_nc_text_rows` buckets words by x-position, which mislands a summary line into the data columns. Fix: `_nc_plausible_company()` rejects those cells before an entry is built, applied in BOTH parsers — the discriminator is "two consecutive letters", verified to keep every real name (`3M Company`, `24 Hour Fitness`, `1-800-FLOWERS`, `BP`, `AT&T Services, Inc.`) while rejecting `0`/`18`/`1,234`/`12/31/2020`/`1a`. With garbage filtered BEFORE the fallback, NC is safe to rescue like the other nine states, so `llm_count_from_text` is re-enabled in both NC vintages. **Verified after: 1151 rows (identical — zero legitimate rows lost), 0 suspect, and ZERO fallback firings** (the 188 bogus rescues gone), CI 223/223 green. Lesson worth keeping: a parser whose bad rows are dropped by a *side effect* is a latent hazard — the moment you add a rescue path, the side effect stops protecting you. Validate the identity field explicitly before rescuing any other field. |
| Ops (Jul 22) | **Shared DeepSeek count-fallback wired into the fragile WARN scrapers — regex-first, LLM-rescue-on-failure — plus the NY regex fix it surfaced.** After the HI OCR + fallback shipped, generalized the pattern for the state scrapers whose count is brittle (fixed column indices / positional PDF cells / one labeled regex) while company+date are reliable. New `railway/sources/warn_llm.py` `llm_count_from_text(text)`: given ONE already-isolated row/notice's text, recover the affected count via DeepSeek, accepted only if the number appears verbatim in that text (anti-hallucination) and clears a >=5 floor; returns 0 (never raises) on any failure. Wired into 10 SAFE+USEFUL scrapers (FL, GA, MI, NY, ID, LA in warn_custom.py; WA, MS, WV in warn_new_states.py) at the point the regex count is 0 — **additive** (never touches a row that already parsed), **gated** (WARN_LLM_FALLBACK=1; byte-identical with it unset, CI-confirmed), **guarded** as above. Excluded NV/MN (failure is total 0-row breakage — no row to attach a count to) and the clean labeled-field states (TX/OH/CO/MA/KY/NM). A `warn-llm-probe` workflow + `warn_llm_probe.py` run the fetchers with the fallback ON and print every recovery, posting nothing — the verify-before-live step. **Probe #1 findings drove two corrections:** (1) **NC removed** — its text/grid parsers emit misaligned rows (company field = a bare number) that the fallback rescued into wild counts (5604, 2035); NC needs proper row validation (spawned as a follow-up), not an LLM band-aid. (2) **NY was firing on 162/544 rows** — all the OLD 2022-2023 WARN-unit form, which uses a single `Number Affected: N` label the scraper's two patterns missed (agent-verified across 49 notices); added `\bNumber Affected:\s*(N)` (word boundary prevents colliding with the new form's "Total Number of Affected Workers"), so NY now parses **deterministically** with zero LLM reliance. **Probe #2 after both fixes: ZERO fallback firings across all 10 scrapers** — the fallback is now a pure DORMANT safety net that activates only when a site actually shifts a column/label in future (each firing logs a `::notice::` for review). Enabled WARN_LLM_FALLBACK=1 in the daily warn-import. Net effect toward "weekly-glance" autonomy: a column/label drift that used to silently zero out a state (MS 2026, the CT `affected_company` mis-select, etc.) now self-heals with a guarded, auditable count instead of bleeding coverage until a human re-recons. |
| 2.19.124 → 2.19.126 (Jul 22) | **Hawaii WARN goes live via OCR + a DeepSeek fallback — a new-source pattern for image-only registers.** Hawaii's WDC posts each notice as an image-scan PDF (no text layer), so the affected-employee count exists only as pixels; the list page carries no count. Verified (agent, real notices) that the counts ARE in the letters but OCR-only. Built `sources/warn_hi_ocr.py`: crawl the per-year pages → render each notice with pypdfium2 → OCR with tesseract → extract the count. **Extraction was calibrated 10/10 against 9 independently-verified notices**; the recurring trap was grabbing TOTAL employed instead of AFFECTED ("Alaska 3375" was a street address; Pulama 450 and HC&D 215 were total headcount), so the extractor classifies each number as affected-vs-workforce-total by its nearest cue and trusts the affected one, with explicit high-confidence patterns (grand total, "N of them separated", "employed by the establishment is N" for closures, "N employees affected", "total number of affected employees is N"), noise filters (ZIP/year/$/%/street-number), an outlier guard (>500 from a non-structural pattern → review; caught the phantom "Honolulu Roofing 754"), and a hard rule to SKIP anything ambiguous rather than guess. Shipped the RUNBOOK way — **dormant + dry-run first** (`hi_warn_dryrun.py` + a manual `hi-warn-dryrun` workflow that installs tesseract and PRINTS extracted counts, posting nothing) — and only flipped live after the table was clean. Live path: `hi_warn_import.py` + daily `hi-warn-import.yml` (installs tesseract, posts via bulk, loud-fail; mirrors federal-RIF). First live import upserted 23. **Then added a DeepSeek fallback** (`_llm_affected_count`, gated behind `HI_LLM_FALLBACK=1`): when the deterministic extractor skips a notice, ask the model for the affected count and accept it ONLY if that exact number appears verbatim in the OCR text (anti-hallucination) AND is >= 5 (WARN notices are mass layoffs; a single-digit fallback count was always the model latching onto a stray number). Dry-run-verified before enabling live (recovered Pulama 15 / Ali'i 100 / Honolulu Roofing's real 15, all matching ground truth), taking the skip rate 47% → 31%. Falls back to regex-only if the LLM is down, so it can never reduce coverage. Also: Hawaii comes off the dark map (`alt_no_register_states` + BLS series) and out of the sources-page gap table, with an honest new "Hawaii WARN (OCR)" source row (scanned-notice OCR, clear-count-only inclusion, source-PDF on every row); HI dropped from the benign-degraded sets and `warn_hi_ocr` registered (3-day staleness + health.js label) so a 0 now alerts. **Pattern to reuse:** regex-first → LLM-fallback-constrained-to-in-source-numbers is the template for hardening format-fragile scrapers toward "weekly glance" autonomy. |
| 2.19.121 → 2.19.123 (Jul 22) | **Nevada now imports automatically and free via a Bluehost server-side mirror — resolving the Akamai bot-wall that blocked CI.** DETR's cumulative master WARN PDF (`/content/media/WARN_and_Non_WARN_Master_w_Logo.pdf`) sits behind an Akamai wall that 403s data-center IPs, so the GitHub importer got 0 for NV (the WARN purge+reimport had exposed this by wiping NV's ~1,961 jobs). A temporary `/nv-fetch-probe` endpoint (2.19.121, since removed) proved **Bluehost's outbound IP is NOT Akamai-blocked** — the site fetched the PDF as a clean `200 application/pdf`. So the fix: a daily WP-cron (`alt_nv_mirror_cron` → `alt_nv_mirror_refresh`) re-fetches the master PDF with browser headers and mirrors it into uploads at `…/wp-content/uploads/nv-warn-master.pdf` (overwrites only on a valid `%PDF` ≥2KB, so a transient 403 can't blank it); `alt_flush_caches_on_deploy` also populates it immediately on deploy. `railway/sources/warn_custom.py` `fetch_nv` now reads `_NV_MASTER_PDFS = (mirror, DETR-direct)` — mirror first (CI-reachable), DETR fallback for residential runs — and breaks after the first source that yields rows so a residential run can't parse both and double the list. Public `/nv-mirror-status` reports mirror freshness. Verified end-to-end: dispatched `warn-import.yml states=NV` from CI → **"WARN NV (custom): 15 notices kept"** → live API `state=NV` = 15 notices / 1,961 jobs restored. Follow-through (2.19.123): removed NV's "bot-walled" row from the sources-page gap table (no longer a gap) and dropped NV from the benign-degraded sets in `ops_status.py` + `health_digest.py` (a CI zero for NV now means the mirror broke and SHOULD alert). Pattern worth reusing for any other bot-walled state site: mirror the file from the un-blocked WP host, read it from there. |
| 2.19.104 → 2.19.105 (Jul 21) | **Site-wide em-dash sweep of UI copy (house style: "no em-dashes in UI copy").** Also made the tracker's "Why our number is lower" callout collapsible (`<details>`) and folded the quality-note paragraph into it. Two passes because the copy lives in more than one place: (1) all `templates/*.php` rendered prose (stat labels like "AI cuts, verified", methodology paragraphs, headings) + loading-value placeholders `>—<` → `…`; (2) nested/generated copy the first pass missed — `templates/partials/country-sources-table.php` (one em dash per country row) **and its generator `railway/generate_country_table.py`** so a regen can't reintroduce it, rendered strings in `includes/` (CPT entry title `%s: %s jobs (%s)`, contact-form error messages, RSS `<title>`s, `/report` title, `/companies` methodology string, `llms.txt` heading, the `/add` duplicate-reject API message), and the three `health.js` discovery-source meta labels. **Left untouched on purpose:** the JS empty-cell glyph (`?? '—'` / `|| '—'` — the correct "no data" mark in a table cell, not prose) and code comments (invisible). Verified live: plugin-rendered region is em-dash-free on tracker/sources/health. Known residual: a single em dash inside a historical **corrections-log note stored in the DB** ("…storing both 20,000 and 9,000 double-counts") — that's data, not authored copy, and needs a data edit (not a code change) to remove. |
| 2.19.96 (Jul 21) | **Source-registry parity guard: a monitored/reporting collector can no longer be missing its health-page label.** The public health page renders EVERY collector that POSTs to the source-health ledger, looking each id up in `meta{}` in `assets/health.js` and falling back to a generic "Operational collector" label when the id is absent (`db.php` stores `alt_source_health[$source]` uncurated, so nothing filters an unlabelled reporter out). That made "added a collector, forgot its label" a silent public-surface drift. New `railway/tests/test_source_registry_parity.py` (same local-run enforcement as `test_warn_url_parity.py`) asserts: every id in `ops_status.py` `MAX_AGE` (the freshness-monitored ingest sources) has a `meta{}` label; every literal `report_source_health("id")` reporter across `railway/` is either labelled in `meta{}` or explicitly classified in a documented `KNOWN_UNLABELLED` set (internal ops/QA telemetry like `health_digest`/`recall_precision`/`tracker_diff`/`industry_backfill`, or reporters that surface under a family/runtime id like `edgar_historical`/`foreign_filings`/`distress_watchlist`/`warn_custom_legacy`) — so a NEW collector forces one deliberate choice, label or classify, and can't slip through. Fixed the one gap this surfaced: `dedupe_llm` is freshness-monitored and reports health but had no label (it was rendering as the generic "Operational collector"), so it now carries a factual `meta{}` entry ("Cross-source duplicate remover (daily deep scan)", Internal). Guard proven non-vacuous (a synthetic unlabelled monitored source and a synthetic new reporter both trip it). Also: (a) **fixed a pre-existing, unrelated vocabulary drift** the full-suite run surfaced — PHP `alt_allowed_reason_tags()` (and the UI label map in `layoffs.js`, and `warn_custom.py` which actually WRITES `["closure"]` for permanent shutdowns) carried `closure`, but the Python `extractor.ALLOWED_REASON_TAGS` allowlist did not, so `test_reason_backfill_guards` was red; `closure` is a live, written, displayed tag, so the correct direction was to add it to the Python allowlist (a validation set — it does not change model emission), restoring Python<->PHP parity. (b) **Added CI**: `.github/workflows/tests.yml` runs the full railway unittest suite (223 tests, offline, ~1s) on every PR and on main — these guards had NO automated runner before (enforced only by the owner running the suite each session); the workflow makes drift a visible check. Enable it as a required status check in branch protection to hard-gate merges. Full suite now 223/223 green. |
| Ops (Jul 21) | **Docs + tooling: a blocked cloud session mistook an egress denial for a source outage (and thought it couldn't deploy).** A cloud session's `ops_status.py` hit `<urlopen error Tunnel connection failed: 403 Forbidden>` on the live tracker + health endpoint and reported "ACTION NEEDED -> a data source broke," then concluded it couldn't update the live site. Both were wrong. Root cause: some cloud environments' egress/network policy denies `asktherecruiter.com` (the proxy answers 403 to CONNECT — the request never reaches the site), so it is neither a source outage nor a deploy blocker: deploy is `git push` -> GitHub Actions "Deploy WordPress plugin" -> FTPS **server-side**, which only needs GitHub. Guards added so no future LLM (Claude/Codex/other) repeats it: (1) `ops_status.py` now distinguishes an egress block from a real outage — `_is_egress_block()` classifies proxy 403/407/tunnel/DNS/route failures (but NOT an `HTTPError`, which means the site actually answered) and reports **ENVIRONMENT BLOCK / exit 3** ("not a source outage; you can still deploy; confirm via a green deploy run") instead of the code-2 "data source broke" path; CI reaches the site so it never hits code 3. (2) `docs/CLOUD-SESSION.md` gains an explicit "a blocked environment can still deploy" table + the green-"Deploy WordPress plugin"-run verify fallback for when the visual curl is unavailable. (3) `CLAUDE.md`'s verify section notes the same fallback. The only thing that needs the owner is optional: allowlist `asktherecruiter.com` in the environment's egress policy to restore the visual curl step. |
| 2.19.82 → 2.19.95 (Jul 21) | **Coverage + integrity + autonomy batch (large session).** (1) **New dormant sources**, each routed through the shared extractor+guards+poster and activated by adding a GitHub secret: `supplemental_news.py` (NewsData.io + Marketaux + Finnhub, non-English/EU news), `distress_watchlist.py` (CourtListener US bankruptcy + Companies House UK insolvency → watchlist news search), `foreign_filings_ingest.py` (EDINET JP + OpenDART KR filing bodies). FMP earnings **dropped** (transcript endpoint is paid-only, HTTP 402). (2) **US-HQ global-cut fix**: a US company's *global* layoff is honestly labeled `country='Multiple countries'`, so it vanished from a `country=United States` filter (Oracle 21k, Block 4k looked "missing"). New `country_basis=any` (union of job-location OR employer-HQ) used by the table + exports; headline stats stay strict. Moved US-vs-survey-benchmark from 64%→76% (all-industry), 60%→66% (tech). (3) **WARN detail fixes**: `.pdf`-in-query-string URLs (WA fortress) now link the actual notice PDF, not the state list; honest "AI classification pending" → "not stated in this filing". (4) **AI precision**: `recall_precision.py` gained AI-attribution precision (quotable-AI-statement rate); a `reclassify-legacy-ai` batch cleared the 76-row legacy backlog, taking precision 98%→100% (US AI 52%→49%, global AI 109k→100k — lower but every job now quote-backed). (5) **Reconciliation** surfaced in the row-detail panel (announced vs executed WARN). (6) **Autonomy**: `health_digest.py` + `health-digest.yml` weekly tripwire — reads the health ledger, fails RED and **emails info@asktherecruiter.com via the new `/alert` endpoint** on any STALE/degraded source, with a paste-ready Claude fix instruction (benign no-register states HI/AR/WY/NH suppressed; 3-day dedup); added the missing zero-result drift tripwire to the LEGACY custom WARN scrapers (parity with new-states). (7) **Gov-sector coverage** (#31) expanded in GDELT `SEGMENT_TERMS`. (8) **Mobile**: bar-list charts bled past the card edge — `.alt-barrow-name` needed `min-width:0` for the ellipsis to engage. (9) Sources/Health pages updated to list only live providers. See RUNBOOK "add/tune/enhance a source" + the "a data source broke" playbook. |
| 2.19.25 (Jul 19) | **Sources page rebuilt as tables + gap states in plain English; why-verified link opens in a new tab; "50 states" lead wording.** The `/sources/` page is now table-first: an "every source at a glance" table (SEC, state WARN, Eurofound ERM, GDELT, NewsAPI, JP/KR/BR research candidates — each with region, what it is, the tier it feeds, and a link), the full state-registry table, and a new **"States we can't fully cover yet — and why"** table that explains each gap in human terms (HI/OK publish no headcount; MO/NM publish nothing; MA/MN publish data but need a custom reader we're building). The Verified card's "Why this is verified" link now carries `target="_blank" rel="noopener"`. Lead copy changed "WARN notices from 41 US states" → "all 50 US states (WARN notices from 41)" to stop the WARN-count being misread as total coverage. (Deploy note: 2.19.23–2.19.25 stacked behind a ~40-min GitHub Actions runner outage; the queued runs were cancelled so the newest push deploys the full superset.) |
| 2.19.24 (Jul 19) | **Sticky active-filter summary.** The active-filter chips ("Filtering: Year 2026 · Industry: Technology …") were rendered inside the sticky `.alt-count-row`, which sits below all the charts — so while scrolling the long results/charts region there was no indicator of what was filtered. Moved the `#alt-active-filters` element to a standalone bar directly under the filter controls with `position: sticky; top: 0` (native, no scroll listeners): it docks under the filters, pins to the top the moment they scroll out of view, and re-docks on the way back up. De-stickied the count-row (now a plain count + export row above the table) so only one bar pins. Admin-bar top-offsets and the mobile horizontal-chip-scroll moved with it; empty (display:none) when no filters are set. |
| 2.19.23 (Jul 19) | **Live-review UX batch: Roles filter, scrollable charts, card cleanup, and the "events" → human-word rename.** From a page walkthrough. (1) **New "Roles most impacted" filter** — a multi-select dropdown (fixed role vocabulary from `alt_role_categories()`) that scopes the whole page to layoffs whose source named that team; backend adds a `roles` param to `alt_db_where` (OR of `role_categories LIKE ',slug,'`, `unknown` never accepted), front-end wires it into params, the active-filter chips (new `ROLE_LABELS`), and reset. (2) **"Reset all filters" moved** up next to the Tech-industry quick-view. (3) **Compact bar-list cards now scroll** — every row renders (was truncated to 4) inside a short `overflow-y:auto` box, so all items (Roles, industries, leaders…) are reachable without expanding. (4) **Removed the fixed "🤖 US AI job cuts, incl. planned" card** (the always-full-US-year one that ignored filters) and its dead client fetch; the filter-responsive "AI-linked, broad (verified + announced)" card already covers that need. (5) **Location on the leaderboard is state/country only** (dropped city parsing per feedback). (6) **Roles chart explained** — the sub-line now says each bar is total job cuts with the orange/🤖 part being the AI-linked share, and a new methodology paragraph covers how role categories are found (two-pass model on stored quote, nothing inferred) and why a bar with no orange isn't an error. (7) **"events" → human words across the visible UI**: leaderboard "Largest single job cuts", company page "Layoff rounds over time", counts → "layoffs", company-timeline → "rounds", source-naming → "reports"; the interactive JS strings too. Dense methodology prose (where "events" is a load-bearing technical term — "canonical events", "per-event database") is deliberately left for a separate careful pass. |
| 2.19.22 (Jul 19) | **Trust + dedup batch: location on the leaderboard, a dedicated Data Sources page, count-scaled dedup window, and a tightened methodology.** Four things from a live-site review. (1) **Location on "Largest single events":** the leaders query now returns a short `location` (city parsed from the WARN excerpt where present, else state, else non-US country) and the front-end appends it to the display label — so six WARN filings by one company (Flagship Facilities: CA 178/13/5/2, WA 67/4) read as the distinct legal notices they are, not duplicates. entry[0] stays the bare company name so tap-to-filter is unchanged. (2) **New `/ai-layoff-tracker/sources/` page** (`page-sources.php` + `[alt_sources]` + retry-until-present auto-create hook): a journalist-facing directory of every pipeline, with all 41 state WARN registries rendered as live links straight from `alt_state_warn_urls()` (generator now emits the full map, not just the accessor — parity test still guards it), plus SEC/EDGAR, Eurofound ERM, GDELT/NewsAPI, and the JP/KR/BR research candidates. Linked from a new "Why this is verified →" link on the Verified headline card, the top lead bar, and a new **"What sources do you use?" FAQ**. (3) **Count-scaled dedup window** (`dedupe_llm.py`): the flat 120-day cluster window let an identical large figure re-reported months apart escape the deep scan entirely (VW "50,000" twice, 125 days apart — 5 past the window). Near-identical material counts (≥95% similar, ≥1,000 jobs) now get a 365-day window so the model at least adjudicates them; dissimilar or tiny counts keep the tight window (conservative — never loosens clustering elsewhere). `dedupe_llm` now also reports to the public health ledger (merged this run + candidate clusters awaiting a later rotation), so "is dedup working?" is a live number. `tests/test_dedupe_window.py` pins it (218 railway tests pass). (4) **Methodology cleanup:** removed the redundant in-page "Live data-source status" block (its data lives on the health page; the JS render is null-guarded so removal is a clean no-op), and collapsed the verbose "Databases by region" section into a short pointer to the Sources page plus the two disclosures unique to it (country-count growth, known gaps). |
| 2.19.21 (Jul 19) | **INCIDENT + fix: hard `require` of the generated WARN-URL partial fataled the whole plugin mid-deploy.** WordPress emailed a recovery-mode notice: `E_ERROR ... Failed opening required '.../templates/partials/warn-state-urls.php'` at `ai-layoff-tracker.php:26`, thrown from bootstrap via `wp-settings.php`. Root cause: the 2.19.16 two-link feature added a bootstrap-time `require_once` of the generated partial. FTP deploys upload files ONE AT A TIME, so the new main plugin file landed before the partial did (the mid-upload race the iron rules already flag for the flush/contact hooks) — and a hard require of a not-yet-present file is a fatal that takes down the ENTIRE plugin (tracker + admin-ajax + wp-admin) on every request until the partial arrives. Pre-upload PHP lint (2.18.1) can't catch it: it's a runtime missing-file, not a syntax error. It self-healed once the partial finished uploading (site was serving 2.19.20 fine), but the fragility would recur on every future deploy. Fix: include the partial only `if (is_readable(...))`, and ALWAYS define `alt_state_warn_list_url()` as a `''`-returning stub when the partial is absent — so no caller ever hits an undefined function and WARN rows merely omit the state-list link until the real map lands. Reinforced iron rule: a bootstrap `require` may only target files that ship IN this same main-file commit AND are essential; a generated/optional data partial must be guarded + stubbed, never hard-required. |
| 2.19.20 (Jul 19) | **All of an event's sources on the detail panel (WARN filing AND the press link).** A merged/corroborated event stores every retained source in the `reports` graph (`alt_event_add_report`), but the row + detail panel only ever surfaced ONE — the row's own primary `source_url` (plus, for WARN, its state list link). So an event backed by both an official WARN notice and the news article that reported it showed only one of them. `/query` now attaches `additional_sources` to each row via `alt_attach_event_sources()` — ONE batched query over the page's event_ids (the company-directory pattern, never per-row), returning that event's other retained sources whose URL is non-empty and differs from the row's own primary link and its WARN state-list link (duplicate URLs collapse). The detail panel renders them as an "Other sources for this event" block (name + source-type label), so corroboration is visible instead of hidden. Read-only: no rows, events, counts, dedup hashes or totals touched; most events have a single report and show nothing extra. Result is cached with the rest of `/query` and invalidates on writes. |
| 2.19.19 (Jul 19) | **Industry backfill for blank-industry rows (finished + shipped a half-built task branch).** A large share of rows carry no `industry` — every structured WARN notice does, plus older news/8K rows whose extraction never resolved a sector — so the industry dropdown and by-industry aggregates under-represented them. The server half existed on an un-merged task branch (`busy-faraday`); this completes and ships it. New keyed `POST /industry-backfill` fills ONLY blank `industry` with a label from the closed vocabulary (`alt_industry_vocabulary()` = `alt_industry_rules()` keys, 19 labels), rejecting anything outside it; it never overwrites a set industry, never pins rows, never touches counts/dates/sources/AI labels. `alt_db_upsert` no longer blanks a set industry when an import (WARN daily) carries none, so a fill survives re-import; not pinning means a purge-reload just returns the row to the visible backlog (honest enrichment, not an override). New `industry_missing=1` query filter surfaces the backlog. New bounded daily worker `railway/industry_backfill.py` (`industry-backfill.yml`, 04:55 UTC, batch 40, 900s deadline, date-rotating slice so "unknown" rows can't stall the head) classifies from each row's OWN company name + STORED excerpt only (zero external fetches) via new `extractor.classify_industry`, constrained to `INDUSTRY_VOCABULARY`; each row is **double-confirmed by two independent model passes** and written only when both agree on the same non-empty label (disagreement or "unknown" → left blank). `tests/test_industry_backfill.py` guards Python↔PHP vocabulary parity (set + order), the pure validation gate, and the two-pass agreement logic (210 railway tests pass). A rejected label from the endpoint is treated as vocabulary drift and fails loudly. |
| 2.19.18 (Jul 19) | **WARN two-link render fix + list-only self-heal.** The 2.19.17 render logic showed BOTH links whenever `source_url` and `source_list_url` differed — which wrongly gave list-only states (e.g. WA, whose stored rows still carried the pre-move `esd.wa.gov/about-employees/WARN` URL) two redundant links: the stale stored list page AND the fresh derived one. Fixed: a new `warnLinks(row)` helper is the single render authority — an **exact per-notice** `source_url` (the six govt per-record states: AZ, DE, GA, KS, ME, VT) renders primary=the notice + secondary="State WARN list"; a **list-only** row renders ONE link and prefers the freshly derived `alt_state_warn_list_url()` value over the possibly-stale stored `source_url`, so the WA database-page move self-heals on the front-end with no re-import. Empirical all-state audit (live `/query` per state, news-link contamination filtered): exactly 6 states publish govt per-record notice pages our importer already captures; ~35 are list-only (no per-notice permalink exists to link); MO & NM are empty (unpublished — the public-records-request operator path). Both render sites (table cell + detail panel) and the numbering (git 2.19.16→2.19.18 for two-link; 2.19.17 in this log is the feature entry, this is the render fix on top) reconciled here. |
| 2.19.17 (Jul 19) | **Two links on WARN rows: the exact notice AND the state list.** WARN rows now carry `source_list_url` (the official state WARN program/database page, derived from the row's state) alongside `source_url`. Where `source_url` is an exact per-notice page (VT-style states), the table cell and detail panel show both — the specific record plus a "State WARN list" link to the index it sits in — instead of silently dropping the list. Where the state publishes only a list (WA, CA, and most states — the notice is a row in a database, no per-notice permalink), the two URLs match and one honest link renders as before. The state→list-URL map is single-sourced: `railway/sources/warn.py::STATE_WARN_URL` is authoritative, `generate_warn_urls.py` writes the PHP partial `templates/partials/warn-state-urls.php`, and `tests/test_warn_url_parity.py` fails the build if they drift. Also refreshed the stale WA URL to the current ESD "WARN layoff and closure database" page, and added `source_list_url` to the CSV export. |
| 2.19.16 (Jul 19) | **Duplicate no-store Cache-Control root-caused and overridden at the Apache layer.** Every PHP response from the host carries a SECOND `Cache-Control: no-cache, no-store, must-revalidate` (+ `Pragma: no-cache`, `Expires: 0`) appended AFTER PHP's headers — proven host-side, not WP-side: a direct request to a plugin file that exits before WP loads still carries the trio, and so does an origin-direct curl (`--resolve` to the Bluehost IP) that bypasses Cloudflare AND the Railway root proxy (`/blog` traffic transits it: `x-railway-*` headers + base64 `host-header: shared.bluehost.com`). Browsers merge the duplicates and no-store wins, so the browser-cache layer (API max-age=300 / page max-age=180) was dead; the CF edge rule survived only because its Edge TTL overrides origin. Fix: `includes/htaccess.php` maintains a marked mod_headers block in the WP root `.htaccess` (`<If>` sections merge after ALL other Apache config levels, so its `Header always unset` + `Header set` win) scoped to anonymous GET/HEAD on the six public read endpoints + the tracker page — `/status` keeps its intentional no-store, logged-in requests untouched. Retry-until-verified init hook (contact-page pattern) with a cache-busted loopback probe after every write: 5xx/no-answer restores the previous file byte-for-byte and marks failed until the next version bump (a bad `.htaccess` would 500 the whole install). Block validated against a local Apache 2.4 with the injection simulated at server-config level (7 scope cases incl. status/logged-in/404). Also: `alt_is_public_read_request` now accepts HEAD alongside GET (HEAD mirrors GET cacheability; note `cf-cache-status` on HEAD reads DYNAMIC regardless — CF only serves cached GETs, so verify edge caching with GET). |
| 2.19.15 (Jul 19) | **Retry-until-verified schema guard.** The 2.19.14 deploy hit the known mid-FTP-upload race from the other side: a request flipped `alt_deployed_version` while the OLD `includes/db.php` was still on disk, so `dbDelta` ran without the new `role_categories`/`roles_evidence` columns and never retried (the version gate was satisfied). Every roles query then silently errored to empty: `top_roles: []`, `roles_known_entries: 0`, worker saw "No rows pending". New `alt_ensure_schema_once` hook checks INFORMATION_SCHEMA for a sentinel column (`ALT_SCHEMA_SENTINEL_COLUMN`, update it on every schema change) and re-runs `alt_db_install()` + bumps `alt_data_ver` on every request until the column verifiably exists — the same retry-until-verified pattern the contact page already uses. Rule reinforced: one-shot version-gated hooks may not perform anything that must exist. |
| 2.19.14 (Jul 19) | **Role-impact extraction + "Roles most impacted" chart** (built on a task branch as 2.18.87, merged to main and shipped as 2.19.14). New fixed role-category vocabulary (10 categories: engineering, product/design, customer support, sales/marketing, HR/recruiting, operations/warehouse, content/trust-and-safety, finance/admin, manufacturing, retail staff) with `alt_normalize_roles` keyword mapping (multi-match — one source names several teams) applied at upsert + `/cleanup` to rows whose freeform `roles` text is stated. New `role_categories`/`roles_evidence` columns; keyed `/enrich-roles` endpoint fills ONLY blank categories (never pins, never touches counts/dates/sources/AI labels; real categories need a ≥12-char stored-text quote; `unknown` marks "checked, source doesn't say" so the queue drains and never appears on any public surface). Bounded daily worker `railway/enrich_roles.py` (`enrich-roles.yml`, 04:23 UTC, batch 40, 900s deadline, largest events first) reads ONLY already-stored row text (roles/excerpt/quotes — zero external fetches) via new `roles_missing=1` query filter, DeepSeek STRICT JSON constrained to the shared vocabulary, quote-verified locally, model failures leave rows queued. `/aggregate` gains `top_roles` ([label, jobs, ai_jobs] like top_industries, reasons-style one-SUM-per-tag) + `totals.roles_known_entries/jobs` (honest coverage denominator). Tracker gains a "Roles most impacted" bar card (AI share = orange segment, CSV download, coverage-stating subtitle); CSV/JSON exports carry role_categories. `enrich-roles` added to the data-corrections allowlist. |
| 2.19.7 (Jul 19) | **Reason-tag backfill.** ~7,400 non-WARN rows (7,292 Eurofound ERM + ~120 older news rows) carried no `reason_tags`, so the Reasons chart/filter under-represented the announced tier. New daily bounded job (`railway/reason_backfill.py` + `reason-backfill.yml`, 04:40 UTC) tags them from the FIXED vocabulary using each row's STORED excerpt only — no source re-fetch, no count/date/stage/AI-label changes. ERM rows map deterministically from Eurofound's own recorded restructuring type embedded in our template excerpt (Internal restructuring→restructuring 4,166; Merger/Acquisition→merger_acquisition 336; Offshoring/Delocalisation→offshoring 374; the live CSV mixes casings, so the match is case-insensitive); Closure/Bankruptcy/Outsourcing/Relocation types name no vocabulary reason and honestly stay untagged with zero model cost. Freeform news excerpts go to DeepSeek with a strict-JSON prompt; `ai_automation` additionally requires the employer's exact quote present in the excerpt (validated locally), `possible_ai` covers press-linked AI framing, and an excerpt naming no reason is a definitive skip. Writes go through /edit (vocabulary re-validated server-side; rows pinned `edited=1` so the daily ERM re-import can't revert — accepting that later Eurofound count revisions to an edited factsheet no longer flow). WARN rows are excluded structurally (`sources=news,8K,press_release,erm` matches source_type; WARN notices state no reasons). Reports health as `reason_backfill`; deadline guard stops safely between rows; a failed /edit batch, health write, or fully-failed model pass exits non-zero. A Python↔PHP vocabulary-parity test guards against silent server-side tag-dropping. Daily model slice rotates by date so no-reason rows can't stall the queue head. |
| 2.19.6 (Jul 19) | **Announced-to-verified conversion metric.** New public cached `GET /conversion`: per announcement month, the share of announced jobs (announced=1) with verified same-company records (announced=0) dated after the announcement anchor and within `window_months` (default 6, max 24), matched jobs capped at each announcement's own count so no plan converts above 100%. Anchor = evidenced `announcement_date` where present (39 rows), else the announced row's recorded date — often the planned effective date, which can only understate conversion. Months are labeled complete / maturing (window still open, figure expected to rise) / pending (future-dated plans; excluded from the chart, kept in the CSV). Row filters scope the announced side only; verified matches deliberately unfiltered (execution can be recorded elsewhere). Tracker page gets a full-width "Do announced cuts actually happen?" bar card beside the announcement-survey comparison: blue = complete window, orange = still maturing, PNG+CSV downloads, plain-language note. Read-only; no rows, events, dedup hashes or totals touched. |
| 2.18.72 (Jul 19) | **Employer-domicile basis for the announcement-survey comparison.** `/aggregate`+`/query` gain `country_basis=employer` (country filter matches evidenced employer domicile, falling back to job location only where domicile is blank — never both) and an `ai_broad=1` row filter matching the existing ai_broad aggregate definition. A curated, committed registry of deterministic public HQ facts (`railway/seed_data/employer_domicile.json`, ~140 companies, ambiguous domiciles deliberately absent) backfills ONLY blank `employer_country` on 'Multiple countries' rows via `/enrich-context` (`employer-domicile-backfill.yml`, bounded, idempotent, dry-run mode; corrections trail names the registry basis via the endpoint's new optional `reason`). Dry run matched 251 of the 436 largest multi-country rows. The tracker's announcement-survey charts add an orange "US-employer basis (survey-comparable)" line and the health benchmark race table adds employer-basis total/AI rows, so US-HQ multi-country events (Oracle 21,000; Block 4,000; UKG 950; ZoomInfo 600...) stop being invisible to the US column. Counts, dates, sources, AI labels and dedup hashes untouched; the strict comparator's `employer_country` gate is unchanged. |
| Ops (Jul 18) | **Eurofound ERM health visibility.** The licensed, source-linked ERM importer was successful but absent from the health page because it did not publish collector telemetry. It now records running, successful row-count, or degraded status in the same public ledger as the other collectors; a failed health write or ERM batch remains a visible workflow failure. The source registry now identifies ERM as a structured official EU source, scoped to its own documented threshold and geography. |
| 2.18.28 (Jul 18) | **Monthly announcement-survey reconciliation history.** Retains January–June 2026 official announcement-survey reports as source-linked monthly and YTD AI-cut benchmarks, with the actual announcement month kept separate from the report publication month. The tracker now renders both monthly and cumulative strict-US comparison trends and a fully linked table. The scheduled worker adds a newly published month from the announcement survey’s official feed, queries source-evidenced tracker records by the same announcement-date window, and records a coverage alert without falsely calling expected data shortfall a workflow failure. Authentication, source fetch, parse and record-write failures still fail loudly; a manual `fail_on_gap` switch remains available for an intentional CI threshold gate. |
| Ops (Jul 18) | **Legacy AI evidence timeout repair.** The scheduled reassessment was cancelled exactly at its 20-minute Actions limit, so its batch is now five and the worker has a 15-minute between-row deadline plus a 35-second model timeout. A bounded partial pass resumes safely next day; a fully unreadable attempted batch still fails visibly. |
| 2.18.27 (Jul 18) | **Publisher and research-product usability.** Added a health-page US national/state widget builder that emits a copyable noindex iframe and exact filtered tracker preview, with no metro scope, third-party code, backlink request or implied completeness. The published quarterly report now offers frozen JSON/CSV appendices derived solely from its immutable stored snapshot. OpenDART has an inactive, metadata-only official discovery client; Korea remains unclaimed/not live pending Korean evidence fixtures, retained-document stage, cursor, health reporting and permission review. The first California recall candidate remains unpublished until independent transcription and record-by-record match review are complete. |
| 2.18.26 (Jul 18) | **Collector-count semantics repair.** The public health page now renders a failed or in-progress collector as “No completed count,” not “0 found.” An upstream GDELT 429 is therefore clearly an unavailable query, never evidence that no historical news exists. |
| 2.18.20 (Jul 18) | **Bounded AI-announcement discovery expansion.** NewsAPI now queries both broad layoffs and explicit AI/automation layoff language across an expanded reputable-outlet list, URL-deduplicating the results. The two calls per twice-daily run remain within the free plan’s stated daily allowance. This increases discovery candidates only; source evidence, deterministic guards and canonical dedup still decide publication. |
| 2.18.19 (Jul 18) | **Announcement-survey API consistency repair.** The tracker page already preferred a report-month-labelled reconciliation over an earlier setup record, but the public benchmark endpoint returned both. It now returns one authoritative retained record per report month while retaining the legacy entry internally for audit. Future writes use the report month itself as the stable key. |
| 2.18.18 (Jul 18) | **Invalid blank-row correction guard.** The public integrity sample exposed one legacy canonical row (ID 60617 / event 34437) with no company, date, source name or source URL. It has no evidentiary value and is removed through the existing correction workflow. Editorial deletion now also cleans the event/report graph only when its last canonical row is gone, preventing an invalid deletion from leaving a phantom integrity count. |
| 2.18.17 (Jul 18) | **Actionable citation-gap samples.** Integrity telemetry now returns up to five already-public canonical rows for any event still missing a linked retained-source report, including its row-level source URL where present. This lets the final exception be assessed from evidence instead of treating a count as an explanation. |
| 2.18.16 (Jul 18) | **Retained-source link repair.** The first citation-integrity check found two canonical events whose row-level source URL was present but whose event graph lacked a linked retained-source report. Added a bounded, key-protected repair that copies only the already-stored canonical-row source data into that event’s retained report set; it makes no external request and changes no event fact. It runs alongside the evidence-hash backfill and reports remaining internal link gaps. |
| 2.18.15 (Jul 18) | **Citation-gap telemetry.** Public integrity status and the health backlog now distinguish raw retained-report volume from the number of canonical events with at least one linked retained-source report. Gaps are shown rather than being implied cited. Added an inactive EDINET official daily-metadata client with bounded, secret-safe error handling and success-only cursor semantics; it does not download filings, create events, run on a schedule or alter coverage claims. |
| 2.18.14 (Jul 18) | **Host-safe widget embed route.** Replaced the shared-host-canonicalized virtual child path with the explicit noindex widget query route, renamed its non-reserved year parameter to `tracker_year`, and remove `X-Frame-Options` during response-header construction only for that iframe response. |
| 2.18.13 / 2.18.12 (Jul 18) | **Widget-route investigation.** The initial virtual child-route attempts were blocked by the shared host's canonicalization and were superseded by the explicit host-safe query route in 2.18.14. No tracker data or framing policy outside the widget response changed. |
| 2.18.11 (Jul 18) | **Safe distribution and evidence foundations.** Added a noindex US national/state iframe widget that displays only source-linked verified aggregates and links to the exact filtered tracker view; metro scope remains excluded. Added an exact-company-number-only Companies House identity adapter that returns a source-linked registered-office candidate without creating events or inferring domicile. Added a source-cited California WARN recall draft, explicitly awaiting independent transcription/match review with no published metric. |
| 2.18.10 (Jul 18) | **Rolling public change report.** The health page now combines the prospective release ledger with the disclosed 30-day correction trail and current collector status. It shows release version, ledger-window net change and corrections/removals/merges without mislabelling net totals as gross additions or inventing pre-ledger history. |
| 2.18.9 (Jul 18) | **Tracker page focus cleanup.** Removed the tracker-only auto-generated table of contents while preserving accessible heading semantics, shortened the introduction into useful methodology/benchmark/health links, and made the tracker-only top-spacing override win over the theme’s inline spacing. |
| Ops (Jul 18) | **Daily lifecycle-review visibility.** Added a cloud-only, read-only daily report for the narrow source-supported announcement-to-later-record candidate queue. It validates the returned payload, records only the bounded count and safety rules in the Actions summary, and cannot invoke a merge, alter totals or remove a source. |
| Ops (Jul 17) | **Evidence-hash backfill rate validated and increased.** A controlled 1,000-report production batch completed in about 1.4 seconds, safely hashing only already-retained excerpts and leaving 42,424 pending. The scheduled rate is now two non-overlapping 1,000-report batches per day (06:35 and 18:35 UTC), with a concurrency guard. Expected completion is about 22 days before allowing for newly retained reports; the public integrity endpoint remains the source of truth. |
| 2.18.8 (Jul 17) | **Feature-state visibility.** The public health page now ends with a plain-language Features list that distinguishes released capabilities, active safe backfills/enrichment, pending reviewed connectors and later research/distribution products. It deliberately separates product rollout status from the live collector/error status shown above it. |
| 2.18.7 (Jul 17) | **Metadata completeness on public health.** The operations page now shows the live count of blank industry fields and US state-unspecified job-location rows, explicitly labelling them as evidence backlogs rather than filling them from HQ, office footprint or model guesses. |
| 2.18.6 (Jul 17) | **Provenance, reconciliation and metadata transparency.** The tracker footer now states the deployed release and reads current dataset revision/status time from the public quality endpoint. A read-only, source-required announcement-lifecycle candidate queue surfaces only high-confidence editorial leads; it never changes totals or sources. Integrity status now discloses blank-industry and US affected-job-state backlogs while explicitly prohibiting HQ/office-footprint inference. |
| 2.18.5 (Jul 17) | **Filter-first tracker hierarchy.** Moved date/search/quick-view and all filter controls above the scoped headline cards. Replaced dense inline card explanations with compact links to accessible methodology and announcement-survey-comparison disclosures; fragment links open their destination panel for keyboard and direct-link users. |
| 2.18.4 (Jul 17) | **Announcement-stage accuracy.** Corrected the headline-card language: an announcement record is an announcement-history event, not a claim that cuts are still unfiled or unexecuted. Later source-evidenced filings/reports are linked or merged when confidently matched; unmatched older announcements remain a disclosed coverage/reconciliation task. |
| 2.18.3 (Jul 17) | **Monthly announcement-survey transparency.** The public reconciliation now retains one displayed record per official report month and automatically renders a clearly labelled cumulative-YTD comparison trend once two official months exist. It never fabricates monthly cuts from a single report and continues to describe the difference as a coverage gap, not accuracy. |
| 2.18.2 (Jul 17) | **Compact date-state formatting.** Date, `upcoming`, and `announced` labels now render as one non-fragmenting table-cell unit, preventing announcement badges from wrapping onto a detached second line on narrow screens. |
| 2.18.1 (Jul 17) | **Deployment PHP-fatal guard.** A WordPress recovery email reported an `api.php` parse error during the older 2.17.2 deployment. The committed 2.17.2 source was balanced and the live 2.18.0 tracker/API subsequently returned 200, indicating a transient in-place FTPS upload read rather than a persistent syntax defect. Deploys now lint every plugin PHP file before upload and verify a cache-busted public tracker API response after upload. |
| Ops (Jul 17) | **External GDELT rate-limit notification repair.** A documented upstream HTTP 429 now leaves source health degraded and the historical cursor unchanged, but completes the scheduled workflow as deferred rather than producing a misleading repository-failure email. Unexpected failures remain red. |
| Ops (Jul 17) | **Evidence-hash backfill observability.** The daily retained-excerpt-only hash job now validates its bounded input and response schema, applies connection/overall time limits, and writes updated/remaining progress to the Actions summary. It still neither fetches external pages nor changes sources, excerpts or factual event fields. |
|---|---|
| 2.18.0 (Jul 17) | **Public AI Tracker Health page.** Added a dynamic operations page at `/blog/ai-layoff-tracker/ai-tracker-health/` with current collector state, last pull, source scope/cadence, safe degraded details, integrity/backlog counts, workstreams and announcement-survey alert context. It uses existing public endpoints; run-history charts begin only when append-only telemetry is installed rather than fabricating legacy daily pulls. |
| 2.17.9 (Jul 17) | **Success-anchored GDELT history recovery.** Historical global-news recovery now uses one seven-day window and advances its persistent cursor only after success. HTTP 429 responses honor a bounded Retry-After/backoff delay, and failed windows stay queued for the next run rather than disappearing until a later rotation. The public source-health endpoint still shows the external degradation; no proxying or prohibited workaround is used. |
| Ops (Jul 17) | **Announcement-survey-candidate context queue.** The daily, evidence-only context worker now starts with announced AI-tagged US job-location candidates ordered by disclosed job count, then rotates the bounded result page daily. This prevents one inaccessible high-impact source from starving later candidates while keeping exact source quotes mandatory; it does not infer employer domicile, announcement date or AI-primary causation. |
| 2.17.8 (Jul 17) | **Dataset release ledger.** Versioned deployments now retain a public snapshot of dataset revision, canonical rows/events and retained reports. The ledger starts prospectively and explicitly does not fabricate legacy addition counts; corrections remain separately disclosed. |
| 2.17.7 (Jul 17) | **Bounded legacy evidence-hash backfill.** Added an autonomous daily 500-report backfill that computes SHA-256 only from excerpts already retained in the database. Public integrity status now discloses hashable, hashed and remaining reports. It never retrieves or claims to archive publisher pages. |
| 2.17.6 (Jul 17) | **Immediate bulk evidence registration.** A WARN import temporarily left newly inserted bulk rows outside the canonical-event graph until the daily migration. Bulk upserts now register their canonical event and retained source report in the same request; re-imports remain idempotent. |
| 2.17.5 (Jul 17) | **Measured-recall publication guardrails.** Added public country-period recall history and a key-protected writer that refuses a sample without a public reference-set URL, bounded numerator/denominator and explicit basis. The companion protocol makes clear that sample recall is neither country completeness nor an accuracy score; the superseded 5/35 baseline is not presented as current. |
| 2.17.4 (Jul 17) | **Public announcement-survey reconciliation panel.** The tracker page now renders retained official announcement-survey comparisons with their strict qualifying tracker figure and a plainly labelled coverage gap—not a claimed accuracy percentage. New reconciliation records retain the report month so the public history grows month by month instead of overwriting a calendar-year slot. |
| 2.17.3 (Jul 17) | **High-impact editorial triage queue.** Added a public, read-only review queue for very large (5,000+), source-quoted AI-primary and multi-country events. It only identifies records for human review, reports retained-source counts and never alters a record, its sources or totals automatically. |
| Ops (Jul 17) | **Announcement-survey threshold failure repair.** The reconciliation command piped output through `tee`, which masked its non-zero threshold result. Enabled `pipefail` so an out-of-threshold benchmark visibly fails the workflow while still retaining/publishing its record. |
| 2.17.2 (Jul 17) | **Retained evidence hashes.** Each newly retained source report now carries a SHA-256 hash of its stored evidence excerpt, exposed with the event’s source reports. This is tamper-evidence for the retained excerpt, not a claim to archive an entire publisher page; legacy report-hash backfill remains a separate bounded migration. |
| 2.17.1 (Jul 17) | **Retained announcement-survey reconciliation history.** Monthly reconciliation now posts its official report URL, strict source-evidenced tracker total, broader diagnostic figure and coverage gap to a public retained endpoint instead of leaving it only as a GitHub artifact. A threshold miss still fails loudly and never changes tracker totals. |
| 2.17.0 (Jul 17) | **Enrichment status and runtime bound.** Quality status now marks announcement/domicile enrichment active. Its successful first ten-record pass took 19m22s (3 source-supported enrichments; 7 inaccessible or unsupported), so the unattended daily batch is reduced to five to stay under the 20-minute Actions cap. Inaccessible publisher pages remain visibly unverified; they are never bypassed. |
| 2.16.9 (Jul 17) | **Announcement-date benchmark basis.** The announcement-survey reconciliation query now filters and groups on `announcement_date`, which exists only when an exact source quote supports it. Rows with unknown announcement dates remain visible in the tracker but are excluded from this like-for-like comparator rather than being silently dated by their effective cuts. |
| 2.16.8 (Jul 17) | **Announcement/domicile evidence enrichment.** Added separate `announcement_date` and employer-domicile evidence fields, an exact-quote-only enrichment endpoint and a bounded daily worker. It fills only blank fields from freshly re-read source text; it cannot alter counts, effective layoff dates, stages, sources or AI labels. Announcement-survey reconciliation now requests the explicitly source-evidenced announcement-date basis, excluding unknown dates rather than substituting effective dates. |
| 2.16.7 (Jul 17) | **Public quality-status foundation.** Added a machine-readable `/quality-status` endpoint with the current dataset revision, 30-day disclosed correction counts, collector health, canonical-source integrity and explicitly scoped workstream states. The on-page corrections section links to it. Additions are deliberately not fabricated from legacy rows without immutable ingest timestamps; that needs the forthcoming dataset-version ledger. Planned or permission-bound connectors are exposed as such; the endpoint never equates absence with coverage. |
| Ops (Jul 17) | **Legacy evidence runtime bound.** The scheduled source-evidence reassessment reached its 20-minute GitHub Actions limit while processing 25 rows, so its scheduled batch is now 10. This preserves the exact-quote requirement and retry behavior while ensuring one slow publisher or model call cannot cancel the complete daily pass. Manual runs can still select up to 100 rows when deliberately supervised. |
| 2.16.6 (Jul 17) | **Announcement-survey scope repair.** The reconciliation artifact now reports a strict US-employer/AI-primary/announcement metric separately from the visible, broader US-job-location/any-AI announcement figure. The tracker cards explicitly warn that they are not survey-comparable, and the country chart labels its filter-exempt values as other possible pivots rather than implying they are inside an active country filter. |
| 2.16.5 (Jul 17) | **Deep-dedup queue and evidence repair.** The prior 60-cluster cap always chose the largest clusters, which could permanently starve a small but high-confidence duplicate pair (the Oracle 20,000-job reports exposed this). The bounded queue now reserves capacity for exact-count repeats and rotates every remaining candidate deterministically. Confirmed duplicate rows now merge their source reports into the keeper's canonical event before removal; dedup no longer trades evidence links for a cleaner total. |
| Research (Jul 17) | **Official-connector admission log.** Documented current primary-source findings for SEDAR+, LSE RNS and ASX. RNS RSS is retired, ASX announcements state non-commercial-use restrictions, and SEDAR+ has a public interactive search but no project-approved incremental interface. Future country connectors must meet licence, stable-interface, evidence-retention, fixture and source-health requirements before becoming live. |
| 2.16.4 (Jul 17) | **Coverage-claim correction.** The market registry and public methodology now distinguish live collectors from official-source candidates. Canada SEDAR+, RNS, ASX, TDnet/EDINET, NSE/BSE, HKEXnews, SGXNet, SENS, DART and TASE were never direct feeds; they are now explicitly labelled as such rather than implied country coverage. The methodology also records the live SEC 6-K foreign-issuer search. |
| Data integrity (Jul 17) | **Duplicate-source retention repair.** Removed client-side pre-dedup skips from all normal ingest paths. WordPress remains the authority for deduplicated totals, but now receives every duplicate article/filing and attaches it as a corroborating source report instead of silently dropping the evidence before it reaches the event graph. |
| 2.16.3 (Jul 17) | **Integrity progress telemetry.** Added a public aggregate-only `/integrity-status` endpoint reporting canonical-event migration progress and retained source-report count, so this foundational data-quality transition can be measured rather than inferred. |
| Ops (Jul 17) | **Historical sweep reliability bound.** A 50-candidate verification sweep exceeded a sensible daily runtime, so scheduled history recovery is now 10 candidates per run and OpenRouter client calls time out after 45 seconds (with one SDK retry). Timed-out candidates are logged and skipped; they never stall the queue. |
| Ops (Jul 17) | **GDELT failure semantics.** Historical GDELT retries are now bounded to three short attempts; exhausted retries raise an error, mark source health degraded and fail the run. The previous collector returned an empty list after a long retry budget, creating a silent coverage-hole risk. |
| Ops (Jul 17) | **Historical wall-time budget.** The scheduled GDELT sweep now exits cleanly after ten minutes of extraction work. Combined with the per-call timeout, this prevents a run from overlapping future scheduled recovery windows. |
| 2.16.2 (Jul 16) | **Source-health running state.** Collector status now reports `running` before a source pull, then healthy/degraded on completion. The public panel no longer presents an active long-running collection as missing status. |
| Data source (Jul 16) | **SEC foreign-issuer expansion.** EDGAR discovery now searches both domestic 8-K and foreign-issuer 6-K filings under the same legal-filings tier, retaining the exact form in the source label. This expands first-party disclosure coverage without weakening source or evidence standards. |
| Ops (Jul 16) | **Historical-sweep workload bound.** The scheduled GDELT history sweep now caps itself at 50 model candidates before article fetching. Trusted-article retrieval is bounded parallel work, so one slow publisher cannot serially stall a whole window. An initial unbounded verification run was cancelled after it exceeded the expected runtime; the rotating recovery programme now has a predictable cost and completion window. |
| Ops (Jul 16) | **Data-quality workflow reliability.** The daily report itself was healthy; only its optional DeepSeek classification spot-check failed. Replaced the brittle inline request with a retried, time-bounded runner that reports temporary audit unavailability in the Actions summary without failing the whole report, while preserving fail-loud behavior if a selected automatic correction cannot be applied. |
| 2.16.1 (Jul 16) | **Public source-health disclosure.** Added a live methodology panel showing the latest autonomous collector status, raw candidate count and timestamp. It explicitly distinguishes a healthy collector from a complete national census, and marks failure as degraded rather than allowing silence to imply zero layoffs. |
| 2.16.0 (Jul 16) | **Canonical event/source-report foundation.** Added an event graph that counts the canonical layoff once but retains each later exact/fuzzy duplicate as a separately retrievable source report. Existing rows are converted in resumable, no-LLM batches; no visible totals, source links or records are deleted by the migration. |
| 2.15.0 (Jul 16) | **Autonomous legacy-evidence and source-health pass.** Added a daily, bounded historical worker that re-fetches an existing AI-linked source and reclassifies causation only when an exact source quote supports its result; inaccessible sources remain legacy/unreviewed and no source/count/date is altered or removed. Added per-collector health reports (status, raw count, timestamp, error detail) at a public API endpoint, so a broken source is observable rather than a silent coverage hole. |
| 2.14.1 (Jul 16) | **Deploy API-cache schema fix.** Version deploys now also bump `alt_data_ver` and clear FAQ/coverage transients. Root cause: the deploy hook cleared page caches but not the versioned `/query`/`/aggregate` micro-cache, so a newly deployed response field could remain absent for up to five minutes. Live verification caught it; every deploy now changes the endpoint cache key immediately. |
| 2.14.0 (Jul 16) | **Autonomous source-first integrity foundation.** Added a market/source registry and broader, reviewable global discovery vocabulary; an opt-in official company IR/newsroom RSS collector; `employer_country`, AI causal class, evidence confidence and publication-status fields; a hard guard rejecting an AI-primary/contributing claim when its claimed quote is not in the supplied source passage; public API detail fields and methodology clarity; monthly announcement-survey like-for-like reconciliation that fails loudly outside the configured threshold; and mobile containment for theme-width/popover overflow. Full implementation handoff: `docs/AUTONOMOUS_DATA_QUALITY.md`. Existing rows remain `legacy_unreviewed` until source-evidence reclassification; no historical headline is silently relabeled. |
| 2.9.0–2.10.1 (Jul 15–16) | **World regions + coverage maximum + SEO pack.** 10 region tabs (adds Canada-first ordering, Latin America, Middle East, Africa; Europe 8→44 countries incl. Russia/Greenland/Balkans/Caucasus, Asia→29, Oceania) with complete on-page region→country documentation rendered from the config; empty-region tabs scope honestly (inject missing country options — Africa tab used to silently show world rows); region selections collapse to one chip; red empty-state; bold narrative numbers; one-row toolbar; mobile fixes (search box was 320px tall — flex-basis became height). **Coverage:** GDELT query de-AI'd (the AI clause excluded ALL general worldwide layoffs from the pipeline — root cause of thin Europe), weekly backfill windows (monthly truncated at the 250-article cap); EDGAR plural terms (+~90-130 filings/90d); custom WARN collectors for MA (Akamai HTTP/2 + Chrome fingerprint via httpx)/MN (Radware-walled; Wayback CDX discovery + seed PDFs)/NC (Drupal CSV)/NV (master PDFs + city vocabulary) = **41 WARN states, the obtainable ceiling**; **Eurofound ERM importer** — official EU27+Norway+UK per-company restructuring announcements, 7,125 job-loss events / 4.56M jobs since 2015, license authorizes reuse with attribution, dedup by factsheet id so Eurofound revisions update in place, daily 12:30 UTC sync. **SEO:** FAQPage JSON-LD + server-rendered FAQ with live numbers (crawler/LLM-visible without JS), Dataset schema enriched (spatialCoverage, dateModified, variableMeasured, layoff-tracker alternateNames). **Recall benchmark #1 (2026-07-15): 14.3%** (5/35 June–July reference events) — the honest baseline before the fixes above; re-measure after sweeps land. |
| 2.8.0–2.8.2 (Jul 15) | **Editorial correction layer + super-test fixes.** `/edit` endpoint + `edit-entries` workflow (field corrections pin the row `edited=1`, suppress the original source hash, survive daily purge+reimport); suppression list honored by `/add`+`/bulk`+upsert, recorded by `/trash`; real calendar-date validation (2026-03-32 → MySQL zero date); `sources` filter matches source_type too (sources=news was silently 0); `/facets` exposes sources vocab; live worked-example figure; `edited` flag public in `/query`. Data corrections from the 51-agent super test: 8 Florida STATE-SIDE TEST rows removed (fake "AT&T" 78,788 was our #1 entry; collector now skips test-named rows), 10 SEC-extraction non-events removed (dollar figures/percentages/boilerplate/wrong-date dupes), country resolved for 88 hidden rows (Oracle 30K → Multiple countries, BBC 2K → UK; world top-countries gap now 0), Ideal US Talent RI 9,891 → 2 (cross-state double count). FL WARN source URL moved (old path 404s for 2,612 rows; fixed for next import). 2.8.1 lesson: `/edit` initially reported success while every `$wpdb->update` silently failed — fail-loudly check added. |
| 2.7.0–2.7.3 (Jul 15) | **Region tabs + narrative**: 7 colored WSJ-style tabs (World/USA/Europe/UK/Asia/Australia/Canada) driving the country filter, hash deep-links (`#usa`), sector-tracker-style auto-updating narrative ("Today, Jul 15: so far in 2026, N verified layoffs … In 2025, …") scoped per tab; "How our numbers compare to other trackers" panel (announcement survey/WSJ/sector trackers/BLS/ONS/Eurostat links + why we differ); daily numbers-snapshot ping added to the data-quality workflow. 2.7.1 fixed a table-killing crash (date-column render signature missing `row` — every draw threw, UI showed "no layoffs match"). 2.7.2 honest empty-region hint. 2.7.3 stopped deleting Autoptimize caches on deploy (CF-cached-410 incident, below). |
| 2.6.0+ (Jul 15) | **The coverage marathon**: Announced tier live (announcement-stage cuts as a separate source-linked headline — the survey-comparable number with receipts). Custom collectors for ALL 8 broken states (TX Socrata JSON, FL REACT export, GA TCSG ajax, OH DAM CSV, MI Sitecore JSON, CO Google Sheets, ID/LA text PDFs) = +5,719 notices/~682K jobs. Parser unlocks for IL/PA (+1,841) and IA/MD/OR/SC/WI (+3,272) — all were schema quirks, not empty states. Non-English world outlets added (Le Monde, Nikkei, Globo...), English-only restriction dropped. Worked disclaimer example on-page (443,600 announced vs ~96,000 verified, H1-26). **37 WARN states / 42 states overall / 34,424 layoffs / 4.8M jobs.** HI+OK publish no counts (excluded per methodology); MO/NM publish nothing. |
| 2.2.2 | `/trash` resolves public API entry ids; executed the three editorial removals (posts 6499/6179/6516) — totals recomputed to 22,688 layoffs / 2.97M jobs |
| 2.2.1 | Ingest-safety HIGHs from 2nd audit: purge only after successful scrape + only with states=all + ≥5K threshold; date-shaped count values rejected; future WARN data no longer dropped from trend charts; REST nocache headers suppressed on public GETs (unblocks CF edge cache); `/trash` editorial endpoint + workflow; contact-page creation lock; JS races/popover/timezone fixes; docs/ created |
| 2.2.0 | API micro-cache (5-min transients keyed by params + `alt_data_ver`); journalist card light restyle; corrections log reset to launch state |
| 2.1.3 | Trend zero-fill honors multi-select periods (Apr–Jul selection → Apr 0 · May 0 · Jun x · Jul 0) |
| 2.1.0–2.1.2 | `/contact` page: auto-created, topic dropdown, honeypot + server-side math challenge + rate limit, mails info@; creation retries (deploy race); styled to match the main ATR app (cream/tan/olive) |
| 2.0.1–2.0.3 | **WARN count parser fix (first number, not concatenated digits)** + `/bulk-purge` clean reload; "upcoming" tag on future-effective filings; "all causes" stat label; public corrections log; link-precision labels ("(list)" vs exact); weekly data-quality anomaly report |
| 2.0.0 | Multi-select EVERYTHING (years/quarters/months/industry/country/state/sources/reasons as checkbox dropdowns; comma-list API params; AND across dimensions); color-coded filter chips per dimension; clickable date-range control; "layoffs" wording |
| 1.9.0–1.9.3 | Charts on top (compact grid, ⤢ expand); always-visible filter bar; GDELT added to the DAILY cron (worldwide press every run); controls moved above charts; January zero-fill; 14 fixes from 1st adversarial audit; WARN links for all states + per-notice where published; byline; date-sanity cleanup (typo'd 2050 filings) |
| 1.8.0–1.8.2 | Tracker redesign (search, quick views, live-updated pill); sticky count row; "Where the cuts are" AI-share bars; country/industry normalization (canonical "United States", fixed industry taxonomy); full-dataset CSV/JSON exports; daily WARN cron 15:00 UTC |
| 1.7.0–1.7.3 | **Server-side re-architecture**: `wp_alt_layoffs` indexed table; `/query` `/aggregate` `/facets` `/bulk`; front-end fully server-side (scales 100K+ rows); US `state` field; WARN source ('warn' tier, no LLM); nationwide import (per-state subprocess + keyword column parsing) |
| 1.6.x | Cross-outlet dedupe endpoint + fuzzy guard; country merge (US/USA/United States); charts on tracker page; multi-color bars; click-to-filter cross-filtering; reactive stats; auto cache-flush on version bump |
| 1.4–1.5 | Full-width layout (theme 645px cap override); credibility pack (methodology, permalinks, citation box); GDELT backfill source; curated AI seed |
| ≤1.3 | Initial: Railway pipeline (EDGAR+NewsAPI → DeepSeek → WP), CPT + REST + DataTables/Chart.js front-end, exports, RSS, SEO JSON-LD, FTPS auto-deploy |

## Data milestones
- 2026-07-15 (end of day): **34,424 layoffs · 4.8M jobs · 42 US states (37 WARN) · 18 countries**
- 2026-07-15 (morning): **~22,700 layoffs · ~3.1M jobs · 25 US states · 13 countries · 2015→present**
- Worldwide GDELT backfill (2023→now): +53 verified (23 AI-cited); India 106K jobs, UK 73K, +Spain/China
- Nationwide WARN: 25 states via warn-scraper; TX/FL/GA/OH/MI/CO/ID/LA unobtainable (upstream scraper breakage / state sites), IA/MD/MO/NM/OK/OR/SC/WI return no data
- Editorial removals 2026-07-15 (via `/trash`, pre-launch): post 23083 "Coal India 73,800" (a *by-2050 projection*, violates methodology), posts 274 & 23100 (Amazon retrospective summary articles double-counting the Oct-2025 30K and 2022-23 27K cuts)

---

## Incident log (root cause → guard now in place)

| Incident | Root cause | Standing guard |
|---|---|---|
| **The "self-completing" EDGAR history sweep had never swept the recent past, and the SEC collector produced 4 rows in a year while reporting `ok` twice a day** — measured 2026-08-01. `source_type=8K` rows: 219 in 2020, 115 in 2024, **4 in 2025, 8 in 2026**, zero in eleven of the twelve gold-set months. Of 24 gold events scored `matched`, exactly one came from the 8-K itself; the other 23 came from WARN/ERM/news. `ops_status.py` printed ALL CLEAR throughout, because the collector WAS running — it pulled 17-50 candidate documents every run | Not the pagination cap (measured: 0 of 33 misses lost to it; 0% binding on `item 2.05` in all 12 months) and not the LLM (measured: 29 of 33 replay to `accepted`, 28 with the exact stated headcount). `backfill.rotating_window` picked its month with `months[now.toordinal() % len(months)]`, which is not a cycle over an array that gains an entry every calendar month — the newest months sit at the top, precisely where the moving wrap-point jumps past them. **2026-01..2026-06 had NEVER been swept in a 3-year lookback; next due 2027-07.** Since the daily cron only searches a 2-day window, this sweep is the sole path that re-searches a past month, so no search improvement could ever reach the months it would have helped. Separately, `extractor.py` truncated `raw_text` to a bare `2000` while `sources/edgar.py` AND `sources/gdelt.py` both build 3000-char windows on purpose — the tail was cut before the model and before the verbatim count guard, so a headcount stated there was dropped as if invented | `backfill.rotating_month()`: one run in three re-verifies a month from the last twelve, the rest walk the full history, both indexed from the NEWEST end so a new month perturbs ancient history rather than the recent past — still date-keyed, so the once-a-day cadence rule survives. `extractor.RAW_TEXT_LIMIT` is now a named constant covering the largest collector window. Two guards that both fail on the old code: `tests/test_rotating_cron_cadence.py::RotatingWindowReachesRecentMonthsTests` (every month of the last twelve re-verified within 120 days, AND the deep history still walked, so recency priority cannot become recency-only) and `tests/test_extractor_text_budget.py` (the extraction budget is a ceiling over every collector's declared window, and the truncation must use the constant, not a pasted number). `railway/edgar_recall_probe.py` + `edgar-recall-probe.yml` make "which stage dropped this filing?" a dry-run question anyone can re-ask. **The lesson: a backfill that says it self-completes must ASSERT it, or "self-healing" is just a comment** |
| **THE PATTERN, written down as an incident in its own right** — 2026-07-31. Read the rows below together and they are one story told repeatedly: a single row, or a single mis-scoped comparison, moves a number the site publishes as fact, and it is live before anyone notices. RI 98,912 (real 9,891). NJ 2.4 **trillion** jobs. AT&T 78,788, a state TEST notice. Coal India 73,800, a by-2050 projection. Intuit 17 (real ~3,000). Oracle counted twice. Spirit +4,000. Each was caught by a person, or by a tripwire written after the previous one | **Every guard was retrospective.** The four live invariants named four companies, and a fifth company was always unguarded. Worse, the Spirit defect proves magnitude checking is not enough on its own: **every row in it was correct**, and the comparison was wrong — a ±45-day numerator against a six-year denominator. No bound on any number would have seen it, because no number was out of bounds | **Three shape guards, in the same registry, that know no event names** (2.19.233). `headline_concentration` bounds ONE row's share of a published headline, with the numerator and denominator produced by one query pair over one filter set so they cannot describe different populations. `headline_movement` fails a headline that moves when the row population did not. `dedup_denominator_scoped` asserts the reconciler still **cannot compute a sum at all** — its denominator can only come from `alt_dedup_window()`, whose constructor is the window filter, and `alt_dedup_subset_verdict()` throws on anything not window-scoped. In Python the same rule is a type error: `plausibility_ratio()` raises `UnboundedDenominator` on an all-time cumulative denominator. The lesson to keep: **a tripwire named after an event only ever guards the past; guard the SHAPE** |
| **The alerting system depended on the host it was alerting about, and the outage MULTIPLIED the red runs it produced** — 2026-07-31 00:48-00:55 UTC. Bluehost answered 504 for everything under `/blog/` (its second window that day; ~6 min in the afternoon). In the sibling talent tracker, `enrich` failed because it could not reach the host, `drain-writers` correctly went red refusing to auto-retry a failed writer, and then the CI failure alert failed FOUR times: "HTTP 504 from /alert", "CI alert could not be delivered". The alarm was mute at exactly the moment it was most needed. **The outage was found by the owner in a browser** — nothing in either repo watched whether the site serving all of it was reachable | Two faults, and the second is the one worth remembering. (1) `/alert` is a REST route on the same WordPress host every alert is about, so host down = alerting down, with no durable state anywhere: an alert raised during the window existed only in a runner that was about to be discarded. (2) `ci_alert.py` exited **1** on a failed POST, on the reasoning that a notifier failing silently is worse than none. True, but it made a delivery failure indistinguishable from an alerter defect, and it AMPLIFIED: an outage reddens N workflows, each spawns an alert run, each of those fails and goes red too, and a session reading `ops_status` is told the ALERTER is broken when the alerter is working perfectly | **A durable, committed outbox.** `railway/alert_outbox.py` + `railway/alert_outbox.json` (mirrored as `alert_outbox.py` / `data/alert_outbox.json` in the sibling): a POST that fails is retried in-run for transient statuses only, then HELD in a committed file that outlives the runner and the outage, and delivered later by `alert-drain.yml` (30 min here; the sibling's `host-watch.yml` at 15 min). **Holding exits 0** — that is the explicit break in the amplification loop, and the module says so in as many words so nobody restores the `exit 1`. Non-zero survives for exactly one case: could neither deliver NOR hold. A recovery queued behind its own un-sent failure CANCELS both, so an outage that heals never mails a stale RED and a stale RECOVERED. **Something watches the host now:** the sibling's `host-watch.yml` GETs one public REST route every 15 minutes, records `data/host_status.json` (committed only on a change or a 6h heartbeat) and surfaces it in `ops_status [2f]`; three consecutive failed runs is a SUSTAINED outage, which opens **one** GitHub issue — the channel that is not on the host, deduped by construction because editing an issue body emails nobody (2 emails per outage against the ~15 raw run notifications sent for one defect). A down host deliberately does NOT redden that watchdog: a red run there would fire the CI alert, which posts to the down host. Held alerts show in `ops_status [4b]` here |
| **`ops_status.py` reported "ACTION NEEDED: 1 item(s) -> newsapi stale" and said NOTHING about a company being overstated by 4,000 jobs on the live site** — 2026-07-30, while `test_dedup_live::test_spirit_counts_once` was red for the fifth time. The one tool CLAUDE.md tells every session to run FIRST, whose whole job is to say what needs a human, was structurally blind to whether the data was correct | Two independent faults compounding. (1) **ops_status only ever read the source-health ledger**, which answers "did the collectors run?" and cannot answer "is what they produced right?". The live invariants existed but lived only in a test file, surfaced only in CI, and only on `push`/`pull_request` — so on a quiet week nothing ran them at all, even though this data changes *without a commit* (WARN lands daily, reconcile-supersets at 16:40 UTC; the Spirit defect appeared when a running all-time sum crossed a threshold, no code changed). (2) **The single item it DID report was permanent noise.** `newsapi` was retired 2026-07-25 but `news_catchup.py` kept POSTing health under that id every Monday; `alt_retired_sources()` deliberately declines to mask a row whose last run POSTdates the retirement, so the retirement was void, and the id carried a 2-day ceiling while the only surviving job runs WEEKLY — stale 5 days in 7, forever. An alarm that can never be cleared is an alarm nobody reads, and it was the only thing on screen while a wrong number was live | **`railway/data_integrity.py`**: the invariants extracted into one registry that `tests/test_dedup_live.py`, `ops_status.py` [3] and `health_digest.py` all import, so a bound cannot drift between the guard that reddens CI and the dashboard that says all is well. Three states, never two — PASS / FAIL / **UNKNOWN**, and UNKNOWN is never folded into PASS, so ops_status cannot print a clean bill of health it did not verify (`DegradationContract` tests pin this). Exit 2 on a failing check, exit 3 on unverified. New daily `data-integrity.yml` at 17:30 UTC (50 min after reconcile) closes the "only runs on push" gap and writes the verdict to the public health ledger; the weekly digest leads with "WRONG NUMBER LIVE" but is explicitly the BACKSTOP, not the alarm — weekly is up to 7 days too slow for a wrong published number. `news_catchup.py` now reports as `news_catchup` @ 9-day ceiling, `alt_retired_sources()['newsapi']` date moved to 2026-07-30 so the frozen row finally masks, and `test_news_catchup_health::test_never_reports_under_the_retired_newsapi_id` stops it recurring. **Retiring a source is THREE steps: drop it from cron.py, add it to `alt_retired_sources()`, and stop every remaining path that posts health under that id** — step 3 was missed and silently voided step 2 |
| Spirit Airlines US-2026 jumped 7,069 → 11,069 (exactly +4,000, the May-5 news report stacking on the May-2 WARN sites); `test_dedup_live::test_spirit_counts_once` red from the 17:09 reconcile of 2026-07-30 | `alt_reconcile_supersets` pass (1) asked "is there a WARN row within ±45 days" per row, but ran the ≥50% plausibility test — and the marking — against the company's **all-time** WARN sum. That denominator only grows: Spirit's news 4,000 covers 6,109 jobs of May-2026 WARN sites but was measured against 8,922 jobs of Spirit WARN notices back to 2020, so the pair un-matched the day the all-time sum crossed 8,000. Margin had been 38 jobs (4,000 vs 3,961.5). Separately, `in_array($st, ['news','erm','8k',…], true)` never matched EDGAR's `8K`, so **no SEC filing had ever entered the dedup** | 2.19.227 scopes the ≥50% test and both marking directions to the ±45-day window, and folds `source_type` case. The reconcile response now reports `changes` (marks that differ from what is stored) so a silent un-match shows up as churn on a day nothing should move; `detail=1` lists them. Live guard unchanged and bound NOT loosened: `railway/tests/test_dedup_live.py` |
| Public API/page responses carried TWO Cache-Control headers (`public, max-age=300…` + `no-cache, no-store, must-revalidate`) — browsers never cached, `cf-cache-status` looked DYNAMIC on HEAD — found 2026-07-19 | Bluehost's Apache appends the no-store trio AFTER PHP's headers on EVERY PHP response (WP-less direct-file probe + origin-direct curl past Cloudflare/Railway both show it); the v2.2.1 WP-filter fix could never reach it | `.htaccess` override block managed by `includes/htaccess.php` (self-healing, canary-probed, auto-rollback); state in option `alt_htaccess_state`; see RUNBOOK "Duplicate Cache-Control returns" |
| WARN purge-reload silently broke every canonical JOIN (company pages 404d, sitemap shrank 14→6) — found 2026-07-18 | Reload re-imports rows with NEW ids; events kept canonical_layoff_id pointing at the deleted ids | The daily event-migrate pass now repairs dangling canonical pointers (33,813 re-pointed) and flushes caches; verify company pages after any future purge-reload |
| CT WARN collection effectively dead (1 wrong row ever; CVS/Aetna 313 dropped) — found 2026-07-18 | Tier-1 count keyword "affected" matched CT DOL's `affected_company` header, so counts parsed from company NAMES (no digits → 0 → dropped) | "company"/"employer" in `_COUNT_EXCL` + CT-shape regression test; nationwide purge-reload rebuilt the table |
| IL revisions never updated counts (Capital One/Discover Riverwoods: held 215, real 2,027) — found 2026-07-18 | IL IEBS keeps ONE cumulative row per site event and revises in place; parser preferred "Expected Layoff" over "Revised Layoff" | `_count_col` prefers a positive "Revised" figure; regression test with the real IEBS shape |
| Intuit stored as 17 jobs (real ~3,000) | Extractor parsed "17% of its staff" as a headcount | `_percent_only_mention` guard rejects a small count that appears in the text only as "N%" + test; row corrected via /edit with sources retained |
| Oracle double-counted as 50,000 (Feb 20K analyst-forecast row + Apr 30K execution row of the same plan) | Anticipatory analyst coverage ("may lay off up to 30,000", TD Cowen) ingested as an announcement event | Rows merged (all reports retained), converged on the 10-K-grounded net 21,000 with the 20-30K gross range documented in the excerpt; corrections trail entry |
| /add source-attach overwrote an unpinned ERM row's fields (Dow briefly showed 4,500/blank country) — same day | Fuzzy same-company ±30d match routes /add into `alt_db_upsert`, which full-row-UPDATEs unpinned rows (last write wins) | Corrected + row pinned (edited=1); lesson: attach evidence to pinned rows only via /edit, or pin first — recorded in the gap-closure plan |
| RI showed 98,912-worker notice (real: 9,891) | Count parser stripped ALL non-digits: "9,891 … (2 from RI)" → 98912 | `_count` parses FIRST number only; date-shaped values → 0; single-notice cap 100K; weekly anomaly report flags ≥5K notices |
| NJ row parsed as 2.4 **trillion** jobs | Multi-county list "240 (Passaic), 417 (Bergen)…" digit-concatenated | Same first-number fix (→ 240, the lower bound) |
| Visible range said "…– Dec 31, 2050" | State filing typo (also "3030-03-30") | Import window 2015→today+18mo; `/cleanup` NULLs implausible dates |
| Nationwide WARN run imported only 4 states | Single `warn-scraper all` process hit the 30-min timeout (CA alone is 17K rows) | Per-state subprocess with 420s timeout each |
| KY/MI/OH/FL/GA scrapers crashed | Missing `pyquery` dependency | In requirements.txt (TX/FL/GA/OH/MI/CO/ID/LA remain upstream-broken — see RUNBOOK) |
| VT parsed 0 rows | Every state names CSV columns differently | Keyword-based column matching; count-column excludes address/site/county headers |
| Import lost ~1,000 rows, workflow showed GREEN | One `/bulk` batch got an HTTP 500; script only printed it | Importer exits non-zero on ANY failed batch; maintenance curls use `--fail-with-body` |
| Purge could wipe table then scrape fail → EMPTY site (audit-caught before it happened) | Purge ran before scrape | Purge only after scrape succeeds, only with `states=all`, only if ≥5,000 notices scraped |
| Contact page 404 after deploy | Version-gated hook fired MID-FTP-upload (contact.php not landed), never retried | Creation retries until page verified; transient lock vs concurrent-init duplicates |
| Changes deployed but site showed old design | FTP deploys skip WP updater hooks → WP-Super-Cache/Autoptimize never flushed | `alt_flush_caches_on_deploy`: version bump auto-flushes page+asset caches, creates/upgrades the DB table |
| Railway POSTs got 406 | Host ModSecurity blocks `python-requests` UA | Descriptive User-Agent on EVERY request to the WP host |
| Railway POSTs got 403 "Just a moment" | Cloudflare Bot Fight Mode | Owner disabled Bot Fight Mode |
| Pipeline posted to wrong site | `WP_SITE_URL` pointed at apex domain (a separate Railway app) | `/blog` hardcoded in workflows; documented everywhere |
| Amazon ×5 / Intel ×2 duplicate entries inflating totals | Multiple outlets, same event | md5 exact hash + fuzzy same-company-±30d guard + `/dedupe` cluster collapse (WARN exempt) |
| "US/USA/United States" as 3 countries; "IT" vs "Information Technology"; "Global"/"India and US" buckets | Freeform LLM extraction | Normalizers at every entry point + `/cleanup`; "Multiple countries" bucket (no double counting); Trinidad-class "and"-countries whitelisted |
| Cache-Control conflict killed CDN caching | WP core appends `no-cache, no-store` to REST responses | `rest_send_nocache_headers` filtered off for anonymous public GETs (v2.2.1) |
| Charts hid future-dated WARN cuts | Zero-fill capped series at current month | Cap applies to fill only, never below real data |
| Table dead ("No layoffs match") while narrative showed 2,368 — every draw crashed | v2.6.0 announced-badge referenced `row` in the date column render, but the callback signature was `(d, t)`; the ReferenceError was swallowed by the ajax `.catch` | Signature fixed `(d, t, row)` (v2.7.1). Diagnosis pattern for "silent" table failures: wrap `settings.ajax` in the console to capture the real stack — see RUNBOOK |
| Every visitor served a dead 0-byte script for what would have been 24h | Deploy flush deleted Autoptimize aggregates; a request in the regeneration window got a 410 with `max-age=86400`, and **Cloudflare cached the 410** for the exact `?ver=` URL | Deploy no longer deletes AO caches (content-hashed filenames self-invalidate; v2.7.3). Recovery lever if it ever recurs: bump `ALT_VERSION` — new `?ver=` = new CF cache key |
| Deployed 2.18.58 but the page ran old JS/CSS (new headline narrative missing, no console errors) | FTPS uploads the main PHP (new `ALT_VERSION`) before the asset files; a request in that window let Autoptimize aggregate the OLD asset content under the NEW `?ver=` key, and that stale mapping persisted for the whole release | Enqueue versions are `ALT_VERSION.filemtime(asset)` from v2.18.59: the completed upload mints a fresh cache key by itself, so neither the race nor AO cache deletion can recur |
| Page served new `ALT_VERSION` with the previous version's template/JS text (2.18.89) | Reads landed inside the lftp mirror window: the main plugin file (new version string) uploads seconds before templates/assets, so version-marker checks pass while content is still old. Deploy concurrency was NOT the cause (the `plugin-deploy` group already serializes runs) | Verify deployments by CONTENT markers, not the version string; any fresh deploy self-heals. Rapid push trains widen the window — space pushes when possible |
| Cached pages intermittently broken (raw dropdowns, dash cards) during rapid deploy days | Autoptimize re-bundles our single-file assets under content-hash names; cached HTML kept referencing bundles AO had pruned or not yet built | Plugin assets excluded from Autoptimize entirely (v2.18.92) — raw mtime-versioned URLs always resolve; a stale page now loads a stale-but-working script instead of nothing |
| v2.18.92's AO exclusion itself blanked the site (dash cards, raw dropdowns, zero console errors) | Autoptimize defers jQuery/DataTables/Chart.js; the newly AO-excluded layoffs.js had no defer, executed during parse before deferred jQuery existed, and died on its IIFE's first line | AO-excluded scripts enqueue with strategy=defer (v2.18.93) so they run after their deferred dependencies in DOM order. RULE: anything excluded from AO must match AO's defer, and blank-page triage starts with the script tags' defer attributes |

## Audits (multi-agent adversarial reviews — run one after every significant change set)
- **2026-07-29 cross-tracker bug-class sweep + 2026-08-02 launch audit (LOCAL, unpushed as written; commits 93f6e7e + 1b91bd0).** Five bug classes found in the SIBLING talent tracker the same night were re-tested here as CLASSES, not one-offs. Three absent, two present.
  - **DOUBLE RENDER — ABSENT, measured not assumed.** The sibling's block theme ran its shortcode twice, so every `getElementById` bound the first copy and half its controls were a dead twin. Here: 0 duplicate ids across all 9 public pages in raw HTML, and 0 in the LIVE DOM after opening all 25 disclosures and scrolling to the bottom (195 id nodes, 174 bar buttons, 6 canvases, 0 disabled). `shortcodes.php:39` already carries the cross-shortcode guard (`alt_dashboard` defers to `alt_tracker`, duplicate-id reasoning in the comment). **Latent, deliberately NOT fixed:** no shortcode guards against ITSELF. A self-guard is not provably safe without a deploy — if any pre-pass (excerpt, TOC, SEO) renders and discards the first copy, the guard blanks the real one, and the HTML cannot distinguish "rendered once" from "rendered twice, first discarded". Four days before launch that is the wrong trade. Owner call.
  - **EXACT-HOST BLOCKLISTS — ABSENT where it counts, but two real SUBSTRING bugs of the same family, both fixed.** There is no blocklist anywhere; every domain list is an allowlist and the canonical matcher `gdelt.py:688` (`dom == d or dom.endswith("." + d)`, gating all 705 `TRUSTED_DOMAINS` on both the API and BigQuery paths) is correct — `news.crunchbase.com` is even an explicit entry. What was wrong: `process_tips._OFFICIAL_RX` searched the WHOLE URL for `warn|edgar|.gov`, so `warnerbros.com`, `.../warning-signs`, `?q=edgar` and `notreal.com/fake.gov/x` all cleared the gate that feeds AUTO-PUBLISH (proved by running the old regex against each). Now host-only and whole-label, with the non-.gov WARN portals DERIVED from `sources.warn.STATE_WARN_URL` so `test_warn_url_parity.py` guards them too. And `tracker_diff.outlet_suggestions` treated an outlet's first label as a substring of any trusted domain, so `news.example.com` matched `apnews.com`, `ft.co.za` matched `ft.com` — suppression means "already covered", so the bug starved the learning loop the function exists for. **Gotcha for the next session:** win keys are EITHER a host OR an RSS outlet name (`_win_key:273`), so a fix must judge both shapes; a host-only fix breaks `test_tracker_weaning`'s pinned `techcrunch` case, which is what caught the first attempt.
  - **COMMA-SPLIT LOCATION PARSING — ABSENT; the correct guard is already the design.** The sibling split "Peoria, IL" and tried each half as a country code (IL→Israel, CA→Canada, MA→Morocco). Here every 2-letter token is tested against a US-STATE table only, never against country codes (`extractor.py:654`, `api.php:502`); there is no ISO alpha-2 table anywhere; collector `country` values are hardcoded canonical strings. `warn.py:306` even carries an explicit comment not to glue the filing state onto a city that may already contain one. **Latent adjacent risk, not fixed:** `api.php:321` collapses ANY comma in the country field to "Multiple countries", so a writer that ever sends "Cork, Ireland" mislabels a single-country event irreversibly. No current writer does.
  - **NORMALISE-OR-DROP WITH A THIN VOCABULARY — mostly absent by opposite policy; one real instance, fixed.** The rule here is the INVERSE of the sibling's: unknown countries and industries pass through raw (`api.php:324` "never lose data") and there is no city column to fail into (`db.php:3525`). The one closed vocabulary gating a writer (19 industries) fails LOUDLY — rejected ids returned, `RuntimeError` on drift, public `$missing_industry` counter. **The real one:** NV WARN's 50-city vocabulary. The master PDF emits "`<company> <city> <county>`" with no delimiters and pdfplumber glues them, so the county strip's `\s+` found "...Reno" instead of a space, stripped nothing, and the entire line became the employer. **Live on the tracker as "Spirit Airlines Las Vegas/RenoClark/Washoe" on a 999-job closure, row id 173507.** Both strips now tolerate the missing space and read a "/"-joined run as one place. The vocabulary was deliberately NOT expanded — truncating a real employer ("... Enterprise", "... Paradise") is worse and less visible than a blank city — so instead a miss is COUNTED AND PRINTED, which is the actual defect being fixed: the ceiling was silent. **Data correction still owed, and the fix must be PUSHED FIRST or the notice vanishes:** `gh workflow run trash-rows.yml -f ids=173507`, then the daily 9 AM ET NV import re-creates it correctly. `/edit` is the WRONG tool: it rewrites the hash to `md5('edited:'.$old)`, which the fixed parser will never emit, so the next import would insert a second row.
  - **DORMANT CRONS THAT LOOK ARMED — ABSENT. All 63 workflows audited.** Exactly one is dormant (`foreign-filings.yml`, deliberate, retired 2026-07-24) and it is commented out INCLUDING the `schedule:` key, so there is no live-key/dead-child YAML no-op anywhere. 43 active crons, 19 manual-only, 2 push/PR. **What was dishonest was the prose, now fixed:** `warn-import.yml` claimed 11 AM ET for a 9 AM ET cron, a 2-hour error in the file every other job times itself against, which had propagated into `data-quality.yml` and `reconcile-supersets.yml`; `industry-propagate.yml` still introduced itself as weekly; `link-check.yml` said 10 AM for 10:30. Comments only, every schedule verified byte-identical by parsing before and after. **NOT fixed, owner call — three sprint crons still hourly against their own revert instructions:** `edgar-history-sweep` (`20 * * * *`), `historical-news-sweep` (`40 * * * *`), `archive-backfill` (`25 * * * *`). The first two spend LLM tokens per run and their headers still describe a daily window. Same shape as the 2026-07-28 industry-drain cost bug (~$7/day), whose own postmortem records that the "self-limiting when empty" reasoning is FALSE for rows where two passes disagree — precisely the justification these three still rest on.
  - **Launch audit, all clean:** 291→314 tests green the way CI runs them (`python -m unittest discover -s tests -p "test_*.py"`); 0 PHP notices/warnings/fatals on any of 9 public pages; 0 console errors; no sideways scroll at 390px on tracker, sources, health, press or a company page (disclosures forced open); 26/26 internal links 200; 24/24 public REST endpoints 200; all 4 sitemaps + feed + robots.txt + llms.txt 200. Only 2 em-dashes site-wide, both unavoidable (one inside a verbatim employer quote, one inside Kentucky's real .gov URL). No placeholder or TODO copy. `?states=NV` is silently ignored while `?state=NV` works — the plural is simply not a parameter; noted, not a defect. **Version: live serves 2.19.221 while the repo is at 2.19.224**, correct because the design-port commits are unpushed. No plugin file touched by this audit, so no bump and nothing to deploy.
- **2026-07-24/25 pre-launch hardening sweep (8 agents: adversarial data-integrity, page/number, dormant-source code-dive, discovery-recall, coverage-gap, security, API/validation, front-end).** Findings + fixes, all shipped v2.19.179→188 unless noted:
  - **Discovery was starved:** NewsAPI returned 0 while reporting "ok" (dead/free-tier); it was masking the primary AI channel. Fix: `newsapi.py` records `last_error`; `cron.py` degrades on error/0-pull. NEW FREE source **`sources/google_news.py`** (Google News RSS, no key — headlines carry the headcount even behind paywalls; live-tested, catches Oracle 21K/Uber/Amazon that GDELT missed) now leads the cron news sweep + feeds `tracker_diff`'s chase.
  - **Recall alarm:** `tracker_diff` now computes full-list recall each run and EMAILS the owner the missing companies below 90% (measured recall was 14.6% before google_news). Names go only to the owner inbox, never repo/health/logs.
  - **The ~5% double-count (news company-wide total summed on top of its WARN sites):** fixed via the **superset dedup model** — `superset_of` column + `alt_reconcile_supersets()` + key-gated `/reconcile-supersets` (dry-run default, `apply=1` writes) + `reconcile-supersets.yml`. Aggregate job-SUMs use `$where_dd` (`superset_of=0`); NOT the row list / repeat-frequency view. US-2026 461,648→**435,627**; all-time 20.23M→20.08M. Reversible (unmark). See [[superset-dedup-model]] memory.
  - **Biggest fake outlier:** AT&T "78,788" was a FL WARN **test/sandbox notice W-1511** (one WARN# faking AT&T+BOEING+"BOEING test"). `fetch_fl` now quarantines a whole poisoned WarnNo; the 4 rows trashed+suppressed via NEW **`trash-rows.yml`** (delete+suppress). Ghost row #70923 (wiped-meta) also trashed.
  - **Health page was BRICKED** (stuck "Loading…"): the real cause was `safeGet(null)`→`get(null)` throwing SYNCHRONOUSLY in the `.map()` before `Promise.all` (a null placeholder slot); the prior "fix" (8bf8caf, a timeout) couldn't catch a sync throw. Real fix: `safeGet` short-circuits null. Also fixed: repeat-companies labeled Amazon as "Twitch" (`MAX(company)`→company-directory `display_name`); /ai-quotes missing scope label; industry taxonomy typo "Adminstrative"+8 non-canonical NACE buckets folded into the 19 (api.php `alt_industry_rules` + `/cleanup`).
  - **Wayback transparency:** never-give-up (weekly re-check of `unavailable`), and every row shows an archive link OR a dated "archive pending, re-checked weekly (last checked …)" disclaimer (`archive_status`+`archive_checked_at` on /query rows).
  - **Reliability/ops:** company-watchlist (30→55) + distress (25→35) timeouts raised (were cancelled). Retired the 3 dead Asian feeds (EDINET/OpenDART/CVM — 0 rows ever; probes gated behind `RUN_DISCOVERY_PROBES`, foreign-filings schedule disabled). See [[api-keys-already-configured]].
  - **Security:** clean (no critical/high). L1 fixed (secret NAMES + repo paths removed from public Health page). L2 fixed (per-IP export throttle). L3 pending (subscribe nonce — low, captcha-gated).
  - **Claims backdrop (macro context) — DATA LIVE:** keyless FRED puller `sources/claims.py` (national ICSA/CCSA SA + 51 states NSA) + `claims_import.py` + `claims-import.yml` → keyed `/claims-ingest` → public `/claims`. Labeled context, NEVER summed into layoff counts. **Front-end chart overlay (bars behind the layoff line + map toggle) NOT yet built — the one real feature remaining.**
  - **STILL PENDING** (for the next session): the claims front-end overlay; announced-vs-documented ROW-DETAIL display (the totals are already deduped, this is presentation); Tyson-style within-WARN duplicate dedup + tripwire; generic-tier state WARN drift monitor (only CA is monitored, `warn_import.py`); security L3; a regression test for `alt_reconcile_supersets`. Minor data nits: news rows placeholder-dated 2027-12-31; invalid `years=` filter returns all rows (db.php `int_in`).

- **2026-07-23 adversarial source-verification audit #1** (fresh-model auditor, 60 rows, seed 20260723, stratified 2025/2026 x warn/news/erm/8K from a 7,810-row pool; sample+pool JSONs preserved in session scratchpad): every sampled row's source_url opened and the company/count/date verified against it. **REVISED AFTER RE-VERIFICATION: strict 57/60 = 95.0%; fair (excluding 2 register-access limitations) 57/58 = 98.3%; structured sources 42/42 PERFECT (WARN 28/28 on data, SEC 4/4, ERM 10/10).** The auditor reported 2 failures; re-verification refuted one. id 61382 Dow (3,700 vs the CBS headline 4,500) is RIGHT: the row's own excerpt documents it as the net-new portion, and Eurofound factsheet 204559 independently records the event as "3,700 - 4,500 jobs ... 4,500 globally, with already 800 jobs being cut in Germany and the UK" - that 800 is retained separately as id 61702, so 3,700 IS the documented floor and "correcting" it to 4,500 would have created an 800-job double-count. LESSON (the important one): a deliberately reconciled net-new row LOOKS like a wrong number to any outside auditor reading only the headline figure, so (a) the audit protocol must weigh a row's reconciliation note before grading, and (b) a human must independently re-verify every proposed numeric change before applying it - applying this one blind would have corrupted the data. The one REAL failure: id 70289 Starbucks 1,000 pinned to the Apr-2026 tech-team event whose own source says the count is unconfirmed (the ~1,000 belongs to a PRIOR retail event) - UNVERIFIABLE. APPLIED 2026-07-23 with owner sign-off: id 70289 trashed through the new dispatch-only corrections path (railway/apply_correction.py + .github/workflows/apply-correction.yml - reason required, dry-run by default, fails loudly on any not_found/rejected id), dedup hash suppressed so the nightly re-scrape cannot resurrect it, and disclosed at the TOP of the public corrections log within the hour. Dow: NO CHANGE, verified correct. **Systemic findings:** (1) BIGGEST exposure is rolling-register link rot, ~25/60 rows - CA links warn_report1.xlsx which holds only the current FY (all pre-FY26-27 CA links rolled over July 1), MD/NJ/FL/IL same shape; data verified true in the states' archived editions, but a journalist clicking the stored link cannot find the row -> spawned follow-up to make stored links year-stable. (2) Qualifier flattening in news counts ("up to 600"/"nearly 4,000" stored as bare numbers) - PASS by the letter, ceilings-not-floors by the spirit; floors handled correctly elsewhere. (3) Metadata nits: id 134375 raw HTML in company_name (WI scrape artifact), id 70233 source_name/host mismatch. Protocol: re-run quarterly with a fresh seed; the 98.3%/42-of-42-structured result is now published in the on-page FAQ ("How do you check your own accuracy?") alongside an explicit ceiling-qualifier disclosure, and is the publishable credibility claim, and the failure list is the to-do. |
- **2026-07-19 historical-year backfill #1 (2025)** (8 web-research agents, quarterly + federal/DOGE + retail-bankruptcy + healthcare/media + tech/AI slices; protocol per QUALITY_ROADMAP_HANDOVER "Historical-year backfill"): ~120 of 2025's largest events verified at named outlets and checked against /query. Headline finding: the 726,686 US total contained ~152K of double counting — UPS Oct-28 48K disclosure counted twice (one row extracted from announcement-survey-roundup coverage) with the Apr 20K stage row also counted; IRS 20K same-day pair; HHS Mar-27 10K RIF ×4 plus FDA/"US health agency" sub-slices of its own announced breakdown; Microsoft May 6K inside the Jul 15K year-program row; Intel Mar-2025 "15,000" sourced to litigation coverage of the Aug-2024 program (merged into the 2024 keeper with its Dec-2024 newsletter dup); Salesforce Jan-1 phantom (Fortune 2026 retrospective); Meta Feb misextraction ("fires 20 employees" article → 3,000); Recruit/Indeed 1,300 ×3; State (1,800/1,300) and Education (Mar RIF re-reported at the Jul SCOTUS date) pairs; CDC 1,300 + Education 460 shutdown slices inside the 4,200 cross-agency Oct RIF row; NOAA probationary fragments; Telefónica news dup of the ERM record. 13 merge groups + 5 conservative-count edits (Amazon 30K→employer-confirmed 14K; Target 1,800→1,000 actual notices; GM 1,200→1,750 announced; Blue Origin 100→1,400; Nissan 20K cumulative→11K increment) via data-corrections runs 29704486337/29704678654 — all duplicate evidence retained as source reports on keeper events. Seeded 34 verified missing announcement-stage events (+97,582 US / +128,127 worldwide): Rite Aid 24,500, Joann 19,000, VA 30,000 (official Jul-7 release; attrition/DRP composition quoted verbatim), SSA 7,000, USAID 1,600, Chevron 6,830, P&G 7,000, Booz Allen 2,500, Paramount 2,000, Synopsys 2,000, Citigroup-China 3,500, ConocoPhillips 2,600, HPE 2,500, Microchip 2,000 + 20 more (runs 29704698202/29704813873, all 201). 14 AI reclassifications (run 29704879762): 11 employer-verbatim upgrades (Salesforce→primary "that's the agentic layer speaking to the customers"; Chegg May+Oct→primary; Amazon, Accenture, CrowdStrike, Recruit/Indeed, Fiverr, Workday, HP, Lufthansa→contributing) and 3 downgrades to ai_linked (Microsoft 15K, Meta-600, IBM — the employers' own statements cite no AI). Net US 2025: 726,686 → **670,658 (55.6% of the announcement survey's 1,206,374 — down from the inflated 60%)**; ai_broad 128,759 (235% of the announcement survey's AI figure) → **52,259 (95%)**. Structural finding: ~250–300K of the announcement survey's 2025 total is voluntary federal separations (75K deferred-resignation acceptances — deliberately NOT seeded because those acceptances are already inside agency totals like VA's 30K — plus attrition-heavy programs), so 90% is not honestly reachable; the residual gap is a documented composition difference plus mid-tail coverage, not a processing defect. Documented skips: Forever 21 700 (WARN rows cover 494 of it), RTI 525/FHI-360 483 (news reports of the same WARN filings), Penn Medicine 300 (vacant-heavy), IBM count edit ("thousands" with no stated floor), Oracle US Aug wave (insider-only "low thousands"; WARN+ERM cover the floors), IRS Feb 6,700 probationary (inside the existing Apr 20K program row), ERM-vs-US-news group overlaps (Intel 24.5K ERM Apr, Microsoft 9K ERM Jul, TCS 12K/19.8K) per the Telia/Nissan precedent. PENDING owner action (trash-entries dispatch was permission-blocked in-session): remove phantom rows 70461 (Meta "8,000" = lawsuit allegation inside a Fortune macro roundup, AI-flagged), 70769 ("US federal government 5,000" = Benzinga commentary on the Nov BLS drop), 70083 (DOGE 10,000 cross-agency aggregate double-counting VA/NOAA/IRS rows) → a further −23,000 honesty correction.
- **2026-07-19 work-backwards audit #1** (8 web-research agents, 91 major 2026 events checked against the live API): 25 missing, 9 present-but-unflagged-AI, 15 count-differs. Root cause was NOT the extractor: WARN reliably captured execution slices (Cisco 471 of 4,000; LinkedIn 606 of 875; Workday 154 of 400; WaPo 324 of ~350; Takeda 247 of 4,500) while the ANNOUNCEMENT-level corporate events — what the announcement survey and sector trackers count — were missing, because GDELT query phrasing favors "layoff" language over earnings-call "restructuring/job cuts" framing and several trade outlets (insurance, gaming) were off the allowlist. Seeded 21 announcement events (AI flag only where the employer explicitly cited AI), reclassified Playtika + ING to contributing_cause with employer quotes. Documented skips: IBM/Google rolling estimates, Alibaba headcount-reduction-not-layoffs, VW 100K sourced rumor, TCS retrospective total, Telia/Nissan group figures overlapping ERM slices, Bungie "reportedly". KNOWN-GAP CLAIM CORRECTED 2026-07-19: Oregon IS collected and our rows faithfully mirror the state's own export — Oregon's official WARN list anonymizes some employers as facility/street names ('Century Blvd., Hillsboro' = Intel Ronler Acres), so employer attribution is impossible without inference we refuse to do. The Intel program itself is fully counted via the national news events (5,000 Jul 2025; 15,500 Aug 2025) plus CA/TX/AZ WARN slices; the 'missing 2,392' was inside those figures and its 2026 dating came from a weak source (day-of-week math proves July 2025). No Oregon build needed. Protocol: re-run this audit monthly; it is the practical "work backwards from the aggregators" loop.
- **2026-07-15 super test #3** (51 agents, 7 suites + adversarial verify): 16 confirmed / 6 refuted. Standouts: Florida's own WARN export contains staff TEST rows (fake AT&T 78,788 topped the tracker — parser was faithful, source was dirty); 99 news/SEC rows had no country (38K jobs incl. Oracle 30K invisible to region tabs); Ideal US Talent company-wide total under RI; FL source page moved (2,612 dead links); zero-date row from "2026-03-32"; sources=news silently 0; stale worked example (−83%). All fixed same day (v2.8.0–2.8.2 + edit/trash workflows). Refuted claims (don't re-flag): /stats "two data stores" (definitional), announced tier all-zero (expected, just launched), Technology-2026 undercount (WARN rows carry no industry — documented).
- **2026-07-14 audit #1** (v1.8.x diff): 16 confirmed findings (country-delimiter dead code, industry 'tech' swallowing biotech/fintech, search surviving Reset, CSV formula gap, admin-bar offsets, silent workflow failures…) — all fixed in v1.9.1.
- **2026-07-15 audit #2** (v1.9.3–v2.1.2 diff): 24 confirmed (4 HIGH: purge-before-scrape, purge+partial-states, date-shaped counts, future-data chart drop) — HIGHs + quick wins fixed in v2.2.1; accepted-risk items documented in RUNBOOK.
- **2026-07-15 live pre-ingest test** (5 suites): filters 38/38 checks over 2,133 validated rows ✓; exports byte-perfect (22,691 = CSV = JSON = API) ✓; all 27 state links live ✓; found Coal India/Amazon editorial removals; measured WARN link precision (~98% state-list pages — inherent, labeled "(list)" in UI); perf: 1.2s WP-bootstrap floor per API hit, ~8 req/s origin ceiling, page HTML cached at 0.4s.

## Infrastructure changes by the owner (outside this repo)
- 2026-07-14: Cloudflare Bot Fight Mode OFF (was blocking the pipeline)
- 2026-07-15: Cloudflare Cache Rule added for `/blog/wp-json/layoffs/v1/*` GETs. ⚠ Set **Browser TTL = Respect origin** (a 5-day browser TTL was initially observed) and Edge TTL ≈ 5 min.
