"""The talent section shows the signals before it explains the method.

Owner, 2026-10-01, on the delivered daily edition: "this email is not
helpful." The section printed the headline count and then four paragraphs of
counting caveats (what a signal is, the verified split, provisional figures,
the hiring mix) before the first company name. The caveats are true and keep
their exact wording; they now sit under "How to read these numbers" after the
ranked signals and the activity counts.

Driven through the PHP harness like the sibling digest tests. Without php on
PATH these SKIP, which is UNKNOWN and not a pass.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_scope_rules import PHP, compose, talent_fixture  # noqa: E402

UNIT_NOTE = "is one sourced employer update, not one job."


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class SignalsComeBeforeCaveats(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = compose(talent_fixture())["text"]

    def test_caveats_have_their_own_heading(self):
        self.assertIn("How to read these numbers", self.text)

    def test_unit_note_is_printed_once(self):
        self.assertEqual(self.text.count(UNIT_NOTE), 1)

    def test_ranked_signals_come_before_the_caveats(self):
        how = self.text.index("How to read these numbers")
        note = self.text.index(UNIT_NOTE)
        self.assertLess(how, note)
        for heading in ("Biggest hiring signals",
                        "Largest observed job-board increases",
                        "Biggest signals and job-board increases"):
            if heading in self.text:
                self.assertLess(self.text.index(heading), how)
                return
        self.fail("no ranked-signals heading in the fixture edition")


if __name__ == "__main__":
    unittest.main()
