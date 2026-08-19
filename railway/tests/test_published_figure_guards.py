"""Proof that the published-figure guards actually discriminate.

A test that asserts a check FAILS on bad data proves only half of what matters. A
check that returns FAIL unconditionally would pass such a test while being
useless. So every case here is a PAIR: the same check, over a DEFECTIVE payload
and over a CORRECTED one, asserted to disagree. That pairing is the whole point —
five tests this session went green against defective code because they never
exercised the path they claimed to cover.

The defective payloads are not invented. Each one is the shape observed on the
live site on 2026-08-04, recorded here so the guard stays armed after the
rendering code is fixed and the live site stops reproducing it.

The third state gets the same treatment. A dead network must never produce a
pass, and there is a case below for each check that asserts exactly that.
"""
import json
import sys
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_integrity as di                                    # noqa: E402
import published_figures as pf                                 # noqa: E402


# ---------------------------------------------------------------------------
# payload builders — the live shapes, both broken and fixed
# ---------------------------------------------------------------------------
def _totals(jobs=956_769, announced=472_301, **kw):
    t = {"jobs": jobs, "announced_jobs": announced, "entries": 3561,
         "ai_verified_jobs": 42_253, "ai_announced_jobs": 59_425,
         "ai_broad_jobs": 124_793, "companies": 2611, "industries": 19,
         "countries": 44, "states": 47}
    t.update(kw)
    return t


def _agg(totals=None, series=None, reasons=None, countries=None, states=None):
    return {"totals": totals if totals is not None else _totals(),
            "series": series if series is not None else [],
            "reasons": reasons if reasons is not None else [],
            "top_countries": countries or [],
            "top_states": states or []}


VERIFIED = 956_769 - 472_301          # 484,468, the live headline

# The doughnut as it was actually served: computed over ALL jobs while the
# headline beside it publishes the verified basis. Sums to 680,320.
BROKEN_REASONS = [["ai_automation", 108_373], ["possible_ai", 10_415],
                  ["revenue_decline", 84_199], ["restructuring", 236_974],
                  ["merger_acquisition", 803], ["offshoring", 1_500],
                  ["product_discontinuation", 704], ["cost_reduction", 123_712],
                  ["macroeconomic", 70_777], ["closure", 42_863]]

# The same ten tags reconciled to the headline basis.
FIXED_REASONS = [["restructuring", 200_000], ["cost_reduction", 150_000],
                 ["ai_automation", 60_000], ["closure", 40_000],
                 ["macroeconomic", 30_000], ["revenue_decline", 4_468]]

# ---------------------------------------------------------------------------
# THE SIX-COLUMN SHAPE, which is what the API has actually returned all along.
# ---------------------------------------------------------------------------
# [tag, all_jobs, all_ai, None, verified_jobs, verified_ai]. Column 1 is NOT what
# the chart draws; renderReasons() pipes every row through verifiedBasis(), takes
# column 4, and drops whatever is left at zero.
#
# These fixtures are the live 2026 rows, and they are the ones that matter most
# in this file: reading column 1 out of them is precisely what made the checker
# report eight slices as 1.2x to 14.9x wrong when the page was correct. Any
# version of the check that reads column 1 fails the tests below.
LIVE_REASONS = [
    ["ai_automation", 108_373, 96_918, None, 45_748, 37_493],
    ["possible_ai", 10_415, 0, None, 700, 0],
    ["revenue_decline", 84_199, 0, None, 12_876, 0],
    ["restructuring", 236_974, 55_035, None, 73_356, 13_460],
    ["merger_acquisition", 803, 0, None, 803, 0],
    ["offshoring", 1_500, 0, None, 0, 0],          # drawn as no slice at all
    ["product_discontinuation", 704, 0, None, 397, 0],
    ["cost_reduction", 123_712, 36_160, None, 100_774, 27_360],
    ["macroeconomic", 70_777, 0, None, 11_902, 0],
    ["closure", 42_863, 0, None, 41_079, 0],
]
LIVE_DRAWN_SUM = 287_635      # the nine drawn slices, verified basis
LIVE_COL1_SUM = 680_320       # what a checker reading column 1 would report

# The shipped chart code, in the two forms it can arrive in. The check reads the
# deployed asset rather than assuming a column, so every fixture below has to
# serve one of these or the check correctly answers UNKNOWN.
JS_VERIFIED_BASIS = ("function ge(t){return(t||[]).map(function(t){"
                     "var e=null!=t[4]?t[4]:t[1];return[t[0],e]})}")
JS_ALL_JOBS_BASIS = "function ge(t){return(t||[]).map(function(t){return[t[0],t[1]]})}"

# The sentence renderReasons() writes into the card. It lives in the SCRIPT, not
# in the server-rendered body, which is why the disclosure scan reads both.
JS_CARD_NOTE = (
    '"Slices are verified job cuts, the same basis as the Verified job cuts tile.'
    ' Reason tags overlap and are not a breakdown of the total: one event can carry'
    ' several tags, an event whose source states no reason carries none, and the'
    ' slices are not meant to sum to the headline."')

SCRIPT_TAG = '<script src="https://example.test/assets/layoffs.js?ver=9"></script>'

