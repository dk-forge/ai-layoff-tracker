"""FRED trend, Census QWI hires-vs-separations and the early-warning view.

Renders the REAL includes/labour-trends.php, includes/early-warning.php and
their partials through tests/fixtures/labour_context_harness.php (WordPress
stubs, a fake $wpdb for the tracker's WARN counts, no network, no DB).

Pinned:
  * the status rule exactly as documented in early-warning.php: latest 3
    months vs the 12 before (monthly), latest quarter vs a year earlier (QWI),
    +/-5% thresholds, at least two judged official series, majority with at
    least two;
  * the tracker's own WARN counts are drawn but NEVER move the status;
  * FRED, QWI and early-warning panels hide when their data is missing, carry
    a source credit and an as-of line, and the QWI copy says separations are
    all-cause;
  * every source a panel shows has a row on the Sources page;
  * no copy claims AI caused anything.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
HARNESS = Path(__file__).resolve().parent / "fixtures/labour_context_harness.php"
PHP = shutil.which("php")
SOURCES_PAGE = (PLUGIN / "templates/page-sources.php").read_text()
TEXTS = {p: (PLUGIN / p).read_text() for p in (
    "includes/labour-trends.php", "includes/early-warning.php",
    "templates/partials/labour-trends.php", "templates/partials/early-warning.php")}
JS = (PLUGIN / "assets/labour-context.js").read_text()


def months(start_y, start_m, n):
    out, y, m = [], start_y, start_m
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


# 2025-01 .. 2026-09: 21 months. Flat 100 for 18 months, then 3 months at 120
# (a +20% move, "rising"), so the rule sees last 3 = 120 vs the 12 before = 100.
MONTHS = months(2025, 1, 21)


def rising(base, n=21, last=3, factor=1.2):
    return [base] * (n - last) + [base * factor] * last


def fred_doc(claims=None):
    claims = claims or rising(200000)
    rows = []
    for ym, v in zip(MONTHS, claims):
        for d in ("07", "14", "21"):
            rows.append(["ICSA", f"{ym}-{d}", v, "Initial jobless claims", "claims", "weekly"])
    for ym in MONTHS:
        rows.append(["UNRATE", f"{ym}-01", 4.2, "Unemployment rate", "unemployment", "monthly"])
        rows.append(["USINFO", f"{ym}-01", 2900.0, "All employees, information sector", "employment", "monthly"])
    return {"source": "fred_labour", "updated": "2026-10-04T12:00:00+00:00",
            "latest": {"weekly": "2026-09", "monthly": "2026-09"}, "rows": len(rows), "attribution": "f",
            "fields": ["series_id", "date", "value", "label", "category", "frequency"],
            "series": {"ICSA": {"label": "Initial jobless claims", "units": "number"}},
            "datasets": {"observations": rows}}


def bls_doc(info=None, total=None):
    def series(label, vals):
        return {"measure": "layoffs_discharges", "unit": "thousands", "dim": "industry", "label": label,
                "points": [[ym, v, ""] for ym, v in zip(MONTHS, vals)]}
    return {"source": "bls_jolts_cps", "updated": "2026-10-04T12:00:00+00:00",
            "latest": {"jolts": "2026-09", "cps": "2026-09"}, "rows": 2, "attribution": "x",
            "datasets": {"jolts": {
                "JTS510000000000000LDL": series("Information", info or rising(30)),
                "JTS000000000000000LDL": series("Total nonfarm", total or [1700] * 21),
            }, "cps": {}}}


QUARTERS = ["2024-Q4", "2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]


def qwi_doc(sep_latest=1100, sep_year_before=1000):
    rows = []
    for q in QUARTERS:
        for st in ("06", "36"):
            for ind in ("51", "31-33"):
                sep = sep_latest if q == "2026-Q3" else sep_year_before if q == "2025-Q3" else 1000
                rows.append(["by_sector", st, q, ind, "0", "A00", "E0", "A0", "A0", 900, sep, 50000])
    sex = [["sex", "06", "2026-Q3", "00", g, "A00", "E0", "A0", "A0", 500, 400, 30000] for g in ("1", "2")]
    return {"source": "census_qwi", "updated": "2026-10-05T00:00:00+00:00", "latest": {"quarterly": "2026-09"},
            "latest_quarter": "2026-Q3", "rows": len(rows) + 2, "attribution": "q",
            "fields": ["breakdown", "state", "quarter", "industry", "sex", "agegrp", "education", "race",
                       "ethnicity", "HirA", "Sep", "EmpEnd"],
            "codes": {"sex": {"0": "All", "1": "Male", "2": "Female"}},
            "datasets": {"by_sector": rows, "sex": sex}}


def warn_rows(n=5):
    return [{"ym": ym, "industry": "Technology", "n": n} for ym in MONTHS]


def opts(**kw):
    o = {"alt_ref_fred_labour": fred_doc(), "alt_ref_bls_jolts_cps": bls_doc(),
         "alt_ref_census_qwi": qwi_doc(), "__warn": warn_rows()}
    o.update(kw)
    return {k: v for k, v in o.items() if v is not None}


@unittest.skipUnless(PHP, "php not installed")
class Php(unittest.TestCase):
    def run_php(self, seed, *args):
        proc = subprocess.run([PHP, str(HARNESS), str(PLUGIN) + "/", json.dumps(seed), *args],
                              capture_output=True, text=True, timeout=60)
        out = json.loads(proc.stdout)
        self.assertNotIn("error", out, out.get("error"))
        return out["html"]

    def bundle(self, seed):
        # "now" in October 2026, so the window ends at 2026-09.
        return self.run_php(seed, "ew", "2026-10-15")


class StatusRuleTests(Php):
    def test_rising_official_series_read_heating_up(self):
        info = self.bundle(opts())["industries"]["information"]
        self.assertEqual(info["status"], "heating")
        self.assertEqual(info["status_label"], "Heating up")
        self.assertTrue(any("+20%" in r for r in info["reasons"]), info["reasons"])
        self.assertTrue(any("QWI separations +10%" in r for r in info["reasons"]), info["reasons"])

    def test_falling_series_read_cooling(self):
        seed = opts(alt_ref_fred_labour=fred_doc(rising(200000, factor=0.8)),
                    alt_ref_bls_jolts_cps=bls_doc(info=rising(30, factor=0.8)),
                    alt_ref_census_qwi=qwi_doc(sep_latest=900))
        self.assertEqual(self.bundle(seed)["industries"]["information"]["status"], "cooling")

    def test_small_moves_read_stable(self):
        seed = opts(alt_ref_fred_labour=fred_doc(rising(200000, factor=1.04)),
                    alt_ref_bls_jolts_cps=bls_doc(info=rising(30, factor=0.97)),
                    alt_ref_census_qwi=qwi_doc(sep_latest=1049))
        self.assertEqual(self.bundle(seed)["industries"]["information"]["status"], "stable")

    def test_one_rising_one_falling_is_stable_not_a_verdict(self):
        seed = opts(alt_ref_fred_labour=fred_doc(rising(200000, factor=1.3)),
                    alt_ref_bls_jolts_cps=bls_doc(info=rising(30, factor=0.7)),
                    alt_ref_census_qwi=qwi_doc(sep_latest=1000))
        self.assertEqual(self.bundle(seed)["industries"]["information"]["status"], "stable")

    def test_threshold_is_five_percent_inclusive(self):
        seed = opts(alt_ref_fred_labour=fred_doc(rising(200000, factor=1.05)),
                    alt_ref_bls_jolts_cps=bls_doc(info=rising(40, factor=1.05)),
                    alt_ref_census_qwi=None)
        self.assertEqual(self.bundle(seed)["industries"]["information"]["status"], "heating")

    def test_fewer_than_two_judged_series_gives_no_label(self):
        # Only 10 months of claims (too short), no JOLTS for the industry, QWI judged: one series.
        short = fred_doc()
        short["datasets"]["observations"] = [r for r in short["datasets"]["observations"] if r[1] >= "2025-12"]
        seed = opts(alt_ref_fred_labour=short, alt_ref_bls_jolts_cps=None)
        info = self.bundle(seed)["industries"]["information"]
        self.assertIsNone(info["status"])
        self.assertEqual(info["status_label"], "")

    def test_tracker_warn_counts_never_move_the_status(self):
        calm = opts(alt_ref_fred_labour=fred_doc([200000] * 21), alt_ref_bls_jolts_cps=bls_doc(info=[30] * 21),
                    alt_ref_census_qwi=qwi_doc(sep_latest=1000), __warn=warn_rows(1))
        surge = dict(calm, __warn=[{"ym": ym, "industry": "Technology", "n": 1 if ym < "2026-07" else 500}
                                   for ym in MONTHS])
        a = self.bundle(calm)["industries"]["information"]
        b = self.bundle(surge)["industries"]["information"]
        self.assertEqual(a["status"], "stable")
        self.assertEqual(b["status"], "stable")
        self.assertEqual(a["reasons"], b["reasons"])
        tracker = [s for s in b["series"] if s["kind"] == "tracker"]
        self.assertEqual(len(tracker), 1)
        self.assertEqual(tracker[0]["raw"][-1], 500)

    def test_timeline_is_aligned_and_indexed(self):
        b = self.bundle(opts())
        self.assertEqual(len(b["months"]), 36)
        self.assertEqual(b["months"][-1], "2026-09")
        for s in b["industries"]["information"]["series"]:
            self.assertEqual(len(s["raw"]), 36)
            self.assertEqual(len(s["index"]), 36)
        qwi = [s for s in b["industries"]["information"]["series"] if s["name"].startswith("QWI")][0]
        self.assertEqual(qwi["raw"][b["months"].index("2026-09")], 2200)  # 2 states summed, quarter end month
        self.assertIsNone(qwi["raw"][b["months"].index("2026-08")])
        jolts = [s for s in b["industries"]["information"]["series"] if s["name"].startswith("JOLTS")][0]
        self.assertEqual(jolts["raw"][-1], 36000)  # thousands -> people

    def test_no_official_data_means_no_view(self):
        self.assertIsNone(self.bundle({"__warn": warn_rows()}))


class RenderTests(Php):
    def test_fred_and_qwi_panels_render_with_credit_and_asof(self):
        html = self.run_php(opts(), "section")
        self.assertIn('data-lc="fred"', html)
        self.assertIn('<option value="ICSA">Weekly initial jobless claims</option>', html)
        self.assertIn('<option value="USINFO">', html)
        self.assertNotIn('<option value="PAYEMS">', html)  # not stored, not offered
        self.assertIn("Source: Federal Reserve Bank of St. Louis, FRED", html)
        self.assertIn("Monthly series through September 2026", html)
        self.assertIn('data-lc="qwi"', html)
        self.assertIn(">California<", html)
        self.assertIn(">New York<", html)
        self.assertIn('<option value="31-33">Manufacturing</option>', html)
        self.assertIn('<option value="sex">Sex</option>', html)
        self.assertIn("<strong>Separations are all-cause</strong>", html)
        self.assertIn("Source: U.S. Census Bureau, LEHD Quarterly Workforce Indicators", html)
        self.assertIn("Data through Q3 2026", html)

    def test_early_warning_renders_status_sources_and_asof(self):
        html = self.run_php(opts(), "section")
        self.assertIn('id="early-warning"', html)
        self.assertIn('data-status="heating"', html)  # "All industries": claims +20%, QWI +10%
        self.assertIn(">Heating up<", html)
        self.assertIn('<option value="information">Information and technology</option>', html)
        for credit in ("our WARN notice records", "FRED", "JOLTS", "Quarterly Workforce Indicators"):
            self.assertIn(credit, html.split('id="early-warning"')[1])
        self.assertIn("claims through September 2026", html)
        self.assertIn("QWI through Q3 2026", html)
        self.assertIn("our WARN notices\n            never do", html)
        self.assertIn("does not say anything about AI", html)
        data = json.loads(re.search(r'data-ew="([^"]*)"', html).group(1).replace("&quot;", '"')
                          .replace("&#039;", "'").replace("&amp;", "&"))
        self.assertIn("information", data["industries"])

    def test_missing_sources_hide_their_panels_without_error(self):
        html = self.run_php(opts(alt_ref_fred_labour=None), "section")
        self.assertNotIn('data-lc="fred"', html)
        self.assertIn('data-lc="qwi"', html)
        html = self.run_php(opts(alt_ref_census_qwi={"datasets": {"by_sector": "garbage"}}), "section")
        self.assertNotIn('data-lc="qwi"', html)
        self.assertIn('data-lc="fred"', html)
        html = self.run_php({"__warn": warn_rows()}, "section")
        self.assertNotIn("<section", html)
        self.assertNotIn("early-warning", html)

    def test_only_fred_still_renders_the_section(self):
        html = self.run_php({"alt_ref_fred_labour": fred_doc()}, "section")
        self.assertIn('data-lc="fred"', html)
        self.assertNotIn('data-lc="qwi"', html)


class SurfaceTests(unittest.TestCase):
    def test_every_shown_source_has_a_sources_page_row(self):
        # panel -> the Sources-page row that must exist for what it shows
        required = {
            "jolts": ["BLS JOLTS &amp; CPS"], "cps": ["BLS JOLTS &amp; CPS"],
            "oecd": ["OECD unemployment"], "fred": ["FRED labour series"], "qwi": ["Census QWI"],
            "ew": ["State WARN notices", "FRED labour series", "BLS JOLTS &amp; CPS", "Census QWI"],
        }
        partials = (PLUGIN / "templates/partials/labour-context.php").read_text() + TEXTS[
            "templates/partials/labour-trends.php"] + TEXTS["templates/partials/early-warning.php"]
        shown = set(re.findall(r'data-lc="([a-z]+)"', partials))
        self.assertEqual(shown, set(required), "a new panel needs its Sources-page rows listed here")
        for panel, rows in required.items():
            for row in rows:
                self.assertIn(f"<td><b>{row}</b></td>", SOURCES_PAGE, f"{panel} shows {row}")

    def test_no_causal_ai_claims_or_em_dashes(self):
        for name, text in TEXTS.items():
            self.assertNotIn("—", text, name)
            self.assertIsNone(re.search(r"\b(due to|because of|caused by|driven by) AI\b", text, re.I), name)
        self.assertIn("does not say anything about AI", TEXTS["templates/partials/early-warning.php"])

    def test_charts_wired_and_token_coloured(self):
        for fn in ("drawFred", "drawQwi", "drawEw"):
            self.assertIn(fn, JS)
        self.assertIn("var TOKS = [", JS)
        boot = (PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("'labour-trends.php', 'early-warning.php'", boot)


if __name__ == "__main__":
    unittest.main()
