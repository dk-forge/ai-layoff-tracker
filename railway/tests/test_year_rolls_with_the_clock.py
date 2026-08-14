"""THE DEFAULT YEAR IS THE CURRENT YEAR, AND IT ROLLS ON ITS OWN.

The page opens scoped to the current year. Every write of that default already
reads `new Date().getFullYear()`, and the server bootstrap already reads
`current_time('Y')`, so nothing here is pinned to a literal. That is the half
that was already right, and `test_the_default_year_is_never_a_literal` holds it.

THE HALF THAT WAS NOT. Selecting a year is not the same as OFFERING one.
`writeControl` on a multi-select only flips `selected` on options that ALREADY
EXIST — it never creates one — and the Years list is built by `initYears` from
the facets, capped like this:

    var maxY = facets.max_date ? Math.min(parseInt(...), nowY) : nowY;

`Math.min` caps the list at the current year, which is correct: a future-dated
WARN effective date must not put 2028 in a Year dropdown. But the same
expression also lets the list END BELOW the current year whenever the data does,
and then the boot default writes a year that is not in the list. `writeControl`
matches nothing, no year is selected, and the page silently opens on ALL TIME:
the hero, the board, the charts, the table and the exports all widen together,
under copy that says the current year.

It survives today only by luck. `max_date` is 2028-08-25 — a future-dated WARN
notice — so `Math.min` returns the current year and the option exists. The
guard is one corrected row away from being load-bearing, and the day it fires is
1 January, which is the one day nobody is reading the dashboard.

Two independent bars, because either alone can be satisfied wrongly:

  * `initYears` must OFFER the current year no matter where the data ends. Run
    in node against a stubbed select, with the clock moved forward, so the
    assertion is on the options the real function actually appends.
  * The boot default must `ensureOption` before it writes, so a Years list built
    some other way tomorrow still cannot degrade the default into all time.
    That one is a source check and says so; it is the belt to the other's
    braces, not a second reading of the same line.

The future-year cap is a REGRESSION BAR here, not proof of this change: it
passed before and must keep passing. It is named rather than left to look like
evidence.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import jsrun  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS = (PLUGIN / "assets/layoffs.js").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()


def strip_js_comments(text):
    """Block and line comments out of JS, so an assertion cannot match prose.

    Two checks in this repo have passed against defective code by matching a
    comment that described a call instead of the call.
    """
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


JS_NC = strip_js_comments(JS)


# A select stub with just enough DOM to let initYears do its real work: it
# appends options and reads nothing else. Stubbing more would start stubbing
# away the thing under test.
DOM_PREAMBLE = """
var SEL = { options: [], appendChild: function (o) { this.options.push(o); } };
var document = {
    getElementById: function (id) { return id === 'alt-f-years' ? SEL : null; },
    createElement: function () { return { value: '', textContent: '' }; }
};
function years() { return SEL.options.map(function (o) { return o.value; }); }
"""


def freeze_year(year):
    """Move the clock so `new Date().getFullYear()` reads `year` in node.

    initYears takes the current year from the clock, which is the whole point
    of the feature, so the only way to test the rollover is to move the clock.
    """
    return """
