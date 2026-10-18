"""Decision logic of scripts/contabo_watch.py, HTTP mocked. Run:
python3 -m unittest discover -s scripts/tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import contabo_watch as cw  # noqa: E402

H = 3600


class Decide(unittest.TestCase):
    def test_one_failure_waits(self):
        a, s = cw.decide({}, False, 1000)
        self.assertEqual((a, s["fails"]), ("wait", 1))

    def test_second_consecutive_failure_restarts(self):
        _, s = cw.decide({}, False, 1000)
        a, s = cw.decide(s, False, 1600)
        self.assertEqual(a, "restart")
        self.assertEqual(s["restarts"], [1600])
        self.assertEqual(s["fails"], 0)

    def test_healthy_resets_count(self):
        _, s = cw.decide({}, False, 1000)
        a, s = cw.decide(s, True, 1600)
        self.assertEqual((a, s["fails"]), ("ok", 0))
        a, _ = cw.decide(s, False, 2200)
        self.assertEqual(a, "wait")

    def test_cooldown_after_restart(self):
        a, _ = cw.decide({"restarts": [1000]}, False, 1000 + 600)
        self.assertEqual(a, "cooldown")

    def test_cap_two_per_six_hours_then_one_mail(self):
        s = {"fails": 1, "restarts": [0, H]}
        a, s = cw.decide(s, False, 2 * H)
        self.assertEqual(a, "capped")
        s["fails"] = 1
        a, s = cw.decide(s, False, 2 * H + 600)
        self.assertEqual(a, "capped-quiet")

    def test_old_restarts_age_out(self):
        a, s = cw.decide({"fails": 1, "restarts": [0, H]}, False, 8 * H)
        self.assertEqual(a, "restart")
        self.assertEqual(s["restarts"], [8 * H])


class WatchWithMockedHttp(unittest.TestCase):
    def run_watch(self, state, statuses, probe_up, now):
        calls = []

        def http(method, url, data=None, headers=None):
            calls.append((method, url))
            self.assertIn("x-request-id", headers)
            box = "box1" if cw.BOXES["box1"]["id"] in url else "box2"
            return (201, {}) if method == "POST" else (200, {"data": [{"status": statuses[box]}]})

        mailed = []
        st = cw.watch(state, "T", now, http=http, probe=lambda ip: probe_up,
                      notify=lambda b, d: mailed.append(b))
        return st, calls, mailed

    def test_down_twice_posts_restart_only_for_down_box(self):
        st, calls, _ = self.run_watch({}, {"box1": "stopped", "box2": "running"}, True, 0)
        st, calls, _ = self.run_watch(st, {"box1": "stopped", "box2": "running"}, True, 600)
        posts = [u for m, u in calls if m == "POST"]
        self.assertEqual(posts, [f"{cw.API}/203574635/actions/restart"])

    def test_running_but_ssh_dead_counts_as_down(self):
        st, _, _ = self.run_watch({}, {"box1": "running", "box2": "running"}, False, 0)
        self.assertEqual(st["box1"]["fails"], 1)

    def test_capped_mails_once(self):
        state = {"box1": {"fails": 1, "restarts": [0, H]},
                 "box2": {}}
        _, calls, mailed = self.run_watch(state, {"box1": "stopped", "box2": "running"}, True, 2 * H)
        self.assertEqual(mailed, ["box1"])
        self.assertFalse([u for m, u in calls if m == "POST"])


if __name__ == "__main__":
    unittest.main()
