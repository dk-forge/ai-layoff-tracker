"""The pre-send gate refuses a bad render before any reader is mailed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import digest_gate  # noqa: E402
from digest_transport import Message  # noqa: E402

GOOD_HEADERS = {"List-Unsubscribe": "<https://x.test/u?t=1>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def msg(html="<p><a href='https://a.test/ok'>x</a><img src='cid:a' alt=''></p>",
        text="hello", headers=None):
    return Message(to="a@b.test", subject="s", html=html, text=text,
                   from_addr="f@b.test",
                   headers=GOOD_HEADERS if headers is None else headers)


class Structural(unittest.TestCase):
    def test_clean_passes(self):
        self.assertEqual(digest_gate.structural(msg()), [])

    def test_oversize_html(self):
        big = "<p>" + "x" * (digest_gate.MAX_HTML_BYTES + 1) + "</p>"
        self.assertTrue(any("bytes" in f for f in digest_gate.structural(msg(big))))

    def test_missing_text_part(self):
        self.assertTrue(any("text/plain" in f for f in digest_gate.structural(msg(text="  "))))

    def test_missing_unsubscribe_headers(self):
        f = digest_gate.structural(msg(headers={"List-Unsubscribe": "<https://x.test/u>"}))
        self.assertTrue(any("list-unsubscribe-post" in x for x in f))
        self.assertEqual(len(digest_gate.structural(msg(headers={}))), 2)

    def test_img_without_alt_fails_but_empty_alt_passes(self):
        self.assertTrue(digest_gate.structural(msg("<img src='cid:a'>")))
        self.assertEqual(digest_gate.structural(msg("<img src='cid:a' alt=''>")), [])


class Links(unittest.TestCase):
    def test_4xx_fails_3xx_ok_blockers_warn_unreachable_warns(self):
        codes = {"https://a.test/gone": 404, "https://a.test/moved": 301,
                 "https://b.test/walled": 403, "https://c.test/down": None}
        html = "".join(f"<a href='{u}'>l</a>" for u in codes)
        r = digest_gate.run_gate([msg(html)], check_network=True,
                                 status=lambda u: codes[u])
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["failures"]), 1)
        self.assertIn("404", r["failures"][0])
        self.assertEqual(len(r["warnings"]), 2)

    def test_reader_links_are_never_requested(self):
        asked = []
        html = ("<a href='https://x.test/u?t=1'>u</a>"
                "<a href='https://x.test/preferences/?t=9'>m</a>"
                "<a href='https://a.test/ok'>ok</a>")
        digest_gate.run_gate([msg(html)], check_network=True,
                             status=lambda u: asked.append(u) or 200)
        self.assertEqual(asked, ["https://a.test/ok"])

    def test_network_off_by_default(self):
        def boom(u):
            raise AssertionError("network used")
        r = digest_gate.run_gate([msg()], status=boom)
        self.assertTrue(r["ok"])


if __name__ == "__main__":
    unittest.main()
