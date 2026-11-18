"""Row 183489 (2026-11-18): a negated headline published as a 60,000 cut."""
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
from negation_guard import count_is_negated  # noqa: E402
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


class NegatedCounts(unittest.TestCase):
    def test_row_183489_not_related_to_job_cuts_is_refused(self):
        self.assertTrue(count_is_negated(60000, SYRACUSE_183489))

    def test_extractor_drops_row_183489(self):
        self.assertIsNone(finalize_extraction(
            _parsed(60000, "Microsoft"), _entry(SYRACUSE_183489)))

    def test_denies_layoffs(self):
        self.assertTrue(count_is_negated(
            500, "Acme denies reports of 500 layoffs at its Ohio plant."))

    def test_no_layoffs_planned(self):
        self.assertTrue(count_is_negated(
            1200,
            "No layoffs are planned for the 1,200 workers at the site, the mayor said."))

    def test_rules_out_job_cuts(self):
        self.assertTrue(count_is_negated(
            3000, "The bank ruled out 3,000 job cuts reported last week."))


class RealCutsStillCount(unittest.TestCase):
    def test_plain_cut(self):
        self.assertFalse(count_is_negated(
            1200, "Acme will lay off 1,200 workers when the plant closes."))

    def test_denial_then_confirmation(self):
        self.assertFalse(count_is_negated(
            800, "After weeks of denials, Acme confirmed 800 job cuts on Monday."))

    def test_unrelated_negation_elsewhere(self):
        self.assertFalse(count_is_negated(
            400, "The outage was not related to the update. Separately, Acme "
                 "is cutting 400 jobs in Texas."))

    def test_negation_in_the_next_sentence_does_not_reach_the_count(self):
        self.assertFalse(count_is_negated(
            500, "Acme cut 500 jobs. No layoffs are planned next year."))

    def test_denying_the_cause_keeps_the_cut(self):
        self.assertFalse(count_is_negated(500, "Acme cut 500 jobs, not related to AI."))
        self.assertFalse(count_is_negated(500, "Acme cut 500 jobs, denying AI was the reason."))

    def test_absent_count(self):
        self.assertFalse(count_is_negated(None, SYRACUSE_183489))
        self.assertFalse(count_is_negated(999, SYRACUSE_183489))


class RefereeIsToldTheRule(unittest.TestCase):
    def test_rules_name_denials(self):
        rules = adjudicate_row.RULES.lower()
        for phrase in ("deny", "not related to", "no layoffs planned"):
            self.assertIn(phrase, rules)


if __name__ == "__main__":
    unittest.main()
