"""An alarm nothing can clear is closed by a HUMAN, and dedup does not pay for it.

THE GAP THIS CLOSES. A cause raised by `ci_alert.build_alert` is keyed
`<workflow>:<branch>:<fingerprint>` and clears only when a green run of THAT
scope posts its resolve. `.github/workflows/tests.yml` fires on `pull_request`
and on pushes to `main`. So the moment a feature branch's PR lands, no run of
that scope will ever happen again: the entry is unclearable, and it earns one
`STILL FAILING` reminder every fourteen days about work that shipped.

This is not new behaviour — the endpoint-backed design had the identical gap and
`alert_outbox.json` is full of `resolve:tests:<feature-branch>` entries that had
nothing to clear. What changed on 2026-08-19 is that the ledger became a
committed file printed by `ops_status.py [4b2]`, so the residue is finally
VISIBLE. A visible stale record that nobody is allowed to touch is an invitation
to hand-edit the JSON, and hand-editing it is how the fourteen-day window and
the RECOVERED-once guarantee get broken without either failure announcing
itself. So there is now a sanctioned path, and it is the one
`data_integrity.close_incident` already established in this repo: a reviewer, a
reason, and evidence — here, WHERE THE CAUSE WAS FIXED.

TWO THINGS ARE UNDER TEST.

  1. THE CLOSE REFUSES A SHRUG, and writes nothing when it refuses. Every
     argument is a requirement. `--fixed-in` is the one worth arguing about and
     it is the one that matters most: a branch being parked is evidence about a
     branch, not about a defect. Closing an alarm whose cause is still live on
     main suppresses the NEXT genuine raise of it, which is the expensive
     mistake in both directions this ledger can fail.

  2. THE CLASSIFIER IS CONSERVATIVE IN ONE DIRECTION ONLY. Missing an orphan
     costs one stale line in a report. Inventing one sends a reviewer to close a
     LIVE alarm. So every uncertainty — remote silent, object not in a shallow
     checkout, a key shape that is not ci_alert's — lands on `open`.

     And the state that was actually in the ledger on 2026-08-19 was not the
     obvious one. `ops/resend-ua` was still on origin: PR #143 had merged and
     the ref was never deleted. A plain does-the-branch-exist check reads that
     as healthy and would have reported the stale entry as a live suppression
     forever, which is the whole defect wearing the fix's clothes.

WHAT IS NOT UNDER TEST HERE, because `test_ops_mail_split.py` already pins it:
one cause is one email, RECOVERED fires once, the 14-day window. A close removes
one entry exactly the way a `resolve` does, so the same cause raises again — one
email — the next time it happens. The only thing a close adds is an audit record
saying who decided and why.
"""
import io
import unittest.mock
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RAILWAY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAILWAY))

import alert_state  # noqa: E402
import ci_alert  # noqa: E402

KEY = "tests:ops-resend-ua:8f32a6ddbcaac88e"
SUBJECT = "CI RED: Tests — AssertionError: alt_company_index_strip is not guarded"
GOOD_REASON = ("the unguarded alt_company_index_strip() was fixed on main at "
               "2.20.111; the guard test passes there now")


class _Ledger:
    """A real alert_state.json in a temp dir, driven by the real code."""

    def __init__(self, open_entries=None):
        self._entries = open_entries if open_entries is not None else {
            KEY: {"first": 1787125267, "last": 1787125267, "subject": SUBJECT}}

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "alert_state.json"
        self.path.write_text(json.dumps(
            {"version": 1, "updated_at": "2026-08-19T09:29:56+00:00",
             "open": self._entries}))
        self._old = os.environ.get("ALERT_STATE_PATH")
        os.environ["ALERT_STATE_PATH"] = str(self.path)
        return self

    def __exit__(self, *exc):
        if self._old is None:
            os.environ.pop("ALERT_STATE_PATH", None)
        else:
            os.environ["ALERT_STATE_PATH"] = self._old
        self._tmp.cleanup()

    def doc(self):
        return json.loads(self.path.read_text())


