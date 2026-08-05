"""Four wrong published numbers, pinned by RUNNING the code that published them.

All four were live on asktherecruiter.com on 2026-08-04 and none of them was
caught by a check. Three of the four sat inches from the number they
contradicted.

    1. THE IN-PROGRESS MONTH. The trend point for August summed the whole
       month, 35,362 verified cuts, under a caption reading "4 of 31 days so
       far" and beside a This-month card publishing 21,776. Only 21,776 had
       taken effect; the other 13,586 were on WARN notices filed for effective
       dates later in August. The 2.19.263 fix labelled the point partial and
       dashed it, which described the smaller number while drawing the larger
       one. A caption is not a fix.

    2. THE HERO'S PERIOD. "2026 YTD" and "so far, as of Aug 4, 2026" over a
       figure scoped to the whole calendar year, 33,939 of it dated ahead of
       today. The same page's FAQPage JSON-LD published the to-date figure,
       because alt_live_numbers() has always clamped at today. One document,
       two totals, one wording.

    3. THE US-STATE CARD. It reconciled a US-only chart against the WORLDWIDE
       verified total, so every non-US cut was charged to a US data-quality
       gap: 193,896 printed as missing where the honest figure was about
       89,848, and on the all-time view 2,383,032 against about 1,285,383.

    4. THE REASONS DOUGHNUT. Drawn on verified PLUS announced beside a
       verified-only headline, with no basis note, and the possible_ai slice
       drawn at 10,415 returned 124,793 when tapped because the reason filter
       was silently translated into ai_broad=1.

WHY THESE EXECUTE INSTEAD OF GREPPING. The same sweep found five checks in
these repos passing against defective code for the wrong reason, two of them
string checks that matched a comment describing a call rather than the call.
jsrun lifts the real function bodies out of layoffs.js and runs them in node,
and PHP_HARNESS below does the same for db.php through the php binary. Where a
check has to read source instead of running it, its docstring says so and says
why.
"""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import jsrun

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
JS = (PLUGIN / "assets/layoffs.js").read_text()
DB_PHP = (PLUGIN / "includes/db.php").read_text()
TRACKER_TPL = (PLUGIN / "templates/page-tracker.php").read_text()

PHP = shutil.which("php")

# The month the clock is inside, as the code computes it.
import datetime
_NOW = datetime.date.today()
NOW_KEY = "%04d-%02d" % (_NOW.year, _NOW.month)
PREV_KEY = "%04d-%02d" % ((_NOW.year, _NOW.month - 1) if _NOW.month > 1 else (_NOW.year - 1, 12))


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"^\s*//.*$", " ", text, flags=re.M)


# A month bucket shaped exactly like /aggregate's, with the live 2026-08 split.
PARTIAL_ROW = {
    "month": NOW_KEY,
    "jobs": 35692, "ai_jobs": 0,
    "verified_jobs": 35362, "announced_jobs": 330,
    "ai_verified_jobs": 0, "ai_announced_jobs": 0, "ai_broad_jobs": 0,
    "to_date": {
        "as_of": _NOW.isoformat(),
        "jobs": 22106, "ai_jobs": 0,
        "verified_jobs": 21776, "announced_jobs": 330,
        "ai_verified_jobs": 0, "ai_announced_jobs": 0, "ai_broad_jobs": 0,
    },
}
COMPLETED_ROW = {
    "month": PREV_KEY,
    "jobs": 55304, "ai_jobs": 400,
    "verified_jobs": 55304, "announced_jobs": 0,
    "ai_verified_jobs": 400, "ai_announced_jobs": 0, "ai_broad_jobs": 0,
}
SERIES = [COMPLETED_ROW, PARTIAL_ROW]


