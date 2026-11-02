"""One emoji leads each digest subject (owner approval 2026-11-02, "Use these
emojis"): layoff tracker U+1F4C9, talent tracker U+1F680, the blog articles
(the AskTheRecruiter newsletter) U+1F3AF. Exactly one, at the start, chosen by
the section the subject leads with."""
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

import digest_layout  # noqa: E402
import digest_send  # noqa: E402
from test_digest_sender import _payload  # noqa: E402

LAYOFF, TALENT, ARTICLES = "\U0001F4C9", "\U0001F680", "\U0001F3AF"


def part(name):
    return (name, "<h2>x</h2>", "x", "", ("", False))


class SubjectEmoji(unittest.TestCase):

    def test_emoji_per_section(self):
        self.assertEqual(digest_layout.subject_emoji([part("layoff")]), LAYOFF)
        self.assertEqual(digest_layout.subject_emoji([part("talent")]), TALENT)
        self.assertEqual(digest_layout.subject_emoji([part("articles")]), ARTICLES)

    def test_first_section_wins_and_unknown_is_empty(self):
        self.assertEqual(digest_layout.subject_emoji([part("talent"), part("layoff")]), TALENT)
        self.assertEqual(digest_layout.subject_emoji([part("follows")]), "")
        self.assertEqual(digest_layout.subject_emoji([]), "")

    def test_prefix_is_applied_once(self):
        self.assertEqual(digest_layout.with_subject_emoji("12 cuts", [part("layoff")]),
                         LAYOFF + " 12 cuts")
        self.assertEqual(digest_layout.with_subject_emoji(LAYOFF + " 12 cuts", [part("layoff")]),
                         LAYOFF + " 12 cuts")

    def test_built_message_leads_with_the_layoff_emoji(self):
        payload = _payload()
        msg = digest_send.build_message(payload, payload["recipients"][0],
                                        "Trackers <d@asktherecruiter.com>",
                                        "info@asktherecruiter.com")
        self.assertTrue(msg.subject.startswith(LAYOFF + " "), msg.subject)
        self.assertEqual(sum(msg.subject.count(e) for e in (LAYOFF, TALENT, ARTICLES)), 1)


if __name__ == "__main__":
    unittest.main()
