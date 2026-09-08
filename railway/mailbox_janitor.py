#!/usr/bin/env python3
"""Read a notification mailbox, summarise it, and delete what it has read.

WHY THIS EXISTS. `errornotifications-sandbox@` held 2,106 messages on
2026-09-08, growing at ~31/day, and nobody had ever read it. Reconnaissance
found 1,455 GitHub notifications and 535 Railway ones. Buried in that was
exactly ONE live problem: a weekly job on main that had been failing for two
weeks. One real signal in 2,106 messages is not a monitoring channel, it is a
place signals go to die.

WHAT THIS IS NOT. It is not a replacement for monitoring. Almost everything in
that mailbox duplicates a signal that can be queried directly and better:
workflow outcomes come from the GitHub API as structured data, not as prose in
an email. The right long-term fix is to stop sending most of it. This exists to
keep the mailbox from becoming a disk problem in the meantime, and to make sure
that if something genuinely new appears there, a human is told.

THE SAFETY LINE, same as the DMARC fetcher. Only messages this has actually
read and classified are deleted, and only once they are older than the
retention window. A message it could not parse stays put: a janitor that
deletes what it failed to understand destroys evidence of its own bug.

RETENTION, not immediate deletion. The window exists so a human can still open
the mailbox and see recent traffic with their own eyes. Deleting on read would
make this script the only witness to its own behaviour.

Pure stdlib.
"""
from __future__ import annotations

import email
import email.utils
import imaplib
import os
import re
import ssl
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

ABSENT, OK, REJECTED, UNKNOWN = "ABSENT", "OK", "REJECTED", "UNKNOWN"

#: Classes of routine notification. Order matters: first match wins.
_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Dependabot's own signature is its SUBJECT shape ("Bump x from 1 to 2");
    # the sender is the generic notifications@github.com, so matching on the
    # word alone misses every one of them and they fall to "other".
    ("github: dependabot",
     re.compile(r"dependabot|\bbump\b .* \bfrom\b .* \bto\b", re.I)),
    ("github: run failed", re.compile(r"run failed|workflow run", re.I)),
    ("railway: build failed", re.compile(r"build failed", re.I)),
    ("railway: deploy crashed", re.compile(r"deploy(ment)? crashed", re.I)),
    ("cpanel/system", re.compile(r"cpanel|lfd|exim|quota", re.I)),
)

#: Words that mean "a human should look at this", regardless of class. Kept
#: deliberately short: a list that matches everything reports nothing.
_ESCALATE = re.compile(
    r"\b(production|prod)\b|\bmain\b|payment|stripe|charge|refund|"
    r"data loss|corrupt|breach|unauthori[sz]ed|quota exceeded|disk full",
    re.I,
)


def _scrub(text, secrets: list[str]) -> str:
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    return out


def _age_days(msg, now: datetime) -> float | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 86400.0


def _classify(subject: str, sender: str) -> str:
    blob = f"{subject} {sender}"
    for label, pat in _CLASSES:
        if pat.search(blob):
            return label
    return "other"


def sweep(host: str, user: str, password: str, retain_days: int,
          dry_run: bool, limit: int = 2000) -> tuple[str, dict, str]:
    """Return (state, findings, detail). Never raises, never leaks."""
    secrets = [password]
    now = datetime.now(timezone.utc)
    classes: Counter[str] = Counter()
    escalate: list[str] = []
    deletable: list[bytes] = []
    unreadable = 0
    total = 0
    try:
        with imaplib.IMAP4_SSL(host, 993, ssl_context=ssl.create_default_context(),
                               timeout=60) as m:
            try:
                m.login(user, password)
            except imaplib.IMAP4.error as exc:
                return REJECTED, {}, _scrub(exc, secrets)
            m.select("INBOX")
            typ, data = m.search(None, "ALL")
            if typ != "OK":
                return UNKNOWN, {}, "mailbox search failed"
            ids = (data[0] or b"").split()[:limit]
            total = len(ids)
            for num in ids:
                typ, raw = m.fetch(num, "(BODY.PEEK[HEADER])")
                if typ != "OK" or not raw or not raw[0]:
                    unreadable += 1
                    continue
                msg = email.message_from_bytes(raw[0][1])
                subject = str(msg.get("Subject") or "")
                sender = str(msg.get("From") or "")
                label = _classify(subject, sender)
                classes[label] += 1
                if _ESCALATE.search(subject) and len(escalate) < 25:
                    escalate.append(subject[:120])
                age = _age_days(msg, now)
                # Undated, or newer than the window: leave it alone.
                if age is not None and age > retain_days:
                    deletable.append(num)
            removed = 0
            if deletable and not dry_run:
                for num in deletable:
                    try:
                        m.store(num, "+FLAGS", "\\Deleted")
                        removed += 1
                    except Exception:
                        continue
                try:
                    m.expunge()
                except Exception:
                    pass
    except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
        return UNKNOWN, {}, _scrub(exc, secrets)

    findings = {
        "total": total, "classes": classes, "escalate": escalate,
        "unreadable": unreadable, "eligible": len(deletable),
        "removed": 0 if dry_run else removed, "dry_run": dry_run,
        "retain_days": retain_days,
    }
    return OK, findings, f"{total} message(s) read"


def main() -> int:
    host = os.environ.get("JANITOR_IMAP_HOST", "").strip()
    user = os.environ.get("JANITOR_IMAP_USER", "").strip()
    pw = os.environ.get("JANITOR_IMAP_PASSWORD", "")
    if not (host and user and pw):
        print("MAILBOX JANITOR: ABSENT -- no credential configured. Not armed.")
        return 0
    retain = int(os.environ.get("JANITOR_RETAIN_DAYS", "14") or 14)
    dry = os.environ.get("JANITOR_DRY_RUN", "true").lower() != "false"

    state, f, detail = sweep(host, user, pw, retain, dry)
    print(f"MAILBOX JANITOR: {state} -- {detail}\n")
    if state == REJECTED:
        print("  Login refused. Rotate the mailbox password and update the secret.")
        return 2
    if state != OK:
        print("  Could not read the mailbox. UNKNOWN, not a pass.")
        return 3

    for label, n in f["classes"].most_common():
        print(f"    {n:>6}  {label}")
    if f["unreadable"]:
        print(f"    {f['unreadable']:>6}  UNREADABLE (left in place on purpose)")
    print(f"\n  older than {f['retain_days']}d and eligible to clear: {f['eligible']}")
    print("  " + (f"DRY RUN, nothing deleted. Set JANITOR_DRY_RUN=false to clear."
                  if f["dry_run"] else f"deleted: {f['removed']}"))

    if f["escalate"]:
        print("\n  SUBJECTS A HUMAN SHOULD SEE (matched production/main/payment/etc):")
        for s in f["escalate"]:
            print(f"    - {s}")
        return 2
    print("\n  Nothing in this mailbox matched the escalation vocabulary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
