"""Project the public backup release into versioned static tracker data."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import backup_tables

TABLES = ("layoffs", "events", "source_reports")
FIELDS = (
    "id", "post_id", "company", "company_key", "job_count", "job_count_max",
    "layoff_date", "announcement_date", "industry", "country",
    "employer_country", "state", "source_type", "verification_level",
    "ai_explicit", "ai_causation", "review_status", "announced", "reason_tags",
    "role_categories", "event_id", "superset_of",
)


def verified_rows(root, table, metadata):
    path = root / f"{table}.jsonl.gz"
    digest = hashlib.sha256()
    count = 0
    if path.stat().st_size != metadata["bytes"]:
        raise ValueError(f"{table}: backup size mismatch")
    with gzip.open(path, "rb") as stream:
        for line in stream:
            digest.update(line)
            count += 1
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{table}: expected a row object")
            backup_tables.assert_columns_pinned(table, row)
            if any(value is not None and type(value) not in {str, int} for value in row.values()):
                raise ValueError(f"{table}: expected scalar column values")
            if backup_tables.scan_row(table, row):
                raise ValueError(f"{table}: backup privacy scan failed")
            yield row
    if not count or count != metadata["rows"] or digest.hexdigest() != metadata["sha256"]:
        raise ValueError(f"{table}: backup row count or checksum mismatch")


def public_source(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"http", "https"} and parsed.hostname and not (
            parsed.username or parsed.password
        ):
            return value
    except ValueError:
        pass
    return None


def publish(root: Path, out: Path) -> int:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or not manifest.get("exported_at")
            or manifest.get("drift", {}).get("verdict") not in {"PASS", "UNKNOWN"}):
        raise ValueError("backup must have a supported schema and a non-failing drift verdict")
    exported_at = datetime.fromisoformat(manifest["exported_at"])
    if exported_at.utcoffset() is None:
        raise ValueError("backup timestamp must include a timezone")
    backup_tables.assert_scanner_detects_seeded_personal_data()
    inputs = manifest["tables"]
    canonical = {
        int(row["id"]): int(row["canonical_layoff_id"])
        for row in verified_rows(root, "events", inputs["events"])
    }
    sources = {}
    for row in verified_rows(root, "source_reports", inputs["source_reports"]):
        url = public_source(row["source_url"])
        if url:
            sources.setdefault(int(row["event_id"]), {})[url] = None

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="alt-data-", dir=out.parent) as temporary:
        stage = Path(temporary) / "tracker-data.json"
        with stage.open("w", encoding="utf-8") as stream:
            header = {
                "schema": 1,
                "exported_at": exported_at.isoformat(),
                "source_checksums": {table: inputs[table]["sha256"] for table in TABLES},
            }
            stream.write(json.dumps(header)[:-1] + ', "records": [\n')
            count = 0
            for row in verified_rows(root, "layoffs", inputs["layoffs"]):
                record = {field: row[field] for field in FIELDS}
                event_id = int(row["event_id"])
                record["source_url"] = public_source(row["source_url"])
                record["canonical"] = canonical.get(event_id) == int(row["id"])
                record["source_urls"] = sorted(sources.get(event_id, ())) if record["canonical"] else []
                if count:
                    stream.write(",\n")
                json.dump(record, stream, ensure_ascii=False, separators=(",", ":"))
                count += 1
            stream.write("\n]}\n")
        os.replace(stage, out)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(f"Published {publish(args.backup, args.out)} records to a local data file")


if __name__ == "__main__":
    main()
