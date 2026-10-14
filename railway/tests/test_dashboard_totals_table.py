"""Server-rendered monthly totals under the dashboard charts (issue #446 item 1).

Crawlers and no-JS readers saw only "Loading charts…" on [alt_dashboard]. The
template now prints a plain <table> of jobs cut and AI-attributed jobs per
month, built from the SAME /aggregate series the chart draws (date_basis=notice,
whole record, include=series), with the same to-date cut for the month the
clock is inside and no future months, matching toDateMonths()/the chart.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "dashboard-totals.php"
TEMPLATE = PLUGIN / "templates" / "page-dashboard.php"


def _php(call, *args):
    src = MOD.read_text(encoding="utf-8")
    funcs = re.findall(r"\nfunction alt_dashboard_totals_(?:rows|table_html)\s*\(.*?\n\}", src, re.S)
    assert len(funcs) == 2, "both pure helpers must exist"
    code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_attr($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function number_format_i18n($n){ return number_format((float)$n); }\n"
            + "\n".join(funcs) + "\n" + call)
    p = subprocess.run(["php", "-r", code, "--", *[json.dumps(a) for a in args]],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return p.stdout


SERIES = [
    {"month": "2026-08", "jobs": 100, "ai_jobs": 10},
    {"month": "2026-09", "jobs": 200, "ai_jobs": 20},
    {"month": "2026-10", "jobs": 900, "ai_jobs": 90,
     "to_date": {"jobs": 300, "ai_jobs": 30}},
    {"month": "2026-12", "jobs": 5000, "ai_jobs": 0},
]


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Rows(unittest.TestCase):
    def rows(self, series, now="2026-10", limit=24):
        out = _php("echo json_encode(alt_dashboard_totals_rows(json_decode($argv[1], true), $argv[2] ? json_decode($argv[2]) : '', (int) json_decode($argv[3])));",
                   series, now, limit)
        return json.loads(out)

    def test_newest_first_future_dropped_current_month_cut_at_today(self):
        rows = self.rows(SERIES)
        self.assertEqual([r["month"] for r in rows], ["2026-10", "2026-09", "2026-08"])
        self.assertEqual(rows[0]["jobs"], 300)
        self.assertEqual(rows[0]["ai_jobs"], 30)

    def test_limit_keeps_most_recent(self):
        self.assertEqual([r["month"] for r in self.rows(SERIES, limit=2)], ["2026-10", "2026-09"])

    def test_empty(self):
        self.assertEqual(self.rows([]), [])


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Html(unittest.TestCase):
    def html(self, rows):
        return _php("echo alt_dashboard_totals_table_html(json_decode($argv[1], true));", rows)

    def test_table_with_caption_headers_and_figures(self):
        out = self.html([{"month": "2026-10", "jobs": 1234, "ai_jobs": 56}])
        self.assertIn("<table", out)
        self.assertIn("<caption", out)
        self.assertIn('scope="col"', out)
        self.assertIn("October 2026", out)
        self.assertIn("1,234", out)
        self.assertIn("56", out)
        self.assertNotIn("—", out, "no em-dashes in UI copy")

    def test_no_rows_renders_nothing(self):
        self.assertEqual(self.html([]).strip(), "")


class Wiring(unittest.TestCase):
    def test_template_prints_the_table_without_js(self):
        t = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("alt_dashboard_totals_table()", t)
        self.assertIn("function_exists('alt_dashboard_totals_table')", t)

    def test_same_query_as_the_chart(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertIn("'alt_api_aggregate'", src)
        self.assertIn("'date_basis' => 'notice'", src)
        self.assertIn("'include' => 'series'", src)

    def test_include_is_loaded(self):
        main = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
        self.assertIn("dashboard-totals.php", main)


if __name__ == "__main__":
    unittest.main()
