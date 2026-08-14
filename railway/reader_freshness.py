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
  * `origin_build()` reads `/status`, which is deliberately no-store and is
    therefore the origin's own answer.
  * a mismatch between the two is content readers cannot see yet.

A mismatch is only a FAULT once the propagation window has passed, and this
module refuses to guess when that is. `check()` takes the deploy's finish time;
without one it returns UNKNOWN, never PASS. A checker that cannot tell
"propagating" from "stuck" and reports healthy is the defect this file exists to
end.

THE VERSION IS NOT THE CONTENT. Measured 2026-08-12, 2.20.21: the deploy's own
reader check requested the bare URL while FTPS was still uploading.
ai-layoff-tracker.php, which carries ALT_VERSION, had landed;
templates/page-tracker.php had not. WP Super Cache stored that render, so every
reader got asset URLs stamped `ver=2.20.21` wrapped around the PREVIOUS
template, for about twenty-five minutes, and this module returned PASS
throughout because 2.20.21 really was the deployed version. It dated the build
and never looked at the body. Two sessions afterwards worked around it locally
rather than fixing it here.

So a second, independent thing is compared: the BUILD STAMP. The plugin hashes
its own files at render time (`includes/build-stamp.php`) and the rendered page
carries the answer as `<!-- alt-build ver=X build=Y -->`, emitted from
`alt_template()`, the funnel every plugin surface renders through, so the stamp
is produced by the same render as the body around it. `/status` reports the same
function's answer, cache-immune. A template that has not landed yet is different
bytes, so it is a different stamp, and

    version equal + stamp different  ==  the 2.20.21 shape, and it is a FAULT.

PASS now requires BOTH to agree. The order of the checks is deliberate: a
version mismatch is still judged first and exactly as before, so nothing this
module could already catch became weaker. Only when the versions agree does a
missing stamp resolve to UNKNOWN.

AND THE CHECK MUST NOT FILL THE CACHE IT IS MEASURING. On 2.20.21 the raced page
was cached BY THE VERIFICATION REQUEST. The bare URL cannot be avoided - it is
the surface - but requesting it while the origin is still incoherent can be.
`wait_for()` polls the no-store `/status` (a REST route, which fills no page
cache) until the ORIGIN reports the expected build, and only then touches the
bare URL. By that point the version bump has also fired
`alt_flush_caches_on_deploy()`, so our request lands on an empty page cache and
fills it with a coherent render instead of a raced one. This does not stop some
OTHER visitor or crawler arriving mid-upload; nothing here can. What changed is
that the result is now detected instead of passed.

