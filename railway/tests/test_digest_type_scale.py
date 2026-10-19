"""One type scale (owner, 2026-10-19: "formatting isn't good on the
newsletters, still various text sizes and styles").

Both editions, composed by the real PHP composers from fixture data and laid
out by the real sender, are parsed and every font-size in every style
attribute must be one of digest_layout.TYPE_SCALE. Two values are exempt and
neither is type: 0 on a table-bar cell, and 1px in the hidden preheader.
A stray size cannot creep back in without failing this.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

import digest_layout as layout  # noqa: E402
import digest_send  # noqa: E402
import test_digest_email_layout as L  # noqa: E402
from test_digest_talent_activity import compose, PHP  # noqa: E402
from test_digest_geography import talent  # noqa: E402
from test_digest_dimension_blocks import layoff_fixture  # noqa: E402

_STYLE = re.compile(r'style\s*=\s*"([^"]*)"', re.I)
_SIZE = re.compile(r"font-size\s*:\s*([^;]+)", re.I)
ALLOWED = {f"{n}px" for n in layout.TYPE_SCALE} | {"0", "1px"}


def sizes(html):
    found = set()
    for style in _STYLE.findall(html):
        for value in _SIZE.findall(style):
            found.add(value.strip())
    return found


def edition(key, part, freq):
    data = L.payload((key,), freq=freq)
    data["sections"][key] = {"html": part["html"], "text": part["text"]}
    return digest_send.build_message(data, data["recipients"][0],
                                     L.FROM, L.REPLY).html


class Scale(unittest.TestCase):
    def test_scale_is_five_ordered_steps(self):
        self.assertEqual(len(set(layout.TYPE_SCALE)), 5)
        self.assertGreater(layout.TYPE_STAT, layout.TYPE_TITLE)
        self.assertGreater(layout.TYPE_TITLE, layout.TYPE_HEADING)
        self.assertGreater(layout.TYPE_HEADING, layout.TYPE_BODY)
        self.assertGreater(layout.TYPE_BODY, layout.TYPE_SMALL)

    def test_fixture_messages_use_only_the_scale(self):
        html = L.message(("layoff", "talent", "articles")).html
        self.assertEqual(sizes(html) - ALLOWED, set())


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class ComposedEditions(unittest.TestCase):
    def test_alt_weekly_uses_only_the_scale(self):
        html = edition("layoff", compose(layoff_fixture()), "weekly")
        self.assertEqual(sizes(html) - ALLOWED, set())
        self.assertIn(f"font-size:{layout.TYPE_STAT}px", html)

    def test_tit_daily_uses_only_the_scale(self):
        html = edition("talent", compose(talent()), "daily")
        self.assertEqual(sizes(html) - ALLOWED, set())

    def test_every_section_heading_has_one_style(self):
        html = edition("layoff", compose(layoff_fixture()), "weekly")
        html += edition("talent", compose(talent()), "daily")
        h3 = set(re.findall(r"<h3 style=\"([^\"]*)\"", html))
        normal = {re.sub(r"color:#[0-9a-fA-F]+;?", "", s) for s in h3}
        self.assertEqual(len(normal), 1, normal)


if __name__ == "__main__":
    unittest.main()
