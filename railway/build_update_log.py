#!/usr/bin/env python3
"""Build the public update log from docs/release-notes.d.

The release notes are already written for readers, one file per change, with a
small front matter block:

    ---
    version: 2.20.301
    type: fix
    area: seo
    date: 2026-11-09
    ---
    One or two plain sentences a reader can understand.

This turns them into wordpress-plugin/ai-layoff-tracker/data/update-log.json,
which /ai-layoff-tracker/update-log/ renders. The page is DERIVED, never typed:
railway/tests/test_public_logs_pages.py fails when the committed file and the
notes disagree, the same way the ingest cadence is derived from railway.toml.

A note is LISTED only once it has shipped: its version must be a real
MAJOR.MINOR.PATCH no newer than the plugin's own `Version:` header. `vNEXT`
and anything ahead of the plugin are unreleased, and listing them would tell a
reader something is live that is not.

Stdlib only. `--check` exits 1 when the committed file is stale.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NOTES_DIR = os.path.join(ROOT, "docs", "release-notes.d")
PLUGIN_MAIN = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "ai-layoff-tracker.php")
OUT = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "data", "update-log.json")

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# House style: no em-dashes in UI copy. A note carrying one is refused rather
# than silently rewritten, so the source file gets fixed.
FORBIDDEN = ("—", "&mdash;")
TYPE_LABELS = {"fix": "Fix", "feat": "New", "feature": "New"}


def vkey(version: str) -> tuple:
    return tuple(int(p) for p in version.split("."))


def plugin_version(main_php: str = PLUGIN_MAIN) -> str:
    with open(main_php, encoding="utf-8") as fh:
        match = re.search(r"^\s*\*\s*Version:\s*([0-9.]+)\s*$", fh.read(), re.M)
    if not match:
        raise ValueError(f"no Version: header in {main_php}")
    return match.group(1)


def parse(text: str) -> tuple[dict, str] | None:
    """Front matter and body, or None for a file with no front matter."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not match:
        return None
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip()
    return meta, match.group(2).strip()


def build(notes_dir: str = NOTES_DIR, main_php: str = PLUGIN_MAIN) -> dict:
    current = vkey(plugin_version(main_php))
    entries = []
    for name in sorted(os.listdir(notes_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(notes_dir, name), encoding="utf-8") as fh:
            parsed = parse(fh.read())
        if parsed is None:
            continue
        meta, body = parsed
        version, date = meta.get("version", ""), meta.get("date", "")
        if not VERSION_RE.match(version) or vkey(version) > current:
            continue  # unreleased (vNEXT) or ahead of the deployed plugin
        if not DATE_RE.match(date) or not body:
            raise ValueError(f"{name}: a released note needs a YYYY-MM-DD date and a body")
        for bad in FORBIDDEN:
            if bad in body:
                raise ValueError(f"{name}: em-dash in reader-facing copy")
        kind = meta.get("type", "").lower()
        entries.append({
            "slug": name[:-3],
            "date": date,
            "version": version,
            "type": TYPE_LABELS.get(kind, kind.capitalize() or "Change"),
            "area": meta.get("area", ""),
            "text": " ".join(body.split()),
        })
    entries.sort(key=lambda e: (e["date"], vkey(e["version"]), e["slug"]), reverse=True)
    return {"source": "docs/release-notes.d", "entries": entries}


def render(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed file is stale")
    args = ap.parse_args(argv)
    fresh = render(build())
    if args.check:
        try:
            with open(OUT, encoding="utf-8") as fh:
                current = fh.read()
        except OSError:
            current = ""
        if current != fresh:
            print("update-log.json is STALE: run python3 railway/build_update_log.py")
            return 1
        print("update-log.json is current")
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(fresh)
    print(f"wrote {len(json.loads(fresh)['entries'])} entries to {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
