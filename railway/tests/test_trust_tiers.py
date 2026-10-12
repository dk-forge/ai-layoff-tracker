"""Trust tiers: verified / reported / measured (owner-approved names, 2026-10-11).

Offline. Runs the REAL includes/trust-tiers.php through the php CLI.

Pinned:
  * every source_type/verification_level the code writes maps to a tier,
    table-driven from docs/VERIFICATION_TIERS.md's own mapping;
  * a news-only row (or press release, Eurofound ERM, empty, unknown) can
    never be verified, whatever its verification_level says;
  * a layoff row is never "measured" (a measured item is never a layoff event);
  * the SQL CASE used by the tier filter/aggregate agrees with the PHP mapper;
  * /query rows, /aggregate (opt-in `tiers` block) and /facets expose tier,
    and the `tier` filter is wired into alt_db_where;
  * the tracker card renders a plain-text tier label with an accessible name
    and no em-dash.
"""
import itertools
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
INC = PLUGIN / "includes/trust-tiers.php"
PHP = shutil.which("php")

SOURCE_TYPES = ["8K", "8k", "warn", "federal_rif", "filing", "news", "press_release",
                "erm", "", "gdelt", "something_new"]
LEVELS = ["gold", "warn", "silver", "bronze", "", "platinum"]

# (source_type, verification_level) -> tier, for every pair the collectors write.
TABLE = [
    ("8K", "gold", "verified"),          # sources/edgar.py
    ("warn", "warn", "verified"),        # sources/warn.py, quebec, wup_mazowieckie
    ("warn", "gold", "verified"),        # sources/warn_mn_letters.py
    ("federal_rif", "warn", "verified"), # sources/federal_layoffs.py
    ("filing", "gold", "verified"),      # foreign_filings_ingest.py (pre-coercion)
    ("press_release", "silver", "reported"),
    ("erm", "silver", "reported"),
    ("news", "bronze", "reported"),
    ("news", "gold", "reported"),        # coerced foreign filing: conservative
    ("8K", "bronze", "reported"),        # official type but downgraded level
    ("", "", "reported"),
]


def php(code):
    out = subprocess.run([PHP, "-r", f"require '{INC}'; {code}"],
                         capture_output=True, text=True, check=True)
    return out.stdout


def tiers_for(pairs):
    payload = json.dumps(pairs)
    return json.loads(php(
        f"$o=array(); foreach (json_decode('{payload}', true) as $p) "
        "{ $o[] = alt_trust_tier($p[0], $p[1]); } echo json_encode($o);"))


@unittest.skipUnless(PHP, "php CLI not installed")
class MapperTest(unittest.TestCase):
    def test_table(self):
        got = tiers_for([[s, l] for s, l, _ in TABLE])
        self.assertEqual(got, [t for _, _, t in TABLE])

    def test_news_only_never_verified(self):
        pairs = [[s, l] for s in ["news", "press_release", "erm", "", "gdelt", "something_new"]
                 for l in LEVELS]
        self.assertNotIn("verified", tiers_for(pairs))

    def test_layoff_row_never_measured(self):
        pairs = [list(p) for p in itertools.product(SOURCE_TYPES, LEVELS)]
        self.assertTrue(set(tiers_for(pairs)) <= {"verified", "reported"})

    def test_vocabulary(self):
        self.assertEqual(json.loads(php("echo json_encode(alt_trust_tiers());")),
                         ["verified", "reported", "measured"])

    def test_sql_case_matches_mapper(self):
        sql = php("echo alt_trust_tier_sql('l.');")
        self.assertIn("l.source_type", sql)
        self.assertIn("l.verification_level", sql)
        self.assertNotIn("measured", sql)
        # Every official type in the SQL is one the mapper verifies.
        for t in ("8K", "warn", "federal_rif", "filing"):
            self.assertIn(f"'{t}'", sql)
        for t in ("news", "press_release", "erm"):
            self.assertNotIn(f"'{t}'", sql)

    def test_doc_lists_every_written_value(self):
        doc = (ROOT / "docs/VERIFICATION_TIERS.md").read_text()
        for v in ["8K", "warn", "federal_rif", "filing", "news", "press_release", "erm",
                  "gold", "silver", "bronze"]:
            self.assertIn(f"`{v}`", doc)


class WiringTest(unittest.TestCase):
    def test_routes_expose_tier(self):
        db = (PLUGIN / "includes/db.php").read_text()
        self.assertIn("'tier'", db)                 # row output + filter param
        self.assertIn("alt_trust_tier_sql(", db)    # filter + aggregate use one SQL
        self.assertIn("'tiers'", db)                # facets + aggregate block

    def test_loaded_guarded(self):
        main = (PLUGIN / "ai-layoff-tracker.php").read_text()
        self.assertIn("includes/trust-tiers.php", main)

    def test_card_badge_accessible_no_em_dash(self):
        js = (PLUGIN / "assets/layoffs.js").read_text()
        i = js.index("function tierBadge")
        body = js[i:js.index("\n    }\n", i)]
        self.assertIn("aria-label", body)
        self.assertNotIn("—", body)
        self.assertIn("tierBadge(row) + verificationBadge(row.verification_level, 'alt-card-ev')", js)


if __name__ == "__main__":
    unittest.main()
