"""The weekly blog digest carries EVERY post of its week (owner, 2026-11-18).

The owner ruled that the weekly digest includes every article published in
the past week and skips the week when there is none. The daily edition keeps
its one featured read plus two (owner, 2026-11-03); the weekly one lists all
of them, past the old fetch ceiling of 12. Driven through the PHP harness;
without php these SKIP (UNKNOWN).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_digest_scope_rules import PHP, compose  # noqa: E402

N = 15


def fixture(freq):
    posts = [{"title": f"Recruiter read number {i}",
              "link": f"https://asktherecruiter.com/blog/read-{i}/",
              "excerpt": f"A plain opening sentence for read number {i} that stands alone.",
              "content": "<p>x</p>",
              "date": f"2026-11-{9 + i % 7:02d} 0{i % 10}:00:00"}
             for i in range(N)]
    return {"compose": "articles", "from": "2026-11-09", "to": "2026-11-15",
            "freq": freq, "posts": posts}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class WeeklyCarriesEveryPost(unittest.TestCase):

    def test_weekly_lists_every_post_of_the_week(self):
        out = compose(fixture("weekly"))
        for i in range(N):
            self.assertIn(f"Recruiter read number {i}\n", out["text"])
        self.assertEqual(out["metric"], f"{N} ways to strengthen your applications")

    def test_daily_keeps_one_featured_and_two_more(self):
        out = compose(fixture("daily"))
        more = out["text"].split("Also worth reading")[1]
        self.assertEqual(len(re.findall(r"^  - ", more, re.M)), 2)

    def test_an_empty_week_composes_nothing(self):
        f = fixture("weekly")
        f["posts"] = []
        self.assertTrue(compose(f).get("null"))


if __name__ == "__main__":
    unittest.main()
