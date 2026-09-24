# Growth features runbook

Written for a Claude session with no memory of the build (plugin 2.20.210,
branch `claude/growth-press-magnet`, 2026-09-24). Every feature below runs on
its own: WP-cron inside the plugin, or an existing GitHub workflow. Nothing
here sends email to a journalist without an admin click.

Common checks for everything on this page:

- `php -l` every file you touch; run the named test before and after.
- An FTP deploy runs no activation hook. The new tables (`wp_alt_press_contacts`,
  `wp_alt_follows`, and the `admitted_by` column on `wp_alt_company_directory`)
  are created by version-gated `dbDelta` calls on the first request after a
  version bump. If a table is missing, bump `Version:` + `ALT_VERSION` and load
  any page once.
- WP-cron needs traffic. If a scheduled hook has not run, list it with
  `wp cron event list` (owner, over SSH) or load any page to trigger it.

---

## 1. Resume call to action

**What it does.** A quiet line, "Changing jobs? / Laid off? / Returning to
work? / New grad or student?", then "Tailor your résumé" linking to
asktherecruiter.com with `utm_source=ai-layoff-tracker&utm_medium=referral&utm_campaign=<surface>`.
The line is picked by `crc32(surface|seed)` so each page is stable in cache.
Surfaces: report pages (`report`, after the citable card, never inside it),
company pages (`company`, inside the existing next-step block), chart embeds
(`embed`), digest footer (`digest`).

**Not on state/facet pages, on purpose.** `railway/tests/test_next_step_block.py`
pins the product off those pages (a reporter slices data there). The owner
must change that ruling in the test's docstring before anyone adds it.

**Where.** `ai-layoff-tracker.php`: `ALT_RESUME_CTA_DEFAULT_BASE`,
`alt_resume_cta_base()`, `alt_resume_cta_url()`, `alt_resume_cta_lines()`,
`alt_resume_cta_html()`, `alt_next_step_tool_url()`. Digest footer: the
`resume` block in `alt_digest_footer_blocks()` (`includes/subscribe.php`) and
its mirror `FOOTER_BLOCKS` in `railway/digest_layout.py`; the payload field
`resume_cta_url` in `includes/digest-api.php`.

**Change the destination.** Set the WP option `alt_resume_cta_base` (for
example `wp option update alt_resume_cta_base https://app.example.org`). A value
that is not a valid http(s) URL falls back to the default. The relay footer
only accepts a URL on the same host as the unsubscribe link; on another host it
falls back to `RESUME_CTA_DEFAULT_URL`. So a different domain also needs
`RESUME_CTA_DEFAULT_BASE` in `digest_layout.py` changed, together with the PHP
constant. `test_resume_cta.py` fails if the two literals differ.

**Broken looks like.** Links without `utm_` params, or the old sandbox
Railway hostname, in page source. **Test:** `railway/tests/test_resume_cta.py`,
`test_digest_sender.py` (footer parity across the three renderers).

## 2. Company, country and US state pages

**What it does.** Every employer with a source-linked event has
`/company-layoffs/<slug>/`, and every country, US state and industry has a
facet page. Each has its own canonical, title and meta, Dataset and
BreadcrumbList JSON-LD (indexable pages only), a headline stat, sources, a
thin-content floor (companies: 2 events; facets: 10 entries) with
`noindex,follow` below it, and a self-served sitemap. New in 2.20.210: a
year-by-year **timeline** (`templates/partials/timeline.php`,
`alt_timeline_by_year()` in `includes/facet-pages.php`). It counts an
in-progress month as of today (`to_date`).

**Auto-update.** `.github/workflows/company-directory-autopilot.yml` runs
**daily** at 14:20 UTC on the self-hosted runner. It admits new employers and,
new in 2.20.210, **promotes** its own `noindex` admissions that have reached
the floor (`alt_company_directory_promote_autopilot()`). Only rows with
`admitted_by = 'autopilot'` are promoted. An editor's noindex is never touched.

**Owner decision pending.** Rows admitted before 2.20.210 have
`admitted_by = ''` and are not promoted. If every existing `noindex` row came
from the autopilot, one statement fixes them:
`UPDATE wp_alt_company_directory SET admitted_by='autopilot' WHERE review_status='noindex';`
Only run it if no editor ever set noindex by hand.

**Broken looks like.** The run summary shows "Promoted to indexable (final
call): 0" for weeks while companies clearly have 2+ events, or the workflow
is red. Read the run log. The server decides everything, so a red run is
usually an HTTP failure. **Tests:** `test_company_pages_auto_update.py`,
`test_facet_timeline.py`, `test_facet_pages.py`.

