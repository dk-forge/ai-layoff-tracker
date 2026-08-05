"""Light and dark theme: the invariants, not the prose.

WHY THE MATCHING IS PARANOID. An adversarial sweep on 2026-08-04 found seven
checks in these two repos that passed against defective code for the wrong
reason, and two of them matched a COMMENT that described a call rather than
the call itself. This file therefore strips comments out of every artefact
before it looks at it, and where a claim is about behaviour rather than about
text it runs the real function in node (see jsrun.py) instead of grepping.

WHAT IT IS ACTUALLY GUARDING, in order of how badly each one bites:

1. A token defined in light but forgotten in dark does not error. It silently
   keeps its light value, so one panel stays white on a dark page and nothing
   anywhere reports a problem. test_every_token_is_defined_in_all_three_blocks
   is the check that catches it, and it is the most valuable one here.
2. A component style written inside the dark block is how two themes drift
   apart over time: the light path never sees that declaration again.
3. A chart colour that is a literal in JS cannot follow the stylesheet,
   because a canvas does not inherit CSS. That was the state before this
   change and it is the failure mode the whole exercise exists to prevent.
4. A contrast claim that lives in a commit message rots. The ratios are
   recomputed here from the values actually shipped in the stylesheet.
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CSS = PLUGIN / "assets/layoffs.css"
JS = PLUGIN / "assets/layoffs.js"
PHP = PLUGIN / "ai-layoff-tracker.php"
TRACKER_TPL = PLUGIN / "templates/page-tracker.php"


def strip_css_comments(text):
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def strip_js_comments(text):
    """Remove // and /* */ comments without eating them out of string
    literals, which is where a naive regex turns a URL into a truncated
    file and makes the test pass on nonsense."""
    out, i, n = [], 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\":
                if i + 1 < n:
                    out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def block_body(css, selector):
    """The declaration text of the rule introduced by `selector`, brace
    matched. Raises when absent, because a test that silently found nothing
    would pass for the worst possible reason."""
    i = css.find(selector)
    if i == -1:
        raise AssertionError("layoffs.css has no rule %r" % selector)
    j = css.index("{", i)
    depth, k = 0, j
    while k < len(css):
        if css[k] == "{":
            depth += 1
        elif css[k] == "}":
            depth -= 1
            if depth == 0:
                return css[j + 1:k]
        k += 1
    raise AssertionError("unbalanced braces after %r" % selector)


def tokens_in(body):
    return dict(re.findall(r"(--alt-[a-z0-9-]+)\s*:\s*([^;]+);", body))


# ---- colour maths, kept local so the test does not trust the code it checks
def _lin(v):
    v /= 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(hexs):
    h = hexs.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


LIGHT_SEL = ":root {"
DARK_MEDIA_SEL = ':root:not([data-theme="light"]) {'
DARK_EXPLICIT_SEL = ':root[data-theme="dark"] {'


class ThemeStructure(unittest.TestCase):
    def setUp(self):
        self.css = strip_css_comments(CSS.read_text())

    def test_light_palette_lives_in_one_root_block(self):
        body = block_body(self.css, LIGHT_SEL)
        toks = tokens_in(body)
        self.assertGreater(len(toks), 50,
                           "the palette should be one :root block, found %d tokens" % len(toks))
        self.assertEqual("light", re.search(r"color-scheme:\s*([a-z ]+);", body).group(1).strip())

    def test_the_media_query_yields_to_an_explicit_light_choice(self):
        """Without the :not(), a visitor on a dark OS who picks light gets
        dark anyway: the media query and the [data-theme] rule would both
        match and the later one would win."""
        self.assertIn(DARK_MEDIA_SEL, self.css)
        i = self.css.index(DARK_MEDIA_SEL)
        head = self.css[:i]
        self.assertRegex(head[-120:], r"@media\s*\(\s*prefers-color-scheme:\s*dark\s*\)",
                         "the :not([data-theme=light]) rule must sit inside the dark media query")

    def test_an_explicit_dark_choice_beats_the_light_default(self):
        self.assertIn(DARK_EXPLICIT_SEL, self.css)
        self.assertGreater(self.css.index(DARK_EXPLICIT_SEL), self.css.index(LIGHT_SEL),
                           "the explicit dark block must come after the light default to win on order")

    def test_every_token_is_defined_in_all_three_blocks(self):
        """The one that matters. A token present in light and missing from a
        dark block does not error, it silently stays light."""
        light = tokens_in(block_body(self.css, LIGHT_SEL))
        media = tokens_in(block_body(self.css, DARK_MEDIA_SEL))
        explicit = tokens_in(block_body(self.css, DARK_EXPLICIT_SEL))

        colourish = {k: v for k, v in light.items()
                     if re.search(r"#[0-9a-fA-F]{3,8}|rgba?\(|^\s*[\d,\s]+$", v)}
        for name in sorted(colourish):
            self.assertIn(name, media, "%s is themed in light but not under the media query" % name)
            self.assertIn(name, explicit, "%s is themed in light but not under [data-theme=dark]" % name)

        self.assertEqual(set(media), set(explicit),
                         "the two dark blocks must define the same token set")
        for name in sorted(set(media)):
            self.assertEqual(media[name].strip(), explicit[name].strip(),
                             "%s disagrees between the two dark blocks" % name)

    def test_the_dark_blocks_hold_nothing_but_tokens(self):
        """A component style in here is how the two themes drift: the light
        path never sees that declaration again."""
        for sel in (DARK_MEDIA_SEL, DARK_EXPLICIT_SEL):
            body = block_body(self.css, sel)
            for decl in body.split(";"):
                decl = decl.strip()
                if not decl:
                    continue
                prop = decl.split(":", 1)[0].strip()
                self.assertTrue(prop.startswith("--") or prop == "color-scheme",
                                "%r declares %r; the dark blocks may only redefine tokens"
                                % (sel, prop))

    def test_no_component_rule_shadows_a_theme_token(self):
        """A token redeclared on .alt-wrap beats :root for everything inside
        it, which pins that token to one theme. Three of them used to be."""
        after = self.css[self.css.index(DARK_EXPLICIT_SEL):]
        after = after[after.index("}"):]
        for m in re.finditer(r"(--alt-[a-z0-9-]+)\s*:\s*([^;]+);", after):
            self.assertTrue(m.group(2).strip().startswith("var("),
                            "%s is redefined outside the palette as %r, which shadows the theme"
                            % (m.group(1), m.group(2).strip()))


class ContrastIsRecomputed(unittest.TestCase):
    """The palette's accessibility claim, checked against the shipped values
    rather than against a commit message."""

    def setUp(self):
        css = strip_css_comments(CSS.read_text())
        self.light = tokens_in(block_body(css, LIGHT_SEL))
        self.dark = tokens_in(block_body(css, DARK_EXPLICIT_SEL))

    # (foreground token, background token, minimum ratio)
    PAIRS = [
        ("--alt-ink", "--alt-surface", 4.5),
        ("--alt-ink", "--alt-page", 4.5),
        ("--alt-ink", "--alt-paper", 4.5),
        ("--alt-ink-2", "--alt-surface", 4.5),
        ("--alt-muted", "--alt-surface", 4.5),
        ("--alt-muted", "--alt-surface-2", 4.5),
        ("--alt-muted", "--alt-paper", 4.5),
        ("--alt-blue", "--alt-surface", 4.5),
        ("--alt-blue-dark", "--alt-surface", 4.5),
        ("--alt-accent", "--alt-surface", 4.5),
        ("--alt-ochre", "--alt-surface", 4.5),
        ("--alt-navy", "--alt-surface", 4.5),
        ("--alt-ai", "--alt-surface", 4.5),
        ("--alt-ai-ink", "--alt-red-tint", 4.5),
        ("--alt-verified", "--alt-surface", 4.5),
        ("--alt-announced-ink", "--alt-surface", 4.5),
        ("--alt-ok-ink", "--alt-ok-bg", 4.5),
        ("--alt-warn-ink", "--alt-warn-bg", 4.5),
        ("--alt-info-ink", "--alt-info-bg", 4.5),
        ("--alt-planned-ink", "--alt-planned-bg", 4.5),
        ("--alt-retired-ink", "--alt-retired-bg", 4.5),
        ("--alt-pct-good", "--alt-surface", 4.5),
        ("--alt-pct-mid", "--alt-surface", 4.5),
        ("--alt-pct-low", "--alt-surface", 4.5),
        ("--alt-crit", "--alt-red-tint", 4.5),
        ("--alt-chart-muted", "--alt-surface", 4.5),
        ("--alt-on-accent", "--alt-blue", 4.5),
        ("--alt-chart-tip-body", "--alt-chart-tip-bg", 4.5),
    ]

    REGIONS = ["world", "usa", "canada", "latam", "europe", "uk",
               "mideast", "africa", "asia", "aus"]

    def _check(self, palette, label):
        bad = []
        for fg, bg, need in self.PAIRS:
            self.assertIn(fg, palette, "%s: %s is not defined" % (label, fg))
            self.assertIn(bg, palette, "%s: %s is not defined" % (label, bg))
            got = contrast(palette[fg], palette[bg])
            if got < need - 0.005:
                bad.append("%s on %s = %.2f:1 (need %.1f)" % (fg, bg, got, need))
        self.assertEqual([], bad, "%s theme fails WCAG AA:\n  %s" % (label, "\n  ".join(bad)))

    def test_light_meets_aa(self):
        self._check(self.light, "light")

    def test_dark_meets_aa(self):
        self._check(self.dark, "dark")

    def test_region_hues_are_readable_in_both_themes(self):
        """These are 14px bold chips, so they are body text, not large text,
        and five of them used to sit under 4.5:1 in the shipped light theme."""
        for label, palette, ground in (("light", self.light, "--alt-surface"),
                                       ("dark", self.dark, "--alt-surface")):
            for region in self.REGIONS:
                tok = "--alt-region-%s" % region
                self.assertIn(tok, palette, "%s: %s missing" % (label, tok))
                got = contrast(palette[tok], palette[ground])
                self.assertGreaterEqual(round(got, 2), 4.5,
                                        "%s: %s is %.2f:1 on the panel" % (label, tok, got))

    def test_the_filled_chip_text_flips_with_the_chip(self):
        """In dark the chip is the LIGHT element, so on-accent cannot be a
        fixed white in both themes."""
        self.assertNotEqual(self.light["--alt-on-accent"].strip().lower(),
                            self.dark["--alt-on-accent"].strip().lower())
        for label, palette in (("light", self.light), ("dark", self.dark)):
            for region in self.REGIONS:
                got = contrast(palette["--alt-on-accent"], palette["--alt-region-%s" % region])
                self.assertGreaterEqual(round(got, 2), 4.5,
                                        "%s: chip text on %s is %.2f:1" % (label, region, got))

    def test_the_certainty_hues_stay_told_apart_in_dark(self):
        """Verified, announced and AI-attributed carry meaning. Checked with
        deltaE2000, not contrast ratio: this is an Okabe-Ito derived palette
        whose hues separate at similar lightness, so a contrast ratio near 1
        between two of them says they are equally light, not that they look
        the same."""
        import math

        def lab(hexs):
            h = hexs.strip().lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = (_lin(int(h[i:i + 2], 16)) for i in (0, 2, 4))
            x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
            y = (0.2126 * r + 0.7152 * g + 0.0722 * b)
            z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
            f = lambda t: t ** (1 / 3.0) if t > 0.008856 else (7.787 * t + 16 / 116.0)
            fx, fy, fz = f(x), f(y), f(z)
            return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

        def de(c1, c2):
            l1, a1, b1 = lab(c1)
            l2, a2, b2 = lab(c2)
            return math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)

        names = ["--alt-verified", "--alt-announced", "--alt-ai", "--alt-accent"]
        for label, palette in (("light", self.light), ("dark", self.dark)):
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    d = de(palette[names[i]], palette[names[j]])
                    self.assertGreater(d, 15.0,
                                       "%s: %s and %s are only dE %.1f apart"
                                       % (label, names[i], names[j], d))


class ChartsReadTheStylesheet(unittest.TestCase):
    """A canvas does not inherit CSS. If these colours are literals in JS the
    charts stay light on a dark page, which is the whole point of the change."""

    def setUp(self):
        self.js = strip_js_comments(JS.read_text())

    def test_the_palette_blocks_are_not_literals_any_more(self):
        for name in ("ALT_RED", "ALT_AMBER", "SEQ_BLUE", "MAP_LAND", "MAP_BLUE", "MAP_RED"):
            self.assertNotRegex(
                self.js, r"\b%s\s*=\s*['\"]#?[0-9a-fA-F(]" % name,
                "%s is assigned a colour literal; it must come from a token" % name)

    def test_the_map_literals_are_not_reassigned_after_the_theme_is_read(self):
        """They used to be. The second assignment ran later and put the light
        values back, so the map was the one surface that stayed light."""
        idx_read = self.js.index("function readTheme(")
        tail = self.js[idx_read:]
        self.assertNotRegex(tail, r"var\s+MAP_BLUE\s*=\s*'rgba",
                            "MAP_* is re-assigned from literals after readTheme()")

    def test_readTheme_actually_reads_custom_properties(self):
        """Executed, not grepped: the real function body is run in node
        against a stub whose getPropertyValue returns a marker, and the
        marker has to come out the other side."""
        jsrun.require_node(self)
        src = JS.read_text()
        preamble = """
