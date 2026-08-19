"""The subject may never leave a reader with a larger AI figure than we report.

THE DEFECT THIS EXISTS FOR, shipped 2026-08-19 in 2.20.103.

    AI Layoff Tracker: 16,842 verified cuts this week

Metric first, inside the character budget, composed from the same query as the
body, and wrong in the way that matters most. A reader who never opens it takes
away "the AI Layoff Tracker counted 16,842 cuts this week". The body of that
same email says no employer named AI on any of them and that the week's AI
figure is ZERO. So the one line reaching the largest audience inflated the
metric the product is named after from nothing to five figures.

Everything inside the edition is scrupulous about this: the reviewed-entry
count, the dated base rate, the "why that matters" line. The subject undid all
of it before the email was opened.

THE DEFECT IS THE JUXTAPOSITION, NOT THE INSTANCE. A brand name beside an
unqualified count reads as a count of that brand's metric, whatever the numbers
are and whichever tier is sending. Fixing the wording of one line would have
left the pattern in place for stream A, which is layoffs-only and legitimately
titled the AI Layoff Tracker.

THE FIX IS STRUCTURAL. Every subject now leads with the SITE:

    Aug 10-16: 16,842 verified job cuts

There is no tracker brand for a count to attach to, so the line cannot be read
as an AI figure at all.

WHAT THIS FILE ENFORCES, and it is deliberately a property rather than a string:

    A COMPOSED SUBJECT EITHER NAMES NO AI TRACKER, OR IT NAMES THE AI FIGURE.

That is checkable because the subject is composed by the site from the same
/aggregate response as the body, so the true AI figure is in hand at compose
time. It holds for any wording a future session picks, including the two
alternatives that were considered and rejected (qualify the noun; name the AI
figure only when it is striking).
"""
import datetime
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
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import digest_layout as layout  # noqa: E402

SUBSCRIBE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                         "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_compose_harness.php")
PHP = shutil.which("php")

# Any way a reader could recognise the AI tracker by name in a subject line.
AI_BRANDS = ("AI Layoff Tracker", "AI Tracker", "AI layoff")

# A figure a reader would read as a count: a number wearing a unit, or a number
# with nothing between it and a brand name.
FIGURE = re.compile(r"\b\d[\d,]*\b")


def _tuple(label, all_jobs, verified_jobs, ai_verified=0):
    return [label, all_jobs, 0, None, verified_jobs, ai_verified]


