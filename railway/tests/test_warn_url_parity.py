"""The generated PHP WARN-URL partial must match the Python source of truth.

Guards the cross-language duplication the tracker relies on to render the
'State WARN list' link: if someone edits STATE_WARN_URL without re-running
generate_warn_urls.py, this fails loudly instead of shipping a stale map.
"""
import os
import re
import unittest

from sources.warn import STATE_WARN_URL

PARTIAL = os.path.join(
    os.path.dirname(__file__), "..", "..", "wordpress-plugin", "ai-layoff-tracker",
    "templates", "partials", "warn-state-urls.php",
)


def parse_php_map(text):
    pairs = re.findall(r"'([A-Z]{2})'\s*=>\s*'((?:[^'\\]|\\.)*)'", text)
    return {st: url.replace("\\'", "'") for st, url in pairs}


class WarnUrlParityTest(unittest.TestCase):
    def test_php_partial_matches_python(self):
        with open(os.path.abspath(PARTIAL), encoding="utf-8") as fh:
            php_map = parse_php_map(fh.read())
        self.assertEqual(
            php_map, STATE_WARN_URL,
            "warn-state-urls.php is out of sync with STATE_WARN_URL — "
            "run `python generate_warn_urls.py`.",
        )


if __name__ == "__main__":
    unittest.main()
