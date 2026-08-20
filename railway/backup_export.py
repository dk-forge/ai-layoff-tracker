#!/usr/bin/env python3
"""Weekly off-host backup of every table this plugin owns that may leave the host.

WHY THIS EXISTS
---------------
Until this shipped, `wp_alt_layoffs` existed in exactly one place: MySQL on a
shared Bluehost account. Roughly 65,000 curated rows, a large share of them
produced by paid LLM extraction, with no copy anywhere. The adjudication files
are committed JSON so the human rulings survive a loss; the extracted rows did
not. If that table went, it went.

WHAT IT PRODUCES
----------------
One directory per run:

    <out>/manifest.json          row counts, checksums, date range, versions
    <out>/<table>.jsonl.gz       one JSON object per line, raw columns

gzipped JSON Lines rather than one blob because a line-per-row file can be
walked, grepped and partially recovered when something is truncated, and a
single 80MB JSON array cannot.

WHERE IT GOES, AND WHY NOT INTO THE REPO
----------------------------------------
The artifact is attached to a GitHub Release. The only thing committed is the
rolling `railway/backup_state.json`, a few kB naming each table's row count,
size and checksum. That split is measured, not stylistic: the compressed export
is several MB a week, so committing the files would add hundreds of MB a year
to a repository that every clone and every one of ~80 workflow checkouts pays
for, permanently, and gzip does not delta-compress so git could not amortise
it. Keeping the state file in the repo is what lets `ops_status` read the
backup's health offline and lets the drift check compare against a value the
host cannot rewrite. Release assets are retained indefinitely, unlike Actions
artifacts, which expire at 90 days.

THE PERSONAL-DATA BOUNDARY
--------------------------
The release is PUBLIC. `wp_alt_subscribers` may never be in it. The boundary is
an allowlist of table names enforced on BOTH sides (the plugin's
/backup-table 400s on anything else; `backup_tables.TABLES` names the same set
here) plus a pinned column allowlist that fails the run on any column nobody
reviewed. `backup_tables` documents why layer 3, the value scanner, is depth
and not the boundary, and why it is proved against a seeded positive control
before its clean result is believed.

DRIFT
-----
An export that silently starts producing zero rows is worse than no export,
because it looks like protection. Every run compares itself to the committed
`railway/backup_state.json` and FAILS on: an empty required table, a required
table missing, a count that fell more than SHRINK_TOLERANCE below the last
good run, a manifest missing a required field, or a walk that returned
materially fewer rows than the site's own COUNT(*) said were there. A run that
could not reach the host is DEFERRED and exits 0 the first two times (the host
being down is not this job's defect); the third consecutive one exits non-zero,
which is host_call's rule and not a new one. A run with no baseline reports
drift UNCHECKED, which is not a pass.

Cheap by construction: no model call, no paid read, plain keyset GETs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import backup_tables
import host_call
import source_health

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
JOB = "backup-export"
HEALTH_SOURCE = "backup_export"

HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "backup_state.json"

# How far a table may shrink against the last good run before the run fails.
# Not zero: /trash, /bulk-purge and the superset reconciler all legitimately
# remove rows, and a hard "never smaller" rule would red the job for the dedup
# pass working. 5% of 65,000 rows is ~3,300, which is far larger than any
# routine correction and far smaller than a truncation.
SHRINK_TOLERANCE = 0.05

# How far the rows we actually WALKED may fall below the COUNT(*) the site
# reported in the same run. Small and non-zero: an import landing mid-walk
# moves the count under us, and keyset paging means that shows up as a few rows
# rather than as corruption. A large gap means the walk stopped early, which is
# the silent-truncation failure this whole check exists for.
WALK_TOLERANCE = 0.01

PAGE_LIMIT = 2000

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base() -> str:
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        raise SystemExit("WP_SITE_URL is not set.")
    return f"{site}/wp-json/layoffs/v1"


def _headers() -> dict:
    key = os.environ.get("WP_API_KEY", "")
    if not key:
        raise SystemExit(
            "WP_API_KEY is not set. The backup read is keyed: the public /query "
            "route omits dedup_hash, which /bulk upserts on, so a file built "
            "from it could not be restored."
        )
    return {"X-Layoff-API-Key": key, "User-Agent": UA}


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------

def fetch_manifest() -> dict:
    return host_call.get_json(f"{_base()}/backup-manifest", headers=_headers(), timeout=60)


def walk_table(name: str, spec: dict):
    """Yield rows of one table in primary-key order, checking columns as we go.

    Keyset, never OFFSET: an import landing mid-walk shifts every later offset,
    which drops rows silently, and on a backup a silently dropped row IS the
    defect.
    """
    after = 0
    seen_columns = False
    while True:
        page = host_call.get_json(
            f"{_base()}/backup-table",
            params={"table": name, "after": after, "limit": PAGE_LIMIT},
            headers=_headers(),
            timeout=180,
        )
        rows = page.get("rows") or []
        if rows and not seen_columns:
            backup_tables.assert_columns_pinned(name, rows[0].keys())
            seen_columns = True
        for row in rows:
            # Layer 2 again, per row: a NULL-heavy first page can hide a column
            # that only appears later, and a per-row check costs nothing next to
            # the network.
            backup_tables.assert_columns_pinned(name, row.keys())
            findings = backup_tables.scan_row(name, row)
            if findings:
                raise backup_tables.PersonalDataInExport(
                    "The value scanner flagged content in the export: "
                    + "; ".join(sorted(set(findings)))
                    + ". THE EXPORT HAS STOPPED and nothing was published. This is "
                      "layer 3 (depth, not the boundary) so it may be a false "
                      "positive on public source text, but a human decides that, "
                      "not this job. See railway/backup_tables.py."
                )
            yield row
        nxt = page.get("next_after")
        if not nxt:
            return
        after = int(nxt)


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------

def write_table(out_dir: Path, name: str, spec: dict) -> dict:
    path = out_dir / f"{name}.jsonl.gz"
    digest = hashlib.sha256()
    rows = 0
    min_date = max_date = None

    # mtime=0 so two runs over identical data produce identical bytes. A
    # checksum that changes because the clock moved cannot answer "did the data
    # change", which is the one question a checksum is for.
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(path, "wb"), mtime=0) as gz:
        for row in walk_table(name, spec):
            line = json.dumps(row, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8") + b"\n"
            gz.write(line)
            digest.update(line)
            rows += 1
            if name == "layoffs":
                d = row.get("layoff_date")
                if d:
                    min_date = d if min_date is None or d < min_date else min_date
                    max_date = d if max_date is None or d > max_date else max_date

    return {
        "rows": rows,
        "bytes": path.stat().st_size,
        # Over the uncompressed lines, so the checksum answers "is this the same
        # data" and not "is this the same compressor".
        "sha256": digest.hexdigest(),
        "restorable": spec["restorable"],
        "date_range": ([min_date, max_date] if name == "layoffs" else None),
    }


# --------------------------------------------------------------------------
# Drift
# --------------------------------------------------------------------------

REQUIRED_MANIFEST_FIELDS = (
    "exported_at", "schema_version", "plugin_version", "tables", "total_rows",
)


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_drift(manifest: dict, previous: dict) -> tuple:
    """(verdict, [lines]). FAIL is loud, UNKNOWN is never a pass."""
    problems, notes = [], []

    for field in REQUIRED_MANIFEST_FIELDS:
        if field not in manifest or manifest[field] in (None, ""):
            problems.append(f"manifest is missing required field '{field}'")

    tables = manifest.get("tables") or {}
    if not tables:
        problems.append("the export contains no tables at all")

    for name, spec in backup_tables.TABLES.items():
        entry = tables.get(name)
        if entry is None:
            if spec["optional"]:
                notes.append(f"{name}: absent (optional table, not on this install)")
            else:
                problems.append(f"{name}: REQUIRED table is missing from the export")
            continue
        if entry.get("rows", 0) == 0 and not spec.get("may_be_empty", False):
            problems.append(
                f"{name}: exported ZERO rows, and this table is declared as one "
                f"that is never legitimately empty")

    if manifest.get("total_rows", 0) == 0:
        problems.append("the export is empty: zero rows across every table")

    prev_tables = (previous.get("tables") or {})
    if not prev_tables:
        notes.append(
            "no previous run to compare against, so shrink drift is UNCHECKED. "
            "That is not a pass; the next run establishes the baseline."
        )
        verdict = UNKNOWN if not problems else FAIL
    else:
        for name, entry in tables.items():
            prev = prev_tables.get(name)
            if not prev or prev.get("rows") is None:
                notes.append(f"{name}: no baseline yet, shrink UNCHECKED")
                continue
            before, now = int(prev["rows"]), int(entry.get("rows", 0))
            if before == 0:
                continue
            drop = (before - now) / before
            if drop > SHRINK_TOLERANCE:
                problems.append(
                    f"{name}: {now:,} rows against {before:,} last run, a "
                    f"{drop:.1%} fall past the {SHRINK_TOLERANCE:.0%} tolerance"
                )
            elif now < before:
                notes.append(f"{name}: {now:,} rows, down {before - now:,} (inside tolerance)")
        verdict = FAIL if problems else PASS

    # What the site said was there against what we actually walked away with.
    for name, entry in tables.items():
        claimed = entry.get("site_count")
        if claimed is None:
            notes.append(f"{name}: the site reported no count, so the walk is UNVERIFIED")
            continue
        got = int(entry.get("rows", 0))
        if claimed > 0 and (claimed - got) / claimed > WALK_TOLERANCE:
            problems.append(
                f"{name}: walked {got:,} rows but the site counted {claimed:,} "
                f"- the walk stopped early"
            )

    if problems:
        return FAIL, problems + notes
    return verdict, notes


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def run(out_dir: Path, *, report: bool, record: bool) -> int:
    started = time.time()

    # Layers 1 and 3 are proved BEFORE anything is read. A guard checked after
    # the fact is a guard the export has already run without.
    backup_tables.assert_allowlists_disjoint()
    backup_tables.assert_scanner_detects_seeded_personal_data()
    print("guards: table allowlist disjoint from the forbidden set; "
          "value scanner flagged its seeded positive control")

    out_dir.mkdir(parents=True, exist_ok=True)

    site = fetch_manifest()
    site_tables = site.get("tables") or {}
    print(f"site: plugin {site.get('plugin_version')} schema {site.get('schema_version')}")
    for entry in site.get("excluded") or []:
        print(f"  EXCLUDED {entry.get('table')}: {str(entry.get('reason'))[:80]}...")

    tables: dict = {}
    for name, spec in backup_tables.TABLES.items():
        state = (site_tables.get(name) or {}).get("state")
        if state in ("absent_optional",):
            print(f"  {name}: absent on this install (optional) - skipped, not zero")
            continue
        if state == "absent_unexpected":
            print(f"  {name}: REQUIRED table absent on the site")
            tables[name] = {"rows": 0, "bytes": 0, "sha256": "", "site_count": None,
                            "restorable": spec["restorable"], "date_range": None}
            continue
        info = write_table(out_dir, name, spec)
        info["site_count"] = (site_tables.get(name) or {}).get("rows")
        tables[name] = info
        print(f"  {name}: {info['rows']:,} rows, {info['bytes'] / 1e6:.2f} MB gz "
              f"(site counted {info['site_count']})")

    manifest = {
        "exported_at": _now(),
        "schema_version": site.get("schema_version"),
        "plugin_version": site.get("plugin_version"),
        "build": site.get("build"),
        "generated_by": "railway/backup_export.py",
        "tables": tables,
        "total_rows": sum(t["rows"] for t in tables.values()),
        "total_bytes": sum(t["bytes"] for t in tables.values()),
        "excluded_tables": backup_tables.FORBIDDEN_TABLES,
        "external_tables": backup_tables.EXTERNAL_TABLES,
    }

    previous = load_state()
    verdict, lines = check_drift(manifest, previous)
    manifest["drift"] = {"verdict": verdict, "notes": lines}

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    took = time.time() - started
    print(f"\nexport: {manifest['total_rows']:,} rows, "
          f"{manifest['total_bytes'] / 1e6:.2f} MB compressed, {took:.0f}s")
    print(f"drift: {verdict}")
    for line in lines:
        print(f"  - {line}")

    if record and verdict != FAIL:
        # The state is what the NEXT run compares against, so a FAILING run must
        # not advance it. Recording a truncated export as the new normal is how
        # a one-week defect becomes permanent - the same reasoning that stops
        # data_integrity's recorder pinning a failing slice's baseline.
        STATE_PATH.write_text(json.dumps({
            "recorded_at": manifest["exported_at"],
            "plugin_version": manifest["plugin_version"],
            "schema_version": manifest["schema_version"],
            "total_rows": manifest["total_rows"],
            "total_bytes": manifest["total_bytes"],
            "took_seconds": round(took),
            "tables": {k: {"rows": v["rows"], "bytes": v["bytes"],
                           "sha256": v["sha256"], "date_range": v["date_range"]}
                       for k, v in tables.items()},
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded baseline -> {STATE_PATH.name}")
    elif record:
        print("baseline NOT advanced: a failing run must not become the new normal")

    if report:
        status = {PASS: "ok", FAIL: "degraded", UNKNOWN: "degraded"}[verdict]
        detail = (f"{verdict}: {manifest['total_rows']:,} rows, "
                  f"{manifest['total_bytes'] / 1e6:.1f} MB gz across "
                  f"{len(tables)} table(s)")
        if verdict != PASS and lines:
            detail += f" - {lines[0]}"
        source_health.report_source_health(HEALTH_SOURCE, status,
                                           entries=manifest["total_rows"],
                                           detail=detail)

    return 0 if verdict == PASS else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="backup-out", help="directory to write the export into")
    ap.add_argument("--report", action="store_true", help="write the verdict to the health ledger")
    ap.add_argument("--record", action="store_true", help="advance railway/backup_state.json on a non-failing run")
    args = ap.parse_args(argv)

    try:
        code = run(Path(args.out), report=args.report, record=args.record)
    except host_call.Deferred as exc:
        # The host never answered. Not this job's defect, and a red run here
        # would fire an alert at a route on the host that is down. The third
        # consecutive deferral exits non-zero; that rule lives in host_call.
        count = host_call.defer(JOB, str(exc))
        print(f"DEFERRED: {exc}")
        print(f"This is deferral {count} in a row for {JOB}. UNKNOWN, never a pass.")
        source_health.report_source_health(
            HEALTH_SOURCE, "degraded", 0,
            f"UNKNOWN: the host never answered ({count} deferral(s) running)")
        return 0 if count < 3 else 2
    except (backup_tables.PersonalDataInExport, backup_tables.UnpinnedColumn) as exc:
        # Loud, and nothing is published. These are the two failures where
        # continuing is worse than stopping.
        print(f"REFUSED: {exc}", file=sys.stderr)
        source_health.report_source_health(
            HEALTH_SOURCE, "degraded", 0, f"REFUSED: {type(exc).__name__}")
        return 2

    host_call.clear(JOB)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
