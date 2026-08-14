"""Guards for the regional-feed collector (sources/regional_feeds.py).

The load-bearing tests are the FIXTURE tests (a real-shaped item in each feed's
real shape must survive to a raw dict carrying its headcount), the AGGREGATOR
guard (a compiled layoff tally can never enter the path), and the REQUEST-URL
guard the 2026-08-14 local_news review demanded: a test that reads what the
collector actually requests, so a dead feed URL or a changed scheme fails
loudly instead of returning quietly empty.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The politeness gap between live fetches is read at import time. These tests
# never touch the network (every fetch is injected), so zero it out.
os.environ.setdefault("REGIONAL_FEEDS_GAP_SECONDS", "0")

from sources import regional_feeds as rf  # noqa: E402


def rss(*items, content=None):
    """A minimal but real RSS 2.0 body in the shape these feeds return.

    `content` optionally adds a <content:encoded> block to every item, which is
    the Caribbean News Global shape (full article text inside the feed).
    """
    body = []
    for title, link, desc in items:
        enc = (f"<content:encoded><![CDATA[{content}]]></content:encoded>"
               if content else "")
        body.append(
            "<item>"
            f"<title>{title}</title>"
            f"<link>{link}</link>"
            f"<description>{desc}</description>"
            "<pubDate>Fri, 14 Aug 2026 09:00:00 GMT</pubDate>"
            f"{enc}"
            "</item>")
    return ("<?xml version='1.0' encoding='UTF-8'?>"
            "<rss version='2.0' "
            "xmlns:content='http://purl.org/rss/1.0/modules/content/'>"
            "<channel>" + "".join(body) + "</channel></rss>")


# One real-shaped layoff item per feed, in the feed's own language and shape.
# Each carries an employer and a headcount, which is what makes it storable.
FIXTURES = {
    "rnz_pacific": (
        "Air Vanuatu to lay off 150 staff in restructure",
        "https://www.rnz.co.nz/international/pacific-news/512345/air-vanuatu",
        "The national carrier confirmed 150 redundancies across Port Vila."),
    "pacific_island_times": (
        "Guam hotel operator cuts 80 jobs as arrivals slump",
        "https://www.pacificislandtimes.com/post/guam-hotel-cuts",
        "The layoffs affect 80 employees across two Tumon properties."),
    "financial_afrik": (
        "Senegal : la Sonatel annonce la suppression de 300 postes",
        "https://www.financialafrik.com/2026/08/14/sonatel-suppression-postes/",
        "Ce contenu est reserve aux membres."),
    "jeune_afrique": (
        "Cameroun : plan social chez Camtel, 400 emplois supprimes",
        "https://www.jeuneafrique.com/1832999/economie/camtel-plan-social/",
        "L'operateur public engage des licenciements touchant 400 salaries."),
    "caribbean_news_global": (
        "Saint Lucia resort retrenches 120 workers",
        "https://caribbeannewsglobal.com/saint-lucia-resort-retrenches-workers/",
        "CASTRIES, St Lucia - The resort confirmed the retrenchment of 120 workers."),
}


class FeedTableTests(unittest.TestCase):
    def test_every_feed_has_url_outlet_note_and_countries(self):
        self.assertTrue(rf.FEEDS)
        for f in rf.FEEDS:
            with self.subTest(feed=f.key):
                self.assertTrue(f.url.startswith("https://"))
                self.assertTrue(f.outlet.strip())
                self.assertTrue(f.note.strip())
                self.assertTrue(f.countries, "no coverage claim to show on the "
                                             "sources page")

    def test_no_feed_is_an_aggregator(self):
        """The feeds themselves must be newsrooms, never tally products."""
        for f in rf.FEEDS:
            with self.subTest(feed=f.key):
                self.assertFalse(rf.is_aggregator(f.url, f.outlet))

    def test_feed_keys_are_unique(self):
        keys = [f.key for f in rf.FEEDS]
        self.assertEqual(len(keys), len(set(keys)))


class RequestUrlGuardTests(unittest.TestCase):
    """The guard the local_news review demanded: read what the collector
    actually requests. A mutation that drops a feed, rewrites its URL or
    switches scheme must fail HERE, not return quietly empty in production."""

    def test_an_armed_run_requests_every_configured_feed_url_exactly(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return 200, rss()

        with patch.dict(os.environ, {"REGIONAL_FEEDS": "all"}, clear=False):
            rf.pull_regional_feeds(fetch=fetch)
        self.assertEqual(sorted(calls), sorted(f.url for f in rf.FEEDS),
                         "the requests made do not match the feed table")

    def test_a_dead_feed_is_a_counted_error_not_a_quiet_zero(self):
        with patch.dict(os.environ, {"REGIONAL_FEEDS": "rnz_pacific"}, clear=False):
            rows, stats = rf.pull_regional_feeds(fetch=lambda u, timeout: (404, ""))
        self.assertEqual(rows, [])
        self.assertGreater(stats["rnz_pacific"]["errors"], 0)
        self.assertIn("404", rf.pull_regional_feeds.last_error)

    def test_a_200_that_parses_to_zero_items_is_an_error(self):
        """The scheme-changed shape: the URL still answers but the body is no
        longer the feed. Marianas Variety's platform serves a full HTML page
        with a 200 at former feed paths; that must degrade, not pass."""
        with patch.dict(os.environ, {"REGIONAL_FEEDS": "rnz_pacific"}, clear=False):
            rows, stats = rf.pull_regional_feeds(
                fetch=lambda u, timeout: (200, "<!DOCTYPE html><html></html>"))
        self.assertEqual(rows, [])
        self.assertGreater(stats["rnz_pacific"]["errors"], 0)
        self.assertTrue(rf.pull_regional_feeds.last_error)

    def test_an_empty_but_valid_feed_is_not_an_error(self):
        """A quiet week in the Pacific is honest absence, not breakage."""
        with patch.dict(os.environ, {"REGIONAL_FEEDS": "rnz_pacific"}, clear=False):
            rows, stats = rf.pull_regional_feeds(fetch=lambda u, timeout: (200, rss()))
        self.assertEqual(rows, [])
        self.assertEqual(stats["rnz_pacific"]["errors"], 0)
        self.assertIsNone(rf.pull_regional_feeds.last_error)


class DormancyTests(unittest.TestCase):
    """Armed by committed default (the measured total is under a dollar a
    month; the price lives in ARMED_BY_DEFAULT's comment). Both directions are
    pinned: a default that quietly disarms loses the long tail without a diff,
    and an off switch that quietly stops working makes every dry run a paid
    run."""

    def test_off_makes_no_request_and_returns_nothing(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return 200, rss()

        with patch.dict(os.environ, {"REGIONAL_FEEDS": "off"}, clear=False):
            rows, stats = rf.pull_regional_feeds(fetch=fetch)
        self.assertEqual(rows, [])
        self.assertEqual(calls, [], "a DORMANT collector made a network request")

    def test_unset_arms_every_wired_feed_by_committed_default(self):
        with patch.dict(os.environ, {"REGIONAL_FEEDS": ""}, clear=False):
            armed = rf.armed_feeds()
        self.assertEqual(sorted(f.key for f in armed),
                         sorted(f.key for f in rf.FEEDS))

    def test_arming_one_feed_arms_only_that_feed(self):
        with patch.dict(os.environ, {"REGIONAL_FEEDS": "rnz_pacific"}, clear=False):
            self.assertEqual([f.key for f in rf.armed_feeds()], ["rnz_pacific"])

    def test_unknown_feed_is_ignored_not_guessed(self):
        with patch.dict(os.environ,
                        {"REGIONAL_FEEDS": "atlantis_times,rnz_pacific"},
                        clear=False):
            self.assertEqual([f.key for f in rf.armed_feeds()], ["rnz_pacific"])


class RelevanceFilterTests(unittest.TestCase):
    def test_ordinary_regional_news_is_dropped_before_it_costs_anything(self):
        for title in (
            "Fiji court rules COI report into appointment was unlawful",
            "Guam lawmaker wants USPS to fix unfair private fees",
            "Jamaica - Ghana to expand bilateral cooperation",
            "Comment l'Afrique du Sud a double l'Espagne sur les agrumes",
        ):
            with self.subTest(title=title):
                keep, why = rf.relevance(title, "")
                self.assertFalse(keep, f"non-layoff story kept ({why})")

    def test_collective_reduction_vocabulary_is_kept_in_both_languages(self):
        for title in (
            "Air Vanuatu to lay off 150 staff in restructure",
            "Saint Lucia resort retrenches 120 workers",
            "Senegal : la Sonatel annonce la suppression de 300 postes",
            "Cameroun : plan social chez Camtel, 400 emplois supprimes",
            "Mine cuts 200 jobs in Solomon Islands",
        ):
            with self.subTest(title=title):
                keep, why = rf.relevance(title, "")
                self.assertTrue(keep, f"real layoff story dropped: {title}")

    def test_sack_is_only_kept_with_a_workforce_word(self):
        """The Nigeria lesson: a bare 'sack' matches kidnapping stories."""
        keep, _ = rf.relevance("Minister sacked over scandal", "")
        self.assertFalse(keep)
        keep, _ = rf.relevance("Cannery sacks 90 workers in Pago Pago", "")
        self.assertTrue(keep)

    def test_individual_dismissal_vocabulary_stays_out(self):
        """'licenciement' in the singular is court-story vocabulary."""
        keep, _ = rf.relevance(
            "Tribunal : le licenciement du directeur juge abusif", "")
        self.assertFalse(keep)


class AggregatorGuardTests(unittest.TestCase):
    def test_a_tally_product_never_becomes_a_raw_dict(self):
        feed = rf.by_key("rnz_pacific")
        item = {"title": "Layoff tracker: every Pacific cut in 2026",
                "link": "https://example.test/layoff-tracker",
                "description": "layoffs list", "published": "", "content": ""}
        self.assertIsNone(rf.build_raw(feed, item))

    def test_a_roundup_on_an_ordinary_path_is_refused(self):
        feed = rf.by_key("caribbean_news_global")
        item = {"title": "Every layoff announced across the Caribbean this year",
                "link": "https://caribbeannewsglobal.com/an-ordinary-slug/",
                "description": "layoffs", "published": "", "content": ""}
        self.assertIsNone(rf.build_raw(feed, item))


class RawDictContractTests(unittest.TestCase):
    def test_each_fixture_survives_discovery_with_its_headcount(self):
        expected = {"rnz_pacific": "150", "pacific_island_times": "80",
                    "financial_afrik": "300", "jeune_afrique": "400",
                    "caribbean_news_global": "120"}
        for key, fx in FIXTURES.items():
            with self.subTest(feed=key):
                def fetch(url, timeout, fx=fx):
                    return 200, rss((fx[0], fx[1], fx[2]))
                with patch.dict(os.environ, {"REGIONAL_FEEDS": key}, clear=False):
                    rows, stats = rf.pull_regional_feeds(fetch=fetch)
                self.assertEqual(len(rows), 1,
                                 f"{key}: fixture did not survive discovery")
                self.assertIn(expected[key], rows[0]["raw_text"])
                self.assertEqual(stats[key]["kept"], 1)

    def test_the_dict_shape_matches_the_shared_news_contract(self):
        fx = FIXTURES["rnz_pacific"]
        raw = rf.build_raw(rf.by_key("rnz_pacific"), {
            "title": fx[0], "link": fx[1], "description": fx[2],
            "published": "Fri, 14 Aug 2026 09:00:00 GMT", "content": ""})
        for k in ("source_type", "source_name", "verification_level", "raw_text",
                  "source_url", "company_name", "ticker", "filing_date"):
            self.assertIn(k, raw)
        self.assertEqual(raw["source_type"], "news")
        self.assertEqual(raw["verification_level"], "bronze")
        self.assertEqual(raw["filing_date"], "2026-08-14")
        self.assertIsNone(raw["company_name"])

    def test_no_country_is_ever_pre_assigned(self):
        """A regional feed's job is discovery only; the extractor decides the
        country from the article, exactly as for every other news source."""
        fx = FIXTURES["caribbean_news_global"]
        raw = rf.build_raw(rf.by_key("caribbean_news_global"), {
            "title": fx[0], "link": fx[1], "description": fx[2],
            "published": "", "content": ""})
        self.assertNotIn("country", raw)

    def test_full_article_content_is_carried_into_raw_text_bounded(self):
        """Caribbean News Global ships whole articles inside the feed; the
        extractor should see that text, capped so one item cannot blow the
        extractor's text budget."""
        long_body = ("The resort confirmed the retrenchment of 120 workers. "
                     * 200)
        raw = rf.build_raw(rf.by_key("caribbean_news_global"), {
            "title": "Saint Lucia resort retrenches 120 workers",
            "link": "https://caribbeannewsglobal.com/x/", "description": "",
            "published": "", "content": long_body})
        self.assertIn("retrenchment of 120 workers", raw["raw_text"])
        self.assertLessEqual(len(raw["raw_text"]), rf.MAX_RAW_TEXT + 200)

    def test_raw_text_names_the_outlet(self):
        """Titles alone rarely tell a model where an outlet publishes."""
        fx = FIXTURES["financial_afrik"]
        raw = rf.build_raw(rf.by_key("financial_afrik"), {
            "title": fx[0], "link": fx[1], "description": fx[2],
            "published": "", "content": ""})
        self.assertIn("Financial Afrik", raw["raw_text"])


class CostBoundTests(unittest.TestCase):
    def test_a_feed_cannot_exceed_its_per_run_candidate_cap(self):
        many = [(f"Resort retrenches {i} workers",
                 f"https://caribbeannewsglobal.com/a{i}/",
                 "retrenchment confirmed") for i in range(60)]

        def fetch(url, timeout):
            return 200, rss(*many)

        with patch.dict(os.environ,
                        {"REGIONAL_FEEDS": "caribbean_news_global"}, clear=False):
            rows, _stats = rf.pull_regional_feeds(fetch=fetch)
        self.assertLessEqual(len(rows), rf.MAX_PER_FEED)


if __name__ == "__main__":
    unittest.main()
