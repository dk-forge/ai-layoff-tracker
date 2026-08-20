"""Guards for the deliberately non-publishing Companies House adapter."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

from sources.companies_house import fetch_registered_identity, public_profile_url


class _Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: self.payload)


class CompaniesHouseIdentityTests(unittest.TestCase):
    def test_exact_number_yields_source_linked_identity_candidate(self):
        session = _Session({
            "company_name": "Example Ltd",
            "company_status": "active",
            "jurisdiction": "england-wales",
            "registered_office_address": {"country": "England"},
        })
        row = fetch_registered_identity("00000006", "test-key", session=session)
        self.assertEqual(row["company_number"], "00000006")
        self.assertEqual(row["registered_office_country"], "England")
        self.assertEqual(row["source_url"], public_profile_url("00000006"))
        self.assertIn("not evidence of employer domicile", row["scope"])
        self.assertNotIn("employer_country", row)
        self.assertEqual(session.calls[0][1]["auth"], ("test-key", ""))

    def test_rejects_fuzzy_company_names(self):
        with self.assertRaisesRegex(ValueError, "company_number"):
            public_profile_url("Example Ltd")


if __name__ == "__main__":
    unittest.main()
