"""Guards for offline resolution of Google News redirectors into publisher URLs.

The defect these pin: rows discovered via Google News RSS cited the REDIRECTOR,
so the permanent Wayback copy preserved a redirect page rather than the evidence,
and the opaque token expires — a citation that rots by construction.

The ceiling they also pin: news.google.com's robots.txt is `Disallow: /`, so the
resolution is OFFLINE ONLY. A future session that "improves" this by fetching the
redirector breaks test_module_makes_no_network_calls_at_all, and it is supposed
to.
"""
import ast
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import google_news_url as gnu  # noqa: E402
from sources.google_news import citation_summary  # noqa: E402

MODULE = Path(gnu.__file__)

# A real opaque token, captured live 2026-08-21. Its base64 body decodes to an
# `AU_yqL...` blob that embeds no URL — which is exactly why it is unresolvable.
OPAQUE = ("https://news.google.com/rss/articles/CBMisAFBVV95cUxPeWliTHMzLXRJWENJSHhGQjAx"
          "cHcyUmlJOFVqN3F2a1FJWVVYNFJWZFFWd25ZQ0g0bXloQ3BaMmpPRXlUUzNGVWs")


def legacy_token_url(article_url, extra=b""):
    """The pre-2024 shape: protobuf field 2 holding the article URL verbatim."""
    raw = article_url.encode()
    blob = b"\x08\x13\x22" + bytes([len(raw)]) + raw + extra
    token = base64.urlsafe_b64encode(blob).decode().rstrip("=")
    return "https://news.google.com/rss/articles/" + token


