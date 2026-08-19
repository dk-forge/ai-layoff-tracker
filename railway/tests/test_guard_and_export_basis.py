"""A GUARD, A GOLD SET AND AN EXPORT ARE ON THE BASIS OF THE THING THEY DESCRIBE.

WHAT WENT WRONG, for the eighth, ninth and tenth time. 28e255d (2.20.4) moved
the tracker's default date basis from the effective date (`layoff_date`) to the
filing date (`date_basis=notice`, COALESCE(announcement_date, layoff_date)). Its
message says the default "lives in four places and all four moved". It has since
been found in six, then seven. Every one of those was a HAND-TYPED copy of the
default that nobody re-typed. This file holds the three that were still open:

  1. railway/data_integrity.py's HEADLINES sent no `date_basis`, so every one of
     them was read on the effective basis under a note claiming they used "the
     same basis the reader's own filter uses". Three of the four carry NO date
     filter at all, so that was a measured no-op and the note was the only
     defect; `worldwide_recent_90d` does carry one, and it is not a no-op.

  2. railway/recall_precision.py asked `years=<the gold set's ANNOUNCEMENT
     year>` on the effective basis. A window that disagrees with its own gold
     set measures nothing reliable.

  3. The CSV export shipped rows selected by `date_basis` under a header that
     named only `layoff_date`, so the file could not reproduce the view it came
     from. The JSON export of the same rows had carried announcement_date all
     along.

THE RULE THESE HOLD, and it is one rule: a basis is never typed into a second
file. `data_integrity` takes it from the stamp the page publishes beside its own
figures, through published_figures.home_basis() — the mechanism that already
exists and is already validated, rather than a fresh copy of the default.
`recall_precision` is the deliberate exception and says so in its own words: its
basis is a property of the GOLD SET, not of the page, so it would not follow the
page back if the page moved.

  4. THE EIGHTH PLACE. `templates/page-press.php` built sixteen links labelled
     "See the rows behind this number" with no `date_basis`, from figures
     computed on hardcoded `layoff_date BETWEEN`, into a page that now defaults
     to the filing basis. Two of them also linked a "so far" figure to the whole
     calendar year.

CONFIRMED RED against the pre-fix tree (`ab4dea1`). Running this file there:

    Ran 17 tests ... FAILED (failures=10, errors=3)   [13 red, 4 green]

    AssertionError: 'date_basis' not found in {'from': '2026-05-13', 'to':
    '2026-08-11'} : the 90-day headline is windowed by date, so its query must
    name the basis it is windowed on

The four that pass on that tree are named in `Provenance` rather than left
looking like proof of this change.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_integrity as di                                    # noqa: E402
import published_figures as pf                                 # noqa: E402

REPO = Path(__file__).resolve().parents[2]
EXPORT_PHP = REPO / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "export.php"
# READ AS SOURCE, NOT IMPORTED, on purpose: recall_precision imports `requests`,
# which is in the lock but not on a bare laptop, and a guard that only runs where
# a third-party package happens to be installed is a guard that quietly stops.
RECALL_PY = Path(di.__file__).parent / "recall_precision.py"

YEAR = "2026"


class _Ctx:
    """The two things _page_date_basis touches, and a record of what it asked for."""

    def __init__(self, stamp_html):
        self.timeout = 5
        self.cachebust = "test"
        self.errors = {}
        self.fetched = []
        self._html = stamp_html

    def fetch(self, url, timeout):
        self.fetched.append(url)
        if self._html is None:
            raise OSError("no route to host")
        return self._html.encode("utf-8")


def page_with_basis(basis):
    """A served home page that stamps its own query, in the minified shape."""
    stamp = '{"years":"%s"' % YEAR
    if basis:
        stamp += ',"date_basis":"%s"' % basis
    stamp += "}"
    return ('<html><body><script>window.ALT_BOOTSTRAP={"aggregate_params":'
            + stamp + '};</script></body></html>')


def headline_query(ctx, h):
    """The query one headline is actually sent, whatever built it.

    Falls back to `_headline_params` when `_headline_query` does not exist, so
    that on a tree without the mechanism these tests fail on the ASSERTION —
    "this query names no basis" — rather than on an AttributeError. An
    AttributeError proves a function is missing; it does not demonstrate the
    defect, and a red that does not show the defect is not evidence.
    """
    build = getattr(di, "_headline_query", None)
    if build is not None:
        return build(ctx, h)
    return di._headline_params(h, ctx.today), None


def strip_php_comments(src):
    """Source with comments removed.

    Two checks in this repo have already passed by matching a comment that
    described the call instead of the call, and the comment this file is about
    quotes the very column list it is checking.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


