"""Every new TECHLOG entry declares the SHAPE of its defect, so recurrence is
counted rather than remembered.

WHY. Two learning layers already work here: a dated regression test per bug
(170 of 213 test files), and CLAUDE.md's 16 "Iron rules learned the hard way",
which generalise past the instance and are loaded into every session. The gap
is between them -- when a new incident arrives, nothing says "this is the fifth
time this shape has happened, and rule 7 was supposed to stop it". A rule that
is too narrow looks exactly like a rule that is working.

WHY A TAG AND NOT A CLASSIFIER. A keyword pass over the prose was tried on
2026-08-28 and matched 150 of 232 entries to one class, because "window" and
"average" appear everywhere. A crude classifier that LOOKS like learning is
worse than none, so the class is declared by whoever writes the entry.

FORWARD ONLY. Entries before CUTOFF are deliberately not back-tagged: tagging
232 historical entries from prose is the same guessing this avoids.
"""
import os
import re
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TECHLOG = os.path.join(REPO, "docs", "TECHLOG.md")
CLASSES_DOC = os.path.join(REPO, "docs", "INCIDENT_CLASSES.md")

# Entries dated on or after this carry a class tag. Everything older is
# grandfathered, on purpose.
#
# 2026-08-29 and not 08-28: six of the eight entries written on 2026-08-28 came
# from OTHER sessions. Their CLASS is readable from the prose, but their GUARD
# is not -- and inventing a test path for someone else's fix is exactly the
# fake precision that made a keyword classifier the wrong answer here. The
# convention applies to entries written after it exists; the two entries
# tagged below are the worked examples.
CUTOFF = date(2026, 8, 29)

_HEAD = re.compile(r"^## (\d{4})-(\d{2})-(\d{2})\b(.*)$", re.M)
_CLASS = re.compile(r"\*\*Class:\*\*\s*([a-z0-9-]+)", re.I)
_GUARD = re.compile(r"\*\*Guard:\*\*\s*(\S.*)$", re.I | re.M)


def vocabulary():
    """The slugs declared in docs/INCIDENT_CLASSES.md's table."""
    with open(CLASSES_DOC, encoding="utf-8") as fh:
        text = fh.read()
    return {m.group(1) for m in re.finditer(r"^\|\s*`([a-z0-9-]+)`\s*\|", text, re.M)}


def entries():
    """(date, heading, body) for every TECHLOG entry, newest first."""
    with open(TECHLOG, encoding="utf-8") as fh:
        text = fh.read()
    marks = list(_HEAD.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        try:
            when = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue
        out.append((when, m.group(4).strip(), text[m.end():end]))
    return out


def tagged_entries():
    return [(d, h, b) for d, h, b in entries() if d >= CUTOFF]


class TheVocabularyIsUsable(unittest.TestCase):
    def test_the_classes_doc_exists_and_declares_slugs(self):
        self.assertTrue(os.path.exists(CLASSES_DOC), "docs/INCIDENT_CLASSES.md is missing")
        self.assertGreaterEqual(len(vocabulary()), 8,
                                "the vocabulary is too small to describe a real defect")

    def test_novel_is_available_so_a_new_shape_is_not_forced_into_a_wrong_slug(self):
        self.assertIn("novel", vocabulary())

    def test_the_cross_cutting_class_is_present(self):
        # 104 of 225 entries described a silent stop; if the vocabulary loses
        # that slug the whole exercise stops describing the main failure mode.
        self.assertIn("silent-stop", vocabulary())


class EveryNewEntryDeclaresItsClass(unittest.TestCase):
    def test_new_entries_carry_a_class_tag(self):
        missing = [f"{d} {h[:60]}" for d, h, b in tagged_entries() if not _CLASS.search(b)]
        self.assertEqual(
            missing, [],
            "TECHLOG entries on or after "
            f"{CUTOFF} must carry `**Class:** <slug>` from docs/INCIDENT_CLASSES.md "
            "so recurrence can be counted. Untagged:\n  " + "\n  ".join(missing))

    def test_every_declared_class_is_in_the_vocabulary(self):
        known = vocabulary()
        bad = []
        for d, h, b in tagged_entries():
            m = _CLASS.search(b)
            if m and m.group(1).lower() not in known:
                bad.append(f"{d} {h[:50]} -> `{m.group(1)}`")
        self.assertEqual(bad, [],
                         "unknown class slug(s); add to docs/INCIDENT_CLASSES.md "
                         "deliberately, or use an existing one:\n  " + "\n  ".join(bad))

    def test_new_entries_name_a_guard_or_say_none_and_why(self):
        # `none` is an honest state. A missing line is not: it is the same
        # "absent read as OK" shape this whole vocabulary is about.
        missing = []
        for d, h, b in tagged_entries():
            m = _GUARD.search(b)
            if not m:
                missing.append(f"{d} {h[:60]}")
            elif m.group(1).strip().lower().startswith("none") and len(m.group(1).strip()) < 12:
                missing.append(f"{d} {h[:60]} (said `none` with no reason)")
        self.assertEqual(missing, [],
                         "each new entry needs `**Guard:** <test path>`, or "
                         "`**Guard:** none - <reason>`:\n  " + "\n  ".join(missing))


class TheGuardCannotGoVacuous(unittest.TestCase):
    """If nothing is ever tagged, the tests above all pass trivially."""

    def test_the_techlog_parses_into_entries(self):
        self.assertGreater(len(entries()), 100,
                           "TECHLOG did not parse; the tag checks would pass vacuously")

    def test_the_format_is_exercised_by_at_least_one_entry(self):
        """The real vacuity risk is that NOTHING is ever tagged.

        Checking "at least one entry is past CUTOFF" would fail on the day the
        convention ships and tempt someone to move CUTOFF backwards to go
        green. Checking that the format is actually USED somewhere holds the
        same property without that pressure.
        """
        known = vocabulary()
        tagged = [
            (d, h) for d, h, b in entries()
            if (m := _CLASS.search(b)) and m.group(1).lower() in known
        ]
        self.assertTrue(
            tagged,
            "no TECHLOG entry anywhere carries a valid `**Class:**` tag, so "
            "every check above passes vacuously. Tag an entry rather than "
            "moving CUTOFF.")

    def test_a_tagged_entry_also_names_its_guard(self):
        """The two halves travel together or the tag is bookkeeping."""
        known = vocabulary()
        for d, h, b in entries():
            m = _CLASS.search(b)
            if m and m.group(1).lower() in known:
                self.assertTrue(
                    _GUARD.search(b),
                    f"{d} {h[:60]} declares a class but names no guard")


if __name__ == "__main__":
    unittest.main()
