"""Two claims that were true of nothing: a dormant collector's health row, and
a "N+" figure that was not a floor.

Neither is a wrong number in a total. Both are a published statement that does
not describe the thing it names, which is the same family as the basis defects
of 2.20.11 through 2.20.15 and is why they are pinned together.

    1. THE DORMANT COLLECTOR THAT READ AS A DEAD ONE. tracker_diff is scheduled
       daily and exits green daily, but its dormant branch returned before any
       report_source_health() call. Its last health row was therefore frozen at
       2026-07-26, two days before the owner made it dormant, and the PUBLIC
       Tracker Health page said "16d old — collector may have STOPPED" about a
       collector that had run successfully that morning. Staleness is measured
       from checked_at, so nothing about that was going to age out: it would
       have said it forever. This is the CLAUDE.md three-step retirement rule
       missing its third step, arriving through a job that was parked rather
       than retired.

    2. THE FLOOR THAT WAS NOT UNDER THE PAGE. The SERP meta description says
       "N+ jobs cut in <year>" and rounds down 10,000 to make the claim a floor.
       It rounded down from alt_live_numbers(), which counts on the EFFECTIVE
       basis, while the page it describes publishes on the FILING basis. Live on
       2026-08-12: effective to-date 479,410, filed to-date 445,869, and
       floor(479,410) = 470,000, which is ABOVE the cite line a reader lands on.
       The rounding was doing real work and was measured against the wrong side.

HOW THESE CHECK. The health call is RUN: main()'s dormant path executes against
a stubbed reporter and the test reads what it was handed. The description is a
source check over the PHP (it needs WordPress and a database to execute), with
comments stripped first, because a comment describing a floor is exactly what
this file exists to distrust.

Confirmed red on the tree before this change: 6 of 7, run as a file. Three of
the six surface as errors rather than failures because the dormant path made no
health post at all, so the assertion indexes an empty list. That IS the defect
and the message says so. The seventh,
test_the_description_still_reads_the_faq_numbers, is a REGRESSION BAR named
here rather than left to look like proof: the description already read
alt_live_numbers(), and this holds it against a later edit that gives the
snippet its own query and therefore its own unlabelled basis.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAILWAY = ROOT / "railway"
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
PLUGIN_PHP = (PLUGIN / "ai-layoff-tracker.php").read_text()
TRACKER_DIFF = (RAILWAY / "tracker_diff.py").read_text()

sys.path.insert(0, str(RAILWAY))

# tracker_diff imports requests at module scope. CI installs it from the lock;
# a bare dev checkout may not have it, and the path under test makes no HTTP
# call whatsoever, so a stub keeps this runnable everywhere rather than
# skipping (a skipped test on the branch that reports health is how the
# original defect stayed invisible). Only installed when the real one is
# absent, so CI still exercises the real import.
def _no_network(*a, **k):
    raise AssertionError("the dormant path must make no HTTP or model call")


for _name in ("requests", "openai"):  # pragma: no cover - environment dependent
    try:
        __import__(_name)
    except ImportError:
        import types
        _stub = types.ModuleType(_name)
        _stub.get = _stub.post = _no_network
        _stub.Session = _stub.OpenAI = _stub.Client = object
        _stub.exceptions = types.SimpleNamespace(RequestException=Exception)
        _stub.RequestException = Exception
        sys.modules[_name] = _stub


def strip_php_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


PHP_NC = strip_php_comments(PLUGIN_PHP)


def _plugin_fn(name):
    needle = "function %s(" % name
    start = PHP_NC.find(needle)
    assert start != -1, "ai-layoff-tracker.php has no `%s`" % needle
    i = PHP_NC.index("{", start)
    depth, j = 0, i
    while j < len(PHP_NC):
        if PHP_NC[j] == "{":
            depth += 1
        elif PHP_NC[j] == "}":
            depth -= 1
            if depth == 0:
                return PHP_NC[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


class ADormantCollectorStillReportsItself(unittest.TestCase):
    """RUNS tracker_diff.run() on its dormant path with the reporter stubbed."""

    def _run_dormant(self):
        import tracker_diff
        seen = []
        real_feeds, real_inline = tracker_diff.FEEDS, tracker_diff.INLINE
        real_report = tracker_diff.report_source_health
        try:
            tracker_diff.FEEDS, tracker_diff.INLINE = [], []
            tracker_diff.report_source_health = (
                lambda *a, **k: seen.append((a, k)) or True)
            tracker_diff.run()
        finally:
            tracker_diff.FEEDS, tracker_diff.INLINE = real_feeds, real_inline
            tracker_diff.report_source_health = real_report
        return seen

    def test_the_dormant_path_posts_a_health_row(self):
        """The whole defect. No post means checked_at never moves, and the
        public page reads STALE about a job that ran this morning."""
        seen = self._run_dormant()
        self.assertEqual(
            len(seen), 1,
            "the dormant run made %d health posts; it must make exactly one, or "
            "the Tracker Health page keeps aging a collector that is running "
            "correctly" % len(seen))
        self.assertEqual(seen[0][0][0], "tracker_diff",
                         "the dormant run reported under the wrong source id")

    def test_it_does_not_cry_degraded(self):
        """Nothing is broken. A dormant job reporting degraded would put a
        permanent red row on a public transparency page and train the reader
        (and the weekly digest) to ignore it."""
        status = self._run_dormant()[0][0][1]
        self.assertEqual(
            status, "ok",
            "a dormant-by-decision collector reported %r; it ran, it did the "
            "correct thing, and the reason belongs in the detail" % status)

    def test_the_detail_says_dormant_and_how_to_re_arm(self):
        """A status of ok with zero entries is indistinguishable from a broken
        collector unless the row says why. The next person to read this page
        must not re-diagnose it as a dead scraper."""
        args = self._run_dormant()[0][0]
        detail = args[3] if len(args) > 3 else ""
        self.assertRegex(detail.lower(), r"dormant",
                         "the health detail does not say the collector is dormant: %r" % detail)
        self.assertRegex(
            detail, r"BENCHMARK_(COMPANIES|FEED_URLS)",
            "the health detail does not say how to re-arm it, which is the one "
            "thing a reader of this row needs: %r" % detail)

    def test_it_is_not_reported_as_retired(self):
        """Retired is one-way and masked. This is one secret away from live, and
        marking it retired would need the full three-step retirement instead."""
        self.assertNotEqual(self._run_dormant()[0][0][1], "retired")


class TheSnippetFigureIsAFloorUnderThePage(unittest.TestCase):

    def test_the_description_floors_on_the_smaller_of_the_two_bases(self):
        """It rounded down from the effective-basis figure while the page it
        describes publishes on the filing basis, so the 'floor' sat above the
        cite line. Comments are stripped, so a comment claiming a floor cannot
        satisfy this."""
        body = _plugin_fn("alt_tracker_meta_description")
        self.assertRegex(
            body, r"min\(",
            "the description does not take the smaller of the two bases before "
            "rounding, so its 'N+' claim is only a floor under one of the page's "
            "two totals: %s" % body[-700:])
        self.assertRegex(
            body, r"jobs_filed",
            "the description never reads the filing-basis figure, so it cannot "
            "know which of the two is smaller")
        self.assertRegex(body, r"floor\(", "the round-down is gone")

    def test_the_filing_basis_pair_is_computed_where_the_others_are(self):
        """One cached row, one hour, both bases. A second query somewhere else
        is a second cache with a second staleness."""
        body = _plugin_fn("alt_live_numbers")
        self.assertRegex(
            body, r"YEAR\(COALESCE\(announcement_date,\s*layoff_date\)\)",
            "alt_live_numbers() does not measure its window on the filing basis, "
            "so nothing can floor the description against the page's own totals")
        self.assertRegex(body, r"'jobs_filed'\s*=>",
                         "the filing-basis figure never reaches the caller")

    def test_the_description_still_reads_the_faq_numbers(self):
        """Regression bar, named in the module docstring. It already did this."""
        body = _plugin_fn("alt_tracker_meta_description")
        self.assertIn("alt_live_numbers()", body)
        self.assertNotRegex(
            body, r"\$wpdb->(get_row|get_var|prepare)",
            "the description grew its own query, which is its own basis and its "
            "own cache one edit later")


if __name__ == "__main__":
    unittest.main()
