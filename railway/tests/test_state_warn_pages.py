"""US state pages answer "<state> WARN notices <year>" (2026-10-12 scored gap 3).

The facet pages already carried totals, a timeline and the 50 latest entries.
What a reader searching "<state> warn notices 2026" lands for was missing: a
matching title/H1, this year's notices by month, the employers and cities
behind them, and a table of the latest notices. includes/state-warn.php adds
those, built ONLY from rows we hold (a state with no WARN notice this year
gets none of it, and the page keeps its generic title).

The pure helpers are exercised with the real PHP, like test_facet_timeline.py.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MODULE = PLUGIN / "includes" / "state-warn.php"
FACET = PLUGIN / "includes" / "facet-pages.php"
TEMPLATE = PLUGIN / "templates" / "page-facet.php"
PARTIAL = PLUGIN / "templates" / "partials" / "state-warn.php"
BOOT = PLUGIN / "ai-layoff-tracker.php"


def _call(fn, *args):
    src = MODULE.read_text(encoding="utf-8")
    code = ""
    # The helper plus any alt_state_warn_* helper it calls.
    for name in re.findall(r"\nfunction (alt_state_warn_\w+)\s*\(", src):
        m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
        if name in ("alt_state_warn_data", "alt_state_warn_schema"):
            continue
        code += m.group(0) + "\n"
    code += "$a = json_decode($argv[1], true);\necho json_encode(" + fn + "(...$a));\n"
    p = subprocess.run(["php", "-r", code, "--", json.dumps(list(args))],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return json.loads(p.stdout)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class CityFromNotice(unittest.TestCase):
    """The city is read from the notice's own text (warn.py writes it there)."""

    def test_reads_the_city_warn_py_wrote(self):
        ex = "Layoff at Acme Corp in San Jose. 120 employees affected, effective 2026-10-12. Filed under the CA WARN Act."
        self.assertEqual(_call("alt_state_warn_city", ex), "San Jose")

    def test_city_with_state_suffix_is_kept_whole(self):
        ex = "Closure at Foo Inc in Minneapolis, MN. 40 employees affected, effective 2026-01-02. Filed under the MN WARN Act."
        self.assertEqual(_call("alt_state_warn_city", ex), "Minneapolis, MN")

    def test_no_city_means_empty_not_a_guess(self):
        ex = "Layoff at Foo Inc. 40 employees affected, effective 2026-01-02. Filed under the MN WARN Act."
        self.assertEqual(_call("alt_state_warn_city", ex), "")
        self.assertEqual(_call("alt_state_warn_city", "Some news text about a city."), "")

    def test_company_with_in_in_its_name(self):
        ex = "Layoff at Built In Inc in Chicago. 9 employees affected, effective 2026-01-02. Filed under the IL WARN Act."
        self.assertEqual(_call("alt_state_warn_city", ex), "Chicago")


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Summaries(unittest.TestCase):
    ROWS = [
        {"company": "Acme", "job_count": 100, "layoff_date": "2026-03-02", "excerpt": "Layoff at Acme in Austin. 100 employees affected, effective 2026-03-02. Filed under the TX WARN Act."},
        {"company": "Acme", "job_count": 50, "layoff_date": "2026-03-20", "excerpt": "Layoff at Acme in AUSTIN. 50 employees affected, effective 2026-03-20. Filed under the TX WARN Act."},
        {"company": "Beta", "job_count": 70, "layoff_date": "2026-01-05", "excerpt": "Layoff at Beta in Dallas. 70 employees affected, effective 2026-01-05. Filed under the TX WARN Act."},
        {"company": "Gamma", "job_count": 5, "layoff_date": "2026-01-09", "excerpt": "Layoff at Gamma. 5 employees affected, effective 2026-01-09. Filed under the TX WARN Act."},
    ]

    def test_months_sum_notices_and_jobs(self):
        got = _call("alt_state_warn_months", self.ROWS)
        self.assertEqual(got, [
            {"month": "2026-01", "notices": 2, "jobs": 75},
            {"month": "2026-03", "notices": 2, "jobs": 150},
        ])

    def test_employers_ranked_by_jobs(self):
        got = _call("alt_state_warn_employers", self.ROWS, 10)
        self.assertEqual([(e["name"], e["notices"], e["jobs"]) for e in got],
                         [("Acme", 2, 150), ("Beta", 1, 70), ("Gamma", 1, 5)])

    def test_cities_case_folded_and_unknown_left_out(self):
        got = _call("alt_state_warn_cities", self.ROWS, 10)
        self.assertEqual([(c["city"], c["notices"], c["jobs"]) for c in got],
                         [("Austin", 2, 150), ("Dallas", 1, 70)])

    def test_faq_answers_only_from_the_numbers(self):
        stats = {"year": 2026, "notices": 4, "jobs": 225,
                 "employers": [{"name": "Acme", "notices": 2, "jobs": 150}],
                 "cities": [{"city": "Austin", "notices": 2, "jobs": 150}],
                 "latest": "2026-03-20"}
        faq = _call("alt_state_warn_faq", "Texas", stats)
        self.assertGreaterEqual(len(faq), 3)
        text = json.dumps(faq)
        self.assertIn("4 WARN notices", text)
        self.assertIn("225", text)
        self.assertIn("Acme", text)
        self.assertIn("Austin", text)

    def test_faq_empty_without_notices(self):
        self.assertEqual(_call("alt_state_warn_faq", "Texas", {"year": 2026, "notices": 0, "jobs": 0,
                                                                "employers": [], "cities": [], "latest": ""}), [])


