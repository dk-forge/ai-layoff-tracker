#!/usr/bin/env python3
"""Rebuild the tracker's tables from a backup produced by `backup_export.py`.

READ THIS BEFORE YOU BELIEVE ANY OF IT
--------------------------------------
There are TWO return paths and they are not equally proven. Say which one you
used when you report a recovery.

  --via bulk    layoffs ONLY, over HTTP, through the existing keyed /bulk
                upsert. Needs no database access, so it works against a host
                where all you have is the site and the key. It is LOSSY and
                `python3 backup_restore.py --fidelity` prints exactly which
                columns survive, measured against the live site rather than
                read off the source.

  --emit-sql    ANY exported table, as INSERT statements to load straight into
                MySQL on the new host. Lossless: it writes the columns the
                export captured, including the ones /bulk has no parameter for.
                This is the path for a reimage, because a reimage has database
                access by definition.

WHAT /bulk-purge IS NOT
-----------------------
It is NOT "empty the table". It deletes WARN rows with no post and no editorial
pin, and nothing else, because it exists to serve the WARN purge-and-reimport
cycle. There is no endpoint that empties `wp_alt_layoffs`, and a restore does
not need one: a reimage starts against tables dbDelta has just created empty.
Do not reach for /bulk-purge as a restore step.

WHY /bulk AND NOT A NEW WRITE ENDPOINT
--------------------------------------
A generic "write these rows into that table" route, keyed or not, is a large
new authority on a public host, and the reimage case already has something
strictly more capable: a MySQL prompt. So the tables /bulk cannot reach are
restored as SQL rather than by widening what the API can be talked into doing.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import backup_tables
import host_call

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# The fields alt_api_bulk reads off an entry. Anything outside this list is in
# the export and is NOT carried by an HTTP restore; --fidelity proves the list
# against the live site rather than trusting it.
BULK_FIELDS = (
    "dedup_hash", "company_name", "ticker", "job_count", "job_count_max",
    "layoff_date", "announcement_date", "industry", "country",
    "employer_country", "employer_country_evidence", "announcement_evidence",
    "state", "source_type", "verification_level", "source_name", "source_url",
    "ai_explicit", "ai_causation", "confidence", "review_status", "announced",
    "ai_language", "reason_tags", "roles", "excerpt",
)

BATCH = 500


def read_jsonl_gz(path: Path):
    with gzip.open(path, "rb") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def row_to_bulk_entry(row: dict) -> dict:
    """One exported layoffs row as an /bulk entry.

    `company` is the column and `company_name` is what /bulk calls it; that
    rename is the single reason this function exists rather than a dict copy.
    `reason_tags` is stored packed as ',a,b,' and /bulk re-packs, so it is
    unpacked here to the list the endpoint expects.
    """
    tags = (row.get("reason_tags") or "").strip(",")
    entry = {
        "dedup_hash": row.get("dedup_hash") or "",
        "company_name": row.get("company") or "",
        "reason_tags": [t for t in tags.split(",") if t],
    }
    for field in BULK_FIELDS:
        if field in ("dedup_hash", "company_name", "reason_tags"):
            continue
        if field in row:
            entry[field] = row[field]
    return entry


def restore_via_bulk(export_dir: Path, base: str, headers: dict, *,
                     limit: int | None, confirm: bool) -> int:
    path = export_dir / "layoffs.jsonl.gz"
    if not path.exists():
        raise SystemExit(f"{path} is not there. --via bulk restores layoffs only.")

    entries, skipped = [], 0
    for row in read_jsonl_gz(path):
        if not row.get("dedup_hash"):
            # /bulk keys on dedup_hash and silently skips a row without one, so
            # count them here instead of discovering a short restore later.
            skipped += 1
            continue
        entries.append(row_to_bulk_entry(row))
        if limit and len(entries) >= limit:
            break

    print(f"{len(entries):,} entries ready ({skipped:,} skipped for a missing dedup_hash)")
    if not confirm:
        print("DRY RUN. Nothing was sent. Re-run with --confirm to write.")
        print("First entry:")
        print(json.dumps(entries[0], indent=2, sort_keys=True)[:1200] if entries else "  (none)")
        return 0

    sent = upserted = 0
    for i in range(0, len(entries), BATCH):
        batch = entries[i:i + BATCH]
        result = host_call.post_json(f"{base}/bulk", {"entries": batch},
                                     headers=headers, timeout=180)
        sent += len(batch)
        upserted += int(result.get("upserted", 0))
        print(f"  {sent:,}/{len(entries):,} sent, {upserted:,} upserted")

    if upserted < sent:
        # Not automatically wrong: alt_db_upsert returns 0 for an editorially
        # SUPPRESSED dedup_hash, and a suppressed row must never come back
        # through an import. But it is never something to discover silently.
        print(f"NOTE: {sent - upserted:,} entries did not upsert. Suppressed rows "
              f"are the expected cause; anything else needs a human.")
    return 0


# --------------------------------------------------------------------------
# SQL emission: the lossless path, for a host where you have MySQL.
# --------------------------------------------------------------------------

def sql_literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    s = str(value)
    # Escape for MySQL string literals. Backslash FIRST and it matters as much
    # as the quote: a value ending in a lone backslash would otherwise escape
    # the closing quote and run the rest of the row as SQL.
    #
    # NUL and Ctrl-Z are escaped rather than stripped. Dropping them was the
    # first version of this line and a real MySQL 8 load caught it: a row whose
    # value contained \x00 came back one byte shorter, silently, with the load
    # reporting success. A restore that quietly alters a value is worse than one
    # that fails, so nothing here removes a character.
    s = (s.replace("\\", "\\\\")
          .replace("'", "\\'")
          .replace("\n", "\\n")
          .replace("\r", "\\r")
          .replace("\x00", "\\0")
          .replace("\x1a", "\\Z"))
    return f"'{s}'"


def emit_sql(export_dir: Path, table: str, prefix: str, out) -> int:
    spec = backup_tables.TABLES.get(table)
    if spec is None:
        raise SystemExit(
            f"'{table}' is not an exported table. Known: {', '.join(sorted(backup_tables.TABLES))}")
    path = export_dir / f"{table}.jsonl.gz"
    if not path.exists():
        raise SystemExit(f"{path} is not in this export.")

    physical = f"{prefix}alt_{table}"
    columns = spec["columns"]
    out.write(f"-- {physical}: from {path.name}\n")
    out.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n")
    out.write("START TRANSACTION;\n")

    rows = 0
    buf = []
    for row in read_jsonl_gz(path):
        backup_tables.assert_columns_pinned(table, row.keys())
        values = ", ".join(sql_literal(row.get(c)) for c in columns)
        buf.append(f"({values})")
        rows += 1
        if len(buf) >= 200:
            out.write(f"INSERT IGNORE INTO `{physical}` (`" + "`, `".join(columns) + "`) VALUES\n")
            out.write(",\n".join(buf) + ";\n")
            buf = []
    if buf:
        out.write(f"INSERT IGNORE INTO `{physical}` (`" + "`, `".join(columns) + "`) VALUES\n")
        out.write(",\n".join(buf) + ";\n")

    out.write("COMMIT;\nSET FOREIGN_KEY_CHECKS=1;\n")
    print(f"{table}: {rows:,} rows of SQL for `{physical}`", file=sys.stderr)
    return rows


# --------------------------------------------------------------------------
# Fidelity: which columns actually survive an HTTP restore. Measured.
# --------------------------------------------------------------------------

def fidelity(base: str, headers: dict, sample: int) -> int:
    """Round-trip real rows through /bulk and diff what came back, per column.

    This is the drill, and its limits are as important as its result:

      IT PROVES   the export file -> /bulk entry -> alt_db_upsert -> read-back
                  chain end to end against the real site, and it MEASURES which
                  columns survive rather than reading the answer off the PHP.

      IT DOES NOT prove an INSERT into an empty table. Every row it sends
                  already exists, so alt_db_upsert takes its UPDATE branch. The
                  two branches differ (the UPDATE branch pins `edited` rows and
                  declines to blank an absent industry), so a green drill is
                  evidence about the update path and silence about the other.
                  Proving the insert path needs a throwaway WordPress, which is
                  a real gap and docs/RECOVERY.md names it as one rather than
                  letting this stand in for it.

    Side effect, stated because it is not nothing: the rows it touches get their
    `updated_at` restamped, so /changed-rows reports them. It writes no new row
    and changes no value, because every value it sends is the value it just read.
    """
    page = host_call.get_json(f"{base}/backup-table",
                              params={"table": "layoffs", "after": 0, "limit": sample},
                              headers=headers, timeout=120)
    before = {r["dedup_hash"]: r for r in page.get("rows", []) if r.get("dedup_hash")}
    if not before:
        print("no rows with a dedup_hash came back; nothing to drill")
        return 3
    print(f"drill: {len(before)} live rows")

    entries = [row_to_bulk_entry(r) for r in before.values()]
    result = host_call.post_json(f"{base}/bulk", {"entries": entries},
                                 headers=headers, timeout=180)
    print(f"/bulk received {result.get('received')}, upserted {result.get('upserted')}")

    page2 = host_call.get_json(f"{base}/backup-table",
                               params={"table": "layoffs", "after": 0, "limit": sample},
                               headers=headers, timeout=120)
    after = {r["dedup_hash"]: r for r in page2.get("rows", []) if r.get("dedup_hash")}

    columns = backup_tables.TABLES["layoffs"]["columns"]
    changed = {c: 0 for c in columns}
    compared = 0
    for h, row in before.items():
        new = after.get(h)
        if new is None:
            continue
        compared += 1
        for c in columns:
            if row.get(c) != new.get(c):
                changed[c] += 1

    print(f"\ncompared {compared} rows, column by column:")
    lost = []
    for c in columns:
        n = changed[c]
        if n == 0:
            continue
        if c == "updated_at":
            print(f"  {c:28s} {n:5d} changed  (expected: every write stamps it)")
            continue
        lost.append(c)
        print(f"  {c:28s} {n:5d} changed  <-- NOT carried by an HTTP restore")
    if not lost:
        print("  every column except updated_at came back identical")
    print("\nColumns /bulk has no parameter for are restored by --emit-sql instead.")
    return 0 if compared else 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--export", default="backup-out", help="directory holding the export")
    ap.add_argument("--via", choices=["bulk"], help="restore layoffs over HTTP through /bulk")
    ap.add_argument("--emit-sql", metavar="TABLE", help="write INSERT statements for one table to stdout")
    ap.add_argument("--prefix", default="wp_", help="WordPress table prefix for --emit-sql")
    ap.add_argument("--fidelity", action="store_true", help="measure which columns survive an HTTP restore")
    ap.add_argument("--sample", type=int, default=200, help="rows for --fidelity")
    ap.add_argument("--limit", type=int, help="restore at most N rows (rehearsal)")
    ap.add_argument("--confirm", action="store_true", help="actually write; without it --via bulk is a dry run")
    args = ap.parse_args(argv)

    if args.emit_sql:
        return 0 if emit_sql(Path(args.export), args.emit_sql, args.prefix, sys.stdout) >= 0 else 2

    import os
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        raise SystemExit("WP_SITE_URL and WP_API_KEY are required for anything that talks to the host.")
    base = f"{site}/wp-json/layoffs/v1"
    headers = {"X-Layoff-API-Key": key, "User-Agent": UA}

    if args.fidelity:
        return fidelity(base, headers, args.sample)
    if args.via == "bulk":
        return restore_via_bulk(Path(args.export), base, headers,
                                limit=args.limit, confirm=args.confirm)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
