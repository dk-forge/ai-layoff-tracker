"""A single uncorroborated news report never leads an edition (audit 2026-11-12).

The 2026-W45 weekly opened "led by Microsoft", put "Microsoft alone is 45% of
the week" in its findings and AI-attributed 61,700 in the subject, all on ONE
Business Insider report of a buyout OFFER. Its Biggest cuts list also carried
Bosch 30,000 (a running total), Wells Fargo 10,000 and Nokia 4,000, each one
bronze news report, all trashed the next day. The rows still count in the
total (the referee, not the email, decides whether a row is real), but the
lead, the subject and the concentration finding go to the largest
CORROBORATED row: a filing (WARN, SEC, ERM), a silver/gold row, or a news row
with a second report. A single report is labelled as one in the list, and the
summary says plainly what each count measures.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_digest_briefing import PHP, base_fixture, compose, row  # noqa: E402


def with_single_report(fx, jobs=60000, extra=None):
    fx = copy.deepcopy(fx)
    r = row(99, "Microsoft", jobs, country="", state="", source_type="news",
            source_name="Business Insider")
    r["verification_level"] = "bronze"
    r["additional_sources"] = []
    if extra:
        r.update(extra)
    fx["layoff_rows"].append(r)
    fx["layoff"]["totals"]["jobs"] += jobs
    return fx


@unittest.skipIf(PHP is None, "php is not on PATH.")
class SingleReportDoesNotLead(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(with_single_report(base_fixture()))
        cls.text = cls.out["text"]
        cls.html = cls.out["html"]

    def test_opening_is_led_by_the_largest_corroborated_row(self):
        lead = self.text.splitlines()[2]
        self.assertNotIn("led by Microsoft", lead)
        self.assertIn("led by Crothall Healthcare", lead)

    def test_subject_does_not_name_the_single_report(self):
        self.assertNotIn("Microsoft", self.out.get("metric", "") or "")

    def test_concentration_finding_says_it_rests_on_one_report(self):
        self.assertNotIn("Microsoft alone is", self.text)
        self.assertIn("rests on a single news report", self.text)

    def test_the_row_is_still_listed_and_labelled_as_one_report(self):
        self.assertIn("Microsoft", self.html)
        self.assertIn("Single report, not yet corroborated", self.html)
        self.assertIn("Microsoft (Business Insider; single report): 60,000 jobs", self.text)

    def test_summary_says_what_each_count_measures(self):
        self.assertIn("What these count:", self.text)
        self.assertIn("named AI as a reason", self.text)
        # 60,000 Microsoft + the base fixture's 40-job Acme UK report.
        self.assertIn("60,040 rest on a single news report", self.text)

    def test_totals_still_reconcile(self):
        self.assertEqual(self.out["held"], [])


@unittest.skipIf(PHP is None, "php is not on PATH.")
class CorroboratedNewsCanLead(unittest.TestCase):

    def test_a_news_row_with_a_second_report_leads(self):
        out = compose(with_single_report(base_fixture(), extra={
            "additional_sources": [{"url": "https://example.test/b"}]}))
        self.assertIn("led by Microsoft", out["text"].splitlines()[2])
        self.assertIn("Microsoft (Business Insider): 60,000 jobs", out["text"])


if __name__ == "__main__":
    unittest.main()