Stdlib only, no keys, safe to run from anywhere.
"""
import argparse
import hashlib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

BASE = os.environ.get("WP_SITE_URL", "https://asktherecruiter.com/blog").rstrip("/")
PAGE_URL = f"{BASE}/ai-layoff-tracker/"
# `?build=1` asks /status to hash the plugin's files and report the build stamp.
# It is opt-in because that route is polled by the live badge in every open tab
# every 60s and is deliberately uncached; hashing 2MB for each of those would be
# a tax on readers to answer a question only this file asks. The query string is
# safe HERE and nowhere near the reader's page: /status is no-store, so it has no
# cache entry for anything to be keyed on. See PAGE_URL, which must stay bare.
STATUS_URL = f"{BASE}/wp-json/layoffs/v1/status?build=1"

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
#
# SIZED FROM THE ONE MEASUREMENT WE HAVE, not from comfort. 2026-08-05:
# 2.19.274 finished at 07:34:35Z, readers healed at 07:42:25Z, 470 seconds. The
# headers then permitted s-maxage=300 per hop over two hops, so 600s of plain
# freshness before stale-while-revalidate was even reached: the realised delay
# was 0.78 of what the headers allowed. Today's page header is s-maxage=60 with
# no swr, so 120s permitted over the two hops and the same ratio predicts ~94s.
# The window this module allows is 120 + 120 = 240s, about 2.5x the scaled
# measurement. Widening it further would re-buy the 2026-08-05 blindness; the
# deploy's own wait is bounded separately (--timeout 600) and simply keeps
# waiting rather than declaring anything.
PROPAGATION_MARGIN_S = 120

# How long the deploy's wait will hold out for the ORIGIN to report the build
# this checkout computes, before deciding the difference is not a deploy in
# flight. The files are already on disk when the deploy step runs - the FTPS
# mirror finished a step earlier - so this covers the flush and a slow first
# render, not an upload.
ORIGIN_GATE_S = 120

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

# Only the PLUGIN'S own fingerprinted assets carry ALT_VERSION. A bare
# ver= match also catches the THEME'S assets (2.0.86, 1.9.2), and on
# 2026-08-07 that made this guard report readers on a superseded build
# while a direct read of layoffs.css?ver= showed them current. The guard
# had the exact defect it exists to catch: measuring the wrong surface.
VERSION_RE = re.compile(r"layoffs\.(?:css|js)\?ver=(\d+\.\d+\.\d+)")

# What the plugin's alt_build_stamp_comment() emits into the body it rendered.
BUILD_RE = re.compile(r"<!--\s*alt-build ver=[\d.]+ build=([0-9a-f]{8,64})\s*-->")

# The plugin tree this checkout would deploy. The expected build stamp is
# computed from it, so the deploy waits on the bytes it is uploading rather than
# on a version string that one file carries.
PLUGIN_DIR = Path(__file__).resolve().parents[1] / "wordpress-plugin" / "ai-layoff-tracker"

ReaderView = namedtuple("ReaderView", "version build headers")


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


def build_in_html(html):
    """The BUILD that rendered this HTML, or None.

    None is not a failure to be smoothed over: it routes to UNKNOWN in check().
    Two DIFFERENT stamps on one page is also None, because half a page from one
    build and half from another is precisely the state this exists to catch and
    is not a value to compare against anything.
    """
    found = set(BUILD_RE.findall(html or ""))
    if len(found) != 1:
        return None
    return found.pop()


def _build_file_excluded(rel):
    """The deploy's own --exclude-globs (.git*, *.zip), and nothing else."""
    for part in rel.split("/"):
        if part.startswith(".git") or part.endswith(".zip"):
            return True
    return False


def checkout_build_stamp(plugin_dir=None):
    """The stamp the plugin in THIS checkout would emit once deployed.

    The Python half of `alt_build_stamp()` in includes/build-stamp.php. Same file
    set (everything the deploy mirrors), same manifest, same digest, same
    truncation. The test executes the PHP against this tree and requires the two
    answers to be equal, because two implementations of one number drift.

    Returns None when the tree is not there, which is UNKNOWN, not a stamp.
    """
    root = Path(plugin_dir or PLUGIN_DIR)
    if not root.is_dir():
        return None
    rels = sorted(str(p.relative_to(root)).replace(os.sep, "/")
                  for p in root.rglob("*") if p.is_file())
    rels = [r for r in rels if not _build_file_excluded(r)]
    if not rels:
        return None
    manifest = []
    for rel in rels:
        digest = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        manifest.append(f"{digest}  {rel}\n")
    return hashlib.sha256("".join(manifest).encode("utf-8")).hexdigest()[:16]


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
    return ReaderView(version_in_html(html), build_in_html(html), headers)


def origin_build(url=STATUS_URL, timeout=40):
    """(version, build) as the ORIGIN reports them. /status is intentionally
    no-store, so no cache can stand in for it. Either may be None."""
    import json
    with _open(url, "AiLayoffTracker/1.0 (+https://asktherecruiter.com)", timeout) as resp:
        payload = json.load(resp)
    version = payload.get("version")
    build = payload.get("build_stamp")
    return (str(version) if version else None, str(build) if build else None)


