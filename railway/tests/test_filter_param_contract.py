"""One canonical list of filter params, pinned to the code that reads them.

Two problems in one family, both found 2026-07-30.

1. The public routes register no `args` schema, so WordPress accepts an unknown
   query param without complaint and the filter is silently dropped:
   `/query?states=NV` returns all 63,671 rows rather than Nevada's 15, and reads
   as a valid answer. The plural gets guessed because the naming is not
   internally consistent (`years/quarters/months/sources/reasons/roles` plural,
   `industry/country/state/employer_country` singular) even though all of them
   take comma-joined lists. The decision was to document the contract rather
   than accept plural aliases — see docs/ARCHITECTURE.md "Filter model" — and
   documentation nothing checks is documentation that rots.

2. `alt_export_is_filtered()` kept its OWN copy of the filter-name list and had
   fallen six params behind `alt_db_where()` (ai_primary, employer_country,
   review_status, context_missing, industry_missing, roles_missing). An export
   narrowed by any of them downloaded as `ai-layoff-tracker-<date>.csv`, the
   filename that means "the whole dataset". Both now read
   `alt_filter_param_names()`.

This file is what makes a new filter impossible to add to alt_db_where without
also listing it, which is the only reason the drift stays fixed. Offline and
static: reads the PHP and the Markdown as text, executes nothing.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB_PHP = PLUGIN / "includes/db.php"
EXPORT_PHP = PLUGIN / "includes/export.php"
ARCH = ROOT / "docs/ARCHITECTURE.md"

# Read by alt_db_where but NOT narrowing on their own: they reinterpret the other
# filters. `except` is internal slicer plumbing, never a caller-facing filter.
NON_NARROWING = {"date_basis", "country_basis", "except"}

# Natural guesses that are deliberately NOT accepted as aliases.
REJECTED_PLURALS = ("states", "countries", "industries", "employer_countries")


def _alt_db_where_source():
    """The body of alt_db_where(), which is where filters are actually read."""
    text = DB_PHP.read_text()
    start = text.index("function alt_db_where(")
    # The next top-level function definition ends it.
    end = text.index("\nfunction ", start + 1)
    return text[start:end]


def _params_read_by_query_builder():
    """Param names alt_db_where reads, via all three shapes it uses.

    Missing a shape gives a false negative, which is how an earlier draft of this
    test concluded `years` was unread — it goes through $int_in, not get_param.
    """
    src = _alt_db_where_source()
    names = set()
    for pattern in (r"get_param\('([a-z_]+)'\)",
                    r"\$str_in\('([a-z_]+)'",
                    r"\$int_in\('([a-z_]+)'"):
        names.update(re.findall(pattern, src))
    return names - NON_NARROWING


def _declared_filter_names():
    """The names inside alt_filter_param_names()'s returned array."""
    text = DB_PHP.read_text()
    start = text.index("function alt_filter_param_names(")
    body = text[start:text.index("\n}", start)]
    return set(re.findall(r"'([a-z_]+)'", body))


class CanonicalListMatchesTheQueryBuilderTests(unittest.TestCase):

    def test_every_narrowing_param_is_declared(self):
        missing = _params_read_by_query_builder() - _declared_filter_names()
        self.assertEqual(
            missing, set(),
            f"alt_db_where() narrows on {sorted(missing)} but "
            f"alt_filter_param_names() does not list them. An export narrowed "
            f"by an unlisted param downloads under the full-dataset filename, "
            f"labelling a partial extract complete. Add them, or add them to "
            f"NON_NARROWING here if they only reinterpret other filters.")

    def test_no_declared_param_is_a_phantom(self):
        extra = _declared_filter_names() - _params_read_by_query_builder()
        self.assertEqual(
            extra, set(),
            f"alt_filter_param_names() lists {sorted(extra)} but "
            f"alt_db_where() never reads them, so they filter nothing while "
            f"making every export claim to be filtered.")

    def test_export_no_longer_keeps_its_own_copy(self):
        src = EXPORT_PHP.read_text()
        start = src.index("function alt_export_is_filtered(")
        body = src[start:src.index("\n}", start)]
        self.assertIn("alt_filter_param_names", body,
                      "alt_export_is_filtered must read the canonical list; a "
                      "second hand-maintained copy is what drifted before")
        self.assertIn("function_exists", body,
                      "keep the FTP-race guard: db.php can be mid-upload and a "
                      "hard dependency would fatal the export")

    def test_export_fallback_list_matches_the_canonical_list(self):
        # The mid-deploy fallback is a copy by necessity; if it silently rots we
        # are back to the original bug for the duration of every deploy.
        src = EXPORT_PHP.read_text()
        start = src.index("function alt_export_is_filtered(")
        body = src[start:src.index("\n}", start)]
        fallback = set(re.findall(r"'([a-z_]+)'", body)) - {
            "alt_filter_param_names", "function_exists"}
        self.assertEqual(fallback, _declared_filter_names())


class DocumentedContractTests(unittest.TestCase):

    def _filter_model_section(self):
        return ARCH.read_text().split("## Filter model")[1].split("\n## ")[0]

    def test_documented_filters_are_all_really_read(self):
        section = self._filter_model_section()
        read = _params_read_by_query_builder()
        # Names the doc presents as accepted filters, taken from its own prose.
        promised = {"years", "quarters", "months", "industry", "country",
                    "state", "sources", "reasons", "from", "to", "q",
                    "company", "keyword", "min_jobs", "ai"}
        for name in promised:
            self.assertIn(name, section,
                          f"'{name}' vanished from the Filter model section")
            self.assertTrue(
                name in read,
                f"docs/ARCHITECTURE.md promises the '{name}' filter but "
                f"alt_db_where never reads it. An unread param is silently "
                f"ignored and returns the UNFILTERED corpus — a wrong answer "
                f"served with a 200, not a missing feature.")

    def test_plural_aliases_are_not_accepted(self):
        read = _params_read_by_query_builder()
        for name in REJECTED_PLURALS:
            self.assertNotIn(
                name, read,
                f"alt_db_where now reads '{name}'. That may be an improvement, "
                f"but docs/ARCHITECTURE.md states plainly that the plurals are "
                f"NOT accepted and shows measured totals proving they return "
                f"the whole corpus. Update that table in the same commit, or "
                f"the docs become the lie they were written to fix.")

    def test_architecture_keeps_the_measurement_and_the_decision(self):
        section = self._filter_model_section()
        # The two opposite failure directions are the point of the table; a
        # future trim that keeps the param list but drops these loses it.
        self.assertIn("63,671", section,
                      "the measured over-reporting total is what makes the "
                      "silent-name failure concrete; keep it or re-measure it")
        for phrase in ("NOT accepted as aliases", "applied_filters"):
            self.assertIn(phrase, section,
                          f"the Filter model section no longer records "
                          f"'{phrase}' — the decision, and the real fix it "
                          f"defers to, must both stay written down")


if __name__ == "__main__":
    unittest.main()
