"""The server-rendered board's default 'now' is the SITE's day (New York).

2026-11-13 00:03 UTC the live board checked 'Today' = 2026-11-13 while the site's
day was still 2026-11-12: alt_signal_board_periods() defaulted to
current_time('timestamp'), the WordPress zone, not alt_site_now_ts().
"""
import os
import re
import unittest

DB = os.path.join(os.path.dirname(__file__), "..", "..", "wordpress-plugin",
                  "ai-layoff-tracker", "includes", "db.php")


class ServerBoardUsesSiteDay(unittest.TestCase):
    def test_default_now_is_site_clock(self):
        src = open(DB, encoding="utf-8").read()
        m = re.search(r"function alt_signal_board_periods\(\$now = null\) \{(.*?)\n\}", src, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)[:700]
        self.assertIn("alt_site_now_ts", body)
        self.assertLess(body.index("alt_site_now_ts"), body.index("current_time"))


if __name__ == "__main__":
    unittest.main()
