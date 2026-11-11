"""The footer postal address is ONE config value (owner review 2026-11-11).

CAN-SPAM 15 U.S.C. 7704(a)(5) needs a valid physical postal address in every
commercial email. This fails when the value is empty or has no street or PO
box line, with ONE exception while the owner has not supplied the address:
the config names the open owner item (asktherecruiter-sandbox
docs/program_board/owner_items.json), so the gap is tracked, not hidden. Once
'street' is filled the exception closes by itself.
"""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import postal_address as pa  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


class PostalAddress(unittest.TestCase):

    def test_validator_rejects_empty_and_streetless(self):
        for bad in ("", "   ", "Netherlands", "AskTheRecruiter"):
            self.assertFalse(pa.has_street_line(bad), bad)
        for good in ("Postbus 1234", "PO Box 77", "P.O. Box 9", "Keizersgracht 123",
                     "123 Main Street"):
            self.assertTrue(pa.has_street_line(good), good)

    def test_configured_address_has_a_street_or_is_a_tracked_owner_item(self):
        cfg = pa.config()
        self.assertTrue(pa.postal_address(cfg).strip(" ."))
        if pa.has_street_line(cfg.get("street") or ""):
            return
        self.assertEqual(cfg.get("pending_owner_item"),
                         "Provide the postal address for email footers",
                         "No street or PO box line and no owner item tracking it.")

    def test_no_footer_hard_codes_the_address(self):
        hits = []
        for base in (ROOT / "wordpress-plugin", ROOT / "railway"):
            for f in base.rglob("*"):
                if f.suffix not in (".php", ".py") or "tests" in f.parts:
                    continue
                if re.search(r"AskTheRecruiter, Netherlands", f.read_text(encoding="utf-8", errors="ignore")):
                    hits.append(str(f.relative_to(ROOT)))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
