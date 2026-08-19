"""THE NEXT-STEP BLOCK MUST NOT GROW INTO AN ADVERT.

WHY THIS FILE EXISTS. The company pages earn their traffic by being a neutral
primary source: a filing, a date, a count and a link, and nothing being sold.
Search Console reads company-name layoff queries at a 33% click-through rate,
and the person behind most of those clicks has just lost a job. So 2.20.115 put
a next-step block on those pages, which is the first thing this plugin has ever
rendered that is not the record.

That block is a standing risk rather than a finished change. Copy blocks drift.
Somebody adds a second link, then a testimonial, then a price, and each edit is
small and defensible on its own. The end state is a data page that reads as
lead generation, and the cost of THAT is not a worse conversion rate. It is a
reporter deciding this source is selling something and citing somebody else.

So the constraints are pinned here as text, on the two templates that carry the
block, and each assertion below names the specific thing that would go wrong.

WHAT IS DELIBERATELY NOT CHECKED HERE. Reading grade, sentence length and the
dash ban already have owners: railway/style_check.py scores both templates as
reader copy, and tests/test_ui_copy_punctuation.py bans the dash characters in
every literal on them. Re-implementing either here would give the project two
definitions of its own style rule, which is the failure mode CLAUDE.md names
about data integrity and it is no better applied to prose.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin" / "ai-layoff-tracker"
COMPANY = PLUGIN / "templates" / "page-company-directory.php"
FACET = PLUGIN / "templates" / "page-facet.php"
MAIN = PLUGIN / "ai-layoff-tracker.php"

# The block's own markup, sliced out of each template so an assertion about
# "the block" cannot accidentally pass on something else on the page.
ASIDE = re.compile(r"<aside class=\"alt-next-step\".*?</aside>", re.S)


def read(path):
    return path.read_text(encoding="utf-8")


def block(path):
    m = ASIDE.search(read(path))
    return m.group(0) if m else ""


def strip_php_comments(src):
    """Comments are rationale, not copy, and they quote the copy verbatim.

    Same distinction style_check.py draws and for the same reason: a checker
    that reads the commentary grades the commentary. This is a deliberately
    small version because the slices here are one block long.
    """
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


class TheBlockExistsOnTheRightSurfaces(unittest.TestCase):

    def test_the_company_page_carries_it(self):
        self.assertTrue(
            block(COMPANY),
            "the company pages are where the converting queries land; without "
            "this block a reader who has just been laid off gets a filing and "
            "no next step")

    def test_the_facet_page_carries_it(self):
        self.assertTrue(block(FACET))

    def test_it_is_an_aside_and_says_so_in_words(self):
        """Visual separation does not survive a screen reader or a text render.

        The tinted ground and the rule above it are two of the three devices
        that mark this as not-the-record. This is the third, and the only one
        that is still there when the CSS is not.
        """
        for path in (COMPANY, FACET):
            html = block(path)
            self.assertIn("Not part of the record", html, str(path))
            self.assertIn('aria-labelledby="alt-next-step-h"', html, str(path))

    def test_the_journalist_pages_are_untouched(self):
        """The citation channel gets nothing of this, on purpose.

        A reporter reaches the tracker, methodology, sources and press pages,
        and those four are the reason anybody cites this site at all.
        """
        for name in ("page-tracker.php", "page-methodology.php",
                     "page-sources.php", "page-press.php"):
            src = read(PLUGIN / "templates" / name)
            self.assertNotIn("alt-next-step", src, name)


class TheDataStaysFirst(unittest.TestCase):

    def test_the_block_renders_after_the_whole_record(self):
        """Position is the load-bearing part of "the data is first".

        Not a nicety: a block of copy above the entries would make the page
        answer a commercial question before it answers the one it was cited
        for. On both templates the record is a loop over events; the block has
        to come after the loop closes AND after the citation box.
        """
        for path, loop_end in ((COMPANY, "</ol>"), (FACET, "</ol>")):
            src = read(path)
            self.assertLess(src.rindex(loop_end), src.index("alt-next-step"),
                            "%s renders the block inside or above the record"
                            % path.name)

    def test_the_block_renders_after_the_citation_box(self):
        for path in (COMPANY, FACET):
            src = read(path)
            self.assertLess(src.index("alt_cite_box_html"),
                            src.index("alt-next-step"), str(path))


class NothingHereLooksCommercialToACrawler(unittest.TestCase):

    def test_no_structured_data_describes_the_offer(self):
        """No Offer, no Product, no Review, no aggregate rating.

        These pages already emit a Dataset node, and that node is the reason a
        machine treats this as a source. A commercial node beside it would
        change what the page IS to anything assessing it.
        """
        banned = ("itemscope", "itemprop", "application/ld+json",
                  "schema.org", "Offer", "AggregateRating", "Product")
        for path in (COMPANY, FACET):
            html = block(path)
            for token in banned:
                self.assertNotIn(token, html, "%s: %s" % (path.name, token))

    def test_every_outbound_link_in_the_block_is_nofollowed(self):
        """Including our own. A data page that passes ranking signal to a
        product it owns is exactly the shape of the thing search engines treat
        as a link scheme, and the point of the block is that it costs the page
        nothing."""
        for path in (COMPANY, FACET):
            html = block(path)
            for tag in re.findall(r"<a\s[^>]*href=\"http[^>]*>", html):
                self.assertIn("nofollow", tag, "%s: %s" % (path.name, tag))


class TheOfferIsQuietAndHonest(unittest.TestCase):

    def test_the_product_is_mentioned_at_most_once_and_only_on_company_pages(self):
        """One line, on the one surface where the reader's intent is personal.

        A facet page reader has not named their own employer, so the intent
        signal is weaker and the page is likelier to be read by somebody
        slicing the data. Those pages get the useful half and none of the
        offer.
        """
        company = strip_php_comments(block(COMPANY))
        # The rendered LINK, not every mention of the helper: the surrounding
        # function_exists() is the FTP-deploy race guard this plugin puts round
        # every optional call, and counting it would make the guard look like a
        # second advert.
        self.assertEqual(company.count("esc_url(alt_next_step_tool_url())"), 1)
        self.assertNotIn("alt_next_step_tool_url", block(FACET))
        self.assertNotIn("resume", block(FACET).lower())

    def test_the_destination_has_exactly_one_definition(self):
        """The tool answers on a sandbox hostname today, and that hostname is
        not a promise. It is defined once so relaunching it is one edit rather
        than a hunt through templates."""
        self.assertIn("function alt_next_step_tool_url", read(MAIN))
        for path in (COMPANY, FACET):
            self.assertNotIn("railway.app", read(path), str(path))

    def test_the_copy_does_not_claim_the_product_is_launched(self):
        company = strip_php_comments(block(COMPANY)).lower()
        self.assertIn("still being tested", company)
        for claim in ("launched", "now available", "sign up now",
                      "get started today", "limited", "act now"):
            self.assertNotIn(claim, company, claim)

    def test_it_discloses_that_the_offer_changes_nothing_about_the_record(self):
        company = strip_php_comments(block(COMPANY))
        self.assertIn("no bearing on what", company)

    def test_nothing_promises_the_reader_legal_advice(self):
        for path in (COMPANY, FACET):
            self.assertIn("not legal advice", strip_php_comments(block(path)))


class TheRegisterHolds(unittest.TestCase):

    # Every entry here is a thing that would be normal in marketing copy and
    # is not acceptable on a page somebody is reading about their own job.
    # Urgency and scarcity first, then the presumption that the reader has
    # been laid off, then the exclamation mark.
    BANNED = (
        "don't wait", "do not wait", "act fast", "act now", "hurry",
        "limited time", "spots left", "only a few", "last chance",
        "derail your career", "bounce back", "land your dream",
        "supercharge", "unlock", "game-changer", "don't let",
        "you've been laid off", "you have been laid off",
        "now that you're out of work", "your layoff",
    )

    def test_no_urgency_scarcity_or_sales_language(self):
        for path in (COMPANY, FACET):
            copy = strip_php_comments(block(path)).lower()
            for phrase in self.BANNED:
                self.assertNotIn(phrase, copy, "%s: %r" % (path.name, phrase))

    def test_no_exclamation_marks(self):
        for path in (COMPANY, FACET):
            self.assertNotIn("!", strip_php_comments(block(path)), str(path))

    def test_the_reader_is_never_assumed_to_have_lost_a_job(self):
        """A journalist and a researcher read these pages too, and so does an
        employee who is fine. The block has to be useful if the reader was laid
        off and unembarrassing if they were not, which means the framing is a
        condition and never a statement about them."""
        for path in (COMPANY, FACET):
            copy = strip_php_comments(block(path))
            self.assertIn("If a layoff affects you", copy, str(path))
            self.assertIn("Some people reach this page", copy, str(path))


class TheUsefulHalfIsActuallyUseful(unittest.TestCase):

    def test_it_names_the_three_things_needed_in_the_first_hour(self):
        """Rights, money, and the free service that exists for this. Each one
        is a link a reader can act on rather than a description of a problem
        they already have."""
        for path in (COMPANY, FACET):
            copy = strip_php_comments(block(path))
            self.assertIn("WARN Act", copy, str(path))
            self.assertIn("Unemployment insurance", copy, str(path))
            self.assertIn("Rapid Response", copy, str(path))

    def test_the_official_links_are_government_sources(self):
        """careeronestop.org is sponsored by the US Department of Labor's
        Employment and Training Administration, and dol.gov is the department
        itself. Neither is a partner, an affiliate or a referral."""
        for path in (COMPANY, FACET):
            html = block(path)
            self.assertIn("careeronestop.org", html, str(path))
            self.assertIn("www.dol.gov", html, str(path))

    def test_the_us_programmes_are_gated_to_us_records(self):
        """The tracker holds records from many countries. Three United States
        programmes shown on a page whose records name no US location is copy
        that is simply not true for its reader.
        """
        company = read(COMPANY)
        self.assertIn("$alt_ns_us", company)
        self.assertIn("in_array('United States'", company)
        facet = read(FACET)
        self.assertIn("$alt_ns_show", facet)
        self.assertIn("$alt_f['dim'] === 'state'", facet)


if __name__ == "__main__":
    unittest.main()
