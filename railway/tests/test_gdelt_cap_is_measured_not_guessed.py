"""A full first PAGE is not a truncated ANSWER.

`Reach.note_query` decided a GDELT window was capped by inferring it:
`returned >= max_records`. That is sound for the public DOC 2.0 API, which
answers one request with at most `maxrecords=250` rows and never pages. It
stopped being sound for the BigQuery mirror on 2026-08-26, when #223 turned
MIRROR_LIMIT into a PAGE size and gave the mirror `query_window_walk`, a
deterministic (date, url) cursor that walks the window to exhaustion across up
to MAX_PAGES pages.

The walk returns `complete`. `_collect_mirror` threw it away and let the
inference guess instead, so the answer was wrong every run for six days:

    to 08-25   returned == 900 exactly   genuinely truncated by the old LIMIT
    08-27      returned 7339             walked to the bottom, reported capped
    08-28      returned 7183             walked to the bottom, reported capped
    08-29      returned 5415             walked to the bottom, reported capped
    08-30      returned 3594             walked to the bottom, reported capped
    08-31      returned 5123             walked to the bottom, reported capped

A walk that really hit its ceiling would have returned 40 * 900 = 36,000.
Meanwhile ops_status [2d] told every session "coverage below the cut was never
offered" about windows where all of it had been offered -- on the same report
as the real, unfixed abandoned-window signal, which is how a true alarm gets
read as more of the same noise.

THE FIX IS TO STOP GUESSING, NOT TO RAISE A NUMBER. `note_query` takes an
explicit `truncated` fact, the caller that knows it passes it, and the
inference stays exactly as it was for the callers that genuinely cannot say --
which is the case these tests spend the most assertions on, because a change
that quietly stopped reporting a real cap would be far worse than the bug.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gdelt_reach


def _calls_to(source: str, opener: str, must_contain: str) -> list[str]:
    """Whole `opener(...)` calls containing `must_contain`, brackets matched.

    A non-greedy `.*?\)` regex stops at the FIRST close paren, which for
    `note_query("mirror", len(arts), ...)` is the one belonging to `len(` --
    so it reads a third of the call and passes on the part with no argument in
    it. That is the same class of mistake as the defect under test: a
    measurement taken of the wrong thing.
    """
    out = []
    at = source.find(opener)
    while at != -1:
        i = at + len(opener) - 1
        depth = 0
        for j in range(i, len(source)):
            if source[j] == "(":
                depth += 1
            elif source[j] == ")":
                depth -= 1
                if depth == 0:
                    call = source[at:j + 1]
                    if must_contain in call:
                        out.append(call)
                    break
        at = source.find(opener, at + 1)
    return out


def _fresh():
    return gdelt_reach.Reach()


def _only(reach):
    assert len(reach.queries) == 1, reach.queries
    return reach.queries[0]


class TheInferenceStillHoldsWhereItIsSound(unittest.TestCase):
    """The public API pages nothing, so a full answer IS a truncated one.

    Every assertion here passes both before and after the change. They are the
    ones that would catch a "fix" that simply stopped reporting caps.
    """

    def test_a_public_query_at_maxrecords_is_capped(self):
        reach = _fresh()
        reach.note_query("broad", 250, 250)
        self.assertTrue(_only(reach)["capped"])

    def test_a_public_query_under_maxrecords_is_not(self):
        reach = _fresh()
        reach.note_query("broad", 249, 250)
        self.assertFalse(_only(reach)["capped"])

    def test_over_the_ceiling_still_counts_as_capped(self):
        reach = _fresh()
        reach.note_query("broad", 251, 250)
        self.assertTrue(_only(reach)["capped"])

    def test_an_abandoned_window_is_not_a_capped_one(self):
        reach = _fresh()
        reach.note_query("broad", None, 250)
        row = _only(reach)
        self.assertTrue(row["abandoned"])
        self.assertFalse(row["capped"])
        self.assertEqual(row["returned"], -1, "abandoned must not read as zero")


class AWalkedWindowSaysSoForItself(unittest.TestCase):
    def test_a_complete_walk_is_not_capped_however_many_rows_it_returned(self):
        """The regression. MUTATION: drop the `truncated` branch from
        note_query, or stop passing it from _collect_mirror, and this fails."""
        reach = _fresh()
        reach.note_query("mirror", 5123, 900, truncated=False)
        self.assertFalse(
            _only(reach)["capped"],
            "5123 rows across a 900-row PAGE size is a window walked to the "
            "bottom, not a truncated one")

    def test_an_incomplete_walk_is_capped_even_at_a_partial_page(self):
        """The other direction, and the one that matters more.

        A walk can stop at MAX_PAGES on a page that is not full. The inference
        would call that complete; the fact says otherwise, and the fact wins.
        """
        reach = _fresh()
        reach.note_query("mirror", 35_500, 900, truncated=True)
        self.assertTrue(_only(reach)["capped"])

    def test_an_explicit_fact_overrides_the_inference_both_ways(self):
        reach = _fresh()
        reach.note_query("mirror", 900, 900, truncated=False)
        reach.note_query("mirror", 12, 900, truncated=True)
        self.assertEqual([q["capped"] for q in reach.queries], [False, True])

    def test_omitting_the_fact_leaves_the_old_behaviour_exactly(self):
        """Callers that cannot say must be untouched by this."""
        for returned, expected in ((900, True), (899, False), (5123, True)):
            reach = _fresh()
            reach.note_query("mirror", returned, 900)
            self.assertEqual(_only(reach)["capped"], expected,
                             f"returned={returned}")

    def test_the_limit_is_still_recorded(self):
        """It is a true fact about the request and [2d] prints it."""
        reach = _fresh()
        reach.note_query("mirror", 5123, 900, truncated=False)
        self.assertEqual(_only(reach)["max_records"], 900)


class TheCallerThatKnowsActuallyPassesIt(unittest.TestCase):
    SOURCE = (Path(__file__).resolve().parents[1] / "sources" / "gdelt.py"
              ).read_text(encoding="utf-8")

    def test_collect_mirror_forwards_the_walk_s_own_verdict(self):
        block = self.SOURCE[self.SOURCE.index("def _collect_mirror"):]
        block = block[:block.index("\n\ndef ")]
        self.assertIn("truncated=not complete", block,
                      "_collect_mirror computes `complete` and then lets "
                      "note_query guess instead, which is the whole defect")

    def test_the_walk_s_verdict_is_not_discarded_anywhere_else(self):
        """Any other mirror note_query has to carry the fact too.

        Read as whole CALLS, not lines: the one in _collect_mirror is wrapped
        across two, and a line-by-line scan would pass it while reading only
        the half without the argument in it.
        """
        calls = _calls_to(self.SOURCE, 'note_query(', '"mirror"')
        self.assertTrue(calls, "no mirror note_query found at all")
        for call in calls:
            self.assertIn("truncated", call, " ".join(call.split()))


class TheReportDescribesTheTestItActuallyRuns(unittest.TestCase):
    SOURCE = (Path(__file__).resolve().parents[1] / "ops_status.py"
              ).read_text(encoding="utf-8")

    def test_the_cap_line_does_not_claim_an_exact_equality(self):
        self.assertNotIn("returned exactly maxrecords", self.SOURCE,
                         "the test is >=, and for the mirror it is now an "
                         "explicit fact rather than a comparison at all; the "
                         "line described neither")


if __name__ == "__main__":
    unittest.main()
