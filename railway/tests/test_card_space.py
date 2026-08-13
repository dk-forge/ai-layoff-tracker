"""NO CARD RENDERS A BAND OF EMPTY SPACE, AND THE RULE IS MEASURED, NOT LISTED.

WHY THIS TEST EXISTS.

The owner reported the same defect three times about three different cards:
"Largest single job cuts" with a band of white under its last row, then "Repeat
layoffs" and "Browse the record: top places", then a soundbite card on the
press page with roughly half the card blank between the statement and its Copy
button. Each report was true. Each was fixable on its own. Fixing them one at a
time guarantees a fourth report, so what he actually asked for was the rule:
"ensure all get formatted automatically all the time".

A test that names cards is the same defect wearing a lab coat, and it has a
second failure mode: it has to be edited every time a card is added, which is
how a test gets deleted. So this asserts A PROPERTY OF ANY CARD, measured off
rendered geometry in real Chrome: no card contains a vertical gap bigger than
GAP_LIMIT, whether that gap is under its last child or in its middle.

WHAT THE FIXTURE REPRODUCES, and why it is built this way.

The defect only exists in a MULTI-COLUMN grid, because a grid row is as tall as
its tallest card and every shorter card in that row is stretched to match. At
375px the grid is one column, nothing stretches, and the live page measured
clean. So the fixture is a two-column grid with a deliberately tall neighbour,
which is what the production page has: the tall card is the one with the
longest basis note, not the one with the longest list.

Three cards, one per outcome the rule has to get right:

  FILLS      a bar list with more rows than its box: the card's spare height
             must become VISIBLE ROWS. The rows were already in the DOM and
             already paid for, so this costs no query and invents nothing.
  CANNOT     a bar list with four real rows, standing in for "By data source",
             which has four data sources and no fifth to invent. Padding it
             would be a lie, so the card must stop being stretched instead.
  PINNED     a soundbite whose actions are pinned to its bottom. A short quote
             stretched to a long quote's height puts the gap in the MIDDLE of
             the card, which a check that only looked below the last child
             would score as perfect.

The real fitCardHeights() runs here, lifted byte for byte out of layoffs.js by
jsrun.extract, against a real DOM. Re-implementing it in the fixture would test
the re-implementation.

AND THE GUARD IS PROVED TO FAIL. TheGuardCanActuallyFailTests puts the old
declarations back and asserts the bands return. A guard that cannot be made to
fail is not evidence of anything; this suite has already caught five checks
that passed against defective code for the wrong reason (CLAUDE.md).

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass.
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import jsrun  # noqa: E402
from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import card_space_audit  # noqa: E402

CSS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.css"
JS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.js"

# A gap wider than this is a band rather than spacing. Deliberate spacing on
# these cards tops out around 20px; one bar row plus its gap is about 46px.
GAP_LIMIT = card_space_audit.GAP_LIMIT

# One row of a bar list, as renderBarList emits it. Long names are supposed to
# ellipsize inside .alt-barrow-name, so one row here carries a name long enough
# to need it: a change that filled cards by letting names run wide would show
# up as a row that got taller instead of clipping.
LONG_NAME = "A Very Long Employer Name That Must Ellipsize Rather Than Wrap Or Bleed, Incorporated"


def _row(i, total):
    name = LONG_NAME if i == 2 else "Employer %d" % i
    width = max(2, int(100 * (total - i) / total))
    return (
        '<button type="button" class="alt-barrow" data-val="e%d">'
        '<span class="alt-barrow-top">'
        '<span class="alt-barrow-name">%s</span>'
        '<span class="alt-barrow-val">%d</span></span>'
        '<span class="alt-bartrack">'
        '<span class="alt-barfill" style="left:0%%;width:%d%%"></span>'
        '</span></button>' % (i, name, (total - i) * 137, width)
    )


def _barlist(n):
    return "".join(_row(i, n) for i in range(1, n + 1))


# The tall neighbour. In production this height comes from a card with a long
# basis note; the fixture states it outright so the row height is deterministic.
TALL = ('<div class="alt-mini alt-chart-card" id="tall">'
        '<div class="alt-chart-head"><div class="alt-chart-h">Tall neighbour</div></div>'
        '<div style="height:520px"></div></div>')

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<!-- The viewport meta is load-bearing, not boilerplate: under mobile
     emulation a page without one gets a 980px layout viewport, so a 375px
     fixture would quietly render the DESKTOP two-column grid and the phone
     assertion below would be measuring the wrong page. -->
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(css)s</style></head>
<body><div class="alt-wrap alt-tracker-wrap">

<div class="alt-minigrid">
  %(tall)s
  <div class="alt-mini alt-chart-card" id="fills">
    <div class="alt-chart-head"><div class="alt-chart-h">Long list</div></div>
    <div class="alt-barlist" id="list-fills">%(many)s</div>
  </div>
  %(tall2)s
  <div class="alt-mini alt-chart-card" id="cannot">
    <div class="alt-chart-head"><div class="alt-chart-h">Four real sources</div></div>
    <div class="alt-barlist" id="list-cannot">%(few)s</div>
  </div>
</div>

<div class="alt-soundbites">
  <figure class="alt-soundbite" id="sb-long">
    <span class="alt-sb-label">Long statement</span>
    <blockquote class="alt-sb-text">%(quote)s</blockquote>
    <figcaption class="alt-sb-actions">
      <button type="button" class="alt-btn alt-btn-sm">Copy statement</button>
      <a class="alt-sb-link" href="#">See the entries</a>
    </figcaption>
  </figure>
  <figure class="alt-soundbite" id="sb-short">
    <span class="alt-sb-label">Short statement</span>
    <blockquote class="alt-sb-text">One short sentence.</blockquote>
    <figcaption class="alt-sb-actions">
      <button type="button" class="alt-btn alt-btn-sm">Copy statement</button>
      <a class="alt-sb-link" href="#">See the entries</a>
    </figcaption>
  </figure>
</div>

</div>
<script>%(js)s</script>
</body></html>
"""

