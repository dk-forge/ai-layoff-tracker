"""Fixture-driven guards for the Japanese/Korean layoff-language detector.

The fixtures are bounded excerpts of real public filings (see
``fixtures/official_filings_manifest.json`` for provenance).  These tests
prove the detector flags genuine restructuring language and refuses the
observed near-miss noise (statute names, debt-ratio cuts, governance
boilerplate) without any network access.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources.layoff_language import (
    TermMatch,
    detect_layoff_language,
    is_review_candidate,
    strip_markup,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _manifest():
    return json.loads((FIXTURES / "official_filings_manifest.json").read_text())


class RealFilingFixtureTests(unittest.TestCase):
    def test_every_manifest_fixture_matches_its_expected_verdict(self):
        entries = _manifest()["fixtures"]
        self.assertGreaterEqual(len(entries), 7)
        for entry in entries:
            with self.subTest(fixture=entry["file"]):
                text = (FIXTURES / entry["file"]).read_text()
                matches = detect_layoff_language(text)
                self.assertEqual(is_review_candidate(matches),
                                 entry["expect_review_candidate"])
                strong = {m.term for m in matches if m.tier == "strong"}
                for term in entry["expect_strong_terms"]:
                    self.assertIn(term, strong)
                if not entry["expect_review_candidate"]:
                    self.assertEqual(strong, set())

    def test_negatives_still_surface_context_matches_for_reviewer_statistics(self):
        text = (FIXTURES / "opendart_kr_20260716000545_hanjin_negative.txt").read_text()
        matches = detect_layoff_language(text)
        self.assertFalse(is_review_candidate(matches))
        self.assertIn("구조조정", {m.term for m in matches})

    def test_excerpts_are_bounded_and_carry_the_match(self):
        text = (FIXTURES / "opendart_kr_20260714000459_kookminbank_prospectus.txt").read_text()
        matches = detect_layoff_language(text, excerpt_radius=80)
        self.assertTrue(matches)
        for match in matches:
            self.assertIsInstance(match, TermMatch)
            self.assertLessEqual(len(match.excerpt), 2 * 80 + len(match.term) + 4)
            self.assertIn(match.term[0], match.excerpt)


class DetectorRuleTests(unittest.TestCase):
    def test_line_break_inside_a_term_still_matches(self):
        matches = detect_layoff_language("当社は希望退\n職者の募集を決議した")
        self.assertIn("希望退職", {m.term for m in matches if m.tier == "strong"})

    def test_korean_spacing_variant_matches_the_compound_term(self):
        matches = detect_layoff_language("당사는 인력 감축 계획을 발표했다")
        self.assertIn("인력감축", {m.term for m in matches if m.tier == "strong"})

    def test_short_hangul_term_requires_a_word_boundary(self):
        # 절감 원가 must NOT be glued into a 감원 match by whitespace stripping.
        self.assertEqual(detect_layoff_language("비용 절감 원가 개선"), ())
        matches = detect_layoff_language("대규모 감원 발표")
        self.assertIn("감원", {m.term for m in matches})
        self.assertFalse(is_review_candidate(matches))  # 감원 is context-tier

    def test_statute_name_alone_is_never_a_candidate(self):
        matches = detect_layoff_language("기업구조조정 촉진법 제8조에 따라")
        self.assertFalse(is_review_candidate(matches))

    def test_match_cap_bounds_pathological_documents(self):
        matches = detect_layoff_language("希望退職 " * 500, max_matches=40)
        self.assertEqual(len(matches), 40)

    def test_strip_markup_drops_tags_scripts_and_entities(self):
        text = strip_markup(
            "<html><script>var a=1;</script><p>희망퇴직&nbsp;실시</p><!-- x --></html>")
        self.assertEqual(text, "희망퇴직 실시")


if __name__ == "__main__":
    unittest.main()
