"""The second duplicate detector must see what the first one structurally cannot.

THE INCIDENT (2026-09-09). Three reports of one Volkswagen event were live at
once. `dedupe_llm` buckets candidates on the company name, so "Volkswagen",
"Volkswagen (VW)" and "Grupo Volkswagen" landed in three buckets and the pair
was never even proposed; and 176988 carries no `layoff_date`, which makes
`days_between` answer 9999 and puts that row permanently out of reach of every
window gate, whatever the bucketing does.

`bucket_key()` was widened the same day (f7fe402) and closes the first half.
This module is the second, independent question, and the tests below are
written to fail if it ever grows a dependency on the first one's key:

  * the trio surfaces from the FIXTURE below, which is the three live rows;
  * the trio still surfaces when every company name is destroyed;
  * the dateless row is never paired away into silence;
  * the module writes nothing and calls no model.

FIXTURE PROVENANCE. 179106 and 176988 are read verbatim from the live /query
response on 2026-09-09. 179133 ("Volkswagen (VW)", 50,000, 2026-09-04) had
already been merged away by the dedup job by the time this test was written,
which is exactly why it is committed here: the pair it formed with 179106 is
the acceptance case and it no longer exists to be re-read.
"""
import ast
import os
import sys
import unittest

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import duplicate_shape_scan as dss  # noqa: E402


def code_of(name):
    """A module's source with its docstring and comment lines removed.

    These guards assert on what the file DOES. Its prose deliberately names the
    write routes it refuses to call and the dedup module whose blind spot it
    covers, and a grep that cannot tell prose from code would either fail on
    the explanation or force the explanation out of the file.
    """
    with open(os.path.join(RAILWAY, name), encoding="utf-8") as fh:
        src = fh.read()
    doc = ast.get_docstring(ast.parse(src))
    if doc:
        src = src.replace(doc, "", 1)
    return "\n".join(line for line in src.splitlines()
                      if not line.lstrip().startswith("#"))


def row(rid, name, count, when, country, source="news", event=None):
    return {"id": rid, "company_name": name, "job_count": count,
            "layoff_date": when, "country": country, "source_type": source,
            "event_id": event}


# The three rows of the 2026-09-09 incident.
VW_179106 = row(179106, "Volkswagen", 50000, "2026-09-03", "Germany")
VW_179133 = row(179133, "Volkswagen (VW)", 50000, "2026-09-04", "Germany")
VW_176988 = row(176988, "Grupo Volkswagen", 60000, "", "Germany")

# Enough ordinary company around them that "date-bearing" is a measured rate
# rather than a fallback, and so the scan has something it must NOT report.
FILLER = [row(900 + i, f"Company {i}", 4000 + i * 500,
              f"20{10 + i:02d}-0{1 + i % 9}-1{1 + i % 8}", "United States")
          for i in range(30)]

LIVE_TRIO = [VW_179106, VW_179133, VW_176988] + FILLER


def pair_ids(report):
    return {frozenset((p["a"]["id"], p["b"]["id"])) for p in report.pairs}


def queued_ids(report):
    return {item["row"]["id"] for item in report.dateless_queue}


class CatchesTheKnownInstance(unittest.TestCase):
    """The acceptance test. A zero here on this corpus means it is broken."""

    def test_the_dated_pair_is_reported(self):
        report = dss.scan(LIVE_TRIO)
        self.assertIn(frozenset((179106, 179133)), pair_ids(report))

    def test_the_dateless_row_gets_its_own_section(self):
        report = dss.scan(LIVE_TRIO)
        self.assertIn(176988, queued_ids(report))

    def test_the_dateless_row_names_the_dated_one_as_a_candidate(self):
        report = dss.scan(LIVE_TRIO)
        item = [q for q in report.dateless_queue if q["row"]["id"] == 176988][0]
        # A strict country match outranks a wildcard one, so the real
        # counterpart leads the hint list rather than hiding at the bottom.
        self.assertEqual(item["neighbours"][0]["id"], 179106)

    def test_the_ordinary_rows_around_it_are_not_reported(self):
        report = dss.scan(LIVE_TRIO)
        flagged = {i for p in pair_ids(report) for i in p} | queued_ids(report)
        self.assertEqual(flagged & {r["id"] for r in FILLER}, set())


