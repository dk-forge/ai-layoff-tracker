"""The reach ledger must MEASURE and must not LEAK.

Two properties, and the second is the one that needs a mechanism rather than a
reviewer:

  1. The accounting is complete and honest. Every candidate lands in exactly
     one reason, an abandoned window is not a zero, and a query that returns
     exactly `maxrecords` is reported as capped.

  2. Nothing published can spell a name. The guard is a whitelist, so the test
     POISONS a run with a headline, a URL and an employer name and proves the
     publish paths refuse rather than sanitise.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_reach  # noqa: E402


class CountryAttribution(unittest.TestCase):
    def test_cctld_is_the_country(self):
        self.assertEqual(gdelt_reach.country_of("cumhuriyet.com.tr"), "tr")
        self.assertEqual(gdelt_reach.country_of("www.example.co.uk"), "uk")
        self.assertEqual(gdelt_reach.country_of("SomeSite.AE"), "ae")

    def test_generic_tld_is_unknown_not_guessed(self):
        # dailysabah.com is Turkish. A domain alone cannot say so, and
        # inventing a map would make a guess look like an attribution.
        self.assertEqual(gdelt_reach.country_of("dailysabah.com"), "zz")
        self.assertEqual(gdelt_reach.country_of(""), "zz")
        self.assertEqual(gdelt_reach.country_of(None), "zz")

    def test_vanity_cctld_is_not_a_country(self):
        self.assertEqual(gdelt_reach.country_of("news.io"), "zz")
        self.assertEqual(gdelt_reach.country_of("thing.tv"), "zz")
        # India's ccTLD is a real signal and is deliberately kept.
        self.assertEqual(gdelt_reach.country_of("outlet.co.in"), "in")


class QueryAccounting(unittest.TestCase):
    def test_exactly_maxrecords_is_capped(self):
        r = gdelt_reach.Reach()
        r.note_query("broad", 250, 250)
        self.assertTrue(r.queries[0]["capped"])
        self.assertEqual(r.totals()["capped"], 1)

    def test_below_maxrecords_is_not_capped(self):
        r = gdelt_reach.Reach()
        r.note_query("broad", 249, 250)
        self.assertFalse(r.queries[0]["capped"])
        self.assertEqual(r.totals()["capped"], 0)

    def test_abandoned_is_not_a_zero(self):
        """The whole point. `returned=0` is 'GDELT answered, nothing there';
        abandoned is 'we never found out'. A totals() that added a zero to
        `returned` would let a lost window read as a quiet day."""
        r = gdelt_reach.Reach()
        r.note_query("broad", None, 250, abandoned=True, rate_limited=True)
        t = r.totals()
        self.assertEqual(t["abandoned"], 1)
        self.assertEqual(t["answered"], 0)
        self.assertEqual(t["returned"], 0)
        self.assertEqual(t["rate_limited"], 1)
        # ...and an abandoned window is never counted as capped.
        self.assertEqual(t["capped"], 0)

    def test_unknown_query_label_refused(self):
        r = gdelt_reach.Reach()
        with self.assertRaises(gdelt_reach.LeakGuard):
            r.note_query("the-broad-layoffs-query", 10, 250)


class CandidateAccounting(unittest.TestCase):
    def test_reasons_partition_the_candidates(self):
        r = gdelt_reach.Reach()
        r.note("a.com.tr", "not_allowlisted", 40)
        r.note("b.ae", "not_allowlisted", 5)
        r.note("c.co.uk", "kept", 3)
        r.note("c.co.uk", "duplicate_url", 2)
        t = r.totals()
        self.assertEqual(t["candidates"], 50)
        self.assertEqual(t["kept"], 3)
        self.assertEqual(t["dropped"], 47)
        self.assertEqual(r.summary()["by_country"]["tr"]["not_allowlisted"], 40)

    def test_unknown_reason_refused(self):
        r = gdelt_reach.Reach()
        with self.assertRaises(gdelt_reach.LeakGuard):
            r.note("a.com", "paywalled")

    def test_generic_tld_share_is_reported_not_hidden(self):
        r = gdelt_reach.Reach()
        r.note("dailysabah.com", "kept")
        self.assertEqual(r.totals()["unknown_country"], 1)


class LeakGuardIsAMechanism(unittest.TestCase):
    """Poison the ledger and prove the publish paths REFUSE."""

    def _poisoned(self):
        r = gdelt_reach.Reach()
        r.note_query("broad", 250, 250)
        r.note("cumhuriyet.com.tr", "not_allowlisted", 9)
        return r

    def test_a_country_code_is_all_a_country_can_be(self):
        r = self._poisoned()
        for value in r.summary()["by_country"]:
            self.assertRegex(value, r"^[a-z]{2}$")

    def test_free_text_smuggled_into_a_country_key_is_refused(self):
        r = self._poisoned()
        r._by_country["Bosch Bursa"] = {"kept": 1}
        with self.assertRaises(gdelt_reach.LeakGuard):
            r.summary()

    def test_free_text_smuggled_into_a_query_label_is_refused(self):
        r = self._poisoned()
        r.queries[0]["label"] = "TPI Composites Izmir"
        with self.assertRaises(gdelt_reach.LeakGuard):
            r.summary()

    def test_note_cc_launders_free_text_to_unknown(self):
        """A downstream caller hands over whatever it holds. Anything that is
        not a two-letter code becomes `zz` rather than reaching the ledger."""
        r = gdelt_reach.Reach()
        r.note_cc("https://example.com/an-article-headline", "gate_no")
        self.assertEqual(list(r.summary()["by_country"]), ["zz"])

    def test_published_lines_carry_no_free_text(self):
        r = self._poisoned()
        blob = " ".join(r.report_lines()) + " " + r.health_detail()
        for name in ("cumhuriyet", "Bosch", "Bursa", "http", ".com", ".tr"):
            self.assertNotIn(name, blob)


class HealthDetailIsABudget(unittest.TestCase):
    """The store truncates `detail` at 240 characters, so the line must SPEND."""

    def _big(self):
        r = gdelt_reach.Reach()
        for label, n in (("broad", 250), ("segment", 250), ("theme", 12)):
            r.note_query(label, n, 250)
        r.note_query("euro", None, 250, abandoned=True, rate_limited=True)
        for i in range(60):
            cc = f"{chr(97 + i // 26)}{chr(97 + i % 26)}"
            r.note_cc(cc, "not_allowlisted", 60 - i)
            r.note_cc(cc, "kept", i % 3)
        return r

    def test_never_exceeds_the_store_limit(self):
        self.assertLessEqual(len(self._big().health_detail()), 240)

    def test_headline_facts_survive_a_tight_budget(self):
        line = self._big().health_detail(budget=80)
        self.assertLessEqual(len(line), 80)
        for fact in ("returned=512", "queries=4", "answered=3",
                     "abandoned=1", "capped=2"):
            self.assertIn(fact, line)

    def test_worst_dropped_country_is_first_in_the_tail(self):
        line = self._big().health_detail()
        tail = line.split("; ")[-1]
        self.assertTrue(tail.startswith("aa "), tail)

    def test_the_detail_is_nameless(self):
        gdelt_reach.assert_nameless(self._big().summary())


class OpsStatusReadsItBack(unittest.TestCase):
    def test_parses_its_own_health_detail(self):
        """The producer and the reader must agree, or the dashboard invents a
        number. Parse the real emitted line rather than a hand-typed one."""
        import ops_status
        r = gdelt_reach.Reach()
        r.note_query("broad", 250, 250)
        r.note_query("euro", None, 250, abandoned=True)
        r.note("a.tr", "not_allowlisted", 200)
        r.note("b.de", "kept", 50)
        runs = [{"status": "ok", "attempted_at": "2026-08-20T22:13:36+00:00",
                 "detail": r.health_detail()}]
        lines, unmeasured = ops_status.gdelt_reach_lines(runs)
        self.assertFalse(unmeasured)
        blob = " ".join(lines)
        self.assertIn("CAP BINDING", blob)
        self.assertIn("WINDOW LOST", blob)
        self.assertIn("kept 50", blob)
        self.assertIn("dropped 200", blob)

    def test_no_reach_facts_is_unknown_not_a_pass(self):
        import ops_status
        lines, unmeasured = ops_status.gdelt_reach_lines(
            [{"status": "ok", "detail": ""}, {"status": "running", "detail": "x"}])
        self.assertTrue(unmeasured)
        self.assertIn("UNKNOWN", lines[0])


if __name__ == "__main__":
    unittest.main()
