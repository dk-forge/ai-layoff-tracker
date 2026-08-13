"""THE GUARD THAT WATCHES THE COVERAGE COMPARISON MUST NOT LEAK IT.

WHY THIS TEST EXISTS, IN TWO HALVES.

THE FIRST HALF IS THE ORDINARY ONE. benchmark_freshness.py exists because the
coverage number against an independent national survey — the figure a journalist
tests first — had no guard at all, only a line in `ops_status.py [6]` reminding a
human to look at it. On 2026-08-12 the comparator side of that ratio had been
re-verified two days earlier while the paragraph carrying the headline
percentage was still the one typed on 2026-07-27, standing on a denominator that
had since moved. Nothing in the system could notice, and the tests below hold the
two ages that now do: how old the oldest comparator-side input is, and how many
hand-written ratio claims predate the last time the figure under them changed.
Both were confirmed to fire against the real file on the day they landed.

THE SECOND HALF IS THE REASON THIS FILE IS NOT ROUTINE. Half of that ratio is
competitor data, and the standing rule is absolute: no competitor or commercial
service name, and no competitor figure, in this repo, in a commit, in a workflow
log, in Actions output, or on any public page. A staleness checker reads the one
local file where those names and figures live. So the checker is one edit away,
forever, from being the thing that carries them into a log — and it would do it
quietly, in an ops line nobody reads closely, on a machine where the file is
present and the reviewer's is not.

Care does not survive that. Shape does. `read_stamps()` is the only function
that sees the file's text and it returns dates and integers; every printed line
is assembled from that structure. `test_no_payload_survives_the_parse` is the
assertion that keeps it true: it parses a fixture stuffed with invented service
names, invented figures and a URL, then asserts that not one of them appears in
any rendered line, in the verdict, or anywhere in the parsed structure's repr.
The fixture's names are fictional on purpose — a test that had to contain the
real ones to prove the real ones do not escape would be the leak it was written
to prevent.

If a future edit adds a field to `Stamps` that carries text, this test goes red
before the leak ships. That is the whole job.
"""
import datetime
import importlib.util
import pathlib
import sys
import unittest


def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError("test_benchmark_freshness: no repo root above %s" % here)


ROOT = _repo_root()
_spec = importlib.util.spec_from_file_location(
    "benchmark_freshness", ROOT / "railway" / "benchmark_freshness.py")
bf = importlib.util.module_from_spec(_spec)
sys.modules["benchmark_freshness"] = bf
_spec.loader.exec_module(bf)


TODAY = datetime.date(2026, 8, 12)


def _doc(our_side="2026-08-12", cells=(), prose=()):
    """Build a benchmark-shaped fragment out of stamps only."""
    parts = ['<div class="s-note" data-bench-stamp>auto-refresh OK %s</div>'
             % our_side if our_side else ""]
    parts.extend('<td class="r">%s</td>' % c for c in cells)
    parts.extend("<p>%s</p>" % p for p in prose)
    return "<html><body>%s</body></html>" % "".join(parts)


# Invented, and every digit of it too. An early draft of this file reached for
# realism and pasted the actual figures out of the local benchmark, which would
# have committed competitor numbers to the repo inside the very test that
# asserts they never escape. The fixture must be fiction all the way down.
FAKE_NAME = "Zarnabex Analytics"
FAKE_FIGURE = "111,222"
FAKE_FIGURE_2 = "333,444"
FAKE_URL = "https://zarnabex.example/blog/report-august"
LEAKY_DOC = (
    '<div class="s-note" data-bench-stamp>auto-refresh OK 2026-08-12</div>'
    '<td class="r" data-claim-url="%s" data-claim-comp="zData">%s zqfrom Mar 2026;'
    ' checked 2026-08-10<div class="figsub">%s, announced</div></td>'
    '<td class="r">%s <div class="figsub" data-claim-manual="1">manual - '
    'last hand-entered 2026-07-23</div></td>'
    '<p>Against %s we are 555,666 vs their %s (2026-07-27), i.e. 42%% '
    'coverage.</p>'
    % (FAKE_URL, FAKE_FIGURE_2, FAKE_NAME, FAKE_FIGURE, FAKE_NAME, FAKE_FIGURE)
)
# Identifying payload only. Deliberately NOT ordinary words like "coverage" or
# "announced": those appear in the checker's own static copy, where they are
# vocabulary rather than anything read out of the file, and asserting on them
# would fail on prose the module always prints and teach the next person to
# weaken the assertion.
SECRETS = (FAKE_NAME, "Zarnabex", "zarnabex", FAKE_FIGURE, FAKE_FIGURE_2,
           FAKE_URL, "555,666", "zData", "zqfrom")