class TheInProgressMonthPlotsWhatItsCaptionClaims(unittest.TestCase):
    """Finding 1. Runs fillMonths(), the function every chart's series goes through."""

    def test_the_charted_point_is_the_to_date_total_not_the_whole_month(self):
        # renderTrend plots `s.verified_jobs != null ? s.verified_jobs : s.jobs`
        # off fillMonths()' output, so that is what this reads.
        out = jsrun.run(
            ["fillMonths", "periodAllowsMonth"],
            # Identity when the tree has no clamp, so a tree without one runs its
            # own fillMonths and gets caught on the value, not on a missing name.
            jsrun.BASE_PREAMBLE + "function toDateMonths(s) { return s; }\n",
            "fillMonths(%s).map(function (s) { return [s.month, (s.verified_jobs != null) ? s.verified_jobs : s.jobs]; })"
            % json.dumps(SERIES), optional=["toDateMonths"],
        )
        plotted = dict(out)
        self.assertIn(NOW_KEY, plotted, "the in-progress month must still be charted")
        self.assertEqual(
            plotted[NOW_KEY], PARTIAL_ROW["to_date"]["verified_jobs"],
            "the in-progress point must plot the cuts whose effective date has arrived "
            "(%d), not the whole month (%d). It is %d."
            % (PARTIAL_ROW["to_date"]["verified_jobs"], PARTIAL_ROW["verified_jobs"], plotted[NOW_KEY]),
        )
        self.assertEqual(
            plotted[PREV_KEY], COMPLETED_ROW["verified_jobs"],
            "a completed month must be untouched by the clamp",
        )

    def test_the_note_states_the_plotted_number_and_the_part_held_back(self):
        """The caption used to describe elapsed days over a value that was not
        elapsed days. Both figures must appear, and they must sum to the month."""
        note = jsrun.run(
            ["fillMonths", "periodAllowsMonth", "partialMonthAt", "partialNoteText", "nowMonthKey"],
            jsrun.BASE_PREAMBLE + "function toDateMonths(s) { return s; }\n",
            "(function () { var s = fillMonths(%s); return partialNoteText(partialMonthAt(s.map(function (r) { return r.month; }), s)); })()"
            % json.dumps(SERIES), optional=["toDateMonths"],
        )
        charted = PARTIAL_ROW["to_date"]["verified_jobs"]
        later = PARTIAL_ROW["verified_jobs"] - charted
        self.assertIn("{:,}".format(charted), note,
                      "the note must name the number the point actually plots: %r" % note)
        self.assertIn("{:,}".format(later), note,
                      "the note must name the part not yet in effect: %r" % note)
        self.assertEqual(charted + later, PARTIAL_ROW["verified_jobs"],
                         "the two figures in the note must sum to the month's verified total")

    def test_the_not_charted_caveat_counts_the_rest_of_this_month(self):
        """The card printed 'N future-dated jobs are not charted' while 13,586
        future-dated jobs sat inside the final plotted point."""
        n = jsrun.run(
            ["futureDatedJobs"], jsrun.BASE_PREAMBLE,
            "futureDatedJobs(%s)" % json.dumps(SERIES),
        )
        expected = PARTIAL_ROW["jobs"] - PARTIAL_ROW["to_date"]["jobs"]
        self.assertEqual(
            n, expected,
            "future-dated jobs must include the rest of the in-progress month (%d), got %d"
            % (expected, n),
        )


class TheHeroPeriodStampSaysWhatTheWindowIs(unittest.TestCase):
    """Finding 2. statPeriodLabel() is the function that wrote 'YTD'."""

    def test_the_current_year_filter_is_not_stamped_ytd(self):
        label = jsrun.run(
            ["statPeriodLabel", "currentPeriodLabel"], jsrun.BASE_PREAMBLE
            + "CONTROLS['alt-f-years'] = ['%d'];\n" % _NOW.year,
            "statPeriodLabel()",
        )
        self.assertEqual(
            label, str(_NOW.year),
            "a whole-calendar-year window may not be stamped YTD: it holds notices "
            "filed for effective dates still ahead. Got %r." % label,
        )

    def test_aggregate_totals_carry_the_to_date_pair(self):
        """Source check, and it has to be: the SELECT needs a database. It reads
        the SQL and the emitted array, not a comment (comments are stripped)."""
        sql = _strip_comments(DB_PHP)
        self.assertIn("to_date_jobs", sql)
        self.assertRegex(
            sql,
            r"COALESCE\(SUM\(CASE WHEN layoff_date <= '\$today_sql' THEN job_count END\),0\) to_date_jobs",
            "the to-date total must be summed with a clamp at today",
        )
        self.assertRegex(sql, r"'to_date_jobs'\s*=>", "the pair must reach the response")
        self.assertRegex(sql, r"'to_date_announced_jobs'\s*=>")

    def test_the_so_far_citeline_quotes_the_to_date_figure(self):
        """Source check: the citeline is PHP that needs WordPress to render.
        It reads the echoed expression, with comments stripped."""
        tpl = _strip_comments(TRACKER_TPL)
        line = [l for l in tpl.splitlines() if "so far, as of" in l]
        self.assertTrue(line, "the citeline sentence is gone")
        self.assertIn(
            "$alt_stat('to-date')", line[0],
            "a sentence reading 'so far, as of <today>' must quote the to-date figure, "
            "not the whole-window total: %s" % line[0].strip(),
        )


