"""One shared GET for URLs that came from OUTSIDE this repository.

Two call sites fetch a URL that a stranger chose: `process_tips` fetches the
link on a public tip, and `enrich_context` re-reads whatever `source_url` a
stored row happens to carry. Both ran on the plain `requests` default, which
follows redirects anywhere and never looks at where it landed. The ingest
runner holds `WP_API_KEY` and `OPENROUTER_API_KEY` in its environment and sits
inside a cloud network, so "fetch this URL for me" is a request to read the
runner's own neighbourhood: `http://169.254.169.254/latest/meta-data/`,
`http://127.0.0.1:8080/`, `http://10.0.0.5/`. Blind SSRF, because the tip
worker does not print the body back, but the LLM pass reads it, the extractor
reads it, and a quoted excerpt can end up on the public page.

The gate in `process_tips` did not help: it ran AFTER the fetch. A domain
allowlist consulted after the bytes are already on the wire is a publishing
gate, not a fetching gate, and this file is the fetching gate.

What is closed here:

* **Scheme.** Only http and https. `file://`, `gopher://`, `ftp://` and the
  rest never reach a socket.
* **Destination address.** Every A/AAAA the host resolves to must be a global
  unicast address. Loopback, RFC1918, link-local (which is where every cloud
  metadata service lives), CGNAT, reserved, multicast and the unspecified
  address are all refused, in v4 and in v6, including the v4-mapped and
  6to4/Teredo spellings that let `::ffff:169.254.169.254` read as "an IPv6
  address" to a naive check.
* **Every hop, not the first.** Redirects are followed by hand with
  `allow_redirects=False`, and the destination is revalidated before each one.
  A public host answering `302 -> http://169.254.169.254/` is the whole attack,
  and it is exactly what a first-hop-only check misses.
* **Body size.** `stream=True` plus a capped raw read, so a hostile or merely
  broken endpoint cannot hand the runner an unbounded body. The cap is on the
  DECOMPRESSED bytes, because that is where a zip bomb lands.
* **Time.** A connect+read timeout on every hop, and a deadline across the
  whole redirect chain so a slow-loris chain cannot outlive it.

What is NOT closed, said plainly rather than left implied: this resolves the
host and then lets `requests` resolve it again to connect, so a name that
answers differently between the two calls (DNS rebinding) is a residual. Fully
closing it means pinning the connection to the address we validated, which
means owning the socket. The exposure here is a tip link and a stored source
URL, and the mitigation is that both fetches are read-only and their output is
gated downstream; if this module ever fronts something that writes, that is the
day to pin the socket.
"""
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlparse, urlunparse

import requests
import urllib3

DEFAULT_UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}

MAX_BYTES = 2_000_000       # decompressed; an article is kilobytes
MAX_REDIRECTS = 5
DEFAULT_TIMEOUT = 30
CHAIN_DEADLINE = 90         # seconds for the whole redirect chain

ALLOWED_SCHEMES = ("http", "https")

# Transient status codes worth one more try. Same set as http_retry, imported
# rather than retyped so the two can never drift into disagreeing about what
# "transient" means.
try:
    from http_retry import TRANSIENT
except ImportError:                                        # pragma: no cover
    from railway.http_retry import TRANSIENT


class BlockedURL(Exception):
    """The URL was refused before any byte was sent. Never a network error."""


def _unwrap(ip):
    """The address an IPv6 wrapper actually points at.

    `::ffff:169.254.169.254` is the metadata service wearing an IPv6 hat, and
    so are the 6to4 (`2002::/16`) and Teredo (`2001::/32`) spellings. Python
    hands these back as ordinary IPv6Address objects whose `is_private` is
    False, so a check that stops at `is_private` waves all three through.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        for inner in (ip.ipv4_mapped, ip.sixtofour, getattr(ip, "teredo", None)):
            if inner is None:
                continue
            # teredo is a (server, client) pair; the client is the payload.
            if isinstance(inner, tuple):
                inner = inner[1]
            return inner
    return ip


def _is_public(ip):
    """True only for a globally routable unicast address.

    Written as an allowlist of one property rather than a denylist of ranges:
    a denylist is a list somebody has to remember to extend, and the ranges
    that matter (100.64/10 CGNAT, 192.0.0.0/24, the v6 unique-local block) are
    exactly the ones a hand-written list forgets.
    """
    ip = _unwrap(ip)
    if ip.is_loopback or ip.is_private or ip.is_link_local:
        return False
    if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return False
    if not ip.is_global:
        return False
    return True


def _resolve(host):
    """Every address the host answers with. Raises BlockedURL if it answers
    with none, because an unresolvable host is not a reason to try anyway."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedURL(f"{host} does not resolve: {exc}") from exc
    addrs = []
    for info in infos:
        try:
            addrs.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addrs:
        raise BlockedURL(f"{host} resolved to nothing usable")
    return addrs


def validate_url(url):
    """Refuse the URL, or return it normalised.

    Raises `BlockedURL` with a reason. Every address the host resolves to must
    be public: a host with one public and one private answer is refused, since
    which one `requests` connects to is not ours to choose.
    """
    parts = urlparse((url or "").strip())
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise BlockedURL(f"scheme {parts.scheme!r} is not http or https")
    host = parts.hostname
    if not host:
        raise BlockedURL("no host in URL")
    # A bare literal is checked directly; getaddrinfo would accept it anyway,
    # but this keeps the error honest about what was refused.
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _is_public(literal):
            raise BlockedURL(f"{host} is not a public address")
        return urlunparse(parts)
    for addr in _resolve(host):
        if not _is_public(addr):
            raise BlockedURL(f"{host} resolves to {addr}, which is not public")
    return urlunparse(parts)


