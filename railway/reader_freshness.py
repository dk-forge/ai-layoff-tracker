"""Does a deploy actually reach READERS, or only the origin?

Every deploy check this repo had measured the wrong surface. `ops_status.py [1]`
fetched `/ai-layoff-tracker/?cb=<uuid>`; `deploy-plugin.yml` fetched
`/wp-json/.../integrity-status?deploy_check=<run id>`. Both carry a query string
no cache has an entry for, so both are answered by the ORIGIN. They prove the
new build is installed. They cannot prove a reader sees it, because a reader
requests the bare URL with no query string, and that is the one key a shared
cache does hold.

Measured 2026-08-05. 2.19.274 finished deploying at 07:34:35Z. Eight minutes
later the bare URL with a browser User-Agent still served HTML built by
2.19.272 (superseded at 07:22), while the same URL plus `?cb=` served 2.19.274
and the cache-immune `/status` endpoint reported 2.19.274. The origin was
correct the whole time. Two chained shared caches were not:

    reader -> Cloudflare -> Railway proxy (x-cache-status) -> Bluehost -> PHP

Both honour the page's own Cache-Control, and their windows ADD: the response
carried `s-maxage=300, stale-while-revalidate=600`, so each hop could serve up
to 900s of stale body and the reader-visible worst case was roughly twice that.
The copy self-healed at 07:42:25 the moment Cloudflare's `age` reached 300, which
is what proves the mechanism: it was TTL, not a hook that never ran.

So this module measures the reader's surface, on purpose:

  * `reader_view()` fetches the BARE url, browser User-Agent, NO query string.
  * `deployed_version()` reads `/status`, which is deliberately no-store and is
    therefore the origin's own answer.
  * a mismatch between the two is content readers cannot see yet.

A mismatch is only a FAULT once the propagation window has passed, and this
module refuses to guess when that is. `check()` takes the deploy's finish time;
without one it returns UNKNOWN, never PASS. A checker that cannot tell
"propagating" from "stuck" and reports healthy is the defect this file exists to
end.

Stdlib only, no keys, safe to run from anywhere.
"""
import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("WP_SITE_URL", "https://asktherecruiter.com/blog").rstrip("/")
PAGE_URL = f"{BASE}/ai-layoff-tracker/"
STATUS_URL = f"{BASE}/wp-json/layoffs/v1/status"

# A reader is a browser. ModSecurity blocks `python-requests`, and more to the
# point a bot User-Agent is not the surface we are trying to measure.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# How many INDEPENDENT shared caches sit between a reader and PHP. Measured
# 2026-08-05: Cloudflare (cf-cache-status) in front of a Railway proxy
# (x-cache-status), each with its own entry and its own timer. Their windows do
# not overlap, they add, which is why a 300s s-maxage produced a reader-visible
# staleness far longer than 300s.
SHARED_CACHE_HOPS = 2

# Slack on top of the window the headers permit: a revalidation is not
# instantaneous and POPs do not all expire together.
PROPAGATION_MARGIN_S = 120

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

VERSION_RE = re.compile(r"ver=(\d+\.\d+\.\d+)")


class Result:
    """A verdict that can say it does not know.

    PASS / FAIL / UNKNOWN are three distinct states. `ok` is true only for PASS,
    so `if result.ok` can never be satisfied by an unanswered check.
    """

    def __init__(self, verdict, detail, served=None, deployed=None, grace=None):
        self.verdict = verdict
        self.detail = detail
        self.served = served
        self.deployed = deployed
        self.grace = grace

    @property
    def ok(self):
        return self.verdict == PASS

    def __repr__(self):
        return f"<Result {self.verdict}: {self.detail}>"


def parse_cache_control(value):
    """`public, max-age=60, s-maxage=60` -> {'public': True, 'max-age': 60, ...}."""
    out = {}
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, _, raw = part.partition("=")
            try:
                out[key.strip().lower()] = int(raw.strip().strip('"'))
            except ValueError:
                out[key.strip().lower()] = raw.strip().strip('"')
        else:
            out[part.lower()] = True
    return out


def version_in_html(html):
    """The plugin version that BUILT this HTML.

    Asset URLs are fingerprinted `?ver=ALT_VERSION.filemtime`, so the version in
    the markup is the version of the PHP that rendered it. Reading it from the
    body rather than from a header is deliberate: headers are rewritten by
    caches, the body is the thing the reader actually got.
    """
    found = VERSION_RE.findall(html or "")
    if not found:
        return None
    # Several assets, all stamped by the same render. Take the most common so a
    # single stray third-party `ver=` cannot decide the answer.
    return max(set(found), key=found.count)


def max_reader_staleness_s(cache_control):
    """Seconds of stale content the response's OWN headers permit a reader.

    s-maxage is the shared-cache freshness lifetime and stale-while-revalidate
    extends it; each hop gets its own full window, so they multiply by the hop
    count. stale-if-error is deliberately NOT counted: it only applies when the
    origin is failing, which is a case where stale beats an error page.
    """
    cc = parse_cache_control(cache_control) if isinstance(cache_control, str) else dict(cache_control or {})
    fresh = cc.get("s-maxage")
    if not isinstance(fresh, int):
        fresh = cc.get("max-age") if isinstance(cc.get("max-age"), int) else 0
    swr = cc.get("stale-while-revalidate")
    if not isinstance(swr, int):
        swr = 0
    return (fresh + swr) * SHARED_CACHE_HOPS


