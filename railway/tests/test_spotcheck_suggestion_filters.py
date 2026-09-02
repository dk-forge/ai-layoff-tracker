"""The spot-check may not mint a label, repeat itself, or mail a reason that
says nothing.

THE MAIL THESE GUARD
--------------------
On 2026-09-02 the daily classification spot-check (run 33666038578) mailed the
owner "24 label relabel(s) HELD for review, not applied". Nothing was written:
the 5,000-job bound held every one of them. But the mail itself was wrong in
three ways, and each is a gate here:

  * VOCABULARY. Seven of the nine distinct industry suggestions named a label
    that does not exist: "Public Administration", "Courier & Delivery",
    "Cinema & Movie", "Airline" (twice), "Banking" (twice), "Agrochemicals".
    alt_industry_rules() in api.php is a closed set of nineteen labels whose
    own comment says an automated classifier must never mint one. Every one
    of those is either a no-op after alt_normalize_industry() or, written raw,
    a near-duplicate in the public filter dropdown.
  * REPETITION. The model returned 84 flags for 29 sampled rows. One row was
    listed four times and another three, and every copy went through the
    confirmation call, the hold path and the mail.
  * EVIDENCE. Most reasons restated the row: "The excerpt mentions 'United
    Parcel Service, better known as UPS', suggesting multiple countries might
    be involved." A Romanian interior ministry was proposed as "Multiple
    countries" because its excerpt says "(Romania)".

A fourth defect surfaced while reading the code: confirmation was a set of
ids, and a sampled row carries an industry flag AND a country flag, so
"agree" on either confirmed both.

The fixture below is the actual 24, transcribed from the mail. The gates run
BEFORE the confirmation call, so nothing here spends a model call, and every
drop is counted in the run summary. Offline throughout.
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import daily_classification_spotcheck as sc
try:
    from tests.test_spotcheck_relabel_bounds import Harness
except ImportError:  # run as a bare file from tests/
    from test_spotcheck_relabel_bounds import Harness

# --- the 2026-09-02 sample (the size-selected half), as /query returns it ---
ERM = ("Internal restructuring at {c} ({k}): {n:,} announced job losses. Recorded "
       "by the European Restructuring Monitor (Eurofound), factsheet 1.")
ROWS = [
    {"id": 111762, "company_name": "Ministerul Administratiei si Internelor",
     "industry": "Government & Nonprofit", "country": "Romania", "job_count": 50000,
     "excerpt": ERM.format(c="Ministerul Administratiei si Internelor", k="Romania", n=50000)},
    {"id": 70667, "company_name": "United Parcel Service",
     "industry": "Logistics & Transport", "country": "United States", "job_count": 48000,
     "excerpt": "The United Parcel Service, better known as UPS, has announced that in the "
                "first nine months of 2025 it has cut 48,000 people from its workforce."},
    {"id": 113529, "company_name": "General Motors", "industry": "Manufacturing",
     "country": "Multiple countries", "job_count": 47000,
     "excerpt": ERM.format(c="General Motors", k="Multiple countries", n=47000)},
    {"id": 64351, "company_name": "Cinemaworld", "industry": "Media & Entertainment",
     "country": "Multiple countries", "job_count": 45000,
     "excerpt": ERM.format(c="Cinemaworld", k="Multiple countries", n=45000)},
    {"id": 176402, "company_name": "American Airlines Group Inc.",
     "industry": "Airlines & Travel", "country": "United States", "job_count": 39000,
     "excerpt": "In total, nearly 39,000 team members have opted for an early retirement."},
    {"id": 64195, "company_name": "Lufthansa", "industry": "Airlines & Travel",
     "country": "Multiple countries", "job_count": 39000,
     "excerpt": ERM.format(c="Lufthansa", k="Multiple countries", n=39000)},
    {"id": 70199, "company_name": "UBS", "industry": "Finance & Insurance",
     "country": "Multiple countries", "job_count": 36000,
     "excerpt": "Up to 36,000 employees might face layoffs as a result of the recent "
                "merger of the Swiss banks Credit Suisse and UBS."},
    {"id": 114335, "company_name": "Citigroup", "industry": "Finance & Insurance",
     "country": "Multiple countries", "job_count": 52000,
     "excerpt": ERM.format(c="Citigroup", k="Multiple countries", n=52000)},
    {"id": 176988, "company_name": "Grupo Volkswagen", "industry": "Automotive",
     "country": "Germany", "job_count": 60000,
     "excerpt": "El automóvil alemán se tambalea y obliga a despedir a más de 60.000 "
                "empleados por la crisis del sector."},
]
NAMES = {r["id"]: r["company_name"] for r in ROWS}
CURRENT = {r["id"]: {"industry": r["industry"], "country": r["country"]} for r in ROWS}


def _f(rid, field, cur, sug, why):
    return {"id": rid, "field": field, "current": cur, "suggested": sug, "why": why}


_VW = ("The excerpt mentions 'El automóvil alemán se tambalea y obliga a despedir a más "
       "de 60.000 empleados por la crisis del sector El Grupo Volkswagen, la entidad más "
       "damnificada, valora otras 50.000 salidas más en caso de que s', suggesting {}")
_UBS = ("The excerpt mentions 'Up to 36,000 employees might face layoffs as a result of "
        "the recent merger of the Swiss banks Credit Suisse and UBS', suggesting {}")
_ERM = "The excerpt mentions 'Internal restructuring at {} (Multiple countries)', suggesting {}"

# The 24 HELD lines of the 2026-09-02 mail, in the order they were mailed.
TONIGHT = [
    _f(111762, "country", "Romania", "Multiple countries",
       "The excerpt mentions 'Ministerul Administratiei si Internelor (Romania)', "
       "suggesting multiple countries might be involved."),
    _f(70667, "country", "United States", "Multiple countries",
       "The excerpt mentions 'The United Parcel Service, better known as UPS', "
       "suggesting multiple countries might be involved."),
    _f(113529, "country", "Multiple countries", "United States",
       _ERM.format("General Motors", "USA as the primary country.")),
    _f(64351, "country", "Multiple countries", "United States",
       _ERM.format("Cinemaworld", "USA as the primary country.")),
    _f(176402, "country", "United States", "Multiple countries",
       "The excerpt mentions 'American Airlines Group Inc.', suggesting multiple "
       "countries might be involved."),
    _f(64195, "country", "Multiple countries", "Germany",
       _ERM.format("Lufthansa", "Germany as the primary country.")),
    _f(70199, "country", "Multiple countries", "Switzerland",
       _UBS.format("Switzerland as the primary country.")),
    _f(114335, "country", "Multiple countries", "United States",
       _ERM.format("Citigroup", "USA as the primary country.")),
    _f(176988, "country", "Germany", "Multiple countries",
       _VW.format("multiple countries might be involved.")),
    _f(111762, "industry", "Government & Nonprofit", "Public Administration",
       "The excerpt mentions 'Ministerul Administratiei si Internelor', suggesting "
       "Public Administration as the primary industry."),
    _f(70667, "industry", "Logistics & Transport", "Courier & Delivery",
       "The excerpt mentions 'The United Parcel Service, better known as UPS', "
       "suggesting Courier & Delivery as the primary industry."),
    _f(113529, "industry", "Manufacturing", "Automotive",
       _ERM.format("General Motors", "Automotive as the primary industry.")),
    _f(64351, "industry", "Media & Entertainment", "Cinema & Movie",
       _ERM.format("Cinemaworld", "Cinema & Movie as the primary industry.")),
    _f(176402, "industry", "Airlines & Travel", "Airline",
       "The excerpt mentions 'American Airlines Group Inc.', suggesting Airline as "
       "the primary industry."),
    _f(64195, "industry", "Airlines & Travel", "Airline",
       _ERM.format("Lufthansa", "Airline as the primary industry.")),
    _f(70199, "industry", "Finance & Insurance", "Banking",
       _UBS.format("Banking as the primary industry.")),
    _f(114335, "industry", "Finance & Insurance", "Banking",
       _ERM.format("Citigroup", "Banking as the primary industry.")),
    _f(176988, "industry", "Automotive", "Manufacturing",
       _VW.format("Manufacturing as the primary industry.")),
    _f(178002, "industry", "Manufacturing", "Agrochemicals",
       "The excerpt specifies 'Cheminova (Denmark)', suggesting Agrochemicals as the "
       "primary industry."),
]
TONIGHT += [TONIGHT[17], TONIGHT[18], TONIGHT[17], TONIGHT[18], TONIGHT[17]]
assert len(TONIGHT) == 24

MINTED = ["Public Administration", "Courier & Delivery", "Cinema & Movie",
          "Airline", "Banking", "Agrochemicals"]


class VocabularyGate(unittest.TestCase):
    """A classifier never mints a label. A suggestion is either a label the
    field can hold, spelled the way it is stored, or it is discarded."""

    def test_every_minted_label_of_the_mail_is_discarded(self):
        for label in MINTED:
            self.assertEqual(sc.canonical_industry(label), "",
                             f'"{label}" is not in alt_industry_vocabulary() and must '
                             "not be proposed as though it were")

    def test_the_vocabulary_is_the_mirror_industry_backfill_uses(self):
        from extractor import INDUSTRY_VOCABULARY
        self.assertEqual(sc.industry_vocabulary(), tuple(INDUSTRY_VOCABULARY),
                         "two Python copies of the closed set is how they drift apart")
        for label in INDUSTRY_VOCABULARY:
            self.assertEqual(sc.canonical_industry(label), label)

    def test_a_vocabulary_label_is_rewritten_to_the_stored_spelling(self):
        self.assertEqual(sc.canonical_industry("automotive"), "Automotive")
        self.assertEqual(sc.canonical_industry("  finance &  insurance "), "Finance & Insurance")

    def test_a_synonym_is_not_folded_it_is_discarded(self):
        # alt_normalize_industry would fold "Banking" onto "Finance & Insurance";
        # a proposal to relabel a Finance & Insurance row "Banking" is a synonym,
        # not a mismatch, and folding it here would manufacture a no-op edit.
        self.assertEqual(sc.canonical_industry("Banking"), "")

    def test_country_accepts_real_countries_and_the_one_multi_label(self):
        self.assertEqual(sc.canonical_country("Switzerland"), "Switzerland")
        self.assertEqual(sc.canonical_country("USA"), "United States")
        self.assertEqual(sc.canonical_country("multiple countries"), "Multiple countries")

    def test_country_discards_regions_states_and_prose(self):
        for value in ("Europe", "EMEA", "Bavaria", "North America", "Global", "Romania and Bulgaria"):
            self.assertEqual(sc.canonical_country(value), "",
                             f'"{value}" is not a value the country field can hold')

    def test_off_vocabulary_flags_are_split_out_with_the_kept_ones_rewritten(self):
        flags = [_f(1, "industry", "Retail & E-commerce", "Courier & Delivery", "x"),
                 _f(2, "industry", "Manufacturing", "automotive", "x"),
                 _f(3, "country", "Germany", "usa", "x"),
                 _f(4, "country", "Germany", "Bavaria", "x")]
        kept, dropped = sc.drop_off_vocabulary_flags(flags)
        self.assertEqual([f["id"] for f in dropped], [1, 4])
        self.assertEqual([f["suggested"] for f in kept], ["Automotive", "United States"])

    def test_tonight_eight_of_nineteen_unique_suggestions_are_minted(self):
        unique, _ = sc.dedupe_flags(TONIGHT)
        kept, dropped = sc.drop_off_vocabulary_flags(unique)
        self.assertEqual(len(dropped), 8)
        self.assertEqual(sorted({f["suggested"] for f in dropped}), sorted(MINTED))
        self.assertEqual(len(kept), 11, "every country suggestion was in the vocabulary")


class RepeatGate(unittest.TestCase):
    def test_tonight_24_lines_are_19_proposals(self):
        kept, repeats = sc.dedupe_flags(TONIGHT)
        self.assertEqual((len(kept), len(repeats)), (19, 5))
        vw = [f for f in kept if f["id"] == 176988 and f["field"] == "industry"]
        self.assertEqual(len(vw), 1, "Grupo Volkswagen was mailed four times")

    def test_a_different_suggestion_for_the_same_row_is_not_a_repeat(self):
        flags = [_f(1, "industry", "Retail & E-commerce", "Technology", "a"),
                 _f(1, "industry", "Retail & E-commerce", "Manufacturing", "b")]
        kept, repeats = sc.dedupe_flags(flags)
        self.assertEqual(len(kept), 2, "two disagreeing answers are information")
        self.assertEqual(repeats, [])

    def test_the_first_copy_is_the_one_kept(self):
        a = _f(1, "industry", "Retail", "Technology", "first")
        b = _f(1, "industry", "Retail", "technology", "second")
        kept, _ = sc.dedupe_flags([a, b])
        self.assertEqual(kept[0]["why"], "first")


class EvidenceGate(unittest.TestCase):
    """A reason that names nothing beyond the row's own name and labels is not
    a reason, and does not reach the owner's inbox."""

    def _one(self, rid, field):
        return next(f for f in TONIGHT if f["id"] == rid and f["field"] == field)

    def test_the_romanian_ministry_is_not_multiple_countries_because_it_is_romanian(self):
        f = self._one(111762, "country")
        self.assertEqual(sc.reason_evidence(f, NAMES[111762]), [])

    def test_an_acronym_of_the_company_name_is_the_company_name(self):
        f = self._one(70667, "country")     # "...better known as UPS"
        self.assertEqual(sc.reason_evidence(f, NAMES[70667]), [])

    def test_the_erm_importers_own_boilerplate_is_not_evidence(self):
        # "Internal restructuring at General Motors (Multiple countries)" is the
        # template erm_import.py writes around the stored label.
        for rid in (113529, 64351, 114335, 64195):
            f = self._one(rid, "country")
            self.assertEqual(sc.reason_evidence(f, NAMES[rid]), [], NAMES[rid])

    def test_a_reader_alias_of_the_proposed_label_is_the_label(self):
        f = _f(176402, "country", "United States", "Multiple countries",
               "the excerpt mentions 'American Airlines Group Inc.'")
        self.assertEqual(sc.reason_evidence(f, NAMES[176402]), [])
        g = _f(64195, "country", "Multiple countries", "Germany", "it is a German company")
        self.assertEqual(sc.reason_evidence(g, NAMES[64195]), [],
                         "'German' merely restates the proposed label")

    def test_a_reason_that_cites_something_survives(self):
        f = self._one(70199, "country")
        self.assertIn("merger", sc.reason_evidence(f, NAMES[70199]))
        g = self._one(176988, "industry")
        self.assertTrue(sc.reason_evidence(g, NAMES[176988]),
                        "a Spanish reason keeps its words: the tokeniser is Unicode-aware")

    def test_tonight_eight_of_the_eleven_in_vocabulary_proposals_are_evidence_free(self):
        unique, _ = sc.dedupe_flags(TONIGHT)
        in_vocab, _ = sc.drop_off_vocabulary_flags(unique)
        kept, dropped = sc.drop_evidence_free_flags(in_vocab, NAMES)
        self.assertEqual(len(dropped), 8)
        self.assertEqual(sorted((f["id"], f["field"]) for f in kept),
                         [(70199, "country"), (176988, "country"), (176988, "industry")])


