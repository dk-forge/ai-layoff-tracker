"""Bounce and complaint handling under Brevo, which does not sign anything.

WHY THIS FILE EXISTS. /digest-webhook verified a Svix signature and dispatched
on Resend's event names (`email.bounced`, `email.complained`). The provider is
now Brevo, which speaks neither. Under Brevo the route therefore processed no
bounce and no complaint at all. It failed closed, which is safe, but the
consequence is not: hard bounces keep being retried and spam complaints keep
being mailed, and a relay suspends an account that goes past roughly 5% bounces
or 0.1% complaints. "Unattended" quietly becomes "suspended".

WHAT BREVO ACTUALLY OFFERS, verified against its own documentation on
2026-08-15 and not assumed. Brevo does NOT sign webhooks: no HMAC, no signing
header, no JWT. "Secure webhook calls" offers a bearer token, arbitrary custom
headers, basic-auth-in-the-URL, and IP allowlisting. So the strongest
authentication available is a shared secret in a header, and these tests pin
that it is present, constant-time, fails closed, and is never read from a URL.

THESE TESTS RUN THE PHP. They do not grep it. A mapping table is exactly the
kind of code that reads correct and behaves wrong, and the specific mistake
this file is guarding against - a substring test that catches `soft_bounce`
along with `hard_bounce` - is invisible to a reader and obvious to a run.

Point ALT_DIGEST_API_PATH at another copy of digest-api.php to run these
against a different tree; that is how they were confirmed RED before the fix
(18 of these 29 fail on the pre-change file).

NOT tests/fixtures/digest_harness.php, on purpose. That one exists for
subscribe.php and gives it a SQLite-backed $wpdb, which is right for testing
what a query returns. The question here is different and simpler: did anything
write to the subscriber table AT ALL. A recording fake answers that in one
assertion, where a real table would have it inferred from a row's after-state,
and "a soft bounce wrote nothing" is the single most important claim in this
file.
"""
import json
import os
import re
import subprocess
import unittest

HERE = os.path.dirname(__file__)
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
API = os.environ.get("ALT_DIGEST_API_PATH") or os.path.join(
    PLUGIN, "includes", "digest-api.php")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


PHP = _php()

TOKEN = "brevo_wh_9f2c41d8a77b4e5aa1c6"

# A captured-shape Brevo transactional event. The field names and the event
# names are Brevo's own (event, email, id, date, ts, message-id, ts_event,
# subject, tags), not invented ones.
def _event(name, email="reader@example.com", **over):
    base = {
        "event": name,
        "email": email,
        "id": 3241093,
        "date": "2026-08-15 09:14:22",
        "ts": 1786958062,
        "message-id": "<202608150914.71460218231@relay.sendinblue.com>",
        "ts_event": 1786958062,
        "subject": "[AskTheRecruiter] Weekly tracker digest",
        "tag": "digest",
        "tags": ["digest"],
        "sending_ip": "77.32.148.22",
        "template_id": 0,
    }
    if name in ("hard_bounce", "soft_bounce", "blocked", "invalid_email"):
        base["reason"] = ("550 5.1.1 <reader@example.com>: Recipient address "
                          "rejected: User unknown in virtual mailbox table")
    base.update(over)
    return base


