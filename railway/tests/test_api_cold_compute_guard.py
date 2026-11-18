"""todo#1881 item 4: fast filter clicks gave 500s (review B1).

Pins the three guards so a refactor cannot quietly drop one:
server single-flight + slot cap in alt_api_cached, the client's one retry on
503, and refreshAll() coalescing bursts while superseded requests abort.
"""

import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
DB = (PLUGIN / "includes" / "db.php").read_text()
JS = (PLUGIN / "assets" / "layoffs.js").read_text()


def body(src, name):
    m = re.search(r"function %s\([^)]*\)\s*\{" % re.escape(name), src)
    assert m, name
    i, depth = m.end(), 1
    while depth:
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
    return src[m.end():i]


class ServerGuard(unittest.TestCase):
    def test_cached_route_misses_go_through_the_guard(self):
        self.assertIn("alt_cold_compute_guard(", body(DB, "alt_api_cached"))

    def test_guard_rechecks_cache_under_lock(self):
        b = body(DB, "alt_api_cached")
        self.assertRegex(b, r"\$hit = get_transient\(\$key\)")

    def test_full_slots_answer_503_with_retry_after(self):
        g = body(DB, "alt_cold_compute_guard")
        self.assertIn("503", g)
        self.assertIn("Retry-After", g)
        self.assertIn("no-store", g)

    def test_locks_release_in_finally(self):
        g = body(DB, "alt_cold_compute_guard")
        self.assertIn("finally", g)
        self.assertEqual(g.count("alt_named_unlock("), 4)

    def test_no_lock_support_falls_back_to_plain_compute(self):
        self.assertIn("if ($got === null) return null;", body(DB, "alt_named_lock"))


class ClientGuard(unittest.TestCase):
    def test_refresh_all_coalesces(self):
        b = body(JS, "refreshAll")
        self.assertIn("REFRESH_GAP_MS", b)
        self.assertIn("refreshAllNow()", b)

    def test_superseded_request_is_aborted(self):
        self.assertIn("st.ctrl.abort()", body(JS, "busyBegin"))

    def test_api_get_retries_a_503_once(self):
        b = body(JS, "apiGet")
        self.assertIn("r.status === 503", b)
        self.assertEqual(b.count("return once()"), 2)  # first call + one retry


if __name__ == "__main__":
    unittest.main()
