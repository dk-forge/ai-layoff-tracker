"""THE DEFAULT TEST RUN OPENS NO CONNECTION TO THE DEPLOYED SITE.

This is the guard for the 2026-09-13 outage. asktherecruiter.com went down
twice in twelve hours; every PHP request timed out at ten seconds, account
wide, across both trackers sharing the ChemiCloud account. It was load, and a
measurable share of it was our own suites fetching the production website on
every push, every pull request and, in the sibling repository, every hour.

WHY THIS IS A RUNTIME CHECK AND NOT A GREP. Forty two modules under `tests/`
contain the string `asktherecruiter.com`, and almost every one of them is
asserting against a PHP source line, which costs nothing. Counting them is not
counting requests. So the modules that CAN reach the network are actually run,
in a child process, under `netblock.py`, and what is asserted is the recorded
connection attempts. A test that measures the thing it is named after cannot
be satisfied by moving a string.

THE POSITIVE CONTROL IS NOT OPTIONAL. A checker that has only ever reported
"clean" is indistinguishable from a checker that is broken, and this repository
has been bitten by exactly that: a probe that read zero because it was never
loaded. `TheBlockerActuallyBlocks` runs a module built to fetch and requires
that it be caught. If that test is ever deleted, every other assertion in this
file becomes unfalsifiable.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import live_host
import netblock

HERE = Path(__file__).resolve().parent
RAILWAY = HERE.parent

# The child needs `tests/` (for the modules' own sibling imports) and
# `railway/` (for the code under test) exactly as the real runner provides
# them. The netblock shim directory goes in FRONT at call time.
_CHILD_PATH = [str(HERE), str(RAILWAY)]


def _run_under_netblock(script_args, tmpdir, env_extra=None):
    """Run a child with the connection blocker armed. Returns (proc, attempts).

    The child's PYTHONPATH carries the shim first, so `sitecustomize` is
    imported before the first line of the module under test. That is early
    enough to catch a module that fetches at IMPORT time, which is the worst
    kind of live call because it happens even for tests that are skipped.
    """
    log = os.path.join(tmpdir, "netblock.log")
    shim = netblock.shim_dir(tmpdir)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([shim] + _CHILD_PATH)
    env["NETBLOCK_LOG"] = log
    env["NETBLOCK_WHO"] = os.path.basename(script_args[0])
    # The default suite is the thing under test, so the opt in must be OFF
    # however this process happened to be invoked.
    env.pop(live_host.ENV, None)
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable] + script_args, cwd=str(HERE),
                          env=env, capture_output=True, text=True, timeout=900)
    return proc, netblock.attempts(log)


def _describe(attempts):
    lines = []
    for a in attempts[:4]:
        frame = ""
        for line in reversed(a["stack"].splitlines()):
            if "/tests/" in line or "/railway/" in line:
                frame = line.strip()
                break
        lines.append("%s:%s  <- %s" % (a["host"], a["port"], frame))
    more = "" if len(attempts) <= 4 else "  (+%d more)" % (len(attempts) - 4)
    return "; ".join(lines) + more


class TheBlockerActuallyBlocks(unittest.TestCase):
    """The positive control. Proven against a known instance, per the rule that
    a scan sharing its target's blind spot reports a clean zero forever."""

    def test_a_module_that_fetches_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            bait = os.path.join(tmp, "bait.py")
            # A name that resolves nowhere. The point is to prove the hook
            # fires BEFORE a packet leaves, so this must never be a real host,
            # and it must certainly never be the one that is down.
            with open(bait, "w", encoding="utf-8") as fh:
                fh.write("import urllib.request\n"
                         "urllib.request.urlopen('https://probe.invalid.example/')\n")
            proc, attempts = _run_under_netblock([bait], tmp)
        self.assertTrue(
            attempts,
            "netblock recorded NOTHING for a module whose only statement is a "
            "fetch. The blocker is not installed in the child, so every other "
            "assertion in this file is reading an empty log and calling it "
            "zero. stdout=%r stderr=%r" % (proc.stdout[-400:], proc.stderr[-400:]))
        self.assertEqual("probe.invalid.example", attempts[0]["host"])

    def test_loopback_is_left_alone(self):
        """cdp.py drives a real headless Chrome over a DevTools socket on
        127.0.0.1. Blocking that would take the rendered guards down with it,
        and a guard that forces people to disable it is a deleted guard."""
        with tempfile.TemporaryDirectory() as tmp:
            bait = os.path.join(tmp, "bait.py")
            with open(bait, "w", encoding="utf-8") as fh:
                fh.write("import socket\n"
                         "s = socket.socket()\n"
                         "try:\n"
                         "    s.connect(('127.0.0.1', 1))\n"
                         "except OSError as e:\n"
                         "    assert 'netblock' not in str(e), e\n")
            _, attempts = _run_under_netblock([bait], tmp)
        self.assertEqual([], attempts,
                         "netblock recorded a loopback connection: %s"
                         % _describe(attempts))


