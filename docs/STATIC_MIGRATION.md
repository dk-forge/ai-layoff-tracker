# AI Layoff Tracker static migration

Status: offline build contract and public backup data projection. Production URL and SEO parity are
blocked on a published-page snapshot. This is not a deploy or cutover approval.
Scope: dk-forge/todo#2880, ALT first. Talent Intelligence Tracker is a later pilot.

## Evidence and data ownership

Audited main at `08f0549` on 2026-11-22. The site base is
`https://asktherecruiter.com/blog`, not the domain root. The plugin runs on
ChemiCloud. The owner has reported a database outage and asked that live
verification stay stopped. This audit made no request to the WordPress host.

The repo is accessible. The missing input is a page export, not GitHub access.
Code search across dk-forge found sitemap implementations and audit reports,
but no saved ALT sitemap plus public-page SEO export. `dk-forge/site-atlas`
contains only README.md at the time of the audit. SEO diagnostics exports
404s and redirect rules, not published pages or sitemap contents.

The latest available public data is the GitHub Actions release
[backup-2026-11-22](https://github.com/dk-forge/ai-layoff-tracker/releases/tag/backup-2026-11-22).
`railway/backup_state.json` records its checksums and 2026-11-22T06:44:13Z
capture. `.github/workflows/backup-export.yml` produces this weekly backup;
`railway/backup_tables.py` pins its table and column allowlists.

| Public backup | Recorded rows | What it preserves |
| --- | ---: | --- |
| layoffs | 74,706 | Records, post IDs, classifications, dates, source links and superset membership |
| events | 114,490 | Canonical event identities |
| source_reports | 145,188 | Retained evidence and corroborating reports |
| company_directory | 44,909 | Reviewed company identities, aliases and stored company slugs |
| archive | 26,969 | Archived evidence URLs |
| digest_editions | 95 | Published edition content and correction fields |
| source_runs | 8,610 | Source-run history |
| warn_transparency | 0 | The existing, legitimately empty editorial register |
| digest_sends, digest_links, post_claps | 115, 2,513, 6 | Aggregate operational records, not the static page catalogue |

These are raw backup row counts, not published event totals. Preserve the
existing canonical-event, review and superset rules before making totals.
The number of company-directory rows is not the number of indexable pages.
Subscriber data is deliberately excluded from these public backups. Never
add subscriber backups, addresses, consent tokens or private benchmark data
to a static build or Actions artifact.

Ingestion still writes to WordPress today: EDGAR/news/GDELT/WARN collection
and correction workflows call `/add`, `/bulk` and keyed correction routes.
The backup is an off-host copy of that curated database, not an independent
data authority. Merely rebuilding its last weekly release after an ingest
does not make that ingest's new records available. A public snapshot publisher
must run after successful curated-data updates before the pilot can claim
database-independent freshness.

`claims-import.yml`, `bls-import.yml`, `oecd-import.yml`, `fred-import.yml`,
`qwi-import.yml` and `ai-exposure-import.yml` also publish macro/reference
data into WordPress. Their archive workflows preserve some upstream input
files in separate GitHub releases, but those are not the normalized published
reference API responses. Include the public reference projections and their
revision dates in the new snapshot publisher. Do not substitute raw source
files for the displayed, normalized reference series.

## Build-only data publisher

Run **Static site (build only)** with `backup_tag=backup-2026-11-22` to
produce the `alt-static-data` artifact, or run this against the downloaded
public release files:

```sh
python railway/static_data.py --backup backup-input --out static-data/tracker-data.json
```

The publisher reads only `manifest.json` and the layoffs, events and source
reports assets. It checks compressed sizes, uncompressed SHA-256 checksums,
row counts, column allowlists and the existing privacy scan. The output keeps
the capture time, source checksums, selected public filter fields, canonical
event membership, evidence URLs and superset membership. Consumers can use
canonical membership plus evidence for sourced views and use
`superset_of = 0` for aggregate views that exclude overlapping records.
Table rows retain individual records, including subset members. The data is
separate from the built HTML and carries the backup's freshness. A local run
with the November 22 release projected 74,706 records.

The live sitemap request from the cloud environment was denied by its proxy
with HTTP 403 at CONNECT. The tests cover independent sitemap fixtures and
check each generated HTML title, canonical and exact tracked CTA. A captured
production sitemap and page export are still needed to run the production
coverage gate. The remaining runtime work includes wiring the static data
into search, filters, charts and aggregates, publishing normalized reference
series after successful updates, and migrating feeds, exports, embeds,
contact and newsletter handling. Editorial pages, redirect targets and legacy
archive assets need to be captured before the build can verify their parity.

## Public URL inventory

Every path below is relative to `/blog`. Braces denote an existing dynamic
value, not a new slug. Source files are under
`wordpress-plugin/ai-layoff-tracker/` unless noted. The baseline snapshot must
enumerate every concrete URL, including noindex pages and redirects; route
patterns alone cannot establish sitemap coverage.

| Page type and URL | Data and rendering source | Current WordPress dependence |
| --- | --- | --- |
| `/ai-layoff-tracker/` | templates/page-ai-tracker.php, shortcodes.php; layoffs/events/source_reports | Page post, query/aggregate/facets endpoints, theme and SEO filters |
| `/layoff-tracker/` and dashboard shortcode pages | templates/page-tracker.php and page-dashboard.php; same corpus | Stored page placement and shortcode rendering must be exported |
| `/ai-layoff-tracker/methodology/` | templates/page-methodology.php, page-faq.php | Stored page and SEO settings |
| `/ai-layoff-tracker/sources/` | templates/page-sources.php; railway/data/source_catalogue.json, source_state.json and source_runs | Live source-health/reference endpoints and stored settings |
| `/ai-layoff-tracker/ai-tracker-health/` | templates/page-health.php; integrity/quality/coverage measurements and source_runs | Multiple live API reads and WordPress options |
| `/ai-layoff-tracker/ai-quotes/` | templates/page-ai-quotes.php; evidence-bearing canonical records | Query endpoint and attribution policy |
| `/ai-layoff-tracker/press/` | templates/page-press.php | Stored page, aggregates and theme |
| `/ai-layoff-tracker/publisher-tools/` | templates/page-publisher.php | Embed endpoints, shortcode examples, stored page |
| `/ai-layoff-tracker/us-warn-registry/` | includes/us-registry.php, template; state coverage measurements | Reference data and stored page |
| `/ai-layoff-tracker/state-of-layoffs/` | quarterly-report workflow, report-article.php and report template | Published report snapshots in WordPress options are not in the backup |
| `/company-layoffs/` and `/company-layoffs/browse/{bucket}/` | includes/company-index.php, company_directory | Stored reviewed identities and query-derived index |
| `/company-layoffs/{slug}/` | includes/company-directory.php; company_directory plus supported canonical records | Reviewed admission, aliases, indexability floor, SEO and aggregate query |
| `/country-layoffs/{slug}/` | includes/facet-pages.php; country facets | Canonical supported records, slug mapping, indexability floor |
| `/state-layoffs/{slug}/` | includes/facet-pages.php; US state facets | Same; do not invent city pages |
| `/industry-layoffs/{slug}/` | includes/facet-pages.php; industry facets | Same |
| `/ai-layoff-tracker/report/` | includes/monthly-report.php and report-seo.php | Date-window queries and SEO filters |
| `/ai-layoff-tracker/report/archive/` | includes/report-seo.php | Published period inventory and date semantics |
| `/ai-layoff-tracker/report/{YYYY}/` | includes/report-seo.php | Historical aggregate window |
| `/ai-layoff-tracker/report/{YYYY-MM}/` | includes/report-seo.php | Historical aggregate window |
| `/ai-layoff-tracker/report/{YYYY-Qn}/` | includes/report-seo.php | Historical aggregate window |
| `/ai-layoff-tracker/editions/` | includes/digest-archive.php; digest_editions | Publication state, stream content and SEO |
| `/ai-layoff-tracker/editions/{daily-or-weekly}/{slug}/` | includes/digest-archive.php; immutable digest_editions | Weekly is indexed; daily remains accessible but noindex |
| `/ai-layoff-tracker/digest/` and `/ai-layoff-tracker/digest/{YYYY-MM-DD}/` | includes/digest-public-archive.php | Older archive storage, publication gate and chart assets |
| `/ai-layoff-tracker/digest/{YYYY-MM-DD}/chart-{1-3}.png` | includes/digest-public-archive.php | Server-side chart rendering; preserve the existing asset URLs |
| `/ai-layoff-tracker/corrections/` | includes/public-logs.php | alt_corrections_log option is not exported by the backup |
| `/ai-layoff-tracker/update-log/` | includes/public-logs.php; data/update-log.json | Static release ledger plus WordPress shell |
| `/layoff/{post-slug}/` | includes/cpt.php and API post creation; layoffs.post_id | wp_posts slugs, post content, status and SEO overrides are absent from backup; the CPT explicitly has no archive |
| `/contact/` | includes/contact.php | Shared blog form handler, nonce/spam controls and email delivery |
| `/?alt_tracker_widget=1` and `/?alt_chart_embed=1` with their filter parameters | Plugin bootstrap and page-widget.php/page-chart-embed.php | Embeddable HTML, frame response headers and aggregate reads; retain query semantics |

The shared blog home, article/category/tag/author archives, legal pages,
Talent Intelligence Tracker and account/subscriber management are outside
the ALT route cutover. Their links and ownership still need to be preserved.
Stored shortcode placements can add public pages beyond the programmed
routes. A WordPress public-page export is needed to identify those placements.

## Crawl, metadata and interactive dependencies

| Surface | Existing implementation | Static requirement |
| --- | --- | --- |
| Search, table, charts, filters | assets/layoffs.js and includes/db.php query/aggregate/facets | Publish a curated public projection; browser reads static data, never wp-json. Match multi-select, date and superset semantics |
| Titles, descriptions, canonicals, robots | company-directory.php, facet-pages.php, report-seo.php, digest archives, shortcodes.php and Rank Math filters | Preserve the observed values and noindex rules for each URL, including overrides |
| schema.org | Plugin bootstrap, page-faq.php, company/facet/report/digest modules | Preserve every observed JSON-LD node, not just a generic Dataset |
| Sitemaps | Rank Math index plus six plugin sitemaps listed below | Compare against an independently captured URL inventory; preserve lastmod and indexing gates |
| RSS | includes/rss.php; `/feed/layoffs` and `/?feed=layoffs` | Static XML with the existing item URLs, GUIDs, dates, title and canonical feed URL |
| Downloads and embeds | includes/export.php, publisher templates | Static public JSON/CSV and embed resources; no keyed/admin routes |
| Contact, tips, corrections | includes/contact.php, feedback handlers | An approved independent handler is required; do not silently render a non-working form |
| Newsletter signup, preference changes and unsubscribe | includes/subscribe.php and digest-api.php | Existing private consent and delivery storage is not static data; keep it outside public artifacts and agree a replacement before cutover |
| Archived editions | includes/digest-archive.php | Use public send-id-zero content, never per-recipient rendered email |
| Free match CTA | includes/atr-signup-cta.php and existing page templates | Every HTML page has a visible phone/desktop link to the homepage free match flow at asktherecruiter.com with UTM tags |

Preserve these plugin sitemap URLs under `/blog`:

- `/company-layoffs-sitemap.xml`
- `/layoff-facets-sitemap.xml`
- `/layoff-reports-sitemap.xml`
- `/layoff-editions-sitemap.xml`
- `/layoff-digest-sitemap.xml`
- `/layoff-logs-sitemap.xml`

Also capture the active `/blog/sitemap_index.xml`, relevant Rank Math page and
layoff-post sitemaps, and the actual root `/robots.txt`. The domain root is
the ATR app, so a later route cutover must not replace its unrelated routes
or robots rules. Do not guess a new root sitemap from the route patterns.

## Build and parity gate

The offline builder consumes only a versioned public snapshot. It must fail
before publishing `dist/` when a baseline sitemap URL lacks a page, title,
description, canonical, JSON-LD or tracked CTA. Tests use a separate sitemap
fixture, not a sitemap generated from the same page list being tested.

Required snapshot inputs still missing from the available backup:

1. Actual sitemap XML, robots.txt, redirects and the concrete public URL list.
2. Observed per-URL titles, descriptions, canonicals, robots and JSON-LD.
3. Public editorial content, immutable report snapshots and legacy archive assets.
4. A curated public data projection and its published revision, plus a publisher
   that updates it after each successful data change without needing WordPress.
5. A decision and independent handler for forms and newsletter management.

No guessed permalink, empty placeholder page, zero total, fixture sitemap or
weekly backup can be labelled current production parity. A build-only Actions
artifact is not a deployment. No Pages project, DNS, routing, WordPress setting,
mail delivery or service variable is changed by this work. Preview deployment
and cutover remain separate owner-controlled steps. Rollback is to keep the
existing site and remove the future Pages route; retain WordPress for 30 days
after the later approved cutover.

## Static pilot checklist

- [x] Main tracker reads the public backup projection when the build has
  `--tracker-data static-data/tracker-data.json`. It supports company search,
  inclusive layoff-date ranges, explicit AI attribution and multi-select
  country, US state, industry and source type. The monthly jobs chart excludes
  superset members. The table keeps them visible.
- [x] CSV and JSON downloads use the full filtered set, including rows beyond
  the visible page. They include attribution and the backup timestamp.
  CSV guards cells against spreadsheet formula execution.
- [x] A captured RSS 2.0 file at `/blog/feed/layoffs` is copied byte for byte,
  served with an RSS content type and advertised on the tracker. The build
  checks its canonical self link.
- [x] An opt-in pilot can set `"wordpress_forms": true` in the snapshot
  manifest. Contact and newsletter links use the existing WordPress forms.
  Keep `/blog/contact/` and `/blog/layoff-tracker/` on that backend, with
  its existing submission, confirmation and unsubscribe routes. The build
  rejects a snapshot that would shadow either form page.
- [x] A noindex widget and monthly chart share that projection at
  `/blog/ai-layoff-tracker/embed/?view=widget` and `?view=chart`. They
  accept company, country, industry, state, sources, from, to and ai filters.
  The build splits the projection into assets under 8 MiB each. A local
  build with the public backup produced seven chunks for 74,706 records.
- [ ] Claude to capture the live sitemap, URL and SEO baseline, including the
  published RSS document, redirect inventory and archive assets. Run the
  production coverage gate with those inputs.
- [ ] Preserve the legacy `/blog/?feed=layoffs` alias at routing time and
  publish current RSS output after curated updates.
- [ ] Complete dashboard parity for remaining filters, alternate date bases,
  charts, reference series and the legacy CSV/JSON URL and schema contracts.
  Verify startup and response times on a cold mobile connection.
- [ ] Keep the legacy query-based widget and chart routes with their existing
  backend during the pilot. Migrate their remaining chart types and filters,
  and verify frame headers and old embed URLs before switching their routing.
- [ ] Validate contact and newsletter submission and confirmation on the
  retained backend. Decide how to preserve those flows before migrating
  the two pages that host them.
- [ ] Refresh the curated projection and normalized reference series after
  successful data updates. A run against the weekly release is a point-in-time
  snapshot.

## Build-only preview, 23 November 2026

`python railway/static_preview.py --out dist` downloads only the public layoffs
and company-directory assets from the GitHub release named by
`railway/backup_state.json`. It verifies the decompressed JSONL checksums,
which is how the existing backup exporter records them. No WordPress request,
private data, credentials or model call is needed. `--backups DIR` instead
uses already downloaded assets and makes the build fully offline.

The preview includes the hub, the company directory and recorded company
slugs that have verified, non-superset rows. It does not reclassify a record.
It displays source rows and their stated counts, not an aggregate or a claim
that this reviewed subset represents all layoffs. Only company, date, country,
job count and public source URL enter the generated row projection.

Every page labels itself Preview, states the backup date, carries noindex and
a UTM-tagged free-match CTA. The preview robots file disallows crawling. Its
preview sitemap describes this subset, not an independent production baseline.
The strict captured-snapshot compiler and its independent-baseline tests remain
unchanged. Missing production pages or SEO fields have not been guessed.

The build-only Action runs on relevant PRs, committed backup-state updates,
successful off-host backup workflow completion and manual invocation. It uploads
`dist/` as `alt-static-preview`; it never deploys it. This closes the earlier
workflow gap where every PR skipped the build and the required manifest did
not exist. Freshness is the backup cadence, not every ingest run. Publishing
all curated data independently and the parity requirements above remain open.
