"""Has ANY collector run at all lately? The alarm for "both ingest hosts off".

WHY THIS EXISTS (2026-10-05 weekly learning review). The daily ingest can run on
two hosts: Railway's cron and `ingest-cron-vps.yml`, which fires only when the
repo variable `ALT_INGEST_ON_VPS` is 'true'. When Railway's cron was retired and
the variable was never set, NEITHER host ran, and nothing said so for seven days.

The existing monitors could not catch it, by construction:
  * `run_completion.py` pairs `running` notes with terminal notes. With no runs
    there is nothing to pair, so it reports no orphans: green.
  * `source_freshness.py` judges whether sources PUBLISH something new. A quiet
    week and a dead pipeline look the same to it.

So this module asks the one question neither asks: when was the NEWEST note of
any kind on `/source-runs`? If it is older than MAX_SILENCE, the pipeline is
not running, whatever the reason. No fix is attempted here; the verdict names
both hosts so the owner can turn one back on.

Stdlib only; read-only public GET.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

BASE = "https://asktherecruiter.com/blog"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# DERIVATION: ingest is scheduled once a day (22:00 UTC). One missed day can be
# a transient host fault; two missed days in a row is a pipeline that is off.
# Two days, not seven: the 2026-09 incident went unnoticed for seven.
MAX_SILENCE = timedelta(days=2)


CRON_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cron.py")


def ingest_sources(path=CRON_PY):
    """Source ids the DAILY ingest (cron.py) writes to /source-runs.

    WHY (2026-10-05, sandbox #1259): the WARN importers run on their own daily
    workflow and also write /source-runs notes (warn_us, warn_custom_states...).
    Counting them meant the alarm said "alive" while cron.py had not run for 6.6
    days. Derived by parsing cron.py (no import: it needs requests + secrets):
    every literal first argument of report_source_health(...) plus every
    ("name", collector) pair in its collector table, so a new collector is
    covered without editing a hand list.
    """
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "report_source_health"
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            names.add(node.args[0].value)
        elif (isinstance(node, ast.Tuple) and len(node.elts) == 2
              and isinstance(node.elts[0], ast.Constant) and isinstance(node.elts[0].value, str)
              and isinstance(node.elts[1], (ast.Name, ast.Attribute))):
            names.add(node.elts[0].value)
    return names


def newest_run(runs, sources=None):
    """The newest parseable `attempted_at` among the rows, or None.

    With `sources`, only rows whose `source` is in that set count."""
    best = None
    for r in runs or ():
        if not isinstance(r, dict):
            continue
        if sources is not None and r.get("source") not in sources:
            continue
        try:
            at = datetime.fromisoformat(
                str(r.get("attempted_at")).replace("Z", "+00:00"))
        except Exception:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if best is None or at > best:
            best = at
    return best


def verdict(runs, now=None, max_silence=MAX_SILENCE, sources=None):
    """(ok, line). ok is False when no DAILY-INGEST run is recent enough,
    INCLUDING no runs. Other writers (the WARN workflow) do not count."""
    now = now or datetime.now(timezone.utc)
    newest = newest_run(runs, ingest_sources() if sources is None else sources)
    if newest is None:
        return False, (f"INGEST SILENT: no collector run recorded on /source-runs "
                       f"in the window. Check both hosts: Railway cron and the "
                       f"repo variable ALT_INGEST_ON_VPS (ingest-cron-vps.yml).")
    age = now - newest
    if age > max_silence:
        hours = int(age.total_seconds() // 3600)
        return False, (f"INGEST SILENT: newest collector run was {newest.isoformat()} "
                       f"({hours}h ago, limit {int(max_silence.total_seconds() // 3600)}h). "
                       f"Check both hosts: Railway cron and the repo variable "
                       f"ALT_INGEST_ON_VPS (ingest-cron-vps.yml).")
    return True, f"ingest alive: newest collector run {newest.isoformat()}"


def _fetch(days):
    url = f"{BASE}/wp-json/layoffs/v1/source-runs?days={days}&per_page=200&cb={uuid.uuid4()}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.load(resp)


def main():
    try:
        data = _fetch(days=7) or {}
    except Exception as exc:  # unreadable is UNKNOWN, never a pass
        print(f"INGEST SILENCE UNKNOWN: could not read /source-runs ({exc})")
        return 3
    ok, line = verdict(data.get("runs") or [])
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
