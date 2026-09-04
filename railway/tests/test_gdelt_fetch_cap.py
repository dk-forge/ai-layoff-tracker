"""The article-FETCH phase must not outrun the run's own candidate cap.

Run 33860668098 (2026-09-04, historical-news-sweep) asked for a candidate cap
of 10 (`BACKFILL_MAX_ARTICLES=10`) and printed "GDELT via BigQuery mirror:
35175 article(s)". `_fetch_trusted` had no cap of its own -- the mirror walks
a window "to completion" regardless of `max_records`, and every trusted,
deduped one of those 35,175 matches got a real HTTP request, one at a time,
through a 4-worker pool. The job was still fetching 27+ minutes later when
`timeout-minutes: 45` killed it; `BACKFILL_DEADLINE_SECONDS=600` never fired
because that clock lives in gdelt_backfill.py's post-collection extraction
loop, which `_fetch_trusted` never returned to reach.

`pull_gdelt_between` now threads its `max_records` into `_fetch_trusted` as
`max_candidates`, bounding the expensive per-URL fetch to exactly as many
candidates as the caller can ever use. Collection itself stays unbounded on
purpose (the mirror's full match set still feeds the ledger/health
bookkeeping) -- only the network fetch is capped.

Hermetic: `_fetch_article` is replaced with a counting stub, so this proves
the bound without touching the network.
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import gdelt_reach  # noqa: E402
from sources import gdelt  # noqa: E402

W_START = datetime(2021, 9, 26, 0, 0, tzinfo=timezone.utc)
W_END = W_START + timedelta(days=6)


class FetchIsCappedToWhatTheCallerCanUse(unittest.TestCase):
    def setUp(self):
        gdelt_reach.reset()
        gdelt._LAST_RUN_INCOMPLETE = False
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write('{"slots": {}}')
        tmp.close()
        self.ledger_path = tmp.name
        self.addCleanup(lambda: os.path.exists(self.ledger_path) and os.unlink(self.ledger_path))

    def _run(self, matched_count, max_records):
        """Simulate a mirror match set of `matched_count` trusted, distinct
        URLs (the 35,175-article shape) and return the fetch-call count."""
        fetched = []

        def fake_mirror(start, end):
            arts = [{"url": f"https://reuters.com/story-{i}", "domain": "reuters.com",
                     "title": "layoffs", "seendate": "20210926T120000Z"}
                    for i in range(matched_count)]
            return arts, "complete"

        def counting_fetch(url, gate=None):
            fetched.append(url)
            return "some article text about layoffs"

        with patch.object(gdelt, "_collect_mirror", fake_mirror), \
             patch.object(gdelt, "_planned_sweeps", lambda: []), \
             patch.object(gdelt, "TRUSTED_DOMAINS", {"reuters.com"}), \
             patch.object(gdelt, "_fetch_article", counting_fetch), \
             patch.object(gdelt.time, "sleep", lambda s: None), \
             patch("sources.gdelt.gdelt_bq.available", lambda: True):
            entries = gdelt.pull_gdelt_between(
                W_START, W_END, max_records=max_records, ledger_path=self.ledger_path)
        return fetched, entries

    def test_a_huge_mirror_match_only_fetches_up_to_the_candidate_cap(self):
        fetched, entries = self._run(matched_count=5000, max_records=10)
        self.assertEqual(len(fetched), 10,
                          "the fetch phase must stop at the run's candidate "
                          "cap, not walk every trusted match the mirror found")
        self.assertEqual(len(entries), 10)

    def test_a_match_set_under_the_cap_is_fetched_in_full(self):
        fetched, entries = self._run(matched_count=3, max_records=10)
        self.assertEqual(len(fetched), 3)
        self.assertEqual(len(entries), 3)

    def test_capped_candidates_are_accounted_for_not_silently_dropped(self):
        self._run(matched_count=50, max_records=10)
        by_reason = gdelt_reach.current().by_reason()
        self.assertEqual(by_reason.get("candidate_cap"), 40)
        self.assertEqual(by_reason.get("kept"), 10)


if __name__ == "__main__":
    unittest.main()
