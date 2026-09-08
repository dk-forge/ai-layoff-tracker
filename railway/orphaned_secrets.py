#!/usr/bin/env python3
"""Secrets this repository holds and no code reads.

WHY THIS EXISTS (sandbox issue #722). On 2026-08-25 the owner registered with
Erhvervsstyrelsen for system-to-system access to Denmark's CVR register, set
DENMARK_DATA_USER and DENMARK_DATA_PASSWORD, and the collector was never
built. The follow-up question went unanswered and nothing recorded it. Two
more were found in the same sweep: JOBINDSATS_API_KEY and FMP_API_KEY, both
with zero references anywhere.

He did the hard part in each case, which is the registration and the waiting.
What was missing was anything that notices.

WHY NO EXISTING GUARD CAUGHT IT. `source_inventory.unimplemented_collectors()`
checks DECLARED collectors: ids that already carry a `meta{}` label. A
collector nobody declared is invisible to it. That guard was built for the
opposite failure, a label with no collector; this is a credential with no
collector, and nothing looked from that direction.

WHAT AN ORPHAN COSTS. A live credential for an integration that does not exist
is a standing grant with no benefit: it cannot break anything, so nobody
notices it, and it sits until it leaks or expires. It is also a record of
intent that was lost, which is the more expensive half.

WHY THIS IS NOT A WORKFLOW. Listing repository secrets needs admin scope,
which a workflow's GITHUB_TOKEN does not have and should not be given. It runs
from `ops_status.py` on a human's authenticated `gh`, at session start, which
is where the rest of the once-a-session questions are asked.

Read-only. Prints NAMES ONLY, never a value: `gh secret list` does not expose
values and this never asks for one.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

#: Searched for a reference to each secret name. CODE AND WORKFLOWS ONLY.
#:
#: `docs/` is deliberately excluded, and that is not an oversight. The first
#: run of this check searched docs too and cleared DENMARK_DATA_USER,
#: JOBINDSATS_API_KEY and FMP_API_KEY -- the three orphans it was written to
#: find -- because an issue and a TECHLOG entry ABOUT the orphans mention them
#: by name. Writing down that a credential is unused would have marked it
#: used. The question is whether code reads it, and only code can answer that.
_SEARCH_DIRS = ("railway", ".github", "wordpress-plugin", "scripts")

#: Names that are legitimately unreferenced in this checkout.
#:
#: EVERY entry needs a reason, because the whole failure this catches is a
#: credential nobody could account for. "Probably fine" is how the Denmark
#: keys sat for five days.
KNOWN_UNREFERENCED: dict[str, str] = {
    "GITHUB_TOKEN": "provided by Actions itself, never declared by us",
}


def _repo_secret_names() -> tuple[list[str], str]:
    """Secret names from `gh`. Returns (names, error)."""
    try:
        out = subprocess.run(
            ["gh", "secret", "list", "--json", "name"],
            cwd=REPO, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], f"could not run gh: {exc}"
    if out.returncode != 0:
        return [], (out.stderr or "gh secret list failed").strip()[:160]
    try:
        return [row["name"] for row in json.loads(out.stdout or "[]")], ""
    except (ValueError, KeyError, TypeError) as exc:
        return [], f"unreadable gh output: {exc}"


def _referenced(name: str) -> bool:
    """True when the repository mentions this secret name anywhere."""
    pattern = re.compile(re.escape(name))
    for rel in _SEARCH_DIRS:
        base = REPO / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg", ".zip"}:
                continue
            # THIS FILE DOES NOT COUNT. Measured on the first run: the guard
            # cleared DENMARK_DATA_USER, JOBINDSATS_API_KEY and FMP_API_KEY --
            # the three orphans it exists to find -- because its own docstring
            # names them as the reason it was written. A checker that reads
            # itself is the purest form of a guard sharing its target's blind
            # spot, and it reported a clean result while looking straight at
            # the problem.
            if path.resolve() == pathlib.Path(__file__).resolve():
                continue
            try:
                if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                continue
    return False


def report() -> int:
    """0 clean, 2 an orphan exists, 3 could not check."""
    names, err = _repo_secret_names()
    print("\n[11] ORPHANED SECRETS  (a credential no code reads)")
    if err:
        print(f"      UNKNOWN: {err}")
        print("      A check that could not run is not a pass. Needs an")
        print("      authenticated `gh` with admin scope on this repository.")
        return 3
    orphans = [
        n for n in names
        if n not in KNOWN_UNREFERENCED and not _referenced(n)
    ]
    if not orphans:
        print(f"      every one of the {len(names)} secret(s) is referenced by code")
        return 0
    for n in sorted(orphans):
        print(f"      ORPHAN   {n}")
    print(f"\n      {len(orphans)} secret(s) exist that nothing in this repository reads.")
    print("      Each is a live grant for an integration that does not exist, and a")
    print("      record of intent that was lost. Decide per secret: BUILD the thing")
    print("      it was obtained for, or REVOKE it and say so in TECHLOG. Adding a")
    print("      name to KNOWN_UNREFERENCED needs a reason, not a shrug.")
    return 2


if __name__ == "__main__":
    sys.exit(report())
