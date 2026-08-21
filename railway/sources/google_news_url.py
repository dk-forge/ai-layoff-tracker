"""Turn a Google News RSS <link> into the publisher's own article URL — OFFLINE.

WHY THIS EXISTS. Rows discovered through Google News RSS stored the REDIRECTOR
as their citation (``https://news.google.com/rss/articles/CBMi...``). Measured
2026-08-19 over a 5,000-row newest-first sample: 124 rows cite news.google.com,
and in the last 90 days that host is the single largest cause of unarchived
news rows (10 of 25). Two defects, both about citation quality:

  1. Even the 'archived' ones snapshot a REDIRECT PAGE. The permanent copy
     preserves a hop, not the evidence.
  2. The tokens are opaque and expire, so the citation rots by construction —
     the exact failure the Wayback work exists to prevent.

WHY IT NEVER MAKES A REQUEST, AND WHY THAT IS THE CEILING. The obvious fix is
to follow the redirect. ``news.google.com/robots.txt`` is ``Disallow: /`` for
``User-agent: *`` (with no ``Allow`` covering ``/rss/articles/``), and names
``ClaudeBot`` / ``anthropic-ai`` / ``GPTBot`` outright. Google's internal
``batchexecute`` route resolves these tokens and is a bot-control bypass. So the
article URL is reachable only by means this project will not use, and this
module resolves what can be resolved WITHOUT A NETWORK CALL. It imports no HTTP
client, and ``tests/test_google_news_url.py`` fails if one ever appears.

WHAT THAT ACTUALLY BUYS TODAY: measured 2026-08-21 over 259 live items across
the US, DE and JP editions, 259 were redirectors and 0 decoded — every current
token is the opaque ``AU_yqL...`` form, whose base64 body carries no URL. The
legacy ``CBMi<len><url>`` form DID embed the publisher URL and is still emitted
by other Google News surfaces and by older feeds, so decoding it is free and
correct; it is simply not where today's items are.

SO THE HONEST OUTCOME IS THREE-STATE, and callers must keep it that way:

  ``direct``      the item already linked the publisher. Canonicalised.
  ``decoded``     a legacy token embedded the URL. Recovered offline.
  ``unresolved``  an opaque token. The redirector is kept AS THE LINK — it does
                  reach the article while the token lives, which the outlet's
                  home page never would — and it is COUNTED, not papered over.

Do NOT "fix" an ``unresolved`` by substituting the ``<source url=...>`` home
page. Publisher identity belongs in ``source_name`` (the collector already puts
it there); a home page cannot verify the specific claim, and archiving one would
register as coverage that is not evidence. Counting the rot is the fix available
here. Reviewed with the owner 2026-08-21.
"""
import base64
import binascii
import re
import urllib.parse

# Google News runs per-country hosts; every one of them redirects the same way.
_GOOGLE_NEWS_HOST = re.compile(r"(^|\.)news\.google\.(com|[a-z]{2,3}(\.[a-z]{2})?)$", re.I)
_GOOGLE_HOST = re.compile(r"(^|\.)google\.(com|[a-z]{2,3}(\.[a-z]{2})?)$", re.I)

# Stripped from a RESOLVED publisher URL only. Every one is a campaign/analytics
# tag that names the referrer, never the document, so dropping it cannot change
# which article the citation points at. Deliberately NOT here: `ref`, `source`
# and `referrer`, which some CMSes use as real routing params — a wrong strip
# silently repoints the citation, which is worse than an untidy URL. The
# redirector's own params are NOT touched: there, the query string is
# load-bearing.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_brand", "utm_social",
    "gclid", "dclid", "fbclid", "msclkid", "twclid", "igshid", "mc_cid",
    "mc_eid", "ocid", "cmpid", "cmp", "ito", "smid", "smtyp", "ns_campaign",
    "ns_mchannel", "ns_source", "at_medium", "at_campaign", "spm",
    "_hsenc", "_hsmi", "guccounter",
})

# The URL charset, minus the bytes that end a protobuf string in practice.
_URL_IN_BLOB = re.compile(rb"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{6,}")


def _host(url):
    try:
        return (urllib.parse.urlsplit(url).netloc or "").split("@")[-1].split(":")[0]
    except ValueError:
        return ""


def is_redirector(url):
    """True for a Google News link that hides the publisher behind a token."""
    return bool(_GOOGLE_NEWS_HOST.search(_host(url or "")))


def canonicalize(url):
    """Drop tracking params and the fragment; leave everything else alone.

    Order-preserving, so two runs of the same URL produce the same string and
    the dedup hash stays stable."""
    url = (url or "").strip()
    if not url:
        return ""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS]
    query = urllib.parse.urlencode(kept)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def _plausible_article_url(url):
    """A decoded blob is only a citation if it is an off-Google http(s) URL."""
    if not url or not url.lower().startswith(("http://", "https://")):
        return False
    host = _host(url)
    if "." not in host or host.endswith("."):
        return False
    return not _GOOGLE_HOST.search(host)


def decode_legacy_token(url):
    """Recover the publisher URL from a legacy Google News link, or None.

    Two legacy shapes, both offline:
      * ``...?url=https%3A%2F%2F...`` — the pre-token form.
      * ``/rss/articles/CBMi<len><url>...`` — base64url protobuf whose first
        string field IS the article URL. The modern ``AU_yqL...`` token carries
        no URL and correctly returns None here.
    """
    url = (url or "").strip()
    if not is_redirector(url):
        return None
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None

    for key, values in urllib.parse.parse_qs(parts.query).items():
        if key.lower() in ("url", "u") and values:
            if _plausible_article_url(values[0]):
                return values[0]

    token = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if len(token) < 16:
        return None
    try:
        blob = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None

    # A legacy blob can hold the canonical URL AND an AMP mirror. Prefer the
    # first non-AMP candidate: the AMP copy is the one that gets retired.
    found = [m.group(0).decode("ascii", "ignore") for m in _URL_IN_BLOB.finditer(blob)]
    candidates = [c for c in found if _plausible_article_url(c)]
    non_amp = [c for c in candidates if "/amp" not in c.lower() and not _host(c).startswith("amp.")]
    for candidate in (non_amp + candidates):
        return candidate
    return None


def resolve(link):
    """``(url, state)`` where state is 'direct', 'decoded' or 'unresolved'.

    NEVER returns an empty url for a non-empty link: an unresolved redirector is
    handed back unchanged, because a link that works today beats a home page
    that never pointed at the article. The state is what the caller counts."""
    link = (link or "").strip()
    if not link:
        return "", "unresolved"
    if not is_redirector(link):
        return canonicalize(link), "direct"
    decoded = decode_legacy_token(link)
    if decoded:
        return canonicalize(decoded), "decoded"
    return link, "unresolved"
