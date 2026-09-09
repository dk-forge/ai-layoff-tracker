"""Guards for dedupe_llm.bucket_key -- the candidate-generation company key.

WHY THIS FILE EXISTS, AND WHICH HALF OF IT MATTERS.

The deep scan buckets rows by company before it compares anything, so a name
variant never produced a bad merge: it produced NO COMPARISON, at zero cost,
with nothing to observe. Live on 2026-09-09, "Volkswagen" and "Volkswagen (VW)"
each reported 50,000 cuts a day apart and sat in different buckets; a third
report arrived as "Grupo Volkswagen"; a fourth, in the same event, WAS caught
by the same job. Widening the bucket makes those pairs candidates.

THE KEEP-APART HALF IS THE ONE THAT MATTERS, and it is not symmetric with the
should-meet half. Under-collapsing leaves a duplicate row on the tracker, which
is visible, countable and reversible. Over-collapsing offers a false pair to a
model that, if it agrees, causes /merge-events to HARD-DELETE a row -- and the
headline movement guard cannot see a deletion. So every pair below that must
stay apart is a real pair read out of the live corpus, not an invention, and a
normaliser that gets greedier must fail here first.

Both corpora were read from the live data on 2026-09-09: the 42,719 distinct
company names /companies returns, plus a paced 2,200-row sample of the
news/8K/press_release/erm rows the dedup job actually fetches.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.setdefault("openai", SimpleNamespace())
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _requests_stub import install as _install_requests  # noqa: E402
_install_requests()

import dedupe_llm as d  # noqa: E402


#: Pairs that MUST land in one bucket. Each is a real name-variation class the
#: corpus contains, named by the class it stands for.
SHOULD_MEET = [
    # The live finding: a parenthetical ticker/alias, and a Spanish-language
    # corporate-group prefix, on the same 2026 Volkswagen event.
    ("Volkswagen", "Volkswagen (VW)", "parenthetical ticker"),
    ("Volkswagen", "Grupo Volkswagen", "Spanish group prefix"),
    ("Volkswagen (VW)", "Grupo Volkswagen", "both variants at once"),
    # Parenthetical alias where the head is a word rather than an initialism.
    ("Meta", "Meta (Facebook)", "parenthetical brand alias"),
    ("Alphabet", "Alphabet (Google)", "parenthetical brand alias"),
    ("Flex Ltd.", "Flex (Flex Global Operations)", "parenthetical division"),
    ("Sony", "Sony (Game Division)", "parenthetical division"),
    ("Royal Bank of Scotland", "Royal Bank of Scotland (RBS)", "parenthetical initialism"),
    ("Advanced Micro Devices, Inc.", "Advanced Micro Devices (AMD)", "parenthetical initialism"),
    # "Group" in the languages we actually ingest. English `group` was already
    # stripped; the others were not, which made this an English-only rule.
    ("Compass Group Canada", "Groupe Compass Canada", "French group prefix"),
    ("Antolin", "Grupo Antolin", "Spanish group prefix"),
    ("Olx Group", "Grupa OLX", "Polish group prefix"),
    ("STI Group", "Gruppo Sti", "Italian group prefix"),
    ("WAZ", "WAZ-Gruppe", "German group suffix"),
    ("Telegraaf Media Groep", "Telegraaf Media", "Dutch group suffix"),
    # Legal forms, plain and dotted, in the languages the corpus carries.
    ("Relacom", "Relacom AB", "Swedish AB"),
    ("Nortura", "Nortura AS", "Norwegian AS"),
    ("Bombardier Transportation", "Bombardier Transportation GmbH", "German GmbH"),
    ("Fugro", "Fugro NV", "Dutch NV"),
    ("Kemira", "Kemira Oyj", "Finnish Oyj"),
    ("Delphi France", "Delphi France SAS", "French SAS"),
    ("MAN", "MAN SE", "European SE"),
    ("Rolls-Royce", "Rolls-Royce Oy Ab", "two stacked Nordic forms"),
    ("Stellantis", "Stellantis N.V.", "dotted N.V."),
    ("Natuzzi", "Natuzzi S.p.A.", "dotted S.p.A."),
    ("COOP Denmark", "COOP Denmark A/S", "slashed A/S"),
    ("Amerplast", "Amerplast Sp. z o.o.", "dotted Polish sp. z o.o."),
]

#: Pairs that MUST NOT share a bucket. Every one is drawn from the live corpus
#: or from the class the corpus proves exists, with the reason it is here.
KEEP_APART = [
    # The task's own examples: a qualified subsidiary is a different employer.
    ("Volkswagen", "Volkswagen Financial Services",
     "a captive finance arm is not the carmaker"),
    ("Delta", "Delta Dental", "different employers that share a first word"),
    ("Delta", "Delta Apparel", "same, and both are in the corpus"),
    # The one over-collapse the corpus actually contains. Merck & Co (Rahway)
    # and Merck KGaA (Darmstadt) are separate companies, so `kgaa` must never
    # join the stripped-suffix list.
    ("Merck & Co., Inc.", "Merck KGaA",
     "two legally separate companies called Merck"),
    # 82 of 82 trailing "Spa" names in the corpus are resorts, so `spa` is not
    # a legal form here even though S.p.A. is.
    ("Rancho Valencia Resort & Spa", "Rancho Valencia Resort",
     "an undotted Spa is a resort's amenity, not an Italian S.p.A."),
    ("Golden Door Spa", "Golden Door", "same"),
    # All five trailing "Zoo" names are zoos, not Polish z o.o.
    ("Santa Barbara Zoo", "Santa Barbara", "a Zoo is not sp. z o.o."),
    # An all-caps initialism head needs its expansion to stay distinguishable.
    ("CTS (Coyne TextileServices)", "CTS Corporation",
     "two different companies both handled CTS"),
    ("BD (Becton Dickinson)", "BD (C.R. Bard Inc.)",
     "a two-letter head cannot carry identity on its own"),
    # A geographic subsidiary is a different employer and a different event.
    ("Volkswagen", "Volkswagen Slovakia", "national subsidiary"),
    ("Volkswagen", "Volkswagen Nutzfahrzeuge", "a separate brand/division"),
    ("Bristol-Myers Squibb", "Bristol-Myers Squibb Canada", "national subsidiary"),
    # A parenthetical is not always an alias; when the head keeps its own
    # words, the two names still differ where they should.
    ("Delta Homes (Ireland)", "Delta", "the head, not the parenthetical, is the name"),
    ("Czech Airlines (CSA)", "Cooper-Standart automotive (CSA)",
     "two firms share an initialism, and it is inside the parenthesis"),
    # Trailing legal-form stripping must not eat a real word.
    ("SAS Institute", "SAS", "a leading SAS is a name, not a French legal form"),
    ("AB InBev", "InBev", "a leading AB is a name, not a Swedish legal form"),
]

# NOT FIXED HERE, ON PURPOSE, and recorded so the next reader does not "find"
# it again: norm_company strips `ag` and `sa` ANYWHERE in a name, not only as a
# suffix, so "Ag Processing Inc." keys as `processing` and "AG Management
# Group" as `management`. That predates this change. Measured over the 42,719
# names, it collides with nothing -- and tightening it to a suffix would LOSE
# two correct merges the corpus contains ("Czech Airlines (CSA)" with "CSA
# (Czech Airlines)", and the Swissport SA rows with the Swissport USA ones).
# The data refused the tightening, so it was not made.


class ShouldMeetTest(unittest.TestCase):
    def test_variants_of_one_employer_share_a_bucket(self):
        for left, right, why in SHOULD_MEET:
            with self.subTest(pair=(left, right), why=why):
                self.assertEqual(d.bucket_key(left), d.bucket_key(right),
                                 f"{left!r} and {right!r} must be candidates ({why})")

    def test_the_live_volkswagen_rows_become_one_bucket(self):
        # 179106 / 179133 / 176988 as they read on the live tracker.
        keys = {d.bucket_key(n) for n in
                ("Volkswagen", "Volkswagen (VW)", "Grupo Volkswagen")}
        self.assertEqual(len(keys), 1)
        self.assertEqual(keys.pop(), "volkswagen")


class KeepApartTest(unittest.TestCase):
    """The half that matters. A false merge deletes a row; nothing sees that."""

    def test_different_employers_never_share_a_bucket(self):
        for left, right, why in KEEP_APART:
            with self.subTest(pair=(left, right), why=why):
                self.assertNotEqual(d.bucket_key(left), d.bucket_key(right),
                                    f"{left!r} and {right!r} must stay apart ({why})")

    def test_rejected_tokens_stay_rejected(self):
        # These are refusals the corpus produced, not preferences. Adding any
        # of them to the stripped-suffix list breaks a KEEP_APART pair above,
        # so pin them here too, where the reason is legible.
        for token in ("spa", "zoo", "kgaa", "konzern", "koncern"):
            self.assertNotIn(token, d._LEGAL_SUFFIX_TOKENS)
            self.assertNotIn(token, d._GROUP_WORDS)


class NeverSubtractsTest(unittest.TestCase):
    """A widening must not remove a row from the candidate set."""

    def test_a_name_that_is_only_a_legal_form_keeps_its_key(self):
        # "SAS" the airline exists in the corpus as a bare name. If the suffix
        # strip emptied it, candidate_clusters (which skips a blank key) would
        # silently drop every SAS row -- a widening that narrows.
        self.assertEqual(d.bucket_key("SAS"), "sas")
        self.assertEqual(d.bucket_key("Groupe"), d.norm_company("Groupe"))

    def test_blank_and_junk_are_handled(self):
        self.assertEqual(d.bucket_key(""), "")
        self.assertEqual(d.bucket_key(None), "")

    def test_every_key_the_old_normaliser_had_still_exists(self):
        for name in [pair for triple in SHOULD_MEET + KEEP_APART for pair in triple[:2]]:
            with self.subTest(name=name):
                if d.norm_company(name):
                    self.assertTrue(d.bucket_key(name),
                                    f"{name!r} lost its bucket entirely")


class BucketingOnlyProposesTest(unittest.TestCase):
    """Sharing a bucket buys a pair the right to be COMPARED, nothing more.

    This is the assumption the widening rests on, so it is asserted against
    the real candidate_clusters rather than trusted from a reading.
    """

    @staticmethod
    def _row(rid, name, jobs, day, country="Germany", source_type="news"):
        return {"id": rid, "company_name": name, "job_count": jobs,
                "layoff_date": day, "country": country,
                "source_type": source_type, "source_url": "", "excerpt": ""}

    def test_a_shared_bucket_alone_does_not_make_a_cluster(self):
        # Same bucket, same country, but the counts are nowhere near each
        # other: the ratio gate keeps them out of the model's sight.
        rows = [self._row(1, "Volkswagen", 50000, "2026-09-03"),
                self._row(2, "Volkswagen (VW)", 12, "2026-09-04")]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_a_country_conflict_still_blocks_a_shared_bucket(self):
        rows = [self._row(1, "Volkswagen", 50000, "2026-09-03", country="Germany"),
                self._row(2, "Volkswagen (VW)", 50000, "2026-09-04", country="Spain")]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_federal_rif_rows_are_still_excluded(self):
        rows = [self._row(1, "Volkswagen", 50000, "2026-09-03", source_type="federal_rif"),
                self._row(2, "Volkswagen (VW)", 50000, "2026-09-04", source_type="federal_rif")]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_the_window_still_applies_to_a_shared_bucket(self):
        # Merely-similar counts (80%) keep the tight 120-day window, so a pair
        # a year apart is not offered even though the names now agree.
        rows = [self._row(1, "Volkswagen", 4000, "2025-01-03"),
                self._row(2, "Volkswagen (VW)", 5000, "2026-09-04")]
        self.assertEqual(d.candidate_clusters(rows), [])

    def test_the_pair_the_fix_is_for_does_become_a_candidate(self):
        rows = [self._row(179106, "Volkswagen", 50000, "2026-09-03"),
                self._row(179133, "Volkswagen (VW)", 50000, "2026-09-04")]
        clusters = d.candidate_clusters(rows)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(sorted(r["id"] for r in clusters[0]), [179106, 179133])


if __name__ == "__main__":
    unittest.main()
