"""The per-country picture cannot quietly become an opinion again.

WHAT THESE GUARD. `country_coverage.REGISTER` will be the evidence behind a
sentence the owner says in public — "100% of what is publicly disclosed, per
country, with the disclosure regime named". The failure that matters is not that
a classification is wrong; a wrong one is visible, cited and arguable. It is that
a classification becomes UNCHECKABLE while still reading as a finding:

  * a country enters the corpus and nobody establishes what exists to be found
    in it, and the register stays green because it only reports what it holds
  * an entry loses its citation and becomes an assertion
  * "no regime exists here" is written once and quoted for years after a
    parliament changed it
  * a REFUSED source quietly becomes a fetched one because somebody decided the
    robots.txt did not really mean us

Each of those has a test below and each fails on a register that omits the
guard. The classifications themselves are checked by their citations, by a
human, which is why every entry is required to carry one.
"""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import country_coverage as cc


def _stub_aggregate(countries):
    """A /aggregate response carrying exactly these country names."""
    body = json.dumps({"map_countries": [[c, 100, 5, None, 0, 0] for c in countries]})
    return lambda url: body


class EveryEntryIsCheckable(unittest.TestCase):
    """An entry without a citation is an assertion, not a finding.

    The register's entire defensibility is that a reader who disagrees can open
    the URL and argue with the statute. An entry that names a regime but cannot
    say where that came from is exactly the kind of error that survives review by
    looking like work.
    """

    def test_every_entry_carries_the_required_fields(self):
        for name, entry in cc.REGISTER.items():
            for field in cc.REQUIRED_FIELDS:
                self.assertTrue(entry.get(field),
                                f"{name}: register entry has no {field!r}")

    def test_every_entry_has_a_known_classification(self):
        for name, entry in cc.REGISTER.items():
            self.assertIn(entry["class"], cc.CLASSIFICATIONS, name)

    def test_every_citation_is_a_url(self):
        for name, entry in cc.REGISTER.items():
            self.assertTrue(str(entry["cite"]).startswith("http"),
                            f"{name}: cite is not a URL a human can open: "
                            f"{entry['cite']!r}")

    def test_every_assessed_date_is_a_real_date(self):
        for name, entry in cc.REGISTER.items():
            try:
                date(*(int(x) for x in entry["assessed"].split("-")))
            except (ValueError, TypeError, AttributeError):
                self.fail(f"{name}: unreadable assessed date {entry['assessed']!r}")

    def test_a_country_with_a_regime_names_its_authority_and_threshold(self):
        """"A regime exists" is only checkable if it says who receives the notice.

        Without the authority and the threshold the claim cannot be falsified,
        and an unfalsifiable claim in this register is worse than a blank one
        because it stops anybody looking.
        """
        for name, entry in cc.REGISTER.items():
            if entry["class"] in (cc.REGIME_WITH_AGGREGATE, cc.REGIME_NO_AGGREGATE,
                                  cc.REFUSED):
                self.assertTrue(entry.get("authority"),
                                f"{name}: claims a regime but names no authority")
                self.assertTrue(entry.get("threshold"),
                                f"{name}: claims a regime but states no threshold")

    def test_a_no_regime_finding_states_what_was_checked(self):
        """NO_REGIME is the strongest claim here and needs the most evidence."""
        for name, entry in cc.REGISTER.items():
            if entry["class"] == cc.NO_REGIME:
                self.assertGreater(len(entry.get("regime") or ""), 40,
                                   f"{name}: 'no regime' must say what was looked for "
                                   f"and found absent, not just assert absence")


class ARefusalStaysARefusal(unittest.TestCase):
    """A source that disallows AI agents is recorded refused, not routed around.

    This already cost the project one otherwise perfect denominator (Wisconsin's
    annual WARN total) and the answer was to record it. The guard exists because
    the temptation to "fix" a REFUSED entry is highest exactly when it is the
    only thing standing between the register and a complete row.
    """

    def test_every_refused_entry_says_who_refused_and_why(self):
        for name, entry in cc.REGISTER.items():
            if entry["class"] == cc.REFUSED:
                for field in cc.REFUSAL_FIELDS:
                    self.assertTrue(entry.get(field),
                                    f"{name}: REFUSED with no {field} recorded")

    def test_a_refusal_missing_its_host_is_unknown_not_a_quiet_refusal(self):
        """REFUSED is terminal, so it must not become the register's dustbin.

        An entry that says "blocked" without naming the host cannot be
        re-checked by anyone, which turns a temporary block into a permanent
        exemption by accident.
        """
        saved = dict(cc.REGISTER)
        try:
            cc.REGISTER["Testland"] = {
                "class": cc.REFUSED, "regime": "x", "authority": "y",
                "threshold": "z", "aggregate": "published but unreachable",
                "assessed": date.today().isoformat(),
                "cite": "https://example.invalid/",
                "refusal_reason": "blocked"}          # no refusal_host
            rec = cc.entry_for("Testland")
            self.assertEqual(rec["state"], cc.UNKNOWN)
            self.assertIn("refusal_host", rec["detail"])
        finally:
            cc.REGISTER.clear()
            cc.REGISTER.update(saved)

    def test_a_refused_country_is_not_measurable(self):
        # It maps to NOT_MEASURABLE, never to MEASURED — a denominator we may
        # not fetch is not a denominator we have.
        self.assertEqual(cc.STATE_OF[cc.REFUSED], cc.NOT_MEASURABLE)


