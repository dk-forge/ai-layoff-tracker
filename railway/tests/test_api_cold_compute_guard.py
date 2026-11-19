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
        self.assertIn("if ($slot === false)", g)
        b = body(DB, "alt_busy_response")
        self.assertIn("503", b)
        self.assertIn("Retry-After", b)
        self.assertIn("no-store", b)

    def test_locks_release_in_finally(self):
        g = body(DB, "alt_cold_compute_guard")
        self.assertIn("finally", g)
        self.assertEqual(g.count("alt_named_unlock("), 5)  # internal path + outer paths

    def test_no_lock_support_falls_back_to_plain_compute(self):
        self.assertIn("if ($got === null) return null;", body(DB, "alt_named_lock"))


class CodexFindings(unittest.TestCase):
    def test_bootstrap_rejects_non_200_pieces(self):
        b = body(DB, "alt_tracker_bootstrap_payload")
        self.assertIn("get_status() === 200", b)
        self.assertIn("is_wp_error($resp)", b)

    def test_waiters_drop_request_local_option_cache_before_rereading(self):
        f = body(DB, "alt_forget_transient_cache")
        self.assertIn("'notoptions'", f)
        self.assertNotIn("wp_cache_delete($key, 'transient')", f)  # never the shared copy
        g = body(DB, "alt_cold_compute_guard")
        f = g.index("alt_forget_transient_cache")
        self.assertLess(g.index("alt_named_lock("), f)
        self.assertGreater(g.index("get_transient", f), f)


class SecondReview(unittest.TestCase):
    """Fallback review (Codex out of credits), high effort, on #693."""

    def test_only_the_visitors_own_rest_call_is_capped(self):
        self.assertIn("alt_is_outer_rest_call($r)", body(DB, "alt_api_cached"))
        g = body(DB, "alt_cold_compute_guard")
        self.assertIn("if (!$outer) {", g)
        internal = g[g.index("if (!$outer) {"):g.index("$key_lock =")]
        self.assertNotIn("busy_response", internal)  # internal callers never get a 503
        self.assertIn("alt_named_lock('k|'", internal)  # but keep single-flight
        o = body(DB, "alt_is_outer_rest_call")
        self.assertIn("REST_REQUEST", o)
        self.assertIn("rest_route", o)

    def test_a_key_lock_timeout_is_busy_not_a_second_compute(self):
        g = body(DB, "alt_cold_compute_guard")
        self.assertIn("if ($key_lock === false) return alt_busy_response();", g)
        self.assertIn("$key_lock = alt_named_lock('k|' . $key, 2);", g)  # waiters hold workers: keep it short

    def test_forget_never_reloads_alloptions_and_forces_ext_reread(self):
        f = body(DB, "alt_forget_transient_cache")
        self.assertNotIn("alloptions", f.split("*/")[-1] if "*/" in f else f.replace("alloptions is", ""))
        self.assertIn("wp_cache_get($key, 'transient', true)", f)

    def test_bootstrap_checks_wp_error_once(self):
        self.assertEqual(body(DB, "alt_tracker_bootstrap_payload").count("is_wp_error($resp)"), 1)


class SecondReviewRound2(unittest.TestCase):
    def test_a_hit_takes_no_lock(self):
        g = body(DB, "alt_cold_compute_guard")
        self.assertLess(g.index("get_transient($key) !== false) return call_user_func($run);"),
                        g.index("alt_named_lock("))

    def test_one_filter_change_fits_in_the_cap(self):
        self.assertIn("define('ALT_COLD_SLOTS', 10)", DB)

    def test_only_the_caps_503_is_retried(self):
        self.assertIn("r.status !== 503 || !r.headers.get('Retry-After')", body(JS, "apiGet"))

    def test_a_burst_retires_requests_already_in_flight(self):
        b = body(JS, "refreshAll")
        for s in ("AGG_SEQ++", "QUERY_SEQ++", "LOC_SEQ++", "busyBegin('alt-cards'", "busyBegin('alt-minigrid'"):
            self.assertIn(s, b)


class FinalReview(unittest.TestCase):
    def test_no_max_wait_fetch_inside_a_burst(self):
        b = body(JS, "refreshAll")
        self.assertIn("if (!REFRESH_TIMER && now - REFRESH_LAST >= REFRESH_GAP_MS)", b)
        self.assertNotIn("MAX_WAIT", JS)


class ClientGuard(unittest.TestCase):
    def test_page_state_follows_every_click_and_only_fetches_coalesce(self):
        b = body(JS, "refreshAll")
        self.assertLess(b.index("updateActiveFilterBar()"), b.index("REFRESH_TIMER"))
        n = body(JS, "refreshAllNow")
        self.assertNotIn("updateActiveFilterBar", n)
        self.assertIn("loadLocations()", n)

    def test_location_table_aborts_the_request_it_replaces(self):
        self.assertIn("LOC_CTRL.abort()", body(JS, "loadLocations"))

    def test_refresh_all_coalesces(self):
        b = body(JS, "refreshAll")
        self.assertIn("REFRESH_GAP_MS", b)
        self.assertIn("refreshAllNow()", b)

    def test_superseded_request_is_aborted(self):
        self.assertIn("st.ctrl.abort()", body(JS, "busyBegin"))

    def test_api_get_retries_the_caps_503_a_bounded_number_of_times(self):
        b = body(JS, "apiGet")
        self.assertIn("return attempt(left - 1)", b)
        self.assertIn("attempt(3)", b)


if __name__ == "__main__":
    unittest.main()
