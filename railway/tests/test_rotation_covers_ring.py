"""Every rotating query set must reach every term, at any supported cadence.

THE DEFECT THIS PINS. Each rotation used to build its own slice index from
`tm_yday * 2 + (hour < 17)`. The `* 2` is a hardcoded runs-per-day, and nothing
tied it to railway.toml. When the cron went to one run a day on 2026-08-14 the
index advanced by two per run while each run consumed one slice, so the ring was
walked in strides of two.

A stride is not "slower coverage" when it shares a factor with the ring size. It
is permanent loss. `EUPHEMISM_TERMS` is 16 taken 2 at a time: from 2026-08-14
exactly 8 of the 16 terms were never queried again, and the 2026-08-18 move from
16:00 to 22:00 swapped which eight rather than fixing any. Six days of worldwide
euphemism discovery ran at half vocabulary and every surface read green, because
a query that is never issued produces no error, no health row and no log line.

So this file does not test the arithmetic in the abstract. It walks each REAL
ring the collectors ship, under each cadence the cron could plausibly hold, and
fails if a single term goes unreached — plus a source check so nobody hand-rolls
a run counter again.
"""
import ast
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone

RAILWAY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import run_slice  # noqa: E402

# Cadences the cron has held or plausibly could. 1/day is live today; 2/day is
# what it held until 2026-08-14 and what the copy still assumed for six days.
CADENCES = {
    "once daily 22:00": [22],
    "once daily 16:00": [16],
    "once daily 09:00": [9],
    "twice daily 13:00+22:00": [13, 22],
    "twice daily 12:00+22:00": [12, 22],
    "three times 06:00+14:00+22:00": [6, 14, 22],
    "four times 00:00+06:00+12:00+18:00": [0, 6, 12, 18],
}

# The rings the collectors actually ship: (module path, terms symbol, per-run
# symbol). Read out of the source with ast rather than imported, so this test
# needs no network, no keys and no optional dependency.
RINGS = (
    ("sources/gdelt.py", "SEGMENT_TERMS", "SEGMENT_QUERIES_PER_RUN"),
    ("sources/gdelt.py", "NATIVE_TERMS", "NATIVE_QUERIES_PER_RUN"),
    ("sources/gdelt.py", "EUPHEMISM_TERMS", "EUPHEMISM_QUERIES_PER_RUN"),
    # The euro sweep was a fifth ring that rotated on `tm_yday % 4`, outside
    # this table and outside the guard below, until 2026-09-02.
    ("sources/gdelt.py", "EURO_TERMS", "EURO_QUERIES_PER_RUN"),
    ("sources/google_news.py", "GOOGLE_NEWS_LOCALES", "LOCALES_PER_RUN"),
    ("sources/newsapi.py", "SEGMENT_TERMS", "SEGMENT_QUERIES_PER_RUN"),
)

# Days simulated per cadence. The slowest live ring (117 terms, 4 a run, one run
# a day) needs 30 runs; a year of headroom keeps this honest if a ring grows.
SIM_DAYS = 400


def _code_lines(path):
    """(lineno, source text) for real code only — no comments, no strings."""
    import tokenize
    from collections import defaultdict
    per_line = defaultdict(list)
    try:
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING,
                                tokenize.NL, tokenize.NEWLINE,
                                tokenize.INDENT, tokenize.DEDENT,
                                tokenize.ENCODING, tokenize.ENDMARKER):
                    continue
                per_line[tok.start[0]].append(tok.string)
    except (SyntaxError, tokenize.TokenError, UnicodeDecodeError):
        return []
    return [(n, " ".join(parts)) for n, parts in sorted(per_line.items())]


def _module_source(rel):
    with open(os.path.join(RAILWAY, rel), encoding="utf-8") as fh:
        return fh.read()


def _literal(src, name):
    """The value of a module-level literal assignment, by AST."""
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found as a module-level literal")


def _per_run_default(src, name):
    """The default of a `max(0, min(C, int(os.environ.get(NAME, "N"))))` line.

    Read as the shipped value: these are env-tunable, and the default is what
    every unattended run actually uses (no workflow sets any of them).
    """
    m = re.search(re.escape(name) + r'\s*=\s*max\(0,\s*min\(\d+,\s*int\(\s*os\.environ\.get\('
                  r'\s*"[A-Z_]+"\s*,\s*"(\d+)"\s*\)\s*\)\s*\)\s*\)', src)
    if m:
        return int(m.group(1))
    m = re.search(re.escape(name) + r'\s*=\s*max\(0,\s*min\(\d+,\s*_env_int\('
                  r'\s*"[A-Z_]+"\s*,\s*(\d+)\s*\)\s*\)\s*\)', src)
    if m:
        return int(m.group(1))
    raise AssertionError(f"could not read the shipped default for {name}")


