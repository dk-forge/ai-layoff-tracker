"""THE LOOP THAT READS THE CURATED LIST MUST NOT BE THE THING THAT PUBLISHES IT.

WHY THIS TEST IS NOT ROUTINE.

`curated_probe.py` reads a local file of items a human copied out of a curated
industry digest. Some of those digests are published BY a comparator. The
standing rule is absolute: no comparator name, domain or figure in this repo, in
a commit, in a PR, in an Actions log, in a fixture, or on any public page. And
the whole job of that module is to say interesting things about the file it just
read, on a machine where the file is present and a reviewer's is not.

Care does not survive that arrangement. Shape does. `assert_nameless` is an
allowlist of numbers, ISO dates and frozen label words, so the public vocabulary
cannot SPELL a name — and that property holds against inputs nobody anticipated,
which is the only kind that matters here.

`test_a_poisoned_run_leaks_nothing` is the assertion that keeps it true: it runs
the whole loop against a worklist stuffed with invented outlet names, invented
domains, invented figures and a provenance line naming an invented digest, then
asserts that not one of those strings appears in stdout, in the committed trend
file, or anywhere in the repr of the returned facts.

THE NAMES IN THE FIXTURE ARE FICTIONAL ON PURPOSE. A test that had to contain the
real ones to prove the real ones do not escape would be the leak it was written
to prevent. This is the same reasoning `test_benchmark_freshness` records, and
for the same file-shaped reason.

AND IT IS PROVEN NON-VACUOUS. `test_the_poison_actually_reached_the_private_sink`
asserts the markers DID reach the local gitignored report. Without it, a probe
that silently did nothing at all would pass every leak assertion above and look
like the strongest guard in the repo.
"""
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date


def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("test_curated_probe_leak: no repo root above %s" % here)


ROOT = _repo_root()
sys.path.insert(0, str(ROOT / "railway"))
_spec = importlib.util.spec_from_file_location(
    "curated_probe", ROOT / "railway" / "curated_probe.py")
cp = importlib.util.module_from_spec(_spec)
sys.modules["curated_probe"] = cp
_spec.loader.exec_module(cp)


# Every one of these is invented. If any ever appears in committed output, the
# corresponding real string would have too.
POISON = [
    "Quillfeather Digest", "quillfeather-digest.example",
    "Vantablack Tribune", "vantablack-tribune.example",
    "Marrowgate Post", "marrowgate-post.example",
    "Zibeline Analytics", "zibeline-analytics.example",
    "878787", "4,242",
    # The recovery path's own inputs: an accessible outlet discovered while
    # chasing an inaccessible one must be just as unpublishable.
    "Thornfield Wire", "Bramblecourt",
]

WORKLIST = """
# from: Quillfeather Digest — https://quillfeather-digest.example/issue/44
# aggregator, never a source: zibeline-analytics.example

Vantablack Tribune reports Hollowmere Systems to cut 4,242 roles in its career residency programme  https://vantablack-tribune.example/a/1
Marrowgate Post: Perrindale Foods lays off 878787 staff at its engineering hub  https://marrowgate-post.example/b/2
Zibeline Analytics tracker lists Kettlewick Ltd cutting 900 jobs  https://zibeline-analytics.example/c/3
Quillfeather Digest roundup — Bramblecourt AG sheds 1,500 positions [paywall]  https://quillfeather-digest.example/d/4
"""


class NamelessGuard(unittest.TestCase):
    def test_free_text_is_refused(self):
        for bad in ("Vantablack Tribune", "vantablack-tribune.example", "", "a"):
            with self.assertRaises(cp.LeakGuard):
                cp.assert_nameless({"date": "2026-08-18", "mode": bad})

    def test_undeclared_key_is_refused(self):
        with self.assertRaises(cp.LeakGuard):
            cp.assert_nameless({"outlet_name": 3})

    def test_numbers_dates_and_frozen_words_pass(self):
        ok = {"date": "2026-08-18", "method": cp.METHOD, "mode": "curated",
              "state": "ran", "matched": 3, "curated_recall_pct": 41.7,
              "lessons_by_tier": {"not_in_feed_set": 2, "vocabulary_gap": 1},
              "held_by_tier": {"warn": 1, "news": 2}, "unknown": None}
        self.assertIs(cp.assert_nameless(ok), ok)

    def test_a_nested_name_is_refused(self):
        with self.assertRaises(cp.LeakGuard):
            cp.assert_nameless({"history": [{"date": "2026-08-18",
                                             "mode": "Marrowgate Post"}]})

    def test_public_render_refuses_before_it_renders(self):
        with self.assertRaises(cp.LeakGuard):
            cp.public_render({"date": "2026-08-18", "mode": "Zibeline Analytics"})


