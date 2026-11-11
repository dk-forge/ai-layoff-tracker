"""A month-sized EDGAR range must not stop at 30 filings per keyword.

The history sweep reads a month at a time; one keyword ("reduction in force")
can match well over 30 8-Ks in a month. The old 3-page ceiling printed a
warning and dropped the rest. Paging now runs until EFTS's own total is read.
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import sources.edgar as edgar  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_efts(total):
    def fake_get(url, params=None, attempts=3):
        start = params["from"]
        n = max(0, min(edgar.PAGE_SIZE, total - start))
        hits = [{"_id": f"{params['forms']}-{start + i}:x.htm", "_source": {}}
                for i in range(n)]
        return _Resp({"hits": {"hits": hits, "total": {"value": total}}})
    return fake_get


class KeywordPagingTests(unittest.TestCase):
    def _search(self, total):
        orig = edgar._get
        edgar._get = _fake_efts(total)
        try:
            return edgar._search_keyword(
                "reduction in force",
                datetime(2026, 10, 1, tzinfo=timezone.utc),
                datetime(2026, 10, 31, tzinfo=timezone.utc))
        finally:
            edgar._get = orig

    def test_month_with_75_matches_reads_all_of_them(self):
        hits = self._search(75)
        self.assertEqual(len(hits), 75 * len(edgar.FORMS))

    def test_small_day_still_stops_at_the_total(self):
        self.assertEqual(len(self._search(4)), 4 * len(edgar.FORMS))


if __name__ == "__main__":
    unittest.main()