class NoPayloadEscapes(unittest.TestCase):
    """The leak boundary, asserted rather than assumed."""

    def test_no_payload_survives_the_parse(self):
        result = bf.check(text=LEAKY_DOC, today=TODAY)
        surface = "\n".join(result.lines) + "\n" + result.verdict
        for secret in SECRETS:
            self.assertNotIn(
                secret, surface,
                "benchmark_freshness leaked %r into its printed output. Every "
                "line must be built from dates and counts only." % secret)

    def test_the_parsed_structure_carries_no_text(self):
        stamps = bf.read_stamps(LEAKY_DOC)
        blob = repr(stamps.__dict__)
        for secret in SECRETS:
            self.assertNotIn(
                secret, blob,
                "Stamps is carrying %r out of the benchmark. It may hold dates "
                "and integers and nothing else." % secret)
        for _kind, day in stamps.comparator:
            self.assertIsInstance(day, datetime.date)
        for day in stamps.narrative:
            self.assertIsInstance(day, datetime.date)

    def test_the_fixture_would_have_caught_a_leak(self):
        """Guard the guard: prove SECRETS are actually present to be leaked."""
        for secret in SECRETS:
            self.assertIn(secret, LEAKY_DOC,
                          "%r is not in the fixture, so asserting it does not "
                          "escape proves nothing." % secret)


class ComparatorAge(unittest.TestCase):
    """A ratio is exactly as fresh as its oldest input."""

    def test_recent_check_is_fresh(self):
        doc = _doc(cells=["checked 2026-08-10"])
        self.assertEqual(bf.check(text=doc, today=TODAY).verdict, bf.FRESH)

    def test_one_missed_monday_is_due_not_stale(self):
        doc = _doc(cells=["checked 2026-08-04"])  # 8 days
        self.assertEqual(bf.check(text=doc, today=TODAY).verdict, bf.DUE)

    def test_two_missed_mondays_is_stale(self):
        doc = _doc(cells=["checked 2026-07-28"])  # 15 days
        self.assertEqual(bf.check(text=doc, today=TODAY).verdict, bf.STALE)

    def test_the_oldest_input_governs_not_the_freshest(self):
        """The defect this guard was built for: one fresh cell speaking for all.

        A weekly check that confirms one comparator input and leaves a
        hand-maintained one untouched for a month must not read as fresh. The
        stale half is still in the ratio.
        """
        doc = _doc(cells=["checked 2026-08-10",
                          "manual - last hand-entered 2026-07-01"])
        result = bf.check(text=doc, today=TODAY)
        self.assertEqual(result.verdict, bf.STALE)
        self.assertEqual(result.stamps.oldest_comparator,
                         datetime.date(2026, 7, 1))

    def test_a_failed_check_does_not_count_as_a_verification(self):
        """A check that ran and confirmed nothing left the old value in place.

        Stamping the failure must not reset the age — the input is as old as
        the last time something actually confirmed it.
        """
        doc = _doc(cells=["checked 2026-07-01; last check failed 2026-08-10"])
        result = bf.check(text=doc, today=TODAY)
        self.assertEqual(result.stamps.oldest_comparator,
                         datetime.date(2026, 7, 1))
        self.assertEqual(result.verdict, bf.STALE)


