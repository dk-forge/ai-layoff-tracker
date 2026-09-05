"""The nine editions (three tiers, three sections) composed from live payloads
on 2026-09-06, and the three things that did not hold.

Every headline figure in all nine reproduced from the /aggregate, /talent/v1
and /wp/v2/posts responses they were fed (worldwide = jobs - announced_jobs,
the regions sum to it, the top five match the leaders, the category counts
match their own filtered calls). Three sentences and one gate did not:

  1. THE TALENT SECTION HAS NEVER ARCHIVED. alt_edition_public_safe refuses
     any query key not on its allowlist, and the talent links carry `since`,
     `until`, `pillar` and `funding`, none of which was listed. 2.20.169
     unlinked the off-host sources and said the talent section archived
     again; on the live composition it reached this rule next and was refused
     on all three tiers, to error_log, exactly as before.
  2. "This week the worldwide total is one employer's story" on the DAILY of
     2026-09-05/06 (Jaguar Land Rover, 73% of the announced-inclusive total).
     The dominance block is composed for every tier and both of its
     interpretation sentences were typed as a week.
  3. "The 3 newest of 12 posts we published on September 5 and 6, 2026" when
     the blog published 43 that day. The query stops at 12 and the caption
     printed the ceiling as the count.

Each fix is proven by mutation: revert it and the test under it reddens.
Without php on PATH the cases SKIP, which is UNKNOWN and not a pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_digest_scope_rules import (PHP, compose, layoff_fixture,  # noqa: E402
                                     talent_fixture)

PLUGIN = os.path.join(HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker")
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
ARCHIVE = os.path.join(PLUGIN, "includes", "digest-archive.php")
GATE_HARNESS = os.path.join(HERE, "fixtures", "edition_archive_harness.php")


def archive_copy(html, text):
    """The archive's own path: the publishable copy, then the unchanged gate,
    exactly as alt_edition_capture does it."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump({"rewrite": {"s": {"html": html, "text": text}}}, handle)
        handle.close()
        run = subprocess.run([PHP, GATE_HARNESS, SUBSCRIBE, ARCHIVE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1500]}")
    return json.loads(run.stdout)["rewrite"]["s"]


