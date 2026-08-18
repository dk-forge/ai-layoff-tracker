"""Render every block of the digest with a count of exactly one.

WHY THIS FILE EXISTS, AND WHY IT IS A TEST RATHER THAN A PROOFREAD.

The owner read the delivered digest of 2026-08-18 and sent back three lines:

    1 of the 5 companies listed ... link to an entry page
    1 more sit below the lines shown
    Open the tracker on this week

The first two are the same defect: a count interpolated in front of a
hard-coded plural. His note about it is the reason this is a test and not a
one-line patch, because he named the cost rather than the typo. A product
whose whole pitch is that it can be cited cannot read as machine output, and a
disagreeing verb is the cheapest possible tell that nobody read the thing
before it went out.

The class is bigger than the three lines. alt_digest_jobs_phrase() had existed
since the first send, carrying a comment saying "1 jobs" is exactly the line a
sceptical reader looks at hardest, and it governed ONE noun. Every other count
in subscribe.php built its own phrase. So the fix is a helper
(alt_digest_count / alt_digest_verb) and this file, which drives all three
composers over fixtures where every count is one and fails on any "1 <plural>"
in either part.

WHY A FIXTURE OF ONES AND NOT THE LIVE DATA. A window holding exactly one
entry, one company, one country, one industry and one source is rare and
completely ordinary: it is what a daily digest looks like on a quiet Sunday.
It is also the only input that exercises every branch at once, and nobody was
ever going to hit it by hand.

Without php on PATH these SKIP, which is not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")


def _tuple(label, all_jobs, verified_jobs):
    """The column order /aggregate really returns. Copied, never invented."""
    return [label, all_jobs, 0, None, verified_jobs, 0]


def compose(fixture):
    """Run one composer through the PHP harness and return both parts."""
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(fixture, handle)
        handle.close()
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1200]}")
    out = json.loads(run.stdout)
    if out.get("null"):
        raise AssertionError("the composer returned nothing for this fixture")
    return out


# ---------------------------------------------------------------------------
# The sweep
#
# "1 " followed by a word ending in s. Deliberately blunt, because the defect
# is blunt and a curated noun list would have to be extended by whoever adds
# the next noun, which is exactly the person who will forget.
#
# The allowlist holds the words that legitimately follow a bare "1" and end in
# s. Every one of them is a word this file has actually seen in a render, and
# a new entry needs a reason written beside it rather than a quiet append.
# ---------------------------------------------------------------------------
ONE_PLURAL = re.compile(r"\b1 ([a-z]+s)\b")
NOT_PLURAL = {
    "is",       # "1 is on an entry with no country recorded" - the fix itself
    "was",      # "Of those, 1 was attributed to AI by the employer"
    "as", "has", "its", "this", "plus", "less",
}

# The verb agreements the owner named by hand, asserted by phrase as well as by
# sweep. The sweep catches nouns; a verb after a clause ("1 of the 5 companies
# listed for 17 to 18 August 2026 link to ...") is far enough from the digit
# that no regex on "1 " will ever see it.
BAD_PHRASES = (
    " link to an entry page",
    " more sit below",
    " are announcements, marked below, and sit ",
    " are on entries with ",
    "Open the tracker on this week",
)


def assert_agrees(case, part, where):
    for match in ONE_PLURAL.finditer(part):
        word = match.group(1)
        if word in NOT_PLURAL:
            continue
        case.fail(f"{where}: '1 {word}' - a count of one governing a plural. "
                  f"Build the phrase with alt_digest_count/alt_digest_verb.")
    for phrase in BAD_PHRASES:
        case.assertNotIn(phrase, part,
                         f"{where}: '{phrase.strip()}' disagrees with a count "
                         f"of one, or is the wording the owner rejected")


# ---------------------------------------------------------------------------
# Fixtures where every count is one
# ---------------------------------------------------------------------------

def layoff_of_one(**over):
    data = {
        "from": "2026-08-17", "to": "2026-08-18", "compose": "layoff",
        "layoff": {
            "totals": {"jobs": 1, "entries": 1, "announced_jobs": 0,
                       "announced_entries": 0, "ai_verified_jobs": 1,
                       "ai_verified_entries": 1, "companies": 1},
            "leaders": [{"company_name": "Solo Corp", "job_count": 1,
                         "layoff_date": "2026-08-18", "ai_explicit": True,
                         "location": "", "permalink": "", "announced": False}],
            "top_countries": [_tuple("United States", 1, 1)],
            "top_industries": [_tuple("Technology", 1, 1), _tuple("Energy", 0, 0)],
            "source_types": [_tuple("warn", 1, 1)],
        },
        "ytd": {"totals": {"jobs": 1, "announced_jobs": 0, "ai_verified_jobs": 1},
                "top_countries": [_tuple("United States", 1, 1)]},
    }
    data.update(over)
    return data


def layoff_with_singular_remainders():
    """The two lines the owner actually quoted, reproduced.

    Two leaders, exactly one of them carrying a permalink, so the entry-page
    claim covers one company; and a country block whose ranked rows leave a
    remainder of exactly one job below the cut and exactly one unplaced.
    """
    data = layoff_of_one()
    data["layoff"]["totals"] = {
        "jobs": 11, "entries": 3, "announced_jobs": 2, "announced_entries": 1,
        "ai_verified_jobs": 1, "ai_verified_entries": 1, "companies": 3,
    }
    data["layoff"]["leaders"] = [
        {"company_name": "Linked Co", "job_count": 5,
         "layoff_date": "2026-08-18", "ai_explicit": False, "location": "",
         "permalink": "https://asktherecruiter.com/blog/layoff/linked/",
         "announced": False},
        {"company_name": "Bulk Filed Co", "job_count": 3,
         "layoff_date": "2026-08-17", "ai_explicit": False, "location": "",
         "permalink": "", "announced": True},
    ]
    # Verified headline is 9. Six ranked countries carrying 8 between them, so
    # the sixth falls below the printed five and leaves a remainder of exactly
    # one, and one job carries no country at all. Both halves of the
    # reconciliation note therefore say "1", which is the line he quoted.
    data["layoff"]["top_countries"] = [
        _tuple("United States", 3, 3), _tuple("Brazil", 1, 1),
        _tuple("Canada", 1, 1), _tuple("France", 1, 1),
        _tuple("Japan", 1, 1), _tuple("Kenya", 1, 1),
    ]
    return data


def talent_of_one():
    return {
        "from": "2026-08-17", "to": "2026-08-18", "compose": "talent",
        "talent": {"total": 1, "companies": 1, "verified": 1, "countries": 1,
                   "rows": [{"company": "Solo Corp", "headline": "opens a site",
                             "published_date": "2026-08-18", "headcount": 1}]},
        "talent_ytd": {"total": 1},
    }


def articles_of_one():
    return {
        "from": "2026-08-17", "to": "2026-08-18", "compose": "articles",
        "posts": [{
            "title": "One post, one minute",
            "link": "https://asktherecruiter.com/blog/one-post/",
            "excerpt": "A WARN notice is a legal filing. It is also a signal.",
            "date": "2026-08-18 09:00:00",
            "content": " ".join(["word"] * 120),
        }],
    }


@unittest.skipUnless(PHP, "php is not on PATH, so the composers cannot run")
class ACountOfOneNeverGovernsAPlural(unittest.TestCase):

    def test_the_layoff_section(self):
        out = compose(layoff_of_one())
        assert_agrees(self, out["text"], "layoff text part")
        assert_agrees(self, out["html"], "layoff html part")

    def test_the_layoff_section_remainder_lines(self):
        """"1 more sit below the lines shown", verbatim from his inbox."""
        out = compose(layoff_with_singular_remainders())
        assert_agrees(self, out["text"], "layoff text part")
        assert_agrees(self, out["html"], "layoff html part")
        self.assertIn("1 more sits below the lines shown", out["text"])
        self.assertIn("1 is on an entry with no country recorded", out["text"])
        self.assertIn("links to an entry page", out["text"])
        self.assertIn("The other one arrived through a bulk filing import",
                      out["text"])

    def test_the_talent_section(self):
        out = compose(talent_of_one())
        assert_agrees(self, out["text"], "talent text part")
        assert_agrees(self, out["html"], "talent html part")

    def test_the_articles_section(self):
        out = compose(articles_of_one())
        assert_agrees(self, out["text"], "articles text part")
        assert_agrees(self, out["html"], "articles html part")

    def test_the_headline_label_agrees_with_the_headline_figure(self):
        """The kicker over a stat of 1 reads "Verified job cut", not "cuts".

        It is a label, so it was tempting to leave it as a category name. It
        sits four pixels above the number it labels, which makes it a caption,
        and a caption that disagrees with its own figure is the thing this
        whole file is about.
        """
        out = compose(layoff_of_one())
        self.assertIn("Verified job cut<", out["html"])
        self.assertIn("1 verified job cut, 17 to 18 August 2026", out["text"])


@unittest.skipUnless(PHP, "php is not on PATH, so the composers cannot run")
class TheTrackerLinkSaysWhereItGoes(unittest.TestCase):
    """"Open the tracker on this week" read awkwardly, and read as nothing
    once the line was quoted on its own. The link carries a specific window
    and a specific date basis, so the label names the window."""

    def test_the_link_text_names_the_window(self):
        out = compose(layoff_of_one())
        self.assertIn("Open the tracker for 17 to 18 August 2026", out["text"])
        self.assertIn("Open the tracker for 17 to 18 August 2026", out["html"])
        self.assertNotIn("Open the tracker on this week", out["text"])


@unittest.skipUnless(PHP, "php is not on PATH, so the composers cannot run")
class TheCitationIsAHeadingLikeEveryOtherBlock(unittest.TestCase):
    """WHAT "CITE THIS IS BROKEN" TURNED OUT TO BE.

    The label used digest_layout's `kicker` variant, which is documented there
    as the eyebrow over a headline FIGURE: 11px, uppercase, grey, and pinned
    tight to what follows because it is meant to sit above a 34px number. Over
    13px grey note text it rendered SMALLER than the thing it labelled, in the
    same grey, with none of the top space an h3 gets, two lines above the rule
    that starts the next tracker. It read as a stray fragment rather than a
    heading, and a screen reader moving by heading skipped the citation.

    The citation string also had the URL concatenated into the same paragraph,
    so a reference meant to be selected and pasted had to be separated from a
    sentence first.
    """

    def test_it_is_a_real_heading(self):
        out = compose(layoff_of_one())
        self.assertIn("<h3>Cite this</h3>", out["html"])
        self.assertNotIn('<p data-alt="kicker">Cite this</p>', out["html"])

    def test_the_url_is_its_own_paragraph_and_still_not_a_link(self):
        out = compose(layoff_of_one())
        url = "https://asktherecruiter.com/blog/ai-layoff-tracker/"
        self.assertIn(f'<p data-alt="note">{url}</p>', out["html"])
        # Still text, never an anchor: a citation is a string somebody pastes,
        # and a counted URL in a published story records the counter instead of
        # our address. See the docblock on alt_digest_cite_note.
        self.assertNotIn(f'<a href="{url}"', out["html"])


if __name__ == "__main__":
    unittest.main()
