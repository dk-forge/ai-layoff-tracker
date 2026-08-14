"""Guards for the dormant local-language news collector.

The load-bearing tests here are the FIXTURE tests: a real-shaped article, in the
market's own language, in the market's own edition, must survive discovery and
build a raw dict that the extractor can read. A test that only asserts a config
key exists would prove nothing -- it would pass against a table full of
misspelled ceids and untranslated phrases.

The aggregator test is the other load-bearing one: it fails if a layoff-tracker
product or a compiled exit list can ever enter the feed path.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The politeness gap between live RSS calls is read at import time. These tests
# never touch the network (every fetch is injected), so the gap is pure latency
# here: without this the suite spends over two minutes asleep.
os.environ.setdefault("LOCAL_NEWS_GAP_SECONDS", "0")

from sources import local_news as ln          # noqa: E402
from sources import local_news_markets as mk  # noqa: E402


def rss(*items):
    """A minimal but real RSS 2.0 body in the shape Google News returns."""
    body = []
    for title, link, source, desc in items:
        body.append(
            "<item>"
            f"<title>{title}</title>"
            f"<link>{link}</link>"
            f"<description>{desc}</description>"
            "<pubDate>Wed, 13 Aug 2026 09:00:00 GMT</pubDate>"
            f"<source url='https://example.test'>{source}</source>"
            "</item>")
    return ("<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
            + "".join(body) + "</channel></rss>")


# One real-shaped article per language, in the market's own words. Each carries
# an employer and a headcount, which is what makes it a storable candidate.
FIXTURES = {
    "Switzerland": (
        "Chopard streicht 25 Stellen am Standort Genf",
        "https://www.bilanz.ch/unternehmen/chopard-stellenabbau",
        "Bilanz",
        "Der Uhrenhersteller baut 25 Stellen ab."),
    "Russia": (
        "Компания «Вымпелком» объявила о сокращении штата на 400 сотрудников",
        "https://www.kommersant.ru/doc/123456",
        "Коммерсант",
        "Сокращение персонала затронет региональные офисы."),
    "Kenya": (
        "Nation Media Group to cut 120 jobs in Nairobi restructuring",
        "https://www.businessdailyafrica.com/bd/corporate/nmg-job-cuts",
        "Business Daily",
        "The publisher said the retrenchment affects 120 staff."),
    "Nigeria": (
        "GTBank sacks workers as Lagos lender lays off 300 staff",
        "https://businessday.ng/companies/article/gtbank-job-cuts",
        "BusinessDay",
        "The bank disengaged 300 staff across its Lagos branches."),
    "Chile": (
        "HIF Global ejecuta despidos en Punta Arenas: 90 trabajadores desvinculados",
        "https://www.df.cl/empresas/industria/hif-despidos",
        "Diario Financiero",
        "La empresa confirmo la desvinculacion de 90 trabajadores."),
    "Turkey": (
        "Ford Otosan Kocaeli fabrikasinda 500 iscinin isten cikarilmasi",
        "https://www.dunya.com/sirketler/ford-otosan-isten-cikarma",
        "Dünya",
        "Toplu isten cikarma 500 calisani kapsiyor."),
    "Egypt": (
        "شركة مصرية تعلن تسريح 200 موظف في القاهرة",
        "https://www.almasryalyoum.com/news/details/123456",
        "المصري اليوم",
        "الشركة اعلنت الاستغناء عن 200 موظف."),
    "Ukraine": (
        "Нова Пошта оголосила про скорочення штату на 250 працівників у Києві",
        "https://www.epravda.com.ua/news/2026/08/13/123456/",
        "Економічна правда",
        "Скорочення персоналу торкнеться 250 працівників."),
    "Colombia": (
        "Avianca anuncia despidos: 400 trabajadores desvinculados en Bogotá",
        "https://www.larepublica.co/empresas/avianca-despidos",
        "La República",
        "La aerolinea confirmo el recorte de personal de 400 empleados."),
    "Serbia": (
        "Fabrika u Kragujevcu otpušta 300 radnika, višak zaposlenih potvrđen",
        "https://www.blic.rs/biznis/fabrika-otpustanje",
        "Blic",
        "Otpuštanje radnika obuhvata 300 zaposlenih."),
    "Angola": (
        "Empresa angolana avanca com despedimentos de 150 trabalhadores em Luanda",
        "https://www.expansao.co.ao/artigo/despedimentos",
        "Expansão",
        "A reestruturacao abrange 150 postos de trabalho."),
    "Albania": (
        "Fabrika fason në Tiranë njofton largime nga puna për 200 punëtorë",
        "https://www.monitor.al/fabrika-largime",
        "Monitor.al",
        "Shkurtime vendesh pune per 200 punonjes."),
}


class MarketTableTests(unittest.TestCase):
    def test_country_names_are_the_names_the_server_will_store(self):
        """A market name must survive alt_normalize_country() unchanged.

        That normalizer returns unknown SINGLE countries as-is but collapses
        anything containing a comma, slash, ampersand or the word "and" into
        "Multiple countries". A market named "Bosnia and Herzegovina" would
        therefore never be filterable under its own name.
        """
        for m in mk.MARKETS:
            with self.subTest(country=m.country):
                self.assertNotIn(",", m.country)
                self.assertNotIn("/", m.country)
                self.assertNotIn("&", m.country)
                self.assertNotRegex(m.country.lower(), r"\band\b")

    def test_every_market_has_editions_queries_anchors_and_publishers(self):
        for m in mk.MARKETS:
            with self.subTest(country=m.country):
                self.assertTrue(m.editions, "no edition to ask")
                self.assertTrue(all(e.queries for e in m.editions))
                self.assertTrue(m.anchors, "no free country filter -> unbounded cost")
                self.assertTrue(m.publishers, "no publisher rescue -> recall loss")
                self.assertTrue(m.note.strip())

    def test_ceid_agrees_with_the_edition_it_claims_to_be(self):
        """A typo'd ceid silently returns a different country's news."""
        for m in mk.MARKETS:
            for e in m.editions:
                with self.subTest(country=m.country, lang=e.lang):
                    self.assertEqual(e.ceid.split(":")[0], e.gl)
                    self.assertTrue(e.ceid.split(":")[1])

    def test_individual_dismissal_vocabulary_stays_out_of_russian(self):
        """Bare "увольнения" returns employment-law rulings, not layoff events.

        Measured 2026-08-13: the top three results for it were a reprimand case
        and a supreme-court ruling on dismissal procedure.
        """
        for country in ("Russia", "Kazakhstan", "Ukraine"):
            for e in mk.BY_COUNTRY[country].editions:
                for q in e.queries:
                    with self.subTest(country=country, lang=e.lang):
                        self.assertNotIn('"увольнения"', q)

    def test_noisy_homographs_are_paired_with_a_workforce_word(self):
        """A bare Nigerian "sack" query returned child-kidnapping stories."""
        for e in mk.BY_COUNTRY["Nigeria"].editions:
            for q in e.queries:
                if "sack" in q:
                    self.assertTrue(
                        any(w in q for w in ("workers", "staff", "employees")),
                        f"bare sack query is a precision trap: {q}")


class AggregatorExclusionTests(unittest.TestCase):
    """A layoff tally is never a source. This test is the enforcement."""

    def test_tracker_and_exit_list_urls_are_refused(self):
        for url in (
            "https://example.test/tech-layoff-tracker",
            "https://example.test/layoff_tracking/2026",
            "https://example.test/tracking-layoffs-2026",
            "https://example.test/layoffs-list",
            "https://example.test/layoffs/database",
            "https://example.test/job-cuts-tracker",
            "https://example.test/whos-hiring-and-firing",
            "https://som.yale.edu/story/2022/companies-leaving-russia",
            "https://example.test/companies-exiting-russia",
            "https://example.test/running-list-of-layoffs",
        ):
            with self.subTest(url=url):
                self.assertTrue(ln.is_aggregator(url), f"admitted an aggregator: {url}")

    def test_ordinary_reporting_from_the_same_publishers_is_allowed(self):
        """The exclusion is on the tally PRODUCT, not the outlet."""
        for url in (
            "https://techcabal.com/2026/08/13/company-x-cuts-jobs/",
            "https://businessdailyafrica.com/bd/corporate/nmg-job-cuts",
            "https://www.df.cl/empresas/industria/hif-despidos",
        ):
            with self.subTest(url=url):
                self.assertFalse(ln.is_aggregator(url))

    def test_no_market_publisher_token_is_an_aggregator(self):
        for m in mk.MARKETS:
            for token in m.publishers:
                with self.subTest(country=m.country, publisher=token):
                    self.assertFalse(
                        ln.is_aggregator(f"https://{token.replace(' ', '')}.test/x", token),
                        f"{m.country} lists an aggregator as a publisher: {token}")

    def test_roundup_articles_on_ordinary_paths_are_refused(self):
        """The leak a URL rule cannot see.

        Outlets that run a layoff tally also republish it onto their normal
        /YYYY/MM/DD/slug/ article path, where it arrives in the ordinary feed
        looking exactly like reporting. Storing one would import someone else's
        count as if it were our own observation.
        """
        for title in (
            "Inside Africa's tech layoffs",
            "12 startups and tech companies that cut workforce in 2025",
            "Tech layoffs tracker: who is cutting now",
            "Tracking the layoffs of 2026",
            "Every layoff announced this year",
            "A list of job cuts across the sector",
            "Layoffs in H1 2026: what the data says",
        ):
            with self.subTest(title=title):
                self.assertTrue(
                    ln.is_aggregator("https://example.test/2026/06/29/a-story/",
                                     "Example", title),
                    f"roundup admitted as reporting: {title}")

    def test_single_employer_stories_are_never_mistaken_for_roundups(self):
        """The exclusion must not eat the rows we actually want."""
        for title in (
            "GTBank sacks workers as Lagos lender lays off 300 staff",
            "Chopard streicht 25 Stellen am Standort Genf",
            "Oracle plans more layoffs before its next fiscal quarter",
            "HIF Global ejecuta despidos en Punta Arenas",
            "Nation Media Group to cut 120 jobs in Nairobi restructuring",
            "Zap Africa layoffs hit 40 employees",
        ):
            with self.subTest(title=title):
                self.assertFalse(
                    ln.is_aggregator("https://example.test/2026/06/29/a-story/",
                                     "Example", title),
                    f"real single-employer story refused: {title}")

    def test_a_research_subdomain_is_excluded_while_its_newsroom_is_not(self):
        self.assertTrue(ln.is_aggregator(
            "https://insights.techcabal.com/inside-africas-tech-layoffs/"))
        self.assertFalse(ln.is_aggregator(
            "https://techcabal.com/2026/02/28/zap-africa-layoffs/"))

    def test_an_aggregator_item_never_becomes_a_raw_dict(self):
        item = {"title": "Layoff tracker: every 2026 cut",
                "link": "https://example.test/layoff-tracker",
                "description": "", "published": "", "source": "Example"}
        self.assertIsNone(ln.build_raw("Kenya", item))

    def test_unparseable_url_is_refused_rather_than_admitted(self):
        self.assertTrue(ln.is_aggregator("http://[::bad::]/x"))


class DormancyTests(unittest.TestCase):
    def test_unset_arming_variable_makes_no_request_and_returns_nothing(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return 200, rss()

        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": ""}, clear=False):
            rows, stats = ln.pull_local_news(fetch=fetch)
        self.assertEqual(rows, [])
        self.assertEqual(calls, [], "a DORMANT collector made a network request")

    def test_arming_one_country_arms_only_that_country(self):
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "Chile"}, clear=False):
            self.assertEqual(ln.armed_countries(), ("Chile",))

    def test_arming_accepts_a_tier_and_all(self):
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "all"}, clear=False):
            self.assertEqual(ln.armed_countries(), mk.COUNTRIES)
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "tier2"}, clear=False):
            armed = ln.armed_countries()
        self.assertTrue(armed)
        self.assertTrue(all(mk.BY_COUNTRY[c].tier == 2 for c in armed))

    def test_unknown_country_is_ignored_not_guessed(self):
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "Atlantis,Chile"}, clear=False):
            self.assertEqual(ln.armed_countries(), ("Chile",))


class RelevanceFilterTests(unittest.TestCase):
    def test_a_foreign_story_in_a_local_edition_is_dropped_before_it_costs_anything(self):
        """hl=de&gl=CH returns plenty of Germany. Those must not reach the LLM."""
        keep, why = ln.relevance(
            "Switzerland",
            "SPD unter Spardruck: Stellenabbau und Streichung der 37-Stunden-Woche",
            "", "BILD")
        self.assertFalse(keep, f"a German story passed a Swiss filter ({why})")

    def test_a_local_story_with_no_locality_token_is_rescued_by_its_publisher(self):
        """The Chopard case: a real Swiss event whose headline says nothing Swiss."""
        keep, why = ln.relevance(
            "Switzerland", "Chopard: Warum 25 Stellen gestrichen werden mussten",
            "", "Bilanz")
        self.assertTrue(keep, "publisher rescue failed; real Swiss events would be lost")
        self.assertTrue(why.startswith("publisher:"))

    def test_a_locality_token_alone_is_enough(self):
        keep, why = ln.relevance("Chile", "Empresa despide en Antofagasta", "", "Unknown Outlet")
        self.assertTrue(keep)
        self.assertTrue(why.startswith("anchor:"))

    def test_the_filter_never_decides_the_stored_country(self):
        """It gates cost only; the raw dict asserts no country of its own."""
        raw = ln.build_raw("Switzerland", {
            "title": "Chopard streicht 25 Stellen", "link": "https://bilanz.ch/a",
            "description": "", "published": "", "source": "Bilanz"})
        self.assertIsNotNone(raw)
        self.assertNotIn("country", raw)
        self.assertIsNone(raw["company_name"])


class RawDictContractTests(unittest.TestCase):
    def test_raw_text_is_always_set(self):
        """The extractor reads ONLY raw_text and returns None when it is empty.

        This is the bug that made a whole source silently post zero rows.
        """
        for country, fx in FIXTURES.items():
            with self.subTest(country=country):
                raw = ln.build_raw(country, {
                    "title": fx[0], "link": fx[1], "description": fx[3],
                    "published": "Wed, 13 Aug 2026 09:00:00 GMT", "source": fx[2]})
                self.assertIsNotNone(raw, "fixture was filtered out")
                self.assertTrue(raw["raw_text"].strip())

    def test_the_dict_shape_matches_the_shared_news_contract(self):
        raw = ln.build_raw("Chile", {
            "title": FIXTURES["Chile"][0], "link": FIXTURES["Chile"][1],
            "description": "", "published": "Wed, 13 Aug 2026 09:00:00 GMT",
            "source": FIXTURES["Chile"][2]})
        for key in ("source_type", "source_name", "verification_level", "raw_text",
                    "source_url", "company_name", "ticker", "filing_date"):
            self.assertIn(key, raw)
        self.assertEqual(raw["source_type"], "news")
        self.assertEqual(raw["verification_level"], "bronze")
        self.assertEqual(raw["filing_date"], "2026-08-13")

    def test_a_recognised_outlet_contributes_its_publication_country(self):
        """Why: "... - Bilanz" does not tell a model that Bilanz is Swiss."""
        raw = ln.build_raw("Switzerland", {
            "title": "Chopard streicht 25 Stellen", "link": "https://bilanz.ch/a",
            "description": "", "published": "", "source": "Bilanz"})
        self.assertIn("Swiss publication", raw["raw_text"])

    def test_an_unrecognised_outlet_gets_no_invented_country_note(self):
        raw = ln.build_raw("Chile", {
            "title": "Despidos masivos en Antofagasta", "link": "https://x.test/a",
            "description": "", "published": "", "source": "Some Blog"})
        self.assertIsNotNone(raw)
        self.assertNotIn("Chilean publication", raw["raw_text"])


class PerLanguageDiscoveryTests(unittest.TestCase):
    """The load-bearing test: a real article, in each language, in each market's
    shape, is DISCOVERED by that market's own queries and survives to a raw dict
    carrying the headcount the extractor needs."""

    def _discover(self, country):
        fx = FIXTURES[country]
        served = []

        def fetch(url):
            served.append(url)
            return 200, rss((fx[0], fx[1], fx[2], fx[3]))

        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": country}, clear=False):
            rows, stats = ln.pull_local_news(fetch=fetch)
        return rows, stats[country], served

    def test_each_language_fixture_is_discovered_and_survives_the_filter(self):
        for country in FIXTURES:
            with self.subTest(country=country):
                rows, st, served = self._discover(country)
                self.assertTrue(served, "no edition was queried")
                self.assertEqual(len(rows), 1,
                                 f"{country}: fixture did not survive discovery")
                self.assertEqual(st["kept"], 1)
                self.assertEqual(st["dropped"], 0)

    def test_the_headcount_survives_into_raw_text(self):
        """If the number is lost before the extractor, the event is unusable."""
        expected = {"Switzerland": "25", "Russia": "400", "Kenya": "120",
                    "Nigeria": "300", "Chile": "90", "Turkey": "500",
                    "Egypt": "200", "Ukraine": "250", "Colombia": "400",
                    "Serbia": "300", "Angola": "150", "Albania": "200"}
        for country, number in expected.items():
            with self.subTest(country=country):
                rows, _st, _served = self._discover(country)
                self.assertIn(number, rows[0]["raw_text"])

    def test_each_market_is_queried_in_its_own_edition(self):
        for country in FIXTURES:
            with self.subTest(country=country):
                _rows, _st, served = self._discover(country)
                gls = {e.gl for e in mk.BY_COUNTRY[country].editions}
                for url in served:
                    self.assertTrue(any(f"gl={gl}" in url for gl in gls),
                                    f"{country} queried a foreign edition: {url}")

    def test_a_foreign_language_article_in_the_same_edition_is_not_kept(self):
        """Discovery must not become "everything the edition returned"."""
        def fetch(_url):
            return 200, rss(
                ("Zillow Stock Slides After Workforce Reduction Announcement",
                 "https://example.test/zillow", "TIKR", ""))
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "Switzerland"}, clear=False):
            rows, stats = ln.pull_local_news(fetch=fetch)
        self.assertEqual(rows, [], "a US story was admitted under a Swiss budget")
        self.assertGreater(stats["Switzerland"]["dropped"], 0)


class CostBoundTests(unittest.TestCase):
    def test_a_country_cannot_exceed_its_per_run_candidate_cap(self):
        """The cap is what makes the price predictable before arming."""
        many = [(f"Despidos masivos en Santiago numero {i}",
                 f"https://df.cl/a{i}", "Diario Financiero", "") for i in range(60)]

        def fetch(_url):
            return 200, rss(*many)

        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "Chile"}, clear=False):
            rows, _stats = ln.pull_local_news(fetch=fetch)
        self.assertLessEqual(len(rows), ln.MAX_PER_COUNTRY)

    def test_an_http_error_degrades_loudly_instead_of_looking_quiet(self):
        with patch.dict(os.environ, {"LOCAL_NEWS_COUNTRIES": "Chile"}, clear=False):
            rows, stats = ln.pull_local_news(fetch=lambda _u: (503, ""))
        self.assertEqual(rows, [])
        self.assertGreater(stats["Chile"]["errors"], 0)
        self.assertTrue(ln.pull_local_news.last_error)


if __name__ == "__main__":
    unittest.main()