class TheLiveModulesDoNotRunByDefault(unittest.TestCase):
    """The three modules that ARE about live data reach nothing when the
    default suite runs them."""

    def _assert_clean(self, module):
        with tempfile.TemporaryDirectory() as tmp:
            proc, attempts = _run_under_netblock([str(HERE / (module + ".py"))], tmp)
        self.assertEqual(
            [], attempts,
            "%s opened %d connection(s) with %s unset, so the ordinary suite "
            "is still load testing production: %s"
            % (module, len(attempts), live_host.ENV, _describe(attempts)))
        # A module that reaches nothing because it CRASHED has also reached
        # nothing, and would pass the assertion above forever.
        self.assertEqual(
            0, proc.returncode,
            "%s exited %d rather than reporting skips. A module that dies on "
            "import reaches no host either, and would satisfy this guard while "
            "testing nothing.\n%s" % (module, proc.returncode, proc.stderr[-1500:]))

    def test_dedup_live(self):
        self._assert_clean("test_dedup_live")

    def test_secondary_surface_consistency(self):
        self._assert_clean("test_secondary_surface_consistency")

    def test_subscriber_routes_live(self):
        self._assert_clean("test_subscriber_routes_live")

    def test_the_skip_says_it_did_not_run(self):
        """A skipped live test must not read as a pass.

        unittest prints a skip reason and nothing else, so the reason is the
        only place this can be said. It has to say it in words a person
        scanning output for trouble will catch.
        """
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = _run_under_netblock(
                [str(HERE / "test_subscriber_routes_live.py"), "-v"], tmp)
        out = proc.stdout + proc.stderr
        self.assertIn("UNKNOWN, NOT RUN", out,
                      "a live test was skipped without saying that nothing "
                      "about the live surface was checked:\n" + out[-1500:])


class TheAccidentalCallerStaysFixed(unittest.TestCase):
    """test_headline_containment reached /corrections out of an invariant's
    FAIL branch: sixteen connections from tests that are offline unit tests by
    intent. It is not registered as a live module and must reach nothing."""

    def test_the_containment_guard_reaches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, attempts = _run_under_netblock(
                [str(HERE / "test_headline_containment.py")], tmp)
        self.assertEqual(
            [], attempts,
            "the containment guard is reading the live site again from a FAIL "
            "branch. An invariant reads the live corrections log only when it "
            "is reading live data (Ctx.disclosed); an injected transport must "
            "resolve to 'not consulted'. Attempts: %s" % _describe(attempts))
        self.assertEqual(0, proc.returncode, proc.stderr[-1500:])


