"""The public Email Archive copy of each sent edition.

What is under test is the PROMISE a public page makes about a private email:
nothing in the archived copy belongs to a reader. No unsubscribe or
preferences link (both are signed per reader), no address, no tracking image,
and the same input always writes the same bytes, so a re-run commits nothing.
"""
import json
import os
import re
import sys
import tempfile
import unittest

RAILWAY = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_archive as da   # noqa: E402

UNSUB = ("https://asktherecruiter.com/blog/wp-admin/admin-post.php"
         "?action=alt_digest_unsub&t=" + "a" * 64)
MANAGE = "https://asktherecruiter.com/blog/digest-preferences/?t=" + "b" * 64


def _payload(freq="daily", **over):
    base = {
        "available": True, "freq": freq, "send_id": 9,
        "from": "2026-10-10", "to": "2026-10-11",
        "sections": {
            "layoff": {"html": "<h2>AI Layoff Tracker</h2><p>12 verified entries.</p>",
                       "text": "AI Layoff Tracker\n12 verified entries.\n"},
            "talent": {"html": "<h2>Talent</h2><p>Contact desk@example.com</p>",
                       "text": "Talent\n"},
        },
        "recipients": [
            {"id": 1, "email": "reader@example.com", "unsub_url": UNSUB,
             "manage_url": MANAGE, "lists": ["layoff"]},
            {"id": 2, "email": "other@example.com", "unsub_url": UNSUB,
             "manage_url": MANAGE, "lists": ["layoff", "talent"]},
        ],
    }
    base.update(over)
    return base


class Sanitize(unittest.TestCase):
    def setUp(self):
        self.edition = da.edition_from_payload(_payload(), "daily")
        self.html = self.edition["html"]

    def test_no_unsubscribe_or_preferences_link_or_wording(self):
        low = self.html.lower()
        self.assertNotIn("unsubscrib", low)
        self.assertNotIn("preferences", low)
        self.assertNotIn("alt_digest_unsub", low)
        self.assertNotIn("a" * 64, self.html)
        self.assertNotIn("b" * 64, self.html)

    def test_no_email_address_survives(self):
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", self.html))

    def test_no_image_at_all(self):
        self.assertNotIn("<img", self.html.lower())

    def test_the_reader_with_the_most_lists_is_the_one_archived(self):
        self.assertEqual(self.edition["sections"], ["layoff", "talent"])
        self.assertIn("12 verified entries", self.html)

    def test_the_postal_address_stays(self):
        self.assertIn("AskTheRecruiter, Netherlands", self.html)

    def test_deterministic(self):
        again = da.edition_from_payload(_payload(), "daily")
        self.assertEqual(again, self.edition)

    def test_sanitize_strips_tracking_pixels_and_token_links(self):
        raw = ('<p>x</p><img src="https://p.example/a.gif" width="1" height="1">'
               '<img style="width:1px;height:1px" src="https://p.example/b.gif">'
               '<a href="https://asktherecruiter.com/x?token=zz">open</a>'
               '<p>Write to someone@example.org today.</p>')
        out = da.sanitize_html(raw)
        self.assertNotIn("<img", out)
        self.assertNotIn("token=", out)
        self.assertIn("open", out)
        self.assertNotIn("@", out)

    def test_monthly_is_not_archived(self):
        self.assertIsNone(da.edition_from_payload(_payload("monthly"), "monthly"))


class WriteAndIndex(unittest.TestCase):
    def test_files_and_index_written_idempotently(self):
        edition = da.edition_from_payload(_payload(), "daily")
        with tempfile.TemporaryDirectory() as root:
            da.write_edition(root, edition)
            base = os.path.join(root, "2026", "10", "2026-10-11-daily")
            self.assertTrue(os.path.exists(base + ".html"))
            with open(base + ".json") as fh:
                meta = json.load(fh)
            self.assertEqual(meta["kind"], "daily")
            self.assertEqual(meta["date"], "2026-10-11")
            self.assertEqual(meta["slug"], "2026-10-11-daily")
            with open(os.path.join(root, "index.json")) as fh:
                first = fh.read()
            da.write_edition(root, edition)
            with open(os.path.join(root, "index.json")) as fh:
                self.assertEqual(fh.read(), first)
            da.write_edition(root, da.edition_from_payload(_payload("weekly"), "weekly"))
            da.write_edition(root, da.edition_from_payload(_payload(to="2026-10-01"), "daily"))
            with open(os.path.join(root, "index.json")) as fh:
                index = json.load(fh)
            slugs = [e["slug"] for e in index["editions"]]
            self.assertEqual(slugs, ["2026-10-11-weekly", "2026-10-11-daily",
                                     "2026-10-01-daily"])
            self.assertEqual(index["editions"][0]["path"],
                             "2026/10/2026-10-11-weekly.html")


class Gating(unittest.TestCase):
    def test_writes_nothing_without_a_destination(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(da.archive_sent_edition(_payload(), "daily"))

    def test_writes_to_the_named_directory(self):
        with tempfile.TemporaryDirectory() as root:
            rel = da.archive_sent_edition(_payload(), "daily", root=root)
            self.assertEqual(rel, "2026/10/2026-10-11-daily")
            self.assertTrue(os.path.exists(os.path.join(root, "index.json")))


if __name__ == "__main__":
    unittest.main()
