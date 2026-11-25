"""Growth experiment 1, the layoff-to-resume loop (dk-forge/todo#2983).

One visible line on every company page and in the daily and weekly digest
emails:

    Laid off from <company>? Check your resume against open jobs, free.

linked to https://asktherecruiter.com/resume-score with exactly

    utm_source=ai-layoff-tracker
    utm_medium=company-page | digest-email
    utm_campaign=layoff-resume-loop
    utm_content=<company-slug>

Pinned here, each for a reason that fails silently otherwise:
- the full UTM set on every rendered link, or the experiment cannot be read;
- the anchor text is the action itself, never "click here" (WCAG 2.4.4);
- "resume" is spelled without accents, and the copy carries no em or en dash;
- the relay's UTM tagger leaves the experiment's tags untouched;
- the monthly edition does not carry it (daily and weekly only).
"""
import html as html_mod
import os
import re
import shutil
import sys
import unittest
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import test_atr_signup_cta as cta_t  # noqa: E402
import test_digest_briefing as brief_t  # noqa: E402
import digest_utm  # noqa: E402

PHP = shutil.which("php")
COPY_TAIL = "Check your resume against open jobs, free."
# The shared banned list (dashes, the banned words), plus two of our own.
BANNED = tuple(cta_t.BANNED) + ("click here", "r\u00e9sum")


def _links(html):
    out = []
    for href, text in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        out.append((html_mod.unescape(href), html_mod.unescape(re.sub("<[^>]+>", "", text))))
    return out


def _resume_links(html):
    return [(u, t) for u, t in _links(html) if "/resume-score" in u]


def _assert_full_utm(tc, url, medium, slug):
    parts = urllib.parse.urlsplit(url)
    tc.assertEqual(f"{parts.scheme}://{parts.netloc}{parts.path}",
                   "https://asktherecruiter.com/resume-score", url)
    q = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    tc.assertEqual(q, {"utm_source": ["ai-layoff-tracker"], "utm_medium": [medium],
                       "utm_campaign": ["layoff-resume-loop"], "utm_content": [slug]}, url)


@unittest.skipUnless(PHP, "UNKNOWN, NOT RUN: php not installed")
class CompanyPageLine(unittest.TestCase):

    def test_line_copy_anchor_and_full_utm_set(self):
        html = cta_t._run_php("echo alt_layoff_resume_line_html('Acme Co', 'acme-co');")
        plain = html_mod.unescape(re.sub("<[^>]+>", "", html))
        self.assertEqual(plain, "Laid off from Acme Co? " + COPY_TAIL)
        links = _resume_links(html)
        self.assertEqual(len(links), 1)
        url, text = links[0]
        self.assertEqual(text, COPY_TAIL)
        _assert_full_utm(self, url, "company-page", "acme-co")

    def test_name_is_escaped_and_slug_derived_when_absent(self):
        html = cta_t._run_php("echo alt_layoff_resume_line_html('AT&T <b>Inc</b>');")
        self.assertNotIn("<b>Inc</b>", html)
        _assert_full_utm(self, _resume_links(html)[0][0], "company-page", "at-t-b-inc-b")

    def test_unknown_medium_falls_back_to_company_page(self):
        url = cta_t._run_php("echo alt_layoff_resume_url('Acme', 'spam');")
        _assert_full_utm(self, url, "company-page", "acme")

    def test_copy_is_clean(self):
        html = cta_t._run_php("echo alt_layoff_resume_line_html('Acme', 'acme');"
                              "echo implode(' ', alt_layoff_resume_email_parts('Acme'));")
        low = html.lower()
        for word in BANNED:
            self.assertNotIn(word, low, word)

    def test_every_company_page_renders_it_with_name_and_slug(self):
        src = cta_t.COMPANY.read_text(encoding="utf-8")
        self.assertIn("alt_layoff_resume_line_html($alt_label, $alt_company['slug'] ?? '')", src)
        self.assertIn("function_exists('alt_layoff_resume_line_html')", src)
        # Above the fold: before the list of entries, after the summary.
        self.assertLess(src.index("alt-company-summary"), src.index("alt_layoff_resume_line_html("))
        self.assertLess(src.index("alt_layoff_resume_line_html("), src.index("alt-company-directory-total"))
        # The template is the one every /company-layoffs/<slug>/ page renders.
        self.assertNotIn("return;", src.split("alt_layoff_resume_line_html(")[0].split("alt_render_page_header();")[1])


@unittest.skipUnless(PHP, "UNKNOWN, NOT RUN: php not installed")
class DigestLine(unittest.TestCase):

    def _compose(self, freq, fx=None):
        fx = fx or brief_t.base_fixture()
        fx["freq"] = freq
        return brief_t.compose(fx)

    def test_weekly_and_daily_carry_the_line_with_full_utm_set(self):
        for freq in ("weekly", "daily"):
            with self.subTest(freq=freq):
                out = self._compose(freq)
                links = _resume_links(out["html"])
                self.assertEqual(len(links), 1, freq)
                url, text = links[0]
                self.assertEqual(text, COPY_TAIL)
                # The lead row of "Biggest cuts" is the largest verified cut.
                _assert_full_utm(self, url, "digest-email", "crothall-healthcare")
                self.assertIn("Laid off from Crothall Healthcare? " + COPY_TAIL, out["text"])
                self.assertIn(url, out["text"])

    def test_monthly_does_not(self):
        out = self._compose("monthly")
        self.assertEqual(_resume_links(out["html"]), [])
        self.assertNotIn(COPY_TAIL, out["text"])

    def test_relay_utm_tagger_keeps_the_experiment_tags(self):
        out = self._compose("weekly")
        hosts = digest_utm.own_hosts("https://asktherecruiter.com/blog/unsub")
        html = digest_utm.tag_html(out["html"], "weekly", hosts)
        text = digest_utm.tag_text(out["text"], "weekly", hosts)
        _assert_full_utm(self, _resume_links(html)[0][0], "digest-email", "crothall-healthcare")
        url = [u for u in re.findall(r"https://\S+", text) if "/resume-score" in u][0]
        _assert_full_utm(self, url, "digest-email", "crothall-healthcare")


if __name__ == "__main__":
    unittest.main()
