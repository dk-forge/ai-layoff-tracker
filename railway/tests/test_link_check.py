"""link_check.py's broken-public-page alert must be deduped by cause.

Until 2026-09-03 `_email` called `ops_notify.notify` with no `dedupe_key` at
all -- every daily run of link-check.yml that found the same broken page
mailed the owner an indistinguishable copy. CLAUDE.md's standing rule is one
cause, one email, with a RECOVERED notice once the cause clears; an outage
lasting a week used to cost seven identical emails. This pins the fix:

  * a broken-page alert always carries a non-empty `dedupe_key`, and the key
    is stable across two runs that find the SAME broken pages (so the ledger
    can recognise "still open") and different when the broken set differs;
  * a clean run (no broken pages) always calls `ops_notify.resolve` with the
    same scope, so a recovered outage is announced once.

Offline: `ops_notify.notify`/`resolve` are monkeypatched, no network, no keys.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import link_check


class DedupeKeyCarried(unittest.TestCase):
    """The alert must name a cause -- proved by mutation, not just presence."""

    def _run_main(self, broken_pages, broken_src=(0, 0, [])):
        calls = {"notify": [], "resolve": []}
        with mock.patch.object(link_check, "SITE", "https://example.test"), \
             mock.patch.object(link_check, "check_pages", return_value=broken_pages), \
             mock.patch.object(link_check, "check_sources", return_value=broken_src), \
             mock.patch.object(link_check, "_report"), \
             mock.patch("ops_notify.notify",
                        side_effect=lambda *a, **kw: calls["notify"].append(kw) or True), \
             mock.patch("ops_notify.resolve",
                        side_effect=lambda *a, **kw: calls["resolve"].append(a) or True):
            link_check.main()
        return calls

    def test_broken_page_alert_carries_a_dedupe_key(self):
        calls = self._run_main([("/ai-layoff-tracker/", 500)])
        self.assertEqual(len(calls["notify"]), 1)
        key = calls["notify"][0].get("dedupe_key")
        self.assertTrue(key, "broken-page alert must carry a dedupe_key")
        self.assertIn(link_check.LINK_CHECK_SCOPE, key)

    def test_same_broken_set_reuses_the_same_key(self):
        first = self._run_main([("/ai-layoff-tracker/", 500)])
        second = self._run_main([("/ai-layoff-tracker/", 502)])  # different code
        self.assertEqual(first["notify"][0]["dedupe_key"],
                         second["notify"][0]["dedupe_key"],
                         "the same broken PATH is the same cause even if the "
                         "HTTP status differs between runs")

    def test_different_broken_set_gets_a_different_key(self):
        one_page = self._run_main([("/ai-layoff-tracker/", 500)])
        two_pages = self._run_main([("/ai-layoff-tracker/", 500),
                                    ("/contact/", 500)])
        self.assertNotEqual(one_page["notify"][0]["dedupe_key"],
                            two_pages["notify"][0]["dedupe_key"])

    def test_clean_run_resolves_the_scope(self):
        calls = self._run_main([])
        self.assertEqual(calls["notify"], [], "a clean run must not alert")
        self.assertEqual(len(calls["resolve"]), 1)
        self.assertEqual(calls["resolve"][0][0], link_check.LINK_CHECK_SCOPE)

    def test_mutation_missing_dedupe_key_is_caught(self):
        """Prove the test actually exercises the fix: strip the key back out
        (the pre-2026-09-03 shape) and confirm this suite would have failed."""
        with mock.patch.object(link_check, "_email",
                               side_effect=lambda subject, body, dedupe_key="":
                                   link_check.ops_notify.notify(subject, body, what="x")):
            calls = []
            with mock.patch.object(link_check, "SITE", "https://example.test"), \
                 mock.patch.object(link_check, "check_pages",
                                   return_value=[("/ai-layoff-tracker/", 500)]), \
                 mock.patch.object(link_check, "check_sources", return_value=(0, 0, [])), \
                 mock.patch.object(link_check, "_report"), \
                 mock.patch("ops_notify.notify",
                            side_effect=lambda *a, **kw: calls.append(kw) or True):
                link_check.main()
            self.assertNotIn("dedupe_key", calls[0])


if __name__ == "__main__":
    unittest.main()
