"""Every link to our own site in a digest email carries UTM tags.

The defect (2026-11-13 audit of the sent editions): one tagged link per email,
the footer's. Methodology, edition page, filtered tracker, contact and the
sister tracker went out untagged, and tracked /click links landed untagged.
"""
import html
import re
import subprocess
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import digest_preview  # noqa: E402
import digest_send  # noqa: E402
import digest_utm  # noqa: E402

SUB = (Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
       / "includes" / "subscribe.php")
HOSTS = digest_utm.own_hosts("https://asktherecruiter.com/blog/x/unsubscribe/t/")
UTM = "utm_source=ai-layoff-tracker&utm_medium=email&utm_campaign=digest-weekly"


def _links(body):
    return [html.unescape(h) for h in re.findall(r'href="([^"]+)"', body)]


class RelayTagging(unittest.TestCase):
    def test_built_message_has_no_untagged_link_to_a_page_of_ours(self):
        m = digest_preview.sample_message()
        for body in (_links(m.html), re.findall(r"https?://\S+", m.text)):
            own = [u for u in body
                   if (urllib.parse.urlsplit(u).hostname or "") in HOSTS
                   and not any(p in u for p in digest_utm.NEVER_TAG)]
            self.assertTrue(own)
            for u in own:
                self.assertIn("utm_source=ai-layoff-tracker", u, u)

    def test_reader_tokens_and_the_unsubscribe_header_are_never_touched(self):
        m = digest_preview.sample_message()
        self.assertEqual(m.headers["List-Unsubscribe"], f"<{digest_preview.UNSUB}>")
        for u in _links(m.html):
            if "unsub" in u or "/preferences/" in u:
                self.assertNotIn("utm_", u, u)

    def test_query_and_fragment_survive_and_the_tags_go_before_the_hash(self):
        u = "https://asktherecruiter.com/blog/ai-layoff-tracker/?from=2026-11-02&q=#alt-export-csv"
        self.assertEqual(digest_utm.tag_url(u, "weekly", HOSTS),
                         "https://asktherecruiter.com/blog/ai-layoff-tracker/?from=2026-11-02&q=&"
                         + UTM + "#alt-export-csv")

    def test_campaign_names_the_tier(self):
        for tier in ("daily", "weekly", "monthly"):
            self.assertIn(f"utm_campaign=digest-{tier}",
                          digest_utm.tag_url("https://asktherecruiter.com/blog/", tier, HOSTS))
        self.assertIn("utm_campaign=digest&",
                      digest_utm.tag_url("https://asktherecruiter.com/blog/", "", HOSTS) + "&")

    def test_not_ours_or_already_tagged_or_a_route_stays_byte_for_byte(self):
        for u in ("https://www.bbc.com/news/articles/x",
                  "https://asktherecruiter.com/?utm_source=ai-layoff-tracker&utm_medium=referral",
                  "https://asktherecruiter.com/blog/wp-json/layoffs/v1/click?s=1&l=ab",
                  "https://asktherecruiter.com/blog/ai-layoff-tracker/confirm/tok/",
                  "https://asktherecruiter.com/blog/digest-preferences/?t=bbbb",
                  "https://asktherecruiter.com/blog/any-page/?token=x",
                  "mailto:info@asktherecruiter.com"):
            self.assertEqual(digest_utm.tag_url(u, "daily", HOSTS), u)

    def test_html_entities_and_untouched_links_keep_their_encoding(self):
        body = ('<a href="https://www.bbc.com/a?x=1&#038;y=2">a</a>'
                '<a href="https://asktherecruiter.com/blog/contact/">c</a>')
        out = digest_utm.tag_html(body, "daily", HOSTS)
        self.assertIn('href="https://www.bbc.com/a?x=1&#038;y=2"', out)
        self.assertIn('href="https://asktherecruiter.com/blog/contact/?utm_source=ai-layoff-tracker'
                      '&amp;utm_medium=email&amp;utm_campaign=digest-daily"', out)

    def test_text_sentence_punctuation_stays_outside_the_url(self):
        out = digest_utm.tag_text("See https://asktherecruiter.com/blog/contact/.", "daily", HOSTS)
        self.assertTrue(out.endswith("utm_campaign=digest-daily."), out)

    def test_build_message_applies_it(self):
        self.assertIn("digest_utm.tag_html(", Path(digest_send.__file__).read_text())


def _fn(name):
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", SUB.read_text(encoding="utf-8"), re.S)
    assert m, f"{name} is missing"
    return m.group(0)


def _php(expr):
    code = _fn("alt_digest_utm_url") + "\necho " + expr + ";"
    p = subprocess.run(["php", "-r", code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


class ClickRedirectTagging(unittest.TestCase):
    H = "array('asktherecruiter.com','www.asktherecruiter.com')"

    def _tag(self, url, freq="weekly"):
        return _php(f"alt_digest_utm_url('{url}', '{freq}', {self.H})")

    def test_the_tracker_landing_is_tagged_before_the_fragment(self):
        self.assertEqual(self._tag("https://asktherecruiter.com/blog/ai-layoff-tracker/?from=1#x"),
                         "https://asktherecruiter.com/blog/ai-layoff-tracker/?from=1&" + UTM + "#x")
        self.assertEqual(self._tag("https://asktherecruiter.com/blog/p/", "daily"),
                         "https://asktherecruiter.com/blog/p/?utm_source=ai-layoff-tracker"
                         "&utm_medium=email&utm_campaign=digest-daily")

    def test_foreign_tagged_and_token_urls_come_back_unchanged(self):
        for u in ("https://evil.example/", "https://asktherecruiter.com/?utm_source=x",
                  "https://asktherecruiter.com/blog/ai-layoff-tracker/unsubscribe/t/",
                  "https://asktherecruiter.com/blog/digest-preferences/?t=bbbb",
                  "https://asktherecruiter.com/blog/any-page/?token=x"):
            self.assertEqual(self._tag(u), u)

    def test_the_handler_tags_only_a_stored_row_and_still_redirects_to_url(self):
        body = _fn("alt_api_digest_click")
        self.assertIn("$url = alt_digest_utm_url($url, $freq, alt_digest_link_hosts());", body)
        self.assertLess(body.index("alt_digest_utm_url("), body.rindex("wp_safe_redirect($url"))


if __name__ == "__main__":
    unittest.main()
