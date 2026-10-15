"""The subscriber email redesign (owner decision 2026-10-15).

Shared visual spec (railway/email_theme.py), inline PNG charts that fetch
nothing (railway/email_charts.py), the dark-mode override, and the transport
gate that admits an image ONLY when it is one of the message's own parts.
Offline: no network, no recipient, no send.
"""
import base64
import os
import re
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import digest_preview                     # noqa: E402
import digest_transport as dt             # noqa: E402
import email_charts                       # noqa: E402
import email_theme                        # noqa: E402


def _png_size(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", png[16:24])


def _png_pixels(png):
    """Decode our own (filter 0, RGBA) PNG back to rows."""
    w, h = _png_size(png)
    pos, data = 8, b""
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        kind = png[pos + 4:pos + 8]
        if kind == b"IDAT":
            data += png[pos + 8:pos + 8 + n]
        pos += 12 + n
    raw = zlib.decompress(data)
    stride = w * 4 + 1
    return [raw[i * stride + 1:(i + 1) * stride] for i in range(h)]


class SharedSpec(unittest.TestCase):
    def test_tokens_are_the_owner_spec(self):
        self.assertEqual(email_theme.FONT,
                         "-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif")
        self.assertEqual((email_theme.INK, email_theme.MUTED, email_theme.BACKGROUND,
                          email_theme.PANEL, email_theme.BORDER, email_theme.ACCENT),
                         ("#111827", "#4b5563", "#ffffff", "#f3f4f6", "#e5e7eb", "#1d4ed8"))
        self.assertEqual((email_theme.DARK_BG, email_theme.DARK_PANEL, email_theme.DARK_INK,
                          email_theme.DARK_MUTED, email_theme.DARK_ACCENT),
                         ("#0b1220", "#111a2e", "#e5e7eb", "#9ca3af", "#93c5fd"))
        self.assertEqual(email_theme.RADIUS_PX, 8)

    def test_every_text_pair_clears_wcag_aa_in_both_modes(self):
        for fg, bg in email_theme.LIGHT_PAIRS + email_theme.DARK_PAIRS:
            self.assertGreaterEqual(email_theme.contrast(fg, bg), 4.5, (fg, bg))

    def test_the_module_imports_nothing_from_this_tracker(self):
        with open(email_theme.__file__, encoding="utf-8") as fh:
            src = fh.read()
        imports = re.findall(r"^(?:from|import)\s+(\S+)", src, re.M)
        self.assertTrue(set(imports) <= {"__future__", "html"}, imports)

    def test_the_style_block_is_dark_only(self):
        block = email_theme.dark_style_block()
        self.assertEqual(block.count("@media"), 1)
        self.assertIn("@media (prefers-color-scheme: dark){", block)
        self.assertNotIn("url(", block)
        self.assertNotIn("@import", block)


class Charts(unittest.TestCase):
    def test_png_is_valid_transparent_and_deterministic(self):
        a = email_charts.column_chart([3, 1, 2], "#e5484d")
        self.assertEqual(a, email_charts.column_chart([3, 1, 2], "#e5484d"))
        self.assertEqual(_png_size(a), (email_charts.WIDTH, email_charts.HEIGHT))
        rows = _png_pixels(a)
        self.assertEqual(rows[0][3], 0, "the corner must be transparent")

    def test_marks_clear_3_to_1_on_both_cards(self):
        for colour in email_charts.CHART_COLOURS.values():
            self.assertGreaterEqual(email_theme.contrast(colour, email_theme.BACKGROUND), 3.0, colour)
            self.assertGreaterEqual(email_theme.contrast(colour, email_theme.DARK_PANEL), 3.0, colour)

    def test_empty_series_draws_nothing_rather_than_a_wrong_chart(self):
        rows = _png_pixels(email_charts.column_chart([0, 0], "#3b82f6"))
        self.assertTrue(all(px == 0 for px in rows[0]))


class TheMessage(unittest.TestCase):
    def setUp(self):
        self.msg = digest_preview.sample_message()

    def test_one_to_three_inline_charts_with_every_figure_in_alt(self):
        self.assertTrue(1 <= len(self.msg.images) <= email_charts.MAX_CHARTS)
        alt = self.msg.images[0]["alt"]
        for fig in ("31,400", "28,900", "48,910"):
            self.assertIn(fig, alt)
            self.assertIn(fig, self.msg.html)  # also printed as text
            self.assertIn(fig, self.msg.text)

    def test_every_img_is_an_own_cid_part(self):
        cids = {i["cid"] for i in self.msg.images}
        srcs = re.findall(r'<img src="([^"]+)"', self.msg.html)
        self.assertEqual(len(srcs), len(cids))
        for src in srcs:
            self.assertTrue(src.startswith("cid:") and src[4:] in cids)
        self.assertNotIn("http", " ".join(srcs))

    def test_shell(self):
        html = self.msg.html
        self.assertIn('<meta name="color-scheme" content="light dark">', html)
        self.assertIn(email_theme.dark_style_block(), html)
        self.assertIn("max-width:600px", html)
        self.assertIn("border-radius:8px", html)
        self.assertIn(">AskTheRecruiter</p>", html)
        self.assertIn("font-variant:small-caps", html)
        self.assertIn("48,910</p>", html, "the headline number is text")
        self.assertIn('href="https://asktherecruiter.com/blog/r/9"', html)
        self.assertNotIn("—", html + self.msg.text)

    def test_the_clean_check_passes(self):
        dt.assert_message_is_clean(self.msg)


class TheGateStillRefusesEveryRemoteFetch(unittest.TestCase):
    def setUp(self):
        self.msg = digest_preview.sample_message()

    def _with(self, html=None, images=None):
        return dt.Message(to=self.msg.to, subject=self.msg.subject,
                          html=self.msg.html if html is None else html,
                          text=self.msg.text, from_addr=self.msg.from_addr,
                          reply_to=self.msg.reply_to, headers=self.msg.headers,
                          images=self.msg.images if images is None else images)

    def test_a_remote_pixel_is_refused(self):
        bad = self.msg.html.replace("</body>",
                                    '<img src="https://p.example/o.gif" alt="x"></body>')
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(html=bad))

    def test_a_cid_with_no_part_is_refused(self):
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(images=()))

    def test_a_part_that_is_not_a_png_is_refused(self):
        fake = tuple(dict(i, png=b"GIF89a") for i in self.msg.images)
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(images=fake))

    def test_an_image_without_alt_is_refused(self):
        bad = re.sub(r' alt="[^"]*"', "", self.msg.html, count=1)
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(html=bad))

    def test_a_light_mode_style_block_is_refused(self):
        bad = self.msg.html.replace("</head>", "<style>p{color:red}</style></head>")
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(html=bad))

    def test_a_url_in_the_style_block_is_refused(self):
        bad = self.msg.html.replace(".et-page{", ".et-page{background:url(https://x.example/a.png);", 1)
        with self.assertRaises(dt.DigestPolicyError):
            dt.assert_message_is_clean(self._with(html=bad))


class Transports(unittest.TestCase):
    def setUp(self):
        self.msg = digest_preview.sample_message()

    def test_smtp_carries_charts_as_related_inline_parts(self):
        mail = dt.SmtpTransport("smtp.example.invalid", 587, "u", "p")._build(self.msg)
        raw = mail.as_string()
        self.assertIn("multipart/related", raw)
        for image in self.msg.images:
            self.assertIn(f"Content-ID: <{image['cid']}>", raw)
        self.assertIn("text/plain", raw)

    def test_resend_carries_charts_with_content_ids(self):
        captured = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"id":"x"}'

        def opener(request, timeout=0):
            import json
            captured.update(json.loads(request.data))
            return Resp()

        dt.ResendTransport("k", opener=opener)._deliver(self.msg)
        ids = [a["content_id"] for a in captured["attachments"]]
        self.assertEqual(ids, [i["cid"] for i in self.msg.images])
        self.assertTrue(base64.b64decode(captured["attachments"][0]["content"]).startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
