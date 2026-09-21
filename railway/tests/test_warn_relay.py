"""The WARN relay: scraped from a US address, posted from the whitelisted one.

From 2026-09-16 the import ran on a European VPS and 18 US state registers
refused it. warn_relay.py lets a US-hosted job scrape and the VPS job post.
These tests hold the two promises that make that safe: an accepted relay
REPLACES the three US scrape seams (nothing is fetched twice), and anything
less than a fresh, matching relay falls back to scraping locally, which is the
behaviour the relay replaced. No network: every seam and every host call is a
stub.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import warn_relay  # noqa: E402


def _e(state, company, jobs=50, date="2026-09-01"):
    return {"source_type": "warn", "source_name": f"{state} WARN notice",
            "verification_level": "warn", "company_name": company, "ticker": None,
            "job_count": jobs, "layoff_date": date, "industry": None,
            "country": "United States", "state": state, "roles": None,
            "excerpt": "x", "source_url": "https://example.gov/warn"}


class ScrapeAndLoad(unittest.TestCase):
    def _doc(self, **over):
        doc = {"v": warn_relay.VERSION,
               "params": {"states": ["all"], "min_employees": 0, "start_date": ""},
               "generic": [_e("OR", "A")], "custom": [_e("FL", "B")],
               "custom_unreachable": {"MA": "refused"},
               "new": {"NM": {"entries": [_e("NM", "C")], "error": None},
                       "KS": {"entries": [], "error": "boom"}},
               "scraped_at": 1_000_000}
        doc.update(over)
        return doc

    def _write(self, doc):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(doc, fh)
        self.addCleanup(os.remove, path)
        return path

    def test_scrape_carries_all_three_seams_and_their_side_channels(self):
        import sources.warn_custom as wc

        def fake_custom(states):
            wc.SOURCE_UNREACHABLE["MA"] = "refused"
            return [_e("FL", "B")]

        def ks():
            raise ValueError("boom")

        with mock.patch("sources.warn.pull_warn", return_value=[_e("OR", "A")]), \
             mock.patch.object(wc, "pull_warn_custom", side_effect=fake_custom), \
             mock.patch("sources.warn_new_states.NEW_CUSTOM_STATES",
                        {"NM": lambda: [_e("NM", "C")], "KS": ks}):
            doc = warn_relay.scrape(["all"], now=lambda: 1_000_000)
        wc.SOURCE_UNREACHABLE.clear()
        self.assertEqual(json.loads(json.dumps(doc)), self._doc())

    def test_a_fresh_matching_relay_is_accepted(self):
        doc = warn_relay.load(self._write(self._doc()), ["all"], now=lambda: 1_000_600)
        self.assertEqual(doc["generic"][0]["state"], "OR")

    def test_everything_else_falls_back_to_a_local_scrape(self):
        now = lambda: 1_000_600  # noqa: E731
        self.assertIsNone(warn_relay.load("", ["all"], now=now))
        self.assertIsNone(warn_relay.load("/nonexistent/relay.json", ["all"], now=now))
        self.assertIsNone(warn_relay.load(self._write(self._doc(v=99)), ["all"], now=now))
        self.assertIsNone(warn_relay.load(self._write(self._doc()), ["CA"], now=now))
        self.assertIsNone(warn_relay.load(self._write(self._doc()), ["all"], 50, now=now))
        self.assertIsNone(warn_relay.load(
            self._write(self._doc()), ["all"],
            now=lambda: 1_000_000 + warn_relay.MAX_AGE_SECONDS + 1))
        self.assertIsNone(warn_relay.load(self._write(self._doc(generic=None)), ["all"], now=now))
        bad = self._write(self._doc())
        with open(bad, "w") as fh:
            fh.write("<html>One moment, please</html>")
        self.assertIsNone(warn_relay.load(bad, ["all"], now=now))


class ImportUsesTheRelay(unittest.TestCase):
    """warn_import.main() with a relay must not call a single US scraper."""

    def test_relay_replaces_the_scrape_and_reaches_bulk(self):
        import warn_import as wi
        import sources.warn_custom as wc
        import sources.warn_new_states as wn
        doc = ScrapeAndLoad()._doc()
        posted = []

        def never(*a, **k):
            raise AssertionError("a US scraper ran although a relay was accepted")

        def fake_bulk(entries):
            posted.extend(entries)
            return len(entries)

        notes = []
        env = {"WARN_STATES": "all", "WARN_RELAY_FILE": "relay.json",
               "WARN_SKIP_QUEBEC": "1", "WARN_SKIP_WUP_MAZOWIECKIE": "1",
               "WP_SITE_URL": "https://example.invalid", "WP_API_KEY": "k"}
        with mock.patch.dict(os.environ, env), \
             mock.patch.object(wi.warn_relay, "load", return_value=doc), \
             mock.patch.object(wi, "pull_warn", side_effect=never), \
             mock.patch.object(wi, "pull_warn_custom", side_effect=never), \
             mock.patch.object(wn, "NEW_CUSTOM_STATES", {"NM": never, "KS": never}), \
             mock.patch.object(wi, "report_source_health",
                               side_effect=lambda *a, **k: notes.append(a) or True), \
             mock.patch.object(wi, "post_bulk", side_effect=fake_bulk), \
             mock.patch.object(wi, "db_frontier_dates", return_value={}), \
             mock.patch.object(wi, "load_state_baselines", return_value={}), \
             mock.patch.object(wi, "save_state_baselines"), \
             mock.patch.object(wi, "assess_state_freshness", return_value=({}, [], [])), \
             mock.patch.object(wi.source_freshness, "save_ledger", create=True), \
             mock.patch.object(wi.source_alert, "announce", create=True, return_value=None), \
             mock.patch.object(wi, "requests"):
            try:
                wi.main()
            except SystemExit as exc:
                self.assertIn(exc.code, (0, None))
        self.assertEqual(sorted(e["company_name"] for e in posted), ["A", "B", "C"])
        self.assertEqual(wc.SOURCE_UNREACHABLE.get("MA"), "refused")
        wc.SOURCE_UNREACHABLE.clear()
        # KS raised in the relay: it must still read as an ERRORED new-state.
        joined = " ".join(str(n) for n in notes)
        self.assertIn("KS", joined)


if __name__ == "__main__":
    unittest.main()
