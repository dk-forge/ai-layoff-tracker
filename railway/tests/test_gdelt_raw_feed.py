"""The published-files path (sources/gdelt_raw.py) and its place in the order.

The DOC query API has answered nothing since 2026-08-19 and the BigQuery
mirror lags its partition, so the broad GDELT window now reads GDELT's own
15-minute GKG files first. These tests are hermetic (the file fetch is
injected, no test touches the network) and pin:

  1. a window is enumerated by NAME (deterministic quarter-hour stamps, both
     feeds), never from the 127 MB master list;
  2. a GKG row becomes a candidate on the MIRROR's semantics exactly:
     UNEMPLOYMENT theme OR the one shared title regex, native phrases included,
     over an HTML-unescaped title;
  3. a 404 inside the publication lag is PENDING and the window is complete;
     an older 404 is a GAP, a transport failure is FAILED, a file the deadline
     skipped is SKIPPED, and each of those makes the window PARTIAL;
  4. the preference order is files -> mirror -> query API, the files are not
     asked for a window older than the horizon or when switched off, and the
     rows still leave through `_fetch_trusted` like every other path;
  5. the newest file stamp consumed is recorded, nameless, and printed in the
     health detail and read back by ops_status [2d], so a lag is visible.

Import note: this module never imports `cdp`, so run_tests.py files it under
the non-browser groups with the other GDELT tests.
"""
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gdelt_reach  # noqa: E402
from sources import gdelt, gdelt_bq, gdelt_raw  # noqa: E402


W_END = datetime(2026, 9, 3, 22, 0, 30, tzinfo=timezone.utc)
W_START = W_END - timedelta(hours=36)
TERMS = ("layoffs", "job cuts", "Stellenabbau", "人員削減")


def _gkg_row(stamp, domain, url, title, themes=""):
    """One 27-column GKG 2.1 line with only the columns the reader uses set."""
    cols = [""] * gdelt_raw.NCOLS
    cols[0] = f"{stamp}-0"
    cols[gdelt_raw.COL_DATE] = stamp
    cols[2] = "1"
    cols[gdelt_raw.COL_DOMAIN] = domain
    cols[gdelt_raw.COL_URL] = url
    cols[gdelt_raw.COL_V2THEMES] = themes
    cols[gdelt_raw.COL_EXTRAS] = f"<PAGE_TITLE>{title}</PAGE_TITLE>"
    return "\t".join(cols)


def _zip(lines, name="x.gkg.csv"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, "\n".join(lines) + "\n")
    return buf.getvalue()


def _stamp_of(url):
    return os.path.basename(url).split(".")[0]


def _feed_of(url):
    return "translation." if ".translation." in url else ""


class SlotEnumeration(unittest.TestCase):
    def test_a_36h_window_is_145_quarter_hour_stamps_and_290_files(self):
        stamps = gdelt_raw.slot_stamps(W_START, W_END)
        self.assertEqual(len(stamps), 145)
        self.assertEqual(stamps[0], "20260902100000")   # start floored to :00
        self.assertEqual(stamps[-1], "20260903220000")  # end floored, slot begun
        self.assertEqual(stamps[1], "20260902101500")
        self.assertEqual(len(gdelt_raw.FEEDS), 2)
        self.assertEqual(gdelt_raw.file_url("20260903220000", ""),
                         "https://data.gdeltproject.org/gdeltv2/20260903220000.gkg.csv.zip")
        self.assertEqual(gdelt_raw.file_url("20260903220000", "translation."),
                         "https://data.gdeltproject.org/gdeltv2/20260903220000.translation.gkg.csv.zip")

    def test_the_end_slot_that_has_not_begun_is_never_asked_for(self):
        end = datetime(2026, 9, 3, 22, 14, 59, tzinfo=timezone.utc)
        self.assertEqual(gdelt_raw.slot_stamps(end - timedelta(minutes=1), end)[-1],
                         "20260903220000")

    def test_no_master_list_is_read(self):
        asked = []

        def fetch(url):
            asked.append(url)
            raise gdelt_raw.NotPublished(url)

        with self.assertRaises(RuntimeError):
            gdelt_raw.read_window(W_END - timedelta(minutes=30), W_END, TERMS, fetch=fetch)
        self.assertTrue(asked)
        for url in asked:
            self.assertTrue(url.endswith(".gkg.csv.zip"), url)
            self.assertNotIn("masterfilelist", url)
            self.assertNotIn("lastupdate", url)


