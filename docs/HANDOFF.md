# Session handoff baton

Gated coordination so **cloud and local sessions never collide** on this repo
(we hit real git conflicts + version-bump races running two at once). Exactly
**one session holds the baton at a time**. `ops_status.py` prints the current
holder, so the start-of-session ritual surfaces it automatically.

## Baton
- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.111.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is.
  Main was RED and this is the fix: `page-company-index.php` (new at 2.20.110)
  declared `alt_company_index_strip()` unguarded, and a template renders more
  than once per request, so a second `function` statement is a FATAL rather than
  a warning. It is now wrapped in `if (!function_exists(...))`, which is what
  `tests/test_no_unguarded_template_functions.py` has always required. Plugin
  files touched: `templates/page-company-index.php`, `ai-layoff-tracker.php`
  (version only). **No data was touched. Next plugin release is 2.20.112.**

- **NO VERSION CLAIMED BY A SIDE SESSION (2026-08-19): operational mail moved to
  Resend.** The baton was read as HELD by `local` and is NOT claimed here.
  **No plugin file was touched and no version was consumed** - the change is
  Python and workflows only, so `reader_freshness.py` has nothing to verify.
  CI alerts, the RECOVERED notices, the weekly health digest and the CI noise
  report now send through `railway/opsmail.py` (Resend, `RESEND_API_KEY`)
  instead of `/wp-json/layoffs/v1/alert`, so the alarm no longer depends on the
  host it monitors. The open/resolved ledger moved with it, from the
  `alt_ci_alert_state` WordPress option into the committed
  `railway/alert_state.json`, and **the claim is committed before the send** so
  the dedup guarantee did not pay for the move. **The subscriber digest is
  untouched**: `digest-send.yml` still selects `DIGEST_TRANSPORT: smtp` (Brevo)
  and `digest_transport.py` was not edited. The `/alert` route itself is still
  deployed and still used by `link_check.py`, `process_tips.py`,
  `openrouter_balance_check.py`, `tracker_diff.py`, `curated_probe.py`,
  `daily_classification_spotcheck.py` and `source_verification_audit.py`; those
  were out of scope and can move the same way later.
- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.109.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. **TWO COLLISIONS: main took 2.20.107 and then
  2.20.108 while this was staged, both caught by re-reading main immediately
  before merging. Merged onto it each time, so the sibling sessions'
  tracking-disclosure constant and SEO diagnostics are untouched.** The change adds the **public edition
  archive**: every digest that goes out is kept forever at
  `/ai-layoff-tracker/editions/<tier>/<slug>/`, so a figure that used to exist
  only in an inbox can be cited. NEW files: `includes/digest-archive.php`,
  `templates/page-editions.php`, plus the test and its harness. Touched, and
  deliberately by four lines only because several sessions are live in them:
  `includes/subscribe.php` (capture + publish call sites, one lead sentence, one
  archive link in the signup form), `includes/digest-api.php` (capture + publish
  call sites), `includes/subscribe-placements.php` (one context name),
  `ai-layoff-tracker.php` (guarded require + version). **The per-tier send
  guards, the send-state columns and `digest_transport` are untouched.** ONE new
  table, `wp_alt_digest_editions`, self-installing. Weekly editions are
  indexable and daily ones are `noindex`, from one setting. **Next plugin
  release is 2.20.110.**
- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.110.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. **TWO COLLISIONS: this was staged as
  2.20.106, main was at 2.20.107 by the first re-read, and at 2.20.109 by the
  second** - both caught by re-reading main immediately before pushing, which is
  the step this file asks for and the only reason neither collided. Rebased to
  2.20.110. The first re-read also showed a
  sibling session had already removed the "in order to" from
  `page-methodology.php`, so that edit was dropped rather than reapplied.

  The change is the **employer browse index**, and it exists because of a
  measurement rather than a hunch. Measured live this session: the company
  sitemap offers 7,500 indexable employer pages; crawling all 103 facet pages
  and collecting every `/company-layoffs/` link they carry found 3,575 distinct
  employer pages linked, of which only **1,539** are pages the sitemap offers.
  So **5,961 of the 7,500 (79.5%) were reachable from a sitemap and from
  nothing else on this site**, and the tracker page, where readers actually
  land, linked to **zero** of them. The facet mesh got this exact fix at
  2.19.243 and the employer set never did.

  New files: `includes/company-index.php` (hub at `/company-layoffs/`, A-Z
  letter pages at `/company-layoffs/browse/<letter>/`) and
  `templates/page-company-index.php`. Plugin files touched:
  `templates/page-tracker.php` (an A-Z block inside the existing "Browse the
  record" section), `templates/page-facet.php` and
  `templates/page-company-directory.php` (a link to the hub),
  `includes/company-directory.php` (one `alt_company_sitemap_urls` filter, so
  the hub joins the company sitemap without entering the published
  `pages_indexable` coverage figure), `assets/layoffs.css`,
  `ai-layoff-tracker.php` (version + a **guarded** `is_readable` require, since
  a hard require of a brand-new include fatals the whole plugin mid-FTPS).
  Rest is TECHLOG.

  **Only the hub is indexable; the 27 letter pages are `noindex, follow`** on
  the same reasoning that keeps weekly report pulses and sub-floor company
  pages out. **No row was edited, no data changed, and no page was removed.**
  The goal is NOT more indexed pages: GSC shows 2,782 already indexed producing
  ~34 clicks in ten weeks, so this is a reader and crawler path to pages that
  already exist.

  **KNOWN GAP left for the owner:** `templates/page-company-index.php` is
  reader-facing copy the style gate does not score, because `LAYOFF_TARGETS`
  lives in the SHA-pinned `railway/style_check.py` that must stay byte-identical
  with the sibling repo. It was measured by hand once with the target
  temporarily added (grade 9.6, zero findings) but is not continuously
  enforced. Closing it needs the cross-repo ritual.
  **Next plugin release is 2.20.111.**
  Written here before the push, and main re-read immediately before merging,
  per the 2.20.92 collision note below.

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.107.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. Branched from `origin/main` at 2.20.106 and
  rebased onto it before pushing, so the sibling session's
  `alt_digest_subject_line` work is untouched. The change makes the **tracking
  disclosure derive from one constant** instead of four hand-typed claims:
  `RELAY_TRACKING_ON` (`railway/digest_layout.py`) and its PHP twin
  `ALT_RELAY_TRACKING` (`includes/subscribe.php`), with a test pinning the two
  together. **Both still say ON and no published claim changed**, because the
  owner has not flipped the Brevo dashboard yet and the copy must not lead the
  setting. Plugin files touched: `includes/subscribe.php`,
  `ai-layoff-tracker.php` (version only). Rest is `railway/digest_layout.py`,
  `railway/digest_transport.py`, three digest test modules, RUNBOOK and this
  file. **The headline finding is that Brevo has no opens-off, clicks-on lever
  at all** (no setting, no plan, no SMTP header), and that turning its tracking
  off entirely costs zero click data, because every click figure comes from our
  own first-party counter and never from Brevo. One live falsehood was fixed on
  the way: `/subscriber-stats` had reported `open_tracking=none` since
  2026-08-16. RUNBOOK "Open and click tracking" holds the flip procedure, the
  evidence and the consent design note. **Next plugin release is 2.20.108.**

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.110.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change makes the 404 log and the
  redirect table READABLE from outside wp-admin, because a session asked to
  find the leak in 417 dead hits and 2,000 redirect hits could see neither and
  was guessing against a screenshot. Claimed 2.20.107, found a sibling
  session had landed that same number on main, and rebased to 2.20.108. Plugin files touched:
  `includes/seo-diagnostics.php` (new, two keyed GET routes, read-only, no
  visitor IP returned, a missing table reports TABLE_MISSING at HTTP 503 rather
  than an empty list) and `ai-layoff-tracker.php` (the guarded require plus the
  version). Rest is `.github/workflows/seo-diagnostics.yml`, manual dispatch
  only. **No live row was edited, no redirect was created and no log was
  cleared.** **Next plugin release is 2.20.111.**

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.106.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change is one banned-jargon fix that
  `railway/style_check.py` was failing on at origin/main, unrelated to any
  in-flight work: the `#m-ai` AI-skills-swap sentence used "in order to", and it
  now reads "Cuts made to hire people with stronger AI skills do not earn the
  strict tag either." The phrase is USED there, not quoted, so the replacement
  is the fix rather than quotation marks. Meaning is unchanged. Plugin files
  touched: `templates/page-methodology.php` (that one phrase) and
  `ai-layoff-tracker.php` (version only). No data, no ruling, no live row.
  **Next plugin release is 2.20.107.** Written here before the push, and main
  re-read immediately before merging, per the 2.20.92 collision note below.

- **NO VERSION CONSUMED BY A SIDE SESSION (2026-08-19): the six speaker rows are
  confirmed and five live rows were corrected.** The baton was read as HELD by
  `local` and is NOT claimed here. **No plugin file was touched and no version was
  consumed** - the change is the `ai-causation-2026-08` adjudications/goldset/
  recommendations/review, `railway/tests/test_adjudication_parking.py` and TECHLOG.
  **No version claimed. Main was at 2.20.105 when this was staged (a sibling
  session landed the digest subject fix while this ran), so the next plugin
  release is 2.20.106 and this change does not move it.**
  The owner deferred one narrow ruling: the mechanical application of his own
  speaker rule (2.20.102) to the six rows he had already seen. All six re-read
  against `#m-ai` before confirming, all six hold, no disagreement with the prior
  session. Gold coverage 194 -> **200 of 200, nothing parked**.
  **THE VERDICT ON THE 2026-08-07 SWAP IS STILL UNKNOWN**, but it is now a SETTLED
  unknown rather than a blocked one: adjudication is complete, and the incumbent and
  the candidate are level on the only unrigged measure (87.5% vs 88.0% referee
  agreement) with every interval wide and overlapping. Do not round it to a pass and
  do not move a production model on it.
  **THIS PUBLISHED.** Five rows corrected via `apply-correction.yml` (dry run, then
  apply) to `ai_explicit=0` / `ai_causation=ai_linked`: 70653 TikTok 439, 54973
  Microsoft 50, 48830 Suncor 400, 70683 ByteDance 500, 107375 General Motors 600.
  Strict AI **203,858 -> 201,869 jobs, 96 -> 91 entries**; `ai_broad_jobs` unchanged
  at 232,573. `headline_movement` PASSED (-1,989 against a floor of 8,000), so **no
  sticky incident opened and no closure package is needed**.
  **TWO THINGS LEFT FOR THE OWNER.** (1) **70293 Snap was NOT corrected**, on
  purpose: its gold label is right on the stored snippet, but the live row's
  `ai_language` is an Evan Spiegel memo quote, so an employer DID speak and the
  speaker rule does not mechanically condemn it. Its real defect is a missing
  receipt (quote absent from its own source text), which resolves to `unknown`, not
  `false`. (2) The five corrected rows still carry the `ai_automation` reason tag,
  which `#m-ai` defines on the same speaker line as the strict tile, so tag and tile
  now disagree; `possible_ai` is the press-linked tag. Probably a sweep, not five
  rows. Neither was authorised, so neither was done.

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.104.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change writes the owner's **AI-skills-swap
  ruling** into the one place a reader can check it: cuts made in order to hire
  people with stronger AI skills do not earn the strict tag, because the test is
  whether the work went away or the required skill changed. Row 107375 (General
  Motors) is `false`. Plugin files touched: `templates/page-methodology.php` (four
  sentences added to `#m-ai`, beside the speaker rule from 2.20.102) and
  `ai-layoff-tracker.php` (version only). Rest is the `ai-causation-2026-08`
  adjudications/goldset/review/recommendations and TECHLOG. **No live row was
  edited and nothing is queued**, though GM is stored live as `ai_explicit=1`, so
  the stored-value disagreement list is now eleven rows rather than ten. **The six
  parked speaker rows stay parked; the harness verdict on the 2026-08-07 swap is
  still UNKNOWN.** **Next plugin release is 2.20.105.**

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.102.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change writes the owner's **speaker
  ruling** into the one place a reader can check it: `ai_explicit` requires THE
  EMPLOYER to have attributed the cuts to AI, and a press characterisation
  without the employer saying it is the broad tier. Plugin files touched:
  `templates/page-methodology.php` (the `#m-ai` rule and the reason-tag
  paragraph that said the tiers differ without saying how),
  `includes/cpt.php` (the `alt_allowed_ai_causation()` comment, which read as
  if a sufficiently explicit press attribution could earn the strict tag),
  `ai-layoff-tracker.php` (version only). Rest is `railway/extractor.py` (both
  prompt sites), the `ai-causation-2026-08` adjudications/goldset/review/
  recommendations, and TECHLOG. **No live row was edited and nothing is
  queued.** **Next plugin release is 2.20.103.**

- **CLOSED BY A SIDE SESSION (2026-08-19): the `us_all_time` containment
  incident.** The baton was read as HELD by `local` and is NOT claimed here.
  **No plugin file was touched and no version was consumed** — the change is
  `railway/headline_incidents.json`, `railway/headline_baseline.json` (both
  written only by `--close-incident`, never by hand) and the reviewer name in
  `railway/close_us_all_time_2026-08-19.sh`, plus TECHLOG. The verdict: the
  -34,303 complement move is CORRECT behaviour, the 28 `employer_country` fills
  from PR #112 carrying 75,893 jobs, re-measured live in this session rather
  than taken from the package. The pair now reads UNKNOWN until the next
  `data-integrity.yml` run advances the containment group together — that is by
  design after any close, not a new failure.

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.99.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change closes the FAILING
  `figures_agree_across_surfaces` invariant. **Neither published figure was
  wrong and nothing was cached**: the home hero (524,905) is the calendar year
  on the FILING basis, which it has headlined since 2.20.4, and the press
  headline (522,255) is the to-date figure on the EFFECTIVE basis, which that
  page counts on by design. What was wrong was one sentence: the press page's
  period table asserted that its 558,253 was "the figure the tracker home page
  headlines", and that stopped being true on 2026-08-10 and was off by 33,348.
  The press page now READS the home figure rather than remembering it, states
  both bases side by side, and stamps them machine-readably; the invariant now
  verifies each surface against the API on ITS OWN stamped basis instead of
  applying the home page's basis to both. Plugin files touched:
  `templates/page-press.php`, `includes/db.php`, `ai-layoff-tracker.php`
  (version only). Rest is `railway/published_figures.py`,
  `railway/tests/test_published_figure_guards.py`, TECHLOG.
  **A SECOND RELEASE FOLLOWED IN THE SAME SESSION, AND THE VERSION MOVED
  TWICE.** The stamp shipped at 2.20.99 as an inline `<script>`; this host
  rewrites those into a base64 `data:` URI, so it was on the page, correct, and
  unreadable, and an element carrier was added beside it (same shape as the
  build stamp at 2.20.38). That follow-up claimed **2.20.100** and a sibling
  session landed a different 2.20.100 on main inside the same twenty minutes -
  caught by re-reading main immediately before merging, which is the step this
  file asks for and the only reason it did not collide. Rebased to
  **2.20.101**. **Next plugin release is 2.20.102.**

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-18): 2.20.97.** The baton was
  read as HELD and is NOT claimed here; only the version number is, which is
  what this file asks for. The change is the **citation affordance a machine can
  read**: the tracker page's "Cite this tracker" box filled its access date from
  JavaScript, so every crawler and answer engine read "Accessed ." and no URL at
  all; and the ~7,600 durable landing pages (company, country, US state, city,
  industry) carried no citation affordance whatsoever. Plugin files touched:
  `ai-layoff-tracker.php` (new `alt_cite_line`/`alt_cite_box_html`),
  `templates/page-tracker.php`, `templates/page-facet.php`,
  `templates/page-company-directory.php`. The 375px wrap fix for the new citation block followed as **2.20.98** (`assets/layoffs.css`): a company slug can run to 90 characters and a flex item defaults to `min-width:auto`, so the URL bled horizontally. **Next plugin release is 2.20.99.**
  Written here and pushed within minutes, per the 2.20.92 collision note below.

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-19): 2.20.103.** The baton was
  read as HELD by `local` and is NOT claimed here; only the version number is,
  which is what this file asks for. The change is the **weekly digest rebuilt
  as an edition**: the owner read a live send and said the whole newsletter was
  confusing. ISO-8601 weeks (Monday to Sunday, `%G-W%V`), the weekly window
  moved from a rolling seven days ending today to the PREVIOUS COMPLETE ISO
  week, two labelled headline figures (United States and worldwide, both strict
  job-location), a derived lead with a week-on-week direction, the AI figure
  promoted with a detection-power line, regional grouping, and every ranked row
  linked to a tracker view carrying `date_basis` explicitly. Plugin files
  touched: `includes/subscribe.php`, `includes/digest-api.php`,
  `ai-layoff-tracker.php` (version only). Rest is `railway/digest_layout.py`,
  `railway/digest_send.py`, digest tests, TECHLOG. **A SIBLING SESSION TOOK 2.20.102 while
  this one was working**, caught by re-reading main immediately before merging,
  which is the step this file asks for and the only reason it did not collide.
  Rebased to **2.20.103**. **A FOLLOW-UP SHIPPED IN THE SAME SESSION AS 2.20.105**: the subject line of
  2.20.103 read "AI Layoff Tracker: 16,842 verified cuts this week" on a week
  whose AI figure was zero, which inflated the product's own metric on its most
  quoted surface. Every subject now leads with the SITE
  (`AskTheRecruiter.com · 2026 Week 33: ...`), so no brand is juxtaposed with a
  raw count, and `railway/tests/test_digest_subject_never_inflates_ai.py` holds
  the property. **A SECOND COLLISION: main was already at 2.20.104 when this was staged, caught by re-reading main immediately before merging. Rebased to 2.20.105. Next plugin release is 2.20.106.** Written here before the push, and main re-read immediately before
  merging, per the 2.20.92 collision note below.

- **STATUS:** HELD
- **HOLDER:** local
- **SINCE:** 2026-08-12
- **WORKING ON (current subject, 2026-08-18, LATEST):** the two non-US
  collective-dismissal registers, landing as **2.20.94**, with a page-cache flush as **2.20.95**
  (`railway/sources/wup_mazowieckie.py`, `railway/sources/quebec.py`,
  `railway/warn_import.py`, `.github/workflows/warn-import.yml`,
  `templates/page-methodology.php`, `templates/page-sources.php`,
  `railway/tests/test_wup_mazowieckie_parse.py`, TECHLOG). The brief was to
  BUILD Quebec and Mazovia; both have been live since 2.19.112 / 2.19.136, so
  this is what the audit found instead. Mazovia was returning **3 of the 11
  notices** its listing page was serving - a capital letter in the legal-form
  anchor cost all of February, three unread deadline phrasings cost all of June,
  and June's largest notice has no legal form at all. Each post states its own
  total, so the run now audits against it (384 of 384). Quebec: all 142 live
  rows cited the publications INDEX rather than the month's PDF, and the
  ministry's four caveats - intention, not completion; cancelled layoffs never
  removed; snapshot never revised - reached no reader. Both are now on the row
  and in a new methodology section. Neither touches `dedup_hash`, so `/bulk`
  field-updates in place. **The Quebec archive backfill is dispatched
  separately** (`quebec_months=40`): measured at 1,318 notices / 48,391 jobs
  from 36 PDFs back to 2023-08, against 142 rows live today.

- **WORKING ON (current subject, 2026-08-19, LATEST):** the email digest's
  dates, places and citation, landing as **2.20.93**
  (`includes/subscribe.php`, `railway/tests/fixtures/digest_compose_harness.php`,
  `railway/tests/test_digest_scope_rules.py`,
  `railway/tests/test_digest_subscription.py`, TECHLOG). The owner's four
  complaints: the send date in the subject (already done, verified here), YTD
  2026 (already done), "dates, locations, countries" (NOT done - the window
  label was being dropped after prepositions, a second date format was in the
  biggest-cuts table, and the place column printed the bare postal code), and
  "Cite this - broken" (markup was fixed, content was not: a third date format
  and no clock on the access date). **THE VERSION COLLIDED ANYWAY.** This claimed 2.20.92 here and pushed,
  and a sibling session landed a different 2.20.92 on main in the same
  window. Rebased to **2.20.93**. Writing the claim down is necessary and
  is not sufficient: a session that needs a version should push the bump
  within minutes of writing the claim, or re-read main immediately before
  merging, which is what caught this one. Only digest files and their tests are touched.
- **VERSION CLAIMED BY A SIDE SESSION (2026-08-18): 2.20.96.** The baton was
  read as HELD and is NOT claimed here; only the version number is. The change
  is the public search box: `/query?q=EY` was a SQL `LIKE '%EY%'` and returned
  1,968 of 65,441 rows on "money", "survey", "Monterrey" and "attorney" (`q=GE`
  returned 8,612, mostly on "Germany"). The one plugin file touched is
  `includes/db.php`; the rest is `railway/tests/test_search_word_boundary.py`,
  its PHP harness and TECHLOG. **Next plugin release is 2.20.97.**

- **VERSION CLAIMED BY A SIDE SESSION (2026-08-18): 2.20.92.** The baton was
  read as HELD and is NOT claimed here; only the version number is, which is
  what this file asks for so the 2.20.88 collision above does not repeat. The
  change is `economynext_lk` leaving `national_feeds` after its stories were
  measured arriving through the Sri Lanka market sweep; the plugin files it
  touches are `templates/page-sources.php`, the generated
  `partials/source-catalogue-table.php` and `assets/health.js`. **Next plugin
  release is 2.20.93.**

- **WORKING ON (current subject, 2026-08-18, LATEST):** the methodology page's
  typed update cadence, landing as **2.20.89** (`templates/page-methodology.php`,
  `railway/tests/test_ingest_schedule.py`, CLAUDE.md, TECHLOG). `2.20.88` fixed
  the generated half (`data/ingest-schedule.json`); this is the SECOND consumer
  of the same fact, which was typed and said "twice daily (morning and after US
  market close)" for a cron that went once-daily on 2026-08-14, plus 11 AM ET /
  noon ET for workflows that run at 9 AM ET / 11 AM ET. Now derived from
  `alt_ingest_schedule()`, with the two GitHub-cron hours stating cadence only.
  **A generator that reads `.github/workflows/` is the open follow-up.**
  **BATON COLLISION, read this before the next one.** Two sessions fixed the JSON
  half independently inside half an hour and both landed **2.20.88**. This one
  read the baton as HELD, saw the holder's live branch touching zero plugin
  files, and judged a version bump safe. It was not: the holder's NEXT commit was
  the same fix. The generated file was byte-identical both ways so nothing was
  lost, but the version collided and this side rebased onto 2.20.89. Reading the
  baton is not holding it - if you need a plugin version and the baton is HELD,
  say so here FIRST and wait for the release.

- **WORKING ON (current subject, 2026-08-18):** the talent digest's two
  reader-visible defects, landed as **2.20.87** (`includes/subscribe.php`,
  `railway/tests/test_digest_scope_rules.py`, TECHLOG). Every row said the
  company twice because `company: headline` sat over a headline written to
  open with the company; measured over the live week, the label is redundant
  on 89.4% of 1,411 rows and load bearing on the 3.3% the headline never
  names, so it is dropped CONDITIONALLY on a contiguous all-token match with
  both sides ASCII folded and legal suffixes stripped, never by prefix strip
  and never unconditionally. The untranslated Spanish and Portuguese rows STAY:
  of the 74 headcount rows that survive the script filter, 17 are Latin-script
  non-English and they carry 74% of the jobs named, two of the top five. They
  are not labelled with a guessed language either; each row now names its
  stored `source_name` and the caption says the headline is a quotation.
  **Backfill RAN** (workflow 32201927849, quebec_months=40): 1,318 Quebec
  notices parsed from 36 monthly PDFs, 1,318/1,357 of what those documents
  declare, and Canada went 195 -> 1,372 live rows back to 2022-06. Mazovia went
  2 -> 10. It left ONE thing behind: the press page kept a pre-backfill render
  while the home hero moved on, because the write path flushes the PHP
  transients and only a version bump flushes WP Super Cache's rendered page.
  2.20.95 is that flush; it cut the gap from 8,025 to 2,650 against a 2,624
  bound, and the residual is two renders taken seconds apart while collectors
  write. **The open `headline_containment` FAIL is NOT this work** - it is PR
  #112's `employer_country` stamping re-scoring published rows into the US
  slice (+79,749 jobs on +41 entries), and only a human can close it.

- **PREVIOUSLY WORKING ON (2026-08-18, later):** the within-WARN revision dedup
  that never once ran for the pair in its own comment, landed as **2.20.86**
  (`includes/db.php`, `railway/tests/test_warn_revision_dedup.py`, ARCHITECTURE,
  TECHLOG). `ops_status [3]` said "within-WARN revision dedup regressed";
  nothing regressed. Pass (3) of `alt_reconcile_supersets` ran inside the
  `company_key` loop, and Texas republishes a revised WARN notice by appending
  the word to the EMPLOYER cell, so the pair keys as two companies and a
  per-company pass can never see it. The live guard slept through 25 days of it
  because it bounds the Tyson sum at 8,945 and the DOUBLED sum was 7,184 — it
  passed on headroom, not agreement, and only reddened when three unrelated
  legitimate Tyson rows crossed the bound. Swept the whole corpus first: 60
  revision-marked rows, 16 WARN at or above the 100 floor, **two real pairs,
  1,870 jobs** (Tyson Amarillo TX 1,761 + Signify/Genlyte TX 109). A third
  same-count pair is REJECTED and pinned as a test (First Brands Darke vs Wood,
  OH, 302 each — two counties, two real notices). Applied via
  `/reconcile-supersets`, which reported `changes: 2` and touched nothing else;
  no `/bulk-purge` was needed because only `superset_of` changed. [3] now reads
  18 passing and no headline incident opened.