class ConfirmationIsPerField(unittest.TestCase):
    def test_agreeing_with_the_country_flag_does_not_confirm_the_industry_flag(self):
        flags = [_f(1, "country", "Germany", "Multiple countries", "a"),
                 _f(1, "industry", "Automotive", "Manufacturing", "b")]
        got = sc.confirmed_flags(flags, [{"id": 1, "field": "country", "agree": True},
                                         {"id": 1, "field": "industry", "agree": False}])
        self.assertEqual([f["field"] for f in got], ["country"])

    def test_a_reply_without_a_field_is_ambiguous_when_the_row_has_two_flags(self):
        flags = [_f(1, "country", "Germany", "Multiple countries", "a"),
                 _f(1, "industry", "Automotive", "Manufacturing", "b")]
        self.assertEqual(sc.confirmed_flags(flags, [{"id": 1, "agree": True}]), [],
                         "an ambiguous agreement is not agreement")

    def test_a_reply_without_a_field_still_confirms_a_single_flag(self):
        flags = [_f(1, "country", "Germany", "Multiple countries", "a")]
        self.assertEqual(len(sc.confirmed_flags(flags, [{"id": 1, "agree": True}])), 1)


class TonightEndToEnd(unittest.TestCase):
    """The real main() over the real sample and the real 24: what reaches the
    confirmation call, the owner and /edit."""

    class _Harness(Harness):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.prompts = []

        def ask_model(self, prompt):
            self.prompts.append(prompt)
            if "auditing" in prompt:
                return {"flags": self.flags}
            # Agree with everything it was shown, per (id, field).
            import json as _json
            shown = _json.loads(prompt[prompt.rindex("\n\n") + 2:])
            return {"confirm": [{"id": f["id"], "field": f["field"], "agree": True}
                                for f in shown]}

    def _run(self):
        h = self._Harness(newest=[], biggest=ROWS, flags=list(TONIGHT))
        code = h.run()
        self.assertEqual(code, 0)
        return h

    def test_nothing_is_written(self):
        h = self._run()
        self.assertEqual(h.edited_ids, set(), "the 5,000-job bound is untouched")

    def test_the_confirmation_call_never_sees_a_minted_label_or_a_repeat(self):
        h = self._run()
        confirm = h.prompts[1]
        for label in MINTED:
            self.assertNotIn(f'"{label}"', confirm)
        self.assertEqual(confirm.count('"id": 176988'), 2,
                         "VW once per field, not four times")

    def test_the_mail_holds_three_and_names_each_once(self):
        h = self._run()
        self.assertEqual(len(h.alert_payloads), 1)
        p = h.alert_payloads[0]
        self.assertTrue(p["subject"].startswith("3 label relabel(s) HELD"), p["subject"])
        self.assertEqual(p["body"].count("HELD row 176988"), 2, "country and industry, once each")
        self.assertEqual(p["body"].count("HELD row 70199"), 1)
        for label in MINTED:
            self.assertNotIn(label, p["body"])
        self.assertNotIn("111762", p["body"], "the Romanian ministry does not reach the inbox")
        self.assertNotIn("178002", p["body"])
        self.assertEqual(p["dedupe_key"], "relabel-hold:176988.70199")

    def test_every_drop_is_counted_in_the_run_summary(self):
        h = self._run()
        out = h.output
        self.assertIn("Discarded 5 repeated flag(s)", out)
        self.assertIn("Discarded 8 off-vocabulary flag(s)", out)
        self.assertIn("Discarded 8 evidence-free flag(s)", out)
        self.assertIn('"Public Administration"', out, "a discarded suggestion is named, not vanished")


if __name__ == "__main__":
    unittest.main()