class RowSemantics(unittest.TestCase):
    """A candidate on the mirror's definition, and nothing looser or tighter."""

    def setUp(self):
        self.match = gdelt_raw.matcher(TERMS)

    def _parse(self, *lines):
        return gdelt_raw.parse_candidates(_zip(lines), self.match)

    def test_title_regex_hit(self):
        out = self._parse(_gkg_row("20260903120000", "reuters.com",
                                   "https://reuters.com/a", "Acme plans layoffs at two plants"))
        self.assertEqual([a["url"] for a in out], ["https://reuters.com/a"])
        self.assertEqual(out[0]["seendate"], "20260903T120000Z")
        self.assertEqual(out[0]["domain"], "reuters.com")

    def test_unemployment_theme_hit_without_a_vocabulary_word(self):
        out = self._parse(_gkg_row("20260903120000", "ft.com", "https://ft.com/b",
                                   "Acme to shrink its workforce",
                                   themes="ECON_STOCKMARKET,12;UNEMPLOYMENT,30;"))
        self.assertEqual(len(out), 1)

    def test_neither_is_dropped(self):
        out = self._parse(_gkg_row("20260903120000", "ft.com", "https://ft.com/c",
                                   "Quarterly results beat estimates",
                                   themes="ECON_STOCKMARKET,12;"))
        self.assertEqual(out, [])

    def test_native_phrase_matches_an_original_language_title(self):
        out = self._parse(_gkg_row("20260903120000", "handelsblatt.com",
                                   "https://handelsblatt.com/d",
                                   "Bosch kündigt Stellenabbau an"),
                          _gkg_row("20260903120000", "nikkei.com",
                                   "https://nikkei.com/e", "日産、人員削減を発表"))
        self.assertEqual(len(out), 2)

    def test_the_title_is_html_unescaped_before_matching(self):
        # The translation feed writes titles with entities on disk; the mirror
        # never unescaped and missed these. `&#32;` is a space: "job cuts".
        out = self._parse(_gkg_row("20260903120000", "elpais.com", "https://elpais.com/f",
                                   "Acme announces job&#32;cuts"))
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "Acme announces job cuts")

    def test_domain_is_lowercased_and_short_rows_are_skipped(self):
        out = self._parse(
            _gkg_row("20260903120000", "WWW.Reuters.com", "https://reuters.com/g", "layoffs"),
            "too\tshort\trow")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["domain"], "www.reuters.com")
        self.assertEqual(gdelt._domain(out[0]), "reuters.com")

    def test_the_regex_is_the_mirror_s_regex(self):
        """One definition: gdelt_bq.title_pattern builds the raw matcher too."""
        seen = {}
        real = gdelt_bq.title_pattern

        def spy(terms):
            seen["terms"] = list(terms)
            return real(terms)

        with patch.object(gdelt_bq, "title_pattern", spy):
            gdelt_raw.matcher(TERMS)
        self.assertEqual(seen["terms"], list(TERMS))