def check(deploy_finished_at=None, now=None):
    """Compare what readers are served against what is deployed.

    `deploy_finished_at` is a timezone-aware datetime for the last successful
    plugin deploy. Pass None when the caller could not determine it: a mismatch
    then resolves to UNKNOWN, because "shipped 20 seconds ago and still
    propagating" and "stuck behind a cache" look identical without it.
    """
    now = now or datetime.now(timezone.utc)
    try:
        view = reader_view()
    except Exception as exc:                      # noqa: BLE001 - reported, not swallowed
        return Result(UNKNOWN, f"could not fetch the reader view of {PAGE_URL}: {exc}")
    try:
        deployed, deployed_build = origin_build()
    except Exception as exc:                      # noqa: BLE001
        return Result(UNKNOWN, f"could not read the deployed version from {STATUS_URL}: {exc}",
                      served=view.version)

    served, served_build = view.version, view.build
    grace = grace_seconds(view.headers.get("cache-control", ""))

    def undecided(detail):
        return Result(UNKNOWN, detail, served=served, deployed=deployed, grace=grace)

    def aged(what, detail_stuck):
        """Shared verdict for any disagreement: propagating, or stuck."""
        if deploy_finished_at is None:
            return undecided(
                f"{what}, and the last deploy time is unknown here, so this cannot be "
                f"told apart from normal propagation (grace is {grace}s)")
        age = (now - deploy_finished_at).total_seconds()
        if age <= grace:
            return Result(PASS,
                          f"propagating, not a fault: {what}, {int(age)}s after the "
                          f"deploy and still inside the {grace}s window",
                          served=served, deployed=deployed, grace=grace)
        return Result(FAIL, f"{what}, {int(age)}s after the deploy and past the "
                            f"{grace}s window. {detail_stuck}",
                      served=served, deployed=deployed, grace=grace)

    # 1. The VERSION, judged exactly as before. Nothing this module could
    #    already catch is allowed to get weaker by adding the stamp.
    if served is None:
        return undecided("the reader view returned no ver= stamp, so nothing was compared")
    if deployed is None:
        return undecided("/status returned no version, so nothing was compared")
    if served != deployed:
        return aged(f"readers are served {served} but {deployed} is deployed",
                    "The origin is correct and a shared cache is not: the bare URL is "
                    "serving a superseded build to every reader and crawler.")

    # 2. The BODY. Same version on both sides proves only that one file landed.
    if served_build is None:
        return undecided(
            f"readers are served {served}, which is the deployed version, but the page "
            f"carries no build stamp, so which BYTES rendered it cannot be told. A page "
            f"can carry a new version around an old body (2.20.21)")
    if deployed_build is None:
        return undecided(
            f"readers are served {served} but /status reported no build stamp, so the "
            f"page's body has nothing cache-immune to be compared against")
    if served_build != deployed_build:
        return aged(
            f"readers are served version {served}, which is current, but a body built "
            f"from {served_build} while the origin would render {deployed_build}",
            "THIS IS THE 2.20.21 SHAPE: the version string reached readers and the "
            "content did not. A page rendered mid-upload is sitting in a cache. See "
            "docs/RUNBOOK.md 'a deploy is not reaching readers'.")

    return Result(PASS,
                  f"readers are served {served} and a body built from {served_build}, "
                  f"which is the deployed build",
                  served=served, deployed=deployed, grace=grace)


