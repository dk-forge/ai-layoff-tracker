"""THE CITY SWEEP READS NAMES AND PUBLISHES COUNTS. PROVE IT BY POISONING A RUN.

`city_recall_sweep.py` is the third recall probe (after the GDELT learning loop
and the curated probe) and it inherits their contract: judgement is IMPORTED
from `tracker_diff`, no page is ever fetched, no model is called, stdout is
counts by shape, and every headline, employer and outlet goes to ONE gitignored
file. Each test here fails on a specific way of breaking that.

  * a poisoned run: invented outlets, employers, domains and figures go in;
    none of them may reach stdout or the fact dict, and all of them MUST reach
    the named file (a probe that did nothing would pass the leak half).
  * no request is built from an item's link or outlet host: only the news
    index and our own /query are ever called.
  * the named file's comment lines carry no dotted token, because
    `curated_probe.parse_worklist` suppresses every domain a `#` line names,
    and an outlet quoted in a diagnosis comment would otherwise exempt itself
    from ever being proposed.
  * the table is 120 cities, every one reaches an edition, and a non-English
    edition is asked in its own vocabulary with the city in its own script.
  * a host that stops answering trips the breaker: the run STOPS asking, every
    later verdict is UNKNOWN rather than a miss, and the summary says so. This
    is the defect the first live run met (2026-09-06, a site-wide HTTP 409 bot
    challenge on our own /blog): without it the sweep walks 120 cities into a
    wall and reports the silence as if it had looked.
  * the native headcount pattern reads the European thousands separator and
    the CJK 万 multiplier, and is COUNTED separately from the English-grade read.

Names in the fixture are fictional on purpose, for the reason
`test_curated_probe_leak` records.
"""
import io
import os
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from email.utils import format_datetime
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
sys.path.insert(0, RAILWAY)

import city_recall_sweep as crs  # noqa: E402
from curated_probe import parse_worklist  # noqa: E402
from sources.native_layoff_terms import PHRASES_BY_LANG, language_of_hl  # noqa: E402

POISON = ["Vantablack Tribune", "vantablack-tribune.example", "Hollowmere Systems",
          "Marrowgate Post", "marrowgate-post.example", "Perrindale Foods",
          "878787", "4,242", "Quillfeather"]

_NOW = format_datetime(datetime.now(timezone.utc))


def _item(title, outlet, home, link="https://news.google.com/rss/articles/CBMiAU_yqL"):
    return {"title": title, "link": link, "description": "", "published": _NOW,
            "source": outlet, "source_home": home}


FAKE_INDEX = {
    "en": [
        _item("Hollowmere Systems to cut 4,242 jobs in Delhi - Vantablack Tribune",
              "Vantablack Tribune", "https://vantablack-tribune.example"),
        _item("Perrindale Foods lays off 878787 workers - Marrowgate Post",
              "Marrowgate Post", "https://marrowgate-post.example"),
        _item("Quillfeather Corp cuts 300 jobs after weak quarter - Reuters",
              "Reuters", "https://www.reuters.com"),
    ],
    "de": [
        _item("Stellenabbau bei Hollowmere: 1.200 Stellen in Berlin gestrichen - Marrowgate Post",
              "Marrowgate Post", "https://marrowgate-post.example"),
    ],
}


class _FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


def _fake_fetch(query, ed):
    lang = language_of_hl(ed[0])
    return list(FAKE_INDEX.get(lang, [])), ""


def _fake_get(url, params=None, headers=None, timeout=None):
    _fake_get.urls.append(url)
    if "/wp-json/layoffs/v1/query" in url:
        token = (params or {}).get("company", "")
        # We hold the 300-job Quillfeather cut; nothing else.
        rows = ([{"job_count": 300, "layoff_date": date.today().isoformat(),
                  "source_type": "news"}] if token == "Quillfeather" else [])
        return _FakeResponse(200, {"data": rows})
    raise AssertionError("unexpected request: " + url)


