"""Offline tests for the filing-shape guards (TECHLOG 2026-09-16).

THE KNOWN INSTANCES this is written from, all live US data of July/August 2026
(docs/findings-july-august-2026-us-accuracy.md):

  * Row 176990, "Aeternum Health", 20,000 jobs, 8-K. The sentence sits in the
    filing's RISK FACTORS and quotes HHS's own press language ("intends to
    reduce our workforce"); the extractor bound "our" to the registrant, a
    shell company. The row also carried announcement_date 2025-03-27 against
    layoff_date 2026-07-07, 467 days. Trashed by correction on 2026-09-16.
  * Row 177216, "Applied Aerospace & Defense", 4,320 jobs, 8-K. The figure is
    4,320 in an Adjusted EBITDA reconciliation headed "(in thousands, except
    percentages)": 4,320 THOUSAND DOLLARS of integration and restructuring
    cost. The filing states no headcount anywhere. Still live.
  * Row 176490, "Aon plc", 3,500 jobs, 8-K, announced 2014-04-01 for
    2020-05-12: 2,233 days. Still live; the invariant FAILS on it today.
  * Rows 178667 / 177173, Paramount, news, 4,500 and 2,500 jobs. A Los Angeles
    County consultancy's projection of REGIONAL production-job losses from a
    merger that is on hold, stored as the studio's own announcement.
    WARN-level tripwire only, never a refusal.

Fixture text is the real filings' own stripped text, cut to the passages that
matter, so a regex that fails on real punctuation fails here. No network, no
keys, no model: the post-parse function is exercised on a fake parsed dict and
the invariant on an injected fetch.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
import urllib.error
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import data_integrity as di  # noqa: E402
import extractor  # noqa: E402
import filing_shapes as fs  # noqa: E402
from extractor import finalize_extraction  # noqa: E402
from sources import edgar  # noqa: E402

# --- real filing text ------------------------------------------------------

#: Aeternum Health 8-K (accession 0001493152-26-032365): the Item 2.01 heading,
#: the Risk Factors heading, and the HHS paragraph the 20,000 was read from, in
#: their real order. The filler stands in for ~100KB of other risk factors.
AETERNUM_HEAD = "☒ Item 2.01 Completion of Acquisition or Disposition of Assets. In our Form 8-K filed February 23, 2026, the registrant, Aeternum Health, Inc. f/k/a Shorepower Technologies, Inc. a Delaware corporation (“Shorepower” or the “Company”) stated that on February 17"
AETERNUM_RISK = "se trends and developments with our products and offerings; Risk Factors Risks Related to our Company and our Business We have an extremely limited operating history. We are currently a start-up company with no current sales of any products. There is no historical basis to make j"
AETERNUM_HHS = "For example, on March 27, 2025, the U.S. Department of Health and Human Services (HHS), which houses both CMS and the FDA, announced significant restructuring in accordance with EO 14219. Among other changes, HHS announced that it intends to reduce our workforce by approximately 10,000 full-time employees, consolidate 28 existing divisions into 15 new divisions, and centralize certain core functions. Notably, this restructuring plan is in addition to other downsizing efforts at HHS, which in combination will result in a reduction of force by 20,000 employees. There is substantial uncertainty regarding how these changes will impact the FDA. HHS intends to reduce the FDA’s workforce by 3,500 individuals, which represents approximately 18% of FDA full-time employees. "
AETERNUM = (AETERNUM_HEAD + " (other disclosures) " + AETERNUM_RISK
            + " (other risks) " + AETERNUM_HHS)

#: Nutanix 8-K (0001193125-26-331661), the Item 2.05 block, real text.
NUTANIX = " accounting standards provided pursuant to Section 13(a) of the Exchange Act. ☐ Item 2.05 Costs Associated with Exit or Disposal Activities. On August 4, 2026, Nutanix, Inc. (the “Company”) announced a plan to reduce its global workforce by approximately 5%, following a review of its business structure. The workforce reduction is intended to streamline and realign the Company’s organizational structure, improve operational efficiency and agility, and reallocate resources toward strategic priorities and long-term growth objectives. The ultimate scope, timing and implementation of the workforce reduction may vary by jurisdiction and remain subject to applicable local law requirements, consultation processes, engagement with employee representative bodies (including works councils where applicable), and other implementation considerations. The Company currently expects to substantially complete the workforce reduction by the end of October 2026. The Company currently estimates that it will incur aggregate pre-tax charges of approximately $33 million to $43 million as part of the workforce reduction, primarily consisting of one-time severance and other termination benefit costs, a substantial majority of which are expected to result in future cash expenditures. These estimates are subject to several assumptions, including applicable local law requirements, consultation obligations, and works council processes in certain jurisdictions, and actual charges may differ materially from current estimates. "

#: Applied Aerospace & Defense earnings release (0001628280-26-055948): the
#: Adjusted EBITDA reconciliation rows and their footnotes, real text.
APPLIED_TABLE = "Share-based compensation expense 110,086 802 110,842 1,604 Transaction costs (1) 5,176 48 19,161 562 Integration and restructuring costs (2) 2,047 1,336 4,320 3,377 Legal contingencies loss (3) — 109 — 116 Management fees (4) 233 421 482 677 Other (5) — 16 — 37 Adjusted EBITDA $ 36,437 $ 26,306 $ 62,976 $ 51,649 Net loss margin (92.0) % (4.1) % (56.1) % (5.3) % Adjusted EBITDA margin 21.8 % 23.2 % 20.9 % 23.0 % (1) Includes transaction-related costs associated with mergers, acquisitions, and costs related to the IPO. (2) Includes acquisition integration and restructuring costs, including plant consolidation and reconfiguration, reductions in force, and executive severance expense. "
#: The units declaration that heads that table in the filing, verbatim.
APPLIED_UNITS = ("Three Months Ended June 30, Six Months Ended June 30, "
                 "(in thousands, except percentages) 2026 2025 2026 2025 ")
APPLIED = APPLIED_UNITS + APPLIED_TABLE
#: Row 177216's stored excerpt, verbatim. It is real text from the filing, and
#: it does not contain 4,320 at all.
APPLIED_FOOTNOTE = ("Includes acquisition integration and restructuring costs, including "
                    "plant consolidation and reconfiguration, reductions in force, and "
                    "executive severance expense.")

#: The two live Paramount excerpts, verbatim from the published rows.
PARAMOUNT_A = ("The merger of Paramount and Warner Bros. could cost about 4,500 film and TV "
               "jobs over three years, according to a new report issued by Los Angeles "
               "County. The report, prepared by CVL Economics, argues that the merger "
               "would accelerate the downturn in L.A. production, which has already cost "
               "52,000 jobs over the last four years.")
PARAMOUNT_B = ("In Los Angeles County alone, the merger could result in a loss of nearly "
               "2,500 jobs, according to an analysis by the Los Angeles County Department "
               "of Economic Opportunity, published in June. As many as 6,000 employees "
               "around the world could also see their positions cut.")

HHS_EXCERPT = ("HHS announced that it intends to reduce our workforce by approximately "
               "10,000 full-time employees, consolidate 28 existing divisions into 15 new "
               "divisions, and centralize certain core functions. Notably, this "
               "restructuring plan is in addition to other downsizing efforts at HHS, "
               "which in combination will result in a reduction of force by 20,000 employees.")


def _entry(text, source_type="8K", filing_date="2026-07-07", section=None, **extra):
    row = {"raw_text": text, "filing_date": filing_date, "source_type": source_type,
           "source_name": "SEC EDGAR 8-K", "source_url": "https://www.sec.gov/x.htm",
           "verification_level": "gold", "company_name": "Filer Inc"}
    if section is not None:
        row["sec_section"] = section
    row.update(extra)
    return row


def _parsed(count, excerpt, company="Filer Inc", layoff_date="2026-07-07", **extra):
    row = {"is_layoff_event": True, "company_name": company, "job_count": count,
           "job_count_max": count, "layoff_date": layoff_date, "excerpt": excerpt,
           "confidence": 90, "ai_causation": "unknown", "reason_tags": []}
    row.update(extra)
    return row


# --- the section detector ----------------------------------------------------

class TheSectionDetector(unittest.TestCase):

    def test_the_hhs_sentence_sits_in_risk_factors(self):
        idx = AETERNUM.lower().find("reduce our workforce")
        self.assertGreater(idx, 0)
        self.assertEqual(fs.filing_section(AETERNUM, idx), fs.RISK_FACTORS_SECTION)

    def test_a_real_item_205_block_is_item_205(self):
        idx = NUTANIX.lower().find("reduce its global workforce")
        self.assertGreater(idx, 0)
        self.assertEqual(fs.filing_section(NUTANIX, idx), "item_2.05")

    def test_a_quoted_reference_to_risk_factors_is_not_a_heading(self):
        """Forward-looking boilerplate names Risk Factors in every filing."""
        text = ('Item 2.05 Costs Associated with Exit or Disposal Activities. See the '
                'Risk Factors section of our Form 10-K. On May 1 the Company committed '
                'to a plan to reduce its workforce by 120 employees.')
        self.assertEqual(fs.filing_section(text, text.find("reduce its")), "item_2.05")

    def test_nothing_before_the_text_is_none_not_risk(self):
        self.assertIsNone(fs.filing_section("reduce its workforce by 120", 0))
        self.assertIsNone(fs.filing_section("", 5))

    def test_the_collector_reports_the_section_beside_the_window(self):
        window, section = edgar._primary_window(AETERNUM)
        self.assertEqual(section, fs.RISK_FACTORS_SECTION)
        self.assertTrue(window)
        window, section = edgar._primary_window(NUTANIX)
        self.assertEqual(section, "item_2.05")


# --- the ingest gates ---------------------------------------------------------

class TheKnownInstances(unittest.TestCase):
    """Each gate refuses the row it was written from, and its mutation passes."""

    def test_176990_is_refused_by_its_section_alone(self):
        row = finalize_extraction(
            _parsed(20000, HHS_EXCERPT, company="Aeternum Health, Inc."),
            _entry(AETERNUM, section=fs.RISK_FACTORS_SECTION), AETERNUM)
        self.assertIsNone(row)

    def test_mutation_the_same_sentence_from_an_item_block_is_not_refused(self):
        """The section is the ONLY thing that changes, and the gate stops firing.

        The row is given no announcement_date so the date gate below cannot be
        what admits or refuses it: this isolates the section gate.
        """
        row = finalize_extraction(
            _parsed(20000, HHS_EXCERPT, company="Aeternum Health, Inc."),
            _entry(AETERNUM, section="item_2.05"), AETERNUM)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 20000)

    def test_176990_is_refused_by_its_own_dates(self):
        """The row's stored fields, verbatim: announced 2025-03-27, effective 2026-07-07."""
        parsed = _parsed(
            20000, HHS_EXCERPT, company="Aeternum Health, Inc.",
            announcement_date="2025-03-27",
            announcement_evidence=("on March 27, 2025, the U.S. Department of Health "
                                   "and Human Services"))
        self.assertIsNone(finalize_extraction(
            parsed, _entry(AETERNUM, section="item_2.05"), AETERNUM))

    def test_mutation_the_same_row_inside_the_ceiling_is_stored(self):
        parsed = _parsed(
            20000, HHS_EXCERPT, company="Aeternum Health, Inc.",
            announcement_date="2026-06-01",
            announcement_evidence=("on March 27, 2025, the U.S. Department of Health "
                                   "and Human Services"))
        row = finalize_extraction(parsed, _entry(AETERNUM, section="item_2.05"), AETERNUM)
        self.assertIsNotNone(row)

    def test_a_year_end_closure_announced_in_may_is_stored(self):
        """Koppers, live row 176908: announced 2026-05-08 for 2026-12-31, 237 days.

        Inside the review band, outside the refusal. This is the row that sets
        the ceiling: a legitimate filing really can lead its own effective date
        by most of a year.
        """
        text = ("Item 2.05 Costs Associated with Exit or Disposal Activities. On May 8, "
                "2026, the Company announced that it will close its plant by December 31, "
                "2026, eliminating approximately 85 positions.")
        parsed = _parsed(85, "eliminating approximately 85 positions",
                         layoff_date="2026-12-31", announcement_date="2026-05-08",
                         announcement_evidence="On May 8, 2026, the Company announced")
        row = finalize_extraction(
            parsed, _entry(text, filing_date="2026-05-08", section="item_2.05"), text)
        self.assertIsNotNone(row)
        self.assertEqual(row["announcement_date"], "2026-05-08")

    def test_the_lead_gate_bites_when_only_the_filing_date_is_old(self):
        """A filing dated long after the announcement is quoting history, even
        when the model dated the effective date recently."""
        text = ("Item 8.01 Other Events. As previously announced on April 1, 2024, the "
                "Company reduced its workforce by 300 employees.")
        parsed = _parsed(300, "reduced its workforce by 300 employees",
                         layoff_date="2026-07-07", announcement_date="2024-04-01",
                         announcement_evidence="As previously announced on April 1, 2024")
        self.assertIsNone(finalize_extraction(
            parsed, _entry(text, filing_date="2026-07-07", section="item_8.01"), text))

    def test_177216_the_real_filing_text_states_4320_only_as_money(self):
        """The dollar figure read as a headcount, on the filing's own text."""
        self.assertTrue(fs.count_only_as_cost(4320, APPLIED))

    def test_mutation_177216_stated_once_as_people_is_not_this_shape(self):
        self.assertFalse(fs.count_only_as_cost(4320, APPLIED + " We eliminated 4,320 positions."))

    def test_177216_is_refused_and_the_cost_gate_is_what_refuses_it(self):
        """The real row, with its real excerpt, and WHICH LAYER decides.

        An older guard already covers this shape at ingest
        (`_count_has_headcount_context`, shipped 2026-09-07 from this very
        filing), so "the row is refused" proves nothing about the new gate on
        its own. The refusal reason is captured and asserted, and the cost gate
        is placed ahead of the excerpt checks so it is the one that speaks.

        What the new gate adds over the old one is REACH: the old gate reads
        only the model's excerpt, so it is silent whenever the model returns an
        excerpt that does sit beside a people-noun somewhere else in the
        filing. This one reads the whole window.
        """
        excerpt = APPLIED_FOOTNOTE
        buf = io.StringIO()
        with redirect_stdout(buf):
            row = finalize_extraction(
                _parsed(4320, excerpt), _entry(APPLIED, section="exhibit"), APPLIED)
        self.assertIsNone(row)
        self.assertIn("only as a cost, scale or table figure", buf.getvalue())

    def test_mutation_without_the_cost_gate_the_old_guard_still_has_to_catch_it(self):
        """The two layers are not redundant, and this pins the difference: strip
        the cost binding out of the text and the new gate lets go, at which
        point the excerpt gate is the only thing left."""
        loose = "Integration and restructuring costs 4,320 for the period."
        self.assertFalse(fs.count_only_as_cost(4320, loose))
        self.assertFalse(extractor._count_has_headcount_context(4320, APPLIED_FOOTNOTE))

    def test_the_units_header_is_what_binds_it(self):
        """Mutation on the units declaration alone: remove it and, with the table
        run also broken up, the figure is no longer bound."""
        loose = "Integration and restructuring costs 4,320 for the period."
        self.assertFalse(fs.count_only_as_cost(4320, loose))
        self.assertTrue(fs.count_only_as_cost(4320, APPLIED_UNITS + loose))

    def test_a_units_header_never_binds_a_people_adjacent_count(self):
        """A press release declares units for its tables and then states a real
        headcount in prose. Refusing that row would be the guard sharing its
        target's blind spot."""
        text = (APPLIED_UNITS + "Net loss 1,234 5,678 Adjusted EBITDA 9,000. "
                "The Company will eliminate 500 positions.")
        self.assertFalse(fs.count_only_as_cost(500, text))

    def test_the_cost_gate_reads_currency_scale_and_tables_as_bound(self):
        self.assertTrue(fs.count_only_as_cost(500, "charges of $500 million"))
        self.assertTrue(fs.count_only_as_cost(500, "severance of USD 500 thousand"))
        self.assertTrue(fs.count_only_as_cost(12, "reduce its workforce by 12%"))
        self.assertTrue(fs.count_only_as_cost(4320, "costs (2) 2,047 1,336 4,320 3,377"))
        self.assertFalse(fs.count_only_as_cost(500, "$500 million of charges and 500 employees"))
        self.assertFalse(fs.count_only_as_cost(500, "will lay off 500 workers"))
        self.assertFalse(fs.count_only_as_cost(500, "no such number here"))

    def test_the_cost_gate_is_8k_only(self):
        """Multilingual news does not get the English money regex, the same trade
        _count_has_headcount_context already makes."""
        text = "La empresa recortara 500 empleos. Los cargos son de $500 millones."
        row = finalize_extraction(
            _parsed(500, "recortara 500 empleos", layoff_date="2026-08-01"),
            _entry(text, source_type="news", filing_date="2026-08-01",
                   verification_level="bronze"), text)
        self.assertIsNotNone(row)


