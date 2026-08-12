"""NO EM DASH AND NO EN DASH ANYWHERE A READER SEES ONE, INCLUDING THE SHORT
STRINGS THE PROSE CHECKER IS NOT ALLOWED TO SCORE.

THE RULE ALREADY EXISTED AND THE CODE DID NOT AGREE WITH IT. docs/STYLE.md
says it plainly ("No em dashes and no en dashes, anywhere in reader copy") and
railway/style_check.py carries BANNED_CHARS to enforce it. It reported zero
findings while the tracker's date-range button rendered

    Jul 13, 2026 – Aug 11, 2026

and five other display strings did the same thing. That is not a bug in the
scorer. style_check reads PROSE: `looks_like_copy()` requires at least twelve
characters and three real words before a segment is scored, and it is right to,
because everything else it measures (reading grade, sentence length, passive
voice) is meaningless on a fragment. A separator literal is three characters.
It was never eligible to be checked, so the ban never reached the one place the
character actually gets used.

So the ban is checked twice, on purpose, and the two halves do not overlap:

  * style_check.py bans it in reader PROSE, in both products, byte-identical,
    with the reading-grade machinery around it.
  * this file bans it in EVERY reader-facing literal in this repository,
    whatever its length, using style_check's own file list and its own
    comment-stripping so there is still one definition of "which files hold
    copy a reader sees".

COMMENTS ARE NOT COPY, and this file would be actively harmful without that
distinction. Both codebases write long rationale comments in the register of
the page and routinely quote the display string that was REPLACED, dash and
all. A checker that read comments would fail after a correct fix and pass
before one. Stripping is style_check's, not a second implementation.

WHAT IS DELIBERATELY NOT COVERED, stated so the gap is a decision and not an
oversight: `railway/sources/warn_new_states.py` normalises " - " to " – " in
EMPLOYER NAMES. That is stored data, it is part of the dedup hash, and
changing it would need /bulk-purge and a full re-import (CLAUDE.md). It is a
value, not copy, and it is out of scope for a punctuation rule.
"""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import style_check as sc                                    # noqa: E402

BANNED = {"—": "em dash", "–": "en dash"}

# style_check's target list is the files that hold reader PROSE, which is the
# right list for a reading-grade score and one file short for this check.
# includes/api.php holds no prose at all and does hold display LABELS that the
# public REST responses carry: `week_range` was building "Aug 3 – Aug 9" and
# was invisible to every check in the repository because the file it lives in
# has no sentences in it. Added here rather than to style_check's list, which
# is byte-identical with the sibling tracker's and is about prose.
EXTRA_TARGETS = [
    ("wordpress-plugin/ai-layoff-tracker/includes/api.php", "api"),
]


def reader_facing_literals():
    """(file, line, string) for every literal on a reader-facing surface.

    Same target list and same comment stripping as style_check.py. The one
    difference is that nothing is filtered out for being too short to score,
    which is the entire point.
    """
    _, targets = sc.detect_product(str(ROOT))
    for rel, page in list(targets) + EXTRA_TARGETS:
        path = ROOT / rel
        if not path.is_file():
            continue
        with io.open(str(path), encoding="utf-8") as fh:
            raw = fh.read()
        ext = path.suffix.lower()
        if ext == ".php":
            src = sc.strip_comments(raw, "php")
            html = sc._blank_php_blocks(src)
            segs = [(t, o) for t, o in sc._html_text_segments(html, rel, page)]
            segs += sc._literal_segments_in_spans(src, sc._php_code_spans(src))
        elif ext == ".js":
            segs = sc._literal_segments(sc.strip_comments(raw, "js"), rel, page)
        elif ext == ".py":
            # style_check drops Python docstrings before it reads literals,
            # and so must this: a module docstring is documentation, and this
            # file's own docstring quotes the character it bans.
            segs = sc._literal_segments(
                sc.strip_py_docstrings(sc.strip_comments(raw, "py")), rel, page)
        else:
            continue
        for text, off in segs:
            yield rel, sc._line_of(raw, off), text


class TheBanReachesShortDisplayStrings(unittest.TestCase):

    def test_no_reader_facing_literal_carries_an_em_or_en_dash(self):
        bad = []
        for rel, line, text in reader_facing_literals():
            for ch, name in BANNED.items():
                if ch in text:
                    bad.append("%s:%d  %s in %r" % (rel, line, name, text[:70]))
        self.assertFalse(
            bad,
            "%d reader-facing string(s) carry a banned dash. docs/STYLE.md: "
            "use a comma, a full stop, a colon, or the word \"to\" in a "
            "range.\n  %s" % (len(bad), "\n  ".join(sorted(set(bad))[:30])))

    def test_the_checker_can_see_a_short_separator(self):
        """The half that makes the half above evidence.

        The defect was not that a dash existed, it was that a three-character
        separator was too short for the prose scorer to be given. So this
        proves the scan reaches one, using the exact string the date-range
        button used to build.
        """
        sample = "var a = 'Jan 1' + ' – Dec 31, ' + b;"
        segs = sc._literal_segments(sc.strip_comments(sample, "js"), "x.js", "p")
        joined = "".join(t for t, _ in segs)
        self.assertIn(
            "–", joined,
            "the literal scan cannot see a separator string, so the assertion "
            "above proves nothing")
        self.assertFalse(
            sc.looks_like_copy(" – Dec 31, "),
            "style_check's prose filter now accepts a fragment this short, "
            "which means the gap this file exists to cover may have moved")

    def test_a_dash_inside_a_comment_is_not_a_finding(self):
        """A comment that quotes the replaced string must not fail the fix."""
        sample = ("// the label used to read 'Jul 13 – Aug 11'\n"
                  "var label = 'Jul 13 to Aug 11';\n")
        segs = sc._literal_segments(sc.strip_comments(sample, "js"), "x.js", "p")
        joined = "".join(t for t, _ in segs)
        self.assertNotIn(
            "–", joined,
            "comments are being read as copy, so this check grades the "
            "commentary instead of the page")


class TheStandardItselfStillSaysSo(unittest.TestCase):
    """If somebody relaxes the written rule, this file should stop claiming
    to enforce it rather than enforce something nobody agreed to."""

    def test_style_md_still_bans_both_characters(self):
        with io.open(str(ROOT / "docs" / "STYLE.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(
            "No em dashes and no en dashes", text,
            "docs/STYLE.md no longer carries the standing ban, so this test "
            "is enforcing a rule the standard does not state")

    def test_style_check_still_carries_both_characters(self):
        self.assertEqual(
            set(sc.BANNED_CHARS), set(BANNED),
            "style_check.BANNED_CHARS and this file disagree about which "
            "characters are banned, which is exactly the drift the two-layer "
            "design is meant to make visible")


if __name__ == "__main__":
    unittest.main()