_fake_get.urls = []

CITIES = (("Delhi", "", "IN"), ("Berlin", "", "DE"))


class CitySweepLeak(unittest.TestCase):
    def _run(self):
        _fake_get.urls = []
        out = pathlib.Path(tempfile.mkdtemp()) / "city-recall-test.txt"
        buf = io.StringIO()
        with patch.object(crs.requests, "get", _fake_get), redirect_stdout(buf):
            facts, named = crs.run("https://example.invalid/blog", out,
                                   fetch=_fake_fetch, sleep=lambda s: None,
                                   cities=CITIES, today=date(2026, 9, 6))
        return facts, named, buf.getvalue(), out

    def test_a_poisoned_run_leaks_nothing_to_stdout_or_facts(self):
        facts, _named, stdout, _out = self._run()
        crs.assert_nameless(facts)
        for marker in POISON:
            self.assertNotIn(marker, stdout, marker)
            self.assertNotIn(marker, repr(facts), marker)
        # And the counts are real: three English items judged, one held.
        self.assertEqual(facts["judged"], 4)
        self.assertEqual(facts["held"], 1)
        self.assertEqual(facts["missed"], 3)
        self.assertEqual(facts["native_parsed"], 1)
        self.assertEqual(facts["miss_tiers"]["not_in_feed_set"], 3)

    def test_the_poison_reached_the_private_sink(self):
        _facts, named, _stdout, out = self._run()
        text = out.read_text(encoding="utf-8")
        for marker in ("Vantablack Tribune", "Hollowmere Systems", "Perrindale Foods",
                       "878787", "4,242"):
            self.assertIn(marker, text, marker)
        misses = [r for r in named if r["verdict"] == "missed"]
        self.assertEqual(len(misses), 3)

    def test_no_request_is_built_from_an_item_link_or_outlet(self):
        self._run()
        for url in _fake_get.urls:
            self.assertIn("/wp-json/layoffs/v1/query", url)
            for host in ("vantablack-tribune.example", "marrowgate-post.example",
                         "news.google.com"):
                self.assertNotIn(host, url)

    def test_named_file_comments_suppress_no_domain(self):
        """Pasting the WHOLE file into the curated worklist must not exempt
        any outlet: comment lines carry no dotted token."""
        _facts, _named, _stdout, out = self._run()
        _items, suppressed = parse_worklist(out.read_text(encoding="utf-8"))
        self.assertEqual(suppressed, set(), suppressed)

    def test_paste_ready_section_is_the_misses_with_their_origin(self):
        _facts, _named, _stdout, out = self._run()
        items, _suppressed = parse_worklist(out.read_text(encoding="utf-8"))
        self.assertEqual(len(items), 3)
        domains = {it["domain"] for it in items}
        self.assertEqual(domains, {"vantablack-tribune.example", "marrowgate-post.example"})

    def test_assert_nameless_refuses_free_text(self):
        with self.assertRaises(crs.LeakGuard):
            crs.assert_nameless({"by_country": {"IN": {"held": "Hollowmere"}}})
        with self.assertRaises(crs.LeakGuard):
            crs.assert_nameless({"outlet": 1})
        crs.assert_nameless({"by_country": {"IN": {"held": 1}}, "by_city": {"c001": {"items": 2}}})


class CityTable(unittest.TestCase):
    def test_120_cities_each_reaching_an_edition(self):
        self.assertEqual(len(crs.CITIES), 120)
        self.assertEqual(len({c[0] for c in crs.CITIES}), 120)
        for city in crs.CITIES:
            ed, _fallback = crs.edition_for(city[2])
            self.assertEqual(len(ed), 3, city)
            self.assertTrue(crs.queries_for_city(city), city)

    def test_non_english_edition_is_asked_in_its_own_words(self):
        qs = crs.queries_for_city(("Tokyo", "東京", "JP"))
        langs = {lang for _q, _ed, lang in qs}
        self.assertIn("ja", langs)
        native = [q for q, _ed, lang in qs if lang == "ja"][0]
        self.assertIn("東京", native)
        self.assertNotIn("Tokyo", native)
        for phrase in PHRASES_BY_LANG["ja"][:2]:
            self.assertIn(phrase, native)
        self.assertIn("when:", native)

    def test_english_edition_gets_one_english_query(self):
        qs = crs.queries_for_city(("Chicago", "", "US"))
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0][2], "en")
        self.assertIn('"Chicago"', qs[0][0])


