#!/usr/bin/env python3
"""Mail the owner when a source goes dark, on the TRANSITION and not before.

This is not a new alert channel and must never become one. It composes a
payload and hands it to the machinery that already exists: `alert_state.claim`
rules on it against the committed ledger (one cause one email, RECOVERED once,
a STILL FAILING reminder at 14 days), and `ci_alert.deliver` sends it through
Resend, which is off the WordPress host this repo reports about.

THE DEDUP KEY IS THE SOURCE AND THE REASON CLASS. NOT THE DAY COUNT.
--------------------------------------------------------------------
`warn:ks` dark for 110 days is the same alarm tomorrow at 111. Putting the count
in the key would defeat dedup completely and mail the owner every single morning
about a thing he already knows. The scope is per source, so recovering Kansas
clears Kansas and nothing else.

The key is built from the source identity and the reason class ONLY, and run
through `ci_alert.normalise` for the same reason ci_alert does it: so a number
that drifts while the same thing stays broken cannot mint a second alarm. It is
never empty — an empty or constant cause key is how one garbage hash silently
swallowed every no-cause failure of a workflow.

A BACKLOG IS ONE EMAIL.
-----------------------
Six states were dark the night this was written. Six emails is how an alert
channel gets filtered, and a filtered channel is why the defect survived. When a
run finds more than one NEW dark source it claims each cause separately (so each
recovers on its own, later) and sends ONE message with a block per source.
"""
import hashlib
import os

import alert_state
import ci_alert
import source_freshness

#: The subject leads with the identifying words, because they are read on a
#: phone and a list of subjects that all start the same way is a list of
#: identical subjects. Country first, then the source name. Nothing before it.
SUBJECT = "{country} - {source}"

US_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "US Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

#: Which classes a future healer could even attempt. Nothing here authorises a
#: repair — this PR detects only — but the owner asked to know from the email
#: whether a thing needs him, so the line has to be in the message.
HEALER_ELIGIBLE = {source_freshness.DRIFT, source_freshness.FORMAT_CHANGE}


def identity(key):
    """('United States', 'Kansas WARN') for 'warn:KS'.

    Falls back to the raw key rather than guessing, so a source namespace added
    later is unmistakable in the subject instead of silently mislabelled as US.
    """
    family, _, rest = str(key).partition(":")
    if family == "warn" and rest.upper() in US_STATE_NAMES:
        return "United States", f"{US_STATE_NAMES[rest.upper()]} WARN"
    return "Worldwide", str(key)


def cause_key(row):
    """`source-dark:<source>:<fingerprint>`, stable while the break is.

    The scope prefix is what `alert_state`'s resolve path matches on
    (`k.startswith(scope + ":")`), so it must carry the source and nothing that
    varies run to run.
    """
    key = str(row["key"]).lower()
    kind = row.get("classification") or source_freshness.DRIFT
    scope = f"source-dark:{key}"
    fingerprint = hashlib.md5(
        ci_alert.normalise(f"{key}|{kind}").encode("utf-8")).hexdigest()[:16]
    return scope, f"{scope}:{fingerprint}"


def paste_line(row):
    """The line he pastes into a Claude Code session. His established loop."""
    country, source = identity(row["key"])
    return (f'"The {source} collector ({country}) has published nothing new for '
            f'{row.get("days_dark")} days. Its own filing rate is '
            f'{row.get("rate_per_year")} notices a year, so this is not a quiet '
            f'spell. Reason class: {row.get("classification")}. Reproduce it '
            f'locally, find the root cause, and fix the collector - do not '
            f'change the freshness threshold. See docs/RUNBOOK.md \'a collector '
            f'went dark\'."')


def block(row):
    country, source = identity(row["key"])
    healable = (row.get("classification") in HEALER_ELIGIBLE)
    lines = [
        f"{country} - {source}",
        "",
        "Paste this into a Claude Code session in the ai-layoff-tracker repo:",
        f"  {paste_line(row)}",
        "",
        f"  days dark:    {row.get('days_dark')}",
        f"  its own rate: {row.get('rate_per_year')} notices/yr",
        f"  P(0 notices): {row.get('p0')}  (a break needs p<{source_freshness.ALPHA_DARK})",
        f"  reason class: {row.get('classification')}",
        ("  a healer could attempt this class (it returns rows, just nothing "
         "new)" if healable else
         "  NOT auto-fixable: this one needs a person"),
        f"  why:          {row.get('last_reason')}",
    ]
    return "\n".join(lines)


