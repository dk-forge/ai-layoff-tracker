"""The report mailbox is emptied as it is read, and only what was read.

The owner noticed his mailboxes filling up. A DMARC mailbox receives a report
from every large receiver every day, forever, and a FULL MAILBOX REJECTS
INCOMING MAIL. That would end this check silently, from a cause that looks
nothing like a broken check: no error, no red run, just reports that stop
arriving.

So the fetcher clears what it harvests. The danger in that is equally obvious:
a fetcher that deletes a message it failed to understand destroys the evidence
of its own bug. These tests pin the line between the two.
"""
from __future__ import annotations

import email.message
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dmarc_fetch import ABSENT, EMPTY, OK, REJECTED, UNKNOWN, _clear, _scrub, fetch  # noqa: E402


class _Conn:
    """Enough IMAP to exercise the harvest-and-clear path."""

    def __init__(self, messages, refuse_login=False, refuse_store=False):
        self.messages = messages
        self.refuse_login = refuse_login
        self.refuse_store = refuse_store
        self.deleted: list[bytes] = []
        self.expunged = False
        self.fetch_commands: list[str] = []

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def login(self, u, p):
        if self.refuse_login:
            import imaplib
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    def select(self, box): return ("OK", [b"1"])
    def search(self, charset, term): return ("OK", [b" ".join(self.messages)])

    def fetch(self, num, spec):
        self.fetch_commands.append(spec)
        return ("OK", [(b"1", self.messages_map[num])])

    def store(self, num, flags, value):
        if self.refuse_store:
            raise RuntimeError("server said no")
        self.deleted.append(num)
        return ("OK", [b""])

    def expunge(self):
        self.expunged = True
        return ("OK", [b""])


def _msg(filename: str | None) -> bytes:
    m = email.message.EmailMessage()
    m["Subject"] = "Report domain: asktherecruiter.com"
    m.set_content("report attached")
    if filename:
        m.add_attachment(b"<feedback/>", maintype="application",
                         subtype="zip", filename=filename)
    return m.as_bytes()


def _conn_with(files, **kw):
    nums = [str(i + 1).encode() for i in range(len(files))]
    c = _Conn(nums, **kw)
    c.messages_map = {n: _msg(f) for n, f in zip(nums, files)}
    return c


def _patched(conn, monkeypatch):
    import dmarc_fetch
    monkeypatch.setattr(dmarc_fetch.imaplib, "IMAP4_SSL",
                        lambda *a, **k: conn)
    return dmarc_fetch


def test_reading_uses_peek_so_it_is_not_a_side_effect(monkeypatch) -> None:
    """A plain FETCH(RFC822) silently sets \\Seen. Reading a mailbox must not
    change it; only the explicit clear step may."""
    conn = _conn_with(["report.zip"])
    _patched(conn, monkeypatch)
    fetch("h", "u", "pw")
    assert conn.fetch_commands, "nothing was fetched"
    assert all("PEEK" in c for c in conn.fetch_commands), conn.fetch_commands


def test_a_harvested_report_is_deleted_and_expunged(monkeypatch) -> None:
    conn = _conn_with(["report.zip", "report2.zip"])
    _patched(conn, monkeypatch)
    state, saved, detail = fetch("h", "u", "pw")
    assert state == OK
    assert len(saved) == 2
    assert len(conn.deleted) == 2, "the mailbox was not cleared and will fill up"
    assert conn.expunged is True
    assert "cleared" in detail


def test_a_message_we_could_not_read_is_never_deleted(monkeypatch) -> None:
    """The important one. A fetcher that deletes what it failed to parse
    destroys the evidence of its own bug, and the report is gone forever."""
    conn = _conn_with([None, "report.zip"])   # first carries no attachment
    _patched(conn, monkeypatch)
    state, saved, _ = fetch("h", "u", "pw")
    assert state == OK
    assert len(saved) == 1
    assert conn.deleted == [b"2"], (
        "only the message whose attachment reached disk may be cleared"
    )


def test_an_empty_mailbox_is_EMPTY_not_UNKNOWN(monkeypatch) -> None:
    """A login that SUCCEEDED and found nothing proves more than one that never
    ran. A newly created report mailbox is legitimately empty until the first
    daily report arrives, and failing on that would cry wolf every day. It is
    still not a pass: readiness stays unanswered and the run says so."""
    conn = _conn_with([None])
    _patched(conn, monkeypatch)
    state, saved, _ = fetch("h", "u", "pw")
    assert state == EMPTY
    assert state != UNKNOWN, "an empty mailbox is not an unreadable one"
    assert saved == []
    assert conn.deleted == []
    assert conn.expunged is False


def test_a_refused_delete_does_not_lose_the_reports(monkeypatch) -> None:
    """Clearing is housekeeping. If the server refuses it, the reports were
    still read and judged, and the run must not fail over the tidying."""
    conn = _conn_with(["report.zip"], refuse_store=True)
    _patched(conn, monkeypatch)
    state, saved, _ = fetch("h", "u", "pw")
    assert state == OK and len(saved) == 1


def test_a_refused_login_is_rejected_not_unknown(monkeypatch) -> None:
    """Two different states: one needs a rotated secret, the other needs
    nothing. Collapsing them sends the owner to rotate a working password."""
    conn = _conn_with(["report.zip"], refuse_login=True)
    _patched(conn, monkeypatch)
    state, saved, _ = fetch("h", "u", "pw")
    assert state == REJECTED
    assert saved == []
    assert conn.deleted == []


def test_the_password_never_survives_into_an_error_string() -> None:
    """Actions logs on this repository are PUBLIC."""
    assert "hunter2" not in _scrub("login failed for u:hunter2@h", ["hunter2"])
    assert "***" in _scrub("login failed for u:hunter2@h", ["hunter2"])


# This suite is unittest, not pytest (#288). Without this, every test above is
# collected as nothing at all and the file passes by never running.
from _pytest_bridge import bind  # noqa: E402

DmarcFetchTests = bind(globals(), "DmarcFetchTests")
