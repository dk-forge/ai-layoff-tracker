"""Email digest subscriptions (includes/subscribe.php): the guards that make
storing a stranger's email address defensible.

This is the site's FIRST feature holding personal data, so the invariants are
consent invariants, and each one is exercised against the REAL PHP handlers
(via tests/fixtures/digest_harness.php: WordPress stubs + a SQLite wpdb),
not against a reimplementation:

  * DOUBLE OPT-IN: a pending address receives exactly one email ever (the
    confirmation); a digest run while pending sends nothing.
  * Zero boxes ticked is refused, and no row is stored.
  * Unsubscribe is one click, works twice (idempotent), and nothing sends
    afterwards.
  * Tokens are 64 hex chars of random_bytes output, unique per row, and not
    derivable from the address; the address never appears in a URL.
  * The purge cron hard-deletes exactly what the privacy note promises:
    unsubscribed + never-confirmed rows past the retention window, and never
    a confirmed subscriber.
  * The mailer stamps a source-health row on COMPLETION with counts only.
"""
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_harness.php")
DIGEST_API = os.path.join(PLUGIN, "includes", "digest-api.php")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


def confirm_subject():
    """The confirmation email's subject, read out of the shipped source.

    Not repeated here as a literal: a test that hard-codes the words is a
    second definition of the highest-stakes string this system sends, and it
    goes green while the two disagree.
    """
    src = open(SUBSCRIBE, encoding="utf-8").read()
    m = re.search(r"function alt_digest_confirm_subject\(\)\s*\{\s*"
                  r"return\s*'([^']*)';", src)
    assert m, ("includes/subscribe.php has no alt_digest_confirm_subject() "
               "returning a single literal, so the confirmation subject is "
               "written at its call site and this test cannot read it")
    return m.group(1)


def single_literal(fn):
    """The one string a `function <fn>() { return '...'; }` returns.

    Same reasoning as confirm_subject() above: a test that writes the words out
    again is a second definition of a reader-facing string and goes green while
    the two disagree.
    """
    src = open(SUBSCRIBE, encoding="utf-8").read()
    m = re.search(r"function %s\(\)\s*\{\s*return\s*'([^']*)';" % re.escape(fn), src)
    assert m, ("includes/subscribe.php has no %s() returning a single literal" % fn)
    return m.group(1)


def list_names():
    """alt_digest_list_names(), read out of the shipped source.

    The change email and the confirmation panel both render these, so the test
    has to fail when a list is renamed in one place only.
    """
    src = open(SUBSCRIBE, encoding="utf-8").read()
    body = re.search(r"function alt_digest_list_names\(\)\s*\{(.+?)\n\}",
                     src, re.S)
    assert body, "includes/subscribe.php has no alt_digest_list_names()"
    pairs = re.findall(r"'(\w+)'\s*=>\s*'([^']*)'", body.group(1))
    assert len(pairs) == 3, "expected three lists, read %r" % (pairs,)
    return dict(pairs)


# Strip PHP comments with PHP's OWN tokenizer before matching source facts.
# A test that greps raw source proves nothing about behaviour: a sentence in a
# docblock saying a route is key gated matches exactly as well as the route
# being key gated, and this session found seven guards that passed for that
# class of reason. token_get_all cannot be fooled by prose.
_STRIP = (r'echo implode("", array_map(function ($t) { return is_array($t) '
          r'? (in_array($t[0], array(T_COMMENT, T_DOC_COMMENT)) ? "" : $t[1]) '
          r': $t; }, token_get_all(file_get_contents($argv[1]))));')