class TheProjectionTripwireIsWarnLevel(unittest.TestCase):
    """Rows 178667 and 177173: a county's regional forecast, not an announcement."""

    def test_both_live_excerpts_trip_it(self):
        self.assertTrue(fs.projection_language(PARAMOUNT_A))
        self.assertTrue(fs.projection_language(PARAMOUNT_B))

    def test_it_names_the_words_it_matched(self):
        self.assertIn("could cost", fs.projection_language(PARAMOUNT_A))

    def test_a_plain_employer_announcement_does_not_trip_it(self):
        self.assertEqual(fs.projection_language(NUTANIX), [])
        self.assertEqual(
            fs.projection_language("Acme will lay off 500 workers in October, the company said."),
            [])

    def test_it_never_refuses_the_row(self):
        """WARN level, by design: the same words also report real announcements."""
        parsed = _parsed(4500, PARAMOUNT_A, company="Paramount-Warner Bros.",
                         layoff_date="2026-08-19")
        row = finalize_extraction(
            parsed, _entry(PARAMOUNT_A, source_type="news", filing_date="2026-08-19",
                           verification_level="bronze"), PARAMOUNT_A)
        self.assertIsNotNone(row)
        self.assertEqual(row["job_count"], 4500)


# --- the live invariant -------------------------------------------------------