# The page states, beside its own numbers, the query they were computed from —
# and the checks read that stamp rather than carrying a hand-typed copy of it
# (see test_figure_stamp_comes_from_the_page.py for why). Every fixture that
# stands in for the home page has to carry it, or it is standing in for a page
# that does not exist. Written in the MINIFIED shape the host serves.
BOOT_PARAMS = {"years": "2026", "date_basis": "notice"}
BOOT_SCRIPT = ('<script>window.ALT_BOOTSTRAP='
               + json.dumps({"ver": "test", "aggregate_params": BOOT_PARAMS})
               + ';</script>')

HOME_HTML = (
    '<span class="alt-hero-figure-value" id="alt-hero-total">{hero}</span> '
    '<span class="alt-hero-figure-label">{label}</span> '
    '<span class="alt-hero-figure-sub"><b id="alt-hero-ai">42,253</b></span>'
    '<span class="alt-stat-value" id="alt-stat-total">{hero}</span>'
    '<span class="alt-stat-value" id="alt-stat-announced">472,301</span>'
    '<span class="alt-stat-value" id="alt-stat-companies">2,611</span>'
    '<span class="alt-stat-value" id="alt-stat-industries">19</span>'
    '<span class="alt-stat-value" id="alt-stat-countries">44</span>'
    '<span class="alt-stat-value" id="alt-stat-states">47</span>'
    '<span class="alt-stat-value" id="alt-stat-ai">42,253</span>'
    '<span class="alt-stat-label">AI cuts, verified (specific)</span>'
    '<span class="alt-stat-value" id="alt-stat-ai-announced">59,425</span>'
    '<span class="alt-stat-label">AI cuts, announced (planned)</span>'
    '<span class="alt-stat-value" id="alt-stat-all">956,769</span>'
    '<span class="alt-stat-value" id="alt-stat-ai-broad">124,793</span>'
    '<span class="alt-stat-label">AI-linked, broad (wider lens)</span>'
    '{extra}'
)

# An explanation long enough to BE one. The signal is rendered text length, not
# geometry: a width probe cannot tell these two apart, because a closed <details>
# still lays out a full-width box for its summary row.
EXPLAINER_BODY = ("<p>" + ("Every tracker measures a different thing, so the "
                           "numbers should differ. We count verified events. " * 12)
                  + "</p>")
SEALED_EXPLAINER = ('<details class="alt-why-lower"><summary>Why our number is '
                    'lower</summary>' + EXPLAINER_BODY + '</details>')
OPEN_EXPLAINER = ('<details class="alt-why-lower" open><summary>Why our number is '
                  'lower</summary>' + EXPLAINER_BODY + '</details>')
# Open, correctly attributed, and empty. The same defect wearing the right
# attribute, and the only thing that catches it is the character count.
HOLLOW_EXPLAINER = ('<details class="alt-why-lower" open><summary>Why our number '
                    'is lower</summary><p>See below.</p></details>')
# A routine FAQ accordion that happens to use the explainer's vocabulary. This is
# working as designed and must never fail the page on its own.
FAQ_USING_THE_PHRASE = ('<details class="alt-faq-item"><summary>How is this '
                        'different from other layoff trackers?</summary><p>We '
                        'publish a documented floor.</p></details>')


def home_html(hero="484,468", label="verified job cuts, 2026 YTD", extra=""):
    # BOOT_SCRIPT is prepended rather than templated into HOME_HTML: it is JSON,
    # its braces are not format placeholders, and str.format eats them.
    return BOOT_SCRIPT + HOME_HTML.format(
        hero=hero, label=label, extra=(extra or OPEN_EXPLAINER) + SCRIPT_TAG)


# The press page states the query behind its own figures, exactly as the tracker
# page does — see the note on BOOT_SCRIPT above and the docstring of
# CrossSurfaceAgreementInvariant. It has to, because the two surfaces have
# counted on two different date bases since 2.20.4 and a checker that applies
# one page's basis to the other reports a wrong cause for a real defect.
PRESS_BASIS_HOME = {"years": "2026", "date_basis": "notice"}
PRESS_BASIS_EFFECTIVE = {"years": "2026", "date_basis": "effective"}


def press_stamp(params=None, to_date=0, calendar=0, home_basis="notice",
                home_calendar=0):
    return ('<script>window.ALT_PRESS_STAMP='
            + json.dumps({"aggregate_params": params or PRESS_BASIS_HOME,
                          "to_date": to_date, "calendar": calendar,
                          "home": {"date_basis": home_basis,
                                   "calendar": home_calendar}})
            + ';</script>')


def press_html(total="484,468", split="", stamp=None, extra=""):
    return (f"<p>The AI Layoff Tracker verified {total} job cuts worldwide in "
            f"2026 so far.</p>{split}{extra}"
            + (press_stamp() if stamp is None else stamp))


def split_sentence(to_date, later, total, year=2026):
    """The reconciling sentence db.php and layoffs.js both print, verbatim."""
    return (f"<p>{to_date:,} have taken effect as of Aug 4, 2026. The other "
            f"{later:,} are on notices already filed for effective dates later in "
            f"{year}. Together they make the {total:,} total for {year}.</p>")


def split_short(to_date, later, total, year=2026):
    """alt_period_split_short() — the compressed form the HOME page prints."""
    return (f"<p>{to_date:,} have taken effect. The other {later:,} are filed for "
            f"effective dates later in {year}. Together, {total:,}.</p>")


def cross_sentence(home_total, this_total, year=2026):
    """alt_basis_cross_sentence() — the press page naming the home headline."""
    return (f"<p>The tracker home page headlines {home_total:,} for {year}, counted "
            f"by the date each cut was filed. This page counts by the date each cut "
            f"takes effect, which is {this_total:,} for {year}. Neither is a "
            f"correction of the other, and both are reproducible from the public "
            f"API.</p>")


