"""THE CONFIRM AND UNSUBSCRIBE LINKS RESOLVE, AND A 404 THERE IS RED.

WHY THIS FILE EXISTS.

On 2026-08-19 the live 404 log carried both subscriber-facing paths:

    /blog/ai-layoff-tracker/confirm/<token>       2 hits
    /blog/ai-layoff-tracker/unsubscribe/<token>   2 hits

Those are the only two links a reader is ever given, and this repo already had
tests for both. `test_digest_link_identity.py` drives the real handlers through
a PHP harness, so it proves the code is right. It cannot prove the DEPLOYED
site answers, and that is the half that was missing. Every dashboard read green
throughout: the send reports success, the relay credential verifies, the health
row is fine, and a confirmation nobody completes reads as `0 sent of 0
eligible`, which is true and says nothing.

A dead unsubscribe is a compliance failure rather than a bug. The
`List-Unsubscribe-Post` header promises Gmail and Yahoo a working POST
endpoint. Mail people cannot stop receiving produces spam complaints instead
of unsubscribes, and complaint rate is what ends a sending domain.

WHAT IS PINNED HERE.

  * the classifier calls a 404 a FAIL and an unreachable host UNKNOWN. A live
    check that cannot reach the site must not read as a clean bill.
  * the probe token can never be a subscriber's, so the one-click POST can be
    fired at production without writing to anybody's row.
  * the dispatcher is still registered on `parse_request`, which is what makes
    the route correct on the first request after an FTP upload rather than on
    the first request after a rewrite flush.
  * no handler emits a 404 for a bad token, which is what makes a 404 in the
    log decidable: it means the route did not resolve, never that the token
    was rejected.
  * and the LIVE routes answer. Unreachable SKIPS loudly; a 404 FAILS.

The live half skips rather than passes when the site cannot be reached, and
`ops_status.py [1c]` makes the opposite call on the same result, reporting
UNKNOWN rather than green. A dashboard that skips reads as a clean bill.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import subscriber_routes
from subscriber_routes import FAIL, PASS, UNKNOWN

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLUGIN = REPO / "wordpress-plugin" / "ai-layoff-tracker"
SUBSCRIBE = (PLUGIN / "includes" / "subscribe.php").read_text(encoding="utf-8")
OPS_STATUS = (REPO / "railway" / "ops_status.py").read_text(encoding="utf-8")


class ProbeTokenCannotBeASubscriber(unittest.TestCase):
    """The POST is fired at production, so the token has to belong to nobody."""

    def test_token_is_never_valid_hex(self):
        # Real tokens are bin2hex(random_bytes(32)): 64 lowercase hex chars.
        self.assertIn("bin2hex(random_bytes(32))", SUBSCRIBE,
                      "token generation changed; re-derive the probe alphabet")
        for _ in range(200):
            token = subscriber_routes.probe_token()
            self.assertEqual(64, len(token))
            self.assertFalse(re.fullmatch(r"[0-9a-f]{64}", token),
                             f"probe token could collide with a real one: {token}")

    def test_each_run_draws_a_fresh_token(self):
        # A constant probe token is a constant cache key, and a shared cache
        # holding one verdict would mask the next regression.
        self.assertNotEqual(subscriber_routes.probe_token(),
                            subscriber_routes.probe_token())


class TheClassifierCannotSmoothOverAFailure(unittest.TestCase):
    """A 404 is FAIL, an unreached host is UNKNOWN, and neither is a pass."""

    def _check_against(self, responses):
        calls = []

        def fake(url, method="GET", data=None, timeout=None):
            calls.append((method, url))
            key = (method, "unsubscribe" if "unsubscribe" in url or "unsub" in url
                   else "confirm")
            # The healthy answers, so a case only has to state what it changes.
            healthy = ((200, "", b"Unsubscribed.") if method == "POST"
                       else (302, "/blog/ai-layoff-tracker/", b""))
            value = responses.get(key, healthy)
            if isinstance(value, Exception):
                raise value
            return value

        original = subscriber_routes._request
        subscriber_routes._request = fake
        try:
            return subscriber_routes.check(), calls
        finally:
            subscriber_routes._request = original

    def test_a_404_on_confirm_fails(self):
        result, _ = self._check_against({("GET", "confirm"): (404, "", b"")})
        self.assertEqual(FAIL, result.verdict)
        self.assertIn("404", result.detail)

    def test_a_404_on_the_one_click_post_fails(self):
        result, _ = self._check_against({("POST", "unsubscribe"): (404, "", b"")})
        self.assertEqual(FAIL, result.verdict)

    def test_a_redirect_on_the_one_click_post_fails(self):
        # RFC 8058: a provider wants a bare 2xx. It need not follow a redirect
        # and may record one as a failed unsubscribe against the domain.
        result, _ = self._check_against(
            {("POST", "unsubscribe"): (302, "/blog/ai-layoff-tracker/", b"")})
        self.assertEqual(FAIL, result.verdict)

    def test_a_get_that_unsubscribes_fails(self):
        # The 2026-08-17 defect: scanners follow relay-rewritten links, so a
        # GET that writes produces confirmed and unsubscribed a minute apart.
        result, _ = self._check_against(
            {("GET", "unsubscribe"): (200, "", b"Unsubscribed.")})
        self.assertEqual(FAIL, result.verdict)

    def test_an_unreachable_host_is_unknown_not_pass(self):
        result, _ = self._check_against(
            {("GET", "confirm"): OSError("connection refused")})
        self.assertEqual(UNKNOWN, result.verdict)
        self.assertFalse(result.ok)
        self.assertIn("NOT a pass", result.detail)

    def test_the_healthy_shape_passes_and_probes_every_route(self):
        result, calls = self._check_against({})
        self.assertEqual(PASS, result.verdict, result.detail)
        self.assertIn("POST", [method for method, _ in calls],
                      "the RFC 8058 one-click endpoint was never probed")
        for verb in ("confirm", "unsubscribe"):
            self.assertTrue(
                any(f"/ai-layoff-tracker/{verb}/" in url for _, url in calls),
                f"the public {verb} route was never probed")
        self.assertTrue(any("admin-post.php" in url for _, url in calls),
                        "the pre-2.20.77 links are in real inboxes and must be probed")


class TheRouteIsStillReachableByConstruction(unittest.TestCase):
    """Two properties of subscribe.php that make a live 404 decidable."""

    def test_the_dispatcher_runs_on_parse_request(self):
        # A rewrite rule only exists once the table has been flushed, and FTP
        # deploys here bypass every hook that would flush it. The window where
        # the rule is missing is a window where a real reader's confirmation
        # link 404s, and that reader is not coming back.
        self.assertRegex(
            SUBSCRIBE,
            r"add_action\(\s*'parse_request'\s*,\s*'alt_digest_public_route_dispatch'",
            "the public confirm/unsubscribe dispatcher is no longer registered")
        self.assertNotRegex(
            SUBSCRIBE, r"add_rewrite_rule\([^)]*(?:confirm|unsubscribe)",
            "these routes must not depend on a rewrite flush")

    def test_no_handler_answers_a_bad_token_with_a_404(self):
        # This is what lets a 404 in the log be read as "the route did not
        # resolve" rather than "the token was rejected". The two are different
        # defects with different fixes.
        for match in re.finditer(r"'response'\s*=>\s*(\d+)", SUBSCRIBE):
            self.assertLess(int(match.group(1)), 400,
                            "a subscriber handler now answers with an error status; "
                            "a 404 in the log stops being decidable")


class OpsStatusWatchesTheseRoutes(unittest.TestCase):
    """A subscriber-facing 404 should be as loud as a stale deploy."""

    def test_section_1c_exists_and_routes_a_failure_to_a_human(self):
        self.assertIn("[1c] SUBSCRIBER ROUTES", OPS_STATUS)
        self.assertIn("import subscriber_routes", OPS_STATUS)
        self.assertIn("a subscriber-facing email route is not answering", OPS_STATUS)


class TheLiveRoutesAnswer(unittest.TestCase):
    """The half no harness can stand in for: the DEPLOYED site.

    Unreachable skips. A 404 does not.
    """

    def test_live(self):
        result = subscriber_routes.check()
        if result.verdict == UNKNOWN:
            self.skipTest(f"site not reachable from here, NOT passing: {result.detail}")
        self.assertEqual(PASS, result.verdict, result.detail)


if __name__ == "__main__":
    unittest.main()
