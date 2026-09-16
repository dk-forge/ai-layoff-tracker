"""Guards for entity_resolution -- "are these two names one employer?".

THE KEEP-APART HALF IS THE ONE THAT MATTERS, and it is not symmetric with the
should-join half, for the reason test_company_bucket_key.py states about
bucketing: a missed duplicate leaves a visible, countable, reversible row on
the tracker, and a false one feeds a guard that sends a human to delete a row
nobody can get back. So every pair below that must stay apart is a real pair
read out of the live corpus on 2026-09-16, not an invention.

The PHP mirror test is the two-copies-drifted guard: alt_canonical_company()
in the plugin is the alias map of record, and a pair added there and not here
is a fold the Python side silently stops making.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import entity_resolution as er  # noqa: E402

API_PHP_PATH = ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php"
API_PHP = API_PHP_PATH.read_text(encoding="utf-8")
PHP = shutil.which("php")


def _php_company_keys(names):
    """alt_company_key() as the SERVER computes it, for the names given."""
    code = (
        "$src = file_get_contents($argv[1]);"
        "foreach (['alt_company_key','alt_canonical_company','alt_nonlatin_company_alias'] as $fn) {"
        "  $start = strpos($src, \"function $fn(\");"
        "  if ($start === false) { fwrite(STDERR, \"missing $fn\"); exit(2); }"
        "  $end = strpos($src, \"\\n}\\n\", $start);"
        "  eval(substr($src, $start, $end - $start + 3)); }"
        "$out = [];"
        "foreach (json_decode($argv[2]) as $n) { $out[$n] = alt_company_key($n); }"
        "echo json_encode($out);")
    run = subprocess.run([PHP, "-r", code, str(API_PHP_PATH), json.dumps(names)],
                         capture_output=True, text=True, timeout=60)
    if run.returncode != 0:
        raise AssertionError(f"php failed: {run.stderr[:800]}")
    return json.loads(run.stdout)


#: Real pairs from the live corpus that MUST resolve to one employer.
SHOULD_JOIN = [
    # The 2026-09-07/08 incident, all four spellings of one 4,000-job event.
    ("Jaguar Land Rover", "JLR", "the trading name"),
    ("Jaguar Land Rover", "Tata Motors’ JLR", "the parent's possessive, curly apostrophe"),
    ("Jaguar Land Rover", "捷豹路虎", "the Chinese name"),
    ("JLR", "捷豹路虎", "trading name against the Chinese name"),
    ("JLR", "Tata Motors' JLR", "straight apostrophe"),
    # Other live clusters the same sweep found.
    ("Supermassive Games", "Supermassive", "a dropped trailing word"),
    ("Samsung", "Samsung India", "a country subsidiary"),
    ("Swiss Post", "Post", "a dropped qualifier"),
    ("Department of Public Works", "Department of Public Works and Highways", "a clipped title"),
    # Already folded by the plugin's own alias map.
    ("Google", "Alphabet", "alias map: subsidiary to parent"),
    ("Facebook", "Meta Platforms, Inc.", "alias map plus a legal form"),
]

#: Real pairs from the live corpus that MUST NOT resolve to one employer.
SHOULD_STAY_APART = [
    ("Tata Steel", "Tata Motors", "two Tata companies, both in the corpus"),
    ("Tata Steel", "Tata Consultancy Services", "same group, different employers"),
    ("Jaguar Land Rover", "Jaguar Health", "a different company that starts the same"),
    ("Trinity Health", "Trinity Industries", "a shared weak head word"),
    ("General Motors", "General Electric", "a shared weak head word"),
    ("Bank of America", "Bank of Ireland", "a shared weak head word"),
    ("Mercer International", "Mercedes", "neither contains nor initialises the other"),
    ("BBC", "BBC Studios" , "PLACEHOLDER"),
]
# BBC/BBC Studios is a genuine judgement call, not a keep-apart: it is removed
# from the list rather than asserted either way, because the corpus holds it as
# one employer's two filings and the module has no evidence to rule on it.
SHOULD_STAY_APART = [p for p in SHOULD_STAY_APART if p[2] != "PLACEHOLDER"]


class TheNamesOneEmployerCanWear(unittest.TestCase):

    def test_every_should_join_pair_joins(self):
        for a, b, why in SHOULD_JOIN:
            with self.subTest(pair=(a, b)):
                self.assertTrue(er.same_entity(a, b), f"{a!r} vs {b!r}: {why}")
                self.assertTrue(er.why_same_entity(a, b), "a join must name its rule")

    def test_it_is_symmetric(self):
        for a, b, _ in SHOULD_JOIN:
            self.assertEqual(er.same_entity(a, b), er.same_entity(b, a), f"{a!r}/{b!r}")


class TheNamesThatMustStayApart(unittest.TestCase):

    def test_every_keep_apart_pair_stays_apart(self):
        for a, b, why in SHOULD_STAY_APART:
            with self.subTest(pair=(a, b)):
                self.assertFalse(er.same_entity(a, b), f"{a!r} vs {b!r}: {why}")
                self.assertEqual("", er.why_same_entity(a, b))

    def test_an_unresolvable_name_is_never_a_match(self):
        """A name the module cannot normalise answers False, not "probably".

        An unknown CJK name has no key at all -- alt_company_key strips it to
        the empty string -- and an empty key must never match another empty
        key, or every unreadable name in the corpus becomes one employer.
        """
        self.assertEqual("", er.entity_key("トヨタ自動車"))
        self.assertFalse(er.same_entity("トヨタ自動車", "東京電力"))
        self.assertFalse(er.same_entity("", ""))
        self.assertFalse(er.same_entity(None, None))

    def test_a_bare_generic_word_never_carries_a_containment_match(self):
        for a, b in (("Health", "Trinity Health"), ("Motors", "Tata Motors"),
                     ("City", "City of Austin")):
            self.assertFalse(er.same_entity(a, b), f"{a!r} inside {b!r}")


class TheInitialismRule(unittest.TestCase):

    def test_it_reads_the_initials_and_nothing_looser(self):
        self.assertTrue(er.same_entity("International Business Machines", "IBM"))
        self.assertFalse(er.same_entity("International Business Machines", "IBX"))
        # One letter is not an initialism, it is a coincidence.
        self.assertFalse(er.same_entity("Jaguar Land Rover", "J"))


class ThePhpMapIsMirrored(unittest.TestCase):
    """alt_canonical_company() is the map of record; drift fails here."""

    @staticmethod
    def _php_pairs():
        body = API_PHP.split("function alt_canonical_company(")[1].split("\n}\n")[0]
        return dict(re.findall(r"'([^']+)'\s*=>\s*'([^']+)'", body))

    def test_the_php_map_is_not_empty(self):
        """A parse that silently found nothing would make this whole case
        vacuous, which is the failure mode the mirror exists to prevent."""
        self.assertGreater(len(self._php_pairs()), 30)

    def test_every_php_alias_is_folded_the_same_way_here(self):
        missing = {k: v for k, v in self._php_pairs().items()
                   if er.ALIASES.get(k) != v}
        self.assertFalse(missing, (
            "alt_canonical_company() folds these pairs and entity_resolution.ALIASES "
            f"does not: {sorted(missing)}. Mirror them, or the Python guards stop "
            "seeing a fold the plugin makes."))


@unittest.skipUnless(PHP, "php binary not available")
class ThePluginAgreesWithThisModule(unittest.TestCase):
    """The server's key and this module's key are one opinion, not two.

    THE FOLD HAS TO HAPPEN ON THE SERVER TOO, or the guard reports a duplicate
    every week and nothing upstream stops the next one being created. The
    Python side detects; alt_company_key() is what makes the incoming report
    fuzzy-match the row that already exists.
    """

    JLR = ["Jaguar Land Rover", "JLR", "Tata Motors\u2019 JLR", "\u6377\u8c79\u8def\u864e"]

    def test_all_four_live_spellings_share_one_server_key(self):
        keys = _php_company_keys(self.JLR)
        self.assertEqual({"jaguar land rover"}, set(keys.values()), keys)

    def test_the_server_key_and_the_python_key_agree(self):
        for name, php_key in _php_company_keys(
                self.JLR + ["Tata Steel", "Tata Motors", "Amazon.com, Inc.", "Google"]).items():
            self.assertEqual(php_key, er.entity_key(name), name)

    def test_a_non_latin_name_the_lists_do_not_know_still_has_no_key(self):
        """Unchanged behaviour, stated: the strip empties it, and an empty key
        matches nothing. That is the honest state, not a defect to paper over."""
        unknown = "\u6771\u4eac\u96fb\u529b"
        self.assertEqual("", _php_company_keys([unknown])[unknown])
        self.assertEqual("", er.entity_key(unknown))


if __name__ == "__main__":
    unittest.main()
