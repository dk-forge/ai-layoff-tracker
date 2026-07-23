"""One shared retry for reads against the shared WordPress host.

The host answers 5xx intermittently on deep-offset pages, especially while a
large WARN import is loading it. Every long scan hits this eventually, and the
default `raise_for_status()` turns one blip into a dead run: the industry
backfill died at page 76 of 140 every morning for days, having classified
nothing, and the legacy-row repair reproduced the identical failure within
hours of that fix because the retry lived in one file instead of a shared one.

Hence this module. A scan that wants to survive a blip imports `get_with_retry`
rather than re-deriving it and drifting.
"""
import time

import requests

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