class TheRefusalLedgerIsWrittenDownNotRemembered(unittest.TestCase):
    """A refusal in prose gets rediscovered; a refusal in a structure does not.

    Two distinct failures are prevented here and they pull in opposite
    directions. One is waste: somebody sees a gap, goes looking for the obvious
    source, and spends an afternoon arriving at the same 403. The other is
    worse: they do not recognise it AS a refusal, retry with a different agent
    string, and quietly turn a respected block into a defeated one.
    """

    def test_every_refusal_names_a_host_and_the_nature_of_the_block(self):
        for row in cc.REFUSAL_LEDGER:
            self.assertTrue(row.get("host"), f"ledger row with no host: {row}")
            self.assertGreater(len(row.get("nature") or ""), 15,
                               f"{row.get('host')}: does not say HOW it refuses, so the "
                               f"next reader cannot tell a robots directive from an "
                               f"outage")

    def test_every_refusal_states_its_alternative_or_says_there_is_none(self):
        """A refusal with a permitted alternative is a detour, not a loss.

        Leaving the field blank makes those two look the same, which is how a
        recoverable gap gets written off.
        """
        for row in cc.REFUSAL_LEDGER:
            self.assertIn("alternative", row,
                          f"{row['host']}: no alternative field — say 'none found' "
                          f"explicitly rather than omitting it")
            self.assertTrue(str(row["alternative"]).strip(), row["host"])

    def test_every_refusal_says_whether_it_was_verified_here(self):
        """This ledger is used to decide NOT to try something.

        "Somebody said it was blocked" is a weaker basis for that than "I read
        the file", and collapsing the two would let a mistaken report become a
        permanent no-go. One of these entries was in fact reported backwards
        first: an Italian host was recorded as permitting us when its robots.txt
        names ClaudeBot and disallows it.
        """
        for row in cc.REFUSAL_LEDGER:
            self.assertIn("verified_here", row, row["host"])
            self.assertIsInstance(row["verified_here"], bool, row["host"])

    def test_a_refused_country_appears_in_the_ledger(self):
        """The register and the ledger must not drift apart.

        A country classified REFUSED names a refusal_host; that host has to be
        findable in the ledger, or the ledger stops being the place a
        collector-builder can trust to be complete.
        """
        hosts = " ".join(r["host"] for r in cc.REFUSAL_LEDGER)
        for name, entry in cc.REGISTER.items():
            if entry["class"] != cc.REFUSED:
                continue
            first = entry["refusal_host"].split(" ")[0].split(",")[0]
            self.assertIn(first, hosts,
                          f"{name} is REFUSED on {first} but that host is not in "
                          f"REFUSAL_LEDGER")

    def test_the_ledger_is_carried_into_the_committed_report(self):
        report = cc.classify_all(fetch=_stub_aggregate(sorted(cc.REGISTER)))
        self.assertEqual(len(report["refusal_ledger"]), len(cc.REFUSAL_LEDGER))