class TheKeyReadsNoCompanyName(unittest.TestCase):
    """The design constraint, asserted rather than asserted-in-a-comment.

    THIS IS THE MUTATION THAT MATTERS. `bucket_key` failed because two rows for
    one event were SPELLED differently. If this scan can be made to miss the
    same pair by changing spellings, it has the same blind spot and is worth
    nothing.
    """

    def test_destroying_every_company_name_changes_nothing(self):
        wrecked = []
        for i, r in enumerate(LIVE_TRIO):
            copy = dict(r)
            copy["company_name"] = f"zz{i}qq"     # no two alike, none real
            wrecked.append(copy)
        report = dss.scan(wrecked)
        self.assertIn(frozenset((179106, 179133)), pair_ids(report))
        self.assertIn(176988, queued_ids(report))

    def test_a_missing_company_name_changes_nothing(self):
        blanked = [dict(r, company_name="") for r in LIVE_TRIO]
        report = dss.scan(blanked)
        self.assertIn(frozenset((179106, 179133)), pair_ids(report))
        self.assertIn(176988, queued_ids(report))

    def test_the_module_never_imports_the_dedup_bucketing(self):
        # A future edit that reaches for norm_company/bucket_key to "reduce
        # noise" would hand this detector the exact blind spot it exists to
        # cover. Read the source, not the namespace: an import inside a
        # function would pass a hasattr check.
        # The docstring names dedupe_llm on purpose (it explains the defect);
        # what must not appear is any code that calls into it.
        body = code_of("duplicate_shape_scan.py")
        for forbidden in ("import dedupe_llm", "from dedupe_llm",
                          "bucket_key(", "norm_company("):
            self.assertNotIn(forbidden, body,
                             f"{forbidden} would re-import the blind spot")


class DatelessRowsAreAState(unittest.TestCase):
    """A blank date is a STATE. It must never become a big number."""

    def test_a_blank_date_is_none_not_a_sentinel(self):
        self.assertIsNone(dss.row_date({"layoff_date": ""}))
        self.assertIsNone(dss.row_date({}))
        self.assertIsNone(dss.row_date({"layoff_date": "not-a-date"}))

    def test_a_dateless_row_is_never_a_dated_pair(self):
        # The failure this replaces: days_between answers 9999, the window gate
        # reads "far apart", and the row silently leaves the candidate set.
        # Here it must leave the PAIR set and arrive in the queue instead.
        self.assertFalse(dss.pair_is_suspect(VW_176988, VW_179106))
        report = dss.scan(LIVE_TRIO)
        self.assertNotIn(176988, {i for p in pair_ids(report) for i in p})
        self.assertIn(176988, queued_ids(report))

    def test_a_source_that_does_not_carry_dates_is_reported_in_bulk(self):
        # ERM's historical records are ~70% dateless. Queueing 500 rows is not
        # a worklist, so that class is COUNTED, never silently dropped.
        erm = [row(1000 + i, f"Erm {i}", 5000, "", "France", source="erm")
               for i in range(40)]
        erm += [row(2000 + i, f"Erm dated {i}", 5000, "2019-03-%02d" % (i + 1),
                    "France", source="erm") for i in range(10)]
        report = dss.scan(erm + LIVE_TRIO)
        self.assertNotIn(1000, queued_ids(report))
        self.assertEqual(report.bulk_dateless.get("erm"), 40)
        # and the dateless news row is still queued alongside it
        self.assertIn(176988, queued_ids(report))

    def test_too_few_rows_to_fit_a_rate_are_queued_not_assumed_systemic(self):
        few = [row(3000 + i, f"Rare {i}", 9000, "", "Spain", source="rare")
               for i in range(3)]
        report = dss.scan(few + LIVE_TRIO)
        self.assertTrue({3000, 3001, 3002} <= queued_ids(report))
        self.assertNotIn("rare", report.bulk_dateless)


class TheGatesThatKeepItAWorklist(unittest.TestCase):

    def test_two_warn_notices_are_not_a_finding(self):
        a = row(1, "Acme", 3000, "2025-01-01", "United States", source="warn")
        b = row(2, "Acme", 3000, "2025-01-05", "United States", source="warn")
        self.assertFalse(dss.pair_is_suspect(a, b))
        # but a WARN row against a news row is exactly the superset case
        self.assertTrue(dss.pair_is_suspect(a, dict(b, source_type="news")))

    def test_federal_rif_rows_never_enter_the_scan(self):
        a = row(1, "Agency", 3000, "2025-01-01", "United States",
                source="federal_rif")
        self.assertFalse(dss.eligible(a))

    def test_rows_already_one_event_are_not_reported(self):
        a = row(1, "Acme", 3000, "2025-01-01", "United States", event=77)
        b = row(2, "Acme Inc", 3000, "2025-01-02", "United States", event=77)
        self.assertFalse(dss.pair_is_suspect(a, b))
        self.assertTrue(dss.pair_is_suspect(a, dict(b, event_id=78)))

    def test_an_incompatible_country_rules_a_pair_out(self):
        a = row(1, "A", 3000, "2025-01-01", "Germany")
        b = row(2, "B", 3000, "2025-01-02", "Japan")
        self.assertFalse(dss.pair_is_suspect(a, b))
        # an unknown country identifies nothing, so it cannot rule anything out
        self.assertTrue(dss.pair_is_suspect(a, dict(b, country="")))

    def test_counts_further_apart_than_the_ratio_are_not_a_pair(self):
        a = row(1, "A", 10000, "2025-01-01", "Germany")
        b = row(2, "B", 8000, "2025-01-02", "Germany")
        self.assertFalse(dss.pair_is_suspect(a, b))

    def test_the_window_is_a_real_bound(self):
        a = row(1, "A", 10000, "2025-01-01", "Germany")
        b = row(2, "B", 10000, "2025-03-01", "Germany")
        self.assertFalse(dss.pair_is_suspect(a, b))

    def test_the_tightest_gap_and_the_biggest_number_read_first(self):
        rows = [
            row(1, "A", 3000, "2025-01-01", "Germany"),
            row(2, "B", 3000, "2025-01-20", "Germany"),
            row(3, "C", 40000, "2025-06-01", "France"),
            row(4, "D", 40000, "2025-06-02", "France"),
        ]
        report = dss.scan(rows)
        self.assertEqual(frozenset((report.pairs[0]["a"]["id"],
                                    report.pairs[0]["b"]["id"])),
                         frozenset((3, 4)))


