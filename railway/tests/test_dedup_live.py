"""Live regression guard for the superset/exact-count dedup (db.php
alt_reconcile_supersets, applied daily via reconcile-supersets.yml).

The dedup logic lives in PHP with no PHP unit harness, so this asserts the
DEPLOYED behavior against the live API: known duplicate events must count ONCE.
If the daily reconcile stops running or a change breaks a pass, these revert to
double-counted and this test fails loudly.

Skips cleanly when the site is unreachable (offline / CI without network), so it
never produces a false failure — run it in a networked nightly job or by hand.
Covers the three dedup passes:
  - news-vs-news exact-count across time  (Coinbase 700 on May 5 + Jul 24 -> 700)
  - news-vs-WARN company-total on site rows (Spirit counts once, not news+WARN)
  - within-WARN revision                   (Tyson 1,761 Amarillo x2 -> once)
"""
import json
import unittest
import urllib.parse
import urllib.request

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}


def _agg(**params):
    params.setdefault("cb", "dedupguard")
    url = BASE + "aggregate?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return json.load(r).get("totals", {})


class DedupLiveRegression(unittest.TestCase):
    def setUp(self):
        try:
            self._all = _agg()
        except Exception as e:  # offline / site down -> skip, never false-fail
            self.skipTest(f"live API unreachable ({e})")
        if not self._all.get("jobs"):
            self.skipTest("live API returned no totals")

    def _company_jobs(self, q, year="2026"):
        t = _agg(q=q, country="United States", country_basis="any", years=year)
        return int(t.get("jobs") or 0), int(t.get("entries") or 0)

    def test_coinbase_counts_once(self):
        # Two news reports of the same 700 cut (May 5 + Jul 24) must sum to 700,
        # not 1,400. Allow the primary's 700; fail if it doubles.
        jobs, _ = self._company_jobs("Coinbase")
        self.assertLess(jobs, 1400, f"Coinbase US-2026={jobs}: news-vs-news dedup regressed")

    def test_spirit_counts_once(self):
        # The May-5 news 4,000 must not stack on top of the ~6-7k May-2 WARN sites.
        jobs, _ = self._company_jobs("Spirit Airlines")
        self.assertTrue(0 < jobs < 11000, f"Spirit US-2026={jobs}: news-vs-WARN dedup regressed")

    def test_tyson_amarillo_not_doubled(self):
        # The identical 1,761 Amarillo WARN filed twice must count once.
        jobs, _ = self._company_jobs("Tyson")
        self.assertLess(jobs, 8945, f"Tyson US-2026={jobs}: within-WARN revision dedup regressed")

    def test_no_fake_att_outlier(self):
        # The trashed+suppressed FL test notice (AT&T 78,788) must stay gone.
        jobs, _ = self._company_jobs("AT&T")
        self.assertLess(jobs, 70000, f"AT&T US-2026={jobs}: the fake 78,788 test row is back")


if __name__ == "__main__":
    unittest.main()