# ---------------------------------------------------------------------------
# 1. the live guards
# ---------------------------------------------------------------------------
class GuardBasisComesFromThePage(unittest.TestCase):

    def setUp(self):
        self.by_name = {h.name: h for h in di.HEADLINES}

    def test_only_the_windowed_headline_is_date_windowed(self):
        """date_windowed is measured off the params, not off the name."""
        windowed = ("trailing_days", "from", "to", "years", "quarters", "months")
        h = self.by_name["worldwide_recent_90d"]
        self.assertTrue(any(k in h.params for k in windowed))
        self.assertTrue(getattr(h, "date_windowed", None),
                        "the 90-day headline selects rows by date, so it has a "
                        "date basis and something has to decide it")
        for name in ("ai_all_time", "worldwide_all_time", "us_all_time"):
            h = self.by_name[name]
            self.assertFalse(any(k in h.params for k in windowed))
            self.assertFalse(getattr(h, "date_windowed", True),
                             f"{name} carries no date filter, so date_basis is a "
                             f"measured no-op on it")

    def test_the_windowed_headline_names_the_pages_basis(self):
        ctx = _Ctx(page_with_basis("notice"))
        ctx.today = __import__("datetime").date(2026, 8, 11)
        params, problem = headline_query(ctx, self.by_name["worldwide_recent_90d"])
        self.assertIsNone(problem)
        self.assertIn("date_basis", params,
                      "the 90-day headline is windowed by date, so its query must "
                      "name the basis it is windowed on")
        self.assertEqual(params["date_basis"], "notice")

    def test_it_follows_the_page_rather_than_a_constant(self):
        """The whole point: move the page and the guard moves with it."""
        import datetime
        for basis in ("notice", "announcement"):
            ctx = _Ctx(page_with_basis(basis))
            ctx.today = datetime.date(2026, 8, 11)
            params, _ = headline_query(ctx, self.by_name["worldwide_recent_90d"])
            self.assertEqual(params["date_basis"], basis)

    def test_no_basis_is_hardcoded_in_data_integrity(self):
        src = Path(di.__file__).read_text(encoding="utf-8")
        src = re.sub(r'"""[\s\S]*?"""', "", src)
        src = re.sub(r"^\s*#.*$", "", src, flags=re.M)
        for literal in ('"notice"', "'notice'", '"announcement"', "'announcement'"):
            self.assertNotIn(literal, src,
                             f"{literal} is typed into data_integrity.py — a basis "
                             f"copied by hand is the defect this change removes")

    def test_an_unreachable_page_is_unknown_not_the_effective_basis(self):
        import datetime
        ctx = _Ctx(None)
        ctx.today = datetime.date(2026, 8, 11)
        params, problem = headline_query(ctx, self.by_name["worldwide_recent_90d"])
        self.assertIsNone(params, "falling back to the effective basis is the defect "
                                  "with a retry in front of it")
        self.assertTrue(problem)

    def test_a_headline_with_no_window_never_asks_the_page(self):
        """Three round trips saved, and a no-op not dressed up as a decision."""
        import datetime
        ctx = _Ctx(None)                       # would raise if it were fetched
        ctx.today = datetime.date(2026, 8, 11)
        for name in ("ai_all_time", "worldwide_all_time", "us_all_time"):
            params, problem = headline_query(ctx, self.by_name[name])
            self.assertIsNone(problem)
            self.assertNotIn("date_basis", params)
        self.assertEqual(ctx.fetched, [])

    def test_home_basis_takes_the_basis_and_never_the_scope(self):
        ctx = _Ctx(page_with_basis("notice"))
        ctx.today = __import__("datetime").date(2026, 8, 11)
        basis, problem = pf.home_basis(ctx)
        self.assertIsNone(problem)
        self.assertEqual(basis, {"date_basis": "notice"})
        self.assertNotIn("years", basis,
                         "home_basis must not hand a caller the page's SCOPE")

    def test_a_narrowed_stamp_still_yields_no_basis(self):
        """The allowlist is not bypassed by the new door."""
        ctx = _Ctx('<script>window.ALT_BOOTSTRAP={"aggregate_params":'
                   '{"years":"2026","date_basis":"notice","company":"Meta"}};</script>')
        ctx.today = __import__("datetime").date(2026, 8, 11)
        basis, problem = pf.home_basis(ctx)
        self.assertIsNone(basis)
        self.assertIn("company", problem)


