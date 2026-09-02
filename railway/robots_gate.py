"""Ask before reading: the robots.txt gate in front of every publisher fetch.

THE DEFECT THIS CLOSES (2026-09-02). `sources.gdelt._fetch_article` read the
BODY of every allowlisted GDELT hit with a bare `requests.get`, presenting as
Chrome on macOS, and consulted nothing first. The allowlist is 738 outlets in
180 countries. Everything else in this repo already knew better and said so
in its own comments: the regional and national feed paths are described as
"robots-checked", `curated_probe` is built so that "no robots.txt is
engaged", and `country_coverage.REFUSAL_LEDGER` states the rule in one line:
read robots.txt BEFORE the first content request on any new host. This path
skipped it. A publisher that says no in robots.txt was never asked, which is
routing around a refusal by omission, and the ledger's whole point is that a
refusal is recorded and honoured, never routed around.

TWO THINGS, SEPARABLE, BOTH HERE.

  1. CONSULT. `RobotsGate.verdict(url)` reads the host's robots.txt once,
     caches the parsed file per host, and answers ALLOW / DISALLOW / UNKNOWN
     for the agent we actually send. Three states, deliberately, and only
     ALLOW permits a fetch: UNKNOWN (the file could not be read: timeout,
     5xx, transport error) is not permission. Absence of a signal is not a
     pass anywhere else in this repo and it is not one here.

  2. IDENTIFY. The agent string sent to a third-party publisher is
     `PUBLISHER_UA`, the identifying one with a contact URL, in the shape the
     repo already uses against its own host. A browser string is justified
     for asktherecruiter.com itself, where ModSecurity blocks `python-requests`
     (CLAUDE.md iron rule; that string is set in `cron.py` and
     `sources/gdelt.py` and is NOT read from here). It is a different thing to
     present as Safari to 738 publishers we do not own, and a robots.txt
     directive addressed to us cannot be honoured by a client that hides who
     it is.

WHAT EACH ANSWER MEANS, and where the line is drawn (RFC 9309 section 2.3.1):

  200            parsed; the verdict is the file's, for our token, else `*`.
  404 / 410      no robots file: unrestricted. That is a reachable answer of
                 "no rules", not an absent one, and the RFC says the same.
  401 / 403      the server refuses the robots file itself to our identifying
                 agent. The refusal ledger calls a 403-to-the-identifying-
                 agent a REFUSAL, and presenting a browser string to get past
                 it would be spoofing an access control aimed at us. DISALLOW.
  anything else  UNKNOWN: 5xx, a timeout, a connection error, a body over the
                 500 KiB the RFC lets a reader stop at. Not fetched. The note
                 says why, so a run log can tell an outage from a refusal.

COST. One robots.txt request per host per process, held for `ttl_seconds`
(24h; the daily collector is a fresh process each run, the backfill is not).
Workers that reach the same host together share one in-flight read rather
than four, so the gate can never amplify: a run that fetches N bodies from H
hosts makes at most H robots requests, and a host that refused makes ONE and
then none. `Crawl-delay` in the file is honoured by `pace(url)`, capped at
`MAX_CRAWL_DELAY` so a hostile value cannot stall a worker pool.

WHAT IT NEVER DOES. It never retries a robots read with a different agent
string, never treats a parse failure as ALLOW, and never lets a caller learn
"allowed" from an exception path. `tests/test_robots_gate.py` breaks the guard
by mutation and proves the article request does not go out.
"""
import threading
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

# The identifying agent sent to publishers. Same shape as the string the repo
# sends to its own host, and by design: there is exactly one name this
# collector answers to in a robots.txt, and it is the first token here.
PUBLISHER_UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

ALLOW = "allow"
DISALLOW = "disallow"
UNKNOWN = "unknown"
STATES = (ALLOW, DISALLOW, UNKNOWN)

