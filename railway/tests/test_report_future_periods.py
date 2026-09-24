"""A FUTURE quarter or week is not a report and must not be indexable.

alt_report_period_identity() already rejected a future year and a future
month, but accepted ?period=2026-Q4 (and any week) while that period had not
yet begun, so a crawler could mint a self-canonical, indexable, empty report
page. The quarter and week branches now apply the same "not later than the
current one" rule as the month branch; anything later falls through to
'invalid' (the existing noindex path).

Runs the real PHP (the include file with WordPress stubbed out). Dates are
computed from the clock so the test never becomes a date bomb.
"""
import datetime as dt
import shutil
import subprocess
import unittest
from pathlib import Path

SEO = (Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
       / "includes" / "report-seo.php")


def _classify(periods):
    src = "<?php\n" + r"""
define('ABSPATH', '/');
function add_filter() {} function add_action() {}
function sanitize_text_field($s) { return trim($s); }
function wp_unslash($s) { return $s; }
require '""" + str(SEO) + r"""';
foreach (array_slice($argv, 1) as $p) {
    $_GET = array('period' => $p);
    $id = alt_report_period_identity();
    echo $p, ' ', $id['kind'], "\n";
}
"""
    p = subprocess.run(["php", "-r", src[5:], "--"] + list(periods),
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return dict(line.split(" ", 1) for line in p.stdout.strip().splitlines())


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class FuturePeriods(unittest.TestCase):
    def test_quarters_and_weeks(self):
        today = dt.datetime.now(dt.timezone.utc).date()
        q = (today.month - 1) // 3 + 1
        nq_y, nq = (today.year + 1, 1) if q == 4 else (today.year, q + 1)
        iy, iw, _ = today.isocalendar()
        nxt = today + dt.timedelta(days=7)
        ny, nw, _ = nxt.isocalendar()
        cur_q, next_q = f"{today.year}-Q{q}", f"{nq_y}-Q{nq}"
        cur_w, next_w = f"{iy}-W{iw:02d}", f"{ny}-W{nw:02d}"
        far_w = f"{today.year + 1}-W10"
        got = _classify([cur_q, next_q, f"{today.year - 1}-Q4", cur_w, next_w,
                         far_w, "2020-W05"])
        self.assertEqual(got[cur_q], "quarter")
        self.assertEqual(got[f"{today.year - 1}-Q4"], "quarter")
        self.assertEqual(got[next_q], "invalid", "a future quarter was accepted")
        self.assertEqual(got[cur_w], "week")
        self.assertEqual(got["2020-W05"], "week")
        self.assertEqual(got[next_w], "invalid", "a future week was accepted")
        self.assertEqual(got[far_w], "invalid")


if __name__ == "__main__":
    unittest.main()
