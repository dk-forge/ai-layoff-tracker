"""READER-FACING COPY ABOUT A CREDENTIAL IS DERIVED, NOT TYPED.

WHAT HAPPENED. JOBINDSATS_API_KEY became a repository secret on 2026-08-13.
No code read it, so nothing here could tell whether it worked, and the public
country table went on saying "Jobindsats varsel API: key application pending"
for 27 days after the application had already succeeded. A dispatched probe on
2026-09-09 got HTTP 200 from /v3/tables?format=json while the same request
with no token, and with a bogus one, was refused 401 before routing.

Two different defects made that possible and both are guarded here.

1. THE CLAIM WAS A STRING. "key application pending" lived in
   generate_country_table.py as literal text, so no run, no test and no
   session could contradict it. It is now composed by `denmark_blurb()` from
   railway/source_credentials.json, whose `state` may only be moved by
   somebody who watched the API answer and who leaves the run link behind.

2. "THE KEY WORKS" IS NOT "DATA FLOWS". Those are separate claims and the
   second one is expensive: a verified credential with no collector behind it
   ingests exactly nothing. The blurb may speak of ingestion only once
   railway/sources/<id>.py exists and cron.py runs it, which is a fact about
   the code and cannot be asserted by editing copy.

The same lesson as tests/test_cadence_is_derived.py, in a place a cadence
scanner cannot see: a credential's state is not a cadence, but it is equally a
fact the repository can read and equally wrong to type.
"""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(RAILWAY, ".."))
if RAILWAY not in sys.path:
    sys.path.insert(0, RAILWAY)

import generate_country_table as gct  # noqa: E402

PARTIAL = os.path.join(
    ROOT, "wordpress-plugin", "ai-layoff-tracker", "templates", "partials",
    "country-sources-table.php")

#: Wording that tells a reader an application is still outstanding.
PENDING = re.compile(
    r"key application pending|application pending|awaiting (?:a |an )?(?:key|credential)"
    r"|pending (?:a |an )?(?:key|credential|api key)", re.I)

#: Wording that asserts data is arriving. `not yet ingested` is the honest
#: form and is excluded by the negative lookbehind on "not yet".
FLOWING = re.compile(
    r"(?<!not yet )\b(?:ingested|ingesting|imported|live|feeding|feeds)\b"
    r"|\b(?:daily|hourly|weekly|monthly)\s+(?:import|ingest|pull)", re.I)


def _denmark_cell():
    with open(PARTIAL, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("<tr><th>Denmark</th>"):
                cells = re.findall(r"<td>(.*?)</td>", line, re.S)
                return cells[0] if cells else ""
    return ""


class TheCredentialLedgerIsReadable(unittest.TestCase):

    def test_every_entry_has_a_state_and_evidence_for_it(self):
        with open(os.path.join(RAILWAY, "source_credentials.json"),
                  encoding="utf-8") as fh:
            rows = json.load(fh).get("credentials", {})
        self.assertTrue(rows, "the credential ledger is empty")
        for secret, row in rows.items():
            with self.subTest(secret=secret):
                self.assertIn(row.get("state"), ("VERIFIED", "REFUSED", "UNTESTED"))
                if row.get("state") in ("VERIFIED", "REFUSED"):
                    self.assertTrue(row.get("checked_at"),
                                    "a settled state needs the date it was settled")
                    self.assertTrue(row.get("evidence"),
                                    "a settled state needs a link to the run that "
                                    "watched it, or it is an assertion again")

    def test_an_unknown_state_reads_as_untested_not_as_a_pass(self):
        self.assertEqual(("UNTESTED", ""), gct.credential_state("NO_SUCH_SECRET"))


class TheCopyMatchesWhatIsRecorded(unittest.TestCase):

    def test_the_committed_partial_carries_the_derived_blurb(self):
        self.assertEqual(
            gct.denmark_blurb(), _denmark_cell(),
            "the public Denmark cell disagrees with what the ledger and the "
            "code say. Re-run python3 railway/generate_country_table.py")

    def test_a_verified_credential_is_never_described_as_pending(self):
        state, _ = gct.credential_state("JOBINDSATS_API_KEY")
        if state != "VERIFIED":
            self.skipTest("the Jobindsats credential is not currently VERIFIED")
        for where, text in (("the generated cell", _denmark_cell()),
                            ("denmark_blurb()", gct.denmark_blurb())):
            with self.subTest(where=where):
                self.assertIsNone(
                    PENDING.search(text),
                    "%s still tells the reader an application is outstanding, "
                    "for a key a run has watched authenticate: %r" % (where, text))

    def test_no_ingestion_is_claimed_before_the_collector_exists(self):
        if gct.collector_is_built("jobindsats"):
            self.skipTest("the collector exists, so ingestion may be described")
        text = gct.denmark_blurb()
        self.assertIsNone(
            FLOWING.search(text),
            "the copy implies Danish data is arriving, but there is no "
            "railway/sources/jobindsats.py that cron.py runs: %r" % text)
        self.assertIn("not yet ingested", text,
                      "a verified key with no collector has to say so plainly")


class TheExistenceTestCannotBeSatisfiedByCopy(unittest.TestCase):
    """A dispatch-only probe workflow NAMES the id. That must not read as a
    collector: source_inventory's corpus test is deliberately the weakest
    possible test of existence, and reusing it here would let a diagnostic
    vouch for a source it only asked a question about."""

    def test_naming_the_id_in_a_workflow_is_not_a_collector(self):
        self.assertFalse(gct.collector_is_built("jobindsats"))
        named = False
        wf = os.path.join(ROOT, ".github", "workflows")
        for name in os.listdir(wf):
            with open(os.path.join(wf, name), encoding="utf-8", errors="ignore") as fh:
                if "jobindsats" in fh.read().lower():
                    named = True
        self.assertTrue(named, "the probe workflow should name the id")


if __name__ == "__main__":
    unittest.main()
