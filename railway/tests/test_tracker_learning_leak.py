"""Leak-safety and mechanics for tracker_diff's LEARNING mode.

The learning loop reads a reference universe of layoff coverage (the GDELT
corpus before our own trusted-domain gate) and turns what we missed into RULES.
Everything it reads is a name: an employer, an outlet, a country, a headline.
Exactly one of those may ever leave the process, and only to the owner's inbox.

THE PROPERTY THIS FILE HOLDS IS STRUCTURAL, NOT EDITORIAL. It is not "we
checked that today's log looks clean". `assert_nameless` is an allowlist over
the entire vocabulary a public sink may contain — numbers, ISO dates, and a
frozen set of label words — so a name cannot be spelled by anything that
reaches stdout, the source-health ledger, or the committed measurement file.
The end-to-end test below poisons a whole run with a marker string and proves
the marker reaches the /alert email and NOTHING else. The email assertion is
there on purpose: a test that only proves silence would also pass if the loop
learned nothing at all.

Offline. Only `requests` is stubbed at module level (never a fake `sources.*`
module — see tests/test_warn_generic_drift.py for why that trap exists);
`sources.gdelt._query_window` is patched as an ATTRIBUTE of the real module and
restored.
"""
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _m in ("requests", "openai"):
    if _m not in sys.modules:
        _stub = types.ModuleType(_m)
        _stub.RequestException = Exception
        sys.modules[_m] = _stub

import tracker_diff as td
import sources.gdelt as gdelt

# One nonsense token that cannot occur in any legitimate public output. Every
# name-bearing field of the poisoned run is built from it, so a single
# case-insensitive search over a sink proves that sink carries no name.
MARK = "Zzqqmarker"


def _poisoned_articles(n=6):
    """A corpus where the employer, the outlet, the country and the language
    are all the marker, and every headline states a headcount we do not hold."""
    return [{
        "title": f"{MARK}{i} to cut {300 + i} jobs in restructuring",
        "domain": f"{MARK.lower()}-news{i % 2}.example",
        "sourcecountry": f"{MARK}land",
        "language": f"{MARK}ish",
        "seendate": "20260818T120000Z",
        "url": f"https://{MARK.lower()}.example/{i}",
    } for i in range(n)]


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


class NamelessGuardTests(unittest.TestCase):
    """The allowlist itself. If this class is wrong, nothing else is safe."""

    def test_numbers_dates_and_labels_pass(self):
        td.assert_nameless({
            "date": "2026-08-18", "method": td.LEARN_METHOD, "mode": "learn",
            "cadence": "daily", "state": "ran", "corpus": 250, "matched": 9,
            "independent_recall_pct": 81.8, "emailed": True, "unknown": None,
            "rules_by_kind": {"outlet": 2, "vocabulary": 1},
        })

    def test_free_text_is_refused(self):
        with self.assertRaises(td.LeakGuard):
            td.assert_nameless({"state": "Acme Corp"})
        with self.assertRaises(td.LeakGuard):
            td.assert_nameless({"rules_by_kind": {"outlet": "example.com"}})

    def test_an_undeclared_key_is_refused(self):
        # A future field cannot be smuggled in by naming it something plausible.
        with self.assertRaises(td.LeakGuard):
            td.assert_nameless({"top_outlet": 3})

    def test_nested_and_exotic_values_are_refused(self):
        with self.assertRaises(td.LeakGuard):
            td.assert_nameless({"rules": [{"date": "2026-08-18", "mode": MARK}]})
        with self.assertRaises(td.LeakGuard):
            td.assert_nameless({"date": object()})

    def test_public_render_refuses_a_name(self):
        with self.assertRaises(td.LeakGuard):
            td.public_render({"cadence": MARK})
        self.assertIn("matched 3", td.public_render({"matched": 3, "rules": 0}))