class EveryFetcherIsRegistered(unittest.TestCase):
    """Catches the NEXT one, which no runtime check over a fixed list can.

    Running all 280 modules under the blocker would cost more than the suite
    it is guarding, so the breadth half is static: a module that builds a
    request to the deployed site has to be in `live_host.LIVE_MODULES`. The
    detector is proven on a known instance below, because a static scan that
    has only ever returned nothing shares its target's blind spot.
    """

    # The request verbs, matched against the end of the dotted name called.
    FETCH_NAMES = ("urllib.request.urlopen", "urlopen", "requests.get",
                   "requests.post", "requests.head", "session.get")
    LIVE_HOST = re.compile(r"https?://(?:www\.)?asktherecruiter\.com")

    @staticmethod
    def _dotted(node):
        """The dotted name of a call target, or "" for anything else."""
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        elif parts:
            return ""
        return ".".join(reversed(parts))

    @classmethod
    def fetchers(cls, sources):
        """Module names that read the deployed site, directly or through a door.

        PARSED, NOT GREPPED, and the first version of this was grepped and was
        wrong within the hour. Both codebases write enormous rationale prose
        that quotes code verbatim, so a regex over the source matched the words
        `reader_freshness.check()` inside a DOCSTRING in
        test_deploy_reaches_readers and reported a module that opens no
        connection at all. That is the same defect `style_check.py` carries a
        whole comment stripper for, and the same one the header of
        test_secondary_surface_consistency warns about: a checker that reads
        commentary grades the commentary. An AST sees calls, and a docstring is
        not a call.

        TWO detectors, because one of them has a hole the size of the actual
        defect. The first looks for a request in a module that also names the
        live host in a string, which catches
        test_secondary_surface_consistency. It does NOT catch test_dedup_live
        or test_subscriber_routes_live, whose source contains neither a
        hostname nor a request: they call an entry point that opens the
        connection three modules deeper. live_host.LIVE_DOORS names those, and
        a door is only a door when it is called with NO arguments, because the
        same call with an injected transport is a stub.
        """
        out = set()
        for name, text in sources.items():
            try:
                # Other modules' invalid escape sequences are their own
                # SyntaxWarning to raise, not this scan's noise to print.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    tree = ast.parse(text)
            except SyntaxError:  # not ours to judge; the suite will say so
                continue
            names_host = any(
                isinstance(n, ast.Constant) and isinstance(n.value, str)
                and cls.LIVE_HOST.search(n.value)
                for n in ast.walk(tree))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                called = cls._dotted(node.func)
                if not called:
                    continue
                if names_host and any(called == f or called.endswith("." + f)
                                      for f in cls.FETCH_NAMES):
                    out.add(name)
                    break
                if node.args or node.keywords:
                    continue  # an injected transport, not a live read
                tail = ".".join(called.split(".")[-2:])
                if tail in live_host.LIVE_DOORS:
                    out.add(name)
                    break
        return out

    def _sources(self):
        return {p.stem: p.read_text(encoding="utf-8")
                for p in sorted(HERE.glob("test_*.py"))
                if p.stem != Path(__file__).stem}

    def test_the_detector_catches_a_known_fetcher(self):
        """The positive control for the static half."""
        bait = ('SITE = "https://asktherecruiter.com/blog/"\n'
                'import urllib.request\n'
                'def go(): return urllib.request.urlopen(SITE)\n')
        self.assertIn("test_bait", self.fetchers({"test_bait": bait}),
                      "the detector does not recognise a plain fetch of the "
                      "live host, so its clean result means nothing")

    def test_the_detector_catches_a_fetch_through_a_door(self):
        """The positive control for the half that matters most.

        This is the shape the direct scan misses entirely: no hostname, no
        request, and twenty four connections a run.
        """
        bait = ("import data_integrity\n"
                "def setUp(self):\n"
                "    self._report = data_integrity.check_all()\n")
        self.assertIn("test_bait", self.fetchers({"test_bait": bait}),
                      "the detector does not recognise a live read made "
                      "through an entry point, which is how two of the three "
                      "known modules reach the site")

    def test_an_injected_transport_is_not_a_door(self):
        """The same call with a stub is how the OFFLINE tests in those very
        modules already work. Flagging it would make the guard unpassable and
        the guard would be deleted."""
        bait = ("import data_integrity\n"
                "report = data_integrity.check_all(fetch=dead)\n")
        self.assertEqual(set(), self.fetchers({"test_bait": bait}))

    def test_a_commented_out_fetch_is_not_a_fetcher(self):
        """The other direction. A detector that fires on rationale prose in a
        codebase written like this one would be muted within a week."""
        bait = ('# We used to urllib.request.urlopen("https://asktherecruiter.com/")\n'
                '# and that is what took the site down.\n'
                'x = 1\n')
        self.assertEqual(set(), self.fetchers({"test_bait": bait}))

    def test_no_unregistered_module_fetches_the_live_host(self):
        unregistered = self.fetchers(self._sources()) - set(live_host.LIVE_MODULES)
        self.assertEqual(
            set(), unregistered,
            "these modules build a request to the deployed site and are not "
            "registered in live_host.LIVE_MODULES: %s. A test that reads "
            "production has to be opted in and gated on %s, or the suite goes "
            "back to load testing the live site on every push."
            % (sorted(unregistered), live_host.ENV))

    def test_the_registry_names_nothing_that_stopped_fetching(self):
        """A registry entry for a module that no longer fetches is a standing
        permission nobody needs, and the next reader will copy it."""
        stale = set(live_host.LIVE_MODULES) - self.fetchers(self._sources())
        self.assertEqual(
            set(), stale,
            "live_host.LIVE_MODULES still grants %s permission to read the "
            "deployed site, but they no longer build a request. Remove the "
            "entry." % sorted(stale))


if __name__ == "__main__":
    unittest.main()
