"""Every card says when this tracker first listed the row (card contract 1.1.0).

The source's own date (card-when) says when the event was published. A reporter
citing a row also needs when WE first carried it, which is the API's
created_at. Rows listed before that column existed carry created_at = null, and
then the card says nothing about it: no guess, no fallback to the source date,
no "not stated" string. Executed for real in node via jsrun.
"""
import unittest

from jsrun import BASE_PREAMBLE, run, require_node

PRE = BASE_PREAMBLE + """
function escapeHtml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
"""


def listed(created_at):
    return run(["cardWhen", "cardListed"], PRE, "cardListed(%s)" % created_at)


class CardFirstListed(unittest.TestCase):
    def setUp(self):
        require_node(self)

    def test_a_row_with_created_at_says_first_listed_in_a_time_element(self):
        html = listed("{created_at: '2026-11-03T14:05:00Z'}")
        self.assertEqual(
            html,
            '<time class="alt-card-listed" datetime="2026-11-03">First listed 3 Nov 2026</time>',
        )

    def test_null_created_at_renders_nothing(self):
        for row in ("{created_at: null}", "{}", "{created_at: ''}", "{created_at: 'garbage'}"):
            self.assertEqual(listed(row), "", row)

    def test_null_created_at_never_falls_back_to_the_source_date(self):
        self.assertEqual(listed("{created_at: null, layoff_date: '2026-01-02'}"), "")

    def test_card_renders_the_listed_slot_between_when_and_src(self):
        from pathlib import Path
        js = (Path(__file__).resolve().parents[2]
              / "wordpress-plugin/ai-layoff-tracker/assets/layoffs.js").read_text()
        start = js.index("function cardHtml(row, i) {")
        body = js[start:js.index("\n    function renderCards()", start)]
        self.assertIn("var listed = cardListed(row);", body)
        foot = body[body.index("alt-card-foot"):]
        self.assertLess(foot.index("alt-card-when"), foot.index("listed"))
        self.assertLess(foot.index("listed"), foot.index("alt-card-src"))


if __name__ == "__main__":
    unittest.main()