class HeadlineReadingTests(unittest.TestCase):
    def test_headcount_forms(self):
        self.assertEqual(td.headline_jobs("Acme to cut 1,200 jobs"), 1200)
        self.assertEqual(td.headline_jobs("Acme lays off 450"), 450)
        self.assertEqual(td.headline_jobs("Acme sheds 12,000 workers"), 12000)

    def test_a_percentage_is_not_a_headcount(self):
        self.assertIsNone(td.headline_jobs("Acme to cut 10% of staff"))

    def test_below_the_floor_is_not_a_candidate(self):
        self.assertIsNone(td.headline_jobs("Acme cuts 4 jobs"))

    def test_employer_token(self):
        self.assertEqual(td.headline_employer_token("Acme to cut 500 jobs"), "Acme")
        self.assertEqual(
            td.headline_employer_token("Exclusive: Acme to cut 500 jobs"), "Acme")
        self.assertEqual(
            td.headline_employer_token("Acme cuts 500 jobs - Some Outlet"), "Acme")

    def test_a_headline_with_no_leading_name_yields_nothing(self):
        # Better to judge nothing than to judge the wrong employer: a bad token
        # would score a real find as a miss and manufacture a rule.
        self.assertEqual(td.headline_employer_token("why 500 jobs went away"), "")

    def test_a_generic_leading_adjective_is_not_an_employer(self):
        # Measured on a real sweep: this headline yielded the "employer" Major.
        self.assertEqual(td.headline_employer_token(
            "Major retail meat company closes plants, lays off over 3,200"), "")


class MatchingTests(unittest.TestCase):
    """Three states, because two of them would lie. See rows_verdict."""

    ROWS = [{"job_count": 500, "layoff_date": "2026-08-01"}]

    def test_same_count_inside_the_window_is_ours(self):
        self.assertEqual(td.rows_verdict(self.ROWS, 500, date(2026, 8, 18)),
                         "match")

    def test_same_count_far_outside_the_window_is_unknown_not_a_miss(self):
        # A retrospective piece about an event we already hold. Calling this a
        # miss would depress recall and invent a rule out of our own coverage.
        self.assertEqual(td.rows_verdict(self.ROWS, 500, date(2025, 1, 1)),
                         "unknown")

    def test_a_different_count_is_a_different_event(self):
        self.assertEqual(td.rows_verdict(self.ROWS, 900, date(2026, 8, 18)),
                         "miss")

    def test_rounding_tolerance(self):
        self.assertEqual(
            td.rows_verdict([{"job_count": 12000, "layoff_date": "2026-08-10"}],
                            12100, date(2026, 8, 18)), "match")

    def test_nothing_of_ours_is_a_miss(self):
        self.assertEqual(td.rows_verdict([], 500, date(2026, 8, 18)), "miss")

    def test_an_undated_row_is_not_held_against_us(self):
        self.assertEqual(
            td.rows_verdict([{"job_count": 500, "layoff_date": None}], 500,
                            date(2026, 8, 18)), "match")


