"""THE /CONTACT INTRO ON THE LIVE SITE MUST FOLLOW THE COPY IN THIS REPO.

WHY THIS FILE EXISTS. An FTP deploy cannot create or edit a WordPress page, so
the plugin does it from a hook on the first request after a version bump.
alt_ensure_contact_page() returns early when the page already exists, which is
correct: it must not clobber the page every request. The refresh path was a
separate one-shot migration keyed on a bare flag, `alt_contact_intro_v2`. That
flag was set on the live site the day the v2 copy landed, so when the wording
moved on the migration was already closed and the page kept the old paragraph.
Nothing reported it. The repo said one thing and the reader saw another, and
the only way to notice was to open the page.

That is a key defect, not a copy defect: the option answered "has a migration
ever run here" when the question is "which revision of our copy is on the
page". So the option is keyed by revision now, and this file holds the shape.

WHAT IS PINNED HERE:

  * the migration reads a revision, not a boolean, and compares with >=, so a
    site that skipped a revision still catches up;
  * every superseded intro has a phrase in alt_contact_intro_shipped_phrases(),
    and the revision counts them. This is what forces the bump: adding new copy
    without retiring the old phrase, or retiring it without bumping, fails here
    rather than silently freezing the live page again;
  * the guard still protects a hand-edit. The migration only overwrites content
    that is verbatim one of OUR shipped intros;
  * no shipped phrase appears in the CURRENT intro. A phrase that matches the
    copy it is supposed to supersede makes the guard match its own output, and
    an owner edit made after that revision would be recognised as ours.

THE SUBJECT LIST IS HELD HERE TOO, for the same reason it was rewritten: the
options are what a person reads before deciding whether this form is for them.
They are alphabetical with the catch-all last, and the catch-all is the only
one allowed to be vague.

AND THE HINT UNDER IT. A label has to be short enough to read in a dropdown, so
it can name the thing without saying who should pick it or what we will need
from them. Every subject carries one sentence that does, it is rendered
server-side for the default option so it is right with JavaScript off, and the
map is keyed by the same keys as the list, because a hint that describes the
wrong option is worse than no hint.
"""

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
CONTACT = (PLUGIN / "includes" / "contact.php").read_text(encoding="utf-8")


def _revision():
    m = re.search(r"define\('ALT_CONTACT_INTRO_REV',\s*(\d+)\)", CONTACT)
    assert m, "ALT_CONTACT_INTRO_REV is gone; the migration is keyed on something else"
    return int(m.group(1))


def _shipped_phrases():
    m = re.search(
        r"function alt_contact_intro_shipped_phrases\(\)\s*\{(.*?)\n\}", CONTACT, re.S
    )
    assert m, "alt_contact_intro_shipped_phrases() is gone"
    return re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))


def _current_intro():
    m = re.search(r'function alt_contact_intro_html\(\)\s*\{\s*return "(.*?)";', CONTACT, re.S)
    assert m, "alt_contact_intro_html() no longer returns one string literal"
    return m.group(1)


def _topics():
    m = re.search(r"function alt_contact_topics\(\)\s*\{(.*?)\n\}", CONTACT, re.S)
    assert m, "alt_contact_topics() is gone"
    return re.findall(r"'([a-z_]+)'\s*=>\s*'((?:[^'\\]|\\.)*)'", m.group(1))


class TheIntroMigrationIsKeyedByRevision(unittest.TestCase):
    def test_it_reads_a_revision_and_not_a_bare_flag(self):
        body = re.search(
            r"function alt_contact_intro_migrate\(\)\s*\{(.*?)\n\}", CONTACT, re.S
        )
        self.assertIsNotNone(body, "alt_contact_intro_migrate() is gone")
        body = body.group(1)
        self.assertIn(
            "(int) get_option('alt_contact_intro_rev') >= ALT_CONTACT_INTRO_REV",
            body,
            "the migration must compare a stored revision with >=, so a site that "
            "missed a revision still catches up",
        )
        self.assertNotIn(
            "alt_contact_intro_v2",
            CONTACT,
            "the one-shot flag is what froze the live intro; it must not come back",
        )

    def test_it_writes_the_revision_back(self):
        self.assertIn(
            "update_option('alt_contact_intro_rev', ALT_CONTACT_INTRO_REV, false)",
            CONTACT,
            "a migration that does not record its revision runs on every request",
        )

    def test_the_revision_counts_the_superseded_intros(self):
        phrases = _shipped_phrases()
        self.assertEqual(
            _revision(),
            len(phrases) + 1,
            "every superseded intro needs a phrase in "
            "alt_contact_intro_shipped_phrases() and a revision to go with it. "
            "Change the copy in alt_contact_intro_html(), add the sentence you "
            "replaced to that list, and bump ALT_CONTACT_INTRO_REV.",
        )

    def test_no_shipped_phrase_matches_the_current_copy(self):
        intro = _current_intro()
        for phrase in _shipped_phrases():
            self.assertNotIn(
                phrase,
                intro,
                "'%s' matches the intro it is meant to supersede, so the guard "
                "would recognise its own output as replaceable" % phrase,
            )

    def test_the_guard_still_protects_a_hand_edit(self):
        body = re.search(
            r"function alt_contact_intro_migrate\(\)\s*\{(.*?)\n\}", CONTACT, re.S
        ).group(1)
        self.assertIn("alt_contact_intro_shipped_phrases()", body)
        self.assertIn("strpos((string) $p->post_content", body)