def _code_only(path):
    """The file's PHP source with every comment removed."""
    php = _php()
    if not php:
        return None
    proc = subprocess.run([php, "-r", _STRIP, "--", path],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout


def _php_relay_tracking(src):
    """The value of ALT_RELAY_TRACKING, read out of the PHP source.

    Parsed rather than executed because these assertions run with or without a
    PHP binary on the box, and a constant is the one thing a regex can read
    without lying about it. It is a `define(..., true|false)` on one line by
    construction; anything else here should fail loudly rather than default.
    """
    m = re.search(r"define\(\s*'ALT_RELAY_TRACKING'\s*,\s*(true|false)\s*\)", src)
    assert m, ("ALT_RELAY_TRACKING is not a one-line define in subscribe.php; "
               "the constant is the mirror of the provider dashboard and every "
               "reader-facing string is derived from it, so it must stay "
               "trivially readable")
    return m.group(1) == "true"


def _tracking_line_branch(src, relay_tracking_on):
    """The always-visible disclosure for one state of ALT_RELAY_TRACKING.

    The template now prints alt_digest_tracking_line() instead of literal
    prose, so a test that slices the template sees a function call. This slices
    the FUNCTION instead and returns the branch the constant selects.

    Split on the STRUCTURE (the close of the if block), never on a phrase from
    the copy. A literal split key is a copy of the copy, and it went stale the
    first time the wording changed: the helper then returned an empty string
    and the assertions below failed for a reason that had nothing to do with
    what the page says.
    """
    body = src[src.index("function alt_digest_tracking_line()"):]
    body = body[:body.index("\n}")]
    on_branch, sep, off_branch = body.partition("\n    }\n")
    assert sep, ("alt_digest_tracking_line() is no longer an if block followed "
                 "by a fallback return, so this helper cannot tell the two "
                 "branches apart")
    return on_branch if relay_tracking_on else off_branch


def _privacy_note_branch(src, relay_tracking_on):
    """The privacy note as a READER sees it, for one state of the constant.

    BOTH variants live in the file, inside an if/else, so slicing the whole
    <details> returns copy that is not on the page. That is not a nitpick: the
    opens-off assertions include a NOT-in, and a NOT-in against a slice holding
    the other branch can never fail. Drop the branch PHP will not run.
    """
    note = src[src.index('<details class="alt-digest-privacy"'):src.index("</details>")]
    head, sep, rest = note.partition("<?php if (ALT_RELAY_TRACKING) : ?>")
    if not sep:
        return note
    on_branch, _, rest2 = rest.partition("<?php else : ?>")
    off_branch, _, tail = rest2.partition("<?php endif; ?>")
    return head + (on_branch if relay_tracking_on else off_branch) + tail


def _load_ops_status():
    if RAILWAY not in sys.path:
        sys.path.insert(0, RAILWAY)
    import ops_status
    return ops_status


def _load_health_digest():
    """health_digest imports requests at module scope; the wiring under test is
    pure formatting, so stand a stub in rather than skip the guard entirely.

    The stub comes from tests/_requests_stub.py, which COMPLETES whatever is
    already in the process-global slot. This used to install its own partial
    stub only when the slot was empty, so in a full-suite run a warn test's
    `RequestException`-only stub got there first and every test below died on
    "module 'requests' does not have the attribute 'get'".
    """
    if RAILWAY not in sys.path:
        sys.path.insert(0, RAILWAY)
    here = os.path.abspath(HERE)
    if here not in sys.path:
        sys.path.insert(0, here)
    from _requests_stub import install as install_requests
    install_requests()
    import health_digest
    return health_digest


def _fake_json_response(payload):
    body = json.dumps(payload).encode()

    class _R:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    return _R()


class StaticGuards(unittest.TestCase):
    """Facts that must be true of the source itself."""

    @classmethod
    def setUpClass(cls):
        cls.src = open(SUBSCRIBE, encoding="utf-8").read()

    def test_module_is_loaded_by_the_plugin(self):
        boot = open(os.path.join(PLUGIN, "ai-layoff-tracker.php"), encoding="utf-8").read()
        self.assertIn("require_once ALT_PLUGIN_DIR . 'includes/subscribe.php';", boot)

    def test_table_is_installed_with_the_layoffs_schema(self):
        db = open(os.path.join(PLUGIN, "includes", "db.php"), encoding="utf-8").read()
        self.assertIn("alt_subscribers", db)
        self.assertIn("UNIQUE KEY email (email)", db)
        for col in ("consent_layoff", "consent_talent", "consent_articles",
                    "freq_layoff", "freq_talent", "confirm_token", "unsub_token",
                    "unsubscribed_at"):
            self.assertIn(col, db, f"subscriber schema is missing {col}")

    def test_tokens_come_from_random_bytes_and_compare_constant_time(self):
        self.assertIn("hash_equals(", self.src)
        # The token factory is random_bytes and nothing else; in particular it
        # never sees the address, so a token cannot be derived from it.
        factory = self.src[self.src.index("function alt_digest_new_token"):]
        factory = factory[:factory.index("\n}")]
        self.assertIn("random_bytes(32)", factory)
        self.assertNotIn("email", factory)
        # And the token columns are only ever fed by that factory.
        for m in re.finditer(r"'(?:confirm_token|unsub_token)'\s*=>\s*([^,\n]+)", self.src):
            self.assertRegex(m.group(1).strip(), r"^(alt_digest_new_token\(\)|null|\$confirm)$",
                             f"token column fed by something other than the factory: {m.group(1)}")

    def test_form_starts_with_every_consent_box_unticked(self):
        boxes = re.findall(r'<input type="checkbox"[^>]*>', self.src)
        self.assertEqual(len(boxes), 3, "the form offers exactly three consent boxes")
        for box in boxes:
            self.assertNotIn("checked", box, f"pre-ticked consent is not consent: {box}")
        # The single frequency default is weekly.
        self.assertRegex(self.src, r'value="weekly" checked')

    def test_no_tracking_pixels_in_any_composed_email(self):
        self.assertNotIn("<img", self.src.lower())

    def test_list_unsubscribe_headers_are_attached(self):
        self.assertIn("List-Unsubscribe:", self.src)
        self.assertIn("List-Unsubscribe=One-Click", self.src)

    def test_no_em_or_en_dashes(self):
        for ch in ("—", "–"):
            self.assertNotIn(ch, self.src)

    def test_signup_is_rate_limited_per_ip(self):
        self.assertIn("alt_digest_rate_", self.src)
        self.assertIn("REMOTE_ADDR", self.src)

    def test_form_renders_on_the_tracker_page(self):
        tpl = open(os.path.join(PLUGIN, "templates", "page-tracker.php"), encoding="utf-8").read()
        self.assertIn("alt_digest_subscribe_form", tpl)

    def test_health_registry_knows_the_mailer(self):
        """A mailer that dies silently must go red: it needs a ceiling in BOTH
        staleness maps and a label on the public health page."""
        railway = os.path.abspath(os.path.join(HERE, ".."))
        ops = open(os.path.join(railway, "ops_status.py"), encoding="utf-8").read()
        dig = open(os.path.join(railway, "health_digest.py"), encoding="utf-8").read()
        js = open(os.path.join(PLUGIN, "assets", "health.js"), encoding="utf-8").read()
        self.assertRegex(ops, r'"digest_mailer":\s*3')
        self.assertRegex(dig, r'"digest_mailer":\s*3')
        self.assertIn("digest_mailer:", js)

    def test_health_is_stamped_on_completion_not_before(self):
        """checked_at must be written AFTER the sends and the purge, so a
        fatal mid-run leaves the row stale instead of freshly green."""
        cron = self.src[self.src.index("function alt_digest_cron_run"):]
        cron = cron[:cron.index("\n}")]
        send_pos = cron.index("alt_digest_send")
        purge_pos = cron.index("alt_digest_purge")
        stamp_pos = cron.index("alt_source_health_record")
        self.assertGreater(stamp_pos, send_pos)
        self.assertGreater(stamp_pos, purge_pos)

    def test_the_articles_list_has_a_composer_behind_it(self):
        """Every box the form offers must be able to produce an email.

        The articles box shipped with the form and had no sender for months:
        somebody who ticked only that one confirmed their address, was never
        counted as a recipient, and received nothing, forever."""
        self.assertIn("function alt_digest_compose_articles(", self.src)
        sender = self.src[self.src.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertIn("alt_digest_compose_articles(", sender)

    def test_the_articles_section_reads_the_sites_own_posts(self):
        fn = self.src[self.src.index("function alt_digest_compose_articles("):]
        fn = fn[:fn.index("\n}")]
        self.assertIn("get_posts(", fn)
        self.assertIn("'post_type'", fn)
        self.assertIn("'publish'", fn)

    def test_an_empty_window_composes_nothing_rather_than_a_filler_line(self):
        fn = self.src[self.src.index("function alt_digest_compose_articles("):]
        fn = fn[:fn.index("\n}")]
        code = re.sub(r"/\*.*?\*/", "", fn, flags=re.S)
        code = re.sub(r"//[^\n]*", "", code)
        self.assertIn("return null;", code)
        for filler in ("No articles", "no articles", "Nothing new",
                       "no new posts", "0 articles"):
            self.assertNotIn(filler, code,
                             f"an absent section must be absent, not {filler!r}")


@unittest.skipUnless(_php(), "php not installed")
class StatsRouteShape(unittest.TestCase):
    """The stats route and the click redirect, asserted against COMMENT-STRIPPED
    source so a docblock can never stand in for a call."""

    @classmethod
    def setUpClass(cls):
        cls.code = _code_only(SUBSCRIBE)

    def _fn(self, name):
        start = self.code.index("function " + name)
        return self.code[start:self.code.index("\n}", start)]

    def test_stats_route_is_registered_in_the_layoffs_namespace(self):
        self.assertRegex(
            self.code,
            r"register_rest_route\(\s*'layoffs/v1'\s*,\s*'/subscriber-stats'",
            "the benchmark panel probes REST; the route must live in layoffs/v1")

    def test_stats_route_is_key_gated_the_same_way_the_others_are(self):
        block = self.code[self.code.index("'/subscriber-stats'"):]
        block = block[:block.index("));")]
        self.assertIn("alt_api_permission", block,
                      "the stats route must reuse the plugin's keyed permission callback")
        self.assertNotIn("__return_true", block, "counts about subscribers are not public")
        self.assertIn("__return_false", block, "and it must fail closed with no key")
        self.assertRegex(block, r"'methods'\s*=>\s*'GET'", "read only: GET and nothing else")

    def test_the_click_route_accepts_no_destination_parameter(self):
        """The whole open-redirect guard rests on this: there is no input the
        caller can put a URL into. Only an integer id and a hex hash."""
        body = self._fn("alt_api_digest_click")
        params = set(re.findall(r"get_param\(\s*'([^']+)'\s*\)", body))
        self.assertEqual(params, {"s", "l"},
                         f"the redirect reads params {sorted(params)}; a destination "
                         f"parameter is exactly what makes an open redirect")
        self.assertRegex(body, r"preg_match\(\s*'/\^\[a-f0-9\]\{32\}\\?\$/'",
                         "the hash parameter must be shape-checked before it reaches SQL")

    def test_every_redirect_target_is_the_stored_row_or_our_own_home(self):
        body = self._fn("alt_api_digest_click")
        targets = re.findall(r"wp_safe_redirect\(\s*([^,\)]+)", body)
        self.assertTrue(targets, "the handler must actually redirect")
        for t in targets:
            self.assertIn(t.strip(), ("$home", "$url"),
                          f"redirect target {t!r} is neither the stored row nor home")
        self.assertIn("alt_digest_link_allowed(", body,
                      "the stored destination must be re-validated at redemption")

    def test_the_host_guard_rejects_by_allowlist_not_by_pattern(self):
        guard = self._fn("alt_digest_link_allowed")
        self.assertIn("in_array(strtolower($parts['host']), alt_digest_link_hosts(), true)", guard)
        # A substring or prefix test would pass example.test.evil.example.
        self.assertNotIn("strpos", guard)
        self.assertNotIn("str_contains", guard)

    def test_the_click_store_has_no_column_that_could_identify_a_visitor(self):
        db = open(os.path.join(PLUGIN, "includes", "db.php"), encoding="utf-8").read()
        block = db[db.index("alt_digest_links'"):]
        block = block[:block.index('$charset;");')]
        for banned in ("ip", "user_agent", "subscriber", "email", "token"):
            self.assertNotIn(banned, block.lower(),
                             f"the click store must not hold {banned}")
        self.assertIn("clicks INT UNSIGNED", block)

    def test_no_open_rate_pixel_and_the_reason_is_left_where_it_will_be_read(self):
        """Deliberately reads the COMMENTS: the requirement is that a future
        session finds the reasoning next to the code, not that a call exists."""
        src = open(SUBSCRIBE, encoding="utf-8").read()
        self.assertNotIn("<img", src.lower())
        reason = src[src.index("WHY THERE IS NO OPEN-RATE PIXEL"):]
        reason = reason[:2000].lower()
        self.assertIn("per-person", reason)
        self.assertIn("half", reason, "the inflation figure must be stated, not implied")
        for word in ("deliver", "click", "unsubscrib"):
            self.assertIn(word, reason, "the comment must name what IS measured instead")

    def test_the_privacy_note_tells_readers_about_the_click_counter(self):
        """Counting clicks without saying so would make the published privacy
        note false, which is worse than not counting."""
        src = open(SUBSCRIBE, encoding="utf-8").read()
        note = src[src.index("alt-digest-privacy"):src.index("</details>")]
        self.assertNotIn("no click tracking", note.lower())
        self.assertIn("counter", note.lower())
        self.assertIn("no IP address", note)

    def test_the_privacy_note_singles_out_the_confirmation_email(self):
        """Measured 2026-08-17: Brevo injects its open pixel into the
        confirmation email as well, and that message goes to a `pending` row,
        which by this file's own design has consented to NOTHING. It cannot be
        exempted (no per-message opt-out through wp_mail), so the only honest
        answer left is to say so. A note that describes tracking as something
        that happens to "an email" leaves a reader to assume it starts once
        they have agreed. Nothing in the repo can catch this drift on its own:
        our message embeds no image and assert_message_is_clean still passes,
        because the pixel is added after we hand the message over.

        CONDITIONAL ON ALT_RELAY_TRACKING SINCE 2.20.107, in both directions.
        The warning is required while opens are recorded, and it is FORBIDDEN
        once they are not: an unconfirmed address that never follows a link is
        then never measured at all, so the same paragraph would be scaring
        people about something that has stopped happening. A disclosure that
        outlives the thing it discloses is its own kind of false.
        """
        src = open(SUBSCRIBE, encoding="utf-8").read()
        on = _php_relay_tracking(src)
        # Both variants live in the file inside an if/else, so slice down to
        # the branch PHP will actually run. A NOT-in against the whole block
        # would match the other branch and could never fail.
        note = _privacy_note_branch(src, on)
        line = _tracking_line_branch(src, on)

        if on:
            self.assertIn("confirmation email", note.lower(),
                          "the privacy note describes tracking without ever naming "
                          "the one message sent before consent exists")
            self.assertIn("before you have agreed to anything", note,
                          "the note must say WHEN the measuring starts, not just "
                          "that it happens")
            self.assertIn("confirmation email", line.lower(),
                          "the disclosure a reader sees without opening anything "
                          "says 'an email', which reads as the digest")
        else:
            self.assertIn("do not record whether you open", note.lower(),
                          "with the relay off the note must say so plainly, not "
                          "go quiet: a reader told otherwise last month is owed "
                          "the correction")
            self.assertNotIn("before you have agreed to anything", note,
                             "the pre-consent warning describes a pixel that is "
                             "no longer sent, so it is now false")
            self.assertIn("records nothing about how you read", line.lower(),
                          "the always-visible line must carry the negative too")
            # The first-party counter survives the relay going off, and the
            # note has to keep saying so. Going quiet about it would turn a
            # true "we stopped measuring opens" into a false "nothing is
            # counted", which is the easier mistake and the worse one.
            self.assertIn("counter", note.lower() + line.lower(),
                          "the note stopped naming the click counter, which "
                          "still runs and still counts")

    def test_the_two_tracking_constants_agree(self):
        """One dashboard setting, mirrored in two languages, and nothing can
        read the dashboard. So the ONLY thing a test can enforce is that the
        two mirrors agree with each other, which is what makes the flip a
        one-line change instead of a hunt. See docs/RUNBOOK.md "Open and click
        tracking"."""
        from digest_layout import RELAY_TRACKING_ON
        php = _php_relay_tracking(open(SUBSCRIBE, encoding="utf-8").read())
        self.assertEqual(
            RELAY_TRACKING_ON, php,
            "digest_layout.RELAY_TRACKING_ON and subscribe.php "
            "ALT_RELAY_TRACKING disagree, so the email footer and the signup "
            "form are telling readers different things about the same pixel")


@unittest.skipUnless(_php(), "php not installed")
class BehaviouralGuards(unittest.TestCase):
    """Run the real handlers end to end through the harness."""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)

    def test_zero_boxes_is_refused_and_stores_nothing(self):
        self.assertTrue(self.o["prefs_none_is_null"])
        self.assertEqual(self.o["submit_zero_boxes"], "lists")
        self.assertTrue(self.o["zero_row_absent"])
        self.assertEqual(self.o["zero_mails"], 0)

    def test_signup_stores_pending_and_sends_only_the_confirmation(self):
        self.assertEqual(self.o["submit_ok"], "check")
        self.assertEqual(self.o["status_after_signup"], "pending")
        self.assertEqual(self.o["consents"], [1, 0, 1])
        self.assertEqual(self.o["mails_after_signup"], 1)
        # The exact subject the file ships, read out of the file rather than
        # copied here. assertIn("Confirm", ...) was the whole check until
        # 2026-08-16, and it would have passed on "Confirmation" or on a
        # subject that had lost the brand entirely.
        want = confirm_subject()
        self.assertEqual(
            self.o["confirm_mail_subject"], want,
            "the confirmation email went out with the subject %r, not the one "
            "alt_digest_confirm_subject() defines (%r). This is the only "
            "message a pending address ever gets and clicking it is the whole "
            "funnel, so its subject has exactly one definition."
            % (self.o["confirm_mail_subject"], want))
        self.assertTrue(
            want.lower().startswith("asktherecruiter.com:"),
            "the confirmation subject is %r. The brand has to lead: a reader "
            "who just typed their address is scanning an inbox for that name, "
            "and a subject they do not recognise produces no complaint and no "
            "error, only a list that quietly stays empty." % want)
        self.assertTrue(self.o["confirm_mail_has_token"])

    def test_the_address_never_travels_in_a_url(self):
        self.assertFalse(self.o["confirm_mail_has_email_in_url"])

    def test_double_opt_in_nothing_sends_to_pending(self):
        sent, eligible, mails = self.o["send_while_pending"]
        self.assertEqual((sent, eligible), (0, 0))
        self.assertEqual(mails, 1, "the confirmation is the only mail a pending address gets")

    def test_confirm_flips_the_row_and_single_uses_the_token(self):
        self.assertEqual(self.o["confirm_redirect"], "confirmed")
        self.assertEqual(self.o["status_after_confirm"], "confirmed")
        self.assertTrue(self.o["confirm_token_cleared"])
        self.assertEqual(self.o["confirm_reuse"], "expired")

    def test_confirmed_subscriber_receives_the_digest_with_unsubscribe(self):
        self.assertEqual(self.o["send_after_confirm"], [1, 1])
        headers = " | ".join(self.o["digest_headers"])
        self.assertIn("List-Unsubscribe:", headers)
        self.assertIn("List-Unsubscribe=One-Click", headers)
        self.assertTrue(self.o["digest_has_unsub_link"])
        self.assertFalse(self.o["digest_has_img"], "no pixels, no images, deliberately")
        self.assertTrue(self.o["digest_mentions_layoff"])

    def test_frequency_is_honoured(self):
        self.assertEqual(self.o["digest_daily_none"][0], 0,
                         "a weekly subscriber gets no daily mail")

    def test_unsubscribe_is_one_click_and_idempotent(self):
        self.assertEqual(self.o["unsub1"], "unsubscribed")
        self.assertEqual(self.o["status_after_unsub"], "unsubscribed")
        self.assertEqual(self.o["unsub2"], "unsubscribed",
                         "a second click must land on the same calm page, not an error")
        self.assertTrue(self.o["unsub_idempotent_same_stamp"])
        self.assertEqual(self.o["send_after_unsub"], [0, 0],
                         "nothing may ever send after an unsubscribe")

    def test_tokens_are_unguessable(self):
        self.assertTrue(self.o["tokens_distinct"])
        self.assertEqual(self.o["tokens_hex64"], [True, True, True, True])
        self.assertTrue(self.o["token_not_derived_from_email"])

    def test_sixth_signup_from_one_ip_is_refused(self):
        self.assertEqual(self.o["rate_limit_codes"],
                         ["check", "check", "check", "check", "check", "rate"])

    def test_purge_deletes_exactly_what_the_privacy_note_promises(self):
        self.assertEqual(self.o["purged"], 2)
        left = [r["email"] for r in self.o["left_after_purge"]]
        self.assertEqual(left, ["confirmed-old@example.com",
                                "pending-fresh@example.com",
                                "unsub-fresh@example.com"])

    def test_health_stamp_holds_counts_never_an_address(self):
        row = self.o["health_row"]
        self.assertIsNotNone(row, "the cron must stamp a digest_mailer health row")
        self.assertEqual(row["status"], "ok")
        self.assertTrue(row.get("checked_at"))
        self.assertNotIn("@", row.get("detail", ""),
                         "health output carries counts only, never an address")

    def test_a_stranger_cannot_change_a_confirmed_subscribers_choices(self):
        self.assertEqual(self.o["prefs_unchanged_until_reconfirm"], [1, 0, "confirmed"])
        self.assertEqual(self.o["change_confirm_redirect"], "updated")
        self.assertEqual(self.o["prefs_after_reconfirm"], [0, 1, "daily", "confirmed"])


@unittest.skipUnless(_php(), "php not installed")
class TheChangeEmailNamesWhatStops(unittest.TestCase):
    """THE GUARD AGAINST A SUBSCRIPTION DISAPPEARING WITHOUT ANYONE SAYING SO.

    alt_digest_prefs_from_post() builds the WHOLE preference set from the ticked
    boxes, every box on the form starts unticked by consent-hygiene design, and
    that form is the only way to change a subscription. So a reader on all three
    lists who ticks one box meaning to ADD it loses the other two. The intro copy
    has warned about it since 2.20.119, and copy is a warning, not a guard.

    The page cannot guard it: no session, the address may never travel in a URL,
    and the manage link in the digest footer is ONE URL for the whole send. The
    confirmation email can, because it goes to the mailbox that owns the row and
    it is already on the mandatory path of every change. So these tests are about
    what that email says, and they run against the real handlers.

    The harness case is exactly the defect: confirmed on `layoff`, resubmitted
    with `talent` alone.
    """

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)

    def test_the_loss_this_guards_is_still_what_the_code_does(self):
        # Not a tautology: if a later session makes the form additive, this
        # fails and the whole class below has to be re-reasoned rather than
        # quietly guarding a scenario that can no longer happen.
        self.assertEqual(
            self.o["prefs_after_reconfirm"][:2], [0, 1],
            "ticking `talent` alone no longer drops `layoff`. The mechanism "
            "these tests describe has changed; re-read alt_digest_change_delta()")

    def test_the_email_names_the_digest_that_will_stop(self):
        body = self.o["change_mail_body"]
        self.assertIn(
            list_names()["layoff"], body,
            "the change confirmation does not name the digest this click "
            "stops, so the reader is told nothing they were not told before: "
            "%r" % body)

    def test_what_stops_is_read_before_the_link_that_stops_it(self):
        body = self.o["change_mail_body"]
        stop = body.find(list_names()["layoff"])
        link = body.find("/confirm/")
        self.assertGreater(stop, -1)
        self.assertGreater(link, -1)
        self.assertLess(
            stop, link,
            "the confirm link comes before the list of what stops, so a reader "
            "can click it without passing the only warning they get")

    def test_the_loss_is_listed_above_the_gain(self):
        body = self.o["change_mail_body"]
        self.assertLess(
            body.find("Stopping:"), body.find("Starting:"),
            "the email opens with what the reader gains. The reader this "
            "exists for believes they are adding a list, so a message that "
            "confirms what they already think gets skimmed")

    def test_the_subject_says_something_stops(self):
        want = single_literal("alt_digest_change_stops_subject")
        self.assertEqual(self.o["change_mail_subject"], want)
        self.assertNotEqual(
            want, confirm_subject(),
            "a change that takes a digest away arrives under the same subject "
            "as a first signup, so the inbox gives the reader no reason to "
            "open the one message that could stop the loss")
        self.assertTrue(want.lower().startswith("asktherecruiter.com:"),
                        "the brand leads on every message this system sends")

    def test_a_change_that_only_adds_raises_no_alarm(self):
        body = self.o["add_mail_body"]
        self.assertNotIn(
            "Stopping:", body,
            "a subscriber who ticked everything they want is told something "
            "is stopping. A warning that fires when nothing is wrong is a "
            "warning readers learn to skip")
        self.assertEqual(self.o["add_mail_subject"],
                         single_literal("alt_digest_change_subject"))
        self.assertIn(list_names()["articles"], body)
        self.assertIn(list_names()["layoff"], body,
                      "the email does not say what keeps arriving, so a reader "
                      "cannot check the whole set from it")
        self.assertEqual(self.o["prefs_after_add"], [1, 1],
                         "ticking both did not keep both")

    def test_a_first_signup_is_not_dressed_up_as_a_change(self):
        body = self.o["confirm_mail_body_new"]
        for phrase in ("Stopping:", "Nothing has changed yet"):
            self.assertNotIn(
                phrase, body,
                "a brand new address is being told about a change to "
                "preferences it does not have: %r" % body)
        self.assertEqual(self.o["confirm_mail_subject"], confirm_subject())

    def test_the_change_email_still_carries_exactly_one_link(self):
        # The unsubscribe link left this message on 2026-08-17 because Brevo
        # rewrites links at the relay and corporate scanners follow them, so a
        # second link means a machine chooses between two outcomes with nobody
        # present. An "add without removing" link would be as mailbox-proof as
        # the confirm link and would reintroduce exactly that.
        urls = re.findall(r"https?://\S+", self.o["change_mail_body"])
        self.assertEqual(
            len(urls), 1,
            "the change email carries %d links. Two links is a scanner "
            "deciding what the subscriber gets: %r" % (len(urls), urls))

    def test_the_change_email_never_carries_the_address(self):
        # The itemised body is new prose next to a token, which is exactly the
        # shape that grows an address in it ("what you get, reader@..."). The
        # signup path already has this guard; the change path now has its own.
        self.assertNotIn(
            "@example.com", self.o["change_mail_body"],
            "the change email carries the subscriber's address. The address "
            "never travels in a URL and it has no business in the body either")


