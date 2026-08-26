"""THE SOURCE-DIRECTORY TABLES ARE NAMED, FOCUSABLE SCROLL REGIONS.

The Sources page carries four horizontally-scrollable directory tables
(country/outlet, catalogue, global authorities, jurisdictions), each inside a
.alt-health-table-wrap. That wrapper scrolled on a phone but was an anonymous,
unfocusable box: a screen reader did not announce it, a keyboard could not reach
it to scroll, and nothing told a touch reader there was more table off the right
edge (external review, mobile audit).

enhanceScrollRegions() in layoffs.js upgrades each wrap in place. This test lifts
that real function (and its two helpers) out of layoffs.js and RUNS them in
headless Chrome against a fixture DOM, then reads the result back:

  - the wrap gains role="region", tabindex="0" and an aria-label naming it;
  - a wide table (overflowing at 375px) gets .alt-scroll-more and a
    .alt-scroll-hint sibling, so the CSS cue shows;
  - a table that fits does NOT get .alt-scroll-more, so the cue stays hidden.

No Chrome, no measurement: this SKIPS loudly rather than passing.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import jsrun  # noqa: E402
from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = (PLUGIN / "assets/layoffs.css").read_text()

# The real function bodies, byte for byte off disk. If any is renamed, extract
# raises rather than testing nothing.
BODIES = "\n".join(jsrun.extract(n) for n in
                   ("enhanceScrollRegions", "scrollRegionLabel", "refreshScrollCue"))

# One wide table (many columns, forced past 375px) and one narrow table that
# fits. Both in the .alt-health-table-wrap the real page uses; the wide one is
# inside <details><summary> the way the generated country table is.
FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%s</style>
<style>
  body { margin: 0; font-family: system-ui, sans-serif; }
  .wide td, .wide th { white-space: nowrap; padding: 8px 16px; }
  .wide { width: 1400px; }
</style>
</head><body>
<main class="alt-wrap alt-sources-page">
  <details class="alt-health-section" open>
    <summary><b>Every country and every outlet we scan</b>, generated from the allowlist</summary>
    <div class="alt-health-table-wrap"><table class="wide"><thead><tr>
      <th>Country</th><th>Official sources</th><th>News outlets scanned</th><th>News scan status</th><th>More</th><th>Even more</th>
    </tr></thead><tbody><tr>
      <td>United States</td><td>WARN + SEC EDGAR</td><td>Reuters, Bloomberg, WSJ, NYT, AP, CNBC</td><td>Active</td><td>x</td><td>y</td>
    </tr></tbody></table></div>
  </details>
  <h2>A narrow one</h2>
  <div class="alt-health-table-wrap" id="narrow"><table><thead><tr><th>A</th><th>B</th></tr></thead>
    <tbody><tr><td>1</td><td>2</td></tr></tbody></table></div>
</main>
</body></html>
"""

PROBE = r"""
(function () {
  enhanceScrollRegions();
  function read(el) {
    if (!el) return null;
    var next = el.nextElementSibling;
    return {
      role: el.getAttribute('role'),
      tabindex: el.getAttribute('tabindex'),
      aria: el.getAttribute('aria-label') || '',
      more: el.classList.contains('alt-scroll-more'),
      hintText: (next && next.classList && next.classList.contains('alt-scroll-hint'))
                  ? (next.textContent || '').trim() : null
    };
  }
  var wraps = document.querySelectorAll('.alt-health-table-wrap');
  return { wide: read(wraps[0]), narrow: read(document.getElementById('narrow')),
           count: wraps.length };
})()
"""


class TheScrollRegionsAreAccessible(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine; scroll-region a11y could "
                "not be measured. UNKNOWN, not a pass.")

    def _run(self, width=375):
        html = FIXTURE % CSS
        try:
            with Browser(width=width, height=812) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                page.eval_js(BODIES + "\ntrue;")
                return page.eval_js(PROBE)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)

    def test_both_wraps_were_found(self):
        got = self._run()
        self.assertEqual(got["count"], 2, "the fixture did not render two wraps")

    def test_the_wrap_becomes_a_named_focusable_region(self):
        w = self._run()["wide"]
        self.assertEqual(w["role"], "region", "the wrap did not become a region")
        self.assertEqual(w["tabindex"], "0", "the wrap is not keyboard-focusable")
        self.assertIn("scrollable table", w["aria"].lower(),
                      "the region has no descriptive aria-label: %r" % w["aria"])
        self.assertIn("every country", w["aria"].lower(),
                      "the region label does not derive from its heading: %r" % w["aria"])

    def test_an_overflowing_table_advertises_the_swipe(self):
        w = self._run()["wide"]
        self.assertTrue(w["more"],
                        "a table wider than 375px did not get .alt-scroll-more")
        self.assertIsNotNone(w["hintText"], "no swipe hint sibling was created")
        self.assertIn("swipe", w["hintText"].lower(),
                      "the swipe hint does not say swipe: %r" % w["hintText"])

    def test_a_table_that_fits_does_not_advertise_a_swipe(self):
        n = self._run()["narrow"]
        self.assertFalse(n["more"],
                         "a table that fits at 375px was marked overflowing, so "
                         "the swipe cue would show when there is nothing to swipe to")

    def test_the_css_hint_is_hidden_until_overflow_on_a_phone(self):
        """Source check on the CSS half: the hint is display:none by default and
        only shown for an overflowing wrap under 767px."""
        self.assertIn(".alt-scroll-hint { display: none;", CSS)
        self.assertIn(
            ".alt-health-table-wrap.alt-scroll-more + .alt-scroll-hint { display: block; }",
            CSS)


if __name__ == "__main__":
    unittest.main()
