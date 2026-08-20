"""The Item 2.05 headcount that is not in the 8-K.

An 8-K filed under Item 2.05 is often a legal wrapper — "the Company committed
to a plan", "the Company expects to incur $X" — and the headcount is furnished
by the press release filed as EX-99.1 in the SAME accession. The collector read
only the primary document, so `extractor._count_in_text` correctly refused a
number it could not see and the filing was dropped at the last step.

Measured on the frozen SEC Item 2.05 gold set (57 filings, 2025-07..2026-06),
re-swept 2026-08-12 against live EDGAR: **7 of 57 filings state their count only
in an exhibit** — Sarepta 500, International Paper 1,100, Starbucks 900,
Celanese 160, Atlassian 1,600, Codexis 46, PLAYSTUDIOS 177. Five were matched
anyway through WARN/ERM/news; two (Codexis, PLAYSTUDIOS) are open misses.

Two properties are pinned here, and the second is the one that is easy to get
wrong:

1. THE GATE. The exhibit is read only when the primary document states no
   headcount at all. Unconditional exhibit fetching would multiply this
   collector's bytes and its paid LLM candidates for a minority of filings.

2. THE ANCHOR. Neither real exhibit contains a single phrase from
   `edgar.KEYWORDS` ("in November 2025, Codexis eliminated 46 positions";
   "Eliminating 177 positions"), so the keyword anchor falls through to
   `text[:RAW_TEXT_LIMIT]` and the counts — at offsets 3,766 and 7,582 of the
   stripped text — are truncated away before the extractor sees them. That is
   the EnerSys failure mode of 2026-08-01 (a real count discarded as though the
   model invented it) one document further along. The exhibit window is
   therefore anchored on the headcount itself.

And one property that must NOT change: Wabash National states "3 salaried and
53 hourly" + "21 salaried and 193 hourly" and never its 270 total. The
extractor refuses derived counts by design — loosening that is what once
published Intuit as 17 jobs. The gate does not even open for Wabash (its
primary window states headcounts), and 270 stays unverifiable either way.
"""
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Offline. No client is constructed and no request is made.
sys.modules.setdefault("openai", SimpleNamespace())
# `requests` is stubbed through tests/_requests_stub.py and nowhere else:
# sys.modules is process-global, so a per-module stub makes the surface a
# function of discovery order (see that module's docstring).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import extractor  # noqa: E402
import sources.edgar as edgar  # noqa: E402


ACC_DIR = "https://www.sec.gov/Archives/edgar/data/1200375/000119312525269716"
PRIMARY_URL = f"{ACC_DIR}/d80118d8k.htm"
INDEX_URL = f"{ACC_DIR}/0001193125-25-269716-index.htm"
EXHIBIT_URL = f"{ACC_DIR}/d80118dex991.htm"

# The shape of a real Item 2.05 primary document: it names the plan and the
# charge, and no headcount anywhere.
PRIMARY_HTML = """<html><body><p>Item 2.05 Costs Associated with Exit or
Disposal Activities.</p><p>On November 5, 2025, the Company committed to a
restructuring plan intended to reduce operating expenses. The Company expects
to incur charges of approximately $3.5 million, substantially all of which will
result in future cash expenditures.</p></body></html>"""

# The shape of the real EX-99.1: a long earnings press release with the count
# thousands of characters in, and NOT ONE phrase from edgar.KEYWORDS. The filler
# pushes the count past RAW_TEXT_LIMIT so an unanchored read cannot reach it.
_FILLER = ("<p>The Company reported revenue growth across its core programs "
           "and reiterated its outlook for the coming fiscal year.</p>") * 60
EXHIBIT_HTML = f"""<html><body><p>Codexis Reports Third Quarter 2025 Financial
Results</p>{_FILLER}<p>Britton Jiminez, Senior Vice President, Sales and
Marketing, will assume leadership for Codexis's commercial activities. In
November 2025, Codexis eliminated 46 positions, or approximately 24% of its
workforce. The company expects to recognize an additional expense of
approximately $3.5 million in the fourth quarter.</p>{_FILLER}</body></html>"""

