"""The public digest archive: /ai-layoff-tracker/digest/ and /<date>/.

Owner decision 2026-10-15. The archive copy must carry NO subscriber data, no
personal unsubscribe or preferences link and no tracking pixel. Two gates hold
that, and both are tested here: the Python cleaner and record check
(digest_archive.public_record / assert_public) and the plugin's own refusal
(alt_digest_pub_is_public), run as REAL PHP against the real record.
Offline: PHP runs locally with WordPress stubbed; nothing touches the site.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import digest_archive  # noqa: E402
import digest_preview  # noqa: E402

PHP_FILE = (Path(__file__).resolve().parents[2]
            / "wordpress-plugin/ai-layoff-tracker/includes/digest-public-archive.php")
STUBS = ("define('ABSPATH','/');define('ALT_VERSION','t');"
         "function add_action(){}function add_filter(){}"
         "function home_url($p=''){return 'https://asktherecruiter.com/blog'.$p;}"
         "function wp_json_encode($v,$f=0){return json_encode($v,$f);}")


def php(expr, data=None):
    code = (STUBS + f"require {json.dumps(str(PHP_FILE))};"
            "$in=json_decode(stream_get_contents(STDIN),true);"
            f"echo json_encode({expr});")
    out = subprocess.run(["php", "-r", code], input=json.dumps(data),
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class PythonRecord(unittest.TestCase):
    def setUp(self):
        self.payload = digest_preview.sample_payload()
        self.record = digest_archive.public_record(self.payload, "weekly")
        self.recipient = self.payload["recipients"][0]

    def test_no_subscriber_data_survives(self):
        blob = self.record["html"] + self.record["text"] + self.record["subject"]
        for secret in (self.recipient["email"], self.recipient["unsub_url"],
                       self.recipient["manage_url"], "a" * 64, "b" * 64):
            self.assertNotIn(secret, blob)
        low = blob.lower()
        for marker in ("unsub", "preferences/", "alt_digest_", "mailto:", "@"):
            self.assertNotIn(marker, low)
        digest_archive.assert_public(self.record)

    def test_no_tracking_pixel_and_only_our_own_charts(self):
        import re
        imgs = re.findall(r"<img\b[^>]*>", self.record["html"])
        self.assertEqual(len(imgs), len(self.record["charts"]))
        for img in imgs:
            self.assertRegex(img, r'^<img src="cid:chart-[1-3]"')

    def test_a_relay_pixel_is_stripped_even_if_injected(self):
        html = '<p>x</p><img src="https://pixel.example/o.gif" width="1">'
        self.assertNotIn("<img", digest_archive.sanitize_html(html, keep_charts=True))

    def test_assert_public_refuses_a_leak(self):
        for leak in ("reader@example.com", "https://x/?t=abc",
                     '<img src="https://p.example/o.gif">', "unsubscribe here"):
            bad = dict(self.record, html=self.record["html"] + leak)
            with self.assertRaises(ValueError, msg=leak):
                digest_archive.assert_public(bad)

    def test_posting_is_through_the_keyed_call_and_never_raises(self):
        seen = {}

        def call(path, payload=None):
            seen["path"], seen["payload"] = path, payload
            return {"ok": True}

        digest_archive.post_public_record(self.payload, "weekly", call=call)
        self.assertEqual(seen["path"], "digest-archive")
        self.assertEqual(seen["payload"]["date"], "2026-10-12")

        def boom(path, payload=None):
            raise OSError("host down")
        self.assertIsNone(digest_archive.post_public_record(self.payload, "weekly", call=boom))

    def test_monthly_and_unknown_kinds_are_not_archived(self):
        self.assertIsNone(digest_archive.public_record(self.payload, "monthly"))


@unittest.skipUnless(shutil.which("php"), "no php binary: UNKNOWN, NOT RUN")
class PluginGate(unittest.TestCase):
    def setUp(self):
        self.record = digest_archive.public_record(digest_preview.sample_payload(), "weekly")

    def test_the_real_record_is_accepted(self):
        self.assertTrue(php("alt_digest_pub_is_public($in['html'],$in['text'])", self.record))

    def test_every_leak_is_refused_server_side(self):
        for leak in ("reader@example.com",
                     '<a href="https://asktherecruiter.com/blog/wp-admin/admin-post.php?action=alt_digest_unsub&t=aa">x</a>',
                     '<a href="https://asktherecruiter.com/blog/ai-layoff-tracker/preferences/1-bb/">x</a>',
                     '<img src="https://pixel.example/o.gif" alt="x">',
                     '<img src="cid:chart-1">',
                     "<script>1</script>",
                     '<p style="background:url(https://x.example/a)">x</p>'):
            with self.subTest(leak=leak):
                self.assertFalse(php("alt_digest_pub_is_public($in['h'],'')",
                                     {"h": self.record["html"] + leak}))

    def test_dates_ranges_and_precedence(self):
        self.assertEqual(php("alt_digest_pub_valid_date($in)", "2026-02-30"), "")
        self.assertEqual(php("alt_digest_pub_valid_date($in)", "2026-10-12"), "2026-10-12")
        rows = [{"edition_date": d} for d in ("2026-10-01", "2026-10-12", "2026-09-20")]
        got = php("alt_digest_pub_filter_range($in,'2026-09-25','')", rows)
        self.assertEqual([r["edition_date"] for r in got], ["2026-10-12", "2026-10-01"])
        got = php("alt_digest_pub_filter_range($in,'bogus','2026-10-01')", rows)
        self.assertEqual([r["edition_date"] for r in got], ["2026-10-01", "2026-09-20"])
        self.assertFalse(php("alt_digest_pub_should_replace('weekly','daily')"))
        self.assertTrue(php("alt_digest_pub_should_replace('daily','weekly')"))

    def test_charts_point_at_our_own_url(self):
        body = php("alt_digest_pub_body($in,'https://asktherecruiter.com/blog/ai-layoff-tracker/digest/2026-10-12/')",
                   self.record["html"])
        self.assertIn('src="https://asktherecruiter.com/blog/ai-layoff-tracker/digest/2026-10-12/chart-1.png"', body)
        self.assertNotIn("cid:", body)

    def test_jsonld_is_newsarticle_and_dataset(self):
        row = {"subject": self.record["subject"], "edition_date": "2026-10-12",
               "period_from": "2026-10-06", "kind": "weekly"}
        nodes = php("alt_digest_pub_jsonld($in,'https://u/','',"
                    "'2026-10-13T11:30:00+00:00')", row)
        self.assertEqual([n["@type"] for n in nodes], ["NewsArticle", "Dataset"])
        self.assertEqual(nodes[1]["temporalCoverage"], "2026-10-06/2026-10-12")

    def test_charts_decode_only_small_pngs(self):
        charts = self.record["charts"] + [{"n": 3, "alt": "x", "png": "R0lGODlh"}]
        got = php("array_keys(alt_digest_pub_decode_charts($in))", charts)
        self.assertEqual(got, [c["n"] for c in self.record["charts"]])


if __name__ == "__main__":
    unittest.main()