# ---------------------------------------------------------------------------
# 2. the gold set
# ---------------------------------------------------------------------------
class GoldSetWindowMatchesTheGoldSet(unittest.TestCase):

    def test_the_basis_is_the_filing_basis_and_not_strict(self):
        src = RECALL_PY.read_text(encoding="utf-8")
        m = re.search(r'^GOLDSET_DATE_BASIS = "([a-z]+)"$', src, flags=re.M)
        self.assertIsNotNone(m, "recall_precision.py names no date basis at all, so "
                                "every year window in it reads the effective date")
        self.assertEqual(m.group(1), "notice",
                         "strict `announcement` drops every row with no filing date: "
                         "measured 19/40 against 33/40 on 2026-08-11")

    def test_every_year_window_in_recall_precision_names_it(self):
        """A `years=` query with no basis reads the effective date, silently."""
        src = RECALL_PY.read_text(encoding="utf-8")
        src = re.sub(r'"""[\s\S]*?"""', "", src)
        src = re.sub(r"^\s*#.*$", "", src, flags=re.M)
        blocks = re.findall(r"params=\{[^}]*\}", src, flags=re.S)
        windowed = [b for b in blocks if '"years"' in b]
        self.assertTrue(windowed, "no year-windowed query found — this test has "
                                  "stopped reading the file it grades")
        for b in windowed:
            self.assertIn("GOLDSET_DATE_BASIS", b,
                          f"this query windows by year on the API default (the "
                          f"EFFECTIVE date) while its gold set is keyed on the "
                          f"announcement year: {b}")


# ---------------------------------------------------------------------------
# 3. the export
# ---------------------------------------------------------------------------
class ExportCarriesTheDateItWasSelectedOn(unittest.TestCase):

    def test_the_csv_header_names_announcement_date(self):
        src = strip_php_comments(EXPORT_PHP.read_text(encoding="utf-8"))
        header = re.search(r"fputcsv\(\$out, array\(\s*'company_name'.*?\)\);",
                           src, flags=re.S)
        self.assertIsNotNone(header, "the CSV header row was not found")
        self.assertIn("'announcement_date'", header.group(0),
                      "the export accepts date_basis and therefore ships rows "
                      "selected on announcement_date, under a header that does not "
                      "contain it — the file cannot reproduce its own view")

    def test_the_csv_body_emits_the_column(self):
        src = strip_php_comments(EXPORT_PHP.read_text(encoding="utf-8"))
        self.assertIn("$row->announcement_date", src,
                      "the header names a column the row writer never emits")

    def test_header_and_row_are_the_same_width(self):
        """A header one cell wider than its rows silently shifts every column."""
        src = strip_php_comments(EXPORT_PHP.read_text(encoding="utf-8"))
        header = re.search(r"fputcsv\(\$out, array\(\s*('company_name'.*?)\)\);",
                           src, flags=re.S).group(1)
        body = re.search(r"alt_export_walk\(function \(\$row\) use \(\$out\) \{\s*"
                         r"fputcsv\(\$out, array\((.*?)\n        \)\);", src,
                         flags=re.S).group(1)
        # Top-level commas only: the row writer nests calls that carry their own.
        def top_level_items(text):
            depth, n = 0, 1
            for ch in text:
                if ch in "([":
                    depth += 1
                elif ch in ")]":
                    depth -= 1
                elif ch == "," and depth == 0:
                    n += 1
            return n
        self.assertEqual(top_level_items(header.rstrip().rstrip(",")),
                         top_level_items(body.rstrip().rstrip(",")),
                         "the CSV header and the row it labels are different widths")


# ---------------------------------------------------------------------------
# 4. the press page's receipt links (THE EIGHTH PLACE)
# ---------------------------------------------------------------------------
PRESS_PHP = (REPO / "wordpress-plugin" / "ai-layoff-tracker" / "templates"
             / "page-press.php")


