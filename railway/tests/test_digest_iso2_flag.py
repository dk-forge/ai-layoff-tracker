"""Every ISO 3166-1 alpha-2 code the digest can name renders a flag.

The 2026-11-09 talent daily printed Austro Panel d.o.o. (BA) and PhinCon (ID)
with no flag. Part of that was a missing country upstream; this pins the
other half: the flag is derived from the stored ISO2 code itself, so it no
longer depends on the country NAME also being a key of the region table
(which knew far fewer names than subscribe.php's ISO list, e.g. 'Aland
Islands', 'Kosovo'). Without php on PATH these SKIP, which is not a pass.
"""
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

from test_digest_talent_activity import PHP, SUBSCRIBE  # noqa: E402

INC = os.path.abspath(os.path.join(HERE, "..", "..", "wordpress-plugin",
                                   "ai-layoff-tracker", "includes"))
REGIONS_PHP = os.path.join(INC, "digest-regions.php")
BRIEFING_PHP = os.path.join(INC, "digest-talent-briefing.php")

_RUNNER = r"""
define('ABSPATH', '/tmp/');
require $argv[1];
$out = array();
foreach (json_decode($argv[2], true) as $c) $out[] = alt_digest_iso2_flag($c);
echo json_encode($out);
"""


def iso_codes():
    """The ISO2 keys of subscribe.php's alt_digest_iso2_country_name table."""
    src = open(SUBSCRIBE, encoding="utf-8").read()
    body = src.split("function alt_digest_iso2_country_name", 1)[1]
    body = body.split("\n}\n", 1)[0]
    return sorted(set(re.findall(r"'([A-Z]{2})'\s*=>", body)))


def expected(code):
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)


def run(codes):
    proc = subprocess.run([PHP, "-r", _RUNNER, "--", REGIONS_PHP, json.dumps(codes)],
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr[:1200] or proc.stdout[:1200])
    return json.loads(proc.stdout)


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class EveryIsoCodeHasAFlag(unittest.TestCase):

    def test_the_iso_list_is_the_full_table(self):
        self.assertGreaterEqual(len(iso_codes()), 240)

    def test_every_code_renders(self):
        codes = iso_codes()
        self.assertEqual(run(codes), [expected(c) for c in codes])

    def test_the_two_rows_from_the_9_nov_email(self):
        self.assertEqual(run(["BA", "ID", "ba", " id "]),
                         [expected("BA"), expected("ID")] * 2)

    def test_not_a_code_is_no_flag(self):
        # Never a made-up flag: blank, a name, a user-assigned code, junk.
        self.assertEqual(run(["", "Bosnia", "ZZ", "XX", "AA", "1A", "USA"]),
                         [""] * 7)

    def test_the_daily_line_takes_its_flag_from_the_code(self):
        src = open(BRIEFING_PHP, encoding="utf-8").read()
        line = src.split("function alt_talent_daily_line", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("alt_digest_iso2_flag($r['country']", line)


if __name__ == "__main__":
    unittest.main()