def _router(routes, default=None):
    """A fetch() that answers by URL substring. Raises for anything unrouted, so
    a check that quietly queries something new cannot slip through green."""
    def fetch(url, timeout):
        for frag, body in routes.items():
            if frag in url:
                return body if isinstance(body, bytes) else (
                    json.dumps(body).encode() if not isinstance(body, str)
                    else body.encode())
        if default is not None:
            return (json.dumps(default).encode()
                    if not isinstance(default, str) else default.encode())
        raise AssertionError("check queried an unrouted URL: " + url)
    return fetch


def _ctx(fetch):
    import datetime
    return di.Ctx(fetch, 5, "cb", today=datetime.date(2026, 8, 4))


def _dead(url, timeout):
    raise urllib.error.URLError("network is down")


class ReconciliationTest(unittest.TestCase):
    """Parts sum to the whole, or the card states why not."""

    # Geography blocks must be present or the check correctly reports UNKNOWN for
    # them — which is right, and which is why these fixtures carry them.
    COUNTRIES = [["United States", 0, 0, 0, 300_000], ["Germany", 0, 0, 0, 50_000]]
    STATES = [["CA", 0, 0, 0, 200_000], ["TX", 0, 0, 0, 100_000]]

    def _run(self, reasons, html, js=JS_VERIFIED_BASIS):
        fetch = _router({
            "layoffs.js": js,
            "ai-layoff-tracker/": html,
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=reasons,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED}],
                              countries=self.COUNTRIES, states=self.STATES),
        })
        return pf.FigureReconciliationInvariant().run(_ctx(fetch))

    # -- the six-column shape: read the column the shipped chart draws ------
    def test_the_sum_is_taken_over_the_column_the_chart_actually_draws(self):
        # THE CHECKER'S OWN DEFECT, pinned. Served the live rows and the live
        # chart code, a check that reads column 1 reports 680,320 and a 1.41x
        # discrepancy that is not on the page. The drawn slices sum to 287,635.
        r = self._run(LIVE_REASONS, home_html(extra=OPEN_EXPLAINER + JS_CARD_NOTE))
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn(f"{LIVE_DRAWN_SUM:,}", r.detail)
        self.assertNotIn(f"{LIVE_COL1_SUM:,}", r.detail,
                         "the check is still reporting a column the chart does "
                         "not draw")

    def test_it_follows_the_chart_code_rather_than_preferring_a_column(self):
        # Same rows, but the deployed asset draws column 1. Then column 1 IS what
        # the reader sees, it outruns the headline, and nothing on the card
        # discloses overlap — so this must fail. A check hard-coded to the
        # verified column would pass here and miss a real regression.
        r = self._run(LIVE_REASONS, home_html(), js=JS_ALL_JOBS_BASIS)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn(f"{LIVE_COL1_SUM:,}", r.detail)

    def test_an_unreadable_chart_asset_is_unknown_not_pass(self):
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=LIVE_REASONS,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED}],
                              countries=self.COUNTRIES, states=self.STATES),
        }, default=None)

        def no_js(url, timeout):
            if "layoffs.js" in url:
                raise urllib.error.URLError("asset 404")
            return fetch(url, timeout)
        r = pf.FigureReconciliationInvariant().run(_ctx(no_js))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertNotEqual(r.state, di.PASS)

    def test_a_sum_below_the_headline_needs_the_untagged_sentence(self):
        # The drawn slices land 196,833 short because rows with no reason tag are
        # on no slice. That is honest ONLY if the card says so. The overlap
        # sentence alone does not cover it: overlap explains a sum that is too
        # HIGH, and pointing it at a sum that is too low explains nothing.
        overlap_only = ('<p>Reason tags overlap: one event can carry more than '
                        'one reason.</p>')
        r = self._run(LIVE_REASONS, home_html(extra=OPEN_EXPLAINER + overlap_only))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("BELOW", r.detail)

    def test_a_slice_larger_than_the_headline_fails_however_it_is_disclosed(self):
        # A slice is a subset. One bigger than the population is a basis error
        # and no sentence on the card can make it true.
        huge = [["restructuring", 0, 0, None, VERIFIED + 1, 0]]
        r = self._run(huge, home_html(extra=OPEN_EXPLAINER + JS_CARD_NOTE))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("cannot be larger than", r.detail)

    def test_fails_when_the_doughnut_outruns_its_own_headline(self):
        # THE LIVE DEFECT: slices summing to 680,320 beside a 484,468 headline.
        r = self._run(BROKEN_REASONS, home_html())
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("680,320", r.detail)
        self.assertIn("484,468", r.detail)

    def test_passes_once_the_slices_are_on_the_headline_basis(self):
        r = self._run(FIXED_REASONS, home_html())
        self.assertEqual(r.state, di.PASS)

    def test_overlap_is_allowed_only_when_the_card_says_so(self):
        # Same broken sum, but now the card tells the reader why it does not add
        # up. That is the escape hatch the brief allows, and it must be the ONLY
        # one — the number itself has not changed.
        disclosed = home_html(extra=OPEN_EXPLAINER +
                              "<p>A cut can carry more than one reason, so these "
                              "slices overlap.</p>")
        r = self._run(BROKEN_REASONS, disclosed)
        self.assertEqual(r.state, di.PASS)

    def test_a_partial_month_drawn_as_complete_fails(self):
        # The monthly chart is disjoint buckets, so it must equal the headline
        # exactly. This is the pre-fix shape: a partial month drawn short.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED - 40_000}]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("cannot reach the published number", r.detail)

    # A SUM AND A BUCKET LABEL FAIL INDEPENDENTLY, which is why the series has
    # two slices and not one. The 2026-08-11 defect showed both at once (the
    # chart drew 2027-02 and 2027-03 inside a 2026 view AND landed 7 short), but
    # a compensating pair of stray buckets sums to exactly the right number, and
    # a dropped row shortens a sum without adding a bucket. Each of the three
    # tests below isolates one of those cases.
    #
    # This is also why every series fixture in this file now carries a `month`
    # key: the real payload always has one, and a bucket with no label cannot be
    # held against the window it is drawn in.

    def test_a_bucket_outside_the_charted_year_fails(self):
        # THE LIVE DEFECT, in miniature: rows selected on
        # COALESCE(announcement_date, layoff_date) and stacked on layoff_date,
        # so notices filed in 2026 for 2027 effective dates opened 2027 buckets
        # inside a view labelled 2026.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED - 500},
                                      {"month": "2027-03", "verified_jobs": 500}]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("2027-03", r.detail)
        self.assertIn("outside it", r.detail)

    def test_stray_buckets_fail_even_when_the_total_is_right(self):
        # The case a sum check cannot see. These buckets add up to the headline
        # exactly; one of them is still in a year the filter excluded.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED - 500},
                                      {"month": "2027-02", "verified_jobs": 500}]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("2027-02", r.detail)
        self.assertNotIn("cannot reach the published number", r.detail,
                         "the sum slice should be silent here: it is correct")

    def test_buckets_with_no_month_label_are_unknown_not_pass(self):
        # Absence of a signal is never a pass in this codebase. A series whose
        # rows carry no month cannot be held against a window, and saying so is
        # the whole difference between UNKNOWN and PASS.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"verified_jobs": VERIFIED}]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertNotEqual(r.state, di.PASS)

    def test_scoped_bars_are_reconciled_against_their_own_denominator(self):
        # The ~104,000 defect: a US-scoped list measured against a WORLDWIDE
        # total. The US bars here sum to 450,000 — under the worldwide 484,468,
        # so a naive check passes — but over the US total of 400,000.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"month": "2026-06", "verified_jobs": VERIFIED}],
                              states=[["CA", 0, 0, 0, 450_000]]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("different bases", r.detail)

    def test_a_dead_network_is_unknown_not_pass(self):
        r = pf.FigureReconciliationInvariant().run(_ctx(_dead))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertNotEqual(r.state, di.PASS)


