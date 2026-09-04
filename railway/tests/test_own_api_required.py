"""An unset WP_SITE_URL fails LOUDLY, as itself, before any request is built.

Three lookups of our OWN rows -- the watchlist's `already_have`,
`tracker_diff._our_rows`, `curated_probe.our_rows` -- built their URL from the
env var and, when it was unset, requested `/wp-json/...` on an EMPTY host,
swallowed the exception and returned their "could not read" value. On
2026-09-04 the curated probe scored a held item (27 rows live) UNKNOWN with the
note "our own API did not answer". It had not been asked. Absence of
configuration is not absence of an answer.

Each lookup now calls `own_api.require_site_url()` OUTSIDE its network try, so
the fault propagates as `SiteNotConfigured` with a message that names the env
var. MUTATION: move the call back inside the try, or restore the
`os.environ.get(...)` read, and the "no request is made" assertions fail.

Offline: `requests` on each module is replaced with a recorder that FAILS the
test if any request is attempted.
"""
import io
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()
if "openai" not in sys.modules:
    sys.modules["openai"] = types.ModuleType("openai")

import own_api  # noqa: E402
import company_watchlist as cw  # noqa: E402
import tracker_diff as td  # noqa: E402
import curated_probe as cp  # noqa: E402

MARK = "Zzqqmarker"


def _forbidden_requests(log):
    def _get(*a, **k):
        log.append(("get", a, k))
        raise AssertionError("a request was built with WP_SITE_URL unset")
    return types.SimpleNamespace(get=_get, post=_get)


def _raising_requests(exc):
    def _get(*a, **k):
        raise exc
    return types.SimpleNamespace(get=_get, post=_get)


class _EnvHarness(unittest.TestCase):
    def setUp(self):
        self._site = os.environ.pop("WP_SITE_URL", None)
        self._saved = (cw.requests, td.requests, cp.requests)
        self.log = []
        cw.requests = td.requests = cp.requests = _forbidden_requests(self.log)

    def tearDown(self):
        cw.requests, td.requests, cp.requests = self._saved
        if self._site is not None:
            os.environ["WP_SITE_URL"] = self._site
        else:
            os.environ.pop("WP_SITE_URL", None)


class TheHelper(_EnvHarness):
    def test_unset_raises_its_own_type_and_names_the_variable(self):
        with self.assertRaises(own_api.SiteNotConfigured) as cm:
            own_api.require_site_url()
        self.assertIn("WP_SITE_URL", str(cm.exception))
        self.assertIn("not an outage", str(cm.exception))

    def test_blank_is_unset(self):
        os.environ["WP_SITE_URL"] = "   "
        with self.assertRaises(own_api.SiteNotConfigured):
            own_api.require_site_url()

    def test_set_returns_the_root_with_no_trailing_slash(self):
        os.environ["WP_SITE_URL"] = "https://example.test/blog/"
        self.assertEqual(own_api.require_site_url(), "https://example.test/blog")

    def test_it_is_a_runtime_error_so_an_unprepared_caller_still_stops(self):
        self.assertTrue(issubclass(own_api.SiteNotConfigured, RuntimeError))


class TheThreeLookups(_EnvHarness):
    def test_the_watchlist_lookup_raises_and_sends_nothing(self):
        with self.assertRaises(own_api.SiteNotConfigured):
            cw.already_have("Uber")
        self.assertEqual(self.log, [])

    def test_the_learning_loop_lookup_raises_and_sends_nothing(self):
        with self.assertRaises(own_api.SiteNotConfigured):
            td._our_rows("Uber")
        self.assertEqual(self.log, [])

    def test_the_curated_probe_lookup_raises_and_sends_nothing(self):
        with self.assertRaises(own_api.SiteNotConfigured):
            cp.our_rows("Uber")
        self.assertEqual(self.log, [])

    def test_an_empty_token_is_still_nothing_to_ask_not_a_fault(self):
        """The token check comes first: nothing to look up is None, as before,
        and does not need the site to say so."""
        self.assertIsNone(td._our_rows(""))
        self.assertIsNone(cp.our_rows(""))


class BehaviourWithTheSiteSetIsUnchanged(unittest.TestCase):
    def setUp(self):
        self._site = os.environ.get("WP_SITE_URL")
        os.environ["WP_SITE_URL"] = "https://example.test/blog"
        self._saved = (cw.requests, td.requests, cp.requests)
        cw.requests = td.requests = cp.requests = _raising_requests(ConnectionError("down"))

    def tearDown(self):
        cw.requests, td.requests, cp.requests = self._saved
        if self._site is None:
            os.environ.pop("WP_SITE_URL", None)
        else:
            os.environ["WP_SITE_URL"] = self._site

    def test_a_real_transport_failure_is_still_the_safe_value(self):
        """The watchlist skips (True), the two probes say UNKNOWN (None). An
        outage that actually happened is still an outage."""
        self.assertIs(cw.already_have("Uber"), True)
        self.assertIsNone(td._our_rows("Uber"))
        self.assertIsNone(cp.our_rows("Uber"))


class TheProbeSaysNotRunInsteadOfNUnknowns(unittest.TestCase):
    """End to end through `curated_probe.main`: a worklist with a judgeable
    item and no WP_SITE_URL exits 2 with its own line, and the item's name is
    not in that line."""

    def setUp(self):
        self._site = os.environ.pop("WP_SITE_URL", None)
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "worklist.txt").write_text(
            f"{MARK} Corp cuts 1,200 jobs https://{MARK.lower()}-wire.example/a\n",
            encoding="utf-8")
        (self.tmp / "deny.txt").write_text("", encoding="utf-8")
        self._env = {}
        for key, name in (("CURATED_WORKLIST", "worklist.txt"),
                          ("CURATED_DENYLIST", "deny.txt"),
                          ("CURATED_REPORT", "report.md"),
                          ("CURATED_KNOWN", "known.json"),
                          ("CURATED_REFUSALS", "refusals.json")):
            self._env[key] = os.environ.get(key)
            os.environ[key] = str(self.tmp / name)
        self._state, cp.STATE_PATH = cp.STATE_PATH, self.tmp / "state.json"
        self._requests = cp.requests
        cp.requests = _forbidden_requests([])

    def tearDown(self):
        cp.STATE_PATH, cp.requests = self._state, self._requests
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self._site is not None:
            os.environ["WP_SITE_URL"] = self._site

    def test_exit_2_with_the_configuration_message(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cp.main([])
        out = buf.getvalue()
        self.assertEqual(rc, 2)
        self.assertIn("NOT RUN", out)
        self.assertIn("WP_SITE_URL", out)
        self.assertNotIn("did not answer", out)
        self.assertNotIn(MARK.lower(), out.lower())


if __name__ == "__main__":
    unittest.main()