var RealDate = Date;
Date = function () {
    if (arguments.length) return new RealDate(arguments[0], arguments[1], arguments[2]);
    return new RealDate(%d, 5, 15);
};
Date.prototype = RealDate.prototype;
""" % year


def run_init_years(now_year, min_date, max_date):
    preamble = jsrun.BASE_PREAMBLE + DOM_PREAMBLE + freeze_year(now_year)
    facets = "{ min_date: %s, max_date: %s }" % (
        "'%s'" % min_date if min_date else "null",
        "'%s'" % max_date if max_date else "null",
    )
    return jsrun.run(["initYears"], preamble, "(initYears(%s), years())" % facets)


class TheCurrentYearIsAlwaysOffered(unittest.TestCase):
    def test_the_current_year_is_offered_when_the_data_ends_last_year(self):
        """1 January: every row still carries last year, the clock does not.

        This is the rollover. Before the fix the list stopped at the data and
        the boot default selected nothing, so the page opened on all time.
        """
        opts = run_init_years(2027, "2002-01-03", "2026-12-28")
        self.assertIn("2027", opts,
                      "initYears built %r with the clock at 2027: the boot default "
                      "writes '2027', writeControl finds no such option, and the "
                      "page silently opens on ALL TIME." % (opts,))
        self.assertEqual(opts[0], "2027", "newest first; %r" % (opts,))

    def test_the_current_year_is_offered_when_there_is_no_data_at_all(self):
        opts = run_init_years(2027, None, None)
        self.assertIn("2027", opts, "empty facets must still offer the current year")

    def test_the_years_run_unbroken_from_the_data_to_now(self):
        """No hole between the last year with rows and the current one."""
        opts = run_init_years(2027, "2024-03-01", "2025-11-02")
        self.assertEqual(opts, ["2027", "2026", "2025", "2024"],
                         "expected an unbroken descending run; got %r" % (opts,))

    def test_no_future_year_is_offered(self):
        """REGRESSION BAR — passed before this change and must keep passing.

        max_date is a future-dated WARN effective date (live: 2028-08-25). A
        Year dropdown offering 2028 in 2026 is a filter that can only return a
        handful of notices under a label a reader will read as a typo.
        """
        opts = run_init_years(2026, "2002-01-03", "2028-08-25")
        self.assertEqual(opts[0], "2026", "future years leaked in: %r" % (opts[:4],))
        self.assertNotIn("2027", opts)
        self.assertNotIn("2028", opts)


class TheDefaultCannotSilentlyBecomeAllTime(unittest.TestCase):
    def test_the_boot_default_ensures_the_option_before_selecting_it(self):
        """SOURCE CHECK (comments stripped), and the reason it is one.

        The write lives inside the facets `.then(...)` of the boot closure,
        which is not a named function and so has no body jsrun can lift. What
        it guards is not a duplicate of initYears: it holds the invariant at the
        point of USE, so any future Years list — server-rendered, cached,
        rebuilt — still cannot leave the default unselected.
        """
        # The one write that establishes the page's default period.
        m = re.search(
            r"if \(noPeriod && document\.getElementById\('alt-f-years'\)\) \{(.*?)\}",
            JS_NC, flags=re.S)
        self.assertIsNotNone(m, "the boot default-period block was renamed or removed")
        block = m.group(1)
        self.assertIn("ensureOption(", block,
                      "the boot default writes a year without ensuring the option "
                      "exists; writeControl never creates one, so a Years list that "
                      "stops short of the current year opens the page on all time. "
                      "Block was:\n%s" % block)
        self.assertLess(block.index("ensureOption("), block.index("writeControl("),
                        "ensureOption must run BEFORE writeControl, not after it")


class TheDefaultYearIsNeverALiteral(unittest.TestCase):
    """REGRESSION BAR — the half that was already right."""

    def test_the_js_default_year_comes_from_the_clock(self):
        self.assertIn("new Date().getFullYear()", JS_NC)
        # A literal year beside the years control is how this gets pinned again.
        for m in re.finditer(r"writeControl\('alt-f-years', \[([^\]]*)\]\)", JS_NC):
            arg = m.group(1)
            self.assertNotRegex(
                arg, r"'20\d\d'",
                "a literal year is being written as the default period: %s" % m.group(0))

    def test_the_server_bootstrap_year_comes_from_the_clock(self):
        self.assertIn("current_time('Y')", DB_PHP,
                      "the bootstrap year must be read from the clock, in site "
                      "timezone, or the inlined first paint pins a year forever")

    def test_the_bootstrap_and_the_js_agree_on_the_basis(self):
        """bootParamsMatch compares every value: a basis split costs the whole
        zero-fetch first paint, silently."""
        self.assertIn("'date_basis' => 'notice'", DB_PHP)
        self.assertIn("var DATE_BASIS = 'notice';", JS_NC,
                      "the JS default basis must be the filing basis the "
                      "bootstrap was computed on")


if __name__ == "__main__":
    unittest.main()