class DrillDownTest(unittest.TestCase):
    """Tapping a slice returns the count it displays."""

    def _run(self, reasons, drill, js=JS_VERIFIED_BASIS):
        def fetch(url, timeout):
            if "layoffs.js" in url:
                return js.encode()
            if "ai-layoff-tracker/" in url and "wp-json" not in url:
                return home_html().encode()
            for tag, tot in drill.items():
                if "reasons=" + tag in url:
                    return json.dumps(_agg(tot)).encode()
            return json.dumps(_agg(reasons=reasons)).encode()
        return pf.DrillDownInvariant().run(_ctx(fetch))

    def test_fails_on_the_slice_that_returns_a_fraction_of_what_it_shows(self):
        # THE LIVE DEFECT: possible_ai displays 10,415 and the click returns 700.
        r = self._run([["possible_ai", 10_415]],
                      {"possible_ai": _totals(jobs=1_400, announced=700)})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("14.9x", r.detail)

    def test_fails_when_the_click_returns_nothing_at_all(self):
        r = self._run([["offshoring", 1_500]],
                      {"offshoring": _totals(jobs=0, announced=0)})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("nothing at all", r.detail)

    def test_passes_when_the_slice_and_the_click_agree(self):
        r = self._run([["closure", 41_079]],
                      {"closure": _totals(jobs=41_079, announced=0)})
        self.assertEqual(r.state, di.PASS)

    # -- the six-column shape -------------------------------------------------
    def test_the_displayed_value_comes_from_the_column_the_chart_draws(self):
        # THE CHECKER'S OWN DEFECT, pinned. Every one of these nine slices agrees
        # exactly with its drill-down on the page. Reading column 1 instead
        # reports eight of them as 1.2x to 14.9x wrong, and every one of those
        # ratios is arithmetic on a number no reader can see.
        drill = {t: _totals(jobs=v, announced=0)
                 for t, v in (("ai_automation", 45_748), ("possible_ai", 700),
                              ("revenue_decline", 12_876), ("restructuring", 73_356),
                              ("merger_acquisition", 803),
                              ("product_discontinuation", 397),
                              ("cost_reduction", 100_774), ("macroeconomic", 11_902),
                              ("closure", 41_079))}
        r = self._run(LIVE_REASONS, drill)
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertNotIn("14.9x", r.detail)

    def test_a_slice_that_is_never_drawn_is_named_undrawn_not_broken(self):
        # offshoring has 1,500 all-jobs and 0 verified, so verifiedBasis() drops
        # it and there is no wedge to tap. Reporting "tapping it returns nothing
        # at all" about a slice that does not exist is a false alarm, and a false
        # alarm is how the next real one gets ignored.
        r = self._run(LIVE_REASONS, {t: _totals(jobs=v, announced=0)
                                     for t, v in (("ai_automation", 45_748),
                                                  ("possible_ai", 700),
                                                  ("revenue_decline", 12_876),
                                                  ("restructuring", 73_356),
                                                  ("merger_acquisition", 803),
                                                  ("product_discontinuation", 397),
                                                  ("cost_reduction", 100_774),
                                                  ("macroeconomic", 11_902),
                                                  ("closure", 41_079))})
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn("untappable", r.detail)
        self.assertIn("offshoring", r.detail)

    def test_it_still_catches_a_real_mismatch_on_the_drawn_column(self):
        # Proof the fix did not just make the check agreeable: same six-column
        # shape, but the click returns a third of the drawn slice.
        rows = [["ai_automation", 108_373, 0, None, 45_748, 0]]
        r = self._run(rows, {"ai_automation": _totals(jobs=15_000, announced=0)})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("45,748", r.detail)

    def test_an_unreadable_chart_asset_is_unknown_not_pass(self):
        def fetch(url, timeout):
            if "layoffs.js" in url:
                raise urllib.error.URLError("asset 404")
            if "ai-layoff-tracker/" in url and "wp-json" not in url:
                return home_html().encode()
            return json.dumps(_agg(reasons=LIVE_REASONS)).encode()
        r = pf.DrillDownInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertIn("NOT", r.detail)

    def test_what_it_skipped_is_named_never_silently_dropped(self):
        r = self._run([["closure", 41_079], ["tiny", 12]],
                      {"closure": _totals(jobs=41_079, announced=0)})
        self.assertIn("< floor 200", r.detail)
        self.assertIn("tiny", r.detail)

    def test_a_dead_network_is_unknown_not_pass(self):
        r = pf.DrillDownInvariant().run(_ctx(_dead))
        self.assertEqual(r.state, di.UNKNOWN)