def _read_capped(response, max_bytes):
    """The first `max_bytes` DECOMPRESSED bytes, then close.

    `decode_content=True` matters: gzip and brotli are where a small response
    becomes a large one, and a cap applied to the wire bytes is not a cap.

    FAILURES DURING THE READ ARE RAISED AS `requests.RequestException`, which
    keeps `safe_get`'s documented contract true for the body and not just the
    request: `raw.read` talks to urllib3 directly, and urllib3's own
    exceptions (`ReadTimeoutError`, `ProtocolError`, ...) are NOT
    `requests.RequestException`. Without this translation a host that returns
    200 and then goes silent mid-body sails past every `except
    requests.RequestException` in the callers — including
    `safe_get_with_retry` itself — and kills the whole run. The sibling
    tracker took exactly that bullet on 2026-08-05 (one dead publisher ended
    a 19-minute press slice); requests performs this same mapping inside
    `iter_content`, and this mirrors it.
    """
    try:
        raw = getattr(response, "raw", None)
        if raw is not None and hasattr(raw, "read"):
            try:
                try:
                    return raw.read(max_bytes + 1, decode_content=True)[:max_bytes]
                except TypeError:
                    # A stub or an older urllib3 without decode_content.
                    return raw.read(max_bytes + 1)[:max_bytes]
            except urllib3.exceptions.ReadTimeoutError as exc:
                raise requests.exceptions.ConnectionError(exc) from exc
            except urllib3.exceptions.DecodeError as exc:
                raise requests.exceptions.ContentDecodingError(exc) from exc
            except urllib3.exceptions.ProtocolError as exc:
                raise requests.exceptions.ChunkedEncodingError(exc) from exc
            except urllib3.exceptions.SSLError as exc:
                raise requests.exceptions.SSLError(exc) from exc
            except (urllib3.exceptions.HTTPError, OSError) as exc:
                raise requests.exceptions.ConnectionError(exc) from exc
        return (response.content or b"")[:max_bytes]
    finally:
        try:
            response.close()
        except Exception:
            pass


def safe_get(url, headers=None, timeout=DEFAULT_TIMEOUT, max_bytes=MAX_BYTES,
             session=None, max_redirects=MAX_REDIRECTS):
    """GET an untrusted URL. Returns `(status_code, bytes, final_url)`.

    Raises `BlockedURL` when the URL, or any host in its redirect chain, is not
    a public http/https destination. Transport errors propagate as
    `requests.RequestException` so a caller can tell "refused" from "failed".
    """
    http = session or requests
    current = validate_url(url)
    started = time.monotonic()
    for hop in range(max_redirects + 1):
        if time.monotonic() - started > CHAIN_DEADLINE:
            raise BlockedURL("redirect chain outlived its deadline")
        response = http.get(current, headers=headers or DEFAULT_UA,
                            timeout=timeout, allow_redirects=False,
                            stream=True)
        location = (response.headers or {}).get("Location") if hasattr(response, "headers") else None
        if response.status_code in (301, 302, 303, 307, 308) and location:
            try:
                response.close()
            except Exception:
                pass
            if hop >= max_redirects:
                raise BlockedURL("too many redirects")
            # Relative Locations are legal and common. Resolve against the hop
            # we are actually on, then revalidate: THIS is the check that a
            # first-hop-only guard skips.
            # urllib's urljoin, not requests.compat.urljoin: a test elsewhere
            # in this suite stubs `requests` into sys.modules, and a stub has
            # no .compat. A security check must not depend on which test ran
            # first.
            nxt = urljoin(current, location)
            current = validate_url(nxt)
            continue
        body = _read_capped(response, max_bytes)
        return response.status_code, body, current
    raise BlockedURL("too many redirects")


def safe_get_text(url, headers=None, timeout=DEFAULT_TIMEOUT,
                  max_bytes=MAX_BYTES, session=None, encoding=None):
    """`safe_get` decoded to str. Returns `(status_code, text, final_url)`."""
    status, body, final = safe_get(url, headers=headers, timeout=timeout,
                                   max_bytes=max_bytes, session=session)
    return status, body.decode(encoding or "utf-8", errors="replace"), final


def safe_get_with_retry(url, headers=None, timeout=DEFAULT_TIMEOUT,
                        max_bytes=MAX_BYTES, attempts=3, backoff=5,
                        session=None, sleep=time.sleep):
    """`safe_get` with `http_retry`'s transient-5xx behaviour.

    Returns `(status, bytes, final_url)`, or None when every attempt failed
    transiently, the same "you decide" contract `get_with_retry` has. A
    `BlockedURL` is NEVER retried: a refusal is an answer, and retrying it just
    spends the run's deadline on a URL that is still refused.
    """
    for attempt in range(attempts):
        try:
            status, body, final = safe_get(url, headers=headers, timeout=timeout,
                                           max_bytes=max_bytes, session=session)
            if status not in TRANSIENT:
                return status, body, final
        except BlockedURL:
            raise
        except requests.RequestException:
            pass
        if attempt < attempts - 1:
            sleep(backoff * (attempt + 1))
    return None
