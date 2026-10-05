"""AI exposure by job and city: collector, import guard, archive, and display.

Offline. The collector is driven by a fake opener serving hand-built files in
the shapes the four sources really publish (probed from a GitHub runner on
2026-10-05: occ_level.csv columns, O*NET 31.0 text zip, OEWS May 2025
national/MSA headers, Employment Projections 2025-35 Table 1.2 headers). The
display is the REAL includes/ai-exposure.php and its partial rendered through
tests/fixtures/ai_exposure_harness.php.

Pinned:
  * exposure is the study's dv_rating_beta, averaged from O*NET-SOC detail
    codes to the 6-digit SOC; only OEWS "detailed" cross-industry rows and
    Employment Projections "Line item" rows join;
  * the import never stores a partial pull, a thin join or an oversize doc,
    and its success notice says site=stored only when the host said so;
  * registration: allow-list, freshness SPECS, workflows, archive;
  * most/least exposed lists, the quadrant rule (>= threshold and growth < 0
    is "exposed and shrinking"), the metro picker; hidden when data is missing;
  * copy says exposure is tasks an AI system could speed up, per the study,
    and never that jobs will be lost; a credit and an as-of line under each
    card; every source shown has a Sources-page row; colour tokens only.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_exposure_archive  # noqa: E402
import ai_exposure_import  # noqa: E402
import reference_freshness as rf  # noqa: E402
from sources import ai_exposure as ax  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
HARNESS = Path(__file__).resolve().parent / "fixtures/ai_exposure_harness.php"
PHP = shutil.which("php")

STUDY_CSV = (
    "O*NET-SOC Code,Title,dv_rating_alpha,dv_rating_beta,dv_rating_gamma,"
    "human_rating_alpha,human_rating_beta,human_rating_gamma\n"
    "15-1252.00,Software Developers,0.4,0.7,1.0,0.3,0.6,0.9\n"
    "43-9022.00,Word Processors and Typists,0.6,0.8,1.0,0.5,0.7,0.9\n"
    "13-2011.00,Accountants and Auditors,0.3,0.6,0.9,0.3,0.5,0.8\n"
    "13-2011.01,Accountants,0.3,0.4,0.9,0.3,0.5,0.8\n"
    "47-2061.00,Construction Laborers,0.0,0.05,0.1,0.0,0.0,0.1\n"
    "35-2014.00,Cooks Restaurant,0.0,0.1,0.2,0.0,0.0,0.1\n"
    "99-9999.00,Bad Row,0.0,not-a-number,0.0,0,0,0\n"
)
ONET_TXT = ("O*NET-SOC Code\tTitle\tDescription\n"
            "15-1252.00\tSoftware Developers\tx\n"
            "43-9022.00\tWord Processors and Typists\tx\n"
            "13-2011.00\tAccountants and Auditors\tx\n"
            "13-2011.01\tForensic Accountants\tx\n"
            "47-2061.00\tConstruction Laborers\tx\n"
            "35-2014.00\tCooks, Restaurant\tx\n")
OEWS_HDR = ("AREA", "AREA_TITLE", "AREA_TYPE", "PRIM_STATE", "NAICS", "NAICS_TITLE", "I_GROUP",
            "OWN_CODE", "OCC_CODE", "OCC_TITLE", "O_GROUP", "TOT_EMP", "EMP_PRSE", "JOBS_1000",
            "LOC_QUOTIENT", "PCT_TOTAL", "PCT_RPT", "H_MEAN", "A_MEAN", "MEAN_PRSE", "H_PCT10",
            "H_PCT25", "H_MEDIAN", "H_PCT75", "H_PCT90", "A_PCT10", "A_PCT25", "A_MEDIAN",
            "A_PCT75", "A_PCT90", "ANNUAL", "HOURLY")


def oews(area, title, code, group, emp, median=50000):
    r = dict.fromkeys(OEWS_HDR)
    r.update(AREA=area, AREA_TITLE=title, NAICS="000000", OCC_CODE=code, O_GROUP=group, OCC_TITLE="BLS " + code,
             TOT_EMP=emp, A_MEDIAN=median)
    return tuple(r[h] for h in OEWS_HDR)


NATIONAL = [OEWS_HDR,
            oews("99", "U.S.", "00-0000", "total", 155000000),
            oews("99", "U.S.", "15-0000", "major", 5000000),
            oews("99", "U.S.", "15-1252", "detailed", 1650000, 133080),
            oews("99", "U.S.", "43-9022", "detailed", 40000, 49280),
            oews("99", "U.S.", "13-2011", "detailed", 1400000, 81680),
            oews("99", "U.S.", "47-2061", "detailed", 1100000, "#"),
            oews("99", "U.S.", "35-2014", "detailed", 1500000, "*")]
METROS = [OEWS_HDR,
          oews("35620", "New York-Newark-Jersey City, NY-NJ", "00-0000", "total", 9000000),
          oews("35620", "New York-Newark-Jersey City, NY-NJ", "15-1252", "detailed", 120000),
          oews("35620", "New York-Newark-Jersey City, NY-NJ", "13-2011", "detailed", 80000),
          oews("35620", "New York-Newark-Jersey City, NY-NJ", "47-2061", "detailed", 50000),
          oews("35620", "New York-Newark-Jersey City, NY-NJ", "43-9022", "detailed", "**"),
          oews("10180", "Abilene, TX", "00-0000", "total", 75000),
          oews("10180", "Abilene, TX", "15-1252", "detailed", 300)]
EP_HDR = ("2025 National Employment Matrix title", "2025 National Employment Matrix code",
          "Occupation type", "Employment, 2025", "Employment, 2035",
          "Employment distribution, percent, 2025", "Employment distribution, percent, 2035",
          "Employment change, numeric, 2025–35", "Employment change, percent, 2025–35")
EP = [("Table 1.2 Occupational projections, 2025–35",) + (None,) * 8, EP_HDR,
      ("Total, all occupations", "00-0000", "Summary", 170280.8, 176198.5, 100, 100, 5917.6, 3.5),
      ("  Software developers", "15-1252", "Line item", 1700, 1950, 1, 1, 250, 15.2),
      ("  Word processors and typists", "43-9022", "Line item", 40.4, 26.5, 0, 0, -13.9, -34.4),
      ("  Accountants and auditors", "13-2011", "Line item", 1500, 1560, 1, 1, 60, 4.0),
      ("  Construction laborers", "47-2061", "Line item", 1100, 1150, 1, 1, 50, 4.5),
      ("  Cooks, restaurant", "35-2014", "Line item", 1500, 1470, 1, 1, -30, -2.0)]


def zbytes(name, body):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, body)
    return buf.getvalue()


class Opener:
    """Serves each source by URL. Spreadsheets are marker bytes that the
    patched _xlsx_rows turns into the rows above."""

    def __init__(self, missing=(), soft404=False):
        self.missing = set(missing)
        self.soft404 = soft404
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        assert "AiLayoffTracker" in req.headers.get("User-agent", "")
        body = None
        if url == ax.STUDY_URL:
            body = STUDY_CSV.encode()
        elif url == ax.ONET_PAGE:
            body = b'<a href="/dl_files/database/db_30_1_text.zip"></a><a href="db_31_0_excel/x.xlsx">'
        elif url == ax.ONET_ZIP.format(v="31_0"):
            body = zbytes("db_31_0_text/Occupation Data.txt", ONET_TXT)
        elif url.endswith("oesm25nat.zip"):
            body = zbytes("oesm25nat/national_M2025_dl.xlsx", b"NAT")
        elif url.endswith("oesm25ma.zip"):
            body = zbytes("oesm25ma/MSA_M2025_dl.xlsx", b"MSA")
        elif url == ax.EP_XLSX:
            body = b"EP"
        elif url.endswith("oesm26nat.zip") and self.soft404:
            body = b"<!DOCTYPE html><html>Page Not Found</html>"
        if body is None or any(m in url for m in self.missing):
            raise OSError(f"HTTP Error 404: Not Found {url}")
        return _Resp(body)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_rows(body, sheet_prefix=None):
    return {b"NAT": NATIONAL, b"MSA": METROS, b"EP": EP}[body]


def pull(**kw):
    with patch.object(ax, "_xlsx_rows", fake_rows):
        return ax.pull(opener=Opener(**kw), today=date(2026, 10, 5))


class ParseTests(unittest.TestCase):
    def test_study_beta_averaged_to_soc(self):
        s = ax.parse_study(STUDY_CSV)
        self.assertEqual(s["13-2011"], 0.5)        # (0.6 + 0.4) / 2
        self.assertEqual(s["15-1252"], 0.7)
        self.assertNotIn("99-9999", s)

    def test_onet_titles_prefer_the_00_code_and_version_is_newest(self):
        t = ax.parse_onet(ONET_TXT)
        self.assertEqual(t["13-2011"], "Accountants and Auditors")
        self.assertEqual(ax.onet_version('db_30_1_text db_31_0_excel db_29_3_text'), "31_0")
        self.assertEqual(ax.onet_version(""), ax.ONET_FALLBACK)

    def test_title_falls_back_to_the_bls_title_when_onet_lacks_one(self):
        p = ax.build_payload({"13-1199": 0.6}, {}, {"13-1199": (100, 1, "Business Operations Specialists, All Other")},
                             {}, {}, {"oews_year": 2025, "ep": "2025-35"})
        self.assertEqual(p["datasets"]["occupations"][0][1], "Business Operations Specialists, All Other")

    def test_oews_detailed_only_and_wage_codes(self):
        n = ax.parse_oews_national(NATIONAL)
        self.assertNotIn("15-0000", n)
        self.assertEqual(n["15-1252"][:2], (1650000, 133080))
        self.assertEqual(n["47-2061"][1], "#")     # above the BLS top code
        self.assertIsNone(n["35-2014"][1])         # suppressed
        m = ax.parse_oews_metros(METROS)
        self.assertEqual(m["35620"]["total"], 9000000)
        self.assertNotIn("43-9022", m["35620"]["occ"])   # "**" withheld

    def test_ep_line_items_and_span(self):
        g, span = ax.parse_ep(EP)
        self.assertEqual(span, "2025-35")
        self.assertEqual(g["43-9022"], -34.4)
        self.assertNotIn("00-0000", g)


class PullTests(unittest.TestCase):
    def test_full_pull_joins_on_soc(self):
        r = pull()
        self.assertEqual(r["errors"], [])
        p = r["payload"]
        occ = {row[0]: row for row in p["datasets"]["occupations"]}
        self.assertEqual(occ["15-1252"], ["15-1252", "Software Developers", 0.7, 1650000, 133080, 15.2])
        self.assertEqual(p["versions"], {"onet": "31.0", "oews": "May 2025", "ep": "2025-35"})
        self.assertEqual(p["latest"], {"oews": "2025-05", "ep": "2025-12"})
        self.assertIn("O*NET 31.0", p["attribution"])
        self.assertIn("CC BY 4.0", p["attribution"])
        self.assertIn("MIT", p["attribution"])
        self.assertEqual(p["study"]["commit"], ax.STUDY_COMMIT)
        self.assertIn(ax.STUDY_COMMIT, ax.STUDY_URL)
        ny = [m for m in p["datasets"]["metros"] if m[0] == "35620"][0]
        self.assertEqual(ny[3], 200000)            # 120000 dev + 80000 acct; laborers not exposed
        self.assertEqual([r[1] for r in p["datasets"]["metro_occupations"] if r[0] == "35620"],
                         ["15-1252", "13-2011"])
        self.assertEqual(p["datasets"]["metros"][0][0], "35620")   # largest first

    def test_newest_oews_release_is_found_by_falling_back_a_year(self):
        # today is 2026: oesm26 404s, oesm25 is used.
        self.assertEqual(pull()["payload"]["versions"]["oews"], "May 2025")

    def test_unpublished_release_answered_with_an_html_page_falls_back(self):
        # 2026-10-05 first live run: oesm26nat.zip returned 200 + HTML, not 404.
        r = pull(soft404=True)
        self.assertEqual(r["errors"], [])
        self.assertEqual(r["payload"]["versions"]["oews"], "May 2025")

    def test_missing_source_is_an_error_not_a_silent_gap(self):
        r = pull(missing=["occupation.xlsx"])
        self.assertTrue(any(e.startswith("ep:") for e in r["errors"]))
        r = pull(missing=["GPTs-are-GPTs"])
        self.assertTrue(any(e.startswith("study:") for e in r["errors"]))


class ImportGuardTests(unittest.TestCase):
    def big(self):
        r = pull()
        occ = r["payload"]["datasets"]["occupations"]
        r["payload"]["datasets"]["occupations"] = [
            [f"11-{i:04d}", f"Job {i}", 0.3, 50000, 60000, 1.0] for i in range(600)] + occ
        r["payload"]["datasets"]["metros"] = [[str(i), f"M{i}", 1000, 100] for i in range(50)]
        return r

    def test_good_pull_stores_and_notice_says_site_stored(self):
        out = io.StringIO()
        with patch.object(ai_exposure_import, "SITE", "https://x.test/blog"), \
             patch.object(ai_exposure_import, "KEY", "k"), \
             patch.object(ai_exposure_import.ax, "pull", return_value=self.big()), \
             patch.object(ai_exposure_import.host_call, "post_json",
                          return_value={"stored": True, "source": "ai_exposure"}) as post, \
             patch.object(ai_exposure_import.host_call, "clear"), \
             patch("sys.stdout", out):
            self.assertEqual(ai_exposure_import.main(), 0)
        self.assertTrue(post.call_args[0][0].endswith("/reference-ingest/ai_exposure"))
        self.assertIn("site=stored", out.getvalue())

    def test_host_not_storing_is_a_red_run(self):
        out = io.StringIO()
        with patch.object(ai_exposure_import, "SITE", "https://x.test/blog"), \
             patch.object(ai_exposure_import, "KEY", "k"), \
             patch.object(ai_exposure_import.ax, "pull", return_value=self.big()), \
             patch.object(ai_exposure_import.host_call, "post_json", return_value={}), \
             patch("sys.stdout", out):
            self.assertEqual(ai_exposure_import.main(), 1)
        self.assertNotIn("site=stored", out.getvalue())

    def test_partial_or_thin_pulls_are_never_stored(self):
        self.assertTrue(ai_exposure_import.should_store(self.big())[0])
        self.assertFalse(ai_exposure_import.should_store(pull(missing=["oesm25ma"]))[0])
        thin = pull()   # five occupations, two metros
        ok, why = ai_exposure_import.should_store(thin)
        self.assertFalse(ok)
        self.assertIn("occupations", why)
        nogrowth = self.big()
        for r in nogrowth["payload"]["datasets"]["occupations"]:
            r[5] = None
        self.assertIn("projections", ai_exposure_import.should_store(nogrowth)[1])
        huge = self.big()
        huge["payload"]["pad"] = "x" * (ai_exposure_import.MAX_BYTES + 1)
        self.assertIn("over", ai_exposure_import.should_store(huge)[1])

    def test_archive_writes_csvs_and_never_thins(self):
        p = pull()["payload"]
        with tempfile.TemporaryDirectory() as d:
            r = ai_exposure_archive.write(d, p)
            self.assertEqual(sorted(r["written"]), ["metro_occupations-M2025.csv", "metros-M2025.csv",
                                                    "occupations-M2025.csv"])
            with open(os.path.join(d, "MANIFEST.json")) as fh:
                man = json.load(fh)
            self.assertEqual(man["study"]["licence"], "MIT")
            self.assertEqual(man["releases"]["M2025"]["ep"], "2025-35")
            thin = dict(p, datasets=dict(p["datasets"], occupations=p["datasets"]["occupations"][:1]))
            self.assertIn("occupations-M2025.csv", ai_exposure_archive.write(d, thin)["kept"])


class RegistrationTests(unittest.TestCase):
    def test_allowed_watched_and_scheduled(self):
        php = (PLUGIN / "includes/reference-data.php").read_text()
        self.assertIn("'ai_exposure' => 'alt_ref_ai_exposure'", php)
        self.assertIn("ai_exposure", rf.SPECS)
        for wf in ("ai-exposure-import.yml", "ai-exposure-archive.yml"):
            text = (ROOT / ".github/workflows" / wf).read_text()
            self.assertIn("workflow_dispatch", text)
            self.assertIn("requirements.lock", text)
        self.assertIn("ai-exposure-import.yml", (ROOT / ".github/workflows/reference-freshness.yml").read_text())
        self.assertIn("job: ai-exposure-import", (ROOT / ".github/workflows/ai-exposure-import.yml").read_text())

    def test_freshness_ceilings(self):
        doc = {"updated": "2026-10-04", "latest": {"oews": "2025-05", "ep": "2025-12"}}
        self.assertTrue(rf.verdict("ai_exposure", doc, today=date(2026, 10, 5))[0])
        # just before the May 2026 OEWS release lands (April 2027) it is still fresh
        self.assertTrue(rf.verdict("ai_exposure", dict(doc, updated="2027-04-20"), today=date(2027, 4, 25))[0])
        # a whole release cycle missed
        self.assertFalse(rf.verdict("ai_exposure", dict(doc, updated="2027-08-01"), today=date(2027, 8, 2))[0])
        # the monthly job stopped storing
        self.assertFalse(rf.verdict("ai_exposure", doc, today=date(2026, 11, 20))[0])


def stored_doc(n=24):
    occ = []
    for i in range(n):
        e = round(0.95 - i * 0.04, 3)
        occ.append([f"15-{1200 + i}", f"Occupation {i}", e, 30000 + i * 1000, 40000 + i * 100,
                    -5.0 if i % 2 else 6.5])
    occ.append(["99-0001", "Tiny job", 0.99, 900, 1, 1.0])   # under the employment floor
    occ.append(["99-0002", "Top coded", 0.01, 400000, "#", None])
    return {"source": "ai_exposure", "updated": "2026-10-05T15:00:00+00:00", "rows": 1, "attribution": "a",
            "threshold": 0.5, "versions": {"onet": "31.0", "oews": "May 2025", "ep": "2025-35"},
            "latest": {"oews": "2025-05", "ep": "2025-12"},
            "datasets": {"occupations": occ,
                         "metros": [["35620", "New York-Newark-Jersey City, NY-NJ", 9000000, 750000],
                                    ["31080", "Los Angeles-Long Beach-Anaheim, CA", 6000000, 400000]],
                         "metro_occupations": [["35620", "15-1200", 300000], ["35620", "15-1201", 200000],
                                               ["31080", "15-1202", 100000]]}}


@unittest.skipUnless(PHP, "php not installed")
class RenderTests(unittest.TestCase):
    def run_php(self, seed, mode="section"):
        proc = subprocess.run([PHP, str(HARNESS), str(PLUGIN) + "/", json.dumps(seed), mode],
                              capture_output=True, text=True, timeout=60)
        out = json.loads(proc.stdout)
        self.assertNotIn("error", out, out.get("error"))
        return out["html"]

    def test_lists_and_quadrants(self):
        b = self.run_php({"alt_ref_ai_exposure": stored_doc()}, "bundle")
        self.assertEqual(b["most"][0]["title"], "Occupation 0")
        self.assertEqual(len(b["most"]), 10)
        self.assertNotIn("Tiny job", [o["title"] for o in b["most"]])
        self.assertEqual(b["least"][0]["title"], "Top coded")
        q = b["quadrants"]
        # i even -> growing, odd -> shrinking; exposure >= 0.5 for i <= 11
        self.assertEqual(q["exposed-shrinking"]["n"], 6)
        self.assertEqual(q["exposed-growing"]["n"], 6)
        self.assertEqual(q["less-shrinking"]["n"], 6)
        self.assertEqual(q["less-growing"]["n"], 6)   # "Top coded" has no projection
        self.assertEqual(list(b["metros"]), ["35620", "31080"])

    def test_section_renders_copy_credit_asof_and_picker(self):
        html = self.run_php({"alt_ref_ai_exposure": stored_doc()})
        self.assertIn('id="ai-exposure"', html)
        self.assertIn("tasks that an AI system could speed up, per\n    Eloundou et al., &quot;GPTs are GPTs&quot;", html)
        self.assertIn("It is not a measure of jobs lost", html)
        self.assertIn(">Exposed and shrinking<", html)
        self.assertIn(">Exposed but growing<", html)
        self.assertIn('<option value="31080">Los Angeles-Long Beach-Anaheim, CA</option>', html)
        self.assertIn("<b class=\"alt-ax-big\">750,000</b>", html)
        self.assertIn("Above BLS top code", html)
        for card in ("lists", "quadrant", "metro"):
            part = html.split(f'data-ax="{card}"')[1].split("</figure>")[0]
            self.assertIn("O*NET Database by USDOL/ETA, used under CC BY 4.0", part, card)
            self.assertIn("Data: BLS employment and wages for May 2025; BLS projections 2025-35; O*NET 31.0", part, card)
            self.assertIn("Collected 5 Oct 2026.", part, card)

    def test_hidden_when_data_missing_or_malformed(self):
        for seed in ({}, {"alt_ref_ai_exposure": {"datasets": {"occupations": "garbage"}}},
                     {"alt_ref_ai_exposure": stored_doc(5)}):
            html = self.run_php(seed)
            self.assertNotIn("<section", html)
            self.assertIn("no reference data stored", html)

    def test_no_metro_data_hides_only_the_picker(self):
        doc = stored_doc()
        doc["datasets"]["metros"] = []
        html = self.run_php({"alt_ref_ai_exposure": doc})
        self.assertIn('data-ax="quadrant"', html)
        self.assertNotIn('data-ax="metro"', html)


class SurfaceTests(unittest.TestCase):
    TEXTS = {p: (PLUGIN / p).read_text() for p in (
        "includes/ai-exposure.php", "templates/partials/ai-exposure.php", "assets/ai-exposure.js")}

    def test_every_source_shown_has_a_sources_page_row_and_register_entry(self):
        sources_page = (PLUGIN / "templates/page-sources.php").read_text()
        register = (ROOT / "docs/OFFICIAL_SOURCE_CONNECTOR_RESEARCH.md").read_text()
        partial = self.TEXTS["templates/partials/ai-exposure.php"]
        # what the credit line names -> its Sources-page row
        shown = {"GPTs are GPTs": "GPTs are GPTs (AI exposure scores)",
                 "O*NET Database": "O*NET occupation data",
                 "Occupational Employment and Wage Statistics": "BLS OEWS",
                 "Employment Projections": "BLS Employment Projections"}
        for credit, row in shown.items():
            self.assertIn(credit, partial)
            self.assertIn(f"<td><b>{row}</b></td>", sources_page, row)
            self.assertIn(f"| `ai_exposure` | {row} |", register, row)
        self.assertIn("alt_shortcode_ai_exposure()", sources_page)

    def test_copy_never_says_jobs_will_be_lost_and_no_em_dashes(self):
        for name, text in self.TEXTS.items():
            self.assertNotIn("—", text, name)
            self.assertIsNone(re.search(r"\b(will (lose|be lost|disappear)|replaced by AI|caused by AI)\b",
                                        text, re.I), name)
        self.assertIn("could speed up", self.TEXTS["templates/partials/ai-exposure.php"])

    def test_css_uses_colour_tokens_only(self):
        css = (PLUGIN / "assets/layoffs.css").read_text()
        block = css[css.index("/* AI exposure by job and city"):]
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", block))

    def test_wired(self):
        boot = (PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("includes/ai-exposure.php", boot)
        self.assertIn("assets/ai-exposure.js", boot)
        self.assertIn("'alt_ai_exposure'", boot)


if __name__ == "__main__":
    unittest.main()
