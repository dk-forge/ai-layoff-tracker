"""The same-company fuzzy merge must not swallow a much larger event.

THE MISS, 2026-09-02. Uber announced ~3,300 job cuts at about 11:30 UTC. GDELT
indexed it from 12:00 UTC (Economic Times, TechCrunch at 13:00, Livemint,
Business Today, Hindustan Times by 15:00); the 22:07 UTC cron pulled it from
the BigQuery mirror and from Google News; the extractor read "Uber, 3,300"
fourteen times. Every one of those POSTs came back 409, and the tracker shows
no Uber row at 3,300. The stage that lost it was `alt_fuzzy_dupe_exists`
(api.php): "same normalized company within +/-30 days" with NO look at the
count, so "Uber, 500, Chile, 2026-08-31" absorbed the global 3,300 as fifteen
source reports (BBC, Business Today, Times of India, Livemint, Moneycontrol,
Hindustan Times, El Periodico, marketscreener among them) and counted zero.
PayPal India (~600) went into "PayPal, 160, Ireland" in the same run.

THE RULE. `alt_fuzzy_count_compatible(incoming, existing)`: an incoming report
at least ALT_FUZZY_DISTINCT_RATIO times the existing row's count is a distinct
event and is stored. Deliberately one-sided: a smaller report arriving after a
known total still merges, because that is usually a country or site slice of
it, and posting slices next to their total is the double-count the superset
pass exists to undo. Unknown counts on either side merge as before.

The functions touch no WordPress API, so they are extracted from the real
api.php and evaluated by php, exactly as test_warn_revision_dedup does.
Without php on PATH these SKIP, which is not a pass. The call-site tests read
the PHP text, so they run everywhere.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
INC = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes")
API = os.path.join(INC, "api.php")
POSTER = os.path.join(ROOT, "railway", "wp_poster.py")
PHP = shutil.which("php")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract(path, name):
    m = re.search(r"\nfunction %s\s*\(.*?\n\}" % re.escape(name), _read(path), re.S)
    if not m:
        raise AssertionError("could not extract %s from %s" % (name, path))
    return m.group(0)


def _compatible(pairs):
    """[(incoming, existing), ...] -> [bool, ...] from the real PHP."""
    define = re.search(r"^if \(!defined\('ALT_FUZZY_DISTINCT_RATIO'\)\).*$",
                       _read(API), re.M)
    if not define:
        raise AssertionError("ALT_FUZZY_DISTINCT_RATIO is not defined in api.php")
    runner = (
        "<?php\n" + define.group(0) + "\n"
        + _extract(API, "alt_fuzzy_count_compatible") + "\n"
        "$out = array();\n"
        "foreach (json_decode($argv[1], true) as $p) {\n"
        "    $out[] = alt_fuzzy_count_compatible($p[0], $p[1]);\n"
        "}\n"
        "echo json_encode($out);\n"
    )
    handle = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False,
                                         encoding="utf-8")
    try:
        handle.write(runner)
        handle.close()
        res = subprocess.run([PHP, handle.name, json.dumps([list(p) for p in pairs])],
                             capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise AssertionError("php failed: " + (res.stderr or "")[:2000])
        return json.loads(res.stdout)
    finally:
        os.unlink(handle.name)


@unittest.skipUnless(PHP, "php not on PATH - UNKNOWN, not a pass")
class CountCompatibility(unittest.TestCase):

    def test_uber_3300_is_not_the_chile_500_row(self):
        # The miss itself: 3,300 incoming, 500 existing, 6.6x.
        self.assertEqual(_compatible([(3300, 500)]), [False],
                         "Uber 3,300 must not merge into Uber 500 Chile")

    def test_paypal_india_is_not_the_ireland_160_row(self):
        # Second instance in the same run: ~600 incoming, 160 existing.
        self.assertEqual(_compatible([(600, 160)]), [False])

    def test_a_restated_count_still_merges(self):
        # "3,000" and "3,300" are one event told twice; so are 10% figures
        # rounded differently. This is what the fuzzy rule is FOR.
        self.assertEqual(_compatible([(3300, 3000), (3000, 3300), (3300, 3300),
                                      (1100, 1000), (1000, 1100)]),
                         [True] * 5)

    def test_a_slice_after_the_total_still_merges(self):
        # One-sided on purpose: "91 jobs in Washington state" after the
        # Zillow 500 event is a slice, and it stays attached as a report.
        self.assertEqual(_compatible([(91, 500), (500, 3300), (1, 3300)]),
                         [True] * 3)

    def test_the_ratio_is_a_boundary_not_a_cliff_in_the_wrong_place(self):
        # Exactly the ratio is distinct; just under it is compatible.
        self.assertEqual(_compatible([(1500, 500), (1499, 500)]), [False, True])

    def test_unknown_counts_are_no_evidence_of_a_different_event(self):
        self.assertEqual(_compatible([(0, 500), (3300, 0), (0, 0), (None, 500)]),
                         [True] * 4)


class TheRuleIsWiredIn(unittest.TestCase):
    """The pure function is worthless if the guard does not call it and the
    /add handler does not pass the count. Both are text-level so they run
    without php; a mutation that drops either line reddens here."""

    def test_the_fuzzy_guard_consults_the_count(self):
        body = _extract(API, "alt_fuzzy_dupe_exists")
        self.assertIn("alt_fuzzy_count_compatible(", body,
                      "alt_fuzzy_dupe_exists no longer checks count compatibility")
        self.assertIn("get_post_meta($id, 'job_count'", body,
                      "the guard must read the candidate row's own job_count")

    def test_add_passes_the_incoming_count_to_the_guard(self):
        src = _read(API)
        calls = re.findall(r"alt_fuzzy_dupe_exists\(([^)]*)\)", src)
        calls = [c for c in calls if not c.startswith("$company, $date")]  # skip the definition
        self.assertTrue(calls, "no call site for alt_fuzzy_dupe_exists")
        for c in calls:
            self.assertIn("$job_count", c,
                          "a call site drops the count and the rule goes vacuous: " + c)

    def test_a_fuzzy_409_names_the_row_that_absorbed_the_report(self):
        # Fourteen "Skipped duplicate at server: Uber" lines said nothing
        # about WHICH row. The 409 must carry the matched row, count and date.
        src = _read(API)
        for key in ("matched_row", "matched_count", "matched_date"):
            self.assertIn("'%s'" % key, src)
        self.assertRegex(src, r"same-company entry within ~30 days already exists\.' \. \$matched_note")

    def test_the_client_prints_the_server_reason(self):
        # Behavioural: a 409 whose body names the absorbing row must reach
        # the run log, or the next swallowed event is again fourteen
        # identical lines that say nothing.
        import io
        import sys
        from unittest import mock
        sys.path.insert(0, os.path.join(ROOT, "railway"))
        import wp_poster

        class _Resp:
            status_code = 409

            def json(self):
                return {"code": "alt_duplicate",
                        "message": "A same-company entry within ~30 days already exists."
                                   " Matched row 178973 (500, 2026-08-31).",
                        "data": {"status": 409, "matched_row": 178973,
                                 "matched_count": 500, "matched_date": "2026-08-31"}}

        out = io.StringIO()
        with mock.patch.dict(os.environ, {"WP_SITE_URL": "https://example.test/blog",
                                          "WP_API_KEY": "k"}), \
             mock.patch.object(wp_poster.requests, "post", return_value=_Resp()), \
             mock.patch("sys.stdout", out):
            status = wp_poster.post_to_wordpress({
                "company_name": "Uber", "job_count": 3300,
                "layoff_date": "2026-09-02", "dedup_hash": "0" * 32})
        self.assertEqual(status, "duplicate")
        line = out.getvalue()
        self.assertIn("Skipped duplicate at server: Uber (3300)", line)
        self.assertIn("Matched row 178973 (500, 2026-08-31)", line,
                      "the server's reason for the 409 must be printed")


if __name__ == "__main__":
    unittest.main()