- **PREVIOUSLY WORKING ON (2026-08-18, earlier):** the healer that could not see a
  self-timeout, and the suite that outgrew its wall. GitHub reports a
  `timeout-minutes` kill as `cancelled`, so `self-heal.yml`'s `failure`-only
  gate skipped six times in the half hour after "Tests" self-killed at 15m0s on
  main, while `ci_alert.py` was mailing the same event as CI SELF-TIMEOUT. One
  definition now serves both (`ci_alert.self_timeout_of_run` /
  `is_self_timeout_cause`), the workflow admits `cancelled` so the gate STEP can
  read the annotations an expression cannot, and **the sibling repo has the same
  fix** (pushed there too). The suite itself: 353s -> 869s in four days, of
  which 177.9s was `time.sleep` against stubbed hosts (an unstubbed source in
  `CronWiringTests`, plus two import-order races on `GAP`) and 100.8s was one
  100-second copy walk computed twice. All fixed where they lived, no assertion
  weakened, and `Tests` now runs as two parallel matrix halves so the ceiling
  stays 15 minutes and still means something. No plugin change, no deploy.
- **PREVIOUSLY WORKING ON (2026-08-17):** the daily digest that never went
  out on a Monday, landed as **2.20.84** (`railway/digest_send.py`,
  `includes/subscribe.php`, `includes/digest-api.php`, `includes/db.php`,
  `.github/workflows/digest-send.yml`, three test files, TECHLOG). The relay
  picked ONE tier per run and picked weekly on a Monday, so every daily
  subscriber got nothing, weekly, in silence. Both tiers now run as two
  independent passes inside the one 13:10 job, and the per-period guard is per
  tier (`last_sent_daily` / `last_sent_weekly`) because a shared stamp let the
  first pass hide everybody from the second. Schedule untouched. The same version also
  stops a plain GET from unsubscribing anybody: a GET now renders a one button
  page and only a POST writes the row, the RFC 8058 POST path is unchanged,
  and the unsubscribe link is out of the confirmation email's body so a link
  scanner can no longer confirm an address and then drop it.
- **AND BEFORE THAT:** the CONFIRMATION email's open
  pixel, landed as **2.20.78** (`includes/subscribe.php` copy and comments,
  `tests/test_digest_subscription.py`, `tests/test_digest_brevo_feedback.py`
  docstring, RUNBOOK, TECHLOG). Measured on a real send: Brevo injects its open
  pixel into the message that ASKS permission, which goes to a `pending` row
  that has consented to nothing. It cannot be exempted - `wp_mail` through the
  Brevo WP plugin has no per-message control and
  `contactPixelTrackingConsent` lives on an API call neither of our two paths
  makes - so the answer is disclosure, and the form copy now names that one
  message. The lever that WOULD separate it is an owner decision, written up in
  RUNBOOK "Open and click tracking", not half-built. The double opt-in
  mechanism is untouched.
- **AND BEFORE THAT:** bounce and complaint handling under **Brevo**, landed as
  **2.20.65** (`includes/digest-api.php` and
  `tests/test_digest_brevo_feedback.py` only). `/digest-webhook` verified a
  Svix signature and dispatched on Resend event names, so under Brevo it
  processed no bounce and no complaint at all - which ends in a suspended relay
  account, not in a quiet gap. **Brevo signs nothing** (no HMAC, no signing
  header, verified against its own docs), so the boundary is a shared token in
  a header, accepted in `Authorization: Bearer` OR `X-Alt-Webhook-Token`
  because this host may strip the former and the two failures look identical.
  Provider chosen by what the request carries, never a setting; the Svix path
  is untouched and Resend still works; one suppression path. Arming it is
  owner-only and the steps are in RUNBOOK "Bounces and complaints".
- **AND WORKING ON:** the digest's presentation, Python side only
  (`railway/digest_layout.py`, `railway/digest_send.py`,
  `tests/test_digest_email_layout.py`). The property is that a FORWARD does
  not break it: webmail deletes `<head>` and every `<style>` block when a
  message is forwarded, so every rule is inline on the element and the
  message carries no style block at all. Nested tables, not flexbox, because
  Outlook draws mail with Word. Plus a preheader and a subject that says what
  changed. No figure is composed here; the site still composes every section.
  **BLOCKED, not done:** three content additions the owner asked for later (a
  date on each entry, one year-to-date line per tracker, a top-countries block
  under the layoff section) all live in `alt_digest_compose_layoff` in
  `includes/subscribe.php`, which another session holds. Reported with a
  ready-to-apply patch rather than edited into a contended file.
- **DONE (this session, picking up that BLOCKED item), landed as 2.20.68:** the three
  content additions, inside `alt_digest_compose_layoff` and
  `alt_digest_compose_talent` in `includes/subscribe.php` and nowhere else.
  A date on every entry, one year-to-date line per tracker, and a
  top-countries block at the foot of the layoff section. Two findings that
  change the shape: `include` on `/aggregate` is an opt-in allowlist, so the
  old `include=leaders` returned `top_countries` EMPTY, and the composer sent
  no `date_basis`, so it inherited `layoff_date` while the tracker page
  defaults to `notice`. The basis is now named in the request and named in
  the copy. No signup markup is touched. Verified on d21d281: Tests, Style
  standard, Card contract, Deploy and the rendered contrast audit all green on
  that SHA, `reader_freshness.py` PASS on 2.20.68, and the digest workflow run
  with `dry_run=1 freq=weekly preview=1` composed all three sections against
  live WordPress with every addition present in BOTH body parts. Left alone on
  purpose: the section's own "N verified entries totalling X job cuts" reads
  `totals.jobs`, which is verified PLUS announced. The year-to-date line reads
  the same field so the two agree; correcting the label is a separate change.
- **DONE (that separate change), landed as 2.20.71:** the label was corrected
  in `alt_digest_compose_layoff` and nowhere else. The section now leads with
  the VERIFIED tier (`jobs - announced_jobs`, `entries - announced_entries`),
  which is the quantity the tracker hero publishes under that same word, and
  states the announced-inclusive totals as a labelled companion followed by
  `alt_announced_tier_sentence()` verbatim. `companies` moved into the
  companion: it is `COUNT(DISTINCT company_key)` over the whole set with no
  split shipped, so leaving it under "verified" would have traded a wrong
  adjective for a mixed-scope sentence. The 2.20.68 year-to-date line moved
  to the verified tier in the same edit, which is what kept it agreeing with
  the headline. Verified on 75f4404: Tests, Style standard, Card contract and
  Deploy green on that SHA, `reader_freshness.py` PASS on 2.20.71, and the
  digest run `dry_run=1 freq=weekly preview=1` composed both tiers into the
  HTML and the plain-text parts against live WordPress.
- **AND WORKING ON:** the AI cumulative chart's gate, landed as **2.20.66**
  (`assets/layoffs.js` and `tests/test_ai_chart_gate_matches_line.py` only).
  It selected and started on `ai_jobs`, which is verified PLUS announced, and
  then drew the verified value, so a month with only announced AI cuts opened
  the series on a flat zero. The gate, the start scan and every plot site now
  read `aiVerifiedJobs()` / `aiAnnouncedJobs()`, the only two definitions.
  Running totals accumulate over the whole series and are sliced for display,
  so no plotted number moves; the announced band stays and stays labelled.
- **AND WORKING ON:** an applause control on single blog posts. One integer per
  post in `wp_alt_post_claps`, incremented by one atomic UPDATE, read for a SET
  of posts in one query so a listing costs one round trip. Anonymous and
  aggregate by construction: the table has two integer columns and no third
  place to put a person. New files only (`includes/blog-claps.php`,
  `assets/blog-claps.{css,js}`); `assets/blog-reading.css` and
  `includes/blog-typography.php` belong to a concurrent session and are not
  touched here.
- **ALSO WORKING ON (that concurrent session):** pass three on the blog reading
  surface, committed locally as **2.20.64**, not pushed and not deployed. The
  measure now climbs with the type to 820px at 23px, the media comes back to
  about 1.25x it instead of 1.49x, the h2 is 1.70x the body with 80px above it,
  the contents is one serif column, and the article sits on a capped 1300px
  card over a ground. 46 tests green; the phone is byte-identical at 18/339 and
  37.0 characters per line. It touches only `assets/blog-reading.css`,
  `railway/tests/test_blog_reading_surface.py`, `docs/TECHLOG.md` and the
  plugin version.
- **TWO SESSIONS, ONE WORKING TREE, SO READ THE VERSION BEFORE YOU BUMP IT.**
  The blog commit took **2.20.64**, so the claps and digest work needs
  **2.20.65**, not the 2.20.64 that was sitting in the working tree. Neither
  session's commit is on `origin/main`. Whoever pushes is publishing and
  deploying BOTH; confirm the other is finished, then push, wait on the commit
  SHA, run `reader_freshness.py`, and re-run the rendered contrast audit. Until
  that happens the live state of both changes is UNKNOWN, not a pass.
- **PREVIOUS SUBJECT:** the ceiling that never reached the ledger. `[2a]`'s two
  "brake is not holding" lines are pre-fix history (8e976ca, 2026-08-14T07:42Z,
  is after both runs) and will age out of the 14d window on their own. What is
  still live is the second half: `record_job_run()` writes `ceiling_usd`, but
  the Railway round trip drops it at BOTH ends — `db.php`'s `add_spend_run`
  whitelist and `spend.harvest_railway_runs()`'s key list — so `railway-cron`,
  the largest metered job in the table, records a cost with no record of what
  it was allowed to spend, permanently and by construction. Fixing the drop and
  pinning the three field lists against each other.
- **BEFORE THAT:** (landed as 2.20.61) the blog article had exactly one
  width; the page now has three (media to 820/960/1040px, the measure to 700px
  at 1400px, the contents box in two columns above 1100px).
- **AND BEFORE THAT:** (landed as 2.20.60) putting our OWN email signup on the pages readers actually land on. `alt_digest_subscribe_form()` renders on the two tracker pages only; it now also renders at the end of single blog posts, on the company profile pages (`/company-layoffs/`), on the country/state/industry facet pages and on the layoff entry permalinks. One placement per page. The component is being made genuinely self-carried (it declared `var(--alt-border)` and `.alt-btn-primary` with no fallback, and neither exists on a blog post, where `layoffs.css` is not enqueued). The third-party Mailjet `.atr-capture` box stays untouched: it lives in WordPress, not this repo.

**Same holder, refreshed 2026-08-13, not a takeover.** The WORKING ON line above
had gone stale: it still named the US incident close, which landed, so a session
reading it could reasonably conclude the holder had stopped and take the baton
under the stale clause. It had not stopped; it was the session that shipped
2.20.23 through 2.20.34. **A stale subject line reads as an absent holder**, and
that is the whole failure mode this file exists to prevent. Update the line when
the subject changes, not only when the baton does.

**Left FREE on purpose by the session behind PR #3.** That session was told not
to push to main, and the baton only gates anything when it is ON main: a claim
that lives on a branch gates nothing, and would have landed as a stale HELD the
moment the PR merged. It worked on a branch, opened a PR and stopped. If you
pick that PR up, claim the baton here first, in the normal way.

**Takeover noted, per the stale-baton clause.** The SEC-recall session claimed
this on 2026-08-01 and landed its answer the same day (`e8b8541`: the misses are
lost to a rotating sweep that never returns, not to the pull cap and not to the
LLM). No commit from that holder since, >24h, and the owner asked for the
remaining work to be finished. Its subject is DONE and its fix is on main; what
is left of that area is the cost half, which is what this session took.

The two pieces of work turned out to share one cause and neither session could
see it alone: the sweep re-reads deep history it has already stored, which is
both why recent months are never reached (recall) and why the account was
losing ~$4/day (cost).

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

## How to work on this repo without publishing a wrong number

Written 2026-08-01, from the mistakes that actually happened rather than from
principle. Every line below is something that went wrong here, to a session
that believed it was being careful. None of it is about being clever; it is
about which evidence is admissible.

**1. Read facts from `origin/main`, never from the local working tree.** The
shared checkout runs behind and holds other sessions' uncommitted files. On
2026-08-01 it was **180 commits stale**, and two numbers were reported to the
owner from it before anyone noticed: a collector called dead that had run and
stored 48 rows, and a row count off by 700. `git show origin/main:path` costs
one command. A stale tree does not announce itself; it just answers confidently.

**2. Look at the page.** A green deploy proves an upload. A passing test proves
an assertion. A sitemap count proves a number. **None of them can see two links
that say the same thing.** The company pages shipped with 400 tests green, a
verified 7,491-URL sitemap and a matched deploy SHA, and still had a citation
that read as a duplicated link and a footnote that printed 316 times. Both were
found in under a minute by opening the page at 375px.

**2b. When something looks odd, do not stop at the first explanation that makes
it fine.** The same day, every company page was rendering WordPress's legacy
`theme-compat/header.php` (a block theme has no `header.php` for `get_header()`
to load), shipping a **duplicate `<title>`, the site name as the page's first
`<h1>`, and no site header, footer or navigation at all** across 34,677 URLs. A
session looked at that page, saw the bare site name where the header belongs,
wrote "it looks unstyled" -- and then checked the stylesheets, found
`layoffs.css` loading and the theme font applied, and concluded it was merely
minimal. **The first observation was right and the follow-up check answered a
different question.** "Is the CSS loading" is not "is the header there". When
the evidence and the explanation disagree, the explanation is the thing to
doubt.

**3. Measure the premise before you build on it.** Briefs are guesses until
something checks them. On 2026-08-01, in the sibling repo: a "24 missing
languages" gap was reproduced at 7x and then a language-neutral control showed
**five sixths of it was which feeds are wired, not which languages are read**;
and a geography fix, applied as briefed, would have stamped a wrong country on
the exact rows it was meant to fix, because `en-GB` returns **100% the same
items as `en-US`**. An agent that measures and contradicts the brief is doing
the job. Say so, then build the part that survived.

**4. A green run can do nothing at all.** `deploy-plugin.yml` defaults to
`dry_run=true`: green, zero bytes uploaded. `collect-structured.yml` succeeded
six times while the collectors inside it had never produced a health row. Ask
what the run *did*, not whether it passed, and prefer an artifact you can count
over an exit code.

**5. Absence of a signal is not a pass.** PASS / FAIL / **UNKNOWN** are three
states and this repo enforces that in `data_integrity.py`. The corollary for
sampling: **0 of 40 is not evidence of zero.** A session declared the archiver
broken on "0 of 40 rows have `archive_url`" when the real rate was 72/17,533 —
at 0.4%, a 40-row sample finds nothing about 86% of the time. Compute what your
sample could have detected before concluding from it.

**6. Cite the file when briefing an agent.** An agent was briefed to design
against the Form D and M&A overstatements; those are the SIBLING repo's
incidents. It grepped, found nothing, said so, and designed against this repo's
real ones. It was right and the brief was wrong. Memory across two similar
projects is exactly where this fails.

**7. Fix the cause, not the symptom, and check the escape hatch too.** Five
failed tickets kept `drain-writers` red; `-f resolve=all` reported success and
cleared none of them, because "all" iterated only orphans while failed tickets
needed an exact ID — and the help text promised otherwise. **The command that
exists to clear a permanently-red job was itself keeping it red.** When a
documented remedy does not work, read it before running it again.

**8. Say what you did not verify, in the same breath as what you did.** Every
entry in the log below has an UNVERIFIED line. That is not hedging; it is the
only thing that tells the next session where to look first.

## Handoff log (newest first — what each session did + what's next)

## #32 - the signup was on two URLs, and could not have survived being on more (2026-08-15, 2.20.60)

Placed `alt_digest_subscribe_form()` on single blog posts (via `the_content`,
gated exactly as `blog-typography.php` gates its stylesheet), the company
profile pages, the country/state/industry pages and the entry permalinks. One
placement per page, through one helper, `includes/subscribe-placements.php`.
No second form, table or route.

**The placement was the small half.** The component's comment claimed it
depended on nothing outside itself; every colour was a bare `var(--alt-*)` and
the submit button wore `.alt-btn-primary`, all of which live in `layoffs.css`,
which is not enqueued on a blog post. Measured in headless Chrome on the blog
fixture, pre-change: *"the signup's outer box has no border width at all"* and
*"the field is 33.0px tall, under the 44px floor"*. Every colour is now a
component token reading the site token with the site's own literal as its
fallback, so tracker surfaces are unchanged to the byte.

**Verified live at 2.20.60**, deploy and Tests both green on the commit SHA,
`reader_freshness.py` PASS. Real Chrome on the live pages, 375x812 and
1280x900: zero horizontal overflow; field, button and privacy summary each
44.0px on all three surfaces; the blog post's block is 668.3px with the submit
ending 593.7px down an 812px screen. Rendered contrast audit PASS on the three
standard surfaces AND on a live company page, facet page and blog post, all
four theme combinations.

**The both-signups state, measured rather than assumed.** The third-party
Mailjet `.atr-capture` box is still on the live post at y=804 (659px tall,
early in the article); ours is at y=8646 (668px) at the end. They are ~7,800px
apart in an 11,732px document, same 339px column, so they never share a screen.
Nothing in this change styles, hides or depends on that box, and a test asserts
our geometry is identical with and without it.

**UNVERIFIED / know before you build on it.** (a) The blog has NO dark mode:
`blog-reading.css` declares no dark palette and the component deliberately ships
no `prefers-color-scheme` block, so the signup's fallback literals are light
only. If anyone gives the blog a dark mode, the signup needs a dark half and a
test will tell them so. (b) Seven test modules error locally on missing
dependencies (`test_extractor_guards`, `test_ssrf_safe_fetch`,
`test_job_deferrals` and four others); they fail identically on the unchanged
tree and are green in CI, which installs the lock. (c) `single-layoff.php` was
included on my own judgement, not by the brief's enumeration: ~1,800 indexable
entry permalinks are a landing surface. It still renders the legacy
`theme-compat/header.php` (HANDOFF item 2b), which this change does not fix.
(d) Section 8 of `blog-reading.css` styles `.atr-capture`; it predates this
change and was left alone rather than removed.

## #31 - the board's cells linked to a page that recounted them (2026-08-12, bumped 2.20.14, shipped inside 2.20.15)

Picked up the second item `ab4dea1` left open, the one #30's entry below also
names. The at-a-glance board counts on the EFFECTIVE date (deliberate, and its
footnote says so) and its cell `hrefs` carried only `from`/`to`, so since 2.20.4
a click landed on a filing-basis view. **Measured on the origin before touching
anything: YTD workers 479,037 in the cell against 460,660 in the view the link
opened, 18,377 apart; this month 37,781 against 35,352; this week 14,162 against
13,071.** Verified live AFTER the deploy, from a reader's view, cell against the
`/aggregate` behind its own href: 373/1, 5,621/49, 38,154/124, 479,410/2,700,
all four exact. The old link would still have shown 4,444 for the week and
461,033 for YTD.

**Both paths or nothing.** The href names `date_basis` AND the `.alt-nfilter`
click handler reads `data-date-basis` and goes through `setDateBasis()`, because
the handler `preventDefault()`s the href: fixing one alone makes the same cell
mean two things depending on whether JS ran. The board's PARAMS were NOT touched
(`alt_signal_board_periods()` and `P` must stay byte-identical or `takeBoot`
rejects the inlined board and every first paint costs four fetches), and the
basis is READ OFF those params rather than hardcoded. New
`railway/tests/test_board_link_basis.py` RUNS both renderers, php and node: 8 of
its 15 fail on the pre-change tree, the other 7 are named in the file as
regression bars.

**One thing fixed that this change caused:** `refreshAll()` does not repaint the
board, so a basis switch never reached the board's footnote. The two wordings
moved into `boardBasisNote()` and `renderBasisCopy()` now swaps that one line in
place with no refetch.

**UNVERIFIED / know before you build on it.** (a) The tap path is proven in node
against the real handler body, not in a browser: no session here has a DOM. (b)
Three concurrent sessions were pushing to main during this one. This work landed
as 2.20.14, a deploy that GitHub cancelled when 2.20.15 queued behind it, so
**2.20.14 never reached a reader**; the code is live inside 2.20.15, which is
what `reader_freshness.py` PASSed on. Its work commit also carries a `wip:`
subject, left rather than force-rewriting shared main history; the TECHLOG entry
is the record. (c) The baton was claimed and released here, and another session
pushed 2.20.15 and 2.20.16 to main while it was HELD. If baton discipline
matters, that is worth the owner knowing.

**Still open in this area:** `data_integrity.py`'s `HEADLINES`/`INVARIANTS` send
no `date_basis` while their comments claim they use the page's, `recall_precision`
queries an announcement-year gold set on the effective basis, and the CSV export
has no `announcement_date` column.

## #30 - the seventh basis, in the one place a reader cannot see it (2026-08-12, 2.20.12)

Picked up the item `ab4dea1` found and deliberately left for its own
measurement: `alt_live_numbers()` is hardcoded `YEAR(layoff_date)` and feeds the
FAQ copy, the **FAQPage JSON-LD** and the SERP meta description, while the cite
line beside it has been on the filing basis since 2.20.4. **Measured live before
touching anything: 479,410 in the structured data against 445,869 in the cite
line, 33,541 apart (7.5%), both worded "so far in 2026 ... worldwide."** Both
reconcile exactly against `/aggregate` on their respective bases, which is what
made the diagnosis provable rather than plausible.

**Kept the effective basis and labelled both, rather than converging them.**
Reasons are in the TECHLOG entry and in the code; the short version is that the
FAQ asks when cuts happened, the same figures are the press and report pages'
documented floor, and this function has no request to take a basis from. The
new test section derives its expected wording from the column the query
actually windows on, so it pins the SQL-to-words agreement and NOT the
decision: a later session may move the query onto the page basis and the tests
still pass, provided the copy moves with it.

Deploy green on the commit SHA; `reader_freshness.py` PASS on 2.20.12; the
labels confirmed live in both the rendered FAQ and the JSON-LD.

**What is still open in this area, unchanged by this session:** the
at-a-glance board's cell `hrefs` carry only `from`/`to`, so a click lands on a
filing-basis view showing a different number than the cell (needs the
`.alt-nfilter` handler in `layoffs.js` to carry the basis, or JS and no-JS
diverge), and `data_integrity.py`'s `HEADLINES`/`INVARIANTS` send no
`date_basis` while their comments claim they use the page's. Also noted, not
fixed: the SERP description rounds down to a floor against the FAQ's number but
nothing enforces it as a floor against the hero's.

## #29 - an outside review, checked line by line, and the incident that is set to erase itself (2026-08-10)

**An external reviewer audited this codebase read-only and produced a document
with an assessment, a repair sequence, anti-drift rules, a release checklist and
cost controls. Its substance is folded in below. Nothing was imported as fact
because a reviewer wrote it: every checkable claim was checked, and the verdicts
include four refutations of the reviewer and one refutation of a document this
repo committed two hours earlier.**

The reviewer's central thesis is that the risk here is complexity rather than
incompetence: individually sensible guards that have begun to contradict each
other, so local correctness no longer adds up to global correctness. That thesis
is CONFIRMED, and the sharpest instance is not in the review. It is item 1 below.

### 1. THE INCIDENT IS SCHEDULED TO LAUNDER ITSELF ON 2026-08-22. Owner decision needed.

`MovementInvariant` is holding the US headline FAIL open by refusing to advance
a failing baseline, which is correct and deliberate (`data_integrity.py:1367-1371`).
The US baseline is therefore pinned at `2026-08-07T18:23:51Z` while the other two
slices advance daily.

At `MAX_BASELINE_AGE_DAYS = 14` (`data_integrity.py:370`) a different guard takes
over. `data_integrity.py:671-676` returns UNKNOWN for a baseline that old, with
`pending=True` and **`suppressed` unset**. `_out`'s own docstring says that is on
purpose: "It is NOT set for the other UNKNOWNs (no baseline, stale baseline,
unreachable API) ... refusing to record them would freeze the guard permanently
unarmed." And `record_baseline` skips only `FAIL` and `suppressed`
(`:1367-1380`). So the first daily run at which the pinned baseline is more than
14 days old **records the failing figure as the new normal**, the slice returns
to PASS the next day, and the incident vanishes with no human involved.

The baseline was captured `2026-08-07T18:23:51Z`. The recorder runs about
18:00Z. **The 2026-08-21 run is still inside 14 days; the 2026-08-22 run is the
one that launders it.** Eleven days from this entry.

Both guards are right on their own. "Never advance over a FAIL" keeps an
incident open. "Never let a stale baseline freeze the guard unarmed" keeps the
check from dying silently. Together they say: hold the incident open for exactly
fourteen days, then adopt it. Nobody decided that.

**This was NOT changed in this session.** It is invariant machinery and the fix
is a design decision, not a repair: the reviewer's recommendation is a sticky
incident record that only a reviewed reason plus affected row IDs can close.
UNVERIFIED: whether a slice that goes UNKNOWN-stale and is then recorded also
resets anything else downstream.

