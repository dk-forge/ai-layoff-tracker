"""The register-of-registers must stay a FILE FINDING, not a catalogue reading.

`country_coverage.PER_EMPLOYER_REGISTERS` answers the question the tracker is
actually for: does any authority on earth publish a list that NAMES the employer
filing a collective-dismissal notice? On 2026-08-19 the answer is four places —
US state WARN units, Quebec, Mazowieckie and Illes Balears — and two of the
near-misses had just been re-opened because the survey's evidence for them was a
catalogue description rather than the file.

THE FAILURE THESE GUARD, and it already happened once. The survey recorded that
Euskadi masks the company CIF. That is a statement about the IDENTIFIER, and it
was read as "the name is there, redacted" — the entry said "one redacted column
from being a fifth register". Downloading eres_cae.csv settled it the other way:
there are sixteen columns and none of them is a name, so nothing is redacted and
there is no fifth register to un-redact. A near-miss that is one decision away
and a near-miss that is a whole new column away are different findings, and only
the file can tell them apart.

  * an entry claims an authority does or does not name employers and carries no
    evidence of what the publication's columns actually are
  * a `names_employers: False` entry acquires a name-shaped column and stays
    False, or a True one stops saying which column carries the name
  * THE TENFOLD TRAP: a Spanish ERE/ERTE file mixes EXTINCIO (dismissal) with
    SUSPENSIO and RED. JOR. (short-time work) in one measure column. Balears is
    359 dismissals inside 3,817 rows; Euskadi is 79 inside 216. Anything built
    on either that forgets to filter reports roughly ten times the layoffs that
    happened. The filter is pinned here even though nothing is wired yet,
    because the moment somebody wires it the vocabulary is what they will reach
    for, and a `dismissal_measures` that quietly equals the whole vocabulary is
    a filter that does nothing while looking like one.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import country_coverage as cc

# What an employer-name column looks like in the languages this register covers.
# Deliberately broad: the test's job is to fail LOUDLY if a name column appears
# beside a `names_employers: False`, and a false alarm there is cheap while a
# miss is the exact error this file exists to prevent.
_NAME_COLUMN_RX = re.compile(
    r"empresa|raz[oó]n social|raho sozial|denominaci[oó]n|employer|company|"
    r"\bname\b|nazwa|zaklad pracy|zakład pracy|pracodawc|entreprise|"
    r"employeur|firma|arbeitgeber|datore", re.I)


def _registers():
    return cc.PER_EMPLOYER_REGISTERS


class EveryEntryIsIdentifiable(unittest.TestCase):

    def test_every_entry_names_a_jurisdiction_a_country_and_a_source(self):
        for r in _registers():
            for field in ("jurisdiction", "country", "what", "cite"):
                self.assertTrue(r.get(field), f"{r.get('jurisdiction')}: {field} missing")
            self.assertIn("names_employers", r,
                          f"{r['jurisdiction']}: must say yes or no, never be silent")
            self.assertIsInstance(r["names_employers"], bool)
            self.assertTrue(r["cite"].startswith("http"),
                            f"{r['jurisdiction']}: citation is not a URL")


class AFindingFromAFileSaysWhatWasInTheFile(unittest.TestCase):
    """`verified_from_file` is a promise that somebody opened the thing."""

    def test_a_file_verified_entry_carries_its_date_and_its_name_column_verdict(self):
        for r in _registers():
            if not r.get("verified_from_file"):
                continue
            self.assertRegex(r["verified_from_file"], r"^\d{4}-\d{2}-\d{2}$",
                             f"{r['jurisdiction']}: verification needs a date")
            self.assertIn("name_column", r,
                          f"{r['jurisdiction']}: file-verified but silent on whether a "
                          f"name column exists — that silence is the original defect")

    def test_a_naming_register_says_which_column_carries_the_name(self):
        for r in _registers():
            if not (r.get("verified_from_file") and r["names_employers"]):
                continue
            self.assertTrue(r.get("name_column"),
                            f"{r['jurisdiction']}: claims to name employers but does not "
                            f"say from which column")

    def test_a_non_naming_register_proves_it_with_the_columns_it_does_publish(self):
        """The claim that decays. 'No name' must be backed by the column list."""
        for r in _registers():
            if r.get("names_employers") or not r.get("verified_from_file"):
                continue
            self.assertIsNone(r.get("name_column"),
                              f"{r['jurisdiction']}: names_employers is False but a name "
                              f"column is recorded — one of the two is wrong")
            cols = r.get("verified_columns")
            self.assertTrue(cols, f"{r['jurisdiction']}: 'no employer name' is only a "
                                  f"finding if the published columns are recorded")
            for c in cols:
                self.assertIsNone(
                    _NAME_COLUMN_RX.search(c),
                    f"{r['jurisdiction']}: column {c!r} looks like an employer name and "
                    f"the entry says this register does not name employers")


class TheShortTimeWorkFilterIsPinned(unittest.TestCase):
    """Filtering on the measure column is what keeps the count honest."""

    def test_a_measure_column_comes_with_its_vocabulary_and_its_dismissal_subset(self):
        for r in _registers():
            if "measure_column" not in r:
                continue
            if r["measure_column"] is None:
                self.assertEqual(tuple(r.get("dismissal_measures") or ()), (),
                                 f"{r['jurisdiction']}: no measure column, so no measure "
                                 f"can be a dismissal filter")
                continue
            values = tuple(r.get("measure_values") or ())
            dismissals = tuple(r.get("dismissal_measures") or ())
            self.assertTrue(values, f"{r['jurisdiction']}: measure column with no "
                                    f"recorded vocabulary cannot be filtered on")
            self.assertTrue(dismissals, f"{r['jurisdiction']}: no measure marked as a "
                                        f"dismissal — the whole file would count")
            for d in dismissals:
                self.assertIn(d, values,
                              f"{r['jurisdiction']}: {d!r} is filtered for but is not in "
                              f"the recorded vocabulary")
            self.assertLess(
                len(set(dismissals)), len(set(values)),
                f"{r['jurisdiction']}: every measure is marked a dismissal, so the "
                f"filter passes the whole file — that is the tenfold inflation with a "
                f"filter-shaped comment on it")

    def test_the_two_spanish_files_keep_extincion_and_drop_the_short_time_work(self):
        """Named explicitly, so a rename cannot quietly widen either one."""
        by_j = {r["jurisdiction"]: r for r in _registers()}
        bal = by_j["Illes Balears"]
        self.assertEqual(tuple(bal["dismissal_measures"]), ("EXTINCIO",))
        for short_time in ("SUSPENSIO", "RED. JOR."):
            self.assertIn(short_time, bal["measure_values"])
            self.assertNotIn(short_time, bal["dismissal_measures"])
        eus = by_j["Euskadi"]
        self.assertEqual(tuple(eus["dismissal_measures"]), ("Extincion",))
        for short_time in ("Suspension", "Reduccion"):
            self.assertIn(short_time, eus["measure_values"])
            self.assertNotIn(short_time, eus["dismissal_measures"])


class TheCountOfRegistersOnEarthIsStated(unittest.TestCase):
    """A number the owner may say out loud, so it fails rather than drifts."""

    def test_four_jurisdictions_name_employers_and_they_are_these_four(self):
        naming = sorted(r["jurisdiction"] for r in _registers()
                        if r["names_employers"])
        self.assertEqual(naming, [
            "Illes Balears",
            "Mazowieckie voivodeship",
            "Quebec",
            "United States (state WARN units)",
        ], "the count of employer-naming registers on earth changed — update the "
           "Sources page and the methodology note in the SAME session")

    def test_euskadi_and_podlaskie_are_settled_near_misses_not_open_questions(self):
        """So nobody re-checks them in six months."""
        by_j = {r["jurisdiction"]: r for r in _registers()}
        for name in ("Euskadi", "Podlaskie voivodeship"):
            r = by_j[name]
            self.assertFalse(r["names_employers"])
            self.assertTrue(r.get("verified_from_file"),
                            f"{name}: re-opened without the file being re-read")


if __name__ == "__main__":
    unittest.main()
