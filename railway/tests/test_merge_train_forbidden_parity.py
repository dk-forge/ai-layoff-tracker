"""The train's forbidden list must never fall behind the healer's.

`.github/merge-train.json` says, in its own `_forbidden` note, that this test
exists and that it "fails if self_heal grows an entry this list does not have".
It did not exist. A config that advertises a guard it does not have is the same
defect class as a `meta{}` label for a collector nobody built: the claim is the
thing people rely on, and nothing was checking it.

WHY THE TWO LISTS ARE RELATED BUT NOT EQUAL. `self_heal.FORBIDDEN` names what an
automated HEALER may not edit. The train's `forbidden_paths` names what it may
not merge a mechanical resolution into, and it is deliberately WIDER: it also
holds the reference sets, the correction specs and the two learning-state files,
which a healer never writes but which a conflict resolution must never touch.

So the direction is the assertion. Every healer entry must appear in the train's
list; the train may hold more, and each extra is fine by construction. An entry
added to the healer and not to the train is the drift this catches, and it is a
one-line change in a file nobody would think to open.
"""
import json
import sys
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parent.parent
ROOT = RAILWAY.parent
sys.path.insert(0, str(RAILWAY))

import self_heal  # noqa: E402

CONFIG = ROOT / ".github" / "merge-train.json"


class ForbiddenParity(unittest.TestCase):

    def setUp(self):
        self.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.train = set(self.cfg["forbidden_paths"])
        self.healer = set(self_heal.FORBIDDEN)

    def test_every_healer_entry_is_forbidden_to_the_train(self):
        missing = sorted(self.healer - self.train)
        self.assertEqual(
            missing, [],
            "these paths are forbidden to the healer but not to the merge "
            "train, so the train could carry a mechanical resolution into one "
            "of them: %s. Add them to forbidden_paths in %s."
            % (missing, CONFIG.name))

    def test_the_train_is_allowed_to_be_wider(self):
        """Stated rather than assumed, so a future session does not 'fix' the
        asymmetry by deleting the train's extra entries."""
        self.assertTrue(self.train - self.healer)

    def test_the_config_names_this_file(self):
        """The note that sent me here must keep pointing at something real."""
        self.assertIn(Path(__file__).name, CONFIG.read_text(encoding="utf-8"))

    def test_neither_list_is_empty(self):
        """An empty list on either side would pass the parity check while
        forbidding nothing at all."""
        self.assertTrue(self.healer)
        self.assertTrue(self.train)


if __name__ == "__main__":
    unittest.main()