# The harness includes the REAL digest-api.php under stub WordPress functions
# and reports, as JSON, the HTTP status, the response body, and every write
# that reached the subscriber table.
HARNESS = r"""<?php
define('ABSPATH', '/tmp/wp/');
define('HOUR_IN_SECONDS', 3600);
define('DAY_IN_SECONDS', 86400);

$SCENARIO = json_decode(file_get_contents($argv[2]), true);
$GLOBALS['WRITES'] = array();
$GLOBALS['OPTIONS'] = isset($SCENARIO['options']) ? $SCENARIO['options'] : array();

class WP_REST_Response {
    public $data; public $status;
    public function __construct($d, $s = 200) { $this->data = $d; $this->status = $s; }
}
class WP_REST_Request {
    private $h; private $b;
    public function __construct($h, $b) {
        $this->h = array(); $this->b = $b;
        foreach ($h as $k => $v) { $this->h[strtolower($k)] = $v; }
    }
    public function get_header($k) {
        $k = strtolower(str_replace('_', '-', $k));
        return isset($this->h[$k]) ? $this->h[$k] : null;
    }
    public function get_body() { return $this->b; }
    public function get_json_params() { return json_decode($this->b, true); }
    public function get_param($k) { return null; }
}

function add_action() {}
function get_option($k, $d = false) {
    return array_key_exists($k, $GLOBALS['OPTIONS']) ? $GLOBALS['OPTIONS'][$k] : $d;
}
function update_option($k, $v, $a = true) { $GLOBALS['OPTIONS'][$k] = $v; return true; }
function is_email($e) { return (bool) filter_var($e, FILTER_VALIDATE_EMAIL); }
function sanitize_email($e) { return trim((string) $e); }
function sanitize_key($k) { return strtolower(preg_replace('/[^a-z0-9_\-]/i', '', (string) $k)); }
function alt_subscribers_table() { return 'wp_alt_subscribers'; }
function alt_digest_sends_table() { return 'wp_alt_digest_sends'; }
function alt_digest_links_table() { return 'wp_alt_digest_links'; }
function alt_digest_table_present($t) { return true; }

/** The list, as a fixture. Anything not named here is not a subscriber. */
function alt_digest_get_by_email($email) {
    foreach ($GLOBALS['SCENARIO']['subscribers'] as $row) {
        if (strcasecmp($row['email'], $email) === 0) return $row;
    }
    return null;
}

class FakeWpdb {
    public $insert_id = 0;
    public function update($table, $data, $where) {
        $GLOBALS['WRITES'][] = array('table' => $table, 'data' => $data, 'where' => $where);
        return 1;
    }
    public function insert($t, $d) { return 1; }
    public function query($q) { return 0; }
    public function prepare($q) { return $q; }
}
$GLOBALS['SCENARIO'] = $SCENARIO;
$wpdb = new FakeWpdb();

if (!empty($SCENARIO['svix_secret'])) {
    define('ALT_DIGEST_WEBHOOK_SECRET', $SCENARIO['svix_secret']);
}
if (isset($SCENARIO['brevo_token'])) {
    define('ALT_DIGEST_BREVO_WEBHOOK_TOKEN', $SCENARIO['brevo_token']);
}

require $argv[1];

$request = new WP_REST_Request($SCENARIO['headers'], $SCENARIO['raw']);
$response = alt_api_digest_webhook($request);
echo json_encode(array(
    'status' => $response->status,
    'body'   => $response->data,
    'writes' => $GLOBALS['WRITES'],
));
"""


