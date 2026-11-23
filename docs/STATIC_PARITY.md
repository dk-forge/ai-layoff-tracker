# Static URL and SEO parity

Scope: todo#2880. This is a read-only comparison, not a deployment or DNS change.

## Run

```sh
python railway/static_parity.py --dist dist --report parity-report.json
```

The default roots include the blog sitemap index and all six ALT plugin
sitemaps. Sitemap indexes are followed recursively, but only ALT hub, company,
country, state, industry and layoff page paths enter the page comparison.
Other blog articles and the hiring tracker are outside this cutover. Supply
one or more `--sitemap URL` arguments to use an independently captured root.
Every URL must stay on the HTTPS blog origin; external targets and path escapes
are refused. No cookies, authentication or privileged WordPress routes are used.

For every discovered ALT URL, the checker finds its static HTML under dist,
or follows a concrete permanent redirect in dist/_redirects. Temporary redirects
cannot excuse a missing page. It compares title, meta description, canonical,
all h1 text, parsed JSON-LD and alternate-language links. Whitespace and JSON
object-key ordering are normalized. Missing pages, missing or hidden-markup
CTAs, invalid JSON-LD, metadata differences, unreachable live pages, unreadable
sitemaps and incomplete comparisons all exit nonzero. The JSON report is still
written. An empty inventory never passes.

The CTA must be named and point to the free homepage or resume-score flow on
Ask The Recruiter, with source, medium and campaign UTM tags. HTML-hidden
anchors do not count. This is a markup check, not computed CSS visibility;
phone and desktop browser layout tests remain necessary.

## Be gentle to the shared host

Live GETs use the existing bot identity, run serially with one second between
requests, and share a locked one-hour on-disk cache. Failed reads are cached too.
Missing static files are reported before fetching their live pages. By default,
at most 500 new requests and 3000 seconds are allowed. Unvisited URLs remain
explicit failures, never a partial pass. Cache entries record their request
time. Use the same cache directory when repeating a local run.

The read-only CI workflow tests the contracts offline on PRs. Its manual live
job downloads an existing static-build artifact, restores the shared cache,
compares it and uploads parity-report.json even on failure. Live jobs are
serialized. Request and time budgets are explicit manual inputs; the time
budget must leave room before the job timeout for writing the report. A full
large-site run can raise the budgets; a budget-limited run cannot approve
cutover. The CLI also supports zero budgets for an unlimited local run.

No live job runs on a PR or a schedule. A workflow run ID and either the full
static artifact or the clearly labelled preview artifact must be chosen. A
preview subset is expected to fail full-site parity. Do not replace the live
sitemap with one generated from the static pages to make the report green.

## Verification limits

The unit fixtures use an independent sitemap, exercise each metadata field,
missing pages, permanent versus temporary mappings, CTA tags and hiding,
recursive discovery, request caching and failure reporting. The authoring
workspace could not fetch the live sitemap through its network proxy; that
check wrote a failed, empty-inventory report and exited 1. No production parity
result is claimed. The CI manual job provides the live comparison path.
