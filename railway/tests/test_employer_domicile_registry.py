"""Offline guards for the curated employer-domicile registry and its matcher.

The registry holds deterministic public HQ facts only; these tests keep its
shape valid (normalized keys, no duplicate claims, evidence fields present)
and pin the matcher behavior the backfill relies on: blank-only writes,
unicode company names, prefix entries and the era guard.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from employer_domicile_backfill import (  # noqa: E402
    build_items, era_allows, load_registry, normalize_company, registry_lookup,
)


class RegistryShape(unittest.TestCase):
    def test_registry_loads_with_normalized_unique_keys(self):
        registry, exact, prefixes = load_registry()
        self.assertGreaterEqual(len(registry["companies"]), 50)
        # load_registry raises on malformed entries; a non-empty exact map
        # proves every match key passed the normalized/unique checks.
        self.assertGreater(len(exact), len(registry["companies"]))
        self.assertTrue(all(entry.get("prefix") for _, entry in prefixes))

    def test_named_us_multi_country_companies_are_covered(self):
        _, exact, prefixes = load_registry()
        for company in ("Oracle", "Meta", "Block", "Snap", "UKG", "ZoomInfo",
                        "SentinelOne", "MRI Software", "Kraken", "BitGo"):
            entry = registry_lookup(exact, prefixes, company)
            self.assertIsNotNone(entry, company)
            self.assertEqual(entry["employer_country"], "United States", company)

    def test_ambiguous_domiciles_stay_absent(self):
        _, exact, prefixes = load_registry()
        for company in ("Airbus", "Shell", "Royal Dutch Shell", "Schlumberger",
                        "Seagate Technology", "SEB", "Booking.com"):
            self.assertIsNone(registry_lookup(exact, prefixes, company), company)


class Matcher(unittest.TestCase):
    def setUp(self):
        self.registry, self.exact, self.prefixes = load_registry()

    def test_normalization_folds_unicode_and_punctuation(self):
        self.assertEqual(normalize_company("Estée Lauder"), "estee lauder")
        # ø/æ have no ASCII decomposition and are dropped without a space.
        self.assertEqual(normalize_company("A.P. Møller-Mærsk"), "a p mller mrsk")
        self.assertEqual(normalize_company("  DOW  INC. "), "dow inc")

    def test_stored_name_variants_resolve(self):
        cases = {
            "Hewlett Packard (HP)": "United States",
            "International Business Machines Corp.": "United States",
            "A.P. Møller-Mærsk": "Denmark",
            "Tata Consultancy Services (TCS)": "India",
            "SAP SE": "Germany",
        }
        for name, country in cases.items():
            entry = registry_lookup(self.exact, self.prefixes, name)
            self.assertIsNotNone(entry, name)
            self.assertEqual(entry["employer_country"], country, name)

    def test_prefix_matches_truncated_doge_but_not_bare_department(self):
        hit = registry_lookup(self.exact, self.prefixes,
                              "Department of Government Efficiency Service (DOGE)")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["employer_country"], "United States")
        self.assertIsNone(registry_lookup(self.exact, self.prefixes, "Department of Government"))

    def test_era_guard_excludes_pre_move_and_undated_rows(self):
        entry = registry_lookup(self.exact, self.prefixes, "Nordea")
        self.assertEqual(entry.get("not_before"), "2018-10-01")
        self.assertFalse(era_allows(entry, {"layoff_date": "2017-10-27"}))
        self.assertFalse(era_allows(entry, {"layoff_date": "", "announcement_date": ""}))
        self.assertTrue(era_allows(entry, {"layoff_date": "2024-09-04"}))

    def test_build_items_fills_blanks_only_and_labels_the_registry(self):
        rows = [
            {"id": 1, "company_name": "Oracle", "employer_country": "United States",
             "layoff_date": "2026-04-06"},
            {"id": 2, "company_name": "Block", "employer_country": "",
             "layoff_date": "2026-02-26"},
            {"id": 2, "company_name": "Block", "employer_country": "",
             "layoff_date": "2026-02-26"},
            {"id": 3, "company_name": "Unknown Startup XYZ", "employer_country": "",
             "layoff_date": "2026-01-01"},
        ]
        items, skipped_era, unmatched = build_items(self.registry, self.exact, self.prefixes, rows)
        self.assertEqual([item["id"] for item in items], [2])
        self.assertEqual(items[0]["employer_country"], "United States")
        self.assertIn("Curated employer-domicile registry", items[0]["employer_country_evidence"])
        self.assertIn("https://block.xyz", items[0]["employer_country_evidence"])
        self.assertEqual(unmatched, ["Unknown Startup XYZ"])
        self.assertEqual(skipped_era, [])


if __name__ == "__main__":
    unittest.main()