LONG_QUOTE = (
    "Employers documented in this tracker have disclosed job cuts in filings, "
    "state notices and reported announcements across every quarter of the "
    "period, and each of those entries links back to the document it was read "
    "from, so the figure can be checked line by line rather than taken on "
    "trust, which is the whole reason the record is kept this way at all."
)


def _fixture(css, js):
    return FIXTURE % {
        "css": css,
        "js": js,
        "tall": TALL,
        "tall2": TALL.replace('id="tall"', 'id="tall2"'),
        "many": _barlist(24),
        "few": _barlist(4),
        "quote": LONG_QUOTE,
    }


def _fit_script():
    """The REAL fitCardHeights, lifted out of layoffs.js and made callable.

    jsrun.extract raises if the function is renamed or removed, so this cannot
    quietly degrade into testing nothing.
    """
    src = JS.read_text()
    m = re.search(r"var CARD_BAND_PX = ([0-9.]+);", src)
    if not m:
        raise AssertionError("layoffs.js no longer declares CARD_BAND_PX")
    return "var CARD_BAND_PX = %s;\n%s\n%s" % (
        m.group(1),
        jsrun.extract("laidOutCards", src),
        jsrun.extract("fitCardHeights", src))


def _undo_the_fix(css):
    """layoffs.css as it was before this change, so the defect comes back.

    Three edits, each the inverse of one shipped declaration. Every one of them
    asserts it matched, because a silent no-op here would turn the failure test
    below into a second copy of the passing one.
    """
    out = css

    # 1. The elastic bar list goes back to a flat cap.
    out, n = re.subn(
        r"flex: 1 1 320px; min-height: 0; max-height: max-content;",
        "max-height: 320px;", out)
    assert n == 1, "expected 1 elastic bar-list rule, found %d" % n

    # 2. Cards stop being flex columns, so the list cannot absorb anything.
    out, n = re.subn(
        r"\.alt-chart-card:has\(\.alt-barlist\) \{ display: flex; flex-direction: column; \}",
        "", out)
    assert n == 1, "expected 1 flex-column card rule, found %d" % n

    # 3. Soundbites go back to stretching to their row.
    out, n = re.subn(r"(\.alt-soundbites \{[^}]*?) align-items: start;", r"\1", out)
    assert n == 1, "expected 1 soundbite align-items rule, found %d" % n
    return out


