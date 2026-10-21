"""The at-a-glance tiles and the table must agree with /query, and ingest must be fresh.

Owner report 2026-10-17: the tracker showed 0 for Today / This week on a phone
while /query held rows for those windows. Nothing in data_integrity compared a
number ON THE PAGE with the API it was counted from, so a page that painted 0
over live rows could pass every check. These tests pin the two new live checks
(board_tiles_match_query, board_tiles_render) and the ingest freshness check.
All offline: every fetch and every render is injected.
"""
import json
import os
import sys
import unittest
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import board_consistency as bc  # noqa: E402
import data_integrity as di  # noqa: E402

WINDOWS = [("2026-10-18", "2026-10-18"), ("2026-10-12", "2026-10-18"),
           ("2026-10-01", "2026-10-18"), ("2026-09-01", "2026-09-30")]


def page(tiles, table_total=4827, table_rows=25):
    cells = "".join(
        f'<a class="alt-sb-cell alt-nfilter" role="cell" href="?x" data-from="{f}" '
        f'data-to="{t}" data-date-basis="notice"><b>{n:,}</b></a>'
        for (f, t), n in tiles)
    boot = {"query": {"total": table_total, "data": [{"id": i} for i in range(table_rows)]},
            "query_params": {"years": "2026", "date_basis": "notice", "per_page": "25"}}
    return ("<html><script>window.ALT_BOOTSTRAP=" + json.dumps(boot) + ";</script>"
            '<div class="alt-sb-row alt-sb-r-jobs" role="row"><a class="alt-sb-cell" '
            'data-from="2026-10-18" data-to="2026-10-18"><b>999</b></a></div>'
            '<div class="alt-sb-row alt-sb-r-events" role="row">'
            '<span class="alt-sb-label">Verified layoffs</span>' + cells + "</div></html>")


class Live:
    """A fake site: per-window /query totals and /aggregate excluded counts."""

    def __init__(self, html, query, excluded=None, table_total=4827, table_rows=25):
        self.html, self.query, self.excluded = html, query, excluded or {}
        self.table_total, self.table_rows = table_total, table_rows
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        if "wp-json" not in url:
            return self.html(q) if callable(self.html) else self.html
        if u.path.endswith("/query"):
            if "from" in q:
                return json.dumps({"total": self.query[(q["from"], q["to"])], "data": []})
            return json.dumps({"total": self.table_total,
                               "data": [{}] * self.table_rows})
        if u.path.endswith("/aggregate"):
            ex = self.excluded.get((q["from"], q["to"]), 0)
            tot = self.query[(q["from"], q["to"])] - ex
            return json.dumps({"totals": {"entries": tot}, "excluded": {"entries": ex}})
        raise AssertionError(url)


def ctx(fetch):
    return di.Ctx(fetch, 5, "cb")


GOOD = dict(zip(WINDOWS, [2, 36, 131, 390]))
CLOCK = datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)   # 12:00 in New York


class Clocked(unittest.TestCase):
    def setUp(self):
        self._now = bc.now_utc
        bc.now_utc = lambda: CLOCK

    def tearDown(self):
        bc.now_utc = self._now


class ParsingThePage(unittest.TestCase):

    def test_reads_the_verified_layoffs_row_only(self):
        tiles = bc.page_tiles(page(list(GOOD.items())))
        self.assertEqual(tiles, [(f, t, n) for (f, t), n in GOOD.items()])

    def test_reads_the_inlined_table(self):
        self.assertEqual(bc.page_table(page([], 10, 3)), (10, 3))

    def test_no_board_is_none(self):
        self.assertEqual(bc.page_tiles("<html></html>"), [])