class RotationCoversRing(unittest.TestCase):

    def _walk(self, hours, size, per_run, days=SIM_DAYS):
        """Which ring positions this cadence reaches over `days` of runs."""
        seen = set()
        start_day = datetime(2026, 8, 14, tzinfo=timezone.utc)
        for d in range(days):
            for h in hours:
                now = (start_day + timedelta(days=d)).replace(hour=h, minute=5)
                idx = run_slice.run_index(now)
                base = (idx * per_run) % size
                for i in range(per_run):
                    seen.add((base + i) % size)
        return seen

    def test_every_shipped_ring_is_fully_reached_at_every_cadence(self):
        for rel, terms_name, per_run_name in RINGS:
            src = _module_source(rel)
            terms = _literal(src, terms_name)
            per_run = _per_run_default(src, per_run_name)
            # google_news pins the US edition and rotates only the remainder.
            size = len(terms) - 1 if terms_name == "GOOGLE_NEWS_LOCALES" else len(terms)
            self.assertGreater(per_run, 0, f"{rel}:{per_run_name} ships disabled")
            for label, hours in CADENCES.items():
                with self.subTest(ring=f"{rel}:{terms_name}", cadence=label):
                    self._patch_hours(hours)
                    seen = self._walk(hours, size, per_run)
                    missing = sorted(set(range(size)) - seen)
                    self.assertEqual(
                        missing, [],
                        f"{rel}:{terms_name} ({size} terms, {per_run} per run) never "
                        f"reaches {len(missing)} position(s) at {label}. A term that "
                        f"is never queried is silent coverage loss, not slow "
                        f"coverage — see railway/run_slice.py.")

    def test_a_missed_run_cannot_strand_a_term(self):
        """Runs that die or never fire must delay a slice, never orphan it.

        Two of the last seven scheduled runs died mid-flight (2026-08-16 and
        2026-08-19, proven by the absent end-of-run record in
        railway/spend_jobs.json), so this is the ordinary case, not a corner.
        """
        self._patch_hours([22])
        src = _module_source("sources/gdelt.py")
        terms = _literal(src, "EUPHEMISM_TERMS")
        per_run = _per_run_default(src, "EUPHEMISM_QUERIES_PER_RUN")
        seen = set()
        start_day = datetime(2026, 8, 14, tzinfo=timezone.utc)
        for d in range(SIM_DAYS):
            if d % 3 == 0:          # every third run dies before it queries
                continue
            now = (start_day + timedelta(days=d)).replace(hour=22, minute=5)
            base = (run_slice.run_index(now) * per_run) % len(terms)
            for i in range(per_run):
                seen.add((base + i) % len(terms))
        self.assertEqual(sorted(seen), list(range(len(terms))),
                         "a run that dies must postpone its slice, not strand it")

    def test_run_index_advances_by_exactly_one_per_run(self):
        """The whole property rests on this: one run, one step."""
        for label, hours in CADENCES.items():
            with self.subTest(cadence=label):
                self._patch_hours(hours)
                seen = []
                start_day = datetime(2026, 12, 30, tzinfo=timezone.utc)
                for d in range(6):          # deliberately spans a year boundary
                    for h in hours:
                        now = (start_day + timedelta(days=d)).replace(hour=h, minute=5)
                        seen.append(run_slice.run_index(now))
                steps = {b - a for a, b in zip(seen, seen[1:])}
                self.assertEqual(steps, {1},
                                 f"{label}: run_index stepped by {sorted(steps)}, not 1. "
                                 f"tm_yday resets on 1 January; use the ordinal.")

    def test_unknown_schedule_repeats_rather_than_skips(self):
        """Failing safe has a direction, and only one of them keeps coverage."""
        run_slice.scheduled_utc_hours = lambda: None
        self.addCleanup(self._restore_hours)
        a = run_slice.run_index(datetime(2026, 8, 20, 13, 5, tzinfo=timezone.utc))
        b = run_slice.run_index(datetime(2026, 8, 20, 22, 5, tzinfo=timezone.utc))
        self.assertEqual(a, b, "an unreadable schedule must collapse a day's runs "
                              "onto one slice (a repeat), never spread them (a skip)")
        self.assertEqual(run_slice.FALLBACK_RUNS_PER_DAY, 1)

    def test_no_collector_hand_rolls_a_run_counter(self):
        """The arithmetic lives in one file, or it drifts back."""
        offenders = []
        # `tm_yday % N` is the same defect as `tm_yday * N`: a slice index
        # derived from the calendar rather than from the run counter. The euro
        # sweep in sources/gdelt.py carried exactly that until 2026-09-02, and
        # the first version of this pattern walked past it.
        pattern = re.compile(r"tm_yday\s*[*%]\s*[\dl(]|hour\s*<\s*17|hour\s*//\s*12")
        for root, _dirs, files in os.walk(RAILWAY):
            if "__pycache__" in root or f"{os.sep}tests" in root:
                continue
            for fn in files:
                if not fn.endswith(".py") or fn == "run_slice.py":
                    continue
                path = os.path.join(root, fn)
                # Tokenise rather than scan lines: the replaced sites are
                # DESCRIBED in the new docstrings, and a line scanner would
                # convict the explanation of being the defect.
                for line_no, code in _code_lines(path):
                    if pattern.search(code):
                        offenders.append(f"{os.path.relpath(path, RAILWAY)}:{line_no}")
        self.assertEqual(offenders, [],
                         "these compute a run slot from a hardcoded cadence; call "
                         "run_slice.rotate() instead: " + ", ".join(offenders))

    # -- helpers ----------------------------------------------------------
    def setUp(self):
        self._real_hours = run_slice.scheduled_utc_hours

    def tearDown(self):
        self._restore_hours()

    def _restore_hours(self):
        run_slice.scheduled_utc_hours = self._real_hours

    def _patch_hours(self, hours):
        run_slice.scheduled_utc_hours = lambda: list(hours)


class LiveScheduleIsReadable(unittest.TestCase):
    """The rotation must read the REAL cron, not the safe fallback, in prod."""

    def test_railway_toml_resolves(self):
        hours = run_slice.scheduled_utc_hours()
        self.assertTrue(hours, "railway.toml did not resolve, so every rotation is "
                               "running on the one-a-day fallback")
        import generate_ingest_schedule as gis
        expected = gis.parse_cron_schedule(gis.TOML.read_text(encoding="utf-8"))
        self.assertEqual(sorted(hours), sorted(expected["utc_hours"]),
                         "run_slice and generate_ingest_schedule disagree about the "
                         "cron; they must read one authority")


if __name__ == "__main__":
    unittest.main()
