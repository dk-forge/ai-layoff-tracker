"""ONE COUNTRY HAS ONE PUBLISHED LABEL.

Measured live on 2026-08-29, six labels for three countries:

    China                          17,790 jobs
    People's Republic of China          2
    South Korea                     3,987
    Korea                           1,197
    Türkiye                         2,200
    Turkey                          1,696

`alt_normalize_country` learned the China and Korea aliases on 2026-08-19 and
the split SURVIVED, for two separate reasons this test pins apart:

  1. Türkiye was never in the normalizer at all. The key-cleaner strips every
     non-ASCII letter, so 'Türkiye' arrives as 'trkiye', matched nothing, and
     fell through the raw-passthrough to become its own country.
  2. China and Korea WERE fixed, but normalizing new input does nothing to rows
     already stored, and `/cleanup` — the idempotent migration route written
     for exactly this — was never dispatched. Ten days later the old labels
     were still live.

So there are two guards here, because there were two failures:

  * the normalizer maps every spelling of a split pair to one label; and
  * `CountryIdentityInvariant` FAILS on live data that carries two labels for
    one country, which is what nothing did before. `country_coverage.py` sees
    the duplication and deliberately only reports it, and
    `CountryCoverageInvariant` passes because both spellings resolve through
    ALIASES to one classified entry. Reporting is not alarming.
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAILWAY = ROOT / "railway"
sys.path.insert(0, str(RAILWAY))

import country_coverage                                          # noqa: E402
import data_integrity as di                                      # noqa: E402

API_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/api.php").read_text()
PHP = shutil.which("php")

# spelling -> the single label it must normalize to.
PAIRS = {
    "Turkey": "Türkiye",
    "Türkiye": "Türkiye",
    "TURKIYE": "Türkiye",
    "turkiye": "Türkiye",
    "Republic of Türkiye": "Türkiye",
    "Korea": "South Korea",
    "South Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "China": "China",
    "People's Republic of China": "China",
    "PRC": "China",
    "Mainland China": "China",
}

# Must be left exactly alone: a real country whose name a careless alias would
# swallow, and the multi-country bucket.
UNTOUCHED = {
    "Germany": "Germany",
    "Czechia": "Czechia",
    "Netherlands": "Netherlands",
    "Trinidad and Tobago": "Trinidad and Tobago",
    "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    "Taiwan": "Taiwan",
    "India and US": "Multiple countries",
}


def _php_fn(name):
    start = API_PHP.index("function %s(" % name)
    i = API_PHP.index("{", start)
    depth, j = 0, i
    while j < len(API_PHP):
        if API_PHP[j] == "{":
            depth += 1
        elif API_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return API_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


@unittest.skipIf(PHP is None, "php CLI not available")
class TheNormalizerCollapsesEverySpelling(unittest.TestCase):

    def _normalize(self, names):
        src = _php_fn("alt_normalize_country")
        body = "\n".join(
            "echo alt_normalize_country(%s), \"\\n\";" % _q(n) for n in names)
        out = subprocess.run([PHP, "-r", src + "\n" + body],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.split("\n")[:len(names)]

    def test_split_pairs_collapse(self):
        names = list(PAIRS)
        for name, got in zip(names, self._normalize(names)):
            with self.subTest(name=name):
                self.assertEqual(got, PAIRS[name])

    def test_real_countries_are_untouched(self):
        names = list(UNTOUCHED)
        for name, got in zip(names, self._normalize(names)):
            with self.subTest(name=name):
                self.assertEqual(got, UNTOUCHED[name])

    def test_the_normalizer_agrees_with_the_coverage_register(self):
        """One definition of 'same country', not two that can drift apart.

        The register canonicalizes toward the endonym; if the normalizer chose
        the exonym, /cleanup would produce a label the register does not carry
        and CountryCoverageInvariant would start reporting an unclassified
        country. Türkiye is in REGISTER; Turkey is not.
        """
        for spelling, canonical in PAIRS.items():
            with self.subTest(spelling=spelling):
                self.assertEqual(
                    country_coverage.canonical(canonical), canonical,
                    "the normalizer's output %r is itself aliased by the "
                    "coverage register — the two disagree about the canonical "
                    "spelling" % canonical)


class _Ctx:
    """Minimal check_all context carrying one canned aggregate response."""

    def __init__(self, labels):
        self.errors = {}
        self._labels = labels

    def payload(self):
        return {"map_countries": [[name, jobs, 0, None, 0, 0]
                                  for name, jobs in self._labels]}


class TheInvariantFailsOnASplitIdentity(unittest.TestCase):

    def _run(self, labels):
        inv = di.CountryIdentityInvariant()
        ctx = _Ctx(labels)
        payload = ctx.payload()
        real = di._fetch_aggregate
        di._fetch_aggregate = lambda c, p: (payload, None, None, None)
        try:
            return inv.run(ctx)
        finally:
            di._fetch_aggregate = real

    def test_two_labels_for_one_country_fail(self):
        r = self._run([("China", 17790), ("People's Republic of China", 2),
                       ("United States", 6064192)])
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("China", r.detail)
        self.assertIn("People's Republic of China", r.detail)

    def test_the_live_2026_08_29_vocabulary_fails(self):
        r = self._run([("China", 17790), ("People's Republic of China", 2),
                       ("South Korea", 3987), ("Korea", 1197),
                       ("Türkiye", 2200), ("Turkey", 1696)])
        self.assertEqual(r.state, di.FAIL)
        self.assertEqual(r.observed, 3, "three countries were split, not %r" % r.observed)

    def test_a_clean_vocabulary_passes(self):
        r = self._run([("China", 17792), ("South Korea", 5184),
                       ("Türkiye", 3896), ("United States", 6064192),
                       ("Multiple countries", 4820439)])
        self.assertEqual(r.state, di.PASS, r.detail)
        self.assertEqual(r.observed, 0)

    def test_an_unreadable_aggregate_is_unknown_not_a_pass(self):
        for block in ({}, {"map_countries": []}, {"map_countries": "nope"}):
            with self.subTest(block=block):
                inv = di.CountryIdentityInvariant()
                real = di._fetch_aggregate
                di._fetch_aggregate = lambda c, p, b=block: (b, None, None, None)
                try:
                    r = inv.run(_Ctx([]))
                finally:
                    di._fetch_aggregate = real
                self.assertEqual(r.state, di.UNKNOWN)

    def test_the_invariant_is_registered(self):
        keys = [getattr(i, "key", None) for i in di.INVARIANTS]
        self.assertIn("country_identity", keys,
                      "an invariant nothing runs is decoration")


def _q(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


if __name__ == "__main__":
    unittest.main()
