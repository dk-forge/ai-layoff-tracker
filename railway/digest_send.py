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
  DIGEST_FREQ                      daily | weekly | auto (default auto).
                                   auto sends daily every day and weekly as
                                   well on a Monday, as two passes in one run.
                                   Naming a tier forces that one, on any day.
  DIGEST_VERIFY_ONLY=1             prove the credential and stop. Connects,
                                   authenticates and hangs up. Reads no
                                   recipient, builds no message, stamps
                                   nothing. Exit 2 only if the relay
                                   REFUSES the credential.
  DIGEST_DRY_RUN=1                 render everything, send nothing
  DIGEST_LIMIT                     stop after N recipients for the whole run,
                                   both tiers together (a first live send)
  DIGEST_PREVIEW=1                 when NOBODY is due, render the live sections
                                   once against a placeholder address so the
                                   email can be read. Ignored by any transport
                                   that sends.
  DIGEST_TEST_TO                   one nominated address. Renders the LIVE
                                   payload for this tier and sends it there
                                   and nowhere else. Reads no subscriber row,
                                   writes none, stamps no last_sent column and
                                   closes no send row.
  DIGEST_TEST_LISTS                which composed sections that one test
                                   message carries, comma separated
                                   (layoff, talent, articles). Default: all of
                                   them, which is what a subscriber to all
                                   three receives.
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
from digest_transport import (ABSENT, OK, REJECTED, UNKNOWN,  # noqa: F401
                              CredentialCheck, DigestPolicyError, Message,
                              TransportError, resolve_transport,
                              sender_identity)

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