class PoisonedRun(unittest.TestCase):
    """Run the whole loop against a poisoned worklist and follow every sink."""

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.worklist = self.tmp / "recall-worklist.txt"
        self.worklist.write_text(WORKLIST, encoding="utf-8")
        self.denylist = self.tmp / "recall-aggregators.txt"
        self.denylist.write_text("zibeline-analytics.example\n", encoding="utf-8")
        self.report = self.tmp / "recall-lessons.md"
        self.state = self.tmp / "state.json"

        # No network in the suite: our own corpus answers nothing, so every
        # judgeable item is a miss and the post-mortem runs at full width. That
        # is the worst case for leakage, which is what we want to test.
        self._rows = cp.our_rows
        cp.our_rows = lambda token, timeout=30: []
        self._email = cp._email
        cp._email = lambda report, facts: False
        self._state_path = cp.STATE_PATH
        cp.STATE_PATH = self.state

        buf = io.StringIO()
        with redirect_stdout(buf):
            self.facts = cp.run(worklist_path=self.worklist,
                                denylist_path=self.denylist,
                                report_path=self.report,
                                known_path=self.tmp / "known.json",
                                refusal_path=self.tmp / "refusals.json",
                                search=lambda token: [
                                    {"title": "Bramblecourt AG sheds 1,500 positions",
                                     "outlet": "Thornfield Wire"}],
                                today=date(2026, 8, 18))
        self.stdout = buf.getvalue()

    def tearDown(self):
        cp.our_rows = self._rows
        cp._email = self._email
        cp.STATE_PATH = self._state_path

    def test_the_poison_actually_reached_the_private_sink(self):
        """NON-VACUITY. A loop that did nothing would pass every test below."""
        self.assertTrue(self.report.exists(), "no local report was written")
        body = self.report.read_text()
        self.assertIn("vantablack-tribune.example", body)
        self.assertIn("marrowgate-post.example", body)
        self.assertEqual(self.facts["state"], "ran")
        self.assertGreater(self.facts["lessons"], 0)

    def test_stdout_carries_no_name(self):
        for marker in POISON:
            self.assertNotIn(marker, self.stdout,
                             f"{marker!r} reached stdout — an Actions log or a "
                             "terminal a human will paste somewhere")

    def test_the_committed_state_carries_no_name(self):
        raw = self.state.read_text()
        for marker in POISON:
            self.assertNotIn(marker, raw, f"{marker!r} reached the committed trend file")
        cp.assert_nameless(json.loads(raw))

    def test_the_returned_facts_carry_no_name(self):
        blob = repr(self.facts)
        for marker in POISON:
            self.assertNotIn(marker, blob, f"{marker!r} survived into the public facts")
        cp.assert_nameless(self.facts)

    def test_the_digest_that_taught_us_never_becomes_a_lesson(self):
        """The provenance host and the denylisted aggregator must not be
        proposed as outlets. Storing an aggregator as a source corrupts the one
        measurement we trust, so this is the load-bearing suppression."""
        body = self.report.read_text()
        self.assertNotIn("Review quillfeather-digest.example", body)
        self.assertNotIn("Review zibeline-analytics.example", body)

    def test_an_unreachable_item_is_a_closed_finding(self):
        self.assertEqual(self.facts["closed"], 1)
        self.assertNotIn("Review quillfeather-digest.example", self.report.read_text())


