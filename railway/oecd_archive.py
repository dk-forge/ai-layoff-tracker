#!/usr/bin/env python3
"""Write the OECD monthly unemployment full history into data/archive/oecd/.

    python oecd_archive.py --out ../data/archive/oecd

One keyless SDMX request with no start period returns every month the OECD
holds. Written as a sorted, compact CSV (a few MB) so git stores each monthly
refresh as a small delta; oecd-archive.yml commits it. CC BY 4.0: the
ATTRIBUTION is written beside it in MANIFEST.json and must travel with any copy.
Stdlib only. Prints one `::notice title=oecd-archive::` line.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sources import oecd_unemployment as oecd  # noqa: E402

CSV_NAME = "unemployment_monthly.csv"
#: Refuse to replace the archive with something this much smaller than it.
MIN_KEEP_RATIO = 0.9
#: "Small" means small: anything bigger goes to a Release, never git.
MAX_BYTES = 40_000_000


def write(out: str, rows) -> dict:
    os.makedirs(out, exist_ok=True)
    body = oecd.to_csv(rows).encode()
    if len(body) > MAX_BYTES:
        raise RuntimeError(f"archive is {len(body)} B, over the {MAX_BYTES} B git ceiling; "
                           "move it to a Release asset like bls-archive.yml")
    path = os.path.join(out, CSV_NAME)
    if os.path.exists(path) and len(body) < MIN_KEEP_RATIO * os.path.getsize(path):
        raise RuntimeError(f"new archive {len(body)} B is under {MIN_KEEP_RATIO:.0%} "
                           f"of the existing {os.path.getsize(path)} B; not replacing")
    with open(path, "wb") as fh:
        fh.write(body)
    manifest = {
        "source": oecd.SOURCE, "dataflow": oecd.DATAFLOW, "query": oecd.url(),
        "file": CSV_NAME, "rows": len(rows), "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "first_month": min((r[3] for r in rows), default=None),
        "latest_month": max((r[3] for r in rows), default=None),
        "countries": len({r[0] for r in rows}),
        "licence": oecd.LICENCE, "attribution": oecd.ATTRIBUTION,
    }
    with open(os.path.join(out, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "..", "data", "archive", "oecd"))
    a = ap.parse_args(argv)
    try:
        rows = oecd.parse_csv(oecd.fetch_csv(None, timeout=600))
        if not rows:
            raise RuntimeError("no rows parsed")
        m = write(a.out, rows)
    except Exception as exc:
        print(f"::error title=oecd-archive::{exc}")
        return 1
    print(f"::notice title=oecd-archive::rows={m['rows']} countries={m['countries']} "
          f"{m['first_month']}..{m['latest_month']} bytes={m['bytes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