var READS = [];
var document = { documentElement: {} };
var window = {
  Chart: { defaults: {} },
  getComputedStyle: function () {
    return { getPropertyValue: function (n) { READS.push(n); return 'TOKEN' + n; } };
  }
};
var PALETTE = ['a','b','c','d','e','f','g','h'];
var CSS_ROOT = null;
var ALT_RED, ALT_AMBER, SEQ_BLUE, SEQ_BLUE_FILL, INK, CHART_DIM, TIP;
var MAP_BLUE, MAP_BLUE_LINE, MAP_RED, MAP_RED_LINE, MAP_LAND, MAP_LAND_LINE;
var MAP_HATCH, MAP_HATCH_LINE, MAP_LABEL, MAP_LABEL_HALO, MAP_PLATE;
"""
        expr = ("(readTheme(), {reads: READS, red: ALT_RED, blue: SEQ_BLUE, "
                "land: MAP_LAND, label: MAP_LABEL, grid: INK.grid, tip: TIP.bg, "
                "chartDefault: window.Chart.defaults.color, pal0: PALETTE[0]})")
        got = jsrun.run(["tok", "readTheme"], preamble, expr, src=src)

        self.assertIn("--alt-ai", got["reads"])
        self.assertIn("--alt-map-land", got["reads"])
        self.assertIn("--alt-chart-grid", got["reads"])
        for key in ("red", "blue", "land", "label", "grid", "tip", "pal0"):
            self.assertTrue(str(got[key]).startswith("TOKEN--alt-"),
                            "%s did not come from a custom property, it is %r"
                            % (key, got[key]))
        self.assertTrue(str(got["chartDefault"]).startswith("TOKEN--alt-"),
                        "Chart.defaults.color is global and is not in the options clone, "
                        "so it has to be re-set on every repaint")

    def test_a_theme_change_drives_the_renderers(self):
        js = self.js
        self.assertIn("alt:themechange", js)
        body = jsrun.extract("repaintForTheme", js)
        for call in ("readTheme()", "renderCharts(LAST_AGG)", "renderConversionChart()",
                     "AI_TRACKER_CHART()", "COMPANY_CHART()"):
            self.assertIn(call, body,
                          "repaintForTheme does not call %s, so that surface keeps "
                          "its old colours" % call)
        self.assertRegex(
            js, r"addEventListener\(\s*'alt:themechange'\s*,\s*repaintForTheme\s*\)",
            "nothing subscribes repaintForTheme to the theme change event")

    def test_the_two_single_page_charts_repaint_without_refetching(self):
        """Both used to mount inline inside a .then(), so the only way to
        repaint them was to issue the query again."""
        js = self.js
        for name in ("AI_TRACKER_CHART", "COMPANY_CHART"):
            self.assertRegex(js, r"%s\s*=\s*function" % name,
                             "%s is not stored as a callable, so a repaint costs a request" % name)

    def test_the_signal_board_heat_matches_on_both_sides(self):
        """The board is painted server side on first load and again in JS on
        filter change. Two formulas, one of which used to be a fixed blue."""
        php = re.sub(r"/\*.*?\*/", " ", TRACKER_TPL.read_text(), flags=re.S)
        self.assertNotIn("rgba(42,120,214,", php,
                         "the server-rendered heat cells are still a fixed blue")
        self.assertIn("rgba(var(--alt-heat-rgb),", php)
        self.assertIn("rgba(' + tok('heat-rgb'", self.js)


class NoFlashAndTheToggle(unittest.TestCase):
    def setUp(self):
        self.php = re.sub(r"/\*.*?\*/", " ", PHP.read_text(), flags=re.S)

    def test_the_theme_is_stamped_from_the_head_before_first_paint(self):
        self.assertIn("alt_theme_boot", self.php)
        self.assertRegex(self.php, r"add_action\(\s*'wp_head'\s*,\s*'alt_theme_boot'\s*,\s*1\s*\)",
                         "the boot script must run early in the head, or the wrong theme paints first")
        boot = self.php[self.php.index("function alt_theme_boot"):]
        boot = boot[:boot.index("add_action('wp_head'")]
        self.assertIn("localStorage", boot)
        self.assertIn("data-theme", boot)
        self.assertIn("documentElement", boot)

    def test_auto_removes_the_attribute_so_the_media_query_governs(self):
        boot = self.php[self.php.index("function alt_theme_boot"):]
        self.assertRegex(boot, r"removeAttribute\(\s*'data-theme'\s*\)",
                         "auto must clear data-theme, not set it to a third value")

    def test_the_boot_script_is_inline_and_not_an_extra_request(self):
        self.assertNotIn("wp_enqueue_script('alt-theme", self.php)
        self.assertIn('<script id="alt-theme-boot">', self.php)

    def test_the_toggle_is_reachable_and_announces_its_state(self):
        boot = self.php[self.php.index("function alt_theme_boot"):]
        self.assertIn("aria-pressed", boot)
        self.assertIn("Colour theme:", boot)
        self.assertRegex(boot, r"createElement\(\s*'button'\s*\)",
                         "the control must be real buttons, so each is a tab stop")
        self.assertIn("'role', 'group'", boot)

    def test_the_toggle_has_a_visible_focus_state(self):
        css = strip_css_comments(CSS.read_text())
        body = block_body(css, ".alt-theme-b:focus-visible {")
        self.assertIn("outline", body)

    def test_transitions_are_dropped_for_reduced_motion(self):
        css = strip_css_comments(CSS.read_text())
        blocks = [m for m in re.finditer(r"@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{", css)]
        self.assertTrue(blocks, "the toggle animates with nothing to turn it off")
        found = False
        for m in blocks:
            body = block_body(css[m.start():], "@media (prefers-reduced-motion: reduce) {")
            if ".alt-theme-b" in body and "transition: none" in body:
                found = True
        self.assertTrue(found, "no reduced-motion block drops the theme control's transition")


class TheSurfacesAroundUs(unittest.TestCase):
    def setUp(self):
        self.css = strip_css_comments(CSS.read_text())

    def test_the_page_ground_follows_the_theme(self):
        """The WordPress theme paints <body> from its own custom property and
        every layer between it and our wrapper is transparent, so re-pointing
        that property is what removes the seam."""
        self.assertIn("--wp--preset--color--base: var(--alt-page)", self.css)
        self.assertIn("--wp--preset--color--contrast: var(--alt-ink)", self.css)

    def test_the_footer_band_does_not_stay_cream_under_a_dark_page(self):
        self.assertRegex(self.css, r"has-background\s*\{[^}]*background-color:\s*var\(--alt-surface\)\s*!important")

    def test_no_background_is_still_hard_wired_white(self):
        after = self.css[self.css.index(DARK_EXPLICIT_SEL):]
        after = after[after.index("}"):]
        hits = re.findall(r"background(?:-color)?\s*:\s*(#fff\b|#ffffff\b)", after)
        self.assertEqual([], hits, "%d background declarations are still literal white" % len(hits))

    def test_the_standalone_embed_follows_the_reader(self):
        embed = re.sub(r"/\*.*?\*/", " ", (PLUGIN / "templates/page-chart-embed.php").read_text(), flags=re.S)
        self.assertNotIn("html,body{margin:0;background:#fff}", embed)
        self.assertIn("background:var(--alt-page)", embed)


class VersionMovesWithTheAssets(unittest.TestCase):
    def test_header_and_constant_agree(self):
        php = PHP.read_text()
        header = re.search(r"^\s*\*\s*Version:\s*([0-9.]+)\s*$", php, re.M).group(1)
        const = re.search(r"define\('ALT_VERSION',\s*'([0-9.]+)'\)", php).group(1)
        self.assertEqual(header, const)


if __name__ == "__main__":
    unittest.main()
