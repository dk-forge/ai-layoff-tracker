"""Send the email digest. Dormant until a transport key exists.

WHAT THIS IS AND WHAT IT IS NOT.

The signup half already existed and is complete: double opt in, token confirm,
one click unsubscribe, a retention purge, and a keyed counts only stats route.
What did not exist was anything that puts a digest on the wire. This is that.

WHERE THE NUMBERS COME FROM.

Nowhere new. The site composes the sections through its own public /aggregate
and /query endpoints (includes/subscribe.php, alt_digest_compose_layoff), which
is the same code path the tracker page itself reads. There is deliberately no
second definition of a headline number in this file: if the digest and the page
ever disagreed, the digest would be the wrong one and nobody would know. A
figure the endpoint cannot supply is OMITTED. Nothing here fills a gap with a
guess, a carried forward value, or a zero.

WHERE THE ADDRESSES GO.

They stay on the WordPress host except for the moment of relay. This job asks
the keyed /digest-recipients route for the rows due in this period, holds them
in memory, hands each to the transport, and posts back COUNTS and ROW IDS. No
address is printed, logged, or written to disk at any point: log lines carry
`redacted()`, and the provider error scrubber takes any address out of a
provider's own message before it can reach a run log.

DORMANCY.

The default transport is dryrun. A named provider with no credential falls back
to dryrun with a notice naming the exact secret. Both exit 0. A missing key is
a state, not a failure, and a red run for it would train the owner to ignore
red runs.

Env:
  WP_SITE_URL, WP_API_KEY          required, as everywhere else
  DIGEST_TRANSPORT                 dryrun (default) | resend | smtp
  RESEND_API_KEY                   required only for resend
  DIGEST_SMTP_HOST/_PORT/_USER/_PASSWORD    required only for smtp
  DIGEST_FROM, DIGEST_REPLY_TO     identity on the verified domain
  DIGEST_FREQ                      daily | weekly | auto (default auto)
  DIGEST_DRY_RUN=1                 render everything, send nothing
  DIGEST_LIMIT                     stop after N recipients (a first live send)
  DIGEST_PREVIEW=1                 when NOBODY is due, render the live sections
                                   once against a placeholder address so the
                                   email can be read. Ignored by any transport
                                   that sends.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import digest_layout
from digest_transport import (DigestPolicyError, Message, TransportError,
                              resolve_transport, sender_identity)

UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

# Politeness pause between messages. Every provider rate limits, and the cheap
# tiers limit hardest. This list is measured in hundreds, so a tenth of a second
# costs a minute on a big send and removes a whole class of failure.
PAUSE_SECONDS = float(os.environ.get("DIGEST_PAUSE", "0.12"))


def _site() -> str:
    return os.environ.get("WP_SITE_URL", "").rstrip("/")


def _key() -> str:
    return os.environ.get("WP_API_KEY", "")


def _call(path: str, params=None, payload=None, timeout: int = 45):
    """One keyed call to the site. Returns parsed JSON or raises."""
    url = f"{_site()}/wp-json/layoffs/v1/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=data,
        headers={"X-Layoff-API-Key": _key(), "User-Agent": UA,
                 "Content-Type": "application/json"},
        method="POST" if data is not None else "GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def resolve_freq(env=None, today=None) -> str:
    """Which tier runs today.

    `auto` mirrors the site's own cron exactly: daily every day, weekly
    additionally on Mondays UTC. One schedule, so there is one thing to watch.
    """
    env = os.environ if env is None else env
    choice = (env.get("DIGEST_FREQ") or "auto").strip().lower()
    if choice in {"daily", "weekly"}:
        return choice
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    return "weekly" if today.isoweekday() == 1 else "daily"


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def usable_sections(payload: dict, wanted) -> list:
    """The sections that actually have something true to say.

    THE OMISSION RULE. A section reaches a reader only when the site handed us
    BOTH rendered parts for it. The composer returns nothing at all when its
    endpoint errors or when the period holds no entries, and this refuses to
    paper over that: an absent section is absent from the email. There is no
    branch here that substitutes a zero, a previous period, or a phrase like
    "no data available" dressed up as a figure.
    """
    out = []
    sections = payload.get("sections") or {}
    for name in wanted:
        section = sections.get(name)
        if not isinstance(section, dict):
            continue
        html = (section.get("html") or "").strip()
        text = (section.get("text") or "").strip()
        if html and text:
            # The fourth member is the section's own inbox snippet, composed
            # by the site for the 130-character ceiling. An older plugin build
            # sends no such field, and '' is the honest value for that: it
            # means "fall back", and digest_layout falls back to a line that
            # still describes THIS section rather than walking to another one.
            out.append((name, html, text, (section.get("preheader") or "").strip()))
    return out


def _same_site(url: str, reference: str) -> bool:
    """Is `url` on the same host as the unsubscribe link the site gave us?

    The unsubscribe URL is the one address in the payload we already trust to
    be ours, so it is the reference. This is not a formality: everything in the
    payload arrives over the network, and a link we print in a mail body under
    our own name has to be a link home.
    """
    try:
        a = urllib.parse.urlsplit(url)
        b = urllib.parse.urlsplit(reference)
    except ValueError:
        return False
    if a.scheme != "https" or a.username or a.password:
        return False
    return bool(a.hostname) and a.hostname.lower() == (b.hostname or "").lower()


def _kicker(payload: dict) -> str:
    """The masthead's second line: which tier this is, and for what window.

    Both facts come from the payload the site sent. When it carries a date
    this cannot read, the line is omitted rather than filled in.
    """
    phrase = digest_layout.period_phrase(payload)
    if not phrase:
        return ""
    freq = str(payload.get("freq") or "").strip().lower()
    tier = {"weekly": "Weekly digest", "daily": "Daily digest"}.get(freq, "Digest")
    return f"{tier}, {phrase}"


def build_message(payload: dict, recipient: dict, from_addr: str,
                  reply_to: str) -> Message | None:
    """One rendered digest, or None when this person has nothing due.

    The footer is built per recipient because the unsubscribe link is theirs
    alone. Everything above it was composed once for the whole send.
    """
    unsub = (recipient.get("unsub_url") or "").strip()
    if not unsub.startswith("https://"):
        return None
    parts = usable_sections(payload, recipient.get("lists") or [])
    if not parts:
        return None

    # A way to change WHAT you get, beside the way to stop everything. One
    # click unsubscribe is a blunt instrument: a reader who wants one of three
    # lists and receives three has exactly one button, and pressing it costs us
    # the other two.
    #
    # The URL comes from the site, never from here. An older plugin build does
    # not send the field, and a link guessed into a million inboxes is worse
    # than no link, so an absent or foreign one is simply omitted.
    manage = str(payload.get("manage_url") or "").strip()
    if not (manage.startswith("https://") and _same_site(manage, unsub)):
        manage = ""
    # Presentation lives in digest_layout: a table shell, every rule inline on
    # the element, and no style block at all, because a forward deletes the
    # head and every style block with it. No figure is composed there either.
    subject = digest_layout.subject_line(payload, parts)
    kicker = _kicker(payload)
    html = digest_layout.render_html(
        parts, subject=subject, preheader=digest_layout.preheader_text(parts),
        kicker=kicker, unsub_url=unsub, manage_url=manage)
    text = digest_layout.render_text(parts, kicker=kicker, unsub_url=unsub,
                                     manage_url=manage)

    return Message(
        to=str(recipient.get("email") or ""),
        subject=subject,
        html=html,
        text=text,
        from_addr=from_addr,
        reply_to=reply_to,
        headers={
            "List-Unsubscribe": f"<{unsub}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            # Groups the digest as bulk mail so a vacation responder does not
            # answer it and a filter can see what it is.
            "Precedence": "bulk",
            "Auto-Submitted": "auto-generated",
        },
    )


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

def send_all(payload: dict, transport, from_addr: str, reply_to: str,
             limit: int | None = None):
    """Hand every due message to the transport. Returns (sent_ids, failures).

    PER RECIPIENT FAILURE NEVER LOSES THE RUN. One address the provider refuses
    is one address, and the remaining hundreds still go out. Two kinds are told
    apart because they need different answers:

      a policy error is OUR bug in composition, is not retried, and is loud;
      a transport error is theirs, is retried once, and is counted.
    """
    recipients = payload.get("recipients") or []
    sent_ids, failures = [], []
    for index, recipient in enumerate(recipients):
        if limit is not None and len(sent_ids) >= limit:
            print(f"DIGEST_LIMIT reached at {limit}; "
                  f"{len(recipients) - index} recipient(s) not attempted this run")
            break
        message = build_message(payload, recipient, from_addr, reply_to)
        if message is None:
            continue
        label = message.redacted()
        try:
            transport.send(message)
        except DigestPolicyError as exc:
            # Composition broke a published promise. Never retried, and never
            # quietly dropped: this is a defect in this repo, not a provider
            # having a bad minute.
            print(f"::error::REFUSED to send to {label}: {exc}")
            failures.append((label, f"policy: {exc}"))
            continue
        except TransportError as exc:
            try:
                time.sleep(1.5)
                transport.send(message)
            except Exception as retry_exc:  # noqa: BLE001
                print(f"::warning::delivery failed for {label}: {retry_exc}")
                failures.append((label, f"transport: {retry_exc}"))
                continue
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::unexpected failure for {label}: {exc}")
            failures.append((label, f"unexpected: {exc}"))
            continue
        sent_ids.append(int(recipient.get("id") or 0))
        if transport.sends and PAUSE_SECONDS > 0:
            time.sleep(PAUSE_SECONDS)
    return sent_ids, failures


def _record_health(status: str, entries: int, detail: str) -> None:
    """The mailer's own row. A sender that silently stops must not look green.

    COUNTS ONLY, as everywhere else touching this list. Stamped on completion,
    never before, so a fatal mid run leaves the row stale and the three day
    ceiling in ops_status and the weekly digest turns it red.
    """
    try:
        from source_health import report_source_health
        report_source_health("digest_mailer", status, entries, detail[:240])
    except Exception as exc:  # noqa: BLE001
        print(f"(digest health post skipped: {exc})")


PREVIEW_ADDRESS = "preview@example.invalid"


def _preview_payload(payload: dict, transport):
    """Render the LIVE sections once when the list has nobody due.

    WHY THIS EXISTS. The RUNBOOK tells the owner to read the rendered email
    before arming the sender, and until now that instruction could not be
    followed: with no confirmed subscriber due, the site composes every
    section from the live endpoints and then the job renders nothing, because
    a message is built per recipient. So the one run that exists to be read
    printed a count and no email.

    IT CANNOT SEND. Two independent reasons: it only substitutes when the
    transport does not put anything on the wire, and the address is on
    `.invalid`, a reserved suffix that resolves nowhere. Nothing about the
    sections is faked. The only invented values are the address and the
    unsubscribe token, both of which are presentation for a reader of the log.

    Returns None when this is not a preview run, and the caller keeps the real
    payload untouched.
    """
    if os.environ.get("DIGEST_PREVIEW", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    if transport.sends:
        print("::warning::DIGEST_PREVIEW is set but this transport SENDS, so "
              "the preview was skipped entirely. A preview recipient must "
              "never reach a provider.")
        return None
    if payload.get("recipients"):
        return None
    # The site's OWN order, not alphabetical. Sorting put "From the blog"
    # above both trackers and made an article title the inbox snippet.
    sections = list((payload.get("sections") or {}).keys())
    if not sections:
        print("DIGEST_PREVIEW: the site composed no section, so there is "
              "nothing to preview. That is the live state, not a failure.")
        return None
    print(f"DIGEST_PREVIEW: nobody is due, so the live sections are rendered "
          f"once against a placeholder recipient at {PREVIEW_ADDRESS}. "
          f"Nothing is sent and no send is recorded.")
    preview = dict(payload)
    preview["send_id"] = 0
    preview["recipients"] = [{
        "id": 0,
        "email": PREVIEW_ADDRESS,
        "unsub_url": f"{_site()}/wp-admin/admin-post.php"
                     f"?action=alt_digest_unsub&t=preview",
        "lists": sections,
    }]
    return preview


def main() -> int:
    if not (_site() and _key()):
        print("WP_SITE_URL and WP_API_KEY are required; nothing attempted")
        return 1

    freq = resolve_freq()
    transport, notice = resolve_transport()
    from_addr, reply_to = sender_identity()
    print(f"digest: freq={freq} transport={transport.describe()}")
    print(f"digest: {notice}")

    try:
        payload = _call("digest-recipients", {"freq": freq})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("::warning::the site has no /digest-recipients route yet, so "
                  "this build of the plugin is older than this job. Nothing "
                  "sent and nothing claimed.")
            return 0
        print(f"::error::could not read the recipient list: HTTP {exc.code}")
        _record_health("degraded", 0, f"recipient route returned HTTP {exc.code}")
        return 1
    except Exception as exc:  # noqa: BLE001
        # The host is shared and 504s now and then. A call that never landed
        # claimed no send, so tomorrow's run repeats it cleanly.
        print(f"::warning::could not reach the recipient route ({exc}); "
              f"nothing was claimed, so the next run repeats this period")
        return 0

    if not payload.get("available"):
        reason = payload.get("reason") or "the site reported no subscriber table"
        print(f"nothing sent: {reason}. This is not a zero subscriber count.")
        return 0

    preview = _preview_payload(payload, transport)
    is_preview = preview is not None
    if is_preview:
        payload = preview

    send_id = int(payload.get("send_id") or 0)
    eligible = len(payload.get("recipients") or [])
    composed = sorted((payload.get("sections") or {}).keys())
    print(f"digest: send_id={send_id} period {payload.get('from')} to "
          f"{payload.get('to')}, {eligible} eligible, sections composed: "
          f"{', '.join(composed) if composed else 'NONE'}")
    if not composed:
        print("no section could be composed from the live endpoints, so there "
              "is nothing true to say. Sending nothing rather than an empty "
              "digest or an invented figure.")

    limit = os.environ.get("DIGEST_LIMIT", "").strip()
    sent_ids, failures = send_all(payload, transport, from_addr, reply_to,
                                  int(limit) if limit.isdigit() else None)

    verb = "would send" if not transport.sends else "sent"
    print(f"digest: {verb} {len(sent_ids)} of {eligible} eligible, "
          f"{len(failures)} failed")

    # Only a run that really put messages on the wire closes the send row and
    # stamps last_sent_at. A dry run that claimed a send would make tomorrow's
    # real run skip everyone it printed.
    if transport.sends and send_id > 0:
        try:
            _call("digest-complete", payload={
                "send_id": send_id, "freq": freq, "eligible": eligible,
                "sent_ids": sent_ids, "failed": len(failures),
                "transport": transport.name,
            })
        except Exception as exc:  # noqa: BLE001
            print(f"::warning::could not record the send ({exc}); the messages "
                  f"went out but the log row still reads 0. The per period "
                  f"guard is what stops a second copy, so investigate before "
                  f"the next run.")

    # A preview stays out of the ledger. Its one placeholder recipient is not
    # a delivery, and a health row that counted it would read as a send.
    if is_preview:
        print("DIGEST_PREVIEW: nothing recorded, because a placeholder is not "
              "a recipient.")
    else:
        detail = (f"{freq}: {len(sent_ids)} sent of {eligible} eligible via "
                  f"{transport.describe()}, {len(failures)} failed")
        _record_health("degraded" if failures else "ok", len(sent_ids), detail)

    # A failed delivery is not a red run on its own: one refused address among
    # hundreds is normal mail, and reddening for it is how a real outage stops
    # being noticed. Everything failing is a different fact.
    if failures and not sent_ids and eligible:
        print("::error::every delivery failed; the transport or its credential "
              "is wrong. Nothing reached a reader.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
