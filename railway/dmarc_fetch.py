#!/usr/bin/env python3
"""Fetch DMARC aggregate reports from a mailbox and judge them unattended.

WHY THIS EXISTS. `dmarc_report.py` answers "would enforcement break our own
mail", and answered it well on 2026-09-08 -- but only because a human noticed
the report in his inbox, saved the zip and handed over the path. A check that
needs a person to notice an attachment is a check that stops happening.

The reports are machine-generated XML, mailed daily by every large receiver to
the address in the DMARC record's `rua=`. Point that at a mailbox this job can
read and the whole loop closes.

THE CREDENTIAL, AND WHY IT IS SHAPED THIS WAY. IMAP access to a mailbox is a
real secret, and on cPanel the same password usually works for SMTP, so a
leaked one can SEND as well as read. That risk is bounded by giving this job a
mailbox that holds nothing else: a dedicated address whose only correspondents
are report robots. Do not point this at info@ or at a person's mailbox. The
password is never logged, never printed and never written to a file; failures
are scrubbed before they reach stdout, because a stack trace with a URL in it
is how credentials end up in a public Actions log.

FOUR STATES, NOT TWO. Learned from the digest mailer, whose relay credential
was rejected for three days while every run was green because nothing ever
exercised it:

  ABSENT     no credential configured. Green, and says it is not armed.
  OK         reports read and judged.
  REJECTED   the server refused the login. RED; a human rotates the secret.
  UNKNOWN    could not reach or parse. Never a pass, never a fault.

Pure stdlib.
"""
from __future__ import annotations

import email
import imaplib
import os
import pathlib
import re
import ssl
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from dmarc_report import analyse, report as judge_reports  # noqa: E402

ABSENT, OK, REJECTED, UNKNOWN = "ABSENT", "OK", "REJECTED", "UNKNOWN"
#: Reachable, authenticated, and holding no new report. On a freshly
#: created mailbox that is the CORRECT answer, not a fault: reports arrive
#: daily and the first has not been sent yet. Distinguished from UNKNOWN
#: because a login that succeeded proves more than one that never ran.
EMPTY = "EMPTY"

#: Only these arrive as DMARC aggregate reports.
_ATTACHMENT = re.compile(r"\.(zip|gz|xml)$", re.IGNORECASE)


def _scrub(text: str, secrets: list[str]) -> str:
    """Never let a credential reach stdout, however it got into a message."""
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    return out


def fetch(host: str, user: str, password: str, limit: int = 0) -> tuple[str, list[str], str]:
    """Return (state, saved report paths, detail). Never raises, never leaks.

    ``limit`` caps messages per run; 0 means read DMARC_MAX_PER_RUN, default
    200. The default is high on purpose: the first run against a mailbox that
    has been filling unread for months has a backlog to drain, and a cap of a
    handful would take weeks to clear it while the mailbox kept growing.
    """
    if not limit:
        try:
            limit = int(os.environ.get("DMARC_MAX_PER_RUN", "200"))
        except ValueError:
            limit = 200
    secrets = [password]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="dmarc-"))
    saved: list[str] = []
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(host, 993, ssl_context=ctx, timeout=30) as m:
            try:
                m.login(user, password)
            except imaplib.IMAP4.error as exc:
                # A refused login is a DIFFERENT state from an unreachable
                # server: one needs a rotated secret, the other needs nothing.
                return REJECTED, [], _scrub(exc, secrets)
            m.select("INBOX")
            typ, data = m.search(None, "UNSEEN")
            if typ != "OK":
                return UNKNOWN, [], "mailbox search failed"
            ids = (data[0] or b"").split()[-limit:]
            harvested: list[bytes] = []
            for num in ids:
                typ, raw = m.fetch(num, "(BODY.PEEK[])")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = email.message_from_bytes(raw[0][1])
                for part in msg.walk():
                    name = part.get_filename() or ""
                    if not _ATTACHMENT.search(name):
                        continue
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    dest = tmp / pathlib.Path(name).name
                    dest.write_bytes(payload)
                    saved.append(str(dest))
                    if num not in harvested:
                        harvested.append(num)
            # A mailbox nobody empties fills up, and a full mailbox rejects
            # mail, which would silently end this check. Clearing happens ONLY
            # for messages whose attachment we actually wrote to disk: a
            # message we could not read stays unread and untouched, so a parse
            # failure is retried and stays visible rather than being destroyed
            # by the thing that failed to understand it.
            if harvested:
                cleared = _clear(m, harvested)
                detail_suffix = f", {cleared} cleared from the mailbox"
            else:
                detail_suffix = ""
        return (OK if saved else EMPTY), saved, (
            f"{len(saved)} report(s) fetched" + detail_suffix if saved
            else "no unread report attachments found"
        )
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        return UNKNOWN, [], _scrub(exc, secrets)