class AgreementTest(unittest.TestCase):
    """The page's number equals the API's answer to that number's own query."""

    def _run(self, hero):
        fetch = _router({"ai-layoff-tracker/": home_html(hero=hero),
                         "aggregate": _agg()})
        return pf.FigureAgreementInvariant().run(_ctx(fetch))

    def test_fails_when_the_page_and_the_api_disagree(self):
        # The pre-fix hero: the page shows a figure the API does not produce for
        # the page's own query.
        r = self._run("444,871")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("444,871", r.detail)
        self.assertIn("484,468", r.detail)

    def test_passes_when_they_agree(self):
        self.assertEqual(self._run("484,468").state, di.PASS)

    def test_a_missing_figure_is_unknown_never_a_quiet_pass(self):
        # Stamped, so this is a page whose FIGURES are gone — not one whose
        # stamp is gone, which is a different UNKNOWN with its own test.
        fetch = _router({"ai-layoff-tracker/": BOOT_SCRIPT + "<p>no figures here</p>",
                         "aggregate": _agg()})
        r = pf.FigureAgreementInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertIn("NOT being checked", r.detail)

    def test_a_dead_network_is_unknown_not_pass(self):
        self.assertEqual(pf.FigureAgreementInvariant().run(_ctx(_dead)).state,
                         di.UNKNOWN)


class BasisTest(unittest.TestCase):
    """A label names its unit, its period and its geography."""

    def _run(self, label):
        fetch = _router({"ai-layoff-tracker/": home_html(label=label)})
        return pf.BasisDisclosureInvariant().run(_ctx(fetch))

    def test_fails_when_the_hero_does_not_state_its_geography(self):
        # THE LIVE DEFECT: "verified job cuts, 2026 YTD" names unit and period
        # but not geography, so a reader cannot tell whether it is comparable to
        # a national estimate.
        r = self._run("verified job cuts, 2026 YTD")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("geography", r.detail)

    def test_fails_when_the_hero_states_no_period(self):
        r = self._run("verified job cuts worldwide")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("period", r.detail)

    def test_passes_when_unit_period_and_geography_are_all_stated(self):
        self.assertEqual(self._run("verified job cuts worldwide, 2026 YTD").state,
                         di.PASS)

    def test_the_shipped_hero_wording_states_all_three(self):
        # THE LIVE DEFECT and its fix. The hero read "verified job cuts, 2026":
        # no geography, and a bare year that does not say whether the window is
        # what has happened or what is on file.
        self.assertEqual(self._run("verified job cuts, 2026").state, di.FAIL)
        self.assertEqual(
            self._run("verified job cuts worldwide, calendar year 2026").state,
            di.PASS)

    def test_the_label_is_read_whole_when_it_contains_nested_spans(self):
        # The shipped label wraps geography and period in their own spans so
        # renderStats() can swap them per filter. Read with a flat regex the text
        # truncates at the first inner </span> and the check reports a missing
        # period that is printed on the page — a false FAIL manufactured by the
        # reader, not by the page.
        nested = ('verified job cuts <span id="alt-hero-total-geo">worldwide</span>'
                  ', <span id="alt-hero-total-period">calendar year 2026</span>')
        self.assertEqual(self._run(nested).state, di.PASS)

    def test_a_bare_year_is_still_not_a_period(self):
        # Deliberate and load-bearing: rows are dated by EFFECTIVE date, so the
        # 2026 window holds notices filed for dates still ahead. "2026" alone
        # leaves a reader unable to tell two figures 33,939 apart from each other,
        # which is exactly the confusion the press page had to reconcile.
        r = self._run("verified job cuts worldwide, 2026")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("period", r.detail)

    def test_two_ai_figures_sharing_one_label_fail(self):
        clash = HOME_HTML.format(
            hero="484,468", label="verified job cuts worldwide, 2026 YTD",
            extra=OPEN_EXPLAINER).replace(
            "AI-linked, broad (wider lens)", "AI cuts, verified (specific)")
        r = pf.BasisDisclosureInvariant().run(
            _ctx(_router({"ai-layoff-tracker/": clash})))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("share one label", r.detail)

    def test_a_dead_network_is_unknown_not_pass(self):
        self.assertEqual(pf.BasisDisclosureInvariant().run(_ctx(_dead)).state,
                         di.UNKNOWN)


