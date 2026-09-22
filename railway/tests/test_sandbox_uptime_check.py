"""The sandbox uptime check: two consecutive failures before it alerts, once
per cause, with a RECOVERED on the next healthy run.

Everything here is offline: every URL fetch and every certificate read is
stubbed (`_far_cert`: both hosts a year out).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alert_state  # noqa: E402
import sandbox_uptime_check as suc  # noqa: E402


def _ok_fetch(url, timeout=15):
    if url == suc.DEEP_URL:
        return 200, json.dumps({"ok": True, "checks": {"db": {"ok": True}}})
    return 200, "ok"


def _failing_fetch(url, timeout=15):
    if url == suc.HEALTHZ_URL:
        return 503, "unavailable"
    if url == suc.DEEP_URL:
        return 200, json.dumps({"ok": True, "checks": {"db": {"ok": True}}})
    return 200, "ok"


def _deep_check_failing_fetch(url, timeout=15):
    if url == suc.DEEP_URL:
        return 200, json.dumps({"ok": False,
                                "checks": {"db": {"ok": True},
                                           "queue": {"ok": False}}})
    return 200, "ok"


_NOW = 1_800_000_000


def _far_cert(host):
    return _NOW + 365 * 86400


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "sandbox_uptime_state.json"
        self.notified = []

    def _notify(self, subject, body):
        self.notified.append((subject, body))
        return True

    def _run(self, fetch, read_cert=_far_cert):
        return suc.run(fetch=fetch, state_path=self.state_path,
                       notify=self._notify, now=_NOW, read_cert=read_cert)


class CheckAllJudgesAllThreeEndpoints(unittest.TestCase):
    def test_all_ok_is_ok(self):
        ok, detail = suc.check_all(fetch=_ok_fetch)
        self.assertTrue(ok)
        self.assertEqual(detail, "ok")

    def test_a_non_200_healthz_is_not_ok(self):
        ok, detail = suc.check_all(fetch=_failing_fetch)
        self.assertFalse(ok)
        self.assertIn("503", detail)

    def test_a_deep_check_reporting_false_is_not_ok(self):
        ok, detail = suc.check_all(fetch=_deep_check_failing_fetch)
        self.assertFalse(ok)
        self.assertIn("queue", detail)

    def test_a_transport_failure_is_not_ok(self):
        def raising(url, timeout=15):
            raise OSError("connection reset")
        ok, detail = suc.check_all(fetch=raising)
        self.assertFalse(ok)
        self.assertIn("could not reach it", detail)


class TwoConsecutiveFailuresGateTheAlert(_Base):
    def test_a_single_failure_does_not_alert(self):
        self._run(_failing_fetch)
        self.assertEqual(self.notified, [])

    def test_a_second_consecutive_failure_does_alert(self):
        self._run(_failing_fetch)
        self._run(_failing_fetch)
        self.assertEqual(len(self.notified), 1)
        self.assertIn("sandbox uptime", self.notified[0][0])

    def test_a_third_consecutive_failure_does_not_alert_again(self):
        self._run(_failing_fetch)
        self._run(_failing_fetch)
        self._run(_failing_fetch)
        self.assertEqual(len(self.notified), 1)

    def test_recovery_after_two_failures_resets_the_streak(self):
        self._run(_failing_fetch)
        self._run(_ok_fetch)
        # The streak reset, so it takes two MORE failures to alert again.
        self._run(_failing_fetch)
        self.assertEqual(self.notified, [])

    def test_a_healthy_run_with_nothing_open_sends_no_recovered_notice(self):
        self._run(_ok_fetch)
        self.assertEqual(self.notified, [])


class RecoveryPairsWithTheOriginalAlert(_Base):
    def test_recovered_sends_exactly_once_after_an_open_alert(self):
        self._run(_failing_fetch)
        self._run(_failing_fetch)  # raises
        self.notified.clear()
        self._run(_ok_fetch)       # resolves
        self.assertEqual(len(self.notified), 1)
        self.assertIn("RECOVERED", self.notified[0][0])
        self._run(_ok_fetch)       # nothing left open, silent
        self.assertEqual(len(self.notified), 1)

    def test_a_failed_send_leaves_the_cause_open_for_a_retry(self):
        self._run(_failing_fetch)
        self._run(_failing_fetch)
        state = alert_state.load(self.state_path)
        self.assertIn(suc.CAUSE_KEY, state.get("open", {}))

        def failing_notify(subject, body):
            return False

        code = suc.run(fetch=_failing_fetch, state_path=self.state_path,
                       notify=failing_notify, now=_NOW, read_cert=_far_cert)
        self.assertEqual(code, 0)  # never reddens itself
        state = alert_state.load(self.state_path)
        self.assertIn(suc.CAUSE_KEY, state.get("open", {}))


class ConsecutiveCounterSurvivesOnTheLedger(_Base):
    def test_the_counter_is_stored_on_the_same_committed_file(self):
        self._run(_failing_fetch)
        state = alert_state.load(self.state_path)
        self.assertEqual(state.get("consecutive_fails"), 1)
        self._run(_ok_fetch)
        state = alert_state.load(self.state_path)
        self.assertEqual(state.get("consecutive_fails"), 0)


class NeverGoesRedOnAFailedCheck(_Base):
    def test_exit_code_is_always_zero(self):
        self.assertEqual(self._run(_failing_fetch), 0)
        self.assertEqual(self._run(_failing_fetch), 0)
        self.assertEqual(self._run(_ok_fetch), 0)


if __name__ == "__main__":
    unittest.main()


def _short_cert(host):
    return _NOW + 3 * 86400 if host == "asktherecruiter.com" else _NOW + 365 * 86400


def _unreadable_cert(host):
    raise OSError("handshake refused")


class CheckCertsJudgesEveryHost(unittest.TestCase):
    def test_a_year_of_runway_is_clear(self):
        expiring, unknown, days = suc.check_certs(read_cert=_far_cert, now=_NOW)
        self.assertEqual((expiring, unknown), ([], []))
        self.assertEqual(set(days), set(suc.CERT_HOSTS))

    def test_under_fourteen_days_names_the_host_and_the_days(self):
        expiring, unknown, _ = suc.check_certs(read_cert=_short_cert, now=_NOW)
        self.assertEqual(expiring, ["asktherecruiter.com expires in 3 day(s)"])
        self.assertEqual(unknown, [])

    def test_exactly_fourteen_days_is_still_clear_and_thirteen_is_not(self):
        at_ceiling = suc.check_certs(read_cert=lambda h: _NOW + 14 * 86400, now=_NOW)
        self.assertEqual(at_ceiling[0], [])
        below = suc.check_certs(read_cert=lambda h: _NOW + 14 * 86400 - 1, now=_NOW)
        self.assertEqual(len(below[0]), len(suc.CERT_HOSTS))

    def test_an_unreadable_certificate_is_unknown_not_expiring(self):
        expiring, unknown, days = suc.check_certs(read_cert=_unreadable_cert, now=_NOW)
        self.assertEqual(expiring, [])
        self.assertEqual(len(unknown), len(suc.CERT_HOSTS))
        self.assertIn("handshake refused", unknown[0])
        self.assertEqual(days, {})

    def test_the_real_reader_is_the_default(self):
        """The injection seam must not silently replace the real read."""
        self.assertIs(suc.check_certs.__defaults__[0], None)
        self.assertTrue(callable(suc._cert_not_after))


class CertExpiryIsItsOwnCause(_Base):
    def test_a_short_certificate_alerts_on_the_first_run(self):
        """No streak: expiry is not a transient blip."""
        self._run(_ok_fetch, read_cert=_short_cert)
        self.assertEqual(len(self.notified), 1)
        self.assertIn("TLS certificate expiring", self.notified[0][0])
        self.assertIn("asktherecruiter.com expires in 3 day(s)", self.notified[0][0])
        state = alert_state.load(self.state_path)
        self.assertIn(suc.CERT_CAUSE_KEY, state.get("open", {}))
        self.assertNotIn(suc.CAUSE_KEY, state.get("open", {}))

    def test_a_repeat_is_suppressed_and_renewal_recovers_once(self):
        self._run(_ok_fetch, read_cert=_short_cert)
        self._run(_ok_fetch, read_cert=_short_cert)
        self.assertEqual(len(self.notified), 1)
        self._run(_ok_fetch, read_cert=_far_cert)
        self.assertEqual(len(self.notified), 2)
        self.assertIn("RECOVERED: TLS certificate", self.notified[1][0])
        self._run(_ok_fetch, read_cert=_far_cert)
        self.assertEqual(len(self.notified), 2)
        self.assertNotIn(suc.CERT_CAUSE_KEY, alert_state.load(self.state_path).get("open", {}))

    def test_unknown_neither_raises_nor_resolves(self):
        self._run(_ok_fetch, read_cert=_unreadable_cert)
        self.assertEqual(self.notified, [])
        self._run(_ok_fetch, read_cert=_short_cert)   # opens the cause
        self._run(_ok_fetch, read_cert=_unreadable_cert)
        self.assertEqual(len(self.notified), 1, "an unreadable cert is not a renewal")
        self.assertIn(suc.CERT_CAUSE_KEY, alert_state.load(self.state_path).get("open", {}))

    def test_the_certificate_does_not_touch_the_outage_streak(self):
        self._run(_ok_fetch, read_cert=_short_cert)
        state = alert_state.load(self.state_path)
        self.assertEqual(int(state.get("consecutive_fails", 0)), 0)
        self._run(_failing_fetch, read_cert=_short_cert)
        self._run(_failing_fetch, read_cert=_short_cert)
        subjects = [s for s, _ in self.notified]
        self.assertEqual(len(subjects), 2)
        self.assertTrue(any("uptime check failing" in s for s in subjects))

    def test_a_failed_cert_send_leaves_the_cause_new_for_a_retry(self):
        def failing_notify(subject, body):
            return False
        suc.run(fetch=_ok_fetch, state_path=self.state_path, notify=failing_notify,
                now=_NOW, read_cert=_short_cert)
        self.assertNotIn(suc.CERT_CAUSE_KEY, alert_state.load(self.state_path).get("open", {}))
        self._run(_ok_fetch, read_cert=_short_cert)
        self.assertEqual(len(self.notified), 1)
