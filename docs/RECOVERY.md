# Recovery

**For the person reading this at 2am with the site down.** Start at the top and
do not skip section 1: most of the time nothing is lost and the fix is to wait.

---

## 1. First, decide which problem you have

Run this. It is read-only, needs no keys, and takes about a minute.

```bash
python3 railway/ops_status.py
```

| What you see | What it is | What to do |
|---|---|---|
| `[1] LIVE TRACKER UNREACHABLE`, everything else fine | The host is down. Bluehost 504s under `/blog/` a few times a month. | **Nothing.** Wait. The sibling repo's `host-watch.yml` probes every 15 minutes and opens ONE GitHub issue on a sustained outage. Data is not lost when the host is unreachable. |
| The site answers but the tracker shows zero or wildly wrong numbers | A data problem, not an outage. | Go to section 2. |
| `[9] OFF-HOST BACKUP` says STALE or UNKNOWN | The backup itself has stopped. | Section 6. Do this even in a calm week. |
| The site is gone and is not coming back | A reimage. | Section 3, then section 7. |

**A slow or 5xx host is not a data loss.** The single most useful thing at 2am
is to not start a restore into a site that was merely busy.

---

## 2. Where the data is

There are two copies and they are not equal.

**The live copy** is MySQL on Bluehost: thirteen tables the plugin owns, of
which `wp_alt_layoffs` is the one that matters. It is the only writable copy.

**The backup copy** is a GitHub Release on this repository, tagged
`backup-YYYY-MM-DD`, written every Sunday by `.github/workflows/backup-export.yml`.
Each release holds one gzipped JSON Lines file per table plus a `manifest.json`.

```bash
gh release list --limit 20 | grep backup-              # what exists
gh release download backup-2026-08-23 --dir ./restore  # get one
python3 -m json.tool < restore/manifest.json | head -40
```

The **twelve most recent** weekly releases are kept; older ones are pruned. The
rolling `railway/backup_state.json` in this repo records every run's row counts
and checksums, and it is committed rather than stored on the host, because a
backup whose only record of itself lives on the machine that might be gone is
not a backup.

### What is in a backup

| Table | What it is | Restore path |
|---|---|---|
| `layoffs` | The curated corpus. The rows that cost real money in LLM extraction. | `bulk` or SQL |
| `events`, `source_reports` | The evidence graph: one real event counted once, with every corroborating source. | derived, or SQL |
| `archive` | Wayback permalinks. Rate-limited into existence over about a week. | SQL |
| `company_directory` | Reviewed employer identities. Human review, not derivable. | SQL |
| `warn_transparency` | Editorial WARN-transparency register. Human adjudication. | SQL |
| `source_runs` | Collector telemetry. Without it, "has this source ever worked" is unanswerable. | SQL |
| `digest_editions` | Published digest editions, which render public URLs that have been linked. | SQL |
| `digest_sends`, `digest_links` | Send counts and aggregate click counters. | SQL |
| `post_claps` | A post id and a count. | SQL |

### What is deliberately NOT in a backup

**`wp_alt_subscribers` is never exported.** It holds email addresses, consent
records, and two live tokens (`confirm_token`, `unsub_token`). The backup
artifact is published to a **public** repository, so that table can never be in
it. This is enforced structurally, not by filtering: the plugin's
`/backup-table` route serves a hard-coded allowlist and refuses everything
else, `railway/backup_tables.py` names the same set on the other side, and a
test asserts the two agree.

**So the subscriber list has no backup at all today.** That is a real gap and it
is the owner's decision to close, not a session's. The options:

| Option | What it costs | What it risks |
|---|---|---|
| **Do nothing** | Nothing. | The list is lost with the host. Subscribers must re-confirm from scratch, and the consent records are gone, which matters if consent is ever questioned. |
| **A private GitHub repo** | A second repo. Actions minutes there are **billed**, unlike these public ones. | A private repo is not an appropriate long-term store for consent records, and it puts personal data somewhere backed up by GitHub rather than by a processor there is an agreement with. |
| **Encrypted artifact, key held off-platform** | A new secret, and a key that must not be lost. | An encrypted blob nobody can decrypt is not a backup. This only works if the key restore is drilled too. |
| **Bluehost's own database backup** | Nothing new. | Same host, so it does not survive the host. |

Do not implement any of these without the owner choosing one.

**`wp_rank_math_redirections`** is Rank Math's table, not this plugin's, and is
not in the automated export. It is readable through the existing keyed
`/seo-redirects` route and restorable through Rank Math's own redirection
importer. Worth keeping for SEO link equity; a manual step.

---

## 3. Restoring the tracker data

### 3a. The lossless path, for a reimage (**preferred**)

A reimage has database access by definition, and this path carries every column
the export captured.

