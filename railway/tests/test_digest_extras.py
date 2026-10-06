"""Subscriber email redesign, slice 1 (owner approval 2026-09-29).

Drives includes/digest-extras.php under the php CLI (no WordPress), then
checks the wiring in subscribe.php / db.php and the relay footer. Without php
on PATH the behaviour cases SKIP, which is UNKNOWN, not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_design                       # noqa: E402
import digest_layout as layout             # noqa: E402

PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
EXTRAS = os.path.join(PLUGIN, "includes", "digest-extras.php")
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
DB = os.path.join(PLUGIN, "includes", "db.php")
MAIN = os.path.join(PLUGIN, "ai-layoff-tracker.php")
PHP = shutil.which("php")


def php(expr: str):
    code = ("require $argv[1];\n"
            "function _sr($l) { return !empty($l['one']); }\n"
            f"echo json_encode({expr});")
    run = subprocess.run([PHP, "-r", code, EXTRAS], capture_output=True,
                         text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1200] or run.stdout[:1200])
    return json.loads(run.stdout)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


LEADERS = ("array("
           "array('company_name'=>'Paramount Skydance','job_count'=>2500,'announced'=>true),"
           "array('company_name'=>'Rumour Co','job_count'=>2200,'announced'=>false,'one'=>1),"
           "array('company_name'=>'Intel','job_count'=>2000,'announced'=>false),"
           "array('company_name'=>'Acme','job_count'=>300,'announced'=>false))")


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class TopStoryAndSubject(unittest.TestCase):
    def test_story_is_the_largest_verified_row(self):
        self.assertEqual(php(f"alt_digest_top_story({LEADERS}, '_sr')"),
                         {"company": "Intel", "jobs": 2000})

    def test_unknown_tier_gives_no_story(self):
        self.assertIsNone(php("alt_digest_top_story(array(array("
                              "'company_name'=>'X','job_count'=>5)))"))

    def test_metric_carries_the_story(self):
        self.assertEqual(
            php("alt_digest_story_metric('13,658 verified job cuts', "
                "array('company'=>'Intel','jobs'=>2000))"),
            "13,658 verified job cuts, led by Intel (2,000)")

    def test_no_story_leaves_the_metric_alone(self):
        self.assertEqual(php("alt_digest_story_metric('5 verified job cuts', null)"),
                         "5 verified job cuts")

    def test_story_never_mentions_ai(self):
        out = php("alt_digest_story_metric('9 verified job cuts', "
                  "array('company'=>'Intel','jobs'=>9))")
        self.assertNotRegex(out, r"\bAI\b")

    def test_subject_carries_story_through_both_senders(self):
        metric = "13,658 verified job cuts, led by Intel (2,000)"
        payload = {"from": "2026-08-10", "to": "2026-08-16", "freq": "weekly",
                   "subject": "x"}
        parts = [("layoff", "<p>x</p>", "AI Layoff Tracker\nx\n", "",
                  (metric, False))]
        subject = layout.subject_line(payload, parts)
        self.assertTrue(subject.startswith(metric), subject)


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class ReasonsAndWhy(unittest.TestCase):
    def test_reason_phrase(self):
        self.assertEqual(php("alt_digest_reason_phrase(',restructuring,cost_reduction,')"),
                         "reason: Restructuring, Cost reduction")

    def test_ai_tags_are_left_to_the_ai_column(self):
        self.assertEqual(php("alt_digest_reason_phrase(array('ai_automation','possible_ai'))"), "")

    def test_why_concentrated(self):
        out = php("alt_digest_why_line(array('company'=>'Intel','jobs'=>3000), 10000)")
        self.assertIn("Intel, is 30% of the verified total", out)

    def test_why_spread(self):
        out = php("alt_digest_why_line(array('company'=>'Intel','jobs'=>500), 10000)")
        self.assertIn("spread out", out)
        self.assertIn("5%", out)

    def test_why_silent_when_dominant_fired_or_no_data(self):
        self.assertEqual(php("alt_digest_why_line(array('company'=>'I','jobs'=>9), 10, true)"), "")
        self.assertEqual(php("alt_digest_why_line(null, 10)"), "")
        self.assertEqual(php("alt_digest_why_line(array('company'=>'I','jobs'=>9), 0)"), "")


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class WeekStrip(unittest.TestCase):
    WEEKS = ("array(" + ",".join(
        f"array('label'=>'Aug {d}','jobs'=>{j})"
        for d, j in [(3, 1200), (10, 900), (17, 1500), (24, 1100),
                     (31, 800), (7, 2000), (14, 1300), (21, 1000)]) + ")")

    def test_eight_weeks_render_and_draw(self):
        html, text = php(f"alt_digest_week_strip({self.WEEKS})")
        self.assertIn("Aug 3 1,200", text)
        self.assertIn("Aug 21 1,000", text)
        drawn = digest_design.add_charts(html)
        self.assertEqual(drawn.count('data-alt="chart-label"'), 8)
        # Bars are decoration: hidden from screen readers, figures in text.
        self.assertIn('aria-hidden="true"', drawn)
        self.assertNotIn("<img", drawn)

    def test_a_missing_week_withholds_the_strip(self):
        weeks = self.WEEKS.replace("'jobs'=>800", "'jobs'=>null")
        self.assertEqual(php(f"alt_digest_week_strip({weeks})"), ["", ""])

    def test_fewer_than_eight_withholds(self):
        self.assertEqual(php("alt_digest_week_strip(array(array('label'=>'Aug 3','jobs'=>1)))"),
                         ["", ""])


class Wiring(unittest.TestCase):
    def test_plugin_loads_the_file_guarded(self):
        main = read(MAIN)
        self.assertIn("includes/digest-extras.php", main)

    def test_composer_uses_every_helper_guarded(self):
        sub = read(SUBSCRIBE)
        for fn in ("alt_digest_top_story", "alt_digest_story_metric",
                   "alt_digest_reason_phrase", "alt_digest_why_line",
                   "alt_digest_week_strip"):
            self.assertIn(f"function_exists('{fn}')", sub, fn)

    def test_leaders_query_selects_reason_tags(self):
        db = read(DB)
        m = re.search(r"SELECT id, company, job_count, layoff_date, ai_explicit[^;]*?LIMIT 24", db, re.S)
        self.assertIsNotNone(m)
        self.assertIn("reason_tags", m.group(0))


class ForwardLine(unittest.TestCase):
    def test_footer_invites_a_forward_on_both_parts(self):
        sentences = layout.footer_sentences(True)
        fwd = [s for s in sentences if "Forward" in s]
        self.assertEqual(len(fwd), 1)
        html = layout._footer("https://x.example/u", "https://x.example/m")
        self.assertIn(layout.SIGNUP_URL, html)
        text = layout.render_text([], kicker="", unsub_url="https://x.example/u",
                                  manage_url="https://x.example/m")
        self.assertIn(layout.SIGNUP_URL, text)

    def test_php_fallback_says_the_same(self):
        self.assertIn("Forward this email", read(SUBSCRIBE))


if __name__ == "__main__":
    unittest.main()
