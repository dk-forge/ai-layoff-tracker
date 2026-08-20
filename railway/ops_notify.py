#!/usr/bin/env python3
"""The one door operational mail leaves by.

WHY THIS FILE EXISTS
--------------------
On 2026-08-19 operational mail moved off the WordPress host and onto Resend,
and `opsmail.py` records at length why. What that change did NOT do was find
every caller. Three of them were converted; nine were not, and those nine went
on POSTing to `/wp-json/layoffs/v1/alert`.

That route calls bare `wp_mail()`. On this install `wp_mail` is intercepted by
the Brevo plugin, which replaces the whole From line with the SUBSCRIBER
relay identity. So the owner received his OpenRouter low-balance alert and his
held-relabel notice from `newsletter@asktherecruiter.com` under the display
name of the reader newsletter, while CI alerts arrived from `ops@`. Two ops
alarms wearing the newsletter's face, in the same inbox, on the same morning.

CLAUDE.md has said since the split that sender identity is deliberately
operational and never the digest's From name. It was true of the paths anybody
had looked at, and the ones nobody had looked at quietly said otherwise.

An alarm that arrives wearing the newsletter's From line is one the owner
filters WITH the newsletter. That is not a cosmetic complaint. It is the same
failure mode as the eight identical emails in one afternoon: the alert channel
gets a filter, and after that the alarm is decoration.

WHAT THIS GUARANTEES
--------------------
One From, one subject prefix, one transport, for everything only the operator
receives.

  From:    opsmail.sender()          "AI Layoff Tracker Ops <ops@...>"
  Subject: opsmail.SUBJECT_PREFIX    "[AI Layoff Tracker] "

Both are applied by `opsmail.send_once`, not here and not by any caller, so
there is exactly one place either can be wrong. `tests/test_ops_sender.py`
fails if a new module grows its own.

THE READER DIGEST IS NOT OPERATIONAL AND MUST NEVER COME THROUGH HERE. It
keeps Brevo, keeps `ALT_DIGEST_FROM_*`, and must never gain the ops prefix: a
person subscribed to that, and a subject stamped `[AI Layoff Tracker]` in
front of an edition they asked for reads as machine noise. Two identities,
cleanly separated. The same test holds that direction too.

WHAT THIS DOES NOT CHANGE
-------------------------
Dedup semantics. `ci_alert.post_alert` rules on the message against the
committed ledger in `alert_state.json`, and `alert_state.decide()` mirrors the
endpoint's three shapes exactly:

    {subject, body}                  send every time, no dedup
    {subject, body, dedupe_key}      raise once per cause, remind at 14 days
    {subject, body, resolve_scope}   clear, mailing once if anything was open

Callers are ported with the shape they already had. A caller that was
undeduped stays undeduped, because changing an alarm's cadence while changing
its From line would make a later "why did this stop mailing?" unanswerable.
The one thing genuinely lost is the endpoint's legacy 3-day suppression by
subject hash, which `decide()` never implemented; the callers relying on it
had subjects carrying a count, so it almost never fired for them.

NEVER PRINTS A SUBJECT OR A BODY. Two callers here (`tracker_diff`,
`curated_probe`) carry company names that must reach the owner's inbox and no
other sink at all, and both have a test that poisons a whole run to prove it.
A debug print of the subject in this file would defeat both of them. The only
thing that reaches stdout is a fixed phrase and a delivery note.

BEST EFFORT, NEVER RAISES. Every caller is a reporting tail on a job that has
already done its real work. A notifier that raises while handling somebody
else's failure has told nobody anything, and it turns a delivery problem into
a red run, which is the amplification loop CLAUDE.md warns about.
"""

from __future__ import annotations

import opsmail


def configured() -> bool:
    """Can operational mail be sent at all right now?

    Callers gate on this instead of on `WP_SITE_URL`/`WP_API_KEY`, which is
    what they used to read and which has had nothing to do with sending mail
    since the Resend move.
    """
    return opsmail.configured()


def notify(subject: str, body: str, *, dedupe_key: str = "",
           resolve_scope: str = "", what: str = "operational alert") -> bool:
    """Send one operational email. Returns True if it went out.

    `what` is a fixed, name-free description used in the one line this prints,
    so a run log says which reporter spoke without quoting anything it said.
    """
    if not configured():
        print(f"ops mail: RESEND_API_KEY is not set, so the {what} was not "
              f"sent. Nothing was lost that the next run will not re-derive.")
        return False

    payload = {"subject": subject or "", "body": body or ""}
    if dedupe_key:
        payload["dedupe_key"] = dedupe_key
    if resolve_scope:
        payload["resolve_scope"] = resolve_scope

    try:
        # Imported here rather than at module scope: `ci_alert` imports
        # `opsmail`, and a top-level import in both directions is a cycle the
        # notification path does not need to own.
        import ci_alert
        ok, note, _transient = ci_alert.post_alert("", "", payload)
    except Exception as exc:  # pragma: no cover - defensive
        # The exception text, not the payload. See the module docstring.
        print(f"ops mail: the {what} could not be sent ({type(exc).__name__}: "
              f"{exc}). This is non-fatal.")
        return False

    print(f"ops mail: {what}: {note}")
    return bool(ok)


def resolve(scope: str, subject: str, body: str,
            what: str = "recovery notice") -> bool:
    """Clear an open cause. Silent when nothing was open, which is what makes
    it safe to call after every healthy run."""
    return notify(subject, body, resolve_scope=scope, what=what)