def real_page(tiles, dated_zero=True):
    """The page as the plugin actually renders it: a zero cell is a <span
    class="alt-sb-zero">, not a link. 2026-10-21 02:14 New York: Today was a
    genuine 0, the zero span carried no window, the parser skipped it, and the
    week tile was read as the Today column (a FAIL over a correct page)."""
    cells = ""
    for (f, t), n in tiles:
        if n:
            cells += (f'<a class="alt-sb-cell alt-nfilter" role="cell" href="?x" '
                      f'data-from="{f}" data-to="{t}" data-date-basis="notice"><b>{n:,}</b></a>')
        else:
            data = f' data-from="{f}" data-to="{t}" data-date-basis="notice"' if dated_zero else ""
            cells += f'<span class="alt-sb-cell alt-sb-zero" role="cell"{data}>0</span>'
    return ('<html><div class="alt-sb-row alt-sb-r-events" role="row">'
            '<span class="alt-sb-label" role="rowheader">Verified layoffs</span>' + cells + "</div></html>")


class ZeroCells(Clocked):
    """A zero tile is a span, and it must still be read as its own window."""

    def run_inv(self, fetch):
        return bc.BoardTilesMatchQuery().run(ctx(fetch))

    def test_a_genuine_zero_today_passes(self):
        live = {**GOOD, WINDOWS[0]: 0}
        r = self.run_inv(Live(real_page(list(live.items())), live))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_the_zero_span_is_parsed_in_its_column(self):
        live = {**GOOD, WINDOWS[0]: 0}
        self.assertEqual(bc.page_tiles(real_page(list(live.items())))[0],
                         ("2026-10-18", "2026-10-18", 0))

    def test_a_zero_span_over_live_rows_fails(self):
        shown = {**GOOD, WINDOWS[0]: 0}
        r = self.run_inv(Live(real_page(list(shown.items())), GOOD))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("shows 0", r.detail)

    def test_an_undated_zero_cell_is_unknown_never_a_shifted_column(self):
        live = {**GOOD, WINDOWS[0]: 0}
        r = self.run_inv(Live(real_page(list(live.items()), dated_zero=False), live))
        self.assertEqual(r.state, di.UNKNOWN, r.detail)
        self.assertNotIn("Today column counts", r.detail)


class TilesMatchQuery(Clocked):

    def run_inv(self, fetch, render=None):
        inv = bc.BoardTilesMatchQuery(render=render or (lambda w: None))
        return inv.run(ctx(fetch))

    def test_matching_tiles_pass_on_both_user_agents(self):
        f = Live(page(list(GOOD.items())), {**GOOD, WINDOWS[3]: 397},
                 excluded={WINDOWS[3]: 7})
        r = self.run_inv(f)
        self.assertEqual(r.state, di.PASS, r.detail)
        uas = [u for u in f.urls if "wp-json" not in u]
        self.assertEqual(len(uas), 2)            # desktop + phone

    def test_zero_tile_over_live_rows_fails(self):
        shown = dict(GOOD)
        shown[WINDOWS[0]] = 0
        r = self.run_inv(Live(page(list(shown.items())), GOOD))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("0", r.detail)
        self.assertIn("2026-10-18", r.detail)

    def test_a_wrong_nonzero_tile_fails(self):
        shown = dict(GOOD)
        shown[WINDOWS[2]] = 60
        r = self.run_inv(Live(page(list(shown.items())), GOOD))
        self.assertEqual(r.state, di.FAIL)

    def test_a_cache_lag_of_one_entry_is_tolerated(self):
        shown = dict(GOOD)
        shown[WINDOWS[1]] = 35
        r = self.run_inv(Live(page(list(shown.items())), GOOD))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_today_column_counting_the_browsers_tomorrow_fails(self):
        # The 2026-10-17 defect: a reader ahead of New York got tomorrow's
        # window, which /query answers truthfully with 0. Agreement with its
        # own window is not enough; the column must be the SITE's today.
        tomorrow = ("2026-10-19", "2026-10-19")
        shown = [(tomorrow, 0)] + list(GOOD.items())[1:]
        r = self.run_inv(Live(page(shown), {**GOOD, tomorrow: 0}))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("site's today", r.detail)

    def test_site_today_tolerates_the_minutes_around_midnight(self):
        near = datetime(2026, 10, 19, 4, 2, tzinfo=timezone.utc)   # 00:02 New York
        self.assertEqual(bc.site_today_candidates(near), {"2026-10-18", "2026-10-19"})
        self.assertEqual(bc.site_today_candidates(CLOCK), {"2026-10-18"})

    def test_aggregate_disagreeing_with_query_fails(self):
        class Skew(Live):
            def __call__(self, url, timeout):
                out = super().__call__(url, timeout)
                if "/aggregate" in url and "2026-10-12" in url:
                    return json.dumps({"totals": {"entries": 0}, "excluded": {"entries": 0}})
                return out
        r = self.run_inv(Skew(page(list(GOOD.items())), GOOD))
        self.assertEqual(r.state, di.FAIL)

    def test_empty_first_table_page_over_rows_fails(self):
        r = self.run_inv(Live(page(list(GOOD.items()), 4827, 0), GOOD))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("table", r.detail)

    def test_page_with_no_board_is_unknown_not_pass(self):
        r = self.run_inv(Live("<html>maintenance</html>", GOOD))
        self.assertEqual(r.state, di.UNKNOWN)

    def test_unreachable_api_is_unknown(self):
        def dead(url, timeout):
            raise OSError("no route")
        r = self.run_inv(dead)
        self.assertEqual(r.state, di.UNKNOWN)
        self.assertTrue(r.transport)