# The Document Format Files table as EDGAR renders it: Seq, Description,
# Document (a link), Type, Size.
INDEX_HTML = f"""<html><body><table summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr><td scope="row">1</td><td scope="row">8-K</td>
<td scope="row"><a href="/Archives/edgar/data/1200375/000119312525269716/d80118d8k.htm">d80118d8k.htm</a></td>
<td scope="row">8-K</td><td scope="row">37342</td></tr>
<tr><td scope="row">2</td><td scope="row">EX-99.1</td>
<td scope="row"><a href="/Archives/edgar/data/1200375/000119312525269716/d80118dex991.htm">d80118dex991.htm</a></td>
<td scope="row">EX-99.1</td><td scope="row">91805</td></tr>
<tr><td scope="row">3</td><td scope="row">XBRL TAXONOMY EXTENSION SCHEMA</td>
<td scope="row"><a href="/Archives/edgar/data/1200375/000119312525269716/cdxs-20251105.xsd">cdxs-20251105.xsd</a></td>
<td scope="row">EX-101.SCH</td><td scope="row">2848</td></tr>
</table></body></html>"""

# Wabash National's primary document, in shape: four stated components, no
# total. 270 is DERIVED and must stay unverifiable.
WABASH_HTML = """<html><body><p>Item 2.05 Costs Associated with Exit or
Disposal Activities.</p><p>The Company will idle its Little Falls, Minnesota
facility, affecting 3 salaried and 53 hourly employees, and its Goshen, Indiana
facility, affecting 21 salaried and 193 hourly employees.</p></body></html>"""


class _Resp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


class _Transport:
    """Serves the three canned documents and records what was asked for."""

    def __init__(self, pages):
        self.pages = pages
        self.asked = []

    def get(self, url, **_kw):
        self.asked.append(url)
        if url not in self.pages:
            raise AssertionError(f"unexpected fetch: {url}")
        return _Resp(self.pages[url])


class _EdgarNetwork:
    """Install a transport over edgar.requests/time for the duration of a test."""

    SENTINEL = object()

    def __init__(self, case, pages):
        self.case = case
        self.transport = _Transport(pages)
        for attr, module, value in (("get", edgar.requests, self.transport.get),
                                    ("sleep", edgar.time, lambda *_a, **_k: None)):
            original = getattr(module, attr, self.SENTINEL)
            setattr(module, attr, value)
            case.addCleanup(self._restore, module, attr, original)

    @classmethod
    def _restore(cls, module, attr, original):
        if original is cls.SENTINEL:
            delattr(module, attr)
        else:
            setattr(module, attr, original)


class FilingIndexUrlTests(unittest.TestCase):

    def test_derived_from_the_document_path(self):
        self.assertEqual(edgar._filing_index_url(PRIMARY_URL), INDEX_URL)

    def test_none_when_the_path_is_not_an_archive_document(self):
        for bad in (None, "", "https://example.com/press-release.html",
                    "https://www.sec.gov/Archives/edgar/data/1200375/"):
            self.assertIsNone(edgar._filing_index_url(bad), bad)


class ExhibitDiscoveryTests(unittest.TestCase):

    def test_reads_the_ex_99_1_row_and_ignores_the_xbrl_rows(self):
        net = _EdgarNetwork(self, {INDEX_URL: INDEX_HTML})
        self.assertEqual(edgar._exhibit_urls(INDEX_URL), [EXHIBIT_URL])
        self.assertEqual(net.transport.asked, [INDEX_URL])


class HeadcountAnchorTests(unittest.TestCase):

    def test_recognises_a_stated_headcount(self):
        for text in ("eliminated 46 positions", "approximately 4,000 employees",
                     "a reduction of about 1 200 jobs", "177 positions",
                     "roughly 900 roles will be affected"):
            self.assertIsNotNone(edgar._headcount_index(text), text)

    def test_does_not_fire_on_money_or_dates(self):
        for text in ("charges of approximately $3.5 million",
                     "the plan was approved on November 5, 2025",
                     "a 24% reduction"):
            self.assertIsNone(edgar._headcount_index(text), text)