class CrossSurfaceTest(unittest.TestCase):
    """One figure on two pages is one number."""

    # The API's two periods for the live 2026 window, which the reconciliation
    # branch checks both figures against. Prose cannot substitute for these.
    API = _totals(jobs=956_008, announced=472_301,
                  to_date_jobs=921_959, to_date_announced_jobs=472_191)
    CALENDAR, TO_DATE = 483_707, 449_768        # 956,008-472,301 / 921,959-472,191

    def _run(self, hero, press, health=None, quality=None,
             home_split="", press_split="", totals=None):
        health = health or {"newsapi": {"status": "retired"}}
        quality = quality or {"source_health": {"newsapi": {"status": "retired"}}}
        return pf.CrossSurfaceAgreementInvariant().run(_ctx(_router({
            "press/": press_html(press, press_split),
            "layoffs.js": JS_VERIFIED_BASIS,
            "ai-layoff-tracker/": home_html(hero=hero,
                                            extra=OPEN_EXPLAINER + home_split),
            "source-health": health,
            "quality-status": quality,
            "aggregate": _agg(totals if totals is not None else self.API),
        })))

    def test_fails_when_home_and_press_publish_different_headlines(self):
        # THE LIVE DEFECT: two totals, nothing on either page tying them together.
        r = self._run("484,468", "450,529")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("33,939", r.detail)

    def test_passes_when_both_pages_publish_the_same_number(self):
        self.assertEqual(self._run("484,468", "484,468").state, di.PASS)

    # -- a STATED and ARITHMETICALLY CORRECT reconciliation ------------------
    def _reconciled(self, **kw):
        split = split_sentence(self.TO_DATE, self.CALENDAR - self.TO_DATE,
                               self.CALENDAR)
        kw.setdefault("home_split", split)
        kw.setdefault("press_split", split)
        return self._run(f"{self.CALENDAR:,}", f"{self.TO_DATE:,}", **kw)

    def test_two_correct_periods_that_add_up_are_allowed(self):
        # Rows are dated by EFFECTIVE date and WARN notices are filed weeks ahead
        # by law, so the calendar year genuinely has two right answers. Both are
        # the API's own figures and both pages print the sentence that adds them.
        r = self._reconciled()
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn("33,939", r.detail)
        self.assertIn("verified against the API", r.detail)

    def test_a_reconciling_sentence_whose_subtraction_is_wrong_still_fails(self):
        # The escape hatch is arithmetic, not prose. Same two correct figures,
        # same sentence shape, a residual that does not close the gap.
        bad = split_sentence(self.TO_DATE, 12_000, self.CALENDAR)
        r = self._run(f"{self.CALENDAR:,}", f"{self.TO_DATE:,}",
                      home_split=bad, press_split=bad)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("does not add up", r.detail)

    def test_a_gap_neither_figure_explains_still_fails(self):
        # Both pages carry a well-formed sentence, but the press figure is not
        # the API's to-date total on the basis the press page itself stamped —
        # so the pair is simply two different answers with an explanation draped
        # over it. The home figure is the API's calendar total here on purpose,
        # so the branch under test is the PRESS one and not the home one.
        split = split_sentence(450_529, 33_178, 483_707)
        r = self._run(f"{self.CALENDAR:,}", "450,529",
                      home_split=split, press_split=split)
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("not the to-date verified total its own stamped query", r.detail)

    def test_an_explanation_on_only_one_page_still_fails(self):
        # A reader on the press page who never sees the home page's sentence has
        # no route to the other figure.
        split = split_sentence(self.TO_DATE, self.CALENDAR - self.TO_DATE,
                               self.CALENDAR)
        r = self._run(f"{self.CALENDAR:,}", f"{self.TO_DATE:,}",
                      home_split=split, press_split="")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("press page does not print", r.detail)

    def test_an_api_that_cannot_answer_is_unknown_not_pass(self):
        r = self._reconciled(totals=_totals(jobs=956_008, announced=472_301))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertNotEqual(r.state, di.PASS)

    # -- TWO BASES, which is what the live site actually publishes -----------
    #
    # Measured 2026-08-19. The home page counts calendar-year 2026 on the FILING
    # basis; the press page counts to-date on the EFFECTIVE basis, by a written
    # owner decision. Both figures are right. The 2,650 gap between them is the
    # residue of a +33,348 basis difference and a -35,998 period difference
    # nearly cancelling, which is why "it is probably cache" was the tempting
    # answer and was wrong.
    NOTICE_API = _totals(jobs=990_873, announced=465_968,
                         to_date_jobs=954_572, to_date_announced_jobs=465_858)
    EFFECTIVE_API = _totals(jobs=1_024_221, announced=465_968,
                            to_date_jobs=988_113, to_date_announced_jobs=465_858)
    N_CAL, N_TD = 524_905, 488_714        # filing basis: home's two periods
    E_CAL, E_TD = 558_253, 522_255        # effective basis: press's two periods

    def _two_bases(self, cross=None, press_stamp_kw=None, hero=None):
        """The live shape: home on the filing basis, press on the effective one.

        `cross` is the sentence the press page prints naming the home figure;
        pass "" to model the page that prints none, which is what the live site
        did until 2.20.99.
        """
        if cross is None:
            cross = cross_sentence(self.N_CAL, self.E_CAL)
        kw = {"params": PRESS_BASIS_EFFECTIVE, "to_date": self.E_TD,
              "calendar": self.E_CAL, "home_basis": "notice",
              "home_calendar": self.N_CAL}
        kw.update(press_stamp_kw or {})
        return pf.CrossSurfaceAgreementInvariant().run(_ctx(_router({
            "press/": press_html(f"{self.E_TD:,}",
                                 split=split_sentence(self.E_TD,
                                                      self.E_CAL - self.E_TD,
                                                      self.E_CAL),
                                 stamp=press_stamp(**kw), extra=cross),
            "layoffs.js": JS_VERIFIED_BASIS,
            "ai-layoff-tracker/": home_html(
                hero=f"{hero if hero is not None else self.N_CAL:,}",
                extra=OPEN_EXPLAINER + split_short(self.N_TD,
                                                   self.N_CAL - self.N_TD,
                                                   self.N_CAL)),
            "source-health": {"newsapi": {"status": "retired"}},
            "quality-status": {"source_health": {"newsapi": {"status": "retired"}}},
            # ORDER MATTERS: _router answers on the first substring that hits,
            # so the basis-qualified route has to precede the bare one. Two
            # bases mean two different answers from one endpoint, and a fixture
            # that returns one of them for both is the defect under test.
            "date_basis=effective": _agg(self.EFFECTIVE_API),
            "aggregate": _agg(self.NOTICE_API),
        })))

    def test_two_bases_that_each_reconcile_and_are_named_pass(self):
        # The fixed shape. Nothing here is equal to anything else: the pass is
        # earned by four separate subtractions and one cross-reference.
        r = self._two_bases()
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn("answer two different questions and both pages say so",
                      r.detail)
        self.assertIn(f"{self.N_CAL:,}", r.detail)

    def test_a_stale_cross_reference_to_the_other_surface_fails(self):
        # THE LIVE DEFECT, pinned. The press page said its own 558,253 was "the
        # figure the tracker home page headlines". That was true until the home
        # default moved to the filing basis on 2026-08-10 and was wrong by
        # 33,348 when it was found. Nothing could notice, because the claim was
        # a sentence somebody typed rather than a number somebody read.
        r = self._two_bases(cross=cross_sentence(self.E_CAL, self.E_CAL))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("read, not remembered", r.detail)
        self.assertIn(f"{self.E_CAL:,}", r.detail)

    def test_two_bases_with_nothing_tying_them_together_fails(self):
        # Two correct figures, each reconciling on its own basis, and a reader
        # who opens both still gets two answers. That is the whole defect and
        # arithmetic alone does not close it.
        r = self._two_bases(cross="")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("does not name the home page's headline figure", r.detail)

    def test_a_press_page_that_states_no_basis_fails(self):
        # NOT unknown. A quotable figure whose basis is unstated is exactly what
        # this module exists to fail, and it is how the check came to measure
        # the press page with the home page's basis in the first place.
        r = self._two_bases(press_stamp_kw=None, cross=None)
        self.assertEqual(r.state, di.PASS)      # control
        r = pf.CrossSurfaceAgreementInvariant().run(_ctx(_router({
            "press/": press_html(f"{self.E_TD:,}", stamp=""),
            "layoffs.js": JS_VERIFIED_BASIS,
            "ai-layoff-tracker/": home_html(hero=f"{self.N_CAL:,}"),
            "source-health": {"newsapi": {"status": "retired"}},
            "quality-status": {"source_health": {"newsapi": {"status": "retired"}}},
            "date_basis=effective": _agg(self.EFFECTIVE_API),
            "aggregate": _agg(self.NOTICE_API),
        })))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("states no window.ALT_PRESS_STAMP", r.detail)

    def test_the_press_stamp_cannot_narrow_its_way_to_agreement(self):
        # The stamp picks a BASIS, never a scope. A press page that quietly
        # scoped its own population would otherwise be able to define any
        # figure into agreement with the API.
        r = self._two_bases(press_stamp_kw={
            "params": {"years": "2026", "date_basis": "effective",
                       "country": "United States"}})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("NARROWED query", r.detail)

    def test_the_home_pages_compressed_sentence_counts_as_a_reconciliation(self):
        # alt_period_split_short() is what the home page actually prints; the
        # long form is the press page's. Reading only the long one would score
        # the home page as printing no reconciliation while it prints one.
        self.assertIsNotNone(
            pf.CrossSurfaceAgreementInvariant()._split_of(
                split_short(self.N_TD, self.N_CAL - self.N_TD, self.N_CAL)))

    def test_equal_numbers_on_two_different_bases_are_not_agreement(self):
        # The tolerance is for two fetches taken seconds apart while a collector
        # writes. It is not a licence for two questions to arrive at one number.
        # Same figure on both surfaces, two stated bases: this must go the long
        # way and be judged on arithmetic, not waved through as "they agree".
        r = pf.CrossSurfaceAgreementInvariant().run(_ctx(_router({
            "press/": press_html(f"{self.N_CAL:,}",
                                 stamp=press_stamp(params=PRESS_BASIS_EFFECTIVE)),
            "layoffs.js": JS_VERIFIED_BASIS,
            "ai-layoff-tracker/": home_html(hero=f"{self.N_CAL:,}"),
            "source-health": {"newsapi": {"status": "retired"}},
            "quality-status": {"source_health": {"newsapi": {"status": "retired"}}},
            "date_basis=effective": _agg(self.EFFECTIVE_API),
            "aggregate": _agg(self.NOTICE_API),
        })))
        self.assertNotEqual(r.state, di.PASS, r.detail)

    def test_fails_when_a_retired_collector_is_published_as_live(self):
        # THE LIVE DEFECT: /source-health masks four retired collectors and
        # /quality-status, which the health page reads, does not.
        r = self._run("484,468", "484,468",
                      quality={"source_health": {"newsapi": {"status": "ok"}}})
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("published as live", r.detail)
        self.assertIn("newsapi", r.detail)

    def test_a_dead_network_is_unknown_not_pass(self):
        self.assertEqual(pf.CrossSurfaceAgreementInvariant().run(_ctx(_dead)).state,
                         di.UNKNOWN)


