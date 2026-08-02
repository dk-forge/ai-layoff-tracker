"""Offline guards for the Alabama custom WARN fetcher (warn_new_states.fetch_al).

AL moved off the generic warn-scraper on 2026-08-02. The released open module
(PyPI 1.2.143) still parses the retired madeinalabama.com HTML table, so once
Alabama moved the list to workforce.alabama.gov it died on `table[0]` with
IndexError, wrote no al.csv, and the state fell out of the sweep (851 -> 0).

The state still publishes the same notices as a headerless CSV. What these tests
pin is not "does it parse" but the thing that is expensive to get wrong: the
fetcher must reproduce the RETIRED module's strings exactly, because company +
date + jobs + state IS the dedup hash. Get any of the three normalisations wrong
and every Alabama notice publishes a SECOND copy of a layoff already on the site.

Verified live on 2026-08-02 against all 825 stored AL rows: 259 distinct notices,
259 upserts, 0 new rows.
"""
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _m in ("requests", "pdfplumber"):
    if _m not in sys.modules:
        _st = types.ModuleType(_m)
        _st.RequestException = Exception
        sys.modules[_m] = _st

from sources.warn import ALL_STATES
from sources.warn_new_states import NEW_CUSTOM_STATES, _al_name


class AlNameNormalisationTests(unittest.TestCase):
    """The three differences between the CSV export and the retired HTML page."""

    def test_internal_whitespace_is_collapsed(self):
        # The CSV pads; the page did not, and the server only trims.
        self.assertEqual(_al_name("Salon Centric  Inc"), "Salon Centric Inc")
        self.assertEqual(_al_name("Overland Contracting   Inc"),
                         "Overland Contracting Inc")

    def test_apostrophe_becomes_typographic(self):
        self.assertEqual(_al_name("David's Bridal"), "David’s Bridal")
        self.assertEqual(_al_name("Joann's Distribution Center"),
                         "Joann’s Distribution Center")

    def test_spaced_separator_becomes_an_en_dash(self):
        self.assertEqual(_al_name("WALMART - STORE #763"),
                         "WALMART – STORE #763")
        self.assertEqual(_al_name("CVG - Commercial Vehicle Group Alabama"),
                         "CVG – Commercial Vehicle Group Alabama")

    def test_unspaced_hyphens_are_part_of_the_name_and_stay_ascii(self):
        # 80 stored AL rows carry one. Swapping these would break the hash for
        # every one of them, which is why the substitution is space-anchored.
        for name in ("Winn-Dixie Montgomery LLC", "JELD-WEN INTERIOR DOORS",
                     "KMART CORPORATION-STORE 4836", "Birmingham-Southern College",
                     "FLEX-N-GATE-ALABAMA", "MID-SOUTH ELECTRONICS, INC."):
            self.assertEqual(_al_name(name), name)

    def test_empty_input_is_empty_not_none(self):
        self.assertEqual(_al_name(None), "")
        self.assertEqual(_al_name("   "), "")


class AlWiringTests(unittest.TestCase):
    def test_al_is_served_by_the_custom_fetcher(self):
        self.assertIn("AL", NEW_CUSTOM_STATES)

    def test_al_is_no_longer_run_by_the_broken_generic_module(self):
        # Leaving AL in ALL_STATES would keep invoking the module that raises,
        # and (because warn_import excludes NEW_CUSTOM_STATES from the generic
        # drift check) its zero would no longer even be reported.
        self.assertNotIn("AL", ALL_STATES)


class AlRowParsingTests(unittest.TestCase):
    """The positional parse, exercised through fetch_al with a stubbed fetch."""

    CSV = (
        'AL202600004,Layoff,07/22/2026,09/30/2026,"BASF Corporation","Mc Intosh",79,1520\n'
        'AL202600003,Closure,07/16/2026,09/14/2026,"Alabama Cooperage",Trinity,71,1519\n'
        'AL202501038,Closure,06/11/2026,06/06/2026,"Legacy Cabinets",Eastaboga,397,1517\n'
        'OLD001,Closure,02/28/2001,04/28/2001,"PLIANT CORPORATION",Birmingham,94,881\n'
        'BAD001,Closure,10/04/2009,11/30/2009,"VISTEON CORPORATION",Tuscaloosa,,232\n'
        'SHORT01,Closure,01/02/2026,01/03/2026,"Too Few Columns"\n'
        'JUNK001,Closure,01/02/0001,01/03/0001,"Junk Date Co",Mobile,50,1\n'
    )

    def _fetch(self, body, status=200):
        from sources import warn_new_states as m
        calls = {}

        class _Resp:
            status_code = status
            text = body

        def _get(url, **kw):
            calls["url"] = url
            return _Resp()

        orig = m.requests.get if hasattr(m.requests, "get") else None
        m.requests.get = _get
        try:
            return m.fetch_al(), calls
        finally:
            if orig is not None:
                m.requests.get = orig

    def test_keeps_only_wellformed_in_window_rows(self):
        rows, _ = self._fetch(self.CSV)
        self.assertEqual([r["company_name"] for r in rows],
                         ["BASF Corporation", "Alabama Cooperage", "Legacy Cabinets"])

    def test_layoff_date_is_the_notice_date_not_the_action_date(self):
        # This is the whole ballgame for dedup: every stored AL row is keyed on
        # the notice date, so keying on the effective date would duplicate all
        # of Alabama rather than upsert onto it.
        rows, _ = self._fetch(self.CSV)
        self.assertEqual(rows[0]["layoff_date"], "2026-07-22")   # not 2026-09-30
        self.assertEqual(rows[2]["layoff_date"], "2026-06-11")   # not 2026-06-06

    def test_closures_are_tagged_and_layoffs_are_not(self):
        rows, _ = self._fetch(self.CSV)
        self.assertEqual(rows[0]["reason_tags"], [])
        self.assertEqual(rows[1]["reason_tags"], ["closure"])

    def test_row_of_the_wrong_width_is_skipped_not_guessed(self):
        # If Alabama adds or removes a column, returning FEWER rows trips the
        # zero-result drift alarm. Shifting the fields would silently publish
        # wrong companies and counts.
        rows, _ = self._fetch(self.CSV)
        self.assertNotIn("Too Few Columns", [r["company_name"] for r in rows])

    def test_a_blocked_fetch_returning_html_yields_nothing(self):
        rows, _ = self._fetch("<!DOCTYPE html><html><body>Access denied</body></html>")
        self.assertEqual(rows, [])

    def test_non_200_yields_nothing(self):
        rows, _ = self._fetch(self.CSV, status=403)
        self.assertEqual(rows, [])

    def test_reads_the_csv_export_not_the_blocked_human_page(self):
        _, calls = self._fetch(self.CSV)
        self.assertEqual(calls["url"], "https://workforce.alabama.gov/documents/warn-list/")

    def test_dedup_hash_is_stable_for_a_known_notice(self):
        # Pinned from the live tracker: changing any normalisation above changes
        # this hash, and a changed hash means a duplicate row on the public site.
        import hashlib
        rows, _ = self._fetch(self.CSV)
        expected = hashlib.md5(
            "warnbasf corporation2026-07-2279AL".encode("utf-8")).hexdigest()
        self.assertEqual(rows[0]["dedup_hash"], expected)


if __name__ == "__main__":
    unittest.main()
