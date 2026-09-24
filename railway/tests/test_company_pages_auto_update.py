"""A page for EVERY company with data, and it keeps up as rows arrive.

Owner addition 2026-09-24. The autopilot already admits every employer with
one source-linked canonical event (below the two-event floor the page renders
`noindex`). The gap: it only ever looked at UNMAPPED keys, so an employer
admitted as `noindex` on its first event stayed out of the index forever, even
after its second, third and tenth. The promotion pass fixes that, and only for
rows the autopilot itself admitted: an editor's deliberate `noindex` carries
`admitted_by = ''` and is never touched.

These are static guards (no database in CI), in the shape of
test_company_directory_guards.py.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
DB = (PLUGIN / "includes" / "db.php").read_text(encoding="utf-8")
DIR = (PLUGIN / "includes" / "company-directory.php").read_text(encoding="utf-8")
WF = (ROOT / ".github" / "workflows" / "company-directory-autopilot.yml").read_text(encoding="utf-8")


def _fn(src, name):
    start = src.index("function " + name + "(")
    return src[start:src.index("\n}\n", start)]


class Provenance(unittest.TestCase):
    def test_directory_records_who_admitted_a_row(self):
        table = DB[DB.index("CREATE TABLE $directory ("):]
        table = table[:table.index(") $charset")]
        self.assertIn("admitted_by VARCHAR(16) NOT NULL DEFAULT ''", table)

    def test_autopilot_marks_its_own_admissions(self):
        body = _fn(DB, "alt_api_company_directory_autopilot")
        self.assertIn("'admitted_by' => 'autopilot'", body)

    def test_admission_writer_persists_it(self):
        body = _fn(DB, "alt_company_directory_admit_mappings")
        self.assertIn("$data['admitted_by']", body)


class Promotion(unittest.TestCase):
    def test_promotion_only_touches_autopilot_noindex_rows_over_the_floor(self):
        body = _fn(DIR, "alt_company_directory_promote_autopilot")
        self.assertIn("d.review_status = 'noindex'", body)
        self.assertIn("d.admitted_by = 'autopilot'", body)
        self.assertIn("alt_company_directory_supported_events_sql()", body)
        self.assertIn("s.supported >= %d", body)
        self.assertIn("'review_status' => 'approved'", body)

    def test_autopilot_runs_promotion_before_the_cache_flush(self):
        body = _fn(DB, "alt_api_company_directory_autopilot")
        self.assertIn("alt_company_directory_promote_autopilot(", body)
        self.assertLess(body.index("alt_company_directory_promote_autopilot("),
                        body.index("alt_flush_caches()"))
        self.assertIn("$out['promoted']", body)


class Cadence(unittest.TestCase):
    def test_runs_daily(self):
        crons = re.findall(r"cron:\s*'([^']+)'", WF)
        self.assertEqual(len(crons), 1)
        self.assertTrue(crons[0].endswith("* * *"), crons[0])


if __name__ == "__main__":
    unittest.main()
