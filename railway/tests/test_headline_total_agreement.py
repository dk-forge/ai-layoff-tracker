"""Two surfaces, one claim, two different totals. And the caveat nobody saw.

Both were live on asktherecruiter.com on 2026-08-04 and neither was caught by
any check here.

------------------------------------------------------------------------------
1. THE HOME PAGE AND THE PRESS PAGE PUBLISHED DIFFERENT HEADLINE TOTALS.

    home hero    484,468 verified job cuts, 2026
    press page   For 2026 so far, 450,529 job cuts are documented worldwide

A gap of 33,939, on the two surfaces a reporter is most likely to quote.
Neither number is wrong. Rows are dated by the day a cut takes EFFECT and WARN
notices are filed weeks ahead by law, so a calendar-year window legitimately
holds cuts dated later in the year: 450,529 had taken effect, 33,939 had not,
and 484,468 is the two added. Both are reproducible from /aggregate, verified
live before and after this change:

    from=2026-01-01&to=2026-12-31   jobs 956,769 - announced 472,301 = 484,468
    from=2026-01-01&to=2026-08-04   jobs 922,720 - announced 472,191 = 450,529

What was wrong is that each page published one of them and named neither the
other nor the arithmetic. The fix is one sentence, alt_period_split_sentence()
in db.php, rendered verbatim by page-tracker.php and page-press.php and rebuilt
character for character by renderStats() in layoffs.js, plus a "which period"
block on the press page that prints all three figures as a table.

------------------------------------------------------------------------------
2. BOTH "WHY OUR NUMBER DIFFERS" EXPLAINERS WERE SEALED SHUT.

Both were collapsed <details>, so the paragraphs that make our figure
defensible when a reader compares it against an independent national survey had
never been seen by anyone who did not click. The short one is no longer a
<details> at all; the long one defaults open.

AND A WARNING ABOUT HOW TO MEASURE THAT, because the obvious instrument is the
wrong one. Rendered in Chrome at 1280px against the real stylesheet, the body
inside a CLOSED <details> still returns a full layout box:

    before   .alt-why-body   rect 1127x309   display block   innerText 0 chars
    after    .alt-why-body   rect 1127x309   display block   innerText 1240

A width or height probe reads "visible" on the defect and would have passed it.
The signals that actually separate the two states are `details.open` and the
rendered TEXT length. The 0px and 4px readings this defect was first reported
with came from a viewport whose clientWidth was itself 0, which is a third way
to get a number that means nothing. The checks below assert on the element and
its attributes, never on a width.

------------------------------------------------------------------------------
HOW THESE CHECK, and where they cannot.

The sentence tests EXECUTE both implementations, the PHP body through the php
binary and the JS body through node, on the same inputs, and fail on any
difference including whitespace. That is the check that matters: a shared
wording that drifts on one surface is the original defect returning.

The template tests PARSE the rendered HTML out of the templates with
html.parser and assert on elements, not on regex hits, because WordPress is not
available here to render them. They are marked as source checks in their own
docstrings. A browser is not available in this runner, so the
rendered reading is not simulated here; it was taken separately, against both
trees and the real stylesheet, and is quoted above.
"""
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = (PLUGIN / "includes/db.php").read_text()
TRACKER_TPL = (PLUGIN / "templates/page-tracker.php").read_text()
PRESS_TPL = (PLUGIN / "templates/page-press.php").read_text()
CSS = (PLUGIN / "assets/layoffs.css").read_text()

PHP = shutil.which("php")

# The live 2026 split, read off /aggregate on 2026-08-04. Used as the input to
# both implementations so a disagreement shows up as the real published strings.
TO_DATE, CALENDAR = 450529, 484468
LATER = CALENDAR - TO_DATE          # 33,939
AS_OF, PERIOD = "Aug 4, 2026", "2026"


