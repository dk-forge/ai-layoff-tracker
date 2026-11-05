"""The nightly ingest posted 0 events for 9 nights and nobody was paged.

2026-10-28 to 2026-11-05: every railway-cron run pulled 800 to 1409
candidates and posted 0, because `spend.py --degrade` had switched paid reads
off ("OpenRouter provider key exhausted"). The run stayed green by design,
ingest-silence stayed green because the collectors still wrote fresh notes,
and the balance check read a different number (`limit_remaining`) and saw
$15 left. These tests pin the watchdog that asks "did the run BRING anything?".
"""
import os
import sys
import unittest
from unittest import mock

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import ingest_yield as y  # noqa: E402

OFF = "paid reads were switched off for this run (ALT_PAID_READS=off)"


def run(day, items, stored, truncated=None, job="railway-cron"):
    e = {"job": job, "date": day, "run_id": f"railway-{day.replace('-', '')}T2210",
         "items": items, "stored": stored}
    if truncated:
        e["truncated"] = truncated
    return e


# The incident ledger, as harvested into railway/spend_jobs.json.
INCIDENT = [run("2026-10-27", 1300, 4)] + [
    run(f"2026-10-{d}", 1366, 0, OFF) for d in (28, 29, 30, 31)]
EXHAUSTED = {"usage": 93.60, "limit": 15.0, "limit_remaining": 0.0, "label": "sk-or-v1-0a1...b2c"}
# The real key on 2026-11-05: its limit resets, so lifetime usage past the
# limit is NOT exhaustion. OpenRouter said limit_remaining 15.
REAL_KEY = {"usage": 93.60, "limit": 15.0, "limit_remaining": 15.0, "label": "sk-or-v1-0a1...b2c"}
HEALTHY = REAL_KEY
SECRET = "sk-or-v1-THIS-IS-THE-WHOLE-SECRET-KEY-b2c"


class ZeroPostStreak(unittest.TestCase):
    def test_the_incident_is_a_four_night_streak(self):
        self.assertEqual(y.zero_post_streak(INCIDENT), 4)

    def test_one_zero_night_is_not_yet_an_incident(self):
        rows = [run("2026-10-27", 1300, 4), run("2026-10-28", 1300, 0)]
        self.assertEqual(y.zero_post_streak(rows), 1)
        self.assertEqual(y.evaluate(rows, HEALTHY, SECRET)["zero_posts"], None)

    def test_a_posted_night_ends_the_streak(self):
        rows = INCIDENT + [run("2026-11-01", 900, 2)]
        self.assertEqual(y.zero_post_streak(rows), 0)

    def test_small_pulls_neither_extend_nor_break_it(self):
        rows = [run("2026-10-28", 1300, 0), run("2026-10-29", 40, 0),
                run("2026-10-30", 1300, 0)]
        self.assertEqual(y.zero_post_streak(rows), 2)

    def test_other_jobs_do_not_count(self):
        rows = INCIDENT + [run("2026-11-01", 500, 9, job="warn-import")]
        self.assertEqual(y.zero_post_streak(rows), 4)

    def test_order_comes_from_the_run_id_not_the_file(self):
        self.assertEqual(y.zero_post_streak(list(reversed(INCIDENT))), 4)


class PaidReadsOff(unittest.TestCase):
    def test_the_real_key_values_are_not_an_alarm(self):
        # usage 93.60, limit 15, limit_remaining 15: a resetting limit, healthy.
        self.assertFalse(y.paid_reads_off(REAL_KEY))
        self.assertIsNone(y.evaluate(INCIDENT, REAL_KEY, SECRET)["paid_reads"])

    def test_limit_remaining_zero_is_off(self):
        self.assertTrue(y.paid_reads_off({"limit": 15, "limit_remaining": 0}))

    def test_lifetime_usage_alone_never_alarms(self):
        self.assertIsNone(y.paid_reads_off({"limit": 15, "usage": 93.60}))

    def test_a_run_note_saying_paid_reads_off_does_not_alarm_on_its_own(self):
        self.assertFalse(y.paid_reads_off(REAL_KEY, INCIDENT))

    def test_no_cap_is_on(self):
        self.assertFalse(y.paid_reads_off({"limit": None, "usage": 5}))

    def test_unknown_key_state_is_not_an_alarm(self):
        self.assertIsNone(y.paid_reads_off(None, []))