@unittest.skipUnless(_php(), "php not installed")
class BothTiersOnAMonday(unittest.TestCase):
    """Monday sends the daily tier AND the weekly tier, and neither eats the other.

    THE DEFECT, 2026-08-17. The relay chose one tier per run and chose weekly
    on a Monday, so every daily subscriber received nothing on a Monday. The
    first repair, running both tiers, was not enough on its own: last_sent_at
    was one column for both tiers, so whichever pass ran first marked the
    subscriber as already sent to and the second pass skipped them. That is
    the same silence wearing a different shape, so the guard is per tier and
    these read it through the real handlers.
    """

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.m = json.loads(proc.stdout)["monday"]

    def test_the_daily_pass_alone_is_what_every_other_day_looks_like(self):
        after = self.m["after_daily_pass"]
        self.assertEqual(after["daily_only"], 1,
                         "a daily subscriber gets one email on any day")
        self.assertEqual(after["weekly_only"], 0,
                         "a weekly subscriber gets nothing on a Tuesday")
        self.assertEqual(after["both_tiers"], 1,
                         "the daily half of a both-tiers subscription")

    def test_the_weekly_pass_still_finds_everyone_it_should(self):
        after = self.m["after_weekly_pass"]
        self.assertEqual(after["daily_only"], 1,
                         "the weekly pass must not mail a daily-only subscriber")
        self.assertEqual(after["weekly_only"], 1,
                         "a weekly subscriber gets their one email on Monday")
        self.assertEqual(after["both_tiers"], 2,
                         "two subscriptions at two cadences is two emails, and "
                         "the daily pass must not have consumed the weekly one")

    def test_each_tier_opens_its_own_send_row(self):
        self.assertEqual(self.m["send_row_freqs"], ["daily", "weekly"])

    def test_running_the_same_day_twice_sends_nobody_a_second_copy(self):
        self.assertEqual(self.m["after_a_rerun"], self.m["after_weekly_pass"])

    def test_the_relay_hands_out_each_tier_to_its_own_subscribers(self):
        self.assertEqual(sorted(self.m["relay_daily_recipients"]),
                         ["both-tiers@example.com", "daily-only@example.com"])
        self.assertEqual(sorted(self.m["relay_weekly_recipients"]),
                         ["both-tiers@example.com", "weekly-only@example.com"])

    def test_recording_the_daily_send_does_not_hide_the_weekly_one(self):
        """The per period guard, read where it actually broke.

        /digest-complete stamps the rows the daily pass mailed. The weekly
        ask happens after that, so this is the exact ordering the live job
        performs on a Monday.
        """
        self.assertIn("both-tiers@example.com", self.m["relay_weekly_recipients"])

    def test_neither_pass_consumes_the_other_lease(self):
        self.assertTrue(self.m["claims_after_both"]["daily"])
        self.assertTrue(self.m["claims_after_both"]["weekly"])

    def test_asking_twice_in_one_period_returns_nobody(self):
        self.assertEqual(self.m["relay_daily_rerun"], [])
        self.assertEqual(self.m["relay_weekly_rerun"], [])


