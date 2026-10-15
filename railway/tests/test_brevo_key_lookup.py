"""alt_brevo_key_lookup() reads the official Brevo plugin's stored v3 key.

The keyed backfill answered 503 "brevo api key not configured" on 2026-10-15
while the owner had the Brevo plugin connected. The lookup now also reads
`sib_api_key_v3` (string or array) after `sib_main_option`, and reports the
source NAME so the keyed stats payload can say where the key came from.
"""
import json
import os
import subprocess
import unittest
from shutil import which

HERE = os.path.dirname(__file__)
SRC = os.path.abspath(os.path.join(HERE, "..", "..", "wordpress-plugin",
                                   "ai-layoff-tracker", "includes", "brevo-sync.php"))
HARNESS = os.path.join(HERE, "fixtures", "brevo_key_harness.php")
PHP = which("php")


@unittest.skipUnless(PHP, "php not installed")
class BrevoKeyLookup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run([PHP, HARNESS, SRC], capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr or p.stdout
        cls.out = p.stdout
        cls.o = json.loads(p.stdout)

    def test_sources(self):
        exp = {"main_access": "sib_main_option.access_key",
               "main_api": "sib_main_option.api_key",
               "v3_string": "sib_api_key_v3",
               "v3_array": "sib_api_key_v3.access_key"}
        for case, src in exp.items():
            self.assertEqual(self.o[case]["source"], src)
            self.assertTrue(self.o[case]["found"], case)

    def test_absent_and_non_v3_are_empty(self):
        for case in ("none", "v2_only"):
            self.assertTrue(self.o[case]["empty"], case)
            self.assertEqual(self.o[case]["source"], "")

    def test_harness_output_never_carries_a_key(self):
        self.assertNotIn("xkeysib-", self.out)


if __name__ == "__main__":
    unittest.main()
