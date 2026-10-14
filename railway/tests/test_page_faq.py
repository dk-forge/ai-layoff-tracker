"""Intro + H2 + 3-question FAQ on every tracker shortcode page, and FAQPage
JSON-LD built from exactly that visible text (#446 items 2 and 3).

Owner ruling 2026-10-14: Claude writes the wording. Rules pinned here:
  * live figures and the year come from the render-time facts, never typed;
  * a figure that cannot be read (0 / missing) drops its sentence, it is never
    printed as 0 and never replaced by a guess;
  * the JSON-LD question and answer strings are byte-identical to the visible
    ones, and the JSON-LD is emitted inside the same block as the FAQ, so it
    can only appear on a page that shows it;
  * no em or en dash, no blanket "primary source" promise, no typed cadence;
  * the tracker page keeps its own FAQ (alt_faq_items) and gets no second one.
"""
import html
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "page-faq.php"
SHORTCODES = PLUGIN / "includes" / "shortcodes.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"
BASE = "https://example.org/blog/"

FULL = {"y": 2031, "entries": 12345, "jobs": 678901, "ai_jobs": 23456,
        "all": 98765, "countries": 61, "start": "2002",
        "warn_states": "46 US states and DC", "cadence": "three times daily"}
EMPTY = {"y": 2031, "entries": 0, "jobs": 0, "ai_jobs": 0, "all": 0,
         "countries": 0, "start": "", "warn_states": "", "cadence": ""}

PAGES = ["page-dashboard.php", "page-us-registry.php", "page-methodology.php",
         "page-sources.php", "page-press.php", "page-ai-quotes.php",
         "page-publisher.php", "page-health.php", "page-ai-tracker.php"]


