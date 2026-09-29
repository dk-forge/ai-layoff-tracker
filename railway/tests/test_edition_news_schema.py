"""Archived editions carry NewsArticle markup with real dates (owner ask 2026-09-29).

alt_edition_news_jsonld() is pure: an edition row plus its URL in, a
NewsArticle array out. datePublished is when the edition was published;
dateModified is the newest correction date, or datePublished when there is
none, so Google News and search can tell a fresh edition from a corrected one.
No row, or an unpublished one, yields nothing.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

MOD = (Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
       / "includes" / "edition-schema.php")
MAIN = MOD.parents[1] / "ai-layoff-tracker.php"


def jsonld(row, url="https://example.com/layoff-editions/weekly/2026-w39/", label="Week 39, 2026"):
    src = MOD.read_text(encoding="utf-8")
    m = re.search(r"\nfunction alt_edition_news_jsonld\s*\(.*?\n\}", src, re.S)
    assert m, "alt_edition_news_jsonld is missing"
    code = (m.group(0) + "\n$a = json_decode($argv[1], true);"
            "\necho json_encode(alt_edition_news_jsonld($a['row'], $a['url'], $a['label'], 'AskTheRecruiter.com', 'https://example.com/'));")
    p = subprocess.run(["php", "-r", code, "--", json.dumps({"row": row, "url": url, "label": label})],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return json.loads(p.stdout)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class EditionNewsSchema(unittest.TestCase):
    def test_dates_and_identity(self):
        out = jsonld({"freq": "weekly", "published_at": "2026-09-28 11:30:00", "corrections": []})
        self.assertEqual(out["@type"], "NewsArticle")
        self.assertEqual(out["datePublished"], "2026-09-28T11:30:00Z")
        self.assertEqual(out["dateModified"], "2026-09-28T11:30:00Z")
        self.assertIn("Week 39, 2026", out["headline"])
        self.assertEqual(out["mainEntityOfPage"], "https://example.com/layoff-editions/weekly/2026-w39/")
        self.assertEqual(out["publisher"]["name"], "AskTheRecruiter.com")
        self.assertTrue(out["isAccessibleForFree"])

    def test_latest_correction_moves_date_modified(self):
        out = jsonld({"freq": "weekly", "published_at": "2026-09-28 11:30:00",
                      "corrections": [{"at": "2026-09-29", "note": "a"}, {"at": "2026-10-02", "note": "b"}]})
        self.assertEqual(out["dateModified"], "2026-10-02T00:00:00Z")

    def test_unpublished_or_empty_yields_nothing(self):
        self.assertEqual(jsonld({"freq": "weekly", "published_at": None}), [])
        self.assertEqual(jsonld(None), [])

    def test_headline_fits_google_limit(self):
        out = jsonld({"freq": "weekly", "published_at": "2026-09-28 11:30:00"}, label="x" * 200)
        self.assertLessEqual(len(out["headline"]), 110)

    def test_main_file_loads_it_guarded(self):
        main = MAIN.read_text(encoding="utf-8")
        self.assertIn("includes/edition-schema.php", main)
        self.assertRegex(main, r"is_readable\(\$alt_edition_schema\)")


if __name__ == "__main__":
    unittest.main()
