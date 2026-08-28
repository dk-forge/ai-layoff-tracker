"""The DIGEST cadence sentences must agree with the schedule that makes them true.

THE DEFECT SHAPE (2026-08-28 nine-edition review, FIX 3). subscribe.php's
alt_digest_cadence_sentence hand-types "each morning", "Monday mornings" and
"at the start of each month", and includes/subscribe.php is not among
tests/test_cadence_is_derived.py's guarded surfaces - that rule is scoped to
INGEST cadence (railway.toml -> ingest-schedule.json). DIGEST cadence is
sourced from railway/digest_slot.py's SEND_TIMES, so a slot move there would
ship a stale promise silently: the exact failure the repo's cadence rule
exists to prevent, on a different clock.

THE RIGHT-SIZED FIX, deliberately NOT a cross-language cadence generator:
these tests DERIVE the phrasing facts from digest_slot.py (the daily slot is
unconditional, the weekly slot's weekday) and fail when subscribe.php's typed
sentences disagree. A slot move now reds CI instead of shipping a stale
promise, and the sentences stay sentences.

AND THE MONTHLY PROMISE MUST NOT RENDER WHILE THE TIER IS UNWIRED.
alt_digest_cadence_sentence already carries "Monthly editions go out at the
start of each month" for the day the tier is armed. SEND_TIMES schedules no
monthly tick and alt_digest_monthly_enabled() ships false, so no reader may
meet that sentence yet: alt_digest_accepted_freq refuses to STORE an
unoffered monthly (a hand-crafted POST is the only way to ask for one - the
form shows weekly/daily radios only), which is what keeps the confirm panel's
promise and the schedule telling one story. Both directions are held here:
the coercion while dormant, and the pass-through once the offer filter is on
- so arming later is flipping the filter beside the new slot, not a rewrite.

The gate/behaviour cases run the real PHP by extraction and SKIP without php
on PATH, which is not a pass. The fact checks are pure source reads and
always run.
"""
import calendar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
PHP = shutil.which("php")

if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_slot  # noqa: E402

WEEKDAY_NAMES = tuple(calendar.day_name)  # Monday..Sunday


def _source():
    with open(SUBSCRIBE, encoding="utf-8") as handle:
        return handle.read()


def _cadence_sentences():
    """The three typed sentences, keyed by the branch that returns them.

    Extraction fails loudly on a rename or a restructure rather than testing
    a stale copy, exactly like the subject-agreement lifter.
    """
    src = _source()
    match = re.search(r"function alt_digest_cadence_sentence\(.*?\n\}",
                      src, re.S)
    assert match, "alt_digest_cadence_sentence not found in subscribe.php"
    body = match.group(0)
    out = {}
    for freq in ("daily", "monthly"):
        branch = re.search(r"\$freq === '" + freq +
                           r"'.*?return\s+'([^']+)';", body, re.S)
        assert branch, f"no {freq} branch in alt_digest_cadence_sentence"
        out[freq] = branch.group(1)
    tail = re.findall(r"return\s+'([^']+)';", body)
    assert tail, "no final return in alt_digest_cadence_sentence"
    out["weekly"] = tail[-1]
    return out


def _tiers():
    """{tier: weekday-or-None} out of digest_slot.SEND_TIMES."""
    return {tier: weekday for tier, weekday in digest_slot.SEND_TIMES.values()}


class TheTypedSentencesMatchTheSchedule(unittest.TestCase):

    def test_the_daily_promise_is_true_seven_days_a_week(self):
        tiers = _tiers()
        self.assertIn("daily", tiers,
                      "subscribe.php promises a daily digest 'each morning' "
                      "but digest_slot.py schedules no daily slot; fix the "
                      "sentence in alt_digest_cadence_sentence in the same "
                      "change")
        self.assertIsNone(
            tiers["daily"],
            "the daily slot gained a weekday restriction in digest_slot.py; "
            "'each morning, so your first one arrives tomorrow' in "
            "alt_digest_cadence_sentence is now a stale promise - update it "
            "in the same change")
        sentence = _cadence_sentences()["daily"]
        self.assertIn("each morning", sentence)
        self.assertIn("tomorrow", sentence)

    def test_the_weekly_promise_names_the_scheduled_weekday(self):
        tiers = _tiers()
        self.assertIn("weekly", tiers, "no weekly slot in digest_slot.py")
        weekday = tiers["weekly"]
        self.assertIsNotNone(weekday, "the weekly slot lost its weekday")
        expected = WEEKDAY_NAMES[weekday - 1]  # ISO 1 = Monday
        sentence = _cadence_sentences()["weekly"]
        self.assertIn(
            expected, sentence,
            f"digest_slot.py sends the weekly on {expected} but "
            f"alt_digest_cadence_sentence promises a different day - the "
            f"stale-promise defect this test exists to red")
        for other in WEEKDAY_NAMES:
            if other != expected:
                self.assertNotIn(other, sentence,
                                 f"the weekly sentence names {other}, which "
                                 f"is not the scheduled weekday")

    def test_no_weekday_is_typed_into_the_daily_sentence(self):
        sentence = _cadence_sentences()["daily"]
        for name in WEEKDAY_NAMES:
            self.assertNotIn(name, sentence)

    def test_the_monthly_slot_and_the_monthly_offer_arm_together(self):
        """The dormant-tier invariant, in both directions.

        A monthly slot in SEND_TIMES with the offer still off is a send no
        subscriber asked for; the offer on with no slot is a promise no job
        fulfils. alt_digest_monthly_enabled's shipped default and the
        schedule must flip in the same change (its own comment says so).
        """
        offered = re.search(
            r"apply_filters\('alt_digest_offer_monthly',\s*(true|false)\)",
            _source())
        self.assertTrue(offered, "alt_digest_monthly_enabled's filter "
                                 "default not found in subscribe.php")
        offered_default = offered.group(1) == "true"
        self.assertEqual(
            "monthly" in _tiers(), offered_default,
            "digest_slot.py's monthly slot and subscribe.php's "
            "alt_digest_offer_monthly default disagree; arm or disarm both "
            "in the same change")