class AnUnclassifiedCountryIsUnknownNotFine(unittest.TestCase):
    """The failure this whole module exists to catch.

    A country arriving in the corpus with nobody establishing what exists to be
    found in it must make the report UNKNOWN and name itself. A register that
    only reports what it holds would stay green forever.
    """

    def test_a_country_in_neither_register_nor_backlog_makes_the_report_unknown(self):
        report = cc.classify_all(fetch=_stub_aggregate(["Wakanda"]))
        self.assertIn("Wakanda", report["undeclared"])
        state, detail = cc.judge(report)
        self.assertEqual(state, cc.UNKNOWN)
        self.assertIn("Wakanda", detail)

    def test_an_acknowledged_country_does_not_redden(self):
        """The backlog is the one concession, and it must actually work.

        A check that is red from the day it ships until the day the last country
        on earth is classified is a check nobody reads — this repo already knows
        what eight identical emails in one afternoon do to an alert channel. So
        acknowledged, dated outstanding work passes; an unnoticed arrival does
        not.
        """
        known = sorted(cc.ACKNOWLEDGED_BACKLOG)[0]
        report = cc.classify_all(fetch=_stub_aggregate([known]))
        self.assertIn(known, report["backlog"])
        self.assertEqual(report["undeclared"], [])
        state, _ = cc.judge(report)
        self.assertEqual(state, cc.PASS)

    def test_the_backlog_cannot_grow_by_itself(self):
        """Nothing may move a country into the backlog at run time.

        Acknowledging a country is a code change with a reviewer. If a runtime
        path could add one, the backlog would be a snooze button rather than a
        declaration, and the guard above would be worth nothing.
        """
        before = dict(cc.ACKNOWLEDGED_BACKLOG)
        cc.classify_all(fetch=_stub_aggregate(["Wakanda", "Atlantis"]))
        self.assertEqual(cc.ACKNOWLEDGED_BACKLOG, before)

    def test_no_country_is_both_classified_and_acknowledged(self):
        """A country in both lists means one of them was never cleaned up."""
        overlap = set(cc.REGISTER) & set(cc.ACKNOWLEDGED_BACKLOG)
        self.assertEqual(overlap, set(),
                         f"classified AND still on the backlog: {sorted(overlap)}")

    def test_every_backlog_entry_says_what_is_outstanding(self):
        """"Not done yet" is not a declaration; it is a shrug.

        The backlog is the register's only concession, and the thing that stops
        it becoming a permanent exemption is that each entry states what is
        actually unresolved — so the next session can pick one up without
        re-deriving the question.
        """
        for name, entry in cc.ACKNOWLEDGED_BACKLOG.items():
            self.assertIsInstance(entry, tuple, name)
            when, why = entry
            date(*(int(x) for x in when.split("-")))
            self.assertGreater(len(why), 30,
                               f"{name}: backlog entry does not say what is outstanding")

    def test_unassessed_is_not_reported_as_no_regime(self):
        """The two look identical on any dashboard that only counts findings.

        "We checked and this country has no disclosure requirement" and "nobody
        looked" are opposite states, and conflating them is how a register turns
        an absence of work into a fact about the world.
        """
        rec = cc.entry_for("Wakanda")
        self.assertEqual(rec["class"], cc.UNASSESSED)
        self.assertEqual(rec["state"], cc.UNKNOWN)
        self.assertNotEqual(rec["class"], cc.NO_REGIME)

    def test_a_scope_that_could_not_be_read_is_unknown_not_an_empty_world(self):
        def boom(url):
            raise OSError("host unreachable")
        report = cc.classify_all(fetch=boom)
        self.assertEqual(report["scope_state"], cc.UNKNOWN)
        state, _ = cc.judge(report)
        self.assertEqual(state, cc.UNKNOWN)

    def test_an_empty_country_list_is_a_fault_not_a_clean_sweep(self):
        report = cc.classify_all(fetch=lambda url: json.dumps({"map_countries": []}))
        self.assertEqual(report["scope_state"], cc.UNKNOWN)


class ClassificationsExpire(unittest.TestCase):
    """A standing finding nobody revisits is a stale claim with an exemption.

    Statutes are amended and ministries start and stop publishing series. The
    register is allowed to be six months behind the world; it is not allowed to
    be silently any older than that.
    """

    def test_an_old_assessment_reports_unknown_rather_than_its_old_class(self):
        stale = (date.today()
                 - timedelta(days=cc.MAX_ASSESSMENT_AGE_DAYS + 1)).isoformat()
        saved = dict(cc.REGISTER)
        try:
            cc.REGISTER["Testland"] = {
                "class": cc.NO_REGIME,
                "regime": "checked the labour code and the statistics office and "
                          "found no mass dismissal notification duty of any kind",
                "authority": None, "threshold": None,
                "aggregate": "none published", "assessed": stale,
                "cite": "https://example.invalid/labour-code"}
            rec = cc.entry_for("Testland")
            self.assertEqual(rec["state"], cc.UNKNOWN)
            self.assertIn("UNVERIFIED", rec["detail"])
        finally:
            cc.REGISTER.clear()
            cc.REGISTER.update(saved)

    def test_an_expired_entry_makes_the_whole_report_unknown(self):
        stale = (date.today()
                 - timedelta(days=cc.MAX_ASSESSMENT_AGE_DAYS + 1)).isoformat()
        saved = dict(cc.REGISTER)
        try:
            cc.REGISTER["Testland"] = {
                "class": cc.NO_REGIME,
                "regime": "checked the labour code and the statistics office and "
                          "found no mass dismissal notification duty of any kind",
                "authority": None, "threshold": None,
                "aggregate": "none published", "assessed": stale,
                "cite": "https://example.invalid/labour-code"}
            report = cc.classify_all(fetch=_stub_aggregate(["Testland"]))
            self.assertIn("Testland", report["expired"])
            state, detail = cc.judge(report)
            self.assertEqual(state, cc.UNKNOWN)
            self.assertIn("Testland", detail)
        finally:
            cc.REGISTER.clear()
            cc.REGISTER.update(saved)

    def test_no_committed_entry_is_already_expired(self):
        """The register as shipped must be inside its own ceiling."""
        today = date.today()
        for name, entry in cc.REGISTER.items():
            age = (today - date(*(int(x) for x in entry["assessed"].split("-")))).days
            self.assertLessEqual(
                age, cc.MAX_ASSESSMENT_AGE_DAYS,
                f"{name} was assessed {age} days ago and is already stale as shipped")