class Wiring(unittest.TestCase):
    def test_module_loaded_guarded(self):
        self.assertIn("'state-warn.php'", BOOT.read_text(encoding="utf-8"))

    def test_facet_data_attaches_warn_only_for_states(self):
        src = FACET.read_text(encoding="utf-8")
        self.assertIn("alt_state_warn_data", src)
        self.assertIn("$dim === 'state' && function_exists('alt_state_warn_data')", src)

    def test_title_names_warn_notices_and_year_for_states(self):
        self.assertIn("WARN notices", FACET.read_text(encoding="utf-8"))

    def test_template_renders_partial_before_the_record(self):
        t = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("partials/state-warn.php", t)
        self.assertLess(t.index("partials/state-warn.php"), t.index("<h2>Recorded entries</h2>"))

    def test_faq_schema_matches_visible_faq(self):
        # FAQPage is only valid when the same Q&A is visible on the page: both
        # are rendered from alt_state_warn_faq(), never typed twice.
        part = PARTIAL.read_text(encoding="utf-8")
        mod = MODULE.read_text(encoding="utf-8")
        self.assertIn("alt_state_warn_faq", part)
        self.assertIn("'FAQPage'", mod)
        self.assertIn("alt_state_warn_faq(", mod.split("function alt_state_warn_schema")[1])

    def test_table_scrolls_inside_its_own_container(self):
        part = PARTIAL.read_text(encoding="utf-8")
        self.assertIn('class="alt-state-warn-scroll"', part)
        css = (PLUGIN / "assets" / "layoffs.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.alt-state-warn-scroll\s*\{[^}]*overflow-x:\s*auto")

    def test_no_em_dash_in_reader_copy(self):
        for p in (PARTIAL, MODULE):
            self.assertNotIn("\u2014", p.read_text(encoding="utf-8"), p.name)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class TimelineFutureYear(unittest.TestCase):
    """Live at 2.20.233 the California page printed "2027 so far 0": a future
    year made only of notices that have not taken effect yet. A year after the
    current one with nothing counted to date is not history and is dropped."""

    def test_future_year_with_nothing_to_date_dropped(self):
        src = FACET.read_text(encoding="utf-8")
        m = re.search(r"\nfunction alt_timeline_by_year\s*\(.*?\n\}", src, re.S)
        code = m.group(0) + "\n$p = json_decode($argv[1], true);\necho json_encode(alt_timeline_by_year($p, 2026));\n"
        pts = [{"date": "2026-05", "jobs": 10, "ai_jobs": 0},
               {"date": "2025-05", "jobs": 10, "ai_jobs": 0},
               {"date": "2027-01", "jobs": 300, "ai_jobs": 0, "to_date": {"jobs": 0, "ai_jobs": 0}}]
        p = subprocess.run(["php", "-r", code, "--", json.dumps(pts)], capture_output=True, text=True, timeout=60)
        self.assertEqual([r["year"] for r in json.loads(p.stdout)], [2025, 2026])


if __name__ == "__main__":
    unittest.main()