def grace_seconds(cache_control):
    return max_reader_staleness_s(cache_control) + PROPAGATION_MARGIN_S


def _open(url, ua, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    return urllib.request.urlopen(req, timeout=timeout)


def reader_view(url=PAGE_URL, timeout=40):
    """Fetch exactly what a reader gets: bare URL, browser UA, NO cache buster.

    Do NOT add a query string here, ever. That is the whole point of the file.
    """
    with _open(url, BROWSER_UA, timeout) as resp:
        html = resp.read().decode("utf-8", "replace")
        headers = {k.lower(): v for k, v in resp.headers.items()}
    return version_in_html(html), headers


def deployed_version(url=STATUS_URL, timeout=40):
    """The origin's own answer. /status is intentionally no-store, so no cache
    can stand in for it."""
    import json
    with _open(url, "AiLayoffTracker/1.0 (+https://asktherecruiter.com)", timeout) as resp:
        payload = json.load(resp)
    version = payload.get("version")
    return str(version) if version else None


def check(deploy_finished_at=None, now=None):
    """Compare what readers are served against what is deployed.

    `deploy_finished_at` is a timezone-aware datetime for the last successful
    plugin deploy. Pass None when the caller could not determine it: a mismatch
    then resolves to UNKNOWN, because "shipped 20 seconds ago and still
    propagating" and "stuck behind a cache" look identical without it.
    """
    now = now or datetime.now(timezone.utc)
    try:
        served, headers = reader_view()
    except Exception as exc:                      # noqa: BLE001 - reported, not swallowed
        return Result(UNKNOWN, f"could not fetch the reader view of {PAGE_URL}: {exc}")
    try:
        deployed = deployed_version()
    except Exception as exc:                      # noqa: BLE001
        return Result(UNKNOWN, f"could not read the deployed version from {STATUS_URL}: {exc}",
                      served=served)

    grace = grace_seconds(headers.get("cache-control", ""))
    if served is None:
        return Result(UNKNOWN, "the reader view returned no ver= stamp, so nothing was compared",
                      deployed=deployed, grace=grace)
    if deployed is None:
        return Result(UNKNOWN, "/status returned no version, so nothing was compared",
                      served=served, grace=grace)
    if served == deployed:
        return Result(PASS, f"readers are served {served}, which is the deployed build",
                      served=served, deployed=deployed, grace=grace)

    if deploy_finished_at is None:
        return Result(UNKNOWN,
                      f"readers are served {served} but {deployed} is deployed, and the last "
                      f"deploy time is unknown here, so this cannot be told apart from normal "
                      f"propagation (grace is {grace}s)",
                      served=served, deployed=deployed, grace=grace)

    age = (now - deploy_finished_at).total_seconds()
    if age <= grace:
        return Result(PASS,
                      f"readers are served {served} and {deployed} is {int(age)}s old, still "
                      f"inside the {grace}s propagation window",
                      served=served, deployed=deployed, grace=grace)
    return Result(FAIL,
                  f"readers are served {served} but {deployed} deployed {int(age)}s ago, past "
                  f"the {grace}s window. The origin is correct and a shared cache is not: the "
                  f"bare URL is serving a superseded build to every reader and crawler.",
                  served=served, deployed=deployed, grace=grace)


def wait_for(expected, timeout=600, interval=15, log=print):
    """Poll the reader's surface until it serves `expected`.

    Returns the measured propagation delay in seconds, or None on timeout.
    Transient fetch failures are retried rather than failing the caller: the
    host 504s under load, and an outage must not be reported as a stale deploy.
    """
    started = time.monotonic()
    last = None
    while True:
        try:
            served, _ = reader_view()
            last = served
            if served == expected:
                return time.monotonic() - started
            log(f"    reader view is {served}, waiting for {expected} "
                f"({int(time.monotonic() - started)}s elapsed)")
        except Exception as exc:                  # noqa: BLE001
            log(f"    reader view unreachable ({exc}); retrying")
        if time.monotonic() - started + interval > timeout:
            log(f"    last reader view was {last}")
            return None
        time.sleep(interval)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wait-for", metavar="VERSION",
                        help="poll the bare URL until it serves this version")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args(argv)

    if args.wait_for:
        print(f"Waiting for readers to be served {args.wait_for} at {PAGE_URL}")
        print("(bare URL, browser User-Agent, no cache buster - this is the reader's surface)")
        delay = wait_for(args.wait_for, timeout=args.timeout, interval=args.interval)
        if delay is None:
            print(f"::error::Readers are STILL not being served {args.wait_for} after "
                  f"{args.timeout}s. The origin may be correct while a shared cache serves a "
                  f"superseded build. See docs/RUNBOOK.md 'a deploy is not reaching readers'.")
            return 1
        print(f"Readers are served {args.wait_for}. Propagation delay: {int(delay)}s.")
        return 0

    result = check()
    print(f"{result.verdict}: {result.detail}")
    return {PASS: 0, FAIL: 2}.get(result.verdict, 3)


if __name__ == "__main__":
    sys.exit(main())
