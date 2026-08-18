"""A ROW IS AN ENTRY, AND THE PAGE HAS TO SAY SO WITHOUT BEING ASKED.

WHY THIS TEST EXISTS. Reader-facing copy called a row an "event", the API
field has always been called `entries`, and the docs said both. Three names for
one thing, and the owner, who commissioned the tracker, could not tell from the
page what "43,266 events" was counting. "Announcement" was considered and
rejected: the tiles already distinguish "Verified job cuts" from "Announced job
cuts (planned)", so reusing that word for a row count would collide with the
most-confused pair on the page.

"Entry" is also the more honest word. One real-world layoff can produce several
rows: a WARN notice, a news report, a filing. That is what the dedup and
superset machinery exists to reconcile. "Event" quietly claims we are counting
real-world happenings. "Entry" claims only that we hold a record.

WHAT THIS PINS, AND WHAT IT DELIBERATELY DOES NOT.

1. No reader-facing string calls a row an event. The strings come from
   railway/style_check.py, which is the one place in this repo that knows which
   files hold copy a reader sees and strips comments before reading them. That
   matters here more than anywhere: this codebase writes enormous rationale
   comments in the register of the copy, and several of them quote the
   REPLACED wording verbatim. A checker reading comments would fail on a
   correct fix.

2. The word survives where it names a real-world happening rather than a row,
   and each survivor is named one at a time below. A rule that discovers its
   own exemptions grants itself new ones every time somebody adds a sentence.

3. NOTHING A CONSUMER READS MOVED. The `entries` / `events` JSON keys, the
   query parameters, the `wp_alt_events` table, the `event_id` column and every
   PHP and JS identifier are untouched, and the third test below asserts a
   sample of them is still there. A payload that renamed its own field would
   break a feed somebody may already consume, and the label above a number is
   not the number's name.

4. The definition line RENDERS. It is the part that actually does the work, and
   it is asserted on `innerText` read off the rendered page in real headless
   Chrome, never on the source and never on `textContent`. The at-a-glance
   board is a `<details>` that ships CLOSED: a closed `<details>` still has a
   box and still carries `textContent` for text no reader can read, and
   `innerText` on a non-rendered subtree falls back to `textContent` too, so
   the only honest read is `innerText` off a rendered ancestor. That is why the
   line sits OUTSIDE the disclosure rather than inside it, and the test asserts
   that placement as well as the text.

No Chrome, no measurement: the rendering test SKIPS loudly rather than passing.
Absence of a signal is not a pass (CLAUDE.md).
"""
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import style_check  # noqa: E402
from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
TEMPLATE = PLUGIN / "templates/page-tracker.php"
CSS = PLUGIN / "assets/layoffs.css"

EVENT_RE = re.compile(r"(?i)\bevents?\b")

# Reader-facing copy style_check does not already target. Its list is the copy
# a human reads on a page body; these are the titles, meta descriptions and
# JSON-LD answers a reader meets in a search result, which is the first place
# most of them meet this tracker at all.
EXTRA_TARGETS = [
    ("wordpress-plugin/ai-layoff-tracker/templates/page-widget.php", "widget"),
    ("wordpress-plugin/ai-layoff-tracker/includes/facet-pages.php", "facet"),
    ("wordpress-plugin/ai-layoff-tracker/includes/company-directory.php",
     "company-directory"),
    ("wordpress-plugin/ai-layoff-tracker/ai-layoff-tracker.php", "meta"),
    ("wordpress-plugin/ai-layoff-tracker/templates/partials/"
     "jurisdiction-table.php", "sources"),
    ("wordpress-plugin/ai-layoff-tracker/templates/partials/"
     "global-authorities-table.php", "sources"),
]

# THE WORD SURVIVES ONLY WHERE IT IS SOMEBODY ELSE'S, OR WHERE IT NAMES A
# REAL-WORLD HAPPENING AND NOT A ROW. Three phrases, each with its reason.
ALLOWED = (
    # Eurofound's own name for what the ERM database records. Renaming another
    # organisation's term would misquote the source we credit.
    "restructuring event",
    # What the BLS does NOT publish. The sentence is about real separations in
    # the economy, which are events; we hold no rows for them at all.
    "event-level detail",
    # The category name for the trackers we are compared against. It is their
    # word for their product, used to say which comparison is being made.
    "tech-event tracker",
)

