"""The applause block on an article follows the page theme, light and dark.

blog-claps.css paints the block in --alt-cl-page, which falls back to #ffffff
when layoffs.css is not loaded. The blog never loads it, so on the theme's dark
page the block was a hard white box. assets/blog-reading.css section 8c rebinds
the component tokens to the page's --alt-read-* tokens, which the theme maps to
its --atr-* palette in both schemes. This reads that rule as text and checks
the contrast of every pair it produces against the theme's palette.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG_CSS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/blog-reading.css"
SELECTOR = "body.single-post .entry-content .alt-clap {"

# The theme's --atr-* values as served on the blog (2.20.281), and the
# plugin's own light literals for a page without the theme.
THEMES = {
    "theme light": {"panel": "#f4f1ea", "ink": "#20283a", "soft": "#404858",
                    "accent": "#4f7257", "accent_strong": "#0f1525",
                    "on_accent": "#fafaf8"},
    "theme dark": {"panel": "#2d2d2c", "ink": "#edece6", "soft": "#bcb8aa",
                   "accent": "#b7d0bb", "accent_strong": "#fafaf8",
                   "on_accent": "#1c1c1c"},
    "no theme": {"panel": "#eef1f5", "ink": "#23272b", "soft": "#55606a",
                 "accent": "#1c5cab", "accent_strong": "#16181d",
                 "on_accent": "#ffffff"},
}


def _lum(hex_):
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _rule():
    src = re.sub(r"/\*.*?\*/", " ", BLOG_CSS.read_text(encoding="utf-8"),
                 flags=re.S)
    i = src.find(SELECTOR)
    assert i > -1, "no rule %r in blog-reading.css" % SELECTOR
    return src[i + len(SELECTOR):src.index("}", i)]


class TheApplauseBlockFollowsTheTheme(unittest.TestCase):

    def test_the_block_is_not_painted_white(self):
        body = _rule()
        self.assertRegex(body, r"background:\s*var\(--alt-read-panel\)")
        self.assertNotRegex(body, r"#fff(fff)?\b\s*!important")

    def test_the_component_tokens_read_the_page_tokens(self):
        body = _rule()
        for token, source in (("--alt-cl-page", "--alt-read-panel"),
                              ("--alt-cl-ink", "--alt-read-ink"),
                              ("--alt-cl-note", "--alt-read-ink-soft"),
                              ("--alt-cl-accent", "--atr-primary-deep")):
            self.assertRegex(
                body, r"%s:\s*var\(%s[,)]" % (re.escape(token), re.escape(source)),
                "%s is not bound to %s, so it keeps its white-page literal "
                "on a dark article" % (token, source))

    def test_it_matches_the_digest_card(self):
        body = _rule()
        self.assertRegex(body, r"border:\s*1px solid var\(--alt-read-panel-edge\)")
        self.assertRegex(body, r"border-radius:\s*12px")

    def test_every_pair_meets_AA_in_both_schemes(self):
        bad = []
        for name, t in THEMES.items():
            for label, fg, bg, floor in (
                    ("ink", t["ink"], t["panel"], 4.5),
                    ("note", t["soft"], t["panel"], 4.5),
                    ("button label", t["accent"], t["panel"], 4.5),
                    ("hovered button", t["on_accent"], t["accent"], 4.5),
                    ("focus outline", t["accent_strong"], t["panel"], 3.0)):
                r = _ratio(fg, bg)
                if r < floor:
                    bad.append("%s %s: %s on %s = %.2f:1" % (name, label, fg, bg, r))
        self.assertEqual([], bad, "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
