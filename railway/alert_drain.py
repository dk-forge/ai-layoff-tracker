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
1  the host is UP and delivery is still refused (a wrong key, a missing route);
   or the queue could not be written; or WP_SITE_URL/WP_API_KEY are unset; or —
   the case this list used to omit — the queue is STUCK and the host-independent
   GitHub-issue fallback could not be used either. That last one is a down host
   AND a red run on purpose: when nothing at all can reach the owner, a red run
   is the only signal left, so it is worth the amplification the other paths
   avoid. Do not "restore" a blanket green here; the amplification rule is about
   an outage that IS being reported some other way.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

import alert_outbox
import ci_alert
import gh_fallback
import opsmail


def drain(outbox: dict, site: str = "", key: str = "") -> tuple[int, int, str, bool]:
    """Deliver held alerts, oldest first.

    Returns (delivered, remaining, last_note, host_down). Stops at the first
    TRANSIENT failure: if the relay is still away there is nothing to learn
    from hammering it, and every entry keeps its place. A SETTLED refusal (a
    missing key, an unverified sender) does NOT stop the drain, because every
    entry will hit it and the count of how many is the size of the problem.

    `ci_alert.deliver`, NOT `ci_alert.post_alert`. A held alert has already been
    ruled on by the ledger and its claim is already committed. Running it
    through the ledger a second time would find its own cause open and suppress
    it, which is an alert lost to the machinery meant to protect it.
    """
    delivered = 0
    note = ""
    host_down = False
    for entry in alert_outbox.pending(outbox):
        payload = entry.get("payload") or {}
        ok, note, transient = ci_alert.deliver(payload)
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

    if not opsmail.configured():
        print("::error::RESEND_API_KEY is not set, so held alerts cannot be "
              "delivered and the owner stays uninformed about every failure in "
              "this queue.")
        return 1
    if args.dry_run:
        print(f"[dry-run] would attempt {len(held)} delivery/deliveries")
        return 0

    delivered, remaining, note, host_down = drain(outbox)
    alert_outbox.save(outbox, args.outbox)
    print(f"delivered {delivered}, {remaining} still held")

    repo = gh_fallback.repo_from_env()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if remaining == 0:
        if not args.no_fallback:
            ok, fallback_note = gh_fallback.close(
                repo, note=(f"The relay answered again at {now} and all "
                            f"{delivered} held alert(s) were delivered. "
                            "Closing; this is the last email about it."))
            if fallback_note != "no fallback issue was open":
                print(f"fallback channel: {fallback_note}")
        return 0

    stuck = alert_outbox.stuck(outbox)
    if host_down:
        # THE VERDICT IS NOT DECIDED YET, AND THIS LINE USED TO SAY IT WAS.
        #
        # It read "This run is NOT failing", printed here, before the fallback
        # below has been attempted. On the one path where the fallback also
        # fails this function returns 1 — a red `Alert drain` run, which
        # ci-alert.yml turns into an email to the owner. So the log asserted the
        # run was green in the same breath as the run went red, and the log is
        # the only place a session reads to tell "the host was down and we kept
        # the alert" from "the alerter is broken".
        #
        # The BEHAVIOUR is right and is unchanged: when nothing is able to tell
        # the owner, a red run is the only signal left. What was wrong was the
        # sentence, so the claim now sits on the paths where it is true.
        print("::warning::the relay is still not answering, so "
              f"{remaining} alert(s) stay held. A down host is not a defect in "
              "this repository, and a red run here would fire the CI alert, "
              "which posts to the down host — so holding the queue is not, by "
              "itself, a failure.")
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
                      "currently able to tell the owner about this, so THIS RUN "
                      "IS FAILING deliberately: a red run is the last signal "
                      "left, even though the alert it fires posts to the same "
                      "host that is down. This is NOT the ordinary held-queue "
                      "case above.")
                return 1
        print(f"This run is NOT failing: {remaining} alert(s) kept their place "
              "and the next drain that reaches the host delivers them.")
        return 0

    # The relay answered and still refused. That is a bad key or an unverified
    # sender, and it will not fix itself while the queue quietly grows.
    print(f"::error::the mail relay is reachable and still refusing these "
          f"alerts ({note}). {remaining} alert(s) will not arrive on their own. "
          "Check RESEND_API_KEY and that OPS_MAIL_FROM uses a domain this "
          "Resend account has verified.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