class ComparisonBasisTest(unittest.TestCase):
    """The explanation of the difference is visible, not sealed away."""

    def _run(self, html):
        return pf.ComparisonBasisInvariant().run(
            _ctx(_router({"ai-layoff-tracker/": html})))

    def test_fails_when_the_explainer_is_sealed_in_a_closed_disclosure(self):
        # THE DEFECT: a <details> with no `open` starts closed, so the reader
        # meets a summary line and nothing else.
        r = self._run(home_html(extra=SEALED_EXPLAINER))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("collapsed disclosure", r.detail)

    def test_fails_when_there_is_no_explainer_at_all(self):
        r = self._run('<span id="alt-hero-total">484,468</span>')
        self.assertEqual(r.state, di.FAIL)

    def test_an_open_explainer_with_text_in_it_passes(self):
        # The two signals that discriminate are `open` and RENDERED TEXT LENGTH.
        # Reporting UNKNOWN here on the grounds that pixel geometry is out of
        # reach was measuring the wrong thing: a closed <details> keeps a full
        # layout box, so width never distinguished these cases anyway.
        r = self._run(home_html(extra=OPEN_EXPLAINER))
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertIn("characters of explanation are readable", r.detail)

    def test_an_open_but_empty_panel_is_the_same_defect_and_fails(self):
        # This is why the character count is asserted and not just the attribute.
        r = self._run(home_html(extra=HOLLOW_EXPLAINER))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("characters of text", r.detail)

    def test_a_collapsed_faq_using_the_same_phrase_does_not_fail_the_page(self):
        # THE FALSE POSITIVE, pinned. "documented floor" also appears inside a
        # routine FAQ accordion, which is collapsed because that is what an
        # accordion is. Failing the page for it reported a sealed explainer on a
        # page whose explainer was open and five thousand characters long — and a
        # guard that cries wolf is a guard that gets muted.
        r = self._run(home_html(extra=OPEN_EXPLAINER + FAQ_USING_THE_PHRASE))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_the_faq_alone_is_not_mistaken_for_the_explainer(self):
        # And the converse: the FAQ's passing phrase must not stand in for a
        # missing explainer either.
        r = self._run(home_html(extra=FAQ_USING_THE_PHRASE))
        self.assertEqual(r.state, di.FAIL)

    def test_a_dead_network_is_unknown_not_pass(self):
        self.assertEqual(pf.ComparisonBasisInvariant().run(_ctx(_dead)).state,
                         di.UNKNOWN)


