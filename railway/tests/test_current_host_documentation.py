"""Current operating docs must name the current WordPress host.

Historical incident narratives may continue to name Bluehost. These narrow
assertions cover only present-tense orientation and recovery contracts, where
an old host name sends the next operator to the wrong place.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CurrentHostDocumentation(unittest.TestCase):
    def test_operator_orientation_names_chemicloud(self):
        for rel in ("AGENTS.md", "CLAUDE.md", "docs/RUNBOOK.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("ChemiCloud", text, rel)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("a WP plugin on Bluehost", agents)
        self.assertNotIn("a WP plugin on Bluehost", claude)

    def test_current_architecture_and_recovery_do_not_name_bluehost_as_live(self):
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        recovery = (ROOT / "docs/RECOVERY.md").read_text(encoding="utf-8")
        self.assertIn("WORDPRESS PLUGIN (ChemiCloud", architecture)
        self.assertNotIn("WORDPRESS PLUGIN (Bluehost", architecture)
        self.assertIn("The live copy** is MySQL on ChemiCloud", recovery)
        self.assertNotIn("The live copy** is MySQL on Bluehost", recovery)


if __name__ == "__main__":
    unittest.main()
