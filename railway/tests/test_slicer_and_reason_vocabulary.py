"""Two hand-typed copies of a vocabulary, both inside /aggregate, both stale.

Found 2026-09-06 by an offline read of includes/db.php against the UI.

1. A SLICER THAT RENDERS ITS OWN DIMENSION. alt_api_aggregate_compute() builds
   every bar list through $topN($col, $except), and $except is the dimension the
   chart draws, dropped from the WHERE so a reader can always see what to pivot
   to. alt_db_where() honours that for date, industry, country,
   employer_country, state, reasons, roles and company_key. It never honoured it
   for `sources`: the block that reads that param carries no $except test at
   all, so $topN('source_type', 'sources') was handed a WHERE that still had the
   source filter in it. With sources=warn selected, the "By data source" card
   showed exactly one bar, warn, at 100%, and there was no way back to the other
   sources from the chart. Nothing errored, because a filter that is applied
   twice is still a valid query.

2. THE REASON VOCABULARY, TYPED A SECOND TIME AND SIX MONTHS BEHIND. The
   canonical list is alt_allowed_reason_tags() in includes/cpt.php (12 tags).
   The reasons breakdown in db.php kept its own literal array of 10, missing
   `bankruptcy` and `federal_workforce` — both real, both emitted by
   railway/extractor.py, both offered in the tracker page's Reasons dropdown and
   both labelled in assets/layoffs.js. The consequences were on-page and silent:
   the reasons doughnut could never draw those two slices, so its slices did not
   sum to the population they were drawn from, and selecting "Bankruptcy /
   insolvency" filtered the table correctly while the chart beside it kept
   insisting no such reason existed. Measured live 2026-09-06: reasons=bankruptcy
   returns 27 entries, and the /aggregate reasons block named ten tags, none of
   them bankruptcy.

Both are the same defect twice: a list that has ONE definition somewhere else,
retyped where it is used. This file pins each to its definition, and the first
check is the general one — it fails for ANY dimension a slicer excepts and
alt_db_where does not honour, not only for `sources`. Offline and static: reads
the PHP as text, executes nothing.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = PLUGIN / "includes/db.php"
CPT_PHP = PLUGIN / "includes/cpt.php"
TRACKER_TPL = PLUGIN / "templates/page-tracker.php"


def _function_source(text, name):
    start = text.index("function %s(" % name)
    end = text.index("\nfunction ", start + 1)
    return text[start:end]


class SlicerExceptIsHonoured(unittest.TestCase):
    """Every dimension a caller excepts must be a dimension alt_db_where drops."""

    def test_every_excepted_dimension_is_read_by_the_query_builder(self):
        text = DB_PHP.read_text()
        where_src = _function_source(text, "alt_db_where")

        # What callers ask to be dropped: alt_db_where($r, 'x') anywhere in the
        # plugin, plus the $topN(col, 'x') slicer form that wraps it.
        asked = set(re.findall(r"alt_db_where\(\s*\$r\s*,\s*'([a-z_]+)'", text))
        asked |= set(re.findall(r"\$topN\(\s*'[a-z_]+'\s*,\s*'([a-z_]+)'", text))
        self.assertIn("sources", asked, "the source-type slicer stopped excepting its own dimension")
        self.assertGreaterEqual(len(asked), 5, "found suspiciously few except keys; the regex has rotted")

        # What alt_db_where actually honours: an explicit $except test, or the
        # third argument of the $str_in helper.
        honoured = set(re.findall(r"\$except\s*[!=]==\s*'([a-z_]+)'", where_src))
        honoured |= set(re.findall(r"\$str_in\(\s*'[a-z_]+'\s*,\s*'[a-z_]+'\s*,\s*'([a-z_]+)'", where_src))

        missing = sorted(asked - honoured)
        self.assertEqual(
            [], missing,
            "alt_db_where ignores except=%r, so the chart that excepts it "
            "renders its own dimension and cannot be pivoted away from" % (missing,))


class ReasonVocabularyHasOneDefinition(unittest.TestCase):
    """cpt.php owns the reason tags; nothing else may keep a private copy."""

    @staticmethod
    def _canonical():
        src = _function_source(CPT_PHP.read_text(), "alt_allowed_reason_tags")
        return set(re.findall(r"'([a-z_]+)'", src))

    def test_canonical_list_is_the_one_we_think_it_is(self):
        canon = self._canonical()
        self.assertIn("bankruptcy", canon)
        self.assertIn("federal_workforce", canon)
        self.assertIn("ai_automation", canon)
        self.assertGreaterEqual(len(canon), 12)

    def test_aggregate_breakdown_covers_every_canonical_tag(self):
        agg = _function_source(DB_PHP.read_text(), "alt_api_aggregate_compute")
        m = re.search(r"\$reason_tags\s*=\s*(.*?);", agg, re.S)
        self.assertIsNotNone(m, "the reasons breakdown no longer builds a $reason_tags list")
        block = m.group(1)
        if "alt_allowed_reason_tags" in block:
            return  # derived from the one definition: nothing left to drift
        typed = set(re.findall(r"'([a-z_]+)'", block))
        missing = sorted(self._canonical() - typed)
        self.assertEqual(
            [], missing,
            "the /aggregate reasons breakdown cannot draw %r, so its slices do "
            "not sum to the rows they are drawn from; read alt_allowed_reason_tags() "
            "instead of retyping the list" % (missing,))

    def test_tracker_dropdown_offers_only_canonical_tags(self):
        """A reason the page offers but the vocabulary does not know filters to nothing."""
        tpl = TRACKER_TPL.read_text()
        sel = re.search(r'<select id="alt-f-reasons".*?</select>', tpl, re.S)
        self.assertIsNotNone(sel, "the Reasons dropdown moved; this guard is now blind")
        offered = set(re.findall(r'<option value="([a-z_]+)"', sel.group(0)))
        self.assertTrue(offered, "the Reasons dropdown lists no options")
        self.assertEqual(
            [], sorted(offered - self._canonical()),
            "the Reasons dropdown offers a tag alt_allowed_reason_tags() does not accept")


if __name__ == "__main__":
    unittest.main()