class WindowOutcomes(unittest.TestCase):
    """pending / gap / failed / skipped, and the newest stamp consumed."""

    def _fixture(self, url):
        stamp = _stamp_of(url)
        feed = _feed_of(url)
        return _zip([_gkg_row(stamp, "reuters.com", f"https://r.com/{feed}{stamp}", "layoffs"),
                     # The same URL in the next file too: deduped once.
                     _gkg_row(stamp, "reuters.com", "https://r.com/shared", "layoffs")])

    def test_every_file_read_is_complete_and_names_the_newest(self):
        arts, rep = gdelt_raw.read_window(W_END - timedelta(hours=1), W_END, TERMS,
                                          fetch=self._fixture)
        self.assertEqual(rep["status"], "complete")
        self.assertEqual(rep["files_expected"], 10)   # 5 slots x 2 feeds
        self.assertEqual(rep["files_read"], 10)
        self.assertEqual(rep["newest"], "20260903220000")
        self.assertEqual(rep["newest_by_feed"], {"": "20260903220000",
                                                 "translation.": "20260903220000"})
        self.assertEqual(gdelt_raw.lag_minutes(rep["newest"], W_END), 0)
        # 10 files x 2 rows, one URL shared by all of them -> 11 distinct.
        self.assertEqual(rep["candidates"], 20)
        self.assertEqual(len(arts), 11)

    def test_a_404_inside_the_publication_lag_is_pending_not_a_gap(self):
        def fetch(url):
            if _feed_of(url) and _stamp_of(url) >= "20260903213000":
                raise gdelt_raw.NotPublished(url)     # translation feed trailing
            return self._fixture(url)

        _arts, rep = gdelt_raw.read_window(W_END - timedelta(hours=1), W_END, TERMS,
                                           fetch=fetch)
        self.assertEqual(rep["status"], "complete")
        self.assertEqual(rep["pending"], 3)
        self.assertEqual(rep["gaps"], 0)
        self.assertEqual(rep["newest_by_feed"]["translation."], "20260903211500")
        self.assertEqual(rep["newest"], "20260903220000")

    def test_a_404_older_than_the_lag_is_a_gap_and_the_window_is_partial(self):
        def fetch(url):
            if _stamp_of(url) == "20260903170000":
                raise gdelt_raw.NotPublished(url)     # five hours before the end
            return self._fixture(url)

        _arts, rep = gdelt_raw.read_window(W_END - timedelta(hours=6), W_END, TERMS,
                                           fetch=fetch)
        self.assertEqual(rep["gaps"], 2)
        self.assertEqual(rep["pending"], 0)
        self.assertEqual(rep["status"], "partial")

    def test_a_transport_failure_is_failed_and_partial(self):
        def fetch(url):
            if _stamp_of(url) == "20260903214500":
                raise ConnectionError("reset")
            return self._fixture(url)

        _arts, rep = gdelt_raw.read_window(W_END - timedelta(hours=1), W_END, TERMS,
                                           fetch=fetch)
        self.assertEqual(rep["failed"], 2)
        self.assertEqual(rep["status"], "partial")

    def test_the_deadline_stops_fetching_and_the_rest_is_skipped(self):
        asked = []
        clock = [0.0]

        def fetch(url):
            asked.append(url)
            clock[0] += 10.0
            return self._fixture(url)

        with patch.object(gdelt_raw.time, "monotonic", lambda: clock[0]):
            _arts, rep = gdelt_raw.read_window(W_END - timedelta(hours=1), W_END, TERMS,
                                               fetch=fetch, deadline=25.0, workers=1)
        self.assertEqual(len(asked), 3)
        self.assertEqual(rep["skipped"], 7)
        self.assertEqual(rep["files_read"], 3)
        self.assertEqual(rep["status"], "partial")

    def test_nothing_read_raises_so_the_caller_falls_through(self):
        def fetch(url):
            raise ConnectionError("down")

        with self.assertRaisesRegex(RuntimeError, "read 0 of"):
            gdelt_raw.read_window(W_END - timedelta(hours=1), W_END, TERMS, fetch=fetch)

    def test_a_404_is_asked_twice_before_it_counts(self):
        calls = []

        class Resp:
            status_code = 404

        def get(url, headers=None, timeout=None):
            calls.append(url)
            return Resp()

        class Session:
            pass

        s = Session()
        s.get = get
        with patch.object(gdelt_raw.time, "sleep", lambda *_: None):
            with self.assertRaises(gdelt_raw.NotPublished):
                gdelt_raw.fetch_file("https://x/y.zip", session=s)
        self.assertEqual(len(calls), gdelt_raw.FETCH_ATTEMPTS)


