"""The committed jurisdiction table must match the collectors, forever.

templates/partials/jurisdiction-table.php powers the methodology page's
"what qualifies as a record, by jurisdiction" section and the caveat link on
every country and state facet page. It is generated from the WARN collectors'
own state lists and the sources' own documented thresholds by
generate_jurisdiction_table.py; this test fails the build if either side
moves without the other, and statically guards the section's non-negotiable
copy rules (descriptive, never accusatory; UNKNOWN, never invented).
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import generate_jurisdiction_table as gjt  # noqa: E402

PLUGIN = os.path.normpath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))


def _read(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


class JurisdictionTableMatchesCollectors(unittest.TestCase):
    def test_committed_partial_matches_regeneration(self):
        self.assertTrue(gjt.OUT.exists(),
                        "jurisdiction-table.php is missing; run "
                        "python3 railway/generate_jurisdiction_table.py")
        self.assertEqual(gjt.render(), gjt.OUT.read_text(),
                         "jurisdiction-table.php drifted from the collectors; "
                         "regenerate with "
                         "python3 railway/generate_jurisdiction_table.py")

    def test_state_lists_parse_to_a_plausible_union(self):
        codes = gjt.covered_warn_jurisdictions()
        # The daily sweep covers 40+ jurisdictions; a partial parse (the bug
        # this guards against truncated a whole list) reads far fewer.
        self.assertGreaterEqual(len(codes), 40, codes)
        self.assertEqual(codes, sorted(set(codes)))
        for known in ("CA", "TX", "NY", "WA", "AL"):
            self.assertIn(known, codes)

    def test_thresholds_are_derived_not_typed(self):
        html = gjt.OUT.read_text()
        # ERM's floor must be the one erm_import.py documents.
        self.assertIn(gjt.erm_threshold(), html)
        self.assertIn("history back to " + gjt.erm_min_year(), html)
        # Unencoded thresholds must say UNKNOWN in plain words.
        self.assertIn("UNKNOWN", html)

    def test_no_em_dashes_in_generated_ui_copy(self):
        html = gjt.OUT.read_text()
        self.assertNotRegex(html, "[—–]")


class NoticeGapCopyGuards(unittest.TestCase):
    """The notice-gap metric is descriptive arithmetic, never an accusation."""

    def _new_copy(self):
        db = _read("includes", "db.php")
        start = db.index("function alt_warn_notice_gap_stats")
        end = db.index("function alt_wilson_interval", start)
        method = _read("templates", "page-methodology.php")
        s2 = method.index('id="m-notice-gap"')
        e2 = method.index("</section>", s2)
        return db[start:end] + method[s2:e2]

    def test_never_labels_an_employer_non_compliant(self):
        text = self._new_copy().lower()
        for banned in ("violation", "violated", "non-compliant",
                       "noncompliant", "illegal", "unlawful", "broke the law"):
            self.assertNotIn(banned, text)

    def test_uses_the_descriptive_phrasing_and_cites_the_exceptions(self):
        text = self._new_copy()
        self.assertIn("shorter than 60 days", text)
        self.assertIn("2102(b)", text)      # lawful-exception citation
        self.assertIn("2104", text)         # court-only enforcement citation
        self.assertIn("not a statement that any employer failed to comply",
                      text)

    def test_exclusions_are_counted_never_imputed(self):
        text = self._new_copy()
        self.assertIn("missing_dates", text)
        self.assertIn("effective_precedes_notice", text)
        self.assertIn("never guessed", text)

    def test_same_date_rows_are_excluded_not_scored_as_zero_notice(self):
        # Single-date states store the notice date in both fields, so gap 0 is
        # ambiguous. First live render scored nine such states "median 0 days,
        # 100% shorter than 60"; this pins the exclusion that fixed it.
        text = self._new_copy()
        self.assertIn("same_date_ambiguous", text)
        self.assertIn("announcement_date < layoff_date", text)
        self.assertIn("announcement_date = layoff_date", text)

    def test_facet_pages_carry_the_jurisdiction_caveat(self):
        facet = _read("templates", "page-facet.php")
        self.assertIn("#m-jurisdictions", facet)
        self.assertIn("Definitions differ by jurisdiction", facet)

    def test_provenance_line_never_assigns_an_origin(self):
        db = _read("includes", "db.php")
        start = db.index("Provenance of the corrections in the log")
        end = db.index("function alt_compact_corrections_log", start)
        body = db[start:end]
        self.assertIn("never assigned a guessed origin", body)
        tracker = _read("templates", "page-tracker.php")
        self.assertIn("alt_corrections_provenance", tracker)
        self.assertIn("counted as unrecorded, not assigned one", tracker)


if __name__ == "__main__":
    unittest.main()
