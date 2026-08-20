"""The "Other talent activity" block: three counts that must be measurements.

WHY THIS FILE EXISTS.

The signup form promises hiring, leadership and compensation signals. The
digest delivered hiring only, so two thirds of what a subscriber consented to
was invisible in every edition. The block that closes that gap asks
/talent/v1/aggregate three more times over the same window, each narrowed by
one filter, and prints the counts.

THE FAULT THAT MAKES THIS A TEST RATHER THAN A REVIEW, MEASURED ON THE LIVE
ROUTE ON 2026-08-19. That endpoint does not validate its filter values. It
DROPS a value it does not recognise and answers with the UNFILTERED total.
Over 2026-08-10 to 2026-08-16, against an unfiltered total of 1,387:

    pillar=leadership_change    846   honoured
    funding=1                   182   honoured
    pillar=rewards_comp          97   honoured
    pillar=leadership_chang   1,387   IGNORED - one character short
    pillar=hiring_expansion   1,387   IGNORED - not a pillar at all
    funding=0                 1,387   IGNORED

So a typo here, or the sibling plugin renaming a pillar, publishes
"Leadership moves 1,387" - the worldwide headline wearing a category label,
presented as a measurement. Nothing fails, nothing logs, and the number is
plausible, which is what makes it worse than a wrong zero.

The three properties held here are therefore: a category whose count equals the
headline is OMITTED rather than published; a category whose call FAILS is
omitted rather than zeroed; and a real zero from a working call is a real
measurement and prints.

Without php on PATH these SKIP, which is not a pass.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

HEADLINE = 1387


def compose(fixture):
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


def fixture(**categories):
    """A talent window whose category answers the caller chooses.

    A category the caller does not name is absent from the fixture, and the
    harness answers that call with an ERROR, which is what the real endpoint
    does when it cannot serve the filter.
    """
    base = {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "talent",
        "talent": {"total": HEADLINE, "companies": 1335, "verified": 141},
        "talent_ytd": {"total": 22670, "companies": 9100, "verified": 3400},
        "talent_q": {"rows": [
            {"company": "Vantage Health", "headline": "Vantage Health adds 2,200 roles",
             "published_date": "2026-08-12", "headcount": 2200,
             "source_name": "Dallas Business Journal", "materiality": "high",
             "confidence": "verified", "pillar": "company_development"},
        ]},
    }
    base.update(categories)
    return base


def activity_line(out):
    """The block's own line, from the plain-text part, or '' when absent."""
    text = out["text"]
    if "Other talent activity" not in text:
        return ""
    block = text.split("Other talent activity", 1)[1]
    for line in block.splitlines():
        if line.strip():
            return line.strip()
    return ""


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class ACategoryCountIsAMeasurementOrItIsAbsent(unittest.TestCase):

    def test_the_three_categories_print_when_all_three_are_real(self):
        """The control. Every rejection below proves nothing without it."""
        out = compose(fixture(
            talent_cat_pillar_leadership_change={"total": 846},
            talent_cat_funding_1={"total": 182},
            talent_cat_pillar_rewards_comp={"total": 97}))
        line = activity_line(out)
        self.assertIn("Leadership moves 846", line)
        self.assertIn("Funding rounds 182", line)
        self.assertIn("Pay and benefits changes 97", line)

    def test_a_count_equal_to_the_headline_is_omitted(self):
        """The signature of a filter the endpoint dropped. Publishing it would
        put the worldwide headline under a category label."""
        out = compose(fixture(
            talent_cat_pillar_leadership_change={"total": HEADLINE},
            talent_cat_funding_1={"total": 182},
            talent_cat_pillar_rewards_comp={"total": 97}))
        line = activity_line(out)
        self.assertNotIn("Leadership moves", line,
                         "a category whose count IS the headline was "
                         "published, so an ignored filter reads as a finding")
        self.assertNotIn(str(HEADLINE), line)
        # The other two are unaffected: one bad filter is not three.
        self.assertIn("Funding rounds 182", line)
        self.assertIn("Pay and benefits changes 97", line)

    def test_a_failed_call_is_omitted_and_never_a_zero(self):
        """UNKNOWN is not a measurement. A category rendered 0 because a
        request failed is a number we did not measure, published as one we
        did."""
        out = compose(fixture(
            talent_cat_funding_1={"total": 182},
            talent_cat_pillar_rewards_comp={"total": 97}))
        line = activity_line(out)
        self.assertNotIn("Leadership moves", line)
        self.assertIn("Funding rounds 182", line)

    def test_a_real_zero_from_a_working_call_is_printed(self):
        """The source answered and the answer is none. That is a measurement
        and it is not the case the guards above are about."""
        out = compose(fixture(
            talent_cat_pillar_leadership_change={"total": 846},
            talent_cat_funding_1={"total": 0},
            talent_cat_pillar_rewards_comp={"total": 97}))
        self.assertIn("Funding rounds 0", activity_line(out))

    def test_the_block_disappears_rather_than_printing_an_empty_line(self):
        """Every category unreadable is no block, not a heading over nothing."""
        out = compose(fixture())
        self.assertNotIn("Other talent activity", out["text"])
        self.assertNotIn("Other talent activity", out["html"])

    def test_the_line_refuses_to_imply_the_categories_partition_the_total(self):
        """They overlap by design: a funded employer can also be hiring. The
        caption has to say so, because three numbers under a headline invite
        exactly one arithmetic and it is the wrong one."""
        out = compose(fixture(
            talent_cat_pillar_leadership_change={"total": 846},
            talent_cat_funding_1={"total": 182},
            talent_cat_pillar_rewards_comp={"total": 97}))
        block = out["text"].split("Other talent activity", 1)[1]
        self.assertIn("overlap", block)
        self.assertIn("do not sum", block)

    def test_every_category_links_to_that_filtered_view_on_this_window(self):
        """A count a reader cannot go and check is a claim, not a figure."""
        out = compose(fixture(
            talent_cat_pillar_leadership_change={"total": 846},
            talent_cat_funding_1={"total": 182},
            talent_cat_pillar_rewards_comp={"total": 97}))
        html = out["html"].split("Other talent activity", 1)[1]
        for token in ("pillar=leadership_change", "funding=1",
                      "pillar=rewards_comp"):
            self.assertIn(token, html, f"{token} is not linked")
        self.assertIn("since=2026-08-10", html)
        self.assertIn("until=2026-08-16", html)


if __name__ == "__main__":
    unittest.main()