class PreferenceOrder(unittest.TestCase):
    """files -> mirror -> query API, inside the existing slot machinery."""

    def setUp(self):
        gdelt_reach.reset()
        gdelt._LAST_RUN_INCOMPLETE = False
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"slots": {}}')
        tmp.close()
        self.ledger_path = tmp.name
        self.addCleanup(lambda: os.path.exists(self.ledger_path) and os.unlink(self.ledger_path))
        for name in ("_sync_ledger_mid_run", "_push_slots_remote"):
            p = patch.object(gdelt, name, lambda *a, **k: None)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(gdelt, "_load_work_ledger", lambda path=None, remote=True: {"slots": {}})
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(gdelt, "_planned_sweeps", lambda: [])
        p.start()
        self.addCleanup(p.stop)
        self.trusted_in = []

        def record_fetch_trusted(arts):
            self.trusted_in.extend(arts)
            return list(arts)

        p = patch.object(gdelt, "_fetch_trusted", record_fetch_trusted)
        p.start()
        self.addCleanup(p.stop)
        self.mirror_calls = []
        self.api_calls = []

        def fake_mirror(start, end):
            self.mirror_calls.append((start, end))
            return [{"url": "mirror-1", "domain": "reuters.com", "title": "layoffs",
                     "seendate": "20260903T120000Z"}], "complete"

        def fake_query(query, start, end, mr, label="broad"):
            self.api_calls.append(label)
            return [{"url": "api-1", "domain": "reuters.com", "title": "layoffs",
                     "seendate": "20260903T120000Z"}], False, None

        for name, fn in (("_collect_mirror", fake_mirror), ("_query_window", fake_query)):
            p = patch.object(gdelt, name, fn)
            p.start()
            self.addCleanup(p.stop)
        self.now = W_END + timedelta(minutes=1)
        p = patch.object(gdelt_raw, "within_horizon",
                         lambda start, now=None: gdelt_raw.HORIZON >= (self.now - start))
        p.start()
        self.addCleanup(p.stop)

    def _raw_ok(self, status="complete"):
        def fake_read(start, end, terms, *, deadline=None, **kw):
            self.raw_terms = list(terms)
            return ([{"url": "raw-1", "domain": "reuters.com", "title": "layoffs",
                      "seendate": "20260903T214500Z"}],
                    {"files_expected": 290, "files_read": 288, "pending": 2, "gaps": 0,
                     "failed": 0, "skipped": 0, "newest": "20260903214500",
                     "newest_by_feed": {"": "20260903214500", "translation.": "20260903210000"},
                     "candidates": 1, "status": status})
        return fake_read

    def _ledger(self):
        with open(self.ledger_path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_files_first_neither_mirror_nor_api_is_asked(self):
        with patch.object(gdelt_raw, "read_window", self._raw_ok()), \
             patch.object(gdelt_bq, "available", lambda: True), \
             patch.dict(os.environ, {"GDELT_PREFER_BQ": "1", "GDELT_RAW_FEED": "1"}):
            out = gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertEqual([a["url"] for a in out], ["raw-1"])
        self.assertEqual(self.mirror_calls, [])
        self.assertEqual(self.api_calls, [])
        # The same exit as every other path: the allowlist, the robots gate,
        # the reach ledger and dedup all live behind _fetch_trusted.
        self.assertEqual([a["url"] for a in self.trusted_in], ["raw-1"])
        self.assertEqual(gdelt.last_run_status(), "ok")
        broad = [s for s in self._ledger()["slots"].values() if s["family"] == "broad"]
        self.assertEqual(broad[0]["status"], "complete")
        self.assertEqual(broad[0]["newest"], "20260903T214500Z")

    def test_the_files_get_the_english_and_native_vocabulary(self):
        with patch.object(gdelt_raw, "read_window", self._raw_ok()):
            gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertIn("layoffs", self.raw_terms)
        for phrase in ("Stellenabbau", "licenciement collectif", "despido colectivo",
                       "esuberi", "人員削減", "정리해고"):
            self.assertIn(phrase, self.raw_terms, f"raw feed regex lacks {phrase}")

    def test_files_fail_then_the_mirror_then_not_the_api(self):
        def boom(*a, **k):
            raise RuntimeError("GDELT raw feed read 0 of 290 files")

        with patch.object(gdelt_raw, "read_window", boom), \
             patch.object(gdelt_bq, "available", lambda: True), \
             patch.dict(os.environ, {"GDELT_PREFER_BQ": ""}):
            out = gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertEqual([a["url"] for a in out], ["mirror-1"])
        self.assertEqual(len(self.mirror_calls), 1)
        self.assertEqual(self.api_calls, [])

    def test_files_fail_no_mirror_then_the_api(self):
        def boom(*a, **k):
            raise RuntimeError("down")

        with patch.object(gdelt_raw, "read_window", boom), \
             patch.object(gdelt_bq, "available", lambda: False):
            out = gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertEqual([a["url"] for a in out], ["api-1"])
        self.assertEqual(self.api_calls, ["broad"])

    def test_a_partial_read_keeps_its_rows_and_reports_degraded(self):
        with patch.object(gdelt_raw, "read_window", self._raw_ok("partial")), \
             patch.object(gdelt_bq, "available", lambda: True):
            out = gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertEqual([a["url"] for a in out], ["raw-1"])
        self.assertEqual(self.mirror_calls, [])      # partial is kept, not re-read
        self.assertEqual(gdelt.last_run_status(), "degraded")
        broad = [s for s in self._ledger()["slots"].values() if s["family"] == "broad"]
        self.assertEqual(broad[0]["status"], "partial")

    def test_a_window_older_than_the_horizon_skips_the_files(self):
        old_start = self.now - gdelt_raw.HORIZON - timedelta(days=1)
        calls = []
        with patch.object(gdelt_raw, "read_window", lambda *a, **k: calls.append(1)), \
             patch.object(gdelt_bq, "available", lambda: True), \
             patch.dict(os.environ, {"GDELT_PREFER_BQ": "1"}):
            gdelt.pull_gdelt_between(old_start, old_start + timedelta(hours=36),
                                     ledger_path=self.ledger_path)
        self.assertEqual(calls, [])
        self.assertEqual(len(self.mirror_calls), 1)

    def test_switched_off_the_files_are_not_asked(self):
        calls = []
        with patch.object(gdelt_raw, "read_window", lambda *a, **k: calls.append(1)), \
             patch.object(gdelt_bq, "available", lambda: False), \
             patch.dict(os.environ, {"GDELT_RAW_FEED": "0"}):
            gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path)
        self.assertEqual(calls, [])
        self.assertEqual(self.api_calls, ["broad"])

    def test_the_deadline_is_handed_to_the_file_read(self):
        seen = {}

        def fake_read(start, end, terms, *, deadline=None, **kw):
            seen["deadline"] = deadline
            return self._raw_ok()(start, end, terms, deadline=deadline)

        with patch.object(gdelt_raw, "read_window", fake_read):
            gdelt.pull_gdelt_between(W_START, W_END, ledger_path=self.ledger_path,
                                     deadline=123456.0)
        self.assertEqual(seen["deadline"], 123456.0)


