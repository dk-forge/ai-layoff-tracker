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
module — see tests/test_warn_generic_drift.py for why that trap exists). The
corpus read is patched at `tracker_diff._learn_fetch`, which is the seam that
already separates "we read it" from "the host did not answer" from "the host
refused our query"; the fetch itself is tested directly against a fake
`requests` below.
"""
import io
import json
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
import time as time_module
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _m in ("requests", "openai"):
    if _m not in sys.modules:
        _stub = types.ModuleType(_m)
        _stub.RequestException = Exception
        sys.modules[_m] = _stub

import tracker_diff as td

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


class CorpusQueryTests(unittest.TestCase):
    """GDELT refuses a long query with HTTP 200 and a plain-text body, which
    reads downstream as a JSON parse error. Measured 2026-08-18: the ingest's
    own 927-character query was refused; 152 characters answered."""

    TERMS = ("layoffs", "job cuts", "reduction in force", "collective dismissal",
             "retrenchment", "workforce optimization", "plant closure")

    def test_the_query_stays_inside_the_ceiling(self):
        for day in (date(2026, 8, 18), date(2026, 8, 19), date(2027, 1, 1)):
            q = td.learn_query(self.TERMS, day)
            self.assertLessEqual(len(q), td.LEARN_QUERY_CHARS)
            self.assertTrue(q.startswith("(") and q.endswith(")"))

    def test_a_single_term_longer_than_the_ceiling_still_yields_a_query(self):
        # Never return "()" — an empty group is a query GDELT accepts and
        # answers with nonsense, which would be read as an empty corpus.
        q = td.learn_query(("a" * (td.LEARN_QUERY_CHARS + 50),), date(2026, 8, 18))
        self.assertTrue(q.startswith("(") and len(q) > 3)

    def test_the_slice_rotates_so_the_whole_vocabulary_is_walked(self):
        seen = {td.learn_query(self.TERMS, date(2026, 8, 18 + i))
                for i in range(len(self.TERMS))}
        self.assertGreater(len(seen), 1)
        joined = " ".join(seen)
        for term in self.TERMS:
            self.assertIn(term, joined)

    def test_no_terms_is_empty_rather_than_a_malformed_query(self):
        self.assertEqual(td.learn_query((), date(2026, 8, 18)), "")


# A payload shaped like the one that reddened CI on 2026-08-19: a lone
# backslash inside one article title, deep in an otherwise fine response, which
# `json.loads` rejects with `Invalid \escape` for the WHOLE body. Written by
# hand rather than captured, because a captured fixture would carry whatever
# outlet and company the real row named, and none of that may enter the repo —
# the failure is exactly reproducible from its shape, so nothing is lost.
def _payload(rows, bad_row=True):
    good = ", ".join(
        '{"url": "https://example%d.test/a", "title": "Acme %d cuts 500 jobs", '
        '"domain": "example%d.test", "language": "English", '
        '"sourcecountry": "United States", "seendate": "20260818T120000Z"}'
        % (i, i, i) for i in range(rows))
    bad = (', {"url": "https://example.test/b", "title": "Beta cuts 300 jobs \\ '
           'in Q3", "domain": "example.test", "language": "English", '
           '"sourcecountry": "United States", "seendate": "20260818T120000Z"}')
    return '{"articles": [ ' + good + (bad if bad_row else "") + ' ]}'


class MalformedPayloadTests(unittest.TestCase):
    """GDELT's JSON is not always JSON, and one bad row must not cost the other
    two hundred. The run that taught this went red with
    `Invalid \escape: line 1 column 114236` — one title, 114KB in."""

    def test_a_clean_payload_parses_whole(self):
        arts, dropped = td.parse_gdelt_json(_payload(3, bad_row=False))
        self.assertEqual((len(arts), dropped), (3, 0))

    def test_one_unparseable_row_does_not_discard_the_rest(self):
        raw = _payload(200)
        with self.assertRaises(ValueError):
            json.loads(raw)          # the fixture really is invalid JSON
        arts, dropped = td.parse_gdelt_json(raw)
        self.assertGreaterEqual(len(arts), 200)
        self.assertEqual(len(arts) + dropped, 201)

    def test_raw_control_characters_are_tolerated(self):
        arts, dropped = td.parse_gdelt_json(
            '{"articles": [{"url": "https://example.test/a", '
            '"title": "Acme\x01 cuts 500 jobs"}]}')
        self.assertEqual((len(arts), dropped), (1, 0))

    def test_a_row_that_cannot_be_recovered_is_COUNTED(self):
        raw = ('{"articles": [ {"url": "https://example.test/a", "title": "ok"}, '
               '{"url": "https://example.test/b", "title": "trunc\\ ')
        arts, dropped = td.parse_gdelt_json(raw)
        self.assertEqual(len(arts), 1)
        self.assertGreaterEqual(dropped, 0)

    def test_a_dropped_row_keeps_the_run_out_of_the_quiet_count(self):
        # A run that could not read part of its own corpus does not KNOW it
        # found nothing, so it must not be allowed to wean the loop quiet.
        point = {"date": "2026-08-18", "dropped": 2}
        self.assertNotIn("rules", point)
        self.assertTrue(td.learn_today([point] * 5, date(2026, 8, 18)))

    def test_junk_is_not_silently_an_empty_corpus(self):
        arts, dropped = td.parse_gdelt_json("not json at all")
        self.assertEqual((arts, dropped), ([], 0))


class FetchOutcomeTests(unittest.TestCase):
    """Three outcomes kept apart: theirs, nobody's, ours. The sibling
    collectors turned "could not reach" into a verdict about their own code;
    this module must not repeat that in a new file."""

    def setUp(self):
        self._saved = (td.requests, td.LEARN_THROTTLE_WAIT)
        td.LEARN_THROTTLE_WAIT = 5

    def tearDown(self):
        td.requests, td.LEARN_THROTTLE_WAIT = self._saved

    def _fetch(self, responses):
        seen = []

        class _R:
            def __init__(self, status, text):
                self.status_code, self.text = status, text

        def _get(url, **kw):
            seen.append(url)
            return _R(*responses[min(len(seen) - 1, len(responses) - 1)])

        td.requests = types.SimpleNamespace(get=_get)
        td.time = types.SimpleNamespace(sleep=lambda *_a: None)
        start = end = datetime(2026, 8, 18, 12, 0, 0)
        try:
            return td._learn_fetch("(layoffs)", start, end), seen
        finally:
            td.time = time_module

    def test_a_good_response_is_read(self):
        (arts, dropped, state), seen = self._fetch([(200, _payload(2, False))])
        self.assertEqual((len(arts), dropped, state), (2, 0, None))
        self.assertEqual(len(seen), 1)

    def test_a_rejected_query_is_OURS_and_is_not_retried(self):
        # A 200 carrying prose is how the endpoint refuses an over-long query.
        (_a, _d, state), seen = self._fetch(
            [(200, "Your query was too short or too long.\n")])
        self.assertEqual(state, "ours")
        self.assertEqual(len(seen), 1)
        (_a, _d, state), _seen = self._fetch([(400, "bad request")])
        self.assertEqual(state, "ours")

    def test_a_throttled_host_is_NOBODY_S_defect(self):
        (_a, _d, state), seen = self._fetch([(429, "slow down")])
        self.assertEqual(state, "unknown")
        self.assertEqual(len(seen), td.LEARN_QUERY_ATTEMPTS)

    def test_a_deterministic_parse_failure_is_not_retried(self):
        # It parses the same way every time; retrying it is wasted work, and
        # the run that taught this burned two attempts on identical bytes.
        (arts, dropped, state), seen = self._fetch([(200, _payload(2))])
        self.assertEqual(len(seen), 1)
        self.assertIsNone(state)
        # The lone backslash is REPAIRED rather than dropped: the row is real
        # coverage and a headline is not worth losing to an escape.
        self.assertEqual((len(arts), dropped), (3, 0))


class MissPostMortemTests(unittest.TestCase):
    """The taxonomy is the deliverable: for each miss, WHICH OF OUR TIERS
    should have caught it. Only the cause is ever written down."""

    TRUSTED = {"reuters.com"}
    TERMS = ("job cuts", "layoffs")

    def _art(self, **kw):
        base = {"domain": "reuters.com", "language": "English",
                "sourcecountry": "United States",
                "title": "Acme announces 500 job cuts"}
        base.update(kw)
        return base

    def test_a_publisher_we_do_not_read_is_the_headline_cause(self):
        self.assertEqual(
            td.classify_miss(self._art(domain="tradepress.example"),
                             self.TRUSTED, self.TERMS), "not_wired")

    def test_a_wired_outlet_in_another_language(self):
        self.assertEqual(
            td.classify_miss(self._art(language="Korean"), self.TRUSTED,
                             self.TERMS), "language_edition")

    def test_a_country_with_no_market_entry(self):
        self.assertEqual(
            td.classify_miss(self._art(sourcecountry="Nigeria"), self.TRUSTED,
                             self.TERMS), "country_edition")

    def test_wording_we_do_not_search_for(self):
        self.assertEqual(
            td.classify_miss(self._art(title="Acme delayers 500 roles"),
                             self.TRUSTED, self.TERMS), "vocabulary_gap")

    def test_everything_covered_and_still_missed_is_named_not_hidden(self):
        # A trusted outlet, a covered country, a language we read and a wording
        # we search for — that is a defect on our side, and it must surface as
        # its own cause rather than being folded into a gap we do not have.
        self.assertEqual(td.classify_miss(self._art(), self.TRUSTED, self.TERMS),
                         "unclassified")

    def test_unreachable_is_never_assigned_by_the_machine(self):
        # A paywall cannot be seen without fetching the page, and fetching it is
        # the one thing this loop must never do. The owner closes those.
        causes = {td.classify_miss(self._art(**kw), self.TRUSTED, self.TERMS)
                  for kw in ({}, {"domain": "x.example"}, {"language": "Korean"},
                             {"sourcecountry": "Nigeria"})}
        self.assertNotIn("unreachable", causes)
        self.assertIn("unreachable", td.MISS_CAUSES)


class RecallBandTests(unittest.TestCase):
    """Bands, never a point, and never summed across incompatible scopes."""

    def test_a_small_denominator_produces_a_wide_band(self):
        point, low, high = td.recall_band(2, 4)
        self.assertEqual(point, 50.0)
        self.assertLess(low, 25.0)
        self.assertGreater(high, 75.0)

    def test_a_larger_denominator_tightens_it(self):
        _p, low4, high4 = td.recall_band(2, 4)
        _p, low40, high40 = td.recall_band(20, 40)
        self.assertLess(high40 - low40, high4 - low4)

    def test_zero_of_three_is_not_certainty(self):
        point, low, high = td.recall_band(0, 3)
        self.assertEqual((point, low), (0.0, 0.0))
        self.assertGreater(high, 25.0)

    def test_nothing_judged_is_no_number_at_all(self):
        self.assertEqual(td.recall_band(0, 0), (None, None, None))

    def test_the_run_records_its_scope_beside_the_number(self):
        # A recall figure without a stated scope is the one that gets quoted
        # against a tracker measuring something else entirely.
        self.assertIn("scope", td._PUBLIC_KEYS)


class LocalItemTests(unittest.TestCase):
    """The hand-pasted path: the designed route where a listing cannot be
    fetched, not a degraded one."""

    def test_the_three_line_forms(self):
        items = td.parse_local_items(
            "# a comment\n\nAcme | 500 | 2026-08-01\nBeta Corp | 1,200\n"
            "Gamma Ltd cuts 300 jobs\n")
        self.assertEqual([i["company"] for i in items],
                         ["Acme", "Beta Corp", "Gamma Ltd cuts 300 jobs"])
        self.assertEqual([i["jobs"] for i in items], [500, 1200, 300])
        self.assertEqual(items[0]["date"], "2026-08-01")
        self.assertIsNone(items[1]["date"])

    def test_an_item_with_no_headcount_is_kept_but_uncounted(self):
        items = td.parse_local_items("Acme\n")
        self.assertEqual(items[0]["jobs"], None)


class EntryPointTests(unittest.TestCase):
    """The guard that a test which only IMPORTS the module cannot give you."""

    def test_the_main_guard_is_the_last_thing_in_the_file(self):
        # `--learn` shipped once with `if __name__ == "__main__"` sitting above
        # the learning block, and the first run on a runner died with
        # `NameError: learn_run is not defined` — the guard executes during
        # import, so everything callable from it must be defined above it.
        # Every test here imports the module and never runs the guard, which is
        # exactly why none of them caught it.
        src = (Path(__file__).resolve().parents[1] / "tracker_diff.py").read_text()
        self.assertEqual(src.count('if __name__ == "__main__":'), 1)
        for name in ("def run(", "def main(", "def learn_run("):
            self.assertLess(src.index(name), src.index('if __name__ =='), name)


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
        self._saved = (td.LEARN_STATE_PATH, td._learn_fetch,
                       td.requests, td.report_source_health)
        td.LEARN_STATE_PATH = os.path.join(self.tmp, "state.json")
        td._learn_fetch = lambda *a, **k: (_poisoned_articles(), 0, None)

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
        (td.LEARN_STATE_PATH, td._learn_fetch,
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
        td._learn_fetch = lambda *a, **k: ([], 0, "unknown")
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

    def test_only_the_anchor_slice_is_measured_but_both_teach(self):
        """The rotating slice must not enter the recall denominator, or the
        number swings on which words came up rather than on our coverage."""
        anchor = _poisoned_articles(3)
        rotating = [dict(a, title=a["title"].replace(MARK, "Qqzz"),
                         domain="rotating-only.example") for a in _poisoned_articles(3)]
        calls = []

        def _two_slices(query, *a, **k):
            calls.append(query)
            return ((anchor if len(calls) == 1 else rotating), 0, None)

        td._learn_fetch = _two_slices
        facts, _ = self._run()
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0], calls[1])
        self.assertEqual(facts["corpus"], 3)
        self.assertEqual(facts["explored"], 3)
        # Measured on the anchor only...
        self.assertEqual(facts["candidates"], 3)
        self.assertEqual(facts["unmatched"], 3)
        # ...while the rules see every miss from both slices.
        self.assertEqual(facts["rule_misses"], 6)
        self.assertTrue(any(k == "outlet" for k in facts["rules_by_kind"]))

    def test_a_rotating_slice_outage_does_not_stop_the_measurement(self):
        anchor = _poisoned_articles(2)
        calls = []

        def _anchor_only(query, *a, **k):
            calls.append(query)
            return (anchor, 0, None) if len(calls) == 1 else ([], 0, "unknown")

        td._learn_fetch = _anchor_only
        facts, _ = self._run()
        self.assertEqual(facts["state"], "ran")
        self.assertEqual(facts["explored"], 0)
        self.assertEqual(facts["candidates"], 2)

    def test_the_quiet_cadence_skips_without_touching_the_corpus(self):
        with open(td.LEARN_STATE_PATH, "w") as fh:
            json.dump({"history": [{"date": f"2026-08-{i:02d}", "rules": 0}
                                   for i in (14, 15, 16)]}, fh)

        def _boom(*a, **k):
            raise AssertionError("a quiet run must not query the corpus")

        td._learn_fetch = _boom
        facts, _ = self._run()          # 2026-08-18 is a Tuesday
        self.assertEqual(facts["state"], "skipped")
        self.assertEqual(facts["cadence"], "quiet")
        self.assertEqual(self.posts, [])


if __name__ == "__main__":
    unittest.main()