@unittest.skipUnless(_php(), "php not installed")
class TheArticlesList(unittest.TestCase):
    """The third consent box, driven end to end.

    It was offered on the form from the first day and had no sender behind it:
    an articles-only subscriber double opted in, was never counted as a
    recipient by either sender, and received nothing, forever.
    """

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)

    def test_a_window_with_no_posts_omits_the_section_entirely(self):
        self.assertTrue(self.o["articles_empty_window_is_null"],
                        "an empty period must compose nothing at all, not an "
                        "empty heading and not a 'no articles this period' line")

    def test_an_articles_only_subscriber_gets_nothing_while_nothing_exists(self):
        self.assertEqual(self.o["articles_only_mails_with_no_posts"], 0)

    def test_an_articles_only_subscriber_is_a_recipient_once_posts_exist(self):
        self.assertTrue(self.o["articles_section_composed"])
        self.assertEqual(self.o["articles_only_mails_with_posts"], 1,
                         "the subscriber who ticked only the articles box must "
                         "receive the digest once the site has published")
        body = self.o["articles_mail_body"]
        self.assertIn("What the WARN data actually says", body)

    def test_the_section_carries_the_posts_own_words_and_nothing_else(self):
        html, text = self.o["articles_html"], self.o["articles_text"]
        for part in (html, text):
            self.assertIn("What the WARN data actually says", part)
            self.assertIn("Reading an 8-K", part)
            self.assertIn("A standfirst an editor wrote about", part)
            # A tracker surface is not an article, whatever type it is stored as.
            self.assertNotIn("Sources", part)
            # Outside the window, and unpublished.
            self.assertNotIn("Last month", part)
            self.assertNotIn("Half written", part)

    def test_html_entities_are_decoded_and_never_reach_a_reader(self):
        """Found in a live preview, not by reasoning. get_the_excerpt returns
        display HTML, wp_strip_all_tags removes tags and leaves entities, and
        the first render published `&#8220;tell me about yourself&#8221;` into
        the plain-text part, where nothing will ever turn it back."""
        for part in (self.o["articles_html"], self.o["articles_text"]):
            self.assertNotIn("&#8220;", part)
            self.assertNotIn("&#8221;", part)
        self.assertIn("\u201ctell me about yourself\u201d", self.o["articles_text"])

    def test_the_section_links_through_the_first_party_counter(self):
        self.assertIn("/wp-json/layoffs/v1/click", self.o["articles_html"])
        self.assertNotIn("<img", self.o["articles_html"].lower())

    # --- the standfirst, and why every item has one now ----------------

    def test_a_post_with_no_typed_excerpt_still_gets_a_standfirst(self):
        """THE DEFECT. This section shipped as a bare list of titles, and the
        code that prints a blurb was right there and looked correct. It read
        `post_excerpt`, the excerpt an editor types by hand, and nobody on
        this blog ever has: it is empty on every post. Measured live on
        2026-08-17, 10 of 10 recent posts have a rendered excerpt of 320 to
        410 characters and 0 of them reached the email. get_the_excerpt() is
        WordPress's own answer and falls back to the post's opening words.

        Nothing is invented in either branch: one is the editor's sentence,
        the other a verbatim trim of the author's.
        """
        for part in (self.o["articles_html"], self.o["articles_text"]):
            self.assertIn("An 8-K is the filing a company makes when something "
                          "material happens.", part)

    def test_only_the_first_sentence_is_taken(self):
        """340 characters under every item is the wall the nine-second budget
        cannot pay for, and a sentence is a unit the author chose."""
        self.assertNotIn("share of the entries in this tracker",
                         self.o["articles_text"])

    def test_a_standfirst_with_no_sentence_end_is_cut_at_a_word_and_marked(self):
        text = self.o["articles_text"]
        line = [l for l in text.splitlines()
                if l.strip().startswith("A very long opening")][0]
        self.assertTrue(line.rstrip().endswith("..."),
                        "a cut standfirst does not show that the author "
                        "carried on")
        self.assertLess(len(line.strip()), 200)

    # --- three, and say so when there were more ------------------------

    def test_it_prints_three_and_names_the_true_total(self):
        """Five titles with a standfirst each is a wall, and this section sits
        below two others. Three with a reason to click beats five without one.
        But "the three newest" is only honest if the reader is told there were
        more, so the query ceiling is above the print limit."""
        for part in (self.o["articles_html"], self.o["articles_text"]):
            self.assertIn("The 3 newest of 4 posts we published between", part)
        self.assertNotIn("A fifth post", self.o["articles_text"],
                         "the cut to three did not actually drop anything")

    def test_the_section_states_its_window_like_every_other_block(self):
        self.assertRegex(self.o["articles_text"],
                         r"posts we published (on|between) .*\b20\d{2}\.")

    def test_the_composer_picks_no_size_and_no_colour_here_either(self):
        """digest_layout.py owns the design. This section used to write its
        own font-size and margins inline, which is a second place the design
        can drift, and the rule the layoff composer is already held to."""
        html = self.o["articles_html"]
        for banned in ("font-size", "color:", "padding-left", "margin:"):
            self.assertNotIn(banned, html,
                             f"the articles composer chose {banned}, which "
                             f"belongs in digest_layout.py and nowhere else")

    def test_the_relay_composes_and_counts_the_third_list_too(self):
        self.assertIn("articles", self.o["relay_sections"],
                      "the relay never composed the articles section")
        self.assertIn(["articles"], self.o["relay_recipient_lists"],
                      "an articles-only subscriber is not returned as a "
                      "recipient, so the external sender never mails them")

    def test_the_relay_hands_out_a_manage_url(self):
        self.assertEqual(self.o["relay_manage_url"],
                         "https://example.test/blog/ai-layoff-tracker/#alt-digest")


