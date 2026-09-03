"""A brake that does not record its own limit cannot be audited.

THE DEFECT. `ops_status.py [2a]` judges each run against the ceiling THAT RUN
ran under, which `spend.record_job_run()` writes into the entry as
`ceiling_usd` (added 2026-08-14, commit 8e976ca). That closed the false alarm
on `edgar-history-sweep`, whose $0.2721 run had an operator's authorised $0.40
override and was being reported against the table's named $0.150.

It did NOT close it for `railway-cron`, and railway-cron is the largest metered
job in the table ($0.086/day on 2026-08-15, ~2x the next). Railway can neither
commit nor be log-harvested, so its ledger entry travels a different road than
every other job's: cron.py POSTs it to the keyed /tracker-meta endpoint, db.php
stores a WHITELISTED subset of the fields, and `spend.harvest_railway_runs()`
copies a SECOND, separately hand-written list of keys back out. Both lists were
written before `ceiling_usd` existed and neither was updated with it, so the
field is dropped twice on a round trip that reports no error. Every
railway-cron entry in the committed ledger records a cost with no record of
what the run was allowed to spend — not for a while, but permanently and by
construction. Measured on 2026-08-15: 5 of 5 railway-cron entries since
2026-08-12 carry `ceiling_usd: None`, including runs hours after the fix.

Three hand-written field lists have to agree and nothing made them. This file
is what makes them. The generic case matters more than the specific one: the
next audit field added to the ledger takes the same road, and a silent drop is
exactly how this one arrived.
"""
import datetime
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import spend  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SPEND_SRC = (ROOT / "railway/spend.py").read_text(encoding="utf-8")
DB_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text(
    encoding="utf-8")


def _add_spend_run_block() -> str:
    """The body of db.php's `add_spend_run` handler — the server-side whitelist.

    Bounded by the `if (!empty($body['add_spend_run'])` test and the line that
    appends the built record, so a field is 'persisted' only if it is named
    between those two points.
    """
    start = DB_PHP.find("$body['add_spend_run']")
    assert start > 0, "db.php no longer handles add_spend_run"
    end = DB_PHP.find("$meta['spend_runs'][] = $rec;", start)
    assert end > start, "could not find the end of the add_spend_run handler"
    return DB_PHP[start:end]


def _harvest_key_list() -> set:
    """The keys `harvest_railway_runs()` copies back out of /tracker-meta."""
    src = SPEND_SRC[SPEND_SRC.find("def harvest_railway_runs"):]
    src = src[:src.find("\ndef ", 1)]
    m = re.search(r"for k in\s*\(([^)]*)\)", src, re.S)
    assert m, "harvest_railway_runs no longer copies an explicit key list"
    return set(re.findall(r'"([a-z_]+)"', m.group(1)))


# Fields `record_job_run()` writes that deliberately do NOT survive the Railway
# road, each with the reason it cannot. Anything else it writes MUST make the
# round trip, or this file goes red rather than the ledger going quiet.
NOT_PERSISTED = {
    # GitHub Actions re-run bookkeeping. Railway has no run attempts: its
    # run_id is minute-stamped by cron.py and a re-post replaces in place.
    "attempt",
}


