"""A published edition is corrected by a dated note, never re-rendered.

`/edition-correction` (includes/digest-archive.php) existed with no caller, so
the 2026-W45 weekly kept its 134,595 headline after 104,000 of it was removed
from the data. `railway/edition_correction.py` is that caller: dry run by
default, a reason-shaped note, the read-back proves the note is on the page.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import edition_correction as ec  # noqa: E402
ec.READBACK_SLEEP = 0

NOTE = "Corrected on 9 November 2026: Microsoft 60,000 buyout offer removed."


class _Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._body


class EditionCorrection(unittest.TestCase):
    def test_note_rules(self):
        self.assertEqual(ec.validate("weekly", "2026-W45", NOTE), [])
        self.assertTrue(ec.validate("weekly", "2026-45", NOTE))
        self.assertTrue(ec.validate("monthly", "2026-W45", NOTE))
        self.assertTrue(ec.validate("weekly", "2026-W45", ""))
        self.assertTrue(ec.validate("weekly", "2026-W45", "x" * 1001))
        self.assertTrue(ec.validate("weekly", "2026-W45", "a — b"), "em-dash refused")

    def test_dry_run_writes_nothing(self):
        with mock.patch.object(ec.requests, "post") as post:
            rc = ec.run("weekly", "2026-W45", NOTE, apply=False, site="https://s", key="k")
        self.assertEqual(rc, 0)
        post.assert_not_called()

    def test_apply_posts_keyed_and_reads_back(self):
        page = _Resp(text="<p>2026-11-09: " + NOTE + "</p>")
        with mock.patch.object(ec.requests, "post", return_value=_Resp(200, {"ok": True})) as post, \
                mock.patch.object(ec.requests, "get", return_value=page):
            rc = ec.run("weekly", "2026-W45", NOTE, apply=True, site="https://s", key="k")
        self.assertEqual(rc, 0)
        args, kw = post.call_args
        self.assertTrue(args[0].endswith("/wp-json/layoffs/v1/edition-correction"))
        self.assertEqual(kw["headers"]["X-Layoff-API-Key"], "k")
        self.assertEqual(kw["json"], {"freq": "weekly", "slug": "2026-W45", "note": NOTE})

    def test_apply_fails_loudly(self):
        with mock.patch.object(ec.requests, "post", return_value=_Resp(400, {"ok": False})):
            self.assertEqual(ec.run("weekly", "2026-W45", NOTE, apply=True, site="https://s", key="k"), 1)
        with mock.patch.object(ec.requests, "post", return_value=_Resp(200, {"ok": True})), \
                mock.patch.object(ec.requests, "get", return_value=_Resp(text="no note here")):
            self.assertEqual(ec.run("weekly", "2026-W45", NOTE, apply=True, site="https://s", key="k"), 1)
        self.assertEqual(ec.run("weekly", "2026-W45", NOTE, apply=True, site="https://s", key=""), 1)


if __name__ == "__main__":
    unittest.main()