# A sample of the machine-readable names that must NOT have moved. Renaming any
# of these breaks a consumer; the label above them is what changed.
FROZEN_IDENTIFIERS = (
    (PLUGIN / "includes/api.php", "'/event/(?P<id>\\d+)/sources'"),
    (PLUGIN / "includes/api.php", "alt_api_event_sources"),
    (PLUGIN / "includes/company-directory.php", "alt_events_table"),
    (PLUGIN / "includes/company-directory.php", "'ai_events'"),
    (PLUGIN / "includes/facet-pages.php", "'events' => $n"),
    (TEMPLATE, "'entries'"),
    (PLUGIN / "assets/layoffs.js", "'entries'"),
)

# The definition line. `DEF_ID` is how the rendering test finds it; the words
# are asserted so a line that renders an empty box, or a different sentence,
# is not read as a pass.
DEF_ID = "alt-board-def"
DEF_TEXT = ("An entry is one layoff reported by one employer. "
            "Workers counts people.")


#: Memoised because the extraction is a 100-SECOND regex walk over every
#: reader-facing file in the product, and two tests need the same answer.
#: Uncached it was the single most expensive thing in the whole suite: 201.6s
#: of the 869s that killed "Tests" on its 15-minute ceiling on 2026-08-18,
#: spent computing one identical list twice. Nothing writes to these files
#: while the suite runs, so the second walk could only ever agree with the
#: first. The `> 500` floor below still runs on the walk that populates it, so
#: a broken extractor is still caught rather than cached.
_SEGMENTS = None


def reader_segments():
    """Every reader-facing string in this product, with file and line."""
    global _SEGMENTS
    if _SEGMENTS is not None:
        return _SEGMENTS
    root = str(ROOT)
    segs = list(style_check.collect(root))
    for rel, page in EXTRA_TARGETS:
        path = os.path.join(root, rel)
        assert os.path.isfile(path), "reader-copy target is gone: %s" % rel
        segs.extend(style_check.extract_file(path, page, root))
    assert len(segs) > 500, (
        "only %d reader-facing strings were extracted, which means the "
        "extractor stopped working and this test is checking nothing"
        % len(segs))
    _SEGMENTS = segs
    return segs


def is_allowed(text):
    low = text.lower()
    return any(phrase in low for phrase in ALLOWED)


class TheCopyCallsARowAnEntry(unittest.TestCase):

    def test_no_reader_facing_string_calls_a_row_an_event(self):
        offenders = []
        for seg in reader_segments():
            if not EVENT_RE.search(seg.text):
                continue
            if is_allowed(seg.text):
                continue
            offenders.append("%s:%s  %s" % (seg.path, seg.line,
                                            seg.text[:120]))
        self.assertEqual(
            [], offenders,
            "%d reader-facing string(s) still call a row an event. A row is "
            "an entry: that is what the API field has always been called, and "
            "one real-world layoff can produce several rows. Fix the copy, do "
            "not widen ALLOWED:\n  %s"
            % (len(offenders), "\n  ".join(offenders)))

    def test_the_allowlist_still_describes_real_copy(self):
        """An exemption for a sentence nobody ships is an exemption that will
        one day excuse something else."""
        blob = "\n".join(s.text.lower() for s in reader_segments())
        for phrase in ALLOWED:
            self.assertIn(
                phrase, blob,
                "ALLOWED still exempts %r, but no reader-facing string "
                "contains it any more. Delete the exemption rather than "
                "leaving it to catch a future sentence nobody argued for."
                % phrase)


class NothingAConsumerReadsMoved(unittest.TestCase):

    def test_the_machine_readable_names_are_untouched(self):
        missing = []
        for path, needle in FROZEN_IDENTIFIERS:
            if needle not in path.read_text():
                missing.append("%s no longer contains %s"
                               % (path.relative_to(ROOT), needle))
        self.assertEqual(
            [], missing,
            "the copy rename reached a machine-readable name. API fields, "
            "query parameters, table names and identifiers stay put: a "
            "payload that renamed its own field breaks a feed somebody may "
            "already consume.\n  %s" % "\n  ".join(missing))