class LedgerFieldsSurviveTheRailwayRoundTrip(unittest.TestCase):
    """Whatever the ledger records, the road Railway takes must carry."""

    def setUp(self):
        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        self._env = {k: os.environ.get(k) for k in
                     ("ALT_JOB", "ALT_RUN_CEILING_USD", "ALT_PAID_READS",
                      "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                      "ALT_RUN_SPEND_FILE", "WP_SITE_URL", "WP_API_KEY")}
        for k in self._env:
            os.environ.pop(k, None)
        self.addCleanup(self._restore)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["ALT_RUN_SPEND_FILE"] = str(Path(self.tmp.name) / "run.json")

    def _restore(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _cron_entry(self) -> dict:
        """The entry cron.py actually builds, ceiling and all."""
        os.environ["ALT_JOB"] = "railway-cron"
        spend.record_usage("deepseek/deepseek-chat",
                           {"prompt_tokens": 1000, "completion_tokens": 100})
        with redirect_stdout(StringIO()):
            entry = spend.record_job_run(
                items=255, stored=3, job="railway-cron",
                run_id="railway-" + datetime.datetime.now(
                    datetime.timezone.utc).strftime("%Y%m%dT%H%M"))
        entry["gate_mode"] = "live"
        return entry

    def test_the_ceiling_is_in_the_entry_cron_posts(self):
        """The premise. If this fails the defect is upstream of the road."""
        entry = self._cron_entry()
        self.assertIsNotNone(
            entry.get("ceiling_usd"),
            "record_job_run() did not write ceiling_usd — a run recording a "
            "cost with no record of what it was allowed to spend")

    def test_wordpress_persists_every_field_the_ledger_records(self):
        missing = sorted(
            k for k in self._cron_entry()
            if k not in NOT_PERSISTED and f"'{k}'" not in _add_spend_run_block())
        self.assertEqual(
            missing, [],
            "db.php's add_spend_run whitelist silently DROPS ledger field(s) "
            f"{missing}. The Railway cron posts them and the server throws "
            "them away without an error, so railway-cron's committed ledger "
            "entry is missing them for good. Add them to the whitelist in "
            "wordpress-plugin/ai-layoff-tracker/includes/db.php (and bump "
            "ALT_VERSION), or name them in NOT_PERSISTED with the reason they "
            "cannot travel.")

    def test_the_harvest_reads_back_every_field_the_ledger_records(self):
        missing = sorted(
            k for k in self._cron_entry()
            if k not in NOT_PERSISTED and k not in _harvest_key_list())
        self.assertEqual(
            missing, [],
            "spend.harvest_railway_runs() silently DROPS ledger field(s) "
            f"{missing} when reading /tracker-meta back into the committed "
            "ledger. The server can store them and the harvest still will not "
            "carry them. Add them to the key list in harvest_railway_runs(), "
            "or name them in NOT_PERSISTED with the reason they cannot travel.")

    def test_a_harvested_railway_entry_still_knows_its_ceiling(self):
        """End to end on the Python half: what /tracker-meta returns is what
        lands in the ledger, with the ceiling intact and numerically equal."""
        posted = self._cron_entry()
        os.environ["WP_SITE_URL"] = "https://example.invalid/blog"
        os.environ["WP_API_KEY"] = "test-key"
        payload = json.dumps({"spend_runs": [posted]}).encode()
        resp = mock.MagicMock()
        resp.read.return_value = payload
        resp.__enter__ = lambda s: s
        resp.__exit__ = lambda s, *a: False
        with mock.patch("urllib.request.urlopen", return_value=resp):
            with redirect_stdout(StringIO()):
                harvested = spend.harvest_railway_runs()
        self.assertEqual(len(harvested), 1, "the harvest lost the run entirely")
        self.assertEqual(
            harvested[0].get("ceiling_usd"), posted["ceiling_usd"],
            "a railway-cron run reached the committed ledger without the "
            "ceiling it ran under, so ops_status [2a] can never judge the "
            "largest metered job in the table against any ceiling at all")


class UnjudgeableRunsAreNotPasses(unittest.TestCase):
    """[2a] must be able to judge a job that has no NAMED ceiling.

    railway-cron is deliberately absent from JOB_RUN_CEILINGS_USD — it keeps
    the global RUN_CEILING_USD default. That is the whole reason its entry has
    to carry its own number: with no named ceiling and no recorded one, [2a]
    has nothing to compare against and skips the run in silence, which is the
    absence of a signal being read as a pass.
    """

    OPS = (ROOT / "railway/ops_status.py").read_text(encoding="utf-8")

    def test_railway_cron_keeps_the_global_default_rather_than_a_named_one(self):
        self.assertNotIn("railway-cron", spend.JOB_RUN_CEILINGS_USD,
                         "railway-cron gained a named ceiling; this test's "
                         "premise moved, re-read it before deleting it")
        self.assertGreater(spend.RUN_CEILING_USD, 0)

    def test_the_dashboard_judges_a_run_by_the_ceiling_it_recorded(self):
        """A run is judged ONLY against the ceiling it RECORDED. A run that
        recorded none is UNKNOWN — never judged against the table's current
        named number, which it may never have run under (an authorised dispatch
        override, or a pre-recording relic). Pinned by shape so the fallback to
        the named ceiling cannot creep back in and re-manufacture the
        edgar-history-sweep false alarm (an authorised $0.40 override reported
        against the named $0.150)."""
        # Pinned BEHAVIOURALLY since 2026-09-03, when the judgement moved into
        # spend.judge_overshoot() so ops_status, the digest and the tests read
        # an overshoot the same way. The property is unchanged: an entry with
        # no ceiling of its own is UNRECORDED, whatever the table currently
        # says, so the edgar-history-sweep false alarm (an authorised $0.40
        # override reported against the named $0.150) cannot come back.
        named = spend.JOB_RUN_CEILINGS_USD["edgar-history-sweep"]
        e = {"job": "edgar-history-sweep", "date": "2026-08-12",
             "cost_usd": named * 2, "calls": 200}
        verdict, why = spend.judge_overshoot(e)
        self.assertEqual(
            verdict, spend.OVERSHOOT_UNRECORDED,
            "a run that recorded no ceiling was judged against one anyway")
        self.assertIn("UNKNOWN", why)
        self.assertEqual(
            spend.judge_overshoot(dict(e, ceiling_usd=named * 3))[0],
            spend.OVERSHOOT_OK,
            "a run under an authorised override must be judged against THAT "
            "override, not the table's named number")
        self.assertIn(
            "judge_overshoot", self.OPS,
            "ops_status [2a] stopped delegating to the one definition and is "
            "judging overshoot with a rule of its own again")


if __name__ == "__main__":
    unittest.main()
