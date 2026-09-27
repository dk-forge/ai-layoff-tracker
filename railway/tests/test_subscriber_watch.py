"""Daily subscriber watch (railway/subscriber_watch.py): pure logic, synthetic numbers."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import subscriber_watch as sw  # noqa: E402


def payload(total=100, last7=10, welcome=None, skipped=0, cap=40, digest=None, day="2026-09-27"):
    p = {"available": True,
         "confirmed": {"total": total, "layoff": 60, "talent": 30, "articles": 20},
         "frequency": {"daily": 25, "weekly": 75},
         "confirmed_last_7_days": last7, "last_send": None}
    if welcome is not None:
        p["welcome_mail"] = {"day": day, "welcome": welcome, "welcome_skipped": skipped,
                             "welcome_cap": cap, "brevo_daily_limit": 300}
    if digest is not None:
        p["last_send"] = {"sent_at": day + " 10:07:00", "recipients": digest}
    return p


def days(n):
    return [f"2026-09-{d:02d}" for d in range(1, n + 1)]


def history_from_totals(totals, **kw):
    return [sw.parse(payload(total=t, **kw), d) for d, t in zip(days(len(totals)), totals)]


class Thresholds(unittest.TestCase):
    def test_constants_pinned(self):
        self.assertEqual(sw.BREVO_DAILY_LIMIT, 300)
        self.assertEqual(sw.WELCOME_CAP_DEFAULT, 40)
        self.assertEqual(sw.WELCOME_WARN_FRACTION, 0.75)
        self.assertEqual(sw.BREVO_WARN_FRACTION, 0.80)
        self.assertEqual(sw.DROP_ZERO_DAYS, 3)
        self.assertEqual(sw.DROP_LOOKBACK_DAYS, 7)
        self.assertEqual(sw.SPIKE_MULTIPLE, 3.0)
        self.assertEqual(sw.CAP_HEADROOM, 1.5)
        self.assertEqual(sw.DIGEST_RESERVE, 0.20)


class PreMergeNoFalseWarn(unittest.TestCase):
    def test_absent_welcome_field_is_not_zero_and_not_warn(self):
        h = [sw.parse(payload(), "2026-09-27")]
        self.assertIsNone(h[0]["welcome"])
        self.assertIsNone(sw.total_sends(h[0]))
        self.assertEqual(sw.evaluate(h), [])
        text = sw.summary(h, [])
        self.assertIn("welcome counter not live yet", text)
        self.assertIn("Follows added/stopped: UNKNOWN", text)

    def test_unavailable_route_says_unknown(self):
        h = [sw.parse({"available": False}, "2026-09-27")]
        self.assertIn("UNKNOWN", sw.summary(h, []))


class WelcomeRules(unittest.TestCase):
    def test_below_75_percent_is_ok(self):
        self.assertEqual(sw.evaluate([sw.parse(payload(welcome=29), "2026-09-27")]), [])

    def test_75_percent_warns(self):
        w = sw.evaluate([sw.parse(payload(welcome=30), "2026-09-27")])
        self.assertEqual(len(w), 1)
        self.assertIn("30 of the 40", w[0])

    def test_skipped_warns(self):
        w = sw.evaluate([sw.parse(payload(welcome=5, skipped=1), "2026-09-27")])
        self.assertTrue(any("skipped" in x for x in w))

    def test_brevo_80_percent(self):
        ok = sw.parse(payload(welcome=10, digest=229), "2026-09-27")
        bad = sw.parse(payload(welcome=10, digest=230), "2026-09-27")
        self.assertEqual(sw.evaluate([ok]), [])
        self.assertTrue(any("Brevo" in x for x in sw.evaluate([bad])))

    def test_old_digest_not_counted_today(self):
        s = sw.parse(payload(welcome=10, digest=250, day="2026-09-26"), "2026-09-27")
        self.assertEqual(sw.total_sends(s), 10)


class Recommendation(unittest.TestCase):
    def test_peak_times_headroom(self):
        h = [sw.parse(payload(welcome=40, skipped=10), "2026-09-27")]
        self.assertEqual(sw.recommend_cap(h), 75)  # 50 x 1.5
        self.assertIn("raise ALT_WELCOME_DAILY_CAP to 75", sw.summary(h, sw.evaluate(h)))

    def test_bounded_to_leave_digest_room(self):
        h = [sw.parse(payload(welcome=40, skipped=160, digest=100), "2026-09-27")]
        self.assertEqual(sw.recommend_cap(h), 140)  # 300*0.8 - 100

    def test_none_before_counter_live(self):
        self.assertIsNone(sw.recommend_cap([sw.parse(payload(), "2026-09-27")]))


class TrendRules(unittest.TestCase):
    def test_net_change_series(self):
        h = history_from_totals([100, 103, 103])
        self.assertEqual([c for _, c, _ in sw.daily_new(h)], [None, 3, 0])

    def test_gross_field_preferred(self):
        p = payload(total=100)
        p["confirmed_yesterday"] = 7
        self.assertEqual(sw.daily_new([sw.parse(p, "2026-09-27")])[0][1:], (7, False))

    def test_drop_after_nonzero_week(self):
        # base, then 7 days of +2, then 3 flat days
        totals = [100] + [100 + 2 * i for i in range(1, 8)] + [114, 114, 114]
        self.assertTrue(any("drop" in x for x in sw.evaluate(history_from_totals(totals))))

    def test_no_drop_without_prior_signups(self):
        self.assertEqual(sw.evaluate(history_from_totals([100] * 11)), [])

    def test_no_drop_with_short_history(self):
        self.assertEqual(sw.evaluate(history_from_totals([100, 102, 102, 102, 102])), [])

    def test_spike(self):
        totals = [100] + [100 + 2 * i for i in range(1, 8)]  # avg 2/day
        self.assertEqual(sw.evaluate(history_from_totals(totals + [119])), [])  # 5 < 6
        self.assertTrue(any("spike" in x for x in sw.evaluate(history_from_totals(totals + [120]))))

    def test_merge_history_replaces_same_day_and_trims(self):
        h = history_from_totals([100] * 3)
        h = sw.merge_history(h, sw.parse(payload(total=5), "2026-09-03"))
        self.assertEqual(len(h), 3)
        self.assertEqual(h[-1]["total"], 5)
        long = history_from_totals([1] * 28) * 3
        self.assertLessEqual(len(sw.merge_history(long, h[-1])), sw.HISTORY_DAYS)


if __name__ == "__main__":
    unittest.main()
