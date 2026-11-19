"""One branded, readable shell for all three digest emails (dk-forge/todo#2763).

Owner review of the 19 Nov 2026 daily: no images, "résumé" with accents, the
brand written "AskTheRecruiter", labels that did not fit the article, a subject
that promised "2 ways to strengthen your applications", no visible sign-up
button, and a tracking note two sentences long. Later the same day: the two
tracker emails are hard to read (no dividers) and every email needs its logo.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import digest_layout  # noqa: E402
import digest_transport  # noqa: E402
import email_theme  # noqa: E402
from test_digest_email_layout import message  # noqa: E402
from test_digest_scope_rules import PHP, compose  # noqa: E402

TRACKING = ("We count opens and clicks to learn which articles help most. "
            "How we use this. Unsubscribe stops both.")


def visible(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class Brand(unittest.TestCase):

    def test_wordmark_and_sender_read_ask_the_recruiter(self):
        self.assertEqual(email_theme.WORDMARK, "Ask The Recruiter")
        self.assertEqual(digest_transport.SENDER_NAME, "Ask The Recruiter")
        self.assertEqual(digest_layout.CAREER_INSIGHTS,
                         "Career Insights from Ask The Recruiter")

    def test_every_edition_has_its_logo_on_our_domain_with_alt(self):
        for sections in (("articles",),):  # trackers: text wordmark (Round3)
            html = message(sections, freq="daily").html
            logo = re.search(r'<img[^>]*data-logo[^>]*>|<img[^>]*src="'
                             + re.escape(email_theme.LOGO_URL) + r'"[^>]*>', html)
            self.assertIsNotNone(logo, sections)
            self.assertIn('alt="Ask The Recruiter', logo.group(0))
            self.assertTrue(email_theme.LOGO_URL.startswith(
                "https://asktherecruiter.com/"))

    def test_no_accented_resume_and_no_joined_brand_in_any_body(self):
        for sections in (("layoff",), ("talent",), ("articles",)):
            m = message(sections, freq="daily")
            for body in (visible(m.html), m.text):
                self.assertNotIn("résumé", body)
                self.assertNotIn("r&eacute;sum&eacute;", body)
                self.assertNotRegex(body, r"AskTheRecruiter(?!\.com)")


class Readable(unittest.TestCase):

    def test_sections_are_split_by_a_thick_divider(self):
        html = message(("layoff", "talent"), freq="daily").html
        self.assertGreaterEqual(html.count(f"border-top:{email_theme.DIVIDER_PX}px solid"), 2)
        self.assertGreaterEqual(email_theme.DIVIDER_PX, 3)

    def test_section_headings_have_room_above(self):
        self.assertRegex(digest_layout.TAG_STYLES["h3"], r"margin:2[4-9]px 0 [6-9]px")


class Tracking(unittest.TestCase):

    def test_calm_one_line_with_privacy_link(self):
        self.assertEqual(" ".join(digest_layout.TRACKING_SENTENCES), TRACKING)
        html = message(("articles",), freq="daily").html
        self.assertRegex(html, r'href="https://asktherecruiter\.com/privacy[^"]*#email-opens-and-clicks"')
        self.assertIn(">How we use this</a>", html)
        self.assertIn(">Unsubscribe</a> stops both.", html)

    def test_plugin_twin_agrees(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "..",
                                "wordpress-plugin", "ai-layoff-tracker",
                                "includes", "subscribe.php"), encoding="utf-8").read()
        self.assertIn(TRACKING.split(" How")[0], src)


class CtaButton(unittest.TestCase):

    def test_button_after_the_lead_story_with_dated_utm(self):
        m = message(("articles",), freq="daily", **{"from": "2026-11-18",
                                                     "to": "2026-11-19"})
        btn = re.search(r'<a[^>]*data-cta[^>]*href="([^"]+)"[^>]*>Check my match score</a>'
                        r'|<a[^>]*href="([^"]+)"[^>]*data-cta[^>]*>Check my match score</a>',
                        m.html)
        self.assertIsNotNone(btn)
        url = btn.group(1) or btn.group(2)
        for part in ("utm_source=newsletter", "utm_medium=email",
                     "utm_campaign=daily-20261119", "utm_content=cta"):
            self.assertIn(part, url)
        self.assertLess(m.html.index("Check my match score"), m.html.index("unsub"))
        self.assertIn("Check my match score", m.text)


class CleanGuardAllowsOnlyOurImages(unittest.TestCase):

    def _msg(self, img):
        return digest_transport.Message(to="a@example.com", subject="s",
                                        html=f"<p>{img}</p><a href=\"https://asktherecruiter.com/u?t=1\">Unsubscribe</a>", text="A real plain text part. Unsubscribe: https://asktherecruiter.com/u?t=1",
                                        from_addr="x@asktherecruiter.com",
                                        headers={"List-Unsubscribe": "<https://asktherecruiter.com/u?t=1>",
                                                 "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"})

    def test_own_https_image_with_alt_passes(self):
        digest_transport.assert_message_is_clean(self._msg(
            '<img src="https://asktherecruiter.com/blog/wp-content/uploads/a.png" alt="A cover">'))

    def test_foreign_or_unlabelled_image_is_refused(self):
        for img in ('<img src="https://evil.example/p.gif" alt="x">',
                    '<img src="https://asktherecruiter.com/a.png">',
                    '<img src="http://asktherecruiter.com/a.png" alt="x">'):
            with self.assertRaises(digest_transport.DigestPolicyError):
                digest_transport.assert_message_is_clean(self._msg(img))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class Newsletter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        posts = [
            {"title": "Quality over quantity: why 10 tailored applications beat 100",
             "link": "https://asktherecruiter.com/blog/quality/",
             "excerpt": "Sending fewer, sharper applications got our test readers more interviews.",
             "content": "<p>x</p>", "date": "2026-11-18 10:00:00",
             "cover": "https://asktherecruiter.com/blog/wp-content/uploads/q.png",
             "cover_alt": "A short stack of tailored applications"},
            {"title": "How recruiters read a gap year", "link": "https://asktherecruiter.com/blog/gap/",
             "excerpt": "A gap on a resume is rarely the problem recruiters say it is, if you name it.",
             "content": "<p>x</p>", "date": "2026-11-18 09:00:00",
             "cover": "https://asktherecruiter.com/blog/wp-content/uploads/g.png"},
        ]
        cls.out = compose({"compose": "articles", "from": "2026-11-18", "to": "2026-11-19",
                           "freq": "daily", "posts": posts})

    def test_each_article_has_its_cover_with_alt(self):
        html = self.out["html"]
        self.assertIn('src="https://asktherecruiter.com/blog/wp-content/uploads/q.png"', html)
        self.assertIn('alt="A short stack of tailored applications"', html)
        # No alt typed on the image: the title is the alt, never empty.
        self.assertIn('alt="How recruiters read a gap year"', html)
        self.assertIn('width="600"', html)
        # The wp_mail fallback has no restyle pass: fluid inline (Codex P2).
        self.assertIn('style="display:block;width:100%;max-width:600px;height:auto;border:0;"', html)

    def test_labels_come_from_the_article_not_a_fixed_string(self):
        body = self.out["html"] + self.out["text"]
        for fixed in ("Read the comparison", "picking the right tool",
                      "a practical step you can use", "context that helps you judge"):
            self.assertNotIn(fixed, body)
        self.assertIn("Sending fewer, sharper applications", self.out["text"])
        self.assertIn("A gap on a resume is rarely the problem", self.out["text"])

    def test_subject_matches_the_content(self):
        self.assertEqual(self.out["metric"], "2 new career reads")

    def test_copy_rules(self):
        body = self.out["html"] + self.out["text"]
        self.assertNotIn("AskTheRecruiter", body)
        self.assertNotIn("résumé", body)


if __name__ == "__main__":
    unittest.main()


class CoordinatorRound2(unittest.TestCase):
    """Brand-coloured dividers, one unsubscribe link, a button in every email."""

    def test_every_email_has_the_button_and_one_unsubscribe_link(self):
        for sections in (("layoff",), ("talent",), ("articles",), ("layoff", "talent")):
            m = message(sections, freq="daily")
            self.assertEqual(m.html.count(">Check my match score</a>"), 1, sections)
            self.assertEqual(len(re.findall(r">Unsubscribe[^<]*</a>", m.html)), 1, sections)

    def test_divider_is_the_brand_colour(self):
        html = message(("layoff", "talent"), freq="daily").html
        self.assertIn(f"border-top:4px solid {email_theme.ACCENT}", html)


class ButtonContrast(unittest.TestCase):
    """Codex P2: the dark link colour overrode the button label (2.70:1)."""

    def test_label_clears_aa_in_light_and_dark(self):
        self.assertGreaterEqual(email_theme.contrast(email_theme.BUTTON_TEXT, email_theme.ACCENT), 4.5)
        self.assertGreaterEqual(email_theme.contrast(email_theme.DARK_BG, email_theme.DARK_ACCENT), 4.5)

    def test_dark_block_gives_the_button_its_own_pair(self):
        block = email_theme.dark_style_block()
        self.assertIn(f".et-card a.et-btn{{color:{email_theme.DARK_BG}!important;", block)
        self.assertIn(f".et-btn-td{{background-color:{email_theme.DARK_ACCENT}!important;", block)
        # The button rule comes after the generic link rule, so it wins.
        self.assertGreater(block.index("a.et-btn"), block.index(".et-card a,"))
        btn = email_theme.button("Go", "https://asktherecruiter.com/")
        self.assertIn('class="et-btn"', btn)
        self.assertIn('class="et-btn-td"', btn)


class Round3(unittest.TestCase):
    """No tracker logo file exists in either tracker repo (checked 2026-11-19),
    so the tracker emails use a text wordmark; only the newsletter shows the
    Ask The Recruiter mark. Every content heading opens with a thick rule."""

    def test_tracker_emails_use_a_text_wordmark(self):
        for sections, product in ((("layoff",), "AI Layoff Tracker"),
                                  (("talent",), "Talent Intelligence Tracker")):
            html = message(sections, freq="daily").html
            self.assertNotIn("data-logo", html)
            self.assertIn(">by Ask The Recruiter</p>", html)
            self.assertIn(f">{product}</p>", html)

    def test_newsletter_keeps_the_mark(self):
        self.assertIn("data-logo", message(("articles",), freq="daily").html)

    def test_content_headings_carry_a_thick_divider(self):
        html = message(("layoff",), freq="weekly").html
        h3 = re.findall(r"<h3 style=\"([^\"]*)\"", html)
        self.assertTrue(h3)
        for style in h3:
            self.assertIn(f"border-top:3px solid {email_theme.ACCENT}", style)


class CtaBox(unittest.TestCase):
    """DK item 11: the button sits in its own tinted box before the footer,
    with a lead line that fits the email."""

    LEADS = {
        "layoff": "Affected by a layoff? Check how your resume fits a new role, free.",
        "talent": "Interested in companies that are hiring? Check how your resume fits their roles, free.",
    }

    def test_box_before_footer_with_the_right_lead(self):
        for key, lead in self.LEADS.items():
            m = message((key,), freq="daily", **{"from": "2026-11-18", "to": "2026-11-19"})
            box = re.search(r'<td data-cta-box[^>]*>(.*?)</td></tr>', m.html, re.S)
            self.assertIsNotNone(box, key)
            self.assertIn(f"background-color:{email_theme.PANEL_TINT}", m.html)
            self.assertIn(lead, m.html)
            self.assertIn(lead, " ".join(m.text.split()))
            self.assertLess(m.html.index(lead), m.html.index("You get this because"))
            self.assertIn(f"utm_campaign={key}-daily-20261119", m.html)

    def test_button_is_not_inside_a_data_section(self):
        m = message(("layoff",), freq="daily")
        self.assertGreater(m.html.index("Check my match score"),
                           m.html.index("Open the AI Layoff Tracker"))
