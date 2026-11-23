# Public snapshot build contract

This is a build-only foundation for todo#2880. There is no production snapshot
in this PR. The test sitemap is synthetic and is not a copy of the live site.
See STATIC_MIGRATION.md for the missing source data and cutover blockers.

## Run offline

```sh
cd railway
python -m unittest tests.test_static_site -v
cd ..
python railway/static_site.py --snapshot static-site/data/manifest.json --out dist
```

The second command requires an actual reviewed public snapshot. It fails when
the manifest is absent. It never substitutes a seed dataset or test fixture.
The output directory must not already exist; failed validation leaves no new
dist directory. Use a fresh output path for each review build.

## Manifest schema 1

The manifest records `captured_at`, `source_revision`, `pages`, `files` and
`sitemaps`. Capture the original sitemap independently of the page catalogue.
Do not construct the baseline sitemap from the pages the builder happened to
render: that would make missing-page coverage a tautology.

Each page records:

- `url`: the exact public URL, with the `/blog` prefix and trailing slash.
- `title`, `description`, `canonical`, `robots`: observed values, not guesses.
- `schema`: the full observed list of JSON-LD nodes, including an explicit empty
  list if that page genuinely has none. The builder escapes script delimiters
  without changing the decoded node values.
- `body`: public, static HTML with exactly one h1. Preserve the published copy.
  Scripts, forms, iframes, SVG, inline handlers and legacy WordPress API calls
  fail validation. They require migration, not silent removal. The capture
  publisher must omit comments and document declarations from body fragments;
  these are rejected because browser comment parsing differs from HTMLParser.
- `rows`, optionally: an already-curated public list with exactly `company`,
  `date`, `country`, `jobs`, `source_url`. These are page-scoped published
  records. The builder does not infer canonical membership, deduplicate raw
  backups, recalculate public totals or publish held rows.

Each file records `url`, snapshot-relative `source` and the source bytes'
`sha256`. Include the captured sitemap index, every child sitemap, robots.txt,
RSS and referenced images. The builder preserves these bytes. Asset references
must be present in the snapshot; the build must not leave images on WordPress.
Source paths cannot escape the snapshot directory. URL paths cannot escape
the output directory. Duplicate pages and output collisions are rejected.

The current compiler supports canonical, path-based HTML pages. Query-only
widget variants, redirects, complete multi-select/date/aggregate filtering,
full-corpus pagination and external form/newsletter handlers remain migration
work. The small browser search only searches the published rows on its page;
it must not be presented as parity with the current server-side tracker.

## Build-only Actions

`.github/workflows/static-site.yml` tests the offline contract on relevant PRs.
When a real snapshot is committed under `static-site/data/`, a push to main
builds `dist/` and retains a seven-day review artifact. Manual builds require
the same real snapshot. The workflow has read-only repository permissions,
no secrets, no deployment action, no Cloudflare credentials and no DNS changes.

This trigger covers public-snapshot updates. Existing ingest workflows do not
yet produce that snapshot, so this PR does not claim to rebuild after every
current WordPress data write. The missing public snapshot publisher must be
implemented before production freshness can pass the migration gate.

## Completion evidence still required

1. Supply the real independently captured sitemap and per-URL page/SEO export.
2. Add and test the public snapshot publisher using the existing curated-data
   semantics and preserving immutable editions and corrections.
3. Migrate the remaining interactive features and query-based embeds.
4. Run the compiler against that full snapshot and report actual URL counts,
   metadata comparisons, static asset coverage and phone/desktop checks.
5. Create a preview only under separate deployment approval, then run the
   issue's parity and Lighthouse checks. No cutover is authorized here.