**FIXED 2026-08-10 (branch `claude/sticky-headline-incidents`).** The sticky
incident record is in: `railway/headline_incidents.json`, read by
`MovementInvariant` and written by `record_baseline`. A rendered FAIL opens an
incident, and from that moment the slice's verdict is FAIL **because the
incident is open**, not because the formula is re-derived each day — which is
the point, since every input to that formula (span, later arrivals, baseline
age) drifts in the forgiving direction while an incident sits. Closing takes
`--close-incident <slice> --reviewed-by --reason --rows --replacement-jobs
--replacement-entries`; all five are required and it writes nothing if any is
missing. Second lock: `record_baseline` refuses to advance any slice with an
open incident whatever state it reports. An unreadable ledger is
UNKNOWN-and-suppressed for every slice, so `rm headline_incidents.json` is not a
way to clear a FAIL either. No bound was touched — `move_floor`, `mean_factor`,
`max_share` and `MAX_BASELINE_AGE_DAYS` are unchanged, and the stale-baseline
UNKNOWN still records for slices with no incident open, so the guard still
cannot freeze unarmed. The live us_all_time incident ships in the ledger, open.
The laundering was replayed on the pre-fix module to confirm the date arithmetic
rather than assume it: at day 20 the old code returns UNKNOWN and writes the
failing figure as the new baseline. Regression test:
`StickyIncidents.test_time_and_later_rows_cannot_close_an_open_incident`.

The UNVERIFIED question is answered. `record_baseline` writes exactly one file,
`headline_baseline.json`, and resets nothing else — so the laundering had no
direct downstream reach. Its INDIRECT reach is the whole point and is total:
with the baseline moved, the next run's slice reads PASS, and every consumer of
that one verdict follows it green — `ops_status [3]`, the public health ledger,
the weekly digest, `test_dedup_live`. One quiet file write, four surfaces
turning green, no row corrected.

### 2. The published US headline is already strict job-location. Three artifacts say otherwise.

REFUTES the reviewer, and REFUTES section 6 of
`docs/US_HEADLINE_MOVEMENT_FORENSICS_2026_08.md`, which this repo committed the
same day.

`assets/layoffs.js` sets `country_basis='any'` in exactly two places: `:845`
(export links) and `:3496`, inside `queryParams()`, which serves the results
list. `/aggregate` is fetched from `currentParams()` (`:863-869`), which never
sets it, and the server default is strict (`db.php:927`). The comment above
`:3496` states this explicitly. So the headline tiles, the charts and the map are
strict job-location, exactly as CLAUDE.md promises; the table and the exports are
the union.

Consequences, none of them fixed here:

- `data_integrity.py:355-365` watches `us_all_time` with
  `country_basis="any"`, labels it **"United States jobs, all time"**, and its
  own note claims that is "the same basis the reader's own filter uses". It is
  the basis the reader's TABLE uses, not the headline. Every alert, every
  RUNBOOK reference and every line of the forensics doc quotes 7,061,880, a
  number no headline tile has ever displayed. The tile shows 6,192,930.
- The forensics doc's finding that 868,950 jobs are "**12.3% of the published
  'United States jobs, all time' figure**" is true of the table and the exports
  and is NOT true of the headline. A session acting on its section 7 would be
  relabelling a figure that is already on the basis being demanded.
- `railway/published_figures.py:668-670` reconciles strict state bars against a
  `country_basis="any"` denominator, so its whole is about 869,000 jobs larger
  than its parts, systematically permissive in the one direction that hides a
  parts-exceed-whole defect.
- `templates/page-methodology.php:39` and `:77` contradict each other 38 lines
  apart, and `templates/page-tracker.php:1003` states the strict claim on the
  page whose list is inclusive.

**The 79,422 asymmetry survives all of this.** US on ANY basis is a filtered
subset of an unfiltered worldwide, so a US rise larger than the worldwide rise is
impossible on either basis. The incident is real; the number it is quoted in is
the wrong one.

### 3. `wp_alt_layoffs` had no `updated_at` column, so the incident window was never recoverable

The forensics doc said the row list needed either a direct
`SELECT ... WHERE updated_at BETWEEN ...` or a new endpoint. The column did not
exist. The `updated_at` at `db.php:146` belongs to `wp_alt_company_directory`.
The proposed query would have returned "Unknown column". The UNKNOWN verdict was
more correct than the document that issued it knew, and stays UNKNOWN
permanently: no archive, no snapshot and no query can now name those rows.

PR #26 adds the column, an index on it, a stamp at every one of the nine writers
to that table including the bulk re-scoring statements, and
`GET /changed-rows` behind the existing `alt_api_permission` gate. It answers
forward only, says so in its own response body (`window_is_instrumented`,
`verdict_when_empty`), and states that deletions are invisible to it because
`/trash` and `/bulk-purge` leave nothing behind. Detail in TECHLOG.

### 4. Verdicts on the reviewer's other checkable claims

CONFIRMED: the movement formula gets more permissive while the baseline is
frozen, in two independent ways. `floor = move_floor * span` (`:682`) grows with
the frozen span, so the current +93,210 passes at span 5.0d; and
`allowance = abs(d_entries) * base_mean * mean_factor` (`:698`) with
`base_mean = 160.787` and `mean_factor = 12` buys 1,929 jobs per net entry, so 49
net new entries clear it. `abs()` means rows LEAVING widen it too. No incident
state exists anywhere other than the baseline's `captured_at`. The regression
test the reviewer asks for (day one fails, later arrivals widen the formula,
verdict must stay FAIL) is absent from `test_headline_guards.py`.

CONFIRMED: `survey_reconcile.py:29` plus `:70` plus `:162-171` calls
`requests.get("")` when `SURVEY_FEED_URL` is unset, though the module comment and
`survey-reconcile.yml:40-42` both promise a dormant exit.
`test_survey_reconcile.py` never exercises the feed axis at all.

CONFIRMED and currently red: `tracker_diff.py:411-417` returns without posting
health, it is absent from `health_digest.py` `MAX_AGE_DAYS`, and it therefore
inherits the 10-day default for a job whose real cadence is never. It is at
14.8 days and is manufacturing a red weekly workflow plus an owner email for a
job that is working as designed. This is the same defect CLAUDE.md's own
retirement rule was written about, and there is no `dormant` state to put it in.

CONFIRMED verbatim: the live integrity alert names
`worldwide_all_time: recorded 20,407,113 jobs / 63,602 entries` as the cause.
That is successful bookkeeping. `data_integrity.main()` prints FAIL lines first
and baseline notes last, sorted, and `ci_alert.extract_cause` matches none of the
FAIL line's shapes (`_UNITTEST_HEAD` needs `FAIL:` with a colon; the text says
"FAILING", not "failed") so it falls through to `body_lines[-1]`. Because
normalisation replaces the digits, the wrong cause has a stable fingerprint and
is the one that gets deduped and mailed, while the real assertion never reaches
the owner. `health_digest.py:231-234` already emits `::error::` for the same
class of thing; `data_integrity.py` does not.

CONFIRMED: an integrity failure is routed into the scraper-repair playbook.
`data_integrity.py:1394-1401` posts its verdict into the SOURCE health ledger as
`degraded`, `health_digest.py:115` folds it into `names`, and `:145-153` then
tells the owner to "find its collector in railway/ ... and fix the parser".
CLAUDE.md states "source health is not data integrity" as an iron rule; the rule
holds at the definition layer and dissolves at the alerting layer.

REFUTED as stated: the reviewer's "+93,211 on +19 entries" is +93,210 on +18.
Its "79,947" mixes a one-day worldwide delta with a three-day US delta; the
single-step figure is 79,422. Its hypothesis that old rows gained a US
`employer_country` is refuted by the repo's own forensics (126 union-only rows,
107 stamped with a 2026-07-19 registry, zero with evidence inside the window, and
the only bulk domicile workflow has never run). Its named rows do not survive
either: DOGE 60,000 was already the largest US row the day before, and Oracle
21,000 sits in `ai_all_time`, which did not move at all.

REFUTED: "the $5/month target is realistic". The named-job ledger
(`spend_jobs.json`) says $0.19/day, projecting to $5.70/30d. The OpenRouter
balance history says the account fell $3.73 over 08-03 to 08-10 against $1.45 of
ledgered job spend, so **the ledger accounts for roughly 39% of the bill**.
`ops_status [2a]` reports $0.43/day, about $13/month, against a $10 policy
allowance. Two cost meters in one repo disagree by about 2.5x and `ops_status`
prints both without reconciling them. Also open: `ai-evidence-sweep` spent
$0.020 in a run against its own $0.015 ceiling, so that per-job brake is not
holding.

CONFIRMED: company-watchlist spent about $0.03/day and stored zero rows on all
three measured days.

UNKNOWN: the reviewer's Microsoft 4,800 and Block 4,000 could not be checked
live. Its claim about invalid GitHub CLI credentials in its own environment is
not checkable from here.

### 5. Three things in the review that would violate CLAUDE.md if adopted

- **"Recommended default: job location"**, with a guard that a US selection
  cannot return a France or Multiple-countries row. CLAUDE.md is explicit:
  "Don't 'fix' the discrepancy - it's intentional and documented." The
  defensible version of the reviewer's point is the LABELLING on
  `page-tracker.php:1003` and `page-methodology.php:39`, and the guard
  configuration in item 2 above. Not the filter semantics.
- **"Every dormant workflow lifecycle-exempt from freshness monitoring."** As
  written that is a blanket silence. `alt_retired_sources()` (`db.php:2027-2029`)
  deliberately refuses to mask a row whose last run postdates the retirement, and
  any `dormant` state must inherit that rule or it becomes a way to hide a
  collector that quietly resumed.
- **The document is itself a second handover file**, titled "HANDOFF BATON" and
  carrying its own baton section. `docs/HANDOFF.md` is the sole handover here;
  its substance is in this entry and its implementation detail is in TECHLOG.
  Do not commit it, and do not let it create a second baton register.

For the record, checked explicitly: the review names no competitor, never
proposes weakening a check to reach green (it says the opposite), never proposes
advancing a baseline over a failing slice, and makes no automation claim.

### 6. The review's substance, condensed

**Assessment.** The engineering is judged sound: retained source evidence with
quotable attribution, explicit verification tiers, a correction history,
normalization at trust boundaries, incident-shaped alert dedup, fail-loud data
jobs, UNKNOWN kept distinct from PASS, immutable snapshots, cost metering. No
rewrite recommended. The stated risk is accumulated complexity, evidenced above.

**Repair sequence, in the reviewer's order, corrected where it was wrong.**
1. Geography contract: one basis per surface, named on every surface. See item 2
   for what is actually broken; the union itself stays.
2. Sticky integrity incidents: a full-cycle FAIL opens state that later
   observations cannot close. See item 1 for the deadline this now has.
3. The US headline step: already enumerated; row IDs permanently UNKNOWN per
   item 3. Correct no data before a row list exists.
4. Field-aware mutation provenance: every data-changing endpoint emits a bounded
   audit record with timestamp, dataset revision, workflow and run ID, reason,
   row IDs, fields before and after, and the aggregate contribution before and
   after per watched headline. Record enrichment separately from correction while
   still noting that it moved a published aggregate. PR #26 is the first quarter
   of this and knows it: it has no prior values and cannot see deletions.
5. Survey config semantics: pick an explicit DORMANT exit or a startup
   configuration error, and test all four feed-by-manifest combinations.
6. Dormant lifecycle: an explicit state that keeps the real last-active
   timestamp, never fabricates an OK heartbeat, and inherits the postdating rule.
7. Structured CI causes: emit a stable `CI_CAUSE:` or `::error::` marker per
   failing invariant, make the parser prefer it, and reject success phrases
   ("recorded", "baseline unchanged", artifact upload, cleanup). Test with a
   failed log followed by successful baseline lines.
8. Typed remediation: route by class (source or parser, data integrity or
   mutation, workflow configuration, deploy or cache, monitoring defect).
9. Cost cadence, only after 7 to 14 days of measured yield.

**Anti-drift rules.** One contract per concept, machine-readable, with secondary
representations generated or validated from it rather than hand-maintained
alongside a comment asserting they match: filter names and semantics, geography
bases, source lifecycle and cadence, invariant metadata and remediation class,
verification tiers, AI-attribution classes, workflow ownership and mutation type.
Comments explain why; tests prove behaviour, and asserting on source text is not
evidence that behaviour exists. Separate pure logic from effects: validate
configuration, compute a typed result, write through one effect layer, emit a
structured summary, derive alerts from the summary and never from log-tail text.
Keep workflows idempotent, resumable, tied to a run ID, bounded in time and
spend, explicit about zero work, dormant, partial and failed, and unable to
report success when a batch or verification step failed. Do not widen bounds to
clear an incident; bounds come from a documented failure model validated against
observed legitimate data.

**Release gate.** A change is finished only when: the intended population and
user-facing definition are one written sentence; unit and incident-shaped
regression tests pass; cross-surface contract tests pass for page, API, chart,
drill-down, export, embed and press or report; data-changing behaviour is
dry-run first and names affected row IDs and the aggregate delta; plugin
`Version:` and `ALT_VERSION` are bumped when plugin files change; the deploy
reaches the bare reader URL and not merely a cache-busted origin (already
enforced, `deploy-plugin.yml:240-247`); live integrity checks run against the
current baseline and dataset revision; no previously open incident is silently
normalised by a new baseline; corrections are logged publicly and definition or
enrichment changes are labelled distinctly; TECHLOG and RUNBOOK record the
observed result rather than the intended one; the tree is clean and the baton
released.

**Cost controls.** Reconcile the two meters before treating any target as met
(see item 4). Standing measures that do hold: cut or gate the company watchlist,
which buys nothing; avoid duplicate supplemental-news runs over one candidate
pool; earned cadence per provider; stop finite enrichment backfills when the
queue drains; keep the live gate and the cheaper extraction model. Do not
economise by removing source links, evidence retention, correction provenance,
immutable reports or integrity checks.

**Do not.** Rewrite the system. Let two sessions edit the same production area at
once. Correct the US total before the changed rows and the governing definition
are known. Call an inclusive union "US jobs". Treat a dormant workflow as a stale
collector. Let successful bookkeeping become an alert cause. Let a confirmed
incident vanish because later traffic enlarged its tolerance, or because a
fourteen-day timer expired.

### What this session shipped

PR #26 (`updated_at` + `/changed-rows`, plugin 2.20.4), PR #27 (the three
`test_ci_noise_report` failures: `MainTests` fixtures are stamped against a fixed
`NOW` while `main()` reads the wall clock, so they aged out of the window on day
eight and would have reddened `Tests` on every push from then on). PR #24 merged
after confirming its four red tests are identical on `origin/main`. The
headline-movement test is untouched and stays red.

**UNVERIFIED in this entry:** the strict-basis US headline was read live once and
not over the incident window, so whether the 08-07 to 08-08 step is the same size
on the strict basis is unmeasured. The two cost meters were compared over one
seven-day span. No claim here rests on the reviewer's document alone; where it
could not be checked, it says UNKNOWN.


## #28 - the archive promise, the freshness fixtures, and a deploy that was green all along (2026-08-07)

**Final dispatch of the session. Both trackers. Everything below is measured;
where it is not, it says so.**

### The headline: a published promise was false, and is not any more

Every listing surface prints, beside a source with no Wayback snapshot yet:
`No archive snapshot yet. We re-check weekly; next check by <date>.` That was
false from 2026-08-05.

The archiver was healthy the whole time. What was wrong is that its advertised
throughput was fiction. From the run logs:

| run | URLs touched | of a stated limit of | stopped by |
|---|---|---|---|
| 2026-08-04 | 1,231 | 1,500 | deadline, mid batch 3 |
| 2026-08-05 | 500 | 1,500 | deadline, after batch 1 |
| 2026-08-06 | 500 | 1,500 | deadline, after batch 1 |

`ARCHIVE_BACKFILL_LIMIT` was **never** the binding constraint. The 2400s
deadline was, itself silently clamped by a 3000s cap inside
`archive_backfill.py`. The job claimed 1,500 a run and delivered a median of
500. **The obvious fix, raising the batch size, would have done nothing** —
which is the only part of this worth remembering.

Measured cycle: on 08-04, 1,231 URLs moved the frontier 3.05 days, so the pool
is ~404 URLs deep per day and needed ~404 re-checks a day to hold position. At
500/day that is a 7.6-day cycle inside a 10-day bound. The margin was ~1.4 days
and nothing ever reported it.

**Both halves are fixed, because fixing only the first repeats this.**

- **The cycle.** Deadline 2400 -> 5400s, cap 3000 -> 6600s, limit 1,500 ->
  2,000, sized off the live pool over the promise rather than picked round.
  `ARCHIVE_SPN_MAX` deliberately unchanged at 80: 16 of 80 captures were
  already throttled, and the throughput that moves this number comes from the
  free availability pass, which is what stamps `checked_at`.
- **The margin.** `/archive-coverage` now publishes `unarchived_live`,
  `rechecked_recent` and `recheck_window_hours`. `ArchiveRecheckInvariant`
  divides them and FAILS when the PROJECTED worst age passes 8d (7d promise +
  1d granularity), i.e. while the 2 days of slack are still intact. Fed the
  2026-08-04 payload it fires; the age half read a comfortable 8.6d that day.

**VERIFIED LIVE**, run `31147628741` dispatched from the branch so the shipped
configuration was measured, not projected:

```
oldest un-archived attempt   11.7d  ->  3.9d   (bound 10d)
frontier                     2026-07-26 11:29  ->  2026-08-03 07:13
coverage                     21,455 -> 21,556   (85.3% -> 85.7%)
touched                      1,657 URLs in 60.5 min, 5 batches
```

It stopped on an **empty batch**, not the deadline and not the limit: the whole
due pool drained in one run. The ~3,660 still pending are all inside their 72h
retry window, so the worst age is now bounded by that spacing rather than by
throughput. Live `/archive-coverage` after the 2.20.2 deploy:
`unarchived_live 3,663`, `rechecked_recent 2,657 / 48h` = 1,328/day = a
2.8-day cycle against an 8-day projected bound.

`ops_status.py [3]`: **14 passing + 1 FAILING -> 15 verified and passing.**

Note `unarchived_live` (3,663) is BELOW `pending` (3,699): the difference is
orphan archive rows the candidate query correctly never hands out, which the
old `pending` figure had been quietly inflating the ring with.

### Reader-freshness CI

`d900985` narrowed `VERSION_RE` correctly but left two tests asserting on
`/a.css?ver=`, so `Tests` was red on `None != '2.19.275'`. **The fixtures were
the stale half, not the matcher.** Rewritten from the live page. The counts are
what matters: three assets there carry `ver=2.0.86` against the plugin's two,
which is exactly how a majority vote over "the first ver= on the page" was won
by somebody else's version. The faithful fixture fails the old matcher with the
incident's own message, `'2.0.86' != '2.19.275'`.

### Found on the way out: every deploy for two days was green and reported red

The reader-verification step added 2026-08-05 polls up to `--timeout 600`, and
was added under `timeout-minutes: 6` (360s). The wait could never finish.
Measured: deploys before that step ran 61-114s; every deploy after it ran
366-380s and was reported CANCELLED **with every step successful**. This
session's own 2.20.2 deploy is one of them, and it is live.

Same shape as the archive defect: a knob configured for a capacity its
container never permits. What it silently disabled matters more than the noise:
`CLAUDE.md` tells an egress-blocked session that **a green deploy run IS proof
it's live**, and there had been no green deploy run for two days, so that
instruction pointed at nothing. Fixed to 15 min, pinned by a test. Run
`31151850965` is the first green deploy since 2026-08-05.

### The model swap SHIPPED, on a news-path answer key

PR #19 had scored models against the SEC Item 2.05 gold set (flash-lite 16/16
at 0.388x cost) and correctly refused to flip: the corpus was SEC-only and the
news path is higher volume, messier and was unmeasured. That gap is now closed.

`railway/news_goldset_build.py` builds the key from **already-stored rows, with
no count typed by hand**: 68 items where two independent sources each left a
stored evidence sentence carrying the same headcount verbatim. 45 corroborated
by a second newsroom, 26 by an official filing (state WARN, Eurofound ERM or
SEC 8-K), which never passes an LLM on that side.

Two guards earned their place against live data:

- The server's +/-30-day fuzzy merge attaches any report for the same employer
  **whatever number it carries** (the Zillow 500 event also holds an outlet
  saying "layoffs hit 91 jobs"), so every corroborator must pass
  `extractor._count_in_text` and `_percent_only_mention` on its own evidence.
- The first row emitted was a Singapore HR site reprinting a Straits Times
  paragraph verbatim: two outlet names, **one observation**. A syndication test
  now refuses that.

The hard part was the window: the news path stores no copy of what it fed the
model, only the model's own output excerpt, and feeding that back would hand a
candidate the answer. Input is therefore rebuilt through the collector's own
window builder from a frozen Wayback snapshot. 19 Google News rows are excluded
with their reason (their input was an RSS headline that no longer exists).

35 scorable items, **$0.16766 billed** over 188 calls:

| model | posted | correct | wrong | $/item |
|---|---|---|---|---|
| deepseek/deepseek-chat (incumbent) | 30 | 30 | 0 | $0.000875 |
| deepseek/deepseek-chat-v3.1 | 31 | 31 | 0 | $0.000897 |
| **google/gemini-2.5-flash-lite** | 30 | 30 | 0 | **$0.000339** |
| google/gemini-2.5-flash | 30 | 30 | 0 | $0.001456 |

Zero wrong counts from any model: the verbatim guard means a cheap model's
failure mode is a DROP, not a bad number published. Incumbent and flash-lite
differ on exactly two items, one each way.

**Flipped** (verified on `origin/main`):

```
MODEL          = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
CLASSIFY_MODEL = os.environ.get("OPENROUTER_CLASSIFY_MODEL", "deepseek/deepseek-chat")
```

`CLASSIFY_MODEL` deliberately does **not** follow `MODEL` any more. It used to
default to it, so this swap would have silently moved three surfaces on a
measurement of one. PR #21, merge `2fba00e`.

Six stale "DeepSeek-V3 extraction" claims in `CLAUDE.md`, `README.md`,
`docs/ARCHITECTURE.md` and `docs/RUNBOOK.md` are corrected in this commit; the
orientation doc every session reads was naming the wrong model.

### Cost, both trackers

Measured cost floor per tracker at full coverage, from a **0.389** cost ratio
measured twice on independent token mixes:

| scenario | per tracker, per month |
|---|---|
| with the model swap (SHIPPED on the layoff tracker today) | **$7.78 to $13.62** |
| with batch on top (not built) | **$3.89 to $6.81** |

The 0.389 ratio was independently reproduced twice more today: 0.388x on the
news gold set and 0.390x on the live `supplemental-news` control run.

**Batch is a second halving that only unlocks AFTER the swap.** OpenRouter
batch pricing is confirmed real at 50% off, but the `:batch` slugs exist for
Gemini and **not** for DeepSeek, so it is unpurchasable while the incumbent is
a DeepSeek model. Deliberately NOT built. Do not build it before the swap.

### Owner-only (a session cannot do these)

- **OpenRouter runway was ~5.7 days** at a $3.49 key cap and a measured
  $2.84/day burn. That burn is **inflated** by two armed press backfills and
  today's A/B runs; it is not the steady state, and the $10/month allowance is
  the policy the guards actually enforce.
- **The talent tracker's key is 402-exhausted.** Verified in its `collect.yml`
  run of 2026-08-07T00:09Z: `key limit reached: collection will fail with 402`,
  $10.08 against a $10 allowance. The guard is WORKING - paid reads off, exit
  0, free collection continues. Do not raise the allowance to make it green.
- **Talent: the ChangXin IPO retract** needs a credentialed `retract.py` and
  must NOT be done as a local-only retraction.

### Still open

1. **Five workflows are RED on main and none of them is a code defect.** All
   five (`AI evidence sweep`, `Announcement lifecycle review candidates`,
   `Hawaii WARN OCR import`, `Live data-integrity check`, `Superset dedup
   reconciliation`) ran on 2026-08-06 between 17:59Z and 19:04Z and were
   **cancelled at 905-1021s**, which matches **none** of their declared job
   timeouts (5, 10, 10, 20, 30 min). `Announcement lifecycle review` ran 15.1
   minutes against a declared 5-minute timeout, so the declared timeout did not
   fire: this is an Actions-side cancellation, not a repo misconfiguration.
   Logs have already rotated, so the cause is **UNKNOWN from here** - not
   benign, just unproven. They should go green on their next scheduled run;
   if they do not, that is the thing to chase.
2. **A cancelled run produces no alert and no readable cause.** `ci_alert.py`
   extracts the failing assertion, and a cancelled job has none, which is why
   `ops_status [4]` prints "(cause line not read)" five times. So a whole class
   of red is invisible to the alerting path. This is the recurring species and
   it is unfixed.
3. **The model swap is only half verified live, and that is recorded as a gap,
   not rounded up to a pass.** Three `supplemental-news` dispatches (two on the
   branch, one on main as a control) all stored 0 rows from the same 24
   candidates, so the zero is the CANDIDATE POOL, not the model. The live cost
   ratio came back 0.390x, independently reproducing the gold set. But **no
   news row has actually landed with a correct count under flash-lite yet.**
   First thing to check on the next real cron run.
4. **`OPENROUTER_MODEL` may be pinned in the Railway environment.** If it is,
   the new code default never reaches the main cron and the swap is a no-op
   there. A session cannot read or change Railway env vars; the owner must
   check. This is the single most likely way the swap silently does nothing.
5. `warn_us` DEGRADED (generic-tier states dark) and `tracker_diff` STALE 11d,
   both pre-existing and both in the RUNBOOK.

### UNVERIFIED by this session

- The **private benchmark** (`scratchpad/bm-live.html`, local only) was NOT
  refreshed. Nothing this session changed a published metric or a source, so
  the vs-competitor read is unaffected, and the owner is out of budget. It was
  last written 2026-08-06.