class RuleRankingTests(unittest.TestCase):
    def _arts(self, n, domain="unknown-outlet.example", country="Nowhere",
              language="English", title="Acme to cut 500 jobs"):
        return [{"title": title, "domain": domain, "sourcecountry": country,
                 "language": language} for _ in range(n)]

    def test_a_repeat_outlet_becomes_a_rule_and_a_single_one_does_not(self):
        one = td.rank_rules(self._arts(1), set(), td_terms := ("job cuts",))
        two = td.rank_rules(self._arts(2), set(), td_terms)
        self.assertEqual([r["kind"] for r in one if r["kind"] == "outlet"], [])
        self.assertEqual([r["subject"] for r in two if r["kind"] == "outlet"],
                         ["unknown-outlet.example"])

    def test_a_trusted_outlet_is_never_suggested(self):
        rules = td.rank_rules(self._arts(4, domain="reuters.com"),
                              {"reuters.com"}, ("job cuts",))
        self.assertEqual([r for r in rules if r["kind"] == "outlet"], [])

    def test_a_repeated_wording_we_cannot_see_becomes_a_vocabulary_rule(self):
        title = "Acme begins a delayering of 500 roles worldwide"
        self.assertFalse(any(r["kind"] == "vocabulary" for r in
                             td.rank_rules(self._arts(1, title=title), set(),
                                           ("job cuts", "layoffs"))))
        rules = td.rank_rules(self._arts(2, title=title), set(),
                              ("job cuts", "layoffs"))
        vocab = [r for r in rules if r["kind"] == "vocabulary"]
        self.assertEqual(len(vocab), 1)
        # The subject is the PHRASING, not the headline: that is what makes it
        # a rule the owner can act on, and what lets two different companies
        # using the same wording add up to one signal.
        self.assertIn("delayering", vocab[0]["subject"])
        self.assertNotIn("acme", vocab[0]["subject"])

    def test_a_headline_our_vocabulary_already_sees_teaches_nothing(self):
        rules = td.rank_rules(self._arts(3, title="Acme announces 500 job cuts"),
                              set(), ("job cuts",))
        self.assertFalse(any(r["kind"] == "vocabulary" for r in rules))

    def test_a_headline_with_no_headcount_yields_no_wording(self):
        # Without a number there is nothing to centre the phrase on, and a
        # whole-headline subject is what made this kind unactionable.
        self.assertEqual(td.vocab_phrase("Acme restructures its org"), "")

    def test_english_never_becomes_a_language_rule(self):
        rules = td.rank_rules(self._arts(5), set(), ("job cuts",))
        self.assertFalse(any(r["kind"] == "language" for r in rules))
        rules = td.rank_rules(self._arts(5, language="Portuguese"), set(),
                              ("job cuts",))
        self.assertTrue(any(r["kind"] == "language" for r in rules))


class EarnedCadenceTests(unittest.TestCase):
    MON = date(2026, 8, 17)
    TUE = date(2026, 8, 18)

    def _hist(self, rule_counts):
        return [{"date": f"2026-08-{i + 1:02d}", "rules": r}
                for i, r in enumerate(rule_counts)]

    def test_a_short_history_runs_daily(self):
        self.assertTrue(td.learn_today([], self.TUE))
        self.assertTrue(td.learn_today(self._hist([0, 0]), self.TUE))

    def test_three_empty_runs_step_down_to_mondays(self):
        hist = self._hist([1, 0, 0, 0])
        self.assertFalse(td.learn_today(hist, self.TUE))
        self.assertTrue(td.learn_today(hist, self.MON))

    def test_one_rule_steps_straight_back_up(self):
        self.assertTrue(td.learn_today(self._hist([0, 0, 0, 2]), self.TUE))