```bash
# 1. Stand up WordPress and install this plugin. Activating it runs dbDelta,
#    which creates all thirteen tables empty. Do not skip this: the SQL below
#    inserts, it does not create.
# 2. Get a backup.
gh release download backup-2026-08-23 --dir ./restore

# 3. Emit and load, table by table. --prefix must match the new install's
#    $table_prefix in wp-config.php.
cd railway
for t in layoffs events source_reports archive company_directory \
         warn_transparency source_runs digest_editions digest_sends \
         digest_links post_claps; do
  python3 backup_restore.py --export ../restore --emit-sql "$t" --prefix wp_ \
    > "/tmp/restore-$t.sql" || continue
  mysql -u USER -p DBNAME < "/tmp/restore-$t.sql"
done

# 4. Check.
mysql -u USER -p DBNAME -e "SELECT COUNT(*) FROM wp_alt_layoffs;"
```

Statements are `INSERT IGNORE`, so re-running one is safe and will not duplicate
rows.

### 3b. The HTTP path, when all you have is the site and the key

Use this when the database is intact but rows are missing or wrong and there is
no MySQL prompt.

```bash
export WP_SITE_URL='https://asktherecruiter.com/blog'
export WP_API_KEY='...'                       # the same secret Actions uses
cd railway

python3 backup_restore.py --export ../restore --via bulk --limit 50   # dry run
python3 backup_restore.py --export ../restore --via bulk --confirm    # write
```

**This path is lossy.** `/bulk` has no parameter for several columns. Section 5
lists exactly which, measured rather than inferred.

### 3c. Then re-derive what is derived

```bash
gh workflow run reconcile-supersets.yml    # one real event counted once
gh workflow run canonical-event-migrate.yml
python3 railway/data_integrity.py          # do the numbers hold
python3 railway/reader_freshness.py        # are readers being served it
```

### `/bulk-purge` is NOT "empty the table"

It deletes WARN rows with no post and no editorial pin, and **nothing else**,
because it exists for the WARN purge-and-reimport cycle. There is no endpoint
that empties `wp_alt_layoffs`. A restore does not need one: a reimage starts
against tables `dbDelta` has just created empty. Do not reach for `/bulk-purge`
as a restore step.

---

## 4. What this backup does NOT cover

**Read this before telling anyone the site is fully backed up.** An owner who
believes he has a full backup and discovers at 2am that his blog posts are gone
is worse off than one who knew the boundary.

| Not covered | Size, measured | Is anything else covering it? |
|---|---|---|
| **`wp_posts`: the blog articles** | **557 posts** | **No repo holds them.** WordPress Tools -> Export writes a WXR file covering posts, pages and custom post types. Nobody runs it on a schedule. Bluehost's own backups cover it only while Bluehost exists. |
| **`wp_posts`: the `layoffs` CPT permalink pages** | **2,063 entries** | Same as above. These are the per-entry permalink pages the tracker links to. |
| **WordPress pages** | **14 pages** | Same as above. |
| **Uploads and media** | **2,171 media items** | **Nothing.** A WXR export records the URLs, not the files. Restoring media needs the `wp-content/uploads` directory, which exists only on the host and in Bluehost's own backups. |
| **The WordPress install** | theme, other plugins, `wp_options` | **Nothing in this repo.** `wp_options` holds the plugin's API key, the dataset-release ledger and the editorial suppression list, none of which are exported. The plugin's own code IS in this repo under `wordpress-plugin/`. |
| **The subscriber list** | see section 2 | **Nothing.** By decision, pending the owner's choice. |
| **Anything ingested since the last Sunday** | up to 7 days | Partly. WARN and news rows are re-derivable by re-running the collectors against their sources, at some cost and with some loss. LLM-extracted rows would be re-extracted, and re-extraction is not guaranteed to reproduce the same classification. |

The honest summary: **the tracker's DATA can be reimaged from GitHub. The BLOG
cannot.** The 557 posts and 2,063 entry pages are the SEO asset, and they live
on Bluehost and nowhere else.

The cheapest way to close the largest part of that gap is a periodic WordPress
WXR export (Tools -> Export -> All content) stored off-host. It would not cover
media files. Nobody is doing it today.

---

## 5. Restore fidelity: which columns actually survive

Measured, not read off the source, by
`.github/workflows/backup-restore-drill.yml`:

```bash
gh workflow run backup-restore-drill.yml -f sample=200
```

It round-trips real rows through `/bulk` and diffs them column by column.

**What the drill proves:** the whole HTTP chain end to end against the real
site, and which columns come back identical.

**What the drill does NOT prove:** an INSERT into an empty table. Every row it
sends already exists, so `alt_db_upsert` takes its UPDATE branch, and the
branches differ (UPDATE pins editorially corrected rows and declines to blank an
absent industry). **Proving the insert path needs a throwaway WordPress, which
this repo does not have.** That gap is open. Section 3a avoids it entirely by
not using `/bulk`.

