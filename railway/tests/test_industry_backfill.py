"""Guards for the industry backfill: cross-language vocabulary parity + the
pure validation/agreement logic the worker relies on.

The worker constrains the model to extractor.INDUSTRY_VOCABULARY and the
/industry-backfill endpoint independently re-validates against the PHP
alt_industry_vocabulary() (= alt_industry_rules() keys). If those two lists
drift, every model-confirmed fill would be rejected server-side and the whole
batch would fail loudly. This test makes the drift fail HERE instead.
"""
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Unit tests exercise pure guardrails and do not create an API client.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

from extractor import (
    INDUSTRY_VOCABULARY,
    _validate_industry_result,
)
import industry_backfill

API_PHP = os.path.join(
    os.path.dirname(__file__), "..", "..", "wordpress-plugin", "ai-layoff-tracker",
    "includes", "api.php",
)


def php_industry_labels():
    """Parse the canonical labels (array keys) out of alt_industry_rules()."""
    with open(os.path.abspath(API_PHP), encoding="utf-8") as fh:
        text = fh.read()
    start = text.index("function alt_industry_rules")
    body = text[start:text.index("\n}", start)]
    # Each rule line is:  'Canonical Label' => array( ... ),
    return [m.group(1) for m in re.finditer(r"'([^']+)'\s*=>\s*array\(", body)]


class IndustryVocabularyParityTest(unittest.TestCase):
    def test_python_matches_php_set(self):
        php = php_industry_labels()
        self.assertTrue(php, "could not parse alt_industry_rules() labels from api.php")
        self.assertEqual(
            set(INDUSTRY_VOCABULARY), set(php),
            "extractor.INDUSTRY_VOCABULARY is out of sync with "
            "alt_industry_rules() in api.php — update whichever drifted.",
        )

    def test_python_matches_php_order(self):
        # Order equality is stricter than set equality and catches a silent
        # reorder; the prompt lists them in this order too.
        self.assertEqual(list(INDUSTRY_VOCABULARY), php_industry_labels())

    def test_no_duplicate_labels(self):
        self.assertEqual(len(INDUSTRY_VOCABULARY), len(set(INDUSTRY_VOCABULARY)))


class ValidateIndustryResultTest(unittest.TestCase):
    def test_exact_vocabulary_label_passes(self):
        self.assertEqual(_validate_industry_result({"industry": "Technology"}),
                         {"industry": "Technology"})

    def test_label_is_trimmed(self):
        self.assertEqual(_validate_industry_result({"industry": "  Technology  "}),
                         {"industry": "Technology"})

    def test_unknown_collapses_to_blank(self):
        self.assertEqual(_validate_industry_result({"industry": "unknown"}), {"industry": ""})

    def test_off_vocabulary_label_collapses_to_blank(self):
        # A hallucinated / near-miss label is never written — it is a skip.
        self.assertEqual(_validate_industry_result({"industry": "Tech"}), {"industry": ""})
        self.assertEqual(_validate_industry_result({"industry": "Healthcare"}), {"industry": ""})

    def test_missing_or_empty_field_is_blank(self):
        self.assertEqual(_validate_industry_result({}), {"industry": ""})
        self.assertEqual(_validate_industry_result({"industry": ""}), {"industry": ""})
        self.assertEqual(_validate_industry_result({"industry": None}), {"industry": ""})

    def test_non_dict_is_none_for_retry(self):
        self.assertIsNone(_validate_industry_result(None))
        self.assertIsNone(_validate_industry_result("Technology"))


class TwoPassAgreementTest(unittest.TestCase):
    """classify_confirmed only writes when two independent passes agree on the
    same non-empty label. Patch classify_industry with a scripted sequence."""

    def _with_passes(self, sequence):
        calls = {"n": 0}

        def fake(company, excerpt):
            i = calls["n"]
            calls["n"] += 1
            return sequence[i]
        return fake

    def setUp(self):
        self._orig = industry_backfill.classify_industry
        industry_backfill.SINGLE_PASS = False

    def tearDown(self):
        industry_backfill.classify_industry = self._orig

    def test_agree_confirms(self):
        industry_backfill.classify_industry = self._with_passes(
            [{"industry": "Technology"}, {"industry": "Technology"}])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("Technology", "confirmed"))

    def test_disagree_is_unconfirmed(self):
        industry_backfill.classify_industry = self._with_passes(
            [{"industry": "Technology"}, {"industry": "Energy"}])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("", "unconfirmed"))

    def test_first_blank_short_circuits(self):
        # A first-pass skip needs no second call.
        industry_backfill.classify_industry = self._with_passes([{"industry": ""}])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("", "unconfirmed"))

    def test_model_failure_propagates(self):
        industry_backfill.classify_industry = self._with_passes([None])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("", "failed"))

    def test_second_pass_failure_is_failed(self):
        industry_backfill.classify_industry = self._with_passes(
            [{"industry": "Technology"}, None])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("", "failed"))

    def test_single_pass_mode_skips_confirmation(self):
        industry_backfill.SINGLE_PASS = True
        industry_backfill.classify_industry = self._with_passes([{"industry": "Energy"}])
        self.assertEqual(industry_backfill.classify_confirmed("Acme", "x"),
                         ("Energy", "confirmed"))


class RotatingSliceTest(unittest.TestCase):
    def test_slice_rotates_and_covers(self):
        rows = list(range(10))
        # batch 4 -> 3 pages; day 0,1,2 cover [0:4],[4:8],[8:10]
        self.assertEqual(industry_backfill.rotating_slice(rows, 4, 0), rows[0:4])
        self.assertEqual(industry_backfill.rotating_slice(rows, 4, 1), rows[4:8])
        self.assertEqual(industry_backfill.rotating_slice(rows, 4, 2), rows[8:10])
        # wraps
        self.assertEqual(industry_backfill.rotating_slice(rows, 4, 3), rows[0:4])

    def test_empty_and_zero_batch(self):
        self.assertEqual(industry_backfill.rotating_slice([], 4, 0), [])
        self.assertEqual(industry_backfill.rotating_slice([1, 2], 0, 0), [])


if __name__ == "__main__":
    unittest.main()
