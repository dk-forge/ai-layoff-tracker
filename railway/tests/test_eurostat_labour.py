"""Eurostat job vacancy + unemployment rates by country: reference collector, offline (#478 item 7).

Keyless, CC BY 4.0 (Eurostat reuse policy). The fixture is a trimmed JSON-stat
2.0 document in the shape the dissemination API returned on 2026-10-15.
"""
import json
import os
import sys
import unittest
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import eurostat_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import eurostat_labour as eu  # noqa: E402

REPO = os.path.dirname(RAILWAY)


def _doc(dim_ids, cats, values):
    dims = {d: {"category": {"index": {k: i for i, k in enumerate(cats[d])}}} for d in dim_ids}
    return {"id": dim_ids, "size": [len(cats[d]) for d in dim_ids],
            "dimension": dims, "value": values}


# geo x time = 3 x 3, flat index = g * 3 + t; US is outside the country set.
JVS = _doc(["freq", "indic_em", "geo", "time"],
           {"freq": ["Q"], "indic_em": ["JVR"], "geo": ["EU27_2020", "DE", "US"],
            "time": ["2022-Q4", "2025-Q3", "2025-Q4"]},
           {"0": 2.0, "1": 2.1, "2": 2.2, "4": 2.7, "5": None, "7": 9.9, "8": 9.9})
UNE = _doc(["freq", "geo", "time"],
           {"freq": ["M"], "geo": ["EU27_2020", "FR"], "time": ["2026-07", "2026-08"]},
           {"0": 5.9, "1": 6.0, "2": 7.5, "3": 7.6})


class Parsing(unittest.TestCase):
    def test_decodes_flat_index(self):
        rows = eu.parse_jsonstat(JVS)
        self.assertIn(("EU27_2020", "2025-Q4", 2.2), rows)
        self.assertIn(("DE", "2025-Q3", 2.7), rows)
        self.assertNotIn("2025-Q4", [p for g, p, _ in rows if g == "DE"], "null skipped")

    def test_list_form_index_and_values(self):
        d = json.loads(json.dumps(UNE))
        d["dimension"]["geo"]["category"]["index"] = ["EU27_2020", "FR"]
        d["value"] = [5.9, 6.0, 7.5, 7.6]
        self.assertIn(("FR", "2026-08", 7.6), eu.parse_jsonstat(d))

    def test_garbage_gives_nothing(self):
        self.assertEqual(eu.parse_jsonstat({"nope": 1}), [])
        self.assertEqual(eu.build_payload({}, today=date(2026, 10, 15))["rows"], 0)

    def test_payload_filters_window_and_latest(self):
        p = eu.build_payload({"vacancy_rate": JVS, "unemployment": UNE}, today=date(2026, 10, 15))
        vac = p["datasets"]["vacancy_rate"]
        self.assertNotIn("US", {r[0] for r in vac}, "only EU/EFTA countries")
        self.assertFalse(any(r[1] < "2023" for r in vac), "window applied")
        self.assertEqual(p["latest"], {"vacancy_rate": "2025-12", "unemployment": "2026-08"})
        self.assertEqual(p["fields"], ["geo", "period", "value"])
        self.assertEqual(p["rows"], len(vac) + len(p["datasets"]["unemployment"]))
        self.assertIn("Eurostat", p["attribution"])
        self.assertIn("CC BY 4.0", p["licence"])
        self.assertIn("not", p["note"].lower())

    def test_period_month(self):
        self.assertEqual(eu.period_month("2026-Q1"), "2026-03")
        self.assertEqual(eu.period_month("2026-08"), "2026-08")

    def test_url_is_keyless_and_filtered(self):
        u = eu.url_for("vacancy_rate", "2023-Q1")
        self.assertTrue(u.startswith(eu.BASE + "jvs_q_nace2?"))
        self.assertIn("indic_em=JVR", u)
        self.assertNotIn("key", u.lower())


class StoreGate(unittest.TestCase):
    def test_refuses_empty_or_short(self):
        self.assertFalse(eurostat_import.should_store({"rows": 0})[0])
        p = eu.build_payload({"vacancy_rate": JVS, "unemployment": UNE}, today=date(2026, 10, 15))
        ok, why = eurostat_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("countries", why)

    def test_refuses_missing_aggregate(self):
        p = {"rows": 5, "geos": {"vacancy_rate": ["DE"] * 30, "unemployment": ["EU27_2020"] * 30}}
        ok, why = eurostat_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("EU27", why)

    def test_accepts_full_geo_set(self):
        geos = list(eu.GEOS)
        p = {"rows": 2, "geos": {"vacancy_rate": geos, "unemployment": geos}}
        self.assertTrue(eurostat_import.should_store(p)[0])

    def test_real_size_fits(self):
        n = len(eu.GEOS) * (36 + 12)
        self.assertLess(len(json.dumps([["EU27_2020", "2026-08", 10.25]] * n)), eurostat_import.MAX_BYTES)


class Wiring(unittest.TestCase):
    def test_freshness_spec(self):
        self.assertIn("eurostat_labour", rf.SPECS)
        doc = {"updated": "2026-10-14", "latest": {"vacancy_rate": "2025-12", "unemployment": "2026-08"}}
        self.assertTrue(rf.verdict("eurostat_labour", doc, today=date(2026, 10, 15))[0])

    def test_registered_on_the_plugin(self):
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker", "includes", "reference-data.php")) as fh:
            self.assertIn("'eurostat_labour' => 'alt_ref_eurostat_labour'", fh.read())

    def test_workflow_keyless_and_dispatchable(self):
        with open(os.path.join(REPO, ".github", "workflows", "eurostat-import.yml")) as fh:
            text = fh.read()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("python eurostat_import.py", text)
        self.assertIn("--require-hashes", text)
        self.assertNotIn("secrets.", text.replace("secrets.WP_API_KEY", ""), "keyless source")


if __name__ == "__main__":
    unittest.main()