def _strip_php_comments(text):
    """Block and line comments out, so a check cannot match a comment.

    Two checks in this repo passed against defective code because a regex hit a
    comment describing a call rather than the call. PHP string literals can
    contain '//' but none of the assertions below look inside one.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def _php_fn(name):
    """Brace-matched source of one top-level `function <name>(` in db.php."""
    needle = "function %s(" % name
    start = DB_PHP.find(needle)
    assert start != -1, "db.php has no `%s`" % needle
    i = DB_PHP.index("{", start)
    depth, j = 0, i
    while j < len(DB_PHP):
        if DB_PHP[j] == "{":
            depth += 1
        elif DB_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return DB_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


def _php_sentence(to_date, calendar, as_of=AS_OF, period=PERIOD):
    body = _php_fn("alt_period_split_sentence")
    code = "%s echo alt_period_split_sentence(%d, %d, %s, %s);" % (
        body, to_date, calendar, repr(as_of).replace("'", '"'), repr(period).replace("'", '"'))
    proc = subprocess.run([PHP, "-r", code], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError("php failed:\n%s" % proc.stderr.strip())
    return proc.stdout


def _js_sentence(to_date, calendar, as_of=AS_OF, period=PERIOD):
    return jsrun.run(
        ["periodSplitSentence"], jsrun.BASE_PREAMBLE,
        "periodSplitSentence(%d, %d, %s, %s)" % (
            to_date, calendar, repr(as_of).replace("'", '"'), repr(period).replace("'", '"')),
    )


@unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
class TheTwoTotalsAreReconciledInOneSentence(unittest.TestCase):
    """EXECUTES alt_period_split_sentence(), the body both templates render."""

    def test_the_sentence_names_all_three_figures(self):
        s = _php_sentence(TO_DATE, CALENDAR)
        for n in (TO_DATE, LATER, CALENDAR):
            self.assertIn(
                "{:,}".format(n), s,
                "a reader given one of these totals must be able to reach the other "
                "from the sentence alone. %d is missing from %r" % (n, s))

    def test_the_three_figures_add_up(self):
        """The arithmetic the sentence asserts has to hold for the figures it
        prints, or the reconciliation is itself a fourth wrong number."""
        s = _php_sentence(TO_DATE, CALENDAR)
        got = [int(x.replace(",", "")) for x in re.findall(r"\d{1,3}(?:,\d{3})+", s)]
        self.assertEqual(len(got), 3, "expected exactly three figures in %r" % s)
        self.assertEqual(got[0] + got[1], got[2],
                         "%d + %d must equal %d" % (got[0], got[1], got[2]))

    def test_nothing_ahead_means_no_sentence(self):
        """A past year has no remainder, and a sentence explaining a zero
        remainder is noise the hero used to be able to print."""
        self.assertEqual(_php_sentence(CALENDAR, CALENDAR), "")

    def test_php_and_js_produce_the_identical_string(self):
        """The anti-drift check, and the reason the helper exists.

        The server renders the sentence and renderStats() rewrites it on every
        filter change. Two hand-maintained copies of one wording is how the two
        surfaces diverged in the first place.
        """
        php, js = _php_sentence(TO_DATE, CALENDAR), _js_sentence(TO_DATE, CALENDAR)
        self.assertEqual(
            php, js,
            "the server sentence and the client sentence must match character for "
            "character.\n  php: %r\n  js : %r" % (php, js))

    def test_php_and_js_agree_on_the_empty_case_too(self):
        self.assertEqual(_php_sentence(CALENDAR, CALENDAR), _js_sentence(CALENDAR, CALENDAR))


class NeitherSurfaceBuildsItsOwnWording(unittest.TestCase):
    """Source checks: both call sites are PHP that needs WordPress to render.

    They read the comment-stripped template text for the CALL, and for the
    absence of the hand-written string the call replaced.
    """

    PHRASE = "are on notices already filed for effective dates later in"

    def test_the_wording_lives_only_in_the_helper(self):
        self.assertIn(self.PHRASE, DB_PHP, "the helper no longer owns the wording")
        for name, src in (("page-tracker.php", TRACKER_TPL), ("page-press.php", PRESS_TPL),):
            self.assertNotIn(
                self.PHRASE, _strip_php_comments(src),
                "%s builds its own copy of the reconciling sentence. That is how the "
                "home page and the press page came to publish 33,939 apart." % name)

    def test_the_hero_calls_the_helper(self):
        # The hero carries the COMPRESSED reconciliation now, so it calls
        # alt_period_split_short(). Same invariant: the wording is a shared
        # helper with a JS twin, never typed into the template. The press page
        # keeps the full sentence and is pinned by the test below.
        self.assertIn("alt_period_split_short(", _strip_php_comments(TRACKER_TPL))

    def test_the_press_page_calls_the_helper(self):
        self.assertIn("alt_period_split_sentence(", _strip_php_comments(PRESS_TPL))

    def test_the_press_page_computes_the_calendar_year_window(self):
        """The press page only ever queried up to today, so it could not have
        named the calendar total even if it wanted to. It needs the same query
        with the end date moved to 31 December, not a second query shape."""
        src = _strip_php_comments(PRESS_TPL)
        self.assertRegex(
            src, r"\$alt_pstats\(sprintf\('%04d-01-01', \$alt_y2\), sprintf\('%04d-12-31', \$alt_y2\)\)",
            "the calendar-year total must come from the SAME helper every other "
            "statement on the page uses, with only the end date changed")
        self.assertRegex(src, r"'calendar'\s*=>", "the calendar figure must reach the render path")
        self.assertRegex(src, r"'to_date'\s*=>")

    def test_the_press_page_tells_the_reader_where_the_other_total_appears(self):
        """A block that prints both figures without saying which page publishes
        which leaves the reporter to guess which one they saw."""
        src = _strip_php_comments(PRESS_TPL)
        self.assertIn("alt-press-period", src, "the which-period block is gone")
        self.assertIn("tracker home page", src,
                      "the press page must name the surface the calendar figure headlines")

    def test_the_press_yearly_table_excludes_rollup_members(self):
        """It read 935,408 for 2026 against the API's 922,720 for the same
        window and measure, +12,688, on the page that exists to be
        reproducible. Every other query on the page already carried this."""
        src = _strip_php_comments(PRESS_TPL)
        m = re.search(r"SELECT YEAR\(layoff_date\) y.*?ORDER BY y DESC", src, re.S)
        self.assertTrue(m, "the yearly-totals query is gone")
        self.assertIn("superset_of=0", m.group(0).replace("superset_of = 0", "superset_of=0"),
                      "the yearly totals must exclude superset members:\n%s" % m.group(0))


class _Tags(HTMLParser):
    """Every start tag with its attributes, in document order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self._text_of = None
        self.summaries = []      # (index_of_open_details, summary_text)
        self._pending = None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "summary":
            self._pending = len(self.tags) - 1
            self._text_of = ""

    def handle_data(self, data):
        if self._text_of is not None:
            self._text_of += data

    def handle_endtag(self, tag):
        if tag == "summary" and self._pending is not None:
            self.summaries.append((self._pending, " ".join(self._text_of.split())))
            self._pending, self._text_of = None, None


