"""Texas must not go dark when its Socrata dataset freezes.

2026-10-19: `fetch_tx` read only data.texas.gov/8w53-c4f6, which TWC stopped
refreshing on 2026-07-07 (newest notice 2026-06-23). The dataset still answered
200 with ~2,300 historical rows, so every count floor stayed green and only
source_freshness noticed (Texas "dark" 18 days) while TWC kept publishing the
same columns in a per-year workbook on its WARN page. These tests serve exactly
that: a frozen dataset plus a current workbook, and require the newer notices,
no duplicate for a notice in both, and survival of the edge's empty-202
challenge. `requests.get` is patched on the module object, never stubbed into
sys.modules.
"""
import io
import sys
import unittest
import urllib.parse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook  # noqa: E402

from sources import warn_custom as wc  # noqa: E402

YEAR = datetime.now().year
PAGE = (f'<a href="/sites/default/files/oei/docs/warn-act-listings-{YEAR}-twc.xlsx">x</a>'
        '<a href="/sites/default/files/oei/docs/warn-act-listings-2019-twc.xlsx">old</a>')

SOCRATA = [{"notice_date": f"{YEAR}-06-23T00:00:00.000", "job_site_name": "Acme Widgets",
            "total_layoff_number": "244", "layoff_date": f"{YEAR}-08-21T00:00:00.000",
            "city_name": "Plano"}]