class RenderedAt390AndDesktop(Clocked):

    def test_rendered_zero_fails_at_390(self):
        def render(width):
            n = 0 if width == 390 else 2
            return {"tiles": [("2026-10-18", "2026-10-18", n)], "cards": 25,
                    "table_total": 4827}
        inv = bc.BoardTilesRender(render=render)
        r = inv.run(ctx(Live("", GOOD)))
        self.assertEqual(r.state, di.FAIL)
        self.assertIn("390", r.detail)

    def test_rendered_empty_cards_fail(self):
        def render(width):
            return {"tiles": [("2026-10-18", "2026-10-18", 2)], "cards": 0,
                    "table_total": 4827}
        r = bc.BoardTilesRender(render=render).run(ctx(Live("", GOOD)))
        self.assertEqual(r.state, di.FAIL)

    def test_both_widths_good_pass(self):
        def render(width):
            return {"tiles": [("2026-10-18", "2026-10-18", 2)], "cards": 25,
                    "table_total": 4827}
        r = bc.BoardTilesRender(render=render).run(ctx(Live("", GOOD)))
        self.assertEqual(r.state, di.PASS, r.detail)

    def test_no_browser_is_unknown(self):
        def render(width):
            raise bc.RenderUnavailable("no Chrome")
        r = bc.BoardTilesRender(render=render).run(ctx(Live("", GOOD)))
        self.assertEqual(r.state, di.UNKNOWN)

    def test_the_phone_render_runs_ahead_of_new_york(self):
        self.assertEqual(bc.RENDER_TZ[390], "Pacific/Kiritimati")

    def test_both_widths_are_rendered(self):
        seen = []

        def render(width):
            seen.append(width)
            return {"tiles": [("2026-10-18", "2026-10-18", 2)], "cards": 25,
                    "table_total": 4827}
        bc.BoardTilesRender(render=render).run(ctx(Live("", GOOD)))
        self.assertEqual(sorted(seen), [390, 1280])


class Registered(unittest.TestCase):

    def test_both_checks_are_in_the_one_registry(self):
        keys = {i.key for i in di.INVARIANTS}
        self.assertIn("board_tiles_match_query", keys)
        self.assertIn("board_tiles_render", keys)


NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def run(source, hours_ago, entries, status="ok"):
    at = NOW.timestamp() - hours_ago * 3600
    return {"source": source, "status": status, "entries": entries,
            "attempted_at": datetime.fromtimestamp(at, timezone.utc).isoformat()}