class TheStateCardReconcilesAgainstTheUnitedStates(unittest.TestCase):
    """Finding 3. Runs barBasisNote(), the function that printed the sentence."""

    TOTALS = {"jobs": 956769, "announced_jobs": 472301}   # worldwide verified 484,468
    US_VERIFIED = 340823
    STATE_ROWS = [["CA", 120000, 0, None], ["TX", 80000, 0, None], ["NY", 50975, 0, None]]

    def _note(self, scope_expr):
        return jsrun.run(
            ["barBasisNote"], jsrun.BASE_PREAMBLE + "var BARLIST_LIMIT = 24;\n",
            "barBasisNote(%s, %s, 'US state', false, %s)"
            % (json.dumps(self.TOTALS), json.dumps(self.STATE_ROWS), scope_expr),
        )

    def test_the_denominator_is_the_us_verified_total(self):
        note = self._note(json.dumps({
            "headline": self.US_VERIFIED, "of": "verified US cuts", "outside": "",
        }))
        world = self.TOTALS["jobs"] - self.TOTALS["announced_jobs"]
        self.assertIn("{:,}".format(self.US_VERIFIED), note,
                      "the US state card must reconcile against the US total: %r" % note)
        self.assertNotIn(
            "{:,}".format(world), note,
            "the US state card must not reconcile against the worldwide verified total "
            "(%s): %r" % ("{:,}".format(world), note),
        )

    def test_the_remainder_never_exceeds_the_us_total(self):
        note = self._note(json.dumps({
            "headline": self.US_VERIFIED, "of": "verified US cuts", "outside": "",
        }))
        drawn = sum(r[1] for r in self.STATE_ROWS)
        # Only the coverage sentence is US-scoped; the announced-tier sentence
        # before it legitimately quotes the worldwide announced figure.
        cover = note[note.index("These "):]
        printed = [int(x.replace(",", "")) for x in re.findall(r"[\d,]{4,}", cover)]
        self.assertIn(self.US_VERIFIED - drawn, printed,
                      "the stated remainder must be US total minus the drawn bars: %r" % note)
        for n in printed:
            self.assertLessEqual(
                n, self.US_VERIFIED,
                "no figure in the US state card's coverage sentence may exceed the US "
                "verified total: %r" % cover,
            )

    def test_the_caller_hands_the_state_card_its_own_scope(self):
        """Source check: the call site needs a rendered page. Comments stripped,
        so a comment naming the scope cannot satisfy it."""
        src = _strip_comments(JS)
        # One level of nesting allowed, because the call carries selectedList(...).
        m = re.search(r"barBasisNote\(barTotals,\s*stateRows,\s*'US state',(?:[^()]|\([^()]*\))*\)", src)
        self.assertIsNotNone(m, "the US state card no longer calls barBasisNote")
        self.assertIn("stateScope", m.group(0),
                      "the US state card must be given a scoped denominator: %s" % m.group(0))
        self.assertRegex(src, r"countryVerifiedTotal\(agg,\s*'United States'\)",
                         "the scope must come from the US row of top_countries")