class NativeHeadcount(unittest.TestCase):
    def test_european_separator_and_cjk_multiplier(self):
        self.assertEqual(crs.native_headline_jobs("Bosch streicht 1.200 Stellen"), 1200)
        self.assertEqual(crs.native_headline_jobs("Renault va supprimer 3 000 postes"), 3000)
        self.assertEqual(crs.native_headline_jobs("大众汽车拟裁员5万人"), 50000)
        self.assertEqual(crs.native_headline_jobs("현대차 500명 희망퇴직"), 500)

    def test_floor_and_percent_are_not_headcounts(self):
        self.assertIsNone(crs.native_headline_jobs("Bosch streicht 12 Stellen"))
        self.assertIsNone(crs.native_headline_jobs("Bosch streicht 10% der Stellen"))

    def test_employer_candidates_skip_city_and_vocabulary(self):
        toks = crs.employer_candidates("Stellenabbau bei Bosch: 1.200 Stellen in Berlin",
                                       {"Berlin"}, ["Stellenabbau", "Stellen"])
        self.assertEqual(toks[0], "Bosch")
        self.assertNotIn("Berlin", toks)
        self.assertLessEqual(len(toks), 2)


if __name__ == "__main__":
    unittest.main()


class HostRefusal(unittest.TestCase):
    """Our own host refusing is UNKNOWN, and a sweep must stop at it."""

    def _run_with(self, get):
        out = pathlib.Path(tempfile.mkdtemp()) / "city-recall-test.txt"
        buf = io.StringIO()
        with patch.object(crs.requests, "get", get), redirect_stdout(buf):
            facts, named = crs.run("https://example.invalid/blog", out,
                                   fetch=_fake_fetch, sleep=lambda s: None,
                                   cities=CITIES, today=date(2026, 9, 6))
        return facts, named, buf.getvalue()

    def test_a_409_wall_trips_the_breaker_and_stops_the_reads(self):
        calls = []

        def refusing_get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            return _FakeResponse(409, {})

        facts, named, stdout = self._run_with(refusing_get)
        self.assertTrue(facts["host_unreachable"])
        # It stopped: the breaker's limit bounds the reads, well under one per
        # candidate token across every city.
        self.assertLessEqual(len(calls), crs.HOST_FAIL_LIMIT)
        # And nothing became a miss on the strength of a wall.
        self.assertEqual(facts["missed"], 0)
        self.assertEqual(facts["held"], 0)
        self.assertEqual(facts["unknown"], facts["judged"])
        self.assertIsNone(facts["held_pct"])
        self.assertIn("UNKNOWN", stdout)
        crs.assert_nameless(facts)

    def test_a_healthy_host_does_not_trip_it(self):
        facts, _named, _stdout = self._run_with(_fake_get)
        self.assertFalse(facts["host_unreachable"])
        self.assertEqual(facts["held"], 1)

    def test_a_failed_read_is_not_cached_as_an_answer(self):
        """A None from a blip must not be remembered as 'we hold nothing'."""
        cache = {}
        breaker = crs.HostBreaker()

        def refusing_get(url, params=None, headers=None, timeout=None):
            return _FakeResponse(409, {})

        with patch.object(crs.requests, "get", refusing_get):
            crs.our_rows("Hollowmere", "https://example.invalid/blog",
                         cache=cache, breaker=breaker, sleep=lambda s: None)
        self.assertEqual(cache, {})
