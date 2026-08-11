"""The one comparison a reader arrives holding, answered on the page.

WHY THIS FILE EXISTS. Someone reading a single month here and the same month in
the US national survey sees two different totals and assumes one of us is wrong.
The page already ships the control that settles it, the "Count Layoffs By"
toggle, and paragraph 4 of "Why our numbers differ from other trackers" is where
it is explained. Before this change that paragraph described OUR dating at
length and never once said what the survey is dating. That is half a
reconciliation, and the missing half is the one the reader came for.

WRITTEN AGAINST THE DEFAULT AS IT STANDS. The default basis moved to the FILING
date in 2.20.7, which is the same question the survey answers, so the two can be
set side by side for one month and read straight against each other. The
effective-date view is the other toggle option. This file pins the copy in that
direction on purpose: an earlier draft of it asserted the opposite arrangement,
which was true of the tree the brief was written against and false of main. A
guard that encodes a stale default would fail a correct page.

WHAT IS PINNED, AND WHY EACH PIECE. Five things have to survive an edit:

  * that the paragraph says what the SURVEY counts, not only what we count;
  * that it says the default is the basis that lines up with it, so a reader
    knows the figure in front of them is already comparable;
  * that it names BOTH toggle options in the exact words printed on the
    buttons. "You can recount on either basis" tells a reader a control exists
    somewhere; naming it tells them where;
  * that the sourcing claim rides along, because the reader's real question is
    which figure to trust, not only why the two differ;
  * that the paragraph lives INSIDE the existing explainer, keeps the
    #alt-basis-explainer anchor the hero links to, and that the explainer is
    still a single, still-open disclosure. This page has shipped a caveat that
    computed to 0x0 and was read by nobody, and a second explainer would be
    worse than none: two answers to one question, drifting apart.

THE STANDING RULE THIS FILE OBEYS. The survey's publisher is never named, in any
file, comment, fixture, branch or log line. The approved public framing is "the
US national survey" or "an independent national estimate". So this file asserts
the PRESENCE of the approved framing and never spells a banned name, because
writing one into an assertion would itself put it in the repo, which is the
thing the rule forbids.

COMMENTS ARE STRIPPED BEFORE ANY MATCH. The template carries a long rationale
comment above this paragraph that quotes the copy, so a checker reading raw
bytes would pass on the commentary alone. Everything below reads the output of
railway/style_check.py's stripper.

PROVEN TO FAIL ON THE PRE-FIX TREE. Run against origin/main@e10cc74, 10 of the
13 tests here failed. The three that did not are named rather than left to look
like proof they are not:

    test_there_is_exactly_one_differences_explainer
    test_the_explainer_is_open_by_default
    test_it_keeps_the_anchor_the_hero_links_to

Each describes a property the old tree already had and this change had to
preserve rather than create: the explainer already existed, was already open,
and already carried the anchor the hero links to. They are regression bars, not
evidence.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
TPL_PATH = PLUGIN / "templates/page-tracker.php"

sys.path.insert(0, str(ROOT / "railway"))
import style_check as sc                                        # noqa: E402

TPL = sc.strip_comments(TPL_PATH.read_text(encoding="utf-8"), "php")

SUMMARY = "Why our numbers differ from other trackers"
# The two words printed on the toggle, verbatim. If either button is relabelled
# the explainer stops pointing at anything and this fails.
TOGGLE_GROUP = "Count Layoffs By"
TOGGLE_FILED = "When it was filed"
TOGGLE_EFFECT = "When it takes effect"


def explainer_body():
    """The panel body of the differences explainer, comments already stripped."""
    i = TPL.find(SUMMARY)
    assert i != -1, "the differences explainer is gone from page-tracker.php"
    start = TPL.rindex("<details", 0, i)
    depth, k, out = 0, start, None
    while k < len(TPL):
        if TPL.startswith("<details", k):
            depth += 1
        elif TPL.startswith("</details>", k):
            depth -= 1
            if depth == 0:
                out = TPL[start:k]
                break
        k += 1
    assert out is not None, "unbalanced <details> around the explainer"
    return out


def text_of(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class ExplainerLocationTests(unittest.TestCase):
    def test_there_is_exactly_one_differences_explainer(self):
        # A second one is two answers to one question, drifting apart.
        self.assertEqual(TPL.count(SUMMARY), 1)

    def test_the_explainer_is_open_by_default(self):
        body = explainer_body()
        self.assertIn("open", body[:body.index(">") + 1],
                      "an explanation sealed in a collapsed panel is not an explanation")

    def test_the_reconciliation_sits_inside_that_explainer(self):
        self.assertIn("national survey", text_of(explainer_body()),
                      "the comparison a reader actually makes is not in the explainer")

    def test_it_keeps_the_anchor_the_hero_links_to(self):
        # The hero's "Why two figures" link lands on this paragraph. Losing the
        # id turns that route into a scroll to the top of the page.
        self.assertIn('id="alt-basis-explainer"', explainer_body())
        self.assertIn('href="#alt-basis-explainer"', TPL)


class ReconciliationCopyTests(unittest.TestCase):
    def setUp(self):
        # The paragraph itself, so "both sides in one paragraph" is a real claim
        # and not two sentences a page apart.
        paras = re.findall(r"<p\b.*?</p>", explainer_body(), flags=re.S)
        hits = [text_of(p) for p in paras if "US national survey" in text_of(p)]
        self.assertEqual(len(hits), 1,
                         "the reconciliation should be one paragraph, found %d" % len(hits))
        self.para = hits[0]

    def test_it_states_what_the_survey_is_counting(self):
        # The half that was missing. The old paragraph described our own dating
        # at length and never said what the other side was dating.
        self.assertIn("The US national survey counts announcements made during a month.",
                      self.para)

    def test_it_states_that_our_default_answers_the_same_question(self):
        # Without this the reader does not know the figure in front of them is
        # already on a comparable basis and goes hunting for a conversion.
        self.assertRegex(
            self.para,
            r"day its notice was filed or the cut was announced, which is the same question",
            "the paragraph never says the default lines up with the survey")

    def test_it_names_both_toggle_options_in_the_words_on_the_buttons(self):
        for token in (TOGGLE_GROUP, TOGGLE_FILED, TOGGLE_EFFECT):
            self.assertIn(token, self.para,
                          "the answer is a control on this page; name it exactly")
        # And each control it names has to exist, with that label, in this file.
        for token in (TOGGLE_GROUP, TOGGLE_FILED, TOGGLE_EFFECT):
            self.assertGreaterEqual(TPL.count(token), 2)

    def test_it_gives_the_worked_example_that_makes_the_gap_concrete(self):
        self.assertRegex(
            self.para,
            r"filed in May for a July closing sits in May on the default and in July on the other",
            "the reader is told the bases differ but not how a single notice moves")

    def test_it_says_neither_basis_is_the_true_one(self):
        # Without this the paragraph reads as a defence of our own choice, which
        # is the impression it exists to remove.
        self.assertIn("Neither basis is the true one.", self.para)

    def test_it_carries_the_sourcing_claim_the_reader_is_really_asking_about(self):
        self.assertRegex(self.para, r"filing or a named report")

    def test_it_states_no_multiple_and_invents_no_figure(self):
        # The size of the monthly gap moves with the data. A number written into
        # prose here would be a published figure with nothing recomputing it.
        self.assertNotRegex(self.para, r"\b(double|twice|half|\d[\d,.]*\s*(percent|%|x))\b")


class NamingRuleTests(unittest.TestCase):
    def test_the_approved_framing_is_what_the_page_uses(self):
        self.assertIn("US national survey", text_of(explainer_body()))

    def test_the_paragraph_attributes_the_other_basis_to_the_survey_not_to_a_brand(self):
        hits = [text_of(p) for p in re.findall(r"<p\b.*?</p>", explainer_body(), flags=re.S)
                if "national survey" in text_of(p)]
        self.assertTrue(hits, "no paragraph in the explainer names the other basis at all")
        para = hits[0]
        # A possessive brand reference is the usual way the rule gets broken.
        self.assertNotIn("competitor", para.lower())
        self.assertNotIn("'s tracker", para.lower())


if __name__ == "__main__":
    unittest.main()