class TheRegisterRefusesToAverage(unittest.TestCase):
    """No worldwide percentage, in the file or in the verdict.

    A single number over a register whose own coverage is the denominator would
    be quoted as a coverage figure, and it would be wrong in the direction that
    flatters. The absence is the design.
    """

    def test_the_report_carries_no_worldwide_rate(self):
        report = cc.classify_all(fetch=_stub_aggregate(sorted(cc.REGISTER)))
        blob = json.dumps(report).lower()
        for banned in ("worldwide_recall", "global_recall", "overall_recall",
                       "worldwide_coverage", "global_coverage_pct"):
            self.assertNotIn(banned, blob, f"{banned} must not exist — see the docstring")

    def test_the_verdict_reports_counts_of_countries_not_a_percentage(self):
        report = cc.classify_all(fetch=_stub_aggregate(sorted(cc.REGISTER)))
        state, detail = cc.judge(report)
        self.assertNotIn("%", detail,
                         "the verdict must not carry a percentage — it would be quoted "
                         "as coverage and its denominator is this register, not the world")


class TheVerdictAgreesWithItself(unittest.TestCase):
    """"1 have no disclosure regime at all" is what the first green run printed.

    NO_REGIME is the count most likely to sit at exactly one for a long time —
    it is the hardest claim to earn — so this is the tally whose agreement
    breaks most often and matters most.
    """

    def _verdict(self, tallies, scope=70):
        return cc.judge({
            "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope_state": cc.MEASURED, "undeclared": [], "expired": [],
            "tallies": tallies, "countries_in_scope": scope})[1]

    def test_a_single_country_takes_a_singular_verb(self):
        detail = self._verdict({cc.NO_REGIME: 1, cc.REGIME_WITH_AGGREGATE: 1,
                                cc.REGIME_NO_AGGREGATE: 1})
        self.assertIn("1 has no disclosure regime at all", detail)
        self.assertIn("1 publishes a countable total", detail)
        self.assertIn("1 has a regime that publishes no aggregate", detail)

    def test_several_countries_take_a_plural_verb(self):
        detail = self._verdict({cc.NO_REGIME: 3, cc.REGIME_WITH_AGGREGATE: 10,
                                cc.REGIME_NO_AGGREGATE: 22})
        self.assertIn("3 have no disclosure regime at all", detail)
        self.assertIn("10 publish a countable total", detail)

    def test_zero_takes_a_plural_verb(self):
        self.assertIn("0 have no disclosure regime at all",
                      self._verdict({cc.NO_REGIME: 0}))


class NotACountryIsNotAFinding(unittest.TestCase):
    """"Multiple countries" is a scope bucket, not a place.

    Classifying it NO_REGIME would read as a finding about a real jurisdiction.
    It is excluded by name, and the exclusion is counted so it cannot be mistaken
    for something nobody looked at.
    """

    def test_multiple_countries_is_excluded_and_counted(self):
        report = cc.classify_all(
            fetch=_stub_aggregate(["Multiple countries"] + sorted(cc.REGISTER)))
        self.assertNotIn("Multiple countries", report["countries"])
        self.assertTrue(any(e["name"] == "Multiple countries"
                            for e in report["excluded_not_a_country"]))
        # ...and it does not make the report UNKNOWN, because it is not owed a
        # classification.
        self.assertNotIn("Multiple countries", report["unassessed"])


