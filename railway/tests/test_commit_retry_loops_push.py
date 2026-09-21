"""A retry loop that REPLAYS its commit must never re-ask "is anything staged?".

`backup-export.yml` committed its baseline inside a three-lap loop whose first
statement was `git diff --staged --quiet && exit 0`. A rejected push was
rebased, the next lap found nothing staged (the commit already existed), printed
"Baseline unchanged." and exited 0 with the commit never pushed. Two weekly
runs, 2026-09-13 and 2026-09-20, were green, published their export, and
recorded nothing; `state_liveness` read the file STALE at 15 days.

Loops that RE-DERIVE (`git reset --hard origin/main`, run the writer again) may
ask the question every lap, because the reset discards the commit and the
answer is about fresh work. Loops that REBASE keep the commit, so inside them
the question is always answered "nothing", whatever happened.

Offline: reads the checkout only.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_LOOP = re.compile(r"^(?P<ind>[ \t]*)for attempt in[^\n]*\n(?P<body>.*?)^(?P=ind)done\b",
                   re.S | re.M)
_STAGED = re.compile(r"git diff --(?:staged|cached) --quiet")


def _files():
    yield from sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    yield from sorted((ROOT / ".github" / "actions").glob("*/action.yml"))


def offenders(text: str) -> list[str]:
    out = []
    for m in _LOOP.finditer(text):
        body = m.group("body")
        if "git rebase" in body and "reset --hard" not in body and _STAGED.search(body):
            out.append(body.strip().splitlines()[0].strip())
    return out


class CommitRetryLoopsPushTests(unittest.TestCase):
    def test_no_rebasing_loop_tests_the_index_inside_the_loop(self):
        bad = {str(f.relative_to(ROOT)): o for f in _files()
               if (o := offenders(f.read_text(encoding="utf-8")))}
        self.assertEqual(bad, {}, "a rebase keeps the commit, so 'nothing staged' on "
                                  "the next lap exits 0 without pushing it")

    def test_the_guard_catches_the_shape_that_shipped(self):
        shipped = (
            "          for attempt in 1 2 3; do\n"
            "            git add x.json\n"
            "            if git diff --staged --quiet; then exit 0; fi\n"
            "            git commit -q -m x\n"
            "            if git push origin HEAD:main; then exit 0; fi\n"
            "            git fetch origin main\n"
            "            git rebase origin/main || { git rebase --abort; exit 0; }\n"
            "          done\n")
        self.assertEqual(len(offenders(shipped)), 1)
        rederiving = shipped.replace(
            "git rebase origin/main || { git rebase --abort; exit 0; }",
            "git reset --hard origin/main")
        self.assertEqual(offenders(rederiving), [])

    def test_the_backup_baseline_is_committed_before_its_push_loop(self):
        text = (ROOT / ".github/workflows/backup-export.yml").read_text(encoding="utf-8")
        step = text[text.index("- name: Commit the drift baseline"):]
        self.assertLess(step.index("git commit -q"), step.index("for attempt in"))
        loops = list(_LOOP.finditer(step))
        self.assertTrue(loops, "the push is still retried")
        self.assertIn("git push origin HEAD:main", loops[0].group("body"))


if __name__ == "__main__":
    unittest.main()
