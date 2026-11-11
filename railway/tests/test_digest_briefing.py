"""The weekly briefing (includes/digest-briefing.php) and its pre-send checks.

Owner request 2026-11-02: trustworthiness first. Each test below is one of the
defects the Week 44 (Oct 26 - Nov 1, 2026) edition carried, or one of the
pre-send checks that must stop a contradiction from being sent:

  - "5,888 from state WARN filings" over Canadian and Polish rows: the source
    class must follow the country, not only source_type `warn`.
  - region rows (unknown country included) must sum to the worldwide figure,
    with US under North America and UK / Netherlands under Europe.
  - every tracker link names the same window and the effective basis.
  - a week above 3x the 8-week median gets a note; no week-over-week %.
  - a claim whose numbers do not reconcile is HELD (omitted + logged).

Drives the real composer through tests/fixtures/digest_compose_harness.php.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
import html as html_mod

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
BRIEFING = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                        "includes", "digest-briefing.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

FROM, TO = "2026-10-26", "2026-11-01"
WEEK_FROMS = ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28",
              "2026-10-05", "2026-10-12", "2026-10-19"]
WEEK_JOBS = [7739, 14084, 71387, 12698, 4474, 4760, 2984]


def tup(label, verified, all_jobs=None):
    return [label, verified if all_jobs is None else all_jobs, 0, None, verified, 0]


def row(i, company, jobs, country="United States", state="CA",
        source_type="warn", source_name="CA WARN notice", event=None, announced=False):
    return {"id": i, "event_id": event if event is not None else 1000 + i,
            "company_name": company, "job_count": jobs, "layoff_date": "2026-10-30",
            "country": country, "state": state, "source_type": source_type,
            "source_name": source_name, "tier": "reported" if announced else "verified",
            "announced": announced, "source_url": "https://edd.ca.gov/warn.xlsx",
            "industry": "Manufacturing"}


def base_fixture():
    rows = [
        row(1, "Crothall Healthcare", 545, state="VA", source_name="VA WARN notice"),
        row(2, "Portland Truck Manufacturing Facility", 387, state="OR",
            source_name="OR WARN notice"),
        row(3, "Venmar Ventilation ULC", 175, country="Canada", state="",
            source_name="Quebec collective dismissal (MESS)"),
        row(4, "Microsoft Sp. z o.o.", 53, country="Poland", state="",
            source_name="Mazowieckie collective-dismissal register (WUP Warszawa)"),
        row(5, "Acme UK Ltd", 40, country="United Kingdom", state="",
            source_type="news", source_name="Named report"),
        row(6, "Unknown Place Co", 20, country="", state=""),
        row(7, "Aryzta", 250, country="Germany", state="", source_type="erm",
            source_name="European Restructuring Monitor (Eurofound)", announced=True),
    ]
    ver = sum(r["job_count"] for r in rows if not r["announced"])
    layoff = {
        "totals": {"jobs": ver + 250, "entries": 7, "announced_jobs": 250,
                   "announced_entries": 1, "ai_verified_jobs": 0, "companies": 7},
        "map_countries": [tup("United States", 932), tup("Canada", 175),
                          tup("Poland", 53), tup("United Kingdom", 40),
                          tup("Germany", 0, 250)],
        "top_countries": [],
        "top_industries": [tup("Manufacturing", 1000), tup("Healthcare & Pharma", 100)],
        "leaders": [{"id": 2, "company_name": "Portland Truck Manufacturing Facility",
                     "job_count": 387, "state": "OR", "country": "United States",
                     "location": "Portland", "announced": False}],
        "concentration": {"largest_row_company": "Crothall Healthcare", "largest_row_jobs": 545},
    }
    weeks = {}
    for f, j in zip(WEEK_FROMS, WEEK_JOBS):
        weeks[f] = {"totals": {"jobs": j, "announced_jobs": 0},
                    "concentration": {"largest_row_company": "Dax-Konzerne" if j == 71387 else "X",
                                      "largest_row_jobs": 46000 if j == 71387 else 10}}
    return {
        "from": FROM, "to": TO, "freq": "weekly", "compose": "layoff",
        "options": {"alt_last_write": 1793597760,
                    "alt_digest_briefing_tiers": "daily,weekly,monthly"},
        "layoff": layoff, "layoff_rows": rows, "weeks": weeks,
        "ytd": {"totals": {"jobs": 700000, "announced_jobs": 526, "ai_verified_jobs": 69361},
                "map_countries": [tup("United States", 600000)]},
    }


def compose(fx):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as h:
        json.dump(fx, h)
    try:
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, h.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(h.name)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1500])
    out = json.loads(run.stdout)
    out["stderr"] = run.stderr
    return out


@unittest.skipIf(PHP is None, "php is not on PATH.")
class Briefing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(base_fixture())
        cls.text = cls.out["text"]
        cls.html = cls.out["html"]

    def test_all_checks_pass_on_a_consistent_week(self):
        self.assertEqual(self.out["held"], [])
        for k, v in self.out["checks"].items():
            self.assertIn(v, ("PASS", "NOTE"), k)

    def test_non_us_notices_are_not_called_state_warn(self):
        notes = [l for l in self.text.splitlines() if "Sources, verified only" in l][0]
        self.assertIn("932 from US state WARN notices", notes)
        self.assertIn("20 from government notices with no country recorded", notes)
        self.assertIn("government collective-dismissal notices outside the US (Canada 175, Poland 53)", notes)
        self.assertNotIn("state WARN filings", self.text)

    def test_region_rows_sum_to_worldwide_with_unknowns(self):
        block = self.text.split("Verified job cuts by region:")[1].split("Provisional")[0]
        rows = re.findall(r"^\s{4}(\S.*): ([\d,]+)$", block, re.M)
        self.assertEqual([r[0].split(" (")[0] for r in rows],
                         ["North America", "Europe", "Not recorded"])
        total = sum(int(n.replace(",", "")) for _, n in rows)
        self.assertEqual(total, 1220)
        self.assertIn("North America (US 932 · rest of North America 175): 1,107", block)
        self.assertIn("Europe (UK 40 · other Europe 53): 93", block)
        self.assertIn("Not recorded: 20", block)
        self.assertNotIn("Asia-Pacific", block)

    def test_every_tracker_link_names_window_and_basis(self):
        urls = [html_mod.unescape(u) for u in re.findall(r'href="([^"]+)"', self.html)]
        urls += re.findall(r"https://\S+", self.text)
        tracker = [u for u in urls if "/ai-layoff-tracker/?" in u]
        self.assertTrue(tracker)
        for u in tracker:
            q = parse_qs(urlparse(u).query, keep_blank_values=True)
            self.assertEqual(q.get("date_basis"), ["effective"], u)
            self.assertEqual(q.get("from"), [FROM], u)
            self.assertEqual(q.get("to"), [TO], u)

    def test_outlier_week_is_noted_and_no_percent_change(self):
        self.assertIn("The Sep 21-27 week was unusually high (71,387)", self.text)
        self.assertIn("Dax-Konzerne at 46,000", self.text)
        self.assertNotIn("vs last week", self.text)
        self.assertNotRegex(self.text, r"[▲▼]")

    def test_trend_is_newest_first_with_ranges_and_marks_provisional(self):
        lines = self.text.split("Last 8 weeks\n")[1].split("The average leaves")[0].splitlines()
        lines.append("")
        self.assertTrue(lines[1].startswith("Oct 26 - Nov 1 (still being counted) 1,220"), lines[1])
        self.assertTrue(lines[-2].startswith("Sep 7-13 7,739"), lines[-2])
        self.assertIn("The average leaves out the current week", self.text)

    def test_facility_name_is_labelled_not_renamed(self):
        self.assertIn("Portland Truck Manufacturing Facility", self.html)
        self.assertIn("Facility named in the filing", self.html)

    def test_required_blocks_survive(self):
        for needle in ("Three things worth knowing", "AI attribution watch",
                       "does not mean AI had no effect", "Snapshot: database last changed",
                       "Cite: AI Layoff Tracker", "/editions/weekly/2026-W44/",
                       "/ai-layoff-tracker/methodology/", "Submit a correction",
                       "Biggest cuts this week (Oct 26 - Nov 1)", "Around the world"):
            self.assertIn(needle, self.text + self.html, needle)
        self.assertNotIn("By US state", self.text)

    def test_subject_metric_never_carries_ai_on_a_zero_week(self):
        self.assertNotIn("AI", self.out["metric"])
        self.assertTrue(self.out["metric"].startswith("1,220 verified job cuts"))
        self.assertTrue(self.out["preheader"])

    def test_house_style(self):
        body = self.text + self.html
        self.assertNotRegex(body, "[\u2013\u2014]")
        for word in ("bl" + "ind", "hon" + "est", "halluc" + "inat"):
            self.assertNotIn(word, body.lower())


@unittest.skipIf(PHP is None, "php is not on PATH.")
class HoldsAContradiction(unittest.TestCase):

    def test_rows_that_do_not_reconcile_hold_the_source_line(self):
        fx = base_fixture()
        fx["layoff_rows"] = fx["layoff_rows"][1:]
        out = compose(fx)
        self.assertEqual(out["checks"]["rows_reconcile"], "FAIL")
        self.assertNotIn("Sources, verified only", out["text"])
        self.assertTrue(any(h["claim"] == "sources" for h in out["held"]))
        self.assertIn("[alt-briefing] held sources", out["stderr"])

    def test_regions_that_do_not_reconcile_are_held(self):
        fx = base_fixture()
        fx["layoff"]["map_countries"].append(tup("France", 5000))
        out = compose(fx)
        self.assertEqual(out["checks"]["regions_reconcile"], "FAIL")
        self.assertNotIn("By region:", out["text"])

    def test_same_event_twice_is_held_but_warn_lookalikes_are_not(self):
        fx = base_fixture()
        dup = dict(fx["layoff_rows"][0], id=99)
        alike = dict(fx["layoff_rows"][0], id=98, event_id=5555)
        fx["layoff_rows"] += [dup, alike]
        fx["layoff"]["totals"]["jobs"] += 545 * 2
        fx["layoff"]["map_countries"][0][4] += 545 * 2
        out = compose(fx)
        self.assertEqual(out["checks"]["duplicates"], "FAIL")
        held = [h["claim"] for h in out["held"]]
        self.assertIn("row 99", held)
        self.assertNotIn("row 98", held)

    def test_a_missing_week_withholds_the_trend(self):
        fx = base_fixture()
        fx["weeks"]["2026-09-14"] = {}
        out = compose(fx)
        self.assertNotIn("Last 8 weeks", out["text"])


@unittest.skipIf(PHP is None, "php is not on PATH.")
class Wiring(unittest.TestCase):

    def test_the_switch_falls_back_to_the_old_composer(self):
        fx = base_fixture()
        fx["options"]["alt_digest_briefing_tiers"] = "none"
        out = compose(fx)
        self.assertNotIn("Three things worth knowing", out["text"])

    def test_production_default_is_all_three_tiers(self):
        src = open(BRIEFING, encoding="utf-8").read()
        m = re.search(r"function alt_briefing_default_tiers\(\) \{\s*return '([^']+)';", src)
        self.assertEqual(m.group(1), "daily,weekly,monthly")
        self.assertIn("get_option('alt_digest_briefing_tiers', alt_briefing_default_tiers())", src)

    def test_daily_and_monthly_use_the_briefing(self):
        for freq, frm, to in (("daily", "2026-11-01", "2026-11-01"),
                              ("monthly", "2026-10-01", "2026-10-31")):
            fx = base_fixture()
            fx.update({"freq": freq, "from": frm, "to": to})
            out = compose(fx)
            self.assertIn(freq + " briefing", out["text"], freq)

    def test_subscribe_loads_the_briefing(self):
        src = open(SUBSCRIBE, encoding="utf-8").read()
        self.assertIn("digest-briefing.php", src)
        self.assertTrue(os.path.isfile(BRIEFING))


if __name__ == "__main__":
    unittest.main()
