"""Every self-served *-sitemap.xml route must register on init priority 1.

Found 2026-11-09: sitemap_index.xml listed /layoff-digest-sitemap.xml but the
URL served 404, while index.php?alt_digest_pub=sitemap rendered fine. The rule
was added on init priority 2. Rank Math adds its own catch-all
`([^/]+?)-sitemap([0-9]+)?\\.xml$` rule on init priority 1, and 'top' rules
match in the order they are added, so any of our sitemap rules added after it
is shadowed. Every working sitemap (company, facets, reports, editions)
registers on priority 1; a sitemap in the index that 404s is a Search Console
"Not found" and Google stops reading it.
"""
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"


def _init_hooks(src):
    """Yield (priority, body) for each add_action('init', ...) in src."""
    named = {}
    # Split at each top-level function so a one-line function cannot swallow
    # the body of the next one.
    for chunk in re.split(r"\n(?=function \w)", src):
        m = re.match(r"function (\w+)\s*\([^)]*\)\s*\{(.*?)\n\}", chunk, re.S)
        if m:
            named[m.group(1)] = m.group(2)
    for m in re.finditer(r"add_action\('init',\s*'(\w+)'(?:,\s*(\d+))?\)", src):
        yield int(m.group(2) or 10), named.get(m.group(1), "")
    for m in re.finditer(r"add_action\('init',\s*function\s*\(\)\s*\{(.*?)\n\},\s*(\d+)\);", src, re.S):
        yield int(m.group(2)), m.group(1)


class SitemapRoutePriority(unittest.TestCase):
    def test_every_sitemap_rule_registers_on_priority_one(self):
        found = {}
        for path in [PLUGIN / "ai-layoff-tracker.php", *sorted((PLUGIN / "includes").glob("*.php"))]:
            src = path.read_text(encoding="utf-8")
            for prio, body in _init_hooks(src):
                for rule in re.findall(r"add_rewrite_rule\('\^([\w-]+-sitemap)\\\.xml\$'", body):
                    found[rule] = (prio, path.name)
        self.assertIn("layoff-digest-sitemap", found)
        self.assertGreaterEqual(len(found), 5, found)
        late = {k: v for k, v in found.items() if v[0] > 1}
        self.assertEqual(late, {}, "sitemap rules after Rank Math's init:1 catch-all are shadowed (404)")


if __name__ == "__main__":
    unittest.main()