class Parsing(unittest.TestCase):
    def test_comments_are_never_items(self):
        items, suppressed = cp.parse_worklist(WORKLIST)
        self.assertEqual(len(items), 4)
        self.assertIn("quillfeather-digest.example", suppressed)
        for item in items:
            self.assertFalse(item["headline"].startswith("#"))

    def test_a_provenance_line_suppresses_its_domain(self):
        _items, suppressed = cp.parse_worklist(
            "# from: https://someplace.example/x\nAcme cuts 500 jobs https://outlet.example/y")
        self.assertIn("someplace.example", suppressed)
        self.assertNotIn("outlet.example", suppressed)

    def test_url_and_headline_split(self):
        items, _ = cp.parse_worklist("Acme to cut 500 jobs  https://outlet.example/a?b=1")
        self.assertEqual(items[0]["domain"], "outlet.example")
        self.assertEqual(items[0]["headline"], "Acme to cut 500 jobs")

    def test_www_is_stripped_so_a_host_matches_the_allowlist(self):
        self.assertEqual(cp.registrable_domain("https://www.Outlet.Example/a"),
                         "outlet.example")

    def test_a_line_with_no_url_still_parses(self):
        items, _ = cp.parse_worklist("Acme to cut 500 jobs")
        self.assertEqual(items[0]["domain"], "")


class Diagnosis(unittest.TestCase):
    TRUSTED = {"wired.example"}
    TERMS = ("lays off", "job cuts")

    def _d(self, item, suppressed=frozenset()):
        return cp.diagnose(item, 500, self.TRUSTED, self.TERMS, suppressed)

    def test_unwired_outlet_is_the_top_lesson(self):
        tier, lessons = self._d({"headline": "Acme lays off 500", "domain": "new.example"})
        self.assertEqual(tier, "not_in_feed_set")
        self.assertEqual([l["kind"] for l in lessons], ["outlet"])

    def test_vocabulary_gap_is_recorded_when_the_outlet_is_wired(self):
        tier, lessons = self._d({"headline": "Acme ends its career residency for 500",
                                 "domain": "wired.example"})
        self.assertEqual(tier, "vocabulary_gap")
        self.assertEqual([l["kind"] for l in lessons], ["vocabulary"])

    def test_an_inaccessible_item_is_not_judged_without_a_search(self):
        """UNKNOWN, not "unreachable". Absence of a signal is not a finding, and
        this repo has paid for that confusion elsewhere."""
        tier, lessons = self._d({"headline": "Acme lays off 500",
                                 "domain": "new.example", "closed": True})
        self.assertEqual(tier, "recovery_unknown")
        self.assertEqual(lessons, [])

    def test_a_suppressed_domain_yields_no_outlet_lesson(self):
        _tier, lessons = self._d({"headline": "Acme lays off 500", "domain": "agg.example"},
                                 suppressed={"agg.example"})
        self.assertEqual([l["kind"] for l in lessons], [])

    def test_no_url_is_its_own_tier(self):
        tier, lessons = self._d({"headline": "Acme lays off 500", "domain": ""})
        self.assertEqual(tier, "no_origin")
        self.assertEqual(lessons, [])

    def test_outlet_outranks_vocabulary_when_both_apply(self):
        tier, lessons = self._d({"headline": "Acme ends its career residency for 500",
                                 "domain": "new.example"})
        self.assertEqual(tier, "not_in_feed_set")
        self.assertEqual(sorted(l["kind"] for l in lessons), ["outlet", "vocabulary"])