def wait_for(expected, expected_build=None, timeout=600, interval=15, log=print):
    """Poll the reader's surface until it serves `expected` (and `expected_build`).

    Returns the measured propagation delay in seconds, or None on timeout.
    Transient fetch failures are retried rather than failing the caller: the
    host 504s under load, and an outage must not be reported as a stale deploy.

    THE ORIGIN IS ASKED FIRST, AND THE BARE URL IS NOT TOUCHED UNTIL IT AGREES.
    On 2.20.21 this function's own request was the one that filled WP Super
    Cache with a render made while the templates were still uploading. /status
    is no-store and is a REST route, so polling it fills no page cache; once it
    reports the expected build, every file is on disk, the version bump has
    fired alt_flush_caches_on_deploy(), and our first bare-URL request can only
    store a coherent render. It does not stop another visitor arriving mid
    upload. Nothing here can, and pretending otherwise is how the last one hid.

    IF THE ORIGIN SETTLES ON A BUILD THIS CHECKOUT DOES NOT RECOGNISE, the gate
    ADOPTS the origin's build and says so loudly rather than failing the deploy.
    The two can legitimately differ for one reason that has nothing to do with a
    deploy reaching readers: a file on the server that is not in this checkout.
    Turning a stray file into a permanently red deploy is how a check gets
    deleted, and the reader-versus-origin comparison still catches the cached
    mid-upload render, which is what this step is for.
    """
    started = time.monotonic()

    def out_of_time():
        return time.monotonic() - started + interval > timeout

    if expected_build:
        gate_until = time.monotonic() + min(timeout, ORIGIN_GATE_S)
        seen = (None, None)
        while True:
            try:
                seen = version, build = origin_build()
                if version == expected and build == expected_build:
                    log(f"    origin is coherent at {expected}/{expected_build} "
                        f"({int(time.monotonic() - started)}s); now asking for the bare URL")
                    break
                log(f"    origin reports {version}/{build}, waiting for "
                    f"{expected}/{expected_build} before touching the reader's URL")
            except Exception as exc:              # noqa: BLE001
                log(f"    /status unreachable ({exc}); retrying")
            if time.monotonic() > gate_until and seen[0] == expected and not seen[1]:
                # The running build predates the stamp, or could not compute one.
                # There is nothing to compare a body against, so this degrades to
                # the version-only wait it was before - loudly, because that is
                # the weaker check this change exists to replace.
                log(f"::warning::The origin is running {expected} but reports no build "
                    f"stamp, so the reader's BODY cannot be checked, only its version. "
                    f"That is the state that passed 2.20.21. Expected "
                    f"{expected_build} from this checkout.")
                expected_build = None
                break
            if time.monotonic() > gate_until and seen[0] == expected and seen[1]:
                log(f"::warning::The origin is running {expected} but reports build "
                    f"{seen[1]}, and this checkout computes {expected_build}. The plugin "
                    f"directory on the server is not byte-identical to this tree - most "
                    f"likely a file that is on the server and not in this checkout. "
                    f"Waiting on the ORIGIN's build instead, which still catches a cached "
                    f"mid-upload render but no longer proves the server matches this "
                    f"commit.")
                expected_build = seen[1]
                break
            if out_of_time():
                log("    the ORIGIN never reported the expected version; the bare URL was "
                    "deliberately never requested, so nothing was cached by this check")
                return None
            time.sleep(interval)

    last = None
    while True:
        try:
            view = reader_view()
            last = (view.version, view.build)
            if view.version == expected and (not expected_build or view.build == expected_build):
                return time.monotonic() - started
            log(f"    reader view is {view.version}/{view.build}, waiting for "
                f"{expected}/{expected_build or 'any build'} "
                f"({int(time.monotonic() - started)}s elapsed)")
        except Exception as exc:                  # noqa: BLE001
            log(f"    reader view unreachable ({exc}); retrying")
        if out_of_time():
            log(f"    last reader view was {last}")
            return None
        time.sleep(interval)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wait-for", metavar="VERSION",
                        help="poll the bare URL until it serves this version")
    parser.add_argument("--expect-build", metavar="STAMP",
                        help="override the build stamp derived from this checkout")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args(argv)

    if args.wait_for:
        # The version alone is what a deploy can pass on the command line, so the
        # BUILD it should also wait for is derived here, from the tree this run
        # would deploy. Waiting on the version alone is the check that passed
        # 2.20.21.
        expected_build = args.expect_build or checkout_build_stamp()
        print(f"Waiting for readers to be served {args.wait_for} at {PAGE_URL}")
        print("(bare URL, browser User-Agent, no cache buster - this is the reader's surface)")
        if expected_build:
            print(f"Expected build stamp from this checkout: {expected_build}")
        else:
            print("::warning::No plugin tree here, so only the VERSION can be waited on. "
                  "That is weaker than this check is meant to be: a page can carry a new "
                  "version around an old body (2.20.21).")
        delay = wait_for(args.wait_for, expected_build=expected_build,
                         timeout=args.timeout, interval=args.interval)
        if delay is None:
            print(f"::error::Readers are STILL not being served {args.wait_for}"
                  f"{'/' + expected_build if expected_build else ''} after {args.timeout}s. "
                  f"The origin may be correct while a shared cache serves a superseded "
                  f"build, or a page rendered mid-upload is cached with the right version "
                  f"and the wrong body. See docs/RUNBOOK.md 'a deploy is not reaching readers'.")
            return 1
        print(f"Readers are served {args.wait_for}. Propagation delay: {int(delay)}s.")
        return 0

    result = check()
    print(f"{result.verdict}: {result.detail}")
    return {PASS: 0, FAIL: 2}.get(result.verdict, 3)


if __name__ == "__main__":
    sys.exit(main())
