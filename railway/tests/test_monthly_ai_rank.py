"""Monthly report: "who said AI caused their cuts", ranked (owner ask 2026-09-29).

alt_mr_ai_rank() is pure: it takes the month's verified rows and returns two
ranked lists. NAMED holds companies whose own statement named AI (ai_explicit=1);
only these count toward the "because of AI" total. MENTIONED holds rows where AI
was linked only loosely or by the press (ai_causation='ai_linked'). A company
that explicitly denied AI is in neither list. Each entry carries the quote and
the source link a reporter needs to check it.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

MOD = (Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
       / "includes" / "monthly-report.php")


def rank(rows, limit=10):
    src = MOD.read_text(encoding="utf-8")
    m = re.search(r"\nfunction alt_mr_ai_rank\s*\(.*?\n\}", src, re.S)
    assert m, "alt_mr_ai_rank is missing"
    code = (m.group(0) + "\n$rows = json_decode($argv[1], true);"
            f"\necho json_encode(alt_mr_ai_rank($rows, {limit}));")
    p = subprocess.run(["php", "-r", code, "--", json.dumps(rows)],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return json.loads(p.stdout)


def row(company, jobs, explicit=0, cause="unknown", quote="", url="", country="", industry=""):
    return {"company": company, "job_count": jobs, "ai_explicit": explicit,
            "ai_causation": cause, "ai_language": quote, "source_url": url,
            "country": country, "industry": industry}


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class AiRank(unittest.TestCase):
    def test_named_and_mentioned_are_separate(self):
        out = rank([
            row("Acme", 500, explicit=1, cause="primary_cause", quote="AI lets us do more with fewer people",
                url="https://example.com/a", country="United States", industry="Technology"),
            row("Beta", 900, cause="ai_linked", quote="analysts tie the cuts to AI", url="https://example.com/b"),
            row("Gamma", 300, cause="explicitly_denied"),
            row("Delta", 700),
        ])
        self.assertEqual([e["company"] for e in out["named"]], ["Acme"])
        self.assertEqual([e["company"] for e in out["mentioned"]], ["Beta"])
        a = out["named"][0]
        self.assertEqual((a["jobs"], a["country"], a["industry"]), (500, "United States", "Technology"))
        self.assertEqual(a["quote"], "AI lets us do more with fewer people")
        self.assertEqual(a["source_url"], "https://example.com/a")

    def test_rows_of_one_company_add_up_and_rank_by_jobs(self):
        out = rank([
            row("Small", 100, explicit=1),
            row("Big", 400, explicit=1, url="https://example.com/big1"),
            row("Big", 800, explicit=1, quote="automation", url="https://example.com/big2"),
        ])
        self.assertEqual([(e["company"], e["jobs"]) for e in out["named"]], [("Big", 1200), ("Small", 100)])
        # The source shown is the largest row's, so the link backs the biggest figure.
        self.assertEqual(out["named"][0]["source_url"], "https://example.com/big2")
        self.assertEqual(out["named"][0]["quote"], "automation")

    def test_limit_and_long_quotes(self):
        rows = [row(f"C{i:02d}", 100 + i, explicit=1, quote="x" * 400) for i in range(15)]
        out = rank(rows, 10)
        self.assertEqual(len(out["named"]), 10)
        self.assertEqual(out["named"][0]["company"], "C14")
        self.assertLessEqual(len(out["named"][0]["quote"]), 201)

    def test_non_http_source_is_dropped(self):
        out = rank([row("Acme", 10, explicit=1, url="javascript:alert(1)")])
        self.assertEqual(out["named"][0]["source_url"], "")

    def test_empty_month(self):
        self.assertEqual(rank([]), {"named": [], "mentioned": []})


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class PitchNamesAiEmployers(unittest.TestCase):
    def pitch(self, fig):
        src = MOD.read_text(encoding="utf-8")
        m = re.search(r"\nfunction alt_mr_pitch\s*\(.*?\n\}", src, re.S)
        code = m.group(0) + "\n$f = json_decode($argv[1], true); echo alt_mr_pitch($f);"
        p = subprocess.run(["php", "-r", code, "--", json.dumps(fig)], capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr + p.stdout
        return p.stdout

    def test_top_three_named_then_count(self):
        named = [{"company": c, "jobs": j} for c, j in (("A", 900), ("B", 500), ("C", 300), ("D", 100))]
        out = self.pitch({"label": "September 2026", "verified_jobs": 5000,
                          "ai_rank": {"named": named, "mentioned": []}})
        self.assertIn("Employers that named AI as a reason: A (900), B (500), C (300), and 1 more in the full report.", out)

    def test_no_named_no_sentence(self):
        out = self.pitch({"label": "September 2026", "verified_jobs": 5000,
                          "ai_rank": {"named": [], "mentioned": [{"company": "X", "jobs": 5}]}})
        self.assertNotIn("named AI as a reason", out)


if __name__ == "__main__":
    unittest.main()
