"""One shared retry for reads against the shared WordPress host.

The host answers 5xx intermittently on deep-offset pages, especially while a
large WARN import is loading it. Every long scan hits this eventually, and the
default `raise_for_status()` turns one blip into a dead run: the industry
backfill died at page 76 of 140 every morning for days, having classified
nothing, and the legacy-row repair reproduced the identical failure within
hours of that fix because the retry lived in one file instead of a shared one.

Hence this module. A scan that wants to survive a blip imports `get_with_retry`
rather than re-deriving it and drifting.

`call_with_retry` (and its `post_with_retry` shorthand) is the write-side
sibling, added 2026-08-11 for the workflows that POST to the same host. It is
here rather than in its own file for exactly the reason above: the transient set
and the "a settled refusal is not retried" rule must have ONE definition, or the
next scan re-derives them and they drift apart.

Two transports on purpose. `get_with_retry` keeps `requests`, which its callers
already install. `call_with_retry` is STDLIB ONLY (urllib) because it runs in
workflows that do no `pip install` at all — the same reasoning as `ci_alert.py`:
the code whose job is to behave well when things are broken must not be
breakable by dependency resolution. `requests` is therefore an OPTIONAL import,
so this module loads on a runner that has no third-party packages.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

try:  # optional: only `get_with_retry` needs it. See the module docstring.
    import requests
except ImportError:  # pragma: no cover - exercised on the stdlib-only runners
    requests = None

# Transient: worth retrying. Anything else (401/403/404) is a real answer the
# caller must handle, and retrying it just wastes the run's deadline.
TRANSIENT = {408, 429, 500, 502, 503, 504, 520, 521, 522, 524}
DEFAULT_UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}


def get_with_retry(url, params=None, headers=None, attempts=3, timeout=60, backoff=5):
    """GET that survives transient 5xx.

    Returns the response, or None when every attempt failed transiently, so the
    caller can decide between "continue with what I have" and "this is a real
    outage". Never raises on transport errors.
    """
    if requests is None:  # pragma: no cover - a caller mistake, not a host fault
        raise RuntimeError("get_with_retry needs `requests`; the stdlib-only "
                           "path is call_with_retry/post_with_retry")

    for attempt in range(attempts):
        try:
            r = requests.get(url, params=params, headers=headers or DEFAULT_UA,
                             timeout=timeout)
            if r.status_code not in TRANSIENT:
                return r
            if attempt < attempts - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            return None
        except requests.RequestException:
            if attempt < attempts - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            return None
    return None


# --------------------------------------------------------------------------
# The write side: three outcomes, never two.
# --------------------------------------------------------------------------

#: The host answered and gave us what we asked for.
OK = "ok"
#: The host could not be reached AT ALL — a transport error, or a transient
#: status that survived every retry. This is NOT a pass and NOT a failure; it is
#: "we did not get to ask". The caller records it and tries again next tick.
DEFERRED = "deferred"
#: The host gave us a real answer we do not accept: a wrong key, a missing
#: route, any non-transient status. Loud, every time. `--fail-with-body` existed
#: so that a refusal could never be mistaken for a success, and that stays true.
FAILURE = "failure"

#: Seconds between in-run retries. Copied in spirit from ci_alert.py: three
#: attempts over ~15s catches the single bad response and the brief wobble,
#: which is most of what this host produces. It deliberately does NOT try to
#: outlast an outage — a ten-minute job cannot, and outlasting is what the
#: deferral ledger and tomorrow's scheduled run are for.
DEFAULT_BACKOFF = (3, 12)


class Unreachable(Exception):
    """The request never got an HTTP answer (DNS, TCP, TLS, timeout)."""


class HostCall:
    """(outcome, status, body, detail) — with `outcome` one of OK/DEFERRED/FAILURE."""

    __slots__ = ("outcome", "status", "body", "detail")

    def __init__(self, outcome, status=None, body="", detail=""):
        self.outcome = outcome
        self.status = status
        self.body = body
        self.detail = detail

    def __repr__(self):  # pragma: no cover - diagnostics only
        return f"HostCall({self.outcome}, status={self.status}, detail={self.detail!r})"


def _send(method, url, data=None, headers=None, timeout=90):
    """One request. Returns (status, body_text); raises Unreachable otherwise.

    The single seam the tests replace, so the three outcomes can be exercised
    without a network and without a live outage to wait for.
    """
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = ""
        if exc.fp:
            try:
                body = exc.read().decode("utf-8", "replace")
            except OSError:
                body = ""
        return exc.code, body
    except urllib.error.URLError as exc:
        raise Unreachable(str(exc.reason)) from exc
    except (OSError, ValueError) as exc:
        raise Unreachable(str(exc)) from exc


def call_with_retry(url, *, method="POST", data=None, headers=None, timeout=90,
                    backoff=DEFAULT_BACKOFF, sleep=None):
    """One host call, resolved to OK / DEFERRED / FAILURE.

    Transient statuses and transport errors are retried across `backoff`; a
    non-transient status is returned immediately, because retrying a settled
    "no" only makes the run longer and the answer is the same.
    """
    # Resolved at CALL time, not as a default argument, so a test can stub
    # `time.sleep` on this module rather than wait out fifteen real seconds
    # per case — the same reason historical_news_sweep does it.
    sleep = sleep or (lambda seconds: time.sleep(seconds))
    sent_headers = dict(DEFAULT_UA)
    sent_headers.update(headers or {})

    detail = "no attempt was made"
    for delay in (None,) + tuple(backoff):
        if delay is not None:
            print(f"  {url} did not answer ({detail}): retrying in {delay}s")
            sleep(delay)
        try:
            status, body = _send(method, url, data=data, headers=sent_headers,
                                 timeout=timeout)
        except Unreachable as exc:
            detail = f"could not reach the host: {exc}"
            continue
        if status in TRANSIENT:
            detail = f"HTTP {status} from the host: {body.strip()[:200]}"
            continue
        if 200 <= status < 400:
            return HostCall(OK, status, body)
        return HostCall(FAILURE, status, body,
                        f"HTTP {status}: {body.strip()[:300]}")
    return HostCall(DEFERRED, None, "", detail)


def post_with_retry(url, *, data=None, headers=None, **kw):
    """POST sibling of `get_with_retry`, resolved to three outcomes."""
    return call_with_retry(url, method="POST", data=data, headers=headers, **kw)


def body_reports_failure(body):
    """Return a reason string when a 2xx body reports its own failure, else "".

    A deferral path that swallowed these would be the softening this change is
    explicitly not allowed to do: data-changing jobs fail loudly on a failed
    batch, and the host answering "I could not do it" is an answer.
    """
    try:
        doc = json.loads(body or "")
    except ValueError:
        return ""
    if not isinstance(doc, dict):
        return ""
    if doc.get("ok") is False or doc.get("success") is False:
        return f"the host reported the work failed: {str(doc)[:200]}"
    for key in ("error", "errors", "failures"):
        value = doc.get(key)
        if value:
            return f"the host reported {key}={str(value)[:200]}"
    for key in ("failed", "failed_count", "errors_count"):
        value = doc.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return f"the host reported {key}={value}"
    return ""


def urlencode_form(pairs):
    """Body + header for a form POST, the `curl --data-urlencode` equivalent."""
    return (urllib.parse.urlencode(list(pairs)).encode("utf-8"),
            {"Content-Type": "application/x-www-form-urlencoded"})


def json_body(payload):
    """Body + header for a JSON POST, the `requests(json=...)` equivalent.

    Here rather than in each caller for the same reason as everything above it:
    the Python workers POST JSON, and each one encoding its own body is how the
    Content-Type quietly drifts off one of them.
    """
    return (json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"})