def _clear(conn, nums: list[bytes]) -> int:
    """Delete the messages we successfully harvested, and expunge.

    The owner noticed his mailboxes filling up. A DMARC mailbox receives a
    report from every large receiver every day, forever, and a full mailbox
    REJECTS incoming mail -- which would end this check silently, from a cause
    that looks nothing like a broken check.

    Deleting is safe here in a way it would not be elsewhere: these are
    machine-generated reports, each superseded daily, the verdict is preserved
    in the workflow run summary, and the mailbox is dedicated to robots. Only
    messages whose attachment reached disk are touched.

    A server that refuses the delete is not an error worth failing the run
    over: the reports were still read and judged, and the next run retries.
    """
    done = 0
    for num in nums:
        try:
            conn.store(num, "+FLAGS", "\\Deleted")
            done += 1
        except Exception:
            continue
    try:
        conn.expunge()
    except Exception:
        pass
    return done


def main() -> int:
    host = os.environ.get("DMARC_IMAP_HOST", "").strip()
    user = os.environ.get("DMARC_IMAP_USER", "").strip()
    pw = os.environ.get("DMARC_IMAP_PASSWORD", "")
    if not (host and user and pw):
        print("DMARC MAILBOX: ABSENT -- no credential configured.")
        print("  This is not a fault. It means the unattended check is NOT ARMED,")
        print("  and DMARC enforcement readiness stays a manual step. Arm it by")
        print("  setting DMARC_IMAP_HOST / _USER / _PASSWORD.")
        return 0

    state, paths, detail = fetch(host, user, pw)
    print(f"DMARC MAILBOX: {state} -- {detail}\n")
    if state == REJECTED:
        print("  The mail server refused the login. Rotate the mailbox password")
        print("  and update the DMARC_IMAP_PASSWORD secret. This is RED on purpose:")
        print("  a rejected credential that reads green is how a check dies quietly.")
        return 2
    if state == EMPTY:
        print("  The mailbox is reachable and the login works, and it holds no new")
        print("  report. On a newly created mailbox that is expected: receivers send")
        print("  these once a day. Enforcement readiness is still UNANSWERED, and this")
        print("  run does not claim otherwise. If this persists for several days the")
        print("  reports have stopped arriving and the rua= address needs checking.")
        return 0
    if state != OK:
        print("  Could not read any report. That is UNKNOWN, not a pass: nothing")
        print("  here established that enforcement is safe.")
        return 3

    code = judge_reports(paths)
    _announce_readiness(analyse(paths))
    return code


#: The selector the HOST signs with. Until mail sent by the web host itself
#: appears in a report, tightening is unproven for that path, however clean
#: the ESPs look.
HOST_SELECTOR = "default@asktherecruiter.com"


def _announce_readiness(a: dict) -> None:
    """Email once, and only when the answer actually changes to yes.

    The point of automating this is that the owner is told when he can act,
    not that a green log accumulates somewhere he never looks. ops_notify
    dedupes by cause, so this is one email when the state flips and silence
    afterwards -- never a daily nag, which is how an alert channel gets
    filtered.
    """
    ready = a["failing"] == 0 and HOST_SELECTOR in a["selectors"]
    if not ready:
        missing = ("the host's own mail has not appeared in a report yet"
                   if a["failing"] == 0
                   else f"{a['failing']} of {a['total']} message(s) would be quarantined")
        print(f"\n  NOT READY to tighten: {missing}.")
        return
    print("\n  READY: every observed sender passes, INCLUDING the host itself.")
    try:
        from ops_notify import notify
    except ImportError:
        from railway.ops_notify import notify
    notify(
        "DMARC can be tightened to p=quarantine",
        "Every sender observed in the latest aggregate report passes DMARC, "
        "and that now includes mail sent by the web host itself (the "
        f"'default' selector), across {a['total']} message(s).\n\n"
        "Record to publish, changing only the policy tag:\n\n"
        "  v=DMARC1; p=quarantine; rua=mailto:dmarc@asktherecruiter.com; "
        "ruf=mailto:dmarc@asktherecruiter.com; fo=1; adkim=r; aspf=r; pct=100\n\n"
        "Senders seen passing: " + ", ".join(a["selectors"]) + "\n\n"
        "This is a recommendation, not an action. Nothing has been changed.",
        dedupe_key="dmarc:ready-to-tighten",
        what="DMARC readiness notice",
    )


if __name__ == "__main__":
    raise SystemExit(main())
