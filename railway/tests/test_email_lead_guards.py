"""Counts that led a sent edition and were not layoffs (audit 2026-11-12).

Row 183237 (2026-11-11): Business Insider's headline "Here's what the 60,000
employees mulling a buyout may not realize" re-entered Microsoft's buyout
ELIGIBILITY pool as 60,000 job cuts two days after row 183020 was trashed for
the same figure. The buyout guard only knew "offer(ed) buyouts" and "eligible",
so "mulling a buyout" and "buyout packages to" walked past it.

Row 183367 (2026-11-11) led the 2026-11-12 daily edition: "1,562 officers who
were dismissed from their positions, during an internal cleansing drive" is a
police force disciplining officers for misconduct, not an employer cutting
jobs. A disciplinary dismissal count is not a layoff count.

Both guards are deterministic and text-based, so they hold whatever the model
does, and the referee prompt states the same rule for the rows already live.
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
from buyout_guard import count_is_only_an_offer  # noqa: E402
from disciplinary_guard import count_is_disciplinary  # noqa: E402
import adjudicate_row  # noqa: E402

BI_183237 = ("I'm the ex-VP of HR at Microsoft. Here's what the 60,000 employees "
             "mulling a buyout may not realize. Microsoft is offering buyout "
             "packages to some 60,000 employees, or more than 25% of the workforce.")
PNP_183367 = ("Almost 6,000 personnel were penalized, including 1,562 officers who "
              "were dismissed from their positions, during an internal cleansing "
              "drive, the Philippine National Police announced on Wednesday.")
REAL_DISMISSAL = ("The carmaker said it will dismiss 1,562 workers as it closes the "
                  "plant to cut costs.")
CUT_VIA_BUYOUTS = "Acme will cut 1,000 jobs, mostly through voluntary buyouts."


def _entry(text):
    return {"raw_text": text, "filing_date": "2026-11-11", "source_type": "news",
            "source_name": "Example", "source_url": "https://example.test/a",
            "verification_level": "bronze"}


def _parsed(count, company):
    return {"is_layoff_event": True, "company_name": company, "job_count": count,
            "job_count_max": count, "layoff_date": "2026-11-11", "confidence": 50,
            "ai_causation": "unknown", "ai_language": None, "reason_tags": []}


class BuyoutHeadline(unittest.TestCase):
    def test_row_183237_mulling_a_buyout_is_refused(self):
        self.assertTrue(count_is_only_an_offer(60000, BI_183237))
        self.assertIsNone(finalize_extraction(_parsed(60000, "Microsoft"), _entry(BI_183237)))

    def test_a_cut_carried_out_through_buyouts_still_counts(self):
        self.assertFalse(count_is_only_an_offer(1000, CUT_VIA_BUYOUTS))


class DisciplinaryDismissal(unittest.TestCase):
    def test_row_183367_police_cleansing_drive_is_refused(self):
        self.assertTrue(count_is_disciplinary(1562, PNP_183367))
        self.assertIsNone(finalize_extraction(
            _parsed(1562, "Philippine National Police"), _entry(PNP_183367)))

    def test_an_economic_dismissal_still_counts(self):
        self.assertFalse(count_is_disciplinary(1562, REAL_DISMISSAL))
        row = finalize_extraction(_parsed(1562, "Acme Motors"), _entry(REAL_DISMISSAL))
        self.assertIsNotNone(row)

    def test_absent_count_is_not_refused(self):
        self.assertFalse(count_is_disciplinary(999, PNP_183367))
        self.assertFalse(count_is_disciplinary(None, PNP_183367))


class RefereeIsToldTheRule(unittest.TestCase):
    """The referees judge rows already live, so they need the same rule."""

    def test_rules_name_each_non_layoff_count(self):
        rules = adjudicate_row.RULES.lower()
        for phrase in ("buyout", "eligib", "pledge", "combined", "disciplin",
                       "different employer"):
            self.assertIn(phrase, rules, phrase)

    def test_rule_numbers_stay_unique_with_the_duplicate_rule(self):
        import re
        nums = re.findall(r"^(\d+)\.", adjudicate_row.RULES + adjudicate_row.DUPLICATE_RULE, re.M)
        self.assertEqual(len(nums), len(set(nums)), nums)


if __name__ == "__main__":
    unittest.main()
