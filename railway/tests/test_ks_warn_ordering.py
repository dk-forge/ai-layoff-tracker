"""The Kansas fetcher must never let its per-run bound decide WHICH notices it reads.

`fetch_ks` caps the per-run detail fetches at `_KS_MAX_DETAILS`. That cap is a
runtime bound, and it is only safe if the ids it truncates are the OLDEST ones.
The kansasworks listing is served OLDEST-FIRST by default (page 1 is 1998-2000,
the newest notice sits ~35 pages in), so a cap applied in listing order reads the
oldest N notices every run, clears any non-zero count floor, and reports healthy
forever while never reaching a new filing. Raising the cap does not fix that: a
cap over an unordered listing is unsafe at every value.

So the ordering is re-established locally, from each row's own Notice Date, and
these tests pin that. The listing here is deliberately served OLDEST-FIRST, i.e.
it models a server that IGNORES the `q[s]=notice_on desc` we ask for -- the
guarantee has to hold without the server's cooperation.

Only `requests`/`pdfplumber` are stubbed (never fake sources.* modules).
"""
import sys
import types
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _m in ("requests", "pdfplumber"):
    if _m not in sys.modules:
        _st = types.ModuleType(_m)
        _st.RequestException = Exception
        sys.modules[_m] = _st

from sources import warn_new_states as ks


PAGE_SIZE = 25


def _make_notices(n):
    """n notices, id 1000+i, one per week, OLDEST first -- newest is the LAST."""
    start = date.today() - timedelta(days=7 * n)
    out = []
    for i in range(n):
        out.append({
            "id": str(1000 + i),
            "company": f"Test Employer {i:03d}",
            "city": "Emporia",
            "date": start + timedelta(days=7 * i),
        })
    return out


def _listing_html(notices):
    rows = "".join(
        '<tr><td><a href="/search/warn_lookups/{id}">{company}</a></td>'
        "<td>{city}</td><td>66801</td><td>1 - Kansas WorkforceONE</td>"
        "<td>{date}</td><td>WARN</td></tr>".format(
            id=n["id"], company=n["company"], city=n["city"],
            date=n["date"].strftime("%b %d, %Y"))
        for n in notices)
    return "<table><tbody>" + rows + "</tbody></table>"


def _detail_html(n):
    return (
        "<dt>Company Name</dt><dd>{company}</dd>"
        "<dt>Address</dt><dd>1 Main St.</dd><dd>{city}, Kansas 66801</dd>"
        "<dt>Notice Date</dt><dd>{date}</dd>"
        "<dt>Number of Employees Affected</dt><dd>75</dd>"
    ).format(company=n["company"], city=n["city"],
             date=n["date"].strftime("%b %d, %Y"))


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status


class _Portal:
    """Serves the listing OLDEST-FIRST, paginated, plus per-notice detail pages."""

    def __init__(self, notices):
        self.by_id = {n["id"]: n for n in notices}
        self.ordered = list(notices)          # oldest first, as the portal does
        self.detail_hits = []

    def get(self, url, **kw):
        if "/search/warn_lookups/" in url:
            nid = url.rsplit("/", 1)[-1]
            self.detail_hits.append(nid)
            n = self.by_id.get(nid)
            return _Resp(_detail_html(n)) if n else _Resp("", 404)
        page = 1
        if "page=" in url:
            page = int(url.split("page=")[1].split("&")[0])
        chunk = self.ordered[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        return _Resp(_listing_html(chunk))


class KsOrderingTests(unittest.TestCase):
    def setUp(self):
        # `requests` may be the real package or this suite's bare stub; either
        # way the fetcher only ever reaches for .get, and nothing here is
        # allowed to make a real request.
        self._real_get = getattr(ks.requests, "get", None)
        self._real_time = ks.time
        ks.time = types.SimpleNamespace(sleep=lambda *a, **k: None)

    def tearDown(self):
        ks.time = self._real_time
        if self._real_get is None:
            try:
                del ks.requests.get
            except AttributeError:
                pass
        else:
            ks.requests.get = self._real_get

    def _run(self, count):
        portal = _Portal(_make_notices(count))
        ks.requests.get = portal.get
        return portal, ks.fetch_ks()

    def test_newest_notice_is_reached_when_listing_is_oldest_first(self):
        """The regression. More notices than the cap, newest LAST in the listing."""
        count = ks._KS_MAX_DETAILS + 40
        portal, entries = self._run(count)
        newest = portal.ordered[-1]
        self.assertIn(newest["id"], portal.detail_hits,
                      "newest notice was never fetched: the per-run bound is "
                      "being applied in listing order, so it decides WHICH "
                      "notices are read, not merely how many")
        self.assertIn(newest["company"], [e["company_name"] for e in entries])

    def test_truncation_drops_the_oldest_not_the_newest(self):
        count = ks._KS_MAX_DETAILS + 40
        portal, entries = self._run(count)
        got = {e["layoff_date"] for e in entries}
        oldest = portal.ordered[0]["date"].isoformat()
        newest = portal.ordered[-1]["date"].isoformat()
        self.assertIn(newest, got)
        self.assertNotIn(oldest, got)

    def test_bound_is_still_honoured(self):
        count = ks._KS_MAX_DETAILS + 40
        portal, _ = self._run(count)
        self.assertLessEqual(len(portal.detail_hits), ks._KS_MAX_DETAILS)

    def test_small_window_reads_everything(self):
        portal, entries = self._run(12)
        self.assertEqual(len(entries), 12)
        self.assertEqual(len(portal.detail_hits), 12)


class KsNewestFirstTests(unittest.TestCase):
    def test_orders_by_notice_date_descending(self):
        rows = [("1", "2025-01-01"), ("2", "2026-05-01"), ("3", "2025-07-04")]
        self.assertEqual(ks._ks_newest_first(rows), ["2", "3", "1"])

    def test_undated_rows_sort_first_never_into_the_truncated_tail(self):
        """A row whose Notice Date did not parse has UNKNOWN recency. Unknown must
        not be treated as old, or a markup change to one column would silently
        push new notices into the part of the list the cap discards."""
        rows = [("1", "2025-01-01"), ("2", ""), ("3", "2026-05-01")]
        self.assertEqual(ks._ks_newest_first(rows)[0], "2")

    def test_listing_rows_reads_id_and_date_together(self):
        html = _listing_html(_make_notices(3))
        rows = ks._ks_listing_rows(html)
        self.assertEqual([r[0] for r in rows], ["1000", "1001", "1002"])
        self.assertTrue(all(r[1] for r in rows), "each row must carry its date")

    def test_listing_rows_drops_duplicate_ids(self):
        html = _listing_html(_make_notices(2)) + _listing_html(_make_notices(2))
        self.assertEqual(len(ks._ks_listing_rows(html)), 2)


if __name__ == "__main__":
    unittest.main()