DEFAULT_TTL_SECONDS = 24 * 3600
ROBOTS_TIMEOUT_SECONDS = 10
MAX_ROBOTS_BYTES = 500 * 1024      # RFC 9309 2.5: a reader may stop here
MAX_CRAWL_DELAY = 30.0             # honoured up to this; a hostile value is capped, not obeyed
_NO_FILE_STATUSES = (404, 410)
_REFUSED_STATUSES = (401, 403)


def robots_url_for(url):
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def host_of(url):
    return (urlsplit(url).netloc or "").lower()


def _default_fetch(robots_url, user_agent):
    """One request. Returns (status, text). Raises on transport failure.

    Reads at most MAX_ROBOTS_BYTES of the body; a longer file returns
    status -1 so the caller records UNKNOWN rather than judging a truncated
    directive set.
    """
    resp = requests.get(robots_url, headers={"User-Agent": user_agent},
                        timeout=ROBOTS_TIMEOUT_SECONDS, stream=True)
    try:
        if resp.status_code != 200:
            return resp.status_code, ""
        # A 200 is not a robots file. Some apex hosts redirect /robots.txt to
        # the HTML homepage (nikkei.com and folha.uol.com.br did on
        # 2026-09-02); parsing a homepage as directives yields "no rules",
        # which would turn a redirect into permission. Not a file we read.
        final_path = urlsplit(resp.url or robots_url).path
        ctype = (resp.headers.get("content-type") or "").lower()
        if not final_path.endswith("/robots.txt") or "text/html" in ctype:
            return -2, ""
        body = resp.raw.read(MAX_ROBOTS_BYTES + 1, decode_content=True)
        if len(body) > MAX_ROBOTS_BYTES:
            return -1, ""
        return 200, body.decode(resp.encoding or "utf-8", errors="replace")
    finally:
        resp.close()