class VocabularyDuplicatesAreReportedNotAbsorbed(unittest.TestCase):
    """Two spellings of one country is a real defect in the stored vocabulary.

    Mapping them to one entry is right — the Republic of Korea's statute does
    not change with the spelling used to store a row — but doing it silently
    would make this register the thing that hides the defect.
    """

    def test_an_alias_is_surfaced_in_the_report(self):
        names = ["Korea", "South Korea"]
        report = cc.classify_all(fetch=_stub_aggregate(names))
        dups = {d["stored"] for d in report["vocabulary_duplicates"]}
        self.assertIn("Korea", dups)

    def test_an_alias_does_not_double_count_the_country(self):
        report = cc.classify_all(fetch=_stub_aggregate(["Korea", "South Korea"]))
        self.assertEqual(report["countries_in_scope"], 1,
                         "one country stored under two spellings is one country")


class FreshnessOfTheRegisterItself(unittest.TestCase):
    """A register that stopped being recomputed is UNKNOWN, not a pass.

    The same failure rolling_recall guards: the number stops being computed and
    nobody notices, because nothing goes red when a job simply stops.
    """

    def test_no_report_at_all_is_unknown(self):
        state, detail = cc.judge(None)
        self.assertEqual(state, cc.UNKNOWN)
        self.assertIn("UNESTABLISHED", detail)

    def test_a_stale_report_is_unknown(self):
        old = (datetime.now(timezone.utc)
               - timedelta(days=cc.MAX_MEASUREMENT_AGE_DAYS + 2))
        state, detail = cc.judge({
            "measured_at": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope_state": cc.MEASURED, "undeclared": [], "expired": [],
            "tallies": {}, "countries_in_scope": 0})
        self.assertEqual(state, cc.UNKNOWN)
        self.assertIn("UNVERIFIED", detail)

    def test_an_unreadable_timestamp_is_unknown(self):
        state, _ = cc.judge({"measured_at": "last tuesday"})
        self.assertEqual(state, cc.UNKNOWN)

    def test_a_committed_measurement_matches_the_register(self):
        doc = cc.load_measurement()
        if doc is None:
            self.skipTest("no register measurement committed yet")
        if doc.get("scope_state") != cc.MEASURED:
            self.skipTest("committed run could not read scope")
        for name, rec in (doc.get("countries") or {}).items():
            if rec.get("class") == cc.UNASSESSED:
                continue
            self.assertIn(name, cc.REGISTER,
                          f"{name} is classified in the committed file but has no "
                          f"entry in the register — the file was hand-edited")


class WiredIntoTheOneRegistry(unittest.TestCase):
    """The invariant is registered, and it actually reads the register.

    `test_dedup_live.InvariantCoverage` mutation-tests this claim: it blinds the
    invariant to an unconditional PASS and demands this case redden. So these
    assertions exercise `run()` rather than describe it.
    """

    def _invariant(self):
        import data_integrity
        found = [i for i in data_integrity.INVARIANTS
                 if i.key == "country_coverage_fresh"]
        self.assertEqual(len(found), 1,
                         "country_coverage_fresh is not registered exactly once")
        return data_integrity, found[0]

    def test_a_missing_register_reports_unknown_not_a_pass(self):
        data_integrity, inv = self._invariant()
        result = type(inv)(measurement_path=Path("/nonexistent/cc.json")).run(None)
        self.assertEqual(result.state, data_integrity.UNKNOWN)
        self.assertTrue(getattr(result, "pending", False),
                        "a register that has never been written is PENDING, so a fresh "
                        "checkout does not redden a push — but it is still UNKNOWN")

    def test_a_stale_register_reports_unknown(self):
        data_integrity, inv = self._invariant()
        old = (datetime.now(timezone.utc)
               - timedelta(days=cc.MAX_MEASUREMENT_AGE_DAYS + 2))
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"measured_at": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "scope_state": cc.MEASURED, "undeclared": [], "expired": [],
                       "tallies": {}, "countries_in_scope": 3}, fh)
            path = fh.name
        result = type(inv)(measurement_path=Path(path)).run(None)
        self.assertEqual(result.state, data_integrity.UNKNOWN)

    def test_an_unclassified_country_reddens_the_invariant(self):
        data_integrity, inv = self._invariant()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"measured_at": datetime.now(timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "scope_state": cc.MEASURED, "undeclared": ["Wakanda"],
                       "expired": [], "tallies": {}, "countries_in_scope": 1}, fh)
            path = fh.name
        result = type(inv)(measurement_path=Path(path)).run(None)
        self.assertEqual(result.state, data_integrity.UNKNOWN)
        self.assertIn("Wakanda", result.detail)


if __name__ == "__main__":
    unittest.main()
