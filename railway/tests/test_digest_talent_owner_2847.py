"""The talent daily has one clear lead and preserves sources when grouping aliases."""
import json
import os
import re
import subprocess
import sys
import unittest
from urllib.parse import parse_qs, urlparse
from html import unescape

sys.path.insert(0, os.path.dirname(__file__))
from test_digest_talent_briefing import PHP, compose
from test_digest_talent_daily_2026_11_12 import row

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "digest-talent-briefing.php")


def fixture(rows=None):
    rows = rows or [row(1, "KLA", "US", 1200, host="one.example"),
                    row(2, "Mistral", "SG", 200, host="two.example", city="Singapore"),
                    row(3, "Mistral AI, Inc.", "SG", 200, host="three.example", city="Singapore"),
                    row(4, "Other", "", direction="neutral")]
    countries = {}
    for item in rows:
        if item["country"]:
            countries[item["country"]] = countries.get(item["country"], 0) + 1
    hiring = sum(item["signal_direction"] == "hiring" for item in rows)
    agg = {"total": len(rows), "companies": len(rows), "stated_headcount": hiring,
           "by_direction": [{"k": "hiring", "n": str(hiring)}],
           "by_country": [{"k": key, "n": str(n)} for key, n in countries.items()]}
    return {"from": "2026-11-21", "to": "2026-11-22", "freq": "daily", "compose": "talent",
            "options": {"alt_digest_talent_briefing_tiers": "daily,weekly,monthly"},
            "talent": agg, "talent_q": {"total": len(rows), "rows": rows},
            "talent_ytd": agg, "talent_geo": agg, "open_roles": {"totals": {"roles": 4242}}}