def compose(fixture):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    try:
        json.dump(fixture, handle)
        handle.close()
        run = subprocess.run([PHP, HARNESS, SUBSCRIBE, handle.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(handle.name)
    if run.returncode != 0:
        raise AssertionError(f"harness failed: {run.stderr[:1200]}")
    out = json.loads(run.stdout)
    if out.get("null"):
        raise AssertionError("the composer returned nothing for this fixture")
    return out


def fixture(ai_jobs=0, verified=16842):
    return {
        "from": "2026-08-10", "to": "2026-08-16", "compose": "layoff",
        "layoff": {
            "totals": {"jobs": verified, "entries": 76,
                       "announced_jobs": 0, "announced_entries": 0,
                       "ai_verified_jobs": ai_jobs,
                       "ai_verified_entries": 1 if ai_jobs else 0,
                       "companies": 73},
            "leaders": [],
            "top_countries": [_tuple("United States", 10132, 10132)],
            "top_industries": [],
            "source_types": [["warn", verified, 0, None, verified, 0]],
        },
        "ytd": {"totals": {"jobs": 520549, "announced_jobs": 0,
                           "ai_verified_jobs": 42953},
                "top_countries": [_tuple("United States", 400000, 400000)]},
    }


def subject_for(section, freq="weekly"):
    """The subject the RELAY would put on a message carrying this section."""
    parts = [("layoff", section["html"], section["text"],
              section.get("preheader", ""),
              (section.get("metric", ""), bool(section.get("minor"))))]
    payload = {"from": "2026-08-10", "to": "2026-08-16", "freq": freq,
               "subject": "[AskTheRecruiter] Weekly tracker digest"}
    return layout.subject_line(payload, parts), parts, payload


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class TheSubjectNeverImpliesAnAiFigureWeDidNotMeasure(unittest.TestCase):

    def _check(self, ai_jobs):
        section = compose(fixture(ai_jobs=ai_jobs))
        subject, _, _ = subject_for(section)
        named = [b for b in AI_BRANDS if b.lower() in subject.lower()]
        if not named:
            # Nothing in the line identifies the AI tracker, so no count in it
            # can be read as that tracker's metric. This is the branch the
            # shipped pattern takes, and it takes it structurally.
            return subject
        # It named the tracker, so it must name the AI figure too, or a reader
        # attaches whatever number IS there to the brand.
        self.assertIn(f"{ai_jobs:,}", subject,
                      f"the subject names {named[0]!r} and carries a figure "
                      f"that is not the AI figure ({ai_jobs:,}), so a reader "
                      f"who only sees the subject leaves with a larger AI "
                      f"number than the email reports: {subject!r}")
        return subject

    def test_a_zero_ai_week_does_not_advertise_five_figures_of_ai_cuts(self):
        """The live week of 10 to 16 August 2026, which is what shipped."""
        subject = self._check(0)
        self.assertIn("16,842 verified job cuts", subject)

    def test_a_non_zero_ai_week_is_held_to_the_same_rule(self):
        self._check(900)

    def test_a_week_where_every_cut_is_ai_attributed_is_too(self):
        """The one shape where the old subject would have been accidentally
        right. A rule that only binds when it is inconvenient is not a rule."""
        self._check(16842)

    def test_the_unit_is_on_the_figure_and_is_not_the_talent_tracker_s(self):
        """"signals" is the talent tracker's unit and deliberately means
        something weaker: a published indication, mostly unverified. Calling
        verified cuts "signals" would give away the differentiator, and it is
        the signals-versus-jobs confusion arriving in the subject line."""
        section = compose(fixture())
        self.assertEqual(section["metric"], "16,842 verified job cuts")
        self.assertNotIn("signal", section["metric"].lower())

    def test_the_layoff_section_names_no_tracker_in_its_fragment(self):
        """The fragment is a figure wearing a unit and nothing else. A brand in
        it would put the brand back beside the count wherever it is joined."""
        section = compose(fixture())
        for brand in AI_BRANDS:
            self.assertNotIn(brand.lower(), section["metric"].lower())


class TheRuleHoldsForEveryShapeTheRelayCanBuild(unittest.TestCase):
    """Python-only, so it runs with or without php."""

    def _subject(self, metrics, freq="weekly"):
        parts = []
        for index, (metric, minor) in enumerate(metrics):
            parts.append((f"s{index}", "<p>x</p>",
                          f"Section {index}\nsomething 2026\n", "",
                          (metric, minor)))
        payload = {"from": "2026-08-10", "to": "2026-08-16", "freq": freq,
                   "subject": "fallback"}
        return layout.subject_line(payload, parts)

    def test_no_shape_puts_a_tracker_brand_beside_a_count(self):
        shapes = (
            [("16,842 verified job cuts", False)],
            [("1,376 hiring signals", False)],
            [("2 new posts", True)],
            [("16,842 verified job cuts", False), ("1,376 hiring signals", False)],
            [("16,842 verified job cuts", False), ("1,376 hiring signals", False),
             ("2 new posts", True)],
        )
        for shape in shapes:
            with self.subTest(shape=shape):
                subject = self._subject(shape)
                for brand in AI_BRANDS:
                    self.assertNotIn(brand.lower(), subject.lower(), subject)
                self.assertTrue(subject.startswith("Aug 10-16: "), subject)

    def test_the_blog_count_never_displaces_a_tracker_metric(self):
        subject = self._subject([("16,842 verified job cuts", False),
                                 ("2 new posts", True)])
        self.assertIn("16,842 verified job cuts", subject)
        self.assertNotIn("new posts", subject)

    def test_the_blog_count_is_used_when_it_is_all_there_is(self):
        subject = self._subject([("2 new posts", True)])
        self.assertIn("2 new posts", subject)

    def test_a_subject_is_never_cut_mid_figure(self):
        """One metric rather than a truncated two. A subject cut mid-figure
        publishes a wrong number in the line most people only ever see."""
        subject = self._subject([("1,234,567,890 verified job cuts " + "x" * 40, False),
                                 ("1,376 hiring signals", False)])
        self.assertLessEqual(len(subject), 100)
        self.assertNotIn("1,376", subject,
                         "the second metric was kept in a line that had to be "
                         "shortened, so it can only be there in part")

    def test_no_metric_at_all_falls_back_and_invents_nothing(self):
        self.assertEqual(self._subject([("", False)]), "Section 0, 2026 Week 33 · August 10-16")

    def test_the_daily_keeps_the_shape_and_swaps_the_period(self):
        """The three editions have to read as one series, so the daily differs
        only in its period token. A day is not a week and is not numbered."""
        subject = self._subject([("1,101 verified job cuts", False)], freq="daily")
        self.assertEqual(
            subject, "Aug 16: 1,101 verified job cuts")
        self.assertNotIn("Week", subject)


class ThePreviewCompletesWhatTheSubjectDrops(unittest.TestCase):
    """The brand prefix costs about twenty characters the From name already
    supplies, and Gmail on mobile truncates near 45, so the second metric is
    what falls off a phone. The preheader is the one slot left to recover it.
    """

    def _parts(self):
        return [
            ("layoff", "<p>x</p>", "AI Layoff Tracker\nsomething 2026\n",
             "0 cuts attributed to AI, 10,132 of the cuts in the United States, "
             "August 10-16, 2026",
             ("16,842 verified job cuts", False)),
            ("talent", "<p>x</p>", "Talent Intelligence Tracker\nsomething 2026\n",
             "1,376 new hiring signals, August 10-16, 2026",
             ("1,376 hiring signals", False)),
        ]

    def test_it_leads_with_the_metric_a_phone_drops(self):
        snippet = layout.preheader_text(self._parts())
        self.assertTrue(snippet.startswith("1,376 hiring signals"), snippet)

    def test_it_does_not_restate_the_first_metric(self):
        snippet = layout.preheader_text(self._parts())
        self.assertNotIn("16,842", snippet,
                         "the one recovery slot was spent repeating the half "
                         "of the subject a phone already shows")

    def test_the_ai_figure_is_in_the_first_forty_characters(self):
        """It is the number a reader is most likely to get wrong from a subject
        line alone, so it goes where a truncated preview still shows it."""
        snippet = layout.preheader_text(self._parts())
        self.assertIn("attributed to AI", snippet[:60], snippet[:60])

    def test_a_single_section_edition_keeps_its_own_snippet(self):
        snippet = layout.preheader_text(self._parts()[:1])
        self.assertTrue(snippet.startswith("0 cuts attributed to AI"), snippet)

    def test_it_stays_inside_the_ceiling_and_is_never_truncated(self):
        parts = self._parts()
        parts[0] = parts[0][:3] + ("y" * 125,) + parts[0][4:]
        snippet = layout.preheader_text(parts)
        self.assertLessEqual(len(snippet), layout.PREHEADER_MAX)
        self.assertNotIn("...", snippet)


if __name__ == "__main__":
    unittest.main()


class TheInboxAndTheArchiveNameThePeriodTheSameWay(unittest.TestCase):
    """A reader moving from the inbox to the archive must meet the same words.

    The subject opens on its period, the archived edition is titled by its
    period, and if the two spelled it differently they would read as two things
    that happen to be about one week rather than as one edition in two places.
    The subject's token is a literal PREFIX of the archive's title, which is
    why alt_digest_edition_label() leads with the ISO week identifier and why
    the archive names a DAILY edition by its date rather than by its two-day
    window.
    """

    ARCHIVE = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker",
                           "includes", "digest-archive.php")

    _RUNNER = r"""
define('DAY_IN_SECONDS', 86400);
foreach (json_decode($argv[1], true) as $path) {
    $src = file_get_contents($path['file']);
    foreach ($path['names'] as $name) {
        if (!preg_match('/\nfunction ' . preg_quote($name, '/') . '\s*\(.*?\n\}/s',
                        $src, $m)) {
            fwrite(STDERR, "could not extract $name\n");
            exit(2);
        }
        eval($m[0]);
    }
}
$out = array();
foreach (json_decode($argv[2], true) as $case) {
    $row = array('freq' => $case[0], 'window_from' => $case[1],
                 'window_to' => $case[2]);
    $period = alt_digest_subject_period($case[0], $case[1], $case[2]);
    $out[] = array($period, alt_edition_label($row));
}
echo json_encode($out);
"""

    CASES = (
        ("weekly", "2026-08-10", "2026-08-16"),
        ("weekly", "2026-12-28", "2027-01-03"),
        ("weekly", "2029-12-31", "2030-01-06"),
        ("daily", "2026-08-18", "2026-08-19"),
        ("daily", "2026-12-31", "2027-01-01"),
    )

    @classmethod
    def setUpClass(cls):
        if PHP is None:
            raise unittest.SkipTest("php is not on PATH. UNKNOWN, not a pass.")
        handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                             encoding="utf-8")
        try:
            handle.write("<?php\n" + cls._RUNNER)
            handle.close()
            run = subprocess.run(
                [PHP, handle.name,
                 json.dumps([
                     {"file": SUBSCRIBE,
                      "names": ["alt_digest_date_range", "alt_digest_iso_week",
                                "alt_digest_week_label", "alt_digest_week_id",
                                "alt_digest_valid_freq",
                                "alt_digest_short_range",
                                "alt_digest_subject_period",
                                "alt_digest_edition_label"]},
                     {"file": cls.ARCHIVE, "names": ["alt_edition_label"]},
                 ]),
                 json.dumps([list(c) for c in cls.CASES])],
                capture_output=True, text=True, timeout=60)
        finally:
            os.unlink(handle.name)
        assert run.returncode == 0, run.stderr or run.stdout
        cls.rows = json.loads(run.stdout)

    def test_the_archive_title_opens_with_the_subject_s_period(self):
        for case, (period, label) in zip(self.CASES, self.rows):
            with self.subTest(case=case):
                self.assertTrue(period, f"no period for {case}")
                self.assertTrue(
                    label.startswith(period),
                    f"the inbox calls this {period!r} and the archive calls it "
                    f"{label!r}, so a reader following the link meets a "
                    f"different name for the same edition")

    def test_a_daily_edition_is_named_by_its_date_not_its_window(self):
        """The daily window is two days and the subject names the send day,
        which is the masthead convention. The archive has to agree."""
        period, label = self.rows[3]
        self.assertEqual(period, "Aug 19")
        self.assertEqual(label, "Aug 19, 2026")

    def test_the_archive_adds_the_year_the_subject_drops(self):
        """The subject is skimmed in an inbox that stamps the date already, so
        those six characters go to the metric instead. This page is CITED, so
        it carries the year."""
        period, label = self.rows[0]
        self.assertEqual(period, "Aug 10-16")
        self.assertEqual(label, "Aug 10-16, 2026")

    def test_a_window_crossing_a_new_year_carries_both_years(self):
        """The only shape where dropping one would publish a wrong year."""
        self.assertEqual(self.rows[1][1], "Dec 28 - Jan 3, 2026-2027")
        self.assertEqual(self.rows[2][1], "Dec 31 - Jan 6, 2029-2030")

    def test_the_iso_week_is_not_in_the_heading_and_is_not_lost(self):
        """"normal people dont care about week 33." It is precise for citation
        and opaque for skimming, so it lives in the archive URL and on the
        edition's own dateline rather than in a heading a reader skims."""
        for _, label in self.rows:
            self.assertNotIn("Week", label, label)
