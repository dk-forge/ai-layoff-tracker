"""THE COPY IN THE SIGNUP MOVED AND NOBODY RE-MEASURED THE PHONE FOLD.

FOUR TIMES IN ONE WEEK, and every time by the same route. The signup block in
includes/subscribe.php has to fit one 812px phone screen from its heading to
its Subscribe button. Two rendered tests hold that bar honestly and caught it
every single time:

    tests/test_digest_route_is_findable.py       the tracker, after the jump
    tests/test_signup_reaches_landing_pages.py   a blog post, at its own top

They are not the problem. The problem is WHEN they speak. Both need headless
Chrome, both take a minute, and neither is the test a person runs after
changing a sentence. So the sequence was always: edit copy, push, deploy,
and twenty minutes later CI reports pixel arithmetic about a build that is
already live. On 2026-08-16 an intro rewrite put the field 862.4px down an
812px screen, and the brief for that very file already said to re-measure the
fold if anything the form renders moves. A written instruction that four
people in a row did not follow is a missing test, not a discipline problem.

WHAT THIS TEST IS. The cheapest possible one. No browser, no fixture, no
rendering: it hashes every reader-facing string the signup puts ABOVE the
Subscribe button and compares that hash to railway/signup_fold_stamp.json,
which is written only by an actual Chrome measurement. Change the copy and this
goes red in milliseconds, locally, on the first `python3 -m unittest` anyone
runs, with one command in the failure message.

WHAT IT IS NOT. It is not a pixel bar and must never be turned into one: it
cannot see a rendered page and has no opinion about how tall a sentence is. It
answers exactly one question - "was the fold measured against THIS copy?" - and
the answer is yes or no. The pixel bars stay where they are and stay the
authority. This one only makes it impossible to reach them by surprise.

WHY A HASH RATHER THAN A CHARACTER BUDGET. A budget is a guess at the
relationship between characters and pixels, and it is wrong the moment a word
wraps differently, a label is added, or a font changes. It would also let a
copy edit through as long as it stayed under the number, which is precisely the
edit that broke this: the 2026-08-16 rewrite REPLACED text and was not much
longer than what it replaced. The honest signal is not "the copy is too long",
it is "the copy is not the copy the measurement was taken against".
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

# The one definition of "the copy above the button", imported rather than
# re-implemented: two extractors is two answers the first time they disagree,
# and the stamp would then be recorded against one and checked against the
# other.
from signup_fold import (  # noqa: E402
    REQUIRED_HEADROOM_PX, STAMP, copy_digest, fold_copy)

RECORD = "python3 railway/signup_fold.py --record"


class TheFoldWasMeasuredAgainstTheCopyThatIsThereNow(unittest.TestCase):

    def setUp(self):
        self.assertTrue(
            STAMP.is_file(),
            "railway/signup_fold_stamp.json does not exist, so nothing records "
            "what the signup's copy was when its phone fold was last measured. "
            "Run: %s" % RECORD)
        self.stamp = json.loads(STAMP.read_text(encoding="utf-8"))

    def test_the_copy_hash_matches_the_recorded_measurement(self):
        sha, chars = copy_digest()
        recorded = self.stamp.get("copy_sha256")
        self.assertEqual(
            recorded, sha,
            "THE SIGNUP'S COPY CHANGED AND THE PHONE FOLD WAS NOT RE-MEASURED.\n"
            "\n"
            "  recorded  %s  (%s chars, measured %s)\n"
            "  now       %s  (%d chars)\n"
            "\n"
            "Everything from the heading to the Subscribe button has to fit one "
            "812px screen after the #alt-digest jump, and the copy is the part "
            "of that block whose height is written rather than laid out. This "
            "has broken four times, always this way.\n"
            "\n"
            "Measure it, read the per-element breakdown, then record:\n"
            "    %s\n"
            "\n"
            "It needs Chrome. If you have none, say UNKNOWN and hand it to "
            "someone who does. Do not edit the stamp by hand: a stamp nobody "
            "measured is worse than no stamp, because the next person believes "
            "it."
            % (recorded, self.stamp.get("copy_chars"),
               self.stamp.get("measured_on"), sha, chars, RECORD))

    def test_the_recorded_figures_clear_the_fold_with_room(self):
        """FIT IS NOT ENOUGH, and the file's own history says why: "it fitted,
        by 2.3px", about a build that then broke. A local render is not a CI
        render - measured 2026-08-16, the same fixtures came out 34px (tracker)
        and 49px (blog) shorter on a Mac than on the Linux runner, purely on
        font metrics. So the recorded numbers have to clear the screen by the
        margin, not merely reach it."""
        figures = self.stamp.get("figures") or {}
        self.assertTrue(
            figures,
            "the stamp records no measured figures at all, so it says the copy "
            "was measured without saying what the measurement was. Re-record: "
            "%s" % RECORD)
        bad = []
        for key, fig in sorted(figures.items()):
            headroom = fig["screen_px"] - fig["reach_px"]
            if headroom < REQUIRED_HEADROOM_PX - 0.05:
                bad.append("%s: the block reaches %.1fpx of a %dpx screen, "
                           "%.1fpx of headroom"
                           % (key, fig["reach_px"], fig["screen_px"], headroom))
        self.assertEqual(
            [], bad,
            "a recorded surface clears the phone fold by less than %.0fpx, "
            "which is inside the gap between this machine and the CI runner:\n"
            "  %s" % (REQUIRED_HEADROOM_PX, "\n  ".join(bad)))

    def test_the_stamp_names_every_surface_the_rendered_tests_hold(self):
        """A stamp that covers the surface nobody broke is not a stamp."""
        figures = self.stamp.get("figures") or {}
        for key in ("tracker@375x812", "blog@375x812"):
            self.assertIn(
                key, figures,
                "the stamp does not carry a figure for %r, so it was recorded "
                "by an older or narrower tool than railway/signup_fold.py. "
                "Re-record: %s" % (key, RECORD))


class TheExtractorStillFindsTheCopy(unittest.TestCase):
    """The guard's own failure mode: an extractor that quietly reads nothing
    hashes the empty string forever and never fires again."""

    def test_it_reads_the_real_sentences_out_of_the_form(self):
        text = fold_copy()
        self.assertGreater(
            len(text), 200,
            "the fold-copy extractor returned %d characters, which is not a "
            "form. It is reading the wrong region of subscribe.php and would "
            "hash the same near-empty string through any copy edit: %r"
            % (len(text), text))
        for phrase, what in (
                ("Email digest", "the block's own heading"),
                ("What would you like?", "the consent fieldset's legend"),
                ("How often", "the frequency fieldset's legend"),
                ("Subscribe", "the submit button")):
            self.assertIn(
                phrase, text,
                "the extracted fold copy does not contain %s (%r), so the "
                "region it slices is no longer the block above the button"
                % (what, phrase))

    def test_it_stops_at_the_button_and_excludes_the_privacy_block(self):
        """The tracking disclosure and the privacy note sit BELOW the Subscribe
        button and cost the fold nothing. Hashing them would fire this guard
        for edits that cannot move the fold, and a guard that cries at the
        wrong edit is a guard people learn to re-record without reading."""
        text = fold_copy()
        self.assertNotIn(
            "hard-deleted automatically", text,
            "the fold copy reaches into the privacy note, which is below the "
            "Subscribe button and outside the budget")
        self.assertNotIn(
            "Unsubscribing stops the sending", text,
            "the fold copy reaches into the tracking disclosure, which is "
            "below the Subscribe button and outside the budget")


if __name__ == "__main__":
    unittest.main()
