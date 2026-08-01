"""A collector's text window must survive the extraction prompt.

Root cause this pins (measured 2026-08-01, SEC Item 2.05 recall investigation):
`sources/edgar.py` builds a 3000-character window centred on the first layoff
keyword, documented as existing "so the relevant passage survives the length
cap". `extractor.extract_layoff_data` then truncated raw_text to 2000, throwing
the last third away before the model ever saw it — and, worse, before
`_count_in_text` ran, so a headcount stated in that third could not pass the
verbatim guard whatever the model returned. The row was then dropped exactly as
if the model had invented a number.

It is invisible from either side. edgar.py looks careful, extractor.py looks
conservative, both are green, and the only symptom is a filing quietly missing
from the data. Measured cost on the gold set: EnerSys 2026-03-25 stated
"approximately 474 employees" 1,756 characters after the Item 2.05 heading —
inside edgar's window, outside the extractor's limit.

sources/gdelt.py builds the same 3000-character window, so this was never
SEC-specific.

The rule: the extraction budget is a CEILING ON COLLECTORS, and every collector
must be at or under it. Raise the extractor first, then the collector.
"""
import re
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]

# Modules that hand `raw_text` to extract_layoff_data and cap it themselves.
# Add a collector here when it starts building its own bounded window.
COLLECTOR_WINDOWS = ("sources/edgar.py", "sources/gdelt.py")

LIMIT_RX = re.compile(r"^RAW_TEXT_LIMIT\s*=\s*(\d+)", re.M)


def _declared_window(rel_path):
    text = (RAILWAY / rel_path).read_text()
    found = LIMIT_RX.search(text)
    assert found, f"{rel_path}: no module-level RAW_TEXT_LIMIT to check"
    return int(found.group(1))


class ExtractionBudgetCoversEveryCollectorWindowTests(unittest.TestCase):

    def test_extractor_reads_at_least_the_largest_collector_window(self):
        import extractor
        for rel_path in COLLECTOR_WINDOWS:
            window = _declared_window(rel_path)
            self.assertGreaterEqual(
                extractor.RAW_TEXT_LIMIT, window,
                f"{rel_path} builds a {window}-char window but "
                f"extract_layoff_data reads only {extractor.RAW_TEXT_LIMIT}. "
                f"The tail is discarded before the model and before the "
                f"verbatim count guard, so a headcount stated there is dropped "
                f"as if it were invented. Raise extractor.RAW_TEXT_LIMIT to at "
                f"least {window}, or shrink the collector's window on purpose.")

    def test_extract_layoff_data_truncates_with_the_named_constant(self):
        # A literal re-introduced at the call site would pass the check above
        # while restoring the bug, because the constant would no longer be the
        # thing doing the truncating.
        source = (RAILWAY / "extractor.py").read_text()
        self.assertIn('raw_text = (raw_entry.get("raw_text") or "")[:RAW_TEXT_LIMIT]',
                      source,
                      "extract_layoff_data must slice raw_text with "
                      "RAW_TEXT_LIMIT, not a pasted number.")

    def test_a_window_sized_entry_reaches_the_prompt_intact(self):
        # End to end on the property that actually matters: text sitting in the
        # last third of a collector window must still be visible to the guards.
        import extractor
        marker = "approximately 474 employees"
        filler = "x" * (extractor.RAW_TEXT_LIMIT - len(marker) - 1)
        raw_text = (filler + " " + marker)[:extractor.RAW_TEXT_LIMIT]
        self.assertIn(marker, raw_text)
        self.assertTrue(
            extractor._count_in_text(474, raw_text),
            "a count in the final characters of the extraction budget must "
            "still satisfy the verbatim guard")


if __name__ == "__main__":
    unittest.main()
