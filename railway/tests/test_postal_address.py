"""The footer postal address is ONE config value (owner review 2026-11-11).

CAN-SPAM 15 U.S.C. 7704(a)(5) needs a valid physical postal address in every
commercial email. This fails when the value is empty or has no street or PO
box line, and pins the owner-approved address (DECISIONS 2026-11-13).
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

    def test_configured_address_is_the_business_postal_mailbox(self):
        # DECISIONS 2026-11-13 (asktherecruiter-sandbox): Postadres Nederland
        # mailbox, a public business address; not a home or visiting address.
        cfg = pa.config()
        self.assertTrue(pa.has_street_line(cfg.get("street") or ""))
        self.assertEqual(cfg["street"], "Torenlaan 5")
        self.assertEqual(pa.postal_address(cfg),
                         "Ask The Recruiter, Torenlaan 5, 1402 AT Bussum, Netherlands.")

    def test_no_pending_owner_item_is_left_in_the_config(self):
        cfg = pa.config()
        self.assertNotIn("pending_owner_item", cfg)
        self.assertNotIn("pending", cfg.get("_why", "").lower())

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
