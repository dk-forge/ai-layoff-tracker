"""THE BOARD'S SIX PERIODS: THE TWO NEW ONES, THEIR LABELS, AND THE PHONE.

The owner asked for two more columns on the at-a-glance board, a COMPLETED
calendar month and a COMPLETED calendar quarter, and then asked the one
question that decides how they have to be built: do the labels update by
themselves?

WHY THE LABELS ARE WHAT THIS FILE MOSTLY MEASURES.

  A literal "July 2026" typed into page-tracker.php is correct until the first
  of September and silently wrong afterwards, with nothing on the page, in CI
  or in the data checks able to notice. That is the same class of defect as a
  published figure with no guard under it, and the answer is the same: compute
  it, and prove the computation moves. So every label is derived from the
  period's OWN from/to rather than from a second reading of the clock (a label
  cannot then disagree with the window above which it sits, not even in the
  seconds around midnight on New Year's Eve), and the tests below inject four
  clocks -- mid-quarter, the first day of a quarter, the first day of a year,
  and a leap February -- and assert every label and every window moves.

WHY THE LABELS SAY "JULY 2026" AND NOT "LAST MONTH".

  The date presets below this board are ROLLING windows and already say "Last
  30 days" and "Last quarter". A completed calendar quarter labelled "Last
  quarter" would put two meanings behind one phrase on one page, which is the
  ambiguity the 2.20.22 entries rename had just removed. Naming the period is
  also what a journalist quotes. The current month is named for the same
  reason: one column naming its period beside one that does not is the same
  defect, smaller. Today and This week keep their words, because they are
  unambiguous and a date over a single day reads as a dateline.

WHY THE SIZING IS MEASURED AND NOT ASSUMED.

  Four columns fit a 375px phone. Six do not. Measured, before any fix, with
  the obvious `repeat(6, minmax(0, 1fr))`: each track came out 46px, "483,788"
  is 48px, and the three largest figures in the Workers row ran into each other
  and read as one string -- while `page.scrollWidth === page.clientWidth` was
  perfectly true and nothing bled. This repo has a documented incident where
  that same equality held over a tracker rendering in 219px of a 375px phone,
  which is why the checks below are on the usable width, on the board's own
  scroll box, and on whether each rendered NUMBER still sits inside its own
  cell -- never on the equality alone.

WHAT WAS ACTUALLY WRONG WITH THE LARGEST-ENTRY CELLS.

  Not overflow, not clipping, not the number squeezed out of view. The name was
  a single nowrap line with text-overflow: ellipsis, and in a 74px column that
  rendered "Les Antoniennes de Marie" as "Les Anto..." -- seven characters of a
  company name. The fix does not ellipsize better; it stops truncating the name
  at all (it wraps, with overflow-wrap: anywhere so no spelling can overflow a
  column). A two-line -webkit-line-clamp was built first and measured out: it
  cuts at two lines but only paints its ellipsis when the cut falls mid-line,
  so "Gruppo Manifatturiero Lombardo S.p.A." came back as "Gruppo
  Manifatturiero" with no marker at all, which is a board cell quietly renaming
  an employer.

  The count is never what goes. It is its own element below the name, outside
  anything that clips, and RenderedCells reads it back out of every cell at
  both widths.

PROVEN RED ON THE PRE-CHANGE TREE. Run against the tree this change starts
from (the four plugin files and the board fixture reverted, this file left in
place): 19 failures and 1 error out of 23. The distinct assertions, verbatim:

    AssertionError: db.php has no `function alt_signal_board_labels(`
    AssertionError: Lists differ: ['today', 'week', 'month', 'ytd'] !=
        ['today', 'week', 'month', 'pmonth', 'pquarter', 'ytd']
    AssertionError: 4 != 6 : the board rendered 4 period columns, not six:
        ['TODAY', 'THIS WEEK', 'THIS MONTH', '2026 YTD']
    AssertionError: Regex didn't match: '^[a-z]+ \\d{4}$' not found in
        'this month' : the current-month column is 'THIS MONTH', which does
        not name its period while the column beside it does
    AssertionError: False is not true : at 375px the board does not scroll, so
        its six columns were squeezed into 318px instead. That is how the
        numbers ran together.
    AssertionError: True is not false : at 375px the employer name 'Les
        Antoniennes de Marie' is cut off. It used to be cut to seven characters
        with an ellipsis; a silent cut is worse, because the shortened name
        reads as the whole one.
    AssertionError: 4 != 6 : at 375px only 4 largest-entry cells rendered
    AssertionError: ... page-tracker.php tells a reader the columns overlap but
        names only the week-inside-month case, and the two new columns overlap
        too
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))

import jsrun  # noqa: E402
from cdp import Browser, CDPUnavailable, find_chrome  # noqa: E402
import contrast_audit  # noqa: E402

PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
DB = PLUGIN / "includes/db.php"
JS = PLUGIN / "assets/layoffs.js"
CSS = PLUGIN / "assets/layoffs.css"
TEMPLATE = PLUGIN / "templates/page-tracker.php"
BOARD_BODY = Path(__file__).resolve().parent / "fixtures/signal_board_body.html"

PHP = shutil.which("php")

# The column order the board publishes, which is the order the two renderers
# have to agree on: it is the key order of the period map in both of them.
ORDER = ["today", "week", "month", "pmonth", "pquarter", "ytd"]

# Four clocks, chosen for what each one can break.
#   mid-quarter   the ordinary case
#   quarter start the completed quarter is the one that just ended, and the
#                 completed month sits INSIDE it
#   year start    every completed window is in the PREVIOUS year, and only the
#                 YTD column stays in this one
#   leap February the completed month is a 29-day one
CLOCKS = {
    "mid_quarter":   ("2026-08-13", {
        "month": ("2026-08-01", "2026-08-13"), "pmonth": ("2026-07-01", "2026-07-31"),
        "pquarter": ("2026-04-01", "2026-06-30"), "ytd": ("2026-01-01", "2026-08-13"),
        "labels": {"month": "August 2026", "pmonth": "July 2026",
                   "pquarter": "Q2 2026", "ytd": "2026 YTD"}}),
    "quarter_start": ("2026-04-01", {
        "month": ("2026-04-01", "2026-04-01"), "pmonth": ("2026-03-01", "2026-03-31"),
        "pquarter": ("2026-01-01", "2026-03-31"), "ytd": ("2026-01-01", "2026-04-01"),
        "labels": {"month": "April 2026", "pmonth": "March 2026",
                   "pquarter": "Q1 2026", "ytd": "2026 YTD"}}),
    "year_start":    ("2027-01-01", {
        "month": ("2027-01-01", "2027-01-01"), "pmonth": ("2026-12-01", "2026-12-31"),
        "pquarter": ("2026-10-01", "2026-12-31"), "ytd": ("2027-01-01", "2027-01-01"),
        "labels": {"month": "January 2027", "pmonth": "December 2026",
                   "pquarter": "Q4 2026", "ytd": "2027 YTD"}}),
    "leap_march":    ("2028-03-05", {
        "month": ("2028-03-01", "2028-03-05"), "pmonth": ("2028-02-01", "2028-02-29"),
        "pquarter": ("2027-10-01", "2027-12-31"), "ytd": ("2028-01-01", "2028-03-05"),
        "labels": {"month": "March 2028", "pmonth": "February 2028",
                   "pquarter": "Q4 2027", "ytd": "2028 YTD"}}),
}


# --------------------------------------------------------------------------
# Lifting the two renderers out and RUNNING them. Neither half is read as
# source: a regex cannot tell a call from a comment describing a call, and
# both of these compute dates.
# --------------------------------------------------------------------------

def _php_block(needle):
    src = DB.read_text()
    start = src.index(needle)
    i = src.index("{", start)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[start:j + 1]
        j += 1
    raise AssertionError("unbalanced braces lifting %r out of db.php" % needle)


def php_board(day):
    """{periods, labels} as the SERVER builds them, for a chosen day."""
    for needle in ("function alt_signal_board_periods(",
                   "function alt_signal_board_labels("):
        if needle not in DB.read_text():
            raise AssertionError("db.php has no `%s`" % needle)
    script = (
        "date_default_timezone_set('UTC');\n"
        "function current_time($f) { return $f === 'timestamp' ? %d : date($f, %d); }\n"
        "%s\n%s\n"
        "$p = alt_signal_board_periods();\n"
        "echo json_encode(array('periods' => $p, 'labels' => alt_signal_board_labels($p)));\n"
        % (_epoch(day), _epoch(day),
           _php_block("function alt_signal_board_periods("),
           _php_block("function alt_signal_board_labels(")))
    out = subprocess.run([PHP, "-r", script], capture_output=True, text=True)
    if out.returncode != 0:
        raise AssertionError("php failed:\n%s" % out.stderr.strip())
    return json.loads(out.stdout)


def _epoch(day):
    import calendar
    import datetime
    d = datetime.datetime.strptime(day, "%Y-%m-%d")
    return calendar.timegm(d.replace(hour=12).timetuple())


def months_full():
    """The real array out of layoffs.js, so a rename fails here loudly."""
    src = JS.read_text()
    m = re.search(r"var MONTHS_FULL = (\[[^\]]*\]);", src, re.S)
    if not m:
        raise AssertionError("layoffs.js has no `var MONTHS_FULL = [`")
    return m.group(1)


def js_board(day):
    """{windows, labels} as the BROWSER builds them, for the same day."""
    pre = ("var MONTHS_FULL = %s;\nfunction pad2(n) { return (n < 10 ? '0' : '') + n; }\n"
           "var NOW = new Date(%s, %s, %s, 12, 0, 0);\n"
           % (months_full(), day[:4], int(day[5:7]) - 1, int(day[8:10])))
    return jsrun.run(
        ["boardWindows", "boardColumnLabels"], pre,
        "(function () { var w = boardWindows(NOW);"
        " return { windows: w, labels: boardColumnLabels(w) }; })()")


# --------------------------------------------------------------------------
# 1. The two new periods exist, on both paths, and are whole periods.
# --------------------------------------------------------------------------

@unittest.skipUnless(PHP, "php binary not available")
class TheTwoCompletedPeriods(unittest.TestCase):

    def setUp(self):
        self.board = php_board("2026-08-13")

    def test_the_completed_month_is_a_period_of_its_own(self):
        self.assertIn(
            "pmonth", sorted(self.board["periods"]),
            "the board has no completed-month column")
        self.assertEqual(
            (self.board["periods"]["pmonth"]["from"],
             self.board["periods"]["pmonth"]["to"]),
            ("2026-07-01", "2026-07-31"),
            "the completed-month column is not the whole of the month before")

    def test_the_completed_quarter_is_a_period_of_its_own(self):
        self.assertIn(
            "pquarter", sorted(self.board["periods"]),
            "the board has no completed-quarter column")
        self.assertEqual(
            (self.board["periods"]["pquarter"]["from"],
             self.board["periods"]["pquarter"]["to"]),
            ("2026-04-01", "2026-06-30"),
            "the completed-quarter column is not the whole of the quarter "
            "before")

    def test_they_are_whole_periods_and_every_other_column_is_still_cut(self):
        """The reason these two are worth adding, stated as an assertion.

        A window running past today carries cuts that have not happened, so
        every to-date column is cut at today. A COMPLETED month and quarter end
        before today and cannot carry a future, which is exactly why they can
        span in full.

        THE CUT SURVIVED THE BASIS MOVE, and that was the question that decided
        whether the move could happen at all. The hazard was stated as an
        effective-date one: rows dated by effective date, WARN notices filed
        weeks ahead. `notice` is COALESCE(announcement_date, layoff_date), so
        the obvious reading is that a filing-basis board cannot be ahead of
        itself and this cut becomes redundant. It is not: a row with no
        evidenced announcement date falls back to its effective date and is
        still filed weeks ahead. Measured live on 2026-08-13, verified rows
        dated after today: 37,902 jobs on the effective basis, 21,712 on the
        filing basis, of which only 8 carry a real future announcement_date.
        Half the future, not none. Uncutting any of these columns would
        publish it.
        """
        p, today = self.board["periods"], "2026-08-13"
        for k in ("today", "week", "month", "ytd"):
            self.assertEqual(
                p[k]["to"], today,
                "the %s column runs past today, so it can publish cuts that "
                "have not happened yet" % k)
        for k in ("pmonth", "pquarter"):
            self.assertLess(
                p[k]["to"], today,
                "the %s column is supposed to be a COMPLETED period and it "
                "reaches today" % k)

    def test_every_column_counts_on_the_pages_own_basis(self):
        """ONE PAGE, ONE BASIS.

        These columns used to name no basis, so the server counted them on its
        default column, layoff_date, the EFFECTIVE date, while the headline
        figure inches above counted by filing date. Two correct totals
        answering two questions on one screen, with only a footnote between
        them, and the owner of the page could not reconcile them.

        The shape rule is unchanged and still asserted: same stage, one key
        set, no column with a rule of its own. What changed is that the key set
        now HAS to contain the basis, on every column and on the same value.
        """
        for k, p in self.board["periods"].items():
            self.assertEqual(
                sorted(p), ["date_basis", "from", "stage", "to"],
                "the %s column's params are %r. Every column carries exactly "
                "from/to/stage/date_basis, or the columns stop being one "
                "question asked over six windows." % (k, p))
            self.assertEqual(p["stage"], "verified",
                             "the %s column counts on a different stage" % k)
            self.assertEqual(
                p["date_basis"], "notice",
                "the %s column counts on %r, not on the page's own default "
                "(the filing basis). A board on a second basis is the defect "
                "this move exists to remove." % (k, p["date_basis"]))

    def test_the_basis_is_the_same_one_the_page_bootstraps_on(self):
        """Not "a basis": THE page's basis, read off the bootstrap rather than
        typed here twice. A board pinned to a constant that no longer matches
        the page default is the same defect wearing the fix's clothes."""
        src = DB.read_text()
        boot = src[src.index("$aggregate_params = array("):]
        boot = boot[:boot.index(");") + 2]
        m = re.search(r"'date_basis'\s*=>\s*'(\w+)'", boot)
        self.assertIsNotNone(
            m, "alt_page_bootstrap() no longer names a date_basis, so the "
               "board has nothing to be pinned to")
        for k, p in self.board["periods"].items():
            self.assertEqual(
                p.get("date_basis"), m.group(1),
                "the %s column counts on %r while the page bootstraps on %r"
                % (k, p.get("date_basis"), m.group(1)))

    def test_the_column_order_is_the_one_the_owner_reads(self):
        self.assertEqual(
            list(self.board["periods"]), ORDER,
            "the board's columns are in the wrong order, so the completed "
            "periods do not sit beside the running ones they qualify")


