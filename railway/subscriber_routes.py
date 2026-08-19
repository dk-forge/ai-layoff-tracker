"""THE TWO LINKS INSIDE AN EMAIL, PROBED ON THE LIVE SITE.

WHY THIS FILE EXISTS.

Two subscriber-facing paths turned up in the live 404 log on 2026-08-19:

    /blog/ai-layoff-tracker/confirm/<token>
    /blog/ai-layoff-tracker/unsubscribe/<token>

Those are the only two links a reader is ever given. The first one IS the
funnel, because nobody is sent a digest until it is clicked. The second one is
promised to Gmail and Yahoo in the `List-Unsubscribe-Post` header of every
message, and they POST it with no human present.

Nothing in this product could have told anybody. The send reports success, the
relay credential verifies, the health row stays green, and a confirmation
nobody completes reads as `0 sent of 0 eligible`, which is true and says
nothing. A dead unsubscribe is worse still: mail people cannot stop receiving
is what produces spam complaints instead of unsubscribes, and complaint rate is
what ends a sending domain.

So the routes are probed the way a reader and a provider actually reach them,
from outside, over the network, against the deployed site.

WHAT IS ASSERTED, AND WHY EACH ONE IS HERE.

  * both public paths ANSWER. A 404 here is the whole defect and is a FAIL.
  * the RFC 8058 one-click POST returns 200. A provider wants a 2xx and
    nothing else, and a 302 to a web page can be recorded as a failed
    unsubscribe against the sending domain.
  * a GET on the unsubscribe path does NOT act. Brevo rewrites every link at
    the relay and corporate scanners follow them, which is how a live defect
    once produced confirmed and unsubscribed a minute apart. A GET must ask.
  * the pre-2.20.77 admin-post shapes still answer. Those URLs are sitting in
    real inboxes and in the headers of every digest already delivered.

THE PROBE TOKEN BELONGS TO NOBODY, BY CONSTRUCTION.

Real tokens are `bin2hex(random_bytes(32))`, so 64 lowercase hex characters.
The probe token is 64 characters that include letters outside the hex alphabet,
so it cannot be equal to any token this product has ever minted. The POST
therefore reaches the handler, exercises the machine path and writes no row.
A fresh one is drawn per run so that no shared cache in front of the site can
answer a later probe from an earlier verdict.

PASS / FAIL / UNKNOWN ARE THREE STATES. A probe that could not be made is
UNKNOWN, never a pass. Absence of a signal is not a pass (CLAUDE.md).

NOTHING IDENTIFYING IS READ, SENT OR PRINTED. The probe token is ours, no
address is involved, no key is needed, and no response body is echoed.

Stdlib only, no keys, safe to run from anywhere.
"""
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import namedtuple

SITE = "https://asktherecruiter.com/blog"

# ModSecurity on this host blocks `python-requests` and the urllib default.
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

TIMEOUT_S = 25

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

# 64 characters, drawn from an alphabet that is deliberately NOT hex. A minted
# token is 64 hex characters, so no draw from this alphabet can ever equal one.
_PROBE_ALPHABET = "ghijklmnopqrstuvwxyz"

Probe = namedtuple("Probe", "label verdict detail")


class Result:
    """A verdict that can say it does not know.

    `ok` is true only for PASS, so `if result.ok` can never be satisfied by a
    probe that never reached the host.
    """

    def __init__(self, verdict, detail, probes=None):
        self.verdict = verdict
        self.detail = detail
        self.probes = list(probes or ())

    @property
    def ok(self):
        return self.verdict == PASS

    def __repr__(self):
        return f"<Result {self.verdict}: {self.detail}>"


def probe_token():
    """A 64 character token that cannot be any subscriber's."""
    return "".join(secrets.choice(_PROBE_ALPHABET) for _ in range(64))


def public_url(verb, token, site=SITE):
    """The URL the plugin's own builder mints, written once here.

    Kept deliberately literal rather than derived. This module is the outside
    view, and a probe that computed the path the same way the site does would
    agree with the site about a path neither of them serves.
    """
    return f"{site}/ai-layoff-tracker/{verb}/{urllib.parse.quote(token)}/"


def legacy_url(action, token, site=SITE):
    """The pre-2.20.77 shape, still sitting in delivered mail."""
    query = urllib.parse.urlencode({"action": action, "t": token})
    return f"{site}/wp-admin/admin-post.php?{query}"


def _request(url, method="GET", data=None, timeout=TIMEOUT_S):
    """Status, final URL and body, WITHOUT following redirects.

    Redirects are not followed on purpose. A 302 to the tracker page is the
    correct answer for a token that matches no row, and following it would
    turn every answer into the same 200 and tell us nothing.
    """
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", UA)
    if body:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Location", ""), resp.read(4096)
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.headers.get("Location", ""), exc.read(4096)


def _acted(status, body):
    """Did this response actually stop the emails?

    The handler answers a completed one-click POST with a bare 200 whose body
    is the single word below. Anything else did not write.
    """
    return status == 200 and b"Unsubscribed." in (body or b"")


