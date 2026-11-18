"""Row 183489 (2026-11-18): a negated headline published as a 60,000 cut.

Design (PR #691 review): a negation cue in the count's own sentence HOLDS the
row for review. It is neither dropped as false nor published as true, so a
regex miss in either direction is held, never lost and never published.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from extractor import finalize_extraction  # noqa: E402
from negation_guard import negation_verdict, HOLD, PASS  # noqa: E402
import adjudicate_row  # noqa: E402

SYRACUSE_183489 = ("Outlook down: Microsoft says outage cause is not related to "
                   "60,000 job cuts - Syracuse.com. Outlook down: Microsoft says "
                   "outage cause is not related to 60,000 job cuts Syracuse.com")


def _entry(text):
    return {"raw_text": text, "filing_date": "2026-11-13", "source_type": "news",
            "source_name": "Example", "source_url": "https://example.test/a",
            "verification_level": "bronze"}


def _parsed(count, company):
    return {"is_layoff_event": True, "company_name": company, "job_count": count,
            "job_count_max": count, "layoff_date": "2026-11-13", "confidence": 50,
            "ai_causation": "unknown", "ai_language": None, "reason_tags": []}


class Held(unittest.TestCase):
    CASES = [
        (60000, SYRACUSE_183489),
        (500, "Acme denies reports of 500 layoffs at its Ohio plant."),
        (500, "Acme denies cutting 500 jobs."),
        (1200, "No layoffs are planned for the 1,200 workers at the site, the mayor said."),
        (3000, "The bank ruled out 3,000 job cuts reported last week."),
        (500, "Acme confirmed no layoffs for its 500 staff."),
        # Cause denials: held for a referee, not dropped and not published.
        (500, "Acme cut 500 jobs, not related to AI."),
        (500, "Acme cut 500 jobs, denying AI was the reason."),
        (800, "After weeks of denials, Acme confirmed 800 job cuts on Monday."),
    ]

    def test_each_is_held(self):
        for n, text in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(negation_verdict(n, text), HOLD)

    def test_extractor_marks_row_183489_held_not_dropped(self):
        out = finalize_extraction(_parsed(60000, "Microsoft"), _entry(SYRACUSE_183489))
        self.assertIsNotNone(out, "a held row must reach WordPress as a held post, not vanish")
        self.assertTrue(out.get("held_reason", "").startswith("negation"))

    def test_a_clean_row_carries_no_hold(self):
        out = finalize_extraction(_parsed(1200, "Acme"),
                                  _entry("Acme will lay off 1,200 workers when the plant closes."))
        self.assertIsNotNone(out)
        self.assertNotIn("held_reason", out)


class Passes(unittest.TestCase):
    CASES = [
        (1200, "Acme will lay off 1,200 workers when the plant closes."),
        (500, "Acme cut 500 jobs. No layoffs are planned next year."),
        (400, "The outage was not related to the update. Separately, Acme is cutting 400 jobs in Texas."),
    ]

    def test_each_passes(self):
        for n, text in self.CASES:
            with self.subTest(text=text):
                self.assertEqual(negation_verdict(n, text), PASS)

    def test_absent_count(self):
        self.assertEqual(negation_verdict(None, SYRACUSE_183489), PASS)
        self.assertEqual(negation_verdict(999, SYRACUSE_183489), PASS)


class RefereeIsToldTheRule(unittest.TestCase):
    def test_rules_name_denials(self):
        rules = adjudicate_row.RULES.lower()
        for phrase in ("deny", "not related to", "no layoffs planned"):
            self.assertIn(phrase, rules)


if __name__ == "__main__":
    unittest.main()