class SupersededQuotedRatios(unittest.TestCase):
    """The 2026-07-27 case: a percentage nobody recomputed."""

    def test_claim_older_than_the_last_recheck_is_stale(self):
        doc = _doc(cells=["checked 2026-08-10"],
                   prose=["we are at 97% coverage (2026-07-27)"])
        result = bf.check(text=doc, today=TODAY)
        self.assertEqual(result.verdict, bf.STALE)
        self.assertEqual(result.stamps.superseded_narrative(),
                         [datetime.date(2026, 7, 27)])

    def test_claim_at_or_after_the_recheck_is_not_flagged(self):
        doc = _doc(cells=["checked 2026-08-10"],
                   prose=["we are at 97% coverage (2026-08-10)"])
        result = bf.check(text=doc, today=TODAY)
        self.assertEqual(result.stamps.superseded_narrative(), [])
        self.assertEqual(result.verdict, bf.FRESH)

    def test_a_claim_citing_several_dates_takes_its_oldest(self):
        doc = _doc(cells=["checked 2026-08-10"],
                   prose=["97% on the 2026-08-11 pull against a 2026-06-01 "
                          "baseline"])
        result = bf.check(text=doc, today=TODAY)
        self.assertEqual(result.stamps.superseded_narrative(),
                         [datetime.date(2026, 6, 1)])

    def test_prose_without_a_percentage_is_not_a_ratio_claim(self):
        doc = _doc(cells=["checked 2026-08-10"],
                   prose=["the sweep ran on 2026-01-01 and stored 12 rows"])
        self.assertEqual(bf.check(text=doc, today=TODAY).stamps.narrative, [])


class NeverASilentPass(unittest.TestCase):
    """PASS, FAIL and UNKNOWN are three states. Absence of a signal is not a pass."""

    def test_missing_file_is_unknown_not_fresh(self):
        result = bf.check(file_missing=True, today=TODAY)
        self.assertEqual(result.verdict, bf.UNKNOWN)
        self.assertFalse(result.needs_a_human)
        self.assertIn("NOT A PASS", "\n".join(result.lines))

    def test_absent_benchmark_path_resolves_to_unknown(self):
        result = bf.check_file(path=ROOT / "no" / "such" / "file.html",
                               today=TODAY)
        self.assertEqual(result.verdict, bf.UNKNOWN)

    def test_a_file_with_no_comparator_stamp_is_unknown(self):
        """Our side refreshed daily says nothing about the other half."""
        result = bf.check(text=_doc(), today=TODAY)
        self.assertEqual(result.verdict, bf.UNKNOWN)

    def test_unknown_exits_3_and_stale_exits_2(self):
        self.assertEqual(bf.check(file_missing=True, today=TODAY).exit_code(), 3)
        stale = bf.check(text=_doc(cells=["checked 2026-06-01"]), today=TODAY)
        self.assertEqual(stale.exit_code(), 2)
        fresh = bf.check(text=_doc(cells=["checked 2026-08-10"]), today=TODAY)
        self.assertEqual(fresh.exit_code(), 0)

    def test_a_malformed_stamp_is_dropped_rather_than_trusted(self):
        doc = _doc(cells=["checked 2026-13-45", "checked 2026-08-10"])
        stamps = bf.read_stamps(doc)
        self.assertEqual([d for _k, d in stamps.comparator],
                         [datetime.date(2026, 8, 10)])


class TheGuardIsWiredIn(unittest.TestCase):
    """A checker nothing calls is a file, not a guard."""

    def test_ops_status_runs_it(self):
        src = (ROOT / "railway" / "ops_status.py").read_text(encoding="utf-8")
        self.assertIn("benchmark_freshness", src,
                      "ops_status.py must run the benchmark freshness check at "
                      "session start, or [6] is a reminder again.")

    def test_the_benchmark_stays_out_of_the_repo(self):
        """The data must never be committable, however this check evolves."""
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("scratchpad/", ignored)
        self.assertFalse((ROOT / "railway" / "bm-live.html").exists())


if __name__ == "__main__":
    unittest.main()
