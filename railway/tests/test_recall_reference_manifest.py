"""Guard against publishing an empty recall-reference template as a result."""
import json
import unittest
from pathlib import Path


class RecallReferenceManifestTests(unittest.TestCase):
    def test_california_template_is_not_a_published_measurement(self):
        path = Path(__file__).resolve().parents[2] / "docs" / "recall-reference-sets" / "ca-us-2026-06.template.json"
        template = json.loads(path.read_text())
        self.assertEqual(template["publication_status"], "template_only_not_a_benchmark")
        self.assertEqual(template["country"], "United States")
        self.assertEqual(template["reference_events"], [])
        self.assertNotIn("sample_recall", template)
        self.assertNotIn("matched_events", template)


if __name__ == "__main__":
    unittest.main()
