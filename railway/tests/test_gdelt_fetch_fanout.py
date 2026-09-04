"""The fetch fan-out is bounded, and ONLY where the surplus is discarded.

Run 33860668098 (2026-09-04) was killed by `timeout-minutes: 45`. The trend
across the eight runs before it ruled out a mis-sized ceiling: 18.3, 17.7,
23.4, 27.5, 22.4, 22.2, 39.2 minutes, then the kill. It grows because the
historical cursor walks forward into busier news months, and it grew in ONE
phase -- `_fetch_trusted`, which issued one HTTP GET per trusted candidate with
no clock and no count. Collection had been bounded by `deadline` since #253;
the fetch that followed it had not.

The measured surplus, from that run's own log: the BigQuery mirror matched
35,175 articles for a single 2021 week, and the caller had asked for TEN.

Three things are pinned here, and the second and third are the reason this file
exists rather than a one-line cap:

  1. a huge match set does NOT become a huge fetch when the caller passed a cap;
  2. the cap counts USABLE RESULTS, not attempts -- about a fifth of these
     fetches fail by publisher design (3,658 trusted -> 3,000 fetched on
     2026-09-03), so a cap on attempts silently under-delivers the sweep;
  3. the LIVE path stays unbounded. `max_records` is a per-query GDELT ceiling
     and `collected` is the union of a dozen queries, so it is not "what the
     caller can use". Live telemetry for 2026-09-02 reads 916 trusted
     candidates, 847 kept, against max_records=250 -- binding the fetch cap to
     max_records would have cut the primary worldwide collector by ~70% with
     every surface still green.

Hermetic: `_fetch_article` is stubbed, nothing touches the network.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_reach  # noqa: E402
from sources import gdelt  # noqa: E402


def _articles(n, prefix="https://www.reuters.com/a"):
    return [{"url": f"{prefix}{i}", "domain": "reuters.com",
             "title": "layoffs", "seendate": "20260820T120000Z"}
            for i in range(n)]


class FetchFanOut(unittest.TestCase):
    def setUp(self):
        gdelt_reach.reset()

    def test_a_huge_match_set_does_not_become_a_huge_fetch(self):
        """The 2026-09-04 shape: thousands matched, ten wanted."""
        fetched = []

        def fake_fetch(url):
            fetched.append(url)
            return "body text"

        with patch.object(gdelt, "_fetch_article", side_effect=fake_fetch), \
             patch.object(gdelt, "_is_trusted", return_value=True), \
             patch.object(gdelt.time, "sleep"):
            out = gdelt._fetch_trusted(_articles(5000), max_candidates=10)

        # A wave of FETCH_WORKERS is always drained, so the bound is the cap
        # plus at most one wave -- never the 5,000 the old code walked.
        self.assertLessEqual(len(fetched), 10 + gdelt.FETCH_WORKERS,
                             "the fetch phase must stop once the caller's "
                             "candidate cap is satisfied")
        self.assertGreaterEqual(len(out), 10,
                                "a satisfied cap must still deliver the "
                                "candidates the caller asked for")

    def test_the_cap_counts_usable_results_not_attempts(self):
        """These fetches fail by publisher design -- 403/404/429 -- and the
        rate is not small: 3,658 trusted produced 3,000 fetched on 2026-09-03,
        and the 2026-09-04 run logged 629 errors. A cap counting ATTEMPTS
        hands the extractor whatever survives; a cap counting RESULTS hands it
        the number it asked for. Pinned at a 50% failure rate so the two
        answers cannot coincide."""
        calls = {"n": 0}

        def flaky(url):
            calls["n"] += 1
            if calls["n"] % 2 == 0:          # every second publisher says no
                raise RuntimeError("403 Client Error: Forbidden")
            return "body text"

        with patch.object(gdelt, "_fetch_article", side_effect=flaky), \
             patch.object(gdelt, "_is_trusted", return_value=True), \
             patch.object(gdelt.time, "sleep"):
            out = gdelt._fetch_trusted(_articles(500), max_candidates=10)

        self.assertGreaterEqual(
            len(out), 10,
            "the cap must be satisfied in USABLE entries: counting attempts "
            "instead delivers only the survivors and quietly shrinks the "
            "sweep's yield")
        self.assertGreaterEqual(
            calls["n"], 20,
            "reaching 10 usable entries through a 50% failure rate must have "
            "cost about twice as many attempts")

    def test_capped_candidates_are_accounted_for_not_silently_dropped(self):
        """gdelt_reach's invariant: every candidate lands in exactly one
        outcome, so the columns add up to the returned count."""
        with patch.object(gdelt, "_fetch_article", return_value="body text"), \
             patch.object(gdelt, "_is_trusted", return_value=True), \
             patch.object(gdelt.time, "sleep"):
            gdelt._fetch_trusted(_articles(200), max_candidates=10)

        by_reason = gdelt_reach.current().by_reason()
        self.assertTrue(by_reason.get("candidate_cap"),
                        "candidates the cap never reached must be recorded, "
                        "not vanish out of the reach accounting")
        attributed = sum(by_reason.get(r, 0) for r in gdelt_reach.REASONS)
        self.assertEqual(attributed, 200,
                         "every one of the 200 candidates must be attributed "
                         "to exactly one outcome")

    def test_no_cap_means_no_cap(self):
        """The default is unbounded, so no existing caller changes behaviour."""
        fetched = []

        def fake_fetch(url):
            fetched.append(url)
            return "body text"

        with patch.object(gdelt, "_fetch_article", side_effect=fake_fetch), \
             patch.object(gdelt, "_is_trusted", return_value=True), \
             patch.object(gdelt.time, "sleep"):
            out = gdelt._fetch_trusted(_articles(120))

        self.assertEqual(len(fetched), 120)
        self.assertEqual(len(out), 120)


class OnlyTheDiscardingCallerCaps(unittest.TestCase):
    """The live collector must NOT inherit a cap from `max_records`."""

    def test_pull_gdelt_between_does_not_default_the_cap_to_max_records(self):
        """Live reality (2026-09-02): 916 trusted candidates, 847 kept, against
        max_records=250. Reusing max_records as the fetch cap would drop ~70%
        of the primary worldwide collector and look green doing it."""
        import inspect
        sig = inspect.signature(gdelt.pull_gdelt_between)
        self.assertIn("max_candidates", sig.parameters,
                      "the fetch cap must be its own parameter")
        self.assertIsNone(
            sig.parameters["max_candidates"].default,
            "the fetch cap must default to UNBOUNDED: the live collector "
            "passes no cap and must keep fetching every trusted candidate")

        src = inspect.getsource(gdelt.pull_gdelt_between)
        self.assertNotIn(
            "max_candidates=max_records", src.replace(" ", ""),
            "max_records is a PER-QUERY ceiling and `collected` is the union "
            "of a dozen queries; it is not the number the caller can use")

    def test_cron_the_live_caller_passes_no_fetch_cap(self):
        import ast
        src = open(os.path.join(os.path.dirname(__file__), "..", "cron.py")).read()
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "pull_gdelt_between"]
        self.assertTrue(calls, "cron.py no longer calls pull_gdelt_between")
        for call in calls:
            self.assertNotIn(
                "max_candidates", [kw.arg for kw in call.keywords],
                "the live collector must stay unbounded in the fetch phase")

    def test_the_backfill_caps_only_when_it_will_discard_the_surplus(self):
        """`BACKFILL_MAX_ARTICLES` unset means a manual, uncapped backfill --
        the workflow promises it stays uncapped, and it discards nothing."""
        import ast
        src = open(os.path.join(os.path.dirname(__file__), "..",
                                "gdelt_backfill.py")).read()
        calls = [n for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "pull_gdelt_between"]
        self.assertEqual(len(calls), 1)
        kw = {k.arg: k.value for k in calls[0].keywords}
        self.assertIn("max_candidates", kw,
                      "the backfill discards every body past max_articles and "
                      "must not fetch them")
        expr = ast.unparse(kw["max_candidates"])
        self.assertIn("max_articles", expr)
        self.assertIn("None", expr,
                      "an uncapped backfill (no BACKFILL_MAX_ARTICLES) must "
                      "pass None, not `remaining`'s 250 fallback")


if __name__ == "__main__":
    unittest.main()
