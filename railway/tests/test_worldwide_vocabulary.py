"""The news net asks each language in its own words, on the paths that run.

Worldwide-coverage audit, 2026-09-02. The measurement behind this file:

  * Of 1,141 news rows on the live tracker, 53 (4.6%) cited a non-English
    outlet, and 474 (41.5%) were United States rows. Every non-US country
    with more than a handful of NEWS rows is anglophone (UK 86, India 78,
    Australia 50, Canada 42, Ireland 16, Singapore 11).
  * `sources/google_news.py` put five ENGLISH queries to 45 editions, 34 of
    them non-English, although `sources/local_news.py` had measured on
    2026-08-13 that an English query on a non-English edition returns the
    worldwide English feed.
  * `sources/gdelt.py` reached GDELT only through the BigQuery mirror on every
    measured run since 2026-08-19 (the public API abandoned the broad window
    on 100% of them), and the mirror's title regex held only the English
    vocabulary against original-language titles.
  * The daily collector's deadline skipped every rotating sweep on the runs of
    2026-08-30 to 2026-09-01 (queries=2) and recorded none of them, so the
    native-language sweeps were not deferred; they were gone.

Each test here fails on the specific regression: an edition asked in the
wrong language, a mirror regex without the native phrases, a vocabulary that
drifts from gdelt's precision-selected ring, or a clock-skipped sweep that
leaves no ledger slot behind.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.dirname(HERE)
sys.path.insert(0, RAILWAY)

from sources import native_layoff_terms as native  # noqa: E402
from sources import google_news  # noqa: E402


def _english_words(text):
    low = text.lower()
    return [w for w in ("layoffs", "job cuts", "lays off", "workforce reduction",
                        "redundancies", "reduction in force") if w in low]


class EveryEditionIsAskedInItsOwnLanguage(unittest.TestCase):

    def test_every_non_english_edition_has_a_native_vocabulary(self):
        """An edition with no vocabulary is skipped, so a missing language is
        silent coverage loss. Name every one."""
        missing = []
        for code, hl, _gl, _ceid in google_news.GOOGLE_NEWS_LOCALES:
            if native.is_english_hl(hl):
                continue
            if not native.google_news_queries(hl):
                missing.append(f"{code} ({hl})")
        self.assertEqual(missing, [],
                         "non-English editions with no native query set (they would be "
                         "skipped every run): " + ", ".join(missing))

    def test_non_english_editions_get_no_english_query(self):
        english = list(google_news.DISCOVERY_QUERIES)
        for loc in google_news.GOOGLE_NEWS_LOCALES:
            qs = google_news.queries_for_edition(loc, english)
            with self.subTest(edition=loc[0]):
                if native.is_english_hl(loc[1]):
                    self.assertEqual(qs, english)
                else:
                    self.assertTrue(qs, f"{loc[0]} would be skipped")
                    for q in qs:
                        self.assertNotIn(q, english,
                                         f"{loc[0]} ({loc[1]}) is asked in English")
                        self.assertEqual(_english_words(q), [],
                                         f"{loc[0]}: English layoff word inside a native query")

    def test_unknown_language_is_skipped_not_asked_in_english(self):
        self.assertEqual(google_news.queries_for_edition(("XX", "xx", "XX", "XX:xx"),
                                                         ["layoffs"]), [])

    def test_the_planned_jobs_carry_the_native_queries(self):
        """End to end through pull_google_news: the requests it builds for a
        German edition are German, and the US edition keeps English."""
        urls = []

        class _Resp:
            status_code = 200
            text = "<rss><channel></channel></rss>"

        def fake_get(url, headers=None, timeout=None):
            urls.append(url)
            return _Resp()

        fake_requests = type("R", (), {"get": staticmethod(fake_get)})
        with patch.object(google_news, "_locales_for_now",
                          lambda: [google_news.GOOGLE_NEWS_LOCALES[0], ("DE", "de", "DE", "DE:de")]), \
             patch.object(google_news, "requests", fake_requests, create=True), \
             patch.object(google_news.time, "sleep", lambda s: None):
            google_news.pull_google_news()
        de = [u for u in urls if "gl=DE" in u]
        us = [u for u in urls if "gl=US" in u]
        self.assertTrue(de and us)
        import urllib.parse
        de_qs = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["q"][0] for u in de]
        self.assertTrue(any("Stellenabbau" in q for q in de_qs),
                        f"German edition asked without German: {de_qs}")
        for q in de_qs:
            self.assertEqual(_english_words(q), [], q)
        for u in us:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)["q"][0]
            self.assertIn(q, google_news.DISCOVERY_QUERIES)


class TheVocabularyIsOneTable(unittest.TestCase):

    def test_every_gdelt_native_term_is_in_the_shared_table(self):
        """gdelt.NATIVE_TERMS stays a literal (the ring test reads it by AST);
        this pins that the shared table cannot drift away from it."""
        import ast
        with open(os.path.join(RAILWAY, "sources", "gdelt.py"), encoding="utf-8") as fh:
            src = fh.read()
        terms = None
        for node in ast.parse(src).body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "NATIVE_TERMS" for t in node.targets):
                terms = ast.literal_eval(node.value)
        self.assertTrue(terms)
        shared = set(native.mirror_title_terms())
        missing = [t for t in terms if t.strip('"') not in shared]
        self.assertEqual(missing, [], f"gdelt NATIVE_TERMS absent from the shared table: {missing}")

    def test_the_mirror_regex_carries_the_native_phrases(self):
        """_collect_mirror hands the walk the English terms PLUS the native
        phrases. Drop the native half and a Handelsblatt 'Stellenabbau' title
        only matches if GDELT's theme tagger also filed it under UNEMPLOYMENT."""
        from sources import gdelt
        seen = {}

        def fake_walk(start, end, terms, **kw):
            seen["terms"] = list(terms)
            return [], True

        with patch.object(gdelt.gdelt_bq, "query_window_walk", fake_walk):
            gdelt._collect_mirror(datetime(2026, 9, 1, tzinfo=timezone.utc),
                                  datetime(2026, 9, 2, tzinfo=timezone.utc))
        self.assertIn("layoffs", seen["terms"])
        for phrase in ("Stellenabbau", "licenciement collectif", "despido colectivo",
                       "esuberi", "人員削減", "정리해고"):
            self.assertIn(phrase, seen["terms"], f"mirror regex lacks {phrase}")
        # And the regex the mirror builds from them matches a native title.
        import re
        from sources import gdelt_bq
        rx = re.compile(gdelt_bq.title_pattern(seen["terms"]))
        self.assertTrue(rx.search("bosch kündigt stellenabbau an"))
        self.assertTrue(rx.search("nissan、人員削減を発表"))
        self.assertFalse(rx.search("quarterly results beat estimates"))

    def test_each_language_yields_at_most_two_queries_and_no_empty_group(self):
        for lang in native.languages():
            qs = native.google_news_queries(f"{lang}-XX")
            self.assertTrue(1 <= len(qs) <= 2, (lang, qs))
            for q in qs:
                self.assertTrue(q.startswith('"') and q.endswith('"'), q)


