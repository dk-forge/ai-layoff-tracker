"""Probe the WARN LLM count-fallback WITHOUT posting.

Runs the fragile fetchers with WARN_LLM_FALLBACK=1 so the shared helper prints a
`::notice:: [warn-llm-fallback] <state> <company>: recovered count N` line every
time it rescues a row the deterministic parser dropped (regex count was 0). Posts
nothing. Use it to eyeball what the fallback would add before enabling it in the
live import. Requires OPENROUTER_API_KEY.

    WARN_LLM_FALLBACK=1 OPENROUTER_API_KEY=... python warn_llm_probe.py
"""
import os
import sys

os.environ.setdefault("WARN_LLM_FALLBACK", "1")

from sources.warn_custom import (
    fetch_fl, fetch_ga, fetch_mi, fetch_ny_history, fetch_id, fetch_la, fetch_nc,
)
from sources.warn_new_states import fetch_wa, fetch_ms, fetch_wv

FETCHERS = {
    "FL": fetch_fl, "GA": fetch_ga, "MI": fetch_mi, "NY": fetch_ny_history,
    "ID": fetch_id, "LA": fetch_la, "NC": fetch_nc,
    "WA": fetch_wa, "MS": fetch_ms, "WV": fetch_wv,
}


def main():
    if os.environ.get("WARN_LLM_FALLBACK") != "1" or not os.environ.get("OPENROUTER_API_KEY"):
        print("Set WARN_LLM_FALLBACK=1 and OPENROUTER_API_KEY to probe.")
        return 1
    print("Probing WARN LLM count-fallback (no posting). Recoveries are printed "
          "as ::notice:: lines by the shared helper.\n")
    total = 0
    for st, fn in FETCHERS.items():
        try:
            rows = fn()
            total += len(rows)
            print(f"{st}: {len(rows)} row(s) parsed")
        except Exception as exc:
            print(f"{st}: FAILED ({exc})")
    print(f"\nTotal rows across fragile fetchers: {total}. "
          "Any ::notice:: lines above are the fallback's recoveries — review them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
