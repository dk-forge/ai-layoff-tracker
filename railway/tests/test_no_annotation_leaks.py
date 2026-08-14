"""A passing test may exercise the annotation path. It may not emit one.

THE DEFECT THIS CLOSES
----------------------
GitHub Actions reads its runners' stdout for workflow commands: any line
beginning `::error::`, `::warning::` or `::notice::` becomes an annotation
rendered at the top of the run, in red, next to the real ones. This repository
emits them deliberately from about forty scripts, which is right — a stale
scraper or a held alert deserves to be visible without opening the log.

`tests/test_host_call_deferral.py` drove `host_call.main()` against a scripted
fake host, in a temporary ledger, for a job called `test-job` that has never
existed, and let the subject print. Three of its PASSING tests therefore hung
these on every run of `Tests`:

    ::error::test-job: the host reported the work failed: {'ok': False, 'failed': 3}
    ::error::test-job: the host reported error=bad request
    ::error::test-job has now deferred 3 times in a row. That is no longer an
             outage — the host is answering other jobs.

On 2026-08-14 a session read them off a red `Tests` run as an escalating job and
went looking for the three items the host had refused. There were none. The
"three" was a fixture body, and the streak was three synthetic 504s in a
tempdir. The false alarm cost more than the real failure in the same run.

WHY THIS IS A TEST AND NOT A CONVENTION
---------------------------------------
The suite has ~1,800 tests and grows weekly; "remember to capture stdout when
your subject annotates" is coverage by diligence, and the one you forget is the
one that mints a red annotation on a green run. So the check runs the modules
that could leak — the ones whose subject is a script that annotates — in a
subprocess, and reads what the runner would have read.

It is deliberately NOT a ban on `::error::` in library code. Those lines are the
point. What is banned is a TEST turning one into an annotation about a host that
was never called.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
RAILWAY = TESTS.parent

#: A workflow command at the start of a line is what the runner acts on.
_COMMAND = re.compile(r"^\s*::(error|warning|notice)\b", re.MULTILINE)

#: Modules whose SUBJECT annotates AND whose tests drive it end to end.
#: Discovered rather than listed, so a new test file that drives one of them is
#: covered the day it lands with nothing to remember.
#:
#: Deliberately not "every script that prints `::`". `spend`, `cron` and
#: `extractor` annotate too and their tests leak the same way ("spend: this run
#: has spent $1.0000, at or past the $0.200 per-run ceiling" is printed by a
#: green suite today), but running all of those here would be running the suite
#: twice. The universal net for those is in `.github/workflows/tests.yml`, which
#: defangs workflow commands coming out of the unittest step: nothing a
#: simulated world prints is an instruction to the runner. This guard is the
#: narrow, fast half — the deferral pair is what actually cost a session.
_ANNOTATING = ("host_call", "deferral_ledger")


def _modules_under_test():
    out = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue                      # never run ourselves: that recurses
        src = path.read_text(encoding="utf-8")
        if any(re.search(rf"^import {name}\b|^from {name} import", src, re.M)
               for name in _ANNOTATING):
            out.append(path.stem)
    return out


class NoTestLeaksAWorkflowCommand(unittest.TestCase):
    def test_the_annotating_modules_are_actually_covered(self):
        """A discovery that finds nothing would pass forever and prove nothing."""
        found = _modules_under_test()
        self.assertIn("test_host_call_deferral", found,
                      "the module that leaked is no longer being checked — the "
                      "discovery above stopped matching it")
        self.assertIn("test_job_deferrals", found, f"only found {found}")

    def test_no_annotation_reaches_the_runner(self):
        modules = _modules_under_test()
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", *modules],
            # From the tests directory, the way `unittest discover -s tests`
            # loads them: each module puts railway/ on sys.path itself.
            cwd=TESTS, capture_output=True, text=True, timeout=600,
        )
        leaked = [line for line in (proc.stdout + "\n" + proc.stderr).splitlines()
                  if _COMMAND.match(line)]
        self.assertEqual(
            leaked, [],
            "these tests printed GitHub workflow commands, so the runner will "
            "annotate a green run with them and someone will act on it:\n  "
            + "\n  ".join(leaked)
            + "\n\nCapture the subject's stdout (contextlib.redirect_stdout, or "
              "mock.patch.object(sys, 'stdout', ...)) and assert on the text "
              "instead of printing it.")
        # Proof the subprocess actually exercised something: a module that
        # failed to import would print nothing and pass this guard forever.
        # Whether those tests PASS is their own business — the suite runs them
        # directly, and this one must not go red on a laptop that is missing an
        # optional dependency.
        ran = re.search(r"^Ran (\d+) tests", proc.stderr, re.M)
        self.assertIsNotNone(ran, f"nothing ran:\n{proc.stderr[-2000:]}")
        self.assertGreater(int(ran.group(1)), 20,
                           "too few tests ran for the annotation paths to have "
                           "been exercised")


if __name__ == "__main__":
    unittest.main()
