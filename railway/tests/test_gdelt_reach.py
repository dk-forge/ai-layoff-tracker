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
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _DT(*a):
    return datetime(*a, tzinfo=timezone.utc)

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


class WhyTheWindowWasLost(unittest.TestCase):
    """THAT a window was abandoned and WHY are different facts.

    Both causes were measured from the first day of this module and neither
    was ever published, so the only durable record of a lost window -- the
    /source-runs history the health page and ops_status [2d] read -- could not
    tell "the server refused us" from "our own clock gave up". They call for
    opposite responses, and the second one costs money: recovering a window
    means more articles and more paid extraction.
    """

    def _run(self, **kw):
        r = gdelt_reach.Reach()
        r.note_query("broad", 40, 250)
        r.note_query("segment", None, 250, abandoned=True, **kw)
        r.note("a.de", "kept", 10)
        return r

    def _read(self, r):
        import ops_status
        lines, unmeasured = ops_status.gdelt_reach_lines(
            [{"status": "degraded", "attempted_at": "2026-09-05T22:27:58+00:00",
              "detail": r.health_detail()}])
        self.assertFalse(unmeasured)
        return " ".join(lines)

    def test_a_throttled_window_says_so(self):
        detail = self._run(rate_limited=True).health_detail()
        self.assertIn("rate_limited=1", detail)
        blob = self._read(self._run(rate_limited=True))
        self.assertIn("throttled by GDELT", blob)
        self.assertIn("Not our request timeout", blob)

    def test_an_upstream_refusal_says_so(self):
        detail = self._run(refused=True).health_detail()
        self.assertIn("refused=1", detail)
        self.assertIn("refused upstream", self._read(self._run(refused=True)))

    def test_a_lost_window_publishes_its_zeros(self):
        """Zeros are the whole point: without them a reader cannot tell a run
        that saw no throttle from a run that never counted one."""
        detail = self._run().health_detail()
        self.assertIn("rate_limited=0", detail)
        self.assertIn("refused=0", detail)
        blob = self._read(self._run())
        self.assertIn("ran out our own clock", blob)

    def test_a_clean_run_spends_no_characters_on_them(self):
        r = gdelt_reach.Reach()
        r.note_query("broad", 40, 250)
        r.note("a.de", "kept", 10)
        detail = r.health_detail()
        self.assertNotIn("rate_limited=", detail)
        self.assertNotIn("refused=", detail)

    def test_a_run_predating_the_counters_is_unknown_not_a_timeout(self):
        """The trap this whole module exists to avoid, in its newest shape: an
        old detail line carries no cause, and reading its absence as 'no
        throttle, therefore our clock' invents the very verdict a session
        would spend money on."""
        import ops_status
        legacy = ("returned=6314 queries=3 answered=1 abandoned=2 capped=0 "
                  "kept=734 dropped=5526 headline_only=54")
        lines, unmeasured = ops_status.gdelt_reach_lines(
            [{"status": "degraded", "attempted_at": "2026-09-05T22:27:58+00:00",
              "detail": legacy}])
        self.assertFalse(unmeasured)
        blob = " ".join(lines)
        self.assertIn("CAUSE UNKNOWN", blob)
        self.assertNotIn("ran out our own clock", blob)

    def test_the_cause_counters_are_nameless(self):
        gdelt_reach.assert_nameless(
            self._run(rate_limited=True, refused=True).summary())

    def test_the_collector_records_a_plain_text_refusal(self):
        """Wiring: `_query_window` classifies the body already. Before this it
        set `rate_limited` for a throttle and recorded NOTHING for any other
        refusal, so a deterministic rejection was indistinguishable from a
        timeout in the one place a human reads."""
        from sources import gdelt as G

        class _Resp:
            status_code = 200
            text = "Your query was too short or too long."

            def raise_for_status(self):
                pass

        gdelt_reach.reset()
        with mock.patch.object(G.time, "sleep"), \
                mock.patch.object(G.requests, "get", return_value=_Resp()):
            articles, rl, err = G._query_window(
                "q", _DT(2026, 9, 5), _DT(2026, 9, 6), 250, reach_label="segment")
        self.assertIsNone(articles)
        self.assertFalse(rl)
        t = gdelt_reach.current().totals()
        self.assertEqual(t["abandoned"], 1)
        self.assertEqual(t["rate_limited"], 0)
        self.assertEqual(t["refused"], 1)


if __name__ == "__main__":
    unittest.main()