def template_markup():
    """The whole tracker template with PHP stripped, not a hand-written slice.

    Same approach as test_tap_targets.py: a fixture somebody maintains by hand
    stops describing the page the first time something moves, and then it
    passes forever. It also means the definition line has to be literal HTML in
    the template rather than a string PHP concatenates, which is the placement
    this test wants anyway.
    """
    return re.sub(r"<\?php.*?\?>", "", TEMPLATE.read_text(), flags=re.S)


FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>body{background:#fff;color:#16181d;margin:0;
             font-family:system-ui,sans-serif}</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
<div class="alt-wrap alt-tracker-wrap">
%(markup)s
</div></div></div></main></div>
</body></html>
"""

# innerText off the RENDERED ANCESTOR, never off the node in isolation and
# never textContent. Also reports whether the line is sealed inside a closed
# disclosure, because a definition a reader has to click for is not a
# definition they will meet.
PROBE = r"""
(function () {
  var el = document.getElementById(%s);
  if (!el) return { found: false };
  var host = el.parentElement || document.body;
  var r = el.getBoundingClientRect();
  var cs = getComputedStyle(el);
  return {
    found: true,
    // innerText read from the rendered ancestor, then narrowed to this line.
    hostText: (host.innerText || '').replace(/\s+/g, ' ').trim(),
    text: (el.innerText || '').replace(/\s+/g, ' ').trim(),
    inClosedDetails: !!(el.closest('details') &&
                        !el.closest('details').open),
    w: Math.round(r.width), h: Math.round(r.height),
    display: cs.display, visibility: cs.visibility
  };
})()
""" % json.dumps(DEF_ID)


class TheDefinitionLineRenders(unittest.TestCase):
    """The line a first-time reader meets before the number, in a browser."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the definition line "
                "could not be rendered. This is UNKNOWN, not a pass: run this "
                "where a browser exists.")
        html = FIXTURE % {"plugin": CSS.read_text(),
                          "markup": template_markup()}
        try:
            with Browser(width=375, height=812) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                cls.probe = page.eval_js(PROBE)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("Chrome would not start: %s" % exc)

    def test_the_line_is_in_the_page_at_all(self):
        self.assertTrue(
            self.probe["found"],
            "page-tracker.php renders no #%s. The at-a-glance board is where "
            "the owner hit the confusion, so that is where the definition "
            "goes, and it has to be literal HTML in the template rather than "
            "a string PHP builds, or no fixture can render it." % DEF_ID)

    def test_the_line_is_not_sealed_inside_a_closed_disclosure(self):
        self.assertFalse(
            self.probe["inClosedDetails"],
            "the definition line sits inside a <details> that ships closed. A "
            "closed <details> still has a box and still carries textContent, "
            "so a source check would call this a pass while no reader could "
            "read it. Put the line outside the disclosure.")

    def test_the_line_has_rendered_text_a_reader_can_read(self):
        self.assertNotEqual(
            "", self.probe["text"],
            "#%s renders with EMPTY innerText (%sx%s, display:%s, "
            "visibility:%s). This codebase has shipped three caveats that "
            "computed to display:none or 0x0 and were never read by anyone."
            % (DEF_ID, self.probe["w"], self.probe["h"],
               self.probe["display"], self.probe["visibility"]))
        self.assertGreater(
            self.probe["h"], 0,
            "#%s has rendered text but zero height" % DEF_ID)
        self.assertEqual(
            DEF_TEXT, self.probe["text"],
            "the definition line rendered as %r. It has to say what an entry "
            "is and what the Workers row counts, in that order, because those "
            "are the two rows of the board it sits under."
            % self.probe["text"])

    def test_the_rendered_ancestor_carries_the_line(self):
        """innerText read from the ancestor, per the brief: a subtree that is
        not rendered would fall back to textContent and hide the defect."""
        self.assertIn(
            DEF_TEXT, self.probe["hostText"],
            "the definition line is not in the rendered innerText of its own "
            "parent, which means the parent is not being laid out")

    def test_the_line_uses_no_dashes(self):
        for bad in ("—", "–"):
            self.assertNotIn(
                bad, DEF_TEXT,
                "no em dashes or en dashes in UI copy (CLAUDE.md). "
                "style_check.py needs 12 characters and 3 real words before a "
                "string is eligible, so a short label slips past it.")


if __name__ == "__main__":
    unittest.main()
