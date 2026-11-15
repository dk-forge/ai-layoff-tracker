"""A search for an employer finds it however its apostrophe was typed.

MEASURED, 2026-11-15, live: `/query?company=Children's Place` (the apostrophe
every keyboard types) returned 6 rows and NOT the Alabama WARN notice for the
same employer, stored as "Children’s Place Distribution" with a typographic
apostrophe (U+2019). `company=Children’s Place` returned that row and missed
the other six. The weekly benchmark scored The Children's Place a WRONG COUNT
(732, "AL row absent") while both rows, 732 + 593 = 1,325, were live. A reader
searching the obvious way saw the same partial answer.

The fold happens ONLY when the term itself carries an apostrophe: a term with
none can never be changed by swapping one apostrophe for another in the
column, so every other search keeps the exact SQL it had (and its cost).

Executed: the SQL the shipped alt_freetext_clause() builds is run in SQLite
with REGEXP registered, against rows shaped like the live ones.
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DB_PHP = os.path.join(ROOT, "wordpress-plugin", "ai-layoff-tracker", "includes", "db.php")
HARNESS = os.path.join(HERE, "fixtures", "freetext_clause_harness.php")
PHP = shutil.which("php")

ROWS = [
    (183154, "The Children's Place"),
    (183327, "Children’s Place Distribution"),
    (144734, "Children’s Place Services Company LLC"),
    (171350, "THE CHILDREN'S PLACE SERVICES CO. LLC"),
    (183330, "Children’s Mercy Hospital"),
    (900001, "Childrens Place Outlet"),
    (900002, "McDonald‘s Franchise"),
]


def clauses(terms):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as h:
        json.dump(terms, h, ensure_ascii=False)
    try:
        run = subprocess.run([PHP, HARNESS, DB_PHP, h.name],
                             capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(h.name)
    if run.returncode != 0:
        raise AssertionError(run.stderr[:1500])
    return {c["term"]: c for c in json.loads(run.stdout)}


def hits(clause):
    db = sqlite3.connect(":memory:")
    db.create_function("REGEXP", 2,
                       lambda pat, s: 1 if re.search(pat, s or "", re.I) else 0)
    db.execute("CREATE TABLE t (id INTEGER, company TEXT)")
    db.executemany("INSERT INTO t VALUES (?, ?)", ROWS)
    # MySQL's `a REGEXP b` is SQLite's `a REGEXP b` -> regexp(b, a). LIKE with
    # esc_like's backslash escape is spelled out, exactly as MySQL defaults.
    sql = clause["sql"].replace("%s", "?").replace(" LIKE ?", " LIKE ? ESCAPE '\\'")
    return sorted(r[0] for r in db.execute("SELECT id FROM t WHERE " + sql, clause["params"]))


@unittest.skipIf(PHP is None, "php is not on PATH. UNKNOWN, not a pass.")
class ApostropheFold(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = clauses(["Children's Place", "Children’s Place",
                         "McDonald's", "Children", "Workday"])

    def test_the_straight_apostrophe_finds_the_typographic_row(self):
        self.assertEqual(hits(self.c["Children's Place"]), [144734, 171350, 183154, 183327])

    def test_the_typographic_apostrophe_finds_the_straight_row(self):
        self.assertEqual(hits(self.c["Children’s Place"]), [144734, 171350, 183154, 183327])

    def test_a_left_single_quote_is_folded_too(self):
        self.assertEqual(hits(self.c["McDonald's"]), [900002])

    def test_the_fold_does_not_invent_a_match_without_an_apostrophe(self):
        self.assertNotIn(900001, hits(self.c["Children's Place"]))

    def test_a_term_without_an_apostrophe_keeps_its_exact_sql(self):
        for term in ("Children", "Workday"):
            self.assertNotIn("REPLACE", self.c[term]["sql"], term)
        # The word boundary still holds: "Children" is not "Childrens".
        self.assertEqual(hits(self.c["Children"]),
                         [144734, 171350, 183154, 183327, 183330])


if __name__ == "__main__":
    unittest.main()