class ItReportsAndNeverWrites(unittest.TestCase):

    def test_no_write_route_and_no_paid_model_is_reachable(self):
        # The prose names the routes it refuses to call, so read the CODE:
        # module docstring and comments removed, everything else kept.
        src = code_of("duplicate_shape_scan.py")
        for forbidden in ("merge-events", "bulk-purge", "move-source-reports",
                          "/add", "/edit", "openai", "OPENROUTER", "metered_call",
                          "WP_API_KEY", "urlopen(req, data", "method=\"POST\""):
            self.assertNotIn(forbidden, src,
                             f"{forbidden} has no business in a read-only reporter")

    def test_the_sweep_is_paced_and_serial(self):
        calls = []

        def fake(params):
            calls.append(dict(params))
            page = int(params["page"])
            return {"total": 1000,
                    "data": [row(page * 1000 + i, "X", 5000, "2025-01-01", "US")
                             for i in range(200)]}

        rows, complete = dss.fetch_top_rows(fetch=fake, top=1000, pause=0)
        self.assertEqual(len(rows), 1000)
        self.assertTrue(complete)
        self.assertEqual([c["page"] for c in calls], [1, 2, 3, 4, 5])
        # The population scanned is the one the headline sums, not the table.
        self.assertTrue(all(str(c["exclude_supersets"]) == "1" for c in calls))
        self.assertTrue(all(c["sort"] == "job_count" for c in calls))

    def test_a_short_serve_is_incomplete_coverage_not_a_clean_floor(self):
        # The corpus claims 5,000 rows and serves 200. The floor of what was
        # read must not be reported as though nothing lives below it.
        def short(params):
            if int(params["page"]) > 1:
                return {"total": 5000, "data": []}
            return {"total": 5000,
                    "data": [row(i, "X", 5000, "2025-01-01", "US") for i in range(200)]}

        rows, complete = dss.fetch_top_rows(fetch=short, top=1000, pause=0)
        self.assertEqual(len(rows), 200)
        self.assertFalse(complete)
        lines = " ".join(dss.summary_lines(dss.scan(rows, complete=complete)))
        self.assertIn("UNKNOWN", lines)

    def test_a_total_we_cannot_read_is_never_full_coverage(self):
        def no_total(params):
            return {"data": [row(i, "X", 5000, "2025-01-01", "US") for i in range(10)]}

        _rows, complete = dss.fetch_top_rows(fetch=no_total, top=1000, pause=0)
        self.assertFalse(complete)

    def test_a_bot_challenge_stops_the_sweep_instead_of_retrying(self):
        pages = []

        def wall(params):
            pages.append(params["page"])
            raise dss.SweepAborted("non-JSON response from /query")

        with self.assertRaises(dss.SweepAborted):
            dss.fetch_top_rows(fetch=wall, top=1000, pause=0)
        self.assertEqual(pages, [1])

    def test_an_empty_read_is_not_a_clean_bill_of_health(self):
        report = dss.scan([])
        lines = " ".join(dss.summary_lines(report))
        self.assertIn("UNKNOWN", lines)
        self.assertNotIn("no near-identical", lines)

    def test_findings_are_reported_as_unknown_never_as_a_failure(self):
        lines = " ".join(dss.summary_lines(dss.scan(LIVE_TRIO)))
        self.assertIn("UNKNOWN", lines)
        self.assertIn("owner adjudicates", lines)
        self.assertNotIn("FAIL", lines)

    def test_the_worklist_states_what_it_could_not_see(self):
        lines = "\n".join(dss.worklist_lines(dss.scan(LIVE_TRIO)))
        self.assertIn("COULD NOT SEE", lines)
        self.assertIn("WARN-against-WARN", lines)


class OpsStatusShowsIt(unittest.TestCase):

    def test_section_3f_is_wired_in(self):
        src = code_of("ops_status.py")
        self.assertIn("[3f] DUPLICATE SHAPE SCAN", src)
        self.assertIn("import duplicate_shape_scan", src)
        # Findings must never become an action item: a suspicion is not a
        # proven duplicate, and an exit 2 for one would train sessions to
        # ignore exit 2. Only an unread sweep is allowed to change the verdict.
        section = src.split("[3f] DUPLICATE SHAPE SCAN")[1].split("[4] RECENT CI")[0]
        self.assertNotIn("issues.append", section)
        self.assertIn("unverified.append", section)


if __name__ == "__main__":
    unittest.main()
