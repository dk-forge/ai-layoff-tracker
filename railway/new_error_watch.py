#!/usr/bin/env python3
"""Hourly new-error watch: Sentry issues, summarised once, mailed by the one door.

WHAT THIS IS
------------
`ci_alert.py` tells the owner when a WORKFLOW goes red. This tells the owner
when a NEW, UNRESOLVED Sentry issue appears in the last hour on the surface
`ops_status.py` already watches for this repository, a second, faster signal
that does not wait for a scheduled job to fail before anyone hears about it.

DEDUPE, THE SAME SHAPE AS `alert_state.py`, A SEPARATE FILE
-------------------------------------------------------------
`ci_alert`'s ledger (`railway/alert_state.json`) is keyed on workflow+branch+
assertion. A Sentry issue is a different kind of cause living in a different
namespace, so it gets its OWN committed ledger, `railway/new_error_state.json`,
built with the exact same module (`alert_state.py`, parameterised by `path=`)
so it carries the identical three semantics: send every time (unused here),
raise once per cause and remind at 14 days, clear once when a cause resolves.
Reusing the module, not re-implementing it, is what keeps "the same shape"
true by construction rather than by promise.

Because the dedup decision is made HERE, against OUR OWN ledger, the message
is handed to `ops_notify.notify()` with no `dedupe_key`/`resolve_scope` of its
own (the "send every time" shape), routing it a second time through
`ci_alert.post_alert`'s ledger would dedupe it a second time, against the
WRONG file, and could silently swallow a genuine alert whose fingerprint
happens to collide in that other namespace.

THE CAUSE KEY mirrors `ci_alert.normalise()`: numbers stripped before hashing,
so `TypeError at line 214` and `TypeError at line 219` are the same cause and
`TypeError` and `KeyError` are not.

ONE MODEL CALL, ONLY WHEN A CAUSE IS NEW
-----------------------------------------
A cause that is already open, or that is a repeat within the reminder window,
gets NO model call: the summary was already sent, and a reminder resends it
from the ledger's stored subject rather than re-asking. Only a first sighting
spends anything.

THE CALL GOES THROUGH `spend.metered_call` (gate read -> request -> meter, one
request per read, the iron rule in CLAUDE.md), but the $3.00/month CEILING it
must respect is NOT `spend.py`'s own $10 allowance, that number is a shared
budget across the OTHER key (`OPENROUTER_API_KEY`) and the OTHER jobs that
spend it, and mixing this repo's slice of a separate, cross-repo $3.00 credit
into that ledger would misattribute both. So this module keeps its OWN
committed spend ledger, `railway/new_error_spend.json`, checked BEFORE the
call and updated with the real cost AFTER it. `spend.metered_call` still gates
the request against `spend.py`'s per-run/monthly brake as a second, harmless
backstop, and it is what gives us "exactly one request, retried only via
`attempts=N`, never from inside the callable."

WHATEVER HAPPENS TO THE SUMMARY, THE ALERT STILL SENDS. A raised exception, an
absent key, or a spent cap all fall through to the same plain alert with a line
that says WHICH of the three happened. An LLM outage must never silence an
error alert; that would be the exact inversion of what this file exists to
prevent.

REDACTION happens before any error text reaches the prompt: email addresses,
bearer tokens, API keys and authorization header values are replaced first.
Nothing else from this repository enters the prompt, only the issue's own
title/culprit/metadata, already public information inside Sentry.

THE ONE DOOR. This module never builds a client for Resend, never reads
`OPS_MAIL_FROM`, never stamps a subject prefix. It builds `(subject, body)`
and hands them to `ops_notify.notify()`, exactly as `tracker_diff` and
`curated_probe` do -- and, like those two, it is therefore BEST EFFORT on
delivery, not a second implementation of `ci_alert`'s outbox hold. The relay
being down does not raise here and does not redden this run (`opsmail`'s own
contract: "BEST EFFORT, NEVER RAISES"); it prints why and the cause stays open
in `new_error_state.json`, so the very next hourly run re-derives it as still
new and tries again. Building a bespoke hold/outbox path around ops_notify's
return value would mean either reading `OPS_MAIL_FROM`/stamping a prefix
ourselves (the thing the one door exists to prevent) or reaching past it into
`ci_alert.post_alert` directly, which is the second sender this design
forbids. Nothing here queues past that: the ledger's own retry loop is the
durability this module gets, and it is bounded (14 days) rather than
unbounded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alert_state  # noqa: E402
import ops_notify  # noqa: E402
import spend  # noqa: E402

ROOT = Path(__file__).resolve().parent

#: Our own dedupe ledger. Same module, same shape, a different namespace from
#: `alert_state.STATE` (railway/alert_state.json), by design, see docstring.
STATE_PATH = ROOT / "new_error_state.json"

#: Our own spend ledger for the separate, cross-repo $3.00/month
#: OPENROUTER_OPS_KEY credit. Committed so any of the three repos sharing that
#: key can see, in one place, what this repo has already spent this month.
SPEND_LEDGER_PATH = ROOT / "new_error_spend.json"

MONTHLY_CAP_USD = 3.00
MODEL = "google/gemini-2.5-flash-lite"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

#: The Sentry organisation lives on the EU region (de.sentry.io), not the
#: default sentry.io/api/0 host — a request to the wrong region's API returns
#: 404s that would otherwise read as "Sentry could not be checked" (UNKNOWN)
#: forever. Read from SENTRY_REGION_URL so a region move is a variable change,
#: never a code change; default matches this org's actual region.
DEFAULT_SENTRY_REGION_URL = "https://de.sentry.io"


def sentry_api_base() -> str:
    region = os.environ.get("SENTRY_REGION_URL", "").strip() or DEFAULT_SENTRY_REGION_URL
    return region.rstrip("/") + "/api/0"

# Prefix on the note fetch_new_issues returns when this watch is simply not
# configured. ABSENT and UNKNOWN are different states and the digest mailer
# already learned this one the hard way: "nothing armed" is green, "armed
# and could not be read" is red, and collapsing the first into the second
# sends someone to fix a thing that was never switched on.
ABSENT_NOTE = "not configured"

#: Every network request gets a browser-ish UA, the same iron rule as every
#: other network caller in this repo, even though neither Sentry nor
#: OpenRouter is the WP host that taught it to us.
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: A cause is "still open" and skipped again inside this window, mirroring
#: alert_state.REMIND_AFTER_SECONDS (14 days) via the shared decide()/claim().


# ---------------------------------------------------------------------------
# Configuration read from the environment. No secret is ever printed.
# ---------------------------------------------------------------------------

def sentry_org() -> str:
    return os.environ.get("SENTRY_ORG", "").strip()


def sentry_project() -> str:
    return os.environ.get("SENTRY_PROJECT", "").strip()


def sentry_token() -> str:
    return os.environ.get("SENTRY_AUTH_TOKEN", "").strip()


def openrouter_ops_key() -> str:
    return os.environ.get("OPENROUTER_OPS_KEY", "").strip()


# ---------------------------------------------------------------------------
# Sentry: unresolved, new issues in the last hour
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: dict):
    """One GET. Returns (status, text). Never raises for an HTTP error status
    (translated to a normal return), only for a transport failure."""
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - best-effort diagnostics only
            body = ""
        return exc.code, body


def fetch_new_issues(hours: int = 1, fetch=None):
    """-> (issues_or_None, note). `issues` is a list of Sentry issue dicts.

    None means "could not be checked" (UNKNOWN, never read as zero issues);
    `fetch` is injectable so tests never open a socket.
    """
    org, project, token = sentry_org(), sentry_project(), sentry_token()
    if not (org and project and token):
        # ABSENT, not UNKNOWN. Nothing is armed here, which is a state of its
        # own and a green one. See run() for why the difference matters.
        return None, (ABSENT_NOTE + ": SENTRY_ORG, SENTRY_PROJECT or "
                      "SENTRY_AUTH_TOKEN is not set, so nothing is armed")
    # "is:new" is not a valid Sentry search token (Sentry confirmed this with
    # a plain HTTP 400 and no body worth surfacing) - "new" is a SORT value,
    # not a filter. "age:-{h}h" is the actual filter for "first seen within
    # the last N hours", which is what this watch means by "new".
    url = (f"{sentry_api_base()}/projects/{org}/{project}/issues/"
           f"?query={urllib.parse.quote(f'is:unresolved age:-{hours}h', safe='')}"
           f"&limit=25")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA,
               "Accept": "application/json"}
    getter = fetch or _http_get
    try:
        status, body = getter(url, headers)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return None, f"could not reach Sentry: {exc}"
    if status != 200:
        # Sentry's own error body (e.g. {"detail": "..."}) is not a secret -
        # it is the API telling us what was wrong with OUR request - and
        # surfacing it is the difference between "Sentry returned HTTP 400"
        # (which says nothing actionable) and knowing which query token or
        # parameter to fix.
        detail = (body or "").strip()[:300]
        return None, (f"Sentry returned HTTP {status}: {detail}" if detail
                       else f"Sentry returned HTTP {status}")
    try:
        issues = json.loads(body or "[]")
    except ValueError:
        return None, "Sentry's response was not valid JSON"
    if not isinstance(issues, list):
        return None, "Sentry's response had an unexpected shape"
    return issues, "ok"


# ---------------------------------------------------------------------------
# Cause key: numbers normalised out before hashing, mirroring ci_alert.normalise
# ---------------------------------------------------------------------------

_NORMALISE = [
    (re.compile(r"0x[0-9a-fA-F]+"), "<hex>"),
    (re.compile(r"\b\d+\b"), "<n>"),
]


def normalise_cause(text: str) -> str:
    out = (text or "").strip()
    for pattern, replacement in _NORMALISE:
        out = pattern.sub(replacement, out)
    return out.strip()


def issue_headline(issue: dict) -> str:
    title = str(issue.get("title") or issue.get("metadata", {}).get("value")
                or issue.get("culprit") or "unknown error")
    culprit = str(issue.get("culprit") or "")
    return f"{title} ({culprit})" if culprit and culprit not in title else title


def cause_key(issue: dict) -> str:
    headline = normalise_cause(issue_headline(issue))
    fp = hashlib.md5(headline.encode("utf-8")).hexdigest()[:16]
    return f"sentry-new-error:{fp}"


# ---------------------------------------------------------------------------
# Redaction. Runs on the error text BEFORE it ever reaches a prompt.
# ---------------------------------------------------------------------------

_REDACTIONS = [
    # Authorization header values (any scheme), checked before bare tokens so
    # the header name is consumed along with its value.
    (re.compile(r"(?i)\bauthorization\s*:\s*\S+"), "authorization: <redacted>"),
    (re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]+"), "bearer <redacted>"),
    # Email addresses.
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
     "<redacted-email>"),
    # Long opaque tokens that look like API keys (OpenRouter/OpenAI/Sentry-
    # style prefixes, or any bare run of 24+ base62 characters).
    (re.compile(r"\b(?:sk|sntrys|sntryu)-[A-Za-z0-9_\-]{10,}\b"), "<redacted-key>"),
    (re.compile(r"\b[A-Za-z0-9_\-]{24,}\b"), "<redacted-token>"),
]


def redact(text: str) -> str:
    """Replace anything that looks like a credential before it can reach a
    prompt. Order matters: authorization headers and bearer tokens are
    consumed before the generic long-token pattern would otherwise partially
    match them."""
    out = str(text or "")
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


# ---------------------------------------------------------------------------
# The $3.00/month ledger for OPENROUTER_OPS_KEY
# ---------------------------------------------------------------------------

def _month_key(now: float | None = None) -> str:
    dt = datetime.fromtimestamp(now, tz=timezone.utc) if now else datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


def load_spend_ledger(path: Path | str = SPEND_LEDGER_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return {"version": 1, "months": {}}
    try:
        doc = json.loads(p.read_text() or "{}")
    except (OSError, ValueError):
        return {"version": 1, "months": {}}
    if not isinstance(doc, dict) or not isinstance(doc.get("months"), dict):
        return {"version": 1, "months": {}}
    return doc


def save_spend_ledger(doc: dict, path: Path | str = SPEND_LEDGER_PATH) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def spend_this_month(path: Path | str = SPEND_LEDGER_PATH, now: float | None = None) -> float:
    doc = load_spend_ledger(path)
    return float(doc.get("months", {}).get(_month_key(now), {}).get("spent_usd", 0.0))


def record_spend(cost_usd: float, path: Path | str = SPEND_LEDGER_PATH,
                  now: float | None = None) -> None:
    if cost_usd <= 0:
        return
    doc = load_spend_ledger(path)
    months = doc.setdefault("months", {})
    key = _month_key(now)
    entry = months.setdefault(key, {"spent_usd": 0.0, "calls": 0})
    entry["spent_usd"] = round(float(entry.get("spent_usd", 0.0)) + float(cost_usd), 6)
    entry["calls"] = int(entry.get("calls", 0)) + 1
    save_spend_ledger(doc, path)


def cap_remaining(path: Path | str = SPEND_LEDGER_PATH, now: float | None = None) -> bool:
    return spend_this_month(path, now) < MONTHLY_CAP_USD


# ---------------------------------------------------------------------------
# One summary call, only for a NEW cause, only under the cap.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are summarising ONE application error for an on-call engineer. Reply "
    "with exactly three lines, plain language, no markdown:\n"
    "What broke: <one sentence>\n"
    "Likely cause: <one sentence>\n"
    "Suggested next step: <one sentence>"
)


def _make_openrouter_call(prompt: str, api_key: str, http_post=None):
    """Exactly one HTTP request. Handed to spend.metered_call as the callable;
    it must never loop or retry, see the module docstring and CLAUDE.md."""
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": UA,
        "HTTP-Referer": "https://asktherecruiter.com/blog/ai-layoff-tracker/",
        "X-Title": "AI Layoff Tracker ops: new-error summary",
    }

    def _default_post():
        req = urllib.request.Request(OPENROUTER_URL, data=body, headers=headers,
                                     method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))

    return (http_post or _default_post)()


def summarize_issue(issue: dict, http_post=None, spend_path: Path | str = SPEND_LEDGER_PATH):
    """-> (summary_text_or_None, reason).

    `reason` is one of: "ok", "no key", "cap reached", "call failed: <why>".
    Never raises: a summary is a nice-to-have on an alert that must still send.
    """
    api_key = openrouter_ops_key()
    if not api_key:
        return None, "no key"
    if not cap_remaining(spend_path):
        return None, "cap reached"

    headline = redact(issue_headline(issue))
    extra = redact(str(issue.get("metadata", {}).get("value")
                        or issue.get("permalink") or ""))
    prompt = f"Error title: {headline}\nDetail: {extra}\n"

    try:
        response = spend.metered_call(
            MODEL,
            lambda: _make_openrouter_call(prompt, api_key, http_post),
            what="new-error summary",
            usage_of=lambda r: (r or {}).get("usage"),
        )
    except spend.PaidReadsOff as exc:
        return None, f"call failed: {exc}"
    except Exception as exc:  # noqa: BLE001 - a summary must never break the alert
        return None, f"call failed: {type(exc).__name__}: {exc}"

    try:
        text = response["choices"][0]["message"]["content"].strip()
        cost = float((response.get("usage") or {}).get("cost") or 0.0)
    except (KeyError, IndexError, TypeError, ValueError):
        return None, "call failed: unexpected response shape"

    record_spend(cost, spend_path)
    return text, "ok"


# ---------------------------------------------------------------------------
# Ledger decide/apply, reusing alert_state.py against OUR path
# ---------------------------------------------------------------------------

def decide_for_issue(issue: dict, state: dict, now: int | None = None):
    key = cause_key(issue)
    subject = f"NEW ERROR: {issue_headline(issue)}"[:180]
    payload = {"subject": subject, "body": "", "dedupe_key": key}
    return alert_state.decide(state, payload, now=now)


def build_body(issue: dict, summary_text, summary_reason: str) -> str:
    permalink = str(issue.get("permalink") or issue.get("shortId") or "")
    lines = [
        "A new, unresolved Sentry issue appeared in the last hour.",
        "",
        f"  issue:     {issue_headline(issue)}",
        f"  Sentry id: {issue.get('shortId') or issue.get('id') or 'unknown'}",
    ]
    if permalink:
        lines.append(f"  link:      {permalink}")
    lines.append("")
    if summary_reason == "ok" and summary_text:
        lines.append("Summary:")
        lines.append(summary_text)
    else:
        why = {
            "no key": "OPENROUTER_OPS_KEY is not set",
            "cap reached": f"the ${MONTHLY_CAP_USD:.2f}/month summary cap is spent",
        }.get(summary_reason, summary_reason)
        lines.append(f"No AI summary: {why}. The issue details above are the "
                      "whole signal for this alert.")
    lines.append("")
    lines.append("You will get ONE more email about this cause: a note when it "
                  "resolves. A repeat within 14 days is suppressed on purpose.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Resolution: an open cause is cleared only when SENTRY says the underlying
# issue is resolved, checked by issue id, never by "it did not show up in
# this hour's /new/ page again" (which would clear every cause a day after it
# opened, whether or not anyone had touched it, and would read as a false
# RECOVERED).
# ---------------------------------------------------------------------------

def fetch_issue_status(issue_id: str, fetch_status=None):
    """-> status string ('resolved', 'unresolved', 'ignored', ...) or None if
    it could not be checked. `fetch_status` is injectable for tests."""
    org, project, token = sentry_org(), sentry_project(), sentry_token()
    if not (org and project and token and issue_id):
        return None
    url = f"{sentry_api_base()}/issues/{issue_id}/"
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA,
               "Accept": "application/json"}
    getter = fetch_status or _http_get
    try:
        status, body = getter(url, headers)
    except (urllib.error.URLError, OSError, TimeoutError):
        return None
    if status != 200:
        return None
    try:
        return json.loads(body or "{}").get("status")
    except ValueError:
        return None


def resolve_settled_causes(state: dict, now: int | None = None, fetch_status=None):
    """Clear every open cause whose Sentry issue now reports 'resolved' or
    'ignored'. Returns a list of Decisions (possibly empty). A cause whose
    status could not be checked is left open (UNKNOWN is not a clear).

    Each settled cause is resolved by its OWN exact key, one `decide()` call
    per cause, so a still-open sibling that merely shares the
    "sentry-new-error" prefix is never swept in by a wider scope.
    """
    entries = state.get("open") or {}
    decisions = []
    for key, entry in list(entries.items()):
        if not key.startswith("sentry-new-error:"):
            continue
        status = fetch_issue_status(entry.get("issue_id"), fetch_status=fetch_status)
        if status not in ("resolved", "ignored"):
            continue
        payload = {"subject": "RECOVERED: new-error watch",
                   "body": "This Sentry issue is now resolved or ignored:\n"
                           f"  {entry.get('subject') or key}",
                   "resolve_scope": key}
        decisions.append(alert_state.decide(state, payload, now=now))
    return decisions


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(*, fetch=None, http_post=None, fetch_status=None,
        state_path: Path | str = STATE_PATH,
        spend_path: Path | str = SPEND_LEDGER_PATH, now: int | None = None,
        sleep=time.sleep, notify=None) -> int:
    """-> exit code. 0 on a clean run (including "nothing new") and 0 when this
    watch is not configured at all; 3 when it IS configured and Sentry could
    not be read (UNKNOWN, never a silent pass)."""
    notify = notify or ops_notify.notify
    issues, note = fetch_new_issues(fetch=fetch)
    if issues is None:
        print(f"new_error_watch: {note}")
        # THREE STATES, NOT TWO. `ABSENT` means no Sentry credentials exist, so
        # this watch was never switched on: exit 0, because an hourly red run
        # for a feature nobody armed is manufactured noise, and manufactured
        # noise is how a real alert gets filtered. `UNKNOWN` means it IS armed
        # and Sentry could not be read, which must go red and stay red. The
        # digest mailer carries the same distinction for the same reason, and
        # CLAUDE.md says plainly not to collapse ABSENT into the fault state.
        return 0 if note.startswith(ABSENT_NOTE) else 3

    state = alert_state.load(state_path)

    for issue in issues:
        decision = decide_for_issue(issue, state, now=now)
        if decision.kind != "raise":
            continue  # already open within the reminder window
        summary_text, summary_reason = None, "no key"
        if decision.subject.startswith("STILL FAILING"):
            summary_reason = "repeat reminder, no new call"
        else:
            summary_text, summary_reason = summarize_issue(
                issue, http_post=http_post, spend_path=spend_path)
        body = build_body(issue, summary_text, summary_reason)
        ok = notify(decision.subject, body)
        status_note = "sent" if ok else (
            "NOT sent, cause stays new so the next hourly run retries it")
        print(f"new_error_watch: {decision.subject}: {status_note}")
        if ok:
            # Only committed to the ledger once it actually sent. A failed
            # send leaves nothing in `open`, so decide() reads this cause as
            # still NEW next run and tries again, the ledger's own retry,
            # bounded by the next hourly tick rather than by an unbounded
            # queue. See the module docstring on why this is not a second
            # outbox.
            alert_state.apply(state, decision, now=now)
            # issue_id is additive metadata beside alert_state's own
            # first/last/subject fields, it is how resolve_settled_causes()
            # later asks Sentry whether THIS specific issue settled.
            state["open"][cause_key(issue)]["issue_id"] = str(
                issue.get("id") or issue.get("shortId") or "")

    for resolve_decision in resolve_settled_causes(state, now=now, fetch_status=fetch_status):
        if resolve_decision.kind != "resolve":
            continue
        # Same ordering as the raise path above, and for the same reason: the
        # clear is committed only once the RECOVERED notice actually sent. A
        # failed send leaves the cause open, so the next hourly run asks Sentry
        # again, finds it still settled and re-sends. Applying first would drop
        # the cause from the ledger whether or not anyone was ever told it
        # recovered, and RECOVERED is mailed once by contract.
        if notify(resolve_decision.subject, resolve_decision.body):
            alert_state.apply(state, resolve_decision, now=now)

    alert_state.save(state, state_path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