class IngestFreshness(unittest.TestCase):

    def test_all_classes_fresh(self):
        runs = [run("gdelt", 3, 40), run("warn_us", 5, 12), run("edgar", 6, 0)]
        v = bc.freshness_verdict(runs, now=NOW)
        self.assertEqual({k: s for k, s, _ in v},
                         {"news": di.PASS, "WARN": di.PASS, "SEC": di.PASS})

    def test_news_with_no_rows_in_24h_fails(self):
        runs = [run("gdelt", 3, 0), run("google_news", 30, 50),
                run("warn_us", 5, 12), run("edgar", 6, 1)]
        v = dict((k, s) for k, s, _ in bc.freshness_verdict(runs, now=NOW))
        self.assertEqual(v["news"], di.FAIL)

    def test_running_notes_do_not_count(self):
        runs = [run("warn_us", 1, 30, status="running"), run("gdelt", 1, 4),
                run("edgar", 1, 0)]
        v = dict((k, s) for k, s, _ in bc.freshness_verdict(runs, now=NOW))
        self.assertEqual(v["WARN"], di.FAIL)

    def test_sec_needs_a_completed_run_not_rows(self):
        runs = [run("gdelt", 1, 4), run("warn_us", 1, 3)]
        v = dict((k, s) for k, s, _ in bc.freshness_verdict(runs, now=NOW))
        self.assertEqual(v["SEC"], di.FAIL)

    def test_the_invariant_fails_on_a_stale_class_and_passes_when_fresh(self):
        def fetch_for(runs):
            return lambda url, timeout: json.dumps({"runs": runs})
        old = bc.freshness_verdict.__defaults__
        stale = [run("gdelt", 1, 4), run("edgar", 1, 0)]
        fresh = stale + [run("warn_us", 1, 3)]
        bc.freshness_verdict.__defaults__ = (NOW, old[1])
        try:
            r = bc.IngestFreshness().run(ctx(fetch_for(stale)))
            self.assertEqual(r.state, di.FAIL)
            self.assertIn("WARN", r.detail)
            self.assertEqual(bc.IngestFreshness().run(ctx(fetch_for(fresh))).state, di.PASS)
            self.assertEqual(bc.IngestFreshness().run(
                ctx(lambda u, t: b"{}")).state, di.UNKNOWN)
        finally:
            bc.freshness_verdict.__defaults__ = old

    def test_cli_alerts_through_ops_notify_and_never_opens_an_issue(self):
        sent = []
        payload = {"runs": [run("gdelt", 1, 4), run("edgar", 1, 0)]}
        code = bc.freshness_main(fetch=lambda: payload, now=NOW,
                                 notify=lambda *a, **k: sent.append((a, k)) or True)
        self.assertEqual(code, 1)
        self.assertEqual(len(sent), 1)
        self.assertIn("WARN", sent[0][0][0])
        self.assertTrue(sent[0][1].get("dedupe_key"))

    def test_cli_fresh_resolves_and_exits_zero(self):
        sent = []
        payload = {"runs": [run("gdelt", 1, 4), run("warn_us", 1, 3), run("edgar", 1, 0)]}
        code = bc.freshness_main(fetch=lambda: payload, now=NOW,
                                 notify=lambda *a, **k: sent.append((a, k)) or True)
        self.assertEqual(code, 0)
        self.assertEqual(sent, [])

    def test_cli_unreadable_is_unknown_exit_3(self):
        def boom():
            raise OSError("down")
        self.assertEqual(bc.freshness_main(fetch=boom, now=NOW, notify=lambda *a, **k: True), 3)

    def test_workflow_carries_the_mail_key_and_no_issue_step(self):
        wf = os.path.join(os.path.dirname(__file__), "..", "..", ".github",
                          "workflows", "tracker-zeros-watch.yml")
        text = open(wf).read()
        self.assertIn("board_consistency.py", text)
        self.assertIn("RESEND_API_KEY", text)
        self.assertIn("OPS_MAIL_FROM", text)
        self.assertNotIn("gh issue", text)
        self.assertNotIn("issues: write", text)


if __name__ == "__main__":
    unittest.main()
