"""A janitor deletes what it has read, never what it failed to read.

`errornotifications-sandbox@` held 2,106 unread messages growing at ~31/day,
and buried in them was exactly ONE live problem: a weekly job on main failing
for two weeks. One real signal in 2,106 is not a channel, it is a place signals
go to die. So this reads the mailbox, says what is in it, escalates anything
that looks like it matters, and clears the rest.

The risk in automating a delete over 2,000 real messages is obvious, and these
tests are the line: a retention window so a human can still look, and an
absolute refusal to delete anything not successfully read and dated.
"""
from __future__ import annotations

import email.message
import email.utils
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from mailbox_janitor import OK, REJECTED, _classify, sweep  # noqa: E402

NOW = datetime.now(timezone.utc)


def _msg(subject: str, sender: str, age_days: float | None) -> bytes:
    m = email.message.EmailMessage()
    m["Subject"] = subject
    m["From"] = sender
    if age_days is not None:
        m["Date"] = email.utils.format_datetime(NOW - timedelta(days=age_days))
    m.set_content("body")
    return m.as_bytes()


class _Conn:
    def __init__(self, msgs, refuse_login=False, unreadable=()):
        self.map = {str(i + 1).encode(): b for i, b in enumerate(msgs)}
        self.refuse_login = refuse_login
        self.unreadable = {str(i).encode() for i in unreadable}
        self.deleted: list[bytes] = []
        self.expunged = False

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def login(self, u, p):
        if self.refuse_login:
            import imaplib
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, box): return ("OK", [b"1"])
    def search(self, c, t): return ("OK", [b" ".join(self.map)])

    def fetch(self, spec, fields):
        """Emulate a BATCHED fetch: "1,2,3" in, interleaved tuples out.

        Real IMAP returns (b"<num> (BODY[...] {size}", payload) tuples with a
        bare b")" separator between them, and the message id is only
        recoverable from that metadata prefix. The double has to reproduce that
        shape or the test proves nothing about the parsing.
        """
        nums = [n.encode() for n in spec.split(",")]
        out = []
        for n in nums:
            if n in self.unreadable:
                continue
            out.append((b"%s (BODY[HEADER] {%d}" % (n, len(self.map[n])), self.map[n]))
            out.append(b")")
        return ("OK", out)

    def store(self, num, flags, value):
        self.deleted.append(num); return ("OK", [b""])

    def expunge(self):
        self.expunged = True; return ("OK", [b""])


def _patch(conn, monkeypatch):
    import mailbox_janitor
    monkeypatch.setattr(mailbox_janitor.imaplib, "IMAP4_SSL", lambda *a, **k: conn)


def test_only_messages_older_than_the_window_are_cleared(monkeypatch) -> None:
    conn = _Conn([
        _msg("Run failed: Frontend CI", "notifications@github.com", 30),
        _msg("Run failed: Frontend CI", "notifications@github.com", 2),
    ])
    _patch(conn, monkeypatch)
    state, f, _ = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert state == OK
    assert conn.deleted == [b"1"], "a recent message must survive for a human to see"
    assert f["removed"] == 1


def test_a_message_it_could_not_read_is_never_deleted(monkeypatch) -> None:
    """A janitor that deletes what it failed to parse destroys the evidence
    of its own bug."""
    conn = _Conn([
        _msg("Run failed", "notifications@github.com", 30),
        _msg("Run failed", "notifications@github.com", 30),
    ], unreadable=(1,))
    _patch(conn, monkeypatch)
    state, f, _ = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert f["unreadable"] == 1
    assert conn.deleted == [b"2"]


def test_an_undated_message_is_never_deleted(monkeypatch) -> None:
    """Without a Date header its age is unknown, and unknown is not old."""
    conn = _Conn([_msg("Run failed", "notifications@github.com", None)])
    _patch(conn, monkeypatch)
    sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert conn.deleted == []


def test_dry_run_deletes_nothing_but_still_counts(monkeypatch) -> None:
    conn = _Conn([_msg("Run failed", "notifications@github.com", 40)])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert f["eligible"] == 1 and f["removed"] == 0
    assert conn.deleted == [] and conn.expunged is False


