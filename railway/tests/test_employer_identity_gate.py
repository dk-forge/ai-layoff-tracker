"""AN EPITHET IS NOT AN EMPLOYER, AND "Unknown" IS NOT AN EMPLOYER EITHER.

Nothing checked that the stored `company` named a company. The extractor skips
a row only when the name is EMPTY, so whatever the headline called the employer
became an employer identity. On 2026-08-29 the live table published, among
others, "Automaker Giant" at 50,000 jobs — the largest 2026 event on the public
`leaders` list, cited to a Google News index record, with no country — while the
tracker separately held "Volkswagen Group", 50,000, the same 2026-03-10, from a
named DW report. One event, published twice, once anonymously.

`alt_is_anonymous_employer()` (includes/db.php) blocks these at the single write
choke point, `alt_db_upsert`. This test runs that PHP function directly.

The two halves matter equally and the SECOND is the dangerous one:

  * REJECT — every anonymised name that was actually live, plus siblings.
  * KEEP   — real employers that a careless rule would delete. "Carrier" is
    Carrier Global and has a legally filed WARN row; "Various Eateries" is a
    listed company whose name starts with a sentinel word; "Group 1 Automotive"
    and "General Motors" are made of words the vocabulary contains. A gate that
    silently deletes a real employer is a worse defect than the one it fixes.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PHP = (ROOT / "wordpress-plugin/ai-layoff-tracker/includes/db.php").read_text()

PHP = shutil.which("php")

# Names that must NEVER be stored. The first seven were live rows on 2026-08-29.
REJECT = [
    "Automaker Giant",
    "Unknown",
    "Auto-parts giant",
    "DTC storage firm",
    "Social media giant",
    # siblings of the same shape
    "Tech giant",
    "Retail chain",
    "the online retailer",
    "Pharma giant",
    "Semiconductor maker",
    "Streaming giant",
    "N/A",
    "Undisclosed",
    "not disclosed",
    "Unnamed company",
    "Confidential",
    "  Unknown  ",
    "UNKNOWN",
]

# Real employers the gate must never touch. Each is here because some plausible
# rule would have deleted it.
KEEP = [
    "Carrier",                  # single generic word, but Carrier Global (has a WARN row)
    "Various Eateries",         # starts with a sentinel word
    "General Motors",           # "general"/"motors" are near-generic
    "Group 1 Automotive",       # begins with a vocabulary word
    "Google parent",            # one real token is enough
    "Volkswagen Group",         # the identified twin of the row that caused this
    "Standard Chartered",
    "National Grid",
    "American Airlines",        # two words, one of them in the vocabulary
    "Global Payments",
    "US Steel",
    "Big Lots",
    "Public Storage",           # S&P 500; killed the first, over-broad vocabulary
    "National Storage Affiliates",
    "Retail Food Group",        # opens with a vocabulary word
    "Major Custom Assemblies, Inc.",
    "The GIANT Company, LLC.",  # a live WARN row: "giant" + "company", real employer
    "Deutsche Bank",
    "Banco Santander",
    "Türk Telekom",             # diacritics are part of a name, not noise
    "Energoremont - Bobov dol JSC",
    "Voice of America and its parent company",
]


def _php_fn(name):
    """Brace-matched source of one top-level `function <name>(` in db.php."""
    start = DB_PHP.index("function %s(" % name)
    i = DB_PHP.index("{", start)
    depth, j = 0, i
    while j < len(DB_PHP):
        if DB_PHP[j] == "{":
            depth += 1
        elif DB_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return DB_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


@unittest.skipIf(PHP is None, "php CLI not available")
class TheGateRejectsEpithetsAndKeepsEmployers(unittest.TestCase):

    def _verdicts(self, names):
        src = "\n".join(_php_fn(f) for f in (
            "alt_normalize_company_ws",
            "alt_anonymous_employer_sentinels",
            "alt_generic_employer_words",
            "alt_employer_legal_suffixes",
            "alt_is_anonymous_employer",
        ))
        cases = "\n".join(
            "echo alt_is_anonymous_employer(%s) ? \"1\\n\" : \"0\\n\";" % _q(n)
            for n in names
        )
        out = subprocess.run(
            [PHP, "-r", "%s\n%s" % (src, cases)],
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        lines = [l for l in out.stdout.splitlines() if l.strip() != ""]
        self.assertEqual(len(lines), len(names), out.stdout + out.stderr)
        return [l.strip() == "1" for l in lines]

    def test_anonymised_names_are_rejected(self):
        for name, blocked in zip(REJECT, self._verdicts(REJECT)):
            with self.subTest(name=name):
                self.assertTrue(
                    blocked,
                    "%r is not an employer identity and must not be stored" % name,
                )

    def test_real_employers_are_kept(self):
        for name, blocked in zip(KEEP, self._verdicts(KEEP)):
            with self.subTest(name=name):
                self.assertFalse(
                    blocked,
                    "%r is a real employer; the gate must never delete it" % name,
                )

    def test_empty_is_rejected(self):
        self.assertEqual(self._verdicts(["", "   "]), [True, True])


class TheGateIsWiredIntoTheOnlyWritePath(unittest.TestCase):
    """A predicate nothing calls is decoration.

    The call must sit inside alt_db_upsert — the single choke point every
    source funnels through — and not in one collector, where the next source
    would bypass it.
    """

    def test_upsert_blocks_an_anonymous_employer(self):
        body = _php_fn("alt_db_upsert")
        self.assertIn(
            "alt_is_anonymous_employer(", body,
            "alt_db_upsert must reject an anonymous employer; the gate is "
            "useless anywhere else because every source writes through here",
        )
        # It must block, not merely warn: the call has to guard a `return`.
        guard = re.search(
            r"if\s*\(\s*alt_is_anonymous_employer\([^)]*\)\s*\)\s*\{\s*return\b",
            body,
        )
        self.assertIsNotNone(
            guard, "the check must return early, not just log")


def _q(s):
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


if __name__ == "__main__":
    unittest.main()
