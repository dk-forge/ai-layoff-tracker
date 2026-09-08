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

    def fetch(self, num, spec):
        if num in self.unreadable:
            return ("NO", None)
        return ("OK", [(b"1", self.map[num])])

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
        def fetch(self, num, spec):
            if num == b"2":
                raise OSError("EOF occurred in violation of protocol")
            return super().fetch(num, spec)

    msgs = [_msg("Run failed", "notifications@github.com", 40) for _ in range(3)]
    conn = _Dropping(msgs)
    _patch(conn, monkeypatch)
    state, f, detail = sweep("h", "u", "pw", retain_days=14, dry_run=False)
    assert state == OK
    assert f["partial"] is True
    assert "PARTIAL" in detail
    assert conn.deleted == [], "a truncated sweep must not delete on partial counts"
