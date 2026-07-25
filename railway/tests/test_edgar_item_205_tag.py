"""Guards for SEC 8-K Item 2.05 ("Costs Associated with Exit or Disposal
Activities") tagging in the EDGAR collector.

EFTS returns each hit's 8-K item codes in `_source.items`. Item 2.05 is the
strongest receipted layoff disclosure a public company files, so a hit carrying
it is marked (via the poster-visible `source_name`) as a verified exit-cost
disclosure. A hit without 2.05 keeps the plain provenance label.

Also guards the fix that `search_company_filings` (the tracker-diff tripwire)
emits the server-recognized `source_type: "8K"` + `verification_level: "gold"`,
not the unrecognized "sec_8k" that the server silently downgraded to news.
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Pure-guard tests do not create API clients or make network calls.
sys.modules.setdefault("openai", SimpleNamespace())
sys.modules.setdefault("requests", SimpleNamespace())

import sources.edgar as edgar
from sources.edgar import _edgar_source_name, _has_exit_cost_item


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def _apple_hit(alt_form=True):
    src = {
        "adsh": "0000320193-26-000001",
        "ciks": ["0000320193"],
        "display_names": ["Apple Inc.  (AAPL)  (CIK 0000320193)"],
        "file_date": "2026-07-01",
        "items": ["2.05", "7.01"],  # <- Item 2.05 present
    }
    hit = {"_id": "0000320193-26-000001:aapl.htm", "_source": src}
    if alt_form:
        hit["_alt_form"] = "8-K"
    return hit


def _msft_hit(alt_form=True):
    src = {
        "adsh": "0000789019-26-000002",
        "ciks": ["0000789019"],
        "display_names": ["Microsoft Corporation  (MSFT)  (CIK 0000789019)"],
        "file_date": "2026-07-02",
        "items": ["7.01"],  # <- no 2.05
    }
    hit = {"_id": "0000789019-26-000002:msft.htm", "_source": src}
    if alt_form:
        hit["_alt_form"] = "8-K"
    return hit


class ExitCostHelperTests(unittest.TestCase):
    def test_detects_item_205(self):
        self.assertTrue(_has_exit_cost_item(["2.05", "7.01"]))

    def test_absent_item_205(self):
        self.assertFalse(_has_exit_cost_item(["7.01", "9.01"]))

    def test_fail_soft_on_malformed_arrays(self):
        # None / missing / wrong type must never raise, and never tag.
        for bad in (None, "2.05", 205, {}, {"2.05": 1}):
            self.assertFalse(_has_exit_cost_item(bad))

    def test_tolerates_whitespace_and_nonstring_codes(self):
        self.assertTrue(_has_exit_cost_item([" 2.05 "]))
        self.assertTrue(_has_exit_cost_item([2.05]))

    def test_source_name_label(self):
        self.assertEqual(_edgar_source_name("8-K", False), "SEC EDGAR 8-K")
        self.assertIn("Item 2.05", _edgar_source_name("8-K", True))


class MainPullTaggingTests(unittest.TestCase):
    def setUp(self):
        self._orig_search = edgar._search_keyword
        self._orig_fetch = edgar._fetch_filing_text
        edgar._search_keyword = lambda kw, s, e: [_apple_hit(), _msft_hit()]
        edgar._fetch_filing_text = lambda url: "The company will reduce its workforce."

    def tearDown(self):
        edgar._search_keyword = self._orig_search
        edgar._fetch_filing_text = self._orig_fetch

    def test_item_205_hit_is_marked_gold_exit_cost(self):
        start = datetime(2026, 7, 1, tzinfo=timezone.utc)
        end = datetime(2026, 7, 3, tzinfo=timezone.utc)
        results = edgar.pull_edgar_filings_between(start, end)
        by_company = {r["company_name"]: r for r in results}

        apple = by_company["Apple Inc."]
        self.assertEqual(apple["source_type"], "8K")
        self.assertEqual(apple["verification_level"], "gold")
        self.assertIn("Item 2.05", apple["source_name"])
        self.assertEqual(apple["sec_items"], ["2.05", "7.01"])

        msft = by_company["Microsoft Corporation"]
        self.assertEqual(msft["source_type"], "8K")
        self.assertEqual(msft["verification_level"], "gold")
        self.assertNotIn("2.05", msft["source_name"])
        self.assertEqual(msft["source_name"], "SEC EDGAR 8-K")


class SearchCompanyFilingsTests(unittest.TestCase):
    _SENTINEL = object()

    def setUp(self):
        # `requests`/`time` may be real modules or the stub above; save with a
        # sentinel so tearDown restores or deletes correctly either way.
        self._orig_get = getattr(edgar.requests, "get", self._SENTINEL)
        self._orig_sleep = getattr(edgar.time, "sleep", self._SENTINEL)
        self._orig_fetch = edgar._fetch_filing_text
        edgar.requests.get = lambda *a, **k: _FakeResp(
            {"hits": {"hits": [_apple_hit(alt_form=False), _msft_hit(alt_form=False)]}}
        )
        edgar._fetch_filing_text = lambda url: "The company will reduce its workforce."
        edgar.time.sleep = lambda *_a, **_k: None

    def tearDown(self):
        edgar._fetch_filing_text = self._orig_fetch
        if self._orig_get is self._SENTINEL:
            del edgar.requests.get
        else:
            edgar.requests.get = self._orig_get
        if self._orig_sleep is self._SENTINEL:
            del edgar.time.sleep
        else:
            edgar.time.sleep = self._orig_sleep

    def test_emits_recognized_source_type_and_tags_205(self):
        out = edgar.search_company_filings("Apple Inc.", days_back=120)
        self.assertTrue(out, "search_company_filings returned nothing")
        by_company = {r["company_name"]: r for r in out}

        # The recognized SEC values, not the old "sec_8k" (downgraded to news).
        for entry in out:
            self.assertEqual(entry["source_type"], "8K")
            self.assertEqual(entry["verification_level"], "gold")

        self.assertIn("Item 2.05", by_company["Apple Inc."]["source_name"])
        self.assertNotIn("2.05", by_company["Microsoft Corporation"]["source_name"])


if __name__ == "__main__":
    unittest.main()