def _row(row_id, jobs, announced, effective, source_type="8K", excerpt="x 1 y"):
    return {"id": row_id, "job_count": jobs, "announcement_date": announced,
            "layoff_date": effective, "source_type": source_type, "excerpt": excerpt}


AON = _row(176490, 3500, "2014-04-01", "2020-05-12")
AETERNUM_ROW = _row(176990, 20000, "2025-03-27", "2026-07-07", excerpt=HHS_EXCERPT)
KOPPERS = _row(176908, 85, "2026-05-08", "2026-12-31")
APPLIED_ROW = _row(177216, 4320, "", "2026-08-12", excerpt=APPLIED_FOOTNOTE)
ORDINARY = [_row(1, 1200, "2026-08-01", "2026-08-01", excerpt="1,200 employees"),
            _row(2, 800, "", "2026-08-05", excerpt="800 positions"),
            _row(3, 300, "2026-07-30", "2026-08-20", excerpt="300 roles")]


def _page(rows, total=None):
    return json.dumps({"data": rows,
                       "total": len(rows) if total is None else total}).encode()


def _ctx(body, today=date(2026, 9, 16)):
    def fetch(url, timeout):
        if isinstance(body, Exception):
            raise body
        return body
    return di.Ctx(fetch, 5, "cb", today=today)