def test_something_that_matters_is_escalated(monkeypatch) -> None:
    """The whole point: one real signal must not be summarised away."""
    conn = _Conn([
        _msg("Run failed: Frontend CI", "notifications@github.com", 30),
        _msg("Deployment crashed: production backend", "railway@railway.app", 30),
    ])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert any("production" in s for s in f["escalate"]), f["escalate"]


def test_routine_noise_is_not_escalated(monkeypatch) -> None:
    """A list that matches everything reports nothing."""
    conn = _Conn([_msg("Bump vitest from 4 to 5", "notifications@github.com", 30)])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert f["escalate"] == []


def test_our_own_ops_mail_is_routine_never_escalated(monkeypatch) -> None:
    """2026-09-10 and 09-11: the janitor read its own RECOVERED notice
    ("... Mailbox janitor: Something in the notification mailbox needs a
    human"), classified it "other", escalated, and went red about itself two
    days running. Our stamped ops mail is a copy of a ledger entry, routine
    here exactly as GitHub's own notifications are."""
    ops = "AI Layoff Tracker Ops <ops@asktherecruiter.com>"
    recovered = ("[AI Layoff Tracker] RECOVERED: CI RED: Mailbox janitor: "
                 "Something in the notification mailbox needs a human")
    unread = ("[AI Layoff Tracker] CI RED: Mailbox janitor: The mailbox could "
              "not be read. UNKNOWN, not a pass.")
    assert _classify(recovered, ops) == "ops mail (ours)"
    assert _classify(unread, "someone@example.com") == "ops mail (ours)"
    assert _classify("Fwd: [AI Layoff Tracker] weekly health digest", ops) == "ops mail (ours)"
    conn = _Conn([_msg(recovered, ops, 2), _msg(unread, ops, 2)])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert f["escalate"] == [], f["escalate"]


def test_an_unknown_shape_still_escalates() -> None:
    """The class for our mail must not widen 'other' out of existence."""
    assert _classify("Your account has been suspended", "abuse@host.example") == "other"


def test_a_refused_login_is_rejected_and_touches_nothing(monkeypatch) -> None:
    conn = _Conn([_msg("x", "y@z", 40)], refuse_login=True)
    _patch(conn, monkeypatch)
    state, _f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert state == REJECTED
    assert conn.deleted == []


def test_the_observed_traffic_classifies_rather_than_falling_to_other() -> None:
    """Built from what was actually measured in the real mailbox."""
    assert _classify("Bump x from 1 to 2", "notifications@github.com") == "github: dependabot"
    assert _classify("Run failed: Backend Architecture Gate", "notifications@github.com") == "github: run failed"
    assert _classify("Build failed - ATR-Sandbox", "railway@railway.app") == "railway: build failed"
    assert _classify("Deployment crashed", "railway@railway.app") == "railway: deploy crashed"


def test_a_dropped_connection_mid_sweep_deletes_nothing(monkeypatch) -> None:
    """MEASURED 2026-09-08: a single-session sweep of a 2,106-message mailbox
    had its connection closed ("EOF occurred in violation of protocol").

    A partial pass is still useful, but its counts are partial, and a delete
    decision taken on partial information is how the wrong thing gets removed
    quietly. So a truncated sweep reports what it saw and deletes none of it.
    """
    class _Dropping(_Conn):
        def fetch(self, spec, fields):
            raise OSError("EOF occurred in violation of protocol")

    msgs = [_msg("Run failed", "notifications@github.com", 40) for _ in range(3)]
    conn = _Dropping(msgs)
    _patch(conn, monkeypatch)
    state, f, detail = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert state == OK
    assert f["partial"] is True
    assert "PARTIAL" in detail
    assert conn.deleted == [], "a truncated sweep must not delete on partial counts"


