"""The week number is ISO-8601, and the ISO year is not the calendar year.

WHY THE NUMBER EXISTS AT ALL. The owner read a live send whose subject said
"the week to August 19, 2026", off a rolling seven days ending on the send day.
That is a Wednesday-to-Wednesday window: it belongs to no week anybody
recognises, its last two days were still filling up while the email described
them, and it can carry no number a reader can check. He asked for a week
number and, on being shown that ISO weeks start on Monday, settled on ISO.

WHY ISO RATHER THAN A SUNDAY START. ISO is the international standard, the
number is correct by definition rather than by convention, and this is a
worldwide tracker. A Sunday-start week would have needed a second, US-specific
numbering rule (the CDC's MMWR convention is the only published one) that
disagrees with ISO for one day of every week, and two conventions in one
product is how a reader ends up unable to tell which week they are holding.

THE DEFECT THIS FILE EXISTS TO CATCH. ISO week 1 is the week holding the first
Thursday of January, so the ISO year and the calendar year disagree for a few
days every year: January 1, 2027 is a Friday in week 53 of ISO year 2026, and
December 31, 2029 is a Monday in week 1 of ISO year 2030. PHP spells them `W`
and `o`; `Y` beside `W` is the bug. Python spells them with
`date.isocalendar()`, whose member 0 is the ISO year and is NOT `date.year`.

That defect ships silently and is found the following January, which is why it
is pinned here with real boundary dates in both directions and in both
implementations.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import digest_layout as layout  # noqa: E402

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
PHP = shutil.which("php")

_WANTED = ("alt_digest_date_range", "alt_digest_iso_week",
           "alt_digest_week_label", "alt_digest_edition_label",
           "alt_digest_weekly_window", "alt_digest_valid_freq",
           "alt_digest_window")

_RUNNER = r"""
define('DAY_IN_SECONDS', 86400);
$src = file_get_contents($argv[1]);
foreach (explode(',', $argv[2]) as $name) {
    if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                    $src, $m)) {
        fwrite(STDERR, "could not extract $name from subscribe.php\n");
        exit(2);
    }
    eval($m[0]);
}
$in = json_decode($argv[3], true);
$out = array();
foreach ($in['labels'] as $pair) {
    $out['labels'][] = alt_digest_edition_label($pair[0], $pair[1]);
}
foreach ($in['weeks'] as $day) {
    $out['weeks'][] = alt_digest_week_label($day);
}
foreach ($in['windows'] as $stamp) {
    $out['windows'][] = alt_digest_window('weekly', strtotime($stamp . ' UTC'));
}
foreach ($in['dailies'] as $stamp) {
    $out['dailies'][] = alt_digest_window('daily', strtotime($stamp . ' UTC'));
}
echo json_encode($out);
"""


def php(payload):
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write("<?php\n" + _RUNNER)
        handle.close()
        run = subprocess.run([PHP, handle.name, SUBSCRIBE, ",".join(_WANTED),
                              json.dumps(payload)],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"php runner failed: {run.stderr[:1200]}")
    return json.loads(run.stdout)


# (first day of the window, last day, the label both sides must produce).
# Every one of these was worked out from the calendar, not from the code.
EDITIONS = (
    ("2026-08-10", "2026-08-16", "Week 33 \u00b7 August 10-16, 2026"),
    ("2026-08-03", "2026-08-09", "Week 32 \u00b7 August 3-9, 2026"),
    # A window that straddles a month, so the range shape changes too.
    ("2026-08-31", "2026-09-06", "Week 36 \u00b7 August 31 - September 6, 2026"),
    # THE BOUNDARY, FORWARD. January 1, 2027 is a Friday, so this Monday to
    # Sunday week is week 53 of ISO YEAR 2026 while three of its days are in
    # calendar 2027.
    ("2026-12-28", "2027-01-03", "Week 53 \u00b7 December 28, 2026 - January 3, 2027"),
    # THE BOUNDARY, BACKWARD. December 31, 2029 is a Monday and opens week 1 of
    # ISO year 2030, while the calendar year is still 2029.
    ("2029-12-31", "2030-01-06", "Week 1 \u00b7 December 31, 2029 - January 6, 2030"),
    # A 53-week ISO year, read at its end.
    ("2020-12-28", "2021-01-03", "Week 53 \u00b7 December 28, 2020 - January 3, 2021"),
)

# (a UTC instant a run could start at, the window a WEEKLY edition reports).
WINDOWS = (
    # The intended send: Monday, reporting the week that closed yesterday.
    ("2026-08-17 13:10:00", ["2026-08-10", "2026-08-16"]),
    # Forced with DIGEST_FREQ on another day. Still the last COMPLETE week,
    # never a window starting on whatever day the run happens to fire.
    ("2026-08-19 04:00:00", ["2026-08-10", "2026-08-16"]),
    ("2026-08-23 23:59:00", ["2026-08-10", "2026-08-16"]),
    # A Monday that opens an ISO year, reporting week 53 of the one before.
    ("2027-01-04 13:10:00", ["2026-12-28", "2027-01-03"]),
)


class ThePythonSideIsISO(unittest.TestCase):
    """Runs with or without php, because the relay composes the masthead and
    the subject and must be right on its own."""

    def test_the_iso_year_is_read_and_not_the_calendar_year(self):
        for first, last, label in EDITIONS:
            with self.subTest(first=first):
                start = datetime.date.fromisoformat(first)
                end = datetime.date.fromisoformat(last)
                self.assertEqual(
                    f"{layout.week_label(start)} \u00b7 {layout.date_range(start, end)}",
                    label)

    def test_the_edition_phrase_is_the_label(self):
        payload = {"from": "2026-12-28", "to": "2027-01-03", "freq": "weekly"}
        self.assertEqual(layout.period_phrase(payload),
                         "Week 53 \u00b7 December 28, 2026 - January 3, 2027")

    def test_a_daily_edition_carries_no_week_number(self):
        """A day is not a week, and numbering one would be a label a reader
        cannot check against anything."""
        payload = {"from": "2026-08-17", "to": "2026-08-18", "freq": "daily"}
        self.assertEqual(layout.period_phrase(payload), "August 18, 2026")
        self.assertNotIn("Week", layout.period_phrase(payload))

    def test_the_number_never_travels_without_its_dates(self):
        """A bare "Week 33" is a label a reader has to look up, and two
        readers on two conventions look it up differently."""
        for first, last, label in EDITIONS:
            self.assertRegex(label, r"^Week \d+ \u00b7 .*\d{4}$")


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheTwoImplementationsAgree(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.out = php({
            "labels": [[a, b] for a, b, _ in EDITIONS],
            "weeks": [a for a, _, _ in EDITIONS],
            "windows": [stamp for stamp, _ in WINDOWS],
            "dailies": ["2026-08-19 04:00:00"],
        })

    def test_the_site_and_the_relay_label_a_week_identically(self):
        for (first, last, label), got in zip(EDITIONS, self.out["labels"]):
            with self.subTest(first=first):
                self.assertEqual(got, label,
                                 "the in-WordPress sender and the relay would "
                                 "put different week numbers on one edition")

    def test_the_weekly_window_is_the_previous_complete_iso_week(self):
        for (stamp, expected), got in zip(WINDOWS, self.out["windows"]):
            with self.subTest(stamp=stamp):
                self.assertEqual(got, expected)
                start = datetime.date.fromisoformat(got[0])
                end = datetime.date.fromisoformat(got[1])
                self.assertEqual(start.isoweekday(), 1,
                                 "an ISO week starts on a Monday")
                self.assertEqual(end.isoweekday(), 7,
                                 "an ISO week ends on a Sunday")
                self.assertEqual((end - start).days, 6)
                self.assertLess(end, datetime.datetime.fromisoformat(stamp).date(),
                                "the window is not complete at send time")

    def test_the_daily_window_did_not_move(self):
        """The daily tier covers yesterday and today, is provisional by design
        and says so. Fixing the weekly edition must not have changed it."""
        self.assertEqual(self.out["dailies"][0], ["2026-08-18", "2026-08-19"])


if __name__ == "__main__":
    unittest.main()
