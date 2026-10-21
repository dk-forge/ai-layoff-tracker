"""Roo, the floating feedback widget, on every /blog page (owner ruling 2026-10-21).

Recorded in asktherecruiter-sandbox docs/DECISIONS.md "Roo feedback on every
surface". The blog posts to the SAME feedback pipeline as the AskTheRecruiter
app (`/api/feedback/site`, same origin, so no CORS), tagged `product=blog` with
the page path, behind the app's honeypot + Turnstile. Visibility is the shared
rule: 100% of visitors until 2027-02-01, then a sticky 50% from a stable id in
localStorage. The JS carries a MIRROR of the sandbox helper; the golden buckets
below are the same numbers the sandbox and fasthire tests pin.

What is asserted, and why:
  * the include is GUARDED with is_readable (2.19.20: an FTP deploy can land the
    main file first, and a hard require fatals the whole plugin);
  * assets are enqueued on wp_enqueue_scripts, on every front-end page;
  * config travels on a data- attribute, never wp_localize_script or an inline
    script (Autoptimize sweeps inline objects into a later bundle; TIT CLAUDE.md
    gotcha #10), and the assets dir stays in the Autoptimize exclude;
  * the visibility rule on both sides of the date, run in node against the
    SHIPPED file, not a reimplementation;
  * the surface: native button with an ARIA label, a labelled modal dialog,
    Escape closes, 44px targets, fits 375px, reduced motion, no em-dash.

No node binary: SKIP loudly rather than pass. Absence of a signal is not a pass.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MAIN_PHP = PLUGIN / "ai-layoff-tracker.php"
ROO_PHP = PLUGIN / "includes/roo-feedback.php"
ROO_JS = PLUGIN / "assets/roo-feedback.js"
ROO_CSS = PLUGIN / "assets/roo-feedback.css"
NODE = shutil.which("node")


def _read(p):
    return p.read_text(encoding="utf-8")


class TheIncludeIsWiredSafely(unittest.TestCase):
    def test_main_file_requires_it_behind_is_readable(self):
        src = _read(MAIN_PHP)
        self.assertIn("includes/roo-feedback.php", src)
        self.assertRegex(src, r"is_readable\(\$alt_roo_feedback\)\)\s*\{\s*require_once \$alt_roo_feedback;")

    def test_assets_are_enqueued_on_every_front_end_page(self):
        src = _read(ROO_PHP)
        self.assertIn("add_action('wp_enqueue_scripts'", src)
        self.assertIn("assets/roo-feedback.js", src)
        self.assertIn("assets/roo-feedback.css", src)
        self.assertNotRegex(src, r"is_single\(|is_singular\(|is_page\(")

    def test_config_rides_a_data_attribute_not_an_inline_object(self):
        src = _read(ROO_PHP)
        self.assertIn("data-alt-roo=", src)
        self.assertNotIn("wp_localize_script", src)
        self.assertNotIn("wp_add_inline_script", src)
        self.assertIn("ai-layoff-tracker/assets", _read(MAIN_PHP))  # AO exclude still covers it

    def test_config_names_the_one_pipeline_and_the_blog_tag(self):
        src = _read(ROO_PHP)
        self.assertIn("'/api/feedback/site'", src)
        self.assertIn("'product'  => 'blog'", src)
        self.assertRegex(src, r"0x4[A-Za-z0-9_-]{18,}")  # the app's public Turnstile site key


class TheVisibilityRule(unittest.TestCase):
    def setUp(self):
        if not NODE:
            self.skipTest("UNKNOWN, NOT RUN: no node binary")

    def _rule(self, expr):
        script = (
            "const vm=require('vm');const fs=require('fs');"
            "const ctx={};vm.createContext(ctx);"
            "vm.runInContext(fs.readFileSync(%s,'utf8'),ctx);"
            "const R=ctx.AltRooRule;process.stdout.write(JSON.stringify(%s));"
        ) % (json.dumps(str(ROO_JS)), expr)
        out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_constants_and_golden_buckets_match_every_other_surface(self):
        got = self._rule("[R.UNTIL,R.PERCENT,R.KEY,R.bucket('visitor-a'),R.bucket('visitor-b'),"
                         "R.bucket('00000000-0000-4000-8000-000000000000')]")
        self.assertEqual(got, ["2027-02-01T00:00:00Z", 50, "atr_roo_vid", 75, 94, 41])

    def test_everyone_before_the_cutover(self):
        got = self._rule("['visitor-a','visitor-b',null].map(i=>R.show(i,Date.parse('2027-01-31T23:59:59Z')))")
        self.assertEqual(got, [True, True, True])

    def test_sticky_half_from_the_cutover(self):
        got = self._rule("['visitor-a','visitor-c',null].map(i=>R.show(i,Date.parse('2027-02-01T00:00:00Z')))")
        self.assertEqual(got, [False, True, False])
        share = self._rule("Array.from({length:2000},(_,i)=>R.show('id-'+i,Date.parse('2027-06-01T00:00:00Z'))).filter(Boolean).length")
        self.assertTrue(900 < share < 1100, share)


class TheSurface(unittest.TestCase):
    def test_button_and_dialog_are_accessible(self):
        js = _read(ROO_JS)
        self.assertIn("aria-label', 'Give us feedback'", js)
        self.assertIn("aria-haspopup', 'dialog'", js)
        self.assertIn("role', 'dialog'", js)
        self.assertIn("aria-modal', 'true'", js)
        self.assertIn("aria-labelledby'", js)
        self.assertIn("'Escape'", js)
        self.assertIn("aria-live', 'polite'", js)

    def test_payload_is_the_app_shape_with_the_blog_tag_and_page(self):
        js = _read(ROO_JS)
        for field in ("rating", "text", "email", "page", "product", "website", "turnstile_token"):
            self.assertIn(field + ":", js)
        self.assertIn("location.pathname", js)

    def test_css_targets_44px_fits_375_and_respects_reduced_motion(self):
        css = _read(ROO_CSS)
        self.assertIn("min-height:44px", css.replace(" ", ""))
        self.assertIn("max-width:calc(100vw-32px)", css.replace(" ", ""))
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn(":focus-visible", css)

    def test_no_em_dash_in_reader_copy(self):
        for p in (ROO_JS, ROO_CSS, ROO_PHP):
            self.assertNotIn("—", _read(p), p.name)


if __name__ == "__main__":
    unittest.main()