# --------------------------------------------------------------------------
# 2. THE LABELS. Computed, and proved to move.
# --------------------------------------------------------------------------

@unittest.skipUnless(PHP, "php binary not available")
class TheLabelsAreComputed(unittest.TestCase):

    def test_the_labels_move_with_the_clock(self):
        """Four clocks, including a year rollover and a leap February."""
        for name, (day, want) in CLOCKS.items():
            got = php_board(day)["labels"]
            for key, label in want["labels"].items():
                self.assertEqual(
                    got[key], label,
                    "on %s (%s) the %s column is labelled %r and should be "
                    "%r. A label that does not move with the clock is a "
                    "hardcoded one." % (day, name, key, got[key], label))

    def test_the_relative_labels_stay_relative(self):
        for day, _ in CLOCKS.values():
            got = php_board(day)["labels"]
            self.assertEqual(got["today"], "Today")
            self.assertEqual(got["week"], "This week")

    def test_no_label_is_written_down_in_the_template(self):
        """The template must not contain a month name or a quarter of its own.

        This is the defect being prevented, in its literal form: a typed
        "July 2026" that goes wrong on 1 September with nothing to catch it.
        """
        src = re.sub(r"/\*.*?\*/", "", TEMPLATE.read_text(), flags=re.S)
        src = "\n".join(l for l in src.splitlines()
                        if not l.lstrip().startswith("//"))
        board = src[src.index("$alt_board_periods ="):src.index("$alt_sb_head =")]
        for month in ("January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November",
                      "December"):
            self.assertNotIn(
                month, board,
                "page-tracker.php types the month name %r into the board's "
                "column labels" % month)
        self.assertNotRegex(
            board, r"'Q[1-4] ",
            "page-tracker.php types a quarter into the board's column labels")
        self.assertIn(
            "alt_signal_board_labels", board,
            "the template no longer takes its labels from the one function "
            "that derives them from the windows")

    def test_a_label_cannot_disagree_with_the_window_above_which_it_sits(self):
        """The labels are a function of the PERIODS, not of a second clock.

        Passing a period map through and getting labels for THAT map back is
        the property; a labeller that reads the clock again could disagree
        with the windows it is labelling (midnight on 31 December).
        """
        got = php_board("2026-08-13")
        forced = json.loads(json.dumps(got["periods"]))
        forced["pmonth"] = {"from": "2025-11-01", "to": "2025-11-30",
                            "stage": "verified"}
        script = (
            "date_default_timezone_set('UTC');\n"
            "function current_time($f) { return $f === 'timestamp' ? %d : date($f, %d); }\n"
            "%s\n%s\n"
            "echo json_encode(alt_signal_board_labels(json_decode('%s', true)));\n"
            % (_epoch("2026-08-13"), _epoch("2026-08-13"),
               _php_block("function alt_signal_board_periods("),
               _php_block("function alt_signal_board_labels("),
               json.dumps(forced)))
        out = subprocess.run([PHP, "-r", script], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(
            json.loads(out.stdout)["pmonth"], "November 2025",
            "the completed-month label ignored the window it was given and "
            "read the clock instead, so the two can disagree")

    def test_no_label_carries_a_dash(self):
        """House rule, and short labels slip past style_check.py."""
        for day, _ in CLOCKS.values():
            for k, v in php_board(day)["labels"].items():
                for bad in ("—", "–"):
                    self.assertNotIn(bad, v, "%s label %r" % (k, v))

    def test_the_labels_do_not_reuse_the_rolling_presets_words(self):
        """"Last month" / "Last quarter" already mean ROLLING windows on this
        page. A completed calendar period may not borrow the phrase."""
        for day, _ in CLOCKS.values():
            labels = [v.lower() for v in php_board(day)["labels"].values()]
            for phrase in ("last month", "last quarter", "previous month",
                           "previous quarter"):
                self.assertNotIn(
                    phrase, labels,
                    "a completed calendar column is labelled %r, which the "
                    "date presets below the board already use for a rolling "
                    "window" % phrase)


# --------------------------------------------------------------------------
# 3. THE TWO RENDERERS AGREE. They must, byte for byte: bootParamsMatch /
#    takeBoot rejects the server-inlined board on any difference and the first
#    paint silently becomes six REST calls.
# --------------------------------------------------------------------------

@unittest.skipUnless(PHP, "php binary not available")
class BothRenderersAgree(unittest.TestCase):

    def setUp(self):
        jsrun.require_node(self)

    def test_the_two_renderers_agree_on_every_window(self):
        for name, (day, _) in CLOCKS.items():
            php = php_board(day)["periods"]
            js = js_board(day)["windows"]
            self.assertEqual(
                list(php), list(js),
                "on %s the two renderers disagree about which columns exist, "
                "or their order: php=%r js=%r" % (name, list(php), list(js)))
            for k in php:
                self.assertEqual(
                    [php[k]["from"], php[k]["to"]], js[k],
                    "on %s (%s) the %s window is %s..%s on the server and "
                    "%s..%s in the browser. takeBoot rejects the inlined "
                    "board on exactly this, and the first paint becomes six "
                    "fetches." % (day, name, k, php[k]["from"], php[k]["to"],
                                  js[k][0], js[k][1]))

    def test_the_two_renderers_agree_on_every_label(self):
        for name, (day, _) in CLOCKS.items():
            php = php_board(day)["labels"]
            js = js_board(day)["labels"]
            self.assertEqual(
                php, js,
                "on %s (%s) the server and the browser print different column "
                "headings over the same numbers: %r vs %r"
                % (day, name, php, js))

    def test_the_browser_period_map_has_the_same_six_keys_in_the_same_order(self):
        """P itself, read off the source: it is a literal and it is the thing
        takeBoot compares."""
        src = JS.read_text()
        block = src[src.index("var P = {"):]
        block = block[:block.index("};")]
        keys = re.findall(r"^\s{12}(\w+):", block, re.M)
        self.assertEqual(
            keys, ORDER,
            "P in layoffs.js declares %r, not the board's six columns in "
            "order" % keys)
        names = re.search(r"var KEYS = \[(.*?)\];", src).group(1)
        self.assertEqual(
            [k.strip().strip("'") for k in names.split(",")], ORDER,
            "KEYS in layoffs.js is not the board's six columns in order")


# --------------------------------------------------------------------------
# 4. THE PHONE. Rendered geometry, at 375 and 1280, in headless Chrome.
# --------------------------------------------------------------------------

FIXTURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>%(plugin)s</style>
<style>%(freeze)s</style>
</head>
<body class="wp-singular page-template-default page">
<div class="wp-site-blocks"><main class="wp-block-group has-global-padding">
<div class="wp-block-group alignfull"><div class="entry-content alignfull">
<div class="alt-wrap alt-tracker-wrap alt-dashboard">
%(markup)s
</div></div></div></main></div>
</body></html>
"""

PROBE = r"""
(function () {
  var board = document.querySelector('.alt-sb');
  var de = document.documentElement;
  var wrap = document.querySelector('.alt-narrative-wrap');
  if (!board || !wrap) return null;
  function txt(e) { return (e.innerText || '').trim(); }
  var cells = Array.prototype.map.call(
    board.querySelectorAll('.alt-sb-r-largest .alt-sb-ev'), function (c) {
      var cr = c.getBoundingClientRect();
      var name = c.querySelector('b'), num = c.querySelector(':scope > span');
      var nr = num.getBoundingClientRect();
      return {
        name: txt(name),
        name_clipped: name.scrollWidth > name.clientWidth + 1
                   || name.scrollHeight > name.clientHeight + 1,
        num: txt(num),
        num_clipped: num.scrollWidth > num.clientWidth + 1
                  || num.scrollHeight > num.clientHeight + 1,
        num_inside: nr.left >= cr.left - 1 && nr.right <= cr.right + 1
                 && nr.bottom <= cr.bottom + 1
      };
    });
  // Every numeric row, including BOTH AI rows: the fifth row is the one this
  // change adds and it carries the widest label on the board, so it is the
  // one most likely to squeeze its own numbers.
  var numbers = Array.prototype.map.call(
    board.querySelectorAll('.alt-sb-r-workers .alt-sb-cell,'
                         + '.alt-sb-r-events .alt-sb-cell,'
                         + '.alt-sb-r-ai .alt-sb-cell,'
                         + '.alt-sb-r-aibroad .alt-sb-cell'), function (c) {
      var inner = c.querySelector('b') || c;
      var r = inner.getBoundingClientRect(), cr = c.getBoundingClientRect();
      return {t: txt(inner),
              inside: r.left >= cr.left - 1 && r.right <= cr.right + 1};
    });
  // Scroll the board to its far edge and ask two questions there: does the
  // last column become reachable, and does the row label stay put.
  board.scrollLeft = board.scrollWidth;
  var cols = board.querySelectorAll('.alt-sb-headrow .alt-sb-col');
  var bb = board.getBoundingClientRect();
  var last = cols[cols.length - 1].getBoundingClientRect();
  var lab = board.querySelector('.alt-sb-r-workers .alt-sb-label')
                 .getBoundingClientRect();
  var reachable = last.right <= bb.right + 1 && last.left >= bb.left - 1;
  var pinned = lab.left >= bb.left - 1 && lab.left < bb.right;
  board.scrollLeft = 0;
  // The row labels, read as innerText off the rendered rowheader, and the
  // board's own painted height. The fifth row's cost is measured, not
  // estimated: six columns already only fit as a scroll container.
  var rows = Array.prototype.map.call(
    board.querySelectorAll('.alt-sb-row[class*="alt-sb-r-"]'), function (r) {
      var lab = r.querySelector('.alt-sb-label');
      return {cls: r.className, label: lab ? txt(lab) : '',
              label_h: lab ? Math.round(lab.getBoundingClientRect().height) : 0};
    });
  var footEl = document.querySelector('.alt-sb-foot');
  return {
    board_h: Math.round(board.getBoundingClientRect().height),
    rows: rows,
    foot: footEl ? txt(footEl) : '',
    viewport: de.clientWidth,
    page_bleeds: de.scrollWidth > de.clientWidth + 1,
    usable_share: +(board.clientWidth / de.clientWidth * 100).toFixed(1),
    board_client_w: board.clientWidth,
    board_scroll_w: board.scrollWidth,
    board_scrolls: board.scrollWidth > board.clientWidth + 1,
    board_inside_card: Math.round(board.getBoundingClientRect().right)
                       <= Math.round(wrap.getBoundingClientRect().right) + 1,
    cols: Array.prototype.map.call(cols, txt),
    col_w: cols.length ? Math.round(cols[0].getBoundingClientRect().width) : 0,
    body_chars: txt(document.getElementById('alt-narrative')).length,
    largest: cells,
    numbers: numbers,
    last_column_reachable: reachable,
    label_pinned_when_scrolled: pinned
  };
})()
"""


def board_markup():
    """The real <details> off the template, with the served board inside it."""
    html = re.sub(r"/\*.*?\*/", "", TEMPLATE.read_text(), flags=re.S)
    start = html.index('<details class="alt-narrative-wrap"')
    end = html.index("</details>", start) + len("</details>")
    frag = html[start:end]
    frag = re.sub(r"<\?php.*?\?>", lambda m: BOARD_BODY.read_text(), frag,
                  flags=re.S)
    assert "alt-sb-r-largest" in frag, "the board body did not land in the slice"
    return frag


class RenderedCells(unittest.TestCase):
    """Geometry and innerText from the rendered ancestor. Never markup."""

    @classmethod
    def setUpClass(cls):
        if not find_chrome():
            raise unittest.SkipTest(
                "no Chrome/Chromium on this machine, so the board could not "
                "be measured. This is UNKNOWN, not a pass.")
        cls._markup = board_markup()
        cls._cache = {}

    def probe(self, width):
        if width in self._cache:
            return self._cache[width]
        html = FIXTURE % {"plugin": CSS.read_text(),
                          "freeze": contrast_audit.FREEZE_CSS,
                          "markup": self._markup}
        try:
            with Browser(width=width, height=900 if width >= 768 else 812) as page:
                page.call("Page.navigate", {"url": "about:blank"})
                page.eval_js(
                    "(function(){document.open();document.write(%s);"
                    "document.close();return true;})()" % json.dumps(html))
                got = page.eval_js(PROBE)
        except CDPUnavailable as exc:
            raise unittest.SkipTest("could not launch Chrome: %s" % exc)
        self.assertIsNotNone(got, "the fixture rendered no board at %dpx" % width)
        self._cache[width] = got
        return got

    def test_six_columns_render_and_the_page_does_not_bleed(self):
        for width in (375, 1280):
            got = self.probe(width)
            self.assertEqual(
                len(got["cols"]), 6,
                "the board rendered %d period columns, not six: %r"
                % (len(got["cols"]), got["cols"]))
            self.assertFalse(
                got["page_bleeds"],
                "at %dpx the PAGE scrolls sideways. The board may scroll; the "
                "page may not." % width)
            self.assertTrue(
                got["board_inside_card"],
                "at %dpx the board is painted outside the card that holds it"
                % width)

    def test_the_usable_width_is_reported_and_is_not_a_sliver(self):
        """The 219px-of-a-375px-phone incident, as a bar.

        scrollWidth === clientWidth was true throughout that one, so the share
        of the viewport the board actually occupies is what is asserted.
        """
        for width, floor in ((375, 80.0), (1280, 80.0)):
            got = self.probe(width)
            self.assertGreaterEqual(
                got["usable_share"], floor,
                "at %dpx the board occupies %.1f%% of the viewport (%dpx of "
                "%d). scrollWidth == clientWidth proves nothing about this."
                % (width, got["usable_share"], got["board_client_w"], width))

    def test_the_board_scrolls_inside_its_own_box_on_a_phone(self):
        """Six columns cannot fit a 375px phone at a readable size, so the
        board carries its own scroll box and the page never moves. Every
        column has to be reachable in it, and the row label has to stay."""
        got = self.probe(375)
        self.assertTrue(
            got["board_scrolls"],
            "at 375px the board does not scroll, so its six columns were "
            "squeezed into %dpx instead. That is how the numbers ran "
            "together." % got["board_client_w"])
        self.assertTrue(
            got["last_column_reachable"],
            "the last period column cannot be scrolled into view at 375px")
        self.assertTrue(
            got["label_pinned_when_scrolled"],
            "scrolling the board sideways at 375px takes the row label with "
            "it, so a scrolled column no longer says which measure it is")

    def test_a_desktop_reader_is_not_made_to_scroll(self):
        got = self.probe(1280)
        self.assertFalse(
            got["board_scrolls"],
            "at 1280px the board scrolls sideways, which is a phone answer "
            "applied to a screen with room for all six columns")

    def test_the_number_is_never_the_thing_that_is_truncated(self):
        """The hard rule. A reader losing "1,100" is worse than losing the
        tail of a company name, so every rendered count is read back out of
        its own cell at both widths."""
        for width in (375, 1280):
            got = self.probe(width)
            self.assertEqual(
                len(got["largest"]), 6,
                "at %dpx only %d largest-entry cells rendered"
                % (width, len(got["largest"])))
            for cell in got["largest"]:
                self.assertTrue(
                    cell["num"], "at %dpx a largest-entry cell renders a "
                    "company with no count beside it: %r" % (width, cell))
                self.assertFalse(
                    cell["num_clipped"],
                    "at %dpx the count %r in the %r cell is clipped. The "
                    "number is the one thing that may never be what goes."
                    % (width, cell["num"], cell["name"]))
                self.assertTrue(
                    cell["num_inside"],
                    "at %dpx the count %r is painted outside the %r cell"
                    % (width, cell["num"], cell["name"]))
            for n in got["numbers"]:
                self.assertTrue(
                    n["inside"],
                    "at %dpx the %r in a numeric row is painted outside its "
                    "own cell, which is how six columns squeezed into a phone "
                    "made three figures read as one string" % (width, n["t"]))

    def test_a_long_company_name_is_readable_rather_than_seven_characters(self):
        """The reported defect. innerText is the FULL name whether it is
        painted or ellipsised away, so the readable test is whether the name
        element is clipped at all."""
        for width in (375, 1280):
            got = self.probe(width)
            longest = max(got["largest"], key=lambda c: len(c["name"]))
            self.assertGreater(
                len(longest["name"]), 20,
                "the fixture has no long company name in it, so this proves "
                "nothing: %r" % [c["name"] for c in got["largest"]])
            for cell in got["largest"]:
                self.assertFalse(
                    cell["name_clipped"],
                    "at %dpx the employer name %r is cut off. It used to be "
                    "cut to seven characters with an ellipsis; a silent cut "
                    "is worse, because the shortened name reads as the whole "
                    "one." % (width, cell["name"]))

    def test_the_fifth_row_renders_and_says_what_it_contains(self):
        """Rendered innerText off the rowheader, at both widths. The label is
        the longest on the board and at 375px it becomes a full-width row of
        its own, which is exactly where a clause gets clipped away and the
        containment silently stops being stated."""
        for width in (375, 1280):
            got = self.probe(width)
            classes = [r["cls"] for r in got["rows"]]
            self.assertEqual(
                len(got["rows"]), 5,
                "at %dpx the board rendered %d rows, not five: %r"
                % (width, len(got["rows"]), [r["label"] for r in got["rows"]]))
            self.assertTrue(
                any("alt-sb-r-aibroad" in c for c in classes),
                "at %dpx there is no broad-lens row on the rendered board: %r"
                % (width, classes))
            broad = [r for r in got["rows"] if "alt-sb-r-aibroad" in r["cls"]][0]
            self.assertIn(
                "includes the above", broad["label"].casefold(),
                "at %dpx the broad row's label reads %r. The clause that says "
                "it contains the strict row is not decoration: without it two "
                "adjacent AI figures invite being added."
                % (width, broad["label"]))

    def test_the_fifth_rows_numbers_are_reported_at_both_widths(self):
        """The board's cost, measured rather than assumed. Six columns already
        only fit as a scroll container, so a fifth row is the change most
        likely to have been waved through on a desktop."""
        # Measure BOTH widths and report BOTH before asserting on either. A
        # loop that asserts as it goes reports only the first width that
        # fails, which is the one case where the other number is wanted.
        seen = [(w, self.probe(w)) for w in (375, 1280)]
        for width, got in seen:
            print("\n  %dpx: board %dpx tall, %d rows, %.1f%% of the viewport "
                  "(%dpx of %d), scrolls=%s, page bleeds=%s"
                  % (width, got["board_h"], len(got["rows"]),
                     got["usable_share"], got["board_client_w"], width,
                     got["board_scrolls"], got["page_bleeds"]))
        for width, got in seen:
            self.assertEqual(
                len(got["numbers"]), 24,
                "at %dpx the four numeric rows did not render 24 cells "
                "between them: %d" % (width, len(got["numbers"])))

    def test_the_footnote_containment_sentence_is_readable_as_rendered(self):
        """innerText from the rendered list, not the markup that built it."""
        foot = self.probe(375)["foot"].casefold()
        self.assertIn(
            "contains every one of those cuts", foot,
            "the rendered footnote does not carry the containment sentence")
        self.assertIn("never added together", foot)
        self.assertIn(
            "by filing date", foot,
            "the rendered footnote no longer names the basis the board counts "
            "on, which is the whole reason the board was moved onto it")

    def test_the_completed_periods_are_readable_on_the_rendered_board(self):
        """innerText from the rendered ancestor, which is the only one of the
        three ways of asking that reports what a reader can read."""
        got = self.probe(1280)
        heads = [c.casefold() for c in got["cols"]]
        self.assertEqual(
            heads[:2], ["today", "this week"],
            "the two relative columns changed: %r" % got["cols"])
        self.assertRegex(
            heads[2], r"^[a-z]+ \d{4}$",
            "the current-month column is %r, which does not name its period "
            "while the column beside it does" % got["cols"][2])
        self.assertRegex(
            heads[3], r"^[a-z]+ \d{4}$",
            "the completed-month column is %r" % got["cols"][3])
        self.assertRegex(
            heads[4], r"^q[1-4] \d{4}$",
            "the completed-quarter column is %r" % got["cols"][4])
        self.assertRegex(heads[5], r"^\d{4} ytd$")


# --------------------------------------------------------------------------
# 5. What the board still promises. The footnote's claim is the one thing a
#    new column could quietly falsify.
# --------------------------------------------------------------------------

class TheTwoAiRows(unittest.TestCase):
    """THE BROAD LENS, AND THE ONE THING IT MUST NOT INVITE.

    The strict AI figure is the tightest of the four AI measures this tracker
    holds. On the board it stood alone, which is why the owner read it and
    asked whether that was really all: the broad lens was in the API and on the
    methodology page and nowhere a reader looks.

    CLAUDE.md's rule about the AI measures is the constraint that shapes the
    fix, not a footnote to it: they carry distinguishing labels and are never
    summed or blended. Two AI rows adjacent on one card is precisely where a
    reader adds them, so the containment is stated on the row's own label AND
    in the footnote, and both halves are asserted here.

    THE CONTAINMENT WAS CHECKED BEFORE IT WAS WRITTEN, against the live API on
    2026-08-13 rather than against the SQL: an `ai=1` slice reports
    ai_broad_jobs equal to its own jobs (42,253), and an `ai_broad=1` slice
    reports ai_jobs = 42,253 inside jobs = 53,253. Strict is a subset, not an
    overlap. The definitions in db.php say the same thing and are pinned below,
    because a sentence on a page is only true while the SQL under it is.
    """

    STRICT = "alt-sb-r-ai"
    BROAD = "alt-sb-r-aibroad"

    def rows(self, src):
        """(class, label, totals key) for every numeric row, off the source of
        whichever renderer is being asked."""
        php = re.findall(
            r"\$alt_sb_numrow\('([\w-]+)', '((?:[^'\\]|\\.)*)', '(\w+)'\)", src)
        js = re.findall(
            r"numRow\('([\w-]+)', '((?:[^'\\]|\\.)*)', '(\w+)'\)", src)
        return php + js

    def test_the_broad_lens_is_a_row_on_both_renderers(self):
        for path, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            rows = self.rows(path.read_text())
            keys = [k for _, _, k in rows]
            self.assertIn(
                "ai_broad_jobs", keys,
                "%s draws no broad-lens row, so the board still publishes the "
                "tightest of the four AI measures as if it were the only one. "
                "Rows found: %r" % (where, keys))
            self.assertEqual(
                keys, ["jobs", "entries", "ai_jobs", "ai_broad_jobs"],
                "%s draws %r. The broad lens belongs directly under the strict "
                "row it contains, and the announced tier is deliberately NOT a "
                "third AI row." % (where, keys))

    def test_the_announced_tier_did_not_become_a_third_ai_row(self):
        """Refused on purpose. Announced versus verified is what the Workers
        and Verified layoffs rows already carry, and three AI rows on one card
        is where the board stops being readable."""
        for path, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            keys = [k for _, _, k in self.rows(path.read_text())]
            for banned in ("ai_announced_jobs", "ai_verified_jobs",
                           "ai_primary_jobs"):
                self.assertNotIn(
                    banned, keys,
                    "%s added %s as a third AI row" % (where, banned))

    def test_the_two_ai_labels_state_the_containment_rather_than_implying_it(self):
        """The rule is that a reader must not be able to add them. Two labels
        that merely differ ("Explicitly AI-attributed", "AI-linked, broad")
        distinguish the measures and say nothing about how they relate, and a
        reader who cannot tell reaches for the plus sign."""
        for path, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            rows = {c: lab for c, lab, _ in self.rows(path.read_text())}
            self.assertIn(self.BROAD, rows, where)
            strict, broad = rows[self.STRICT], rows[self.BROAD]
            self.assertNotEqual(
                strict, broad,
                "%s gives the two AI rows the same label" % where)
            self.assertIn(
                "includes the above", broad.casefold(),
                "%s labels the broad row %r, which names the measure and not "
                "its relationship to the strict row above it. Adjacent AI rows "
                "that do not say one contains the other get added together."
                % (where, broad))

    def test_no_board_label_carries_a_dash(self):
        """House rule. style_check.py needs 12 characters and 3 real words
        before a string is eligible, so a row label can carry one straight past
        it: this reads the labels themselves."""
        for path, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            for _, lab, _ in self.rows(path.read_text()):
                for bad in ("—", "–"):
                    self.assertNotIn(bad, lab, "%s row label %r" % (where, lab))

    def test_the_footnote_says_the_broad_lens_contains_the_strict_one(self):
        """One plain sentence, on both renderers, in the footnote a reader
        actually reaches. "Never added together" is the operative half."""
        for path, where in ((TEMPLATE, "page-tracker.php"), (JS, "layoffs.js")):
            src = path.read_text()
            foot = src[src.index('<ul class="alt-sb-foot">'):]
            foot = foot[:foot.index("</ul>")]
            self.assertIn(
                "contains every one of those cuts", foot,
                "%s does not tell a reader that the broad lens CONTAINS the "
                "strict measure, so the two AI rows read as two independent "
                "figures" % where)
            self.assertIn(
                "never added together", foot,
                "%s does not say the two AI rows are never summed" % where)

    def test_the_containment_is_true_in_the_sql_the_sentence_describes(self):
        """The sentence is only true while the definitions under it are. The
        broad measure must be the strict predicate ORed with something, so
        every strictly attributed row is inside it by construction."""
        src = DB.read_text()
        broad = re.findall(
            r"CASE WHEN ([^T]*?) THEN job_count END\),0\) ai_broad_jobs", src)
        self.assertTrue(broad, "db.php no longer defines ai_broad_jobs")
        for expr in broad:
            self.assertIn(
                "ai_explicit=1 OR", expr,
                "ai_broad_jobs is defined as %r, which does not contain the "
                "strict predicate. The board now tells readers the broad lens "
                "contains the strict one; this is that claim." % expr.strip())


class TheFootnoteIsStillTrue(unittest.TestCase):

    def test_the_board_still_says_the_dropdowns_do_not_change_it(self):
        for src, where in ((TEMPLATE.read_text(), "page-tracker.php"),
                           (JS.read_text(), "layoffs.js")):
            foot = src[src.index('<ul class="alt-sb-foot">'):]
            foot = foot[:foot.index("</ul>")]
            self.assertIn(
                "follows the region tabs above", foot,
                "%s dropped the clause saying the board is scoped by the "
                "region tabs only" % where)
            self.assertIn(
                "do not change it", foot,
                "%s dropped the clause saying the filters below do not narrow "
                "the board" % where)
            self.assertEqual(
                4, foot.count("<li"),
                "%s no longer splits the board footnote into four clauses"
                % where)

    def test_the_overlap_clause_covers_the_new_columns(self):
        """A completed month sits inside a completed quarter in the first
        month of any quarter, which is a THIRD way the columns overlap."""
        for src, where in ((TEMPLATE.read_text(), "page-tracker.php"),
                           (JS.read_text(), "layoffs.js")):
            foot = src[src.index('<ul class="alt-sb-foot">'):]
            foot = foot[:foot.index("</ul>")]
            self.assertIn(
                "completed month can sit inside a completed quarter", foot,
                "%s tells a reader the columns overlap but names only the "
                "week-inside-month case, and the two new columns overlap too"
                % where)


if __name__ == "__main__":
    unittest.main()