class FreshnessIsVisible(unittest.TestCase):
    """The newest file consumed is a recorded number, nameless, and read back."""

    def _reach(self):
        r = gdelt_reach.Reach()
        r.note_query("raw", 310, 0, truncated=False)
        r.note_raw_feed(files_expected=290, files_read=286, pending=4, gaps=0,
                        failed=0, skipped=0, newest="20260903214500", lag_minutes=15)
        r.note("a.de", "not_allowlisted", 200)
        r.note("b.de", "kept", 50)
        return r

    def test_the_summary_is_nameless_and_carries_the_stamp_as_a_number(self):
        s = self._reach().summary()
        self.assertEqual(s["raw"]["newest"], 20260903214500)
        self.assertEqual(s["raw"]["lag_minutes"], 15)
        self.assertEqual(s["by_label"]["raw"]["queries"], 1)
        gdelt_reach.assert_nameless(s)

    def test_the_health_detail_names_the_newest_file_and_the_lag(self):
        line = self._reach().health_detail()
        self.assertLessEqual(len(line), 240)
        self.assertIn("raw_files=286/290", line)
        self.assertIn("raw_newest=2026-09-03T21:45Z", line)
        self.assertIn("raw_lag_min=15", line)
        self.assertIn("raw_pending=4", line)
        # The headline facts ops_status [2d] already parses are untouched.
        self.assertRegex(line, r"^returned=310 queries=1 answered=1 abandoned=0 "
                               r"capped=0 kept=50 dropped=200")

    def test_ops_status_reads_the_freshness_back(self):
        import ops_status
        runs = [{"status": "ok", "attempted_at": "2026-09-03T22:13:36+00:00",
                 "detail": self._reach().health_detail()}]
        lines, unmeasured = ops_status.gdelt_reach_lines(runs)
        self.assertFalse(unmeasured)
        blob = " ".join(lines)
        self.assertIn("FRESHNESS: published files read 286/290", blob)
        self.assertIn("2026-09-03T21:45Z", blob)
        self.assertIn("15 min behind", blob)

    def test_a_run_without_the_files_reads_freshness_unknown_not_fresh(self):
        import ops_status
        r = gdelt_reach.Reach()
        r.note_query("mirror", 5000, 900, truncated=False)
        runs = [{"status": "ok", "attempted_at": "2026-09-03T22:13:36+00:00",
                 "detail": r.health_detail()}]
        lines, _ = ops_status.gdelt_reach_lines(runs)
        self.assertIn("FRESHNESS UNKNOWN", " ".join(lines))

    def test_no_file_read_is_not_zero_lag(self):
        r = gdelt_reach.Reach()
        r.note_raw_feed(files_expected=10, files_read=0, pending=0, gaps=0, failed=10,
                        skipped=0, newest=None, lag_minutes=None)
        self.assertIsNone(r.summary()["raw"]["newest"])
        self.assertNotIn("raw_lag_min", r.health_detail())
        self.assertIsNone(gdelt_raw.lag_minutes(None, W_END))


if __name__ == "__main__":
    unittest.main()
