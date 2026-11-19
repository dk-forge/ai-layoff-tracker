"""todo#2731: the phone sign-up bar on blog posts and the blog home.

The 2026-11-19 audit at 390px found no visible UTM-tagged sign-up link on the
blog home or on 20 sampled posts (the header button is hidden on phones). The
bar now renders there too, tagged utm_source=blog&utm_medium=cta, the post slug
in utm_content, and still renders nothing on pages or other templates.
"""
import shutil
import unittest

from test_atr_signup_cta import _hrefs, _run_php

WP = ("$GLOBALS['t_single'] = %s; $GLOBALS['t_home'] = %s;\n"
      "function is_singular($t = '') { return $GLOBALS['t_single']; }\n"
      "function is_home() { return $GLOBALS['t_home']; }\n"
      "function get_post_field($f) { return 'Salary-Negotiation_tips<x>'; }\n")


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class BlogBar(unittest.TestCase):

    def test_post_gets_bar_tagged_blog_with_slug(self):
        html = _run_php(WP % ("true", "false") + "alt_atr_cta_sticky_bar();")
        hrefs = _hrefs(html)
        self.assertEqual(len(hrefs), 1)
        self.assertIn("/resume-score?", hrefs[0])
        for part in ("utm_source=blog", "utm_medium=cta", "utm_campaign=sticky_bar",
                     "utm_content=salary-negotiation_tipsx"):
            self.assertIn(part, hrefs[0])
        self.assertIn('id="alt-atr-bar"', html)

    def test_blog_home_gets_bar_without_slug(self):
        hrefs = _hrefs(_run_php(WP % ("false", "true") + "alt_atr_cta_sticky_bar();"))
        self.assertEqual(len(hrefs), 1)
        self.assertIn("utm_source=blog", hrefs[0])
        self.assertNotIn("utm_content", hrefs[0])

    def test_other_pages_get_nothing(self):
        self.assertEqual(_run_php(WP % ("false", "false") + "alt_atr_cta_sticky_bar();").strip(), "")

    def test_tracker_pages_keep_tracker_source(self):
        html = _run_php(WP % ("true", "false")
                        + "$GLOBALS['alt_test_tracker'] = true; alt_atr_cta_sticky_bar();")
        self.assertIn("utm_source=ai-layoff-tracker", _hrefs(html)[0])
