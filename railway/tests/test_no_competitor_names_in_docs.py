"""Competitor names never enter this public repo's docs or reader copy.

The brand is standalone and the repo is public, so a competitor's name or
figure in `docs/`, the README or the plugin's reader copy is a leak the
standing rule forbids (CLAUDE.md, "Competitor data stays private"). On
2026-09-12 a benchmark refresh committed a four-tracker comparison table into
`docs/` and quoted it in the baton file; nothing noticed for two days because
the only banned-word check read a test fixture. This scans the prose.

The banned list is deliberately generic and case-insensitive. It is kept
here, in a test, because a test is the one place a competitor's name may
legitimately appear in this repo.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

SCAN_DIRS = ("docs", "wordpress-plugin")
SCAN_FILES = ("README.md",)
SCAN_EXT = (".md", ".php", ".js", ".html", ".txt", ".json")

BANNED = (
    "layoffs.fyi",
    "trueup",
    "challenger, gray",
    "warntracker",
    "warn act tracker",
    "warnscan",
    "layoffalert",
    "eurolayoffs",
    "intellizence",
)


def _files():
    for name in SCAN_FILES:
        p = os.path.join(REPO, name)
        if os.path.exists(p):
            yield p
    for d in SCAN_DIRS:
        root = os.path.join(REPO, d)
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith(SCAN_EXT):
                    yield os.path.join(dirpath, f)


class NoCompetitorNamesInDocs(unittest.TestCase):
    def test_docs_and_reader_copy_name_no_competitor(self):
        offenders = []
        for path in _files():
            try:
                text = open(path, encoding="utf-8", errors="ignore").read().lower()
            except OSError:
                continue
            for banned in BANNED:
                if banned in text:
                    offenders.append(f"{os.path.relpath(path, REPO)}: {banned}")
        self.assertEqual(offenders, [], "competitor names in public docs or reader copy")

    def test_the_guard_catches_a_planted_name(self):
        # A scan is worthless until it has caught one known instance.
        planted = "we are behind LayoffAlert on 44 states".lower()
        self.assertTrue(any(b in planted for b in BANNED))

    def test_the_scan_reads_something(self):
        # An empty walk would pass vacuously; make sure the dirs exist and are read.
        self.assertGreater(sum(1 for _ in _files()), 50)
