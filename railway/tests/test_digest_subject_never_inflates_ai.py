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
                self.assertTrue(subject.endswith(" · Aug 10-16"), subject)

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
            subject, "1,101 verified job cuts · Aug 16")
        self.assertNotIn("Week", subject)


class ThePreviewAddsAndNeverRepeats(unittest.TestCase):
    """The one rule a preview line has, and the owner caught us breaking it.

    His Gmail iOS screenshot showed four editions in a list. Two of the three
    standalone streams had a preview that restated the subject:

        1,376 hiring signals · Aug 10-16
          1376 new hiring signals, August 10-1...

        2 new posts · Aug 10-16
          2 posts published between August 1...

    A preview is the ONE recovery slot a reader gets before deciding whether to
    open. Spending it on a sentence already on screen wastes it entirely. So
    every composer now writes a snippet carrying the facts its own subject
    cannot: the AI figure and the United States split for the layoff tracker,
    the verified split for the talent tracker, the newest post's title for the
    blog.
    """

    def _parts(self):
        return [
            ("layoff", "<p>x</p>", "AI Layoff Tracker\nsomething 2026\n",
             "0 cuts attributed to AI, 10,132 in the United States, "
             "across 73 companies.",
             ("16,842 verified job cuts", False)),
            ("talent", "<p>x</p>", "Talent Intelligence Tracker\nsomething 2026\n",
             "411 of 1,376 verified against a primary document, "
             "from 288 companies.",
             ("1,376 hiring signals", False)),
        ]

    def _payload(self):
        return {"from": "2026-08-10", "to": "2026-08-16", "freq": "weekly",
                "subject": "fallback"}

    def test_no_figure_in_the_preview_is_already_in_the_subject(self):
        parts = self._parts()
        subject = layout.subject_line(self._payload(), parts)
        snippet = layout.preheader_text(parts)
        # The METRICS only. The trailing period token is a date and its
        # numerals ("Aug 10-16") are not figures a preview could restate.
        metrics_part = subject.rsplit(" · ", 1)[0]
        for figure in re.findall(r"\b\d[\d,]*\b", metrics_part):
            self.assertNotIn(
                figure, snippet,
                f"{figure!r} is in the subject AND the preview, so the one "
                f"recovery slot a reader gets was spent repeating it")

    def test_the_preview_carries_the_ai_figure_the_subject_cannot(self):
        snippet = layout.preheader_text(self._parts())
        self.assertIn("attributed to AI", snippet)

    def test_the_period_is_not_repeated_in_the_preview(self):
        """The subject trails the period and the inbox stamps the date, so a
        window in the preview is the third copy of one fact in two lines."""
        snippet = layout.preheader_text(self._parts())
        self.assertNotIn("Aug 10-16", snippet)
        self.assertNotIn("August 10-16", snippet)

    def test_a_single_section_edition_keeps_its_own_snippet(self):
        snippet = layout.preheader_text(self._parts()[:1])
        self.assertTrue(snippet.startswith("0 cuts attributed to AI"), snippet)

    def test_it_stays_inside_the_ceiling_and_is_never_truncated(self):
        parts = self._parts()
        parts[0] = parts[0][:3] + ("y" * 125,) + parts[0][4:]
        snippet = layout.preheader_text(parts)
        self.assertLessEqual(len(snippet), layout.PREHEADER_MAX)
        self.assertNotIn("...", snippet)


class EveryFigureIsFormattedTheSameWayOnEverySurface(unittest.TestCase):
    """A figure rendered two ways in one message, side by side in a list.

    The owner's inbox screenshot showed `1,376` in a subject beside `1376` in
    its own preview, and `16,842` beside `10132`. Both strings are composed by
    the site through number_format_i18n, and this session could NOT reproduce
    the unformatted rendering from the code: nothing between composition and
    the wire strips a separator. The cause is therefore UNKNOWN and may be the
    client's own snippet extraction.

    What is checkable is the property, so the property is pinned here: a figure
    appearing in more than one composed string is spelled identically in all of
    them. If a future edit ever formats one surface differently, this fails
    rather than shipping two spellings of one number.
    """

    def test_a_figure_in_two_composed_strings_is_spelled_once(self):
        parts = [
            ("layoff", "<p>x</p>", "AI Layoff Tracker\nx 2026\n",
             "411 of 1,376 verified against a primary document.",
             ("1,376 hiring signals", False)),
        ]
        payload = {"from": "2026-08-10", "to": "2026-08-16", "freq": "weekly",
                   "subject": "fallback"}
        subject = layout.subject_line(payload, parts)
        snippet = layout.preheader_text(parts)
        # 1376 appears in both. It must wear its separator in both.
        self.assertIn("1,376", subject)
        self.assertIn("1,376", snippet)
        for line in (subject, snippet):
            self.assertNotRegex(
                line, r"(?<![\d,])\d{4,}(?![\d,])",
                f"a four-digit-or-longer figure is missing its thousands "
                f"separator: {line!r}")

    def test_the_layout_module_never_reformats_a_site_figure(self):
        """It joins strings the site composed and computes nothing, which is
        why the two surfaces cannot disagree about a separator."""
        source = open(os.path.join(RAILWAY, "digest_layout.py"),
                      encoding="utf-8").read()
        self.assertNotIn("{:,}", source)
        self.assertNotIn("format(", source.split("def subject_line")[1]
                         .split("def preheader_text")[0])
