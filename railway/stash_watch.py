"""The git stash stack, surfaced — because it is shared and nothing else watches it.

WHY THIS EXISTS

The stash stack is per-REPOSITORY, not per-worktree. Every worktree of a repo
pushes onto and pops off the SAME stack. With a dozen agent worktrees live at
once that is a shared mutable structure with no owner, and this repo already
carries the evidence: `stash@{0}` here is literally labelled "restored: popped
by accident from a sibling worktree". CLAUDE.md forbids `git stash` for exactly
this reason.

WHY IT CANNOT BE PREVENTED, ONLY DETECTED

The rule is not being broken by hand — it is broken by tooling. `git rebase
--autostash` and `git pull --rebase --autostash` push a stash silently, and the
sibling talent repo accumulated FOUR of them that way. The obvious fix does not
work: `rebase.autoStash=false` is set locally in all three repos, but an
EXPLICIT `--autostash` on the command line overrides config, and there is no
config key and no hook that can refuse a stash push without risking a rebase
left half-finished. So this file does not pretend to enforce. It detects, and it
makes the detection actionable.

WHAT IT PRINTS, AND WHY THE DEFAULT IS THE CHEAP CHECK

"3 stash entries" tells nobody anything and gets skimmed. What a human needs is
whether the entry's content is already on `origin/main` — landed work parked in
a shared structure is clutter, unlanded work is a hostage. So every entry is
classified:

  LANDED       every file it touches is byte-identical to origin/main. The
               stash changed those files relative to its own base, and main now
               holds exactly the stash's version, so there is nothing in it that
               main does not have. Definitive, and one `rev-parse` per file.
  BINARY-ONLY  it touches only database/image blobs. No code is at stake.
  DIFFERS      at least one file is not identical to main. This is NOT a verdict
               that the work is unlanded — main may hold the same change plus
               later edits. Deciding that needs the line-level check, which is
               too expensive to run every session, so it is named as a command
               rather than guessed at.
  UNKNOWN      the stack, the entry, or origin/main could not be read.

`--containment` runs the expensive half on demand: for every added line in the
entry, is that line present in origin/main's copy of the file today. That is a
heuristic and says so — high means landed, low means look, and the identifiers
are printed so a human can grep for them.

UNKNOWN IS NOT A PASS. A repo that could not be read reports UNKNOWN with the
date it was attempted, never silence and never a clean bill.
"""

import subprocess
from datetime import datetime, timezone

# Above this many entries, a human should adjudicate. Two is not a magic
# number: it is "a stash you made ten minutes ago and are about to pop, plus
# one you forgot". Anything more is a stack nobody owns.
CEILING = 2

BINARY_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".png", ".jpg", ".jpeg",
                   ".gif", ".zip", ".pdf", ".tsbuildinfo")

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


def _git(repo, args, timeout=30):
    """Run a git command. Returns (ok, stdout). Never raises."""
    try:
        out = subprocess.run(["git", "-C", repo] + args, capture_output=True,
                             text=True, timeout=timeout)
    except Exception:  # noqa: BLE001 - an unreadable repo is UNKNOWN, not a crash
        return False, ""
    return out.returncode == 0, out.stdout


def _is_binary(path):
    return path.lower().endswith(BINARY_SUFFIXES)


def _entry_files(repo, ref):
    ok, out = _git(repo, ["stash", "show", "--name-only", ref])
    if not ok:
        return None
    return [l for l in out.splitlines() if l.strip()]


def classify(repo, index, base="origin/main"):
    """The CHEAP per-entry verdict. One rev-parse per changed file."""
    ref = f"stash@{{{index}}}"
    files = _entry_files(repo, ref)
    if files is None:
        return UNKNOWN, "could not read the entry", []
    if not files:
        return UNKNOWN, "the entry lists no files", []

    code = [f for f in files if not _is_binary(f)]
    if not code:
        return "BINARY-ONLY", f"{len(files)} binary file(s), no code", files

    differing = []
    for f in code:
        ok_a, a = _git(repo, ["rev-parse", f"{ref}:{f}"])
        ok_b, b = _git(repo, ["rev-parse", f"{base}:{f}"])
        if not ok_a:
            return UNKNOWN, f"could not read {f} out of the entry", files
        if not ok_b:
            differing.append(f)  # absent from main entirely
            continue
        if a.strip() != b.strip():
            differing.append(f)
    if not differing:
        return "LANDED", f"all {len(code)} code file(s) identical to {base}", files
    return "DIFFERS", (f"{len(differing)} of {len(code)} code file(s) differ from "
                       f"{base}"), files


