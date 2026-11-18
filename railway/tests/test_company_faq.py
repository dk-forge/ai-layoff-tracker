"""Company page FAQ + FAQPage JSON-LD (CGO SEO/GEO pass 2026-11-18).

Facts only from the page's own rows; JSON-LD strings equal the visible ones.
"""
import html
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "company-faq.php"
STUBS = r"""define('ABSPATH','/');
function esc_html($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function esc_url($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function wp_json_encode($v,$f=0){return json_encode($v,$f);}
"""
EVENTS = [
    {"layoff_date": "2025-03-02", "job_count": 120, "sources": [{"url": "https://warn.example/a", "name": "Ohio WARN"}]},
    {"layoff_date": "2026-06-10", "job_count": 0, "sources": [{"url": "https://news.example/b", "name": "Reuters"}]},
    {"layoff_date": "2026-02-01", "job_count": 49, "sources": [{"url": "https://sec.example/c", "name": "SEC 8-K"}]},
]


def _php(expr):
    src = MOD.read_text(encoding="utf-8").replace("<?php", "", 1)
    p = subprocess.run(["php", "-r", STUBS + src + "\n" + expr], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


def _items(events, year=2026, name="Acme"):
    return json.loads(_php("echo json_encode(alt_company_faq_items(%s, json_decode(%s, true), %d));"
                           % (json.dumps(name), json.dumps(json.dumps(events)), year)))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class CompanyFaq(unittest.TestCase):
    def test_this_year_answer_counts_only_this_years_rows_and_cites_latest(self):
        a = _items(EVENTS)[0]
        self.assertEqual(a["q"], "Did Acme have layoffs in 2026?")
        self.assertEqual(a["a"], "Yes. The tracker lists 2 layoff records at Acme in 2026, covering 49 jobs. "
                                 "The latest is dated 10 June 2026 (source: Reuters).")
        self.assertEqual(a["link"]["url"], "https://news.example/b")

    def test_no_rows_this_year_says_so_with_latest_date(self):
        a = _items(EVENTS[:1])[0]["a"]
        self.assertEqual(a, "The tracker has no 2026 layoff record for Acme. The latest record is dated 2 March 2025 (source: Ohio WARN).")

    def test_total_answer_and_zero_jobs_clause_dropped(self):
        self.assertIn("3 layoff records for Acme since 2 March 2025, with 169 jobs cut", _items(EVENTS)[1]["a"])
        no_jobs = [dict(EVENTS[1])]
        self.assertNotIn("jobs", _items(no_jobs)[1]["a"].split(".")[0])

    def test_nothing_without_rows_or_name(self):
        self.assertEqual(_items([]), [])
        self.assertEqual(_items(EVENTS, name=""), [])

    def test_jsonld_equals_visible_text(self):
        out = _php("echo alt_company_faq_html(alt_company_faq_items('Acme & Co', json_decode(%s, true), 2026));"
                   % json.dumps(json.dumps(EVENTS)))
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', out, re.S).group(1))
        self.assertEqual(ld["@type"], "FAQPage")
        for q in ld["mainEntity"]:
            self.assertIn("<h3>" + html.escape(q["name"]) + "</h3>", out)
            self.assertIn("<p>" + html.escape(q["acceptedAnswer"]["text"]), out)
        self.assertNotRegex(out, "[–—]")

    def test_wired_into_template_and_loader(self):
        tpl = (PLUGIN / "templates" / "page-company-directory.php").read_text(encoding="utf-8")
        self.assertIn("alt_company_faq_block($alt_dir)", tpl)
        self.assertIn("includes/company-faq.php", (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8"))
        self.assertIn("empty($data['indexable'])", MOD.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