def _parse(template_text):
    """Parse a template's HTML with the PHP blocks removed.

    Regex is not good enough here: the question is which ELEMENT carries a
    class and whether that element has an `open` attribute, and one of the
    wrong-for-the-right-reason failures this suite has already seen was a CSS
    width read as a font size by a pattern that matched the wrong line.
    """
    p = _Tags()
    p.feed(re.sub(r"<\?php.*?\?>", " ", template_text, flags=re.S))
    p.close()
    return p


class TheDifferenceExplainersAreOpenWithoutAClick(unittest.TestCase):
    """Source checks, parsed. Deliberately NOT width checks: a closed <details>
    keeps a full layout box in Chrome, so a rect probe passes on the defect.
    See the module docstring for the before/after rendered reading."""

    def test_the_short_explainer_is_not_a_disclosure_at_all(self):
        p = _parse(TRACKER_TPL)
        owners = [t for t, a in p.tags if "alt-why-lower" in a.get("class", "")]
        self.assertTrue(owners, "the 'why our number is lower' callout is gone")
        self.assertNotIn(
            "details", owners,
            "the callout that defends our figure against an independent national "
            "estimate may not be a collapsed disclosure: it measured 0px wide on a "
            "rendered page, which means no reader had seen it.")

    def test_no_stylesheet_rule_can_collapse_the_short_explainer(self):
        self.assertNotIn(
            ".alt-why-lower[open]", CSS,
            "an [open] rule means something still expects it to be collapsible")

    def test_the_long_explainer_defaults_open(self):
        p = _parse(TRACKER_TPL)
        hit = [(i, txt) for i, txt in p.summaries
               if "differ from other trackers" in txt.lower()]
        self.assertTrue(hit, "the 'why our numbers differ' block is gone")
        idx = hit[0][0]
        # The <details> that owns this summary is the nearest preceding one.
        owner = None
        for j in range(idx - 1, -1, -1):
            if p.tags[j][0] == "details":
                owner = p.tags[j][1]
                break
        self.assertIsNotNone(owner, "the summary is not inside a <details>")
        self.assertIn(
            "open", owner,
            "it measured 4px wide on a rendered page because it defaulted shut. "
            "Attributes present: %r" % sorted(owner))


