"""The claim matrix must agree with the registers it claims to derive from.

This is the lesson `generate_us_registry.py` taught on 2026-09-15: a generated
artifact with no generator on a schedule is born stale and nothing notices. The
committed matrix is a launch-facing statement about what may and may not be
published per country, so a drift between it and `country_coverage.py` is a
wrong claim, not a formatting nit.

Offline by construction: the module under test reads two committed Python
structures and writes Markdown. No socket, no model.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAILWAY = HERE.parent
sys.path.insert(0, str(RAILWAY))

import country_coverage as cc          # noqa: E402
import worldwide_claim_matrix as wcm   # noqa: E402


class CommittedMatrixIsCurrent(unittest.TestCase):
    def test_committed_file_matches_regeneration(self):
        """The whole point. --check is what CI would run."""
        self.assertTrue(wcm.OUT.exists(), f"{wcm.OUT} is missing")
        self.assertEqual(
            wcm.OUT.read_text(encoding="utf-8"),
            wcm.render(),
            "The committed claim matrix disagrees with country_coverage.py. "
            "Run: python3 railway/worldwide_claim_matrix.py --write",
        )

    def test_check_mode_agrees(self):
        self.assertEqual(wcm.main(["--check"]), 0)

    def test_every_register_country_appears(self):
        rows = wcm.build()
        self.assertEqual(
            {r["country"] for r in rows},
            set(cc.REGISTER),
            "a country in the register is missing from the matrix, or vice versa",
        )


class TheRuleItself(unittest.TestCase):
    """These pin the claim rule, not the rendering."""

    def test_only_employer_naming_countries_can_carry_recall(self):
        """The one rule the whole measurement programme rests on."""
        naming = set(wcm.naming_jurisdictions())
        for row in wcm.build():
            if row["tier"] == wcm.EVENT_RECALL:
                self.assertIn(
                    row["country"], naming,
                    f"{row['country']} is marked EVENT_RECALL but no register there "
                    "names the employer; only a named employer turns a total into "
                    "a set of identifiable events",
                )

    def test_a_refusal_outranks_a_known_aggregate(self):
        """A figure the publisher blocks is not ours to take, aggregate or not."""
        naming = wcm.naming_jurisdictions()
        entry = {"class": cc.REFUSED, "aggregate": "a complete quarterly series exists"}
        tier, _ = wcm.tier_for("Nowhere", entry, naming)
        self.assertEqual(tier, wcm.REFUSED)

    def test_an_aggregate_is_a_share_and_never_recall(self):
        tier, why = wcm.tier_for(
            "Nowhere", {"class": cc.REGIME_WITH_AGGREGATE}, {})
        self.assertEqual(tier, wcm.OFFICIAL_SHARE)
        self.assertNotIn("recall", why.lower())

    def test_no_regime_and_no_aggregate_both_land_in_discovery_only(self):
        for klass in (cc.REGIME_NO_AGGREGATE, cc.NO_REGIME):
            tier, _ = wcm.tier_for("Nowhere", {"class": klass}, {})
            self.assertEqual(tier, wcm.DISCOVERY_ONLY, klass)

    def test_a_naming_register_beats_a_bare_aggregate(self):
        naming = {"Nowhere": [{"jurisdiction": "Somewhere", "in_tracker": False}]}
        tier, _ = wcm.tier_for(
            "Nowhere", {"class": cc.REGIME_WITH_AGGREGATE}, naming)
        self.assertEqual(tier, wcm.EVENT_RECALL)

    def test_a_masked_identifier_register_does_not_count_as_naming(self):
        """Euskadi settled this by download: a masked CIF on 216 of 216 rows.

        `names_employers: False` must never reach EVENT_RECALL, or the matrix
        would promise a recall figure over a denominator with no identities.
        """
        for r in cc.PER_EMPLOYER_REGISTERS:
            if r.get("names_employers"):
                continue
            self.assertNotIn(
                r["jurisdiction"],
                [j["jurisdiction"]
                 for js in wcm.naming_jurisdictions().values() for j in js],
                f"{r['jurisdiction']} does not name employers and must not be "
                "treated as a recall-capable register",
            )


class TheDocumentSaysWhatItDoesNotKnow(unittest.TestCase):
    def test_it_does_not_publish_a_last_collection_time(self):
        """Source health and claim-type are different questions.

        Mixing them is how a stale collector and an unmeasurable country come
        to look alike on a dashboard. The document is ALLOWED to say in prose
        that it omits collection times -- that is the disclosure. What it must
        not do is carry one as DATA, so this checks the table rows, not the
        whole file.
        """
        rows = [ln for ln in wcm.render().splitlines()
                if ln.startswith("|") and not set(ln) <= set("|-: ")]
        self.assertTrue(rows, "no table rows rendered")
        for ln in rows:
            low = ln.lower()
            for phrase in ("last successful collection", "last collected", "checked_at"):
                self.assertNotIn(phrase, low,
                                 f"a table row carries {phrase!r} as data: {ln}")
            self.assertNotRegex(
                ln, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
                f"a table row carries a collection timestamp: {ln}")

    def test_it_states_the_recall_capable_count(self):
        n = wcm.counts()
        self.assertIn(f"**{n[wcm.EVENT_RECALL]} of ", wcm.render())

    def test_no_network_import(self):
        src = (RAILWAY / "worldwide_claim_matrix.py").read_text(encoding="utf-8")
        for bad in ("urlopen", "import requests", "socket."):
            self.assertNotIn(bad, src, f"the matrix generator must not {bad}")


if __name__ == "__main__":
    unittest.main()
