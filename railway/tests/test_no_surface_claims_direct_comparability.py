"""OUR FIGURE IS ON THE SAME BASIS AS THE NATIONAL SURVEY. IT IS NOT THE SAME NUMBER.

Three surfaces told a reader the filed-basis total "compares directly" with a
national estimate for the same month: the Verified job cuts tile, the "When it
was filed" toggle, and the basis explainer, which said the headline "can be set
beside a national estimate for the same month and read straight against it".

That claim was measured once and then left to age against a figure that moved
underneath it. Measured live on 2026-08-13, US verified, filing basis, against
the published national totals for the same months:

    May 2026    ours 51,755   national 97,006   ours is 47% BELOW
    Jun 2026    ours 36,176   national 45,849   ours is 21% BELOW
    Jul 2026    ours 39,877   national 33,429   ours is 19% ABOVE
    Jan to Jul  ours 317,554  national 477,033  ours is 67% of theirs

The repo's own comments still say July "reads within about one percent" of the
national estimate. That was true when it was written and is not true now: July
kept collecting WARN notices after the sentence was published, which is exactly
the failure mode `benchmark_freshness.py` exists to catch for the private
comparison, and this copy is the same defect on a public surface.

WHAT IS AND IS NOT BEING CLAIMED HERE. The BASIS choice is not in question and
these tests do not touch it. The filing basis asks the same question the survey
asks, so it is the right basis to compare ON, and saying so is honest and worth
saying. What is wrong is the leap from "same basis" to "same measurement". We
count only cuts with a filing or a named report behind them. The survey also
counts federal reductions, buyout ceilings and employer estimates that never
produce a public document, and a measured decomposition of the Jan to Jul gap
puts the majority of it in exactly those receiptless categories rather than in
our coverage. Two totals built from different populations do not "compare
directly" however they are dated.

WHY THIS IS A SEPARATE FILE from test_basis_reconciliation_copy.py. That file
holds the SHAPE of the explainer paragraph: that it names both bases, names the
controls, gives the worked example and invents no figure. It has no opinion on
whether the paragraph's central claim is true. These tests hold the CLAIM, on
every surface that makes it, including the two tooltip strings that live in
both layoffs.js and page-tracker.php and therefore drift.

NO FIGURE IS WRITTEN INTO THE COPY, deliberately, and
test_it_states_no_multiple_and_invents_no_figure in the sibling file already
forbids one in the explainer. The numbers above belong in this docstring, where
they date themselves and nothing publishes them.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS = (PLUGIN / "assets/layoffs.js").read_text()
TPL = (PLUGIN / "templates/page-tracker.php").read_text()


def strip_js_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


def strip_php_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


JS_NC = strip_js_comments(JS)
TPL_NC = strip_php_comments(TPL)

# Every phrasing that asserts the two totals can be read as one measurement.
# Comments are stripped before matching, so a rationale note explaining why the
# claim was REMOVED cannot re-fail this.
DIRECT_COMPARABILITY = (
    "compares directly",
    "compare directly",
    "read straight against it",
    "read straight against each other",
    "directly comparable with a national",
    "the same as the national",
    "matches the national",
)

# The claim that decayed. It is a measured percentage sitting next to a figure
# that kept moving, so it must not be written down anywhere in the plugin,
# comments included: the next editor reads comments.
STALE_PRECISION = (
    "within about one percent",
    "within one percent",
)


def quote(text, phrase, pad=90):
    """The line the phrase sits on, so a failure names the defect not the file.

    assertNotIn would render the entire 6,000-line source into the failure
    message, which buries the one sentence under review.
    """
    i = text.find(phrase)
    if i == -1:
        return ""
    return " ".join(text[max(0, i - pad):i + len(phrase) + pad].split())


class NoSurfaceClaimsTheTotalsAreOneMeasurement(unittest.TestCase):
    def test_the_javascript_basis_copy_does_not_claim_it(self):
        for phrase in DIRECT_COMPARABILITY:
            self.assertTrue(
                phrase not in JS_NC,
                "layoffs.js basis copy still claims direct comparability (%r). "
                "The filing basis makes the two totals worth setting side by "
                "side; it does not make them the same measurement.\n  ...%s..."
                % (phrase, quote(JS_NC, phrase)))

    def test_the_tracker_template_does_not_claim_it(self):
        for phrase in DIRECT_COMPARABILITY:
            self.assertTrue(
                phrase not in TPL_NC,
                "page-tracker.php still claims direct comparability (%r)\n  ...%s..."
                % (phrase, quote(TPL_NC, phrase)))

    def test_no_file_in_the_plugin_carries_the_decayed_percentage(self):
        """Comments INCLUDED. This one is aimed at the next editor, not the reader."""
        for path in sorted(PLUGIN.rglob("*")):
            if path.suffix not in (".php", ".js") or not path.is_file():
                continue
            text = path.read_text(errors="ignore")
            for phrase in STALE_PRECISION:
                self.assertTrue(
                    phrase not in text,
                    "%s still says the figure sits %r of the national estimate. "
                    "It was measured once on a month that was still collecting "
                    "WARN notices; US July 2026 has since moved to 19 percent "
                    "ABOVE the national figure.\n  ...%s..."
                    % (path.relative_to(ROOT), phrase, quote(text, phrase)))


class TheHonestClaimIsStillMade(unittest.TestCase):
    """Removing the overclaim must not remove the reason the basis was chosen.

    Deleting the sentence and saying nothing would leave a reader who arrived
    with a national number in their head with no idea why ours differs, which is
    the confusion the whole basis change was made to end.
    """

    def test_the_explainer_still_says_the_two_are_worth_comparing(self):
        para = self._explainer()
        self.assertRegex(
            para, r"side by side|beside a national estimate",
            "the explainer no longer tells the reader the two totals are on the "
            "same basis and worth setting against each other")

    def test_the_explainer_says_what_we_do_not_count(self):
        """The concrete reason the totals differ, named rather than gestured at."""
        para = self._explainer()
        self.assertRegex(
            para, r"not the same measurement",
            "the explainer must say plainly that the two are not one measurement")
        for token in ("federal", "buyout", "estimate"):
            self.assertIn(
                token, para.lower(),
                "the explainer names no receiptless category (%r); without them "
                "'not the same measurement' is an unexplained hedge" % token)

    def test_the_tile_and_the_toggle_carry_the_same_correction(self):
        for surface, text in (("layoffs.js", JS_NC), ("page-tracker.php", TPL_NC)):
            self.assertIn(
                "not the same measurement", text,
                "%s tooltips still describe the comparison without the caveat; "
                "the tile and the toggle are the two places a reader meets the "
                "claim before they ever reach the explainer" % surface)

    def _explainer(self):
        m = re.search(r'<p id="alt-basis-explainer">(.*?)</p>', TPL_NC, flags=re.S)
        self.assertIsNotNone(m, "the basis explainer paragraph is gone")
        return re.sub(r"<[^>]+>", " ", m.group(1))


class NoDashesInTheReplacedCopy(unittest.TestCase):
    """House rule: no em dashes or en dashes in UI copy."""

    def test_the_basis_surfaces_use_no_em_or_en_dash(self):
        m = re.search(r'<p id="alt-basis-explainer">(.*?)</p>', TPL_NC, flags=re.S)
        self.assertIsNotNone(m)
        targets = [("explainer", m.group(1))]
        block = JS_NC[JS_NC.index("var BASIS_COPY"):]
        targets.append(("BASIS_COPY", block[:block.index("};") + 2]))
        for name, text in targets:
            for dash in ("—", "–", "&mdash;", "&ndash;"):
                self.assertNotIn(dash, text,
                                 "%s copy contains %r" % (name, dash))


if __name__ == "__main__":
    unittest.main()
