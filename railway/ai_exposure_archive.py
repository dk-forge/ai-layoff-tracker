#!/usr/bin/env python3
"""Archive the joined AI-exposure tables into data/archive/ai_exposure/.

    python ai_exposure_archive.py --out ../data/archive/ai_exposure

One sorted CSV per dataset per OEWS release (`occupations-M2025.csv`,
`metros-M2025.csv`, `metro_occupations-M2025.csv`, ~100 KB together) plus
MANIFEST.json with the study commit, versions, licences and hashes. The
served document holds only the newest release; this keeps every one. Same
approach as qwi_archive.py: committed to git, refuses a partial pull, and a
file is never replaced by one under 90% of its size. Prints one
`::notice title=ai-exposure-archive::` line. No key.
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

from sources import ai_exposure as ax  # noqa: E402

MIN_KEEP_RATIO = 0.9
MAX_BYTES = 5_000_000


def to_csv(header, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(sorted(rows, key=lambda r: [str(x) for x in r]))
    return buf.getvalue().encode()


def write(out: str, payload: dict) -> dict:
    os.makedirs(out, exist_ok=True)
    tag = "M" + payload["latest"]["oews"][:4]
    files, kept = {}, []
    for name, header in payload["columns"].items():
        body = to_csv(header, payload["datasets"][name])
        if len(body) > MAX_BYTES:
            raise RuntimeError(f"{name} is {len(body)} B, over {MAX_BYTES} B")
        fn = f"{name}-{tag}.csv"
        path = os.path.join(out, fn)
        if os.path.exists(path) and len(body) < MIN_KEEP_RATIO * os.path.getsize(path):
            kept.append(fn)
            continue
        with open(path, "wb") as fh:
            fh.write(body)
        files[fn] = {"rows": len(payload["datasets"][name]), "bytes": len(body),
                     "sha256": hashlib.sha256(body).hexdigest()}
    man_path = os.path.join(out, "MANIFEST.json")
    try:
        with open(man_path) as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        manifest = {}
    manifest.update({"source": ax.SOURCE, "study": ax.STUDY, "licence": ax.LICENCE,
                     "attribution": payload["attribution"], "threshold": payload["threshold"],
                     "columns": payload["columns"]})
    manifest.setdefault("releases", {})[tag] = payload["versions"]
    manifest.setdefault("files", {}).update(files)
    manifest["files"] = dict(sorted(manifest["files"].items()))
    with open(man_path, "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return {"written": sorted(files), "kept": kept}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "data", "archive", "ai_exposure"))
    a = ap.parse_args(argv)
    try:
        pull = ax.pull()
        if pull["errors"] or not pull["payload"]["datasets"]["occupations"]:
            raise RuntimeError("partial pull: " + "; ".join(pull["errors"])[:500])
        r = write(a.out, pull["payload"])
    except Exception as exc:
        print(f"::error title=ai-exposure-archive::{str(exc)[:600]}")
        return 1
    print(f"::notice title=ai-exposure-archive::written={','.join(r['written']) or '-'} "
          f"kept={','.join(r['kept']) or '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