class ExhibitFallbackTests(unittest.TestCase):
    """The two open gold-set misses, in the shape EDGAR actually serves them."""

    def _pages(self):
        return {PRIMARY_URL: PRIMARY_HTML, INDEX_URL: INDEX_HTML,
                EXHIBIT_URL: EXHIBIT_HTML}

    def test_the_count_only_in_the_exhibit_survives_to_the_extractor(self):
        net = _EdgarNetwork(self, self._pages())
        text, url = edgar.fetch_document_window(PRIMARY_URL)

        # The window the collector hands over must satisfy the verbatim guard
        # AFTER extract_layoff_data's own truncation — the EnerSys lesson: a
        # count inside the collector's window and outside the extractor's is a
        # count that does not exist.
        self.assertTrue(
            extractor._count_in_text(46, text[:extractor.RAW_TEXT_LIMIT]),
            "the exhibit states 'Codexis eliminated 46 positions' but 46 did "
            "not survive to extractor.RAW_TEXT_LIMIT — the count is dropped as "
            "though the model invented it")
        self.assertEqual(url, EXHIBIT_URL,
                         "a row must cite the document whose sentence it quotes")
        self.assertIn(INDEX_URL, net.transport.asked)

    def test_the_window_is_anchored_on_the_count_not_on_the_document_head(self):
        # The property, not the byte offset: an unanchored read of this exhibit
        # returns its first RAW_TEXT_LIMIT characters, which do not contain 46.
        _EdgarNetwork(self, self._pages())
        text, _ = edgar.fetch_document_window(PRIMARY_URL)
        whole = edgar._strip_html(EXHIBIT_HTML)
        self.assertFalse(
            extractor._count_in_text(46, whole[:extractor.RAW_TEXT_LIMIT]),
            "fixture no longer reproduces the bug: the count must sit beyond an "
            "unanchored read, as it does in the real filings (offsets 3,766 and "
            "7,582)")
        self.assertEqual(
            [k for k in edgar.KEYWORDS if k in whole.lower()], [],
            "fixture must contain no edgar.KEYWORDS phrase, like the real "
            "exhibits — that is why the keyword anchor cannot save this")

    def test_the_gate_stays_shut_when_the_primary_states_a_headcount(self):
        stated = ("<html><body><p>Item 2.05.</p><p>The Company will reduce its "
                  "workforce by approximately 500 employees.</p></body></html>")
        net = _EdgarNetwork(self, {PRIMARY_URL: stated})
        text, url = edgar.fetch_document_window(PRIMARY_URL)
        self.assertEqual(url, PRIMARY_URL)
        self.assertTrue(extractor._count_in_text(500, text))
        self.assertEqual(
            net.transport.asked, [PRIMARY_URL],
            "the filing index must not be fetched when the primary document "
            "already states a headcount — unconditional exhibit reads are a "
            "large increase in bytes and in paid extraction candidates")

    def test_an_unreachable_exhibit_leaves_the_primary_untouched(self):
        net = _EdgarNetwork(self, {PRIMARY_URL: PRIMARY_HTML})  # index 404s
        text, url = edgar.fetch_document_window(PRIMARY_URL)
        self.assertEqual(url, PRIMARY_URL)
        self.assertIn("committed to a restructuring plan", text)
        self.assertIn(INDEX_URL, net.transport.asked)


class WabashStillMissesTests(unittest.TestCase):
    """The miss that must stay a miss. Do not 'fix' this test."""

    WABASH_URL = ("https://www.sec.gov/Archives/edgar/data/879526/"
                  "000087952626000003/wnc-20260105.htm")

    def test_a_derived_total_is_not_recoverable_and_the_gate_never_opens(self):
        net = _EdgarNetwork(self, {self.WABASH_URL: WABASH_HTML})
        text, url = edgar.fetch_document_window(self.WABASH_URL)
        self.assertEqual(url, self.WABASH_URL)
        self.assertEqual(
            net.transport.asked, [self.WABASH_URL],
            "the primary document states component headcounts, so the exhibit "
            "gate must not open")
        self.assertFalse(
            extractor._count_in_text(270, text[:extractor.RAW_TEXT_LIMIT]),
            "270 is the SUM of four separately stated components. The extractor "
            "refuses derived counts by design; admitting this is what published "
            "Intuit as 17 jobs. If this assertion fails, something was loosened.")
        for component in (3, 53, 21, 193):
            self.assertTrue(extractor._count_in_text(component, text),
                            f"{component} is stated verbatim and must remain so")


class ExhibitWindowIsWithinTheExtractionBudgetTests(unittest.TestCase):

    def test_the_exhibit_window_is_no_wider_than_the_extractor_reads(self):
        # Same rule as tests/test_extractor_text_budget.py, applied to the new
        # document: a window the extractor will not read is a window that lies.
        self.assertLessEqual(
            edgar.RAW_TEXT_LIMIT, extractor.RAW_TEXT_LIMIT,
            "the exhibit window uses edgar.RAW_TEXT_LIMIT; it must fit inside "
            "extractor.RAW_TEXT_LIMIT or the tail is cut before the guards")

    def test_the_exhibit_reader_uses_the_named_constant(self):
        source = (Path(__file__).resolve().parents[1]
                  / "sources" / "edgar.py").read_text()
        self.assertTrue(
            re.search(r"def _window_at\(text, idx\):[\s\S]{0,600}?"
                      r"text\[start:start \+ RAW_TEXT_LIMIT\]", source),
            "the shared windowing helper must slice with RAW_TEXT_LIMIT, not a "
            "pasted number")


if __name__ == "__main__":
    unittest.main()
