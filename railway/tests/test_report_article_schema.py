"""Monthly / quarterly / yearly report pages carry Article JSON-LD (SEO audit
2026-10-13 item 7). Week and invalid periods are noindex and get none."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MOD = PLUGIN / "includes/report-article.php"
STUB = ("function add_action(...$a){}function home_url($p='/'){return 'https://x.example/blog'.$p;}"
        f"require '{MOD}';")


def _run(code):
    return subprocess.run(["php", "-r", STUB + code], capture_output=True, text=True, check=True).stdout


class Wiring(unittest.TestCase):
    def test_loaded(self):
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/report-article.php';",
                      (PLUGIN / "ai-layoff-tracker.php").read_text())


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: no php binary")
class Behaviour(unittest.TestCase):
    def test_month_article(self):
        a = json.loads(_run("echo json_encode(alt_report_article_node('month','2026-06','June 2026',"
                            "'https://x.example/blog/ai-layoff-tracker/report/2026-06/','2026-06-29'));"))
        self.assertEqual(a["@type"], "Article")
        self.assertEqual(a["headline"], "June 2026 Layoffs Report: Verified Job Cuts")
        self.assertEqual(a["datePublished"], "2026-06-01")
        self.assertEqual(a["dateModified"], "2026-06-29")
        self.assertEqual(a["mainEntityOfPage"], "https://x.example/blog/ai-layoff-tracker/report/2026-06/")
        self.assertEqual(a["isBasedOn"]["@id"], "https://x.example/blog/ai-layoff-tracker/#dataset")

    def test_quarter_and_year_start_dates(self):
        q = json.loads(_run("echo json_encode(alt_report_article_node('quarter','2026-Q2','Q2 2026','u',''));"))
        self.assertEqual(q["datePublished"], "2026-04-01")
        self.assertNotIn("dateModified", q)
        y = json.loads(_run("echo json_encode(alt_report_article_node('year','2025','2025','u','2025-12-30'));"))
        self.assertEqual(y["datePublished"], "2025-01-01")

    def test_no_node_for_noindex_kinds(self):
        for k in ("week", "invalid", "archive", "current"):
            self.assertEqual(_run(f"var_export(alt_report_article_node('{k}','2026-W02','x','u','2026-01-09'));"), "NULL")


if __name__ == "__main__":
    unittest.main()