class RecallDenominator(unittest.TestCase):
    """THE NUMBER MUST MEASURE OUR COVERAGE, NOT OUR PARSER.

    Found on the first live run. A self-probe built entirely out of rows we
    demonstrably hold scored 73.3% instead of ~100%, because every line whose
    headcount sat below the parser's floor had been counted as a coverage miss.
    A recall figure that falls when our own parsing declines to judge something
    is measuring the wrong thing, and it fails in the believable direction, so
    nobody would have queried it.
    """

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self._rows, self._email = cp.our_rows, cp._email
        self._state = cp.STATE_PATH
        cp.STATE_PATH = self.tmp / "state.json"
        cp._email = lambda report, facts: False

    def tearDown(self):
        cp.our_rows, cp._email, cp.STATE_PATH = self._rows, self._email, self._state

    def _run(self, text):
        wl = self.tmp / "w.txt"
        wl.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            facts = cp.run(worklist_path=wl, denylist_path=self.tmp / "none.txt",
                           report_path=self.tmp / "r.md",
                           known_path=self.tmp / "known.json",
                           today=date(2026, 8, 18))
        return facts

    def test_a_sub_floor_item_is_unparsed_not_a_miss(self):
        """"Acme lays off 9" is below the headcount floor: not judgeable."""
        cp.our_rows = lambda token, timeout=30: []
        facts = self._run("Acme lays off 9 employees  https://new.example/a")
        self.assertEqual(facts["unparsed"], 1)
        self.assertEqual(facts["judged"], 0)
        self.assertEqual(facts["unmatched"], 0)
        self.assertIsNone(facts["curated_recall_pct"])

    def test_an_item_we_hold_scores_full_recall_even_beside_unparsed_lines(self):
        cp.our_rows = lambda token, timeout=30: [
            {"job_count": 500, "layoff_date": "2026-08-10", "source_type": "news"}]
        facts = self._run(
            "Acme lays off 500 employees  https://new.example/a\n"
            "Beta lays off 9 employees  https://new.example/b\n")
        self.assertEqual(facts["judged"], 1)
        self.assertEqual(facts["matched"], 1)
        self.assertEqual(facts["curated_recall_pct"], 100.0)
        self.assertEqual(facts["unparsed"], 1)

    def test_an_unreadable_api_is_unknown_and_leaves_the_denominator(self):
        cp.our_rows = lambda token, timeout=30: None
        facts = self._run("Acme lays off 500 employees  https://new.example/a")
        self.assertEqual(facts["unknown"], 1)
        self.assertEqual(facts["judged"], 0)
        self.assertIsNone(facts["curated_recall_pct"])

    def test_an_unparsed_line_can_still_teach_an_outlet(self):
        """The lesson histogram is deliberately WIDER than the denominator: an
        item we cannot score still names a host we do not read."""
        cp.our_rows = lambda token, timeout=30: []
        facts = self._run("Acme lays off 9 employees  https://new.example/a")
        self.assertEqual(facts["judged"], 0)
        self.assertEqual(facts["new_outlets"], 1)

    def test_the_two_percentages_have_different_denominators_on_purpose(self):
        """One unparsed item that names an unwired outlet: nothing to SCORE, so
        recall is undefined — but the curator did teach us something, so
        dependence is 100%. Collapsing these onto one denominator would either
        hide the lesson or invent a coverage miss."""
        cp.our_rows = lambda token, timeout=30: []
        facts = self._run("Acme lays off 9 employees  https://new.example/a")
        self.assertIsNone(facts["curated_recall_pct"])
        self.assertEqual(facts["taught_pct"], 100.0)

    def test_taught_pct_is_a_proportion_and_cannot_exceed_one_hundred(self):
        """One item can yield an outlet lesson AND a vocabulary lesson. Counting
        subjects over items made this 200% in the first version."""
        cp.our_rows = lambda token, timeout=30: []
        facts = self._run(
            "Acme ends its career residency programme for 500  https://new.example/a")
        self.assertGreaterEqual(facts["new_outlets"] + facts["new_terms"], 2)
        self.assertLessEqual(facts["taught_pct"], 100.0)


