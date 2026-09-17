"""The hourly new-error watch: no spend on a repeat, no silence on a failure.

Defends the properties the task called out explicitly:

  * a cause that is not NEW never triggers a model call
  * once the $3.00/month cap is spent, no call is made and the alert still
    sends, saying plainly that the summary is missing because of the cap
  * a summary call that raises still lets the alert send, saying plainly that
    the summary is missing because the call failed
  * redaction removes an email address, a bearer token and an API key before
    anything reaches a prompt
  * a repeat cause within the reminder window does not alert twice
  * the ledger keeps alert_state's three shapes (raise/remind/resolve)

Everything here is offline: Sentry, OpenRouter and ops_notify are all stubbed.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import alert_state  # noqa: E402
import new_error_watch as watch  # noqa: E402
import spend  # noqa: E402


def issue(title="TypeError: cannot read x", culprit="views.py in render",
          short_id="ALT-1", permalink="https://sentry.io/x/1/"):
    return {"title": title, "culprit": culprit, "shortId": short_id,
            "id": "1", "permalink": permalink, "metadata": {"value": title}}


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_path = Path(self.tmp.name) / "new_error_state.json"
        self.spend_path = Path(self.tmp.name) / "new_error_spend.json"

        self._env = {k: os.environ.get(k) for k in
                     ("SENTRY_ORG", "SENTRY_PROJECT", "SENTRY_AUTH_TOKEN",
                      "OPENROUTER_OPS_KEY", "ALT_PAID_READS",
                      "ALT_RUN_CEILING_USD")}
        os.environ["SENTRY_ORG"] = "org"
        os.environ["SENTRY_PROJECT"] = "proj"
        os.environ["SENTRY_AUTH_TOKEN"] = "test-sentry-token"
        os.environ["OPENROUTER_OPS_KEY"] = "test-ops-key"
        os.environ.pop("ALT_PAID_READS", None)
        os.environ["ALT_RUN_CEILING_USD"] = "5.00"
        self.addCleanup(self._restore_env)

        spend.reset_run_meter()
        self.addCleanup(spend.reset_run_meter)
        self._snap = spend.SNAPSHOT_PATH
        spend.SNAPSHOT_PATH = str(Path(self.tmp.name) / "spend_month.json")
        self.addCleanup(lambda: setattr(spend, "SNAPSHOT_PATH", self._snap))
        spend._prices_fetched = True

        self.notified = []

    def _restore_env(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _fetch(self, issues):
        def fetch(url, headers):
            return 200, json.dumps(issues)
        return fetch

    def _post_ok(self, text="line1\nline2\nline3", cost=0.001):
        def post():
            return {"choices": [{"message": {"content": text}}],
                    "usage": {"cost": cost}}
        return post

    def _notify(self, subject, body, **_kw):
        self.notified.append((subject, body))
        return True

    def _run(self, issues, http_post=None, fetch_status=None):
        return watch.run(fetch=self._fetch(issues), http_post=http_post,
                          fetch_status=fetch_status,
                          state_path=self.state_path, spend_path=self.spend_path,
                          notify=self._notify)


class NoCallWhenNothingIsNew(_Base):
    def test_an_already_open_cause_makes_no_call(self):
        calls = []
        code = self._run([issue()], http_post=lambda: calls.append(1) or self._post_ok()())
        self.assertEqual(code, 0)
        self.assertEqual(len(self.notified), 1, "first sighting should alert once")

        self.notified.clear()
        code = self._run([issue()], http_post=lambda: (_ for _ in ()).throw(
            AssertionError("no call should be made for a repeat cause")))
        self.assertEqual(code, 0)
        self.assertEqual(self.notified, [],
                         "a cause still open within the reminder window must not re-alert")


class TheCapStopsTheCallButNotTheAlert(_Base):
    def test_cap_reached_sends_a_plain_alert_with_no_call(self):
        # Pre-spend the whole monthly cap.
        watch.record_spend(watch.MONTHLY_CAP_USD, self.spend_path)
        called = []
        code = self._run([issue()], http_post=lambda: called.append(1))
        self.assertEqual(code, 0)
        self.assertEqual(called, [], "no request should be made once the cap is spent")
        self.assertEqual(len(self.notified), 1)
        _subject, body = self.notified[0]
        self.assertIn("cap", body.lower())
        self.assertIn("no ai summary", body.lower())


class ARaisingCallStillAlerts(_Base):
    def test_a_call_that_raises_still_sends_and_says_so(self):
        def boom():
            raise TimeoutError("provider timed out")
        code = self._run([issue()], http_post=boom)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.notified), 1)
        _subject, body = self.notified[0]
        self.assertIn("no ai summary", body.lower())
        self.assertIn("call failed", body.lower())

    def test_a_successful_call_records_spend_and_is_included(self):
        code = self._run([issue()], http_post=self._post_ok("what/cause/step", 0.01))
        self.assertEqual(code, 0)
        _subject, body = self.notified[0]
        self.assertIn("what/cause/step", body)
        self.assertAlmostEqual(watch.spend_this_month(self.spend_path), 0.01, places=6)


class Redaction(_Base):
    def test_email_bearer_and_api_key_are_removed(self):
        text = ("contact dak@dakotta.com, Authorization: Bearer sk-abcdef0123456789ABCDEF, "
                "bearer abcdefghijklmnopqrstuvwx, key=abcdefghijklmnopqrstuvwxyz012345")
        out = watch.redact(text)
        self.assertNotIn("dak@dakotta.com", out)
        self.assertNotIn("abcdef0123456789ABCDEF", out)
        self.assertNotIn("Bearer sk-abcdef0123456789ABCDEF", out)


class RepeatCauseDoesNotAlertTwice(_Base):
    def test_same_cause_two_runs_one_alert(self):
        self._run([issue()], http_post=self._post_ok())
        self.assertEqual(len(self.notified), 1)
        self.notified.clear()
        self._run([issue()], http_post=self._post_ok())
        self.assertEqual(self.notified, [])

    def test_a_new_different_cause_does_alert(self):
        self._run([issue(title="TypeError: x")], http_post=self._post_ok())
        self.assertEqual(len(self.notified), 1)
        self.notified.clear()
        self._run([issue(title="KeyError: y")], http_post=self._post_ok())
        self.assertEqual(len(self.notified), 1)


class LedgerKeepsAlertStatesThreeShapes(_Base):
    def test_raise_then_resolve_round_trip(self):
        self._run([issue()], http_post=self._post_ok())
        state = alert_state.load(self.state_path)
        self.assertEqual(len(state.get("open") or {}), 1)

        self.notified.clear()
        resolved_status = lambda url, headers: (200, json.dumps({"status": "resolved"}))
        code = self._run([], http_post=self._post_ok(), fetch_status=resolved_status)
        self.assertEqual(code, 0)
        state = alert_state.load(self.state_path)
        self.assertEqual(state.get("open"), {}, "the cleared cause must leave the ledger")
        self.assertTrue(any("RECOVERED" in s for s, _b in self.notified))

    def test_a_recovered_notice_that_fails_to_send_leaves_the_cause_open(self):
        """RECOVERED is mailed once by contract, so a failed send must retry.

        The raise path already commits to the ledger only after notify()
        returns True. The clear path has to match: if it applied first, a
        relay outage would drop the cause from the ledger with nobody ever
        told it recovered, and no later run would re-derive it.
        """
        self._run([issue()], http_post=self._post_ok())
        self.assertEqual(len(alert_state.load(self.state_path).get("open") or {}), 1)

        resolved_status = lambda url, headers: (200, json.dumps({"status": "resolved"}))

        self.notified.clear()
        failing = lambda subject, body, **_kw: (
            self.notified.append((subject, body)) or False)
        code = watch.run(fetch=self._fetch([]), http_post=self._post_ok(),
                         fetch_status=resolved_status,
                         state_path=self.state_path, spend_path=self.spend_path,
                         notify=failing)
        self.assertEqual(code, 0)
        self.assertTrue(any("RECOVERED" in s for s, _b in self.notified),
                        "it must still try to send")
        self.assertEqual(
            len(alert_state.load(self.state_path).get("open") or {}), 1,
            "an undelivered RECOVERED must leave the cause open so the next "
            "run re-sends it")

        self.notified.clear()
        code = self._run([], http_post=self._post_ok(), fetch_status=resolved_status)
        self.assertEqual(code, 0)
        self.assertTrue(any("RECOVERED" in s for s, _b in self.notified),
                        "the next run re-sends it")
        self.assertEqual(alert_state.load(self.state_path).get("open"), {})

    def test_an_open_cause_is_not_cleared_while_still_unresolved(self):
        self._run([issue()], http_post=self._post_ok())
        self.notified.clear()
        still_unresolved = lambda url, headers: (200, json.dumps({"status": "unresolved"}))
        code = self._run([], http_post=self._post_ok(), fetch_status=still_unresolved)
        self.assertEqual(code, 0)
        state = alert_state.load(self.state_path)
        self.assertEqual(len(state.get("open") or {}), 1,
                         "a cause must stay open until Sentry reports it settled")
        self.assertEqual(self.notified, [])

    def test_state_file_has_alert_states_shape(self):
        self._run([issue()], http_post=self._post_ok())
        doc = json.loads(self.state_path.read_text())
        self.assertIn("open", doc)
        self.assertIn("version", doc)
        for key, entry in doc["open"].items():
            self.assertIn("first", entry)
            self.assertIn("last", entry)
            self.assertIn("subject", entry)


class AbsentIsGreenAndUnknownIsNot(_Base):
    """Three states, not two, and the middle one is what stops hourly noise.

    Merging this with no SENTRY_ORG/SENTRY_PROJECT set would have produced a
    red run every hour for a feature nobody had switched on. CLAUDE.md already
    rules on this shape for the digest mailer: ABSENT (nothing armed) is green,
    and collapsing it into the fault state sends someone to fix a thing that
    was never configured.
    """

    def test_no_sentry_credentials_at_all_is_green(self):
        for key in ("SENTRY_ORG", "SENTRY_PROJECT", "SENTRY_AUTH_TOKEN"):
            os.environ.pop(key, None)
        self.assertEqual(self._run([]), 0,
                         "an unconfigured watch must not manufacture a red run")

    def test_configured_but_unreadable_is_still_red(self):
        # Armed and broken is the case the exit code exists for.
        def failing(url, headers):
            raise OSError("connection reset")
        code = watch.run(fetch=failing, state_path=self.state_path,
                         spend_path=self.spend_path, notify=self._notify)
        self.assertEqual(code, 3)

    def test_a_partial_configuration_is_absent_not_armed(self):
        # Half-configured is not armed: without a token nothing can be read,
        # and reporting that hourly as a fault is the same noise.
        os.environ.pop("SENTRY_AUTH_TOKEN", None)
        self.assertEqual(self._run([]), 0)


class UnknownWhenSentryCannotBeRead(_Base):
    def test_missing_config_is_green_and_fetches_nothing(self):
        # This asserted exit 3 until 2026-09-15. Merging on that would have
        # produced a red run every hour, because SENTRY_ORG and SENTRY_PROJECT
        # do not exist as repository variables yet. Unconfigured is ABSENT and
        # green; it still must not reach the network, and must not alert.
        os.environ.pop("SENTRY_AUTH_TOKEN", None)
        code = watch.run(fetch=lambda url, headers: (_ for _ in ()).throw(
            AssertionError("should not fetch when unconfigured")),
            state_path=self.state_path, spend_path=self.spend_path,
            notify=self._notify)
        self.assertEqual(code, 0)
        self.assertEqual(self.notified, [])


class SentryApiBaseIsRegionAware(unittest.TestCase):
    """The org lives on the EU region, not sentry.io. A hardcoded base would
    404 every request and read as UNKNOWN forever without anyone noticing
    (fetch_new_issues never raises on a non-200 status, it just reports the
    HTTP code). SENTRY_REGION_URL makes the host a variable, not code."""

    def setUp(self):
        self._prev = os.environ.pop("SENTRY_REGION_URL", None)
        self.addCleanup(lambda: self._prev is not None and
                         os.environ.__setitem__("SENTRY_REGION_URL", self._prev))
        self.addCleanup(lambda: os.environ.pop("SENTRY_REGION_URL", None))

    def test_default_is_the_eu_region_not_sentry_io(self):
        self.assertEqual(watch.sentry_api_base(), "https://de.sentry.io/api/0")

    def test_region_var_overrides_the_default(self):
        os.environ["SENTRY_REGION_URL"] = "https://us.sentry.io"
        self.assertEqual(watch.sentry_api_base(), "https://us.sentry.io/api/0")

    def test_trailing_slash_on_the_region_var_is_tolerated(self):
        os.environ["SENTRY_REGION_URL"] = "https://de.sentry.io/"
        self.assertEqual(watch.sentry_api_base(), "https://de.sentry.io/api/0")


class StatsPeriodIsNeverAnArbitraryDuration(_Base):
    """statsPeriod on the project-issues endpoint only shapes the per-issue
    stats graph and Sentry rejects anything but '', '24h' or '14d' with an
    HTTP 400 -- the region fix in #386 pointed requests at a host that
    actually validates this and turned a silent 404 into a live 400. The
    "last N hours" window belongs in the search query's age filter, which
    accepts any duration, not in statsPeriod."""

    def test_the_request_carries_no_stats_period_param(self):
        seen = {}

        def fetch(url, headers):
            seen["url"] = url
            return 200, "[]"

        watch.fetch_new_issues(hours=1, fetch=fetch)
        self.assertNotIn("statsPeriod", seen["url"])

    def test_the_hour_window_is_encoded_as_an_age_filter(self):
        seen = {}

        def fetch(url, headers):
            seen["url"] = url
            return 200, "[]"

        watch.fetch_new_issues(hours=1, fetch=fetch)
        query = urllib.parse.unquote(seen["url"].split("query=", 1)[1].split("&", 1)[0])
        self.assertIn("age:-1h", query)
        self.assertIn("is:unresolved", query)
        self.assertIn("is:new", query)


if __name__ == "__main__":
    unittest.main()