class PressReceiptLinksReproduceTheirOwnFigure(unittest.TestCase):
    """Sixteen links labelled "See the rows behind this number" did not.

    Every figure on the press page is computed on hardcoded `layoff_date
    BETWEEN` — the effective date. Both link builders passed the caller's args
    to add_query_arg() with no `date_basis`, and a tracker URL that names no
    basis gets the page default, which since 2.20.4 is the FILING date. Three
    links on this page were fixed in 2.20.11; these sixteen were not.
    """

    def setUp(self):
        self.src = strip_php_comments(PRESS_PHP.read_text(encoding="utf-8"))

    def test_both_link_builders_name_the_basis(self):
        for name in ("$alt_lk", "$alt_plk"):
            m = re.search(re.escape(name) + r" = function \(\$args\).*?\n    \};",
                          self.src, flags=re.S)
            self.assertIsNotNone(m, f"{name} is not the closure this test grades")
            self.assertIn("'date_basis' => 'effective'", m.group(0),
                          f"{name} builds a link to a page that defaults to the "
                          f"filing basis, from a figure counted on the effective "
                          f"one, under the label 'See the rows behind this number'")

    def test_the_basis_is_named_once_not_per_call_site(self):
        """One definition. Sixteen copies is how the previous seven happened.

        SIX, and every one of them is named. Four are the original set: the two
        link builders and the two evidence-tier links. Two arrived with 2.20.99
        and are NOT receipt links, which is the thing this count exists to
        bound:

          * the "which date" block links the SAME year on BOTH bases on
            purpose, side by side, because its whole subject is that the two
            surfaces count differently. It cannot go through $alt_plk for two
            reasons - $alt_plk hardcodes `effective`, so it cannot express the
            filing half; and $alt_plk only exists on a cache MISS, so the
            render path cannot call it at all without fatalling on every cached
            load.
          * the ALT_PRESS_STAMP declares which basis this page's own figures
            were computed on, for railway/published_figures.py to verify
            against /aggregate. It is a statement of fact about the page, not a
            link out of it.

        A seventh would mean a receipt link re-typing the basis again, which is
        exactly the defect. Raise this number only with the site named here.
        """
        self.assertEqual(self.src.count("'date_basis' => 'effective'"), 6,
                         "expected the two link builders, the two evidence-tier "
                         "links, the which-date block's effective half and the "
                         "press stamp; more than that means the basis is being "
                         "re-typed per call site")

    def test_the_which_date_block_links_both_bases_and_only_there(self):
        """The one place that names the FILING basis, and it names both.

        A press page that links the filing basis anywhere else would be sending
        a reader from an effective-basis figure to a filing-basis view - the
        original defect, inverted. The cross-basis block is allowed to do it
        because it is about the difference and prints both."""
        cut = self.src.find("alt-press-which-date")
        self.assertNotEqual(cut, -1, "the which-date block is gone")
        self.assertNotIn("'date_basis' => 'notice'", self.src[:cut],
                         "the press page names the filing basis BEFORE the "
                         "which-date block, so a receipt link is sending readers "
                         "to a view its figure was not computed on")
        block = self.src[cut:]
        # Exactly two, and they are the pair that block is about: the link that
        # opens the tracker on the filing basis, and the stamp declaring which
        # basis the home figure beside it was read on.
        self.assertEqual(block.count("'date_basis' => 'notice'"), 2)
        self.assertIn("'date_basis' => 'effective'", block)

    def test_a_so_far_figure_is_not_linked_to_the_whole_calendar_year(self):
        """The other half. Fixing the basis alone made this link WORSE.

        Measured 2026-08-11: the sentence reads 479,037 verified jobs (Jan 1 to
        today); `years=2026` on the matched effective basis returns 514,111.
        The unfixed link returned 480,685, so the two defects were partly
        cancelling and the basis fix alone would have widened the gap from
        1,648 to 35,074.
        """
        for call in re.findall(r"\$alt_period_items\([^;]*?\);", self.src, flags=re.S):
            if "so far" in call:
                self.assertNotIn("'years'", call,
                                 "a 'so far' figure is computed Jan 1 to today but "
                                 "linked to the whole calendar year")
        for call in re.findall(r"\$alt_build\([^;]*?\)\)", self.src, flags=re.S):
            if "so far" in call:
                self.assertNotIn("'years'", call,
                                 "a 'so far' figure is computed Jan 1 to today but "
                                 "linked to the whole calendar year")


class Provenance(unittest.TestCase):
    """Named rather than omitted, because an unlisted gap reads as coverage."""

    def test_four_of_these_are_regression_bars_not_proof(self):
        # RUN AGAINST ab4dea1, these four PASS, and none of them is evidence for
        # this change. Two are structural (the CSV writer's own width; the fact
        # that a windowless headline never fetches the page); one holds the stamp
        # allowlist published_figures already enforced; one is this test. Listed
        # so nobody reads "17 passing" as seventeen pieces of evidence.
        bars = (
            "ExportCarriesTheDateItWasSelectedOn.test_header_and_row_are_the_same_width",
            "GuardBasisComesFromThePage.test_a_headline_with_no_window_never_asks_the_page",
            "GuardBasisComesFromThePage.test_no_basis_is_hardcoded_in_data_integrity",
            "Provenance.test_four_of_these_are_regression_bars_not_proof",
        )
        # Three of the thirteen reds ERROR rather than FAIL: they reach for
        # published_figures.home_basis(), which does not exist on that tree. An
        # error names a missing function, which is honest but is not the defect,
        # so those three are evidence of the mechanism and not of the bug.
        self.assertEqual(len(bars), 4)


if __name__ == "__main__":
    unittest.main()
