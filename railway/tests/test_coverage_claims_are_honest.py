"""WORLDWIDE DISCOVERY IS NOT WORLDWIDE COVERAGE, AND THE COPY MAY NOT IMPLY IT.

The sources page told a reader we cover "every country": the GDELT reach cell
read "Worldwide, every country" and the news section was headed "every country
& outlet we scan", over a paragraph that said we watch outlets "in every
country". We run worldwide DISCOVERY, but measured coverage varies by country
and is disclosed per country in the table directly below that copy. Claiming
uniform coverage is the overstatement the external review flagged
(docs/EXTERNAL_REVIEW_2026-08-20.md, finding 8).

These are copy assertions, scoped to the SPECIFIC overstatements this change
removed. "Almost every country requires employers to notify a labour
authority" is a true sentence elsewhere on the same page and must stay, so this
file never bans the bare words "every country" - it bans the three claims that
implied uniform coverage, and requires the honest qualifier in their place.

The country count stays DERIVED from the collector's own configuration
($alt_scan_countries), never a typed literal, so it cannot go stale.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (ROOT / "wordpress-plugin/ai-layoff-tracker/templates/page-sources.php").read_text()


def visible_copy(text):
    text = re.sub(r"<\?php.*?\?>", " ", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


VIS = visible_copy(SOURCES)


class TheSourcesCopyDoesNotClaimUniformCoverage(unittest.TestCase):

    REMOVED = (
        "Worldwide, every country",             # the GDELT reach cell
        "every country &amp; outlet we scan",   # the news-section heading
        "news outlets in every country",        # the section's lead paragraph
    )

    def test_the_uniform_coverage_claims_are_gone(self):
        for phrase in self.REMOVED:
            self.assertNotIn(
                phrase, SOURCES,
                "page-sources.php still claims uniform coverage: %r" % phrase)

    def test_the_honest_qualifier_is_present(self):
        self.assertIn(
            "coverage varies by country", VIS.lower(),
            "the sources copy no longer discloses that coverage varies by country")
        self.assertIn(
            "worldwide discovery", VIS.lower(),
            "the sources copy no longer frames the news path as discovery")

    def test_the_true_notify_sentence_was_not_collateral_damage(self):
        """A guard on the guard: the legitimate 'Almost every country requires
        employers to notify' sentence is not what this change was about."""
        self.assertIn("Almost every country requires employers to notify", VIS)

    def test_the_country_count_is_derived_not_typed(self):
        """The heading's figure comes from $alt_scan_countries (generated from
        the collector's allowlist), never a literal that can go stale."""
        heading = re.search(r'id="alt-src-news".*?</h2>', SOURCES, re.S)
        self.assertIsNotNone(heading, "the news-section heading is gone")
        self.assertIn("$alt_scan_countries", heading.group(0),
                      "the heading hard-codes a country count instead of deriving it")
        self.assertNotRegex(
            heading.group(0), r"\b\d{2,3}\s+configured country markets\b",
            "a literal country count was typed into the heading")

    def test_no_em_or_en_dashes_in_the_changed_copy(self):
        for line in (
            '<b>GDELT news index</b>',
            'id="alt-src-news"',
            "we run worldwide discovery",
        ):
            i = SOURCES.find(line)
            self.assertNotEqual(i, -1, "changed copy moved: %r" % line)
            block = SOURCES[i:i + 400]
            for dash in ("—", "–"):
                self.assertNotIn(dash, block, "em or en dash in UI copy near %r" % line)


if __name__ == "__main__":
    unittest.main()
