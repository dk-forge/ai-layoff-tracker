

import unittest  # noqa: E402


class InlineInkFollowsDarkMode(unittest.TestCase):
    """Owner review 2026-11-11: bold employer names, the glance title and the
    italic caveat carried inline #111827 and stayed dark on the dark card."""

    def test_strong_b_em_i_are_recoloured_in_dark_mode(self):
        import email_theme as t
        block = t.dark_style_block()
        for tag in ("strong", "b", "em", "i"):
            self.assertIn(f".{t.CLASSES['card']} {tag}", block)
