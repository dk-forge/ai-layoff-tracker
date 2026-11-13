"""Email audit of 2026-11-13 (owner: "fix all emails to 100%"), layoff side.

1. The preheader said "across 7 companies" while the opening said 6 employers:
   it read totals.companies, which also holds announced plans. It now counts
   the verified employers the opening counts.
2. The trend line said "the 8-week average" while averaging 7 weeks (the
   current week is provisional and left out). It now names the span it used.
3. The monthly edition said "45% of the week". The findings now use the
   edition's own period.
4. The welcome email's plain-text part had no unsubscribe link, only a promise
   of one "at the foot" of later editions.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_briefing import PHP, base_fixture, compose  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PREFS = os.path.join(HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker",
                     "includes", "subscriber-prefs.php")


def render(kind):
    fx = base_fixture()
    fx["freq"] = kind
    return compose(fx)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class Wording(unittest.TestCase):

    def test_preheader_counts_the_employers_the_opening_counts(self):
        out = render("weekly")
        self.assertIn("across 6 employers", out["preheader"])
        self.assertNotIn("7 companies", out["preheader"])

    def test_the_average_names_the_weeks_it_covers(self):
        text = render("weekly")["text"]
        self.assertNotIn("8-week average", text)
        self.assertIn("below the average of the previous 7 weeks of 16,875", text)

    def test_a_monthly_finding_says_month(self):
        text = render("monthly")["text"]
        self.assertNotIn("of the week", text)
        self.assertIn("45% of the month", text)
        self.assertIn("45% of the week", render("weekly")["text"])

    def test_house_style(self):
        out = render("monthly")
        self.assertNotRegex(out["text"] + out["html"] + out["preheader"], "[–—]")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class WelcomePlainText(unittest.TestCase):

    def test_the_text_part_carries_the_unsubscribe_link(self):
        run = subprocess.run([PHP, os.path.join(HERE, "fixtures", "welcome_body_probe.php"), PREFS],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr[:800])
        self.assertIn("Unsubscribe now: https://x/unsub/abc", run.stdout)


if __name__ == "__main__":
    unittest.main()