def check(site=SITE, token=None):
    """Probe every shape a reader or a provider can arrive on."""
    token = token or probe_token()
    probes = []
    unreachable = []

    def run(label, url, method="GET", data=None):
        """The response, or None when the host could not be reached at all."""
        try:
            return _request(url, method=method, data=data)
        except Exception as exc:                       # noqa: BLE001
            unreachable.append(label)
            probes.append(Probe(label, UNKNOWN, f"not reached: {exc}"))
            return None

    # 1 and 2. Both public paths must answer. A 404 is the defect this file
    # exists to catch, and no handler in subscribe.php emits one: an unknown,
    # expired or already used token redirects. So a 404 here means the route
    # did not resolve, not that the token was rejected.
    for verb in ("confirm", "unsubscribe"):
        label = f"GET /ai-layoff-tracker/{verb}/"
        got = run(label, public_url(verb, token, site))
        if got is None:
            continue
        status, location, body = got
        if status == 404:
            probes.append(Probe(label, FAIL,
                                "404: the route did not resolve. Readers clicking this "
                                "link in an email reach a dead page."))
        elif status == 503:
            probes.append(Probe(label, UNKNOWN,
                                "HTTP 503: site is in its deploy maintenance window."))
        elif status >= 400:
            probes.append(Probe(label, FAIL, f"HTTP {status}: the route did not answer."))
        else:
            probes.append(Probe(label, PASS, f"HTTP {status} (answered)"))

        # A GET must never be the thing that stops the emails. Scanners follow
        # these links with nobody present.
        if verb == "unsubscribe" and _acted(status, body):
            probes.append(Probe("GET does not act", FAIL,
                                "a GET on the unsubscribe path completed the unsubscribe. "
                                "Link scanners follow these with no human present."))
        elif verb == "unsubscribe":
            probes.append(Probe("GET does not act", PASS, "a GET asks, it does not write"))

    # 3. The RFC 8058 one-click POST. This is the compliance one: the header
    # promises a working POST endpoint to the two providers that require it.
    label = "POST /ai-layoff-tracker/unsubscribe/ (RFC 8058 one-click)"
    got = run(label, public_url("unsubscribe", token, site),
              method="POST", data={"List-Unsubscribe": "One-Click"})
    if got is not None:
        status, location, body = got
        if status == 200:
            probes.append(Probe(label, PASS, "HTTP 200, as RFC 8058 requires"))
        elif status == 404:
            probes.append(Probe(label, FAIL,
                                "404: the one-click endpoint promised in every "
                                "List-Unsubscribe-Post header is dead."))
        elif status == 503:
            probes.append(Probe(label, UNKNOWN,
                                "HTTP 503: site is in its deploy maintenance window."))
        else:
            probes.append(Probe(label, FAIL,
                                f"HTTP {status}: a provider needs a bare 2xx here and may "
                                "record anything else as a failed unsubscribe."))

    # 4. The old shapes. These are in inboxes and in the headers of every
    # digest already delivered, so they outrank the pretty ones.
    for action in ("alt_digest_confirm", "alt_digest_unsub"):
        label = f"GET admin-post.php?action={action} (pre-2.20.77 links)"
        got = run(label, legacy_url(action, token, site))
        if got is None:
            continue
        status, location, body = got
        if status == 503:
            probes.append(Probe(label, UNKNOWN,
                                "HTTP 503: site is in its deploy maintenance window."))
        elif status >= 400:
            probes.append(Probe(label, FAIL,
                                f"HTTP {status}: a link already sent to a real address "
                                "no longer works."))
        else:
            probes.append(Probe(label, PASS, f"HTTP {status} (answered)"))

    failed = [p for p in probes if p.verdict == FAIL]
    if failed:
        return Result(FAIL,
                      "; ".join(f"{p.label}: {p.detail}" for p in failed),
                      probes)
    # 503 (deploy maintenance window) is UNKNOWN, never FAIL, matching every
    # other live check against this host (data_integrity.py, published_figures.py,
    # ci_alert.py): the site answered, but with the status it deliberately
    # returns while an FTPS deploy is landing, not with a broken route.
    unknown = [p for p in probes if p.verdict == UNKNOWN and p.label not in unreachable]
    if unreachable or unknown:
        parts = []
        if unreachable:
            parts.append("could not reach " + ", ".join(sorted(set(unreachable))))
        parts.extend(f"{p.label}: {p.detail}" for p in unknown)
        return Result(UNKNOWN, "; ".join(parts) + ". This is NOT a pass.", probes)
    return Result(PASS,
                  f"{len(probes)} probe(s) answered: both public routes resolve, the "
                  "one-click POST returns 200, a GET does not act, and the pre-2.20.77 "
                  "links still work.",
                  probes)


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    site = argv[0] if argv else SITE
    result = check(site=site)
    print("SUBSCRIBER ROUTES  (confirm + unsubscribe, probed from outside)")
    for probe in result.probes:
        print(f"    {probe.verdict:<7} {probe.label}: {probe.detail}")
    print(f"    verdict: {result.verdict}")
    if result.verdict == FAIL:
        print("    -> docs/RUNBOOK.md 'a subscriber route is 404ing'.")
        return 2
    return 0 if result.ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
