"""The AI cumulative chart must select and start on the value it draws.

THE DEFECT, as it was live. `/aggregate` reports three AI numbers per month:
`ai_jobs` (verified PLUS announced), `ai_verified_jobs` and
`ai_announced_jobs`. `renderAiCumulative` gated on `ai_jobs > 0` and scanned
for its start index on `ai_jobs > 0`, and then plotted the VERIFIED value. So
a month whose AI cuts were only announced passed the gate, became the first
point of the series, and drew the verified trend beginning on a flat zero.

This is not hypothetical and the fixtures below are not invented. They are the
live response of
`/aggregate?from=2024-01-01&to=2024-12-31` and `/aggregate?years=2026`, read on
2026-08-15. January 2024 carries ai_jobs 8,000, ai_verified_jobs 0,
ai_announced_jobs 8,000, and the chart opened on it.

HOW THESE TESTS RUN. Through tests/jsrun.py, which lifts the real function
bodies out of layoffs.js and evaluates them in node. The renderer under test is
the one on disk, byte for byte; only the page plumbing is stubbed. The two
accessors are passed as `optional` so this module can also be pointed at a tree
from BEFORE they existed: there, the tree's own renderer runs and the
assertions fail on the wrong months it actually draws, rather than on a missing
symbol.

WHAT MUST NOT MOVE. The owner's instruction was "no number changes, the trend
just begins where the data actually begins". That is a testable claim and
`PlottedNumbersDoNotMove` is where it is tested: every cumulative value drawn
must equal the running total taken from the START OF THE SERIES, not from the
start of the chart window. If the running totals were restarted at the window,
moving the start index would silently move the announced band down by every
announced job that preceded the first verified month.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jsrun import BASE_PREAMBLE, JS_PATH, run  # noqa: E402

JS = JS_PATH.read_text()


# ---------------------------------------------------------------------------
# Real payloads. Trimmed to the fields the charts read, values untouched.
# ---------------------------------------------------------------------------

# /aggregate?from=2024-01-01&to=2024-12-31 - the view that exposed the defect:
# its FIRST AI month is announced-only.
LIVE_2024 = [
    {"month": "2024-01", "jobs": 123694, "verified_jobs": 79795, "ai_jobs": 8000, "ai_verified_jobs": 0, "ai_announced_jobs": 8000},
    {"month": "2024-02", "jobs": 102197, "verified_jobs": 44348, "ai_jobs": 700, "ai_verified_jobs": 700, "ai_announced_jobs": 0},
    {"month": "2024-03", "jobs": 128817, "verified_jobs": 73257, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-04", "jobs": 87482, "verified_jobs": 54051, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-05", "jobs": 69197, "verified_jobs": 48597, "ai_jobs": 600, "ai_verified_jobs": 600, "ai_announced_jobs": 0},
    {"month": "2024-06", "jobs": 62296, "verified_jobs": 43379, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-07", "jobs": 70678, "verified_jobs": 27158, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-08", "jobs": 91465, "verified_jobs": 69365, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-09", "jobs": 72483, "verified_jobs": 26274, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
    {"month": "2024-10", "jobs": 71407, "verified_jobs": 20157, "ai_jobs": 500, "ai_verified_jobs": 500, "ai_announced_jobs": 0},
    {"month": "2024-11", "jobs": 88431, "verified_jobs": 27555, "ai_jobs": 459, "ai_verified_jobs": 459, "ai_announced_jobs": 0},
    {"month": "2024-12", "jobs": 106120, "verified_jobs": 36589, "ai_jobs": 0, "ai_verified_jobs": 0, "ai_announced_jobs": 0},
]

# /aggregate?years=2026, completed months only. Its first AI month IS verified,
# so this view must come out of the change with every point where it was: it is
# the regression bar on "no published number changes".
LIVE_2026 = [
    {"month": "2026-01", "jobs": 157067, "verified_jobs": 62331, "ai_jobs": 5150, "ai_verified_jobs": 5150, "ai_announced_jobs": 0},
    {"month": "2026-02", "jobs": 96464, "verified_jobs": 38421, "ai_jobs": 6650, "ai_verified_jobs": 6000, "ai_announced_jobs": 650},
    {"month": "2026-03", "jobs": 206963, "verified_jobs": 97019, "ai_jobs": 23000, "ai_verified_jobs": 2400, "ai_announced_jobs": 20600},
    {"month": "2026-04", "jobs": 134514, "verified_jobs": 72034, "ai_jobs": 23130, "ai_verified_jobs": 22000, "ai_announced_jobs": 1130},
    {"month": "2026-05", "jobs": 122974, "verified_jobs": 50171, "ai_jobs": 19310, "ai_verified_jobs": 200, "ai_announced_jobs": 19110},
    {"month": "2026-06", "jobs": 79822, "verified_jobs": 56765, "ai_jobs": 2225, "ai_verified_jobs": 1350, "ai_announced_jobs": 875},
    {"month": "2026-07", "jobs": 123950, "verified_jobs": 82575, "ai_jobs": 10006, "ai_verified_jobs": 5153, "ai_announced_jobs": 4853},
]

# The degenerate view the fix must not delete: AI plans announced, none of them
# verified yet. Real rows, from the same 2024 response, with the verified
# months dropped.
ANNOUNCED_ONLY = [LIVE_2024[0], LIVE_2024[2], LIVE_2024[3]]


PREAMBLE = BASE_PREAMBLE + """
var MOUNTED = null, CLEARED = [], RANGE_TEXT = null;
var ALT_RED = '#d55e00', ALT_AMBER = '#e69f00';
function tok(name, fallback) { return fallback; }
function compareSelections() { return null; }
function mountChart(id, config) { MOUNTED = { id: id, config: config }; }
function clearChart(id) { CLEARED.push(id); }
function cloneOptions() {
    return { scales: { y: { ticks: {} } }, plugins: { tooltip: { callbacks: {} }, legend: {} } };
}
var ELEMENTS = {
    'alt-chart-ai-cumulative': { id: 'alt-chart-ai-cumulative' },
    'alt-cum-range': { set textContent(v) { RANGE_TEXT = v; }, get textContent() { return RANGE_TEXT; } }
};
var document = { getElementById: function (id) { return ELEMENTS[id] || null; } };
function drawn(series) {
    MOUNTED = null; CLEARED = []; RANGE_TEXT = null;
    renderAiCumulative(series);
    if (!MOUNTED) return { cleared: CLEARED, range: RANGE_TEXT, datasets: null };
    return {
        cleared: CLEARED,
        range: RANGE_TEXT,
        labels: MOUNTED.config.data.labels,
        datasets: MOUNTED.config.data.datasets.map(function (d) { return { label: d.label, data: d.data }; })
    };
}
"""

REAL = ["renderAiCumulative", "fillMonths", "toDateMonths", "periodAllowsMonth"]
OPTIONAL = ("aiVerifiedJobs", "aiAnnouncedJobs")


def draw(series):
    return run(REAL, PREAMBLE, "drawn(%s)" % json.dumps(series), optional=OPTIONAL)


def cumulative(series, field):
    """Running total of `field` from the START OF THE SERIES, by month."""
    out, run_total = {}, 0
    for row in series:
        run_total += row[field]
        out[row["month"]] = run_total
    return out


def label(month_key):
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return "%s %s" % (names[int(month_key[5:]) - 1], month_key[:4])


class GateMatchesTheLine(unittest.TestCase):
    def test_an_announced_only_month_is_not_charted_as_a_verified_point(self):
        # Jan 2024: ai_jobs 8,000, ai_verified_jobs 0. Under the old gate it
        # was the chart's first point and the verified line opened flat on it.
        got = draw(LIVE_2024)
        self.assertIsNotNone(got["datasets"], "the 2024 view drew no chart at all")
        verified = got["datasets"][0]
        self.assertEqual(
            verified["label"], "AI-attributed (verified)",
            "the first dataset is meant to be the verified line")
        self.assertNotIn(
            label("2024-01"), got["labels"],
            "Jan 2024 has ai_verified_jobs 0 and is charted on the verified "
            "line anyway: the gate is reading ai_jobs (verified PLUS "
            "announced) while the line draws the verified value")
        self.assertGreater(
            verified["data"][0], 0,
            "the verified line opens on %s at %s, a point with nothing "
            "verified behind it" % (got["labels"][0], verified["data"][0]))

    def test_the_verified_line_starts_at_the_first_verified_month(self):
        got = draw(LIVE_2024)
        self.assertEqual(
            got["labels"][0], label("2024-02"),
            "the first month with any verified AI cuts is Feb 2024 (700); the "
            "chart starts on %s" % got["labels"][0])
        self.assertEqual(got["datasets"][0]["data"][0], 700)

    def test_the_range_caption_names_the_month_the_line_begins(self):
        # The caption is the same claim in words, and it was reading off the
        # same wrong index.
        self.assertEqual(draw(LIVE_2024)["range"], "since " + label("2024-02"))

    def test_a_view_whose_first_ai_month_is_verified_is_untouched(self):
        got = draw(LIVE_2026)
        self.assertEqual(got["labels"][0], label("2026-01"))
        self.assertEqual(got["range"], "since " + label("2026-01"))
        self.assertEqual(len(got["labels"]), len(LIVE_2026))


class TheAnnouncedBandSurvives(unittest.TestCase):
    def test_the_band_is_still_drawn_and_still_says_announced(self):
        got = draw(LIVE_2024)
        self.assertEqual(
            len(got["datasets"]), 2,
            "the announced band is gone; the 2024 view holds 8,000 announced "
            "AI cuts and they have nowhere else on this chart to appear")
        announced = got["datasets"][1]
        self.assertIn("Announced", announced["label"])
        self.assertNotIn("verified", announced["label"].lower().replace("announced", ""))

    def test_a_view_with_only_announced_plans_still_draws_its_band(self):
        # Nothing here is verified, so a gate that read the verified value and
        # stopped would clear the card and publish "no AI cuts" over 8,000
        # announced ones.
        got = draw(ANNOUNCED_ONLY)
        self.assertIsNotNone(
            got["datasets"],
            "an announced-only view cleared the chart entirely (cleared: %s)"
            % got["cleared"])
        self.assertEqual(got["labels"][0], label("2024-01"))
        self.assertEqual(got["datasets"][-1]["data"][0], 8000)
        self.assertIn("Announced", got["datasets"][-1]["label"])


class PlottedNumbersDoNotMove(unittest.TestCase):
    """The owner's hard bar: the trend may begin later, no value may change.

    Every drawn point is checked against the running total taken from the
    start of the SERIES. A renderer that restarted its running totals at the
    chart window would pass every test above and fail these, because moving
    the start index would have moved the announced band down by the 8,000
    announced jobs that precede the first verified month.
    """

    def _check(self, series):
        got = draw(series)
        want_v = cumulative(series, "ai_verified_jobs")
        want_a = cumulative(series, "ai_announced_jobs")
        by_label = {label(row["month"]): row["month"] for row in series}
        for i, lab in enumerate(got["labels"]):
            month = by_label[lab]
            self.assertEqual(
                got["datasets"][0]["data"][i], want_v[month],
                "verified cumulative at %s is %s, series says %s"
                % (lab, got["datasets"][0]["data"][i], want_v[month]))
            if len(got["datasets"]) > 1:
                self.assertEqual(
                    got["datasets"][1]["data"][i], want_a[month],
                    "announced cumulative at %s is %s, series says %s"
                    % (lab, got["datasets"][1]["data"][i], want_a[month]))

    def test_every_point_in_the_2024_view_equals_the_series_running_total(self):
        self._check(LIVE_2024)

    def test_every_point_in_the_2026_view_equals_the_series_running_total(self):
        self._check(LIVE_2026)

    def test_the_2026_totals_are_the_published_ones(self):
        # 42,253 verified is the figure the signal board's own comment quotes
        # for AI-attributed jobs in 2026; if this moves, something published
        # moved with it.
        got = draw(LIVE_2026)
        self.assertEqual(got["datasets"][0]["data"][-1], 42253)
        self.assertEqual(got["datasets"][1]["data"][-1], 47218)


class OneDefinition(unittest.TestCase):
    """Five hand-written copies of two accessors is how this drifted apart.

    These pin the collapse rather than the fix, because the fix survives only
    while there is one definition. A sixth copy written next year would draw
    correctly on the day it was written and is exactly the shape of the defect.
    """

    def _accessor(self, name):
        needle = "function %s(" % name
        if needle not in JS:
            raise AssertionError(
                "layoffs.js has no `%s`: there is no single definition for "
                "the accessor to be the only copy of" % needle)
        start = JS.index(needle)
        depth, i = 0, JS.index("{", start)
        while True:
            if JS[i] == "{":
                depth += 1
            elif JS[i] == "}":
                depth -= 1
                if depth == 0:
                    return JS[start:i + 1]
            i += 1

    def _code_outside(self, bodies):
        """layoffs.js with the accessor bodies and all comments removed."""
        src = JS
        for body in bodies:
            src = src.replace(body, "")
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"(?m)^\s*//.*$", "", src)
        return src

    def test_the_two_accessors_exist_and_are_declared_once(self):
        for name in ("aiVerifiedJobs", "aiAnnouncedJobs"):
            self.assertEqual(
                JS.count("function %s(" % name), 1,
                "%s must be declared exactly once" % name)

    def test_the_split_fields_are_read_nowhere_else(self):
        outside = self._code_outside(
            [self._accessor("aiVerifiedJobs"), self._accessor("aiAnnouncedJobs")])
        for field in ("ai_verified_jobs", "ai_announced_jobs"):
            self.assertNotIn(
                field, outside,
                "%s is read outside the accessor that defines what it means; "
                "that is the second copy this fix exists to remove" % field)

    def test_the_cumulative_renderer_never_reads_ai_jobs(self):
        body = JS[JS.index("function renderAiCumulative("):]
        body = body[: body.index("\n    }\n")]
        body = re.sub(r"(?m)^\s*//.*$", "", body)
        self.assertNotIn(
            "ai_jobs", body,
            "renderAiCumulative is reading ai_jobs again; it is verified PLUS "
            "announced and this chart draws those two apart")


if __name__ == "__main__":
    unittest.main()