class TheIntakeIsWiredThroughTheGate(unittest.TestCase):
    """Source-level: the two places a frequency is stored must ask
    alt_digest_accepted_freq, or the gate below tests nothing."""

    def test_the_signup_intake_uses_accepted_freq(self):
        src = _source()
        body = re.search(r"function alt_digest_prefs_from_post\(.*?\n\}",
                         src, re.S)
        self.assertTrue(body, "alt_digest_prefs_from_post not found")
        self.assertIn("alt_digest_accepted_freq", body.group(0),
                      "the signup intake stores a frequency without the "
                      "unoffered-monthly gate")

    def test_the_parked_prefs_restore_uses_accepted_freq(self):
        src = _source()
        # The confirm path that applies parked pending_prefs to the row.
        parked = re.search(r"\$parked\[\$cols\['freq'\]\].*?;", src, re.S)
        self.assertTrue(parked, "the parked-prefs freq restore not found")
        self.assertIn("alt_digest_accepted_freq", parked.group(0),
                      "parked preferences can smuggle an unoffered monthly "
                      "past the intake gate")


_GATE_RUNNER = r"""
// $argv[3] is 'on' to force the offer filter true, anything else leaves the
// shipped default in charge.
function apply_filters($tag, $value) {
    global $FORCE_ON;
    if ($FORCE_ON && $tag === 'alt_digest_offer_monthly') return true;
    return $value;
}
$FORCE_ON = (($argv[3] ?? '') === 'on');
$src = file_get_contents($argv[1]);
foreach (explode(',', $argv[2]) as $name) {
    if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                    $src, $m)) {
        fwrite(STDERR, "could not extract $name from subscribe.php\n");
        exit(2);
    }
    eval($m[0]);
}
echo json_encode(array(
    'accepted_monthly' => alt_digest_accepted_freq('monthly'),
    'accepted_daily'   => alt_digest_accepted_freq('daily'),
    'accepted_junk'    => alt_digest_accepted_freq('bogus'),
    'sentence'         => alt_digest_cadence_sentence(
                              alt_digest_accepted_freq('monthly')),
));
"""

_GATE_FNS = ("alt_digest_valid_freq", "alt_digest_monthly_enabled",
             "alt_digest_accepted_freq", "alt_digest_cadence_sentence")


def run_gate(force_on):
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write("<?php\n" + _GATE_RUNNER)
        handle.close()
        run = subprocess.run([PHP, handle.name, SUBSCRIBE,
                              ",".join(_GATE_FNS),
                              "on" if force_on else "off"],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"php runner failed: {run.stderr[:1200]}")
    return json.loads(run.stdout)


@unittest.skipIf(PHP is None, "php is not on PATH, so the gate could not be "
                              "run. UNKNOWN, not a pass.")
class TheMonthlyPromiseWaitsForTheOffer(unittest.TestCase):

    def test_an_unoffered_monthly_cannot_be_stored(self):
        out = run_gate(force_on=False)
        self.assertEqual(out["accepted_monthly"], "weekly")
        self.assertEqual(out["accepted_daily"], "daily")
        self.assertEqual(out["accepted_junk"], "weekly")

    def test_the_dormant_tier_never_shows_its_promise(self):
        # The confirm panel's sentence for whatever a monthly request really
        # stored: it must not say "Monthly" while the tier is unwired.
        out = run_gate(force_on=False)
        self.assertNotIn("Monthly", out["sentence"])
        self.assertNotIn("start of each month", out["sentence"])

    def test_arming_the_offer_lets_monthly_through_with_its_promise(self):
        # The other direction, so arming later is a filter flip and not a
        # rewrite: with the offer on, monthly stores as monthly and the
        # sentence is the monthly one.
        out = run_gate(force_on=True)
        self.assertEqual(out["accepted_monthly"], "monthly")
        self.assertIn("start of each month", out["sentence"])
        self.assertIn("month so far", out["sentence"])


if __name__ == "__main__":
    unittest.main()
