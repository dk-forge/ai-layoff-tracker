"""Guards for the national-publisher collector (sources/national_feeds.py).

The load-bearing tests are the PER-LANGUAGE FIXTURE tests (a real-shaped item
in each of the four languages these feeds publish in must survive to a raw
dict still carrying its headcount), the AGGREGATOR guard (a compiled layoff
tally can never enter the path), the REQUEST-URL guard (a test that reads what
the collector actually requests, so a dead feed URL or a changed scheme fails
loudly instead of returning quietly empty), and the CATALOGUE PARITY guard
(every wired feed is a row on the public catalogue, and no wired row claims a
publisher the code does not read).
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The politeness gap between live fetches is read at import time. These tests
# never touch the network (every fetch is injected), so zero it out.
os.environ.setdefault("NATIONAL_FEEDS_GAP_SECONDS", "0")

from sources import national_feeds as nf  # noqa: E402

# ...AND THE ENV VAR ALONE IS NOT ENOUGH, because `GAP` is read at IMPORT
# time. Run alone this module imports national_feeds first and the line above
# wins. Run under `discover`, test_cost_funnel has already imported cron,
# which imports this collector, so GAP was fixed at 1.0 long before this file
# was read and every paced fetch in here slept for real: 23.2s and 14.1s of
# the 869s suite that self-killed on its 15-minute ceiling on 2026-08-18.
# Exactly the import-order defect TECHLOG records for 2026-08-14, in two more
# places. Setting it on the module cannot lose that race. These tests inject
# every fetch, so there is no host to be polite to; the shipped default is
# untouched.
nf.GAP = 0.0

CATALOGUE = Path(__file__).resolve().parents[1] / "data" / "source_catalogue.json"


def rss(*items, content=None):
    """A minimal but real RSS 2.0 body in the shape these feeds return."""
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


# One real-shaped layoff item per LANGUAGE, in that language's own shape, each
# carrying an employer and a headcount - which is what makes it storable.
LANG_FIXTURES = {
    "en": ("dawn_business_pk",
           "Textile mill lays off 400 workers in Karachi",
           "https://www.dawn.com/news/1899001/textile-mill-lays-off-workers",
           "The mill confirmed 400 redundancies at its Karachi plant."),
    "es": ("gestion_pe",
           "Minera despide a 250 trabajadores en Arequipa",
           "https://gestion.pe/economia/minera-despidos-arequipa-noticia/",
           "La empresa confirmo el cese de 250 trabajadores este mes."),
    "ru": ("kursiv_kz",
           "Компания сократит штат на 300 сотрудников",
           "https://kz.kursiv.media/2026-08-14/kompaniya-sokratit-shtat/",
           "Массовое сокращение затронет 300 сотрудников в Алматы."),
    "sr": ("biznis_rs",
           "Fabrika otpusta 200 radnika u Kragujevcu",
           "https://biznis.rs/vesti/fabrika-otpusta-radnike/",
           "Kolektivno otpustanje pogodice 200 radnika."),
}
EXPECTED_COUNT = {"en": "400", "es": "250", "ru": "300", "sr": "200"}


class FeedTableTests(unittest.TestCase):
    def test_every_feed_has_url_outlet_country_language_and_note(self):
        self.assertTrue(nf.FEEDS)
        for f in nf.FEEDS:
            with self.subTest(feed=f.key):
                self.assertTrue(f.url.startswith("https://"))
                self.assertTrue(f.outlet.strip())
                self.assertTrue(f.country.strip())
                self.assertTrue(f.note.strip())
                self.assertIn(f.lang, nf.LANG_TERMS,
                              "a feed reads in a language with no vocabulary")

    def test_one_publisher_per_country(self):
        """The committed rule: the TOP verified publisher, once per country.
        A second feed for a country doubles the cost for correlated coverage."""
        seen = [f.country for f in nf.FEEDS]
        self.assertEqual(len(seen), len(set(seen)),
                         f"more than one feed per country: {seen}")

    def test_no_feed_is_an_aggregator(self):
        for f in nf.FEEDS:
            with self.subTest(feed=f.key):
                self.assertFalse(nf.is_aggregator(f.url, f.outlet))

    def test_feed_keys_are_unique(self):
        keys = [f.key for f in nf.FEEDS]
        self.assertEqual(len(keys), len(set(keys)))


class CatalogueParityTests(unittest.TestCase):
    """The owner's country research is repo data, not chat history. Every
    wired feed must appear on the public catalogue as wired, and the catalogue
    must not claim a wired publisher no collector actually reads."""

    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(CATALOGUE.read_text(encoding="utf-8"))["sources"]

    def test_every_row_has_country_language_and_a_known_status(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            with self.subTest(row=r.get("publisher")):
                self.assertTrue(r.get("country"))
                self.assertTrue(r.get("language"))
                self.assertIn(r.get("status"), {"wired", "researched", "refused"})

    def test_every_refused_row_states_its_measured_reason(self):
        """A refusal without evidence is a shrug that will be re-probed."""
        for r in self.rows:
            if r.get("status") == "refused":
                with self.subTest(row=r.get("publisher")):
                    self.assertTrue(str(r.get("reason", "")).strip(),
                                    "a refusal with no measured reason")

    def test_every_wired_national_feed_is_a_wired_catalogue_row(self):
        wired = {r["publisher"] for r in self.rows
                 if r.get("status") == "wired"
                 and r.get("collector") == "national_feeds"}
        self.assertEqual(wired, {f.outlet for f in nf.FEEDS})

    def test_no_catalogue_row_claims_an_unread_national_publisher(self):
        urls = {f.url for f in nf.FEEDS}
        for r in self.rows:
            if r.get("status") == "wired" and r.get("collector") == "national_feeds":
                with self.subTest(row=r["publisher"]):
                    self.assertIn(r.get("feed_url"), urls)


class RequestUrlGuardTests(unittest.TestCase):
    """Read what the collector actually requests. A mutation that drops a
    feed, rewrites its URL or switches scheme must fail HERE, not return
    quietly empty in production."""

    def test_an_armed_run_requests_every_configured_feed_url_exactly(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return 200, rss()

        with patch.dict(os.environ, {"NATIONAL_FEEDS": "all"}, clear=False):
            nf.pull_national_feeds(fetch=fetch)
        self.assertEqual(sorted(calls), sorted(f.url for f in nf.FEEDS),
                         "the requests made do not match the feed table")

    def test_a_dead_feed_is_a_counted_error_not_a_quiet_zero(self):
        with patch.dict(os.environ, {"NATIONAL_FEEDS": "kursiv_kz"}, clear=False):
            rows, stats = nf.pull_national_feeds(fetch=lambda u, timeout: (404, ""))
        self.assertEqual(rows, [])
        self.assertGreater(stats["kursiv_kz"]["errors"], 0)
        self.assertIn("404", nf.pull_national_feeds.last_error)

    def test_html_served_at_a_feed_path_is_an_error(self):
        """The measured failure shape of half the refused candidates: the URL
        answers 200 and serves a full HTML page. That must degrade, not pass."""
        with patch.dict(os.environ, {"NATIONAL_FEEDS": "kursiv_kz"}, clear=False):
            rows, stats = nf.pull_national_feeds(
                fetch=lambda u, timeout: (200, "<!doctype html><html></html>"))
        self.assertEqual(rows, [])
        self.assertGreater(stats["kursiv_kz"]["errors"], 0)
        self.assertTrue(nf.pull_national_feeds.last_error)

    def test_an_empty_but_valid_feed_is_not_an_error(self):
        """A week with no layoff story is honest absence, not breakage."""
        with patch.dict(os.environ, {"NATIONAL_FEEDS": "kursiv_kz"}, clear=False):
            rows, stats = nf.pull_national_feeds(fetch=lambda u, timeout: (200, rss()))
        self.assertEqual(rows, [])
        self.assertEqual(stats["kursiv_kz"]["errors"], 0)
        self.assertIsNone(nf.pull_national_feeds.last_error)


class DormancyTests(unittest.TestCase):
    """Armed by committed default at a measured $2.27/month worst case (the
    derivation lives in ARMED_BY_DEFAULT's comment). Both directions are
    pinned: a default that quietly disarms loses fourteen countries without a
    diff, and an off switch that quietly stops working makes every dry run a
    paid run."""

    def test_off_makes_no_request_and_returns_nothing(self):
        calls = []

        def fetch(url, timeout):
            calls.append(url)
            return 200, rss()

        with patch.dict(os.environ, {"NATIONAL_FEEDS": "off"}, clear=False):
            rows, _stats = nf.pull_national_feeds(fetch=fetch)
        self.assertEqual(rows, [])
        self.assertEqual(calls, [], "a DORMANT collector made a network request")

    def test_unset_arms_every_wired_feed_by_committed_default(self):
        with patch.dict(os.environ, {"NATIONAL_FEEDS": ""}, clear=False):
            armed = nf.armed_feeds()
        self.assertEqual(sorted(f.key for f in armed),
                         sorted(f.key for f in nf.FEEDS))

    def test_arming_one_feed_arms_only_that_feed(self):
        with patch.dict(os.environ, {"NATIONAL_FEEDS": "kursiv_kz"}, clear=False):
            self.assertEqual([f.key for f in nf.armed_feeds()], ["kursiv_kz"])

    def test_unknown_feed_is_ignored_not_guessed(self):
        with patch.dict(os.environ,
                        {"NATIONAL_FEEDS": "atlantis_herald,kursiv_kz"},
                        clear=False):
            self.assertEqual([f.key for f in nf.armed_feeds()], ["kursiv_kz"])


class RelevanceFilterTests(unittest.TestCase):
    def test_ordinary_national_news_is_dropped_before_it_costs_anything(self):
        for lang, title in (
            ("en", "Princess Iman blessed with twins"),
            ("en", "Maysan Oil Company markets 440-tonne sulphur shipment"),
            ("es", "Activos en custodia crecen y llegan a US$ 6.600 millones"),
            ("ru", "Акмарал Ерекешева заняла шестое место на чемпионате мира"),
            ("sr", "Cene stanova u Srbiji opet porasle, objavio RGZ"),
        ):
            with self.subTest(title=title):
                keep, why = nf.relevance(lang, title, "")
                self.assertFalse(keep, f"non-layoff story kept ({why})")

    def test_collective_vocabulary_is_kept_in_every_wired_language(self):
        for lang, (_key, title, _link, _desc) in LANG_FIXTURES.items():
            with self.subTest(lang=lang):
                keep, _why = nf.relevance(lang, title, "")
                self.assertTrue(keep, f"real layoff story dropped: {title}")

    def test_individual_dismissal_vocabulary_stays_out_per_language(self):
        """Spanish bare 'despido', Serbian bare 'otkaz' and Russian bare
        'увольнение' are the vocabulary of single-dismissal court stories."""
        for lang, title in (
            ("es", "Tribunal declara nulo el despido del gerente"),
            ("sr", "Sud poništio otkaz direktoru marketinga"),
            ("ru", "Верховный суд разъяснил порядок увольнения работника"),
        ):
            with self.subTest(title=title):
                keep, why = nf.relevance(lang, title, "")
                self.assertFalse(keep, f"court story kept ({why})")

    def test_a_non_english_feed_still_reads_english_wire_copy(self):
        """These publishers run English wire headlines inside their own feeds;
        a real layoff story is worth an extraction whatever it is written in."""
        keep, why = nf.relevance("ru", "Boeing to cut 900 jobs at its plant", "")
        self.assertTrue(keep, f"English story in a Russian feed dropped ({why})")

    def test_the_english_half_cannot_be_bought_with_playoff(self):
        """Every non-English feed is ALSO read with the English vocabulary, so
        a hole in the English set is a hole in all four languages at once.
        MEASURED 2026-08-17 while pricing the researched publishers: six of the
        ten items that passed this gate across 57 publishers' own feeds were
        Spanish-language football stories kept on `term:en:layoff` matching
        'playoffs'. Each would have bought a paid extraction."""
        for lang, title, snippet in (
            ("es", "Sporting Cristal venció 4-1 a Sport Huancayo",
             "se mete en la pelea por los playoffs"),
            ("en", "Tabla del Torneo Clausura", "playoff race"),
            ("ru", "Плей-офф чемпионата", "the playoffs continue"),
        ):
            with self.subTest(title=title):
                keep, why = nf.relevance(lang, title, snippet)
                self.assertFalse(keep, f"sports story kept on {why}")

    def test_a_body_with_bytes_after_the_closing_tag_still_parses(self):
        """The Kathmandu Post is WIRED and its /rss began serving a Cloudflare
        beacon <script> after </rss> on 2026-08-17, which made a perfectly
        good channel a counted error on every run."""
        good = rss(("Mill lays off 400 workers", "https://example.org/a",
                    "400 redundancies confirmed."))
        items, is_feed = nf._parse_items(
            good + '<script src="https://cdn.example/beacon.js"></script>')
        self.assertTrue(is_feed)
        self.assertEqual(len(items), 1)

    def test_an_html_page_at_a_feed_path_is_still_an_error(self):
        """The trailing-junk trim must not soften the changed-scheme guard."""
        items, is_feed = nf._parse_items("<!doctype html><html><body>x</body></html>")
        self.assertFalse(is_feed)
        self.assertEqual(items, [])

    def test_an_english_feed_does_not_widen_into_other_vocabularies(self):
        """The reverse must NOT hold: widening every feed to every language
        buys noise, and the per-language sets are precision-tuned."""
        self.assertEqual(nf.relevance("en", "Fabrika otpusta 200 radnika", "")[0],
                         False)


class AggregatorGuardTests(unittest.TestCase):
    def test_a_tally_product_never_becomes_a_raw_dict(self):
        feed = nf.by_key("dawn_business_pk")
        item = {"title": "Layoff tracker: every Pakistani cut in 2026",
                "link": "https://example.test/layoff-tracker",
                "description": "layoffs list", "published": "", "content": ""}
        self.assertIsNone(nf.build_raw(feed, item))

    def test_a_roundup_on_an_ordinary_path_is_refused(self):
        feed = nf.by_key("larepublica_co")
        item = {"title": "Every layoff announced in Colombia this year",
                "link": "https://www.larepublica.co/an-ordinary-slug/",
                "description": "despidos", "published": "", "content": ""}
        self.assertIsNone(nf.build_raw(feed, item))


class RawDictContractTests(unittest.TestCase):
    def test_each_language_fixture_survives_discovery_with_its_headcount(self):
        for lang, (key, title, link, desc) in LANG_FIXTURES.items():
            with self.subTest(lang=lang):
                def fetch(url, timeout, t=title, l=link, d=desc):
                    return 200, rss((t, l, d))
                with patch.dict(os.environ, {"NATIONAL_FEEDS": key}, clear=False):
                    rows, stats = nf.pull_national_feeds(fetch=fetch)
                self.assertEqual(len(rows), 1,
                                 f"{lang}: fixture did not survive discovery")
                self.assertIn(EXPECTED_COUNT[lang], rows[0]["raw_text"],
                              "the headcount did not reach raw_text")
                self.assertEqual(stats[key]["kept"], 1)

    def test_the_dict_shape_matches_the_shared_news_contract(self):
        _key, title, link, desc = LANG_FIXTURES["en"]
        raw = nf.build_raw(nf.by_key("dawn_business_pk"), {
            "title": title, "link": link, "description": desc,
            "published": "Fri, 14 Aug 2026 09:00:00 GMT", "content": ""})
        for k in ("source_type", "source_name", "verification_level", "raw_text",
                  "source_url", "company_name", "ticker", "filing_date"):
            self.assertIn(k, raw)
        self.assertEqual(raw["source_type"], "news")
        self.assertEqual(raw["verification_level"], "bronze")
        self.assertEqual(raw["filing_date"], "2026-08-14")
        self.assertIsNone(raw["company_name"])

    def test_no_country_is_ever_pre_assigned(self):
        """A national feed's job is discovery only. The extractor decides the
        country from the article, so a Ghanaian paper covering a Nigerian
        closure still lands as Nigeria."""
        _key, title, link, desc = LANG_FIXTURES["es"]
        raw = nf.build_raw(nf.by_key("gestion_pe"), {
            "title": title, "link": link, "description": desc,
            "published": "", "content": ""})
        self.assertNotIn("country", raw)

    def test_full_article_content_is_carried_into_raw_text_bounded(self):
        """Post-Courier ships whole articles inside the feed."""
        long_body = "The company confirmed 150 redundancies in Port Moresby. " * 200
        raw = nf.build_raw(nf.by_key("post_courier_pg"), {
            "title": "Cannery lays off 150 workers",
            "link": "https://www.postcourier.com.pg/x/", "description": "",
            "published": "", "content": long_body})
        self.assertIn("150 redundancies", raw["raw_text"])
        self.assertLessEqual(len(raw["raw_text"]), nf.MAX_RAW_TEXT + 200)

    def test_raw_text_names_the_outlet(self):
        _key, title, link, desc = LANG_FIXTURES["ru"]
        raw = nf.build_raw(nf.by_key("kursiv_kz"), {
            "title": title, "link": link, "description": desc,
            "published": "", "content": ""})
        self.assertIn("Kursiv", raw["raw_text"])


class CostBoundTests(unittest.TestCase):
    def test_a_feed_cannot_exceed_its_per_run_candidate_cap(self):
        many = [(f"Fabrika otpusta {i} radnika",
                 f"https://biznis.rs/a{i}/", "kolektivno otpustanje")
                for i in range(1, 60)]

        def fetch(url, timeout):
            return 200, rss(*many)

        with patch.dict(os.environ, {"NATIONAL_FEEDS": "biznis_rs"}, clear=False):
            rows, _stats = nf.pull_national_feeds(fetch=fetch)
        self.assertLessEqual(len(rows), nf.MAX_PER_FEED)

    def test_the_armed_worst_case_stays_inside_the_committed_ceiling(self):
        """The arming decision is arithmetic, not a vibe: if a later change
        adds feeds or raises the cap past $4/month, this fails and the owner
        gets asked again."""
        worst = len(nf.FEEDS) * nf.MAX_PER_FEED * 2 * 30 * 0.000315
        self.assertLessEqual(round(worst, 2), 4.00,
                             f"armed worst case is ${worst:.2f}/month")


if __name__ == "__main__":
    unittest.main()
