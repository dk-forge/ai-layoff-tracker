"""The GDELT work ledger must survive the container that wrote it.

THE DEFECT THIS PINS (measured 2026-08-28). PR #223 built a cross-run work
ledger so an abandoned or capped GDELT window is RETRIED on a later run instead
of vanishing -- leak #3 in that PR's own list. It stored the ledger in
``railway/gdelt_work_ledger.json``, which is correct for a checkout and inert
for the thing that actually runs the sweep: the live cron runs on Railway, in
an ephemeral container with no volume and no git identity, so the file is
discarded the instant the run ends.

The result was a mechanism that looked present and did nothing. The committed
ledger held ZERO slots from the day the feature shipped, while a single
production run abandoned 7 of 12 windows. Every one of those windows was lost,
not retried. Nothing reported it, because the health page's ``degraded`` reads
as "known partial coverage, queued for retry" -- which is precisely the claim
the ledger was supposed to make true. A guard that silently stops guarding is
worse than no guard, because it also stops anyone looking.

THE RULE THESE TESTS HOLD: the ledger round-trips through the keyed
/tracker-meta endpoint (the same transport cron.py already uses for its spend
records, and the same one spend.py harvests back), the file is still written
for checkouts, and BOTH directions are best-effort -- an ingest run must never
be taken down by its own bookkeeping.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sources import gdelt  # noqa: E402


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _Recorder:
    """Stands in for ``requests``; records every POST instead of sending it."""

    def __init__(self, payload=None, status_code=200, raises=None):
        self.calls = []
        self._payload = payload if payload is not None else {}
        self._status = status_code
        self._raises = raises

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        if self._raises:
            raise self._raises
        return _FakeResponse(self._payload, self._status)


class LedgerPersistenceBase(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        handle.close()
        os.unlink(handle.name)
        self.path = handle.name
        self.addCleanup(
            lambda: os.path.exists(self.path) and os.unlink(self.path))
        self._real_requests = gdelt.requests
        self.addCleanup(lambda: setattr(gdelt, "requests", self._real_requests))
        self._saved_env = {k: os.environ.get(k)
                           for k in ("WP_SITE_URL", "WP_API_KEY")}
        self.addCleanup(self._restore_env)
        # The two process-level sync guards are module state; a test that left
        # them set would silently disarm the next test's remote call.
        self._reset_sync_guards()
        self.addCleanup(self._reset_sync_guards)

    @staticmethod
    def _reset_sync_guards():
        gdelt._REMOTE_LEDGER_READ = False
        gdelt._REMOTE_LEDGER_PUSHED = None

    def _restore_env(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _arm(self, recorder):
        gdelt.requests = recorder
        os.environ["WP_SITE_URL"] = "https://example.test/blog"
        os.environ["WP_API_KEY"] = "test-key"

    def _disarm(self, recorder):
        gdelt.requests = recorder
        os.environ.pop("WP_SITE_URL", None)
        os.environ.pop("WP_API_KEY", None)

    @staticmethod
    def _slot(updated, status="failed", family="segment", returned=0):
        return {
            "family": family,
            "window_start": "20260828T000000Z",
            "window_end": "20260828T120000Z",
            "status": status,
            "returned": returned,
            "cap_hit": False,
            "attempts": 1,
            "first_seen": updated,
            "updated": updated,
        }


class WithoutCredentialsNothingLeavesTheProcess(LedgerPersistenceBase):
    """The unconfigured case must behave exactly as it did before."""

    def test_save_makes_no_request(self):
        recorder = _Recorder()
        self._disarm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        self.assertEqual(recorder.calls, [])

    def test_load_makes_no_request(self):
        recorder = _Recorder()
        self._disarm(recorder)
        gdelt._load_work_ledger(path=self.path)
        self.assertEqual(recorder.calls, [])

    def test_the_file_is_still_written_and_read(self):
        recorder = _Recorder()
        self._disarm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        self.assertIn("a", gdelt._load_work_ledger(path=self.path)["slots"])


class TheLedgerReachesTheKeyedEndpoint(LedgerPersistenceBase):
    def test_save_posts_the_slots_under_set_gdelt_ledger(self):
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        posts = [c for c in recorder.calls if "set_gdelt_ledger" in (c["json"] or {})]
        self.assertEqual(len(posts), 1, "the ledger was not persisted remotely")
        self.assertIn("a", posts[0]["json"]["set_gdelt_ledger"])
        self.assertTrue(posts[0]["url"].endswith("/wp-json/layoffs/v1/tracker-meta"))

    def test_the_request_carries_the_key_and_a_non_python_user_agent(self):
        # ModSecurity on the WP host blocks python-requests outright, so a
        # default UA here would fail every sync while looking like an outage.
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {}}, path=self.path)
        headers = recorder.calls[0]["headers"]
        self.assertEqual(headers.get("X-Layoff-API-Key"), "test-key")
        self.assertNotIn("python-requests", headers.get("User-Agent", "").lower())

    def test_the_file_is_still_written_when_the_remote_is_armed(self):
        # The remote is for the cron; the file is what a checkout reads.
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        with open(self.path, encoding="utf-8") as fh:
            self.assertIn("a", json.load(fh)["slots"])


class AFreshContainerRecoversWhatItNeverWrote(LedgerPersistenceBase):
    """THE defect: the cron starts with no file and must not start with no work."""

    def test_load_recovers_slots_from_the_endpoint(self):
        remote = {"gdelt_ledger": {"owed": self._slot("20260828T100000Z")}}
        recorder = _Recorder(payload=remote)
        self._arm(recorder)
        # No file at all — a container that has never run before.
        self.assertFalse(os.path.exists(self.path))
        ledger = gdelt._load_work_ledger(path=self.path)
        self.assertIn("owed", ledger["slots"],
                      "an abandoned window did not survive the container")

    def test_local_and_remote_are_unioned_not_replaced(self):
        remote = {"gdelt_ledger": {"from_cron": self._slot("20260828T100000Z")}}
        recorder = _Recorder(payload=remote)
        self._disarm(recorder)
        gdelt._save_work_ledger(
            {"slots": {"from_checkout": self._slot("20260828T100000Z")}},
            path=self.path)
        self._arm(recorder)
        slots = gdelt._load_work_ledger(path=self.path)["slots"]
        self.assertIn("from_cron", slots)
        self.assertIn("from_checkout", slots)

    def test_the_more_recently_updated_record_wins(self):
        key = "same"
        remote = {"gdelt_ledger": {key: self._slot("20260828T120000Z",
                                                   status="complete")}}
        recorder = _Recorder(payload=remote)
        self._disarm(recorder)
        gdelt._save_work_ledger(
            {"slots": {key: self._slot("20260828T100000Z", status="failed")}},
            path=self.path)
        self._arm(recorder)
        slots = gdelt._load_work_ledger(path=self.path)["slots"]
        self.assertEqual(slots[key]["status"], "complete")

    def test_a_tie_keeps_the_local_record(self):
        # A run that just recorded an outcome must not be overwritten by the
        # copy it read at startup.
        key = "same"
        stamp = "20260828T100000Z"
        remote = {"gdelt_ledger": {key: self._slot(stamp, status="complete")}}
        recorder = _Recorder(payload=remote)
        self._disarm(recorder)
        gdelt._save_work_ledger(
            {"slots": {key: self._slot(stamp, status="partial")}}, path=self.path)
        self._arm(recorder)
        slots = gdelt._load_work_ledger(path=self.path)["slots"]
        self.assertEqual(slots[key]["status"], "partial")


class BookkeepingNeverTakesDownTheRun(LedgerPersistenceBase):
    """Every failure mode is survivable, and none of them is read as 'nothing owed'."""

    def test_a_raising_transport_does_not_propagate_on_save(self):
        recorder = _Recorder(raises=RuntimeError("connection reset"))
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        with open(self.path, encoding="utf-8") as fh:
            self.assertIn("a", json.load(fh)["slots"])

    def test_a_raising_transport_does_not_propagate_on_load(self):
        recorder = _Recorder(raises=RuntimeError("connection reset"))
        self._arm(recorder)
        self.assertEqual(gdelt._load_work_ledger(path=self.path)["slots"], {})

    def test_a_non_200_is_not_treated_as_an_empty_ledger(self):
        # The local slot must survive a 503; UNKNOWN is not "nothing is owed".
        recorder = _Recorder(payload={}, status_code=503)
        self._disarm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        self._arm(recorder)
        self.assertIn("a", gdelt._load_work_ledger(path=self.path)["slots"])

    def test_a_malformed_remote_payload_is_ignored(self):
        recorder = _Recorder(payload={"gdelt_ledger": "not-a-map"})
        self._arm(recorder)
        self.assertEqual(gdelt._load_work_ledger(path=self.path)["slots"], {})

    def test_a_non_dict_slot_in_the_remote_payload_is_dropped(self):
        recorder = _Recorder(payload={"gdelt_ledger": {"bad": 7, "good":
                                      self._slot("20260828T100000Z")}})
        self._arm(recorder)
        slots = gdelt._load_work_ledger(path=self.path)["slots"]
        self.assertNotIn("bad", slots)
        self.assertIn("good", slots)

    def test_an_unwritable_path_still_syncs_remotely(self):
        # A read-only filesystem is survivable now that the remote copy is the
        # one the live cron depends on.
        recorder = _Recorder()
        self._arm(recorder)
        unwritable = os.path.join(self.path, "nope", "ledger.json")
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=unwritable)
        posts = [c for c in recorder.calls if "set_gdelt_ledger" in (c["json"] or {})]
        self.assertEqual(len(posts), 1)


class TheSyncIsBoundedForTheBACKFILL(LedgerPersistenceBase):
    """`pull_gdelt_between` is called ONCE per run by the cron and once per
    WEEK-WINDOW by gdelt_backfill.py, so an un-guarded sync would add two
    requests per window to a shared host that has 504'd under load."""

    def test_the_remote_is_read_once_per_process_not_once_per_window(self):
        recorder = _Recorder(payload={"gdelt_ledger": {}})
        self._arm(recorder)
        for _ in range(5):
            gdelt._load_work_ledger(path=self.path)
        self.assertEqual(len(recorder.calls), 1,
                         "the backfill re-read the ledger on every window")

    def test_an_unchanged_ledger_is_not_re_posted(self):
        recorder = _Recorder()
        self._arm(recorder)
        ledger = {"slots": {"a": self._slot("20260828T100000Z")}}
        gdelt._save_work_ledger(ledger, path=self.path)
        gdelt._save_work_ledger(ledger, path=self.path)
        gdelt._save_work_ledger(ledger, path=self.path)
        self.assertEqual(len(recorder.calls), 1,
                         "an idle window still cost a request")

    def test_a_changed_ledger_IS_re_posted(self):
        # The guard must not cost the durability it exists to make affordable.
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z")}},
                                path=self.path)
        gdelt._save_work_ledger({"slots": {"a": self._slot("20260828T100000Z"),
                                           "b": self._slot("20260828T110000Z")}},
                                path=self.path)
        self.assertEqual(len(recorder.calls), 2)

    def test_a_failed_read_does_not_consume_the_once_per_process_budget(self):
        # A guard that armed on FAILURE would turn one flaky request into a
        # process that never recovers its ledger at all.
        recorder = _Recorder(raises=RuntimeError("connection reset"))
        self._arm(recorder)
        gdelt._load_work_ledger(path=self.path)
        gdelt.requests = _Recorder(payload={"gdelt_ledger":
                                            {"owed": self._slot("20260828T100000Z")}})
        self.assertIn("owed", gdelt._load_work_ledger(path=self.path)["slots"])

    def test_a_failed_push_is_retried_on_the_next_save(self):
        # Likewise: the fingerprint must record what the endpoint ACCEPTED, not
        # what we attempted, or one 503 would suppress every later push.
        recorder = _Recorder(payload={}, status_code=503)
        self._arm(recorder)
        ledger = {"slots": {"a": self._slot("20260828T100000Z")}}
        gdelt._save_work_ledger(ledger, path=self.path)
        good = _Recorder()
        gdelt.requests = good
        gdelt._save_work_ledger(ledger, path=self.path)
        self.assertEqual(len(good.calls), 1, "a 503 permanently muted the sync")


class TheRemoteCanBeTurnedOff(LedgerPersistenceBase):
    """`remote=False` is what a test or an offline tool passes."""

    def test_save_with_remote_false_makes_no_request(self):
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._save_work_ledger({"slots": {}}, path=self.path, remote=False)
        self.assertEqual(recorder.calls, [])

    def test_load_with_remote_false_makes_no_request(self):
        recorder = _Recorder()
        self._arm(recorder)
        gdelt._load_work_ledger(path=self.path, remote=False)
        self.assertEqual(recorder.calls, [])


if __name__ == "__main__":
    unittest.main()
