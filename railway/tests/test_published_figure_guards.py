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

SEALED_EXPLAINER = ('<details class="alt-why-lower"><summary>Why our number is '
                    'lower</summary><p>documented floor</p></details>')
OPEN_EXPLAINER = ('<details class="alt-why-lower" open><summary>Why our number is '
                  'lower</summary><p>documented floor</p></details>')


def home_html(hero="484,468", label="verified job cuts, 2026 YTD", extra=""):
    return HOME_HTML.format(hero=hero, label=label, extra=extra or OPEN_EXPLAINER)


def press_html(total="484,468"):
    return (f"<p>The AI Layoff Tracker verified {total} job cuts worldwide in "
            f"2026 so far.</p>")


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

    def _run(self, reasons, html):
        fetch = _router({
            "ai-layoff-tracker/": html,
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=reasons,
                              series=[{"verified_jobs": VERIFIED}],
                              countries=self.COUNTRIES, states=self.STATES),
        })
        return pf.FigureReconciliationInvariant().run(_ctx(fetch))

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
                              series=[{"verified_jobs": VERIFIED - 40_000}]),
        })
        r = pf.FigureReconciliationInvariant().run(_ctx(fetch))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("cannot reach the published number", r.detail)

    def test_scoped_bars_are_reconciled_against_their_own_denominator(self):
        # The ~104,000 defect: a US-scoped list measured against a WORLDWIDE
        # total. The US bars here sum to 450,000 — under the worldwide 484,468,
        # so a naive check passes — but over the US total of 400,000.
        fetch = _router({
            "ai-layoff-tracker/": home_html(),
            "country=United+States": _agg(_totals(jobs=500_000, announced=100_000)),
            "aggregate": _agg(reasons=FIXED_REASONS,
                              series=[{"verified_jobs": VERIFIED}],
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

    def _run(self, reasons, drill):
        def fetch(url, timeout):
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

    def test_what_it_skipped_is_named_never_silently_dropped(self):
        r = self._run([["closure", 41_079], ["tiny", 12]],
                      {"closure": _totals(jobs=41_079, announced=0)})
        self.assertIn("below floor", r.detail)
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
        fetch = _router({"ai-layoff-tracker/": "<p>no figures here</p>",
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

    def _run(self, hero, press, health=None, quality=None):
        health = health or {"newsapi": {"status": "retired"}}
        quality = quality or {"source_health": {"newsapi": {"status": "retired"}}}
        return pf.CrossSurfaceAgreementInvariant().run(_ctx(_router({
            "press/": press_html(press),
            "ai-layoff-tracker/": home_html(hero=hero),
            "source-health": health,
            "quality-status": quality,
        })))

    def test_fails_when_home_and_press_publish_different_headlines(self):
        # THE LIVE DEFECT: home 484,468 vs press 450,529 for the same claim.
        r = self._run("484,468", "450,529")
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("33,939", r.detail)

    def test_passes_when_both_pages_publish_the_same_number(self):
        self.assertEqual(self._run("484,468", "484,468").state, di.PASS)

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
        # THE LIVE DEFECT: a rendered measurement found these panels at 0 and 4
        # pixels wide because <details> has no `open`.
        r = self._run(home_html(extra=SEALED_EXPLAINER))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("collapsed disclosure", r.detail)

    def test_fails_when_there_is_no_explainer_at_all(self):
        r = self._run('<span id="alt-hero-total">484,468</span>')
        self.assertEqual(r.state, di.FAIL)

    def test_an_open_explainer_still_reports_area_as_unknown_not_pass(self):
        # Honest ceiling: this runner has no browser, so non-zero rendered area
        # is UNVERIFIED. It must surface as UNKNOWN, never quietly as a pass.
        r = self._run(home_html(extra=OPEN_EXPLAINER))
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertIn("NOT VERIFIED HERE", r.detail)

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
