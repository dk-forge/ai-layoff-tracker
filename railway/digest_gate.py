"""Pre-send quality gate for the subscriber digests.

`digest_send` used to prove one thing before it sent: that the SMTP
credential logs in. Nothing looked at the message. The 2026-11-15 email audit
found a monthly edition that Gmail clipped and an archive link that 404ed,
both invisible to every check in the run.

This gate reads the RENDERED messages (the exact bytes `build_message` made)
and refuses the whole run, before the first real recipient, on any of:

  * html larger than MAX_HTML_BYTES (Gmail clips at ~102 KB; 100 KB leaves
    room for the tracking pixel the relay appends),
  * no text/plain part,
  * no List-Unsubscribe or no List-Unsubscribe-Post header,
  * an <img> with no alt attribute (a tracking pixel carries alt="" on
    purpose; an absent attribute is the defect),
  * a link that answers 4xx, redirects are NOT followed and are fine.

A known bot-blocker answering 403/429/999 is a WARNING, as is a link we could
not reach at all: "could not tell" is never a pass and never a fault.
Per-reader links (unsubscribe, preferences) are never requested: a GET on an
unsubscribe URL would unsubscribe the reader.

The link check touches the network, so it is opt in (DIGEST_GATE_LINKS=1, set
by digest-send.yml). The structural checks are pure and always run.
"""
from __future__ import annotations

import html as _html
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MAX_HTML_BYTES = 100 * 1024
MAX_LINKS = 150
LINK_TIMEOUT = 8
WORKERS = 8
UA = "Mozilla/5.0 (compatible; AiLayoffTracker/1.0; +https://asktherecruiter.com)"
# Status codes a bot wall answers with. Warn only.
BLOCKER_CODES = {403, 429, 999}

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_ALT = re.compile(r"\balt\s*=", re.I)
_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)


def _links(html: str, skip: set) -> list:
    seen, out = set(), []
    for raw in _HREF.findall(html):
        url = _html.unescape(raw).strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        if url in skip or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def structural(message) -> list:
    """Failures for one rendered Message. Pure; no network."""
    fails = []
    size = len((message.html or "").encode("utf-8"))
    if size > MAX_HTML_BYTES:
        fails.append(f"html is {size} bytes, over the {MAX_HTML_BYTES} limit")
    if not (message.text or "").strip():
        fails.append("no text/plain part")
    headers = {k.lower(): v for k, v in (message.headers or {}).items()}
    for name in ("list-unsubscribe", "list-unsubscribe-post"):
        if not str(headers.get(name) or "").strip():
            fails.append(f"missing {name} header")
    bad = [t for t in _IMG.findall(message.html or "") if not _ALT.search(t)]
    if bad:
        fails.append(f"{len(bad)} <img> without an alt attribute")
    return fails


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # a 3xx is an answer, not a hop
        return None


def _status(url: str) -> int | None:
    """HTTP status, redirects not followed; None when unreachable."""
    opener = urllib.request.build_opener(_NoRedirect)
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with opener.open(req, timeout=LINK_TIMEOUT) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue  # some hosts refuse HEAD only; ask once with GET
            return exc.code
        except (urllib.error.URLError, socket.timeout, OSError, ValueError):
            return None
    return None


def check_links(urls, status=_status) -> tuple:
    """(failures, warnings) over unique urls. `status` is injectable."""
    urls = list(urls)[:MAX_LINKS]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        codes = list(pool.map(status, urls))
    fails, warns = [], []
    for url, code in zip(urls, codes):
        host = urllib.parse.urlsplit(url).netloc
        if code is None:
            warns.append(f"{host}: could not be reached (UNKNOWN)")
        elif code in BLOCKER_CODES:
            warns.append(f"{host}: {code} (bot blocker, not counted)")
        elif 400 <= code < 500:
            fails.append(f"{url}: {code}")
    return fails, warns


def run_gate(messages, check_network=False, status=_status) -> dict:
    """Judge the sample messages. {'ok', 'failures', 'warnings', 'checked'}."""
    failures, warnings, links = [], [], []
    skip = set()
    for i, m in enumerate(messages, 1):
        for f in structural(m):
            failures.append(f"message {i}: {f}")
        # Reader-specific links named by the headers are never requested.
        for v in (m.headers or {}).values():
            skip.update(re.findall(r"<(https?://[^>]+)>", str(v)))
        for u in _links(m.html or "", skip):
            if u not in links:
                links.append(u)
    # Any link carrying the reader's own token is theirs alone.
    links = [u for u in links if not re.search(r"[?&](token|t|unsub|key)=", u, re.I)
             and "unsubscribe" not in u.lower() and "preferences" not in u.lower()
             and "/manage" not in u.lower()]
    if check_network:
        f, w = check_links(links, status)
        failures += f
        warnings += w
    return {"ok": not failures, "failures": failures, "warnings": warnings,
            "checked": {"messages": len(messages),
                        "links": len(links) if check_network else 0,
                        "html_bytes": [len((m.html or "").encode("utf-8"))
                                       for m in messages]}}
