"""Bring the live GDELT work ledger back to the committed file.

Since 2026-08-28 the live cron keeps the ledger of unfinished GDELT windows on
the host (the keyed /tracker-meta endpoint), because an ephemeral container
keeps no file. The committed railway/gdelt_work_ledger.json is what a local
run, a test and a reviewer read, and nothing wrote it after the commit that
added it: ops_status [2f] called it NEVER_USED on 2026-09-05 while the host
held 77 slots. This is the one writer. It runs from the daily balance/harvest
workflow, which commits the file with the other ledgers.

It reads through the SAME loader the cron uses (file unioned with the host
copy) and writes the file WITHOUT pushing back, so it can never overwrite the
host with a stale checkout. An unreadable host leaves the file byte-identical
and prints UNKNOWN: a file that stops changing is then the honest signal, read
by state_liveness, rather than a fresh file that says nothing is owed. Output
is counts only; slot keys are never printed here.
"""
from __future__ import annotations

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources import gdelt  # noqa: E402


def main(path: str | None = None) -> int:
    path = path or gdelt.WORK_LEDGER_PATH
    gdelt._REMOTE_LEDGER_READ = False
    ledger = gdelt._load_work_ledger(path=path, remote=True)
    if not gdelt._REMOTE_LEDGER_READ:
        print("GDELT ledger harvest: UNKNOWN, /tracker-meta could not be read; "
              "the committed file is left exactly as it was, which is not a pass")
        return 0
    gdelt._save_work_ledger(ledger, path=path, remote=False)
    by_status = collections.Counter(
        str(slot.get("status")) for slot in ledger.get("slots", {}).values())
    summary = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    print(f"GDELT ledger harvest: {len(ledger.get('slots', {}))} slot(s) written "
          f"to the committed file ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
