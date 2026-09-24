"""No workflow file may repeat a mapping key.

source-verification-audit.yml carried `OPS_MAIL_FROM` twice in one `env:`
block (until 2026-09). PyYAML silently keeps the last value, so every local
check passed, but GitHub rejects the whole file: every push produced a failed
run with NO jobs ("workflow file issue") and the monthly audit could not run.
This parses every workflow with a loader that refuses duplicate keys.
"""
import unittest
from pathlib import Path

import yaml

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows"


class _StrictLoader(yaml.SafeLoader):
    pass


def _no_dupes(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dupes)


class NoDuplicateKeys(unittest.TestCase):
    def test_every_workflow(self):
        files = sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))
        self.assertTrue(files)
        for f in files:
            with self.subTest(workflow=f.name):
                yaml.load(f.read_text(encoding="utf-8"), Loader=_StrictLoader)

    def test_guard_is_not_vacuous(self):
        with self.assertRaises(yaml.constructor.ConstructorError):
            yaml.load("env:\n  A: 1\n  A: 2\n", Loader=_StrictLoader)


if __name__ == "__main__":
    unittest.main()