def _run(raw, headers=None, brevo_token=TOKEN, svix_secret="",
         subscribers=None):
    """POST `raw` at the real route and report what it did."""
    import tempfile
    if subscribers is None:
        subscribers = [{"id": 41, "email": "reader@example.com",
                        "status": "confirmed"}]
    scenario = {
        "raw": raw if isinstance(raw, str) else json.dumps(raw),
        "headers": headers or {},
        "brevo_token": brevo_token,
        "svix_secret": svix_secret,
        "subscribers": subscribers,
        "options": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        hpath = os.path.join(tmp, "harness.php")
        spath = os.path.join(tmp, "scenario.json")
        with open(hpath, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        with open(spath, "w", encoding="utf-8") as fh:
            json.dump(scenario, fh)
        proc = subprocess.run([PHP, hpath, API, spath],
                              capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise AssertionError(
            "the webhook harness did not run.\nstdout: %s\nstderr: %s"
            % (proc.stdout[-3000:], proc.stderr[-3000:]))
    try:
        return json.loads(proc.stdout[proc.stdout.index("{"):])
    except ValueError:
        raise AssertionError("harness printed non-JSON:\n" + proc.stdout[-3000:])


def _auth(token=TOKEN):
    return {"Authorization": "Bearer " + token,
            "Content-Type": "application/json"}


@unittest.skipUnless(PHP, "php binary not available")
class BrevoSuppression(unittest.TestCase):
    """The four outcomes, run end to end through the real handler."""

    def test_a_hard_bounce_stops_sending_to_that_address(self):
        got = _run(_event("hard_bounce"), _auth())
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 1,
                         "a hard bounce did not suppress the address, so the "
                         "next digest retries a mailbox the relay has already "
                         "told us does not exist: %r" % (got,))
        self.assertEqual(len(got["writes"]), 1, got["writes"])
        write = got["writes"][0]
        self.assertEqual(write["data"]["status"], "bounced",
                         "a hard bounce must record 'bounced', which is a dead "
                         "mailbox, and not 'unsubscribed', which is a person's "
                         "decision: %r" % (write["data"],))
        self.assertEqual(write["where"], {"id": 41})

    def test_a_soft_bounce_changes_nothing_at_all(self):
        """The expensive mistake. A full inbox is not a reason to delete
        anyone, and `strpos($event, 'bounce')` catches this one too."""
        got = _run(_event("soft_bounce"), _auth())
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 0, got)
        self.assertEqual(got["writes"], [],
                         "a SOFT bounce wrote to the subscriber table. Someone "
                         "whose mailbox was full for an hour has been dropped "
                         "from the list: %r" % (got["writes"],))

    def test_a_spam_complaint_unsubscribes(self):
        got = _run(_event("spam"), _auth())
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 1, got)
        self.assertEqual(got["writes"][0]["data"]["status"], "unsubscribed",
                         "a spam complaint is a withdrawal of consent and must "
                         "record 'unsubscribed', not 'bounced': %r" % (got,))

    def test_an_unsubscribe_through_brevos_own_link_unsubscribes(self):
        got = _run(_event("unsubscribed"), _auth())
        self.assertEqual(got["body"]["stopped"], 1, got)
        self.assertEqual(got["writes"][0]["data"]["status"], "unsubscribed")

    def test_an_invalid_email_is_recorded_as_a_bounce(self):
        """Brevo could not route the address at all. That is the same fact as
        a hard bounce and is deliberately recorded as the same status."""
        got = _run(_event("invalid_email"), _auth())
        self.assertEqual(got["body"]["stopped"], 1, got)
        self.assertEqual(got["writes"][0]["data"]["status"], "bounced")

    def test_the_events_that_must_never_suppress(self):
        """`blocked` is Brevo declining to send to an address on ITS blocklist.
        That is a consequence of an earlier suppression, not new evidence, and
        acting on it would let the relay's state overwrite ours."""
        for name in ("delivered", "request", "deferred", "blocked", "error",
                     "opened", "unique_opened", "click", "proxy_open",
                     "unique_proxy_open"):
            got = _run(_event(name), _auth())
            self.assertEqual(got["writes"], [],
                             "the %r event wrote to the subscriber table" % name)
            self.assertEqual(got["body"]["stopped"], 0, name)

    def test_engagement_events_are_not_stored_anywhere(self):
        """The published privacy note says we cannot tell whether you opened an
        email. An open event must therefore leave no trace, not a counted one."""
        got = _run(_event("opened", link="https://asktherecruiter.com/blog/x",
                          user_agent="Mozilla/5.0", device_used="DESKTOP"),
                   _auth())
        self.assertEqual(got["writes"], [], got["writes"])
        self.assertNotIn("user_agent", json.dumps(got["body"]))
        self.assertEqual(got["body"], {"ok": True, "stopped": 0},
                         "the response to an open event carries more than a "
                         "count: %r" % (got["body"],))

    def test_an_address_that_is_not_on_the_list_changes_nothing(self):
        got = _run(_event("hard_bounce", email="stranger@example.net"), _auth())
        self.assertEqual(got["body"]["stopped"], 0, got)
        self.assertEqual(got["writes"], [])

    def test_a_row_already_unsubscribed_is_not_written_again(self):
        got = _run(_event("hard_bounce"), _auth(), subscribers=[
            {"id": 41, "email": "reader@example.com", "status": "unsubscribed"}])
        self.assertEqual(got["body"]["stopped"], 0, got)
        self.assertEqual(got["writes"], [],
                         "re-suppressing an already-unsubscribed row would move "
                         "unsubscribed_at forward and postpone the 30 day erase")

    def test_the_response_never_carries_an_address(self):
        got = _run(_event("hard_bounce"), _auth())
        self.assertNotIn("reader@example.com", json.dumps(got["body"]),
                         "the webhook response echoes the address back, which "
                         "makes this route an address oracle")


