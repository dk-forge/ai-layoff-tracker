"""GLEIF LEI: unique name AND country, 8-K and news rows only, never WARN.

Offline. Synthetic rows in the /query and golden-copy shapes.
"""
import csv
import io
import json
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gleif_lei  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "includes" / "company-lei.php"
LEI = "549300ACMEGB0000AA01"
HEADER = ["LEI", "Entity.LegalName", "Entity.OtherEntityNames.OtherEntityName.1",
          "Entity.LegalAddress.Country", "Entity.EntityStatus", "Registration.RegistrationStatus"]


def row(name, source_type, country="", employer_country=""):
    return {"company_name": name, "source_type": source_type,
            "country": country, "employer_country": employer_country}


def golden(tmp, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(rows)
    path = Path(tmp) / "gc.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("golden.csv", buf.getvalue())
    return path


class Normalise(unittest.TestCase):
    def test_suffixes_accents_punctuation(self):
        self.assertEqual(gleif_lei.normalise_name("Hook Media, Inc."), "hook media")
        self.assertEqual(gleif_lei.normalise_name("HÖÖK media AB"), "hook media")
        self.assertEqual(gleif_lei.normalise_name("Société Générale S.A."), "societe generale")
        self.assertEqual(gleif_lei.normalise_name("Smith & Sons GmbH & Co. KG"), "smith and sons")
        self.assertEqual(gleif_lei.normalise_name("Inc."), "")


class Employers(unittest.TestCase):
    def test_warn_rows_are_never_read(self):
        emp = gleif_lei.employers_from_rows([
            row("Local Bakery LLC", "warn", "United States"),
            row("Acme Corp", "8K", "United States"),
            row("Beta Ltd", "news", "United Kingdom"),
            row("Gamma", "press_release", "United Kingdom"),
        ])
        self.assertEqual(emp, {"Acme Corp": {"US"}, "Beta Ltd": {"GB"}})

    def test_domicile_wins_over_job_location(self):
        emp = gleif_lei.employers_from_rows([row("Acme Corp", "news", "India", "United Kingdom")])
        self.assertEqual(emp["Acme Corp"], {"GB"})

    def test_unknown_country_name_is_no_country(self):
        emp = gleif_lei.employers_from_rows([row("Acme Corp", "news", "Multiple countries")])
        self.assertEqual(emp["Acme Corp"], set())


class Match(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_match(self, employers, records):
        return gleif_lei.match_all(employers, gleif_lei.iter_golden_copy(golden(self.tmp, records)))

    def test_country_is_required_hook_media(self):
        got = self.run_match({"Hook Media, Inc.": {"US"}},
                             [["549300SWEDEN0000HOOK", "HÖÖK media AB", "", "SE", "ACTIVE", "ISSUED"]])
        self.assertEqual(got, {})

    def test_unique_match(self):
        got = self.run_match({"Acme Corp": {"GB"}},
                             [[LEI, "ACME CORP LIMITED", "", "GB", "ACTIVE", "ISSUED"]])
        self.assertEqual(got, {"Acme Corp": LEI})

    def test_two_entities_same_name_same_country_is_ambiguous(self):
        got = self.run_match({"Twin Ltd": {"GB"}},
                             [["549300TWIN00000000A1", "Twin Limited", "", "GB", "ACTIVE", "ISSUED"],
                              ["549300TWIN00000000B2", "TWIN PLC", "", "GB", "ACTIVE", "ISSUED"]])
        self.assertEqual(got, {})

    def test_two_countries_or_none_gets_nothing(self):
        recs = [[LEI, "Acme Corp", "", "GB", "ACTIVE", "ISSUED"]]
        self.assertEqual(self.run_match({"Acme Corp": {"GB", "US"}}, recs), {})
        self.assertEqual(self.run_match({"Acme Corp": set()}, recs), {})

    def test_inactive_and_retired_are_skipped(self):
        got = self.run_match({"Gone Ltd": {"GB"}, "Old Co": {"US"}},
                             [["549300DEAD0000000001", "Gone Ltd", "", "GB", "INACTIVE", "ISSUED"],
                              ["549300RETIRED0000001", "Old Co", "", "US", "ACTIVE", "RETIRED"]])
        self.assertEqual(got, {})

    def test_output_is_attributed_and_sorted(self):
        out = Path(self.tmp) / "o.json"
        gleif_lei.write_output(out, {"b": "B", "a": "A"}, "2026-10-13 08:00:00")
        doc = json.loads(out.read_text())
        self.assertEqual(list(doc["companies"]), ["a", "b"])
        self.assertEqual(doc["source"]["licence"], "CC0 1.0")
        self.assertIn("never WARN", doc["source"]["rows"])


STUBS = r"""
define('ABSPATH', '/'); define('ALT_PLUGIN_DIR', '/nonexistent/');
function esc_html($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
"""


@unittest.skipIf(shutil.which("php") is None, "UNKNOWN, NOT RUN: php not installed")
class Page(unittest.TestCase):
    def php(self, expr):
        src = INC.read_text().replace("<?php", "", 1)
        p = subprocess.run(["php", "-r", STUBS + src + "\n" + expr],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        return p.stdout

    MAP = f"$m = array('Acme Corp' => '{LEI}', 'Acme Corporation' => '{LEI}', 'Other' => '549300OTHER000000001');"

    def test_names_must_agree_on_one_lei(self):
        self.assertEqual(self.php(self.MAP + "echo alt_company_lei_for_names(array('Acme Corp','Acme Corporation','x'), $m);"), LEI)
        self.assertEqual(self.php(self.MAP + "echo alt_company_lei_for_names(array('Acme Corp','Other'), $m);"), "")
        self.assertEqual(self.php(self.MAP + "echo alt_company_lei_for_names(array('nobody'), $m);"), "")

    def test_events_shape_and_missing_file(self):
        self.assertEqual(self.php(self.MAP + "echo alt_company_lei_for_events(array(array('company_name'=>'Acme Corp')), $m);"), LEI)
        self.assertEqual(self.php("echo json_encode(alt_company_lei_map());"), "[]")

    def test_html_and_jsonld(self):
        html = self.php(f"echo alt_company_lei_html('{LEI}');")
        self.assertIn(f'href="https://search.gleif.org/#/record/{LEI}"', html)
        self.assertIn("GLEIF Golden Copy", html)
        self.assertNotIn("—", html)   # no em-dashes in UI copy
        ld = json.loads(self.php(f"echo json_encode(alt_company_lei_jsonld('{LEI}'));"))
        self.assertEqual(ld["leiCode"], LEI)
        self.assertEqual(ld["identifier"]["propertyID"], "LEI")
        self.assertEqual(self.php("echo alt_company_lei_html('');"), "")


if __name__ == "__main__":
    unittest.main()