class TheAlertText(unittest.TestCase):
    def test_it_names_the_exact_fix_and_the_key_tail_only(self):
        verdict = y.evaluate(INCIDENT, EXHAUSTED, SECRET)
        a = verdict["paid_reads"]
        self.assertIsNotNone(a)
        self.assertIn("OpenRouter key for the layoff tracker hit its limit. Open "
                      "https://openrouter.ai/settings/keys, edit the key ending b2c, "
                      "raise the limit.", a["body"])
        for alert in (verdict["paid_reads"], verdict["zero_posts"]):
            self.assertNotIn(SECRET, alert["body"] + alert["subject"])
            self.assertNotIn("THIS-IS-THE-WHOLE", alert["body"])

    def test_without_a_label_it_falls_back_to_the_one_way_fingerprint(self):
        self.assertEqual(y.key_tail({}, SECRET), y.spend.key_fingerprint(SECRET))
        self.assertNotIn(SECRET, y.key_tail({}, SECRET))

    def test_zero_posts_caused_by_paid_reads_carries_the_same_fix(self):
        a = y.evaluate(INCIDENT, EXHAUSTED, SECRET)["zero_posts"]
        self.assertIn("4 nightly runs", a["body"])
        self.assertIn("raise the limit", a["body"])

    def test_text_is_plain_ascii_with_no_dash_glyphs(self):
        v = y.evaluate(INCIDENT, EXHAUSTED, SECRET)
        for a in (v["paid_reads"], v["zero_posts"]):
            text = (a["subject"] + a["body"]).lower()
            self.assertNotIn(chr(0x2014), text)
            self.assertTrue(text.isascii(), "plain ASCII mail text")


class OncePerIncident(unittest.TestCase):
    def test_each_cause_has_a_stable_dedupe_key(self):
        a = y.evaluate(INCIDENT, EXHAUSTED, SECRET)
        b = y.evaluate(INCIDENT + [run("2026-11-01", 1020, 0, OFF)], EXHAUSTED, SECRET)
        self.assertEqual(a["paid_reads"]["dedupe_key"], b["paid_reads"]["dedupe_key"])
        self.assertEqual(a["zero_posts"]["dedupe_key"], b["zero_posts"]["dedupe_key"])
        self.assertNotEqual(a["paid_reads"]["dedupe_key"], a["zero_posts"]["dedupe_key"])

    def test_main_raises_with_dedupe_and_resolves_when_clear(self):
        sent = []
        with mock.patch.object(y.ops_notify, "notify",
                               side_effect=lambda s, b, **k: sent.append(("n", k)) or True), \
             mock.patch.object(y.ops_notify, "resolve",
                               side_effect=lambda scope, s, b, **k: sent.append(("r", scope)) or True):
            y.deliver(y.evaluate(INCIDENT, EXHAUSTED, SECRET))
            self.assertEqual([k for k, _ in sent], ["n", "n"])
            self.assertTrue(all(kw.get("dedupe_key") for _, kw in sent))
            sent.clear()
            y.deliver(y.evaluate([run("2026-11-01", 900, 3)], HEALTHY, SECRET))
            self.assertEqual(sorted(s for _, s in sent),
                             sorted([y.KEY_PAID_READS, y.KEY_ZERO_POSTS]))

    def test_unknown_key_state_never_resolves_the_paid_reads_alarm(self):
        sent = []
        with mock.patch.object(y.ops_notify, "notify", return_value=True), \
             mock.patch.object(y.ops_notify, "resolve",
                               side_effect=lambda scope, s, b, **k: sent.append(scope)):
            y.deliver(y.evaluate([], None, ""))
        self.assertNotIn(y.KEY_PAID_READS, sent)
        self.assertNotIn(y.KEY_ZERO_POSTS, sent)


class ItMakesNoModelCall(unittest.TestCase):
    """ingest-silence.yml holds the OpenRouter key and is EXEMPT from the
    degrade step (test_spend_guard), so this module must never spend it."""

    def test_it_makes_no_model_call(self):
        with open(os.path.join(RAILWAY, "ingest_yield.py"), encoding="utf-8") as fh:
            src = fh.read()
        for needle in ("/chat/completions", "chat.completions", "metered_call", "import openai"):
            self.assertNotIn(needle, src)


class TheWatchdogIsWired(unittest.TestCase):
    def test_ingest_silence_runs_it_with_the_mail_key_and_the_ledger_commit(self):
        path = os.path.join(RAILWAY, "..", ".github", "workflows", "ingest-silence.yml")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("ingest_yield.py", text)
        for needle in ("RESEND_API_KEY", "OPS_MAIL_FROM", "ALERT_STATE_COMMIT",
                       "contents: write", "OPENROUTER_API_KEY"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