class ClockSkippedSweepsAreQueuedNotLost(unittest.TestCase):
    """The deadline branch used to `break` and log 'ledger retries them next
    run' while writing nothing. A slot the clock skips is now QUEUED, exactly
    like a slot the outage breaker skips, so a later run re-issues it."""

    def setUp(self):
        from sources import gdelt
        import gdelt_reach
        gdelt_reach.reset()
        gdelt._LAST_RUN_INCOMPLETE = False
        self.gdelt = gdelt
        self._fetch = patch.object(gdelt, "_fetch_trusted", lambda arts, max_candidates=None: list(arts))
        self._fetch.start()
        self.addCleanup(self._fetch.stop)
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"slots": {}}')
        tmp.close()
        self.ledger_path = tmp.name
        self.addCleanup(lambda: os.path.exists(self.ledger_path) and os.unlink(self.ledger_path))
        # No remote ledger round-trip in a unit test.
        for name in ("_sync_ledger_mid_run", "_push_slots_remote"):
            p = patch.object(gdelt, name, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)
        self._load = patch.object(gdelt, "_load_work_ledger",
                                  lambda path=None, remote=True: {"slots": {}})
        self._load.start()
        self.addCleanup(self._load.stop)

    def test_sweeps_skipped_by_the_deadline_land_in_the_ledger_as_queued(self):
        gdelt = self.gdelt
        now = [0.0]
        saved = {}

        def fake_query(query, start, end, mr, label="broad"):
            if label == "broad":
                now[0] = 999.0   # the broad slot alone ate the budget
            return [], False, None

        def fake_save(ledger, path=None, remote=True):
            saved["ledger"] = ledger

        with patch.object(gdelt, "_query_window", fake_query), \
             patch.object(gdelt, "_save_work_ledger", fake_save), \
             patch.object(gdelt, "_planned_sweeps",
                          lambda: [("native", '"Stellenabbau"'), ("euro", '"esuberi"'),
                                   ("theme", "(theme:X)")]), \
             patch.object(gdelt.time, "monotonic", lambda: now[0]):
            gdelt.pull_gdelt_between(
                datetime(2026, 9, 1, tzinfo=timezone.utc),
                datetime(2026, 9, 2, tzinfo=timezone.utc),
                max_records=5, ledger_path=self.ledger_path, deadline=500.0)

        slots = saved["ledger"]["slots"]
        queued = sorted(s["family"] for s in slots.values() if s.get("status") == "queued")
        self.assertEqual(queued, ["euro", "native", "theme"],
                         "a sweep the clock skipped left no ledger slot behind")
        for s in slots.values():
            if s.get("status") == "queued":
                self.assertEqual(s.get("attempts"), 0, "queueing must not spend an attempt")
        self.assertEqual(gdelt.last_run_status(), "degraded")


if __name__ == "__main__":
    unittest.main()
