"""A hiring figure can never become a layoff count."""
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


def parsed(count):
    return {
        "is_layoff_event": True,
        "company_name": "Freeport Aggregates",
        "job_count": count,
        "job_count_max": count,
        "layoff_date": "2026-09-22",
        "excerpt": "will create 20 new jobs",
    }


def entry(text):
    return {
        "raw_text": text,
        "source_type": "news",
        "source_name": "Example",
        "source_url": "https://example.test/story",
        "filing_date": "2026-09-22",
    }


class JobCreationGuardTests(unittest.TestCase):
    def test_exact_live_false_positive_is_rejected(self):
        text = ("The company is targeting completion of its planned capacity "
                "expansion, which will create 20 new jobs in operations and "
                "maintenance.")
        self.assertIsNone(finalize_extraction(parsed(20), entry(text), text))

    def test_creation_elsewhere_does_not_hide_a_real_cut(self):
        text = ("The company will eliminate 20 positions this month. "
                "A separate expansion will create 50 new jobs next year.")
        row = finalize_extraction(parsed(20), entry(text), text)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 20)

    def test_mixed_sentence_is_left_for_the_existing_extractor_rules(self):
        text = "The company will eliminate 20 roles and create 20 new jobs."
        self.assertIsNotNone(finalize_extraction(parsed(20), entry(text), text))


if __name__ == "__main__":
    unittest.main()