Columns `/bulk` has no parameter for, and which therefore need section 3a:

- `id`, `post_id` - reassigned on insert; `post_id` links to a CPT post a reimage does not have anyway
- `company_key` - re-derived from `company` by `alt_company_key()`
- `role_categories`, `roles_evidence` - re-derivable only where `roles` text exists
- `edited` - the editorial pin. **Losing this un-pins corrected rows**, so a later re-import could revert a correction
- `event_id`, `superset_of` - rebuilt by `reconcile-supersets` and the event migration
- `updated_at` - restamped by the write, by design

`job_count_max`, `employer_country_evidence` and `announcement_evidence` **are**
carried, as of 2.20.126. They were not before.

### The SQL path was verified against a real MySQL 8

Against MySQL 8 in Docker, loading the emitter's output into the real schema
taken verbatim from `db.php`:

```
SCHEMA OK
RESTORE SQL ACCEPTED BY MYSQL 8
rows_loaded 10
MISMATCHES: 0 of 10 | all values byte-identical
```

That drill found a defect: `sql_literal` **stripped** NUL rather than escaping
it, so a value came back one byte shorter with the load reporting success. It
now escapes, and `tests/test_backup_restore_sql.py` carries the regression.

---

## 6. When the backup itself is the problem

`ops_status [9]` is the offline read. The export also goes `degraded` on the
health page and surfaces in the weekly digest.

**"The weekly backup stopped"** - no export in more than 15 days against a
weekly cadence:

```bash
gh run list --workflow=backup-export.yml -L 5
gh workflow run backup-export.yml
```

**"The export FAILED on drift"** - it refused to publish. Read which check:

- *ZERO rows in a required table* / *walked fewer rows than the site counted* -
  the walk stopped early. Do not lower the tolerance. Check the plugin is at the
  expected version and that `/backup-manifest` answers.
- *a count more than 5% below the last run* - something removed rows. Compare
  against `railway/backup_state.json` and find out what. A failing run
  deliberately does **not** advance the baseline, so next week still compares
  against the last good one.
- *no previous run to compare against* - UNCHECKED, not a pass. The next run
  establishes the baseline.

**"The export REFUSED: UnpinnedColumn"** - the site returned a column
`railway/backup_tables.py` does not name. **Read that column's schema before
doing anything else.** If it holds personal data, remove it from the plugin's
`alt_backup_tables()` allowlist. If it is ordinary data, add it to `TABLES`.
Do not widen the check.

**"The export REFUSED: PersonalDataInExport"** - the value scanner flagged
content. This is layer three and it is a denylist, so it may be a false positive
on public source text, but **a human decides that, not the job**. The artifact
was not published. Nothing was leaked.

Adjudicate it like this, which is what happened the first time it fired:

1. Find the actual value. The refusal names the table and column but never the
   value, because the log is public. Query the live API for that column.
2. Decide what it is. The first firing was
   `layoffs.source_url: a 64-hex token-shaped string`, one row in 11,800:
   `https://finnhub.io/api/news?id=<sha256-shaped>`, a news provider's article
   identifier. Benign.
3. Narrow the exemption **by column name, one at a time**, and write the
   evidence into the comment above it in `railway/backup_tables.py`. Never
   loosen the pattern, and never exempt a column class.
4. Add a test that the exemption did not widen: a bare token in a NON-exempt
   column of the same table must still fire.

---

## 7. What a full reimage looks like, in order

1. Stand up WordPress somewhere new. Set `WP_SITE_URL` to the new `/blog` path.
2. Deploy this plugin from `wordpress-plugin/ai-layoff-tracker/`. Activating it
   creates all thirteen tables.
3. Restore the tracker data per **3a**.
4. Restore the blog: a WXR file if one exists, or a Bluehost backup. **If
   neither exists, the 557 posts and 2,063 entry pages are gone.**
5. Restore `wp-content/uploads` from a Bluehost backup. There is no other copy.
6. Re-set the plugin API key, then update `WP_API_KEY` and `WP_SITE_URL` in this
   repo's Actions secrets.
7. Re-run the derived passes per **3c**.
8. Rank Math redirects: re-import through Rank Math.
9. Subscribers: gone, unless the owner has chosen a destination since this was
   written. They must opt in again.
10. Verify: `python3 railway/ops_status.py`, then the four surfaces named in
    `CLAUDE.md`.

---

## 8. Honest limits of this document

- The **insert path** of `/bulk` has never been exercised against an empty
  table. Section 3a does not use it; section 3b does.
- The **SQL path** is verified to "MySQL 8 accepted it and every value came back
  byte-identical" on a ten-row adversarial set, plus the offline parser suite.
  It has not been exercised at 65,000 rows.
- **Nothing here has been run against a real second host**, because there is not
  one. The first true reimage will find something this document did not
  anticipate. Write down what it was.
