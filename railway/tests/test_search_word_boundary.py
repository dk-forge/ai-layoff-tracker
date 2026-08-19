"""The public search box is not a substring match.

MEASURED, 2026-08-18, live:

    /layoffs/v1/query?q=EY   ->  1,968 of 65,441 rows
    /talent/v1/query?q=EY    -> 13,934 of 30,986 rows

Two letters, no boundary, so "money", "survey", "Monterrey", "key" and
"attorney" all answered. The top hits for a reader searching a Big Four firm
were a Brazilian space startup and a Chilean statistics agency. The same
endpoint was correct on `Workday` (4) and `Stripe` (4), which is exactly why it
survived every spot check: the defect only bites on the short all-caps names
this domain is made of -- EY, PwC, IBM, SAP, BT, GE, HP, KPMG, UBS, ING.

It is the same defect the ingest gate had when `layoff` matched `playoff`
(railway/sources/regional_feeds.py), and it takes the same answer.

WHAT THESE TESTS HOLD, AND WHY EACH ONE IS HERE.

1. A boundary, not a length floor. A minimum query length would return an
   honest-looking zero for a real two-letter employer, and an empty result that
   looks correct is worse than a noisy one that obviously is not.
2. Case-insensitive still. `workday` must find `Workday`. We match the token
   and not the case of the string.
3. NON-LATIN TERMS KEEP THE SUBSTRING SEARCH. A word boundary needs a non-word
   character on the far side of the term, and Japanese and Chinese are written
   without one, so a boundary would match nothing at all. Korean has the spaces
   and glues particles on. The corpus really holds those rows -- 145 Korean and
   434 Japanese in the talent tracker on the day of the fix, one of the owner's
   four probe items reachable only through a Korean headline -- so this is not
   a hypothetical. Their behaviour is deliberately unchanged.
4. The dialect is PROVEN on the server, never assumed. MySQL 8 runs ICU and
   takes `\\b` while rejecting the POSIX `[[:<:]]` it used to require; 5.7 takes
   `[[:<:]]` and reads `\\b` as a literal `b`, which matches nothing and would
   empty the search box. alt_regexp_boundary_syntax() probes with BOTH a
   positive and a negative and falls back to plain substring when neither
   passes -- three states, and "it did not error" is not one of them.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB_PHP = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                      "includes", "db.php")
HARNESS = os.path.join(HERE, "fixtures", "search_boundary_harness.php")
PHP = shutil.which("php")

# (term, haystack, should_match)
MATCH_CASES = [
    # The defect, in the words that caused it.
    ("EY", "EY LLP confirmed the cuts", True),
    ("EY", "the company said money was tight", False),
    ("EY", "INE activa reclutamiento para encuestadores", False),
    ("EY", "a survey of Monterrey employers", False),
    ("EY", "EY's audit practice", True),
    ("ey", "Workday and EY both filed", True),        # case-insensitive
    ("GE", "GE Aerospace cut 200 jobs", True),
    ("GE", "the plant in Germany closed", False),
    ("BT", "BT Group said", True),
    ("BT", "there is no doubt about it", False),
    ("SAP", "SAP SE announced", True),
    ("SAP", "the sapphire plant", False),
    ("HP", "HP Inc", True),
    ("HP", "a champion sharpener", False),
    # What already worked must keep working.
    ("Workday", "Workday Inc said", True),
    ("workday", "Workday Inc said", True),
    ("Stripe", "Stripe laid off staff", True),
    ("Expedia", "Expedia Group", True),
    # Punctuation in a real employer name.
    ("AT&T", "AT&T cut jobs", True),
    ("H&M", "H&M closed stores", True),
    ("3M", "3M reduced headcount", True),
    # Non-Latin: substring, exactly as before.
    ("退任", "NHK、理事7人が異例の同時退任へ", True),
    ("사임", "트레이드 데스크(TTD), 이사 사임 및 감사", True),
    ("삼성", "삼성전자가 반도체 인력을 늘린다", True),
]


@unittest.skipIf(PHP is None,
                 "php is not on PATH, so the shipped search logic could not be "
                 "run. UNKNOWN, not a pass.")
class SearchBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        terms = ["EY", "Workday", "AT&T", "退任", "사임", "삼성", "NVIDIA 한국",
                 "", "   ", "...", "(EY)", "a.i.", "U.S. Steel", "3M"]
        payload = {"terms": terms,
                   "matches": [[t, h] for t, h, _ in MATCH_CASES]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(payload, fh)
            path = fh.name
        try:
            run = subprocess.run([PHP, HARNESS, DB_PHP, path],
                                 capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(path)
        if run.returncode != 0:
            raise AssertionError(f"the harness failed: {run.stderr[:2000]}")
        cls.out = json.loads(run.stdout)

    def test_the_defect_and_everything_that_already_worked(self):
        got = {(t, h): hit for t, h, hit in self.out["matches"]}
        for term, haystack, want in MATCH_CASES:
            self.assertEqual(got[(term, haystack)], want,
                             f"q={term!r} against {haystack!r}")

    def test_a_two_letter_name_gets_a_boundary_and_not_a_length_floor(self):
        """The wrong fix is `if (strlen($q) < 3) return nothing`. It reads as an
        honest empty result and silently deletes every two-letter employer."""
        self.assertEqual(self.out["patterns"]["EY"]["icu"], r"\bEY\b")
        self.assertEqual(self.out["patterns"]["EY"]["posix"], "[[:<:]]EY[[:>:]]")

    def test_a_non_latin_term_stays_a_substring_search(self):
        for term in ("退任", "사임", "삼성", "NVIDIA 한국"):
            for dialect in ("icu", "posix"):
                self.assertEqual(self.out["patterns"][term][dialect], "",
                                 f"{term} must not be boundary-matched")

    def test_an_unsupported_dialect_falls_back_rather_than_guessing(self):
        """alt_regexp_boundary_syntax() returns '' when the server proves
        neither syntax. Every term must then decline a pattern, so the caller
        runs the LIKE alone instead of a regex the engine misreads."""
        for term, patterns in self.out["patterns"].items():
            self.assertEqual(patterns["none"], "", term)

    def test_a_boundary_is_only_asserted_where_one_can_hold(self):
        """`\\b` against a bracket asserts a boundary between two non-word
        characters, which never holds, so `(EY)` would return nothing at all."""
        self.assertEqual(self.out["patterns"]["(EY)"]["icu"], r"\(EY\)")
        self.assertEqual(self.out["patterns"]["a.i."]["icu"], r"\ba\.i\.")

    def test_an_empty_or_punctuation_only_term_asks_for_no_regex(self):
        for term in ("", "   ", "..."):
            self.assertEqual(self.out["patterns"][term]["icu"], "", repr(term))

    def test_every_search_path_on_the_endpoint_uses_the_one_clause(self):
        """`q`, `company` and `keyword` are three public free-text paths and
        all three had the defect. A fourth added later must come through
        alt_freetext_clause() too, or it reintroduces it on its own."""
        with open(DB_PHP, encoding="utf-8") as fh:
            source = fh.read()
        where = source[source.index("function alt_db_where("):
                       source.index("function alt_db_prep(")]
        for param in ("'q'", "'company'", "'keyword'"):
            # The statement that opens with this parameter, up to its clause.
            start = where.index(f"get_param({param})")
            window = where[start:start + 400]
            self.assertIn("alt_freetext_clause", window,
                          f"the {param} search path is not boundary-matched")
            self.assertNotIn("LIKE %s", window.split("alt_freetext_clause")[0],
                             f"the {param} search path still builds a raw LIKE")

if __name__ == "__main__":
    unittest.main()
