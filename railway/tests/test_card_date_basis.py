"""The card's date says WHAT date it is (audit 2026-11-15).

Half of the newest 100 /query rows carry no announcement_date, and the card
printed layoff_date bare ("15 Nov 2026"), which a reader takes for a published
date. It is not: on a WARN row it is the legal effective date (often weeks
after the notice), on an ERM row it is Eurofound's announcement date, and on a
news or 8-K row it is the date the cuts were reported to take place. The card
now names the basis, and a WARN row that carries its filed date shows both.
Executed for real in node via jsrun.
"""
import unittest

from jsrun import BASE_PREAMBLE, run, require_node

PRE = BASE_PREAMBLE + """
function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
"""


def when(row):
    return run(["cardWhen", "cardWhenHtml"], PRE, "cardWhenHtml(%s)" % row)


class CardDateBasis(unittest.TestCase):
    def setUp(self):
        require_node(self)

    def test_a_warn_row_says_effective(self):
        self.assertEqual(
            when("{source_type: 'warn', layoff_date: '2026-11-15', announcement_date: ''}"),
            '<time class="alt-card-when" datetime="2026-11-15">Effective 15 Nov 2026</time>')

    def test_a_warn_row_with_its_notice_date_shows_both(self):
        self.assertEqual(
            when("{source_type: 'warn', layoff_date: '2026-11-15', announcement_date: '2026-10-30'}"),
            '<time class="alt-card-when" datetime="2026-11-15">Effective 15 Nov 2026</time>'
            '<time class="alt-card-filed" datetime="2026-10-30">filed 30 Oct 2026</time>')

    def test_an_announced_row_says_announced(self):
        for row in ("{source_type: 'erm', announced: true, layoff_date: '2026-11-03'}",
                    "{source_type: 'news', announced: true, layoff_date: '2026-11-03'}"):
            self.assertIn(">Announced 3 Nov 2026<", when(row), row)

    def test_news_and_filings_say_layoff_date(self):
        for st in ("news", "8K", "federal"):
            self.assertIn(">Layoff date 3 Nov 2026<",
                          when("{source_type: '%s', layoff_date: '2026-11-03'}" % st), st)

    def test_no_bare_date_is_ever_rendered(self):
        for row in ("{source_type: 'warn', layoff_date: '2026-11-03'}",
                    "{source_type: 'news', layoff_date: '2026-11-03'}",
                    "{layoff_date: '2026-11-03'}"):
            self.assertNotIn('">3 Nov 2026<', when(row), row)

    def test_a_missing_date_keeps_the_shared_not_stated_string(self):
        self.assertEqual(when("{source_type: 'warn', layoff_date: ''}"),
                         '<span class="alt-card-when alt-card-nowhere">Date not stated</span>')

    def test_the_card_uses_it(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parents[2]
              / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.js").read_text()
        start = js.index("function cardHtml(row, i) {")
        body = js[start:js.index("\n    function renderCards()", start)]
        self.assertIn("cardWhenHtml(row)", body)


if __name__ == "__main__":
    unittest.main()
