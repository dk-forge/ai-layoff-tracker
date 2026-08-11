"""THE GUARD THAT WOULD HAVE CAUGHT THE UNREADABLE DARK PAGE.

Nothing in either repository evaluated what a page RENDERS AS in a non-default
theme. reader_freshness.py proves which VERSION of the bytes a reader is
served; every other front-end check reads the stylesheet as text. A site-level
rule living in the WordPress database - not in this repo, not in the sibling -
declared `color:#1a1a1a !important` on `.entry-content h2` and beat every token
the plugin owns. In light that is 16:1 and invisible as a problem. In dark it
put ~173 text elements between 1.06:1 and 1.28:1, which does not read as low
contrast, it reads as a page that failed to load. Every check in the repo was
green the entire time, because the defect only exists once the cascade
resolves, and nothing resolved a cascade.

So this file does two different jobs, and the second is the one that matters.

  1. It measures the CONTRACT: given the real layoffs.css and a faithful
     reproduction of the site override, does every text element clear WCAG AA
     in dark? That is the regression test for the fix.

  2. It measures the CHECKER: with the plugin's winning declarations removed,
     does the audit actually FAIL? A guard that cannot be made to fail is not
     evidence of anything, and this suite has already caught five checks that
     passed against defective code for the wrong reason.

Everything runs against a LOCAL fixture, so it needs no network and is safe in
CI. The live-site sweep is `railway/contrast_audit.py`, which is the same probe
pointed at the real pages; see .github/workflows/contrast-audit.yml.

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
import contrast_audit  # noqa: E402

CSS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.css"

# Copied verbatim off the live document head on 2026-08-10. This is the rule
# that lives in the WordPress database, and reproducing it exactly is the whole
# point: a fixture that omits it measures a page nobody is served.
SITE_OVERRIDE = """
.entry-content p ,.wp-block-post-content p  { font-size:1.05rem !important; line-height:1.78 !important; color:#2a2a2a !important; margin-bottom:1.2rem !important }
.entry-content h2,.wp-block-post-content h2 { font-size:1.45rem !important; font-weight:700 !important; color:#1a1a1a !important; border-bottom:2px solid #eef3ee !important }
.entry-content h3,.wp-block-post-content h3 { font-size:1.15rem !important; font-weight:600 !important; color:#222 !important }
"""

# The theme paints <body> from its own custom properties, which the plugin
# re-points under dark. Reproduced here because that indirection is exactly
# what made the defect survive: the background flipped and the ink did not.
THEME_SHIM = """
body { background-color: var(--wp--preset--color--base, #ffffff);
       color: var(--wp--preset--color--contrast, #16181d);
       margin: 0; font-family: system-ui, sans-serif; }
"""

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<style>%(plugin)s</style>
<style>%(theme)s</style>
<style>%(site)s</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
<div class="alt-wrap alt-tracker-wrap">
  <h2>Where the cuts are</h2>
  <h2 class="alt-why-summary">Why our number is lower, and why it is the one to cite</h2>
  <h3>How it is trending</h3>
  <h3 class="alt-browse-heading">By country</h3>
  <p class="alt-hero-thesis">Every entry links to the filing, notice or report it came from.</p>
  <p class="alt-chart-note">Figures are verified job cuts on the filing basis.</p>
  <p class="alt-why-quality">Counts parse the first number in the filing only.</p>
  <p>A plain paragraph with <b>a bold lead in</b> and a sentence after it.</p>
</div></div></div></main></div>
</body></html>
"""


def _strip_the_fix(css):
    """Return layoffs.css with the plugin's winning colour declarations gone.

    This reconstructs the DEFECT, so the test below can prove the audit sees
    it. It removes whole rule blocks whose selector list reaches
    `.alt-wrap p|h2|h3` inside the site rule's own scope - i.e. exactly the
    declarations added to beat the override, and nothing else.
    """
    out, i, removed = [], 0, 0
    for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        sel = m.group(1)
        if re.search(r"\.(entry-content|wp-block-post-content)\s+\.alt-wrap\s+(p|h2|h3)\b", sel):
            out.append(css[i:m.start()])
            i = m.end()
            removed += 1
    out.append(css[i:])
    assert removed >= 2, "found %d blocks to strip; the fix moved" % removed
    return "".join(out)


class _Measured(unittest.TestCase):
    """Loads a fixture in headless Chrome and returns the audit's own rows."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so rendered contrast could "
                "not be measured. This is UNKNOWN, not a pass: run "
                "`python3 railway/contrast_audit.py` where a browser exists.")

    def _rows(self, css, theme="dark"):
        html = FIXTURE % {"plugin": css, "theme": THEME_SHIM, "site": SITE_OVERRIDE}
        try:
            with Browser(width=1280, height=900) as page:
                page.call("Emulation.setEmulatedMedia", {
                    "features": [{"name": "prefers-color-scheme", "value": theme}]})
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                page.eval_js("document.documentElement.setAttribute("
                             "'data-theme', %s)" % json.dumps(theme))
                rows = page.eval_js(contrast_audit.PROBE_JS)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertTrue(rows, "the fixture rendered no text at all, so this "
                              "measured nothing")
        return rows


class DarkContrastTests(_Measured):

    def test_the_shipped_stylesheet_clears_aa_under_the_site_override(self):
        rows = self._rows(CSS.read_text(), "dark")
        bad = contrast_audit.violations(rows)
        self.assertEqual(
            [], [(b["sel"], b["color"], b["bg"], b["ratio"]) for b in bad],
            "text below WCAG AA in dark, with the site override applied")

    def test_light_is_not_regressed_by_the_dark_fix(self):
        rows = self._rows(CSS.read_text(), "light")
        bad = contrast_audit.violations(rows)
        self.assertEqual(
            [], [(b["sel"], b["color"], b["bg"], b["ratio"]) for b in bad],
            "the dark fix darkened light text")

    def test_the_headings_and_paragraphs_are_actually_being_measured(self):
        # Guards the fixture itself. If a selector change ever stops these from
        # rendering, the two tests above would pass by measuring nothing.
        rows = self._rows(CSS.read_text(), "dark")
        sels = " ".join(r["sel"] for r in rows)
        for needle in ("h2.alt-why-summary", "h3.alt-browse-heading",
                       "p.alt-hero-thesis", "p.alt-chart-note"):
            self.assertIn(needle, sels, "fixture no longer renders %s" % needle)


class TheGuardCanActuallyFailTests(_Measured):
    """With the fix removed, the audit MUST report the original defect.

    This is the half that makes the two tests above mean something. It is also
    the reproduction of the live incident: same override, same tokens, same
    markup, and the plugin's winning declarations taken back out.
    """

    def test_removing_the_fix_reproduces_the_unreadable_page(self):
        rows = self._rows(_strip_the_fix(CSS.read_text()), "dark")
        bad = contrast_audit.violations(rows)
        self.assertTrue(bad, "the audit passed a page whose headings and "
                             "paragraphs are hard-coded #1a1a1a/#2a2a2a on a "
                             "#12141a background: it cannot catch the defect "
                             "it exists for")
        worst = min(b["ratio"] for b in bad)
        self.assertLess(worst, 1.5, "expected the reproduction to land near "
                                    "1:1, got %.2f" % worst)

    def test_it_names_the_elements_a_reader_lost(self):
        rows = self._rows(_strip_the_fix(CSS.read_text()), "dark")
        flagged = {b["sel"] for b in contrast_audit.violations(rows)}
        for needle in ("h2.alt-why-summary", "p.alt-hero-thesis"):
            self.assertIn(needle, flagged,
                          "%s vanished for the reader and the audit did not "
                          "flag it" % needle)


class ProbeArithmeticTests(unittest.TestCase):
    """The ratio maths, on values with a known answer. No browser needed.

    The first run of the audit reported twenty violations that were entirely
    its own measurement: `.alt-btn` carries `transition: background .15s`, so
    reading a computed background in the same task that flipped the theme
    returned the PREVIOUS colour. A guard that invents failures gets muted as
    fast as one that misses them, so the freeze is asserted here.
    """

    def test_the_thresholds_are_the_wcag_aa_ones(self):
        self.assertEqual(contrast_audit.AA_NORMAL, 4.5)
        self.assertEqual(contrast_audit.AA_LARGE, 3.0)

    def test_violations_uses_the_large_text_threshold_for_large_text(self):
        rows = [
            {"sel": "h1", "ratio": 3.2, "large": True, "color": "", "bg": ""},
            {"sel": "p", "ratio": 3.2, "large": False, "color": "", "bg": ""},
        ]
        got = [v["sel"] for v in contrast_audit.violations(rows)]
        self.assertEqual(got, ["p"])

    def test_the_audit_disables_transitions_before_measuring(self):
        self.assertIn("transition: none !important", contrast_audit.FREEZE_CSS)
        self.assertIn("animation: none !important", contrast_audit.FREEZE_CSS)

    def test_it_measures_both_matched_and_mismatched_theme_combinations(self):
        # A reader on a dark OS who picks Light exercises a different half of
        # the stylesheet than either matched combination.
        combos = {(os_s, attr) for _, os_s, attr in contrast_audit.THEMES}
        self.assertIn(("dark", None), combos, "the default for a dark-OS "
                                              "reader is not being measured")
        self.assertIn(("dark", "light"), combos)
        self.assertIn(("light", "dark"), combos)

    def test_an_unmeasurable_run_is_not_a_pass(self):
        src = (ROOT / "railway/contrast_audit.py").read_text()
        self.assertIn("return 3", src, "no UNKNOWN exit path")
        self.assertRegex(src, r"RESULT: UNKNOWN")


if __name__ == "__main__":
    unittest.main()
