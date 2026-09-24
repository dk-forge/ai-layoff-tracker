"""Every copied chart embed carries a visible, FOLLOWED source backlink + CC BY.

A link inside an iframe is on OUR page, not the host's, so it earns no
citation where the chart is published. The copyable snippet therefore adds a
plain paragraph under the iframe: "Source: AI Layoff Tracker" linking to the
tracker (no nofollow: this is the attribution CC BY 4.0 asks for) and the
licence link. The framed page repeats both in its own footer for readers.
"""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
JS = (PLUGIN / "assets" / "layoffs.js").read_text(encoding="utf-8")
EMBED = (PLUGIN / "templates" / "page-chart-embed.php").read_text(encoding="utf-8")


def _fn(src, name):
    start = src.index("function " + name + "(")
    return src[start:src.index("\n    }", start)]


class SnippetAttribution(unittest.TestCase):
    def test_snippet_has_a_followed_source_link(self):
        body = _fn(JS, "embedSnippet")
        self.assertIn("Source: ", body)
        self.assertIn(">AI Layoff Tracker</a>", body)
        # The source anchor must not be nofollowed.
        src_anchor = re.search(r"<a href=\"' \+ [^+]+ \+ '\"[^>]*>AI Layoff Tracker</a>", body)
        self.assertTrue(src_anchor, "source anchor not found in embedSnippet")
        self.assertNotIn("nofollow", src_anchor.group(0))

    def test_snippet_names_the_licence(self):
        body = _fn(JS, "embedSnippet")
        self.assertIn("https://creativecommons.org/licenses/by/4.0/", body)
        self.assertIn("CC BY 4.0", body)

    def test_the_popover_is_titled_and_explains_attribution(self):
        body = _fn(JS, "openEmbedPop")
        self.assertIn("Embed this chart", body)
        self.assertIn("CC BY 4.0", body)


class FramedPage(unittest.TestCase):
    def test_footer_says_source_and_licence(self):
        foot = EMBED[EMBED.index('<p class="alt-embed-foot">'):]
        foot = foot[:foot.index("</p>")]
        self.assertIn("Source: ", foot)
        self.assertIn("creativecommons.org/licenses/by/4.0/", foot)


if __name__ == "__main__":
    unittest.main()