class TheInvariantOnTheKnownInstances(unittest.TestCase):

    def test_it_fails_on_the_live_aon_row_and_names_it(self):
        res = di.FilingShapeInvariant().run(_ctx(_page(ORDINARY + [AON])))
        self.assertEqual(res.state, di.FAIL)
        self.assertIn("176490", res.detail)
        self.assertIn("2,233 days", res.detail)
        self.assertIn("3,500", res.detail)

    def test_it_would_have_failed_on_aeternum(self):
        res = di.FilingShapeInvariant().run(_ctx(_page(ORDINARY + [AETERNUM_ROW])))
        self.assertEqual(res.state, di.FAIL)
        self.assertIn("176990", res.detail)
        self.assertIn("467 days", res.detail)

    def test_mutation_widening_the_ceiling_silences_it(self):
        """Proof the threshold is what catches these, and the reason it is not
        to be widened when it fires."""
        self.assertEqual(
            di.filing_shape_findings([AON, AETERNUM_ROW], refuse_after=10000)["refuse"], [])
        self.assertEqual(
            [r["id"] for r in di.filing_shape_findings([AON, AETERNUM_ROW])["refuse"]],
            [176490, 176990])

    def test_the_review_band_is_named_but_never_failed(self):
        res = di.FilingShapeInvariant().run(_ctx(_page(ORDINARY + [KOPPERS])))
        self.assertEqual(res.state, di.PASS)
        self.assertIn("176908", res.detail)
        self.assertIn("adjudicate, not failed", res.detail)

    def test_177216_is_named_as_the_count_absent_shape_but_not_failed(self):
        res = di.FilingShapeInvariant().run(_ctx(_page(ORDINARY + [APPLIED_ROW])))
        self.assertEqual(res.state, di.PASS)
        self.assertIn("177216", res.detail)
        self.assertIn("row-177216 shape", res.detail)

    def test_ordinary_rows_pass_and_the_floor_is_printed(self):
        res = di.FilingShapeInvariant().run(_ctx(_page(ORDINARY, total=991)))
        self.assertEqual(res.state, di.PASS)
        self.assertIn("down to 300 jobs", res.detail)
        self.assertIn("NOT claimed clean", res.detail)

    def test_non_8k_rows_are_ignored_however_long_their_lead(self):
        news = _row(9, 5000, "2014-01-01", "2026-01-01", source_type="news")
        self.assertEqual(di.filing_shape_findings([news])["refuse"], [])