def build(rows, run_url=""):
    """(subject, body) for one or many dark sources. One backlog, one email."""
    if len(rows) == 1:
        country, source = identity(rows[0]["key"])
        subject = SUBJECT.format(country=country, source=source)
        subject = f"{subject} - dark {rows[0].get('days_dark')}d"
        head = ["This source is publishing nothing new and every count-based "
                "check reads it as healthy.", ""]
    else:
        subject = (f"{len(rows)} sources dark - "
                   + ", ".join(identity(r["key"])[1] for r in rows[:3])
                   + ("" if len(rows) <= 3 else f" and {len(rows) - 3} more"))
        head = [f"{len(rows)} sources are publishing nothing new. This is one "
                "finding, not one email each - act on any of them "
                "independently.", ""]
    body = head + ["\n".join([block(r), ""]) for r in rows]
    body.append("")
    body.append("To see the current state of every source:")
    body.append("  python3 railway/source_freshness.py --report")
    if run_url:
        body.append(f"Run: {run_url}")
    body.append("")
    body.append("You will get ONE more email per source: a RECOVERED notice on "
                "its next healthy run. Repeats of the same cause are suppressed "
                "on purpose, with a STILL FAILING reminder after 14 days.")
    return subject[:180], "\n".join(body)


def already_open(dedupe_key, path=None):
    state = alert_state.load(alert_state.state_path(path))
    return dedupe_key in (state.get("open") or {})


def announce(rows, *, run_url="", sender=None):
    """Claim each NEW dark source, then send ONE email covering them.

    Returns (sent, keys_claimed, note). Never raises: a data job that dies while
    telling somebody about a gap has turned one problem into two.
    """
    sender = sender or ci_alert.deliver
    fresh, claims = [], []
    for row in rows:
        scope, dedupe = cause_key(row)
        if already_open(dedupe):
            continue
        fresh.append((row, dedupe))
    if not fresh:
        return False, [], "every dark source is already an open alarm"

    subject, body = build([r for r, _ in fresh], run_url=run_url)
    idem = ""
    for row, dedupe in fresh:
        payload = {"subject": subject, "body": body, "dedupe_key": dedupe}
        try:
            decision, recorded = alert_state.claim(payload)
        except Exception as exc:                              # noqa: BLE001
            print(f"::warning::could not claim {dedupe}: {exc}")
            continue
        if not decision.sends:
            continue
        claims.append(dedupe)
        idem = idem or decision.idempotency_key()
    if not claims:
        return False, [], "another run claimed these first"
    try:
        ok, note, _transient = sender({"subject": subject, "body": body},
                                      idem=idem)
    except Exception as exc:                                  # noqa: BLE001
        ok, note = False, str(exc)
    if not ok:
        # Loud, not red. A delivery failure must never manufacture a red run;
        # ops_status [4b] is where a held or failed alert is chased.
        print(f"::warning::the dark-source alert could not be delivered ({note}). "
              f"The causes are recorded open in railway/alert_state.json and "
              f"railway/source_state.json, so ops_status still shows them.")
    return ok, claims, note


def announce_recovery(key, *, sender=None):
    """Clear one source's alarm. Mails once, only if something was open."""
    sender = sender or ci_alert.deliver
    scope = f"source-dark:{str(key).lower()}"
    country, source = identity(key)
    payload = {
        "subject": SUBJECT.format(country=country, source=source) + " - recovered",
        "body": (f"{source} ({country}) is publishing again. It cleared the "
                 f"freshness check on its own cadence, so nothing needs doing."),
        "resolve_scope": scope,
    }
    try:
        decision, _recorded = alert_state.claim(payload)
    except Exception as exc:                                  # noqa: BLE001
        print(f"::warning::could not clear {scope}: {exc}")
        return False
    if not decision.sends:
        return False
    try:
        ok, _note, _t = sender({"subject": decision.subject,
                                "body": decision.body},
                               idem=decision.idempotency_key())
        return ok
    except Exception as exc:                                  # noqa: BLE001
        print(f"::warning::recovery notice not delivered: {exc}")
        return False


def enabled():
    """Mail only where a relay is configured. Absent is ABSENT, not broken."""
    try:
        import opsmail
        return opsmail.configured()
    except Exception:                                          # noqa: BLE001
        return False


def run_url():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run = os.environ.get("GITHUB_RUN_ID", "")
    return f"https://github.com/{repo}/actions/runs/{run}" if repo and run else ""
