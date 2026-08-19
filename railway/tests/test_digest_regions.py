"""Every country the tracker holds sits in a named region, or in a stated one.

WHY A REGIONAL GROUPING EXISTS. The owner asked whether the digest's geography
should be worldwide, the United States, or both, and whether there should be a
regional breakdown. Both, as two headline figures, and yes. What it replaced
was a flat top five countries in which one line was the United States and the
other four were small, which is not a picture of the world.

WHY THIS TEST EXISTS. `alt_normalize_country()` returns an unrecognised single
country UNCHANGED rather than dropping it, which is right for the database and
means a region map can never be complete by construction. So the map is an
ALLOWLIST and the fallback is a stated "Elsewhere" line, never a guess at a
continent. This walks the vocabulary the live tracker actually serves and fails
on a name the map does not know, so the list is maintained by a failing test
rather than by somebody remembering.

THE VOCABULARY IS A COMMITTED SNAPSHOT AND NOT A LIVE FETCH. A test that reads
asktherecruiter.com is a test that goes red when the host does, and this one has
nothing to say about the host. The snapshot is the /facets country list read on
2026-08-19; refresh it when a collector starts producing a country nobody here
has seen, which is exactly when this test should fail first.

WHAT IS DELIBERATELY REFUSED. "Multiple countries" is the stored bucket for a
cross-border cut announced with no per-country split. It has no job location, so
folding it into a region would invent one and double-count the jobs against the
region that really holds them. It maps to nothing and gets a line of its own.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
PHP = shutil.which("php")

# /wp-json/layoffs/v1/facets, countries[], read 2026-08-19.
VOCABULARY = (
    "Argentina", "Australia", "Austria", "Bangladesh", "Belgium",
    "Bosnia and Herzegovina", "Botswana", "Brazil", "Bulgaria", "Cambodia",
    "Canada", "Chile", "China", "Colombia", "Croatia", "Cyprus", "Czechia",
    "Denmark", "Estonia", "Finland", "France", "Germany", "Greece",
    "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Ireland",
    "Isle of Man", "Israel", "Italy", "Japan", "Jersey", "Kenya", "Korea",
    "Kuwait", "Latvia", "Lithuania", "Luxembourg", "Malaysia", "Malta",
    "Mexico", "Morocco", "Multiple countries", "Netherlands", "New Zealand",
    "Nigeria", "Norway", "Pakistan", "People's Republic of China", "Peru",
    "Philippines", "Poland", "Portugal", "Romania", "Serbia", "Singapore",
    "Slovakia", "Slovenia", "South Africa", "South Korea", "Spain",
    "Sri Lanka", "Sweden", "Switzerland", "Taiwan", "Thailand", "Türkiye",
    "United Kingdom", "United States", "Uruguay", "Vietnam",
)

_WANTED = ("alt_digest_region_of", "alt_digest_region_order", "alt_digest_lower")

_RUNNER = r"""
$src = file_get_contents($argv[1]);
foreach (explode(',', $argv[2]) as $name) {
    if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                    $src, $m)) {
        fwrite(STDERR, "could not extract $name from subscribe.php\n");
        exit(2);
    }
    eval($m[0]);
}
$in = json_decode($argv[3], true);
$out = array('order' => alt_digest_region_order(), 'map' => array());
foreach ($in as $country) { $out['map'][$country] = alt_digest_region_of($country); }
echo json_encode($out);
"""


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EveryCountryIsPlacedOrStated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                             encoding="utf-8")
        try:
            handle.write("<?php\n" + _RUNNER)
            handle.close()
            probe = list(VOCABULARY) + ["Atlantis", "", "  ", "united states"]
            run = subprocess.run(
                [PHP, handle.name, SUBSCRIBE, ",".join(_WANTED),
                 json.dumps(probe)],
                capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(handle.name)
        assert run.returncode == 0, run.stderr or run.stdout
        out = json.loads(run.stdout)
        cls.map = out["map"]
        cls.order = out["order"]

    def test_every_country_the_tracker_serves_has_a_region(self):
        unmapped = sorted(c for c in VOCABULARY
                          if c != "Multiple countries" and not self.map[c])
        self.assertEqual(
            unmapped, [],
            "these countries would be filed under a stated 'Elsewhere' line "
            "rather than a region. That is the honest fallback and not a bug, "
            "but it is also this test asking you to place them: add each to "
            "alt_digest_region_of() in includes/subscribe.php")

    def test_the_bucket_is_refused_rather_than_placed(self):
        """A cross-border cut has no job location. Folding it into APAC or
        Europe would invent one and double-count the jobs."""
        self.assertEqual(self.map["Multiple countries"], "")

    def test_an_unknown_country_is_not_guessed_at(self):
        self.assertEqual(self.map["Atlantis"], "",
                         "the map guessed a continent for a name it does not "
                         "know, which is worse than saying Elsewhere")

    def test_nothing_at_all_is_nothing_at_all(self):
        self.assertEqual(self.map[""], "")
        self.assertEqual(self.map["  "], "")

    def test_the_match_is_case_insensitive(self):
        """The country column is freeform before alt_normalize_country() and
        a case difference must not cost a region."""
        self.assertEqual(self.map["united states"], "United States")

    def test_the_united_states_is_first_in_the_printed_order(self):
        """It is the stated first priority and it is already a headline above,
        so a reader should not have to hunt a ranked list for it."""
        self.assertEqual(self.order[0], "United States")

    def test_every_region_the_map_produces_is_in_the_printed_order(self):
        """A region the map can emit and the order does not name would be
        silently dropped from the table, and its jobs with it."""
        produced = {r for r in self.map.values() if r}
        missing = sorted(produced - set(self.order))
        self.assertEqual(missing, [],
                         f"these regions are emitted and never printed: "
                         f"{missing}")

    def test_the_united_kingdom_line_means_the_united_kingdom(self):
        """Jersey, Guernsey and the Isle of Man are Crown Dependencies and not
        part of it. The first render of this block printed a line labelled
        'United Kingdom' whose only member was Jersey."""
        self.assertEqual(self.map["United Kingdom"], "United Kingdom")
        for crown in ("Jersey", "Isle of Man"):
            self.assertEqual(self.map[crown], "Europe", crown)

    def test_both_spellings_of_china_and_korea_land_together(self):
        """The vocabulary carries two of each, because the collectors do."""
        self.assertEqual(self.map["China"],
                         self.map["People's Republic of China"])
        self.assertEqual(self.map["Korea"], self.map["South Korea"])


if __name__ == "__main__":
    unittest.main()
