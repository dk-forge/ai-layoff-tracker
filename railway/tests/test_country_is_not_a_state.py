"""A US state may not sit in the country column.

THE DEFECT, FOUND BY THE OWNER IN A DELIVERED EMAIL, 2026-08-18.

    Where the jobs were
    ... counted where the jobs were rather than where the employer is based.
      United States    365 jobs
      North Carolina     1 job

North Carolina is not a country. It was a bad ROW rather than a bad render:
the digest reads /aggregate's `top_countries`, which is a GROUP BY on the
`country` column, and the column really held the string. Confirmed live the
same day on the successor case, id 134152, Vestis Services LLC, an NC WARN
notice whose site is in Lexington KY, stored with state "NC" and country
"Kentucky".

WHY NOTHING STOPPED IT. Every write path normalises through
alt_normalize_country(), and that function's documented rule was "unknown
single countries are returned unchanged (never lose data)". Right for a
country nobody thought to map. Wrong for a value that is not a country at all.
The row entered through /edit, the one path a human drives; no collector can
produce it (warn.py, warn_custom.py and erm_import.py all hard-code a country)
and /enrich-context writes only employer_country. "Only a human can do it" is
not a guard, so the guard is now in the normaliser, where every path already
goes: /add, /bulk, /edit, the re-normalise migration AND the country FILTER,
so a reader who filters on "Kentucky" is answered with the United States rows
rather than a dead facet.

FILTERING AT RENDER WOULD HAVE BEEN THE WRONG FIX. The digest would have
looked right while the tracker page's country dropdown, the exports, the facet
pages and the public API all kept serving the state. One wrong value, five
surfaces.

The function touches no WordPress API, so it is extracted from api.php and
evaluated rather than the plugin being booted. Without php on PATH these SKIP,
which is not a pass.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes",
                   "api.php")
PHP = shutil.which("php")

_RUNNER = r"""
$src = file_get_contents($argv[1]);
if (!preg_match('/\nfunction alt_normalize_country\s*\(.*?\n\}/s', $src, $m)) {
    fwrite(STDERR, "could not extract alt_normalize_country from api.php\n");
    exit(2);
}
eval($m[0]);
$out = array();
foreach (json_decode($argv[2], true) as $value) {
    $out[] = alt_normalize_country($value);
}
echo json_encode($out);
"""


def normalize(values):
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write("<?php\n" + _RUNNER)
        handle.close()
        run = subprocess.run([PHP, handle.name, API, json.dumps(list(values))],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"php runner failed: {run.stderr[:1200]}")
    return dict(zip(values, json.loads(run.stdout)))


STATES = (
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Hawaii",
    "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin",
    "Wyoming",
)


@unittest.skipUnless(PHP, "php is not on PATH")
class NoUSStateSurvivesAsACountry(unittest.TestCase):

    def test_every_state_folds_to_the_united_states(self):
        out = normalize(STATES)
        for state in STATES:
            with self.subTest(state=state):
                self.assertEqual(out[state], "United States")

    def test_the_two_the_owner_actually_saw(self):
        out = normalize(("North Carolina", "Kentucky"))
        self.assertEqual(out["North Carolina"], "United States")
        self.assertEqual(out["Kentucky"], "United States")

    def test_a_state_annotated_united_states_folds(self):
        """THE SUCCESSOR CASE, LIVE 2026-08-28. Row 134117 (Conduent, in the
        Idaho WARN register) carried country "United States (NJ)": the cleaner
        reduces it to "united states nj", which is neither a state name nor a
        mapped country, so the unknown-single-country rule let it through to
        the country facet and the coverage register refused it as a country.
        Every annotation shape that cleans to "united states <state>" folds."""
        out = normalize(("United States (NJ)", "United States (New Jersey)",
                         "United States - NJ", "United States, Idaho",
                         "united states of america (CA)"))
        for value in out:
            with self.subTest(value=value):
                self.assertEqual(out[value], "United States")

    def test_the_annotated_georgia_is_the_state(self):
        # Bare "Georgia" stays a country (see below); "United States (GA)"
        # names the union first, so the suffix can only mean the state.
        self.assertEqual(normalize(("United States (GA)",))["United States (GA)"],
                         "United States")

    def test_annotated_territories_and_usvi_are_left_alone(self):
        # Same territory judgement as the bare list: PR/GU/VI/AS/MP are not
        # folded, and the USVI's own name is not a state annotation.
        out = normalize(("United States Virgin Islands", "United States (PR)",
                         "United States (Guam)"))
        for value in out:
            with self.subTest(value=value):
                self.assertEqual(out[value], value)

    def test_case_and_spacing_do_not_get_a_state_through(self):
        out = normalize(("north carolina", "  NORTH   CAROLINA  ",
                         "New  York", "district of columbia"))
        for value in out:
            with self.subTest(value=value):
                self.assertEqual(out[value], "United States")


@unittest.skipUnless(PHP, "php is not on PATH")
class TheGuardCostsNoRealCountry(unittest.TestCase):

    def test_georgia_is_left_alone_because_it_is_a_country(self):
        """THE ONE COLLISION, AND IT IS DELIBERATE.

        Georgia is a US state and a sovereign country. Folding it would lose a
        country to save a state, and in a column whose job is to name countries
        the country is the more likely meaning. A US-Georgia row is caught by
        its `state` column instead. Do not "complete" the list later without
        reading this.
        """
        self.assertEqual(normalize(("Georgia",))["Georgia"], "Georgia")

    def test_territories_are_left_alone(self):
        """Puerto Rico and Guam are routinely counted as their own
        jurisdictions. Calling one "United States" here would be a judgement,
        not a normalisation, so they are not in the list."""
        out = normalize(("Puerto Rico", "Guam"))
        self.assertEqual(out["Puerto Rico"], "Puerto Rico")
        self.assertEqual(out["Guam"], "Guam")

    def test_the_existing_vocabulary_still_behaves(self):
        out = normalize(("US", "usa", "UK", "England", "Global", "EMEA",
                         "India and US", "UK/Germany", "Trinidad and Tobago",
                         "Bosnia and Herzegovina", "Brazil", ""))
        self.assertEqual(out["US"], "United States")
        self.assertEqual(out["usa"], "United States")
        self.assertEqual(out["UK"], "United Kingdom")
        self.assertEqual(out["England"], "United Kingdom")
        self.assertEqual(out["Global"], "Multiple countries")
        self.assertEqual(out["EMEA"], "Multiple countries")
        self.assertEqual(out["India and US"], "Multiple countries")
        self.assertEqual(out["UK/Germany"], "Multiple countries")
        self.assertEqual(out["Trinidad and Tobago"], "Trinidad and Tobago")
        self.assertEqual(out["Bosnia and Herzegovina"], "Bosnia and Herzegovina")
        self.assertEqual(out["Brazil"], "Brazil")
        self.assertEqual(out[""], "")

    def test_an_unknown_country_is_still_returned_unchanged(self):
        """The rule the guard narrows, not the rule it replaces."""
        out = normalize(("Ruritania", "Kiribati"))
        self.assertEqual(out["Ruritania"], "Ruritania")
        self.assertEqual(out["Kiribati"], "Kiribati")


if __name__ == "__main__":
    unittest.main()
