"""The US jurisdiction registry page derives every cell; nothing is typed.

data/us-jurisdictions.json is written by railway/generate_us_registry.py from
the source inventory, the WARN scrapers' own state lists, the official-URL map,
source_state.json and the WARN workflows' cron lines. The plugin adds the live
health ledger and the layoffs table at render time. These tests pin:

  * the committed file is what the generator produces today (a scraper added,
    removed or marked UNAVAILABLE must reach the public page the same commit);
  * one row per jurisdiction in source_inventory.US_JURISDICTIONS, no more and
    no fewer;
  * every collector row names a health id the public health page declares, so
    "last successful collection" can never read from an id nothing reports;
  * "no public register" is said only where a reviewer recorded it or where
    nothing exists at all, never as a default for a collector that is merely
    quiet;
  * the page's copy types no cadence and no em dash, and it is wired into
    every list a secondary page must join (title sync, own-<h1> strip, asset
    gate, public-surface list, link check).
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

import generate_us_registry as gur  # noqa: E402
import source_inventory as si  # noqa: E402


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


class CommittedRegistryTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(_read(str(gur.OUT)))

    def test_committed_json_matches_regeneration(self):
        self.assertTrue(gur.committed_matches(), (
            "data/us-jurisdictions.json is stale. Run "
            "`python3 railway/generate_us_registry.py` and commit the result; "
            "the public page must move with the collectors, not after them."))

    def test_one_row_per_jurisdiction(self):
        codes = [r["code"] for r in self.doc["rows"]]
        self.assertEqual(codes, list(si.US_JURISDICTIONS))
        self.assertEqual(self.doc["jurisdictions"], 56)

    def test_every_health_id_is_declared_on_the_health_page(self):
        declared = set(si.declared_collectors())
        self.assertTrue(declared, "could not read assets/health.js meta{}")
        for row in self.doc["rows"]:
            for c in row["collectors"]:
                self.assertIn(c["health_id"], declared,
                              "%s collector %s reports under %r, which the "
                              "health page does not declare" % (row["code"], c["tier"], c["health_id"]))

    def test_every_collector_tier_is_a_known_tier(self):
        for row in self.doc["rows"]:
            for c in row["collectors"]:
                self.assertIn(c["tier"], gur.TIERS)
                self.assertEqual(c["method"], gur.TIERS[c["tier"]]["method"])

    def test_collected_jurisdictions_carry_an_official_source(self):
        # A collector reads a page; a row saying "collected" with no page to
        # cite would be a claim with nothing behind it.
        for row in self.doc["rows"]:
            if row["collectors"]:
                self.assertTrue(row["official_url"].startswith("https://"),
                                "%s is collected but has no official URL" % row["code"])

    def test_no_public_register_is_a_recorded_finding_not_a_default(self):
        for row in self.doc["rows"]:
            if not row["no_public_register"]:
                continue
            fresh = row["freshness"]
            recorded = (fresh["state"] == "UNAVAILABLE"
                        and row.get("unavailable", {}).get("classification") == "policy"
                        and row.get("unavailable", {}).get("reason"))
            nothing = (not row["collectors"] and not row["official_url"]
                       and fresh["state"] == "ABSENT")
            self.assertTrue(recorded or nothing,
                            "%s says 'no public register' without a reviewer's "
                            "reason or a total absence" % row["code"])
        # And a quiet or unjudged collected state is never called a
        # non-register.
        for row in self.doc["rows"]:
            if row["collectors"] and row["freshness"]["state"] in ("HEALTHY", "UNKNOWN", "ABSENT"):
                self.assertFalse(row["no_public_register"], row["code"])

    def test_oklahoma_is_unavailable_with_a_page_not_a_missing_register(self):
        # The one jurisdiction the ledger marks UNAVAILABLE that still
        # publishes: notices without headcounts. The page must say that, not
        # "no public register".
        ok = next(r for r in self.doc["rows"] if r["code"] == "OK")
        self.assertEqual(ok["freshness"]["state"], "UNAVAILABLE")
        self.assertTrue(ok["official_url"])
        self.assertFalse(ok["no_public_register"])

    def test_cadence_is_parsed_from_the_workflow_cron(self):
        self.assertEqual(gur.cadence_phrase("0 13 * * *"), "daily")
        self.assertEqual(gur.cadence_phrase("30 16 * * 1"), "weekly")
        self.assertEqual(gur.cadence_phrase("0 */6 * * *"), "")
        self.assertEqual(gur.cadence_phrase("not a cron"), "")
        # The shipped WARN workflow really is daily; if it moves, the JSON
        # moves with it via the parity test above.
        for row in self.doc["rows"]:
            for c in row["collectors"]:
                self.assertIn(c["cadence"], ("daily", "weekly", ""))


class PageWiringTests(unittest.TestCase):
    TEMPLATE = os.path.join(PLUGIN, "templates", "page-us-registry.php")
    INCLUDE = os.path.join(PLUGIN, "includes", "us-registry.php")
    MAIN = os.path.join(PLUGIN, "ai-layoff-tracker.php")
    SHORTCODES = os.path.join(PLUGIN, "includes", "shortcodes.php")

    def test_template_has_exactly_one_h1(self):
        self.assertEqual(len(re.findall(r"<h1[\s>]", _read(self.TEMPLATE))), 1)

    def test_no_em_dash_in_reader_copy(self):
        for path in (self.TEMPLATE, self.INCLUDE):
            self.assertNotIn("—", _read(path), path)
            self.assertNotIn("&mdash;", _read(path), path)

    def test_no_typed_cadence_in_the_template(self):
        # The cadence cell is read from the JSON, which is read from the cron.
        body = _read(self.TEMPLATE)
        self.assertIsNone(re.search(r"\b(twice|once) (a |per )?(day|daily)\b", body, re.I))
        self.assertIsNone(re.search(r"\b\d{1,2}\s?(am|pm)\s+ET\b", body, re.I))

    def test_the_include_is_required_guarded_and_the_page_is_registered(self):
        main = _read(self.MAIN)
        self.assertIn("includes/us-registry.php", main)
        self.assertIn("is_readable($alt_us_registry)", main)
        self.assertIn("'alt_us_registry'", main)            # asset gate
        self.assertIn("us-warn-registry/", main)            # IndexNow list
        sc = _read(self.SHORTCODES)
        self.assertIn("'ai-layoff-tracker/us-warn-registry'", sc)   # title sync
        own = re.search(r"function alt_own_h1_shortcodes\(\) \{(.*?)\n\}", sc, re.S).group(1)
        self.assertIn("'alt_us_registry'", own)
        pub = re.search(r"function alt_public_surface_shortcodes\(\) \{(.*?)\n\}", sc, re.S).group(1)
        self.assertIn("'alt_us_registry'", pub)

    def test_the_include_defines_no_sql_in_the_template(self):
        self.assertNotIn("SELECT", _read(self.TEMPLATE))
        self.assertIn("alt_source_health_masked", _read(self.INCLUDE))

    def test_link_check_and_sources_page_reach_it(self):
        self.assertIn("/ai-layoff-tracker/us-warn-registry/", _read(RAILWAY, "link_check.py"))
        self.assertIn("us-warn-registry", _read(PLUGIN, "templates", "page-sources.php"))

    def test_health_page_labels_link_every_warn_collector_to_the_registry(self):
        js = _read(PLUGIN, "assets", "health.js")
        self.assertIn("usRegistryUrl", js)
        for cid in ("warn_us", "warn_hi_ocr", "warn_mn_letters",
                    "warn_custom_states", "warn_custom_legacy"):
            line = re.search(r"^\s{4}%s\s*:\s*\[(.*)\],?$" % cid, js, re.M)
            self.assertIsNotNone(line, cid)
            self.assertIn("'us'", line.group(1), "%s label carries no registry link" % cid)


if __name__ == "__main__":
    unittest.main()
