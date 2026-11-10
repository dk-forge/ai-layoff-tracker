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

    # Weekly benchmark 2026-11-08 (docs/benchmarks/2026-11-08.md): two live rows
    # in the top of the window were retrospectives the guard did not recognise.
    def test_a_past_year_reference_is_not_a_new_event(self):
        # Row 183047: a 2026 San Diego profile recalled "in 2011 Nokia announced
        # some 4,000 layoffs" and the row was stored as 4,000 on 2026-11-05.
        text = ("However, in 2011 Nokia announced some 4,000 layoffs, including "
                "hundreds in San Diego. Both Pahissa and Fuentes lost their jobs.")
        self.assertEqual(retrospective_verdict(4000, text), ("retrospective", None))

    def test_a_new_cut_that_mentions_a_past_year_keeps_its_row(self):
        text = ("The company said today it will cut 3,000 jobs, after it cut 10,000 "
                "in 2023.")
        self.assertEqual(retrospective_verdict(3000, text), ("event", None))

    def test_a_future_year_is_not_a_past_year(self):
        text = "Widget Inc will cut 2,000 jobs in 2027, the company said in a memo."
        self.assertEqual(retrospective_verdict(2000, text), ("event", None))

    def test_a_rises_to_total_is_cumulative(self):
        # Row 183019: "Personalabbau bei Bosch steigt auf mehr als 30.000 Stellen".
        de = "Personalabbau bei Bosch steigt auf mehr als 30.000 Stellen."
        self.assertEqual(retrospective_verdict(30000, de), ("retrospective", None))
        en = "Bosch's job-cut programme rises to more than 30,000 positions."
        self.assertEqual(retrospective_verdict(30000, en), ("retrospective", None))
        # But "will rise to" a new cut with its own date is left alone.
        ok = "Bosch said today it will cut 1,500 more jobs, which brings the total to 30,000."
        self.assertEqual(retrospective_verdict(30000, ok), ("incremental", 1500))

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


class NetHeadcountDeclineIsNotAnEvent(unittest.TestCase):
    """2026-11-09 headline incident (ai_all_time, us_all_time).

    Two of the rows removed that day were not layoffs at all: Wells Fargo's
    workforce "shrinking by more than 10,000" over time, and the combined net
    headcount change of all DAX companies (~46,000). A net decline or a
    multi-employer sum is not one employer's cut, so it must never be stored
    as a dated event.
    """

    def test_wells_fargo_workforce_shrink_is_not_a_10000_layoff(self):
        text = ("Wells Fargo's workforce has shrunk by more than 10,000 employees, "
                "the bank said, as it leans on automation.")
        self.assertEqual(retrospective_verdict(10000, text), ("retrospective", None))
        text = "Wells Fargo headcount fell by 10,000 over the year."
        self.assertEqual(retrospective_verdict(10000, text), ("retrospective", None))

    def test_dax_combined_net_change_is_not_one_event(self):
        text = ("Germany's DAX companies cut a combined net 46,000 jobs, according "
                "to an EY analysis.")
        self.assertEqual(retrospective_verdict(46000, text), ("retrospective", None))
        de = "Die DAX-Konzerne haben unterm Strich netto 46.000 Stellen abgebaut."
        self.assertEqual(retrospective_verdict(46000, de), ("retrospective", None))

    def test_a_plain_cut_that_mentions_headcount_keeps_its_row(self):
        text = "Acme will cut 1,000 jobs, about 5% of its headcount, the company said."
        self.assertEqual(retrospective_verdict(1000, text), ("event", None))



if __name__ == "__main__":
    unittest.main()
