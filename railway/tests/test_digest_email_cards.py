"""Subscriber email redesign (owner OK 2026-10-28, "yes please").

Pins the nine findings of the review of the archived 2026-10-25 weekly and
2026-10-26 daily:
  1. no fixed width that cannot shrink below a 360px phone;
  2. one font stack, three sizes plus the stat (see test_digest_type_scale);
  3. the edition title shown once (masthead), not again as the section h2;
  4. news first, method last under "How we count", nothing dropped;
  5/6. every item is a card with a place pill, muted when there is no place,
       including the leadership / funding / pay lists;
  7. one accent per edition (no green rule);
  8. the 8-week strip is a table of horizontal bars, never a PNG;
  9. Outlook-safe: cards are tables, every rule inline.
php cases SKIP without php, which is UNKNOWN, not a pass.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import digest_design  # noqa: E402
import digest_layout as layout  # noqa: E402
from test_digest_scope_rules import PHP, compose, layoff_fixture  # noqa: E402
from test_digest_talent_redesign import daily  # noqa: E402

PIN = "\U0001F4CD "


def _render(section, html):
    return layout.render_html([(section, html, "x\ny", "", ("", False))],
                              subject="s", preheader="p", kicker="k",
                              unsub_url="https://asktherecruiter.com/u",
                              manage_url="", dark_mode=True)


class Arrange(unittest.TestCase):
    FRAG = ('<h2>AI Layoff Tracker</h2><p data-alt="stat">7,862</p>'
            '<h3>Source quality</h3><p>Where these came from.</p>'
            '<h3>Which industries</h3><p>Retail 4</p>'
            '<h3>Biggest cuts</h3><p>Acme</p>'
            '<h3>Data notes</h3><p>Both figures are provisional.</p>'
            '<h3>Cite this</h3><p>Cite us.</p>')

    def test_title_once_news_first_method_last(self):
        out = layout.arrange_section(self.FRAG, "AI Layoff Tracker")
        self.assertNotIn("<h2>", out)
        order = [out.index(s) for s in ("7,862", "Biggest cuts", "Which industries",
                                        "Cite this", "How we count",
                                        "Where these came from.",
                                        "Both figures are provisional.")]
        self.assertEqual(order, sorted(order))
        for kept in ("Source quality", "Data notes"):
            self.assertIn(f'<p data-alt="kicker">{kept}</p>', out)

    def test_a_second_trackers_title_is_kept(self):
        out = layout.arrange_section("<h2>Talent Intelligence Tracker</h2>",
                                     "AI Layoff Tracker")
        self.assertIn("<h2>Talent Intelligence Tracker</h2>", out)

    def test_more_stays_with_its_list(self):
        out = layout.arrange_section("<h3>Where</h3>w<h3>Top hiring today</h3>a"
                                     "<h3>More</h3>b", "")
        self.assertTrue(out.startswith("<h3>Top hiring today</h3>a<h3>More</h3>b"))


class Shell(unittest.TestCase):
    def test_no_fixed_width_wider_than_a_phone_inside_the_card(self):
        html = _render("layoff", '<p data-alt="weeks">Aug 3 73,472 · Aug 10 73,739 · '
                       'Aug 17 13,938 · Aug 24 71,387 · Aug 31 12,824 · Sep 7 4,396 · '
                       'Sep 14 4,654 · Sep 21 2,980</p>')
        widths = [int(w) for w in re.findall(r'width="(\d+)"', html)]
        self.assertEqual([w for w in widths if w > 360], [layout.WIDTH_PX])
        self.assertIn(f"max-width:{layout.WIDTH_PX}px", html)
        self.assertNotIn("<img", html)
        self.assertIn('bgcolor="' + digest_design.RED, html)   # bars are table cells
        self.assertNotIn("data-alt=", html)

    def test_no_green_rule_in_either_edition(self):
        frag = '<p data-alt="finding">f</p><p data-alt="why">w</p>'
        for section in ("layoff", "talent"):
            self.assertNotIn(digest_design.GREEN, _render(section, frag))

    def test_dark_mode_reaches_pills(self):
        block = layout.email_theme.dark_style_block()
        self.assertIn(".et-card span", block)
        self.assertIn(layout.PILL_BG, block)


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class TalentCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = compose(daily())

    def test_every_item_is_a_card_with_a_place_pill(self):
        html = self.out["html"]
        self.assertNotIn("<li>", html)
        cards = re.findall(r'<td data-alt="card">(.*?)</td>', html, re.S)
        # 5 top + 2 more + 3 leadership + 1 funding
        self.assertEqual(len(cards), 11)
        for card in cards:
            self.assertRegex(card, r'data-alt="pill(?:-muted)?">(?:' + PIN
                             + r'|Location not recorded)')

    def test_leadership_rows_now_say_where(self):
        lead = self.out["html"].split("Leadership moves</p>", 1)[1]
        self.assertIn(PIN + "United States", lead)
        self.assertIn(PIN + "United Kingdom", lead)

    def test_place_pill_links_to_the_filtered_tracker(self):
        self.assertRegex(self.out["html"],
                         r'<a href="[^"]*country(?:%3D|=)GB[^"]*" data-alt="pill">'
                         + PIN + "United Kingdom</a>")

    def test_missing_place_is_a_muted_pill(self):
        out = compose(daily(talent_q={"rows": [
            {"company": "Kodas", "headline": "Kodas to hire", "published_date": "2026-10-12",
             "headcount": 9, "country": "", "source_url": "https://n.example/k"}]}))
        self.assertIn('<span data-alt="pill-muted">Location not recorded</span>', out["html"])

    def test_text_part_is_unchanged_in_shape(self):
        self.assertIn("  - Bolt adds 300 roles (300 jobs, United States, Example Wire,",
                      self.out["text"])


@unittest.skipUnless(PHP, "php is not installed. UNKNOWN, not a pass.")
class LayoffCards(unittest.TestCase):
    def test_biggest_cuts_are_cards_with_place_pills(self):
        html = compose(layoff_fixture())["html"]
        cuts = html.split("<h3>Biggest cuts</h3>", 1)[1].split("<h3>", 1)[0]
        self.assertEqual(cuts.count('<td data-alt="card">'), 2)
        self.assertIn('<span data-alt="pill-muted">Location not recorded</span>', cuts)
        self.assertRegex(cuts, r'state=CA[^"]*" data-alt="pill">' + PIN + "California")
        self.assertIn('<span data-alt="pill">announced</span>', cuts)


if __name__ == "__main__":
    unittest.main()