@unittest.skipUnless(PHP, "php binary not available")
class BrevoAuthentication(unittest.TestCase):
    """Brevo signs nothing, so the shared token is the entire boundary."""

    def test_an_unauthenticated_request_is_refused(self):
        got = _run(_event("hard_bounce"), {"Content-Type": "application/json"})
        self.assertEqual(got["status"], 401,
                         "a Brevo-shaped POST with no credential was ACTED ON. "
                         "This endpoint is public, so that is a stranger's "
                         "button for unsubscribing any address they can guess")
        self.assertEqual(got["writes"], [])

    def test_a_wrong_token_is_refused(self):
        got = _run(_event("hard_bounce"), _auth("brevo_wh_wrongwrongwrong"))
        self.assertEqual(got["status"], 401, got)
        self.assertEqual(got["writes"], [])

    def test_a_token_prefix_is_not_enough(self):
        """A prefix match, or a comparison that stops at the first differing
        byte, turns the token into something guessable one byte at a time."""
        got = _run(_event("hard_bounce"), _auth(TOKEN[:-1]))
        self.assertEqual(got["status"], 401, got)
        got = _run(_event("hard_bounce"), _auth(TOKEN + "x"))
        self.assertEqual(got["status"], 401, got)

    def test_it_fails_closed_when_no_token_is_configured(self):
        """The same rule the Svix path already follows: no secret, no action."""
        got = _run(_event("hard_bounce"), _auth(), brevo_token="")
        self.assertEqual(got["status"], 401,
                         "with no token configured the route accepted a bounce. "
                         "An unconfigured install must refuse everything, not "
                         "accept everything")
        self.assertEqual(got["writes"], [])

    def test_the_token_is_accepted_in_a_custom_header_too(self):
        """Apache with PHP as CGI drops the Authorization header before PHP
        sees it, and on that host a bearer-only check 401s in a way that looks
        exactly like a wrong token. Brevo can send an arbitrary header, so the
        operator has a second route that survives."""
        got = _run(_event("hard_bounce"),
                   {"X-Alt-Webhook-Token": TOKEN,
                    "Content-Type": "application/json"})
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 1, got)

    def test_a_wrong_custom_header_token_is_refused(self):
        got = _run(_event("hard_bounce"),
                   {"X-Alt-Webhook-Token": "nope", "Content-Type": "application/json"})
        self.assertEqual(got["status"], 401, got)

    def test_the_comparison_is_constant_time(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        fn = src[src.index("function alt_digest_brevo_authenticated"):]
        fn = fn[:fn.index("\n}")]
        self.assertIn("hash_equals(", fn,
                      "the token is compared with == or ===, which returns as "
                      "soon as two bytes differ and leaks the token's prefix")
        # The comparison must be hash_equals and nothing else. Guarding only on
        # the presence of hash_equals would pass a function that also short
        # circuits on a plain == somewhere above it.
        loose = re.findall(r"\$(?:token|candidate|custom|auth)\s*={2,3}\s*\$",
                           fn)
        self.assertEqual(loose, [],
                         "the token is compared against another variable with "
                         "== or ===, which returns as soon as two bytes differ: "
                         "%r" % (loose,))

    def test_the_token_is_never_read_from_the_url(self):
        """Every guide recommends putting the secret in the path or the query
        string. Bluehost writes the full request line to an access log, so that
        is a secret written to a file we do not control, permanently."""
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        fn = src[src.index("function alt_digest_brevo_authenticated"):]
        fn = fn[:fn.index("\n}")]
        for forbidden in ("get_param", "$_GET", "get_query_params", "REQUEST_URI"):
            self.assertNotIn(forbidden, fn,
                             "the Brevo token is read from the URL via %r, so "
                             "it lands in the host's access log" % forbidden)


@unittest.skipUnless(PHP, "php binary not available")
class ProviderSelection(unittest.TestCase):
    """Which provider is talking is read off the request, not configured."""

    def test_the_svix_path_still_verifies_and_still_suppresses(self):
        """Resend remains a supported transport. A genuine Svix-signed
        email.bounced must still work, byte for byte as before."""
        import base64
        import hashlib
        import hmac
        import time
        secret_bytes = b"0123456789abcdef0123456789abcdef"
        secret = "whsec_" + base64.b64encode(secret_bytes).decode()
        raw = json.dumps({"type": "email.bounced",
                          "data": {"to": ["reader@example.com"],
                                   "bounce": {"type": "Permanent",
                                              "subType": "General"}}})
        msg_id, ts = "msg_2abcDEF", str(int(time.time()))
        sig = base64.b64encode(hmac.new(
            secret_bytes, f"{msg_id}.{ts}.{raw}".encode(), hashlib.sha256
        ).digest()).decode()
        got = _run(raw, {"svix-id": msg_id, "svix-timestamp": ts,
                         "svix-signature": "v1," + sig},
                   brevo_token="", svix_secret=secret)
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 1,
                         "the Svix path stopped working: %r" % (got,))
        self.assertEqual(got["writes"][0]["data"]["status"], "bounced")

    def test_a_bad_svix_signature_is_refused_and_does_not_fall_through(self):
        """A request that claims to be Svix is verified as Svix or refused. If
        a bad signature fell through to the Brevo path, the strong check would
        be optional: send Resend's body with a junk signature and no token."""
        raw = json.dumps({"type": "email.bounced",
                          "data": {"to": ["reader@example.com"]},
                          "event": "hard_bounce", "email": "reader@example.com"})
        got = _run(raw, {"svix-id": "msg_1", "svix-timestamp": "9999999999",
                         "svix-signature": "v1,notarealsignature",
                         "Authorization": "Bearer " + TOKEN},
                   svix_secret="whsec_" + "AAAA" * 8)
        self.assertEqual(got["status"], 401,
                         "a forged Svix signature fell through to the weaker "
                         "Brevo path and was acted on: %r" % (got,))
        self.assertEqual(got["writes"], [])

    def test_the_provider_is_not_chosen_by_configuration(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        fn = src[src.index("function alt_api_digest_webhook"):]
        fn = fn[:fn.index("\n}")]
        for forbidden in ("getenv", "DIGEST_TRANSPORT", "ALT_DIGEST_PROVIDER"):
            self.assertNotIn(forbidden, fn,
                             "the dispatcher picks a provider from %r. A "
                             "setting nobody remembers to change is how bounce "
                             "handling silently stops" % forbidden)
        self.assertIn("get_header", fn)

    def test_a_body_that_is_neither_provider_is_refused(self):
        for raw in ("", "not json", "[]", json.dumps({"hello": "world"}),
                    json.dumps({"type": "email.bounced",
                                "data": {"to": ["reader@example.com"]}})):
            got = _run(raw, _auth())
            self.assertEqual(got["status"], 401,
                             "a body of %r was not refused" % (raw[:60],))
            self.assertEqual(got["writes"], [])


@unittest.skipUnless(PHP, "php binary not available")
class BatchedDelivery(unittest.TestCase):
    """Brevo's optional batched mode. Its delivered shape is NOT documented,
    so all three plausible shapes are accepted: rejecting the one that turns
    out to be real would drop bounces silently, which is this whole defect."""

    def test_a_top_level_array_of_events_is_processed(self):
        got = _run([_event("hard_bounce"),
                    _event("soft_bounce", email="second@example.com"),
                    _event("spam", email="third@example.com")],
                   _auth(), subscribers=[
                       {"id": 41, "email": "reader@example.com", "status": "confirmed"},
                       {"id": 42, "email": "second@example.com", "status": "confirmed"},
                       {"id": 43, "email": "third@example.com", "status": "confirmed"}])
        self.assertEqual(got["status"], 200, got)
        self.assertEqual(got["body"]["stopped"], 2, got)
        by_id = {w["where"]["id"]: w["data"]["status"] for w in got["writes"]}
        self.assertEqual(by_id, {41: "bounced", 43: "unsubscribed"},
                         "the batch was not applied per event: %r" % (by_id,))

    def test_an_items_wrapped_batch_is_processed(self):
        got = _run({"items": [_event("hard_bounce")]}, _auth())
        self.assertEqual(got["body"]["stopped"], 1, got)


@unittest.skipUnless(PHP, "php binary not available")
class OneSuppressionPath(unittest.TestCase):
    """Two ways to stop sending is two ways to get one of them wrong."""

    def test_every_provider_goes_through_alt_digest_stop_sending(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        writers = [line for line in src.splitlines()
                   if "wpdb->update(" in line and "subscribers_table" in line]
        self.assertEqual(len(writers), 1,
                         "the subscriber table is updated from %d places. There "
                         "must be exactly one definition of 'stop sending to "
                         "this address': %r" % (len(writers), writers))
        stop = src[src.index("function alt_digest_stop_sending"):]
        stop = stop[:stop.index("\n}")]
        self.assertIn("wpdb->update(", stop,
                      "the one writer is no longer alt_digest_stop_sending")

    def test_both_providers_carry_the_same_30_day_erase_promise(self):
        """unsubscribed_at is what the retention purge reads. A suppression
        written without it is a row that is never erased."""
        got = _run(_event("hard_bounce"), _auth())
        self.assertIn("unsubscribed_at", got["writes"][0]["data"],
                      "a Brevo suppression carries no unsubscribed_at, so the "
                      "30 day purge will never reach it: %r" % (got["writes"],))
        self.assertIsNone(got["writes"][0]["data"]["confirm_token"])

    def test_the_brevo_mapping_is_an_exact_lookup_not_a_substring_test(self):
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        fn = src[src.index("function alt_digest_brevo_action"):]
        fn = fn[:fn.index("\n}")]
        self.assertNotIn("strpos(", fn,
                         "the event mapping uses strpos, which matches "
                         "'soft_bounce' against 'bounce' and deletes people "
                         "whose mailbox was briefly full")
        self.assertNotIn("str_contains(", fn)


class TheFileIsStillWellFormed(unittest.TestCase):

    @unittest.skipUnless(PHP, "php binary not available")
    def test_it_parses(self):
        proc = subprocess.run([PHP, "-l", API], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_the_no_signature_reality_is_written_down_not_implied(self):
        """A reader who assumes Brevo signs will think this endpoint is
        stronger than it is, and will not ask for the token to be rotated."""
        with open(API, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("BREVO DOES NOT SIGN ITS WEBHOOKS", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
