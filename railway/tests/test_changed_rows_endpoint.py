"""The row-level "what changed, and when" surface, and the guard that keeps it true.

On 2026-08-08 the published "United States jobs, all time" headline rose 92,686
while the worldwide headline, of which US is a strict subset, rose 13,264.
79,422 jobs entered the published US figure without entering the corpus. The
forensic investigation could not name one row, because `wp_alt_layoffs` recorded
nothing about WHEN a row was last written. (The forensics doc asserted the
column already existed; it did not. The `updated_at` in db.php belonged to the
company-directory table.) So the answer was UNKNOWN and no amount of reading the
public API could have made it anything else.

An endpoint that reads a timestamp is worth nothing if the timestamp is not
written. The load-bearing test in this file is therefore not the one about the
route: it is `EveryWriterStamps`, which fails when someone adds a backfill that
mutates rows without recording that it did. That is exactly how the column would
quietly stop meaning anything, six months from now, with every other check green.

Offline and static: reads the PHP as text and executes nothing. PHP comments are
stripped BEFORE matching, so a rule that is only satisfied by a sentence in a
comment fails here.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = PLUGIN / "includes/db.php"
MAIN_PHP = PLUGIN / "ai-layoff-tracker.php"


def strip_php_comments(text):
    """Remove /* */ and // comments, keeping string literals intact.

    Comment text is prose, and prose is not a guarantee. Every assertion below
    runs against this output so that documenting an intention can never be
    mistaken for implementing it.
    """
    out = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            end = text.find("\n", i)
            i = n if end == -1 else end
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


DB = strip_php_comments(DB_PHP.read_text())
MAIN = strip_php_comments(MAIN_PHP.read_text())


def function_body(text, name):
    """Source of one PHP function, from its signature to the next top-level one."""
    start = text.index("function %s(" % name)
    end = text.find("\nfunction ", start + 1)
    return text[start:end if end != -1 else len(text)]


def create_table_sql(text):
    """The CREATE TABLE for wp_alt_layoffs inside alt_db_install()."""
    body = function_body(text, "alt_db_install")
    start = body.index('$sql = "CREATE TABLE')
    return body[start:body.index('dbDelta($sql);', start)]


class TheColumnExistsAndIsIndexed(unittest.TestCase):
    def setUp(self):
        self.sql = create_table_sql(DB)

    def test_the_layoffs_table_records_when_a_row_was_last_written(self):
        self.assertRegex(
            self.sql, r"\bupdated_at\s+DATETIME\b",
            "wp_alt_layoffs has no updated_at column, so no endpoint can say which "
            "rows moved and the next headline step is UNKNOWN for the same reason "
            "the 2026-08-08 one was")

    def test_existing_rows_are_not_back_filled_with_a_migration_timestamp(self):
        """NULL is the honest value for a row nobody observed changing.

        DEFAULT CURRENT_TIMESTAMP on an ADD COLUMN stamps every existing row with
        the migration instant, which would assert that 63,000 rows changed at
        once. None of them did. A fabricated timestamp is worse than a missing
        one because it reads as evidence.
        """
        m = re.search(r"\bupdated_at\s+DATETIME[^,]*", self.sql)
        self.assertIsNotNone(m, "no updated_at column to check")
        decl = m.group(0)
        self.assertIn("NULL", decl)
        self.assertNotIn("CURRENT_TIMESTAMP", decl,
                         "an ADD COLUMN default would back-fill every pre-existing "
                         "row with the migration time and invent 63,000 changes")

    def test_the_window_scan_has_an_index_to_use(self):
        self.assertRegex(
            self.sql, r"KEY\s+updated_at\s*\(\s*updated_at\s*\)",
            "a window query over updated_at without an index is a full scan of the "
            "whole table on a shared host")

    def test_the_schema_sentinel_names_the_newest_column(self):
        """The deploy-race guard re-runs dbDelta until the NEWEST column exists.

        Leaving it on the previous newest column means a mid-FTP deploy can mark
        the schema verified while updated_at was never created, which is exactly
        how role_categories was lost in 2026-07.
        """
        self.assertIn("define('ALT_SCHEMA_SENTINEL_COLUMN', 'updated_at');", MAIN)


class EveryWriterStamps(unittest.TestCase):
    """The column is only as true as the writers that maintain it.

    This walks db.php for every statement that writes the layoffs table and
    requires each one to record that it wrote. A backfill added later without a
    stamp does not produce a wrong number and does not turn anything red on its
    own; it silently subtracts itself from every future investigation. This test
    is the only thing that notices.
    """

    # $wpdb->update/insert calls whose target is the layoffs table. Other tables
    # in this file (archive, directory, source runs) keep their own conventions.
    LAYOFF_TABLE_FNS = (
        "alt_event_for_layoff",
        "alt_db_upsert",
        "alt_api_reclassify",
        "alt_api_enrich_context",
        "alt_api_enrich_roles",
        "alt_api_industry_backfill",
        "alt_api_edit",
        "alt_reconcile_supersets",
        "alt_api_cleanup",
    )

    def test_every_function_that_writes_the_layoffs_table_stamps_updated_at(self):
        """Each write is checked on its own terms, not counted.

        Three shapes exist. A write passing an inline array literal must carry
        `updated_at` inside that literal. A write passing a `$data` variable is
        covered by the function assigning `$data['updated_at']` before it, which
        is one assignment for however many branches share the array. A raw
        `UPDATE $table SET` must name the column in its own SET clause.
        """
        missing = []
        for name in self.LAYOFF_TABLE_FNS:
            body = function_body(DB, name)
            calls = re.findall(r"\$wpdb->(?:update|insert)\s*\(\s*([^;]*?)\)\s*(?:===|;|\))",
                               body, re.S)
            raws = re.findall(r"UPDATE \$table SET[^\"']*", body)
            if not calls and not raws:
                missing.append("%s: expected to write the layoffs table, found no write" % name)
                continue
            data_var_stamped = "$data['updated_at'] = alt_db_touch_utc();" in body
            for call in calls:
                if "array(" in call.split(",", 1)[-1] and "$data" not in call:
                    if "'updated_at'" not in call:
                        missing.append("%s: inline write without updated_at: %s"
                                       % (name, " ".join(call.split())[:90]))
                elif "$data" in call and not data_var_stamped:
                    missing.append("%s: writes $data but never stamps it" % name)
            for raw in raws:
                if "updated_at = UTC_TIMESTAMP()" not in raw:
                    missing.append("%s: raw write without updated_at: %s"
                                   % (name, " ".join(raw.split())[:90]))
        self.assertEqual(
            [], missing,
            "a writer to wp_alt_layoffs that does not stamp updated_at removes "
            "itself from every future forensic window:\n  " + "\n  ".join(missing))

    def test_the_stamp_is_utc_not_site_local(self):
        """One clock. current_time('mysql') would follow the site timezone and a
        window query would be off by the host offset without anything looking
        wrong."""
        body = function_body(DB, "alt_db_touch_utc")
        self.assertIn("gmdate(", body)
        self.assertNotIn("current_time(", body)

    def test_the_bulk_rescoring_paths_are_stamped_too(self):
        """The superset clean-slate and the cleanup normalizers are raw SQL that
        can re-score thousands of already-published rows in one statement. They
        are the shape of mutation the 2026-08-08 step is suspected to be, so
        they are the ones that must not be missed."""
        for stmt in (
            "UPDATE $table SET superset_of = 0, updated_at = UTC_TIMESTAMP()",
            "UPDATE $table SET layoff_date = NULL, updated_at = UTC_TIMESTAMP()",
        ):
            self.assertIn(stmt, DB, "unstamped bulk re-scoring statement: %s" % stmt)


class TheEndpointIsGatedLikeEveryOtherOperationalOne(unittest.TestCase):
    def test_registered_get_only_behind_the_shared_api_key_gate(self):
        m = re.search(
            r"register_rest_route\('layoffs/v1', '/changed-rows', array\((.*?)\)\);",
            DB, re.S)
        self.assertIsNotNone(m, "/changed-rows is not registered")
        reg = m.group(1)
        self.assertIn("'methods' => 'GET'", reg, "read-only surface must be GET only")
        self.assertNotIn("POST", reg)
        self.assertIn("alt_api_permission", reg,
                      "must reuse the gate /alert, /tracker-meta and "
                      "/press-subscribers already use")
        self.assertIn("'__return_false'", reg,
                      "fail closed: with no key configured this must not fall open")

    def test_it_is_not_added_to_the_publicly_cached_endpoint_list(self):
        """Two independent places grant a public cache lifetime by endpoint name.
        A keyed forensic surface in either would be cached by a shared CDN."""
        self.assertIn("'/changed-rows'", DB, "no endpoint exists, so nothing to check")
        pub = function_body(DB, "alt_is_public_read_request")
        self.assertNotIn("changed-rows", pub)
        self.assertNotIn("changed-rows", (PLUGIN / "includes/htaccess.php").read_text())

    def test_the_response_is_no_store(self):
        body = function_body(DB, "alt_api_changed_rows")
        self.assertIn("'Cache-Control', 'no-store, max-age=0'", body)


class ItRefusesToLetSilenceLookLikeAFinding(unittest.TestCase):
    """PASS, FAIL and UNKNOWN are three states. An empty result for a window that
    predates the column is UNKNOWN. Returning `[]` with no qualification would
    let a future session write "no rows changed in the window" and be wrong in
    the most convincing possible way.
    """

    def setUp(self):
        self.body = function_body(DB, "alt_api_changed_rows")

    def test_the_response_says_whether_the_window_is_even_instrumented(self):
        self.assertIn("'window_is_instrumented'", self.body)
        self.assertRegex(
            self.body,
            r"\$instrumented\s*=\s*\(\$first_stamp !== null[^;]*\$since >= \$first_stamp\)",
            "instrumentation must be decided by comparing the window start "
            "against the earliest stamp the column actually holds")

    def test_an_uninstrumented_empty_window_is_labelled_unknown(self):
        self.assertIn("'verdict_when_empty'", self.body)
        self.assertIn("UNKNOWN", self.body)

    def test_it_admits_that_deletions_are_invisible(self):
        """A row removed by /trash or /bulk-purge leaves no timestamp. A headline
        that moved because mass LEFT the corpus cannot be explained here, and a
        reader must be told that rather than concluding from an empty list."""
        self.assertIn("'deletions_not_covered'", self.body)

    def test_it_admits_it_holds_no_prior_values(self):
        self.assertIn("'prior_values_not_retained'", self.body)


class TheWindowAndPagingCannotSilentlyDrift(unittest.TestCase):
    def setUp(self):
        self.body = function_body(DB, "alt_api_changed_rows")

    def test_an_unparseable_bound_is_a_400_not_a_different_window(self):
        for code in ("alt_bad_since", "alt_bad_until", "alt_bad_window"):
            self.assertIn(code, self.body)
        self.assertIn("'status' => 400", self.body)

    def test_a_naive_instant_is_read_as_utc(self):
        parse = function_body(DB, "alt_changed_rows_parse_instant")
        self.assertIn("DateTimeZone('UTC')", parse)
        self.assertIn("$raw .= 'Z'", parse,
                      "a bound with no zone must be read as UTC, not as the site "
                      "timezone, or a forensic window silently shifts by the offset")

    def test_paging_is_keyset_not_offset(self):
        """Offset paging over a table being written skips and repeats rows. On
        this endpoint the row that gets skipped is the one someone is hunting."""
        self.assertIn("ORDER BY updated_at ASC, id ASC", self.body)
        self.assertIn("updated_at > %s OR (updated_at = %s AND id > %d)", self.body)
        self.assertNotIn("OFFSET", self.body)

    def test_the_limit_has_a_default_and_a_hard_ceiling(self):
        self.assertIn("$limit = 200", self.body)
        self.assertIn("min(1000, $limit)", self.body)

    def test_a_forged_cursor_is_rejected_rather_than_reinterpreted(self):
        self.assertIn("alt_bad_cursor", self.body)


class TheRowCarriesWhatDecidesAHeadline(unittest.TestCase):
    """The point of the endpoint is to explain a headline move, so each row has
    to carry the fields that decide which headline it lands in. Job location and
    employer domicile are separate memberships because the published US slice is
    the country_basis=any UNION of the two, and 12.3% of that headline is rows
    whose jobs are not in the US."""

    def setUp(self):
        self.body = function_body(DB, "alt_api_changed_rows")

    def test_every_field_needed_to_explain_a_move_is_selected(self):
        for col in ("id", "company", "job_count", "layoff_date", "country",
                    "employer_country", "state", "source_type", "source_url",
                    "superset_of", "updated_at"):
            self.assertRegex(self.body, r"\b%s\b" % col, "row omits %s" % col)

    def test_slice_membership_is_reported_not_left_to_the_reader(self):
        for flag in ("'in_us_job_location'", "'in_us_employer_domicile'",
                     "'in_us_published_slice_any'", "'in_us_union_only'",
                     "'counted_in_totals'"):
            self.assertIn(flag, self.body)

    def test_counted_in_totals_matches_how_aggregate_counts(self):
        """/aggregate appends `AND superset_of = 0`. If this flag drifted from
        that rule the endpoint would confidently exonerate the rows that moved
        the number."""
        self.assertIn("$counts = ((int) $row['superset_of'] === 0)", self.body)
        self.assertIn("AND superset_of = 0", DB)

    def test_it_publishes_no_field_the_row_does_not_already_publish(self):
        """Every returned column is one /query already exposes publicly. This
        endpoint changes who can ask WHEN, not what is knowable about a row."""
        query_body = function_body(DB, "alt_api_query")
        select = re.search(r"SELECT(.*?)FROM", self.body, re.S).group(1)
        returned = set(re.findall(r"\b([a-z_]+)\b", select)) - {"select", "from"}
        # updated_at is the new field and is the reason the endpoint exists.
        for col in returned - {"updated_at"}:
            self.assertTrue(
                col in query_body or col in DB,
                "%s is returned here but is not an existing row field" % col)


if __name__ == "__main__":
    unittest.main()
