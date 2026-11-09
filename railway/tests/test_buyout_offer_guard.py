"""An offer of voluntary buyouts to N eligible employees is not N job cuts.

Row 183020 (2026-11-03): "Microsoft offered buyouts to around 60,000
employees." was stored as 60,000 verified, AI-attributed job cuts and was 45%
of the 2026-W45 weekly edition. The cited reports describe ELIGIBILITY for a
voluntary programme (Fortune: "This offer gives eligible employees who may be
considering a future outside the company a new choice"); nobody knows how many
will accept. The guard is deterministic and text-based, like the
retrospective guard, so it holds whatever the model does.
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

MICROSOFT = ("Microsoft offered buyouts to around 60,000 employees. An employment "
             "lawyer explains what to weigh before accepting the offer.")
ELIGIBLE = ("Microsoft expands buyouts: 60,000 employees eligible for the voluntary "
            "programme, the company said in a memo.")
SPANISH = "La empresa ofreció bajas voluntarias a 2.000 empleados elegibles."
REAL_CUT = ("Acme will lay off 1,200 workers after only 300 accepted buyouts offered "
            "to 5,000 employees.")
ACCEPTED = "Acme said 1,500 employees accepted its buyout offer and will leave in March."


def _entry(text):
    return {"raw_text": text, "filing_date": "2026-11-03", "source_type": "news",
            "source_name": "Example", "source_url": "https://example.test/a",
            "verification_level": "bronze"}


def _parsed(count, company="Microsoft"):
    return {"is_layoff_event": True, "company_name": company, "job_count": count,
            "job_count_max": count, "layoff_date": "2026-11-03", "confidence": 50,
            "ai_causation": "unknown", "ai_language": None, "reason_tags": []}


class BuyoutOfferIsNotACut(unittest.TestCase):
    def test_microsoft_row_183020_is_refused(self):
        self.assertTrue(count_is_only_an_offer(60000, MICROSOFT))
        self.assertIsNone(finalize_extraction(_parsed(60000), _entry(MICROSOFT)))

    def test_eligible_employees_figure_is_refused(self):
        self.assertTrue(count_is_only_an_offer(60000, ELIGIBLE))
        self.assertTrue(count_is_only_an_offer(2000, SPANISH))

    def test_a_real_cut_beside_an_offer_still_counts(self):
        self.assertFalse(count_is_only_an_offer(1200, REAL_CUT))
        row = finalize_extraction(_parsed(1200, company="Acme"), _entry(REAL_CUT))
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 1200)

    def test_accepted_buyouts_are_real_departures(self):
        self.assertFalse(count_is_only_an_offer(1500, ACCEPTED))

    def test_plain_layoff_is_untouched(self):
        text = "Widget Inc announced 500 layoffs effective October 1."
        self.assertFalse(count_is_only_an_offer(500, text))


if __name__ == "__main__":
    unittest.main()