@unittest.skipUnless(_php(), "php not installed")
class ClickCountingAndStats(unittest.TestCase):
    """The send log, the aggregate counter, the open-redirect guard and the
    stats payload, all driven through the real handlers."""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE, DIGEST_API],
                              capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr or proc.stdout
        cls.o = json.loads(proc.stdout)

    # --- the send log -------------------------------------------------

    def test_a_run_with_nobody_eligible_logs_no_send(self):
        self.assertEqual(self.o["sends_logged_when_nobody_eligible"], 0,
                         "'last digest sent to 0' would read as a failed delivery "
                         "when nothing was due to go out")

    def test_the_send_row_counts_what_actually_went_out(self):
        recipients, eligible, freq = self.o["send_row"]
        self.assertEqual((recipients, eligible, freq), (2, 2, "weekly"))
        self.assertTrue(self.o["send_row_matches_mails"],
                        "recipients must equal the messages wp_mail actually accepted")

    # --- click counting -----------------------------------------------

    def test_the_digest_links_through_the_first_party_counter(self):
        self.assertTrue(self.o["digest_uses_click_url"])
        self.assertFalse(self.o["digest_html_has_bare_tracker_link"],
                         "the counted link is the one in the HTML, or nothing is counted")
        # ONE LINK PER DESTINATION, AND THERE ARE MANY DESTINATIONS NOW. This
        # asserted exactly one, which was true while the section's only link
        # was the tracker link at its foot. The owner's fourth complaint was
        # that nothing else was linked: the biggest-cuts rows, the geography
        # lines and the industry lines were all plain text. Every one of them
        # is a counted link now, so the assertion that means something is that
        # they are all first-party and all carry the date basis.
        self.assertGreater(self.o["links_stored"], 1)
        for url in self.o["link_urls"]:
            self.assertTrue(url.startswith("https://example.test/blog/"),
                            f"the counter would forward off-site: {url}")
            if "/ai-layoff-tracker/?" in url:
                self.assertIn("date_basis=effective", url,
                              f"a digest link that does not name its date "
                              f"basis lands on the page's default filing "
                              f"basis, which is a different number: {url}")
        # The counted destination is the tracker page carrying THIS window and
        # THIS date basis, not the bare page. The email used to ship a caveat
        # saying the page counts on a different basis and would show a
        # different total, which made the click meant to prove the figure the
        # click that contradicted it. `effective` is the page's spelling of the
        # composer's `layoff_date`; the page silently ignores any other value,
        # so pinning the literal here is what stops that regressing quietly.
        link = self.o["link_url"]
        self.assertTrue(
            link.startswith("https://example.test/blog/ai-layoff-tracker/?"),
            f"the counted link left the tracker page: {link}")
        self.assertIn("date_basis=effective", link)
        self.assertRegex(link, r"[?&]from=\d{4}-\d{2}-\d{2}")
        self.assertRegex(link, r"[?&]to=\d{4}-\d{2}-\d{2}")
        # Every other filter is CLEARED, not omitted: the page restores a
        # returning visitor's saved filters before it reads the URL, and a key
        # that is absent leaves their old filter ANDed into our number.
        # The trailing `=` is written by hand and asserted here. add_query_arg
        # DROPS it on an empty value, which the first live preview emitted as
        # `&years&quarters&months`. URLSearchParams does read a bare key as an
        # empty value, so that URL worked by accident, and the whole point of
        # these keys is telling "present and empty" from "absent". A link whose
        # job is to reproduce a published figure does not rest on a parser's
        # tolerance for a malformed pair.
        for blank in ("country=", "industry=", "years=", "min_jobs=", "q="):
            self.assertIn(blank, link,
                          f"{blank} is not cleared, so a returning reader's "
                          f"saved filter survives into the figure we linked")
            self.assertNotRegex(link, r"[?&]" + blank[:-1] + r"(&|$)",
                                f"{blank[:-1]} lost its '=' and is now a bare "
                                f"key, which is add_query_arg's behaviour and "
                                f"not the contract this link needs")
        self.assertTrue(self.o["link_starts_at_zero"])

    def test_a_click_counts_once_and_lands_on_the_stored_destination(self):
        self.assertEqual(self.o["click_redirect"], self.o["link_url"])
        self.assertEqual(self.o["clicks_after_one"], 1)

    def test_the_counter_is_rate_limited_without_breaking_the_link(self):
        self.assertTrue(self.o["flood_all_landed"],
                        "a rate-limited visitor still reaches the page; only the count stops")
        self.assertEqual(self.o["clicks_after_flood"], 61,
                         "1 counted click plus a ceiling of 60 from the flooding address")

    # --- the open-redirect guard --------------------------------------

    def test_no_input_shape_can_send_a_visitor_off_our_domain(self):
        home = self.o["home_url"]
        for case in ("click_unknown_hash", "click_bad_hash_shape",
                     "click_bad_send_id", "click_negative_send"):
            self.assertEqual(self.o[case], home, f"{case} left our domain")

    def test_a_hostile_row_planted_in_the_table_is_still_not_followed(self):
        self.assertEqual(self.o["click_planted_foreign_host"], self.o["home_url"],
                         "the host guard must run again at redemption, not only at storage")
        self.assertEqual(self.o["planted_row_click_count"], 0)

    def test_the_host_allowlist_over_the_usual_bypasses(self):
        a = self.o["link_allowed"]
        self.assertTrue(a["own_host"])
        self.assertTrue(a["www_sibling"])
        for case in ("foreign", "userinfo", "prefix_trick", "protocol_rel",
                     "javascript", "data_uri", "relative", "empty"):
            self.assertFalse(a[case], f"{case} must not be an allowed destination")

    def test_a_refused_destination_is_neither_wrapped_nor_stored(self):
        self.assertTrue(self.o["track_link_refuses_foreign"],
                        "a link we will not count is left alone, never rewritten")
        self.assertTrue(self.o["track_link_stored_nothing"])

    # --- the stats payload --------------------------------------------

    def test_no_address_appears_anywhere_in_the_payload(self):
        self.assertNotIn("@", self.o["stats_json"],
                         "the stats route returns counts only; no address, ever")

    def test_the_payload_carries_every_field_the_owner_asked_for(self):
        s = self.o["stats"]
        self.assertTrue(s["available"])
        self.assertEqual(s["confirmed"],
                         {"total": 2, "layoff": 2, "talent": 0, "articles": 0})
        self.assertEqual(s["pending"], 0)
        self.assertEqual(s["unsubscribed"], 1)
        self.assertEqual(s["signups_retained"], 3)
        self.assertEqual(s["confirm_rate"], 0.6667)
        self.assertEqual(s["confirmed_last_7_days"], 2)
        self.assertEqual(s["frequency"], {"daily": 1, "weekly": 1})
        # Was a hardcoded "none" on both sides, and was FALSE from 2026-08-16
        # until 2.20.107: the field is named open_tracking in a payload about
        # the mailing list, so it reads as a claim about the emails a
        # subscriber receives, and the relay had been measuring those for
        # three days. It now derives from ALT_RELAY_TRACKING, so the operator
        # payload cannot disagree with the note published to readers.
        src = open(SUBSCRIBE, encoding="utf-8").read()
        self.assertEqual(s["open_tracking"],
                         "provider" if _php_relay_tracking(src) else "none")

    def test_the_frequency_split_adds_up_to_the_confirmed_total(self):
        s = self.o["stats"]
        self.assertEqual(s["frequency"]["daily"] + s["frequency"]["weekly"],
                         s["confirmed"]["total"],
                         "one subscriber counted once, whichever lists they picked")

    def test_last_send_reports_sent_clicks_and_the_48h_unsubscribes(self):
        last = self.o["stats"]["last_send"]
        self.assertEqual(last["recipients"], 2)
        self.assertEqual(last["clicks"], 61)
        self.assertEqual(last["unsubscribes_48h"], 1)
        self.assertTrue(last["sent_at"])

    def test_a_missing_table_reads_UNKNOWN_and_never_zero(self):
        s = self.o["stats_without_table"]
        self.assertFalse(s["available"])
        self.assertTrue(s["reason"])
        for field in ("confirmed", "pending", "unsubscribed", "signups_retained",
                      "confirm_rate", "confirmed_last_7_days", "frequency", "last_send"):
            self.assertIsNone(s[field],
                              f"{field} is 0 on an install with no table; 0 claims "
                              f"nobody subscribed when the truth is we cannot see")

    def test_a_send_without_the_tables_does_not_fatal(self):
        self.assertEqual(self.o["send_without_tables"], [0, 0])


