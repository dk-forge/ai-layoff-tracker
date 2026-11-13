"""UTM tags on every link to our own site inside a digest email.

WHY THIS EXISTS (owner goal, 2026-11-13: "every link works and carries UTM
tags"). An audit of the sent editions found exactly ONE tagged link per email,
the footer's "asktherecruiter.com" line. The methodology link, the edition
page, the filtered tracker view, the contact page and the sister tracker all
arrived untagged, so a reader who clicked through from an email was counted as
direct traffic and no report could say which edition earned the visit.

WHAT IS TAGGED. A link whose host is our own (the unsubscribe URL's host and
its www sibling, the same reference digest_send._same_site trusts). Each gets

    utm_source=ai-layoff-tracker  utm_medium=email  utm_campaign=digest-<tier>

appended to its existing query, before any #fragment, with the existing query
left byte for byte as it was.

WHAT IS NEVER TAGGED, on purpose:
  - the reader's own unsubscribe, preferences and confirm links (by path,
    whatever shape the site gives them), any URL with a token-style query key,
    and anything under /wp-json/ or admin-post.php. These carry tokens or are API routes;
    a parameter added to a token URL buys no analytics and risks the one link
    that must always work. The /click redirect adds the tags at the far end
    instead (alt_digest_utm_url in subscribe.php), so tracked links still
    land tagged.
  - a link that already carries any utm_ parameter. Its author chose them.
  - another site's link. UTM parameters measure OUR traffic; on a news
    outlet's article they measure nothing for us and can break a signed URL.
"""
from __future__ import annotations

import html as _html
import re
import urllib.parse

UTM_SOURCE = "ai-layoff-tracker"
UTM_MEDIUM = "email"
TIERS = ("daily", "weekly", "monthly")

# Path fragments that mark a link as a token, a route or an action, never a
# page a reader reads. Matched case-insensitively against the path.
NEVER_TAG = ("/wp-json/", "unsub", "confirm", "preferences", "admin-post.php")
# Query keys that carry a reader's token or identity. A URL holding one is a
# private link whatever its path says (the archive sanitizer's
# _PRIVATE_HREF reads the same shape as private).
TOKEN_KEYS = frozenset({"t", "token", "sig", "signature", "key", "email", "e",
                        "uid", "rid"})

_HREF = re.compile(r'(href\s*=\s*)(["\'])(.*?)\2', re.I | re.S)
_TEXT_URL = re.compile(r'https?://[^\s<>"\'\)\]]+')


def campaign(freq: str) -> str:
    f = str(freq or "").strip().lower()
    return f"digest-{f}" if f in TIERS else "digest"


def own_hosts(reference_url: str) -> frozenset:
    """Our host and its www sibling, read from a URL we already trust."""
    host = (urllib.parse.urlsplit(reference_url or "").hostname or "").lower()
    if not host:
        return frozenset()
    sib = host[4:] if host.startswith("www.") else "www." + host
    return frozenset({host, sib})


def tag_url(url: str, freq: str, hosts) -> str:
    """`url` with our UTM parameters, or `url` unchanged when it is not ours to
    tag. Never raises: a link we cannot parse is printed as it came."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    if parts.scheme not in ("http", "https") or parts.username or parts.password:
        return url
    if (parts.hostname or "").lower() not in hosts:
        return url
    path = parts.path.lower()
    if any(p in path for p in NEVER_TAG):
        return url
    keys = [k.lower() for k, _ in
            urllib.parse.parse_qsl(parts.query, keep_blank_values=True)]
    if any(k.startswith("utm_") or k in TOKEN_KEYS for k in keys):
        return url
    utm = urllib.parse.urlencode((("utm_source", UTM_SOURCE),
                                  ("utm_medium", UTM_MEDIUM),
                                  ("utm_campaign", campaign(freq))))
    query = f"{parts.query}&{utm}" if parts.query else utm
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                    query, parts.fragment))


def tag_html(body: str, freq: str, hosts) -> str:
    """Tag every href in an HTML body. Only attributes that change are
    rewritten, so an untouched link keeps its original entity encoding."""
    def repl(m):
        raw = m.group(3)
        url = _html.unescape(raw)
        new = tag_url(url, freq, hosts)
        if new == url:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{_html.escape(new, quote=True)}{m.group(2)}"
    return _HREF.sub(repl, body or "")


TEXT_WIDTH = 78


def tag_text(body: str, freq: str, hosts) -> str:
    """Tag every bare URL in a plain-text body. Sentence punctuation after a
    URL stays outside it.

    The plain-text part wraps prose at 78 columns and lets a URL run long only
    on a line of its own, because a link broken across two lines is a link a
    reader cannot use. A tag can push a "Label: URL" line past that width, so
    such a line is split: the label stays, the URL moves to the next line
    under the same indent."""
    def repl(m):
        url = m.group(0)
        trail = ""
        while url and url[-1] in ".,;:!?":
            trail = url[-1] + trail
            url = url[:-1]
        return tag_url(url, freq, hosts) + trail

    out = []
    for line in (body or "").split("\n"):
        new = _TEXT_URL.sub(repl, line)
        if new != line and len(new) > TEXT_WIDTH and " " in new.strip():
            m = _TEXT_URL.search(new)
            head = new[:m.start()].rstrip()
            if head.strip():
                indent = new[:len(new) - len(new.lstrip())]
                new = head + "\n" + indent + new[m.start():]
        out.append(new)
    return "\n".join(out)
