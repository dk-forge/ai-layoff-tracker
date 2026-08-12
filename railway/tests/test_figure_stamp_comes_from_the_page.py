"""THE QUERY BEHIND A PUBLISHED FIGURE IS READ OFF THE PAGE, NEVER TYPED HERE.

WHAT WENT WRONG. On 2026-08-10 the tracker's default date basis moved from the
effective date to the filing date (2.20.4). The commit that made the move says a
default "lives in four places and all four moved": DATE_BASIS in layoffs.js, the
segmented switch's active option, the server bootstrap's $aggregate_params, and
the hero's basis label. There was a fifth place, and it is not in the plugin at
all: `_home_params` in railway/published_figures.py, the stamped query the
AGREEMENT / RECONCILIATION / DRILL_DOWN / CROSS_SURFACE checks send to
/aggregate when they ask "what should this figure be?".

It was a hand-written `{"years": <current year>}` under a docstring promising it
was "exactly what the unfiltered home page sends". After 2.20.4 that promise was
false. The checks asked /aggregate a question the page never asks, got the
effective-basis answer (998,606 jobs), compared it against the filed-basis figure
the page had rendered (965,180), and reported four CORRECT, internally consistent
figures as wrong by 33,426 jobs and 150 companies for as long as nobody noticed.

The failure mode is worth naming precisely, because it is the mirror image of
the one published_figures.py was built to prevent. That module's whole doctrine
is that a checker must not re-derive a figure's query from an assumption, or it
will agree with its own assumption. A hand-copied query does not agree with its
own assumption — it agrees with the page AS OF THE DAY SOMEONE LAST TYPED IT OUT,
and then silently stops. Both are the same bug: the stamp was not attached to
the thing it stamps.

THE FIX THESE TESTS HOLD. The page already publishes the stamp. The bootstrap
writes `window.ALT_BOOTSTRAP.aggregate_params` beside the totals it computed
from them, in the same render, from the same code. The checker reads it there.
A basis change in the plugin now reaches the checker with no second edit,
because there is no longer a second copy to edit.

AND THE OBVIOUS OBJECTION TO THAT FIX, which the last three tests exist for. If
the checker asks whatever the page tells it to ask, a page that quietly bootstraps
a narrowed query would drag the checker along and stay green while publishing a
scoped number under a worldwide, year-to-date label. So the stamp is validated
before it is used: it must name the current year, and it may otherwise carry only
a BASIS (which date a row counts on, which country column it matches). A stamp
carrying anything that narrows the population is a FAIL, in the checker's own
words, naming the offending key. The page may choose its basis. It may not choose
its scope.

These tests were confirmed RED against the pre-fix tree; the assertion is quoted
in the commit message.
"""
import datetime
import json
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_integrity as di                                    # noqa: E402
import published_figures as pf                                 # noqa: E402

YEAR = "2026"
TODAY = datetime.date(2026, 8, 11)

# The two answers the live API gave for the two bases on 2026-08-11, recorded
# rather than invented. `notice` is what the page publishes; `layoff_date` (the
# no-date_basis default) is what the pre-fix checker asked for and graded
# against.
NOTICE_TOTALS = {"jobs": 965_180, "announced_jobs": 484_495, "companies": 2_548,
                 "entries": 3_450, "industries": 19, "countries": 45, "states": 47,
                 "ai_verified_jobs": 42_253, "ai_announced_jobs": 59_425,
                 "ai_broad_jobs": 124_793}
EFFECTIVE_TOTALS = dict(NOTICE_TOTALS, jobs=998_606, companies=2_698, entries=3_689)

HERO = NOTICE_TOTALS["jobs"] - NOTICE_TOTALS["announced_jobs"]      # 480,685


def boot_script(params):
    """The blob the page inlines, in the MINIFIED shape the host actually serves.

    The template writes `window.ALT_BOOTSTRAP = {...}`; what comes back over the
    wire has had the spaces around `=` squeezed out by the host's optimiser. A
    reader that only matched the un-minified form would find no stamp on the real
    page and report UNKNOWN forever, which is a checker that has quietly stopped
    checking.
    """
    blob = {"ver": "2.20.9", "aggregate_params": params,
            "aggregate": {"totals": NOTICE_TOTALS}}
    return "<script>window.ALT_BOOTSTRAP=" + json.dumps(blob) + ";</script>"


def home_html(params, hero=HERO, totals=NOTICE_TOTALS):
    return (
        boot_script(params)
        + f'<span id="alt-hero-total">{hero:,}</span>'
        + f'<span id="alt-hero-ai">{totals["ai_verified_jobs"]:,}</span>'
        + f'<span id="alt-stat-total">{hero:,}</span>'
        + f'<span id="alt-stat-announced">{totals["announced_jobs"]:,}</span>'
        + f'<span id="alt-stat-companies">{totals["companies"]:,}</span>'
        + f'<span id="alt-stat-industries">{totals["industries"]:,}</span>'
        + f'<span id="alt-stat-countries">{totals["countries"]:,}</span>'
        + f'<span id="alt-stat-states">{totals["states"]:,}</span>'
        + f'<span id="alt-stat-ai">{totals["ai_verified_jobs"]:,}</span>'
        + f'<span id="alt-stat-ai-announced">{totals["ai_announced_jobs"]:,}</span>'
        + f'<span id="alt-stat-all">{totals["jobs"]:,}</span>'
        + f'<span id="alt-stat-ai-broad">{totals["ai_broad_jobs"]:,}</span>'
    )


