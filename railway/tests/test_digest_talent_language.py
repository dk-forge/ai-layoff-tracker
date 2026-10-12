"""Talent digest: a language tag and an English gist on non-English items
(owner-approved 2026-10-12).

The talent tracker now STORES a headline language (ISO 639-1, decided by a
free local detector, NULL when it is not confident) and whether its own stored
summary is English. The digest prints the tag only from that stored code, never
from its own guess, and prints the summary as the English gist only when the
tracker says the summary is English. An English or untagged row is unchanged.
Without php these SKIP, which is UNKNOWN, not a pass.
"""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
from test_digest_talent_activity import PHP  # noqa: E402
from test_digest_talent_redesign import compose, daily, row  # noqa: E402

PT_HEAD = "Carraro Logística tem novas vagas para motoristas em São Paulo"
PT_SUMMARY = "Carraro Logistica is hiring truck drivers in Sao Paulo and Parana."


def pt_row(**over):
    r = row("Carraro", 400, "BR", head=PT_HEAD)
    r.update(language="pt", language_confidence=0.9, summary_language="en",
             summary=PT_SUMMARY)
    r.update(over)
    return r


def rows(*extra):
    base = daily()
    base["talent_q"] = {"rows": list(extra) + base["talent_q"]["rows"]}
    return base


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class LanguageTag(unittest.TestCase):
    def test_non_english_row_carries_tag_and_gist(self):
        out = compose(rows(pt_row()))
        for body in (out["text"], out["html"]):
            self.assertIn("in Portuguese", body)
            self.assertIn("English summary: " + PT_SUMMARY, body)

    def test_no_gist_unless_the_summary_is_english(self):
        out = compose(rows(pt_row(summary_language=None)))
        self.assertIn("in Portuguese", out["text"])
        self.assertNotIn("English summary:", out["text"])
        out = compose(rows(pt_row(summary_language="pt")))
        self.assertNotIn("English summary:", out["text"])

    def test_untagged_and_english_rows_are_unchanged(self):
        for over in ({"language": None}, {"language": "en"}, {"language": "PT!"}):
            out = compose(rows(pt_row(**over)))
            self.assertNotIn("in Portuguese", out["text"])
            self.assertNotIn("English summary:", out["text"])
            self.assertNotRegex(out["text"], r"\bin [A-Z]{2}\b")

    def test_unknown_code_is_named_by_its_code_not_guessed(self):
        out = compose(rows(pt_row(language="sw")))
        self.assertIn("language: sw", out["text"])

    def test_compact_lists_carry_the_tag_too(self):
        lead = row("Lider", 0, "US", head="Lider SA nomeia novo CEO")
        lead.update(language="pt", summary_language="en",
                    summary="Lider SA named a new chief executive.")
        base = daily()
        base["talent_q_pillar_leadership_change"]["rows"].insert(0, lead)
        out = compose(base)
        self.assertIn("in Portuguese", out["text"])
        self.assertIn("English summary: Lider SA named a new chief executive.", out["text"])


if __name__ == "__main__":
    unittest.main()
