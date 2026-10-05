#!/usr/bin/env python3
"""Download the BLS JOLTS + CPS full-history flat files for a monthly archive.

    python bls_archive.py --out bls-archive/

The keyless API stops at ten years per request; the full history lives in the
flat files under https://download.bls.gov/pub/time.series/{jt,ln}/. Together
they are ~150 MB, far too big for git, so bls-archive.yml attaches them (gzip)
to a GitHub Release `bls-archive-YYYY-MM` instead and commits nothing.

Kept: every JOLTS file, and the CPS (LN) mapping files plus `ln.data.1.AllData`
(every LN series). The other `ln.data.*` files are subsets of AllData and are
skipped. A MANIFEST.json lists name, bytes and sha256 per file.

BLS refuses anonymous scripted downloads, so the User-Agent carries a contact
address as BLS asks (https://www.bls.gov/bls/pss.htm). Public domain data.
Stdlib only. Prints one `::notice title=bls-archive::` line.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request

BASE = "https://download.bls.gov/pub/time.series/"
UA = ("AiLayoffTracker/1.0 (+https://asktherecruiter.com; "
      "errornotifications-production@asktherecruiter.com)")
SURVEYS = ("jt", "ln")


def wanted(survey: str, name: str) -> bool:
    if not name.startswith(survey + "."):
        return False
    if survey == "ln" and name.startswith("ln.data.") and name != "ln.data.1.AllData":
        return False
    return True


def listing_names(html: str, survey: str) -> list:
    names = re.findall(r'href="[^"]*/' + survey + r'/([^"/]+)"', html, flags=re.I)
    return sorted({n for n in names if wanted(survey, n)})


def _get(url, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def download(out: str) -> dict:
    os.makedirs(out, exist_ok=True)
    files, total = [], 0
    for survey in SURVEYS:
        with _get(BASE + survey + "/") as r:
            names = listing_names(r.read().decode("utf-8", "replace"), survey)
        if not names:
            raise RuntimeError(f"no files listed for {survey}")
        for name in names:
            dest = os.path.join(out, name + ".gz")
            h, n = hashlib.sha256(), 0
            for attempt in range(3):
                try:
                    with _get(BASE + survey + "/" + name) as r, gzip.open(dest, "wb") as gz:
                        h, n = hashlib.sha256(), 0
                        while True:
                            chunk = r.read(1 << 20)
                            if not chunk:
                                break
                            h.update(chunk)
                            n += len(chunk)
                            gz.write(chunk)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(10 * (attempt + 1))
            files.append({"name": name, "bytes": n, "sha256": h.hexdigest(),
                          "gz_bytes": os.path.getsize(dest)})
            total += n
    manifest = {"source": "bls_jolts_cps", "base": BASE, "files": files,
                "total_bytes": total, "licence": "Public domain (US Government work)",
                "attribution": "Source: U.S. Bureau of Labor Statistics (JOLTS, CPS)."}
    with open(os.path.join(out, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="bls-archive")
    a = ap.parse_args(argv)
    try:
        m = download(a.out)
    except Exception as exc:
        shutil.rmtree(a.out, ignore_errors=True)
        print(f"::error title=bls-archive::download failed: {exc}")
        return 1
    gz = sum(f["gz_bytes"] for f in m["files"])
    print(f"::notice title=bls-archive::files={len(m['files'])} raw_mb={m['total_bytes'] / 1e6:.1f} "
          f"gz_mb={gz / 1e6:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