# ---------------------------------------------------------------------------
# 3. A CACHED PUBLISHED FIGURE HAS TO MOVE WHEN THE DATA MOVES.
# ---------------------------------------------------------------------------
class APublishedFigureCacheTracksTheData(unittest.TestCase):
    """The press page kept publishing the totals the site had before an ingest.

    Live on 2026-08-20, all four caught by `figures_agree_across_surfaces`:

        press "so far" total    523,489    /aggregate said   525,083
        press calendar year     558,253    /aggregate said   559,847
        press "the home page
        headlines N"            524,905    home was serving  526,499

    Every one of them exactly 1,594 low: not a wrong query, one internally
    consistent snapshot of a site that had moved on. The cause was the cache
    KEY. `alt_api_cached`, the facet pages, the company directory and the
    company index all key on `alt_data_ver`, which every data-changing path
    bumps through alt_flush_caches(), so they are orphaned the instant rows
    land. The press page's four caches were keyed on the plugin version alone,
    so nothing short of a deploy or the hourly TTL could move them, and the
    three deletes in alt_flush_caches_on_deploy() that looked like they covered
    this named keys without the suffix and had never matched anything.

    The third figure is the one that makes this a reader's problem rather than
    a checker's: the press page STATES the home page's headline. A number one
    surface remembers about another is a claim, and it was wrong for as long as
    the cache held. Shortening the TTL would only make it rarer.
    """

    # Every transient that holds a number a reader or a journalist can quote.
    FIGURE_CACHES = (
        ("templates/page-press.php",
         ("press_year_stats", "press_sb_groups", "press_statements",
          "press_monthly_compare")),
        ("templates/page-tracker.php", ("fresh_alltime",)),
    )

    @unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
    def _key(self, version, data_ver):
        body = _php_fn("alt_figure_cache_key")
        code = ("define('ALT_VERSION', '%s');"
                "function get_option($n, $d = false) { return %d; }"
                "%s echo alt_figure_cache_key('press_statements');"
                % (version, data_ver, body))
        proc = subprocess.run([PHP, "-r", code], capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError("php failed:\n%s" % proc.stderr.strip())
        return proc.stdout.strip()

    @unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
    def test_a_write_orphans_the_cached_figure(self):
        """The whole defect, executed: same deploy, one more write."""
        self.assertNotEqual(
            self._key("2.20.124", 41), self._key("2.20.124", 42),
            "alt_data_ver moved and the key did not, so the surface would keep "
            "serving the figure it computed before the rows arrived")

    @unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
    def test_a_deploy_orphans_the_cached_figure_too(self):
        """The half that already worked, kept: a deploy can change the SHAPE."""
        self.assertNotEqual(
            self._key("2.20.124", 42), self._key("2.20.125", 42),
            "a deploy that changes what the cached array holds could be served "
            "the old shape")

    def test_every_cached_figure_goes_through_the_one_helper(self):
        """One definition of the key, so a fifth cache cannot be keyed by hand."""
        for rel, names in self.FIGURE_CACHES:
            src = _strip_php_comments((PLUGIN / rel).read_text())
            for name in names:
                for verb in ("get_transient", "set_transient"):
                    self.assertIn(
                        "%s(alt_figure_cache_key('%s')" % (verb, name), src,
                        "%s: %s for '%s' does not go through "
                        "alt_figure_cache_key()" % (rel, verb, name))

    def test_the_helper_folds_in_the_data_version(self):
        body = _strip_php_comments(_php_fn("alt_figure_cache_key"))
        self.assertIn("alt_data_ver", body,
                      "alt_figure_cache_key() no longer reads the data version, "
                      "which is the entire reason it exists")
        self.assertIn("ALT_VERSION", body)

    def test_no_surface_keys_a_figure_on_the_plugin_version_alone(self):
        """The exact shape that shipped the wrong number, banned everywhere.

        `get_transient('alt_something_' . ALT_VERSION)` survives every ingest.
        A cache that legitimately holds no published number (a captcha answer, a
        rate-limit counter) does not need the data version, but it must not be
        keyed on the plugin version either, so this pattern has no honest use.
        """
        offenders = []
        for php in sorted(PLUGIN.rglob("*.php")):
            src = _strip_php_comments(php.read_text())
            for m in re.finditer(r"(get|set)_transient\(\s*'[^']*'\s*\.\s*ALT_VERSION",
                                 src):
                offenders.append("%s: %s" % (php.relative_to(PLUGIN),
                                             m.group(0)))
        self.assertEqual(
            [], offenders,
            "keyed on the plugin version and nothing else, so an ingest cannot "
            "move it. Use alt_figure_cache_key(): " + "; ".join(offenders))

    def test_the_deploy_flush_no_longer_pretends_to_clear_the_press_caches(self):
        """Three deletes that named keys nothing had ever written.

        They are worse than nothing: the next reader of that function believes
        a deploy clears the press page's figures by hand, and stops looking for
        the key that actually holds them.
        """
        main = _strip_php_comments((PLUGIN / "ai-layoff-tracker.php").read_text())
        for dead in ("alt_press_sb_groups", "alt_press_statements",
                     "alt_press_year_stats"):
            self.assertNotIn(
                "delete_transient('%s')" % dead, main,
                "%s has not been a transient key since the version suffix was "
                "added; deleting it is a no-op that reads like protection"
                % dead)


if __name__ == "__main__":
    unittest.main()