class RobotsGate:
    """Per-host robots.txt verdicts with a bounded request cost. Thread-safe."""

    def __init__(self, user_agent=PUBLISHER_UA, ttl_seconds=DEFAULT_TTL_SECONDS,
                 fetch=None, clock=time.monotonic, sleep=time.sleep):
        self.user_agent = user_agent
        self.ttl_seconds = ttl_seconds
        self._fetch = fetch or _default_fetch
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._host_locks = {}
        self._cache = {}          # host -> (expires_at, state, note, parser)
        self._last_hit = {}       # host -> monotonic time of the last body fetch
        self.robots_requests = 0  # every robots.txt request this gate ever made
        self.refused_hosts = {}   # host -> note (DISALLOW at the host level)
        self.unknown_hosts = {}   # host -> note

    # -- the answer ----------------------------------------------------------

    def verdict(self, url):
        """(state, note) for `url`. Only ALLOW permits a body request."""
        host = host_of(url)
        robots_url = robots_url_for(url)
        if not host or not robots_url:
            return UNKNOWN, "robots.txt: URL has no host, nothing to consult"
        state, note, parser = self._entry(host, robots_url)
        if state != ALLOW or parser is None:
            return state, note
        # A file was read and it does not refuse the host outright; the verdict
        # for THIS path is the file's.
        try:
            allowed = parser.can_fetch(self.user_agent, url)
        except Exception as exc:  # a malformed path must not become permission
            return UNKNOWN, f"robots.txt: could not evaluate path ({exc})"
        if allowed:
            return ALLOW, f"{note}; path allowed"
        return DISALLOW, f"robots.txt disallows this path for {self.user_agent.split('/')[0]}"

    def pace(self, url):
        """Honour Crawl-delay for the host before a body request. Blocking."""
        host = host_of(url)
        entry = self._cache.get(host)
        delay = 0.0
        if entry and entry[3] is not None:
            try:
                declared = entry[3].crawl_delay(self.user_agent)
            except Exception:
                declared = None
            if declared:
                delay = min(float(declared), MAX_CRAWL_DELAY)
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._last_hit.get(host, -1e9) + delay - now)
            self._last_hit[host] = now + wait
        if wait > 0:
            self._sleep(wait)

    # -- the cache -----------------------------------------------------------

    def _host_lock(self, host):
        with self._lock:
            lock = self._host_locks.get(host)
            if lock is None:
                lock = self._host_locks[host] = threading.Lock()
            return lock

    def _entry(self, host, robots_url):
        now = self._clock()
        cached = self._cache.get(host)
        if cached and cached[0] > now:
            return cached[1], cached[2], cached[3]
        # One in-flight read per host: workers that arrive together wait for
        # the first one's answer instead of each asking.
        with self._host_lock(host):
            cached = self._cache.get(host)
            if cached and cached[0] > self._clock():
                return cached[1], cached[2], cached[3]
            state, note, parser = self._consult(robots_url)
            with self._lock:
                self._cache[host] = (self._clock() + self.ttl_seconds, state, note, parser)
                if state == DISALLOW:
                    self.refused_hosts[host] = note
                elif state == UNKNOWN:
                    self.unknown_hosts[host] = note
            return state, note, parser

    def _consult(self, robots_url):
        """Exactly one robots.txt request. Returns (host_state, note, parser).

        `host_state` is the verdict for the HOST: DISALLOW here means no path
        on it may be read; ALLOW means the file was read and per-path
        judgement follows. Never raises.
        """
        with self._lock:
            self.robots_requests += 1
        try:
            status, text = self._fetch(robots_url, self.user_agent)
        except Exception as exc:
            return UNKNOWN, f"robots.txt unreachable ({type(exc).__name__}); treated as not allowed", None
        if status in _NO_FILE_STATUSES:
            parser = urllib.robotparser.RobotFileParser()
            parser.parse([])           # no file: no rules; can_fetch answers True
            return ALLOW, "no robots.txt (HTTP %d): unrestricted" % status, parser
        if status in _REFUSED_STATUSES:
            return DISALLOW, ("robots.txt refused to our agent (HTTP %d); a refusal, "
                              "not a gap" % status), None
        if status == -1:
            return UNKNOWN, "robots.txt over %d bytes; not judged, treated as not allowed" % MAX_ROBOTS_BYTES, None
        if status == -2:
            return UNKNOWN, "robots.txt redirected to a page that is not a robots file; treated as not allowed", None
        if status != 200:
            return UNKNOWN, "robots.txt HTTP %d; treated as not allowed" % status, None
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(text.splitlines())
        except Exception as exc:
            return UNKNOWN, f"robots.txt unparseable ({type(exc).__name__}); treated as not allowed", None
        if not parser.can_fetch(self.user_agent, robots_url.rsplit("/robots.txt", 1)[0] + "/"):
            return DISALLOW, f"robots.txt disallows the whole host for {self.user_agent.split('/')[0]}", parser
        return ALLOW, "robots.txt read", parser

    # -- reporting -----------------------------------------------------------

    def hosts_consulted(self):
        return len(self._cache)

    def report_lines(self, prefix="robots"):
        """Run-log lines. Host names appear here and only here: the health
        ledger gets counts (see gdelt_reach), the run log gets the names, and
        the names are the allowlist's own, already public in this repo."""
        lines = [f"{prefix}: {self.hosts_consulted()} host(s) consulted, "
                 f"{self.robots_requests} robots.txt request(s), "
                 f"{len(self.refused_hosts)} refused, {len(self.unknown_hosts)} unreadable"]
        for host in sorted(self.refused_hosts):
            lines.append(f"{prefix} REFUSED {host}: {self.refused_hosts[host]} "
                         f"(candidate for country_coverage.REFUSAL_LEDGER; owner decides)")
        for host in sorted(self.unknown_hosts):
            lines.append(f"{prefix} UNKNOWN {host}: {self.unknown_hosts[host]}")
        return lines
