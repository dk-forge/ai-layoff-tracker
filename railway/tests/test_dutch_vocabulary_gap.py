"""Dutch layoff headlines use the infinitive, and we only asked the participle.

MEASURED, 2026-11-15 (weekly benchmark miss, two weeks running): the Dutch
cabinet's 25,000-job central-government cut ran on 2026-10-26 in NOS, NU, de
Volkskrant, NRC, Trouw, FD and AD, every outlet on the trusted list. Our Dutch
vocabulary was "massaontslag", "collectief ontslag", "banen geschrapt" and
"reorganisatie banen". Against the NL Google News edition for 24-29 October
those returned ZERO items about the cut; "banen schrappen" and "banen
verdwijnen" each returned it (Trouw, Parkstad Actueel, NRC). The same table
feeds the GDELT BigQuery mirror's title regex and the Google News title
prefilter, so all three paths were blind to the same verb form.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from sources import native_layoff_terms as nlt  # noqa: E402
from sources import google_news_prefilter as pf  # noqa: E402

# Titles as served by the NL edition on 2026-11-15 for that window.
MEASURED = (
    "Kan het kabinet wel 25.000 banen schrappen bij de Rijksoverheid?",
    "Kabinet moet eerst visie op 'slimme overheid' hebben, voordat het 25.000 banen schrapt",
)


class DutchHeadlineVerbs(unittest.TestCase):

    def test_the_nl_edition_asks_the_forms_that_returned_the_story(self):
        qs = " ".join(nlt.google_news_queries("nl"))
        for phrase in ("banen schrappen", "banen verdwijnen"):
            self.assertIn('"%s"' % phrase, qs)

    def test_the_old_phrases_are_kept(self):
        for phrase in ("massaontslag", "collectief ontslag", "banen geschrapt"):
            self.assertIn(phrase, nlt.PHRASES_BY_LANG["nl"])

    def test_the_mirror_title_regex_now_sees_the_trouw_headline(self):
        terms = [t.lower() for t in nlt.mirror_title_terms()]
        title = MEASURED[0].lower()
        self.assertTrue(any(t in title for t in terms), "no mirror term matches")

    def test_the_prefilter_keeps_the_trouw_headline(self):
        ok, why = pf.title_verdict(MEASURED[0], "nl")
        self.assertTrue(ok, why)


if __name__ == "__main__":
    unittest.main()
