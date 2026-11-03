"""The blog digest is "Career Insights from AskTheRecruiter" (owner, 2026-11-03).

One featured read (title, a one or two sentence summary, "Read"), then two
secondary reads; no machine caption like "The 3 newest of 5 posts we
published"; the subject is the featured title; an excerpt that reads like
SEO keyword soup falls back to the post's first real sentence; new
subscribers get the blog weekly by default and existing readers keep theirs.
Driven through the PHP harness; without php these SKIP (UNKNOWN).
"""
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_digest_scope_rules import PHP, SUBSCRIBE, compose  # noqa: E402
import digest_layout  # noqa: E402

TITLE = "Which résumé tool is worth it? Jobscan vs Teal vs Rezi vs Simplify"


def fixture():
    posts = [
        {"title": TITLE, "link": "https://asktherecruiter.com/blog/resume-tools/",
         "excerpt": "What does a resume match score job description check mean?",
         "content": "<h2>Intro</h2><p>Short.</p><p>We ran the same résumé through four "
                    "tools and only two caught the missing skills. Here is why.</p>",
         "date": "2026-11-02 10:00:00"},
        {"title": "How recruiters read a gap year", "link": "https://asktherecruiter.com/blog/gap/",
         "excerpt": "A gap on a résumé is rarely the problem recruiters say it is, if you name it.",
         "content": "<p>x</p>", "date": "2026-11-02 09:00:00"},
        {"title": "Salary bands in 2026", "link": "https://asktherecruiter.com/blog/bands/",
         "excerpt": "Pay transparency laws changed what a posted band tells you about an offer.",
         "content": "<p>x</p>", "date": "2026-11-02 08:00:00"},
        {"title": "A fourth post", "link": "https://asktherecruiter.com/blog/four/",
         "excerpt": "A fourth opening sentence that stands on its own here.",
         "content": "<p>x</p>", "date": "2026-11-02 07:00:00"},
    ]
    return {"compose": "articles", "from": "2026-11-02", "to": "2026-11-03",
            "freq": "daily", "posts": posts}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class CareerInsights(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture())
        cls.text, cls.html = cls.out["text"], cls.out["html"]

    def test_brand(self):
        self.assertTrue(self.text.startswith("Career Insights from AskTheRecruiter\n"))
        self.assertNotIn("AI Layoff Tracker", self.text + self.html)
        self.assertEqual(digest_layout.product_name([("articles",)]),
                         "Career Insights from AskTheRecruiter")

    def test_no_machine_lines(self):
        body = self.text + self.html
        for gone in ("newest of", "posts we published", "From the blog",
                     "What we wrote around the numbers"):
            self.assertNotIn(gone, body)

    def test_one_featured_then_two_secondary(self):
        feat = self.text.split("Also worth reading")[0]
        self.assertIn(TITLE, feat)
        self.assertIn("Read: https://asktherecruiter.com/blog/resume-tools/", feat)
        more = self.text.split("Also worth reading")[1]
        self.assertEqual(len(re.findall(r"^  - ", more, re.M)), 2)
        self.assertNotIn("A fourth post", self.text)
        self.assertIn("Read &rarr;", self.html)

    def test_keyword_soup_falls_back_to_first_real_sentence(self):
        self.assertNotIn("match score job description", self.text)
        self.assertIn("We ran the same résumé through four tools and only two "
                      "caught the missing skills.", self.text)

    def test_subject_is_the_featured_title(self):
        self.assertEqual(self.out["metric"], TITLE)

    def test_house_style(self):
        body = self.text + self.html
        self.assertNotRegex(body, "[–—]")
        for word in ("bl" + "ind", "hon" + "est", "halluc" + "inat"):
            self.assertNotIn(word, body.lower())


def _php_eval(code):
    src = ("<?php function sanitize_key($s){return preg_replace('/[^a-z0-9_\\-]/','',strtolower((string)$s));}\n"
           "$s=file_get_contents($argv[1]);\n"
           "foreach(array('alt_digest_accepted_freq','alt_digest_valid_freq','alt_digest_articles_freq_from_post',"
           "'alt_digest_keep_articles_freq','alt_digest_prefs_from_post') as $n){"
           "if(preg_match('/\\nfunction '.$n.'\\s*\\(.*?\\n\\}/s',$s,$m)) eval($m[0]);}\n" + code)
    return subprocess.run([PHP, "/dev/stdin", SUBSCRIBE], input=src, capture_output=True,
                          text=True, timeout=60).stdout


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class WeeklyByDefaultForNewSubscribers(unittest.TestCase):

    def test_new_signup_gets_weekly_blog_even_when_daily_ticked(self):
        out = _php_eval("$p=alt_digest_prefs_from_post(array('alt_list_articles'=>1,"
                        "'alt_list_layoff'=>1,'alt_freq'=>'daily'));"
                        "echo $p['freq_articles'].','.$p['freq_layoff'];")
        self.assertEqual(out, "weekly,daily")

    def test_existing_confirmed_reader_keeps_their_cadence(self):
        out = _php_eval("$p=alt_digest_keep_articles_freq(array('status'=>'confirmed',"
                        "'consent_articles'=>1,'freq_articles'=>'daily'),"
                        "array('consent_articles'=>1,'freq_articles'=>'weekly'));"
                        "echo $p['freq_articles'];")
        self.assertEqual(out, "daily")


if __name__ == "__main__":
    unittest.main()
