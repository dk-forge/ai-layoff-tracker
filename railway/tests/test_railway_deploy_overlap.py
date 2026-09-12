"""The daily collector must survive a code deployment while it is running."""

from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "railway" / "railway.toml"


class RailwayDeployOverlapTests(unittest.TestCase):
    def test_overlap_covers_the_longest_gdelt_budget_and_closeout(self):
        """A new deploy must not SIGTERM a maximum sweep or its closeout."""
        text = CONFIG.read_text(encoding="utf-8")
        match = re.search(r'^\s*overlapSeconds\s*=\s*(\d+)\s*$', text, re.M)
        self.assertIsNotNone(
            match,
            "railway.toml must retain the previous deployment using Railway's numeric overlapSeconds type",
        )
        parsed = tomllib.loads(text)
        self.assertIsInstance(parsed["deploy"]["overlapSeconds"], int)
        self.assertGreaterEqual(
            parsed["deploy"]["overlapSeconds"],
            7200,
            "overlap must cover the one-hour GDELT budget plus downstream closeout",
        )


if __name__ == "__main__":
    unittest.main()
