"""Country coverage tiers are derived from the committed register, never typed.

data/country-coverage.json is written by railway/generate_country_tiers.py.
These tests pin the derivation and the rendering rules:

  * the committed file matches a fresh build on its own date;
  * every country in country_coverage.REGISTER has a row, and every row's
    tier follows the one documented rule (official collector -> 1,
    REGIME_WITH_AGGREGATE -> 2, the three "nothing countable" classes -> 3,
    scan scope only -> 4, unsettled -> none);
  * Tier 1 is exactly the set of countries an official collector serves;
  * measured recall appears ONLY where a real event-recall sample exists (US,
    UK), and Estonia and Taiwan carry an official-total comparison and no
    recall figure;
  * the template prints recall only from the `recall` list and labels the
    official-total comparison as not recall and not accuracy;
  * no em dash and no typed cadence in the new copy; the include is guarded.
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.normpath(os.path.join(RAILWAY, ".."))
PLUGIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker")
sys.path.insert(0, RAILWAY)

import country_coverage as cc          # noqa: E402
import generate_country_tiers as gt    # noqa: E402


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class CommittedTiersTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(_read(str(gt.OUT)))
        self.rows = self.doc["countries"]

    def test_committed_json_matches_regeneration(self):
        self.assertTrue(gt.committed_matches(), (
            "data/country-coverage.json is stale. Run "
            "`python3 railway/generate_country_tiers.py` and commit the result."))

    def test_every_register_country_has_a_row(self):
        for country in cc.REGISTER:
            self.assertIn(country, self.rows)

    def test_tier_one_is_exactly_the_official_collector_set(self):
        for country, row in self.rows.items():
            served = bool(gt.official_collectors_for(country))
            self.assertEqual(row["tier"] == 1, served,
                             "%s: tier %r but official collectors %r" % (country, row["tier"], served))
            self.assertEqual(bool(row["official_collectors"]), served)

    def test_tier_follows_the_register_class(self):
        for country, raw in cc.REGISTER.items():
            row = self.rows[country]
            if row["tier"] == 1:
                continue
            entry = cc.entry_for(country, __import__("datetime").date.fromisoformat(self.doc["generated_on"]))
            if entry.get("state") == cc.UNKNOWN:
                self.assertIsNone(row["tier"], country)
            elif raw["class"] == cc.REGIME_WITH_AGGREGATE:
                self.assertEqual(row["tier"], 2, country)
            elif raw["class"] in (cc.REGIME_NO_AGGREGATE, cc.NO_REGIME, cc.REFUSED):
                self.assertEqual(row["tier"], 3, country)

    def test_scan_scope_only_countries_are_tier_four(self):
        for country, row in self.rows.items():
            if country not in cc.REGISTER:
                self.assertEqual(row["tier"], 4, country)
                self.assertIsNone(row["register"], country)

    def test_no_tier_outside_the_four_or_none(self):
        for country, row in self.rows.items():
            self.assertIn(row["tier"], (1, 2, 3, 4, None), country)
            self.assertEqual(row["tier_label"],
                             gt.TIER_LABELS.get(row["tier"], "Not yet classified"))

    def test_recall_only_where_a_real_event_sample_exists(self):
        with_recall = {c for c, r in self.rows.items() if r["recall"]}
        self.assertEqual(with_recall, set(gt.recall_samples()))
        for c in with_recall:
            for sample in self.rows[c]["recall"]:
                self.assertGreater(int(sample["reference"]), 0)
                self.assertLessEqual(int(sample["matched"]), int(sample["reference"]))
                self.assertTrue(sample.get("measured_at"))

    def test_estonia_and_taiwan_carry_a_comparison_and_no_recall(self):
        for c in ("Estonia", "Taiwan"):
            row = self.rows[c]
            self.assertEqual(row["recall"], [], c)
            self.assertTrue(row["official_total_comparisons"], c)
            for comp in row["official_total_comparisons"]:
                self.assertIn("coverage_lower", comp)
                self.assertNotIn("recall", json.dumps(comp).lower(), c)

    def test_estonia_is_tier_one_through_erm_and_taiwan_is_tier_two(self):
        self.assertEqual(self.rows["Estonia"]["tier"], 1)
        self.assertIn("eurofound_erm", [o["health_id"] for o in self.rows["Estonia"]["official_collectors"]])
        self.assertEqual(self.rows["Taiwan"]["tier"], 2)

    def test_languages_come_from_the_market_editions(self):
        self.assertEqual(self.rows["Switzerland"]["languages"], ["German", "French", "Italian"])
        self.assertIn("Turkish", self.rows["Türkiye"]["languages"])
        self.assertNotIn("Turkey", self.rows, "an alias spelling became its own row")

    def test_health_ids_are_declared_on_the_health_page(self):
        import source_inventory as si
        declared = set(si.declared_collectors())
        self.assertTrue(declared)
        for country, row in self.rows.items():
            for hid in row["health_ids"]:
                self.assertIn(hid, declared, "%s names %r" % (country, hid))


class TemplateTests(unittest.TestCase):
    TEMPLATE = os.path.join(PLUGIN, "templates", "page-facet.php")
    INCLUDE = os.path.join(PLUGIN, "includes", "country-coverage.php")
    MAIN = os.path.join(PLUGIN, "ai-layoff-tracker.php")

    def test_block_is_country_only_and_reads_the_generated_file(self):
        t = _read(self.TEMPLATE)
        self.assertIn("$alt_f['dim'] === 'country' && function_exists('alt_country_coverage')", t)
        self.assertIn("alt_country_coverage($alt_f['display'])", t)

    def test_recall_is_printed_only_from_the_recall_list(self):
        t = _read(self.TEMPLATE)
        block = t[t.index("alt-facet-coverage"):t.index("</section>")]
        self.assertIn("if (!empty($alt_cov['recall']))", block)
        self.assertIn("Measured recall", block)
        # The official-total comparison is labelled as what it is.
        self.assertIn("Official-total comparison", block)
        self.assertIn("It is not recall of individual cases and not a measure of accuracy", block)
        # And the word "accuracy" is never attached to the comparison figure.
        self.assertNotIn("coverage accuracy", block.lower())

    def test_no_em_dash_and_no_typed_cadence(self):
        for path in (self.TEMPLATE, self.INCLUDE):
            body = _read(path)
            self.assertNotIn("—", body, path)
            self.assertNotIn("&mdash;", body, path)
            self.assertIsNone(re.search(r"\b(twice|once) (a |per )?(day|daily)\b", body, re.I), path)

    def test_include_is_required_guarded(self):
        main = _read(self.MAIN)
        self.assertIn("includes/country-coverage.php", main)
        self.assertIn("is_readable($alt_country_coverage)", main)

    def test_no_sql_in_the_include(self):
        self.assertNotIn("SELECT", _read(self.INCLUDE))
        self.assertNotIn("$wpdb", _read(self.INCLUDE))


class MeasurementCommitWorkflowsTests(unittest.TestCase):
    """The two measurement crons that feed country-coverage.json must
    regenerate and commit it in the SAME run as their own measurement file,
    or the committed tiers can go stale on main again (2026-09-18: the
    rolling-recall and national-denominators measurements updated and
    country-coverage.json was not regenerated, so test_country_tiers.py
    failed on main and on every PR built from it)."""

    WORKFLOWS = {
        os.path.join(ROOT, ".github", "workflows", "rolling-recall.yml"):
            "railway/rolling_recall_measurement.json",
        os.path.join(ROOT, ".github", "workflows", "national-denominators.yml"):
            "railway/national_denominators_measurement.json",
    }
    COVERAGE_PATH = "wordpress-plugin/ai-layoff-tracker/data/country-coverage.json"

    def test_each_measurement_workflow_regenerates_and_commits_the_tiers(self):
        for path, measurement_path in self.WORKFLOWS.items():
            yml = _read(path)
            self.assertIn(
                "generate_country_tiers.py", yml,
                f"{path} must run railway/generate_country_tiers.py before "
                "committing its measurement, or country-coverage.json can "
                "disagree with what it was just derived from.")
            # The regeneration must happen BEFORE the commit step, not after,
            # or the stale file ships and the fresh one is left uncommitted.
            gen_pos = yml.index("generate_country_tiers.py")
            commit_pos = yml.index("Commit the measurement")
            self.assertLess(
                gen_pos, commit_pos,
                f"{path} regenerates country-coverage.json AFTER committing "
                "the measurement; it must run before the commit step.")
            # And the commit step must stage the regenerated file alongside
            # its own measurement file, in the same commit.
            commit_step = yml[commit_pos:]
            self.assertIn(measurement_path, commit_step, path)
            self.assertIn(self.COVERAGE_PATH, commit_step, path)

    def test_committed_tiers_agree_with_both_measurement_files(self):
        # A generator run against what is actually committed right now must
        # match what is actually committed right now. This is a direct check
        # of the disagreement class (measurement file moved, tiers file did
        # not), independent of test_committed_json_matches_regeneration's own
        # date-anchored comparison.
        self.assertTrue(gt.committed_matches(), (
            "data/country-coverage.json disagrees with a fresh regeneration "
            "from the currently committed measurement files. Run "
            "`python3 railway/generate_country_tiers.py` and commit the "
            "result."))


if __name__ == "__main__":
    unittest.main()