def _php(call, *args):
    src = MOD.read_text(encoding="utf-8")
    funcs = re.findall(r"\nfunction alt_page_faq_[a-z_]+\s*\(.*?\n\}", src, re.S)
    code = ("function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }\n"
            "function esc_url($s){ return (string)$s; }\n"
            "function wp_json_encode($v,$f=0){ return json_encode($v,$f); }\n"
            + "\n".join(funcs) + "\n" + call)
    p = subprocess.run(["php", "-r", code, "--", *[json.dumps(a) for a in args]],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


def content(tpl, facts):
    return json.loads(_php(
        "echo json_encode(alt_page_faq_content(json_decode($argv[1]), json_decode($argv[2], true), json_decode($argv[3])));",
        tpl, facts, BASE))


def render(tpl, facts):
    return _php(
        "$c = alt_page_faq_content(json_decode($argv[1]), json_decode($argv[2], true), json_decode($argv[3]));"
        "echo alt_page_faq_insert('<main class=\"alt-wrap\"><h1>T</h1><p>x</p></main>', $c);",
        tpl, facts, BASE)


def visible_text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Copy(unittest.TestCase):
    def test_every_page_has_intro_h2_and_three_questions(self):
        for tpl in PAGES:
            with self.subTest(tpl=tpl):
                c = content(tpl, FULL)
                self.assertTrue(c["intro"].strip())
                self.assertTrue(c["h2"].strip())
                self.assertEqual(len(c["faq"]), 3)
                n = len(re.findall(r"[.!?](?:\s|$)", visible_text(c["intro"])))
                self.assertTrue(2 <= n <= 3, (tpl, n, c["intro"]))

    def test_tracker_and_unknown_pages_get_nothing(self):
        self.assertIsNone(content("page-tracker.php", FULL))
        self.assertIsNone(content("page-widget.php", FULL))

    def test_live_figures_and_year_come_from_facts(self):
        all_text = " ".join(json.dumps(content(t, FULL)) for t in PAGES)
        for v in ("2031", "678,901", "23,456", "46 US states and DC", "three times daily"):
            self.assertIn(v, all_text)
        src = MOD.read_text(encoding="utf-8")
        self.assertNotRegex(re.sub(r"(?m)^\s*(\*|//).*$", "", src), r"\b20[12]\d\b",
                            "no year typed into the copy")

    def test_unreadable_figure_drops_the_sentence(self):
        for tpl in PAGES:
            with self.subTest(tpl=tpl):
                c = content(tpl, EMPTY)
                text = json.dumps(c)
                self.assertNotRegex(text, r"(?<![\d,.])0 (job|verified|entries|countries|US states)")
                self.assertTrue(c["intro"].strip())
                for q, a in c["faq"]:
                    self.assertTrue(a.strip(), (tpl, q))

    def test_no_dashes_no_blanket_primary_promise_no_hype(self):
        for tpl in PAGES:
            text = visible_text(json.dumps(content(tpl, FULL), ensure_ascii=False))
            with self.subTest(tpl=tpl):
                self.assertNotIn("—", text)
                self.assertNotIn("–", text)
                self.assertNotRegex(text, r"(?i)every (figure|entry|number)[^.]*primary source")
                self.assertNotRegex(text, r"(?i)\b(revolutionary|unprecedented|skyrocket\w*)\b")
                for s in re.split(r"(?<=[.!?])\s+", text):
                    if re.search(r"(?i)caused by AI|AI (really )?caused", s):
                        self.assertRegex(s, r"(?i)\b(not|no|whether)\b", "causation only ever denied or asked: " + s)

    def test_links_methodology_and_sources(self):
        for tpl in PAGES:
            text = json.dumps(content(tpl, FULL))
            with self.subTest(tpl=tpl):
                if tpl != "page-methodology.php":
                    self.assertIn(BASE + "ai-layoff-tracker/methodology/", text)
                if tpl != "page-sources.php":
                    self.assertIn(BASE + "ai-layoff-tracker/sources/", text)

    def test_sentences_stay_under_thirty_words(self):
        for tpl in PAGES:
            c = content(tpl, FULL)
            parts = [c["intro"]] + [a for _, a in c["faq"]]
            for p in parts:
                for s in re.split(r"(?<=[.!?])\s+", visible_text(p)):
                    self.assertLessEqual(len(s.split()), 30, (tpl, s))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Markup(unittest.TestCase):
    def test_jsonld_matches_visible_faq_exactly(self):
        for tpl in PAGES:
            with self.subTest(tpl=tpl):
                out = render(tpl, FULL)
                c = content(tpl, FULL)
                m = re.findall(r'<script type="application/ld\+json">(.*?)</script>', out, re.S)
                self.assertEqual(len(m), 1)
                ld = json.loads(m[0])
                self.assertEqual(ld["@type"], "FAQPage")
                pairs = [(e["name"], e["acceptedAnswer"]["text"]) for e in ld["mainEntity"]]
                self.assertEqual(pairs, [tuple(x) for x in c["faq"]])
                for q, a in pairs:
                    self.assertIn(">" + html.escape(q, quote=False) + "<", out.replace("&#039;", "'"))
                    self.assertIn(a, out)

    def test_layout_intro_after_h1_section_inside_main(self):
        out = render("page-dashboard.php", FULL)
        self.assertLess(out.index("</h1>"), out.index('class="alt-page-intro"'))
        self.assertLess(out.index('class="alt-page-intro"'), out.index("<p>x</p>"))
        self.assertLess(out.index('<section class="alt-page-faq"'), out.index("</main>"))
        self.assertRegex(out, r'<section class="alt-page-faq"[^>]*>\s*<h2[^>]*>')

    def test_no_h1_prepends_intro_and_appends_section(self):
        out = _php("$c = alt_page_faq_content('page-ai-tracker.php', json_decode($argv[1], true), 'https://e/');"
                   "echo alt_page_faq_insert('<div class=\"alt-wrap\">x</div>', $c);", FULL)
        self.assertTrue(out.startswith('<p class="alt-page-intro"'))
        self.assertTrue(out.rstrip().endswith("</section>"))


class Wiring(unittest.TestCase):
    def test_module_loaded_and_template_funnel_calls_it(self):
        self.assertIn("includes/page-faq.php", MAIN.read_text(encoding="utf-8"))
        self.assertIn("alt_page_faq_template", SHORTCODES.read_text(encoding="utf-8"))

    def test_seo_head_untouched_tracker_faq_kept(self):
        src = MOD.read_text(encoding="utf-8")
        self.assertNotIn("rank_math", src)
        self.assertNotIn("wp_head", src)
        self.assertIn("function alt_faq_items", MAIN.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
