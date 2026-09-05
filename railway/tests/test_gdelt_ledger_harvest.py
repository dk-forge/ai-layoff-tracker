"""The committed GDELT work ledger is written by exactly one thing, daily.

ops_status [2f] found railway/gdelt_work_ledger.json NEVER_USED on 2026-09-05:
the live cron had kept the ledger on the host since 2026-08-28 and no job
brought it back, so reviewers read an empty file while the host held 77 slots.
These pin the harvester that closes that: it writes the live slots into the
file, it leaves the file untouched and says UNKNOWN when the host cannot be
read, and the daily workflow runs it and commits the file.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.join(HERE, "..")
REPO = os.path.join(RAILWAY, "..")
sys.path.insert(0, RAILWAY)

import gdelt_ledger_harvest  # noqa: E402
from sources import gdelt  # noqa: E402


def _stamp(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _live_slots():
    end = datetime.now(timezone.utc) - timedelta(hours=6)
    start = end - timedelta(hours=36)
    key = f"segment|deadbeef00|{_stamp(start)}|{_stamp(end)}"
    return {key: {"family": "segment", "status": "queued",
                  "window_start": _stamp(start), "window_end": _stamp(end),
                  "attempts": 2}}


class _Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "gdelt_work_ledger.json")
        gdelt._REMOTE_LEDGER_READ = False
        self.addCleanup(setattr, gdelt, "_REMOTE_LEDGER_READ", False)

    def run_harvest(self, remote_returns):
        out = io.StringIO()
        with mock.patch.object(gdelt, "_remote_tracker_meta",
                               return_value=remote_returns) as remote, \
                redirect_stdout(out):
            rc = gdelt_ledger_harvest.main(self.path)
        return rc, out.getvalue(), remote


class TheFileGainsTheLiveSlots(_Harness):
    def test_live_slots_land_in_the_committed_file(self):
        slots = _live_slots()
        rc, out, _remote = self.run_harvest({"gdelt_ledger": slots})
        self.assertEqual(rc, 0)
        with open(self.path, encoding="utf-8") as fh:
            written = json.load(fh)
        self.assertEqual(set(written["slots"]), set(slots))
        self.assertIn("1 slot(s) written", out)

    def test_it_never_pushes_back_to_the_host(self):
        """The file is the copy; the host is the source. One direction only."""
        _rc, _out, remote = self.run_harvest({"gdelt_ledger": _live_slots()})
        bodies = [c.kwargs.get("body") if c.kwargs else (c.args[0] if c.args else None)
                  for c in remote.call_args_list]
        self.assertTrue(remote.call_args_list, "the host was never read")
        self.assertTrue(all(not b for b in bodies), bodies)

    def test_output_carries_counts_and_no_slot_key(self):
        slots = _live_slots()
        _rc, out, _remote = self.run_harvest({"gdelt_ledger": slots})
        for key in slots:
            self.assertNotIn(key, out)
        self.assertIn("queued=1", out)


class AnUnreadableHostChangesNothing(_Harness):
    def test_the_file_is_byte_identical_and_the_run_says_unknown(self):
        before = json.dumps({"slots": {"old|x|20260101T000000Z|20260102T000000Z": {
            "status": "queued", "window_end": "20260102T000000Z"}}}, indent=2) + "\n"
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(before)
        rc, out, _remote = self.run_harvest(None)
        self.assertEqual(rc, 0, "a host hiccup is UNKNOWN, not a red run")
        with open(self.path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)
        self.assertIn("UNKNOWN", out)


class TheDailyWorkflowRunsItAndCommitsTheFile(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPO, ".github", "workflows",
                               "openrouter-balance-check.yml"), encoding="utf-8") as fh:
            self.yml = fh.read()

    def test_the_step_exists_with_the_host_credentials(self):
        self.assertIn("gdelt_ledger_harvest.py", self.yml)
        step = self.yml.split("Harvest the live GDELT work ledger", 1)[1]
        step = step.split("- name:", 1)[0]
        self.assertIn("WP_API_KEY", step)
        self.assertIn("WP_SITE_URL", step)

    def test_the_commit_step_adds_the_ledger_file(self):
        commit = self.yml.split("Commit today's balance reading", 1)[1]
        add_line = [l for l in commit.splitlines() if "git add" in l]
        self.assertTrue(add_line, "no git add in the commit step")
        self.assertIn("railway/gdelt_work_ledger.json", add_line[0])


if __name__ == "__main__":
    unittest.main()
