"""One door to the health ledger, and it retries.

On 2026-09-17 `enrich_roles` finished its work, wrote its end-of-run spend
record, and lost its terminal health note to one connection reset, because it
POSTed `/source-health` itself, once. The `running` note left behind read as a
collector that died mid-flight (`ops_status [2e]`). `source_health.py` already
retries a transient failure three times; three modules simply were not using
it. This fails on any module that writes the ledger with a POST of its own.
Offline: it reads source text only.
"""
import re
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
WRITER = "source_health.py"
#: A write to the ledger: `.post(` whose call text names the route. A GET of
#: the public ledger (ops_status, health_digest, source_inventory) is a read.
POST_TO_LEDGER = re.compile(r"\.post\(\s*[^)]{0,200}?/source-health", re.S)


class OneWriter(unittest.TestCase):
    def test_only_source_health_posts_to_the_ledger(self):
        offenders = []
        for path in sorted(RAILWAY.rglob("*.py")):
            if "tests" in path.parts or path.name == WRITER:
                continue
            if POST_TO_LEDGER.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(str(path.relative_to(RAILWAY)))
        self.assertEqual(offenders, [], "these modules POST /source-health themselves, "
                         "in one attempt; call source_health.report_source_health")

    def test_the_pattern_catches_the_defect_it_was_written_for(self):
        old = ('requests.post(\n    f"{SITE}/wp-json/layoffs/v1/source-health",\n'
               '    json={"source": "role_enrichment"})')
        self.assertTrue(POST_TO_LEDGER.search(old))


if __name__ == "__main__":
    unittest.main()