class Server:
    """The live site as it stood on 2026-08-11: /aggregate answers the basis it
    is ASKED for, and the page is rendered on the filed basis.

    The point of answering both bases honestly is that a checker sending the
    wrong one is not rescued by the fixture. It gets the other basis's real
    numbers, exactly as it did in production.
    """

    def __init__(self, stamp):
        self.stamp = stamp
        self.aggregate_queries = []

    def fetch(self, url, timeout):
        path, _, qs = url.partition("?")
        q = dict(urllib.parse.parse_qsl(qs))
        if "wp-json" not in url:
            return home_html(self.stamp).encode()
        if "aggregate" not in path:
            raise AssertionError("check queried an unrouted URL: " + url)
        self.aggregate_queries.append(q)
        totals = NOTICE_TOTALS if q.get("date_basis") == "notice" else EFFECTIVE_TOTALS
        return json.dumps({"totals": totals, "series": [], "reasons": [],
                           "top_countries": [], "top_states": []}).encode()


def run_agreement(stamp):
    srv = Server(stamp)
    res = pf.FigureAgreementInvariant().run(di.Ctx(srv.fetch, 5, "cb", today=TODAY))
    return res, srv


class TheStampComesFromThePage(unittest.TestCase):

    def test_the_checker_asks_on_the_basis_the_page_says_it_used(self):
        """The regression, run end to end: the page states date_basis=notice, so
        that is what /aggregate is asked. Pre-fix this sent years=2026 alone."""
        res, srv = run_agreement({"years": YEAR, "date_basis": "notice"})
        self.assertTrue(srv.aggregate_queries, "the check never called /aggregate")
        sent = srv.aggregate_queries[0]
        self.assertEqual(
            sent.get("date_basis"), "notice",
            "the check asked /aggregate %r; the page said its figures came from "
            "date_basis=notice" % (sent,))
        self.assertEqual(res.state, di.PASS, res.detail)

    def test_a_page_on_the_effective_basis_is_followed_there_too(self):
        """Not hard-coded the other way either. Flip the page's stamp and the
        checker follows, or it has simply swapped one frozen copy for another."""
        stamp = {"years": YEAR, "date_basis": "effective"}
        eff_hero = EFFECTIVE_TOTALS["jobs"] - EFFECTIVE_TOTALS["announced_jobs"]
        srv = Server(stamp)
        srv.fetch = lambda url, timeout, s=srv: (            # page renders effective
            home_html(stamp, hero=eff_hero, totals=EFFECTIVE_TOTALS).encode()
            if "wp-json" not in url else Server.fetch(s, url, timeout))
        res = pf.FigureAgreementInvariant().run(di.Ctx(srv.fetch, 5, "cb", today=TODAY))
        self.assertEqual(srv.aggregate_queries[0].get("date_basis"), "effective")
        self.assertEqual(res.state, di.PASS, res.detail)

    def test_it_still_catches_a_genuinely_wrong_figure(self):
        """The discriminating half. Following the page's stamp must not turn the
        check into one that cannot fail: a hero the API does not produce for the
        page's OWN query is still a FAIL."""
        srv = Server({"years": YEAR, "date_basis": "notice"})
        srv.fetch = lambda url, timeout, s=srv: (
            home_html(s.stamp, hero=444_871).encode()
            if "wp-json" not in url else Server.fetch(s, url, timeout))
        res = pf.FigureAgreementInvariant().run(di.Ctx(srv.fetch, 5, "cb", today=TODAY))
        self.assertEqual(res.state, di.FAIL)
        self.assertIn("444,871", res.detail)
        self.assertIn(f"{HERO:,}", res.detail)


class ThePageCannotDefineItsWayToGreen(unittest.TestCase):
    """The stamp is validated before it is trusted."""

    def test_a_narrowing_stamp_is_a_failure_not_an_instruction(self):
        res, srv = run_agreement({"years": YEAR, "date_basis": "notice",
                                  "country": "United States"})
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("country", res.detail)
        self.assertIn("NARROWED", res.detail)
        self.assertEqual(srv.aggregate_queries, [],
                         "the check queried the narrowed scope instead of "
                         "reporting it")

    def test_the_wrong_year_is_a_failure(self):
        """A year-to-date label over last year's bootstrap."""
        res, _ = run_agreement({"years": "2025", "date_basis": "notice"})
        self.assertEqual(res.state, di.FAIL, res.detail)
        self.assertIn("2025", res.detail)

    def test_a_page_with_no_stamp_is_unknown_never_a_quiet_pass(self):
        def fetch(url, timeout):
            if "wp-json" not in url:
                return home_html({"years": YEAR}).replace(
                    "window.ALT_BOOTSTRAP=", "window.SOMETHING_ELSE=").encode()
            return json.dumps({"totals": EFFECTIVE_TOTALS}).encode()
        res = pf.FigureAgreementInvariant().run(di.Ctx(fetch, 5, "cb", today=TODAY))
        self.assertEqual(res.state, di.UNKNOWN, res.detail)
        self.assertIn("NOT checked", res.detail)


class TheStampIsWhatTheDeployedPluginWrites(unittest.TestCase):
    """Source-side half: the page must actually publish the stamp this reads.

    Read-the-source is the weaker instrument and it is used here only for the one
    thing a fixture cannot establish — that the field this module keys on is the
    field the plugin emits.
    """

    def test_the_bootstrap_publishes_its_aggregate_params(self):
        db = (Path(__file__).resolve().parents[2]
              / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()
        self.assertIn("'aggregate_params' => $aggregate_params", db,
                      "alt_tracker_bootstrap_payload no longer publishes the "
                      "query its inlined totals were computed from, so the "
                      "published-figure checks have nothing to read")


if __name__ == "__main__":
    unittest.main()