def _workbook():
    wb = Workbook()
    ws = wb.active
    ws.append(["NOTICE_DATE", "JOB_SITE_NAME", "COUNTY_NAME", "WDA_NAME",
               "TOTAL_LAYOFF_NUMBER", "LayOff_Date", "WFDD_RECEIVED_DATE", "CITY_NAME"])
    # the same notice the frozen dataset already holds ...
    ws.append([datetime(YEAR, 6, 23), "Acme Widgets", "Collin", "x", 244,
               datetime(YEAR, 8, 21), datetime(YEAR, 6, 23), "Plano"])
    # ... and one filed after it froze
    ws.append([datetime(YEAR, 10, 7), "Example Care LP", "Tarrant", "x", 79,
               datetime(YEAR, 12, 6), datetime(YEAR, 10, 7), "Fort Worth"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class _Resp:
    def __init__(self, status=200, content=b"", payload=None):
        self.status_code, self.content, self._payload = status, content, payload
        self.text = content.decode("utf-8", "replace") if content[:2] != b"PK" else ""

    def json(self):
        return self._payload


class FetchTxReadsTheWorkbook(unittest.TestCase):
    def setUp(self):
        self._get, self._sleep = wc.requests.get, wc.time.sleep
        wc.time.sleep = lambda *_: None
        self.challenges = 0

    def tearDown(self):
        wc.requests.get, wc.time.sleep = self._get, self._sleep

    def _serve(self, challenge_first=0):
        book = _workbook()

        def get(url, **kw):
            if urllib.parse.urlsplit(url).hostname == "data.texas.gov":
                return _Resp(payload=SOCRATA)
            if self.challenges < challenge_first:
                self.challenges += 1
                return _Resp(status=202)           # the edge's empty challenge
            if url.endswith(".xlsx"):
                assert str(YEAR) in url, "an out-of-window workbook was fetched"
                return _Resp(content=book)
            return _Resp(content=PAGE.encode())
        wc.requests.get = get

    def test_a_notice_filed_after_the_dataset_froze_is_read(self):
        self._serve()
        names = {e["company_name"] for e in wc.fetch_tx()}
        self.assertIn("Example Care LP", names)

    def test_a_notice_in_both_copies_is_one_entry(self):
        self._serve()
        out = wc.fetch_tx()
        self.assertEqual(sum(e["company_name"] == "Acme Widgets" for e in out), 1)
        self.assertEqual(len({e["dedup_hash"] for e in out}), len(out))

    def test_the_empty_202_challenge_is_retried_not_believed(self):
        self._serve(challenge_first=2)
        names = {e["company_name"] for e in wc.fetch_tx()}
        self.assertIn("Example Care LP", names)

    def test_a_blocked_page_still_returns_the_dataset(self):
        def get(url, **kw):
            if urllib.parse.urlsplit(url).hostname == "data.texas.gov":
                return _Resp(payload=SOCRATA)
            return _Resp(status=202)
        wc.requests.get = get
        out = wc.fetch_tx()
        self.assertEqual([e["company_name"] for e in out], ["Acme Widgets"])


class RelayedTexasIsTopedUpWhereThePostRuns(FetchTxReadsTheWorkbook):
    """2026-10-20: the relay's scrape job (a GitHub runner) was refused the TWC
    page ("no workbook links ... blocked or moved"), so the relayed TX set was
    the frozen dataset alone and Texas stayed dark. The posting job re-reads the
    workbooks from its own address and unions them by dedup_hash."""

    def _relayed(self):
        def frozen(url, **kw):
            return _Resp(payload=SOCRATA)
        wc.requests.get = frozen
        return wc._tx_rows_to_entries(SOCRATA, "https://data.texas.gov/d/8w53-c4f6")

    def test_the_workbook_notice_is_added_once(self):
        relayed = self._relayed() + [{"state": "FL", "dedup_hash": "fl1", "company_name": "F"}]
        self._serve()
        out = wc.tx_workbook_supplement(relayed)
        names = [e["company_name"] for e in out]
        self.assertIn("Example Care LP", names)
        self.assertEqual(names.count("Acme Widgets"), 1)
        self.assertIn("F", names)

    def test_a_blocked_page_leaves_the_relayed_set_unchanged(self):
        relayed = self._relayed()
        wc.requests.get = lambda url, **kw: _Resp(status=202)
        self.assertEqual(wc.tx_workbook_supplement(relayed), relayed)

    def test_an_exception_never_sinks_the_import(self):
        relayed = self._relayed()

        def boom(url, **kw):
            raise OSError("down")
        wc.requests.get = boom
        self.assertEqual(wc.tx_workbook_supplement(relayed), relayed)


FIXTURE = (Path(__file__).resolve().parent / "fixtures"
           / "tx_warn_listings_2026_twc_2026-11-05.xlsx")


class ChallengedPageStillReadsTheWorkbook(unittest.TestCase):
    """2026-11-05: warn:TX dark 36 days. Both the relay runner and the posting
    runner logged "TX: no workbook links on the TWC WARN page (blocked or
    moved)" every day: TWC's edge challenges the HTML page from datacenter
    addresses, while the workbook itself sits at a stable, predictable URL
    (warn-act-listings-<year>-twc.xlsx, same pattern 2021-2026). The page is
    only a link index, so a challenged page must fall back to that URL. The
    fixture is the real 2026 workbook as TWC served it on 2026-11-05."""

    def setUp(self):
        self._get, self._sleep = wc.requests.get, wc.time.sleep
        wc.time.sleep = lambda *_: None
        self.fetched = []
        book = FIXTURE.read_bytes()

        def get(url, **kw):
            self.fetched.append(url)
            if url.endswith(f"warn-act-listings-{YEAR}-twc.xlsx"):
                return _Resp(content=book)
            return _Resp(status=202)               # page and anything else challenged
        wc.requests.get = get

    def tearDown(self):
        wc.requests.get, wc.time.sleep = self._get, self._sleep

    def test_the_real_workbook_parses(self):
        rows = wc._tx_workbook_rows(FIXTURE.read_bytes())
        self.assertEqual(len(rows), 115)
        self.assertEqual(max(r["notice_date"] for r in rows), "2026-11-03")
        entries = wc._tx_rows_to_entries(rows, wc._TX_PAGE)
        self.assertEqual(len(entries), 115)

    def test_a_challenged_page_falls_back_to_the_known_workbook_url(self):
        names = {e["company_name"] for e in wc.tx_workbook_supplement([])}
        self.assertIn("MV Transportation, Inc (Corpus Christi)", names)
        self.assertTrue(any(u.startswith(wc._TX_ORIGIN + "/sites/default/files/oei/docs/")
                            for u in self.fetched))

    def test_fallback_covers_only_the_current_and_previous_year(self):
        self.assertEqual([y for y, _ in wc._tx_xlsx_links("", YEAR)], [YEAR, YEAR - 1])


class RefusedRunnersReadTheArchivedWorkbook(unittest.TestCase):
    """2026-11-13: warn:TX dark 44 days AFTER the 2.20.298 direct-URL fallback
    shipped. The posting runner's log, every day: "TX: WARN page not served",
    "TX 2026 workbook: not served", "TX 2025 workbook: not served". TWC's edge
    refused BOTH runners for the page AND the workbooks, while the same URLs
    answered 200 elsewhere with notices through 2026-11-03. The fixture above is
    that file. So when TWC refuses, the importer reads the newest Wayback
    capture of the same workbook, and only a recent one."""

    TODAY = datetime(2026, 11, 13).date()

    def setUp(self):
        self._get, self._sleep = wc.requests.get, wc.time.sleep
        wc.time.sleep = lambda *_: None
        self.book = FIXTURE.read_bytes()
        self.fetched = []
        self.capture_ts = "20261109081500"
        self.index_up = True

    def tearDown(self):
        wc.requests.get, wc.time.sleep = self._get, self._sleep

    def _serve(self):
        def get(url, **kw):
            self.fetched.append(url)
            host = urllib.parse.urlsplit(url).hostname
            if host == "www.twc.texas.gov":
                return _Resp(status=403, content=b"Access Denied")   # every runner, every URL
            if host == "web.archive.org" and url.endswith("/cdx/search/cdx"):
                if not self.index_up:
                    raise OSError("reset")
                want = kw["params"]["url"]
                rows = [["timestamp"]]
                if want.endswith(f"warn-act-listings-{YEAR}-twc.xlsx"):
                    rows.append([self.capture_ts])
                return _Resp(content=b"[]", payload=rows)
            if host == "web.archive.org" and f"/web/{self.capture_ts}id_/" in url:
                return _Resp(content=self.book)
            return _Resp(status=404)
        wc.requests.get = get

    def _entries(self):
        real = wc._tx_wayback_get
        wc._tx_wayback_get = lambda url, today=None: real(url, today=self.TODAY)
        try:
            return wc.tx_workbook_supplement([])
        finally:
            wc._tx_wayback_get = real

    def test_a_refused_runner_reads_the_recent_capture(self):
        self._serve()
        out = self._entries()
        self.assertEqual(len(out), 115)
        self.assertIn("MV Transportation, Inc (Corpus Christi)", {e["company_name"] for e in out})

    def test_archived_rows_cite_twc_and_hash_like_the_direct_read(self):
        self._serve()
        out = self._entries()
        direct = wc._tx_rows_to_entries(wc._tx_workbook_rows(self.book), wc._TX_PAGE)
        self.assertEqual({e["dedup_hash"] for e in out}, {e["dedup_hash"] for e in direct})
        self.assertEqual({e["source_url"] for e in out}, {wc._TX_PAGE})

    def test_a_stale_capture_is_refused_not_used(self):
        self.capture_ts = "20261001000000"          # 43 days before TODAY
        self._serve()
        self.assertEqual(self._entries(), [])
        r, why = wc._tx_wayback_get(wc._TX_XLSX_FALLBACK.format(year=YEAR), today=self.TODAY)
        self.assertIsNone(r)
        self.assertIn("not used", why)

    def test_an_unreachable_archive_never_sinks_the_import(self):
        self.index_up = False
        self._serve()
        self.assertEqual(self._entries(), [])

    def test_twc_is_always_tried_first(self):
        self._serve()
        self._entries()
        first_archive = next(i for i, u in enumerate(self.fetched) if "archive.org" in u)
        self.assertTrue(any("twc.texas.gov" in u for u in self.fetched[:first_archive]))

    def test_a_refusal_says_what_came_back(self):
        self._serve()
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._entries()
        self.assertIn("HTTP 403", buf.getvalue())

    def test_the_archive_job_captures_the_workbooks(self):
        import archive_sources
        urls = archive_sources.source_urls()
        for u in wc.tx_workbook_urls():
            self.assertIn(u, urls)
        self.assertEqual(wc.tx_workbook_urls(2026), [
            wc._TX_XLSX_FALLBACK.format(year=2026), wc._TX_XLSX_FALLBACK.format(year=2025)])


if __name__ == "__main__":
    unittest.main()