def talent_with_categories(**over):
    """The talent fixture with all three category calls answered, which is
    what puts the `pillar` and `funding` links into the section. The counts
    are arbitrary; the links are the subject."""
    fixture = talent_fixture(**over)
    fixture["talent_cat_pillar_leadership_change"] = {"total": 7}
    fixture["talent_cat_funding_1"] = {"total": 3}
    fixture["talent_cat_pillar_rewards_comp"] = {"total": 2}
    return fixture


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheTalentSectionPassesTheArchiveGate(unittest.TestCase):

    def test_the_composed_talent_section_is_publishable_on_every_tier(self):
        for freq, window in (("daily", ("2026-08-15", "2026-08-16")),
                             ("weekly", ("2026-08-10", "2026-08-16")),
                             ("monthly", ("2026-08-01", "2026-08-16"))):
            out = compose(talent_with_categories(
                **{"from": window[0], "to": window[1], "freq": freq}))
            self.assertNotIn("null", out, f"{freq}: the talent section did not compose")
            copy = archive_copy(out["html"], out["text"])
            self.assertTrue(copy["gate"]["ok"],
                            f"{freq}: the archive refused the talent section: "
                            f"{copy['gate']['rule']}")

    def test_the_section_really_carries_the_keys_the_gate_used_to_refuse(self):
        """A pass over a section with no such link would prove nothing."""
        out = compose(talent_with_categories())
        for key in ("since=", "until=", "pillar=", "funding="):
            self.assertIn(key, out["html"], f"no link carries {key}")

    def test_a_key_the_composer_never_mints_is_still_refused(self):
        """The allowlist grew by the four keys the talent URL builder mints,
        not by a wildcard. `direction` is a real talent filter that no link in
        this email carries, and it stays refused until a composer needs it."""
        link = ("https://asktherecruiter.com/blog/talent-intelligence-tracker/"
                "?since=2026-08-10&until=2026-08-16&direction=hiring")
        copy = archive_copy(f'<p><a href="{link}">x</a></p>', link)
        self.assertFalse(copy["gate"]["ok"])
        self.assertEqual(copy["gate"]["rule"],
                         "a link carries a query key that is not on the allowlist")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheDominanceSentenceNamesTheWindowNotAWeek(unittest.TestCase):

    def _daily_dominated(self):
        fixture = layoff_fixture(**{"from": "2026-09-05", "to": "2026-09-06",
                                    "freq": "daily"})
        fixture["layoff"]["leaders"][0]["job_count"] = 9000
        return compose(fixture)["text"]

    def test_a_daily_edition_does_not_call_two_days_a_week(self):
        text = self._daily_dominated()
        self.assertIn("one employer's story rather than a broad shift across many", text)
        self.assertNotIn("This week", text)
        self.assertNotIn("this week", text.split("AI-attributed cuts")[0])

    def test_the_sentence_carries_the_window_it_describes(self):
        text = self._daily_dominated()
        self.assertIn("Over September 5-6, 2026, the worldwide total is one "
                      "employer's story", text)

    def test_the_ai_driver_sentences_name_the_window_too(self):
        fixture = layoff_fixture(**{"from": "2026-09-05", "to": "2026-09-06",
                                    "freq": "daily"})
        fixture["layoff"]["leaders"][0]["ai_explicit"] = True
        fixture["layoff"]["totals"]["ai_verified_jobs"] = 4320
        fixture["layoff"]["totals"]["ai_verified_entries"] = 1
        text = compose(fixture)["text"]
        self.assertIn("account for all of the AI-attributed cuts in that window", text)
        self.assertIn("Over September 5-6, 2026, the AI attribution came from "
                      "a single employer", text)
        self.assertNotIn("week's AI-attributed", text)
        self.assertNotIn("This week's", text)


def articles_fixture(n_posts):
    posts = []
    for i in range(n_posts):
        posts.append({
            "title": f"Post number {i + 1}",
            "link": f"https://asktherecruiter.com/blog/post-{i + 1}/",
            "excerpt": "An opening sentence that stands on its own.",
            "content": "<p>" + ("word " * 440) + "</p>",
            "date": f"2026-09-05 {(23 - i) % 24:02d}:00:00",
        })
    return {"compose": "articles", "from": "2026-09-05", "to": "2026-09-06",
            "freq": "daily", "posts": posts}


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheArticlesCaptionCountsPastTheFetchCeiling(unittest.TestCase):

    def test_forty_three_posts_are_not_called_twelve(self):
        out = compose(articles_fixture(43))
        for part in (out["html"], out["text"]):
            self.assertIn("The 3 newest of 43 posts we published", part)
            self.assertNotIn("of 12 posts", part)

    def test_still_only_three_are_printed(self):
        text = compose(articles_fixture(43))["text"]
        self.assertIn("Post number 1", text)
        self.assertIn("Post number 3", text)
        self.assertNotIn("Post number 4", text)

    def test_below_the_ceiling_the_count_is_unchanged(self):
        out = compose(articles_fixture(4))
        self.assertIn("The 3 newest of 4 posts we published", out["text"])

    def test_exactly_the_ceiling_is_the_ceiling(self):
        """12 posts really is 12. The fix must not add one or say 'at least'."""
        out = compose(articles_fixture(12))
        self.assertIn("The 3 newest of 12 posts we published", out["text"])

    def test_the_harness_ceiling_is_real(self):
        """The stub used to return every fixture post regardless of the
        ceiling, which is why this defect was invisible to every earlier
        articles test. A stub kinder than get_posts() proves nothing."""
        harness = open(os.path.join(HERE, "fixtures", "digest_compose_harness.php"),
                       encoding="utf-8").read()
        self.assertIn("$args['numberposts']", harness)
        self.assertIn("'ids'", harness)


if __name__ == "__main__":
    unittest.main()
