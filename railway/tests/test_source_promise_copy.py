"""READER-FACING COPY MAY NOT PROMISE A PRIMARY SOURCE FOR EVERY FIGURE.

The tracker already classifies its own links honestly. `alt_source_link_label`
(includes/api.php) returns "View official filing" for a filing, "View employer
statement" for a press release, "View source report" for a news article and
"View Google News index record" for a Google News redirect, and
test_source_link_label.py pins that a redirect is NEVER called a primary source.

Meanwhile eight pieces of copy told the reader the opposite, in the blanket
form, across five files:

    page-tracker.php:1046   "Every figure links to a primary source"
    page-tracker.php:1578   "Every entry links to its primary source"
    page-tracker.php:1668   "Every figure links to a primary source."
    page-methodology.php:16 "Every published number traces back to a primary source."
    report-seo.php:191      "with a primary source behind every number."
    ai-layoff-tracker.php   x3 (schema.org description, meta description, FAQ)

Roughly half the corpus is news, and a news report is not a primary source. On
2026-08-29 the largest 2026 row on the public leaders list was cited to a
Google News INDEX record — the one thing the label function refuses by name to
call primary — under a page promising a primary source for every figure.

This test fails on the BLANKET promise only. Saying that a WARN notice or an
8-K IS a primary source is true and stays allowed; what is banned is the
universal quantifier attached to it, because that is the half that is false.

Guard for docs/TECHLOG.md 2026-08-29.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"

# Reader-facing surfaces. Anything a human reads on the site or in a search
# result: templates, the plugin bootstrap (schema.org + meta + FAQ) and the
# report SEO block.
SURFACES = sorted(
    [p for p in (PLUGIN / "templates").glob("*.php")]
    + [PLUGIN / "ai-layoff-tracker.php",
       PLUGIN / "includes" / "report-seo.php",
       PLUGIN / "includes" / "subscribe.php"]
)

# "every|each|all ... primary source" within one clause, in either order.
BLANKET = re.compile(
    r"(?:\bevery\b|\beach\b|\ball\b)[^.<>]{0,80}?primary[\s-]+source"
    r"|primary[\s-]+source[^.<>]{0,80}?\b(?:every|each|all)\b",
    re.I,
)

# GDELT does not watch every country. It issues a rotating, capped set of
# queries against a reviewed outlet allowlist; a country with no allowlisted
# outlet is invisible to it. page-sources.php and api.php already say so.
OVERREACH = re.compile(
    r"searches every country|every country on earth|all countries on earth"
    r"|scans? every country",
    re.I,
)


def _offences(pattern):
    out = []
    for path in SURFACES:
        if not path.exists():
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            m = pattern.search(line)
            if m:
                out.append("%s:%d: %s" % (path.relative_to(ROOT), n, m.group(0).strip()))
    return out


class TheCopyDoesNotOverPromise(unittest.TestCase):

    def test_no_blanket_primary_source_promise(self):
        bad = _offences(BLANKET)
        self.assertEqual(bad, [], (
            "reader-facing copy promises a primary source for every figure, but "
            "about half the corpus is news and alt_source_link_label() refuses "
            "to call a news report — or a Google News redirect — a primary "
            "source. Say what the dataset actually holds: 'a filing, an "
            "employer statement, or a named source report'.\n  "
            + "\n  ".join(bad)))

    def test_no_claim_that_gdelt_watches_every_country(self):
        bad = _offences(OVERREACH)
        self.assertEqual(bad, [], (
            "copy claims GDELT searches every country. Discovery is a rotating, "
            "capped set of queries against a reviewed outlet allowlist; a "
            "country with no allowlisted outlet never appears no matter what "
            "happens there.\n  " + "\n  ".join(bad)))


class TheHonestVocabularyIsActuallyUsed(unittest.TestCase):
    """The replacement wording has to be present, or this test passes on a
    page that simply deleted the sentence and told the reader nothing."""

    def test_the_tracker_page_states_what_a_source_is(self):
        text = (PLUGIN / "templates/page-tracker.php").read_text()
        self.assertIn("named source report", text)
        self.assertIn("employer statement", text)


if __name__ == "__main__":
    unittest.main()
