"""The subscriber email design the owner approved (shown 2026-09-29, rolled out
2026-10-05): a colour per tracker (red for layoffs, blue for talent), green
highlights, bold section headings, a bigger lead number, simple tables and
small charts that a mail client can draw.

The charts are TABLE BARS, never an image: the transport refuses any message
that fetches, and an inline image would also be a picture with no text. Every
figure a bar stands for is still printed beside it, so a client that drops the
bar loses nothing a reader needs.
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

import digest_design as design  # noqa: E402
import digest_layout as layout  # noqa: E402
import digest_transport as dt  # noqa: E402
from test_digest_email_layout import (LAYOFF_HTML, forwarded,  # noqa: E402
                                      message)

TALENT_SERIES_HTML = (
    '<h2>Talent Intelligence Tracker</h2>'
    '<p data-alt="kicker">New hiring signals</p>'
    '<p data-alt="stat">88</p>'
    '<p data-alt="finding">Warsaw led Europe for the second week.</p>'
    '<h3>Other talent activity</h3>'
    '<p data-alt="series">August 7-14, 2026, worldwide: '
    '<a href="https://asktherecruiter.com/blog/r/5">Funding</a> 41 · '
    '<a href="https://asktherecruiter.com/blog/r/6">Leadership</a> 17 · '
    'Expansion 9. These categories overlap.</p>')


def _ratio(a, b):
    def lum(h):
        out = []
        for i in (1, 3, 5):
            c = int(h[i:i + 2], 16) / 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _invert(h):
    return "#" + "".join(f"{255 - int(h[i:i + 2], 16):02x}" for i in (1, 3, 5))


class ColourPerTracker(unittest.TestCase):
    def test_layoff_section_wears_red_and_talent_wears_blue(self):
        self.assertEqual(design.accent_for("layoff"), design.RED)
        self.assertEqual(design.accent_for("follows"), design.RED)
        self.assertEqual(design.accent_for("talent"), design.BLUE)
        html = message(("layoff", "talent")).html
        self.assertIn(f"color:{design.RED}", html)
        self.assertIn(f"color:{design.BLUE}", html)

    def test_a_layoff_only_email_carries_no_talent_blue(self):
        html = message(("layoff",)).html
        self.assertIn(design.RED, html)
        self.assertNotIn(design.BLUE, html)

    def test_every_new_colour_clears_4_5_upright_and_inverted(self):
        pairs = [(design.RED, layout.CARD_BG), (design.BLUE, layout.CARD_BG),
                 (design.GREEN, layout.CARD_BG),
                 (layout.INK, design.GREEN_BG)]
        for ink, bg in pairs:
            self.assertGreaterEqual(round(_ratio(ink, bg), 2), 4.5, (ink, bg))
            self.assertGreaterEqual(
                round(_ratio(_invert(ink), _invert(bg)), 2), 4.5,
                f"{ink} on {bg} fails once a dark-mode client inverts it")


class HeadingsAndLeadNumber(unittest.TestCase):
    def test_section_heading_is_bold_and_carries_the_accent_bar(self):
        out = layout.restyle('<h2>AI Layoff Tracker</h2>', accent=design.RED)
        self.assertIn("font-weight:800", out)
        self.assertIn(f"border-left:4px solid {design.RED}", out)
        self.assertIn(f"color:{design.RED}", out)

    def test_sub_heading_is_bold(self):
        out = layout.restyle('<h3>Biggest cuts</h3>', accent=design.BLUE)
        self.assertIn("font-weight:700", out)
        self.assertIn(f"color:{design.BLUE}", out)

    def test_lead_number_is_bigger_than_before_and_in_the_accent(self):
        out = layout.restyle('<p data-alt="stat">48,910</p>', accent=design.RED)
        self.assertIn("font-size:40px", out)
        self.assertIn(f"color:{design.RED}", out)
        pair = layout.restyle('<p data-alt="stat-pair">1</p>', accent=design.RED)
        self.assertIn("font-size:30px", pair)

    def test_green_highlight_on_a_finding(self):
        out = layout.restyle('<p data-alt="finding">x</p>', accent=design.RED)
        self.assertIn(f"background-color:{design.GREEN_BG}", out)
        self.assertIn(f"border-left:3px solid {design.GREEN}", out)


class SmallCharts(unittest.TestCase):
    def test_a_ranked_table_gets_a_bar_per_row_scaled_to_the_largest(self):
        out = design.add_charts(LAYOFF_HTML)
        bars = re.findall(r'data-alt="bar" width="(\d+)%"', out)
        self.assertEqual(bars, ["100", "78"])  # 1,200 and 940 jobs

    def test_the_rendered_layoff_email_carries_the_chart(self):
        html = message(("layoff",)).html
        self.assertIn(f'bgcolor="{design.RED}"', html)
        self.assertIn('width="78%"', html)
        self.assertNotIn("data-alt", html)

    def test_a_series_line_gets_a_bar_chart(self):
        out = layout.restyle(design.add_charts(TALENT_SERIES_HTML,
                                               accent=design.BLUE),
                             accent=design.BLUE)
        self.assertIn(f'bgcolor="{design.BLUE}"', out)
        self.assertEqual(re.findall(r'width="(\d+)%" bgcolor="' + design.BLUE + '"', out),
                         ["100", "41", "22"])
        for label in ("Funding", "Leadership", "Expansion"):
            self.assertIn(label, out)

    def test_unparseable_series_draws_no_chart_rather_than_a_wrong_one(self):
        odd = '<p data-alt="series">Nothing countable here.</p>'
        self.assertEqual(design.add_charts(odd), odd)

    def test_the_chart_is_decorative_and_fetches_nothing(self):
        built = message(("layoff", "talent", "articles"))
        dt.assert_message_is_clean(built)
        low = built.html.lower()
        for token in ("<img", "url(", "src=", "<script", "<link", "<style"):
            self.assertNotIn(token, low)
        self.assertIn('aria-hidden="true"', built.html)

    def test_chart_cells_survive_a_forward_with_their_own_style(self):
        body = forwarded(message(("layoff",)).html)
        cells = re.findall(r'<td width="\d+%" bgcolor="[^"]+"[^>]*>', body)
        self.assertTrue(cells)
        for cell in cells:
            self.assertIn("style=", cell)
            self.assertIn("background-color:", cell)

    def test_the_plain_text_part_is_unchanged_by_the_design(self):
        built = message(("layoff",))
        self.assertNotIn("bgcolor", built.text)
        self.assertIn("1,200 jobs", built.text)


if __name__ == "__main__":
    unittest.main()