class DependenceTrend(unittest.TestCase):
    """"NEW" MUST MEAN NEW ACROSS RUNS, OR THE NUMBER CANNOT FALL.

    `taught_pct` is the measure of dependence on the curated source, and it is
    the half of the growth story recall cannot tell: recall rises when the
    digest gets easier as well as when we get better. For it to mean anything,
    a digest that names the same unwired outlet every week has to stop counting
    as teaching after the first time.

    The subjects are names, so the ledger that remembers them cannot be
    committed. It lives beside the worklist under the gitignored scratchpad, and
    only its COUNTS ever cross into the repo — which these tests also assert.
    """

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.known = self.tmp / "known.json"
        self._rows, self._email = cp.our_rows, cp._email
        self._state = cp.STATE_PATH
        cp.STATE_PATH = self.tmp / "state.json"
        cp._email = lambda report, facts: False
        cp.our_rows = lambda token, timeout=30: []

    def tearDown(self):
        cp.our_rows, cp._email, cp.STATE_PATH = self._rows, self._email, self._state

    def _run(self, text, n=1):
        wl = self.tmp / f"w{n}.txt"
        wl.write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            facts = cp.run(worklist_path=wl, denylist_path=self.tmp / "none.txt",
                           report_path=self.tmp / f"r{n}.md",
                           known_path=self.known, today=date(2026, 8, 18))
        return facts

    ITEM = "Acme lays off 500 employees  https://new.example/a"

    def test_the_same_outlet_twice_only_teaches_once(self):
        first = self._run(self.ITEM, 1)
        self.assertEqual(first["new_outlets"], 1)
        self.assertGreater(first["taught_pct"], 0)
        second = self._run(self.ITEM, 2)
        self.assertEqual(second["new_outlets"], 0,
                         "a gap suggested last run counted as teaching again")
        self.assertEqual(second["taught_pct"], 0.0)
        # It is still a live gap and must still be reported — just not as new.
        self.assertEqual(second["lessons_by_tier"].get("not_in_feed_set"), 1)

    def test_the_ledger_is_never_the_committed_file(self):
        self._run(self.ITEM, 1)
        self.assertTrue(self.known.exists())
        self.assertIn("new.example", self.known.read_text())
        committed = json.loads((self.tmp / "state.json").read_text())
        self.assertNotIn("new.example", json.dumps(committed))
        cp.assert_nameless(committed)

    def test_a_run_that_could_not_report_does_not_advance_the_ledger(self):
        """If the owner never saw the suggestion, it is not already suggested."""
        buf = io.StringIO()
        wl = self.tmp / "w.txt"
        wl.write_text(self.ITEM, encoding="utf-8")
        with redirect_stdout(buf):
            facts = cp.run(worklist_path=wl, denylist_path=self.tmp / "none.txt",
                           report_path=self.tmp / "nodir" / "sub" / "r.md",
                           known_path=self.known, today=date(2026, 8, 18))
        if not facts["reported"] and not facts["emailed"]:
            self.assertFalse(self.known.exists())

    def test_a_missing_ledger_reads_as_nothing_known(self):
        known = cp.read_known(self.tmp / "absent.json")
        self.assertEqual(known, {"outlet": set(), "vocabulary": set()})


class RecoveringAnInaccessibleEvent(unittest.TestCase):
    """"THE SOURCE IS PAYWALLED" AND "THE EVENT IS UNREACHABLE" ARE DIFFERENT CLAIMS.

    The first design conflated them and filed every paywalled miss as closed.
    That quietly wrote off the most learnable class of miss in the loop: a major
    exclusive is picked up within hours by wires, trade press and
    foreign-language outlets, and that follow-on coverage is public. Reading a
    news INDEX for it is ordinary discovery, not a workaround — the paywalled
    article still goes unread, and no content request is made to any outlet.

    Only "no accessible outlet reported it at all" is closed.
    """
    TRUSTED = {"wired.example"}
    TERMS = ("lays off", "job cuts")
    ITEM = {"headline": "Acme lays off 500", "domain": "paid.example", "closed": True}

    def _r(self, hits, item=None, suppressed=frozenset()):
        return cp.recover(item or self.ITEM, self.TRUSTED, self.TERMS,
                          suppressed, lambda token: hits)

    def test_accessible_coverage_from_an_unwired_outlet_is_recoverable(self):
        """The valuable case, and the likely common one."""
        tier, lessons = self._r([{"title": "Acme lays off 500", "outlet": "openwire.example"}])
        self.assertEqual(tier, "recoverable")
        self.assertEqual([l["subject"] for l in lessons], ["openwire.example"])

    def test_the_paywalled_outlet_is_never_the_lesson(self):
        """It stays in the refusal ledger. The ACCESSIBLE outlet gets wired."""
        _tier, lessons = self._r([{"title": "Acme lays off 500", "outlet": "openwire.example"}])
        self.assertNotIn("paid.example", [l["subject"] for l in lessons])

    def test_coverage_only_from_wired_outlets_is_our_vocabulary_not_the_paywall(self):
        tier, lessons = self._r([
            {"title": "Acme ends its career residency programme for 500",
             "outlet": "wired.example"}])
        self.assertEqual(tier, "vocabulary_gap")
        self.assertEqual([l["kind"] for l in lessons], ["vocabulary"])

    def test_wired_outlet_in_wording_we_search_is_neither_lesson(self):
        tier, lessons = self._r([{"title": "Acme lays off 500", "outlet": "wired.example"}])
        self.assertEqual(tier, "should_have_held")
        self.assertEqual(lessons, [])

    def test_no_accessible_coverage_at_all_is_the_only_closed_finding(self):
        tier, lessons = self._r([])
        self.assertEqual(tier, "unreachable")
        self.assertEqual(lessons, [])

    def test_a_failed_search_is_unknown_never_unreachable(self):
        tier, _ = self._r(None)
        self.assertEqual(tier, "recovery_unknown")

    def test_a_suppressed_outlet_cannot_be_recovered_into_a_source(self):
        """An aggregator carrying the story is not an outlet to wire."""
        tier, lessons = self._r([{"title": "Acme lays off 500", "outlet": "agg.example"}],
                                suppressed={"agg.example"})
        self.assertNotIn("agg.example", [l["subject"] for l in lessons])
        self.assertNotEqual(tier, "recoverable")

    def test_recovery_is_bounded_so_it_cannot_become_a_database_walk(self):
        """The trigger is an event we know occurred and do not hold. A cap makes
        "enumerate everything a curated list names" structurally impossible as
        well as forbidden."""
        self.assertLessEqual(cp.RECOVER_MAX, 40)
        self.assertGreaterEqual(cp.RECOVER_MAX, 1)


