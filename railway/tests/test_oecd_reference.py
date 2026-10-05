"""OECD monthly unemployment reference collector: offline.

tests/fixtures/oecd_ialfs_une_m.csv is a real OECD SDMX csv response recorded
by the depth-source probe on 2026-10-05 (PR #468). No test opens a connection.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

# The suite's one `requests` installer: the real module when it is installed
# (CI), a complete offline stub otherwise. Called before importing the
# collector so a later module's partial stub cannot take the slot first.
from tests import _requests_stub  # noqa: E402

_requests_stub.install()

import oecd_archive  # noqa: E402
import oecd_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import oecd_unemployment as oecd  # noqa: E402

FIXTURE = os.path.join(RAILWAY, "tests", "fixtures", "oecd_ialfs_une_m.csv")
REPO = os.path.dirname(RAILWAY)


def recorded():
    with open(FIXTURE, encoding="utf-8") as fh:
        return fh.read()


def with_extra_rows():
    """The recorded header plus synthetic sex/age rows in the same shape."""
    text = recorded()
    lines = text.splitlines()
    base = lines[1].split(",")
    hdr = lines[0].split(",")
    out = list(lines)
    for sex, age, per, val in (("F", "Y15T24", "2026-08", "6.1"), ("M", "Y25T74", "2026-07", "3.4"),
                               ("F", "Y15T24", "2026-07", ""), ("_T", "Y_GE15", "2026-Q2", "4.0")):
        row = list(base)
        row[hdr.index("SEX")], row[hdr.index("AGE")] = sex, age
        row[hdr.index("TIME_PERIOD")], row[hdr.index("OBS_VALUE")] = per, val
        out.append(",".join(row))
    return "\n".join(out) + "\n"


class FakeOpener:
    def __init__(self, body):
        self.body, self.urls = body, []

    def __call__(self, req, timeout):
        self.urls.append(req.full_url)
        return io.BytesIO(self.body.encode())


class QueryTest(unittest.TestCase):
    def test_key_has_nine_dimensions_and_pins_rate_sa_monthly(self):
        parts = oecd.KEY.split(".")
        self.assertEqual(len(parts), 9)
        self.assertEqual(parts[1], "UNE_LF_M")
        self.assertEqual(parts[4], "Y")
        self.assertEqual(parts[8], "M")
        self.assertEqual(parts[5:7], ["", ""])   # every sex, every age

    def test_window_start(self):
        self.assertEqual(oecd.window_start(date(2026, 10, 5), 60), "2021-10")
        self.assertEqual(oecd.window_start(date(2026, 1, 5), 1), "2025-12")


class ParseTest(unittest.TestCase):
    def test_recorded_response(self):
        rows = oecd.parse_csv(recorded())
        self.assertEqual(len(rows), 4)
        self.assertIn(("USA", "_T", "Y_GE15", "2026-08", 4.1), rows)

    def test_sex_and_age_kept_blank_and_quarterly_dropped(self):
        rows = oecd.parse_csv(with_extra_rows())
        self.assertEqual(len(rows), 6)
        keys = {(r[1], r[2]) for r in rows}
        self.assertIn(("F", "Y15T24"), keys)
        self.assertIn(("M", "Y25T74"), keys)
        self.assertNotIn("2026-Q2", {r[3] for r in rows})

    def test_payload_carries_cc_by_attribution(self):
        p = oecd.build_payload(oecd.parse_csv(with_extra_rows()))
        self.assertEqual(p["licence"], "CC BY 4.0")
        self.assertIn("OECD", p["attribution"])
        self.assertIn("CC BY 4.0", p["attribution"])
        self.assertEqual(p["latest"], {"monthly": "2026-08"})
        self.assertEqual(p["datasets"]["monthly"]["JPN"]["F|Y15T24"], [["2026-08", 6.1]])

    def test_fetch_uses_the_window(self):
        op = FakeOpener(recorded())
        self.assertEqual(len(oecd.parse_csv(oecd.fetch_csv("2021-10", opener=op))), 4)
        self.assertIn("startPeriod=2021-10", op.urls[0])


class StoreGuardTest(unittest.TestCase):
    def test_partial_pull_is_not_stored(self):
        ok, why = oecd_import.should_store(oecd.build_payload(oecd.parse_csv(recorded())))
        self.assertFalse(ok)
        self.assertIn("countries", why)

    def test_empty_pull_is_not_stored(self):
        self.assertFalse(oecd_import.should_store(oecd.build_payload([]))[0])


class ArchiveTest(unittest.TestCase):
    def test_writes_sorted_csv_and_manifest_with_attribution(self):
        rows = oecd.parse_csv(with_extra_rows())
        with tempfile.TemporaryDirectory() as d:
            m = oecd_archive.write(d, rows)
            with open(os.path.join(d, oecd_archive.CSV_NAME)) as fh:
                lines = fh.read().splitlines()
            with open(os.path.join(d, "MANIFEST.json")) as fh:
                man = json.load(fh)
        self.assertEqual(lines[0], "ref_area,sex,age,month,unemployment_rate_pct")
        self.assertEqual(lines[1:], sorted(lines[1:]))
        self.assertEqual(m["rows"], 6)
        self.assertIn("CC BY 4.0", man["attribution"])

    def test_refuses_a_big_shrink(self):
        rows = oecd.parse_csv(with_extra_rows())
        with tempfile.TemporaryDirectory() as d:
            oecd_archive.write(d, rows)
            with self.assertRaises(RuntimeError):
                oecd_archive.write(d, rows[:1])


class FreshnessTest(unittest.TestCase):
    def test_spec_and_endpoint_registered(self):
        self.assertIn("oecd_unemployment", rf.SPECS)
        with open(os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker",
                               "includes", "reference-data.php")) as fh:
            self.assertIn("'oecd_unemployment' =>", fh.read())

    def test_fresh_and_stale(self):
        doc = {"updated": "2026-10-02T14:35:00+00:00", "latest": {"monthly": "2026-08"}}
        self.assertTrue(rf.verdict("oecd_unemployment", doc, today=date(2026, 10, 5))[0])
        self.assertTrue(rf.verdict("oecd_unemployment", dict(doc, updated="2026-11-12"),
                                   today=date(2026, 11, 14))[0])
        ok, line = rf.verdict("oecd_unemployment", dict(doc, updated="2026-12-10"),
                              today=date(2026, 12, 12))
        self.assertFalse(ok)
        self.assertIn("monthly", line)


if __name__ == "__main__":
    unittest.main()
