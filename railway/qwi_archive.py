#!/usr/bin/env python3
"""Archive each pulled Census QWI quarter into data/archive/qwi/<YYYY-Qn>.csv.

    CENSUS_API_KEY=... python qwi_archive.py --out ../data/archive/qwi

The served document keeps only the latest 8 quarters; this keeps every
quarter we have ever pulled, one sorted CSV per quarter (~100-200 KB each),
so git history grows by one small file a quarter plus revisions. Same
approach as oecd_archive.py (committed to git, not a Release: it is small).
A quarter file is never replaced by one under 90% of its size (QWI revises,
it does not shrink). The key is never printed. Stdlib only. Prints one
`::notice title=qwi-archive::` line.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import census_qwi as qwi  # noqa: E402

MIN_KEEP_RATIO = 0.9
MAX_BYTES = 5_000_000   # per quarter file; anything bigger means the query changed


def to_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(qwi.FIELDS)
    w.writerows(sorted(rows, key=lambda r: [str(x) for x in r[:9]]))
    return buf.getvalue().encode()


def write(out: str, datasets: dict) -> dict:
    os.makedirs(out, exist_ok=True)
    byq = {}
    for rows in datasets.values():
        for r in rows:
            byq.setdefault(r[2], []).append(r)
    files, kept = {}, []
    for q, rows in sorted(byq.items()):
        body = to_csv(rows)
        if len(body) > MAX_BYTES:
            raise RuntimeError(f"{q} is {len(body)} B, over {MAX_BYTES} B")
        path = os.path.join(out, f"{q}.csv")
        if os.path.exists(path) and len(body) < MIN_KEEP_RATIO * os.path.getsize(path):
            kept.append(q)   # a thinner re-pull never replaces a fuller quarter
            continue
        with open(path, "wb") as fh:
            fh.write(body)
        files[q] = {"rows": len(rows), "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()}
    man_path = os.path.join(out, "MANIFEST.json")
    try:
        with open(man_path) as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        manifest = {}
    manifest.update({"source": qwi.SOURCE, "api": qwi.API, "fields": qwi.FIELDS,
                     "codes": qwi.CODES, "licence": qwi.LICENCE,
                     "attribution": qwi.ATTRIBUTION})
    manifest.setdefault("quarters", {}).update(files)
    manifest["quarters"] = dict(sorted(manifest["quarters"].items()))
    with open(man_path, "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    return {"written": sorted(files), "kept": kept}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "data", "archive", "qwi"))
    a = ap.parse_args(argv)
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not key:
        print("::error title=qwi-archive::CENSUS_API_KEY secret is missing or empty")
        return 1
    try:
        p = qwi.pull(key)
        if p["errors"] or not p["rows"]:
            raise RuntimeError("partial pull: " + "; ".join(p["errors"])[:500])
        r = write(a.out, p["datasets"])
    except Exception as exc:
        print(f"::error title=qwi-archive::{qwi.scrub(exc, key)}")
        return 1
    print(f"::notice title=qwi-archive::written={','.join(r['written'])} kept={','.join(r['kept']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