## 3. Embeddable charts

**What it does.** Every chart card with an id in `EMBED_OK` (`assets/layoffs.js`)
has an Embed button. It opens "Embed this chart" with copyable code: the iframe
(`?alt_chart_embed=1&chart=<id>`), then a plain paragraph with **Source: AI
Layoff Tracker** (a followed link to the tracker view) and **CC BY 4.0**. The
framed page (`templates/page-chart-embed.php`) repeats source and licence in
its footer, plus the `embed` resume link (nofollow).

**Broken looks like.** Copied code without the Source paragraph, or a
`nofollow` on the source link. **Test:** `test_embed_attribution.py`.

## 4. Monthly report and press

**What it does.** `/ai-layoff-tracker/report/?period=YYYY-MM` renders live.
Monthly mode now adds: top employers, top US states and top countries, a CSV
link for exactly that period (`alt_mr_csv_url()`), a press contact line, and a
"Press release summary" textarea (`alt_mr_pitch()`) under the card.

**Schedule.** WP-cron `alt_monthly_report_tick` runs daily at 10:00 UTC
(06:00 ET). From the **first business day** of a month
(`alt_mr_first_business_day()`: skips weekends, New Year's Day and its Monday
observance, and Labor Day), it freezes the previous month's figures and pitch
into the option `alt_monthly_report_latest`. That is always on or before
the national announcement survey's first-Thursday release, except when 1 January is itself the first
Thursday. `/press` shows it under "Latest monthly report" (`#alt-latest-monthly`).

**Broken looks like.** `/press` has no "Latest monthly report" section after
the first business day. Then `alt_monthly_report_latest` is missing or stale:
`wp option get alt_monthly_report_latest`, then `wp cron event run alt_monthly_report_tick`.
**Test:** `test_monthly_report.py`.

## 5. Press list (journalist contacts)

**What it does.** Tools > Press list (admin only, `manage_options` plus nonces).
Holds name, outlet, email, beat, consent/source note, status, last contacted.
You can add a contact, import a CSV (header row required:
`name,outlet,email,beat,consent_note`), or copy the opted-in `/press` signups.
**Sending:** tick contacts and click Send. Each ticked, active contact not yet
pitched this period gets one plain-text `wp_mail` with the frozen pitch and an
opt-out link. The opt-out asks for a POST confirm, then records `opted_out` +
`opted_out_at`. A re-import never re-activates an opted-out contact.

**Owner action.** There is no journalist list, and none may be bought or
scraped. Who goes on the list, and on what basis, is the owner's decision.
Mail goes through `wp_mail`, which the Brevo plugin sends under its own From
identity.

**Broken looks like.** Send reports "Sent 0 of N". Check the contacts are
`active` and not already pitched for this period, and check Brevo's plugin
log. **Test:** `test_press_list.py` (no scheduled send, one `wp_mail` call site).

## 6. Follow a company or a US state

**What it does.** A "Follow <name>" form on company pages and US state pages.
It calls the digest's own `alt_digest_signup()`, which keeps the reader's
existing lists and adds the layoff list, so the existing confirmation email is
the double opt-in. The follow is stored `pending` in `wp_alt_follows`.
`alt_digest_confirm()` fires `alt_digest_confirmed`, which activates it. Each
digest, `alt_follows_section_for()` composes up to 10 matching rows: written in
the window, or announced or effective in it. The relay (`follow_section` in
`/digest-recipients`, appended by `railway/digest_send.py`) and the wp_mail
fallback add it after the reader's sections, for layoff-list readers only.
`alt_follows_cleanup` (WP-cron, daily) deletes follows of unsubscribed or
deleted subscribers, and pending ones older than 30 days.

**Broken looks like.** Followers get no "What you follow" block during a week
with matching rows. Check that `alt_follows_db_version` is set, that the row's
status is `active` (the reader clicked confirm), and that the subscriber is
`confirmed` with the layoff list at this frequency. **Test:** `test_follow_alerts.py`.

## 7. Author box

**What it does.** "About the author" plus a Person JSON-LD node on report,
company, US state, methodology and press pages. **It is invisible until the
owner fills `ALT_AUTHOR_PROFILE` in `includes/author-box.php`** (look for
`TODO_OWNER_BIO`). Both name and bio are required. **Test:** `test_author_box.py`.
