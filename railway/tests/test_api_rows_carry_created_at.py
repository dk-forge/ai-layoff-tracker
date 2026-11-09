"""Every public API row says when it was first listed (#3695, press-readiness gap 2).

A reporter citing a row needs to know when the tracker first carried it, apart
from the layoff date. The post's GMT publish date is that moment. Static: reads
the PHP as text, comments stripped first.
"""
import re
import unittest
from pathlib import Path

API_PHP = Path(__file__).resolve().parents[2] / "wordpress-plugin/ai-layoff-tracker/includes/api.php"


def _code() -> str:
    text = API_PHP.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)//.*$", "", text)


class ApiRowsCarryCreatedAt(unittest.TestCase):
    def test_entry_to_array_emits_created_at_from_post_date_gmt(self):
        body = _code().split("function alt_entry_to_array(", 1)[1].split("\nfunction ", 1)[0]
        self.assertRegex(body, r"'created_at'\s*=>")
        self.assertIn("post_date_gmt", body)

    def test_created_at_is_iso_utc(self):
        body = _code().split("function alt_entry_to_array(", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("Y-m-d\\TH:i:s\\Z", body)


if __name__ == "__main__":
    unittest.main()
