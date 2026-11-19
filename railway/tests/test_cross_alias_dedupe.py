"""One event under two employer names must be counted ONCE before publish.

THE DEFECT (dk-forge/todo#2791, 2026-11-19). `alt_reconcile_supersets` pass (2),
news-vs-news exact count, groups rows on `company_key`, so "KLM" and
"Air France-KLM" are two companies and the pass never compares them. The live
invariant `cross_alias_duplicate_rows` (railway/data_integrity.py) saw five
such events after publish: 11,050 excess jobs in the headline, worst
KLM / Air France-KLM 5,000 each on 2026-11-05 (rows 182986 and 188040).

The fix is pass (2b) in db.php, which runs the SAME name rules as
`entity_resolution.same_entity` (one key contained in the other with a
distinctive token, or an initialism) across company keys, with the invariant's
own date window. These lift the real PHP and run it; without php on PATH they
SKIP, which is not a pass.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DB = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php")
PHP = shutil.which("php")
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import data_integrity  # noqa: E402
import entity_resolution  # noqa: E402


def _src():
    with open(DB, encoding="utf-8") as fh:
        return fh.read()


def _extract(name):
    m = re.search(r"\nfunction %s\s*\(.*?\n\}" % re.escape(name), _src(), re.S)
    if not m:
        raise AssertionError("could not extract %s from db.php" % name)
    return m.group(0)


def _row(rid, key, count, when, st="news", ai=0):
    return {"id": rid, "company": key, "company_key": key, "source_type": st,
            "job_count": count, "layoff_date": when, "ai_explicit": ai}


def _marks(rows, already=None):
    parts = [_extract("alt_cross_alias_weak_tokens"),
             _extract("alt_cross_alias_same_employer"),
             _extract("alt_cross_alias_news_marks")]
    define = re.search(r"^if \(!defined\('ALT_CROSS_ALIAS_MAX_GAP_DAYS'\)\).*$", _src(), re.M)
    if not define:
        raise AssertionError("ALT_CROSS_ALIAS_MAX_GAP_DAYS is not defined in db.php")
    runner = ("<?php\n" + define.group(0) + "\n" + "\n".join(parts) + "\n"
              "$in = json_decode($argv[1], true);\n"
              "$m = alt_cross_alias_news_marks($in['rows'], $in['already']);\n"
              "echo json_encode((object) $m);\n")
    fh = tempfile.NamedTemporaryFile("w", suffix=".php", delete=False, encoding="utf-8")
    try:
        fh.write(runner)
        fh.close()
        res = subprocess.run([PHP, fh.name, json.dumps({"rows": rows, "already": already or {}})],
                             capture_output=True, text=True, timeout=60)
        if res.returncode != 0:
            raise AssertionError("php failed: " + (res.stderr or "")[:2000])
        return {int(k): int(v) for k, v in json.loads(res.stdout).items()}
    finally:
        os.unlink(fh.name)


# The five live pairs of 2026-11-19, keyed as alt_company_key stores them.
LIVE = [
    (_row(182986, "klm", 5000, "2026-11-05"), _row(188040, "air france klm", 5000, "2026-11-05")),
    (_row(183498, "jaguar land rover jlr", 3000, "2026-11-13"), _row(183598, "jaguar land rover", 3000, "2026-11-13")),
    (_row(183354, "oakland arena coliseum", 1600, "2026-11-05"), _row(183551, "oakland coliseum and arena", 1600, "2026-11-06")),
    (_row(183263, "qantas", 850, "2026-11-10"), _row(183569, "qantas airways", 850, "2026-11-10")),
    (_row(183461, "north star health alliance", 600, "2026-09-22"), _row(182244, "north star", 600, "2026-09-24")),
]


@unittest.skipUnless(PHP, "php not on PATH - UNKNOWN, not a pass")
class CrossAliasDedupeTest(unittest.TestCase):

    def test_each_live_pair_collapses_to_one_row(self):
        for keep, dup in LIVE:
            marks = _marks([keep, dup])
            self.assertEqual(marks, {dup["id"]: keep["id"]},
                             "%s / %s, %d jobs, still counts twice"
                             % (keep["company_key"], dup["company_key"], keep["job_count"]))

    def test_all_five_together_exclude_exactly_11050(self):
        rows = [r for pair in LIVE for r in pair]
        marks = _marks(rows)
        by_id = {r["id"]: r for r in rows}
        self.assertEqual(sum(by_id[m]["job_count"] for m in marks), 11050)

    def test_ai_flagged_row_wins_the_primary_slot(self):
        marks = _marks([_row(1, "klm", 5000, "2026-11-05"),
                        _row(2, "air france klm", 5000, "2026-11-06", ai=1)])
        self.assertEqual(marks, {1: 2})

    def test_two_employers_sharing_a_weak_word_stay_two(self):
        # "Tata" inside both is not evidence; neither key contains the other.
        self.assertEqual(_marks([_row(1, "tata steel", 2000, "2026-11-05"),
                                 _row(2, "tata motors", 2000, "2026-11-05")]), {})
        # An all-weak contained side ("air") is not evidence either.
        self.assertEqual(_marks([_row(1, "air", 900, "2026-11-05"),
                                 _row(2, "air canada", 900, "2026-11-05")]), {})

    def test_outside_the_two_day_window_stays_two(self):
        self.assertEqual(_marks([_row(1, "klm", 5000, "2026-11-01"),
                                 _row(2, "air france klm", 5000, "2026-11-05")]), {})

    def test_different_counts_stay_two(self):
        self.assertEqual(_marks([_row(1, "klm", 5000, "2026-11-05"),
                                 _row(2, "air france klm", 4000, "2026-11-05")]), {})

    def test_warn_rows_are_exempt(self):
        self.assertEqual(_marks([_row(1, "klm", 500, "2026-11-05", st="warn"),
                                 _row(2, "air france klm", 500, "2026-11-05", st="warn")]), {})

    def test_initialism_joins(self):
        self.assertEqual(_marks([_row(1, "jaguar land rover", 4000, "2026-09-07"),
                                 _row(2, "jlrx", 4000, "2026-09-07"),
                                 _row(3, "ibm", 3900, "2026-09-07"),
                                 _row(4, "international business machines", 3900, "2026-09-08")]),
                         {4: 3})

    def test_rows_already_marked_are_left_alone(self):
        self.assertEqual(_marks([_row(1, "klm", 5000, "2026-11-05"),
                                 _row(2, "air france klm", 5000, "2026-11-05")],
                                already={"2": 99}), {})


class ParityTest(unittest.TestCase):

    def test_window_matches_the_live_invariant(self):
        self.assertIn("ALT_CROSS_ALIAS_MAX_GAP_DAYS', %d)" % data_integrity.CROSS_ALIAS_MAX_DATE_GAP_DAYS,
                      _src())

    def test_weak_tokens_match_entity_resolution(self):
        body = _extract("alt_cross_alias_weak_tokens")
        php = set(re.findall(r"'([a-z]+)'", body))
        self.assertEqual(php, set(entity_resolution._WEAK_TOKENS))


if __name__ == "__main__":
    unittest.main()
