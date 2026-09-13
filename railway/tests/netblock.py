"""Refuse, and RECORD, every outbound connection a test process attempts.

WHY THIS FILE EXISTS, 2026-09-13. The website went down twice in twelve hours.
Every PHP request to asktherecruiter.com timed out at ten seconds, account
wide: the blog root, the WordPress REST index, this tracker's routes and the
sibling talent tracker's routes, all failing identically. It was not a code
fault. It was load, and a measurable share of that load was our own test
suites, which use the production website as test data. This repository's suite
runs on every push and every pull request across four parallel legs; the
sibling's runs hourly, forever, on a cron. The site was being load tested
against production around the clock by the things that are supposed to be
telling us it is healthy.

A grep could not settle how bad it was. Forty two modules under `tests/` name
`asktherecruiter.com`, but almost all of them name it inside a PHP string they
are asserting against, which costs nothing. The only honest way to count a
network call is to WATCH FOR ONE, so this installs itself under the socket
layer, records the attempt with a full stack, and then refuses it.

HOW IT IS INSTALLED. Drop this directory on `PYTHONPATH` under the name
`sitecustomize` and Python imports it before the first line of anything else,
including a subprocess a test spawns. `tests/test_offline_suite_is_offline.py`
does exactly that and reads the log back.

It is `sitecustomize` rather than `usercustomize` for a reason that cost an
hour: `usercustomize` is only imported when the interpreter has user site
packages enabled, and a virtualenv frequently does not. The probe that reads
"zero connections" because it was never loaded is worse than no probe, because
zero is the answer everybody wants.

IT BLOCKS EVERYTHING, NOT JUST ONE HOST. A test that reaches Wikidata, GDELT,
EDGAR or openrouter.ai in the default suite is the same defect wearing a
different hostname, and an allowlist here would be a place for the next one to
hide. Loopback is exempt because `cdp.py` drives a real headless Chrome over a
DevTools socket on 127.0.0.1, which is a subprocess we own and not the open
internet.
"""
import os
import socket
import sys
import traceback

# Where to append. Set by whoever installs this; with no log set the blocker
# still refuses, it just keeps no record.
_LOG = os.environ.get("NETBLOCK_LOG")
_WHO = os.environ.get("NETBLOCK_WHO", "?")

# The DevTools socket and anything else we started ourselves.
_LOOPBACK = ("localhost", "127.0.0.1", "::1", "", None)

RECORD_END = "---END---"


def _record(host, port):
    if host in _LOOPBACK:
        return
    if not _LOG:
        return
    # The last two frames are this function and the hook that called it.
    stack = "".join(traceback.format_stack()[:-2])
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write("HOST\t%s\tPORT\t%s\tWHO\t%s\n" % (host, port, _WHO))
        fh.write("ARGV\t%r\tPID\t%s\tPPID\t%s\n"
                 % (sys.argv, os.getpid(), os.getppid()))
        fh.write(stack)
        fh.write(RECORD_END + "\n")


class BlockedByNetblock(OSError):
    """Raised in place of a connection. An OSError subclass on purpose: the
    code under test already handles `OSError` as "the host is unreachable" and
    resolves it to UNKNOWN, which is the honest reading of a blocked call."""


def _blocked(what):
    return BlockedByNetblock(
        "netblock: the offline test suite may not open a network connection "
        "(%s). If this test is genuinely about live data, register it in "
        "tests/live_host.py and gate it on ALT_LIVE_TESTS." % (what,))


def install():
    """Patch the two chokepoints every Python HTTP client goes through.

    BOTH are patched, not one. `getaddrinfo` catches a client resolving a
    hostname, which is nearly all of them and is what gives us a readable
    hostname to report. `socket.connect` catches a client handed a literal IP,
    which resolves nothing and would otherwise walk straight past a
    `getaddrinfo` hook.
    """
    if getattr(socket, "_netblock_installed", False):
        return

    def getaddrinfo(host, port, *a, **k):
        _record(host, port)
        raise _blocked("resolving %r" % (host,))

    def connect(self, address):
        try:
            host, port = address[0], address[1]
        except (TypeError, IndexError, KeyError):
            host, port = address, None
        if host in _LOOPBACK:
            return _real_connect(self, address)
        _record(host, port)
        raise _blocked("connecting to %r" % (address,))

    _real_connect = socket.socket.connect
    socket.getaddrinfo = getaddrinfo
    socket.socket.connect = connect
    socket._netblock_installed = True


def attempts(log_path):
    """The connection attempts recorded in a log, as a list of dicts.

    A MISSING FILE MEANS NO ATTEMPT WAS RECORDED, WHICH IS NOT THE SAME AS
    "the run was clean", and the caller has to establish that the run happened
    at all before reading this as a zero. That distinction is the reason this
    returns a list and never a bare count.
    """
    out = []
    try:
        with open(log_path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return out
    for block in text.split(RECORD_END + "\n"):
        head = block.strip().splitlines()
        if not head or not head[0].startswith("HOST\t"):
            continue
        parts = head[0].split("\t")
        out.append({"host": parts[1], "port": parts[3],
                    "who": parts[5] if len(parts) > 5 else "?",
                    "stack": "\n".join(head[1:])})
    return out


# The shim a child process actually imports. Python imports `sitecustomize`
# before the first line of user code, which is the only hook early enough to
# catch a module that fetches at IMPORT time -- the worst kind of live call,
# because it happens even for tests that are skipped.
_SHIM = """# Written by tests/netblock.py. Not part of the shipped tree.
import sys
sys.path.insert(0, %r)
import netblock
netblock.install()
"""


def shim_dir(tmpdir):
    """Materialise a `sitecustomize.py` in `tmpdir` and return the directory.

    Put the result FIRST on a child's PYTHONPATH. Importing this module in the
    parent does NOT arm anything: `install()` is never called at import, so a
    test can read `attempts()` back without having blocked its own process.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(tmpdir, "sitecustomize.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_SHIM % (here,))
    return tmpdir
