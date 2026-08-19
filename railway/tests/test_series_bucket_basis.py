"""A BUCKET IS KEYED ON THE DATE ITS OWN FILTER SELECTED ON.

WHAT WENT WRONG. 28e255d (2.20.4) moved the page's default date basis from the
effective date to the filing date. Its message says the default "lives in four
places and all four moved". The fifth was the live-integrity checker (b0c86b0).
The sixth was the monthly series in alt_api_aggregate_compute(): its rows were
selected through alt_db_where(), which is basis aware, and then GROUPed by a
hand-written CONCAT(YEAR(layoff_date), MONTH(layoff_date)), which is not. On the
page's own default query (years=2026&date_basis=notice) the chart therefore
picked rows by one date and stacked them by another. Measured live on
2026-08-11, before the fix:

  * the payload carried 2027-02 and 2027-03 buckets inside a view labelled
    2026 (notices filed in 2026 for effective dates in 2027);
  * the series summed to 480,678 verified jobs under a headline of 480,685,
    seven short. Those seven are rows with a real announcement_date and a NULL
    layoff_date: the filter counted them, and the series' own
    `AND layoff_date > '2000-01-01'` sentinel threw them away.

Both symptoms are one mismatch, so both are fixed by one rule and held here:
anything that groups, orders, windows or labels a period over rows selected by
alt_db_where must take its date expression from alt_db_date_col(), which is now
where alt_db_where takes it too.

WHAT IS DELIBERATELY NOT HELD HERE. The to_date_* / td_* columns stay pinned to
layoff_date on every basis. They answer "what has already taken effect", which
is an effective-date question in any view, and the sentence this repo publishes
from them says the words "have taken effect". The reasoning is written out at
the $date_col assignment in alt_api_aggregate_compute(). A test that forced them
onto the view's basis would be pinning the wrong decision, so instead
test_the_to_date_columns_stay_on_the_effective_date holds the decision that was
made, and will fail loudly if someone "finishes the job" without reading it.

HOW THESE CHECK. The helper is RUN through the php binary against a stub
request, so the three bases are proved by execution rather than by matching
source. The two checks that must read source strip comments first, because this
file's own rationale quotes the defective expression it is about and two checks
in this repo have already passed by matching a comment that described a call
instead of the call.

CONFIRMED RED on the pre-fix tree (the db.php in b0c86b0), run as a file, with
comments stripped before matching: 8 of these 10 tests fail there, the first
being

    AssertionError: '$date_col' not found in "SELECT CONCAT(YEAR(layoff_date),
    '-',LPAD(MONTH(layoff_date),2,'0'))" : the monthly bucket key does not use
    the request's date column

The two that pass on that tree are named here rather than left looking like
proof of this change: test_the_to_date_columns_stay_on_the_effective_date is a
REGRESSION BAR on a decision that predates it, and
test_the_conversion_endpoint_buckets_on_its_own_anchor pins a sibling query
that was already correct and is the worked example of what correct looks like.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = (PLUGIN / "includes/db.php").read_text()

PHP = shutil.which("php")


def strip_php_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


DB_NC = strip_php_comments(DB_PHP)


def _php_fn(name, src=None):
    """Brace-matched source of one top-level `function <name>(` in db.php."""
    src = DB_PHP if src is None else src
    marker = "function %s(" % name
    if marker not in src:
        raise AssertionError("db.php has no function %s()" % name)
    start = src.index(marker)
    i = src.index("{", start)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


def _aggregate_body():
    """alt_api_aggregate_compute(), comments stripped.

    Stripped, and that is the whole reason this helper exists rather than a
    plain substring search over DB_NC: the fix's own comment block quotes
    `YEAR(layoff_date)` while explaining why it is gone, so a checker reading
    the file with comments in it would find the defective expression in the
    text that documents its removal and report the fix as the defect.
    """
    return strip_php_comments(_php_fn("alt_api_aggregate_compute"))


def _series_query():
    """The monthly-series SELECT, from its CONCAT key to its GROUP BY."""
    body = _aggregate_body()
    m = re.search(r'"SELECT CONCAT\((.*?)GROUP BY m ORDER BY m ASC"', body, re.S)
    if not m:
        raise AssertionError(
            "the monthly series query no longer has the shape this test reads "
            "(a SELECT CONCAT(...) ... GROUP BY m). If it was rewritten, rewrite "
            "this test against the new shape rather than deleting it")
    return "SELECT CONCAT(" + m.group(1) + "GROUP BY m ORDER BY m ASC"


# --------------------------------------------------------------------------
# 1. One definition of the date expression, and it is reachable.
# --------------------------------------------------------------------------

PHP_BASIS_HARNESS = r"""
class WP_REST_Request {
    private $p;
    public function __construct($p) { $this->p = $p; }
    public function get_param($k) { return isset($this->p[$k]) ? $this->p[$k] : null; }
}
%s
foreach (array('', 'notice', 'announcement', 'effective', 'nonsense') as $b) {
    echo $b, "\t", alt_db_date_col(new WP_REST_Request(array('date_basis' => $b))), "\n";
}
"""


def _BASIS_FNS():
    """Both halves of the accessor, because it is TWO functions now.

    alt_db_date_col() takes a WP_REST_Request; alt_db_date_expr() is the same
    answer for callers that have no request to ask - a page template that needs
    one figure on a basis that is not its own, so it can name another surface's
    number honestly rather than remembering it (2.20.99). The harness runs the
    real source of both, so a split that broke the delegation would fail here
    rather than at render time.
    """
    return _php_fn("alt_db_date_col") + "\n" + _php_fn("alt_db_date_expr")


class TheBasisHasOneDefinition(unittest.TestCase):

    def test_the_request_free_accessor_delegates_rather_than_copying(self):
        """alt_db_date_col must not keep its own copy of the expression.

        The whole point of alt_db_date_expr existing is that there is ONE owner
        of the basis SQL. Two functions each holding the branch is the defect
        the accessor was extracted to end, wearing a second name."""
        col = strip_php_comments(_php_fn("alt_db_date_col"))
        self.assertIn("alt_db_date_expr(", col,
                      "alt_db_date_col re-derives the expression instead of "
                      "delegating to the request-free owner")
        self.assertNotIn("COALESCE(announcement_date", col,
                         "alt_db_date_col still holds its own copy of the basis "
                         "expression")

    def test_the_date_expression_is_a_named_function(self):
        """It was a local inside alt_db_where(), which is why the series could
        not use it and hand-wrote its own. A local is not reusable, and every
        place that cannot reuse it copies it or guesses."""
        self.assertIn("function alt_db_date_col(", DB_NC,
                      "there is no shared accessor for the request's date basis, so "
                      "every caller that needs it has to re-derive it")

    def test_the_where_clause_uses_that_one_definition(self):
        """Two copies of this expression is the whole bug class. If
        alt_db_where re-derives its own, the accessor can drift from the filter
        it is supposed to describe and every consumer inherits the drift."""
        where = strip_php_comments(_php_fn("alt_db_where"))
        self.assertIn("alt_db_date_col(", where,
                      "alt_db_where re-derives the date column instead of taking it "
                      "from the shared accessor")
        self.assertNotRegex(
            where, r"\$date_col\s*=\s*'COALESCE\(announcement_date",
            "alt_db_where still holds its own copy of the basis expression")

    @unittest.skipUnless(PHP, "php binary not available")
    def test_each_basis_resolves_to_the_column_it_names(self):
        """Run, not read. An accessor that returns the wrong expression is
        worse than the inline copy it replaced, because now everything is
        wrong in the same direction and nothing disagrees."""
        out = subprocess.run(
            [PHP, "-r", PHP_BASIS_HARNESS % _BASIS_FNS()],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = dict(line.split("\t", 1) for line in out.stdout.splitlines() if "\t" in line)
        self.assertEqual(got["notice"], "COALESCE(announcement_date, layoff_date)",
                         "the filed basis, which is the page's default, does not "
                         "coalesce: %r" % got.get("notice"))
        self.assertEqual(got["announcement"], "announcement_date")
        self.assertEqual(got[""], "layoff_date",
                         "an unset basis no longer falls back to the effective date")
        self.assertEqual(got["effective"], "layoff_date")
        self.assertEqual(got["nonsense"], "layoff_date",
                         "an unrecognised basis must fall back, not produce SQL of "
                         "its own")

    @unittest.skipUnless(PHP, "php binary not available")
    def test_the_expression_is_safe_to_inline_before_prepare(self):
        """It is concatenated into SQL that later goes through $wpdb->prepare,
        which eats a bare '%'. It also has to bind under a table alias, so no
        expression may name the table."""
        out = subprocess.run(
            [PHP, "-r", PHP_BASIS_HARNESS % _BASIS_FNS()],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        for line in out.stdout.splitlines():
            if "\t" not in line:
                continue
            expr = line.split("\t", 1)[1]
            self.assertNotIn("%", expr, "the basis expression carries a '%%': %r" % expr)
            self.assertNotIn("wp_alt_layoffs", expr,
                             "the basis expression names the table, so it cannot bind "
                             "inside a query that aliases it: %r" % expr)


# --------------------------------------------------------------------------
# 2. The monthly series buckets on the axis it was selected on.
# --------------------------------------------------------------------------

class TheMonthlySeriesBucketsOnItsOwnFilter(unittest.TestCase):

    def test_the_bucket_key_is_built_from_the_requests_date_column(self):
        """This is the defect. The key was CONCAT(YEAR(layoff_date), ...) while
        the WHERE it sits on ran on COALESCE(announcement_date, layoff_date),
        so the 2026 view drew 2027-02 and 2027-03 buckets."""
        q = _series_query()
        key = q[:q.index(" m,")]
        self.assertIn("$date_col", key,
                      "the monthly bucket key does not use the request's date column: %s"
                      % key)
        self.assertNotIn(
            "YEAR(layoff_date)", key,
            "the monthly bucket key is still hardcoded to the effective date while "
            "its own WHERE clause may be running on the filing date: %s" % key)

    def test_the_series_sentinel_guard_moves_with_the_basis(self):
        """`> '2000-01-01'` is "this row has a usable date". Asked of
        layoff_date while the view counts on the filed basis, it silently drops
        every row that has an announcement_date and no effective date. That is
        where the seven missing jobs went, and a chart quietly short of its own
        headline is the harder half of this defect to see."""
        q = _series_query()
        self.assertIn("$date_col > '2000-01-01'", q,
                      "the series' date sentinel is not on the request's date column, "
                      "so rows the filter counted can be dropped from the chart: %s" % q)
        self.assertNotIn("layoff_date > '2000-01-01'", q)

    def test_the_aggregate_takes_the_column_from_the_shared_accessor(self):
        """Not from a local re-derivation inside the aggregate, which would be
        the same two-copies bug one function further along."""
        body = _aggregate_body()
        self.assertRegex(
            body, r"\$date_col\s*=\s*alt_db_date_col\(\$r\)",
            "alt_api_aggregate_compute does not take its date column from "
            "alt_db_date_col")

    def test_the_coverage_dates_report_the_axis_the_view_was_filtered_on(self):
        """min_date/max_date are published as a period: "Covering 2019 to 2026"
        and schema.org temporalCoverage on the facet pages. Read off
        layoff_date under a filed-basis filter, a 2026 view can claim to cover
        2027, which is the bucket-label defect wearing a different hat."""
        body = _aggregate_body()
        self.assertIn("MAX($date_col) max_date", body,
                      "the published coverage window is still read off the effective "
                      "date regardless of the basis the rows were selected on")
        self.assertNotIn("MAX(layoff_date) max_date", body)


# --------------------------------------------------------------------------
# 3. The decisions this change deliberately did NOT make.
# --------------------------------------------------------------------------

class TheDecisionsThatWereMadeOnPurpose(unittest.TestCase):

    def test_the_to_date_columns_stay_on_the_effective_date(self):
        """REGRESSION BAR, and it passes on the pre-fix tree by design.

        to_date answers "what has already taken effect". alt_period_split_short
        renders it as "N have taken effect. The other M are filed for effective
        dates later in <period>", verbatim on the hero, the press page and in
        renderStats. Put it on the filing basis and that sentence starts
        describing filings while keeping the word "effect": a correct number
        under a wrong label, which is the exact defect the basis work exists to
        remove. The bucket KEY follows the view; this SUBSET of the bucket
        answers a different question and says so.
        """
        body = _aggregate_body()
        self.assertIn("layoff_date <= '$today_sql'", body,
                      "the to_date columns were moved off the effective date; the "
                      "sentence published from them says 'have taken effect', which "
                      "is an effective-date claim on every basis")
        self.assertNotIn("$date_col <= '$today_sql'", body)

    def test_the_conversion_endpoint_buckets_on_its_own_anchor(self):
        """The worked example of what correct looks like, and it was already
        correct: /conversion drops the date filters out of alt_db_where,
        re-applies them against its own $anchor, and groups on that SAME
        $anchor. Selection axis and bucket axis are one expression. Pinned so a
        later edit cannot regress it into the shape the series was in."""
        conv = strip_php_comments(_php_fn("alt_api_conversion_compute"))
        self.assertIn("CONCAT(YEAR($anchor),'-',LPAD(MONTH($anchor),2,'0'))", conv,
                      "/conversion no longer buckets on the anchor it filters on")
        self.assertNotIn("CONCAT(YEAR(a.layoff_date)", conv)


if __name__ == "__main__":
    unittest.main()
