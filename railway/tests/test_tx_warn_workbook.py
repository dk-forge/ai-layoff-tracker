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
            if "data.texas.gov" in url:
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
            if "data.texas.gov" in url:
                return _Resp(payload=SOCRATA)
            return _Resp(status=202)
        wc.requests.get = get
        out = wc.fetch_tx()
        self.assertEqual([e["company_name"] for e in out], ["Acme Widgets"])


if __name__ == "__main__":
    unittest.main()