@unittest.skipIf(PHP is None, "php is not on PATH")
class TalentOwner2847(unittest.TestCase):
    def key(self, company):
        program = "define('ABSPATH', '/'); require " + json.dumps(SOURCE) + "; echo alt_talent_employer_key(json_decode(file_get_contents('php://stdin'), true));"
        result = subprocess.run([PHP, "-r", program], input=json.dumps({"company": company}), text=True, capture_output=True, check=True)
        return result.stdout

    def test_legal_suffixes_and_the_confirmed_mistral_alias(self):
        for name in ("Mistral", "MISTRAL AI", "Mistral AI, Inc.", "Mistral Ltd.", "mistralai"):
            with self.subTest(name=name):
                self.assertEqual(self.key(name), "mistral")
        self.assertNotEqual(self.key("Scale AI"), self.key("Scale"))
        self.assertNotEqual(self.key("A B"), self.key("AB"))
        self.assertEqual(self.key("Acme Inc."), self.key("ACME Ltd."))

    def test_one_employer_line_keeps_both_sources_and_no_duplicate_subject_name(self):
        out = compose(fixture())
        lines = re.findall(r'<p data-alt="item-line">(.*?)</p>', out["html"])
        mistral = [line for line in lines if "Mistral" in line]
        self.assertEqual(len(mistral), 1)
        self.assertIn("https://two.example/2", mistral[0])
        self.assertIn("https://three.example/3", mistral[0])
        self.assertEqual(out["metric"].lower().count("mistral"), 1)
        self.assertNotIn("+ 1 more", out["metric"])
        self.assertEqual(out["held"], [])
        self.assertEqual(out["checks"]["rows_reconcile"], "PASS")

    def test_different_plans_and_locations_are_kept_separate(self):
        rows = [row(1, "Mistral", "SG", 200, city="Singapore"),
                row(2, "Mistral AI", "SG", 300, city="Singapore"),
                row(3, "Mistral Ltd", "FR", 200, city="Paris")]
        self.assertEqual(compose(fixture(rows))["html"].count('data-alt="item-line"'), 3)

    def test_one_headline_three_metrics_and_a_tracked_top_button(self):
        out = compose(fixture())
        html = out["html"]
        self.assertEqual(html.count('data-alt="lead"'), 1)
        self.assertLess(html.index('data-alt="lead"'), html.index('data-alt="glance"'))
        glance = html.split('data-alt="glance"', 1)[1].split('</table>', 1)[0]
        self.assertEqual(glance.count('data-alt="glance-fact"'), 3)
        self.assertIn("Hiring signals: 3", glance)
        self.assertIn("Biggest announced plan: KLA, 1,200 roles", glance)
        self.assertIn("Open roles tracked: 4,242", glance)
        self.assertNotIn("Country not recorded", glance)
        self.assertNotIn("Other employer news", glance)
        self.assertNotIn("hiring signals, led by", out["text"])
        self.assertIn("How we count", out["text"])
        method = out["text"].split("How we count", 1)[1]
        self.assertIn("Country not recorded: 1 of 4 signals (25%)", method)
        self.assertIn("Other employer news: 1", method)
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>Check your resume against these roles, free</a>', html)
        self.assertEqual(len(links), 1)
        target = urlparse(unescape(links[0]))
        tags = parse_qs(target.query)
        self.assertEqual(target.hostname, "asktherecruiter.com")
        self.assertEqual(target.fragment, "start-intake")
        self.assertEqual(tags["utm_source"], ["tit_email"])
        self.assertEqual(tags["utm_campaign"], ["daily_top"])
        self.assertLess(html.index("Check your resume against these roles, free"), html.index('data-alt="item-line"'))

    def test_missing_open_roles_are_not_invented_as_zero(self):
        fx = fixture()
        fx["open_roles"] = None
        html = compose(fx)["html"]
        self.assertIn("Open roles tracked: not available", html)
        self.assertNotIn("Open roles tracked: 0", html)

    def test_delivered_top_cta_is_a_phone_safe_button(self):
        from cdp import Browser
        from digest_layout import render_html
        out = compose(fixture())
        html = render_html([("talent", out["html"], out["text"])],
                           subject=out["metric"], preheader="Hiring update", kicker="Daily",
                           unsub_url="https://example.com/unsubscribe",
                           manage_url="https://example.com/preferences", dark_mode=True)
        for width, scheme in ((390, "light"), (390, "dark"), (1280, "light"), (1280, "dark")):
            with self.subTest(width=width, scheme=scheme), Browser(width=width, height=900) as page:
                page.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]})
                page.eval_js("document.open();document.write(%s);document.close();" % json.dumps(html))
                data = json.loads(page.eval_js("""JSON.stringify((() => {
                    const a = [...document.querySelectorAll('a')].find(a =>
                        a.textContent === 'Check your resume against these roles, free');
                    const r = a.getBoundingClientRect(), s = getComputedStyle(a);
                    return {height:r.height, right:r.right, background:s.backgroundColor,
                        color:s.color, width:innerWidth, overflow:document.documentElement.scrollWidth};
                })())"""))
                self.assertGreaterEqual(data["height"], 44)
                self.assertEqual(data["background"], "rgb(79, 114, 87)" if scheme == "light" else "rgb(156, 192, 161)")
                self.assertEqual(data["color"], "rgb(255, 255, 255)" if scheme == "light" else "rgb(28, 28, 28)")
                self.assertLessEqual(data["right"], width)
                self.assertLessEqual(data["overflow"], width)

    def test_equal_job_board_deltas_keep_each_scan_and_board_total(self):
        rows = [row(1, 'Cloudflare', 'US', 12, board=True, source='Greenhouse job board',
                    host='job-boards.greenhouse.io', headline='Cloudflare job board: 461 to 473'),
                row(2, 'Cloudflare', 'US', 12, board=True, source='Greenhouse job board',
                    host='job-boards.greenhouse.io', headline='Cloudflare job board: 473 to 485')]
        out = compose(fixture(rows))
        self.assertEqual(out['html'].count('data-alt="item-line"'), 2)
        for total in (473, 485):
            self.assertIn(f'+12 open roles since our last scan, {total} listed', out['text'])
        for source in ('https://job-boards.greenhouse.io/1', 'https://job-boards.greenhouse.io/2'):
            self.assertIn(source, out['html'])