class RefusalLedger(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.path = pathlib.Path(tempfile.mkdtemp()) / "refusals.json"

    def test_the_reason_is_kept_per_domain(self):
        cp.merge_refusals(self.path, [{"domain": "paid.example", "reason": "paywall",
                                       "date": "2026-08-18"}])
        led = json.loads(self.path.read_text())
        self.assertEqual(led["paid.example"]["reason"], "paywall")

    def test_the_ledger_is_local_and_not_the_committed_file(self):
        self.assertEqual(pathlib.Path(cp.DEFAULT_REFUSALS).parent.name, "scratchpad")

    def test_the_marker_reason_is_parsed_off_the_line(self):
        items, _ = cp.parse_worklist("Acme lays off 500 [botwall]  https://p.example/a")
        self.assertTrue(items[0]["closed"])
        self.assertEqual(items[0]["reason"], "botwall")


class LocalOnly(unittest.TestCase):
    def test_the_default_worklist_is_inside_the_gitignored_scratchpad(self):
        """A workflow would need the worklist, and the worklist in the repo IS
        the leak. Every default path must sit under the one directory .gitignore
        excludes in its entirety."""
        ignored = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn("scratchpad/", [l.strip() for l in ignored])
        for path in (cp.DEFAULT_WORKLIST, cp.DEFAULT_DENYLIST, cp.DEFAULT_REPORT,
                     cp.DEFAULT_KNOWN):
            self.assertEqual(pathlib.Path(path).parent.name, "scratchpad",
                             f"{path} is not under the gitignored scratchpad")

    def test_no_workflow_runs_this_module(self):
        """Both extensions, because a guard that only knows `.yml` would wave
        through the first `.yaml` anyone adds — and this is the guard standing
        between the worklist and a runner."""
        wf = ROOT / ".github" / "workflows"
        files = list(wf.glob("*.yml")) + list(wf.glob("*.yaml"))
        self.assertGreater(len(files), 0, "no workflows found; this guard went vacuous")
        offenders = [p.name for p in files if "curated_probe" in p.read_text()]
        self.assertEqual(offenders, [], "curated_probe must not run in CI: a runner "
                                        "that can read the worklist is the leak")

    def test_a_missing_worklist_is_idle_not_a_failure(self):
        import tempfile
        missing = pathlib.Path(tempfile.mkdtemp()) / "nope.txt"
        buf = io.StringIO()
        with redirect_stdout(buf):
            facts = cp.run(worklist_path=missing, today=date(2026, 8, 18))
        self.assertEqual(facts["state"], "idle")
        cp.assert_nameless(facts)


class NoPaidCallsAndNoFetching(unittest.TestCase):
    """Both properties are read off the PARSE TREE, not off the text.

    A grep over the source cannot tell a call from the paragraph explaining why
    there is no call — the first version of this test failed on its own module
    docstring. Worse, it would have passed a file that discussed nothing and
    called everything. The AST answers the question actually being asked.
    """

    def _tree(self):
        import ast
        return ast.parse((ROOT / "railway" / "curated_probe.py").read_text())

    def test_the_module_imports_no_paid_path(self):
        import ast
        tree = self._tree()
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
                imported |= {a.name for a in node.names}
        for banned in ("openai", "spend", "metered_call", "extractor", "wp_poster"):
            self.assertNotIn(banned, imported,
                             f"{banned} imported into a loop documented as costing "
                             "nothing and storing nothing")

    def test_the_environment_it_reads_contains_no_model_key(self):
        """The full set of env vars this module can read, off the parse tree.

        Stated as an allowlist rather than a denylist of key names: the claim
        being made is "nothing here can spend", and that is only true if the
        whole environment surface is known, not if the three keys someone
        thought of are absent."""
        import ast
        allowed = {"WP_SITE_URL", "WP_API_KEY", "CURATED_WORKLIST",
                   "CURATED_DENYLIST", "CURATED_REPORT", "CURATED_KNOWN",
                   "CURATED_REFUSALS", "CURATED_RECOVER_MAX", "CURATED_MATCH_DAYS"}
        read = set()
        for node in ast.walk(self._tree()):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("get", "environ")
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "environ"):
                for arg in node.args[:1]:
                    if isinstance(arg, ast.Constant):
                        read.add(arg.value)
        self.assertTrue(read, "no env read found; this guard went vacuous")
        self.assertEqual(read - allowed, set(),
                         "this module reads an environment variable outside its "
                         "declared surface")

    def _request_urls(self):
        """(lineno, {names in the URL expression}) for every requests.* call."""
        import ast
        out = []
        for node in ast.walk(self._tree()):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not (isinstance(fn, ast.Attribute)
                    and isinstance(fn.value, ast.Name) and fn.value.id == "requests"):
                continue
            url = node.args[0] if node.args else None
            names = {n.id for n in ast.walk(url) if isinstance(n, ast.Name)} if url else set()
            out.append((node.lineno, names))
        return out

    def test_every_request_target_is_a_declared_endpoint(self):
        """Two endpoints exist and no third may appear: our own API (built from
        `site`, i.e. WP_SITE_URL) and the news INDEX (built by `_rss_url`, the
        Google News RSS this repo already runs as its free discovery source)."""
        calls = self._request_urls()
        self.assertGreater(len(calls), 0, "no requests call found; this guard went vacuous")
        for lineno, names in calls:
            self.assertTrue(names & {"site", "_rss_url"},
                            f"a requests call on line {lineno} targets neither our own "
                            "API nor the news index — it may reach an arbitrary host")

    def test_no_request_is_ever_built_from_an_item(self):
        """THE LOAD-BEARING ONE. We never fetch an outlet's page — not the
        paywalled one, not any other. Reading the index for who else covered an
        event is discovery; fetching the article would be the workaround the
        rules forbid, and this is what stops a later edit from quietly turning
        the first into the second."""
        for lineno, names in self._request_urls():
            for banned in ("url", "link", "domain", "item", "hit", "article"):
                self.assertNotIn(banned, names,
                                 f"a requests call on line {lineno} builds its URL from "
                                 f"{banned!r} — that is a content request to an outlet")

    def test_site_is_only_ever_our_configured_host(self):
        import ast
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "site" for t in node.targets):
                literals = {n.value for n in ast.walk(node.value)
                            if isinstance(n, ast.Constant) and isinstance(n.value, str)}
                self.assertIn("WP_SITE_URL", literals,
                              "`site` is assigned from something other than WP_SITE_URL")


if __name__ == "__main__":
    unittest.main()
