"""ONE definition of "the invariant registry, with no live incident in it".

WHY THIS FILE EXISTS.

`railway/headline_incidents.json` is committed, mutable, and read by
`data_integrity.MovementInvariant` at run time. An entry under `open` makes its
slice report FAIL **deliberately and without consulting the network**, because
time, later rows and an unreachable API must never be able to close a finding a
human has not closed.

That is correct in production and poison in a unit test. Any test that calls
`data_integrity.check_all()` over the real registry inherits whatever incident
happens to be open on the day it runs, so a true statement about live data
answers a question the test never asked. Such a test passes for months and then
reddens on an unrelated adjudication that is nobody's defect.

FOUND 2026-09-09. `test_cloudflare_edge_unknown.py` shipped on 2026-09-08 doing
exactly this and went red the same week, when the `worldwide_all_time` incident
opened. `test_dedup_live.py` already carried a private `_without_open_incidents`
against the same hazard, written on 2026-08-22, and the new file could not
inherit a mitigation that lived inside another test module. So the mitigation
lives here now, once, and both import it.

WHAT THIS IS NOT. It does not relax an assertion, widen a tolerance, or make the
sticky-incident mechanism quieter. The incident still reports FAIL everywhere it
is read for real: `data_integrity.py` on its own registry, `ops_status.py [3]`,
the digest, and `test_dedup_live`'s own live pass. This only stops an OFFLINE
test from reading it. Pass `incidents_path` to point the guard at a FIXTURE
ledger when the incident behaviour itself is what you mean to exercise.
"""
from pathlib import Path

import data_integrity

#: A path that must never exist. `load_incidents` treats a MISSING file as an
#: empty ledger (it has to bootstrap) and raises on one that exists and does not
#: parse, so a name nothing writes is the cheapest empty ledger there is.
EMPTY_LEDGER = Path(__file__).with_name("no-such-incident-ledger.json")


def without_open_incidents(invariants, incidents_path=None):
    """`invariants`, with every MovementInvariant re-pointed off the live ledger.

    `incidents_path` defaults to EMPTY_LEDGER; give it a fixture path to test
    what an open incident does.
    """
    if incidents_path is None:
        incidents_path = EMPTY_LEDGER
        assert not EMPTY_LEDGER.exists(), (
            f"{EMPTY_LEDGER} must not exist - it stands in for an empty ledger")
    return tuple(
        data_integrity.MovementInvariant(incidents_path=incidents_path)
        if isinstance(i, data_integrity.MovementInvariant) else i
        for i in invariants)


def live_only(invariants):
    """`invariants`, keeping only the ones that actually read the live site.

    A structural invariant (`reads_live_data = False`, e.g. ErmProvenanceInvariant)
    answers from committed state - a measurement file, a register - and its
    verdict on any given day is independent of whatever fetch a transport test
    stubs in. Folding one into a transport-only or payload-only assertion
    inherits a real, unrelated finding the same way an open headline incident
    does above: `erm_provenance` reddened `test_cloudflare_edge_unknown`'s edge-
    blip claim and `test_dedup_live`'s empty-payload claim on 2026-09-09 when a
    genuine re-scored ERM row (179002, Cheminova) landed in the committed
    measurement, neither of which has anything to do with what either test
    means to exercise.
    """
    return tuple(i for i in invariants if getattr(i, "reads_live_data", True))
