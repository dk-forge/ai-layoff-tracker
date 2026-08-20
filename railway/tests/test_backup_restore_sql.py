"""The lossless restore path: does the emitted SQL say what the rows said.

WHAT THIS IS AND IS NOT
-----------------------
The reimage path is `--emit-sql`: INSERT statements loaded straight into MySQL
on the new host, because that is the only path carrying the columns /bulk has
no parameter for. The failure that matters is a quoting bug, and a quoting bug
does not announce itself: it truncates a value, merges two rows, or runs part
of a value as SQL, and the load reports success.

This suite runs OFFLINE and with no database engine, so it verifies the
statements by PARSING them back with an independently written MySQL
string-literal reader (`decode_literal` / `parse_inserts` below). That is the
inverse function, written separately from the emitter rather than derived from
it, which is what makes it able to catch an asymmetry. It proves: every value
survives verbatim, NULL stays NULL and never becomes the four characters
N-U-L-L, a value containing a quote or a semicolon cannot break out of its
literal, the column list lines up with the values, and no row is lost at the
200-row batch seam.

It does NOT prove MySQL accepted the file. That was done once, by hand, against
a real MySQL 8 in Docker, and the result is quoted in docs/RECOVERY.md under
the restore drill. Re-run that when the emitter changes; do not upgrade this
docstring's claim without it.
"""
import gzip
import io
import json
import pathlib
import re
import sys
import tempfile
import unittest

RAILWAY = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

from tests import _requests_stub  # noqa: E402
_requests_stub.install()

import backup_restore  # noqa: E402
import backup_tables  # noqa: E402


NASTY = {
    # Every one of these has broken a naive emitter somewhere.
    "quote": "O'Brien Industries",
    "backslash": "C:\\path\\",
    "trailing_backslash": "ends with a backslash \\",
    "newline": "line one\nline two",
    "carriage": "line one\r\nline two",
    "unicode": "Société Générale — 日本語 — emoji ok",
    "semicolon": "value; DROP TABLE wp_alt_layoffs; --",
    "quote_and_slash": "it's \\ both",
    # These two are here because the first version of sql_literal STRIPPED
    # them. A real MySQL 8 load accepted the file and returned the value one
    # byte shorter, silently, with the load reporting success. A restore that
    # quietly alters a value is worse than one that fails.
    "nul_byte": "null\x00byte",
    "ctrl_z": "ctrl\x1aZ",
}


def write_export(tmp: pathlib.Path, table: str, rows):
    path = tmp / f"{table}.jsonl.gz"
    with gzip.open(path, "wb") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False).encode("utf-8") + b"\n")
    return path


def layoff_row(**over):
    row = {c: None for c in backup_tables.TABLES["layoffs"]["columns"]}
    row.update({
        "id": 1, "dedup_hash": "a" * 32, "company": "Acme", "company_key": "acme",
        "job_count": 100, "job_count_max": 120, "layoff_date": "2026-01-15",
        "country": "United States", "state": "CA", "source_type": "warn",
        "verification_level": "warn", "ai_explicit": 0, "confidence": 90,
        "announced": 0, "edited": 0, "event_id": 0, "superset_of": 0,
        "reason_tags": ",cost,", "excerpt": "Plain text.",
    })
    row.update(over)
    return row


# --------------------------------------------------------------------------
# An independently written reader for what the emitter writes. Deliberately NOT
# built from backup_restore.sql_literal: two functions derived from one table of
# escapes agree with each other by construction and prove nothing.
# --------------------------------------------------------------------------

_UNESCAPE = {"\\": "\\", "'": "'", '"': '"', "n": "\n", "r": "\r",
             "t": "\t", "0": "\x00", "b": "\b", "Z": "\x1a"}


def decode_literal(text, i):
    """Read one MySQL literal starting at text[i]. Returns (value, next_index)."""
    if text.startswith("NULL", i):
        return None, i + 4
    if text[i] not in "'":
        # A bare number. The emitter writes ints and floats unquoted, so the
        # reader has to accept them or it would call every count a syntax error.
        m = re.match(r"-?\d+(?:\.\d+)?(?:e[-+]?\d+)?", text[i:], re.I)
        assert m, f"expected a literal at {i}: {text[i:i+30]!r}"
        raw = m.group(0)
        return (float(raw) if any(c in raw for c in ".eE") else int(raw)), i + len(raw)
    i += 1
    out = []
    while True:
        ch = text[i]
        if ch == "\\":
            nxt = text[i + 1]
            out.append(_UNESCAPE.get(nxt, nxt))
            i += 2
            continue
        if ch == "'":
            return "".join(out), i + 1
        out.append(ch)
        i += 1


