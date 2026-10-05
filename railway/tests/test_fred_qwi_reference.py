"""FRED labour series + Census QWI reference collectors: offline.

No live response could be recorded (the sandbox that wrote this has no egress
to either API), so the fixtures below are hand-built in the documented
response shapes: FRED `series/observations` JSON and the Census Data API
array-of-arrays. No test opens a connection; no test needs a key.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import date

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

from tests import _requests_stub  # noqa: E402

_requests_stub.install()

import fred_archive  # noqa: E402
import fred_import  # noqa: E402
import qwi_archive  # noqa: E402
import qwi_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import census_qwi as qwi  # noqa: E402
from sources import fred_labour as fred  # noqa: E402

REPO = os.path.dirname(RAILWAY)
PLUGIN = os.path.join(REPO, "wordpress-plugin", "ai-layoff-tracker")
SECRET = "k3y-SHOULD-NEVER-APPEAR"


def fred_body(dates_vals):
    return json.dumps({"observations": [{"date": d, "value": v} for d, v in dates_vals]})


class FredOpener:
    def __init__(self, fail=()):
        self.urls, self.fail = [], set(fail)

    def __call__(self, req, timeout):
        self.urls.append(req.full_url)
        sid = req.full_url.split("series_id=")[1].split("&")[0]
        if sid in self.fail:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(
                json.dumps({"error_message": f"api_key {SECRET} is not registered"}).encode()))
        if fred.SERIES[sid][2] == "weekly":
            return io.BytesIO(fred_body([("2026-09-19", "230000"), ("2026-09-26", "225000")]).encode())
        return io.BytesIO(fred_body([("2026-07-01", "4.1"), ("2026-08-01", "."),
                                     ("2026-09-01", "4.2")]).encode())


def qwi_table(breakdown, states=("06", "36"), quarters=("2025-Q3", "2025-Q4")):
    ep, dim, _ = qwi.QUERIES[breakdown]
    values = {"industry": ["51", "54"], "agegrp": ["A00", "A04"], "sex": ["0", "2"],
              "education": ["E0", "E4"], "race": ["A0", "A4"], "ethnicity": ["A0", "A2"]}[dim]
    hdr = ["HirA", "Sep", "EmpEnd", dim, "time", "ownercode", "seasonadj", "state"]
    rows = [hdr]
    for st in states:
        for q in quarters:
            for v in values:
                rows.append(["100", "90", "5000", v, q, "A05", "U", st])
    rows.append([None, None, None, values[0], quarters[0], "A05", "U", "01"])  # suppressed
    return json.dumps(rows)


class QwiOpener:
    def __init__(self, states=("06", "36"), bad=None):
        self.urls, self.states, self.bad = [], states, bad

    def __call__(self, req, timeout):
        self.urls.append(req.full_url)
        for b, (ep, dim, fixed) in qwi.QUERIES.items():
            if f"/qwi/{ep}?" in req.full_url and f"%2C{dim}&" in req.full_url and \
                    all(f"{k}={v}" in req.full_url for k, v in fixed.items()):
                if b == self.bad:
                    return io.BytesIO(b"<html>Invalid Key</html>")
                st = req.full_url.split("for=state%3A")[1].split("&")[0]
                if st == "%2A":
                    raise AssertionError("the API refuses a state wildcard")
                return io.BytesIO(qwi_table(b, (st,) if st in self.states else ()).encode())
        raise AssertionError("unexpected url")


class FredTest(unittest.TestCase):
    def test_curated_series(self):
        for s in ("UNRATE", "PAYEMS", "ICSA", "CCSA", "JTSLDL", "USINFO", "LNS14027662"):
            self.assertIn(s, fred.SERIES)
        # Not a FRED id (live 400 "series does not exist", 2026-10-05); USINFO is it.
        self.assertNotIn("CES5000000001", fred.SERIES)

    def test_parse_drops_missing_and_rows_are_flat_with_label_and_category(self):
        rows = fred.parse("UNRATE", fred_body([("2026-08-01", "."), ("2026-09-01", "4.2")]))
        self.assertEqual(rows, [["UNRATE", "2026-09-01", 4.2, "Unemployment rate",
                                 "unemployment", "monthly"]])
        self.assertEqual(fred.FIELDS[:3], ["series_id", "date", "value"])

    def test_pull_payload(self):
        op = FredOpener()
        p = fred.pull("abc", fred.window_start(date(2026, 10, 5)), opener=op)
        self.assertEqual(len(op.urls), len(fred.SERIES))
        self.assertIn("observation_start=2016-01-01", op.urls[0])
        self.assertEqual(p["latest"], {"monthly": "2026-09", "weekly": "2026-09"})
        self.assertTrue(fred_import.should_store(p)[0])
        self.assertIn("FRED", p["attribution"])

    def test_bad_key_is_explained_but_never_printed_and_not_stored(self):
        p = fred.pull(SECRET, "2016-01-01", opener=FredOpener(fail={"ICSA"}))
        ok, why = fred_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("ICSA", why)
        blob = json.dumps(p)
        self.assertNotIn(SECRET, blob)
        self.assertIn("not registered", blob)

    def test_archive(self):
        p = fred.pull("abc", "1900-01-01", opener=FredOpener())
        with tempfile.TemporaryDirectory() as d:
            m = fred_archive.write(d, p["datasets"]["observations"])
            with open(os.path.join(d, fred_archive.CSV_NAME)) as fh:
                lines = fh.read().splitlines()
            self.assertEqual(lines[0], "series_id,date,value")
            self.assertEqual(lines[1:], sorted(lines[1:]))
            self.assertEqual(m["rows"], p["rows"])
            with self.assertRaises(RuntimeError):
                fred_archive.write(d, p["datasets"]["observations"][:2])


class QwiTest(unittest.TestCase):
    def test_queries_cover_each_breakdown_once_on_the_right_endpoint(self):
        self.assertEqual({v[0] for v in qwi.QUERIES.values()}, {"sa", "se", "rh"})
        self.assertEqual(qwi.QUERIES["education"][0], "se")
        self.assertEqual(qwi.QUERIES["race"][0], "rh")
        u = qwi.url("by_sector", "abc", date(2026, 10, 5), state="36")
        self.assertEqual(len(qwi.STATES), 51)
        for needle in ("for=state%3A36", "time=from+2022-Q1", "ind_level=S", "ownercode=A05"):
            self.assertIn(needle, u)

    def test_rows_carry_every_dimension(self):
        rows = qwi.parse("education", qwi_table("education"))
        self.assertEqual(len(rows), 8)   # suppressed all-null row dropped
        r = dict(zip(qwi.FIELDS, rows[0]))
        self.assertEqual(r["breakdown"], "education")
        self.assertEqual((r["industry"], r["sex"], r["agegrp"], r["race"]), ("00", "0", "A00", "A0"))
        self.assertIn(r["education"], ("E0", "E4"))
        self.assertEqual((r["HirA"], r["Sep"], r["EmpEnd"]), (100, 90, 5000))

    def test_keep_latest(self):
        rows = qwi.parse("sex", qwi_table("sex", quarters=("2025-Q1", "2025-Q2", "2025-Q3")))
        self.assertEqual({r[2] for r in qwi.keep_latest(rows, 2)}, {"2025-Q2", "2025-Q3"})

    def test_pull_store_guard_and_freshness_month(self):
        states = tuple(qwi.STATES)
        op = QwiOpener(states)
        p = qwi.pull("abc", opener=op)
        self.assertEqual(len(op.urls), 6 * 51)   # one request per breakdown per state
        self.assertEqual(len(p["states"]), 51)
        self.assertEqual(p["latest"], {"quarterly": "2025-12"})
        self.assertTrue(qwi_import.should_store(p)[0], qwi_import.should_store(p))
        self.assertFalse(qwi_import.should_store(qwi.pull("abc", opener=QwiOpener()))[0])  # 2 states

    def test_invalid_key_page_is_a_named_error_without_the_key(self):
        states = tuple(qwi.STATES)
        p = qwi.pull(SECRET, opener=QwiOpener(states, bad="race"))
        ok, why = qwi_import.should_store(p)
        self.assertFalse(ok)
        self.assertIn("race", why)
        self.assertIn("Invalid Key", " ".join(p["errors"]))
        self.assertNotIn(SECRET, json.dumps(p))

    def test_archive_one_file_per_quarter(self):
        p = qwi.pull("abc", opener=QwiOpener(), states=("06", "36"))
        with tempfile.TemporaryDirectory() as d:
            r = qwi_archive.write(d, p["datasets"])
            self.assertEqual(r["written"], ["2025-Q3", "2025-Q4"])
            with open(os.path.join(d, "MANIFEST.json")) as fh:
                self.assertIn("2025-Q4", json.load(fh)["quarters"])
            thin = {"sex": p["datasets"]["sex"][:1]}
            self.assertEqual(qwi_archive.write(d, thin)["kept"], ["2025-Q3"])


class RegistrationTest(unittest.TestCase):
    def test_sources_allowed_and_watched(self):
        with open(os.path.join(PLUGIN, "includes", "reference-data.php")) as fh:
            php = fh.read()
        for src in (fred.SOURCE, qwi.SOURCE):
            self.assertIn(f"'{src}' =>", php)
            self.assertIn(src, rf.SPECS)

    def test_freshness(self):
        doc = {"updated": "2026-10-02T14:00:00+00:00",
               "latest": {"monthly": "2026-08", "weekly": "2026-09"}}
        self.assertTrue(rf.verdict("fred_labour", doc, today=date(2026, 10, 5))[0])
        ok, line = rf.verdict("fred_labour", dict(doc, updated="2026-11-20"),
                              today=date(2026, 11, 21))
        self.assertFalse(ok)
        self.assertIn("weekly", line)
        q = {"updated": "2026-10-02", "latest": {"quarterly": "2025-12"}}
        self.assertTrue(rf.verdict("census_qwi", q, today=date(2026, 10, 5))[0])
        self.assertFalse(rf.verdict("census_qwi", dict(q, updated="2027-04-08"),
                                    today=date(2027, 4, 10))[0])

    def test_workflows_pass_keys_only_through_secrets(self):
        for wf, secret in (("fred-import.yml", "FRED_API_KEY"), ("fred-archive.yml", "FRED_API_KEY"),
                           ("qwi-import.yml", "CENSUS_API_KEY"), ("qwi-archive.yml", "CENSUS_API_KEY")):
            with open(os.path.join(REPO, ".github", "workflows", wf)) as fh:
                text = fh.read()
            self.assertIn(f"{secret}: ${{{{ secrets.{secret} }}}}", text)
            self.assertIn("workflow_dispatch", text)
            self.assertNotIn("echo $" + secret, text)


@unittest.skipUnless(shutil.which("php"), "php not installed")
class PhpFilterTest(unittest.TestCase):
    def run_filter(self, doc, params):
        out = subprocess.run(
            ["php", os.path.join(RAILWAY, "tests", "fixtures", "reference_filter_harness.php"),
             os.path.join(PLUGIN, "includes", "reference-data.php")],
            input=json.dumps({"doc": doc, "params": params}), capture_output=True, text=True,
            check=True)
        return json.loads(out.stdout)

    def test_filters_rows_by_field_and_ignores_other_params(self):
        p = qwi.pull("abc", opener=QwiOpener(), states=("06", "36"))
        out = self.run_filter(p, {"state": "06,99", "education": "E4", "cb": "x"})
        self.assertEqual(list(out["datasets"]["sex"]), [])
        self.assertEqual(len(out["datasets"]["education"]), 2)
        self.assertTrue(all(r[1] == "06" for r in out["datasets"]["education"]))
        self.assertEqual(out["rows"], 2)
        same = self.run_filter(p, {"cb": "x"})
        self.assertEqual(same["rows"], p["rows"])
        self.assertNotIn("filtered", same)

    def test_document_without_fields_is_untouched(self):
        doc = {"datasets": {"monthly": {"USA": {"_T|Y_GE15": [["2026-08", 4.1]]}}}, "rows": 1}
        self.assertEqual(self.run_filter(doc, {"state": "06"}), doc)


@unittest.skipUnless(shutil.which("php"), "php not installed")
class SourcesPageTest(unittest.TestCase):
    """Owner rule: every reference source is a row on the public Sources page."""

    def test_every_reference_source_is_a_row_on_the_rendered_page(self):
        html = subprocess.run(
            ["php", os.path.join(RAILWAY, "tests", "fixtures", "sources_page_harness.php"), PLUGIN],
            capture_output=True, text=True, check=True).stdout
        expect = {  # source id -> (row name, official link)
            "bls_jolts_cps": ("<b>BLS JOLTS &amp; CPS</b>", "https://www.bls.gov/jlt/"),
            "oecd_unemployment": ("<b>OECD unemployment</b>", "https://data-explorer.oecd.org/"),
            "fred_labour": ("<b>FRED labour series</b>", "https://fred.stlouisfed.org/"),
            "census_qwi": ("<b>Census QWI</b>", "https://lehd.ces.census.gov/data/"),
        }
        self.assertEqual(set(expect), set(rf.SPECS), "a reference source has no Sources row")
        for src, (name, link) in expect.items():
            self.assertIn(name, html, src)
            self.assertIn(f'href="{link}"', html, src)
        with open(os.path.join(REPO, "docs", "OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md")) as fh:
            register = fh.read()
        for src in expect:
            self.assertIn(f"`{src}`", register)


if __name__ == "__main__":
    unittest.main()