def _flag(name: str) -> bool:
    """One reading of a yes/no environment variable."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _today():
    """Today in UTC. One place to read the clock, so a test can pin the day."""
    return datetime.datetime.now(datetime.timezone.utc).date()


def resolve_freqs(env=None, today=None) -> tuple:
    """Which tiers run today, in the order they are sent.

    `auto` mirrors the site's own cron exactly: daily every day, weekly
    ADDITIONALLY on Mondays UTC. One schedule, so there is one thing to
    watch, and two passes inside the one run on a Monday.

    THE DEFECT THIS ANSWERS, 2026-08-17. This returned a single tier, and on
    a Monday that tier was weekly rather than daily. The workflow runs once a
    day and this function chose what it sent, so every daily subscriber
    received nothing on a Monday. It was silent, it was weekly, and the
    docstring above described the intended behaviour the whole time.

    A subscriber who takes both tiers now receives two emails on a Monday.
    That follows from their own two choices, and it is not merged: merging
    would need the daily pass to know what the weekly pass is about to say.
    The two passes cannot suppress each other either, because the server side
    guard is per tier. See alt_digest_last_sent_column() in subscribe.php.

    DIGEST_FREQ still forces exactly one tier on any day of the week. That is
    what the workflow dispatch input is for.
    """
    env = os.environ if env is None else env
    choice = (env.get("DIGEST_FREQ") or "auto").strip().lower()
    if choice in {"daily", "weekly"}:
        return (choice,)
    today = today or _today()
    return ("daily", "weekly") if today.isoweekday() == 1 else ("daily",)


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
            out.append((name, html, text,
                        (section.get("preheader") or "").strip(),
                        (section.get("subject") or "").strip()))
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
    # "Edition" rather than "digest", because the word a masthead uses is the
    # word a reader takes for what this is. The phrase already carries the ISO
    # week number and the dates it covers for a weekly send.
    tier = {"weekly": "Weekly edition", "daily": "Daily edition"}.get(freq, "Edition")
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
    # The week-numbering convention, and only on the tier that prints a week
    # number. See digest_layout.WEEK_CONVENTION for why it is stated at all.
    edition_note = (digest_layout.WEEK_CONVENTION
                    if str(payload.get("freq") or "").strip().lower() == "weekly"
                    else "")
    html = digest_layout.render_html(
        parts, subject=subject, preheader=digest_layout.preheader_text(parts),
        kicker=kicker, unsub_url=unsub, manage_url=manage,
        edition_note=edition_note)
    text = digest_layout.render_text(parts, kicker=kicker, unsub_url=unsub,
                                     manage_url=manage, edition_note=edition_note)

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


def health_reading(credential, transport, details, failed_rows):
    """(status, detail) for the mailer's own health row. Never a silent pass.

    THE DEFECT THIS ANSWERS, 2026-08-19. The armed Brevo credential was being
    rejected with 535 and the mailer's health row read `ok, 0 entries` every
    day, because the row described the SEND and there was nothing to send: the
    list had nobody due, so `0 sent of 0 eligible` was true, complete and
    green. It is a real reading of a run that never touched the relay, and it
    is exactly as green as a run that sent to everybody. Two runs did touch the
    relay and both were manual test sends, which stay out of this ledger on
    purpose, so the one signal that existed was a red dispatch nobody watches.

    So the row now carries the credential state as well as the send counts, and
    the two facts are kept apart. `0 sent of 0 eligible` says nothing about
    whether this job COULD send, and it must never again read as if it did.
    """
    prefix = f"credential={credential.state.upper()}"
    body = "; ".join(details) if details else "no tier recorded a pass"

    if credential.state == REJECTED:
        return "degraded", f"{prefix} - {credential.detail}. {body}"
    if failed_rows:
        return "degraded", f"{prefix}; {body}"
    if credential.state == UNKNOWN and transport.sends:
        # NOT a pass. The relay could not be asked, so nothing is established,
        # and a green row here would be the same lie in a quieter voice. It is
        # equally not a fault: the run exits 0 and tomorrow settles it.
        return "degraded", f"{prefix} - {credential.detail}. {body}"
    if credential.state == ABSENT:
        # Dormant by design. Green, and the detail says why it is green so the
        # health page never reads it as a sender that is working.
        return "ok", f"{prefix} (dormant, nothing armed); {body}"
    return "ok", f"{prefix}; {body}"


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


# A token that belongs to nobody, and cannot be made to belong to anybody.
# The unsubscribe handler looks this up in the subscriber table, finds no row,
# and answers a POST with a bare 200 (includes/subscribe.php,
# alt_digest_unsubscribe). So the RFC 8058 header a test message carries is
# structurally real - one https URL, One-Click POST, our own host - and acts on
# nobody. A test send MUST NOT mint a real token: a token minted for a
# non-subscriber is a live unsubscribe link for somebody else's row the moment
# the minting logic is ever wrong.
TEST_UNSUB_TOKEN = "test-send-belongs-to-no-subscriber"
TEST_UNSUB_PATH = "ai-layoff-tracker/unsubscribe"


def _test_lists(env, sections):
    """Which composed sections the one test message carries.

    Named order is ignored: the SITE's order is kept, because that order is
    what decides the subject and the inbox snippet, and a test that reordered
    them would be showing a layout no subscriber receives.
    """
    raw = (env.get("DIGEST_TEST_LISTS") or "").strip()
    if not raw:
        return list(sections)
    wanted = {p.strip().lower() for p in raw.replace(",", " ").split() if p.strip()}
    return [name for name in sections if name.lower() in wanted]


def _test_payload(payload: dict, freq: str, env=None):
    """Send the LIVE digest to one nominated address and nowhere else.

    WHY THIS EXISTS. "Show me the email" had no answer that put an email in an
    inbox. The dry run prints to a run log, the preview needs nobody to be due
    AND a transport that does not send, and a real send is governed - correctly
    - by the per tier guard, so the day the digest has already gone out is
    exactly the day a demonstration is impossible. Three requests to see it
    went unanswered for that reason.

    WHAT IT DOES NOT TOUCH, and each of these is deliberate:

      the per tier guard. Untouched, unread and unweakened. A test run stamps
      no `last_sent_daily` and no `last_sent_weekly`, because it never calls
      /digest-complete: send_id is forced to 0 and that is the sole condition
      the completion call is made under. Nobody is hidden from tomorrow's run.

      the subscriber table. The one address is the one handed in by the
      operator. No row is read for it, and none is written.

      the unsubscribe path. The link is a token that matches no row, so the
      one-click POST answers 200 and unsubscribes nobody. The header shape is
      the real one, so what the operator sees is what a subscriber gets.

    IT REFUSES rather than competes. If real recipients ARE due for this tier,
    a test run would replace them in this pass. It stops instead and says so:
    a demonstration must never be the reason a subscriber missed a digest.

    Returns (payload, halt_code). `halt_code` is None to carry on, or an exit
    code to stop this tier with.
    """
    env = os.environ if env is None else env
    address = (env.get("DIGEST_TEST_TO") or "").strip()
    if not address:
        return None, None
    if "@" not in address or address.count("@") != 1:
        print(f"::error::DIGEST_TEST_TO is not an address; nothing sent")
        return None, 1

    due = payload.get("recipients") or []
    if due:
        print(f"::error::DIGEST_TEST_TO is set and {len(due)} real recipient(s) "
              f"are due for the {freq} tier right now. A test send would take "
              f"this pass and they would wait for the next one, so nothing was "
              f"sent at all. Run the test when the tier has already gone out, "
              f"which is when the per period guard leaves nobody due.")
        return None, 1

    sections = list((payload.get("sections") or {}).keys())
    if not sections:
        print(f"DIGEST_TEST_TO: the site composed no section for the {freq} "
              f"window, so there is nothing true to send. That is the live "
              f"state, not a failure.")
        return None, 0

    lists = _test_lists(env, sections)
    if not lists:
        print(f"::error::DIGEST_TEST_LISTS names no section the site composed "
              f"for this window. Composed: {', '.join(sections)}. Nothing sent.")
        return None, 1

    print(f"DIGEST_TEST_TO: sending the LIVE {freq} payload to ONE nominated "
          f"address, carrying {', '.join(lists)}. No subscriber row is read or "
          f"written, no last-sent column is stamped, no send row is closed, "
          f"and the unsubscribe link is a token that belongs to nobody.")
    test = dict(payload)
    # The single condition under which /digest-complete is called. Zero here is
    # what makes a test send unable to claim a period.
    test["send_id"] = 0
    test["recipients"] = [{
        "id": 0,
        "email": address,
        "unsub_url": f"{_site()}/{TEST_UNSUB_PATH}/{TEST_UNSUB_TOKEN}/",
        "lists": lists,
    }]
    return test, None


def _run_tier(freq: str, transport, from_addr: str, reply_to: str,
              limit: int | None) -> dict:
    """One tier's whole pass: ask, render, send, record what went out.

    A PASS IS INDEPENDENT OF THE OTHER ONE, and that is the design. The site
    keys the composer, the recipient query, the send row and the relay lease
    by frequency, so a Monday's two passes share nothing but the connection.
    Neither can consume the other's lease, and neither can mark the other's
    subscribers as already sent to: the per period guard is per tier as well
    (alt_digest_last_sent_column in includes/subscribe.php).

    Returns a small record for the caller to sum. `halt` means stop the run
    rather than try the next tier, because the fault is not about this tier.
    """
    result = {"code": 0, "sent": 0, "failed": 0, "eligible": 0, "detail": "",
              "preview": False, "test": False, "halt": False}
    print(f"digest: freq={freq} transport={transport.describe()}")

    try:
        payload = _call("digest-recipients", {"freq": freq})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print("::warning::the site has no /digest-recipients route yet, so "
                  "this build of the plugin is older than this job. Nothing "
                  "sent and nothing claimed.")
            result["halt"] = True
            return result
        print(f"::error::could not read the recipient list: HTTP {exc.code}")
        _record_health("degraded", 0, f"recipient route returned HTTP {exc.code}")
        result["code"] = 1
        result["halt"] = True
        return result
    except Exception as exc:  # noqa: BLE001
        # The host is shared and 504s now and then. A call that never landed
        # claimed no send, so tomorrow's run repeats it cleanly. The other
        # tier is not attempted either: the same host answers both.
        print(f"::warning::could not reach the recipient route ({exc}); "
              f"nothing was claimed, so the next run repeats this period")
        result["halt"] = True
        return result

    if not payload.get("available"):
        reason = payload.get("reason") or "the site reported no subscriber table"
        print(f"nothing sent: {reason}. This is not a zero subscriber count.")
        result["halt"] = True
        return result

    # A nominated test address takes precedence over the preview: it is the
    # explicit instruction, and the preview only ever substitutes when nobody
    # asked for anything else.
    test, halt = _test_payload(payload, freq)
    if halt is not None:
        result["halt"] = True
        result["code"] = halt
        return result
    if test is not None:
        payload = test
        result["test"] = True
    else:
        preview = _preview_payload(payload, transport)
        result["preview"] = preview is not None
        if preview is not None:
            payload = preview

    send_id = int(payload.get("send_id") or 0)
    eligible = len(payload.get("recipients") or [])
    result["eligible"] = eligible
    composed = sorted((payload.get("sections") or {}).keys())
    # WHAT WAS COMPOSED AND WHAT IS ACTUALLY GOING OUT, because they are not
    # the same thing and the log used to print only the first.
    #
    # THE DEFECT. A test send with DIGEST_TEST_LISTS=talent logged "sections
    # composed: articles, layoff, talent" and delivered talent alone, which is
    # correct behaviour and an unreadable log: the line reports identically
    # whether the filter took effect or not, so it cannot be used to verify the
    # input that it is the only evidence for. Somebody read it as proof the
    # flag was ignored and filed a bug against working code.
    #
    # `included` is the union of what the recipients in this payload will
    # actually receive, taken from the same `lists` field build_message reads,
    # so it cannot drift from the message.
    included = sorted({name for r in (payload.get("recipients") or [])
                       for name in (r.get("lists") or [])
                       if name in (payload.get("sections") or {})})
    print(f"digest: send_id={send_id} period {payload.get('from')} to "
          f"{payload.get('to')}, {eligible} eligible, sections composed: "
          f"{', '.join(composed) if composed else 'NONE'}; "
          f"sections included in what goes out: "
          f"{', '.join(included) if included else 'NONE'}")
    if not composed:
        print("no section could be composed from the live endpoints, so there "
              "is nothing true to say. Sending nothing rather than an empty "
              "digest or an invented figure.")

    sent_ids, failures = send_all(payload, transport, from_addr, reply_to, limit)
    result["sent"] = len(sent_ids)
    result["failed"] = len(failures)

    verb = "would send" if not transport.sends else "sent"
    print(f"digest: {freq}: {verb} {len(sent_ids)} of {eligible} eligible, "
          f"{len(failures)} failed")

    # Only a run that really put messages on the wire closes the send row and
    # stamps the tier's last-sent column. A dry run that claimed a send would
    # make tomorrow's real run skip everyone it printed.
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
    if result["preview"]:
        print("DIGEST_PREVIEW: nothing recorded, because a placeholder is not "
              "a recipient.")
    elif result["test"]:
        # A test send stays out of the ledger for the same reason a preview
        # does. One nominated address is not the list, and a health row
        # counting it would read as a digest that went out.
        print("DIGEST_TEST_TO: nothing recorded in the mailer's health row, "
              "and no last-sent column stamped. The scheduled run is "
              "unaffected.")
    else:
        result["detail"] = (f"{freq}: {len(sent_ids)} sent of {eligible} "
                            f"eligible via {transport.describe()}, "
                            f"{len(failures)} failed")

    # A failed delivery is not a red run on its own: one refused address among
    # hundreds is normal mail, and reddening for it is how a real outage stops
    # being noticed. Everything failing is a different fact.
    if failures and not sent_ids and eligible:
        print("::error::every delivery failed; the transport or its credential "
              "is wrong. Nothing reached a reader.")
        result["code"] = 2
    return result


def main() -> int:
    if not (_site() and _key()):
        print("WP_SITE_URL and WP_API_KEY are required; nothing attempted")
        return 1

    freqs = resolve_freqs()
    transport, notice = resolve_transport()
    from_addr, reply_to = sender_identity()
    print(f"digest: tiers={', '.join(freqs)}")
    print(f"digest: {notice}")

    # PROVE THE CREDENTIAL BEFORE READING THE LIST, and prove it whether or not
    # anybody is due. This is one connection, one LOGIN and a QUIT: no message
    # is built, no recipient is read and nothing is stamped. It exists because
    # for three days the only code that ever touched the relay was code that
    # had a message in its hand, so a rejected password and an empty list were
    # the same green run.
    credential = transport.verify()
    print(f"digest: credential {credential.line()}")

    if _flag("DIGEST_VERIFY_ONLY"):
        # Deliberately stamps nothing. This is the "did my rotation work?"
        # button, and a manual run that wrote the mailer's health row would let
        # a human hide a scheduled job that had stopped.
        print("DIGEST_VERIFY_ONLY: the credential was checked and nothing else "
              "was done. No recipient was read, no message was built, no "
              "health row was written.")
        return 2 if credential.is_fault else 0

    if credential.is_fault:
        # A refusal is settled: every message this run would build is a message
        # the relay is going to bounce, so the list is not read and no send row
        # is opened for a send that cannot happen. This IS recorded even on a
        # manual run - the guard that keeps test sends out of the ledger is
        # about deliveries, and a rejected credential is a fact about the
        # mailer no matter who pressed the button.
        print("::error::the relay REFUSED our credential, so nothing was "
              "attempted. This is a fault a human has to clear by rotating the "
              "secret: see RUNBOOK 'the digest cannot authenticate'.")
        status, detail = health_reading(credential, transport, [], 0)
        _record_health(status, 0, detail)
        return 2

    if len(freqs) > 1:
        print("digest: it is a Monday, so both tiers go out from this one "
              "run, as two separate passes. One cron, one job, two sends.")

    raw = os.environ.get("DIGEST_LIMIT", "").strip()
    remaining = int(raw) if raw.isdigit() else None

    codes, details = [], []
    sent_rows = 0
    failed_rows = 0
    for freq in freqs:
        if remaining == 0:
            # The run's whole allowance is spent. Asking the site for this
            # tier's list would open a send row nothing could ever fill.
            print(f"DIGEST_LIMIT is spent, so the {freq} tier was not asked "
                  f"for. Re-run without a limit to send it.")
            break
        outcome = _run_tier(freq, transport, from_addr, reply_to, remaining)
        codes.append(outcome["code"])
        sent_rows += outcome["sent"]
        failed_rows += outcome["failed"]
        if outcome["detail"]:
            details.append(outcome["detail"])
        if remaining is not None:
            # ONE ceiling for the whole run, not one per tier. DIGEST_LIMIT
            # exists for a first live send, and a Monday that quietly doubled
            # it would defeat the only brake that send has.
            remaining = max(0, remaining - outcome["sent"])
        if outcome["halt"]:
            break

    # A DELIVERY IS A STRONGER PROOF THAN A LOGIN. If the relay was unreachable
    # at check time but then carried real messages, the question the check could
    # not settle has been settled by the run itself, and the row should say so.
    if sent_rows and not credential.is_pass:
        credential = CredentialCheck(
            OK, transport.name,
            f"proved by delivery: {sent_rows} message(s) were accepted by the "
            f"relay during this run")

    # ONE health row for the run, naming every tier it covers. Two rows would
    # overwrite each other and the survivor would describe half the job. It is
    # written whenever a tier completed a pass, and it now carries the
    # credential state as well as the counts, so `0 sent of 0 eligible` can no
    # longer be the whole story.
    if details:
        status, detail = health_reading(credential, transport, details, failed_rows)
        _record_health(status, sent_rows, detail)
    return max(codes) if codes else 0


if __name__ == "__main__":
    sys.exit(main())