- The five cancelled workflows above: cause **not determined**, logs gone.
- `[4c] DIGEST SUBSCRIBERS` is UNKNOWN from this environment (no `WP_API_KEY`).
  That is not "zero subscribers".

### The lesson, in one line

Roughly a dozen defects across both trackers this week were one species: a
mechanism reporting health while doing nothing, so the search is **"what would
never tell us if it broke"** - and today it caught a limit that was never
reached, a check that only fired after the promise broke, a fixture that could
not fail, and a deploy that was green all along.

**Baton left FREE.** It was FREE at the start and no concurrent session
existed; this entry is the handoff.


## #26 - three UX-audit defects fixed on a branch; PR #3 open, NOT merged

Two of the three were wrong published numbers. See TECHLOG 2026-08-04
(2.19.263) for the full write-up; the short version:

1. The in-progress month was drawn as a completed one, so on 4 August three
   charts published the reverse of the data (August's 16,546 verified cuts in
   four days read as a ~70% collapse against a ~58,000 monthly run rate; the
   AI-share line terminated at exactly 0.0%; the year-over-year line crossed
   under last year). All three now label it partial, dash it, and name the
   elapsed days. Nothing is extrapolated.
2. Bar cards drew verified + announced beside a verified-only headline
   (~757,000 visible against 444,871). They now draw a verified pair added at
   `$topN[4]/[5]`, and each card reconciles its bars against the headline out
   loud.
3. The page title was 46px and the figure the page publishes was 20px in a
   side panel. The verified total is now the hero figure; three totals whose
   captions existed only to warn readers off them are demoted behind a
   disclosure with their IDs intact.

**What is next.** The PR is green (816 tests) but deliberately unmerged, because
merging is deploying. It needs a human to merge, then the usual live pass: the
four surfaces at 2.19.263, and specifically eyeball the trend / AI-share /
year-over-year cards on a phone, since the partial-month note is the longest
string on a ~190px mini card. Nothing about this change touches ingest, so no
source health or Sources-page update is owed.

- 2026-08-04 local (Claude Fable 5, public-accuracy fix agent) #25: **THE FOUR PUBLIC-ACCURACY DEFECTS FROM AUDIT #24, ALL FIXED IN ONE VERSION (2.19.261), ALL VERIFIED ON THE LIVE PAGE.**
  (1) **Coverage counts now have exactly one owner.** `alt_coverage_counts()` owns "N countries" and "N US states"; `alt_live_numbers()` delegates to it instead of running its own `COUNT(DISTINCT state)` over EVERY row (that was the 50 the FAQ attributed to WARN, and it shipped inside FAQPage JSON-LD); `alt_warn_states_phrase()` renders the sentence so the register map's DC key is never counted twice again (that was the 48). The country count drops the "Multiple countries" placeholder bucket. A **fourth** stale figure went with them, the health table's typed "WARN notices, 44 jurisdictions", now a count-free phrase because that file is generated offline and cannot read live data. LIVE: 46 US states and DC everywhere (prose + JSON-LD + ribbon), 57 countries; "50 US states", "48 US states", "58 countries", "44 jurisdictions" all return 0 hits on the page.
  (2) **"203 countries" is now 180.** 21 of those rows were US metro outlets or US states, 2 were grouping rows. The count is whitelisted against real country and territory names; US metros fold into the United States row (1 outlet -> 25, where they belonged); grouping rows are listed but not counted. **Direction of failure is deliberate:** an unfamiliar name UNDERstates reach and the generator prints it, so an omission is visible rather than silent. `railway/tests/test_country_scope.py` (9 tests) fails if a US state or metro is ever counted as a country again, if a counted row is not a real country, or if the committed partials drift from the generator. **It also caught drift nobody would have noticed:** the generator still emitted the dead "NewsAPI" name while the committed partial had been hand-corrected to "Google News", so the next routine re-run would have quietly restored a retired collector to a public page. Pinned by the test.
  (3) **The last doubled `/blog/`.** `single-layoff.php:13` built `home_url('/blog/ai-layoff-tracker/')` over a `home_url()` that already ends in `/blog`. Confirmed live before the fix (`href=".../blog/blog/ai-layoff-tracker/"`, 301) and after (clean, 0 occurrences of `blog/blog` on the page).
  (4) **Real 1200x630 social card + live `dateModified`.** `assets/social-card.png` (source HTML beside it, headless-Chrome render command in its header) replaces the 512x512 site-icon crop that was being served under `twitter:card=summary_large_image`. **The important part is HOW:** one WordPress install serves both trackers and the whole blog, and that bad image is the SITE-WIDE Rank Math fallback, so it is applied through per-page filters gated on `alt_is_tracker_surface()` and the shared default is untouched. Verified: the sibling tracker page and a normal blog post still serve their own images. `dateModified` and `og:updated_time` now derive from `alt_last_write` (was frozen at 2026-07-14 beside a live-dated Dataset node and copy saying "updated daily" four times), and the Article is attributed to the site's Organization node instead of Person "admin".
  **RESIDUAL, honestly:** the Article node's `image` property is still Rank Math's `@id` reference to the old icon ImageObject; my filter sets it at priority 20 and something later re-resolves it. `og:image`/`twitter:image` (what actually renders a share) are correct, so this was left rather than spend a second version bump on it. A future session can try the same filter at a higher priority. Tests 734 OK; deploy SHA-matched green; rendered at 375px (docW == winW, ribbon right edge 274px) and 1280px (no overflow); ops_status exit 0. The runway warning is pre-existing and untouched.
- 2026-08-04 local (Claude Fable 5) #24: **A 40-AGENT AUDIT OF BOTH TRACKERS, and it found the thing every previous session missed.** Perf, security, coverage, cost, autonomy, pages and breakage, each measured, then every critical/high claim adversarially re-verified before it was believed. Full report: session scratchpad `audit2/00-SYNTHESIS.md` (30 ranked items with evidence). Six of seven severe claims were DOWNGRADED by the verifiers, which is the point of running them.
  **THE FINDING THAT OUTRANKS EVERYTHING, and it is in the SIBLING repo:** of the talent tracker's top 25 funding rows, only 6 are a private company's disclosed round stored at the right scale. `100 billion lira (\$2.3 billion)` is stored as \$100.00B, about 43x wrong. Private-market ASSETS (\$539B), investor FUND raises (\$15B), and an IPO (\$8.6B) are all counted as company funding rounds. So its public "\$221B raised" headline is inflated. And of the 20 largest disclosed private rounds of 2026 it holds 9, missing the two largest private rounds ever recorded, while the collectors were awake and storing 1,093 signals in the six days around one of them. A wrong published number outranks every feature by this repo's own rules.
  **THIS repo, verified good news:** against the US national announcement survey we stand at **100 percent like-for-like** (444,005 vs 443,604), clear the WARN-only floor (vs 270,641), and the private benchmark's tech cell has been LYING IN OUR DISFAVOUR: it divides a US-filtered numerator by global denominators. Corrected, global tech 2026 is 160,357 jobs / 335 entries = **131 percent and 94 percent of the two tech specialists by jobs**, ~70 percent by events. We have been strategising against a number that was too harsh.
  **THIS repo, confirmed defects (ranked in the synthesis):** every coverage count has three different sources of truth (50 vs 48 vs 47, and the 50 ships inside FAQPage JSON-LD); the public "203 countries" scan claim overcounts by ~11 percent because 21 rows are US metros or states rendered as countries (the honest figure is ~180); `single-layoff.php:13` doubles `/blog/` so ~1,800 entry pages funnel their main internal link through a 301; og:image is a 512px favicon under `summary_large_image` and the Article node is frozen at 2026-07-14 with author "admin"; the weekly Wayback archiver has self-timed-out for two weeks with no alert BY DESIGN while the archive re-check invariant sits at 8.3 days against a 10-day bound; tip URLs are fetched BEFORE the domain-trust gate (blind SSRF from a runner holding both API keys); Python deps are unpinned floors with bare `pip install` in scheduled workflows.
  **FIXED AND LIVE THIS SESSION:** the export path fataled on `?q[]=x` after the throttle slot was burned and after the CSV headers, BOM and header row were on the wire (2.19.259) - **and note the self-correction, because it is the lesson**: that first fix DROPPED the offending key, which the audit correctly called worse, since dropping `?company[]=x` silently widens to the whole 63,000-row corpus served under a filename saying "filtered". It now refuses with 400 before any byte (2.19.260). A confident wrong answer beats a visible failure only in appearance.
  **NOT DONE / NEXT:** (a) the whole ranked backlog, top of which is the owner's OpenRouter top-up - the account was ~\$18 with ~3.5 days and this key's own cap binds in about a day; (b) three fix agents were mid-flight at handoff (public accuracy, alerting, security) plus two workflows (landmark funding, narrative UX) - read their reports, and if one never arrived treat that area as UNKNOWN rather than clear; (c) the two Cloudflare rules (drop utm/fbclid/gclid from the cache key here; cache talent/v1 GET reads there) are owner actions and are the largest speed wins available; (d) a systematic pass over EVERY chart title on both pages - the owner caught "Where the Money Went" plotting cities beside siblings reading "by Country" and "by Industry", and said "but many".