class _Measured(unittest.TestCase):
    """Renders the fixture in headless Chrome and returns the audit's rows."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so card geometry could not "
                "be measured. This is UNKNOWN, not a pass: run "
                "`python3 railway/card_space_audit.py` where a browser exists.")

    def _cards(self, css, js, width=1280):
        html = _fixture(css, js)
        try:
            with Browser(width=width, height=900) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js("(function(){document.open();document.write(%s);"
                             "document.close();return true;})()" % json.dumps(html))
                raw = page.eval_js(
                    card_space_audit.MEASURE_JS % json.dumps(card_space_audit.CARD_SELECTOR))
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        cards = json.loads(raw)["cards"]
        self.assertTrue(cards, "the fixture rendered no cards at all, so this "
                               "measured nothing")
        return cards

    def _shipped(self, width=1280):
        return self._cards(CSS.read_text(), _fit_script() + "\nfitCardHeights();", width)

    def _worst(self, cards):
        return max(cards, key=lambda c: c["gap"])


class NoCardWastesItsOwnHeightTests(_Measured):

    def test_no_card_contains_a_band_of_empty_space(self):
        # The rule, stated once, over every card the fixture renders. A card
        # added to this page later is covered by the same assertion.
        cards = self._shipped()
        bands = [(c["title"], c["gap"], c["where"]) for c in cards if c["gap"] > GAP_LIMIT]
        self.assertEqual(
            [], bands,
            "%d card(s) render more than %.0fpx of empty space inside "
            "themselves: %s. A card either fills the height its grid row gives "
            "it, or stops being stretched to it. Never pad a list with rows "
            "that are not real."
            % (len(bands), GAP_LIMIT, bands))

    def test_the_spare_height_became_visible_rows_and_not_white_space(self):
        # The specific win: the card that CAN fill puts the row's spare height
        # into rows the reader can see. Asserted as measured geometry, not as a
        # row-count constant: what matters is that the list is as tall as the
        # space its card was given.
        cards = self._shipped()
        fills = [c for c in cards if c["title"] == "Long list"]
        self.assertEqual(1, len(fills), "fixture no longer renders the long-list card")
        elastic = fills[0]["elastic"]
        self.assertIsNotNone(elastic, "the long-list card has no bar list")
        self.assertGreater(
            elastic["height"], 320.0,
            "the bar list is still %.0fpx tall in a %.0fpx card. It has %.0fpx "
            "of real rows waiting and the card's spare height went to white "
            "space instead of to rows."
            % (elastic["height"], fills[0]["height"], elastic["content"]))

    def test_a_card_that_cannot_fill_is_not_padded_out(self):
        # The other half, and the one that must NOT be answered with content:
        # four real sources stay four rows. The card gets shorter instead.
        cards = self._shipped()
        cannot = [c for c in cards if c["title"] == "Four real sources"]
        self.assertEqual(1, len(cannot), "fixture no longer renders the short-list card")
        self.assertEqual(
            4, cannot[0]["elastic"]["rows"],
            "the short card gained rows. Filling a card with entries that are "
            "not real is the one fix this must never make.")
        self.assertLessEqual(
            cannot[0]["gap"], GAP_LIMIT,
            "the four-source card still wastes %.0fpx; it should have stopped "
            "stretching to its row." % cannot[0]["gap"])

    def test_a_long_name_still_ellipsizes_rather_than_wrapping(self):
        # The thing not to break. A name cut with no visible marker reads as a
        # complete company name, which is worse than a visible cut, so the row
        # must stay one line high and keep its ellipsis.
        try:
            with Browser(width=1280, height=900) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js("(function(){document.open();document.write(%s);"
                             "document.close();return true;})()"
                             % json.dumps(_fixture(CSS.read_text(),
                                                   _fit_script() + "\nfitCardHeights();")))
                probe = page.eval_js(r"""
                    (function () {
                      var rows = document.querySelectorAll('#list-fills .alt-barrow');
                      var name = rows[1].querySelector('.alt-barrow-name');
                      var cs = getComputedStyle(name);
                      return JSON.stringify({
                        text: name.innerText.trim(),
                        rowHeights: [rows[0].getBoundingClientRect().height,
                                     rows[1].getBoundingClientRect().height],
                        overflow: cs.textOverflow,
                        clipped: name.scrollWidth > name.clientWidth + 1
                      });
                    })()""")
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        got = json.loads(probe)
        self.assertTrue(got["clipped"],
                        "the long name is no longer overflowing its row, so this "
                        "test is not measuring truncation any more")
        self.assertEqual(
            "ellipsis", got["overflow"],
            "a long employer name is being cut with no visible marker, which "
            "reads as a complete company name")
        self.assertAlmostEqual(
            got["rowHeights"][0], got["rowHeights"][1], delta=1.0,
            msg="the long-name row is %.1fpx against %.1fpx for a short one, so "
                "the name wrapped instead of ellipsizing"
                % (got["rowHeights"][1], got["rowHeights"][0]))

    def test_the_fixture_uses_the_container_the_template_actually_ships(self):
        # THE BUG THIS EXISTS FOR. The first cut of the fix, and of this
        # fixture, both said `.alt-chart-grid`. The tracker's cards are in
        # `.alt-minigrid`, so the fixture agreed with the defect and the tests
        # above went green against a page-level no-op that only the live audit
        # caught. A fixture is only evidence while it is the same shape as the
        # page, so that is asserted rather than assumed.
        template = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-tracker.php").read_text()
        self.assertIn(
            'class="alt-minigrid"', template,
            "page-tracker.php no longer puts its chart cards in .alt-minigrid, "
            "so this fixture is measuring a container the reader never gets")

    def test_one_column_is_unaffected(self):
        # At 375px the grid is one column, nothing stretches, and none of this
        # should be doing anything. This is the guard on the phone: it is where
        # a "fill the card" change would silently lengthen the page.
        cards = self._cards(CSS.read_text(),
                            _fit_script() + "\nfitCardHeights();", width=375)
        fills = [c for c in cards if c["title"] == "Long list"][0]
        self.assertLessEqual(
            fills["elastic"]["height"], 321.0,
            "the bar list grew to %.0fpx at 375px, where no card is stretched. "
            "That is extra page height on a phone, bought for nothing."
            % fills["elastic"]["height"])


class TheGuardCanActuallyFailTests(_Measured):
    """With the shipped declarations removed, the bands must come back.

    This is the half that makes the class above mean something.
    """

    def test_putting_the_flat_cap_back_reproduces_the_reported_bands(self):
        cards = self._cards(_undo_the_fix(CSS.read_text()), "")
        bands = [(c["title"], c["gap"]) for c in cards if c["gap"] > GAP_LIMIT]
        titles = set(t for t, _ in bands)
        self.assertIn(
            "Long list", titles,
            "with the flat 320px cap restored, the long-list card did NOT show "
            "a band, so the passing test above is not measuring the defect. "
            "Gaps seen: %s" % [(c["title"], c["gap"]) for c in cards])
        self.assertIn(
            "Short statement", titles,
            "with the soundbite grid stretching again, the short statement did "
            "NOT show a band. Gaps seen: %s"
            % [(c["title"], c["gap"]) for c in cards])


if __name__ == "__main__":
    unittest.main()
