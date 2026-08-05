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
import types
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
RAILWAY = os.path.abspath(os.path.join(HERE, ".."))
PLUGIN = os.path.abspath(os.path.join(
    HERE, "..", "..", "wordpress-plugin", "ai-layoff-tracker"))
SUBSCRIBE = os.path.join(PLUGIN, "includes", "subscribe.php")
HARNESS = os.path.join(HERE, "fixtures", "digest_harness.php")


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    from shutil import which
    return which("php")


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


def _load_ops_status():
    if RAILWAY not in sys.path:
        sys.path.insert(0, RAILWAY)
    import ops_status
    return ops_status


def _load_health_digest():
    """health_digest imports requests at module scope; the wiring under test is
    pure formatting, so stand a stub in rather than skip the guard entirely."""
    if RAILWAY not in sys.path:
        sys.path.insert(0, RAILWAY)
    if "requests" not in sys.modules:
        stub = types.ModuleType("requests")
        stub.get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network in tests"))
        stub.post = stub.get
        sys.modules["requests"] = stub
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

    def test_articles_consent_sends_nothing_and_says_so(self):
        """No article mechanism exists; the flag records consent only, and the
        code must say so where a future sender would be added."""
        self.assertIn("'articles' deliberately absent", self.src)
        sender = self.src[self.src.index("function alt_digest_send("):]
        sender = sender[:sender.index("\n}")]
        self.assertNotIn("consent_articles = 1", sender,
                         "nothing may send under the articles consent yet")


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


@unittest.skipUnless(_php(), "php not installed")
class BehaviouralGuards(unittest.TestCase):
    """Run the real handlers end to end through the harness."""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE],
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
        self.assertIn("Confirm", self.o["confirm_mail_subject"])
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
class ClickCountingAndStats(unittest.TestCase):
    """The send log, the aggregate counter, the open-redirect guard and the
    stats payload, all driven through the real handlers."""

    @classmethod
    def setUpClass(cls):
        proc = subprocess.run([_php(), HARNESS, SUBSCRIBE],
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
        self.assertEqual(self.o["links_stored"], 1)
        self.assertEqual(self.o["link_url"], "https://example.test/blog/ai-layoff-tracker/")
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
        self.assertEqual(s["open_tracking"], "none")

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
