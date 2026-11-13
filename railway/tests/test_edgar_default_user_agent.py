"""SEC lookups from jobs that never set EDGAR_USER_AGENT must still identify us.

The 2026-11-13 September replay (news-catchup, run 43465041444) logged
"EDGAR warning: EDGAR_USER_AGENT is not set" and the news estimate for The
Trade Desk never formed: SEC rejects the fallback "unknown@example.com", so
the 10-K headcount lookup returned nothing. 29 workflows that run the
extractor do not set the variable (only 8 do), and the Railway cron path
shares the same code, so the default belongs in `sources/edgar._headers`.
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _requests_stub import install as _install  # noqa: E402
_install()

from sources import edgar  # noqa: E402


class DefaultUserAgent(unittest.TestCase):
    def test_unset_falls_back_to_the_project_contact_not_example_dot_com(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EDGAR_USER_AGENT", None)
            ua = edgar._headers()["User-Agent"]
        self.assertIn("asktherecruiter.com", ua)
        self.assertNotIn("example.com", ua)
        self.assertNotIn("unknown", ua)

    def test_an_explicit_value_still_wins(self):
        with mock.patch.dict(os.environ, {"EDGAR_USER_AGENT": "Custom Agent a@b.co"}):
            self.assertEqual(edgar._headers()["User-Agent"], "Custom Agent a@b.co")

    def test_an_empty_value_is_treated_as_unset(self):
        with mock.patch.dict(os.environ, {"EDGAR_USER_AGENT": "  "}):
            self.assertIn("asktherecruiter.com", edgar._headers()["User-Agent"])


if __name__ == "__main__":
    unittest.main()
