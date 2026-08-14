"""Quebec discovery/parse floors, and the silent-zero escalation.

These cover one incident with two halves (2026-08-13).

THE INSTANCE. `warn_quebec` reported "parser returned 0, check PDF layout" for
days. The parser was fine and so were the PDFs: discovery went through ONE
scraped HTML landing page, that page stopped returning links from CI, and the
collector had no other way to the documents. Repairing it also exposed three
quieter defects that a zero-check would never have caught, because the run was
not zero -- it was thin:
  * Quebec NUMBERED companies ("2534-1215 Quebec Inc.", "7806302 Canada Inc")
    were dropped by a guard meant to catch dates leaking into employer names.
  * the completeness audit double-counted, because the PDF prints its tally per
    region AND again as a grand total.
  * French typography groups thousands with a space, so "1 006" read as 1.

THE PATTERN. A collector returning zero where zero is impossible must escalate
like a stale one, saying what the source is worth and what to try instead --
not sit at "degraded" waiting to be noticed.

unittest, not pytest: the railway suite is run by `unittest discover` on a
runner that does not install pytest, so a pytest-only test file is an
ImportError that takes the whole suite down with it.
"""
import datetime
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import health_digest
import source_value
from sources import quebec


class _Resp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class DiscoveryDoesNotDependOnTheOnePageThatBroke(unittest.TestCase):
    def test_a_dead_landing_page_does_not_zero_the_collector(self):
        """The exact CI failure: the landing page answers with nothing usable."""
        with mock.patch.object(quebec.requests, "get",
                               return_value=_Resp(503, "")):
            urls, notes = quebec._discover(4)
        self.assertTrue(urls, "a dead landing page must not zero the collector: "
                              "Quebec is the only named layoff register in Canada")
        self.assertTrue(
            all(u.startswith("https://cdn-contenu.quebec.ca/") for u in urls))
        self.assertIn("503", notes["landing"])

    def test_the_landing_page_raising_does_not_zero_discovery(self):
        with mock.patch.object(quebec.requests, "get",
                               side_effect=OSError("tunnel refused")):
            urls, notes = quebec._discover(3)
        self.assertTrue(urls)
        self.assertIn("failed", notes["landing"])

    def test_the_six_renamed_months_are_reachable(self):
        """Route B is useless on these months unless the exceptions are encoded.

        The ministry filed 2023-10 and 2023-11 under a 2032 year typo and used
        a different stem for 2023-12..2024-03. A generated URL 404s on all six,
        so without this map a "36-month" backfill silently loses half a year.
        """
        for month in ["2023-10", "2023-11", "2023-12",
                      "2024-01", "2024-02", "2024-03"]:
            with self.subTest(month=month):
                self.assertIn(month, quebec._MONTH_URL_EXCEPTIONS)
        self.assertIn(
            "2032-10", quebec._MONTH_URL_EXCEPTIONS["2023-10"],
            "the 2032 typo is the ministry's, confirmed against the PDF's own "
            "/Subject metadata; correcting it here breaks the URL")

    def test_discovery_does_not_reach_below_the_live_archive(self):
        with mock.patch.object(quebec.requests, "get",
                               return_value=_Resp(503, "")):
            urls, _ = quebec._discover(120)
        self.assertTrue(urls)
        months = re.findall(r"(\d{4}-\d{2})", " ".join(urls))
        self.assertTrue(
            all(m >= "2021-01" for m in months),
            "nothing before the live CDN archive should be generated; older "
            "months exist only in Wayback and under other filenames")


class ParsingFloors(unittest.TestCase):
    def test_numbered_companies_are_valid_employers(self):
        """These are legal employer names, and the register is full of them."""
        for name in ["2534-1215 Québec Inc.", "9263-9319 Québec Inc.",
                     "7806302 Canada Inc - Planchers Mistral"]:
            with self.subTest(name=name):
                self.assertTrue(
                    quebec._valid_emp(name),
                    f"{name!r} is a numbered company, not a wrapped fragment; "
                    r"the old guard matched \d{4}-\d{2} inside it and dropped "
                    "real statutory notices")

    def test_a_real_date_in_a_name_is_still_rejected(self):
        """Widening for numbered companies must not let a date leak back in."""
        self.assertFalse(quebec._valid_emp("Foo Inc. 2026-07-14"))
        self.assertFalse(quebec._valid_emp("Bar Ltee 2026-07"))

    def test_french_thousands_separator_is_read(self):
        """'1 006' is one thousand and six, not one."""
        self.assertEqual(quebec._num("1 006"), 1006)
        self.assertEqual(quebec._num("1 006"), 1006)
        self.assertEqual(quebec._num("1 006"), 1006)
        self.assertEqual(quebec._num("710"), 710)

    def test_declared_total_prefers_the_grand_total_line(self):
        """The tally prints per region AND as a grand total; summing both
        double-counts the document and makes a complete parse look half
        missing."""
        line = ("Total - Nombre d'avis : 33 Total - Nombre de salariés "
                "licenciés : 1 006")
        m = quebec._GRAND_TOTAL_RX.search(line)
        self.assertIsNotNone(m, "the grand-total line must be recognised")
        self.assertEqual(quebec._num(m.group("notices")), 33)
        self.assertEqual(quebec._num(m.group("jobs")), 1006)

    def test_address_tail_is_stripped_from_employer_name(self):
        self.assertEqual(
            quebec._clean_emp("Les Chantiers de Chibougameau Ltée 67 Rue"),
            "Les Chantiers de Chibougameau Ltée")

    def test_health_detail_names_the_route_when_nothing_was_readable(self):
        """A zero must not be blamed on the parser when discovery is what
        died."""
        report = {"routes": {"landing": "HTTP 503", "constructed": "4 url(s)"},
                  "urls": 4, "fetched": 0, "parsed": 0, "declared_notices": 0,
                  "declared_jobs": 0, "jobs": 0, "errors": []}
        with mock.patch.object(quebec, "_LAST_REPORT", report):
            detail = quebec.health_detail([])
        self.assertIn("503", detail)
        self.assertIn("not a parser one", detail)


