"""Daily edition fixes from the owner's feedback of 2026-11-04.

1. Layoff news leads. Blog and career reads sit in a clearly labelled
   "Career resources" section, only for readers who ticked the existing
   `articles` list (consent_articles), and never make up a whole edition for
   a layoff-list reader.
2. The subject leads with the reader benefit and never names a competitor
   (the featured title "Jobscan vs Teal vs Rezi" used to BE the subject).
3. Excerpts read like a person wrote them: no SEO questions. Each article has
   a call to action that says what it is ("Read the guide", "Read the
   comparison").
4. A one-line "Why it matters" takeaway per item.
5. A condensed footer that still keeps unsubscribe, preferences and the
   tracking disclosure.

The composer is PHP and is driven through the harness; without php those
tests SKIP (UNKNOWN, not a pass).
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from test_digest_scope_rules import PHP, SUBSCRIBE, compose  # noqa: E402
from test_digest_career_insights import fixture  # noqa: E402
import digest_layout  # noqa: E402
import digest_send  # noqa: E402

COMPETITORS = ("Jobscan", "Teal", "Rezi", "Simplify")
UNSUB = "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/abc"
MANAGE = "https://asktherecruiter.com/blog/ai-layoff-tracker/preferences/1-abc"


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class CareerResourcesSection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = compose(fixture())
        cls.text, cls.html = cls.out["text"], cls.out["html"]

    def test_clearly_labelled_secondary_section(self):
        self.assertTrue(self.text.startswith("Career resources\n"))
        self.assertIn("<h2>Career resources</h2>", self.html)
        self.assertIn("opted into career resources", self.text)

    def test_subject_leads_with_the_benefit_and_names_no_competitor(self):
        metric = self.out["metric"]
        self.assertEqual(metric, "3 ways to strengthen your applications")
        for name in COMPETITORS:
            self.assertNotIn(name, metric)
            self.assertNotIn(name, self.out.get("preheader", ""))

    def test_no_seo_question_in_any_excerpt(self):
        for line in self.text.splitlines():
            if line.startswith(("Why it matters", "  ")) or not line.strip():
                continue
            if any(t in line for t in ("Jobscan", "gap year", "Salary bands")):
                continue  # a title is the author's, not an excerpt
            self.assertFalse(line.rstrip().endswith("?"), line)

    def test_every_article_has_a_specific_call_to_action(self):
        self.assertIn("Read the comparison &rarr;", self.html)
        self.assertIn("Read the guide &rarr;", self.html)
        self.assertEqual(self.html.count("&rarr;</a>"), 3)
        self.assertIn("Read the comparison: https://asktherecruiter.com/blog/resume-tools/",
                      self.text)

    def test_one_why_it_matters_line_per_item(self):
        self.assertEqual(self.text.count("Why it matters: "), 3)
        self.assertEqual(self.html.count('data-alt="why"'), 3)

    def test_house_style(self):
        body = self.text + self.html
        self.assertNotRegex(body, "[–—]")
        for word in ("bl" + "ind", "hon" + "est", "halluc" + "inat"):
            self.assertNotIn(word, body.lower())


def _payload():
    def sec(name):
        return {"html": f"<h2>{name}</h2><p>x</p>", "text": f"{name}\nx",
                "preheader": "", "metric": f"{name} metric",
                "minor": name == "articles"}
    return {"freq": "daily", "from": "2026-11-03", "to": "2026-11-03",
            "sections": {"articles": sec("articles"), "layoff": sec("layoff")}}


class LayoffNewsLeads(unittest.TestCase):

    def test_articles_go_last_whatever_order_the_lists_arrive_in(self):
        parts = digest_send.usable_sections(_payload(), ["articles", "layoff"])
        self.assertEqual([p[0] for p in parts], ["layoff", "articles"])

    def test_articles_alone_are_never_a_layoff_readers_whole_edition(self):
        payload = _payload()
        del payload["sections"]["layoff"]
        recipient = {"unsub_url": UNSUB, "lists": ["layoff", "articles"]}
        self.assertIsNone(digest_send.build_message(
            payload, recipient, "a@asktherecruiter.com", "a@asktherecruiter.com"))

    def test_an_articles_only_reader_still_gets_career_resources(self):
        payload = _payload()
        del payload["sections"]["layoff"]
        recipient = {"unsub_url": UNSUB, "lists": ["articles"]}
        self.assertIsNotNone(digest_send.build_message(
            payload, recipient, "a@asktherecruiter.com", "a@asktherecruiter.com"))

    def test_the_wp_mail_fallback_holds_the_same_rule(self):
        with open(SUBSCRIBE, encoding="utf-8") as handle:
            src = handle.read()
        self.assertIn("alt_digest_articles_only_for_layoff_reader(", src)


class CondensedFooter(unittest.TestCase):

    def test_fewer_words_same_promises(self):
        words = sum(len(s.split()) for s in digest_layout.footer_sentences(True))
        self.assertLessEqual(words, 36)
        html = digest_layout._footer(UNSUB, MANAGE)
        self.assertIn(f'href="{UNSUB}"', html)
        self.assertIn(f'href="{MANAGE}"', html)
        self.assertIn(" ".join(digest_layout.TRACKING_SENTENCES), html)

    def test_one_paragraph_above_the_disclosure(self):
        html = digest_layout._footer(UNSUB, MANAGE)
        top = html.split("<table")[0]
        self.assertEqual(len(re.findall(r"<p\b", top)), 1)


if __name__ == "__main__":
    unittest.main()
