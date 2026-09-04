"""Reads of our OWN public API share one rule: an unset `WP_SITE_URL` is a
configuration fault that says so, never a silence that reads as an outage.

Three modules look our own rows up before judging anything -- the watchlist's
`already_have`, `tracker_diff._our_rows`, `curated_probe.our_rows`. Each built
its URL from the env var and, when it was unset, requested `/wp-json/...` on an
EMPTY host, caught the exception, and returned its "could not read" value. On
2026-09-04 that made a held item (27 rows live) score UNKNOWN in the curated
probe with the note "our own API did not answer". The API had answered nothing
because nothing had been asked; absence of configuration is not absence of an
answer, and a machine whose output is lessons must not learn from a request it
never sent.

Stdlib only. Nothing here prints a name or reads anything but the environment.
"""
from __future__ import annotations

import os

DEFAULT_HINT = "https://asktherecruiter.com/blog"


class SiteNotConfigured(RuntimeError):
    """`WP_SITE_URL` is unset or blank. Distinct from an upstream failure on
    purpose, so a caller cannot fold it into "did not answer"."""


def require_site_url() -> str:
    """Our site root with no trailing slash, or raise `SiteNotConfigured`.

    Callers put this OUTSIDE their network try/except: the point is that a
    missing setting propagates as itself rather than as the exception the empty
    host would have produced.
    """
    site = (os.environ.get("WP_SITE_URL") or "").strip().rstrip("/")
    if not site:
        raise SiteNotConfigured(
            "WP_SITE_URL is not set, so our own API cannot be read. This is a "
            "configuration fault on this machine, not an outage of the site: "
            f"export WP_SITE_URL={DEFAULT_HINT} and run again.")
    return site
