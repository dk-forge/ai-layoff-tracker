"""Offline tests for railway/erm_provenance_check.py.

The check reads the country an ERM row was IMPORTED with out of the excerpt
`erm_import.py` wrote at import time, and compares it to the `country` column
as it stands now. A disagreement means an already-published row was re-scored.

These run with no network: every row is a literal dict of the shape /query
returns. The live figures they encode are the ones the check actually found on
2026-08-11.
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_integrity as di
import erm_provenance_check as epc


def _row(rid, jobs, imported, stored, company="Acme", edited=True, source_type="erm"):
    return {
        "id": rid, "job_count": jobs, "country": stored, "company_name": company,
        "source_type": source_type, "edited": edited,
        "excerpt": (f"Internal restructuring at {company} ({imported}): {jobs:,} "
                    f"announced job losses. Recorded by the European Restructuring "
                    f"Monitor (Eurofound), factsheet 1."),
    }


class ExcerptCountry(unittest.TestCase):
    def test_reads_the_country_the_importer_wrote(self):
        self.assertEqual(
            epc.excerpt_country("Internal restructuring at Citigroup (Multiple "
                                "countries): 52,000 announced job losses."),
            "Multiple countries")

    def test_a_company_name_carrying_its_own_brackets_still_parses(self):
        # 459 of 19,494 live ERM rows look like this. Anchoring on the FIRST
        # parenthesis reads the company's own abbreviation as the country and
        # then fails to parse, and an unparsed row must never be called clean.
        self.assertEqual(
            epc.excerpt_country("Internal restructuring at Zespol Elektrowni "
                                "Patnow-Adamow-Konin (ZE PAK) (Poland): 700 "
                                "announced job losses."),
            "Poland")

    def test_an_unreadable_excerpt_is_none_and_not_a_guess(self):
        self.assertIsNone(epc.excerpt_country("no country here at all"))
        self.assertIsNone(epc.excerpt_country(""))
        self.assertIsNone(epc.excerpt_country(None))


class Contradictions(unittest.TestCase):
    def test_the_three_live_rows_of_2026_08(self):
        rows = [
            _row(114335, 52000, "Multiple countries", "United States", "Citigroup"),
            _row(113529, 47000, "Multiple countries", "United States", "General Motors"),
            _row(64351, 45000, "Multiple countries", "United States", "Cinemaworld"),
            _row(110920, 30000, "Multiple countries", "Multiple countries",
                 "Bank of America", edited=False),
            _row(1, 700, "Poland", "Poland", "ZE PAK"),
        ]
        bad, unreadable = epc.contradictions(rows)
        self.assertEqual([x["id"] for x in bad], [114335, 113529, 64351])
        self.assertEqual(sum(x["jobs"] for x in bad), 144000)
        self.assertEqual(unreadable, [])
        self.assertEqual({x["stored_country"] for x in bad}, {"United States"})

    def test_biggest_first_so_the_headline_mover_leads(self):
        rows = [_row(2, 10, "France", "Spain"), _row(3, 9000, "France", "Spain")]
        bad, _ = epc.contradictions(rows)
        self.assertEqual([x["id"] for x in bad], [3, 2])

    def test_an_agreeing_row_is_not_reported(self):
        bad, unreadable = epc.contradictions([_row(4, 500, "Germany", "Germany")])
        self.assertEqual(bad, [])
        self.assertEqual(unreadable, [])

    def test_an_unreadable_row_is_its_own_state_never_a_pass(self):
        row = _row(5, 500, "Germany", "Germany")
        row["excerpt"] = "legacy text with no importer sentence"
        bad, unreadable = epc.contradictions([row])
        self.assertEqual(bad, [])
        self.assertEqual([r["id"] for r in unreadable], [5])

    def test_non_erm_rows_are_out_of_scope(self):
        # Only erm_import writes the country into the excerpt. Reading any other
        # source's excerpt the same way would invent findings.
        row = _row(6, 500, "Germany", "United States", source_type="news")
        bad, unreadable = epc.contradictions([row])
        self.assertEqual(bad, [])
        self.assertEqual(unreadable, [])


def _measurement(rows=19497, unreadable=0, bad=(), age_days=0.0):
    when = datetime.now(timezone.utc) - timedelta(days=age_days)
    return {"measured_at": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "erm_rows": rows, "unreadable": unreadable,
            "contradictions": list(bad), "jobs": sum(x["jobs"] for x in bad)}


CONTRADICTION = {"id": 114335, "company": "Citigroup", "jobs": 52000,
                 "imported_country": "Multiple countries",
                 "stored_country": "United States", "edited": True}


class Judge(unittest.TestCase):
    """The bound, in the ONE place the dashboard and the exit code both read."""

    def test_the_live_2026_08_12_measurement_passes(self):
        state, detail = epc.judge(_measurement())
        self.assertEqual(state, epc.PASS, detail)
        self.assertIn("19,497", detail)

    def test_a_contradiction_is_a_fail_that_names_the_row(self):
        state, detail = epc.judge(_measurement(bad=[CONTRADICTION]))
        self.assertEqual(state, epc.FAIL)
        self.assertIn("114335", detail)
        self.assertIn("52,000", detail)
        self.assertIn("Multiple countries", detail)

    def test_an_unparseable_excerpt_is_unknown_never_a_pass(self):
        # Unchecked rows are the one state this check must never round down.
        state, detail = epc.judge(_measurement(unreadable=459))
        self.assertEqual(state, epc.UNKNOWN)
        self.assertIn("459", detail)

    def test_a_stale_measurement_is_unknown_never_a_pass(self):
        state, detail = epc.judge(
            _measurement(age_days=epc.MAX_MEASUREMENT_AGE_DAYS + 1))
        self.assertEqual(state, epc.UNKNOWN)
        self.assertIn("UNVERIFIED", detail)

    def test_a_measurement_inside_the_weekly_cadence_is_still_judged(self):
        state, _ = epc.judge(_measurement(age_days=7.5))
        self.assertEqual(state, epc.PASS)

    def test_no_measurement_at_all_is_unknown_and_says_how_to_seed_it(self):
        state, detail = epc.judge(None)
        self.assertEqual(state, epc.UNKNOWN)
        self.assertIn("--write", detail)

    def test_an_empty_erm_corpus_is_a_fail(self):
        state, detail = epc.judge(_measurement(rows=0))
        self.assertEqual(state, epc.FAIL)

    def test_a_garbled_measurement_is_unknown(self):
        self.assertEqual(epc.judge({"erm_rows": "lots"})[0], epc.UNKNOWN)


class WiredIntoTheOneRegistry(unittest.TestCase):
    """It was a check nobody ran, which is the same as no check."""

    def _run(self, measurement):
        path = Path(tempfile.mkdtemp()) / "m.json"
        if measurement is not None:
            path.write_text(json.dumps(measurement), encoding="utf-8")
        inv = di.ErmProvenanceInvariant(measurement_path=path)
        return inv.run(di.Ctx(lambda url, timeout: b"{}", 5, "cb"))

    def test_it_is_registered(self):
        self.assertIn("erm_provenance", [i.key for i in di.INVARIANTS])

    def test_the_committed_measurement_makes_it_pass_today(self):
        self.assertEqual(self._run(_measurement()).state, di.PASS)

    def test_a_contradiction_reddens_the_invariant(self):
        res = self._run(_measurement(bad=[CONTRADICTION]))
        self.assertEqual(res.state, di.FAIL)
        self.assertIn("114335", res.detail)

    def test_a_missing_measurement_is_unknown_and_pending(self):
        res = self._run(None)
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertTrue(res.pending)

    def test_it_does_not_touch_the_network(self):
        # It reads the committed file, so it must be honest about that: a check
        # declaring reads_live_data would be claimed by the degradation
        # contract tests it cannot satisfy.
        inv = next(i for i in di.INVARIANTS if i.key == "erm_provenance")
        self.assertFalse(inv.reads_live_data)


class TheCommittedFileIsReal(unittest.TestCase):

    def test_the_repos_own_measurement_parses_and_is_judgeable(self):
        m = epc.load_measurement()
        self.assertIsInstance(m, dict, "railway/erm_provenance_measurement.json is missing")
        state, detail = epc.judge(m)
        self.assertIn(state, (epc.PASS, epc.FAIL, epc.UNKNOWN), detail)
        self.assertIsInstance(m.get("contradictions"), list)


if __name__ == "__main__":
    unittest.main()
