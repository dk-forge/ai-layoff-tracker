"""Production GET entry points cannot bypass the common read budget."""
import ast
import unittest
from pathlib import Path


def direct_reads(source):
    tree = ast.parse(source)
    aliases = {alias.asname or alias.name: alias.name
               for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        for local, module in aliases.items():
            if module == 'requests' and name in (local + '.get', local + '.head'):
                found.append(node.lineno)
            if module == 'urllib.request' and name == local + '.urlopen':
                found.append(node.lineno)
    return found


class ReaderSurface(unittest.TestCase):
    def test_detector_sees_direct_calls_and_aliases(self):
        self.assertEqual([2], direct_reads('import requests as http\nhttp.get(url)'))
        self.assertEqual([2], direct_reads('import urllib.request\nurllib.request.urlopen(url)'))
        self.assertEqual([], direct_reads('import blog_read_cache as reads\nreads.get(url, getter=requests.get)'))

    def test_all_production_get_entry_points_use_the_budget(self):
        root = Path(__file__).resolve().parents[1]
        violations = []
        for path in root.rglob('*.py'):
            if 'tests' in path.parts or path.name == 'blog_read_cache.py':
                continue
            for line in direct_reads(path.read_text()):
                violations.append(f'{path.relative_to(root)}:{line}')
        self.assertEqual([], violations)
