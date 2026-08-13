"""HOW OLD IS THE COVERAGE COMPARISON? A DATE IS NOT A COMPETITOR FIGURE.

WHAT THIS GUARDS, AND WHY IT COULD NOT BE GUARDED THE OBVIOUS WAY.

The single most quotable number this project has is its coverage against an
independent US national survey of announced job cuts. It is the number a
journalist tests first. It was also, until this file, the least watched number
in the system: every other headline figure has a live invariant in
data_integrity.py, and this one had a line in `ops_status.py [6]` that said
"refresh vs-competitor read" and checked nothing at all. It was a reminder
wearing the clothes of a monitor, which is this codebase's signature defect and
the reason for the paragraph you are reading.

The reason it stayed unguarded is real and does not go away. Half of that ratio
is competitor data. Under the standing rule in CLAUDE.md no competitor or
commercial service name, and no competitor figure, may appear in this repo, in
a commit, in a workflow log, in Actions output, or on any public page. The
owner has confirmed that rule again. So the denominator cannot be stored here,
cannot be put in a secret, and cannot be fetched by a workflow that prints what
it found. The comparison itself must stay on the owner's machine, in the
local-only, gitignored `scratchpad/bm-live.html`.

WHAT IS AUTOMATABLE ANYWAY. A DATE. An age in days is not a figure and names
nobody. That is the whole idea here, and it is enough to have caught the thing
that was actually wrong.

MEASURED 2026-08-12, and this is what the file said on the day this was written.
Our own side of the ratio is recomputed daily by the owner's local refresher and
the US all-time numerator additionally has a live invariant (`us_all_time`,
country_basis=any) in data_integrity.py, so the numerator was never the exposure.
The comparator side is re-checked weekly and had moved on 2026-08-10. The
narrative paragraph that carries the headline percentage was computed on
2026-07-27, against the denominator that the weekly check superseded sixteen
days later, and nothing recomputed it or flagged it. The number being quoted all
week was a hand-written figure standing on a denominator that no longer existed.
No alarm anywhere in the system was capable of noticing that, because every
alarm that could have was forbidden from reading the only file that knew.

SO THIS FILE WATCHES TWO AGES AND EMITS NOTHING ELSE.

  A. COMPARATOR VERIFICATION AGE. The oldest date on which any comparator-side
     input was last verified, auto or by hand. A ratio is exactly as fresh as
     its denominator, so the oldest one governs and the freshest is not allowed
     to speak for the rest.

  B. NARRATIVE CLAIMS STANDING ON A SUPERSEDED DENOMINATOR. The count of
     hand-written ratio claims whose own date stamp predates the most recent
     comparator verification. Those are percentages that were true when typed
     and were never recomputed when the figure underneath them moved. This is
     the check that fires on the defect described above.

THE THRESHOLDS ARE THE REFRESHER'S REAL CADENCE, NOT A PREFERENCE. The owner's
local claim check runs on Mondays. One missed Monday is ordinary life, so DUE
opens at 8 days. Two missed Mondays is a loop that has stopped rather than a
week that got busy, so STALE opens at 15 days. A ceiling that does not match the
job's real cadence is permanent noise that hides real breakage, which this repo
has already paid for once on a weekly job wearing a two-day ceiling.

WHAT THIS FILE IS STRUCTURALLY INCAPABLE OF LEAKING, AND HOW.

`read_stamps()` is the only function that ever sees the benchmark's text, and it
returns `Stamps` — `datetime.date` objects and integers, nothing else. No string
from the file survives the parse. Every line this module prints is assembled
from that structure, so there is no path by which a name, a figure, a URL or a
sentence can reach stdout, a log, or a diff. That is a property of the shape
rather than of anyone's care while editing, which is the point.
`tests/test_benchmark_freshness.py` proves it by parsing a fixture stuffed with
invented names and figures and asserting that none of them appear in any
rendered line.

WHAT THIS DOES NOT DO, SAID PLAINLY. It does not recompute the ratio, it cannot
tell whether the comparison is CORRECT, and it will never replace the human. The
refresh stays manual, because the data may not leave the machine. All this does
is make an unrefreshed comparison visibly unrefreshed instead of silently
assumed. That is a smaller claim than "the coverage number is monitored" and it
is the true one.

Stdlib only, no keys, no network. Safe to run anywhere — and off the owner's
machine there is no file to read, which resolves to UNKNOWN and never to a pass.
"""
import argparse
import datetime
import os
import pathlib
import re
import sys

FRESH, DUE, STALE, UNKNOWN = "FRESH", "DUE", "STALE", "UNKNOWN"