class PoisonedRunTests(unittest.TestCase):
    """End to end with every name replaced by a marker. This is the test that
    would fail if someone added a `print(domain)` for debugging."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._saved = (td.LEARN_STATE_PATH, gdelt._query_window,
                       td.requests, td.report_source_health)
        td.LEARN_STATE_PATH = os.path.join(self.tmp, "state.json")
        gdelt._query_window = lambda *a, **k: (_poisoned_articles(), False, None)

        self.posts = []
        self.health = []
        fake = types.SimpleNamespace(
            # Our own /query: we hold nothing for these employers, so every
            # poisoned headline is a miss and every rule kind fires.
            get=lambda *a, **k: _FakeResponse({"data": []}),
            post=lambda url, **k: (self.posts.append((url, k)) or _FakeResponse({})),
        )
        td.requests = fake
        td.report_source_health = lambda *a: self.health.append(a)
        os.environ["WP_SITE_URL"] = "https://example.test/blog"
        os.environ["WP_API_KEY"] = "test-key"

    def tearDown(self):
        (td.LEARN_STATE_PATH, gdelt._query_window,
         td.requests, td.report_source_health) = self._saved

    def _run(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            facts = td.learn_run(today=date(2026, 8, 18))
        return facts, buf.getvalue()

    def test_the_marker_reaches_the_owner_email_and_nothing_else(self):
        facts, out = self._run()

        # 1. The loop actually learned something. Without this the rest of the
        #    assertions would pass on an empty run and prove nothing.
        self.assertGreater(facts["rules"], 0)
        alerts = [k for url, k in self.posts if url.endswith("/alert")]
        self.assertEqual(len(alerts), 1)
        email = json.dumps(alerts[0])
        self.assertIn(MARK.lower(), email.lower())

        # 2. stdout — the GitHub Actions log — carries no name.
        self.assertNotIn(MARK.lower(), out.lower())

        # 3. The source-health ledger (a PUBLIC page) carries no name.
        self.assertNotIn(MARK.lower(), json.dumps(self.health).lower())

        # 4. The committed measurement file carries no name.
        with open(td.LEARN_STATE_PATH) as fh:
            self.assertNotIn(MARK.lower(), fh.read().lower())

        # 5. The returned fact dict is publishable by construction.
        td.assert_nameless(facts)

    def test_the_state_file_is_a_trend_not_a_dump(self):
        self._run()
        with open(td.LEARN_STATE_PATH) as fh:
            state = json.load(fh)
        self.assertEqual(len(state["history"]), 1)
        point = state["history"][0]
        self.assertEqual(point["date"], "2026-08-18")
        self.assertEqual(point["method"], td.LEARN_METHOD)
        self.assertIn("independent_recall_pct", point)
        td.assert_nameless(state)

    def test_independent_recall_counts_only_what_it_could_judge(self):
        # Every poisoned headline is unmatched, so recall is 0% over a real
        # denominator — never a silent 100% on an empty judgement.
        facts, _ = self._run()
        self.assertEqual(facts["independent_recall_pct"], 0.0)
        self.assertEqual(facts["candidates"], facts["unmatched"])
        self.assertEqual(facts["matched"], 0)

    def test_a_lookup_failure_is_unknown_never_a_miss(self):
        td.requests = types.SimpleNamespace(
            get=lambda *a, **k: _FakeResponse({}, status=503),
            post=lambda url, **k: (self.posts.append((url, k)) or _FakeResponse({})),
        )
        facts, _ = self._run()
        self.assertEqual(facts["matched"], 0)
        self.assertEqual(facts["unmatched"], 0)
        self.assertGreater(facts["unknown"], 0)
        self.assertIsNone(facts["independent_recall_pct"])
        self.assertEqual(facts["rules"], 0)

    def test_an_upstream_outage_is_unknown_and_teaches_nothing(self):
        gdelt._query_window = lambda *a, **k: (None, True, "HTTP 429")
        facts, out = self._run()
        self.assertEqual(facts["state"], "unknown")
        # No rule may be inferred from a corpus nobody could read...
        self.assertNotIn("rules", facts)
        # ...it is not a broken collector either (nothing of ours failed)...
        self.assertEqual(self.health[0][1], "ok")
        self.assertIn("UNKNOWN", self.health[0][3])
        # ...and it is recorded, so an outage is visible rather than absent,
        # while carrying no `rules` key the earned cadence could mistake for a
        # quiet day.
        with open(td.LEARN_STATE_PATH) as fh:
            point = json.load(fh)["history"][-1]
        self.assertEqual(point["state"], "unknown")
        self.assertNotIn("rules", point)
        self.assertTrue(td.learn_today([point] * 5, date(2026, 8, 18)))

    def test_the_quiet_cadence_skips_without_touching_the_corpus(self):
        with open(td.LEARN_STATE_PATH, "w") as fh:
            json.dump({"history": [{"date": f"2026-08-{i:02d}", "rules": 0}
                                   for i in (14, 15, 16)]}, fh)

        def _boom(*a, **k):
            raise AssertionError("a quiet run must not query the corpus")

        gdelt._query_window = _boom
        facts, _ = self._run()          # 2026-08-18 is a Tuesday
        self.assertEqual(facts["state"], "skipped")
        self.assertEqual(facts["cadence"], "quiet")
        self.assertEqual(self.posts, [])


if __name__ == "__main__":
    unittest.main()