def _cli(*argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = alert_state.main(list(argv))
    return code, buf.getvalue()


class AClosedAlarmCarriesAFinding(unittest.TestCase):
    def test_a_reviewed_close_removes_the_entry_and_records_who_and_why(self):
        with _Ledger() as led:
            rec = alert_state.close_alarm(KEY, reviewed_by="dak",
                                          reason=GOOD_REASON, fixed_in="2.20.111")
            doc = led.doc()
        self.assertEqual(doc["open"], {}, "the alarm is still open after a close")
        self.assertEqual(len(doc["closed"]), 1)
        stored = doc["closed"][0]
        self.assertEqual(stored["key"], KEY)
        self.assertEqual(stored["reviewed_by"], "dak")
        self.assertEqual(stored["fixed_in"], "2.20.111")
        self.assertEqual(stored["reason"], GOOD_REASON)
        self.assertEqual(stored["subject"], SUBJECT,
                         "the closed record must carry what the alarm SAID, or the "
                         "audit trail is a key and a shrug")
        self.assertEqual(rec["closed_at"], stored["closed_at"])

    def test_a_close_without_a_reviewer_writes_nothing(self):
        with _Ledger() as led:
            with self.assertRaises(ValueError):
                alert_state.close_alarm(KEY, reviewed_by="", reason=GOOD_REASON,
                                        fixed_in="2.20.111")
            self.assertIn(KEY, led.doc()["open"])

    def test_a_one_word_reason_is_refused_and_writes_nothing(self):
        with _Ledger() as led:
            with self.assertRaises(ValueError):
                alert_state.close_alarm(KEY, reviewed_by="dak", reason="fixed",
                                        fixed_in="2.20.111")
            self.assertIn(KEY, led.doc()["open"],
                          "an alarm closed with 'fixed' is one nobody can audit later")

    def test_fixed_in_is_required_because_a_parked_branch_proves_nothing(self):
        """The load-bearing one.

        A branch being merged or deleted is a fact about a BRANCH. The alarm is
        about a DEFECT. If nobody can name where the cause was fixed, it may
        still be live on main, and closing the alarm means the next genuine
        occurrence of it raises into a ledger that has already been told this
        cause is resolved.
        """
        with _Ledger() as led:
            with self.assertRaises(ValueError) as ctx:
                alert_state.close_alarm(KEY, reviewed_by="dak", reason=GOOD_REASON,
                                        fixed_in="")
            self.assertIn("--fixed-in", str(ctx.exception))
            self.assertIn(KEY, led.doc()["open"])

    def test_closing_a_key_that_is_not_open_writes_nothing(self):
        with _Ledger() as led:
            with self.assertRaises(ValueError):
                alert_state.close_alarm("tests:main:0000000000000000",
                                        reviewed_by="dak", reason=GOOD_REASON,
                                        fixed_in="2.20.111")
            self.assertEqual(sorted(led.doc()["open"]), [KEY])

    def test_the_closed_history_is_capped_and_keeps_the_newest(self):
        many = {f"tests:b{i}:{i:016x}": {"first": i, "last": i, "subject": f"s{i}"}
                for i in range(alert_state.MAX_CLOSED + 5)}
        with _Ledger(many) as led:
            for k in sorted(many):
                alert_state.close_alarm(k, reviewed_by="dak", reason=GOOD_REASON,
                                        fixed_in="2.20.111")
            history = led.doc()["closed"]
        self.assertEqual(len(history), alert_state.MAX_CLOSED)


class TheCommandLineDoesNotLie(unittest.TestCase):
    """`close_incident`'s own scar: the one command a human is REQUIRED to run
    wrote the ledger and then crashed printing the summary, so every successful
    close read as a failure and invited a re-run."""

    def test_a_successful_close_exits_zero_and_prints_what_it_stored(self):
        with _Ledger() as led:
            code, out = _cli("--close", KEY, "--reviewed-by", "dak",
                             "--reason", GOOD_REASON, "--fixed-in", "2.20.111")
            self.assertEqual(led.doc()["open"], {})
        self.assertEqual(code, 0, f"a successful close exited {code}:\n{out}")
        self.assertIn("CLOSED", out)
        self.assertIn("2.20.111", out)
        self.assertIn("dak", out)

    def test_a_refused_close_exits_two_and_says_nothing_was_written(self):
        with _Ledger() as led:
            code, out = _cli("--close", KEY, "--reviewed-by", "dak",
                             "--reason", "fixed", "--fixed-in", "2.20.111")
            self.assertIn(KEY, led.doc()["open"])
        self.assertEqual(code, 2)
        self.assertIn("Nothing was written", out)

    def test_the_listing_never_crashes_on_a_status_it_cannot_spell(self):
        """Same defect class as the crash above, one layer up. Every status the
        classifier can emit must render, so a new one added later degrades to a
        blank tag rather than a traceback on the ops report."""
        with _Ledger():
            for status in (alert_state.OPEN, alert_state.ORPHANED,
                           alert_state.MERGED, alert_state.UNKNOWN, "a-new-word"):
                rows = [(KEY, "2026-08-19T07:41:07+00:00",
                         "2026-08-19T07:41:07+00:00", SUBJECT, status)]
                with unittest.mock.patch.object(alert_state, "classify_open",
                                                return_value=rows):
                    code, _out = _cli()
                self.assertEqual(code, 0, f"the listing crashed on status {status!r}")


class WhatCanNeverClearItself(unittest.TestCase):
    #: origin as it stood on 2026-08-19: main, plus the parked ops/resend-ua.
    REMOTE = {"main": "a" * 40, "ops-resend-ua": "b" * 40, "live-work": "c" * 40}

    def _classify(self, remote=REMOTE, ancestor=None, entries=None):
        with _Ledger(entries) as _led:
            return {k: st for k, _f, _l, _s, st in alert_state.classify_open(
                remote=remote, is_ancestor=ancestor or (lambda a, b: False))}

    def test_a_branch_gone_from_origin_is_orphaned(self):
        got = self._classify(remote={"main": "a" * 40})
        self.assertEqual(got[KEY], alert_state.ORPHANED)

    def test_a_merged_but_undeleted_branch_is_the_case_that_was_actually_open(self):
        """2026-08-19: `ops/resend-ua` was still on origin. PR #143 had merged
        and the ref was never deleted, so a does-the-branch-exist check reads it
        as healthy and the stale entry sits there forever."""
        got = self._classify(ancestor=lambda sha, main: sha == "b" * 40)
        self.assertEqual(got[KEY], alert_state.MERGED)

    def test_a_live_branch_is_left_alone(self):
        entries = {"tests:live-work:1234567890abcdef":
                   {"first": 1, "last": 1, "subject": "s"}}
        got = self._classify(entries=entries)
        self.assertEqual(list(got.values()), [alert_state.OPEN])

    def test_a_silent_remote_is_unknown_and_never_orphaned(self):
        """`remote_branches` returns None when there is no network, no remote or
        an egress block. Reading that as an empty remote would orphan every
        alarm in the ledger at once."""
        with _Ledger():
            rows = alert_state.classify_open(remote=True)
            # Drive the real path with the real helper stubbed to "unanswerable".
            import unittest.mock as m
            with m.patch.object(alert_state, "remote_branches", return_value=None):
                rows = alert_state.classify_open(remote=True)
        self.assertEqual([r[4] for r in rows], [alert_state.UNKNOWN])

    def test_not_asking_is_not_unknown(self):
        """The default listing is offline and says nothing about branches. That
        is a third state, and printing `branch?` against every alarm because
        nobody looked is noise on the report that exists to cut noise."""
        with _Ledger():
            rows = alert_state.classify_open()
        self.assertEqual([r[4] for r in rows], [alert_state.OPEN])

    def test_a_shallow_checkout_cannot_prove_merged_and_says_open(self):
        """`git merge-base --is-ancestor` on an object a shallow clone does not
        hold exits non-zero, which is indistinguishable from 'no'. `_is_ancestor`
        answers None there, and None must land on OPEN."""
        got = self._classify(ancestor=lambda sha, main: None)
        self.assertEqual(got[KEY], alert_state.OPEN)

    def test_a_live_data_key_is_never_branch_judged(self):
        """Branch-free by design: a live-data incident is one alarm across every
        branch and ANY branch's green run clears it. Reading `live.data` as a
        deleted branch would mark a genuinely clearable alarm unclearable."""
        key = f"tests:{alert_state.LIVE_DATA_SEGMENT}:2e215caae5bac21b"
        got = self._classify(remote={"main": "a" * 40},
                             entries={key: {"first": 1, "last": 1, "subject": "s"}})
        self.assertEqual(got[key], alert_state.OPEN)
        self.assertIsNone(alert_state.branch_slug(key))

    def test_another_senders_key_shape_is_never_read_as_a_branch(self):
        """Other senders put their own keys in this ledger. `ci-noise:2026-w33`
        is an ISO week, and a loose pattern would read it as a deleted branch and
        declare a live alarm unclearable."""
        for key in ("ci-noise:2026-w33", "relabel-hold:114335-113529",
                    "tests:main", "tests:some-branch:nothexdigits!!"):
            self.assertIsNone(alert_state.branch_slug(key), key)


class TheTwoSpellingsOfABranchStayTogether(unittest.TestCase):
    def test_the_slug_matches_ci_alerts_exactly(self):
        """`ci_alert` bakes `_slug(branch, 32)` into the scope and imports THIS
        module, so the function cannot be imported back and is duplicated. The
        duplicate has to agree, or a real branch stops matching its own key and
        every live alarm reads as orphaned.

        `ops/resend-ua` is in the list on purpose: the slash is why comparing
        branch NAMES would have failed.
        """
        for name in ("main", "ops/resend-ua", "claude/clever-solomon-d1e879",
                     "Feature_Branch", "a" * 60, "", "///"):
            self.assertEqual(alert_state._slug(name, 32), ci_alert._slug(name, 32),
                             f"the two slugs disagree on {name!r}")

    def test_the_live_data_segment_matches_ci_alerts_exactly(self):
        self.assertEqual(alert_state.LIVE_DATA_SEGMENT, ci_alert.LIVE_DATA_SEGMENT)

    def test_a_real_ci_alert_key_round_trips_back_to_its_branch(self):
        """The end-to-end claim, built by the real minting code rather than a
        hand-typed string: whatever `build_alert` produces, `branch_slug` reads
        the branch back out of it."""
        _subj, _body, key = ci_alert.build_alert(
            repo="dk-forge/ai-layoff-tracker", workflow="Tests",
            branch="ops/resend-ua", event="push", run_url="u", run_id="1",
            cause="AssertionError: alt_company_index_strip is not guarded",
            context="")
        self.assertEqual(alert_state.branch_slug(key), "ops-resend-ua")


class ClosingIsNotAWayAroundDedup(unittest.TestCase):
    def test_the_same_cause_raises_again_after_a_close(self):
        """A close is not an immunity. It removes one entry exactly the way a
        `resolve` does, so if the defect comes back the owner is told — once."""
        with _Ledger() as led:
            alert_state.close_alarm(KEY, reviewed_by="dak", reason=GOOD_REASON,
                                    fixed_in="2.20.111")
            payload = {"subject": SUBJECT, "body": "b", "dedupe_key": KEY}
            state = alert_state.load(led.path)
            first = alert_state.decide(state, payload)
            self.assertEqual(first.kind, "raise",
                             "a closed cause that recurs must alarm again")
            alert_state.apply(state, first)
            self.assertEqual(alert_state.decide(state, payload).kind, "silent",
                             "and then be deduped exactly as before")

    def test_a_close_touches_nothing_but_the_one_key(self):
        entries = {KEY: {"first": 1, "last": 1, "subject": SUBJECT},
                   "tests:main:aaaaaaaaaaaaaaaa": {"first": 2, "last": 2,
                                                   "subject": "other"}}
        with _Ledger(entries) as led:
            alert_state.close_alarm(KEY, reviewed_by="dak", reason=GOOD_REASON,
                                    fixed_in="2.20.111")
            doc = led.doc()
        self.assertEqual(sorted(doc["open"]), ["tests:main:aaaaaaaaaaaaaaaa"])
        self.assertEqual(doc["open"]["tests:main:aaaaaaaaaaaaaaaa"]["first"], 2,
                         "a close must not restamp an untouched alarm — the age "
                         "of an open alarm is the most useful thing about it")

    def test_the_reminder_window_is_untouched(self):
        self.assertEqual(alert_state.REMIND_AFTER_SECONDS, 14 * 24 * 3600)


class TheRunbookOffersTheSanctionedPath(unittest.TestCase):
    """The section that said 'never hand-edit the ledger' offered no
    alternative, which is how a hand edit happens anyway."""

    RUNBOOK = RAILWAY.parent / "docs" / "RUNBOOK.md"

    def test_the_playbook_exists_and_names_the_command(self):
        text = self.RUNBOOK.read_text(encoding="utf-8")
        self.assertIn("AN OPEN ALARM CANNOT CLEAR ITSELF", text.upper())
        self.assertIn("--close", text)
        self.assertIn("--fixed-in", text)
        self.assertIn("--reviewed-by", text)


if __name__ == "__main__":
    import unittest.mock  # noqa: F401  - used above
    unittest.main()
