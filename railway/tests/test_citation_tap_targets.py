"""THE CITATION PAGE CLEARS THE 44px FLOOR TOO.

The single-entry page (/blog/layoff/{company}-{date}) is the surface a
journalist opens from a citation, and it was never in the tap-target sweep that
the tracker and the five secondary pages pass (test_tap_targets.py). Measured on
the live page at 375px, its primary source button was ~36.8px tall and the
"All layoffs" back link ~18px, both under WCAG 2.5.5's 44px floor.

This renders the two controls in headless Chrome at 375px and asserts each is at
least 44px tall, then removes the CSS block that fixes them and asserts they go
BACK under 44px, because a guard that cannot see the defect is not evidence.

No Chrome, no measurement: this SKIPS loudly rather than passing. Absence of a
signal is not a pass (CLAUDE.md).
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"

TAP_MIN = 44.0

# The real markup single-layoff.php emits, with realistic text (the template
# echoes its label through PHP, so a PHP-stripped fixture would measure an empty
# box). The classes and nesting are exactly the template's.
SINGLE_MARKUP = """
<div class="alt-wrap alt-single">
  <a class="alt-back" href="#">&larr; All layoffs</a>
  <h1 class="alt-single-title">Acme Corporation</h1>
  <div class="alt-single-stat">1,200 jobs cut &middot; 2026-08-01</div>
  <p><a class="alt-btn alt-btn-primary" href="#" target="_blank" rel="noopener nofollow">View source report (Reuters) &#8599;</a></p>
</div>
"""

THEME_SHIM = "body { background:#fff; color:#16181d; margin:0; font-family: system-ui, sans-serif; }"

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>%(theme)s</style>
</head>
<body class="wp-singular page">
<div class="wp-site-blocks"><main class="wp-block-group">
<div class="entry-content">
%(markup)s
</div></main></div>
</body></html>
"""

PROBE = r"""
(function () {
  function box(sel) {
    var el = document.querySelector(sel);
    if (!el) return null;
    var r = el.getBoundingClientRect();
    return { w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10,
             text: (el.innerText || '').trim().slice(0, 40) };
  }
  return { btn: box('.alt-single .alt-btn-primary'),
           back: box('.alt-single .alt-back') };
})()
"""


def strip_citation_block(css):
    """Reconstruct the page as it was: no 44px floor on this page's controls.

    This is the measured pre-fix state. If the guard cannot be made to fail on
    it, it is not evidence.
    """
    a = css.find("/* CITATION-PAGE TAP TARGETS")
    b = css.find("/* END CITATION-PAGE TAP TARGETS */")
    assert a >= 0 and b >= 0, "the citation tap-target block is gone from layoffs.css"
    out = css[:a] + css[b + len("/* END CITATION-PAGE TAP TARGETS */"):]
    assert out != css, "removing the block changed nothing"
    return out


class _Rendered(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so citation tap targets "
                "could not be measured. UNKNOWN, not a pass.")

    def measure(self, css, width=375):
        html = FIXTURE % {"plugin": css, "theme": THEME_SHIM, "markup": SINGLE_MARKUP}
        try:
            with Browser(width=width, height=812) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                return page.eval_js(PROBE)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)


class TheCitationPageControlsClearTheFloor(_Rendered):

    def test_the_fixture_rendered_both_controls(self):
        got = self.measure(CSS.read_text())
        self.assertIsNotNone(got["btn"], "the source button did not render")
        self.assertIsNotNone(got["back"], "the back link did not render")

    def test_the_source_button_is_at_least_44_tall_at_375(self):
        got = self.measure(CSS.read_text())
        self.assertGreaterEqual(
            got["btn"]["h"], TAP_MIN,
            "the citation page's source button is %.1fpx tall at 375px (%r)"
            % (got["btn"]["h"], got["btn"]["text"]))

    def test_the_back_link_is_at_least_44_tall_at_375(self):
        got = self.measure(CSS.read_text())
        self.assertGreaterEqual(
            got["back"]["h"], TAP_MIN,
            "the citation page's back link is %.1fpx tall at 375px"
            % got["back"]["h"])

    def test_the_guard_fails_on_the_page_as_it_was(self):
        """The half that makes the halves above evidence: with the fix removed
        both controls must measure under the floor."""
        got = self.measure(strip_citation_block(CSS.read_text()))
        self.assertTrue(
            got["btn"]["h"] < TAP_MIN or got["back"]["h"] < TAP_MIN,
            "the pre-fix stylesheet produced no undersized control (button "
            "%.1fpx, back %.1fpx), so this guard cannot see the defect it was "
            "written for" % (got["btn"]["h"], got["back"]["h"]))

    def test_the_desktop_layout_is_untouched(self):
        """The brief was mobile. The 44px floor must not leak to the desk,
        where these are hit with a pointer."""
        got = self.measure(CSS.read_text(), width=1280)
        self.assertLess(
            got["back"]["h"], TAP_MIN,
            "the 44px phone floor leaked to the desktop layout: the back link "
            "is %.1fpx tall at 1280px" % got["back"]["h"])


class TheCssBlockIsScopedToAPhone(unittest.TestCase):
    """Source check: at a desk these are pointer targets and the page is denser
    by design, so the floor must be inside a <=767px media query."""

    def test_the_block_is_inside_a_max_width_767_query(self):
        css = CSS.read_text()
        a = css.find("/* CITATION-PAGE TAP TARGETS")
        b = css.find("/* END CITATION-PAGE TAP TARGETS */")
        self.assertTrue(a >= 0 and b >= 0, "the citation tap-target block is gone")
        block = css[a:b]
        self.assertRegex(
            block, r"@media\s*\(max-width:\s*767px\)",
            "the citation tap-target rules are not scoped to <=767px")


if __name__ == "__main__":
    unittest.main()
