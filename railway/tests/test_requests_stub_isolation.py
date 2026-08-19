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
        # a stub verb that returns None makes an unpatched call look like a pass
        got = self._run(
            "import _requests_stub; _requests_stub.install()\n"
            "import requests\n"
            "try:\n"
            "    requests.get('https://example.test')\n"
            "    print('SILENT')\n"
            "except RuntimeError as e:\n"
            "    print('raised' if 'no network' in str(e) else 'wrong')\n")
        self.assertEqual(got, "raised")

    def test_installing_twice_keeps_the_same_module(self):
        got = self._run(
            "import _requests_stub\n"
            "a = _requests_stub.install(); b = _requests_stub.install()\n"
            "print(a is b and a is sys.modules['requests'])\n")
        self.assertEqual(got, "True")


if __name__ == "__main__":
    unittest.main()