def containment(repo, index, base="origin/main"):
    """The EXPENSIVE per-file check, on demand only.

    For each added line in the entry's own diff, is that line present in
    `base`'s copy of the file today. A heuristic, deliberately: it cannot tell
    a landed change from a coincidence of common lines, and it cannot see a
    change that landed reworded. High means landed, low means a human should
    look, and the caller is shown the file so they can.
    """
    ref = f"stash@{{{index}}}"
    files = _entry_files(repo, ref)
    if files is None:
        return None
    rows = []
    for f in files:
        if _is_binary(f):
            rows.append((f, None, 0, "binary — not comparable"))
            continue
        ok_main, main_blob = _git(repo, ["show", f"{base}:{f}"])
        if not ok_main:
            rows.append((f, None, 0, f"ABSENT from {base} entirely"))
            continue
        ok_d, diff = _git(repo, ["diff", f"{ref}^", ref, "--", f])
        if not ok_d:
            rows.append((f, None, 0, "UNKNOWN — could not read the diff"))
            continue
        main_lines = set(l.strip() for l in main_blob.splitlines())
        total = hit = 0
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            s = line[1:].strip()
            if len(s) < 12:      # skip braces, blank lines, one-word tokens
                continue
            total += 1
            if s in main_lines:
                hit += 1
        if total == 0:
            rows.append((f, None, 0, "no substantive added lines"))
        else:
            rows.append((f, hit * 100 // total, total, ""))
    return rows


def check(repo=".", base="origin/main"):
    """The section verdict. Returns (verdict, why, lines)."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    ok, out = _git(repo, ["stash", "list"])
    if not ok:
        return UNKNOWN, (f"could not read the stash stack in {repo} (checked "
                         f"{stamp}). THIS IS NOT A PASS."), []
    entries = [l for l in out.splitlines() if l.strip()]
    if not entries:
        return PASS, "stash stack empty", []

    base_ok, _ = _git(repo, ["rev-parse", "--verify", base])
    lines = []
    autos = 0
    unknowns = 0
    for i, raw in enumerate(entries):
        subject = raw.split(": ", 1)[1] if ": " in raw else raw
        if "autostash" in raw.lower():
            autos += 1
        ok_age, age = _git(repo, ["log", "-1", "--format=%cr", f"stash@{{{i}}}"])
        age = age.strip() if ok_age and age.strip() else "age UNKNOWN"
        if not base_ok:
            verdict, why = UNKNOWN, f"{base} is not present in this checkout"
            unknowns += 1
        else:
            verdict, why, _files = classify(repo, i, base)
            if verdict == UNKNOWN:
                unknowns += 1
        lines.append(f"stash@{{{i}}}  {verdict:11} {age:>16}  {subject[:70]}")
        lines.append(f"              {why}")

    if unknowns:
        lines.append(f"{unknowns} entr(y/ies) could not be classified — UNKNOWN, not a pass "
                     f"(checked {stamp}).")
    lines.append("containment (line-level, on demand):  "
                 "python3 railway/stash_watch.py --containment N")

    if autos or len(entries) > CEILING or unknowns:
        why = f"{len(entries)} stash entries"
        if autos:
            why += (f", {autos} of them AUTOSTASH — written by `git rebase/pull "
                    f"--autostash`, which CLAUDE.md forbids and config cannot block")
        if unknowns:
            why += f", {unknowns} UNKNOWN"
        return FAIL, why, lines
    return WARN, f"{len(entries)} stash entries on a stack every worktree shares", lines


def _main(argv):
    import sys
    repo = "."
    if "--containment" in argv:
        i = argv.index("--containment")
        try:
            idx = int(argv[i + 1])
        except (IndexError, ValueError):
            print("usage: stash_watch.py --containment N")
            return 1
        rows = containment(repo, idx)
        if rows is None:
            print(f"UNKNOWN — could not read stash@{{{idx}}}. Not a pass.")
            return 3
        print(f"stash@{{{idx}}} — added lines present in origin/main today")
        print("  (a heuristic: high means landed, low means a human should look)")
        for f, pct, total, note in rows:
            if pct is None:
                print(f"    {'—':>5}        {f}   {note}")
            else:
                print(f"    {pct:>4}% of {total:<5} added lines   {f}")
        return 0
    verdict, why, lines = check(repo)
    print(f"STASH STACK: {verdict} — {why}")
    for l in lines:
        print(f"    {l}")
    return 2 if verdict in (FAIL, UNKNOWN) else 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