# The comparator claim check runs weekly, on Mondays. One missed Monday is a
# busy week; two is a stopped loop. See the header on why these are the
# refresher's cadence rather than a taste.
COMPARATOR_DUE_DAYS = 8
COMPARATOR_STALE_DAYS = 15

# The benchmark is LOCAL ONLY and gitignored (the whole `scratchpad/` dir is, so
# a stray copy cannot be committed by accident). This module holds the path and
# never the contents.
DEFAULT_BENCHMARK = "scratchpad/bm-live.html"

_ISO = r"(\d{4})-(\d{2})-(\d{2})"

# Stamps the owner's local refresher writes. Each says "somebody or something
# last confirmed this input on this date". We read the DATE and discard the
# sentence it sat in.
_OUR_SIDE_RE = re.compile(r"auto-refresh\s+\w+\s+" + _ISO)
_COMPARATOR_RES = (
    # the weekly automated re-check of a comparator's own published claim
    ("auto", re.compile(r"checked\s+" + _ISO)),
    # a cell with no machine-readable claim page: a human typed it
    ("manual", re.compile(r"hand-entered\s+" + _ISO)),
    # the check ran and could not confirm the figure; the old value was kept,
    # so the input is as old as whenever it last DID confirm, not as old as this
    ("failed", re.compile(r"last check failed\s+" + _ISO)),
    ("failed", re.compile(r"figure not re-found\s+" + _ISO)),
)

# A hand-written ratio claim: a percentage and an ISO date inside one text node.
# Deliberately narrow. It matches the prose that carries a percentage and dates
# it, which is the only prose that can go stale without anything noticing, and
# it captures the DATE only — never the percentage, never the sentence.
_NARRATIVE_RE = re.compile(r">([^<>]{0,400}?%[^<>]{0,400}?)<", re.S)


def _repo_root():
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    return here.parent.parent


def benchmark_path():
    """Where the local-only benchmark lives. Overridable for the sibling repo."""
    override = os.environ.get("ALT_BENCHMARK_FILE")
    if override:
        return pathlib.Path(override).expanduser()
    return _repo_root() / DEFAULT_BENCHMARK


class Stamps:
    """Dates and counts. Never text from the file it was parsed out of.

    This class is the leak boundary. If a future edit wants to add a field here,
    the question to ask is not "is this useful" but "can this carry a name or a
    figure". Anything that can, does not belong.
    """

    def __init__(self, our_side=None, comparator=None, narrative=None):
        # date | None — when our own half of the ratio was last recomputed
        self.our_side = our_side
        # list[(kind, date)] — kind is one of "auto" / "manual" / "failed"
        self.comparator = sorted(comparator or [], key=lambda kd: kd[1])
        # list[date] — the date stamp each hand-written ratio claim carries
        self.narrative = sorted(narrative or [])

    @property
    def oldest_comparator(self):
        return self.comparator[0][1] if self.comparator else None

    @property
    def newest_comparator(self):
        return self.comparator[-1][1] if self.comparator else None

    def superseded_narrative(self):
        """Claims typed before the last time the denominator was re-verified.

        A percentage stamped earlier than the most recent comparator check was
        computed against a figure that has since been confirmed to have moved
        (or confirmed not to have — the stamp cannot tell which, and does not
        pretend to). Either way nobody recomputed it. Returns dates only.
        """
        newest = self.newest_comparator
        if newest is None:
            return []
        return [d for d in self.narrative if d < newest]


def _dates(pattern, text):
    out = []
    for m in pattern.finditer(text):
        try:
            out.append(datetime.date(int(m.group(1)), int(m.group(2)),
                                     int(m.group(3))))
        except ValueError:
            # A malformed stamp is not a date. Dropping it can only make the
            # verdict older and louder, never quieter, which is the safe way
            # for a staleness check to be wrong.
            continue
    return out


def read_stamps(text):
    """Parse dates out of the benchmark. THE ONLY FUNCTION THAT SEES ITS TEXT.

    Everything downstream consumes the returned `Stamps` and never `text`, which
    is what makes a leak a structural impossibility rather than a discipline.
    """
    ours = _dates(_OUR_SIDE_RE, text)
    comparator = []
    for kind, pattern in _COMPARATOR_RES:
        comparator.extend((kind, d) for d in _dates(pattern, text))

    narrative = []
    for m in _NARRATIVE_RE.finditer(text):
        segment = m.group(1)
        # One claim, one age: a sentence citing several dates is only as fresh
        # as its oldest input.
        found = _dates(re.compile(_ISO), segment)
        if found:
            narrative.append(min(found))

    return Stamps(our_side=max(ours) if ours else None,
                  comparator=comparator,
                  narrative=narrative)


