"""Owner request 2026-11-15: the open roles block rides the layoff DAILY only."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import digest_preview  # noqa: E402
import digest_send  # noqa: E402

BLOCK = {"html": "<p data-alt=\"openroles\">OPENROLES-MARK</p>", "text": "OPENROLES-MARK"}


def render(freq, lists):
    payload = digest_preview.sample_payload()
    payload["freq"] = freq
    recipient = {"email": "a@b.test", "unsub_url": "https://asktherecruiter.com/u?t=1",
                 "lists": lists, "open_roles_section": BLOCK}
    m = digest_send.build_message(payload, recipient, "f@b.test", "r@b.test")
    return m


class LayoffDailyOpenRoles(unittest.TestCase):
    def test_daily_layoff_reader_gets_block(self):
        m = render("daily", ["layoff"])
        self.assertIsNotNone(m)
        self.assertIn("OPENROLES-MARK", m.html)
        self.assertIn("OPENROLES-MARK", m.text)

    def test_weekly_and_monthly_layoff_reader_do_not(self):
        for freq in ("weekly", "monthly"):
            m = render(freq, ["layoff"])
            if m is not None:
                self.assertNotIn("OPENROLES-MARK", m.html, freq)

    def test_talent_reader_still_gets_it(self):
        m = render("daily", ["talent"])
        if m is not None:
            self.assertIn("OPENROLES-MARK", m.html)

    def test_plugin_rule_is_daily_only_for_layoff(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "..", "wordpress-plugin",
                                "ai-layoff-tracker", "includes", "digest-open-roles.php")).read()
        self.assertIn("in_array('layoff', $lists, true) && $freq === 'daily'", src)


if __name__ == "__main__":
    unittest.main()
