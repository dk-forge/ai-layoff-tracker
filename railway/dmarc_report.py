#!/usr/bin/env python3
"""Read a DMARC aggregate report and say whether enforcement is safe yet.

WHY THIS EXISTS. On 2026-09-08, mid hosting migration, the question "can we
move DMARC from p=none to p=quarantine" had been open all day and was being
answered by guesswork: a DNS selector scan found no Brevo key and concluded
there might not be one, which was wrong and would have been a dangerous thing
to act on. Brevo publishes at brevo1/brevo2 as CNAMEs into its own zone.

The aggregate report settles it with evidence instead. It lists every source
that sent mail claiming to be the domain, and what each one's SPF and DKIM
actually did at a real receiver. That is not inferable from DNS.

WHAT IT DECIDES, AND WHAT IT REFUSES TO. It reports whether every observed
sender would survive enforcement. It does NOT say "tighten now", because one
report is one day from one receiver: a sender that happened not to send that
day is invisible, and invisible is not safe. The verdict names what it saw and
how much it saw, so a human decides with the coverage in front of them.

Usage:
    python3 railway/dmarc_report.py <report.zip|report.xml|report.gz> [...]

Pure stdlib. Reads local files only; sends nothing anywhere.
"""
from __future__ import annotations

import gzip
import pathlib
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone


def _xml_documents(path: pathlib.Path) -> list[bytes]:
    """The XML inside a .zip, .gz or bare .xml report."""
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            return [z.read(n) for n in z.namelist() if n.endswith(".xml")]
    if path.suffix == ".gz":
        return [gzip.decompress(path.read_bytes())]
    return [path.read_bytes()]


def _ts(value: str | None) -> str:
    try:
        return datetime.fromtimestamp(int(value or 0), timezone.utc).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "?"


def analyse(paths: list[str]) -> dict:
    """Parse reports into {total, failing, senders, selectors, windows, policies}.

    Split out so an unattended caller can ask "is the new host's own mail in
    here yet" without re-parsing or screen-scraping report()'s output.
    """
    total = failing = 0
    senders: dict[tuple, dict] = {}
    windows: list[str] = []
    policies: set[str] = set()
    selectors: set[str] = set()
    for raw in paths:
        path = pathlib.Path(raw)
        if not path.exists():
            continue
        for doc in _xml_documents(path):
            root = ET.fromstring(doc)
            meta = root.find("report_metadata")
            rng = meta.find("date_range") if meta is not None else None
            if rng is not None:
                windows.append(f"{_ts(rng.findtext('begin'))} .. {_ts(rng.findtext('end'))}")
            pol = root.find("policy_published")
            if pol is not None:
                policies.add(f"p={pol.findtext('p')} adkim={pol.findtext('adkim')} "
                             f"aspf={pol.findtext('aspf')}")
            for rec in root.findall("record"):
                row = rec.find("row")
                ev = row.find("policy_evaluated")
                auth = rec.find("auth_results")
                try:
                    count = int(row.findtext("count") or 0)
                except ValueError:
                    count = 0
                dkim = (ev.findtext("dkim") or "").lower()
                spf = (ev.findtext("spf") or "").lower()
                survives = dkim == "pass" or spf == "pass"
                passing = sorted({
                    f"{d.findtext('selector')}@{d.findtext('domain')}"
                    for d in (auth.findall("dkim") if auth is not None else [])
                    if (d.findtext("result") or "") == "pass"
                })
                selectors.update(passing)
                key = (row.findtext("source_ip"), tuple(passing), survives)
                e = senders.setdefault(key, {"count": 0, "dkim": dkim, "spf": spf})
                e["count"] += count
                total += count
                if not survives:
                    failing += count
    return {"total": total, "failing": failing, "senders": senders,
            "selectors": sorted(selectors), "windows": sorted(set(windows)),
            "policies": sorted(policies)}


def report(paths: list[str]) -> int:
    """0 = every observed sender survives enforcement. 2 = at least one does not."""
    for raw in paths:
        if not pathlib.Path(raw).exists():
            print(f"  MISSING  {raw}")
            return 3
    a = analyse(paths)
    total, failing, senders = a["total"], a["failing"], a["senders"]
    windows, policies = a["windows"], a["policies"]

    print("DMARC AGGREGATE REPORT")
    for w in windows:
        print(f"  window   {w} UTC")
    for p in policies:
        print(f"  policy   {p}")
    print(f"  messages {total}\n")

    for (ip, selectors, survives), e in sorted(senders.items(), key=lambda kv: -kv[1]["count"]):
        mark = "OK  " if survives else "FAIL"
        sel = ", ".join(selectors) or "no passing DKIM signature"
        print(f"  {mark} {ip:<16} x{e['count']:<4} dkim={e['dkim']:<5} spf={e['spf']:<5}  {sel}")

    print()
    if total == 0:
        print("  NO RECORDS. Nothing was observed, which is UNKNOWN and not a pass.")
        return 3
    if failing:
        print(f"  {failing} of {total} message(s) would be acted on by p=quarantine.")
        print("  DO NOT TIGHTEN. Identify each failing sender above first.")
        # 2026-09-09: this returns 1 (NOT READY), not 2 (FAULT).
        #
        # The policy live today is p=none, so nothing is actually being
        # quarantined. "One sender would fail IF we tightened" is the answer to
        # the question this check exists to ask, not a fault, and it will stay
        # true every day until every sender aligns. Returning 2 made the
        # workflow red daily and mailed the owner about it, which is precisely
        # what `_announce_readiness` refuses to do three functions away: "never
        # a daily nag, which is how an alert channel gets filtered."
        #
        # A rejected mailbox login stays 2 and an unreadable report stays 3.
        # Those are faults. Not-yet-ready is a measurement.
        return 1
    print(f"  All {total} observed message(s) pass DMARC and would survive p=quarantine.")
    print("  This is ONE report from ONE receiver over the window shown. A sender that")
    print("  did not send in that window is absent, not proven safe. Read the sender")
    print("  list above and confirm it contains every service you actually use before")
    print("  tightening.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(3)
    raise SystemExit(report(sys.argv[1:]))