class TheReasonsDoughnutDrawsAndFiltersOneThing(unittest.TestCase):
    """Finding 4. Runs renderReasons() and currentParams(), the two real paths."""

    # /aggregate's reasons shape: [tag, jobs, ai_jobs, null, verified, verified_ai]
    REASONS = [
        ["ai_automation", 108373, 108373, None, 45748, 45748],
        ["possible_ai", 10415, 0, None, 700, 0],
        ["restructuring", 200000, 0, None, 150000, 0],
    ]

    DOM = """
var DRAWN = null, NOTE = null;
var INK = { primary: '#000', secondary: '#000', muted: '#000', grid: '#000' };
var REASON_LABELS = { ai_automation: 'Reason tag: AI or automation', possible_ai: 'Reason tag: AI press-linked', restructuring: 'Restructuring' };
var document = { getElementById: function () { return {}; } };
function clearChart() { DRAWN = 'cleared'; }
function setBarBasisNote(id, txt) { NOTE = txt; }
function mountChart(id, cfg) { DRAWN = cfg; }
function toggleMultiFilter() {}
function refreshAll() {}
// Present only from 2.19.265. Declared here so the PRE-FIX renderReasons, which
// never calls it, still runs and can be caught drawing the wrong basis.
if (typeof reasonsBasisNote !== 'function') { var reasonsBasisNote = function () { return ''; }; }
"""

    def test_the_slices_are_the_verified_basis(self):
        drawn = jsrun.run(
            ["renderReasons", "verifiedBasis"],
            jsrun.BASE_PREAMBLE + self.DOM,
            "(function () { renderReasons(%s, 'alt-f-reasons', []); return DRAWN.data.datasets[0].data; })()"
            % json.dumps(self.REASONS), optional=["reasonsBasisNote"],
        )
        expected = sorted([r[4] for r in self.REASONS], reverse=True)
        self.assertEqual(
            drawn, expected,
            "the doughnut must draw the verified pair (%s), the same basis as the "
            "headline tile, not verified plus announced (%s)"
            % (expected, sorted([r[1] for r in self.REASONS], reverse=True)),
        )

    def test_the_card_carries_a_basis_note(self):
        note = jsrun.run(
            ["renderReasons", "verifiedBasis"],
            jsrun.BASE_PREAMBLE + self.DOM,
            "(function () { renderReasons(%s, 'alt-f-reasons', []); return NOTE; })()"
            % json.dumps(self.REASONS), optional=["reasonsBasisNote"],
        )
        self.assertTrue(note, "the reasons card must state its basis like every other card")
        self.assertIn("verified", note.lower())
        self.assertIn("not a breakdown of the total", note.lower(),
                      "a doughnut asserts a partition; these tags overlap, so it must say so")

    def test_tapping_a_reason_filters_to_that_reason(self):
        """The 12x defect: the possible_ai slice drew 10,415 and returned 124,793."""
        params = jsrun.run(
            ["currentParams", "multiParam"],
            jsrun.BASE_PREAMBLE + "var DATE_BASIS = 'effective';\nCONTROLS['alt-f-reasons'] = ['possible_ai'];\n",
            "currentParams()",
        )
        self.assertEqual(
            params.get("reasons"), "possible_ai",
            "selecting a reason tag must filter by that reason tag, got %r" % params,
        )
        self.assertNotIn(
            "ai_broad", params,
            "a reason-tag selection must not become a broad-AI filter: the slice drew "
            "the tag's total and the filter returned the flag column's, about twelve "
            "times larger. Got %r" % params,
        )

    def test_the_broad_measure_keeps_its_own_control(self):
        params = jsrun.run(
            ["currentParams", "multiParam"],
            jsrun.BASE_PREAMBLE + "var DATE_BASIS = 'effective';\nCONTROLS['alt-f-ai-broad'] = true;\n",
            "currentParams()",
        )
        self.assertEqual(params.get("ai_broad"), "1",
                         "the broad AI measure must still be reachable, on its own filter")


PHP_HARNESS = r"""
<?php
// Stubs for the WordPress plumbing alt_api_quality_status() touches. Nothing
// under test is stubbed: alt_source_health_masked, alt_retired_sources and
// alt_api_quality_status are the real bodies, lifted off disk below.
$GLOBALS['OPTIONS'] = json_decode(getenv('ALT_TEST_OPTIONS'), true);
function get_option($k, $d = false) { return $GLOBALS['OPTIONS'][$k] ?? $d; }
function sanitize_key($k) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $k)); }
function rest_ensure_response($x) { return new AltTestResponse($x); }
function alt_api_integrity_status() { return new AltTestResponse(array('status' => 'stub')); }
class AltTestResponse { public $d; function __construct($d) { $this->d = $d; } function get_data() { return $this->d; } }
%s
$r = alt_api_quality_status();
echo json_encode($r->get_data()['source_health']);
"""


