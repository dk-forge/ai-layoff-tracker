"""The owner's review of the Nov 1-12 monthly test send (2026-11-13): "are we 100%?"

It was not. Each class below is one finding, held by a test that reddens if
the fix is reverted:

  1. CLIPPED. The message arrived at 183,793 bytes of HTML and Gmail clips
     past ~102 KB, hiding the footer and the unsubscribe link. The full-size
     monthly (edition_size_fixture, calibrated on that send) must render
     under 95 KB AS RECEIVED, i.e. after the relay's click tracking rewrites
     every link, with the unsubscribe link inside the budget.
  2. "led by KLM" in the opening while Top employers ranked BT first. The
     lead uses the employer ranking, or says it is the largest corroborated.
  3. "Verified only" over a list of single-report rows; the single-report
     share sat in a footnote. The subtitle no longer says "Verified only" and
     the share is in the headline sentence.
  4. "Multiple or other countries 13,148" vs "Multiple countries 11,748". The
     1,400 was Russia, unknown to the region table. One label, one figure.
  5. "28% of this week's verified cuts" in a monthly.

Without php on PATH these SKIP, which is UNKNOWN and not a pass.
"""
import copy
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import edition_size_fixture as size  # noqa: E402
from edition_size_fixture import PHP  # noqa: E402


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class MonthlyFitsUnderTheClip(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.msg, cls.lay, cls.tal = size.build()

    def test_received_size_is_under_the_ceiling(self):
        got = size.received_size(self.msg.html)
        self.assertLess(got, size.CEILING_BYTES,
                        "monthly edition is %d bytes as received (ceiling %d, Gmail clips at %d)"
                        % (got, size.CEILING_BYTES, size.CLIP_BYTES))

    def test_unsubscribe_link_is_present_and_inside_the_budget(self):
        html = self.msg.html
        self.assertIn("alt_digest_unsub", html)
        self.assertIn("Unsubscribe", html)
        cut = html.find("alt_digest_unsub")
        self.assertLess(size.received_size(html[:cut]), size.CLIP_BYTES)
        self.assertIn("List-Unsubscribe", self.msg.headers)

    def test_the_fixture_is_full_size(self):
        # A fixture that shrank would make the ceiling meaningless: it must
        # still carry the shape that clipped (dozens of rows and both sections).
        self.assertGreaterEqual(len(re.findall(r'href="https?://', self.msg.html)), 30)
        self.assertIn("Biggest cuts this month", self.msg.html)
        self.assertIn("Who&#39;s hiring", self.msg.html.replace("Who's", "Who&#39;s"))

    def test_monthly_who_is_hiring_is_a_teaser_with_one_link(self):
        html = self.tal["html"]
        self.assertEqual(html.count("<li>"), 5)
        self.assertEqual(len(re.findall(r"href=", html)), 1)
        self.assertIn("See all 40 hiring signals", html)
        self.assertIn("direction=hiring", html)

    def test_no_inherited_font_restated_inside_a_cell(self):
        # Only cells and body restate the stack (classic Outlook); a p, span or
        # a inside a cell inherits it.
        fonts = re.findall(r'<(\w+)[^>]*style="[^"]*font-family:', self.msg.html)
        self.assertTrue(fonts)
        self.assertEqual(set(fonts) - {"td", "body", "th"}, set(), set(fonts))

    def test_bar_cells_carry_no_type(self):
        for cell in re.findall(r'<td[^>]*style="([^"]*font-size:0[^"]*)"', self.msg.html):
            self.assertNotIn("font-family", cell)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class LeadAgreesWithTopEmployers(unittest.TestCase):

    def test_single_report_top_employer_is_not_led_by_someone_else(self):
        out = size.compose(size.layoff_fixture())
        opening = out["text"].splitlines()[2]
        # Telecom Group (8,000) is a single report and first in Top employers;
        # the opening may not say "led by" anyone else.
        self.assertNotIn("led by Flag Carrier", opening)
        self.assertIn("the largest corroborated: Flag Carrier Airline in Netherlands (5,000 jobs)", opening)
        self.assertIn("Telecom Group had the most verified cuts this month, on a single report not yet corroborated.",
                      out["text"])

    def test_corroborated_top_employer_still_leads(self):
        fx = size.layoff_fixture()
        for r in fx["layoff_rows"]:
            if r["company_name"] in ("Telecom Group", "Bank Holding"):
                r["verification_level"] = "silver"
        out = size.compose(fx)
        self.assertIn("led by Telecom Group in United Kingdom", out["text"].splitlines()[2])
        self.assertIn("Telecom Group had the most verified cuts this month.", out["text"])


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class CopyMatchesTheData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = size.compose(size.layoff_fixture())
        cls.text = cls.out["text"]

    def test_list_is_not_labelled_verified_only(self):
        self.assertNotIn("Verified only, largest first", self.text)
        self.assertIn("A single news report not yet corroborated is labelled as one.", self.text)

    def test_single_report_share_is_in_the_headline_sentence(self):
        glance = self.text.split("This month at a glance\n")[1].splitlines()[0]
        self.assertRegex(glance, r"[\d,]+ rest on a single news report not yet corroborated \(\d+%\)\.")

    def test_period_is_the_month_not_this_week(self):
        self.assertNotIn("this week's", self.text)
        self.assertIn("of the verified cuts in the month were in", self.text)

    def test_multiple_countries_has_one_figure(self):
        fx = size.layoff_fixture()
        fx["layoff_rows"].append(size._row(99, "Moscow Plant", 1400, "Russia", single=True))
        fx["layoff"]["map_countries"].append(size.tup("Russia", 1400))
        fx["layoff"]["totals"]["jobs"] += 1400
        text = size.compose(fx)["text"]
        region = re.search(r"^\s+Multiple countries: ([\d,]+)$", text, re.M)
        top = re.search(r"Top countries: .*?Multiple countries ([\d,]+)", text)
        self.assertIsNotNone(region, text)
        self.assertNotIn("Multiple or other countries", text)
        if top:
            self.assertEqual(region.group(1), top.group(1))
        # Russia is placed in Europe, not folded into "Multiple countries".
        self.assertRegex(text, r"Europe \(.*\): [\d,]+")


if __name__ == "__main__":
    unittest.main()
