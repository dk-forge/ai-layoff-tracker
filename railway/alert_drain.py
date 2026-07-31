#!/usr/bin/env python3
"""Deliver the alerts that were held while the host was unreachable.

WHY THIS IS SO MUCH SMALLER THAN THE SIBLING'S host_watch.py
------------------------------------------------------------
Both trackers live on the SAME Bluehost account, so there is exactly one host to
watch and it should be watched once. The talent tracker's `host-watch.yml` probes
it every 15 minutes and, on a sustained outage, opens ONE GitHub issue. Adding a
second, identical watchdog here would double the requests to a host that has
already shown its ceiling twice in a day, and — worse — send the owner two
emails per outage instead of one. An undeduped alarm is the problem this whole
change exists to fix; duplicating it across repos would be that problem with a
second repository attached.

So this repo does not re-watch the host. It does the ONE thing the sibling
cannot do on its behalf: drain this repo's own outbox, which lives in this
repository and which nothing outside it can see.

**AND THIS ONLY TOUCHES THE HOST WHEN THERE IS SOMETHING TO SAY.** An empty
outbox exits in a fraction of a second having made no request at all, which is
the normal case ~always. The delivery attempt IS the reachability check; there
is no separate probe, because a probe that succeeds and a delivery that succeeds
answer the same question and only one of them also does the job.

WHAT STILL WATCHES THE HOST FROM HERE
-------------------------------------
`ops_status.py [1]` fetches the live tracker at every session start and exits 2
when it cannot reach it — it printed `UNREACHABLE: HTTP Error 504` during the
2026-07-31 window. That is the session-time check and it is independent of the
sibling, so removing `host-watch.yml` over there could not leave this repo
blind, only slower to notice. `[4b]` below reports what is held.

EXIT CODES
----------
0  nothing held, or everything held was delivered, or the host is still down and
   the queue kept its place. A down host is not a defect in this repository, and
   a red run here would fire the CI alert, which posts to the down host, which
   is precisely the amplification loop this design exists to break.
1  the host is UP and delivery is still refused (a wrong key, a missing route),
   or the queue could not be written. Those a human can act on here.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import alert_outbox
import ci_alert
import gh_fallback


def drain(outbox: dict, site: str, key: str) -> tuple[int, int, str, bool]:
    """Deliver held alerts, oldest first.

    Returns (delivered, remaining, last_note, host_down). Stops at the first
    TRANSIENT failure: if the host is still away there is nothing to learn from
    hammering it, and every entry keeps its place. A SETTLED refusal (bad key,
    missing route) does NOT stop the drain — every entry will hit it, and the
    count of how many is the size of the problem.
    """
    delivered = 0
    note = ""
    host_down = False
    for entry in alert_outbox.pending(outbox):
        payload = entry.get("payload") or {}
        ok, note, transient = ci_alert.post_alert(site, key, payload)
        if ok:
            alert_outbox.mark_delivered(entry, f"delivered late: {note}")
            delivered += 1
            print(f"  delivered {entry.get('key')}: {note}")
            continue
        alert_outbox.record_attempt(entry, note)
        print(f"  still undeliverable {entry.get('key')}: {note}")
        if transient:
            host_down = True
            break
    return delivered, len(alert_outbox.pending(outbox)), note, host_down


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deliver what the outage held back")
    ap.add_argument("--outbox", default=str(alert_outbox.OUTBOX))
    ap.add_argument("--site", default=os.environ.get("WP_SITE_URL", ""))
    ap.add_argument("--no-fallback", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    outbox = alert_outbox.load(args.outbox)
    held = alert_outbox.pending(outbox)
    if not held:
        print("Nothing is held. No request was made to the host.")
        return 0

    print(f"{len(held)} alert(s) held:")
    for entry in held:
        print(f"  {entry.get('raised_at')}  x{entry.get('attempts', 0)}  "
              f"{(entry.get('payload') or {}).get('subject', entry.get('key'))[:70]}")

    site = (args.site or "").rstrip("/")
    key = os.environ.get("WP_API_KEY", "")
    if not (site and key):
        print("::error::WP_SITE_URL / WP_API_KEY are not set, so held alerts "
              "cannot be delivered and the owner stays uninformed about every "
              "failure in this queue.")
        return 1
    if args.dry_run:
        print(f"[dry-run] would attempt {len(held)} delivery/deliveries")
        return 0

    delivered, remaining, note, host_down = drain(outbox, site, key)
    alert_outbox.save(outbox, args.outbox)
    print(f"delivered {delivered}, {remaining} still held")

    repo = gh_fallback.repo_from_env()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if remaining == 0:
        if not args.no_fallback:
            ok, fallback_note = gh_fallback.close(
                repo, note=(f"The host answered again at {now} and all "
                            f"{delivered} held alert(s) were delivered. "
                            "Closing; this is the last email about it."))
            if fallback_note != "no fallback issue was open":
                print(f"fallback channel: {fallback_note}")
        return 0

    stuck = alert_outbox.stuck(outbox)
    if host_down:
        # Deliberately green. The queue is doing exactly what it was built for.
        print("::warning::the host is still not answering, so "
              f"{remaining} alert(s) stay held. This run is NOT failing: the "
              "outage is not a defect in this repository, and a red run here "
              "would fire the CI alert, which posts to the down host.")
        if stuck and not args.no_fallback:
            # It has been down long enough that "it will pass" is no longer the
            # honest reading. Say so on the channel that is not on the host.
            ok, fallback_note = gh_fallback.open_or_update(
                repo, line=(f"- **{now}** — {remaining} alert(s) still held; "
                            f"the oldest has failed delivery "
                            f"{max(e.get('attempts', 0) for e in stuck)} times "
                            f"(`{note}`)."))
            print(f"fallback channel: {fallback_note}")
            if not ok:
                print("::error::alerts are held AND the host-independent "
                      f"fallback could not be used: {fallback_note}. Nothing is "
                      "currently able to tell the owner about this.")
                return 1
        return 0

    # The host answered and still refused. That is a wrong key or a missing
    # route, and it will not fix itself while the queue quietly grows.
    print(f"::error::the host is reachable and still refusing these alerts "
          f"({note}). {remaining} alert(s) will not arrive on their own — check "
          "WP_API_KEY and that the plugin carrying /alert is deployed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
