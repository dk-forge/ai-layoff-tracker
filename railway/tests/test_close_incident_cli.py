"""The one command a human is REQUIRED to run, and both of its halves were broken.

`close_incident` is the deliberate human-in-the-loop gate on this repo: a
failing headline slice reports FAIL until a person closes it with a reviewer, a
reason, THE AFFECTED ROW IDs and an explicit replacement baseline. The function
itself was careful. Its command line was not, and both defects were found by
running it for real on 2026-08-12 to close `us_all_time`.

    1. `--rows` SILENTLY KEPT THE FIRST ID AND DROPPED THE REST. It read
       `_arg(argv, "--rows", "")`, which takes the single token after the flag
       and then splits it on commas and spaces. `--rows 114335,113529,64351`
       worked. `--rows 114335 113529 64351`, which is what a person types,
       recorded ONLY 114335 and exited zero. The incident was about three ERM
       rows and the ledger claimed one.

       This is the worst field in the record to truncate quietly. It exists
       because "if they cannot be named, the cause has not been found", so a
       silently partial list is a closed incident asserting a finding nobody
       made, in the file that is the audit trail for exactly that.

    2. EVERY SUCCESSFUL CLOSE CRASHED AFTER WRITING. The summary printed
       `closed['slice']`; the stored record has `label` and no `slice`, so the
       CLI wrote the ledger and the replacement baseline, then raised KeyError
       and exited non-zero. Success looked like failure, which invites the
       reviewer to run it again.

Both are pinned by DRIVING main() against a temp ledger and reading what was
stored, not by inspecting the parser. The first defect was invisible to every
possible source check: the code did exactly what it said, on one token.
"""
import io
import json
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import data_integrity as di  # noqa: E402


OPEN_LEDGER = {
    "closed": [],
    "open": {
        "us_all_time": {
            "label": "United States jobs, all time",
            "opened_at": "2026-08-10T19:36:59Z",
            "detail": "+93,210 jobs over 3.0d on +18 entries",
            "baseline_at_open": {"jobs": 6968670, "entries": 43341,
                                 "captured_at": "2026-08-07T18:23:51Z"},
            "observed_at_open": {"jobs": 7061880, "entries": 43359,
                                 "captured_at": "2026-08-10T19:36:59Z"},
        }
    },
}

ROWS = ["114335", "113529", "64351"]


class TheCloseCommandRecordsWhatTheReviewerTyped(unittest.TestCase):

    def _close(self, row_argv):
        """Drive main() end to end against a throwaway ledger."""
        tmp = Path(tempfile.mkdtemp())
        inc, base = tmp / "headline_incidents.json", tmp / "headline_baseline.json"
        inc.write_text(json.dumps(OPEN_LEDGER))
        base.write_text(json.dumps({}))
        real_inc, real_base = di.INCIDENTS_PATH, di.BASELINE_PATH
        di.INCIDENTS_PATH, di.BASELINE_PATH = inc, base
        argv = ["--close-incident", "us_all_time",
                "--reviewed-by", "dak",
                "--reason", "Traced to the daily spot-check relabelling three ERM "
                            "rows off Multiple countries; reverted and the mechanism "
                            "is bounded. This reason is long enough to pass the floor.",
                *row_argv,
                "--replacement-jobs", "6978103",
                "--replacement-entries", "43368"]
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                code = di.main(argv)
        finally:
            di.INCIDENTS_PATH, di.BASELINE_PATH = real_inc, real_base
        return code, buf.getvalue(), json.loads(inc.read_text())

    def test_space_separated_rows_are_all_recorded(self):
        """The defect, in the spelling a person actually types."""
        code, out, ledger = self._close(["--rows", "114335", "113529", "64351"])
        stored = ledger["closed"][-1]["affected_row_ids"]
        self.assertEqual(
            stored, ROWS,
            "the reviewer named 3 rows and the ledger stored %d (%r). A partial "
            "--rows is a closed incident claiming a finding nobody made."
            % (len(stored), stored))
        self.assertEqual(code, 0)

    def test_comma_separated_rows_still_work(self):
        """The old documented spelling must not break: an invocation copied from
        the runbook has to keep recording what it says."""
        _, _, ledger = self._close(["--rows", "114335,113529,64351"])
        self.assertEqual(ledger["closed"][-1]["affected_row_ids"], ROWS)

    def test_the_quoted_spelling_still_works(self):
        """The form the old parser was actually written for."""
        _, _, ledger = self._close(["--rows", "114335 113529 64351"])
        self.assertEqual(ledger["closed"][-1]["affected_row_ids"], ROWS)

    def test_rows_stops_at_the_next_flag(self):
        """Greedy collection must not swallow the rest of the command line and
        record --replacement-jobs as a row id."""
        _, _, ledger = self._close(["--rows", "114335", "113529", "64351"])
        stored = ledger["closed"][-1]["affected_row_ids"]
        for bad in ("--replacement-jobs", "6978103", "--replacement-entries", "43368"):
            self.assertNotIn(bad, stored,
                             "--rows swallowed a later flag or its value: %r" % stored)

    def test_a_successful_close_exits_zero_and_says_so(self):
        """It wrote the ledger, then raised KeyError on closed['slice'] and
        exited non-zero. Success that looks like failure gets re-run."""
        code, out, _ = self._close(["--rows", "114335", "113529", "64351"])
        self.assertEqual(code, 0, "a successful close must exit 0")
        self.assertIn("CLOSED", out, "the close printed no confirmation: %r" % out)
        self.assertIn("us_all_time", out,
                      "the confirmation does not name the slice it closed: %r" % out)
        self.assertIn("dak", out, "the confirmation does not name the reviewer")

    def test_the_confirmation_lists_every_row_it_stored(self):
        """The printed summary is the only place a reviewer can catch a
        truncated --rows, which is exactly how the original defect hid."""
        _, out, ledger = self._close(["--rows", "114335", "113529", "64351"])
        for rid in ledger["closed"][-1]["affected_row_ids"]:
            self.assertIn(rid, out,
                          "row %s was stored but not shown back to the reviewer: %r"
                          % (rid, out))

    def test_an_empty_rows_list_is_still_refused(self):
        """The gate itself must survive this change: no rows, no close."""
        code, out, ledger = self._close([])
        self.assertEqual(code, 2, "a close with no rows must be refused")
        self.assertIn("REFUSED", out)
        self.assertIn("us_all_time", ledger["open"],
                      "the incident was closed despite being refused")


if __name__ == "__main__":
    unittest.main()
