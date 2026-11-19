"""Every country in the committed measurement is classified or acknowledged.

A country that arrives in the data must fail a unit test here, not only the
live data-integrity check (2026-11-19: Bahamas, Bolivia, Malawi and Samoa
reached the corpus undeclared and data-integrity.yml exited 3).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import country_coverage as cc


class EveryCorpusCountryIsDeclared(unittest.TestCase):
    def test_every_country_in_the_committed_measurement_is_declared(self):
        doc = cc.load_measurement()
        self.assertIsNotNone(doc, "no committed country_coverage_measurement.json")
        names = set(doc.get("countries") or {})
        self.assertTrue(names, "committed measurement lists no countries")
        undeclared = sorted(
            n for n in names
            if cc.canonical(n) not in cc.REGISTER
            and cc.canonical(n) not in cc.ACKNOWLEDGED_BACKLOG)
        self.assertEqual(undeclared, [],
                         "countries in the data that are neither in REGISTER nor "
                         "ACKNOWLEDGED_BACKLOG: " + ", ".join(undeclared))



REGIONS_PHP = (Path(__file__).resolve().parents[2] / "wordpress-plugin"
               / "ai-layoff-tracker" / "includes" / "digest-regions.php")


def _region_table_names():
    import re
    text = REGIONS_PHP.read_text(encoding="utf-8")
    start = text.index("function alt_digest_world_country_table")
    body = text[start:text.index("function alt_digest_world_region($")]
    return {(a or b).lower() for a, b in re.findall(r"""(?:'([^']+)'|"([^"]+)")\s*=>\s*'[A-Z]{2}'""", body)}


class EveryCorpusCountryHasARegion(unittest.TestCase):
    """A corpus country missing from the region table falls into "Other"."""

    def test_every_country_in_the_committed_measurement_has_a_region(self):
        doc = cc.load_measurement()
        self.assertIsNotNone(doc)
        known = _region_table_names()
        missing = sorted(n for n in (doc.get("countries") or {})
                         if n.lower() not in known)
        self.assertEqual(missing, [],
                         "corpus countries absent from digest-regions.php: "
                         + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
