"""A WARN notice and its refiled revision must share ONE dedup key.

THE DEFECT, ON A PUBLIC PAGE FROM 2026-07-24 UNTIL 2026-08-18.

`alt_reconcile_supersets` pass (3) — "within-WARN revision" — is documented as
the rule that collapses a state WARN notice and the amended copy the state
later republishes:

    (3) within-WARN duplicate: same company + same STATE + EXACT same count
        (>=100) within ~90 days is a notice + its refiled revision, not two
        real events (Tyson: 1,761 Amarillo TX on both Jan 20 and Feb 24).

It never once did that for the pair named in its own comment. The pass ran
INSIDE `foreach ($by as $grp)`, and `$by` is grouped on `company_key`. Texas
republishes a revised notice with the word appended to the employer cell, so
the two rows never met:

    Tyson Foods, Inc. (Amarillo B-Shift Operations
        -> tyson foods amarillo b shift operations
    Tyson Foods, Inc (Amarillo B-Shift Operations) Updated
        -> tyson foods amarillo b shift operations updated

Two keys, two groups, one pass that only ever compares within a group. 1,761
jobs counted twice, every day, on the headline.

WHY THE LIVE GUARD SLEPT THROUGH IT. `data_integrity.tyson_warn_revision` was
written the same afternoon as the pass and bounded the live Tyson US-2026 sum
at 8,945. The DOUBLE-COUNTED total that day was 7,184, so the guard passed
while asserting a thing that was false — it had headroom, not agreement. It
only reddened on 2026-08-18, when three legitimate new Tyson WARN rows (IL 103,
IL 2,495, UT 723) pushed the doubled sum to 10,505 and finally crossed the
bound. The bound was never the finding; the second row was.

WHY THE KEY IS FIXED HERE AND NOT IN alt_company_key(). Adding these words to
that function's stopword list changes fuzzy dedup, the company directory and
superset passes (1) and (2) for every source, and it over-strips: "Revision
Optics, Inc." would key as `optics`. The revision key is therefore a SEPARATE
key used by pass (3) and nowhere else, and a LEADING marker is only stripped
when a multi-token employer survives — so "Revision Optics" keeps its name and
"UPDATE First Brands Group Seneca" loses its decoration.

WHAT MUST NOT COLLAPSE. Companies legally file several WARN notices close
together and WARN is deliberately exempt from fuzzy cross-outlet dedup. Two
DIFFERENT First Brands sites in Ohio filed the identical 302 within 90 days;
the site name is part of the employer cell, so they keep distinct keys and stay
two rows. That case is pinned below.

The functions touch no WordPress API, so they are extracted and evaluated
rather than the plugin being booted. Without php on PATH these SKIP, which is
not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
INC = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes")
API = os.path.join(INC, "api.php")
DB = os.path.join(INC, "db.php")
PHP = shutil.which("php")

# The two Amarillo rows exactly as the Texas WARN table published them and as
# they are stored live (ids 136371 and 136079, TX, 1,761 each, 2026-01-20 and
# 2026-02-24 — 35 days apart, inside the pass's 90-day window).
TYSON_ORIGINAL = "Tyson Foods, Inc. (Amarillo B-Shift Operations"
TYSON_REVISION = "Tyson Foods, Inc (Amarillo B-Shift Operations) Updated"
# The same defect, second instance (ids 142097 and 141305, TX, 109 each,
# 2024-05-16 and 2024-08-02 — 78 days apart).
SIGNIFY_ORIGINAL = "Signify North America Corporation - Genlyte Thomas LLC"
SIGNIFY_REVISION = "Signify North America Corporation-Genlyte Thomas LLC (Updated)"
# Two DIFFERENT Ohio sites that coincidentally filed 302 each within 90 days
# (ids 135331 and 135004). These are two real notices and must stay two rows.
FIRST_BRANDS_DARKE = "First Brands Group Darke"
FIRST_BRANDS_WOOD = "UPDATE First Brands Group Wood"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract(path, name):
    m = re.search(r"\nfunction %s\s*\(.*?\n\}" % re.escape(name), _read(path),
                  re.S)
    if not m:
        raise AssertionError("could not extract %s from %s" % (name, path))
    return m.group(0)


def _block(src, opener):
    """The braced block that `opener` introduces, by brace matching."""
    start = src.index(opener)
    i = src.index("{", start)
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
    raise AssertionError("unbalanced braces after " + opener)


def _keys(names):
    """Return [(company_key, warn_revision_key), ...] from the real PHP."""
    parts = [
        _extract(API, "alt_canonical_company"),
        _extract(API, "alt_company_key"),
        _extract(DB, "alt_strip_revision_marker"),
        _extract(DB, "alt_warn_revision_key"),
    ]
    # The stripper reads a define() from db.php; carry it over verbatim.
    define = re.search(r"^if \(!defined\('ALT_REVISION_MARKER_WORDS'\)\).*$",
                       _read(DB), re.M)
    if not define:
        raise AssertionError("ALT_REVISION_MARKER_WORDS is not defined in db.php")
    runner = (
        "<?php\n" + define.group(0) + "\n" + "\n".join(parts) + "\n"
        "$out = array();\n"
        "foreach (json_decode($argv[1], true) as $n) {\n"
        "    $out[] = array(alt_company_key($n), alt_warn_revision_key($n));\n"
        "}\n"
        "echo json_encode($out);\n"
    )
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write(runner)
        handle.close()
        res = subprocess.run([PHP, handle.name, json.dumps(list(names))],
                             capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise AssertionError("php failed: " + (res.stderr or "")[:2000])
        return [tuple(p) for p in json.loads(res.stdout)]
    finally:
        os.unlink(handle.name)


@unittest.skipUnless(PHP, "php not on PATH — UNKNOWN, not a pass")
class WarnRevisionKeyTest(unittest.TestCase):

    def test_the_defect_itself_is_pinned(self):
        # The plain company_key really does split the pair. If this ever stops
        # being true the revision key is no longer load-bearing and the reason
        # for all of the above has changed — read it before deleting it.
        (orig, _), (rev, _) = _keys([TYSON_ORIGINAL, TYSON_REVISION])
        self.assertNotEqual(
            orig, rev,
            "alt_company_key no longer splits the Tyson Amarillo pair; the "
            "revision key exists because it did")

    def test_tyson_amarillo_shares_one_revision_key(self):
        # 1,761 jobs, TX, 35 days apart: one notice, republished.
        (_, orig), (_, rev) = _keys([TYSON_ORIGINAL, TYSON_REVISION])
        self.assertEqual(
            orig, rev,
            "the 1,761 Amarillo notice and its revision must share ONE key; "
            "they do not, so 1,761 jobs count twice on the live headline")
        self.assertEqual(orig, "tyson foods amarillo b shift operations")

    def test_signify_genlyte_shares_one_revision_key(self):
        # 109 jobs, TX, 78 days apart: the same defect, a second time.
        (_, orig), (_, rev) = _keys([SIGNIFY_ORIGINAL, SIGNIFY_REVISION])
        self.assertEqual(orig, rev)

    def test_two_real_sites_with_the_same_count_stay_apart(self):
        # 302 jobs each, OH, within 90 days — but Darke and Wood are two
        # counties and two notices. Collapsing these would be the opposite
        # error, and WARN's exemption from cross-outlet dedup exists for it.
        (_, darke), (_, wood) = _keys([FIRST_BRANDS_DARKE, FIRST_BRANDS_WOOD])
        self.assertNotEqual(
            darke, wood,
            "two different First Brands sites must not merge on an equal count")

    def test_a_leading_marker_that_is_the_name_is_kept(self):
        # "Revision Optics" is a company, not a revision of "Optics". A leading
        # marker is only stripped when a multi-token employer survives.
        (plain, rev), = _keys(["Revision Optics, Inc."])
        self.assertEqual(rev, plain)
        self.assertEqual(rev, "revision optics")

    def test_leading_and_repeated_markers_are_stripped(self):
        for name, want in (
            ("UPDATE First Brands Group Seneca", "first brands seneca"),
            ("UPDATED Eagle Machining - First Brands Group, LLC",
             "eagle machining first brands"),
            ("*UPDATED*  Schneider Electric 6th Notice",
             "schneider electric 6th notice"),
            ("Prime Time Inc. (Head Start) Multiple Locations in Ouachita "
             "Parish UPDATE: UPDATE:",
             "prime time head start multiple locations in ouachita parish"),
            ("TIAA - Update", "tiaa"),
            ("Hostess Brands-Revised", "hostess brands"),
            ("American Express (Amended)", "american express"),
        ):
            with self.subTest(name=name):
                (_, rev), = _keys([name])
                self.assertEqual(rev, want)

    def test_an_ordinary_name_is_untouched(self):
        for name in ("21st Amendment Brewery Cafe", "Tyson Fresh Meats",
                     "First Brands Group Darke", "Sherwin-Williams"):
            with self.subTest(name=name):
                (plain, rev), = _keys([name])
                self.assertEqual(rev, plain)


@unittest.skipUnless(PHP, "php not on PATH — UNKNOWN, not a pass")
class ReconcilePassWiringTest(unittest.TestCase):
    """The key is only half of it: pass (3) has to be able to USE it.

    The pass sat inside `foreach ($by as $grp)`, so no key it computed could
    have reached across two company_key groups — which is the only place the
    duplicate ever was. Pin that it runs over the whole WARN set instead.
    """

    def test_pass_three_is_not_nested_in_the_company_key_loop(self):
        body = _block(_read(DB), "function alt_reconcile_supersets(")
        self.assertIn("alt_warn_revision_key(", body,
                      "pass (3) must group on the revision key")
        self.assertIn("foreach ($warn_all as $w)", body,
                      "pass (3) must iterate every WARN row, not one "
                      "company_key group — the grouping WAS the defect")
        # The load-bearing claim: the revision pass is OUTSIDE the per-company
        # loop. Inside it, no key it computes can reach the other group, which
        # is the only place a refiled revision ever sits.
        per_company = _block(body, "foreach ($by as $grp)")
        self.assertNotIn(
            "alt_warn_revision_key(", per_company,
            "the revision pass is nested in the company_key loop again — that "
            "is the 2026-07-24 defect, and it makes the pass a no-op")


if __name__ == "__main__":
    unittest.main()
