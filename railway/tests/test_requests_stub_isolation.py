"""The `requests` stub is shared, complete, and installed in exactly one place.

Six test modules used to each stand their own partial `requests` stub into
sys.modules and skip when the slot was already taken, which made the module's
surface a function of unittest's discovery order. Running
`tests/test_digest_subscription.py` alone passed; running the whole suite gave
five ERRORs in `WeeklyEmailWiring` - "module 'requests' does not have the
attribute 'get'" - because a warn test's `RequestException`-only stub got there
first. Five red tests about nothing, which is how a suite trains people to
ignore red.

sys.modules is process-global and cannot be restored in tearDown (the module
under test binds `requests` at import and keeps that reference), so the
isolation has to be structural: ONE installer, and it completes rather than
skips.
"""
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLER = "_requests_stub.py"
SELF = os.path.basename(__file__)   # this file quotes the broken shape on purpose

sys.path.insert(0, HERE)


class OneInstaller(unittest.TestCase):

    def test_no_test_module_writes_the_requests_slot_itself(self):
        writes = re.compile(
            r"sys\.modules\s*\[\s*[\"']requests[\"']\s*\]\s*=|"
            r"sys\.modules\.setdefault\(\s*[\"']requests[\"']")
        offenders = []
        for name in sorted(os.listdir(HERE)):
            if not name.endswith(".py") or name in (INSTALLER, SELF):
                continue
            with open(os.path.join(HERE, name), encoding="utf-8") as fh:
                body = fh.read()
            if writes.search(body):
                offenders.append(name)
        self.assertEqual(
            offenders, [],
            "these modules install their own `requests` into the process-global "
            "slot; import `install` from tests/_requests_stub.py instead, or the "
            "surface depends on discovery order again")


class TheStubIsComplete(unittest.TestCase):
    """Run in a subprocess: these assertions are about a fresh sys.modules."""

    def _run(self, body):
        code = ("import sys, types\n"
                "sys.path.insert(0, %r)\n" % HERE) + body
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_it_completes_a_partial_stub_left_by_someone_else(self):
        # exactly the shape that broke WeeklyEmailWiring: RequestException, no get
        got = self._run(
            "rq = types.ModuleType('requests')\n"
            "rq.RequestException = Exception\n"
            "sys.modules['requests'] = rq\n"
            "import _requests_stub; _requests_stub.install()\n"
            "import requests\n"
            "print(all(hasattr(requests, n) for n in "
            "('get', 'post', 'Session', 'RequestException')))\n")
        self.assertEqual(got, "True")

    def test_the_verbs_refuse_the_network_rather_than_returning_none(self):
        """The refusal is raised AND no socket is ever opened.

        Both halves, because the first alone proved nothing and said so
        loudly. This assertion used to call `requests.get('https://example.test')`
        against whatever `install()` returned. Locally that is the stub and it
        passed; on CI `requests` is installed from the lock, `install()` rightly
        prefers the real module, and the "guard" made a REAL request — which
        failed with
        `requests.exceptions.ConnectionError ... NameResolutionError` and
        reddened CI on 2026-08-19. A test named "refuses the network" was the
        only thing in the suite reaching for DNS.

        Two structural fixes, and neither is a hosts-file entry or an
        `except ConnectionError`: either of those makes this pass while proving
        the opposite of its name.

        1. Seed an EMPTY `requests` into a fresh subprocess's `sys.modules`, so
           `install()` completes a stub and the assertion is about the stub on
           every machine. What is under test is the stub's contract, not
           whether the runner has the real library.
        2. Arm a tripwire on `socket` FIRST. `RuntimeError` is a weak witness --
           a future verb could open a connection and raise it afterwards -- so
           the socket layer, not the exception type, is what testifies that
           nothing left the process.
        """
        got = self._run(
            # (2) the tripwire goes down before anything can import around it
            "import socket\n"
            "touched = []\n"
            "def _tripped(*a, **k):\n"
            "    touched.append(1)\n"
            "    raise AssertionError('the network was touched')\n"
            "socket.socket = _tripped\n"
            "socket.create_connection = _tripped\n"
            "socket.getaddrinfo = _tripped\n"
            # (1) exercise the stub, not whatever the runner happens to have
            "sys.modules['requests'] = types.ModuleType('requests')\n"
            "import _requests_stub; _requests_stub.install()\n"
            "import requests\n"
            "verdict = 'SILENT'\n"
            "try:\n"
            "    requests.get('https://example.test')\n"
            "except RuntimeError as e:\n"
            "    verdict = 'raised' if 'no network' in str(e) else 'wrong'\n"
            "except BaseException as e:\n"
            "    verdict = type(e).__name__\n"
            "print(verdict, 'sockets=%d' % len(touched))\n")
        self.assertEqual(got, "raised sockets=0")

    def test_the_tripwire_itself_fires_when_something_does_reach_the_network(self):
        """A guard nobody has seen fail is a guard nobody should trust.

        Without this, `sockets=0` above would also be what a broken tripwire
        printed, and the test would go green on exactly the defect it exists to
        catch.
        """
        got = self._run(
            "import socket\n"
            "touched = []\n"
            "def _tripped(*a, **k):\n"
            "    touched.append(1)\n"
            "    raise AssertionError('the network was touched')\n"
            "socket.socket = _tripped\n"
            "socket.create_connection = _tripped\n"
            "socket.getaddrinfo = _tripped\n"
            "try:\n"
            "    socket.create_connection(('example.test', 443))\n"
            "except AssertionError:\n"
            "    pass\n"
            "print('sockets=%d' % len(touched))\n")
        self.assertEqual(got, "sockets=1")

    def test_installing_twice_keeps_the_same_module(self):
        got = self._run(
            "import _requests_stub\n"
            "a = _requests_stub.install(); b = _requests_stub.install()\n"
            "print(a is b and a is sys.modules['requests'])\n")
        self.assertEqual(got, "True")


if __name__ == "__main__":
    unittest.main()
