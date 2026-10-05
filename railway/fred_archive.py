#!/usr/bin/env python3
"""Write the full history of the curated FRED series into data/archive/fred/.

    FRED_API_KEY=... python fred_archive.py --out ../data/archive/fred

One request per series with no start date returns every observation FRED
holds (ICSA weekly since 1967 is the biggest, a few thousand rows). Written as
a sorted compact CSV (well under 1 MB) so git stores each refresh as a small
delta; fred-archive.yml commits it. Same approach as oecd_archive.py. The key
is never printed. Stdlib only. Prints one `::notice title=fred-archive::` line.
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

from sources import fred_labour as fred  # noqa: E402

CSV_NAME = "observations.csv"
MIN_KEEP_RATIO = 0.9
MAX_BYTES = 40_000_000
FULL_HISTORY_START = "1900-01-01"


def to_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["series_id", "date", "value"])
    w.writerows(sorted((r[0], r[1], r[2]) for r in rows))
    return buf.getvalue().encode()


def write(out: str, rows) -> dict:
    os.makedirs(out, exist_ok=True)
    body = to_csv(rows)
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"archive is {len(body)} B, over the {MAX_BYTES} B git ceiling")
    path = os.path.join(out, CSV_NAME)
    if os.path.exists(path) and len(body) < MIN_KEEP_RATIO * os.path.getsize(path):
        raise RuntimeError(f"new archive {len(body)} B is under {MIN_KEEP_RATIO:.0%} "
                           f"of the existing {os.path.getsize(path)} B; not replacing")
    with open(path, "wb") as fh:
        fh.write(body)
    manifest = {
        "source": fred.SOURCE, "api": fred.API, "file": CSV_NAME,
        "series": {s: {"label": v[0], "category": v[1], "frequency": v[2], "units": v[3]}
                   for s, v in fred.SERIES.items()},
        "rows": len(rows), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        "first_date": min((r[1] for r in rows), default=None),
        "latest_date": max((r[1] for r in rows), default=None),
        "licence": fred.LICENCE, "attribution": fred.ATTRIBUTION,
    }
    with open(os.path.join(out, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "data", "archive", "fred"))
    a = ap.parse_args(argv)
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        print("::error title=fred-archive::FRED_API_KEY secret is missing or empty")
        return 1
    try:
        p = fred.pull(key, FULL_HISTORY_START)
        if p["errors"] or not p["rows"]:
            raise RuntimeError("partial pull: " + "; ".join(p["errors"])[:500])
        m = write(a.out, p["datasets"]["observations"])
    except Exception as exc:
        print(f"::error title=fred-archive::{fred.scrub(exc, key)}")
        return 1
    print(f"::notice title=fred-archive::rows={m['rows']} {m['first_date']}..{m['latest_date']} "
          f"bytes={m['bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