class TheSubjectListReadsLikeSomeoneWroteIt(unittest.TestCase):
    def test_every_label_is_title_case(self):
        small = {"a", "an", "the", "or", "in", "of", "at", "to", "with", "and"}
        for key, label in _topics():
            words = label.split()
            for i, word in enumerate(words):
                if i and word.lower() in small:
                    continue
                self.assertTrue(
                    word[:1].isupper(),
                    "subject '%s' is not title case: %r" % (key, label),
                )

    def test_the_catch_all_is_last_and_the_rest_are_alphabetical(self):
        labels = [label for _, label in _topics()]
        self.assertEqual(
            labels[-1],
            "Something Else",
            "the catch-all is only correct once every other line has been ruled "
            "out, so it goes last",
        )
        body = labels[:-1]
        self.assertEqual(
            body,
            sorted(body),
            "a person scans this list for their own words, so it is alphabetical",
        )

    def test_the_tip_key_still_feeds_the_tips_ledger(self):
        self.assertIn("'tip'", CONTACT)
        self.assertIn("$topic_key === 'tip'", CONTACT)
        keys = [key for key, _ in _topics()]
        for required in ("tip", "correction", "press", "api", "partnership", "other"):
            self.assertIn(
                required,
                keys,
                "the key is what the mail handler and the tips ledger read; "
                "renaming one silently changes behaviour",
            )

    def test_only_the_catch_all_may_be_vague(self):
        for key, label in _topics():
            if key == "other":
                continue
            self.assertGreaterEqual(
                len(label.split()),
                3,
                "subject '%s' reads as a category name rather than as the thing "
                "a person is bringing us: %r" % (key, label),
            )




class EverySubjectExplainsItself(unittest.TestCase):
    def _hints(self):
        m = re.search(r"function alt_contact_topic_hints\(\)\s*\{(.*?)\n\}", CONTACT, re.S)
        assert m, "alt_contact_topic_hints() is gone"
        return dict(
            re.findall(r"'([a-z_]+)'\s*=>\s*'((?:[^'\\]|\\.)*)'", m.group(1))
        )

    def test_every_subject_has_one(self):
        hints = self._hints()
        for key, label in _topics():
            self.assertIn(
                key,
                hints,
                "subject %r has no hint, so a reader has only the label to go on"
                % label,
            )

    def test_no_hint_belongs_to_a_subject_that_is_gone(self):
        keys = {key for key, _ in _topics()}
        for key in self._hints():
            self.assertIn(
                key, keys, "hint %r describes a subject that no longer exists" % key
            )

    def test_a_hint_is_a_sentence_and_not_a_restated_label(self):
        labels = {key: label for key, label in _topics()}
        for key, hint in self._hints().items():
            self.assertGreaterEqual(
                len(hint.split()),
                8,
                "hint for %r is too short to add anything: %r" % (key, hint),
            )
            self.assertTrue(
                hint.rstrip().endswith("."),
                "hint for %r is not written as a sentence: %r" % (key, hint),
            )
            self.assertNotEqual(
                hint.rstrip(". ").lower(),
                labels[key].lower(),
                "hint for %r just repeats the label" % key,
            )

    def test_the_fallback_is_empty_and_not_another_subjects_hint(self):
        body = re.search(
            r"function alt_contact_topic_hint\(\$key\)\s*\{(.*?)\n\}", CONTACT, re.S
        )
        self.assertIsNotNone(body, "alt_contact_topic_hint() is gone")
        self.assertIn("''", body.group(1))

    def test_it_is_rendered_before_any_script_runs(self):
        self.assertIn(
            "alt_contact_topic_hint($first)",
            CONTACT,
            "the hint for the default option must be rendered server-side, or "
            "the form opens with a blank line under the subject",
        )
        self.assertIn('id="alt-c-topic-hint"', CONTACT)
        self.assertIn('aria-describedby="alt-c-topic-hint"', CONTACT)

    def test_the_resume_subject_stops_asking_for_a_news_report(self):
        self.assertIn(
            "alt-app-note",
            CONTACT,
            "the resume tool is the one subject that is not about the tracker; "
            "leaving the source-link wording up tells the person they picked "
            "the wrong option",
        )
        self.assertIn("Link to the page (optional)", CONTACT)

if __name__ == "__main__":
    unittest.main()
