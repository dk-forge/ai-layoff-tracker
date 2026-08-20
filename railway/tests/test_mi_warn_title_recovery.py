"""Offline guard for the Michigan custom WARN fetcher (warn_custom.fetch_mi).

Measured 2026-08-19: michigan.gov's Sitecore SXA search API reports Count=112
and returns 112 fragments, but fetch_mi returned only 88 entries. 23 of the 24
dropped records were dropped for the same reason.

The reason is NOT a missing company name. It is an EMPTY ONE that still
matches. Newer fragments render the anchor as a placeholder --
`<a class="content-title-link" href="" ...></a>` with no text and no href --
and put the real name in the `<h3>` right after it. The title expression was

    re.search(<anchor>) or re.search(<h3>)

and `or` short-circuits on the MATCH OBJECT, not on the text it captured. The
placeholder anchor matches, the `<h3>` branch never runs, `_strip_tags` yields
"", and `_entry` returns None for an empty company. The docstring already said
records come in two shapes; the code could only ever read the first one.

These tests pin the fix at the level that is expensive to get wrong: the name
that reaches `_entry` IS part of the dedup hash (company+date+jobs+state), so a
recovered row must carry the source's own name verbatim -- never one guessed
from a URL slug -- or it publishes a second copy of a notice we already hold.

Conservative skipping is pinned too: a fragment with no name anywhere, and a
fragment whose date is a month with no day ("Commencing June 2025"), must both
stay dropped. A wrong number is worse than a missing one.

The fixture is five real captured fragments (the fifth has its <h3> removed to
make the genuinely-nameless case). No network, no model call.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Parser-only test: never import a real HTTP client. `requests` is stubbed
# through tests/_requests_stub.py and nowhere else -- sys.modules is
# process-global, so a per-module stub makes the surface a function of
# discovery order (see that module's docstring). The transport is patched per
# test with mock.patch.object, which restores itself.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources import warn_custom as wc  # noqa: E402

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "mi_sxa_search_results.json").read_text())


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def _paid_call_is_a_failure(_text, _label=""):
    raise AssertionError(
        "fetch_mi made a paid model call; MI is an LLM-free WARN path")


def _run_fetch_mi(payload=FIXTURE):
    """fetch_mi against a captured payload, with the paid path booby-trapped."""
    urls = []

    def _get(url, **_kw):
        urls.append(url)
        return _FakeResponse(payload)

    with mock.patch.object(wc.requests, "get", _get), \
            mock.patch.object(wc, "llm_count_from_text", _paid_call_is_a_failure):
        return wc.fetch_mi(), urls


def _by_company(entries):
    return {e["company_name"]: e for e in entries}


class MiTitleRecoveryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.entries, cls.urls = _run_fetch_mi()
        cls.byname = _by_company(cls.entries)

    def test_placeholder_anchor_does_not_swallow_the_h3_name(self):
        """The regression. Fails on the pre-fix code: SMBC is dropped entirely."""
        self.assertIn("SMBC MANUBANK", self.byname,
                      "record with an empty content-title-link anchor and a "
                      "populated <h3> was dropped")
        e = self.byname["SMBC MANUBANK"]
        self.assertEqual(e["job_count"], 1)
        self.assertEqual(e["layoff_date"], "2026-10-09")
        self.assertEqual(e["state"], "MI")

    def test_h3_name_is_the_source_string_not_a_url_slug(self):
        # The slug is "general-motors-lansing-region"; the published name is not.
        self.assertIn("General Motors, LLC — Lansing Region", self.byname)
        e = self.byname["General Motors, LLC — Lansing Region"]
        self.assertEqual(e["job_count"], 350)
        self.assertEqual(e["layoff_date"], "2027-01-14")

    def test_the_old_anchor_shape_still_parses_unchanged(self):
        # A real anchor with real text must be read from the anchor, so the
        # hashes of the 88 rows that already worked do not move.
        self.assertIn("Samaritas", self.byname)
        e = self.byname["Samaritas"]
        self.assertEqual(e["job_count"], 58)
        self.assertEqual(e["layoff_date"], "2026-03-31")

    def test_a_fragment_with_no_name_anywhere_is_skipped(self):
        for e in self.entries:
            self.assertNotIn("no-title-at-all", e["source_url"])

    def test_a_month_only_date_is_skipped_not_guessed(self):
        # "Layoff date: Commencing June 2025" -- no day. Dropping it is correct;
        # inventing the 1st (or today) would publish a wrong effective date.
        self.assertNotIn("LACROIX Electronics", self.byname)

    def test_recovered_rows_carry_the_warn_shape_and_hash_inputs(self):
        for e in self.entries:
            self.assertEqual(e["source_type"], "warn")
            self.assertEqual(e["source_name"], "MI WARN notice")
            self.assertEqual(e["country"], "United States")
            self.assertFalse(e["ai_explicit"])
            self.assertTrue(e["dedup_hash"])
            self.assertGreater(e["job_count"], 0)

    def test_the_fetch_costs_nothing_and_makes_one_request(self):
        # _paid_call_is_a_failure would have raised; one GET, no model call.
        self.assertEqual(len(self.urls), 1)
        self.assertIn("michigan.gov", self.urls[0])


if __name__ == "__main__":
    unittest.main()
