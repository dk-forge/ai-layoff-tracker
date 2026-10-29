"""The tracker's filter fields keep a 3:1 edge and a 44px target in both themes.

The site theme ships `input, textarea, select { border: 1px solid
var(--atr-border) !important; ... }`. --atr-border is a panel hairline:
#b89f70 on white is 2.55:1 and #5e574a on the dark page is 2.39:1, so every
<input> and <select> in the filter bar failed WCAG 1.4.11 and the deploy step
"Verify the deployed page is readable in both themes" went red on 7 controls.
layoffs.css takes the edge back with !important and --alt-control-border. This
reads that rule as text and measures the token against every background in
both themes, the way test_blog_applause_theme.py does for the applause block.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.css"

# Every field the audit's FILTER_CONTROLS reaches that is an <input>/<select>.
FIELDS = (
    "#alt-search",
    "#alt-sort",
    '.alt-filter input[type="text"]',
    '.alt-filter input[type="number"]',
    '.alt-filter input[type="date"]',
    ".alt-filter select:not([multiple])",
    '#alt-range-pop input[type="date"]',
)

# Backgrounds a field edge sits between: the plugin's own surfaces and the
# theme's --atr-surface / --atr-bg, which the theme may still paint around it.
BACKGROUNDS = {
    "light": ("#ffffff", "#fafaf8", "#f4f1ea"),
    "dark": ("#191c23", "#1c1c1c", "#252525", "#2d2d2c"),
}


def _lum(hex_):
    rgb = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _src():
    return re.sub(r"/\*.*?\*/", " ", CSS.read_text(encoding="utf-8"),
                  flags=re.S)


def _override_body():
    src = _src()
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", src):
        sels = {s.strip() for s in m.group(1).split(",")}
        if set(FIELDS) <= sels and "!important" in m.group(2):
            return m.group(2)
    raise AssertionError("no !important rule covers every filter field")


def _control_border_values():
    return re.findall(r"--alt-control-border:\s*(#[0-9a-fA-F]{6})", _src())


class FilterFieldsBeatTheThemeBorder(unittest.TestCase):

    def test_the_edge_and_fill_are_the_plugin_tokens_and_important(self):
        body = _override_body()
        self.assertRegex(
            body, r"border:\s*1px solid var\(--alt-control-border\)\s*!important")
        self.assertRegex(body, r"background:\s*var\(--alt-surface\)\s*!important")
        self.assertNotIn("--atr-border", body)

    def test_the_target_is_the_control_height_token(self):
        self.assertRegex(_override_body(), r"min-height:\s*var\(--alt-ctl-h\)")
        src = _src()
        self.assertRegex(
            src, r"max-width:\s*767px\)\s*\{\s*:root\s*\{\s*--alt-ctl-h:\s*44px")

    def test_the_edge_clears_3_to_1_in_both_themes(self):
        values = _control_border_values()
        self.assertGreaterEqual(len(values), 3, values)
        light, dark = values[0], values[1:]
        for bg in BACKGROUNDS["light"]:
            self.assertGreaterEqual(_ratio(light, bg), 3.0, (light, bg))
        for edge in dark:
            for bg in BACKGROUNDS["dark"]:
                self.assertGreaterEqual(_ratio(edge, bg), 3.0, (edge, bg))

    def test_the_theme_hairline_would_fail(self):
        # Guards the premise: if the theme token ever clears 3:1 on its own
        # this override is no longer the thing holding the line.
        self.assertLess(_ratio("#b89f70", "#ffffff"), 3.0)
        self.assertLess(_ratio("#5e574a", "#191c23"), 3.0)


if __name__ == "__main__":
    unittest.main()