class OpsStatusWiring(unittest.TestCase):
    """Section [4c] of the session-start tool. Counts only, UNKNOWN never 0."""

    NUMBERS = {
        "available": True,
        "confirmed": {"total": 412, "layoff": 380, "talent": 141, "articles": 96},
        "pending": 23, "unsubscribed": 17, "signups_retained": 452,
        "confirm_rate": 0.9115, "confirmed_last_7_days": 31,
        "frequency": {"daily": 88, "weekly": 324},
        "last_send": {"send_id": 9, "freq": "weekly", "sent_at": "2026-08-03 13:00:04",
                      "recipients": 405, "eligible": 412, "clicks": 62,
                      "unsubscribes_48h": 3},
    }

    def setUp(self):
        self.ops = _load_ops_status()

    def test_the_section_is_printed_at_session_start(self):
        code = open(os.path.join(RAILWAY, "ops_status.py"), encoding="utf-8").read()
        code = re.sub(r"#.*", "", code)     # comments prove nothing about wiring
        self.assertIn("subscriber_lines()", code,
                      "the helper must actually be called from main(), not merely defined")

    def test_no_key_reads_UNKNOWN(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            lines = self.ops.subscriber_lines()
        self.assertIn("UNKNOWN", lines[0])
        self.assertNotIn("0", " ".join(lines),
                         "with no key there is no number to print, not even a zero")

    def test_an_install_without_the_table_reads_UNKNOWN(self):
        payload = {"available": False, "reason": "the subscriber table does not exist"}
        with mock.patch.dict(os.environ, {"WP_API_KEY": "k"}, clear=True), \
                mock.patch("urllib.request.urlopen",
                           return_value=_fake_json_response(payload)):
            lines = self.ops.subscriber_lines()
        self.assertIn("UNKNOWN", lines[0])
        self.assertIn("cannot see", " ".join(lines))

    def test_an_unreachable_route_reads_UNKNOWN(self):
        with mock.patch.dict(os.environ, {"WP_API_KEY": "k"}, clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=OSError("blocked")):
            lines = self.ops.subscriber_lines()
        self.assertIn("UNKNOWN", lines[0])

    def test_numbers_render_as_counts_with_no_address_and_no_open_rate(self):
        with mock.patch.dict(os.environ, {"WP_API_KEY": "k"}, clear=True), \
                mock.patch("urllib.request.urlopen",
                           return_value=_fake_json_response(self.NUMBERS)):
            lines = self.ops.subscriber_lines()
        text = " ".join(lines)
        self.assertIn("subscribers 412 confirmed", text)
        self.assertIn("layoff 380, talent 141, articles 96", text)
        self.assertIn("+31 in the last 7 days", text)
        self.assertIn("pending 23, unsubscribed 17", text)
        self.assertIn("confirm rate 91.1%", text)
        self.assertIn("daily 88, weekly 324", text)
        self.assertIn("sent to 405, 62 click(s), 3 unsubscribed within 48h", text)
        self.assertNotIn("@", text)
        self.assertIn("no open-rate figure", text)

    def test_an_empty_send_log_is_not_reported_as_a_failed_send(self):
        payload = dict(self.NUMBERS, last_send=None)
        with mock.patch.dict(os.environ, {"WP_API_KEY": "k"}, clear=True), \
                mock.patch("urllib.request.urlopen",
                           return_value=_fake_json_response(payload)):
            text = " ".join(self.ops.subscriber_lines())
        self.assertIn("none logged yet", text)
        self.assertNotIn("sent to 0", text)


class WeeklyEmailWiring(unittest.TestCase):
    """The one line the owner reads in the weekly email."""

    def setUp(self):
        self.hd = _load_health_digest()

    def test_the_line_is_attached_to_the_owner_email(self):
        code = open(os.path.join(RAILWAY, "health_digest.py"), encoding="utf-8").read()
        code = re.sub(r"#.*", "", code)
        self.assertRegex(code, r"subscribers\s*=\s*subscriber_line\(\)",
                         "the line must be computed in main(), not merely defined")
        self.assertRegex(code, r"_email_alert\([^)]*subscribers\)",
                         "and handed to the email builder")
        self.assertRegex(code, r"lines\.append\(\"\\n\"\s*\+\s*subscribers\)",
                         "and actually appended to the body")

    def _line(self, payload=None, env=None, boom=False):
        env = env if env is not None else {"WP_SITE_URL": "https://x.test/blog",
                                           "WP_API_KEY": "k"}

        class _Resp:
            status_code = 200

            def json(self_inner):
                return payload
        get = (mock.Mock(side_effect=RuntimeError("blocked")) if boom
               else mock.Mock(return_value=_Resp()))
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(self.hd.requests, "get", get):
            return self.hd.subscriber_line()

    def test_it_renders_the_counts_the_owner_asked_for(self):
        line = self._line(OpsStatusWiring.NUMBERS)
        self.assertEqual(
            line,
            "Subscribers 412 (+31 this week), last digest sent to 405, "
            "62 clicks, 3 unsubscribed.")
        self.assertNotIn("@", line)

    def test_no_key_reads_UNKNOWN_not_zero(self):
        line = self._line(env={})
        self.assertIn("UNKNOWN", line)
        self.assertIn("not a zero", line)
        self.assertNotIn("0", line)

    def test_a_missing_table_reads_UNKNOWN_not_zero(self):
        line = self._line({"available": False, "reason": "the subscriber table does not exist"})
        self.assertIn("UNKNOWN", line)
        self.assertIn("the subscriber table does not exist", line)
        self.assertNotIn("Subscribers 0", line)

    def test_an_unreachable_route_reads_UNKNOWN_not_zero(self):
        line = self._line(boom=True)
        self.assertIn("UNKNOWN", line)
        self.assertNotIn("Subscribers 0", line)

    def test_no_send_yet_is_stated_rather_than_reported_as_zero_delivered(self):
        line = self._line(dict(OpsStatusWiring.NUMBERS, last_send=None))
        self.assertIn("no digest sent yet", line)
        self.assertNotIn("sent to 0", line)


if __name__ == "__main__":
    unittest.main()
