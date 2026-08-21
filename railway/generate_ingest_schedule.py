#!/usr/bin/env python3
"""Derive the public "next update" schedule from the REAL ingest cron.

The tracker page promises a next-collection time (Eurostat pattern: headline +
dateline + next release). That promise must come from railway/railway.toml,
the cron that actually runs, never from typed copy: the old typed
"9 AM & 6 PM ET" was DST-wrong half the year (the cron is UTC-fixed) and would
silently lie if the schedule ever moved.

Writes wordpress-plugin/ai-layoff-tracker/data/ingest-schedule.json, which the
plugin reads (alt_ingest_schedule in db.php) and layoffs.js receives via
altData.ingest. If the file is missing or malformed, every consumer renders
NOTHING there: an absent schedule is honest, a stale typed one is not (same
contract as data/recall-measurement.json).

Output is deterministic (no timestamp), so a regen with an unchanged cron is a
byte-for-byte no-op. tests/test_ingest_schedule.py fails when the committed
JSON drifts from railway.toml, so the cron cannot move without this file
following it.
"""
from __future__ import annotations

import ast
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOML = ROOT / "railway" / "railway.toml"
OUT = ROOT / "wordpress-plugin" / "ai-layoff-tracker" / "data" / "ingest-schedule.json"


def parse_cron_schedule(toml_text: str) -> dict:
    """Extract cronSchedule and reduce it to daily UTC hours + minute.

    Only the shape this service actually uses is supported (fixed minute,
    comma list of hours, every day). Anything else raises: a silent fallback
    here would put a wrong promise on the flagship page.
    """
    m = re.search(r'^\s*cronSchedule\s*=\s*"([^"]+)"', toml_text, re.M)
    if not m:
        raise ValueError("no cronSchedule found in railway.toml")
    cron = m.group(1).strip()
    fields = cron.split()
    if len(fields) != 5:
        raise ValueError(f"unexpected cron shape: {cron!r}")
    minute_f, hour_f, dom, month, dow = fields
    if (dom, month, dow) != ("*", "*", "*"):
        raise ValueError(f"schedule is not simple-daily, refusing to summarise: {cron!r}")
    if not re.fullmatch(r"\d{1,2}", minute_f):
        raise ValueError(f"unsupported minute field: {minute_f!r}")
    minute = int(minute_f)
    if not 0 <= minute <= 59:
        raise ValueError(f"minute out of range: {minute}")
    hours = []
    for h in hour_f.split(","):
        if not re.fullmatch(r"\d{1,2}", h):
            raise ValueError(f"unsupported hour field: {hour_f!r}")
        hv = int(h)
        if not 0 <= hv <= 23:
            raise ValueError(f"hour out of range: {hv}")
        hours.append(hv)
    if not hours:
        raise ValueError(f"no hours in cron: {cron!r}")
    return {
        "cron": cron,
        "utc_hours": sorted(set(hours)),
        "utc_minute": minute,
        "cadence": "daily",
        "source": "railway/railway.toml [deploy] cronSchedule",
    }


# Rotating query rings the PUBLIC pages quote a sweep time for. Each run takes
# `per_run` terms and `run_slice.rotate` steps by exactly one run, so the full
# sweep is ceil(size / per_run) RUNS -- which is only a number of DAYS once you
# know the cadence. That is the whole reason these are derived here instead of
# typed: the Sources page said "about every six days" for the editions ring,
# which was true at two runs a day and became eleven days on 2026-08-14 with
# nobody to notice. Sizes are read from the collectors by AST so this stays
# stdlib-only and needs no key, no network and no optional dependency.
ROTATIONS = (
    # (public key, module, terms symbol, per-run symbol, skip_first)
    # google_news pins the US edition and rotates only the remainder.
    ("news_editions", "sources/google_news.py",
     "GOOGLE_NEWS_LOCALES", "LOCALES_PER_RUN", True),
    ("gdelt_segments", "sources/gdelt.py",
     "SEGMENT_TERMS", "SEGMENT_QUERIES_PER_RUN", False),
)


def _ring_size(module_rel: str, terms: str, skip_first: bool) -> int:
    src = (ROOT / "railway" / module_rel).read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == terms for t in node.targets):
            n = len(ast.literal_eval(node.value))
            return n - 1 if skip_first else n
    raise ValueError(f"{terms} not found in {module_rel}")


def _per_run(module_rel: str, name: str) -> int:
    src = (ROOT / "railway" / module_rel).read_text(encoding="utf-8")
    m = re.search(re.escape(name) + r'\s*=\s*max\(0,\s*min\(\d+,\s*(?:int\(\s*os\.environ\.get\('
                  r'\s*"[A-Z_]+"\s*,\s*"(\d+)"\s*\)\s*\)|_env_int\(\s*"[A-Z_]+"\s*,\s*(\d+)\s*\))', src)
    if not m:
        raise ValueError(f"could not read the shipped default for {name}")
    return int(m.group(1) or m.group(2))


def rotation_sweeps(runs_per_day: int) -> dict:
    """Days to sweep each public rotating ring once, at this cadence."""
    out = {}
    for key, module_rel, terms, per_run_name, skip_first in ROTATIONS:
        size = _ring_size(module_rel, terms, skip_first)
        per_run = _per_run(module_rel, per_run_name)
        if per_run <= 0:
            continue
        runs = math.ceil(size / per_run)
        out[key] = {
            "terms": size,
            "per_run": per_run,
            "runs": runs,
            "days": math.ceil(runs / max(1, runs_per_day)),
        }
    return out


def build_schedule(toml_text: str) -> dict:
    """The whole committed document: the cron, plus what it implies.

    One function so the generator and tests/test_ingest_schedule.py cannot
    disagree about what the file should contain.
    """
    schedule = parse_cron_schedule(toml_text)
    schedule["rotation"] = rotation_sweeps(len(schedule["utc_hours"]))
    return schedule


def main() -> int:
    schedule = build_schedule(TOML.read_text(encoding="utf-8"))
    rendered = json.dumps(schedule, indent=2, sort_keys=True) + "\n"
    if OUT.exists() and OUT.read_text(encoding="utf-8") == rendered:
        print(f"unchanged: {OUT}")
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT}: {schedule['cron']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
