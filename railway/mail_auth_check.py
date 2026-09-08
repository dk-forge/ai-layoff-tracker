#!/usr/bin/env python3
"""Are the records that make our mail deliverable still published?

WHY THIS EXISTS. On 2026-09-08 the hosting move to a new provider was being
planned, and the migration brief correctly identified that the Bluehost DKIM
key had to be replaced. What no document mentioned was that operational
alerting passes DMARC on two records nobody had written down:

    send.asktherecruiter.com   TXT  v=spf1 include:amazonses.com ~all
    resend._domainkey          TXT  (RSA key)

Resend is deliberately NOT in the root SPF record. It aligns through that
subdomain and that DKIM key. Delete either while "cleaning up DNS", tighten
DMARC to quarantine, and every CI alert, every RECOVERED notice and the weekly
health digest starts getting quarantined -- with no error anywhere, because a
quarantined message is a successful send as far as the sender is concerned.

That is precisely the failure the August move to Resend was meant to prevent:
an alarm that cannot report its own silence. A missing DNS record is a quieter
version of the same thing.

WHAT THIS DOES NOT DO. It does not prove mail is delivered, and it cannot. It
proves the records exist and have the shape they need. Delivery has one
honest test, which is sending a real message; this catches the class of
breakage where a record was dropped and nobody will notice for weeks.

THREE STATES, and the third is the point. Resolution happens over DNS-over-
HTTPS, so a session with no egress cannot answer the question. That is
UNKNOWN. It is never a pass, and it is never a fault.

Pure stdlib, no keys, read-only.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

#: Google's resolver over HTTPS. Chosen because it needs no dependency and no
#: key; any DoH endpoint returning the same JSON shape would do.
_DOH = "https://dns.google/resolve"
_TIMEOUT = 12

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"


@dataclass(frozen=True)
class Requirement:
    """One record that must exist, and what makes it the right record."""

    name: str
    kind: str
    must_contain: str
    why: str


#: The protected set. Each entry is here because something breaks quietly
#: without it, and the ``why`` is what a future session needs in order to
#: not "clean it up".
REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "send.asktherecruiter.com",
        "TXT",
        "include:amazonses.com",
        "Resend's return path. Operational alerts align SPF through this "
        "subdomain, NOT through the root SPF record.",
    ),
    Requirement(
        "resend._domainkey.asktherecruiter.com",
        "TXT",
        "p=",
        "Resend's DKIM key. Without it every ops alert fails DMARC once "
        "enforcement is on.",
    ),
    Requirement(
        "asktherecruiter.com",
        "TXT",
        "include:spf.brevo.com",
        "The reader digest sends through Brevo. Losing this quarantines the "
        "subscriber newsletter, not the spammers.",
    ),
    Requirement(
        "_dmarc.asktherecruiter.com",
        "TXT",
        "v=DMARC1",
        "The policy record itself. Its absence is not lenient, it is "
        "unauthenticated.",
    ),
)


def _resolve(name: str, kind: str) -> tuple[list[str] | None, str]:
    """Return (records, error). ``None`` records means could not resolve."""
    url = f"{_DOH}?" + urllib.parse.urlencode({"name": name, "type": kind})
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
        return None, f"resolver unreachable: {exc}"
    except (ValueError, json.JSONDecodeError) as exc:
        return None, f"resolver returned no usable answer: {exc}"
    answers = body.get("Answer") or []
    return [str(a.get("data", "")).strip('"') for a in answers], ""


def check_one(req: Requirement) -> tuple[str, str]:
    """Judge one requirement. Returns (state, detail)."""
    records, err = _resolve(req.name, req.kind)
    if records is None:
        return UNKNOWN, err
    if not records:
        return FAIL, "no record published"
    joined = " ".join(records)
    if req.must_contain.lower() in joined.lower():
        return PASS, ""
    return FAIL, f"published but missing {req.must_contain!r}"


def report() -> int:
    """Print the verdict. 0 healthy, 2 a record is gone, 3 could not check."""
    results = [(r, *check_one(r)) for r in REQUIREMENTS]
    worst = 0
    print("\n[4f] MAIL AUTH RECORDS  (protected set -- do not prune these)")
    for req, state, detail in results:
        line = f"      {state:<7} {req.name} {req.kind}"
        print(line + (f"  -- {detail}" if detail else ""))
        if state == FAIL:
            print(f"              WHY IT MATTERS: {req.why}")
            worst = 2
        elif state == UNKNOWN and worst < 2:
            worst = 3
    if worst == 0:
        print("      all protected records present and correctly shaped")
    elif worst == 3:
        print("      could not resolve from here, so this is UNKNOWN, not a pass")
    return worst


if __name__ == "__main__":
    sys.exit(report())
