"""Ask a public JSON endpoint a question and answer it in a sentence.

WHY THIS FILE EXISTS.

The deploy workflow verified the live API with one pipeline:

    curl --fail --silent ... | python3 -c 'import json, sys;
        payload = json.load(sys.stdin);
        assert "canonical_events" in payload; print("verified")'

That line has two independent ways of telling an operator nothing at all, and
the owner was emailed by both of them.

  * an empty or non-JSON body raises
    `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`,
    which names no URL, no HTTP status, no content type and no body. It says
    only that something that was supposed to be JSON was not.
  * a body that parses but is the wrong shape raises a bare `AssertionError`
    with no message at all.

The alert body is what survives the run's log retention, so those two strings
are the whole of what a human reads at 3am. Neither is actionable.

Worse, `curl --fail` swallows the body of any error response, so the one piece
of evidence that would have identified the answer (an HTML error page, a
Cloudflare interstitial, a WordPress fatal) was discarded before Python ever
saw it. The status and the body have to be captured SEPARATELY, and both have
to be reported.

PASS / FAIL / UNKNOWN ARE THREE STATES.

An endpoint that answers with the wrong content is a FAIL: it was asked, it
replied, the reply is wrong. An endpoint that could not be reached at all, or
that answered through Cloudflare's 52x family (which the edge mints itself
when it could not get an answer out of the origin), was never asked, so
nothing here is a verdict about it. That is UNKNOWN, and UNKNOWN is neither a
pass nor a fault. Absence of a signal is not a pass (CLAUDE.md). The same
three-state shape, and the same exit codes, as `reader_freshness.py` and
`subscriber_routes.py`: 0 PASS, 2 FAIL, 3 UNKNOWN.

WHAT IS PRINTED, AND WHY IT IS SAFE.

The HTTP status, the content type and the first `--max-excerpt` characters of
the body. These endpoints are public and unauthenticated, so their bodies
carry nothing private, and the excerpt is truncated anyway. No header is
echoed, no request carries a credential, and nothing in this module reads an
environment secret. Control characters are collapsed so a body cannot smuggle
an ANSI escape or a `::error::` line of its own into the run log.

Stdlib only, no keys, safe to run from anywhere.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

# ModSecurity on this host blocks `python-requests` and the urllib default.
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

TIMEOUT_S = 30
MAX_EXCERPT = 200

# Cloudflare mints these itself when it could not get an answer out of the
# origin: 520 unknown, 521 refused, 522 timed out, 523 unreachable, 524 timed
# out after connecting. The request never reached WordPress, so the reply says
# nothing about the endpoint. Same reasoning, same list, as subscriber_routes.
_EDGE_TO_ORIGIN = {520, 521, 522, 523, 524}

# 503 during a deploy is this workflow's OWN maintenance window: the mirror
# drops WordPress's `.maintenance` file before it uploads, deliberately, so
# that a mid-upload visitor gets a 503 with Retry-After instead of a fatal.
# Reading our own maintenance flag as a broken endpoint would be a checker
# reporting the thing it was designed to cause.
_TRANSIENT = {429, 500, 502, 503, 504} | _EDGE_TO_ORIGIN

# A gateway saying its upstream did not answer is the 52x fact one hop closer
# to us: Bluehost served 504s under /blog twice on 2026-07-31 with the site
# itself fine. 429 is the host declining to be asked. Neither is a reply from
# the endpoint. A 500 is deliberately NOT here: that is PHP answering, and a
# fatal in a plugin we just uploaded is exactly the fault this step is for.
_NO_ANSWER = {
    429: "the host declined to answer (rate limited), so the endpoint was never asked",
    502: "a gateway in front of the site could not get an answer out of it",
    504: "a gateway in front of the site timed out waiting for it",
}

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class Result:
    """A verdict that can say it does not know.

    `ok` is true only for PASS, so `if result.ok` can never be satisfied by a
    request that never reached the host.
    """

    def __init__(self, verdict, detail, status=None, content_type=None, excerpt=None):
        self.verdict = verdict
        self.detail = detail
        self.status = status
        self.content_type = content_type
        self.excerpt = excerpt

    @property
    def ok(self):
        return self.verdict == PASS

    def __repr__(self):
        return f"<Result {self.verdict}: {self.detail}>"


def excerpt(body, limit=MAX_EXCERPT):
    """The first `limit` characters of a body, safe to put in a log line.

    Bytes rather than characters is the wrong unit for a human, and an
    undecodable byte is not a reason to lose the whole excerpt, so the body is
    decoded with replacement. Whitespace runs collapse because an HTML error
    page is mostly newlines and a one-line log entry is what gets emailed.
    """
    if body is None:
        return ""
    if isinstance(body, bytes):
        text = body.decode("utf-8", "replace")
    else:
        text = body
    text = _CONTROL.sub(" ", text)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit] + f"... [truncated at {limit} characters]"
    return text


def fetch(url, timeout=TIMEOUT_S, cookie=""):
    """Status, content type and body, captured SEPARATELY.

    An HTTP error is not an exception here: its status and its body are the
    evidence. Only a request that produced no response at all raises.
    """
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json")
    if cookie:
        # The host runs a bot challenge in front of /blog; the deploy's own
        # curl carried this cookie, so this carries it too. It is a public
        # challenge marker, not a credential, and it is never printed.
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read(65536)
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.headers.get("Content-Type", ""), exc.read(65536)


def judge(status, content_type, body, require=(), url="", require_type=True):
    """Turn one captured response into one of the three verdicts.

    Deliberately pure: it takes a response rather than making one, so every
    branch below is reachable from a unit test without a network.
    """
    where = f" from {url}" if url else ""
    ctype = (content_type or "").split(";")[0].strip() or "no content type"
    head = excerpt(body)

    if status in _EDGE_TO_ORIGIN:
        return Result(UNKNOWN,
                      f"HTTP {status}{where}: Cloudflare could not get an answer out of "
                      "the origin, so no request reached the endpoint. This is NOT a "
                      "verdict on the endpoint.",
                      status=status, content_type=ctype, excerpt=head)

    if status == 503:
        return Result(UNKNOWN,
                      f"HTTP 503{where}: the site reports itself briefly unavailable "
                      "(this deploy drops WordPress's .maintenance flag during the "
                      "upload). Nothing was asked of the endpoint. This is NOT a "
                      "verdict on the endpoint.",
                      status=status, content_type=ctype, excerpt=head)

    if status in _NO_ANSWER:
        return Result(UNKNOWN,
                      f"HTTP {status}{where}: {_NO_ANSWER[status]}. This is NOT a "
                      "verdict on the endpoint.",
                      status=status, content_type=ctype, excerpt=head)

    if status != 200:
        return Result(FAIL,
                      f"HTTP {status}{where}, expected 200. Content-Type was {ctype}. "
                      f"First {MAX_EXCERPT} characters of the body: {head or '(empty)'}",
                      status=status, content_type=ctype, excerpt=head)

    if not (body or b"").strip():
        return Result(FAIL,
                      f"HTTP 200{where} with an EMPTY body, expected JSON. "
                      f"Content-Type was {ctype}. An empty 200 is usually a PHP fatal "
                      "swallowed by output buffering, or a cache storing a failed "
                      "render.",
                      status=status, content_type=ctype, excerpt="")

    try:
        payload = json.loads(body)
    except (ValueError, TypeError) as exc:
        return Result(FAIL,
                      f"HTTP 200{where} but the body is not JSON ({exc}). "
                      f"Content-Type was {ctype}. First {MAX_EXCERPT} characters of the "
                      f"body: {head}",
                      status=status, content_type=ctype, excerpt=head)

    if require_type and not isinstance(payload, dict):
        return Result(FAIL,
                      f"HTTP 200{where} returned valid JSON of type "
                      f"{type(payload).__name__}, expected a JSON object. "
                      f"First {MAX_EXCERPT} characters of the body: {head}",
                      status=status, content_type=ctype, excerpt=head)

    missing = [key for key in require if key not in payload]
    if missing:
        found = ", ".join(sorted(payload)[:12]) or "(no keys at all)"
        return Result(FAIL,
                      f"HTTP 200{where} returned a JSON object that is MISSING "
                      f"{', '.join(missing)}. Keys present: {found}. "
                      f"First {MAX_EXCERPT} characters of the body: {head}",
                      status=status, content_type=ctype, excerpt=head)

    wanted = ", ".join(require) if require else "valid JSON"
    return Result(PASS,
                  f"HTTP 200{where} returned a JSON object carrying {wanted}.",
                  status=status, content_type=ctype, excerpt=head)


def check(url, require=(), attempts=4, retry_delay=5.0, timeout=TIMEOUT_S,
          cookie="", sleep=time.sleep, fetcher=fetch):
    """Fetch and judge, retrying only what a retry can change.

    A 200 carrying the wrong body will carry the same wrong body again, so it
    is answered at once. A transport error, a 429 or a 5xx can differ on the
    next attempt, which is what the workflow's old `curl --retry-all-errors`
    was buying, and it is kept.
    """
    last = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            status, ctype, body = fetcher(url, timeout=timeout, cookie=cookie)
        except Exception as exc:                       # noqa: BLE001
            last = Result(UNKNOWN,
                          f"could not reach {url}: {exc.__class__.__name__}: {exc}. "
                          "No request was answered, so nothing here is a verdict on "
                          "the endpoint.")
            status = None
        else:
            last = judge(status, ctype, body, require=require, url=url)
            if last.verdict != UNKNOWN and status not in _TRANSIENT:
                return last
        if attempt < max(1, attempts) and (status is None or status in _TRANSIENT):
            sleep(retry_delay)
            continue
        return last
    return last


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--require", action="append", default=[], metavar="KEY",
                        help="a top-level JSON key the answer must carry")
    parser.add_argument("--label", default="", help="what this endpoint is, for humans")
    parser.add_argument("--where", default="",
                        help="where a human should look when this fails")
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--retry-delay", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=TIMEOUT_S)
    parser.add_argument("--cookie", default="",
                        help="a Cookie header value (the host's public bot-challenge marker)")
    args = parser.parse_args(argv)

    result = check(args.url, require=args.require, attempts=args.attempts,
                   retry_delay=args.retry_delay, timeout=args.timeout,
                   cookie=args.cookie)
    label = f"{args.label}: " if args.label else ""
    print(f"{result.verdict}: {label}{result.detail}")
    if not result.ok and args.where:
        print(f"Where to look: {args.where}")
    return {PASS: 0, FAIL: 2}.get(result.verdict, 3)


if __name__ == "__main__":
    sys.exit(main())
