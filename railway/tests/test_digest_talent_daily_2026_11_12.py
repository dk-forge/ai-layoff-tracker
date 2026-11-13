"""Owner review of the talent daily of 2026-11-12 ("fix all emails to 100%").

The delivered edition, subject "Who's hiring: Salute plans 12,000 roles in
United States + 8 more", had five defects this file pins, on rows shaped like
that day's (a cut-down copy of the window, offline):

1. The subject led with a single-source figure. Salute's 12,000 is a
   three-year goal from one Fox Business video page; Salute's own release said
   10,000. A number may lead only when it is filed (tier verified) or
   corroborated by a second publisher. Otherwise the subject names employers
   and carries no figure, and the body labels the plan "one report".
2. "Cloudflare: 12 roles, open listings" was the NET CHANGE on a board of 473.
   A job-board line now says "+12 open roles since our last scan, 473 listed".
3. The glance printed "Hiring signals: 9" and "Employer-activity signals: 104
   from 104 employers" without saying they are the 113. It now says
   "All signals: 113 = 9 about hiring + 104 other employer news".
4. "Universidad para la Paz: 7 roles" and "Real Value Supermarket: roles not
   stated" were featured. Plans under 25 roles, or with none stated, are
   counted and reached by "See all", not featured.
5. The page keeps counting after the send; the email says when it counted.

Driven through the PHP harness. Without php on PATH these SKIP (UNKNOWN).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from test_digest_talent_briefing import PHP, compose  # noqa: E402

FROM, TO = "2026-11-11", "2026-11-12"


def row(i, company, country, headcount=None, *, host="example.com", source="Reporter",
        board=False, headline="", direction="hiring", tier="reported", city=""):
    r = {"signal_id": f"n{i}", "company": company, "company_key": company.lower(),
         "country": country, "hq_country": "", "signal_direction": direction,
         "headcount": None if headcount is None else str(headcount),
         "industry": "technology", "city": city, "state": "",
         "source_name": source, "source_url": f"https://{host}/{i}",
         "materiality": "high", "confidence": "reported", "tier": tier,
         "headline": headline or f"{company} news"}
    if board:
        r["collector"] = "ats_boards"
        r["tier"] = "measured"
    return r


def fixture(extra=()):
    rows = [
        row(1, "Salute", "US", 12000, host="www.foxbusiness.com", source="Fox Business"),
        row(2, "Airwallex", "SG", 1000, host="technode.global", source="TNGlobal", city="Singapore"),
        row(3, "Mediaset", "IT", 430, host="www.repubblica.it", source="la Repubblica"),
        row(4, "Eswatini Air", "SZ", 80, host="www.eswatiniobserver.com", source="Eswatini Observer"),
        row(5, "Universidad para la Paz", "CR", 7, host="www.elfinancierocr.com", source="El Financiero CR"),
        row(6, "Real Value Supermarket", "NG", None, source="Punch"),
        row(7, "Cloudflare", "", 12, board=True, source="Greenhouse job board",
            host="job-boards.greenhouse.io",
            headline="Cloudflare's job board listed 12 more active postings than our previous scan (job board: 461 to 473)"),
        row(8, "Ramp", "US", 11, board=True, source="Ashby job board", host="jobs.ashbyhq.com", city="New York",
            headline="Ramp's job board listed 11 more active postings in New York than our previous scan (job board: 165 to 176)"),
        row(9, "Neurophos", "US", 7, board=True, source="Ashby job board", host="jobs.ashbyhq.com", city="Austin",
            headline="Neurophos's job board listed 7 more active postings in Austin than our previous scan (job board: 19 to 26)"),
        row(10, "Acme Capital", "GB", direction="neutral"),
        row(11, "Beta Labs", "DE", direction="neutral"),
        row(12, "Gamma Co", "", direction="neutral"),
    ] + list(extra)
    hiring = sum(1 for r in rows if r["signal_direction"] == "hiring")
    by_country = {}
    for r in rows:
        if r["country"]:
            by_country[r["country"]] = by_country.get(r["country"], 0) + 1
    agg = {"total": len(rows), "companies": len(rows), "stated_headcount": sum(1 for r in rows if r["headcount"]),
           "by_direction": [{"k": "hiring", "n": str(hiring)}, {"k": "neutral", "n": str(len(rows) - hiring)}],
           "by_country": [{"k": k, "n": str(v)} for k, v in by_country.items()]}
    return {"from": FROM, "to": TO, "freq": "daily", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": len(rows), "rows": rows},
            "talent_ytd": agg, "talent_geo": agg}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class SingleSourceNeverLeadsTheSubject(unittest.TestCase):

    def test_an_uncorroborated_figure_stays_out_of_the_subject(self):
        out = compose(fixture())
        self.assertNotIn("12,000", out["metric"])
        self.assertNotIn("plans", out["metric"])
        self.assertEqual(out["metric"], "Who's hiring: Salute, Airwallex, Mediaset + 6 more")

    def test_the_body_labels_the_single_source(self):
        text = compose(fixture())["text"]
        self.assertIn("Biggest announced plan: Salute, 12,000 roles in United States (one report: Fox Business)", text)
        self.assertIn("led by Salute (plans 12,000 roles in United States, one report)", text)

    def test_a_second_publisher_lets_the_number_lead(self):
        second = row(20, "Salute", "US", 12000, host="www.datacenterknowledge.com", source="DCK")
        out = compose(fixture([second]))
        self.assertTrue(out["metric"].startswith("Who's hiring: Salute plans 12,000 roles in United States"),
                        out["metric"])
        self.assertNotIn("one report", out["text"].split("Announced hiring plans\n", 1)[0])

    def test_a_filed_figure_leads_on_its_own(self):
        fx = fixture()
        fx["talent_q"]["rows"][0]["tier"] = "verified"
        self.assertTrue(compose(fx)["metric"].startswith("Who's hiring: Salute plans 12,000"))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class BoardChangeIsNotBoardSize(unittest.TestCase):

    def test_a_board_line_shows_the_change_and_the_board(self):
        text = compose(fixture())["text"]
        self.assertIn("Cloudflare: +12 open roles since our last scan, 473 listed", text)
        self.assertIn("Ramp: +11 open roles since our last scan, 176 listed", text)
        self.assertNotIn("12 roles, open listings", text)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class GlanceAddsUp(unittest.TestCase):

    def test_the_counts_are_named_and_sum(self):
        head = compose(fixture())["text"].split("Announced hiring plans\n", 1)[0]
        self.assertIn("All signals: 12 = 9 about hiring + 3 other employer news", head)
        self.assertIn("Hiring: 9 (6 announced plans, 3 job-board changes)", head)
        self.assertIn("Other employer news: 3 (funding, leadership, sites and pay, from 3 employers; not hiring counts)", head)
        m = re.search(r"All signals: (\d+) = (\d+) about hiring \+ (\d+)", head)
        self.assertEqual(int(m.group(1)), int(m.group(2)) + int(m.group(3)))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class FeatureBar(unittest.TestCase):

    def test_small_and_unstated_plans_are_not_featured(self):
        text = compose(fixture())["text"]
        plans = text.split("Announced hiring plans\n", 1)[1].split("Job-board changes\n", 1)[0]
        self.assertNotIn("Universidad para la Paz", plans)
        self.assertNotIn("Real Value Supermarket", plans)
        self.assertIn("Eswatini Air: 80 roles", plans)
        self.assertIn("plans under 25 roles are in the full list", plans)
        self.assertIn("7 featured, see all 9 hiring signals", text)

    def test_counts_say_when_they_were_taken(self):
        self.assertRegex(compose(fixture())["text"],
                         r"Counts as of \d\d:\d\d UTC; the page adds signals that arrive later\.")

    def test_a_tied_region_is_named_the_same_way_twice(self):
        text = compose(fixture())["text"]
        self.assertIn("Leading regions: North America and Europe, 3 signals each", text)
        self.assertIn("By region, North America and Europe led with 3 signals each", text)

    def test_house_style(self):
        out = compose(fixture())
        self.assertNotRegex(out["text"] + out["html"] + out["metric"], "[–—]")


if __name__ == "__main__":
    unittest.main()