class MissingDataIsNotAPass(unittest.TestCase):

    def test_unreachable_is_unknown(self):
        self.assertEqual(
            di.FilingShapeInvariant().run(_ctx(OSError("refused"))).state, di.UNKNOWN)

    def test_503_is_the_deploy_window(self):
        err = urllib.error.HTTPError("u", 503, "maint", {}, None)
        res = di.FilingShapeInvariant().run(_ctx(err))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("503", res.detail)

    def test_an_empty_page_is_unknown_not_a_clean_sweep(self):
        res = di.FilingShapeInvariant().run(_ctx(_page([])))
        self.assertEqual(res.state, di.UNKNOWN)
        self.assertIn("did not run", res.detail)

    def test_an_undecodable_body_is_unknown(self):
        self.assertEqual(
            di.FilingShapeInvariant().run(_ctx(b"<html>bot challenge</html>")).state,
            di.UNKNOWN)


class WiredIntoTheOneRegistry(unittest.TestCase):

    def test_registered_exactly_once(self):
        self.assertEqual([i.key for i in di.INVARIANTS].count("filing_shape_tells"), 1)

    def test_declares_that_it_reads_live_data(self):
        self.assertTrue(di.FilingShapeInvariant.reads_live_data)

    def test_one_request_never_a_page_walk(self):
        urls = []

        def fetch(url, timeout):
            urls.append(url)
            return _page(ORDINARY)

        di.FilingShapeInvariant().run(di.Ctx(fetch, 5, "cb", today=date(2026, 9, 16)))
        self.assertEqual(len(urls), 1)
        self.assertIn("sources=8K", urls[0])
        self.assertIn("page=1", urls[0])

    def test_both_layers_read_one_ceiling(self):
        """The ingest gate and the live invariant must not drift apart."""
        self.assertIs(extractor.MAX_8K_LEAD_DAYS, fs.MAX_8K_LEAD_DAYS)
        self.assertIs(di.MAX_8K_LEAD_DAYS, fs.MAX_8K_LEAD_DAYS)


if __name__ == "__main__":
    unittest.main()