def test_the_real_subjects_that_broke_escalation_do_not_escalate(monkeypatch) -> None:
    """THE regression guard, written from live traffic rather than invention.

    The first escalation rule matched the word "main". GitHub puts the branch
    in every notification subject, so all 251 CI failures in a 400-message
    sample escalated and the report said nothing. A synthetic fixture (a
    dependency bump) passed the "routine noise" test and let it ship.

    These are verbatim subjects from the real mailbox.
    """
    real = [
        "[dk-forge/asktherecruiter-sandbox] Run failed: Frontend CI - main",
        "[dk-forge/asktherecruiter-sandbox] Run failed: Backend Architecture Gate - main",
        "[dk-forge/asktherecruiter-sandbox] Run failed: Production E2E Gate - main",
        "Build failed - ATR-Sandbox",
    ]
    conn = _Conn([_msg(s, "notifications@github.com", 30) for s in real])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert f["escalate"] == [], (
        f"CI outcomes must not escalate; they are watched via the API. Got: "
        f"{f['escalate']}"
    )


def test_a_mime_encoded_subject_still_classifies_and_does_not_escalate(monkeypatch) -> None:
    """A second way a real subject broke escalation, distinct from the "main"
    regression above.

    GitHub Q-encodes the ENTIRE Subject header (RFC 2047), not just the
    non-ASCII part, whenever the subject contains so much as one em-dash or
    emoji -- ordinary for a PR title. `_classify` matched literal text like
    "run failed", but the raw undecoded header carries "run_failed" (Q-encoding
    turns every space into "_") split across wrapped encoded-words, so the
    match never fires, the message falls through to "other", and "other"
    always escalates. Verbatim (line-wrapped, multi-encoded-word) header from
    the real sandbox mailbox.
    """
    raw = (
        b"Subject: =?utf-8?q?[dk-forge/asktherecruiter-sandbox]_PR_run_failed:_Frontend_CI_-?=\n"
        b" =?utf-8?q?_Wave_D_=E2=80=94_merge_conflict?=\n"
        b"From: notifications@github.com\n"
        b"Date: " + email.utils.format_datetime(NOW - timedelta(days=30)).encode() + b"\n\n"
        b"body"
    )
    conn = _Conn([raw])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert f["escalate"] == [], (
        f"a routine CI failure with an encoded subject must not escalate; got: {f['escalate']}"
    )


def test_a_crashed_deployment_escalates_even_with_a_dull_subject(monkeypatch) -> None:
    """The signal genuinely not covered anywhere else. It escalates on its
    CLASS, so it does not depend on alarming words appearing in the subject."""
    conn = _Conn([_msg("Deployment crashed", "railway@railway.app", 30)])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert len(f["escalate"]) == 1


def test_repeats_of_one_subject_collapse_to_one_finding(monkeypatch) -> None:
    """16 copies of one subject is one finding. Printing it 16 times buries
    everything else, which is how a report becomes unreadable."""
    conn = _Conn([_msg("Deployment crashed", "railway@railway.app", 30)
                  for _ in range(16)])
    _patch(conn, monkeypatch)
    _s, f, _d = sweep("h", "u", "pw", retain_days=14, dry_run=True)
    assert len(f["escalate"]) == 1
    assert "x16" in f["escalate"][0]


def test_a_session_that_dies_at_logout_does_not_erase_the_sweep(monkeypatch) -> None:
    """MEASURED 2026-09-08, and it is why every janitor run on record was red.

    The sweep read the mailbox, classified it and deleted what it had read,
    and then IMAP4_SSL.__exit__ called LOGOUT on a connection the server had
    already dropped after being made to delete and expunge. The exception
    escaped the teardown, the whole sweep resolved to UNKNOWN, and the run
    reported "the mailbox could not be read" while messages were in fact
    being cleared. Work that already happened must not be invalidated by the
    closing of the session that did it.
    """
    class _DiesAtLogout(_Conn):
        def logout(self):
            import ssl
            raise ssl.SSLEOFError("EOF occurred in violation of protocol")

        def __exit__(self, *a):
            self.logout()

    conn = _DiesAtLogout([_msg("Run failed", "notifications@github.com", 40)])
    _patch(conn, monkeypatch)
    state, f, detail = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert state == OK, f"a dead logout must not become the verdict, got {state}"
    assert f["removed"] == 1
    assert f["unclean_logout"] is True, "and it must be reported, not swallowed"
    assert "logout" in detail


# This suite is unittest, not pytest (#288). Without this, every test above is
# collected as nothing at all and the file passes by never running.
from _pytest_bridge import bind  # noqa: E402

MailboxJanitorTests = bind(globals(), "MailboxJanitorTests")