def parse_inserts(sql):
    """Every row of every INSERT in `sql`, as lists of Python values."""
    rows = []
    for m in re.finditer(r"INSERT IGNORE INTO `([^`]+)` \(([^)]*)\) VALUES\n", sql):
        i = m.end()
        while True:
            while i < len(sql) and sql[i] in " \n\t":
                i += 1
            if i >= len(sql) or sql[i] != "(":
                break
            i += 1
            row = []
            while True:
                while sql[i] == " ":
                    i += 1
                value, i = decode_literal(sql, i)
                row.append(value)
                while sql[i] == " ":
                    i += 1
                if sql[i] == ",":
                    i += 1
                    continue
                assert sql[i] == ")", f"unterminated row near {sql[i:i+40]!r}"
                i += 1
                break
            rows.append(row)
            if i < len(sql) and sql[i] == ",":
                i += 1
                continue
            break
    return rows


class TheEmittedSqlSaysWhatTheRowsSaid(unittest.TestCase):

    def _load(self, rows):
        """Emit SQL for these rows, then read it back with the inverse parser."""
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            write_export(tmp, "layoffs", rows)
            out = io.StringIO()
            n = backup_restore.emit_sql(tmp, "layoffs", "wp_", out)
            sql = out.getvalue()
        columns = backup_tables.TABLES["layoffs"]["columns"]
        parsed = parse_inserts(sql)
        for row in parsed:
            self.assertEqual(len(row), len(columns),
                             "a row has a different number of values than columns")
        return n, columns, parsed

    def test_a_plain_row_round_trips(self):
        row = layoff_row()
        n, columns, got = self._load([row])
        self.assertEqual(n, 1)
        self.assertEqual(len(got), 1)
        back = dict(zip(columns, got[0]))
        self.assertEqual(back["company"], "Acme")
        self.assertEqual(back["dedup_hash"], "a" * 32)

    def test_every_nasty_string_survives_verbatim(self):
        rows = []
        for i, (name, value) in enumerate(sorted(NASTY.items()), start=1):
            rows.append(layoff_row(id=i, dedup_hash=f"{i:032d}",
                                   company=value, excerpt=f"{name}: {value}"))
        n, columns, got = self._load(rows)
        self.assertEqual(n, len(rows))
        self.assertEqual(len(got), len(rows), "a row was lost or the SQL split wrong")
        seen = {dict(zip(columns, r))["company"] for r in got}
        for value in NASTY.values():
            self.assertIn(value, seen, f"{value!r} did not survive the SQL round trip")

    def test_no_character_is_ever_dropped(self):
        """Regression: sql_literal used to delete NUL instead of escaping it."""
        for name in ("nul_byte", "ctrl_z"):
            with self.subTest(name):
                value = NASTY[name]
                _, columns, got = self._load([layoff_row(company=value)])
                back = dict(zip(columns, got[0]))["company"]
                self.assertEqual(back, value)
                self.assertEqual(len(back), len(value), "a character was dropped")

    def test_a_null_stays_null_and_is_not_the_string_NULL(self):
        row = layoff_row(layoff_date=None, excerpt=None)
        _, columns, got = self._load([row])
        back = dict(zip(columns, got[0]))
        self.assertIsNone(back["layoff_date"])
        self.assertIsNone(back["excerpt"])

    def test_the_semicolon_payload_did_not_execute(self):
        """A value containing SQL must land as a value, not run as SQL."""
        row = layoff_row(company=NASTY["semicolon"])
        _, columns, got = self._load([row])
        self.assertEqual(len(got), 1)
        self.assertEqual(dict(zip(columns, got[0]))["company"], NASTY["semicolon"])

    def test_batching_across_the_insert_boundary_keeps_every_row(self):
        """The emitter flushes every 200 rows; the seam is where rows go missing."""
        rows = [layoff_row(id=i, dedup_hash=f"{i:032d}", company=f"Co {i}")
                for i in range(1, 451)]
        n, _, got = self._load(rows)
        self.assertEqual(n, 450)
        self.assertEqual(len(got), 450)

    def test_the_column_list_and_the_values_line_up(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            write_export(tmp, "layoffs", [layoff_row()])
            out = io.StringIO()
            backup_restore.emit_sql(tmp, "layoffs", "wp_", out)
        sql = out.getvalue()
        columns = backup_tables.TABLES["layoffs"]["columns"]
        self.assertIn("`" + "`, `".join(columns) + "`", sql)
        self.assertIn("INSERT IGNORE INTO `wp_alt_layoffs`", sql)

    def test_the_prefix_is_honoured(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            write_export(tmp, "layoffs", [layoff_row()])
            out = io.StringIO()
            backup_restore.emit_sql(tmp, "layoffs", "wpxy_", out)
        self.assertIn("`wpxy_alt_layoffs`", out.getvalue())


class TheEmitterRefusesWhatItShould(unittest.TestCase):

    def test_an_unknown_table_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                backup_restore.emit_sql(pathlib.Path(d), "subscribers", "wp_", io.StringIO())

    def test_an_unpinned_column_in_the_file_stops_the_emit(self):
        """A file carrying a column nobody reviewed must not be loaded blindly."""
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            row = layoff_row()
            row["email"] = "someone@example.invalid"
            write_export(tmp, "layoffs", [row])
            with self.assertRaises(backup_tables.UnpinnedColumn):
                backup_restore.emit_sql(tmp, "layoffs", "wp_", io.StringIO())


class TheFidelityDrillSaysWhatItMeasured(unittest.TestCase):
    """A clean diff over an unrepresentative sample is a flattering number.

    The drill's headline is "every column came back identical". That is only
    interpretable next to what the sample actually contained, so the drill
    prints its own composition and names any column it did NOT exercise.
    """

    def test_it_reports_composition_and_names_unexercised_columns(self):
        import inspect
        src = inspect.getsource(backup_restore.fidelity)
        self.assertIn("what this sample actually exercised", src)
        self.assertIn("NOT EXERCISED", src)

    def test_it_coerces_mysql_string_zeros(self):
        """"0" is truthy in Python, and counting it as a value inflates the sample."""
        import inspect
        src = inspect.getsource(backup_restore.fidelity)
        self.assertIn('v not in (None, "", "0", 0)', src)

    def test_it_refuses_to_let_the_result_stand_for_an_insert(self):
        import inspect
        src = inspect.getsource(backup_restore.fidelity)
        self.assertIn("NOT a statement about", src)
        self.assertIn("INSERT into an empty table", src)

    def test_it_says_pinned_rows_prove_the_pin_and_not_fidelity(self):
        import inspect
        src = inspect.getsource(backup_restore.fidelity)
        self.assertIn("editorially PINNED", src)


class TheBulkEntryMapping(unittest.TestCase):

    def test_company_is_renamed_and_tags_are_unpacked(self):
        entry = backup_restore.row_to_bulk_entry(
            layoff_row(company="Acme", reason_tags=",cost,ai,"))
        self.assertEqual(entry["company_name"], "Acme")
        self.assertNotIn("company", entry)
        self.assertEqual(entry["reason_tags"], ["cost", "ai"])

    def test_empty_tags_become_an_empty_list_not_a_stray_token(self):
        entry = backup_restore.row_to_bulk_entry(layoff_row(reason_tags=""))
        self.assertEqual(entry["reason_tags"], [])

    def test_the_three_columns_bulk_learned_to_carry_are_sent(self):
        """These were in alt_db_upsert all along and alt_api_bulk dropped them."""
        entry = backup_restore.row_to_bulk_entry(layoff_row(
            job_count_max=999,
            employer_country_evidence="HQ stated in the filing.",
            announcement_evidence="Announced on the call."))
        self.assertEqual(entry["job_count_max"], 999)
        self.assertEqual(entry["employer_country_evidence"], "HQ stated in the filing.")
        self.assertEqual(entry["announcement_evidence"], "Announced on the call.")

    def test_columns_bulk_cannot_carry_are_absent_rather_than_silently_wrong(self):
        entry = backup_restore.row_to_bulk_entry(layoff_row(
            superset_of=42, event_id=7, edited=1, company_key="acme"))
        for lost in ("superset_of", "event_id", "edited", "company_key", "id"):
            self.assertNotIn(lost, entry,
                             f"{lost} is not a /bulk parameter and must not be sent")


if __name__ == "__main__":
    unittest.main()