def _php_fn(name, required=True):
    """Source of one top-level `function <name>(` in db.php, brace-matched.

    `required=False` returns '' when the name is absent, so the same harness can
    be pointed at a tree from before a helper existed and still run that tree's
    OWN handler. Otherwise the test would abort on a missing symbol, which
    proves a rename, not a defect.
    """
    needle = "function %s(" % name
    start = DB_PHP.find(needle)
    if start == -1 and not required:
        return ""
    assert start != -1, "db.php has no `%s`" % needle
    i = DB_PHP.index("{", start)
    depth, j = 0, i
    while j < len(DB_PHP):
        if DB_PHP[j] == "{":
            depth += 1
        elif DB_PHP[j] == "}":
            depth -= 1
            if depth == 0:
                return DB_PHP[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces extracting %s" % name)


@unittest.skipUnless(PHP, "php is not installed; cannot execute db.php")
class QualityStatusMasksRetiredCollectors(unittest.TestCase):
    """Finding 5, from the same sweep. EXECUTES alt_api_quality_status().

    /source-health returned newsapi, edinet_jp, opendart_kr and cvm_br as
    'retired' while /quality-status returned all four as 'ok' at the same
    instant, because one reader applied alt_retired_sources() and the other read
    the option raw. The public Health page fetches /quality-status, so the
    transparency page was the one showing retired collectors as live: exactly
    the failure this repo raised to an iron rule, arriving through a second
    reader instead of a second writer.
    """

    OPTIONS = {
        "alt_source_health": {
            # checked_at BEFORE the retirement date, like the live rows.
            "newsapi": {"status": "ok", "entries": 113, "checked_at": "2026-07-27T11:03:40+00:00"},
            "edinet_jp": {"status": "ok", "entries": 0, "checked_at": "2026-07-23T22:10:10+00:00"},
            "gdelt": {"status": "ok", "entries": 40, "checked_at": "2026-08-04T02:00:00+00:00"},
        },
        "alt_corrections_log": [],
        "alt_data_ver": 7,
    }

    def _run(self):
        import os
        bodies = "\n".join(filter(None, (
            _php_fn("alt_retired_sources"),
            _php_fn("alt_source_health_masked", required=False),
            _php_fn("alt_api_quality_status"),
        )))
        env = dict(os.environ, ALT_TEST_OPTIONS=json.dumps(self.OPTIONS))
        proc = subprocess.run([PHP, "-r", (PHP_HARNESS % bodies).replace("<?php", "", 1)],
                              capture_output=True, text=True, env=env)
        if proc.returncode != 0:
            raise AssertionError("php failed:\n%s" % proc.stderr.strip())
        return json.loads(proc.stdout)

    def test_retired_collectors_are_not_published_as_ok(self):
        health = self._run()
        for src in ("newsapi", "edinet_jp"):
            self.assertEqual(
                health[src]["status"], "retired",
                "/quality-status published the retired collector %s as %r; the public "
                "Health page renders this endpoint" % (src, health[src]["status"]),
            )

    def test_a_live_collector_is_untouched(self):
        health = self._run()
        self.assertEqual(health["gdelt"]["status"], "ok",
                         "masking must not touch a collector that is still running")

    def test_the_real_last_run_timestamp_survives_masking(self):
        health = self._run()
        self.assertEqual(health["newsapi"]["checked_at"], "2026-07-27T11:03:40+00:00",
                         "fabricating a fresh checked_at would claim a months-idle "
                         "collector was checked just now")

    def test_no_public_reader_of_the_health_option_skips_the_mask(self):
        """Source check over every PHP file: a runtime check cannot see a reader
        that does not exist yet. Comments are stripped first."""
        offenders = []
        for path in sorted(PLUGIN.rglob("*.php")):
            src = _strip_comments(path.read_text())
            for m in re.finditer(r"get_option\(\s*'alt_source_health'", src):
                # The writer reads it to merge one row back in; that is the one
                # legitimate raw read, and it is inside the masked function too.
                window = src[max(0, m.start() - 900):m.start()]
                fn = re.findall(r"function (\w+)\(", window)
                if fn and fn[-1] in ("alt_source_health_masked", "alt_source_health_record"):
                    continue
                offenders.append("%s: %s" % (path.name, fn[-1] if fn else "?"))
        self.assertEqual(
            offenders, [],
            "every public reader of alt_source_health must go through "
            "alt_source_health_masked(); raw readers: %s" % offenders,
        )


if __name__ == "__main__":
    unittest.main()