class AZeroThatCannotBeLegitimateMustEscalate(unittest.TestCase):
    def test_quebec_zero_is_declared_an_outage(self):
        self.assertTrue(source_value.zero_is_outage("warn_quebec"))
        worth = source_value.worth_line("warn_quebec")
        self.assertIn("Canada", worth)
        self.assertIn("10 employees", worth)

    def test_a_genuinely_quiet_source_is_not_an_outage(self):
        """The alarm must not cry wolf: that is how a channel gets filtered."""
        for src in ["warn_mazowieckie", "eurofound_erm",
                    "courtlistener_bankruptcy", "companies_house_insolvency",
                    "company_watchlist", "tracker_diff", "press_releases",
                    "digest_mailer", "context_enrichment"]:
            with self.subTest(source=src):
                self.assertFalse(source_value.zero_is_outage(src))

    def test_routes_are_never_empty_even_for_an_unknown_source(self):
        routes = source_value.routes_for("some_source_added_next_year")
        self.assertTrue(routes,
                        "a repair brief with no candidate routes is the old shrug")

    def test_escalation_line_leads_with_the_value_not_the_status(self):
        line = source_value.escalation_line("warn_quebec", "parser returned 0")
        self.assertTrue(line.startswith("warn_quebec is returning NO ROWS"))
        self.assertIn("ONLY public per-employer layoff register in Canada", line)

    def test_paste_line_carries_candidate_routes(self):
        """The digest promises a paste-ready fix instruction; it must name
        where to look, not just which source broke."""
        brief = source_value.repair_brief("warn_quebec")
        self.assertIn("CDN_TEMPLATE", brief)
        self.assertIn("Total - Nombre d'avis", brief)
        self.assertIn("web.archive.org", brief)

    def test_every_characterised_source_has_worth_and_routes(self):
        for src, entry in sorted(source_value.SOURCE_VALUE.items()):
            with self.subTest(source=src):
                self.assertTrue(entry.get("worth"))
                self.assertTrue(entry.get("routes"))
                self.assertIn("zero_is_outage", entry)


class TheDigestRedensOnACollectorReturningNothing(unittest.TestCase):
    """The case neither existing signal could see: the collector ran on
    schedule (so it is not stale) and reported ok (so it is not degraded),
    while producing no rows at all."""

    def _run_digest(self, ledger):
        class R:
            status_code = 200

            @staticmethod
            def json():
                return ledger

        with mock.patch.object(health_digest, "SITE", "https://example.invalid"), \
             mock.patch.object(health_digest, "DRY", True), \
             mock.patch.object(health_digest, "subscriber_line", lambda: ""), \
             mock.patch.object(health_digest.requests, "get",
                               return_value=R()):
            return health_digest.main()

    def test_a_zero_returning_collector_fails_the_run(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rc = self._run_digest({"warn_quebec": {
            "status": "ok", "entries": 0, "checked_at": now,
            "detail": "ran fine"}})
        self.assertEqual(rc, 2, "a collector returning nothing, where nothing "
                                "is impossible, must redden the digest like a "
                                "stale one")

    def test_a_legitimate_zero_does_not_fail_the_run(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rc = self._run_digest({"courtlistener_bankruptcy": {
            "status": "ok", "entries": 0, "checked_at": now,
            "detail": "no distressed companies surfaced this run"}})
        self.assertEqual(rc, 0)

    def test_a_healthy_quebec_run_does_not_fail(self):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        rc = self._run_digest({"warn_quebec": {
            "status": "ok", "entries": 20, "checked_at": now,
            "detail": "20/20 notices, 710 jobs from 1 monthly PDF(s)"}})
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