- 2026-08-03 local (Claude, credibility batch) #23: **THE EXTERNAL-CREDIBILITY BATCH, ALL FOUR ITEMS LIVE. 2.19.255 -> 2.19.258, each deploy SHA-matched and curl-verified.** (1) `#m-jurisdictions`: per-jurisdiction "what qualifies as a record" table GENERATED from the collectors' own configs (`generate_jurisdiction_table.py`; state lists read via the AST after a lazy regex silently truncated ALL_STATES on `table[0]` in a comment, 48 -> 20; ERM floor parsed from erm_import.py; UNKNOWN printed where no threshold is encoded), drift-guarded by `tests/test_jurisdiction_table.py`; caveat line + link on every country/state facet page. (2) `#m-notice-gap`: `alt_warn_notice_gap_stats()` computes median recorded notice days and share shorter than 60, per state and overall, from announcement_date/layoff_date only. **CAUGHT LIVE, POST-DEPLOY, BY READING THE PAGE:** the first render scored nine single-date states "median 0 days, 100% shorter than 60" (their layoff_date IS the notice column via warn.py's fallback); fixed same hour in 2.19.257 by making identical-date rows a counted exclusion (`same_date_ambiguous`, 5,293) with the reason printed. Live figures after the fix: 15,727 dual-dated notices, median 61 days, 31.6% (4,977) shorter than 60; verdict words banned by static guard, statutes cited beside the numbers. (3) `docs/AUDIT.md` auditor's pack (index + exact offline commands + a "not independently verifiable today" list), linked from `#m-audit`. (4) `#m-who` disclosure section (prose flagged DRAFT FOR OWNER REVIEW in a PHP comment — **the owner should confirm the no-paid-placement / no-services sentences**) and a computed corrections-provenance line on the log: 111 entries, 88 internal-audit/automated, 0 external, 23 unrecorded (markers only, never assigned). 2.19.258 bounds the jurisdiction table (fixed layout, min-width 860) after it inflated to 1537px. Tests 723 OK before each push; rendered at 375px (no page overflow, tables scroll in their own wrap) and desktop (DOM-verified 1024/1280). **UNVERIFIED:** desktop screenshots came back blank when scrolled (a Browser-pane capture quirk — a control shot of pre-existing content at scrollY=1000 was equally blank; DOM metrics stood in for pixels), so the desktop check is DOM-verified, not eyeballed; the "Who runs this" prose awaits the owner's words; no second pair of eyes on the provenance marker lists. Benchmark note added locally. Runway warning (~3.6d) pre-existing and untouched.
- 2026-08-03 local (Claude, task #65) #22: **THE HARVEST WAS WRITING TO A DOOR IT COULD NOT OPEN.** spend_jobs.json sat empty on main since the per-job ledger shipped; diagnosis from the 04:46 UTC dispatch run: `spend.py --harvest` read the run logs FINE with github.token (the unproven permission was fine), but the commit step's push got 403 "denied to github-actions[bot]" because the workflow declared no `permissions:` and the default token is read-only; the step swallows push failures by design, so seven green runs recorded nothing (daily balance history was silently lost the same way). Fix `ed38307`: `contents: write` + explicit `actions: read` on openrouter-balance-check.yml (an explicit block replaces defaults). PROVEN: dispatched once, "Pushed on attempt 1", origin/main now holds 4 entries for 2026-08-03 (enrich-roles $0.0048/40 items, industry-backfill $0.0171/200, reason-backfill $0.0050/40, reclassify-legacy-ai $0.00/3). **NEXT SESSION (dated note in TECHLOG 2026-08-03):** judge on several days of ledger, then (a) confirm ai-evidence-sweep cheap post-NewsAPI-fix, (b) company-watchlist to weekly if $/stored-row stays effectively infinite (workflow header reasoning + ops_status ceiling table together), (c) supplemental-news rides the funnel-port, no piecemeal gate. Tests 713 OK before each push; no plugin files touched, no deploy. **THE AUDIENCE UX PASS AND THE OWNER'S DESIGN, BOTH TRACKERS. 2.19.250 -> 2.19.255 here, 1.64.0 -> 1.66.1 in the sibling, all deployed and live-verified.**
  **THIS PAGE:** headline tiles are SERVER-RENDERED (no-JS curl byte-matched against /aggregate - the citability page no longer hands crawlers "..."); first-screen cite line with CSV/JSON links that honor the active filters; next-update time DERIVED from railway.toml by generate_ingest_schedule.py with a drift test (the typed "9 AM & 6 PM ET" was DST-wrong half the year); Sources + Roles are multi-select dropdowns (audit: every list filter already accepts comma lists end to end; company/keyword/dates are single by API design and reported, not faked); corrections log has per-entry anchors; the 700-outlet table collapsed to a link; trend explainer cut to two sentences + (i).
  **THE DESIGN (owner-shared artifact, extract in the session scratchpad's audience-spec.md ADDENDUM):** signal board (Workers / Verified / Explicitly AI-attributed / Largest event x Today / Week / Month / YTD) evolving #alt-narrative - per-row heat, every cell a REAL href (?from=&to= / ?years=) so it filters with no JS, Largest cells link to entry permalinks with a company-filter fallback; serif hero thesis ("Every layoff here is verified. That is the whole point."); derived coverage ribbon ("Covering Jan 2002 to <today> . 57 countries . 47 US states"); freshness panel with the "No figure appears unless its source states it" line; warm-paper/ink-navy/ochre palette shared with the sibling. Above-the-fold words DOWN (289 -> 270, and the no-JS reader gains the whole board).
  **CAUGHT LIVE, POST-DEPLOY, BY READING THE PAGE (three, all fixed same hour):** week 10,591 > month 2,720 is calendar-correct and read as a bug until the footnote said so (2.19.254); Roo's status line bled 120px past its card at 1280 (2.19.255); on the sibling, a future-dated filing put "Covering ... to 2 Sep 2026" on the ribbon - "Covering" claims collection, so the sentence clamps to today while the row keeps its honest date (1.66.1).
  **DISPUTED-AND-RIGHT, twice:** the roles bars were already wired (2.19.221) and the AI-share monthly chart already existed - the audience spec's audit predated them. An agent that measures before building saved two duplicate features.
  **ALSO TODAY:** 6,182 gate labels banked in the sibling (classifier training data provably flowing); evidence sweep off the week-dead NewsAPI; BENCHMARK_* rename; CI noise structurally quiet in both repos (red once per problem, weekly noise report).
  **OPEN:** tomorrow 13:00 UTC = first post-fix burn reading + first per-job cost harvest (ops_status [2a] names any liar); press backfill needs credit; owner owes the top-up and the BENCHMARK_* list; MT/NE WARN watch; alt-sb-eq equal-column styling unobserved until a 1st-of-month.
- 2026-08-02 local (Claude, spend-guard session) #20: **THE BURN, AND EVERYTHING DOWNSTREAM OF IT.** The OpenRouter account was falling ~$6.5/day (~$210/mo) against a $5 target, with ~3 days of credit left and every guard reading healthy.
  **CAUSE, measured not guessed:** `backfill.py` behind edgar-history-sweep had no seen-URL pre-check (its gdelt sibling always did) and BACKFILL_LIMIT capped POSTS not CALLS - 5,044 filings re-read on 07-28, 4,190 on 07-29. The recall session's finding (`e8b8541`, sweep never returns to recent months) was the same defect read from the coverage end. Fixed `14242cd`: pre-check fails OPEN, BACKFILL_MAX_CALLS=400. Also reverted the hourly history sweep (120 extractions per stored row, measured) and dropped my own first hypothesis (Railway cron: ~$0.17/day, innocent).
  **THE GUARD:** `railway/spend.py` ported from the sibling ($10/mo INTERIM, degrade-not-halt, per-run $0.20 ceiling metered from OpenRouter's usage object - the only state-free brake, hence the only one Railway can run). Runway alerting on the balance job: alerts on days-left, not level; fired correctly on its first run (3.2d at $6.72/day). Per-job attribution `5ce3889`: SPEND_LEDGER_V1 lines harvested daily into railway/spend_jobs.json, ops_status [2a] prints $/day + $/row per job, ceilings table must sum to budget (test-pinned). Found dedupe_llm ignoring the guard entirely and three self-client scripts unmetered.
  **ALSO THIS SESSION:** Alabama WARN restored (scraper IndexError swallowed by check=False since the state moved hosts; recovered on first live run, MT/NE now watched); evidence sweep pointed at Google News instead of the week-dead NewsAPI (`e0662b7`); benchmark rename COMPETITOR_* -> BENCHMARK_* (`6dfe9eb`, secrets never set so no shim); CI noise structurally fixed both repos (red once per problem + 24h re-red, displaced scheduled runs auto-resolve, weekly noise report; talent was ~180 of ~190 non-green runs from one re-reddening bug); #62 closed (headline_movement HEALED - push-time reads inside a 5h ingest; partial cycle now UNKNOWN, recorder refuses suppressed verdicts); wayback promise UI on every surface with derived next-check dates, a starvation bug fixed (newest-first ordering starved old pending URLs), and the 42% recall paragraph now rendering from committed measurement JSON.
  **BATON:** taken over from the SEC-recall session under the stale-baton clause (its subject was answered and landed; >24h idle; owner asked for the rest). Released after this entry.
  **OPEN FOR THE NEXT SESSION:** (a) tomorrow's 13:00 UTC balance run is the first post-fix burn reading AND the first ledger harvest - if burn is not near ~$1/day, ops_status [2a] now names the spender; (b) `docs/RECALL_BENCHMARK_PROTOCOL.md` says the recall figure "must not be published" while the methodology page publishes it (owner-sanctioned 2.19.245, single-editor caveat kept) - reconciled below; (c) warn_us MT/NE dark since 22:57Z 08-02, possibly weekend; (d) the owner still owes the account a top-up and the BENCHMARK_* secrets.
- 2026-08-01 local (Claude Code) #20: **THE RECALL CLAIM IS NOW MEASURED AND CAN FAIL. Independent SEC Item 2.05 gold set (57 events), Wilson intervals on every rate, a floor wired into `data_integrity.INVARIANTS`. Audit item #19(d), open since the last session, is done. No plugin change, so no version bump.**
  **WHAT WAS WRONG.** `recall_precision.py` printed a recall percentage and `main()` ended in `return 0` whatever it printed. No threshold anywhere, so a coverage collapse could not redden CI, could not reach `ci_alert.py` and could not appear in `ops_status`. It was also measuring something weaker than it sounded: `seed_data/recall_goldset.csv` is 40 of the year's most-reported cuts matched by asking whether the company appears **anywhere** in our data **that year**. That is company-presence-in-a-year, not event recall, and a set made of Amazon/Microsoft/Meta/Oracle/Volkswagen cannot fall far. It is **kept and still printed** with its interval, relabelled for what it is, and carries no threshold. Nothing was deleted or weakened.
  **THE GOLD SET, AND WHY IT IS INDEPENDENT.** Every 8-K filed 2025-07-01..2026-06-30 whose **structured** `items` array carries code 2.05, from EDGAR full-text search month by month: 215 accessions. Re-pulled with an independent control query in every one of the twelve months, which found **zero** item-2.05 filings the first query had missed. Every document of every filing fetched from `www.sec.gov/Archives`; the 64 with a number-plus-employee-noun sentence read by hand. **57 events** after excluding five that state only a percentage, a retained headcount or a pre-action total (Intel's 75,000 is the staff who REMAIN, Atara's 15 is who is KEPT, Geron's 260 is the PRE-cut total — `extractor.py` rejects derived counts by design, so scoring those as misses would measure a documented decision) and collapsing two accessions that are the same announcement filed twice. Primary regulator index; no aggregator, no competitor list; selection rule fixed before any tracker query. **Not** independent of the tracker's design: an EDGAR collector already reads this corpus.
  **THE NUMBER: 24 of 57 = 42.1%, Wilson 95% CI [30.2%, 55.0%].** The interval is the honest form and the point estimate alone is not. n=57 supports "well under half" and supports nothing to the nearest percent; it covers ONE source family over ONE window and says nothing about private employers, non-US employers, WARN-only or news-only events. **Do not quote it as "our recall".** Precision now reports intervals too: **38/39 = 97.4% [86.8%, 99.5%]** on counts verbatim in their source, **53/53 = 100% [93.2%, 100%]** on AI-attribution quotes — 53 observations are not certainty, which is the point.
  **⚠️ THE MISSES ARE REAL AND THEY ARE NOT A SOURCE OUTAGE.** `ops_status.py` printed ALL CLEAR with the EDGAR collector healthy while **HP's 4,000-6,000, Newell's 900, Autoliv's 2,200 in Türkiye, Molson Coors' 400, Elanco's 300, Domtar's 350, GoPro's 145 and Beyond Meat's 44** were absent from the published data — every one disclosed in an 8-K our own collector reads. `sources/edgar.py` caps at `MAX_PAGES_PER_KEYWORD = 3` (30 hits per keyword per form) and prints a warning when a keyword matches more. That is a candidate cause, it is **not** confirmed, and it is deliberately left alone: this session's job was to make the number measurable, and changing the collector in the same session would have moved the thing being measured.
  **THE MACHINE MUST NOT PROMOTE ITS OWN RECALL.** The deterministic alias/window matcher scored **31** against the editor's **24** — twelve points of inflation from a Hormel Georgia WARN filed ten weeks BEFORE the announcement it was meant to represent, an Italian composites maker for HP Inc, Dow Jones for Dow, and an Ohio WARN for a plan scoped to EMEA. So the numerator counts only editor-confirmed events, rejected candidates are recorded per row, and any new row for a not-matched event prints as `ADJUDICATE` and is never counted. Separately the live `company=` filter is a substring LIKE and returned **Experian for Xperi, Capgemini for Gemini, Insight Behavioral for Sight Sciences and a Baltic fish processor for KALA BIO**, so matching is a token-**prefix**, with a test naming all four pairs.
  **THE THRESHOLD, AND WHY IT IS NOT THE INTERVAL'S LOWER BOUND.** `MATCHED_FLOOR = 20 of 57`. Two different questions were on the table and mixing them is the scope error `plausibility_ratio()` refuses: the Wilson bound describes uncertainty about the **population**, while the gold set is **frozen** and re-measured, so the denominator cannot move and the numerator changes only on real gain or loss — there is no sampling noise to absorb. Twenty is four events below today's 24: enough that a rename breaking one alias or a dedup merge does not redden CI, few enough that a collector regression does. Precision is the opposite case (its sample IS redrawn each run) so its floor is on the **Wilson lower bound at 0.80**, which trips at six bad rows in 57 — about one false alarm per 200 runs at 98% true, where 0.85 would trip at four and fire ~1.5 times a year for nothing.
  **VERIFIED, not asserted:** the floor was made to fail by hand (19/57) and produced a FAIL in `data_integrity.py`, a red `test_dedup_live`, and a cause string `ci_alert.extract_cause` pulls out cleanly; 537 offline tests green, 24 of them new, with only the known `test_archive_backfill` missing-`requests` error; `ops_status.py` ALL CLEAR exit 0 with **8** data-integrity checks; and the workflow was **dispatched for real** (run 30717555371) — it measured 24/57, wrote the file, committed it and pushed to main, so the commit loop is proven in situ rather than by inspection.
  **UNVERIFIED, stated plainly:** (a) **no second editor has reviewed the 57 match decisions** — this manifest has one author and says so, which is exactly why it is marked `internal_regression_reference` and a test keeps it off `/benchmarks/recall`. (b) The 12-month enumeration's completeness rests on control queries agreeing, not on a proof; a 2.05 filing whose body never spells the phrase would be invisible to both. (c) Behaviour under a Bluehost 504 mid-measurement is proven by unit test, not in the field. (d) One decision is genuinely arguable and is flagged in the manifest as `ambiguous_not_matched` (Hyster-Yale: Illinois WARNs four months after a global plan that names no site), resolved conservatively; the permissive reading would be 25/57. (e) The private benchmark (`scratchpad/bm-live.html`) was NOT refreshed. (f) No live page was opened — this session changed no plugin file, so nothing renders differently.
  **NOT DONE / NEXT:** (a) **Why is Item 2.05 recall 42%?** The `MAX_PAGES_PER_KEYWORD = 3` cap is the first thing to measure, then how many candidates the LLM extractor discards. Fix that and the floor should be RAISED, deliberately and with the reasoning written down. (b) A second editor on the 57 decisions would let this set graduate toward the publication protocol. (c) #9 items 4-7 and the CPT-noindex half of item 2 are still open. (d) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables.
- 2026-08-01 local (Claude Code) #19: **CRAWLABLE COUNTRY / US STATE / INDUSTRY PAGES. 124 pages, 103 indexable. Audit #9 item 1, open for five sessions, is done. 2.19.239 -> 2.19.243, all deployed and verified live.**
  **WHAT SHIPPED.** `/country-layoffs/{slug}/`, `/state-layoffs/{slug}/`, `/industry-layoffs/{slug}/`, sitemapped together at `/layoff-facets-sitemap.xml` (in the Rank Math index, `X-Robots-Tag: noindex, follow`). **37 countries + 47 US states + 19 industries indexable; 18 countries and 3 states (WY 2, AR 2, OK 3) are `noindex, follow`; industries all clear.** Built on `includes/company-directory.php`'s shape on purpose, not a new idea: one rewrite rule per dimension, rows through `alt_api_query_compute()`, stats through `alt_api_aggregate_compute()`, ONE floor helper read by page AND sitemap, robots/canonical/title/description repeated on both SEO plugins' filters, Dataset (`isPartOf` the tracker dataset) + BreadcrumbList on indexable pages only, alias 301s.
  **THE FLOOR IS 10, AND THE NUMBER WAS MEASURED.** The company floor is 2 because that page is the only URL assembling one employer's filings into a history. A facet page with two events IS its two company pages, so the same reasoning gives a different number. Live at the boundary: 2 events (Mexico) = 2 employers / 1 industry / 2 months; 5 (Japan) = 5/4/4; **10 (China) = 9 employers / 5 industries / 9 months**; 11 (Singapore) = 11/7/10. Ten is where every block becomes a list rather than a restatement. Note what does NOT drive it: the company floor also had to hold back ~27k near-duplicates, a doorway set. There are 124 facet values total, so set-level suppression is not the governing risk here and the floor is set where the page stops repeating itself, not higher.
  **COUNTRY BASIS, DECIDED AND STATED ON THE PAGE: the STRICT job-location default, never `country_basis=any`.** The inclusive basis is correct where it is used and must not be "fixed", but on a page titled "Layoffs in Germany" it would list rows whose own country field reads "Multiple countries", and it would publish a fifth number for Germany that no other surface shows. Measured: +61 events for Germany, +126 for the US. Each page says which basis it used and links to the inclusive view.
  **NO CITY PAGES, and that is a data fact rather than a shortcut.** The brief asked for them "where the data supports it" and it does not: `wp_alt_layoffs` has no city column, the WARN scrapers parse a city into free text and deliberately keep it out of the dedup hash, and `alt_short_location()` says in as many words that this product is not city-level. Generating them would mean parsing places back out of prose.
  **THE COST PROBLEM, and the one shared-code change it needed.** The full `/aggregate` is ~31 statements, most of them per-tag loops nothing but the tracker's charts read (`reasons` is 10 SUMs, `top_roles` one per category, `map_*` re-runs `top_*` at a bigger LIMIT). Measured live: **8.1s for `country=United States`, 19.0s with `sourced=1`** — unwearable on a cold page render against a host that 504'd twice on 2026-07-31. `/aggregate` now takes an opt-in `include` block list; **omitting it returns byte-identical output**, verified live. New `facet_counts` block gives per-value EVENT counts for all three dimensions in 3 grouped queries, so the floor is evaluated for 124 facets without 124 requests.
  **A TRAP AVOIDED BY READING THE CONSUMER FIRST.** `facet_counts` is a NAMED block and not a fourth element on the `[label, jobs, ai_jobs]` triple, because `renderBarList()` in layoffs.js **already reads index [3] as a display label** (the country flag, the source-type name) and `top_industries`/`top_states` are handed to it unmapped. A fourth element would have silently printed "1,384" as the name of a bar. It is also **opt-in only, not in the default set** — it shipped inside the default at 2.19.239 and that put three grouped COUNTs over the whole table onto the flagship page's cold aggregate to serve a block only the facet sitemap reads. A new block should earn its place in the default, not inherit it.
  **⚠️ THE BIG ONE, AND IT WAS NOT MY FEATURE: EVERY COMPANY PAGE HAD BEEN RENDERING THE LEGACY THEME SHIM SINCE 2.19.233.** `get_header()` in a BLOCK theme has no header.php to load, so WordPress falls back to `wp-includes/theme-compat/header.php`. On this site (twentytwentyfive) that shipped **a second `<title>`**, an **`<h1>` containing the SITE NAME emitted before the page's own `<h1>`** (so the first heading on "Boeing Company layoffs" read "AskTheRecruiter.com"), and **no site header, footer or navigation at all — just a bare `<hr />`**, which is also why those pages offered no route back into the site. Invisible to a status code, a sitemap count, and every assertion about body content; 400 green tests, a matched deploy SHA and a verified 7,491-URL sitemap all missed it. **I only found it because the new pages inherited it and I opened one.** Fixed for BOTH surfaces in `alt_render_page_header()`/`alt_render_page_footer()`: block themes get the document emitted properly plus the theme's real header/footer template parts, classic themes keep `get_header()`, `wp_head()` still runs so the SEO plugin and the block-theme viewport meta behave normally, and it is guarded on `function_exists('block_template_part')` so a theme without parts degrades rather than fatals. Verified live on both: 1 title, 1 correct H1, real site nav and footer.
  **FOUR MORE DEFECTS, ALL FOUND BY LOOKING AT THE PAGE AT 375px, NONE FINDABLE BY CURL.** (1) "Location: Germany." printed on all 50 rows of the Germany page, because `alt_short_location()` returns the country for a non-US row; shown now only when it adds something, which on the US page is the state code. (2) The headline statistics were `<br>`-separated lines sharing one line-height, and since the figure is 24px against a 16px label, a label that wrapped left its tail stranded on a line of its own reading as a separate statistic. (3) **"4,000 jobs across 1 employers."** (4) The H1, `<title>` and meta description of the biggest page in the set read **"Layoffs in United States"**; a closed article list now, because there is no rule (it is "the Netherlands" but "Germany"). Plus one caught the same way at 2.19.242: the Texas page rendered "Countries affected here: United States, 224,107 jobs", its own scope as a one-item list, fixed both specifically (state pages no longer request the block) and generally (no breakdown under two entries renders).
  **INTERLINKING, which is the point of the set.** Every event row links to its employer's company page; each page lists employers by recorded rounds (**not** their job total, because `repeat_companies` is computed over the un-deduped WHERE on purpose and its jobs figure can include a superset member); country -> its US states and industries; industry -> countries and states; state -> up to its country; and every page carries the full list of indexable siblings in its dimension, so the set is a connected mesh rather than 103 pages reachable only from a sitemap. **The 34,677 company pages are the entry point**: each now links out to its own country/state/industry pages, and only to ones above the floor, so nothing links into a thin page. Verified live on Germany: 50 events all linking to company pages, 10 industries, 12 employers (Siemens, Bosch, Continental...), 36 sibling countries.
  **VERIFIED LIVE, not asserted:** ver=2.19.243 on the matching deploy SHA every time; 103-URL sitemap with the correct split and `X-Robots-Tag`, and present in `sitemap_index.xml`; Germany `follow, index` + self-canonical + a real meta description, Botswana and Wyoming `noindex, follow` + still 200 + explaining themselves; `/country-layoffs/usa/` 301 -> `united-states/` and `/state-layoffs/ca/` 301 -> `california/`, query string preserved; `multiple-countries` and unknown slugs 404; the default `/aggregate` still returns every block populated with `facet_counts` empty; **rendered in a browser at 375px with zero elements exceeding the viewport** (measured per element, because this site's inline `html,body{overflow-x:hidden}` makes a `scrollWidth` check meaningless here). 512 offline tests green, 68 of them new; `ops_status.py` ALL CLEAR exit 0 with 7 data-integrity checks passing and no failing workflow.
  **UNVERIFIED, stated plainly:** (a) **Only Germany, the United States and Texas were actually LOOKED at**; the other 121 pages are verified by curl and by the shared template, not by eye, and no page was seen at desktop width (the browser pane here is fixed at mobile). (b) **No local PHP/MySQL**, so the `include` gating and `facet_counts` SQL are proven by `php -l`, by the offline guards and by live behaviour after deploy, not by a local test DB. (c) The **cold** render cost of the biggest pages is only bounded, not tuned: Germany was 5.3s cold and the US aggregate is the 19s case, held behind a 30-minute page transient and a 6-hour `facet_counts` transient, both keyed on `alt_data_ver` so a write can never serve a superseded number. Nobody has measured what a crawler sees when every transient expires at once after a WARN import. (d) The private benchmark (`scratchpad/bm-live.html`) was NOT refreshed. (e) `/company-layoffs/boeing/` is a 404 and that is **correct** — the canonical slug is `boeing-company`; an alias 301 for bare brand names was not built.
  **NOT DONE / NEXT:** (a) #9 items 4 (titles/descriptions on the OTHER pages), 5 (frozen `dateModified`, `author` = admin), 6 (137KB inline CSS) and 7 (og:image is a 512x512 favicon) remain. (b) The second half of #9 item 2 is still deliberately open: making the `layoffs` CPT noindex by default and sitemapping only rows that clear a content bar. (c) **The company pages should get the same interlink treatment the facet pages just proved out** — they now link OUT to facets, but nothing links in from the tracker page itself, so the whole mesh's only on-site entry is a company page or the sitemap. A compact "browse by country / state / industry" block on the tracker page is the obvious next step and was left alone because that template is 61KB and could not be visually verified here. (d) `recall_precision.py` still has no threshold and always exits 0. (e) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables.
- 2026-08-01 local (Claude Code) #18: **HEADLINE GUARDRAILS (7 live invariants, the Spirit class made structurally impossible), and two company-page defects that only rendering the page could find. 2.19.235 -> 2.19.238, all deployed and verified live.**
  **THE SPIRIT CLASS IS NOW IMPOSSIBLE TO WRITE, not merely tested for.** Spirit was not a bad row: every row in it was correct. A +/-45-day numerator was tested against a six-year cumulative denominator, and a denominator that only grows eventually makes any real cluster look implausible (64 companies double-counting 60,367 jobs; 43 companies with 113,786 real jobs suppressed to zero, Boeing's genuine 17,000 among them). **No magnitude bound would ever have caught that**, which is why the fix is structural: `alt_reconcile_supersets()` pass (1) can no longer compute a sum at all. Its denominator can only come from `alt_dedup_window()`, whose constructor IS the window filter, with no argument that yields an unwindowed total, no default window, and anything wider than `ALT_DEDUP_MAX_WINDOW_DAYS` (200) rejected as an all-time sum in disguise. The >=50% verdict lives only in `alt_dedup_subset_verdict()`, which THROWS on a denominator not carrying window scope. Proved behaviour-identical to the old inline version over 5,469 randomised company groups / 3,914 marks, zero mismatches.
  **THE BRIEF WAS WRONG AND THE AGENT SAID SO, which is the behaviour to keep.** It was briefed to design against the Form D ($86bn) and M&A ($14bn) overstatements. Those are **the SIBLING talent tracker's incidents** (`../AI Talent Intelligence Dashboard/docs/HANDOVER.md`), not this repo's; this tracker counts jobs, not dollars. It grepped, found nothing, said so, and designed against the incidents this repo actually logs: RI 98,912 (real 9,891, count parser stripped non-digits), NJ **2.4 trillion** jobs (digit-concatenated county list), AT&T 78,788 (a Florida TEST notice), Coal India 73,800 (a by-2050 projection), Intuit 17 (real ~3,000, "17% of staff"), Oracle counted twice, and Spirit. **Never brief an agent on incidents from memory; cite the file.**
  **THREE CHECKS, in the existing `railway/data_integrity.py` registry** (one definition, imported by the test, ops_status and the digest; no parallel set). `headline_concentration`: the largest single counted row stays under a measured share bound (trailing-90d worldwide 20% against a live 3.51%, AI all-time 25% against 9.98%, worldwide all-time 1% against 0.30%, US all-time 2% against 0.86%) AND the block's denominator equals `totals.jobs`, so numerator and denominator travel together. `headline_movement`: day-over-day against a committed `railway/headline_baseline.json`, passing only if the rows that arrived or LEFT carry the move; the recorder **refuses to advance a failing slice**, because recording it makes today's defect tomorrow's normal. `dedup_denominator_scoped`: asserts the structural guard above is still in db.php and the reconciler still owns no local sum.
  **THE HONEST CEILING, written into the docstring rather than glossed:** the movement guard does NOT catch Spirit itself. A 4,000-job un-match on one company is inside daily noise at headline scale, and a bound tight enough to see it would fire every day. That drift is the per-company invariants' job.
  **`Result.pending` is a fourth word for a third state.** UNKNOWN that this environment cannot answer YET (build predates the field; baseline not yet written). Still UNKNOWN on the dashboard, the ledger and the exit code; it only stops every push reddening for the two minutes an FTPS deploy takes. `ops_status` prints `NOT WATCHING YET` and exits 3. Also fixed `Report.one_line()`, which rendered a shape guard's failure as `"... = None"` — the alert would have carried the label with the cause removed.
  **TWO COMPANY-PAGE DEFECTS THAT 400 TESTS, A GREEN DEPLOY AND A 7,491-URL SITEMAP COUNT ALL MISSED**, found by opening the page in a browser at 375px. (1) Boeing's first event listed "CA WARN notice (official WARN list; the notice was filed here...)" **twice**. The two hrefs are genuinely different (the state's rolling xlsx and its WARN landing page) and citing both is correct, but identical words pointing at different places reads as a duplicate-link bug. Links now say `(data file)` / `(state page)`. (2) That explanation then printed **316 times** on one page, roughly 28KB. Moved to one page-level note rendered only when the page cites a WARN source: Boeing went 366,153 -> 330,584 bytes. **The general rule: curl proves a page exists and says what you expect; only rendering it shows what it looks like to a reader.**
  **VERIFIED LIVE:** ver=2.19.238; `concentration` block present with `headline_jobs == totals.jobs`; `data_integrity.py` 7/7; `ops_status.py` ALL CLEAR exit 0 with 7 checks; `data-integrity.yml` green with the baseline committed on attempt 1; Boeing page 375px `scrollWidth == clientWidth` (no mobile overflow), unique meta description carrying real figures, canonical, `follow, index`, and BreadcrumbList + Dataset + CollectionPage JSON-LD. 478 offline tests green.
  **UNVERIFIED:** desktop rendering of the company pages was not seen (the browser pane here is fixed at mobile width); `move_floor` values are reasoned, not measured, because until `headline_baseline.json` existed nothing had recorded this site's day-over-day deltas — RUNBOOK says raise a noisy floor and write down why, never delete it and never fit it to today's move.
  **NOT DONE / NEXT:** (a) **#9 item 1 is IN FLIGHT** — a session is building the country / state-city / industry pages on the company-page template; if that agent did not land, it is the biggest SEO item left. (b) The private benchmark (`scratchpad/bm-live.html`) was NOT refreshed and needs the owner: it is local-only and its competitor figures are hand-maintained. (c) #9 items 4, 5, 6 (137KB inline CSS) and 7 (og:image is a 512x512 favicon) remain. (d) `recall_precision.py` still has no threshold and always exits 0.
- 2026-08-01 local (Claude Code) #17: **ONE COMPANY PAGE PER EMPLOYER. 29 pages -> 34,677, of which 7,491 are indexable. 2.19.233 + 2.19.234, both deployed and verified live.**
  **THE GATE WAS NEVER THE PROBLEM, and the audit (#9 item 3) had already said so.** 29 employers had a page against 38,086 employers that have at least one source-linked canonical event, and 17 of the 24 largest by event count had none. The indexability rule (>=2 sourced events) was sound; the THROUGHPUT was the defect. The autopilot considered only keys with >=3 sourced events and admitted **25 a week**, so the backlog grew faster than the indexer drained it. Nothing was misconfigured. The mechanism could not finish and had no way to say so.
  **NO NEW ROUTE.** `/company-layoffs/{slug}/` already existed with alias 301s, breadcrumbs and a self-served sitemap. Minting a second URL space would have orphaned the 29 live pages and their accumulated signals for no gain. What changed is coverage, correctness and the SEO head.
  **THE FLOOR, decided and written into the code** (`alt_company_directory_indexable_floor()`, one definition, read by admission + sitemap + page so they cannot disagree). A page EXISTS at >=1 source-linked canonical event and is INDEXABLE at >=2. Below the floor it is `noindex, follow`, not absent: the employer and the event are real, the URL is the thing we ask people to cite, and `follow` is the point because the links out are why a thin page is worth keeping. It is not indexable because with one event it repeats what the entry permalink already says, and ~27k near-duplicates is the mass-generated doorway pattern. **Result: 7,491 indexable, 27,186 noindex, 3,409 held for identity review** (generic or unusable names: these get NO page, which is the right answer for "Unknown Company").
  **THE PAGE'S ROWS NOW COME THROUGH `alt_api_query_compute()`**, and that is not tidying. Hand-written SQL is how this page had become **the one surface that never learned about supersets**: /aggregate, the report pages and the press page all append `superset_of = 0` and this did not, so a reconciled rollup row and the per-site rows it absorbed were BOTH listed and BOTH summed into the page total. Boeing measurably drops 324 -> 321 events. Three filters were added to the shared builder to make it possible (`company_key` exact identity, `sourced=1`, `exclude_supersets=1`), documented in ARCHITECTURE's Filter model and pinned by the existing contract test. Proven live: `company_key=boeing` = 324 against `company=Boeing` = 340, because the substring filter also catches "BOEING9" and "Boeing Compnay".
  **THREE DEFECTS FOUND ON THE WAY, none of them the assignment.**
  (1) **`alt_db_where()` was not alias-safe.** Every existing filter uses bare column names, which bind under any alias, so it had never mattered. A correlated filter must name the outer row, and **MySQL hides the real table name once an alias is given**, so `sourced=1` on `/conversion` (`FROM $table a`) would have been an unknown-column 500. `$alias` is now a parameter; that one caller passes it; `/conversion?sourced=1` verified 200.
  (2) **The autopilot's "most frequently reported name" was a `SELECT DISTINCT` taking whatever came back first.** The docstring had claimed modal selection for months. Now actually modal, ties to the shorter name.
  (3) **Company pages forced a cache bypass** (`DONOTCACHEPAGE` + `nocache_headers()`). Invisible at 29 URLs; at one per employer it makes every crawler hit an origin request on a host that returned 504 twice on 2026-07-31. It never bought freshness either, since the data sits in a 5-minute transient regardless. Rendered pages are cacheable for 10 minutes now; a MISS stays uncacheable, because that slug becomes real the moment the indexer admits it.
  **THE ONE THAT ALMOST SHIPPED SILENTLY, and the lesson worth keeping.** Dropping the "qualifying events disagree on the company name" park was correct and, on its own, **completely inert**. A parked key already had a `pending` row, the candidate query counted ANY directory row as "already mapped", and so the employers the old rule had caught could never re-enter the funnel. That set is not random: **name variants come from scale**, so the rule had selected almost exactly the largest employers. Boeing files as "Boeing", "Boeing Co", "Boeing Company", "The Boeing Company" and two misspellings; 324 events bought it a pending row and no page. **`/company-layoffs/boeing-company/` was still a 404 after the coverage work landed and I only caught it by checking the audit's named examples against the live sitemap rather than trusting the coverage counter.** Fixed in 2.19.234; the identity sanity gate still runs on every reconsidered key, so nothing is promoted that could not be admitted fresh. **General rule: when you retire an admission rule, the records it already rejected do not re-enter the funnel by themselves.**
  **ALSO:** meta description on company pages (there was none, #9 item 4) plus a `Dataset` node on indexable pages only, `isPartOf` the tracker dataset so it reads as a slice and not a rival dataset with the same name; the **1,798 orphan entry permalinks now have a path** (#9 item 2, the company half) since the company page links each entry and each entry links back up; the sitemap query ran one correlated COUNT per approved directory row (fine at 29, a timeout at thousands) and is now a single grouped join; the public `/company-directory` listing is paged and carries a `coverage` block so the claim is checkable from outside without a key; and the health page publicly claimed a "three or more" threshold while the gate was two.
  **VERIFIED LIVE, not asserted:** ver=2.19.234; sitemap 7,491 URLs with correct `X-Robots-Tag`; Boeing 321 events / 475 source links / 175 "Filed as" variants shown rather than smoothed over; a below-floor page 200 + `noindex, follow` + absent from the sitemap + explaining itself; an entry permalink carrying its company backlink; `/query` unfiltered still 63,715 so the new params changed no default. 400 offline tests green (`test_company_directory_guards.py` went 5 -> 28).
  **UNVERIFIED, stated plainly:** (a) **no browser in this session** — no company page has been LOOKED at, at any width; the template is a list rather than a table specifically to avoid the 375px overflow bar, but nobody has seen it render. (b) **No local PHP/MySQL test DB** (`scripts/setup_test_db.sh` needs a MySQL this machine does not have), so the new SQL was proven by `php -l`, by reasoning, and by live behaviour after deploy, NOT by a byte-identical diff against the old queries. (c) 7,862 employers sit above the index floor but only 7,491 are indexable; the ~371 gap is the identity gate plus slug collisions and was not itemised.
  **NOT DONE / NEXT:** (a) **#9 item 1 is now the biggest single SEO opportunity left and is untouched** — `?country=`/`?state=`/`?industry=` still return byte-identical HTML on one canonical, 120 facet values collapsing onto one rankable page. The company-page work is the template for it: rewrite rule, server-rendered rows through the query layer, unique title/description, self-canonical, own sitemap. (b) #9 items 4 (titles/descriptions on the OTHER pages), 5 (frozen `dateModified`, `author` = admin), 6 (137 KB inline CSS) and 7 (og:image is a 512x512 favicon) remain. (c) The **second half of #9 item 2 is deliberately NOT done**: making the `layoffs` CPT noindex by default and sitemapping only rows that clear a content bar is an indexation-policy change over 1,798 live URLs and wanted its own session, not a rider on this one. (d) The private benchmark (`scratchpad/bm-live.html`) was NOT refreshed. (e) `recall_precision.py` still has no threshold and always exits 0 (flagged #13-#16). (f) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables (flagged #13-#16).
- 2026-07-31 local (Claude Code) #16: **THE TWO TRACKERS NOW SHARE ONE CARD, AND A BUILD GOES RED WHEN THEY DRIFT. 2.19.232 here, 1.60.1 in the sibling, both deployed and verified live.**
  **THE DEFECT WAS NOT THE MISMATCH.** The owner screenshotted the sibling talent tracker's results list, liked it, and asked for this one to match "exactly". By the time an agent looked, the sibling had already changed its own labels, so neither side could say which design was current. Shipping matching pixels once would have fixed nothing: they had drifted once and would drift again inside a fortnight. **The inability to say which one was current was the defect**, and that is what this fixes.
  **MECHANISM: a contract as DATA, not shared code.** `docs/card-contract.json`, **byte-identical in both repos** (proven at the git level: both `origin/main` blobs hash to `02f957df`, and both files to sha256 `5ce62ea8…`). It holds the structure, the class suffixes, the badge order, the four direction words, the shared not-stated strings, the two a11y rules and the mobile rule. **Shared code was rejected** — different repos, tables, REST namespaces, plugins, deploy paths and first-paint languages (this one inlines `ALT_BOOTSTRAP` and renders in JS; the sibling renders in PHP), so a library across that boundary buys a coupled release and a card change blocked on the other side's deploy. **A convention in the docs was rejected** for the reason this repo keeps relearning: a rule nothing enforces is one that has already been broken and nobody has noticed.
  **THREE THINGS HOLD IT, and each covers what the others cannot.** (1) `railway/tests/test_card_contract.py`, offline, every push — 18 tests reading the contract and asserting the markup this repo actually renders satisfies it; it cannot see the sibling. (2) The digest recorded **twice** in-repo (the test and the TECHLOG spec section), so an accidental edit fails and a deliberate one forces you to notice it is a two-repo change. (3) **`.github/workflows/card-contract.yml`**, which fetches the sibling's copy and reddens while the two differ — the only mechanism that can see across the repo boundary, which is why it needs a network and lives in CI rather than the offline suite. It runs on a **schedule** as well as on push, because a change made in the SIBLING produces no event here. A fetch failure exits **non-zero**: could-not-check must never read as agreement, same rule as `ops_status`/`ci_status`.
  **PROVEN, not asserted:** the cross-repo job ran green on its first real push in BOTH repos; and its RED path was exercised locally against a one-word mutation of the live file (detected, would exit 1), as was the unreachable path (404 → curl exit 22, never a pass). Changing the card is now a four-step job and you cannot do three and ship — edit the contract, update the digest in the test and TECHLOG, change the markup, copy the file across; miss the last and **both** repos stay red.
  **WHAT CHANGED HERE.** The layout was already the screenshot's, so the change is the badge row: three contract badges in a fixed order (**direction, evidence, amount**), then this product's own (AI attribution, reason tags). New direction badge carrying the sibling's vocabulary — **Cutting Roles** when the record names a headcount, **Headcount Not Stated** when it does not. The keys are ours and DERIVED, because this tracker has no `signal_direction` column; the four strings are shared. `Adding Roles` and `Pay Change` never occur here and are absent by declaration, never renamed. The mapping is justified: the sibling's `neutral` bucket is defined by its own comment as "the source says nothing about headcount", and a layoff row carrying no count is that exact state. **The amount badge is now OMITTED when there is no amount** instead of a pill reading "Count not stated" — the direction badge already says so, and two badges saying one thing was a duplicate. **Title Case on those four is deliberate and on the record** (the sentence-case house rule still governs everything outside them): the owner has asked for Title Case three times and the sibling has a PHP test enforcing it, so flipping it is a contract change, not a tidy-up.
  **A11Y HELD, and is now pinned.** The detail expander stays a real `<button type=button aria-expanded>` (it was a mouse-only `<tr>` click before 2.19.226) and the test asserts the button AND the handler that keeps `aria-expanded` in step. No element in the card carries an `aria-label`, and the test refuses to let one appear over visible text — the defect the sibling shipped and fixed. **375px is checked by CAUSE, not symptom**: no card rule may pin a width, free-text fields must wrap. Deliberately NOT `scrollWidth === innerWidth`, which passes on a clipped page and is meaningless here anyway against the theme's inline `html,body{overflow-x:hidden}`.
  **IN THE SIBLING (1.60.1), for the record:** its results table became this same card at every width (it was a 7-column table that turned into cards below 860px through a stack of `@media` rules — two descriptions of one layout); its four sortable column headers went with the table but **every ordering they offered is now an option on the one sort control, on the same `sort` parameter**, so no old share link broke; and a **THIRD** direction vocabulary was found still live on its employer pages ("Cutting back" one click from "Cutting Roles") and folded into the shared map. 2,752 tests green there, 377 here.
  **UNVERIFIED, stated plainly:** there is no browser in this session. The sibling's cards are **server-rendered** and were confirmed in the live HTML (50 cards, every contract slot, zero `aria-label`, 45 `<time datetime>`, 0 leftover table markup). **This repo's cards are painted by JavaScript from `ALT_BOOTSTRAP`**, so the live check could only confirm that `layoffs.js?ver=2.19.232` is served and carries the new vocabulary and the `alt-card-dir` class. **Nobody has looked at the rendered result on this tracker**, at any width. That is the one thing worth a human's thirty seconds.
  **NOT DONE / NEXT:** (a) the 2.19.219-220 SEO queue (items 1-7 in #9) is STILL untouched and still the priority — four sessions running now. (b) The private benchmark (`scratchpad/bm-live.html`) was NOT refreshed this session; nothing here changes a competitor-facing number, but the card redesign is a presentation dimension the benchmark has a column for. (c) `recall_precision.py` still has no threshold and always exits 0 (flagged #13, #14, #15). (d) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables (flagged #13, #14, #15). (e) The sibling's disabled `CI failure alert` workflow from #15 is still the owner's to re-enable.
- 2026-07-31 local (Claude Code) #15: **THE ALERTING SYSTEM DEPENDED ON THE HOST IT WAS ALERTING ABOUT. Fixed in BOTH repos; nothing here needed a plugin deploy, so ALT_VERSION is unchanged at 2.19.231.**
  **THE DEFECT, proven in production the night before.** 00:48-00:55 UTC Bluehost answered 504 for everything under `/blog/` (second window that day; ~6 min in the afternoon). In the sibling talent tracker: `enrich` failed because it could not reach the host -> `drain-writers` correctly went red refusing to auto-retry a failed writer -> the CI failure alert fired for both and **POSTed to `/alert`, a REST route on the host that was down**. "HTTP 504 from /alert" x4, "CI alert could not be delivered" x4. The alarm was mute at exactly the moment it was needed — the same failure class this project keeps finding, one layer up. **The outage was found by the OWNER in a browser.** `railway/ci_alert.py` here is the same design against the same host; it simply had no red run that night.
  **AMPLIFICATION was the second, separate defect.** The alerter exited **1** on a failed POST, on the reasoning that a silent notifier is worse than none. True, and it made an outage manufacture red runs which manufacture alerts which also fail — and it told a session the ALERTER was broken when the alerter was working perfectly and the host was down.
  **MECHANISM: a durable, committed outbox, not a longer backoff.** `railway/alert_outbox.py` + `railway/alert_outbox.json`. A failed POST is retried in-run for TRANSIENT statuses only (5xx/timeouts; a 401 or 404 is a settled no and retrying it just makes the run longer), then HELD in a file that outlives the runner and the outage. New `alert-drain.yml` delivers it every 30 minutes — and **an empty outbox makes no request to the host at all**, so the normal tick costs nothing and adds no load. `railway/ops_status.py [4b]` shows what is held; 12 failed attempts makes it ACTION NEEDED, because a queue that quietly never drains is the original silence with extra steps. **Holding exits 0** — that is the explicit break in the loop, and both the module and CLAUDE.md say so in as many words so nobody restores the `exit 1`. Non-zero survives for exactly one case: could neither deliver NOR hold. A recovery queued behind its own un-sent failure CANCELS both, so an outage that heals never mails a stale RED followed by a stale RECOVERED.
  **WHAT WATCHES THE HOST NOW, and why it is not here.** Both trackers share one Bluehost account, so the host is watched ONCE — in the sibling: `host-watch.yml` GETs one public REST route every 15 min (cache-busted, so Cloudflare cannot answer for a dead origin), records a committed ledger, and surfaces it in its `ops_status [2f]`. Three consecutive failed runs = SUSTAINED, which opens **one GitHub issue** — the channel that is not on the host. Deduped by construction: opening and closing each email once, every update in between edits the body and mails nobody (2 emails per outage against the ~15 raw run notifications GitHub sent for one defect). Neither of the 2026-07-31 windows would have opened one, which is correct — both healed in under ten minutes and an alarm that fires on every wobble gets filtered. A down host deliberately does NOT redden that watchdog. **A second identical watchdog here was considered and rejected:** it would double the load on a host that has shown its ceiling twice in a day and send two emails per outage. This repo's own check remains `ops_status.py [1]`, at session start, independent of the sibling — it printed `UNREACHABLE: HTTP Error 504` during the window.
  **⚠️ ONE THING ONLY THE OWNER CAN UNDO, and it is the most important line here.** In the SIBLING repo, `CI failure alert` was **disabled by hand at 2026-07-31T01:01 UTC**, two minutes after it failed four times — an entirely reasonable reaction to an alarm that had started amplifying an outage, and nothing would ever have reminded anyone to turn it back on. A disabled workflow is not red, produces no runs to go stale, and appears only in `gh workflow list`. **The sibling's `ci_status.py` now goes red on it** (new `MUST_STAY_ON`), but re-enabling is a repo setting and was left for the owner: `gh workflow enable 'CI failure alert' -R dk-forge/talent-intelligence-tracker`. **Until that is run, the sibling's red runs reach nobody.** This repo's alerter is ACTIVE and was verified green end to end tonight.
  **ALSO, in the sibling: the archive cadence came down from every 3 hours to every 8** (`20 */8 * * *`). The arithmetic: 444 URLs confirmed absent from Wayback, ~20 snapshots a run, so 8 runs/day clears it in ~3 days and 3 runs/day in ~8. Eight days is the cheap side of the trade, because each run holds the single `talent-collect` write lock for up to 25 min — 200 min/day at the old cadence against 75 now — and everything queued behind it (collect, enrich, backfills) POSTs to the WordPress host and lands in a burst when the lock clears. **THIS repo's own hourly archive sprint, reverted 2026-07-30 after runs were handed 0, 2 and 7 candidates, is the precedent that decided it:** the 444 is a real backlog today and will not be one next week, at which point every extra slot is a 25-minute lock window spent on a no-op.
  **VERIFIED LIVE, not asserted:** `host-watch` dispatched twice against production (HTTP 200 in 2.1s, ledger committed to main); `alert-drain` dispatched here (`Nothing is held. No request was made to the host.`); the new "Hold the alert" step observed on a real `ci-alert` run (`The alert was delivered; there is nothing to hold.`); 393 offline tests green here, 2,663 in the sibling.
  **A BUG THE FIRST LIVE RUN CAUGHT, worth remembering:** `git add a b` where `b` does not exist fails the whole command and stages **NEITHER**. The sibling's first watchdog run probed, wrote its ledger, and reported "Nothing new to record" because `data/alert_outbox.json` correctly did not exist yet. Add paths one at a time in any commit step that touches a file which may legitimately be absent.
  **NOT DONE / NEXT:** (a) the 2.19.219-220 SEO queue (items 1-7 in #9) is STILL untouched and still the priority — three sessions running. (b) The held-alert path has never been exercised by a real outage; it is proven by unit test and by the empty-queue live run, not by a 504. (c) The sibling has genuinely red runs from tonight's outage (`collect`, `enrich`, `drain-writers`, `deploy-robots`, `collect national press`) plus four failed writer-queue tickets — none of them mine, all of them invisible to the owner until that workflow is re-enabled. (d) `recall_precision.py` still has no threshold and always exits 0 (flagged #13, #14, unchanged). (e) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables (flagged #13, #14, unchanged).
- 2026-07-30 local (Claude Code) #14: **A RED RUN NOW EMAILS THE OWNER, DEDUPED BY CAUSE. 2.19.231, armed and proven end to end against the live endpoint.** The owner's words: "I don't get notified of workflow failures. I only see them when I check, and I've been checking sporadically." #13 made ops_status report whether the DATA is correct; this makes a red run reach a PERSON. The Spirit assertion reddened CI eight times over an afternoon and the signal died in GitHub Actions.
  **MECHANISM, and why not the obvious two.** One `workflow_run` listener (`.github/workflows/ci-alert.yml`) subscribing to `workflows: ['*']`, not an `if: failure()` step in each of 66 workflow files. Sixty-six edits is sixty-six chances to forget one, and the one you forget is the one that breaks; a reusable workflow has the same coverage-by-diligence problem because it still needs a `jobs:` entry everywhere. Two properties decided it beyond the edit count: (a) `workflow_run` keys off a run COMPLETING, not off how it started, so it covers `schedule` runs — which is most of this repo's data jobs; (b) it runs on its own runner, so it cannot be taken down by the OOM/timeout/cancel that took down the run it is reporting on, and it can never mask the original failure. **`workflows: ['*']` was verified empirically, not assumed** — the first listener runs fired for "Tests" and "Deploy WordPress plugin" within two minutes of the push. Free: the repo is public.
  **DEDUPE BY CAUSE IS THE FEATURE, not a refinement.** `railway/ci_alert.py` pulls the terminal assertion out of `gh run view --log-failed`, then normalises numbers, timestamps, SHAs and runner paths OUT before hashing. Replayed against the seven real red runs of that afternoon: **six collapse to one key** (`tests:main:c72edfc2f50f2da0`) and the seventh, a genuinely different assertion, correctly gets its own. So six emails become one, and a second real breakage is never swallowed. The open/resolved state lives server-side in `/alert` as an **option, not a transient** — an evicted transient either re-mails an alert already read or silently swallows the RECOVERED, and neither failure announces itself.
  **PROVEN END TO END, four dispatches through the live production endpoint** (new `ci-alert-selftest.yml`, manual-dispatch only, keep it): marker 101 fails -> `emailed the owner`; marker **102** fails -> **same key, `suppressed: this exact cause is already open`** (this is the load-bearing proof — a DIFFERENT number, one cause); `pass` -> `resolve ci-alert-self-test:main: emailed the owner` (RECOVERED); marker 103 fails -> **`emailed the owner` again**, proving the alarm CLEARED rather than went permanently quiet. That last one matters: an un-clearable alarm is what the newsapi 2-day ceiling on a weekly job already cost us.
  **ops_status.py gained `[4] RECENT CI`** — latest run per workflow on main, with the actual assertion and the run URL, contributing to exit 2. It shares `ci_alert.extract_cause` with the emailer for the same reason #13 put the invariants in one registry: the dashboard and the email must never describe one failure two ways. Sections renumbered, SOURCES -> `[5]`, BENCHMARK -> `[6]`. **Honest degradation:** no gh / no auth / no egress prints `UNKNOWN — could not read CI state` and exits **3**, never a clean bill of health; proven by running with `gh` off PATH. Note the distinction from `[3]`, which deliberately re-queries live rather than reading a CI verdict: a cached conclusion is worthless about DATA that changes with no commit, but it is the PRIMARY SOURCE about workflows.
  **⚠️ A TRAP THAT COST ME THE SIBLING'S PUSH TWICE, worth more than the feature.** In the sibling repo a `git rebase --continue` turned my commit into a MERGE commit, and **`git rebase` silently DROPS merge commits by default** — so `git push` was a no-op that returned 0, and my own "PUSHED" echo printed anyway. Two rounds of work looked landed and were not. **`git rev-parse HEAD` is not proof of a push.** Verify with `git fetch && git ls-tree origin/main <path>`. This is the same class of false-green this project keeps paying for, and I walked straight into it while building the alarm for it.
  **NOT DONE / NEXT:** (a) the 2.19.219-220 SEO queue (items 1-7 in #9) is still untouched and still the priority. (b) `recall_precision.py` still has no threshold and always exits 0 (flagged by #13, unchanged). (c) `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables (flagged by #13, unchanged). (d) The 14-day "STILL FAILING" reminder for a cause that stays open is implemented but has NOT been observed firing — it cannot be without waiting a fortnight or clock-shifting the host.
- 2026-07-30 local (Claude Code) #13: **ops_status NOW REPORTS WHETHER THE DATA IS CORRECT, NOT JUST WHETHER THE COLLECTORS RAN. 2.19.230.** Ran alongside #12's dedup work: the baton was HELD for the Spirit fix, so this touched only the health/ops surface (data_integrity.py, ops_status.py, health_digest.py, health.js meta, db.php retirement date) and never the dedup path; the version bump was taken after #12 released at 2.19.229.
  **THE GAP.** `test_dedup_live` caught Spirit reading 11,069 instead of ~7,069 and reddened CI five times, while `ops_status.py` — the tool CLAUDE.md tells every session to run FIRST — printed `ACTION NEEDED: 1 item(s) -> newsapi stale` and said nothing about a company overstated by 4,000 jobs on the live site. It read the source-health ledger only, which answers "did the collectors run?" and cannot answer "is what they produced correct?".
  **THE DESIGN, and why not the alternatives.** Invariants extracted into `railway/data_integrity.py`, imported by the test, ops_status AND health_digest — one definition, so a bound can never drift between the guard that reddens CI and the dashboard that says all is well (that drift would be this same bug one level up). **Not shelling out to pytest:** ops_status is documented fast/read-only/stdlib-only/key-free/offline-capable, and unittest collapses "could not check" into a green run via skipTest — fatal for a dashboard. **Not reading the last CI conclusion:** needs gh+auth (dies exactly in the egress-blocked case ops_status exists for), but the real objection is that it is a CACHED VERDICT ABOUT A PAST STATE OF THE DATA — this data changes with no commit at all (WARN daily, reconcile at 16:40 UTC), and the Spirit defect appeared when a running all-time sum crossed a threshold. That is the sibling repo's "Nothing queued, nothing lost" failure exactly.
  **HONEST DEGRADATION is the load-bearing part.** Three states, never two: PASS / FAIL / **UNKNOWN**, and UNKNOWN is never folded into PASS. FAIL outranks UNKNOWN outranks silence. Proven end to end, not asserted: a simulated proxy-403 session prints four UNKNOWNs and `DATA INTEGRITY IS UNKNOWN, NOT CLEAR` at exit 3; a `{}` body (site answers, no totals) refuses to pass and exits 2; a replayed 11,069 Spirit payload prints FAILING and exits 2; zero jobs is a FAIL, not a pass under the bound. Five `DegradationContract` tests pin all of it and need no network.
  **Exit codes:** a failing invariant exits 2 (never 0) and prints before the source-staleness item, because a stale collector is data we have not gathered while a failing invariant is a wrong number already published. A run that could not verify exits 3 and explicitly refuses to say ALL CLEAR.
  **Fed to the owner without CI:** new `data-integrity.yml`, daily 17:30 UTC — deliberately 50 min AFTER reconcile-supersets (16:40) so it checks the data as that pass leaves it — writes the verdict to the public health ledger as `data_integrity`. **This also closes a gap nobody had noticed: `test_dedup_live` only ever ran on push/PR, so on a quiet week the live guard did not run at all.** health_digest leads with "WRONG NUMBER LIVE" and now fails on it, but the code says in as many words that WEEKLY is up to 7 days too slow for a wrong published number and must stay the backstop, not the alarm.
  **NEWSAPI VERDICT: neither broken nor retired — a retired collector's name worn by a live weekly job.** `newsapi` was stood down 2026-07-25, but `news_catchup.py` was missed and kept POSTing health under that id every Monday (last run 2026-07-27, success, 113 articles). Two consequences: (a) the retirement was **silently void**, because `alt_retired_sources()` deliberately refuses to mask a row whose last run POSTdates the retirement, so the public health page kept advertising it as a live "Twice daily · Worldwide" collector; (b) it carried a **2-day ceiling on a WEEKLY job**, so it read stale 5 days out of 7 forever — and that un-clearable amber was the only thing on ops_status the day Spirit was wrong. Fixed: news_catchup reports as `news_catchup` @ 9d with its own health.js label, the `newsapi` retirement date moved to 2026-07-30 so the frozen row finally masks, and a test pins the id. **Rule now in CLAUDE.md: retiring a source is THREE steps — drop it from cron.py, add it to alt_retired_sources(), and stop every remaining path that posts health under that id. Step 3 was missed and silently voided step 2.**
  **Note the honest limit of the acceptance test:** the integrity check was RED for Spirit at 20:57 UTC (11,069, captured) and #12's 2.19.227/229 fix landed while this was being built, so it now reads PASS at 7,069. The RED path is therefore re-proven by replaying the captured payload, not by leaving the site broken.
  **Next:** unchanged — the 2.19.219-220 SEO queue (items 1-7 in #9), crawlable country/state/industry views still the biggest single win. Two things this session surfaced and did NOT fix: `recall_precision.py` computes precision/recall but has **no threshold and always exits 0**, so a 40% recall week looks identical to a 95% one; and `health_digest.MAX_AGE_DAYS` / `ops_status.MAX_AGE` are still two hand-maintained tables that have drifted before (they agree today) — worth collapsing into one shared registry the same way the invariants just were.
- 2026-07-30 local (Claude Code) #13: **SUPERSET DEDUP WAS ROTTING BY DESIGN. 2.19.227-229, applied and verified live. Spirit US-2026 11,069 → 7,069, all four live guards green.**
  **THE BUG, because the shape of it matters more than the row.** `alt_reconcile_supersets` pass (1) established "these document the same event" with a ±45-day proximity check, then ran the ≥50% plausibility test — and the marking — against the company's **ALL-TIME WARN sum**. That denominator only grows, so **every match in the table sat on a fuse.** Spirit's May-2026 news total of 4,000 covers 6,109 jobs of May-2026 WARN sites, but was being measured against 8,922 jobs of Spirit WARN notices reaching back to 2020. The margin had been **38 jobs** (4,000 vs half of 7,923); the day the all-time sum crossed 8,000 the pair silently un-matched and the news row started stacking. The daily job had been reporting this for four days as `members_marked` drifting 668 → 543 → 534 → 519 and nobody could see which pairs were falling out, because the response was three totals and no diff.
  **THE BUG RAN THE OTHER WAY TOO, and that half was bigger.** When a news total exceeded the all-time sum, it marked that company's WARN rows **from unrelated years** as members of the one event. **Boeing's real October-2024 announcement of 17,000 was itself marked a subset of a single WARN row and counted ZERO.** Fixing the window restores 113,786 jobs across 43 employers (Amazon 16,951, Tesla 14,000, Microsoft 12,098, Meta 11,000, Intel 7,987, Cisco 5,600) and suppresses 60,367 across 64 that were double-counting (United Airlines 18,038, Spirit 5,128, American Airlines 4,362, Meta 3,969). **89 companies moved; the live headline went 20,111,915 → 20,166,034.** That number is a correction, not growth — the private benchmark carries a dated line saying so, because a future read would otherwise see it as coverage catching up.
  **A SECOND DEFECT IN THE SAME FUNCTION: no SEC filing had ever entered the dedup.** `in_array($st, ['news','erm','8k',…], true)` against EDGAR's `source_type = '8K'`. A strict compare, an uppercase literal everywhere else in db.php, and a silent miss for the life of the feature. An 8-K company-wide total stacked on its own WARN sites permanently.
  **THE TEST BOUND WAS NOT TOUCHED.** It is still `< 11,000`. It caught this exactly as designed and the root cause is now written into the test's own comment.
  **TOOLING, and why it is not gold-plating.** Working out why one row was not being marked took most of the session, because nothing exposed what the reconciler *sees* — I was inferring `company_key` from `COUNT(DISTINCT …)` in aggregate responses. `probe=<employer>` now dumps every input row with its key and its mark, and it immediately surfaced something the inference could not: **Spirit's TX, BWI and O'Hare notices key as `spirit airlines dfw may 2026`, `spirit airlines bwi`, `spirit airlines at o hare airport`** — rows that look like the same employer and never meet, because the WARN filer wrote a site name into the company field. Also: `changes` (marks that differ from stored) is now in every response, so a silent un-match shows as churn on a quiet day. **And a trap worth remembering twice:** the `detail` list was capped at 500 against 576 changes, which dropped the Spirit row from the diff and **made a working fix look broken for two deploys**; the cap is 2000 now and the workflow prints "listing N of M (truncated)". A bounded diagnostic must say when it is bounding. Separately, an Actions log line big enough (a full `detail=1` body) is **silently dropped** by the log uploader — the run goes green and prints nothing.
  **⚠️ ANOTHER SESSION WAS WRITING THIS REPO AT THE SAME TIME, while the baton said I held it.** Mid-session, `railway/data_integrity.py`, `.github/workflows/data-integrity.yml` and edits to `ops_status.py` / `health_digest.py` / `news_catchup.py` / `test_dedup_live.py` / `assets/health.js` / `db.php` (a newsapi-retirement fix) appeared in my working tree. **A `git add -A` of mine swept `data_integrity.py` onto main alone, which turned CI red** (it reports health under an id whose `meta{}` label was still uncommitted). I untracked it with `git rm --cached` — the file is still in the working tree for that session to land with its companions — and CI is green on my head. **Those changes are UNCOMMITTED and NOT MINE; do not attribute or discard them.** Lesson for everyone: `git add -A` is unsafe in this repo; add explicit paths. And the baton is only as good as the sessions that read it.
  **NOT DONE / NEXT:** (a) the entity-key split above — Spirit's TX+BWI+O'Hare sites, the known Meta pair, and whatever else `probe` would show — is still open and is now the biggest remaining source of quiet double-counting; it needs the re-key repair, which changes dedup hashes and so needs purge + re-import, not an upsert. (b) The exact row that tipped Spirit over the threshold is **unrecoverable**: `wp_alt_layoffs` has no `created_at`/`updated_at`, so "when did this row arrive" cannot be answered at all. That is worth fixing on its own merits — it would have turned an hour of archaeology into one query. (c) The 2.19.219-220 SEO queue (items 1-7 in #9) is still untouched and still the priority; crawlable country/state/industry views remain the biggest single win.
- 2026-07-30 local (Claude Code) #12: **THE RESULTS TABLE IS NOW A LIST OF CARDS, AND DATATABLES IS GONE. 2.19.226, deployed green on the matching SHA, live and verified by curl.** Owner ask, looking at the sibling talent tracker: "why can't we have the cards look just like this exactly? And we have the source link and wayback link for both?" Nothing was copied from the sibling and the sibling was not modified; it was read, then equivalents written in `alt-` classes.
  **READ THIS FIRST — the brief I was given was wrong about the code, and the correction matters more than the feature.** I was told DataTables was a client-side library sorting a server-side dataset, so "largest cuts" only ever ordered the loaded page, and told to write that up as a real defect. **It is not true.** The instance was `serverSide: true` and its ajax callback posted `sort`/`dir` to `/query`, where `alt_api_query_compute` does the `ORDER BY` and `LIMIT/OFFSET` over the whole filtered set. **Sorting has always ordered all 63,670 events; no reader was ever shown a wrong view; no incident entry was written for a defect that does not exist.** DataTables was drawing the pager and the sortable headers and nothing else, which is precisely why it could be deleted without replacing any capability. If a future brief asserts a defect, check the code before writing it into TECHLOG.
  **What the removal bought, measured on the wire:** `jquery.dataTables.min.css` (2,067 B, **render-blocking and cross-origin**) and `jquery.dataTables.min.js` (29,230 B) both gone; our own assets moved +1,383 B (JS) and −218 B (CSS), so **net −30,132 B of transfer**. **Render-blocking stylesheets on the flagship page went 5 → 4, and the one removed was the only cross-origin one** — that closes the open perf item in #9's queue (item 6, "render-blocking DataTables CSS from cdnjs"). The 137 KB of inline CSS in `<head>` is **untouched and still the biggest remaining perf item**; it is not ours (21 blocks from the theme and other plugins) and needs its own session. jQuery is no longer a dependency of `alt-js` (six call sites were the only ones in the file), though the theme still loads it for `jquery.sticky-kit`, so that is not a byte saving.
  **Scale was never the problem and I deliberately did not "solve" it.** One page of cards exists at a time (25 default, 10/25/50/100), paged server-side against the same endpoint. **No client-side virtualisation** — that would be the same mistake in a new shape. `ALT_BOOTSTRAP` still gives a zero-fetch first paint: `queryParams()` builds the same four keys the old ajax callback did, so `takeBoot` still matches. **Note the coupling:** `alt_tracker_bootstrap_payload()` in db.php and `queryParams()` in layoffs.js must produce byte-identical params or the zero-fetch paint silently becomes a fetch; there is a comment at both ends now.
  **A dead option removed on the way:** `verification_level` was in the JS `sortFields` array but **not** in the PHP `$sortable` allowlist, so clicking the Source header had always silently fallen back to `layoff_date`. The `#alt-sort` select (which already existed) is now the only sort UI, and `setSort()` no longer names a column INDEX — the sort options were coupled to the table's column order.
  **Accessibility went forward.** The expander was a click handler on `<tr>`: mouse only, no `aria`, no focus ring. It is a real `<button aria-expanded>` per card now, keyboard reachable, whole-card click kept as a mouse convenience. `<ol>` because the order is the content; `aria-busy` on load; `aria-current="page"` on the pager. Card and detail links set their own colour and `:focus-visible` — they had been inheriting from the deleted `table.dataTable a` rule, which is the kind of thing that goes missing silently when a selector is removed.
  **The archived copy is now the sibling's exact shape** (` · archived`, quieter ink, same `title` text), always a SECOND link beside the publisher's, never a swap. Ours additionally keeps an **honest dated pending note** where no snapshot exists, which the sibling has no equivalent of.
  **VERIFIED, and how:** a jsdom harness drives the real `layoffs.js` against real `/query` payloads — 44 assertions, all green: zero-fetch first paint, `sort=job_count&dir=desc` on "Largest cuts", `page=2&per_page=25` on Next, **`country_basis=any` on the results list and NOT on `/aggregate`** (the documented split is intact), exports still filtered + inclusive-basis + relabelled, chips, empty state, and HTML-injection payloads rendering as literal text. Live: 2.19.226 served, `#alt-cards` and `#alt-pager` in the HTML, `#alt-table` gone, zero datatables requests, deployed JS parses and contains the card code, and all 7 tracker pages plus 3 company pages return 200.
  **NOT VERIFIED — and one specific trap a future session must not fall into.** No browser here, so **how it looks is unchecked**: the card at 375px, badge-row wrapping, and horizontal bleed. jsdom does no layout. **Do not validate this with `scrollWidth === innerWidth`** — and here that is worse than the generic warning: this site already ships an inline `html,body{overflow-x:hidden}` guard (from the theme or another plugin, not ours), so **that check passes on this domain no matter how badly a card overflows.** Only eyes or a real screenshot can settle it. The owner is checking.
  **Left open, deliberately:** (a) **the sibling still renders no archived links on its live page** — its `archive_url` support is in its 1.55.0 code but a curl of its live results list found zero, matching its own TECHLOG note that every archiving run so far was a dry run; that is a change for whoever holds ITS baton, and I did not touch it per the standing read-only rule. (b) **The brief's description of the sibling's card did not match the sibling** (it described a serif employer name, an industry field, a `$250M` money badge and a blue headline with an arrowed source link; the live sibling has an uppercase sans eyebrow, no industry, no per-row money badge, an ink headline and a middot with no arrow — its money badge and left-rail shape live on other surfaces). I built to the sibling's real results card plus the brief's rail and job-count badge and wrote the differences into TECHLOG rather than silently picking one. **If the owner wanted the company-profile timeline card instead, that is the surface to point a future session at.** (c) `ops_status.py` still reports **newsapi stale** — unchanged from the start of this session, pre-existing, not touched.
  **Next:** unchanged priority — the 2.19.219-220 SEO queue (items 1-7 in #9), with **crawlable country/state/industry views still the biggest single win.** One thing this change makes newly cheap: the card headline now links each entry's permalink when it has one, which starts closing #9 item 2 (1,798 orphan permalinks that `/query` returned and nothing rendered) — the remaining half of that item is the noindex-by-default gate and sitemapping. Also worth noting for whoever does SSR work: the cards are still client-rendered into an empty `<ol>`, exactly as the table's `<tbody>` was, so **no SEO regression, but no gain either** — server-rendering that first page of cards is now a small, self-contained job and would put real rows in the crawled HTML for the first time.
- 2026-07-29 local (Claude Code) #11: **CLICK-TO-FILTER VERIFIED BY ACTUALLY CLICKING IT; link/archive infrastructure confirmed healthy; no code changed here.** This session's build work was almost entirely on the SIBLING talent tracker (see its own `docs/TECHLOG.md` — do not import its state into this repo). What happened HERE:
  **The #10 "HONEST GAP" is now closed.** #10 shipped 2.19.221 without ever exercising a click. Driven in a real browser this session: clicking **Sales & marketing** in the roles chart filtered the page and wrote `?years=2026&roles=sales_marketing`, the visible Roles dropdown updated to match (so a reader can see WHY the page narrowed), `aria-pressed` read `true` on the active bar, a second chart click **stacked** rather than overwrote (`&company=Salesforce`), and a second click on each toggled it off leaving a completely clean param-free URL. Also confirmed live: **123 bar buttons, zero disabled** — before #10, three whole charts were dead buttons.
  **A measurement gotcha worth keeping:** reading `aria-pressed` straight after `.click()` returns the STALE node — the card re-renders, so the reference must be re-queried. First read said `false` and was wrong.
  **Link-rot infrastructure verified running, not assumed:** `Broken-link check` (daily 10 AM ET) green, `Source-archive backfill` green and running hourly, `Archive WARN sources to Wayback` (Mondays) present. **The sibling has NONE of this** and it is now being ported there; if you are asked to build it here, it already exists.
  **`ops_status.py` ALL CLEAR**, 33 sources OK, three retired foreign-filing probes correctly marked, zero failed workflow runs across the last 25 (the only red on the account was the sibling's, and was its fail-loud guard working as designed).
  **Next:** unchanged — the 2.19.219-220 SEO queue (items 1-7 in #9) is still untouched and still the priority. **Crawlable country/state/industry views remain the biggest single win on this site.** One refinement learned on the sibling and worth applying here: those generated pages need a **per-cell threshold** (only generate where a facet has enough rows to be substantively different), because thin programmatic page sets get filtered by Google at the SET level, dragging the strong pages down with them — a smaller set that all ranks beats a large set that gets suppressed.
- 2026-07-29 local (Claude Code) #10: **CLICK-TO-FILTER ON EVERY CHART, 2.19.221.** Owner ask was parity with the talent tracker ("we can click on things on the graphs and it filters the full page"). Read that plugin read-only first: it has NO canvas at all, every chart there is an HTML bar list of real `<button>`s carrying `data-k`, delegated per card, mapped card-element -> filter key, toggled, then one `refresh()` that fans out to table + chips + address bar + exports. **The layoff tracker already had most of that shape** (industries, US states, countries, largest cuts, repeat layoffs, reasons doughnut). Real gaps, now closed: (a) three bar lists rendered as `disabled` buttons - **Roles most impacted**, **By data source**, **AI intensity by industry**; (b) **nothing wrote the address bar**, so a filtered view could only be shared via the per-card share button, never by copying the URL. **Two data-coupling traps worth remembering:** `/aggregate` keys `top_roles` by LABEL while the `roles` filter takes SLUGS (new `ROLE_SLUG_BY_LABEL` derived from `ROLE_LABELS`, checked byte-for-byte against `alt_role_categories()`), and the **By data source** chart speaks `source_type` (`erm`/`news`/`8K`/`press_release`/`federal_rif`) not verification tier - which works only because db.php's `sources` param already matches `verification_level IN (...) OR source_type IN (...)`. All six source_type values and the role slugs were proven to filter against the LIVE endpoint before shipping. New `ensureOption()` adds the missing dropdown option so a tap on a value /facets never listed can't silently no-op, and it is ALSO wired into `restoreFiltersFromUrl()` - without that a shared `?sources=news` link silently dropped the filter for the recipient. Monthly canvas charts get `onClick -> pickMonth()`, writing the same Years+Months controls the dropdowns write. Map bubbles now TOGGLE via `toggleMultiFilter` instead of overwriting via `writeControl`. `country_basis=any` untouched: still table-only, headline stats still strict job-location. URL sync is `replaceState` with the same querystring the share buttons build, and the DEFAULT view (this year only) deliberately keeps a clean param-free URL so the crawled URL and the `ALT_BOOTSTRAP` zero-fetch first paint are unaffected - **verified live: clean URL still carries ALT_BOOTSTRAP, `?years=2026&roles=engineering&sources=news` returns 200, correctly skips the bootstrap, and its aggregate returns 7 entries / 9,312 jobs.** Also: **Company** chip added (the largest-cuts and repeat-layoffs charts write that text box and there was no visible X to undo them) and `.alt-barrow:focus-visible` (every bar row is a real `<button>`, was tabbable, drew no ring at all). **HONEST GAP - the owner is verifying this by hand:** no browser in this session, so the actual clicking/tapping was NEVER exercised. What IS proven: deploy green on the matching SHA, `/status` reports 2.19.221, the minified asset on the CDN parses and contains the new code, the new copy renders, and every filter value the charts now emit filters correctly server-side. **Also unverified by design:** canvas charts (the two monthly ones and the pre-existing reasons doughnut) have no keyboard route INSIDE the canvas - the equivalent keyboard control is the Years/Months/Reasons dropdown, which is what they write. Every bar list is fully keyboard-operable. **Next:** the 2.19.219-220 SEO queue (items 1-7 in #9) is untouched and still the priority; crawlable country/state/industry views remains the biggest single win.
- 2026-07-28 **DECISION (supersedes the "owner action" in #7/#8/#9): the competitor secrets are NOT needed and nobody should ask for them again.** Competitor tracking already lives in the LOCAL benchmark, and that mechanism is fully self-contained: `scratchpad/gen.py` reads only our own `agg_global/us/tech.json` and the competitor figures are hand-maintained in `scratchpad/bm-live.html` — **no secret is involved anywhere in it**. `COMPETITOR_FEED_URLS`/`COMPETITOR_COMPANIES` power only the SEPARATE optional `tracker-diff` gap-chase loop, which stays **dormant by the owner's decision**; dormant it exits green on its daily schedule and costs nothing (verified). CLAUDE.md and RUNBOOK updated to say so. Repo re-verified clean of competitor names in tracked files (`git grep` finds none; `.claude/worktrees/` is excluded via `.git/info/exclude`, so old copies there are local-only and never pushed).
- 2026-07-28 local (Claude Code) #9: **FULL SEO AUDIT + TRACKER CARD FIXES, 2.19.219-220.** A parallel agent audited the live site end to end; every claim below was re-verified against production before and after the fix.
  **MANUAL-ACTION RISK, now cleared.** `alt_seo_head()` gated on `alt_page_needs_assets()`, true for every tracker sub-page, every company page and all 1,798 single-layoff permalinks. So byte-identical **FAQPage markup was emitted on ~1,830 URLs where none of that Q&A text is visible** (breaks Google's structured-data-must-match-visible-content rule) and ~1,830 **Dataset nodes all named "AI Layoff Tracker"** with differing `url` and no shared `@id`, so nothing could resolve which URL IS the dataset. Both now emit ONLY on the tracker page; Dataset carries `@id = <tracker>#dataset`. Verified live: FAQPage/Dataset = 0 on /press/, /sources/, a company page and an entry page; exactly 1 each on the tracker.
  **noindex that never worked.** The health page's rule hooked core's `wp_robots`, which **Rank Math replaces**, so the ops dashboard had been serving `follow, index` the entire time. Now repeated on `rank_math/frontend/robots` + `wpseo_robots`, applied to `newsletter-confirmed` too, and both dropped from the SEO plugin's sitemap (a noindex URL inside a sitemap is exactly what Search Console reports as "Excluded by noindex tag" — the owner's second alert). **Pattern to remember: any robots/canonical/title decision on this site must be repeated on the SEO plugin's filter; core hooks alone are silently overridden.**
  **Four visual defects on the flagship page.** (a) "Repeat layoffs" was the ONLY card of 16 missing `alt-chart-card`, so it had no border, no card background and no share/embed controls (JS injects those into `.alt-chart-btns`, which it lacked). (b) Bar-list values were clipped mid-glyph: `.alt-barrow-name` has `flex-grow:1`, so an over-wide row shrinks BOTH children in proportion to base size and the value's base is larger, so the value absorbed the shrink and its `nowrap` text spilled while the short name never ellipsized. `.alt-barrow-val { flex: 0 0 auto }` makes the name truncate instead, which is the documented intent. (c) `overflow-y:auto` makes the browser compute `overflow-x` as auto too, producing a horizontal scrollbar under the bars; now `overflow-x: hidden`. (d) The jobless-claims note ran as an always-open paragraph, making that card ~2x its row-mates' height and leaving a big blank gap beside them; now a collapsed `<details>` disclosure, and that card gained the download/expand controls it never had.
  **AUDIT FINDINGS NOT YET FIXED — this is the priority queue for the next session, highest value first:**
  1. **No crawlable filtered views.** `?country=`, `?state=`, `?industry=` return BYTE-IDENTICAL HTML with the same title and canonical; the params are ignored server-side. 51 countries + 50 states + 19 industries = 120 facet values, and 63,605 events, all collapsing onto ONE rankable page. Build `/ai-layoff-tracker/country/{slug}/` etc. as rewrite rules (mirror `company-directory.php:132`), server-render headline stats + top rows, unique title/description, self-canonical, sitemap them. **Biggest single SEO opportunity on the site.**
  2. **1,798 entry permalinks are orphans**: indexable, in NO sitemap, and linked from nowhere — the tracker table never renders the `permalink` field the /query API returns. Also thin (~90 unique words). Fix together: make the `layoffs` CPT noindex by DEFAULT and promote only rows that clear a content bar (has `ai_language`, or gold/warn verification, or a job-count floor), sitemap only those, and link them from the table + company pages.
  3. **Only 23 company pages exist** and 17 of the top 24 companies by event count have none (Boeing 324 events, Siemens 114,746 jobs, Wells Fargo, Walmart, Tesla...). The indexability gate (>=2 sourced events) is sound — **the throughput cap is the problem**: `db.php` admits 25/week. Raise the cap and/or run daily until the backlog clears. Also `page-health.php:66` publicly says "three or more" while the gate is two.
  4. **No meta description on any page except the tracker** (/sources/, /methodology/, /press/, /ai-quotes/, company pages, entry pages all have none), and titles are brand-suffix templates with no topical keywords ("Data Sources - AskTheRecruiter.com").
  5. **Article `dateModified` is frozen 13 days back** on the flagship page while the visible copy says "updated twice daily" and our own Dataset node says today. Freshness is asserted only in the field Google ignores. `author` is also "admin".
  6. **Perf:** 137 KB of inline CSS across 20 `<style>` blocks in `<head>` (163 KB head, 413 KB page), plus render-blocking DataTables CSS from cdnjs. Self-host it; server-render the headline stat numbers (they render as literal `…` until JS fills them, so the LCP text shifts).
  7. **og:image is a 512x512 favicon** declared `summary_large_image` on every page. Needs a 1200x630 card carrying the live headline figure.
  **Verified CLEAN, do not re-investigate:** robots.txt (both root and /blog/), company sitemap `X-Robots-Tag`, alias 301 consolidation, company-page BreadcrumbList, `<html lang>`, no 404s in any sitemap, talent-tracker page is genuinely distinct content (not a duplicate).
  **Answered for the owner:** press-page soundbites are NOT archived (recomputed live each load); the permanent citable surface is the report archive. Every number on every surface is live from the DB (proved twice: 342,978 -> 343,344 within one session, all surfaces moving together). The two empty grid slots on the last card row are a 3-column reflow artifact, NOT a missing feature — `reasons` is already charted (doughnut, "Reasons cited"); the only genuinely unused dimension is the AI-causation TIER split (primary / contributing / linked), which the press page computes but the tracker never shows. That is the one card worth adding; filler cards would cost credibility on a data product.
  **Next:** queue items 1-7 above; competitor secrets STILL not added (see #7).
- 2026-07-28 local (Claude Code) #8: **SEO/INDEXABILITY PASS, 2.19.217-218.** Triggered by two Search Console alerts the owner forwarded.
  **DEPLOYS WERE 500ing THE LIVE SITE (root cause of the "Server error (5xx)" alert).** `lftp mirror` overwrites PHP in place, so mid-upload WordPress fatals. PROVEN, not inferred: the deploy ran 01:14:38-01:15:44 and test_dedup_live recorded HTTP 500 at 01:15:21, inside that window. Fix: the upload now sits inside a WP `.maintenance` window, so the same seconds serve a 503 + Retry-After that crawlers wait out. **The timestamp written into `.maintenance` MUST be a literal** (`printf '<?php $upgrading = %s; ?>' "$(date +%s)"`) — writing `time()` would make it permanently "now" and strand the site behind a 503 forever; as a literal, WP self-clears after 10 minutes. Plus an `if: always()` cleanup step. Verified live: 503 during the upload, 200 immediately after. Knock-on: test_dedup_live now SKIPS on 503 specifically (deploy window is not a regression) while every other 4xx/5xx still fails loud.
  **THE WHOLE REPORT ARCHIVE WAS INVISIBLE TO SEARCH.** Every period renders from ONE page via `?period=`, so Rank Math canonicalised all ~60 dated reports to the bare `/report/` URL, and that base URL was the only report URL in any sitemap. Worse, all of them served the identical title "Monthly Job Cuts Report" — wrong even on the quarterly/yearly ones — so making them indexable WITHOUT fixing titles would have created 60 duplicates. New `includes/report-seo.php`: self-canonical per month/quarter/year + archive hub; `?scope=us` consolidates into its worldwide twin; weekly pulses and junk/future periods are `noindex, follow` (52 thin pages a year is the doorway pattern that costs a domain its standing); per-period titles + descriptions; `/layoff-reports-sitemap.xml` (62 URLs, all verified 200) appended to the SEO plugin's index; own guarded rewrite flush since FTP deploys never fire activation hooks.
  **GOTCHA that cost a version:** Rank Math CACHES the sitemap index, so 2.19.217's new sitemap served 200 with 62 URLs while `sitemap_index.xml` still listed the old set. 2.19.218 invalidates via Rank Math's own API where the class exists, then sweeps `_transient_rank_math_sitemap%` / `_transient_wpseo_sitemap%` directly (class/method names have moved between versions). **Note `alt_flush_caches_on_deploy()` had NO `global $wpdb`** — adding a `$wpdb` call without it would have fataled the site on the first request after deploy. Verified live: the report sitemap is now in the index.
  **Alert triage for the record:** the health_digest email was the stale warn_us row already cleared (health fully green); the two Tests failures were this same 500-then-503 during deploys, green on every commit since; **jewsofindia.com is NOT this project** (separate site, possibly same Bluehost account).
  **Owner data point:** Bing/Copilot citations climbed from ~36/day (late June) to ~300-400/day (late July) — consistent with IndexNow going live 2026-07-25.
  **Next:** act on the parallel full-SEO audit findings (titles/structured data/company-page thresholds/crawlable country+state+industry views/internal linking); competitor secrets STILL not added (see #7).
- 2026-07-28 local (Claude Code) #7: **VERIFICATION PASS after #6 + two more numbers fixes (2.19.215-216).**
  **COMPETITOR SECRETS STILL MISSING:** owner believed they re-added `COMPETITOR_FEED_URLS`/`COMPETITOR_COMPANIES`, but a dispatched dry-run proved BOTH env vars arrive empty (checked repo Actions secrets, talent repo, dependabot/codespaces stores — nowhere visible). They must be added as **repo Actions secrets on dk-forge/ai-layoff-tracker** (Settings → Secrets and variables → Actions), exact names above. ALSO fixed a latent workflow bug: tracker-diff.yml only ever forwarded `COMPETITOR_FEED_URLS` — `COMPETITOR_COMPANIES` was never passed to the script, so the inline-list option could never have worked (commit ea7c5cd adds the pass-through).
  **2.19.215:** the FAQ "How many layoffs in <year> so far" answer said "verified" over a query that summed the announced tier AND future-dated rows (837,931 vs the press floor's number for the same window) — `alt_live_numbers()` year row now filters `announced=0` and `layoff_date <= today`.
  **2.19.216 (found while verifying .215):** the press-page headline stats (`$alt_stats`), the AI-tier sums, and EVERY aggregate on page-report.php filtered `announced=0` but not `superset_of=0`, double-counting rollups + their members (+25,242 on the 2026 floor). Same class as the .214 card fix, applied to all stats closures on both templates. **Verified live: press floor = headline bite = FAQ = 342,978; US 286,393 below it.** Rule of thumb now proven three times: ANY page-level SUM needs `superset_of=0` (and `announced=0` if the copy says "verified") or it will contradict the API.
  **Ambers cleared for real:** today's 13:50 UTC WARN import predated the #6 fixes (ran commit ccce9be), so the stored warn_us degraded row was stale by construction. Dispatched a fresh import on latest main: **warn_us now ok** (42,398 upserted, no drift complaint) and **Kansas's first custom-scraper rows are live** (First Student 151 May-2026, Ashley Clinic 116, etc.). Health digest re-dispatched so its self-status heals under the new logic.
  **Also verified:** the hourly industry cron is dead in actual Actions behavior (no run after the fix merged — the next is the daily 04:55 trickle).
  **Next:** owner adds the two competitor secrets (then dispatch `tracker-diff.yml` with dry_run=1 to confirm activation); the #6 parked items stand (unclassifiable marker, 2021 news gap, entity re-key, branch protection on main).
- 2026-07-28 local (Claude Code) #6: **AUTONOMOUS PRODUCTION SWEEP (owner: "go without me"), 2.19.214.** Three parallel audits + own checks; every fix verified live.
  **THE COST BUG:** the industry drain sprint was never reverted — hourly x8 shards re-classifying a ~400-row backlog of rows where the two passes DISAGREE (no marker written, so they re-queue forever). Measured: 99.7% of each hour's rows identical to the previous hour, ~68,000 LLM calls/day ≈ **$7/day for ~3 fills**. Reverted to the daily single-shard trickle. ~97% of LLM spend removed. **Residual design gap: a disagreement still writes no marker** (contrast enrich_roles' 'unknown'), so the daily trickle re-checks ~200 of the 400 forever at ~$0.15/day — acceptable, but a server-accepted 'unclassifiable' marker is the clean fix.
  **PRESS INTEGRITY (P0, journalist-facing):** three press soundbite closures lacked announced=0 + superset_of=0, so the page showed 'United States 370,097' beside a worldwide verified 368,220. Fixed + verified live (US card now 286,393 < world 368,220). Same class fixed: FAQ event count (was 63,599 vs API 62,931 — alt_live_numbers now superset-guarded; live match verified), AI-quotes counts, retired-NewsAPI still advertised in FAQ prose AND FAQPage JSON-LD (now Google News), duplicate Dataset JSON-LD on press+report removed, basis-table rows now name their tier.
  **KANSAS dark since ~May:** the open warn-scraper times out (420s/run) walking the full kansasworks history. New bounded `fetch_ks` in warn_new_states (15-month window + detail pages for headcounts; parsers live-verified), KS removed from the generic sweep, 5 offline tests. Remaining genuinely-dark generic states after all exclusions: **none named** (KS custom now; NM excluded via NEW_CUSTOM_STATES — F22).
  **GOOGLE NEWS regression (mine, yesterday):** query-major job order meant the LAST discovery query — the bankruptcy/shutdown sweep feeding the new bankruptcy tag — NEVER executed. Now locale-major (every query gets the US edition first), cross-edition duplicate stories title-deduped before the LLM, politeness gap on error paths, env parses can't kill the cron at import, rotation index schedule-agnostic.
  **Other fixes:** federal_layoffs now emits `federal_workforce` (the Government/public-sector filter returned ZERO rows from its own collector; monthly /bulk upsert re-tags history in place); classify_reason_tags mini-prompt now carries the 12 tag definitions it told the model to use; OK added to digest benign set; test_dedup_live fails on HTTP 4xx/5xx instead of skipping green forever; seen-urls pre-check extracted to `seen_urls.py` and wired into gdelt_backfill + company_watchlist + supplemental_news; WATCHLIST_BATCH 60→150; company-directory ORDER BY alias fix (possible silently-empty sitemap), 301 loop guard + query-string preserve, honest scope note (the Meta pair is two STALE company_keys — needs the entity re-key repair, not URL canonicalisation); methodology documents the 12-tag reason taxonomy; sources page edition wording matches the real ~6-day rotation.
  **LEARNING LOOPS (audited end-to-end):** WORKING — watchlist self-grow (9,343 of 9,397 companies from own captures), recall alarm (gold-set recall 80%, precision 97%, AI precision 100%), health digest (real email fired). **DORMANT — the tracker_diff weaning loop has NEVER run: `COMPETITOR_FEED_URLS`/`COMPETITOR_COMPANIES` secrets were lost in the repo deletion and not re-added.** OWNER ACTION: re-add them (values are the owner's, private); everything downstream (independent recall, learn-from-wins, vocab capture, /tracker-meta) is deployed and waiting. NOTE: /tracker-meta is POST-only — a GET 404 is expected, not a missing route. Euphemism + edition sweeps run only on Railway's 2×/day cron (Actions news runs use the BQ mirror) — verify via Railway logs, not gh.
  **Next:** owner re-adds the competitor secrets; consider a server-accepted 'unclassifiable' industry marker; 2021 news-gap investigation still open (GDELT probe was rate-limited, inconclusive); entity re-key repair for stale company_keys.
- 2026-07-27/28 local (Claude Code) #5: **REPO DELETION + RECOVERY, then coverage/UX work through 2.19.213.**
  **INCIDENT (most important thing in this entry):** `dk-forge/ai-layoff-tracker` was **deleted from GitHub** mid-session (most likely a mis-click while creating the talent-tracker repos; three were created in the same minutes). Nothing was lost: the site never went down, the DB was untouched, and the full 711-commit history existed on the local clone. Recovery = recreate the repo public + `git push`. **What does NOT survive: every repo Secret, and the Actions run history.** Owner re-added the secrets. Lesson: the local clone is the real backup, and **branch protection on `main` is still not enabled** — worth doing.
  **DEPLOY PATH (cost ~2h):** after the rebuild, deploys uploaded to the wrong directory. WordPress lives at `/home1/xhcvdemy/public_html/AskTheRecruiter.com/blog/` — note the **`AskTheRecruiter.com` segment**, which nothing in the repo documented and which no amount of guessing found. `WP_PLUGIN_REMOTE_DIR` must be that **full absolute path**. Ground truth is WP admin → Site Health → Info → Directories (it reports its own paths); do not infer it. Also note the secret is named `FTP_USERNAME` (not `FTP_USER`).
  **SHIPPED (mine):** (a) **2.19.206** Wayback archives **newest-first** (`ORDER BY MAX(layoff_date) DESC`) so 2026/2025 links complete before older years — ordering, not filtering, so nothing is excluded; coverage 35% → **78.8%**. (b) **2.19.207** the **two counting bases published live** on methodology + press (`alt_country_basis_compare()` computes both from the table, one-hour transient): job-location **380,594** vs employer-basis **431,371**, difference **50,777** = multi-country cuts by US-HQ employers. This existed because the owner read the private benchmark's 431k against the site's 380k as a discrepancy — if the owner reads it that way, a journalist will. Press copy sits ABOVE "Numbers you can use right now" so a reporter picks the basis before quoting. (c) **warn drift**: the generic-tier alert named 12 dark states when only 2 were uncovered (8 have custom scrapers, OK has no register, HI has its own OCR collector) — now only watches states where the generic tier is the ONLY source, so a real breakage is not buried. (d) **2.19.211** reason tags **bankruptcy + federal_workforce** added to all four mirrors (extractor vocabulary + prompt definitions, `cpt.php` gate, JS labels, filter dropdown); also fixed a pre-existing gap where **`closure` was in the vocabulary but missing from the filter AND from the classifier's response list**, so the model was never told it could return it. Applied to existing rows automatically by the daily reason-tag backfill (stored excerpts only, no re-fetch). (e) **2.19.212** company pages get **one canonical URL each**, aliases 301 to it, sitemap GROUPs BY company_key. NB the Meta/Meta-Platforms pair turned out NOT to be aliases (different `company_key`, different data) — it is a genuine **entity-merge** job, deferred because re-keying changes dedup hashes and needs purge + re-import. (f) **2.19.213** Google News now reads **45 national editions** instead of only `US:en` — verified live (GB → Mobile Europe, CA → Yahoo Finance Canada). **Budget-neutral**: `MAX_ITEMS` still caps the run, so it changes WHICH articles are seen, not how many are extracted. (g) live dedup guard now **skips** on a transient API blip instead of erroring (it reddened CI while Spirit 7,069 and Tyson 7,184 were both well inside bounds).
  **MEASURED:** cost ~**$5-10/mo** (key had $22.69 left); Wayback **78.8%** (0 unavailable); history swept — GDELT historical at **2018-09**, EDGAR at **2020-08**, so 2019-2024 is done.
  **FINDING worth chasing:** **2021 news coverage is anomalous** — 5,326 jobs from news against 143,023 WARN (ratio **0.04**, where 2023 runs 1.41). WARN being lower in 2021-22 is real (tight labour market), but the news gap looks like a genuine collection gap, not a quiet year. Candidates: GDELT's older-archive depth, or news rows being absorbed by the news-vs-WARN superset dedup.
  **PARKED (all deliberate, none blocking):** company-page tiering (23 indexable of 20,000 companies — mass-generating thin pages risks the whole domain under Helpful Content; tier as index-substantial / noindex-thin / improve-UI); the EDGAR Item 1.02/2.01 sweep (volume measured: **682 filings/90d vs 61 for 2.05**, ~$0.25-0.50/mo, but **yield unproven** — sample before arming); the Meta entity merge; `docs/RECEIPTLESS_CATEGORY_PLAN.md` Ranks 2/4b.
  **Next:** enable branch protection on `main`; investigate the 2021 news gap; then company-page tiering.
- 2026-07-25 local (Claude Code) #4: **HOST GOTCHA — .txt never reaches WordPress on Bluehost.** Proven on production: a missing normal path returns WP's 404 (UTF-8) while a missing `.txt` returns Apache's raw 404 (iso-8859-1), so Apache serves static extensions straight from disk and never hands them to PHP. Two things were silently broken by this: (a) `alt_serve_llms_txt` had NEVER worked here — Rank Math's llms.txt won only because it was a REAL FILE; turning the feature off left the stale file behind (owner deleted it), after which the URL 404'd rather than falling through to us; (b) the IndexNow key file would not have served either, so ownership verification would have failed and NO submission would ever be accepted — i.e. the IndexNow work in 2.19.202-204 was broken in practice. FIX (2.19.205): `alt_write_static_files()` writes llms.txt and `<key>.txt` as real files into ABSPATH whenever the version or key changes, reads each back to confirm, and records an explicit failure state so a read-only filesystem is visible. Verified live: /blog/llms.txt now returns the tracker version. **RULE for future work: on this host, anything that must live at a .txt (or any static-extension) URL has to be a real file on disk — an init/rewrite hook will never fire.** Also: KEEP Rank Math (it serves the whole sitemap_index.xml plus 8 of our filters incl. company-directory noindex/canonical); only its AI-visibility/LLMs.txt feature is off.
- 2026-07-25 local (Claude Code) #3: **IndexNow + final retirement fix**, 2.19.201→204, deployed green. (a) Retirement guard compared the last run to a rolling 2-day window, so a freshly retired source un-retired itself for 2 days (ops_status went red on 'newsapi degraded' whose last run predated the retirement) — entries now carry retired_on and only a run NEWER than that counts as reactivation. (b) **IndexNow live**: pushes data changes to Bing (powers ChatGPT search) + Yandex the moment the dataset changes, throttled to once/day, non-blocking, fired from alt_flush_caches via a new alt_data_written action; submits the 6 public surfaces. Key is MINTED SERVER-SIDE and stored in the DB — never in this public repo (the protocol asks that only the owner + engines know it; an earlier commit hardcoded one, now abandoned/unused). Key file served at /blog/<key>.txt; Option-2 scope means it can only claim /blog/* URLs, which is exactly where every tracker page lives. (c) Owner-only IndexNow panel on the health page (admin capability check, verified invisible to the public) showing the key, key-file URL, last submission result and one-click per-URL submission links. **OWNER ACTIONS unchanged + one new:** disable Rank Math's LLMs.txt so ours serves; verify in Bing Webmaster Tools (the IndexNow key + links are on the health page when logged in) and Google Search Console.
- 2026-07-25 local (Claude Code) #2: **360 ADVERSARIAL PASS + PERF**, 2.19.199→200, all green, verified live. Three parallel audits found 4 breaks-now bugs (all fixed): google_news' GLOBAL cap starved the company-chase + euphemism queries at cap 150 (company queries now FIRST + per-query slice); the map's AI-dot floor could exceed its blue bubble; vocab_hit substring-matched ('RIF' in 'tariff') so the missed-vocabulary learning was inert; the euphemism terms were segments (AND-ed with base vocabulary) so pure doublespeak could never match — now standalone on the native rotation. Also: weaning gauge records competitor spellings (was counting chased companies as independent), retirement keeps REAL timestamps + un-masks reactivated sources, date_basis share links round-trip (a 'notice date' link showed recipients DIFFERENT numbers), one Dataset JSON-LD per page. PERF: layoffs.js 82.7→44.9KB gzip (deploy-pipeline minify; repo keeps source), d3+topojson (~95KB) lazy-load on map reveal, API no-store stripped for claims/reconciliation/quality-status, assets immutable, preconnect. **Found a deploy bug:** the flush cleared every cache except the htaccess guard, so header changes lagged up to 12h — fixed, verified applied. **OWNER ACTIONS (only these):** (1) disable Rank Math's LLMs.txt in WP admin so OUR tracker llms.txt serves (currently overridden by a generic resume-content file); (2) verify in Bing Webmaster Tools (powers ChatGPT search) + Google Search Console, submit sitemap. **Next for any session:** watch the first learning email (vocab + outlet·country candidates) and paste adoptions back; consider branch protection on main if a collaborator is ever added; the remaining ~2,650 unclassified-industry rows are LLM-disagreement rows that stay honestly blank by design (hourly cloud sprint is self-limiting, costs nothing when idle).
- 2026-07-25 local (Claude Code): FULL-AUDIT + LEARNING-MACHINE session, 2.19.193→198, all green + verified live. (1) CI unbroken: fake sources.* stubs in two warn tests leaked and shadowed real modules for the whole suite — requests-only stubs now, 267 tests green. (2) Retirements self-heal: alt_retired_sources() in db.php coerces newsapi/edinet_jp/opendart_kr/cvm_br to benign 'retired' on /source-health (never re-alarms); public copy synced everywhere. (3) Tracker narrative: 3 labeled chart chapters (Where/Trending/Who+why), map full-width with 4px-floor AI dots (was invisibly proportional), claims overlay on-by-default, announced un-stacked, 'AI-attributed'=strict everywhere, colorblind chips fixed, health page de-jargoned, no prose em-dashes. (4) NEW 'Jobless claims by US state' card (DOL, grey, context-only, auto-updates weekly; layoff cards relabeled to disambiguate). (5) WEANING machine in tracker_diff + keyed /tracker-meta: daily INDEPENDENT recall (have minus ever-chase-resolved), learn-from-wins (outlet · country tagged; allowlist candidates), missed-vocabulary capture (invisible-headline email to owner with paste-back line), earned Mondays-only cadence at ≥90% for 21d. (6) Euphemism vocabulary (base 42→48 + paired noisy segments), dedup near-count floor 1000→250, Google News throttled 150. (7) Cost: owner set key cap $50; steady ~$5-10/mo; industry tail draining via sequential dispatches. Private bm refreshed (LOCAL): US 97% basis-any / H1 80% / tech 103% of the live tech tracker. **Next:** watch the first learning email land (vocab + outlet·country candidates) and paste back any adoptions; consider the second tech tracker's gap (74%) via startup-press allowlist growth; TX/GA/WA/MI are the biggest state gaps vs the announcement survey.
- 2026-07-21 local: honest 'Data last updated' timestamps on report/press/sources from alt_last_write (real last-ingest time, NOT page-load). Fixed report's misleading DateTime('now') stamp. Sources notes its list changes on deploys, not daily. **Next (BIG): investigate WARN gap — WARNTracker 775,892 vs our 239,450 (31%) on the same source.**
- 2026-07-21 local: self-growing watchlist — new public /companies endpoint (distinct captured names, cached) + company_watchlist self-grows from it (WATCHLIST_SELF_GROW). Monitored universe now compounds with every capture. **Next:** point WATCHLIST_INDEX_URLS at S&P500/Russell CSVs; build GLEIF/SEC alias feed.
- 2026-07-21 local (Claude Code): added prominent public 'Why our number is lower' journalist callout on the tracker page (competitor-free). **Next:** point COMPETITOR_FEED_URLS at the tech-event tracker export to auto-run the gap-chase.
- 2026-07-21 local (Claude Code): removed the dead public competitor-benchmark block from health.js (competitor/history numbers were in the served JS source, never rendered — no PHP container). Benchmark stays private (bm-live.html). **Next:** CA WARN backfill once egress allowlisted.
- 2026-07-21 local (Claude Code): built the handoff baton + env-equip kit
  (`docs/ENVIRONMENT-SETUP.md`, `scripts/setup_test_db.sh`,
  `railway/gen_synthetic_snapshot.py`) + wired the baton into `ops_status.py`.
  **Next:** a cloud session with egress + the test DB can do the CA WARN
  backfill, self-host the chart libs, and the `/aggregate` query-fold perf work.

## #25 - security hardening live; the talent red is a backlog item, not a bug

**Live at 2.19.262.** Shipped via PR #2 rather than a direct push, because here a
push IS a deploy and a security change should not ship unreviewed. Deploy green on
the merged SHA `2f2a5af`, live page confirms `ver=2.19.262`. Closes audit ranks
23, 24, 27:

- **SSRF.** A public tip's URL was fetched twenty-six lines BEFORE the domain-trust
  gate, and that gate is a publish gate, so nothing gated the fetch at all. The
  context enricher fetched whatever `source_url` a stored row carried behind one
  `startswith` check that only ever saw hop zero. Both ran in a runner holding the
  WordPress and OpenRouter keys. `railway/safe_fetch.py` now owns it: http/https
  only, every resolved address must be globally routable including the v4-mapped
  and 6to4 spellings a naive `is_private` misses, redirects revalidated BEFORE
  EVERY HOP, capped body, whole-chain deadline.
- **Dependencies.** 20+ workflows ran a bare `pip install` into those runners. Now
  hash-pinned with `--require-hashes`.
- **Encoding.** The CSV formula guard tested byte zero only, so a leading TAB was a
  formula to a spreadsheet and invisible to the guard; the quarterly appendix had
  no guard at all.

**Sibling repo (talent) note for whoever picks this up:** its `main` has been red
for 6+ commits and the cause is NOT a broken test. `tests/test_audit_publishers.py`
names 13 publishers that each cost a gold-set event and for which the catalogue
holds neither a feed nor a written reason, across Argentina, Romania, Georgia,
Taiwan, Indonesia, South Africa, Oman, Poland, Nepal and Spain/LatAm. The test is
correct. **Do not weaken it to get green** - wire a feed or write a refusal with
the URLs probed and the status codes seen. Its security batch (1.68.1) is on main
and deliberately NOT deployed until that lands, so the deploy ships one clean state.

## #26 - the sweep that ran out of road (2026-08-04)

A six-finder adversarial sweep hit the account usage limit partway through: 21 of
55 agents completed, 34 died on the limit, INCLUDING the completeness critic and
the final synthesis. So this entry is a fragment, not a verdict. **Treat the
unfinished areas as UNKNOWN, not clear.** Full journal, including every agent's
raw return value:
`~/.claude/projects/-Users-dakotta-Projects-atr-layoff-tracker/80b9494c-3cd9-4fe5-b975-f8d9350063d1/subagents/workflows/wf_2c7f3121-e7a/journal.jsonl`
It can be resumed: `Workflow({scriptPath: .../final-lock-and-load-sweep-wf_2c7f3121-e7a.js, resumeFromRunId: 'wf_2c7f3121-e7a'})`. Completed agents replay from cache, so a resume costs only the 34 that failed.

**Fully verified (finder + adversarial verifier) before the limit: 12 findings.**
Two worth reading first, and note that in BOTH cases the verifier DOWNGRADED the
finder's severity with sound reasoning. The adversarial layer earned its keep.

**1. `running` is a source-health status that both monitors count as healthy,
and its `checked_at` is stamped BEFORE the work starts.** `db.php:1967` accepts
it; ~15 collectors post it pre-work (`cron.py:87,170,217`, `warn_import.py:274`,
`erm_import.py:139`, and ten more). Neither `health_digest.py:150-161` nor
`ops_status.py:491-503` has a branch for it, so it falls to `else: ok += 1`.
Because the post refreshes freshness, a collector killed BETWEEN the `running`
post and its terminal post leaves the ledger stuck at `running`, re-freshened on
every attempt, counted healthy forever. The staleness branch can never fire while
the job keeps STARTING; it would have to stop starting. This is the same species
as the Wayback archiver that died at 20m every run, the alert key the endpoint
could never accept, and the review queue nobody drained. Currently LATENT: no
source sits in `running` right now, which is why it reads as medium and not high.
Fix: treat `running` as a bounded transient. Flag one whose `checked_at` is older
than ~2x that source's ceiling, or stop stamping `checked_at` on the running post
and only stamp it on a terminal outcome.

**2. The staleness-ceiling parity test only checks the harmless direction.**
`test_source_registry_parity.py:150` filters ops-only keys with `if ops[k] >
default`, so it fires only when the digest would be too TIGHT (false STALE,
merely noisy) and never when it is too LOOSE (a real gap). `google_news` has a
2-day ceiling in `ops_status.py:76` and is absent from `health_digest.py`'s
`MAX_AGE_DAYS`, so it inherits DEFAULT 10. The test passes by construction. The
verifier correctly downgraded this to LOW and explained why: `cron.py:188-211`
posts a fresh degraded report on any google_news failure, so the ceiling is never
reached, and the only path to real staleness also stales three sources that ARE
in the digest. Fix is still worth doing (flag both directions; add
`"google_news": 2`), but it is hygiene, not a monitoring hole.

**The pattern is now four-for-four.** Every serious defect found in this session
was a mechanism that reported health while doing nothing. When looking for the
next one, that is the search: not "what is broken" but "what would never tell us
if it broke".

**Also unfinished, and NOT to be assumed clean:** the money-burn, published-
numbers, autonomy-loop and regression-risk verifications all died on the limit,
as did the four agents working on the star affordance, the IL/SG/CA registries,
the FTP hunt for the mobile-blocking CSS, and the Jan-Jun press probe. One
partial signal only, unverified: the registry agent's last words were "Israel
shows real event volume, Canada CSV downloaded". Do not act on that without
redoing the licence and signal checks.

## #27 - final state 2026-08-04, live and verified

**Live: 2.19.269.** CI green. Everything below was verified against the live site
or the live API, not inferred from a green run.

**Shipped since #26:** security hardening (SSRF closed, deps hash-pinned, four
encoding gaps); the mobile column (219px to 339px at 375px); partial-month and
chart-basis corrections; the hero relabelled with a reconciling line; the reasons
doughnut moved to one basis with its 12x drill-down fixed; /quality-status no
longer publishing retired collectors; the home page and press page now naming the
same period; and the published-figure invariant.

**The correction to #26:** Israel IS wired and verified. That entry said the
registry agent's fragment was unverified. It has since been substantiated:
data.gov.il `ica-changes`, CC-BY, four act codes that are the Israeli SH01
analogue, 343 rows across 311 companies in a 14-day dry run. Singapore is wired
(incorporations only). CANADA IS REFUSED with evidence: 642,984 rows, no industry
column, no event stream, and the per-company API is lookup-by-id only, so
harvesting means polling 642,984 ids. Do not re-open Canada without new evidence.

**THE ONE RED THAT MUST STAY RED.** `data-integrity.yml` runs the six new
published-figure invariants against the LIVE site. Several were failing when last
measured and some of those fixes have since merged, so the next run tells you
which are real. **Do not make it green by weakening a check, excluding a figure,
or relaxing a threshold.** The invariant is armed by MUTATION: it replaces an
invariant's `run()` with an unconditional PASS and asserts the named test goes
red, so a stub cannot satisfy it. That mechanism replaced one that compared
`INVARIANTS` against a hand-written list of strings and could have been silenced
forever by typing six words into it.

**Two slips of mine, both fixed, both worth knowing:** merging two PRs branched
from different bases sent the version BACKWARDS (2.19.267 to 2.19.266). That is
not cosmetic here, because the bump is what fires `alt_flush_caches_on_deploy`;
a backwards version can leave new code live behind stale assets while the deploy
reports success. And a `git add -A` swept `.worktrees/design-adopt` into main as
an embedded git repo, a path that looks present and is empty in every clone.
`.worktrees/` is gitignored now.

**THE PATTERN, which is the most useful thing in this file.** Roughly ten defects
today were one species: a mechanism that reports health while doing nothing. An
archiver that had never once completed in its history. An alert key the endpoint
could never accept. A review queue withholding 80 percent of the funding dollars.
A benchmark badge certifying its own freshness with no JavaScript behind it. A
test fixture answering 200 where the server answers 201. A CSS sweep that
downloaded 0 of 213 files and reported "no match". A coverage guard satisfiable
by typing strings. And several tests passing against defective code for the wrong
reason: a comment matched instead of a call, a CSS width read as a font size,
concatenated JS string literals, an indexed media-query block, and a
reconciliation measured against the basis that excused the defect.

Two of those were found INSIDE the audit hunting for them. So when you look for
the next one, the question is not "what is broken" but **"what would never tell
us if it broke."** Search for: a check whose success path never executes; a
threshold derived from the data it polices; a state that is terminal because
nothing drains it; an assertion testing a proxy rather than the property its
docstring names; a status stamped BEFORE the work it describes.

**Still open:** `running` as a health status both monitors count as healthy with
`checked_at` stamped pre-work (latent, medium); the staleness-parity test that
only checks the harmless direction (low); and the remaining sweep backlog, 5 high
7 medium 21 low, in the workflow journal named in #26. Owner-only: the ChangXin
IPO retract and the archive re-check margin.

## #28 - external adversarial review, folded in as the work queue (2026-08-10)

A read-only second-opinion audit was commissioned from a separate AI reviewer.
It changed no files, ran no workflows, wrote no data. Its full text lives OUTSIDE
this repo at ~/.codex/visualizations/2026/08/10/019fec71-.../HANDOFF_BATON.md,
which means no session will ever read it, so its substance is recorded here and
THIS FILE stays canonical.

**Its verdict, which I agree with:** the risk here is accumulated complexity, not
bad code. Many sophisticated guards, workflows and definitions now disagree with
one another at the seams. Local correctness is no longer enough; definitions, UI,
monitoring, docs and alert language need ONE authoritative contract. Evidence from
this week alone: an `if:` key added to a job that already had one (breaking the
file), four version collisions including one that moved BACKWARDS and skipped the
cache flush, three separate staleness definitions, and a coverage guard that
checked a list of strings rather than whether tests existed.

**Working agreement, agreed:** one implementation owner at a time; the reviewer is
read-only and adversarial; no two agents edit the same area concurrently; every
change starts from current origin/main; the baton is claimed before implementation
and released only after tests, deploy verification, live verification and docs.

**THE ONE ITEM THAT CONFLICTS WITH CLAUDE.md - OWNER DECISION NEEDED, DO NOT
UNILATERALLY "FIX" IT.** The reviewer calls the geography basis a P0: the browser
sends `country_basis=any`, a union of job-location OR employer-domicile, so a
France FedEx cut and global Oracle/Microsoft cuts can enter a United States
selection. CLAUDE.md says the opposite in plain terms: "Don't fix the discrepancy
- it's intentional and documented", with headline stats staying strict
job-location while table/exports use the union.
Both can be true at once, and that is the actual finding: the union may be a
legitimate second metric that is simply MISLABELLED. Three populations exist and
only the first may ever be called "United States jobs": (1) jobs cut in the US,
(2) global jobs cut by US-domiciled employers, (3) their union. Before any code
change, someone must establish which population each surface currently shows and
which it CLAIMS to show. If they already agree, this is closed and CLAUDE.md wins.
If they do not, the fix is labelling, not arithmetic.

**P0, uncontested: confirmed integrity incidents must be STICKY.** The movement
check refuses to advance a failing baseline on first failure, but later unrelated
rows enlarge the allowance until the same unexplained jump passes against the old
baseline, with the cause never identified. A full-cycle FAIL must open an incident
that later observations CANNOT close; closing requires a reviewed reason, the
affected row ids and field changes, and a replacement baseline. Regression test to
write: day one fails on an unexplained +93,211 jobs across +19 entries, later
arrivals make the old formula permissive, and the incident must remain OPEN.
This is the same species as everything else found this week: a check that heals
itself without anyone learning why.

**P0, uncontested: enumerate +93,211 BEFORE touching data.** Do not delete, edit
or re-dedupe rows to make an alarm green. The arithmetic suggests geography
enrichment rather than new events: US headline about +93,211 against a worldwide
move of about +13,264 over the same interval, so roughly 79,947 jobs entered the
US slice without entering the worldwide corpus, consistent with old rows gaining
a US employer_country under the inclusive union. Oracle 21,000, Microsoft 4,800,
Block 4,000 and a DOGE 60,000 row carry most of the magnitude. Required first:
exact row ids, old and new country / employer_country, old and new counted status
per watched headline, the workflow and run that mutated each, and whether the
result is wrong data, correct data under a misleading label, or a deliberate
definition change.

**P1 queue, in the reviewer's order:** field-aware mutation provenance (row ids,
fields before and after, aggregate contribution before and after, enrichment
recorded separately from correction); survey_reconcile calling requests.get('')
when SURVEY_FEED_URL is absent despite comments claiming dormancy, with the full
four-way config matrix tested; an explicit dormant/retired LIFECYCLE so a
by-design dormant collector is freshness-exempt by contract rather than drifting
stale or faking an OK heartbeat; structured CI causes (a stable CI_CAUSE marker
or ::error:: annotation the parser prefers) so success bookkeeping like
"worldwide_all_time: recorded ..." can never again be reported as a failure
cause; and typed remediation so an integrity failure does not tell the owner to
repair a scraper.

**Standing rules worth keeping verbatim:** one contract per concept, generated
rather than hand-mirrored across Python, PHP, JS, docs and tests. Comments explain
why, tests prove behaviour, and NEVER test for a comment as evidence behaviour
exists. Validate config, compute with pure functions, write through one effect
layer, emit a structured summary, and derive alerts from that summary rather than
from log-tail text. Never widen a bound to clear an incident.

**Cost, measured by the reviewer from committed ledgers:** 2026-08-07 $0.2364,
08-08 $0.1835, 08-09 $0.1504. The three-day mean projects to about $5.71 per 30
days and 08-09 alone to about $4.51, so the target is realistic for marginal model
spend. Do NOT economise by removing source links, evidence retention, correction
provenance, immutable reports or integrity checks: those are the product's
citation advantage and the reason it can be quoted.

**Review limitation it declared, and which should be respected:** GitHub CLI
credentials were invalid in that environment, so private Actions logs were not
read. Its conclusions rest on emails, local git objects, public API reads and
committed ledgers. Anything resting on a private log is UNVERIFIED, not wrong.
