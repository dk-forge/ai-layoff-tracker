"""The Hawaii OCR deadline must clear SETUP overhead too, not just the 60s tail.

THE DEFECT THIS CLOSES
-----------------------
`Hawaii WARN OCR import` run 45217500485 (job 137842496900, 2026-11-23) was
cancelled by the workflow's own `timeout-minutes: 30` -- the exact failure mode
`DEADLINE_SECONDS` exists to prevent (see the 2026-09-16 incident documented
next to that constant). It happened anyway: checkout, the pip-cache restore,
the spend guard, the secret check, tesseract and `pip install` together spent
446s of the job's shared 1800s wall clock before the OCR step even started
(the restore alone took 6m21s that run, a slow stretch on the self-hosted
runner's network -- `actions/setup-python@v6` logged a steady 2.2-3.4 MB/s for
an 808MB cache). That left only 1354s for a step whose own deadline was 1500s,
so the runner's kill fired at 1367s in, 133s before the script would have
stopped itself cleanly, and the run lost every notice it had OCR'd with no
terminal health note posted.

`tests/test_deadline_below_workflow_timeout.py` already pairs this deadline
against the workflow's kill, but only with a flat 60s margin for the clean-stop
tail -- it has no model of setup overhead, so a ceiling that is safe by that
test's arithmetic can still lose the race in practice. Setup overhead measured
across the runs of 2026-11-17 through 2026-11-23 (checkout through `pip
install`, before the OCR step starts): 96s, 98s, 124s, 136s, 244s, 446s -- real
variance, not a one-off, driven by how long the self-hosted runner's network
takes to restore the pip wheel cache.

This test encodes that measured worst case directly, so it is red against the
old 1500s ceiling and green once the ceiling leaves room for it.
"""
import sys
import unittest
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _requests_stub  # noqa: F401,E402
_requests_stub.install()
import hi_warn_import  # noqa: E402


class DeadlineClearsRealSetupOverhead(unittest.TestCase):

    #: Worst setup overhead (checkout -> pip install, before the OCR step
    #: starts) measured across the runs of 2026-11-17 to 2026-11-23. The
    #: 2026-11-23 run (446s) is the one the workflow cancelled.
    MEASURED_WORST_SETUP_OVERHEAD_SECONDS = 446
    #: hi-warn-import.yml's `timeout-minutes: 30`.
    WORKFLOW_TIMEOUT_SECONDS = 30 * 60
    #: The tail a clean stop needs: post the health note, write state, exit.
    CLEAN_STOP_MARGIN_SECONDS = 60

    def test_deadline_plus_worst_observed_setup_overhead_clears_the_kill(self):
        budget = (self.WORKFLOW_TIMEOUT_SECONDS
                  - self.MEASURED_WORST_SETUP_OVERHEAD_SECONDS
                  - self.CLEAN_STOP_MARGIN_SECONDS)
        self.assertLessEqual(
            hi_warn_import.DEADLINE_SECONDS, budget,
            f"DEADLINE_SECONDS={hi_warn_import.DEADLINE_SECONDS}s leaves no room "
            f"for the {self.MEASURED_WORST_SETUP_OVERHEAD_SECONDS}s of setup "
            f"overhead already observed plus the {self.CLEAN_STOP_MARGIN_SECONDS}s "
            f"clean-stop margin -- the workflow's own timeout fires first, exactly "
            f"as it did on run 45217500485 / job 137842496900.")


if __name__ == "__main__":
    unittest.main()