class OfflineOnly(unittest.TestCase):
    def test_module_makes_no_network_calls_at_all(self):
        """robots.txt forbids following the redirector, so nothing may fetch it.

        Asserted on the SOURCE, not on behaviour: a network call added behind a
        branch no test happens to take would pass a behavioural check."""
        tree = ast.parse(MODULE.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for banned in ("requests", "urllib3", "httpx", "http", "socket", "aiohttp"):
            self.assertNotIn(banned, imported,
                             f"{banned} imported: this module must never fetch "
                             "a page news.google.com/robots.txt disallows")
        # urllib is allowed, but only for parsing — never for opening a URL.
        self.assertNotIn("urllib.request", MODULE.read_text())


class Resolution(unittest.TestCase):
    def test_opaque_token_keeps_the_redirector_and_is_counted_unresolved(self):
        url, state = gnu.resolve(OPAQUE)
        self.assertEqual(state, "unresolved")
        self.assertEqual(url, OPAQUE,
                         "an unresolvable link must be handed back intact: it "
                         "reaches the article while the token lives")

    def test_unresolved_never_degrades_to_a_publisher_home_page(self):
        """The <source url> home page is identity, not evidence.

        Substituting it would make an unverifiable citation look archivable,
        which is the coverage-that-is-not-evidence failure this repo refuses."""
        url, _ = gnu.resolve(OPAQUE)
        self.assertNotEqual(url, "https://www.geekwire.com")
        self.assertTrue(url.startswith("https://news.google.com/"))

    def test_legacy_token_decodes_to_the_publisher_url(self):
        url, state = gnu.resolve(legacy_token_url("https://www.bbc.co.uk/news/business-123"))
        self.assertEqual((url, state), ("https://www.bbc.co.uk/news/business-123", "decoded"))

    def test_legacy_query_param_form_decodes(self):
        url, state = gnu.resolve(
            "https://news.google.com/news/url?sa=t&url=https%3A%2F%2Fwww.reuters.com%2Fb%2Fa.html")
        self.assertEqual((url, state), ("https://www.reuters.com/b/a.html", "decoded"))

    def test_decoded_prefers_the_canonical_url_over_an_amp_mirror(self):
        amp = b"\xd2\x01\x27" + b"https://amp.example.com/news/story-1"
        url, _ = gnu.resolve(legacy_token_url("https://www.example.com/news/story-1", amp))
        self.assertEqual(url, "https://www.example.com/news/story-1")

    def test_a_google_url_inside_the_blob_is_not_treated_as_the_article(self):
        url, state = gnu.resolve(legacy_token_url("https://news.google.com/foo"))
        self.assertEqual(state, "unresolved")

    def test_direct_publisher_link_passes_through_canonicalised(self):
        url, state = gnu.resolve(
            "https://www.geekwire.com/a.html?utm_source=g&utm_medium=rss&id=7#top")
        self.assertEqual((url, state), ("https://www.geekwire.com/a.html?id=7", "direct"))

    def test_canonicalise_keeps_params_that_may_route(self):
        """`ref`/`source`/`referrer` are real params on some CMSes. Stripping one
        repoints the citation, which is worse than an untidy URL."""
        for param in ("ref", "source", "referrer"):
            self.assertEqual(gnu.canonicalize(f"https://ex.com/a?{param}=x"),
                             f"https://ex.com/a?{param}=x")

    def test_canonicalise_is_stable(self):
        once = gnu.canonicalize("https://ex.com/a?b=1&utm_id=9&c=2")
        self.assertEqual(once, gnu.canonicalize(once),
                         "an unstable canonical form would churn the dedup hash")

    def test_empty_and_malformed_links_never_raise(self):
        for link in ("", None, "not a url", "https://", "news.google.com/rss/articles/!!"):
            self.assertIsInstance(gnu.resolve(link)[0], str)

    def test_national_google_news_hosts_are_recognised(self):
        for host in ("news.google.com", "news.google.co.uk", "news.google.de"):
            self.assertTrue(gnu.is_redirector(f"https://{host}/rss/articles/AAAA"))
        self.assertFalse(gnu.is_redirector("https://www.notgoogle.com/x"))
        self.assertFalse(gnu.is_redirector("https://googlenews.example.com/x"))


class CitationSummary(unittest.TestCase):
    def test_summary_names_the_ceiling_even_when_nothing_resolved(self):
        line = citation_summary({"direct": 0, "decoded": 0, "unresolved": 9})
        self.assertIn("0/9", line)
        self.assertIn("robots.txt", line,
                      "the reason must travel with the number, or a future "
                      "session re-derives it")

    def test_summary_counts_decoded_as_resolved(self):
        self.assertIn("3/4", citation_summary(
            {"direct": 1, "decoded": 2, "unresolved": 1}))

    def test_summary_handles_an_empty_run(self):
        self.assertEqual(citation_summary({}), "no items to cite")
        self.assertEqual(citation_summary(None), "no items to cite")


FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
  <item><title>Acme cuts 400 jobs</title>
        <link>{opaque}</link>
        <pubDate>Wed, 19 Aug 2026 10:00:00 GMT</pubDate>
        <source url="https://www.geekwire.com">geekwire.com</source></item>
  <item><title>Beta lays off 900 staff</title>
        <link>{legacy}</link>
        <pubDate>Wed, 19 Aug 2026 11:00:00 GMT</pubDate>
        <source url="https://www.reuters.com">Reuters</source></item>
</channel></rss>"""


class CollectorWiring(unittest.TestCase):
    """The resolution must happen BEFORE the row is built, in the collector that
    feeds extract_layoff_data — not in a later repair pass."""

    def _pull(self):
        from sources import google_news

        class _R:
            status_code = 200
            text = FEED.format(
                opaque=OPAQUE,
                legacy=legacy_token_url("https://www.reuters.com/biz/beta.html"))

        with patch.object(google_news.requests, "get", return_value=_R()),              patch.object(google_news.time, "sleep", lambda *_a, **_k: None),              patch.object(google_news, "_locales_for_now",
                          lambda: [google_news.GOOGLE_NEWS_LOCALES[0]]):
            return google_news.pull_google_news(queries=["layoffs"]), google_news

    def test_rows_carry_the_resolved_url_and_the_states_are_counted(self):
        rows, google_news = self._pull()
        by_url = {r["source_url"] for r in rows}
        self.assertIn("https://www.reuters.com/biz/beta.html", by_url)
        self.assertIn(OPAQUE, by_url)
        self.assertEqual(google_news.pull_google_news.citation_states,
                         {"direct": 0, "decoded": 1, "unresolved": 1})

    def test_rows_still_go_through_the_pipeline_unchanged(self):
        """raw_text is what the extractor reads; an empty one posts nothing."""
        rows, _ = self._pull()
        self.assertTrue(rows)
        for row in rows:
            self.assertTrue(row["raw_text"].strip())
            self.assertEqual(row["source_type"], "news")
            self.assertIsNone(row["company_name"],
                              "the extractor fills this in; the collector must not")

    def test_publisher_identity_still_reaches_the_row_as_the_source_name(self):
        rows, _ = self._pull()
        self.assertEqual({r["source_name"] for r in rows},
                         {"geekwire.com", "Reuters"})


if __name__ == "__main__":
    unittest.main()
