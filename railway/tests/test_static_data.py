"""Tests for the release-to-static-data publication boundary."""
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import static_data


class StaticData(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "out" / "tracker-data.json"
        self.manifest = {
            "schema_version": 1,
            "exported_at": "2026-11-22T06:44:13Z",
            "drift": {"verdict": "PASS"},
            "tables": {},
        }
        row = dict.fromkeys(static_data.FIELDS, "")
        row.update(id="1", event_id="3", superset_of="0", company="Acme",
                   source_url="https://example.org/filing", job_count="25")
        self.tables = {
            "layoffs": [row, dict(row, id="2", superset_of="1")],
            "events": [{"id": "3", "canonical_layoff_id": "1"}],
            "source_reports": [
                {"event_id": "3", "source_url": "https://example.org/filing"},
                {"event_id": "3", "source_url": "https://example.org/corroboration"},
                {"event_id": "3", "source_url": "javascript:example"},
            ],
        }

    def write_backup(self):
        for table, rows in self.tables.items():
            lines = "".join(json.dumps(row) + "\n" for row in rows).encode()
            compressed = gzip.compress(lines)
            (self.root / f"{table}.jsonl.gz").write_bytes(compressed)
            self.manifest["tables"][table] = {
                "bytes": len(compressed), "rows": len(rows),
                "sha256": hashlib.sha256(lines).hexdigest(),
            }
        self.write_manifest()

    def write_manifest(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))

    def test_projects_canonical_evidence_and_keeps_superset_members(self):
        self.write_backup()
        self.assertEqual(static_data.publish(self.root, self.output), 2)
        data = json.loads(self.output.read_text())
        self.assertEqual(data["exported_at"], "2026-11-22T06:44:13+00:00")
        canonical, member = data["records"]
        self.assertTrue(canonical["canonical"])
        self.assertEqual(canonical["source_urls"], [
            "https://example.org/corroboration", "https://example.org/filing",
        ])
        self.assertFalse(member["canonical"])
        self.assertEqual(member["source_urls"], [])
        self.assertEqual(member["superset_of"], "1")

    def test_checksum_failure_cannot_replace_previous_output(self):
        self.write_backup()
        static_data.publish(self.root, self.output)
        previous = self.output.read_bytes()
        self.manifest["tables"]["layoffs"]["sha256"] = "0" * 64
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            static_data.publish(self.root, self.output)
        self.assertEqual(self.output.read_bytes(), previous)

    def test_nested_values_never_appear_in_published_data(self):
        self.tables["layoffs"][0]["company"] = {"email": "sample@example.org"}
        self.write_backup()
        with self.assertRaisesRegex(ValueError, "scalar column values"):
            static_data.publish(self.root, self.output)
        self.assertFalse(self.output.exists())
