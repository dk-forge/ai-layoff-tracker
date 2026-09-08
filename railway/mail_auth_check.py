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

import hashlib
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
    """One record that must exist, and what makes it the right record.

    ``sha256`` pins the key material of a record whose VALUE matters, not just
    its presence. A DKIM key is the case: the record can be present, well
    formed, and still be the wrong key, at which point every message it signs
    fails. A pinned fingerprint turns that into a FAIL instead of a mystery.

    A deliberate key rotation will fail this check. That is the intent: the
    rotation is then confirmed by a human and the pin updated with --pin,
    rather than a silent swap nobody notices.
    """

    name: str
    kind: str
    must_contain: str
    why: str
    sha256: str = ""


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
        "default._domainkey.asktherecruiter.com",
        "TXT",
        "p=MIIBIjANBgkq",
        "The HOST's outbound signing key, for mail sent by the site itself. "
        "Confirmed on 2026-09-08 to have survived the hosting migration intact "
        "(cPanel validates it against the private key the new server holds), "
        "which is why it was NOT replaced. Its Cloudflare comment field wrongly "
        "says 'resend'; go by the selector, never the comment.",
        "b43de228b49f358e",
    ),
    Requirement(
        "brevo2._domainkey.asktherecruiter.com",
        "TXT",
        "p=",
        "The reader newsletter's DKIM key, published as a CNAME into Brevo. "
        "PROVEN load-bearing by Google's DMARC aggregate report for 2026-09-07: "
        "every Brevo message passed DMARC on this selector and FAILED SPF "
        "alignment (envelope domain gg.d.sender-sib.com), so DKIM is the only "
        "thing carrying the subscriber digest. Lose it and enforcement "
        "quarantines the readers' mail, not a spammer's.",
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
    if req.must_contain.lower() not in joined.lower():
        # A placeholder counts as missing, and says so in those words. On
        # 2026-09-08 a sibling domain was found publishing the literal string
        # "p=REPLACE_WITH_BLUEHOST_KEY", so its mail had never once been
        # signed. The host's own validator called that "problems exist".
        if "replace_with" in joined.lower() or "your_key" in joined.lower():
            return FAIL, "record is an unfilled PLACEHOLDER, not a key"
        return FAIL, f"published but missing {req.must_contain!r}"
    if req.sha256:
        actual = _key_fingerprint(joined)
        if actual != req.sha256:
            return FAIL, (
                f"key CHANGED: pinned {req.sha256}, published {actual}. "
                f"If this was a deliberate rotation, re-pin with --pin"
            )
    return PASS, ""


def _key_fingerprint(record: str) -> str:
    """A short, stable fingerprint of a DKIM record's key material."""
    key = record.replace(" ", "").split("p=", 1)[-1]
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


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


def pin() -> int:
    """Print the fingerprint of every pinned record, for --pin after a
    deliberate rotation. Prints; never edits the file itself, because a pin
    that updates itself protects nothing."""
    for req in REQUIREMENTS:
        if not req.sha256:
            continue
        records, err = _resolve(req.name, req.kind)
        if not records:
            print(f"    {req.name}: could not read ({err or 'no record'})")
            continue
        print(f"    {req.name}: {_key_fingerprint(' '.join(records))}")
    return 0


if __name__ == "__main__":
    sys.exit(pin() if "--pin" in sys.argv else report())