class Result:
    """A verdict that can say it does not know, and lines safe to print."""

    def __init__(self, verdict, lines, stamps=None):
        self.verdict = verdict
        self.lines = lines
        self.stamps = stamps

    @property
    def needs_a_human(self):
        return self.verdict == STALE

    def exit_code(self):
        if self.verdict == UNKNOWN:
            return 3
        if self.verdict in (DUE, STALE):
            return 2
        return 0


def _age(day, today):
    return (today - day).days


def check(text=None, path=None, today=None, file_missing=False):
    """Grade the comparison's freshness. Returns a Result of dates and ages.

    `file_missing` is passed by callers that already know the benchmark is not
    on this machine, which is the normal state of every cloud session and is a
    genuine UNKNOWN rather than a fault.
    """
    today = today or datetime.date.today()

    if file_missing or text is None:
        return Result(UNKNOWN, [
            "UNKNOWN - the local benchmark is not on this machine, so nothing",
            "  here checked how old the coverage comparison is. The file is",
            "  local-only by design (competitor figures never enter the repo),",
            "  so this check only resolves on the owner's machine.",
            "  THIS IS NOT A PASS.",
        ])

    stamps = read_stamps(text)
    lines = []

    if stamps.our_side is None:
        lines.append("our side       UNKNOWN - no refresh stamp found in the file")
    else:
        lines.append("our side       recomputed %s (%dd ago), and the US "
                     "numerator also has" % (stamps.our_side.isoformat(),
                                             _age(stamps.our_side, today)))
        lines.append("               a live invariant in data_integrity.py "
                     "(us_all_time)")

    if not stamps.comparator:
        lines.append("comparison     UNKNOWN - no verification stamp found, so "
                     "the age of the")
        lines.append("               other half of the ratio could not be "
                     "established")
        return Result(UNKNOWN, lines, stamps)

    oldest, newest = stamps.oldest_comparator, stamps.newest_comparator
    oldest_age = _age(oldest, today)
    kinds = {}
    for kind, day in stamps.comparator:
        kinds.setdefault(kind, []).append(day)

    verdict = FRESH
    if oldest_age >= COMPARATOR_STALE_DAYS:
        verdict = STALE
    elif oldest_age >= COMPARATOR_DUE_DAYS:
        verdict = DUE

    lines.append("comparison     oldest input verified %s (%dd ago) -> %s"
                 % (oldest.isoformat(), oldest_age, verdict))
    lines.append("               newest %s; %s"
                 % (newest.isoformat(),
                    ", ".join("%d %s" % (len(v), k)
                              for k, v in sorted(kinds.items()))))

    superseded = stamps.superseded_narrative()
    if superseded:
        # This is the one that fires on a quoted percentage nobody recomputed.
        verdict = STALE
        lines.append("quoted ratios  %d hand-written ratio claim(s) are older "
                     "than the last" % len(superseded))
        lines.append("               denominator re-check (%s): stamped %s"
                     % (newest.isoformat(),
                        ", ".join(d.isoformat() for d in superseded)))
        lines.append("               Those percentages stand on a figure that "
                     "has since been")
        lines.append("               re-verified and were never recomputed. "
                     "Do not quote them.")
    elif stamps.narrative:
        lines.append("quoted ratios  %d claim(s), all at or after the last "
                     "denominator re-check"
                     % len(stamps.narrative))

    if verdict == STALE:
        lines.append("ACTION         refresh the comparison by hand, then "
                     "re-run this check.")
        lines.append("               See docs/RUNBOOK.md 'the coverage "
                     "comparison is stale'.")
    return Result(verdict, lines, stamps)


def check_file(path=None, today=None):
    path = pathlib.Path(path) if path else benchmark_path()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return check(file_missing=True, today=today)
    except OSError as exc:
        # It is here and we could not read it. That is a real unknown, and
        # naming the errno cannot leak the contents.
        return Result(UNKNOWN, [
            "UNKNOWN - the local benchmark exists but could not be read (%s)."
            % exc.__class__.__name__,
            "  THIS IS NOT A PASS.",
        ])
    return check(text=text, today=today)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="How old is the coverage comparison? Prints dates and ages "
                    "only - never a competitor name or figure.")
    ap.add_argument("--file", default=None,
                    help="path to the local-only benchmark (default: %s)"
                         % DEFAULT_BENCHMARK)
    args = ap.parse_args(argv)

    result = check_file(args.file)
    print("BENCHMARK COVERAGE COMPARISON: %s" % result.verdict)
    for line in result.lines:
        print("    %s" % line)
    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())
