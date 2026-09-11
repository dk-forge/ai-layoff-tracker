"""A retrospective count is never a new event dated by the article (2026-09-12).

Row 179276 (TECHLOG 2026-09-11): a South African explainer said "Amazon has
cut around 30,000 corporate jobs since late 2025" and the extractor stored
30,000 jobs on the article's publish date, ai_explicit, confidence 95. It led
the daily digest and was a third of the year's AI-attributed total. The guard
under test is deterministic and text-based (`extractor.retrospective_verdict`,
applied in `finalize_extraction`), so it holds no matter what the model does
with the prompt's CUMULATIVE TRAP. No network, no model: the post-parse
function is exercised directly on a fake parsed dict.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import extractor  # noqa: E402
from extractor import finalize_extraction, retrospective_verdict  # noqa: E402

AMAZON = ("Amazon has cut around 30,000 corporate jobs since late 2025, in what the "
          "company framed as a push to operate like the world's largest startup. The "
          "reductions began in October 2025 and continued through July 2026, and CEO "
          "Andy Jassy said generative AI would reduce the corporate workforce over "
          "time. Here is what it means for South African job seekers.")

INCREMENTAL = ("Acme Corp cut 300 more jobs on Tuesday, bringing the total to 30,000 "
               "since the restructuring began in 2025. The company said AI tools had "
               "made the roles redundant.")

PLAIN = ("Widget Inc announced 500 layoffs effective October 1, the company said in "
         "a memo to staff. The cuts affect its logistics division.")

SPANISH = ("Telefonica ha recortado 5.000 empleos desde 2025, segun un informe de la "
           "empresa publicado este jueves. La compania atribuye los recortes a la "
           "inteligencia artificial.")


def _entry(text, filing_date="2026-09-10"):
    return {"raw_text": text, "filing_date": filing_date, "source_type": "news",
            "source_name": "Example", "source_url": "https://example.test/a",
            "verification_level": "bronze"}


def _parsed(count, date="2026-09-10", company="Amazon", quote=None, **extra):
    row = {"is_layoff_event": True, "company_name": company, "job_count": count,
           "job_count_max": count, "layoff_date": date, "confidence": 95,
           "ai_causation": "primary_cause", "ai_language": quote,
           "reason_tags": ["ai_automation"]}
    row.update(extra)
    return row


class RetrospectiveCountIsNotAnEvent(unittest.TestCase):
    def test_amazon_explainer_is_not_stored_as_a_dated_30000_row(self):
        self.assertEqual(retrospective_verdict(30000, AMAZON), ("retrospective", None))
        row = finalize_extraction(_parsed(30000, quote="generative AI would reduce the corporate workforce"),
                                  _entry(AMAZON))
        self.assertIsNone(row, "a cumulative 30,000 dated by the article was stored")

    def test_incremental_figure_wins_over_the_cumulative_one(self):
        self.assertEqual(retrospective_verdict(30000, INCREMENTAL), ("incremental", 300))
        row = finalize_extraction(_parsed(30000, company="Acme Corp", quote="AI tools had made the roles redundant"),
                                  _entry(INCREMENTAL))
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 300)
        self.assertEqual(row["job_count_max"], 300, "the cumulative ceiling survived")
        self.assertEqual(row["layoff_date"], "2026-09-10")
        # And when the model already picked 300, it stays 300.
        self.assertEqual(retrospective_verdict(300, INCREMENTAL), ("event", None))

    def test_plain_announcement_is_untouched(self):
        self.assertEqual(retrospective_verdict(500, PLAIN), ("event", None))
        row = finalize_extraction(_parsed(500, company="Widget Inc", date="2026-10-01",
                                          ai_causation="unknown"), _entry(PLAIN))
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 500)
        self.assertEqual(row["layoff_date"], "2026-10-01")

    def test_spanish_desde_is_retrospective(self):
        self.assertEqual(retrospective_verdict(5000, SPANISH), ("retrospective", None))
        self.assertIsNone(finalize_extraction(_parsed(5000, company="Telefonica",
                                                      ai_causation="unknown"),
                                              _entry(SPANISH)))

    def test_german_seit_is_retrospective(self):
        text = "Siemens hat seit 2025 rund 4.000 Stellen abgebaut, teilte der Konzern mit."
        self.assertEqual(retrospective_verdict(4000, text), ("retrospective", None))

    def test_a_dated_new_cut_in_a_retrospective_sentence_keeps_its_row(self):
        text = ("The company said today it will cut 1,200 jobs, the latest in a series "
                "of reductions since 2024.")
        self.assertEqual(retrospective_verdict(1200, text), ("event", None))

    def test_a_superlative_since_is_a_comparison_not_a_total(self):
        text = "Ford will cut 2,000 salaried jobs, its biggest reduction since 2020."
        self.assertEqual(retrospective_verdict(2000, text), ("event", None))
        text = "Ford ha anunciado 2.000 despidos, el mayor recorte desde 2020."
        self.assertEqual(retrospective_verdict(2000, text), ("event", None))

    def test_the_phrase_constant_is_what_the_guard_reads(self):
        # Mutation: with the "since <year>" span removed the Amazon row would
        # pass as an event, so the constant is load-bearing, not decorative.
        without_since = tuple(p for p in extractor.RETROSPECTIVE_SPANS
                              if "since" not in p)
        self.assertLess(len(without_since), len(extractor.RETROSPECTIVE_SPANS))
        with patch.object(extractor, "RETROSPECTIVE_SPANS", without_since):
            self.assertEqual(retrospective_verdict(30000, AMAZON), ("event", None))
            self.assertIsNotNone(finalize_extraction(_parsed(30000), _entry(AMAZON)))
        # Same for the anchors: without "bringing the total to" the 30,000 in the
        # incremental text is no longer recognised as cumulative.
        with patch.object(extractor, "CUMULATIVE_ANCHORS", ()), \
                patch.object(extractor, "RETROSPECTIVE_SPANS",
                             tuple(p for p in extractor.RETROSPECTIVE_SPANS if "total" not in p)):
            self.assertEqual(retrospective_verdict(30000, INCREMENTAL), ("event", None))

    def test_prompt_carries_the_rule_too(self):
        self.assertIn("CUMULATIVE TRAP", extractor.SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