class RegistryTest(unittest.TestCase):
    """The wiring itself, because a guard nobody runs is not a guard."""

    def test_the_figure_guards_are_in_the_one_registry(self):
        keys = {i.key for i in di.INVARIANTS}
        for inv in pf.FIGURE_INVARIANTS:
            self.assertIn(inv.key, keys,
                          "a figure guard exists but ops_status, the digest and "
                          "the test suite would never see it")

    def test_the_comparison_uses_the_approved_framing(self):
        # Standing rule in both repos: no competing tracker and no survey
        # publisher is ever named, in any file. The approved public wording is
        # "the US national survey" or "an independent national estimate".
        #
        # This test deliberately asserts the PRESENCE of that framing rather than
        # the absence of specific names, because writing the banned names into an
        # assertion would itself put them in the repo — which is the thing the
        # rule forbids. The absence side is enforced by the repo-wide name scan,
        # not by spelling the names out here.
        src = Path(pf.__file__).read_text(encoding="utf-8").lower()
        self.assertIn("national survey", src)
        self.assertIn("national estimate", src)
        # And the module must never fall back to a possessive brand reference.
        self.assertNotIn("competitor", src)

    def test_every_figure_declares_a_unit_a_period_and_a_geography(self):
        for f in pf.HOME_FIGURES:
            self.assertTrue(f.unit and f.period and f.geography, f.key)

    def test_figures_not_covered_are_named_rather_than_omitted(self):
        self.assertTrue(pf.HOME_NOT_RECOMPUTABLE,
                        "an uncovered figure that is not named reads as covered")


if __name__ == "__main__":
    unittest.main()
