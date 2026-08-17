"""Applause on a blog post (includes/blog-claps.php): the invariants.

This feature is a public write endpoint on an anonymous site, so the guards are
privacy guards and correctness guards, and every one of them is exercised
against the REAL PHP through tests/fixtures/claps_harness.php (WordPress stubs
plus a SQLite wpdb on a FILE), never against a reimplementation.

  * THE INCREMENT IS ATOMIC. Sixteen processes tap one row at once and the
    total is exact. The same harness then runs a read-modify-write version and
    is asserted to LOSE counts, so this test cannot quietly stop being able to
    detect the defect it exists for. A concurrency test that has lost its
    ability to fail is worse than no concurrency test, because it is quoted.
  * THE ENDPOINT REFUSES EVERYTHING THAT IS NOT A PUBLISHED POST: a page, a
    layoffs entry, an attachment, a draft, a private post, a password protected
    one, an id that does not exist, and zero. And it writes NO ROW for any of
    them, because a row is itself a small disclosure that an id exists.
  * THE BATCH HELPER ISSUES ONE QUERY for many ids. A listing that called a
    single-row helper in a loop is the standard way a counter becomes a
    performance incident, so the shape is asserted, not the timing.
  * NO IDENTITY FIELD IS WRITTEN. Three independent ways: the schema has two
    integer columns and no third; the whole database is dumped after a request
    carrying a known address and user agent and neither string appears in any
    cell of any table; and the throttle key is asserted to live in a transient
    with an expiry and nowhere else.

Plus the surface rules: 44px controls, a real button that ships disabled so the
page works with scripting off, an aria-live region, a visible focus state,
prefers-reduced-motion, AA contrast recomputed from the shipped values in both
palettes, and no em-dash in reader copy.

No PHP binary, no measurement: these SKIP loudly rather than passing. Absence
of a signal is not a pass (CLAUDE.md).
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
CLAPS_PHP = PLUGIN / "includes/blog-claps.php"
CLAPS_CSS = PLUGIN / "assets/blog-claps.css"
CLAPS_JS = PLUGIN / "assets/blog-claps.js"
MAIN_PHP = PLUGIN / "ai-layoff-tracker.php"
HARNESS = Path(__file__).resolve().parent / "fixtures/claps_harness.php"


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    return shutil.which("php")


PHP = _php()

# Read off the shipped file rather than repeated here: a test that hard-codes
# 10 keeps working while the server clamps at something else.
ALT_CLAPS_PER_REQUEST = int(re.search(
    r"define\('ALT_CLAPS_PER_REQUEST',\s*(\d+)\)",
    CLAPS_PHP.read_text()).group(1))


def _strip_php_comments(path):
    """The file's source with every comment removed, via PHP's own tokenizer.

    A test that greps raw source proves nothing: a sentence in a docblock
    saying the increment is atomic matches exactly as well as the increment
    being atomic. token_get_all cannot be fooled by prose.
    """
    code = (r'echo implode("", array_map(function ($t) { return is_array($t) '
            r'? (in_array($t[0], array(T_COMMENT, T_DOC_COMMENT)) ? "" : $t[1]) '
            r': $t; }, token_get_all(file_get_contents($argv[1]))));')
    proc = subprocess.run([PHP, "-r", code, "--", str(path)],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return proc.stdout


def _strip_css_comments(text):
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


def _strip_js_comments(text):
    out, i, n, quote = [], 0, len(text), None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"":
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


class HarnessMixin(unittest.TestCase):
    """Runs the real PHP over a throwaway SQLite file."""

    @classmethod
    def setUpClass(cls):
        if not PHP:
            raise unittest.SkipTest(
                "no php binary found: the applause guards measure the REAL "
                "handlers, and a run that could not measure is UNKNOWN, not a pass")

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="alt-claps-")
        self.db = os.path.join(self.dir, "claps.sqlite")
        self.harness("install")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_raw(self, *args, timeout=120):
        proc = subprocess.run(
            [PHP, str(HARNESS), str(CLAPS_PHP), self.db, *[str(a) for a in args]],
            capture_output=True, text=True, timeout=timeout)
        return proc

    def harness(self, *args, timeout=120):
        proc = self.run_raw(*args, timeout=timeout)
        self.assertEqual(proc.returncode, 0,
                         "harness mode %r failed:\n%s\n%s"
                         % (args, proc.stdout, proc.stderr))
        return json.loads(proc.stdout.strip().splitlines()[-1])


class AtomicIncrement(HarnessMixin):
    WRITERS = 16
    EACH = 25

    def _hammer(self, mode):
        with ThreadPoolExecutor(max_workers=self.WRITERS) as pool:
            procs = [pool.submit(self.run_raw, mode, 101, self.EACH)
                     for _ in range(self.WRITERS)]
            for f in procs:
                p = f.result()
                self.assertEqual(p.returncode, 0,
                                 "a writer process failed:\n%s\n%s" % (p.stdout, p.stderr))
        return int(self.harness("total", 101)["claps"])

    def test_sixteen_concurrent_writers_lose_no_count(self):
        want = self.WRITERS * self.EACH
        got = self._hammer("bump")
        self.assertEqual(got, want, (
            "alt_claps_add() lost counts under concurrent writers: %d processes "
            "x %d taps should be %d claps, the row holds %d. The increment must "
            "be ONE statement the database resolves under a row lock "
            "(UPDATE ... SET claps = claps + %%d), never a read in PHP followed "
            "by a write in PHP." % (self.WRITERS, self.EACH, want, got)))

    def test_the_same_harness_still_catches_a_lost_update(self):
        """The control. If this ever passes, the test above proves nothing."""
        want = self.WRITERS * self.EACH
        got = self._hammer("rmw")
        self.assertLess(got, want, (
            "the read-modify-write CONTROL did not lose a single count under "
            "%d concurrent processes (%d of an expected %d). That means this "
            "harness can no longer distinguish an atomic increment from a racy "
            "one, so the atomicity test above is passing for the wrong reason. "
            "Fix the harness, do not delete this assertion."
            % (self.WRITERS, got, want)))

    def test_the_increment_reads_nothing_before_it_writes(self):
        src = _strip_php_comments(CLAPS_PHP)
        body = src[src.index("function alt_claps_add("):]
        body = body[:body.index("\nfunction ")]
        self.assertIn("SET claps = claps + %d", body,
                      "alt_claps_add() must increment with a single "
                      "'SET claps = claps + %d' statement resolved by the database")
        for banned in ("get_var", "get_row", "get_results"):
            self.assertNotIn(banned + "(", body, (
                "alt_claps_add() calls %s() before its write. That is a "
                "read-modify-write and it loses a count when two readers tap at "
                "once. The database must do the addition." % banned))


class EndpointRefusals(HarnessMixin):
    # id -> why it must be refused
    REFUSED = {
        102: "a draft post",
        103: "a private post",
        104: "a page, not a post",
        105: "a layoffs tracker entry, not a post",
        106: "an attachment",
        107: "a password protected post",
        999: "an id no post has",
        0: "zero",
        -5: "a negative id",
    }

    def test_only_a_published_post_is_accepted(self):
        ok = self.harness("endpoint", 101, 1)
        self.assertNotIn("error", ok,
                         "a published post of type 'post' must be applaudable, got %r" % (ok,))
        self.assertEqual(ok["data"]["claps"], 1)
        self.assertTrue(ok["data"]["counted"])

    def test_every_other_id_is_refused_and_writes_no_row(self):
        for post_id, what in sorted(self.REFUSED.items()):
            with self.subTest(post_id=post_id, kind=what):
                res = self.harness("endpoint", post_id, 1)
                self.assertEqual(res.get("error"), "alt_clap_bad_post", (
                    "POST /clap accepted id %d (%s). The write endpoint is "
                    "public, so anything that is not a PUBLISHED post of type "
                    "'post' must be refused. Got: %r" % (post_id, what, res)))
                self.assertEqual(res.get("status"), 404,
                                 "a refused id must answer 404, got %r" % (res.get("status"),))
                self.assertEqual(res.get("rows"), [], (
                    "POST /clap wrote a counter row for id %d (%s) even though "
                    "it refused the request. A row is itself a disclosure that "
                    "the id exists. Rows found: %r"
                    % (post_id, what, res.get("rows"))))

    def test_a_single_request_cannot_carry_a_large_number(self):
        res = self.harness("endpoint", 101, 100000)
        self.assertEqual(res["data"]["claps"], 10, (
            "POST /clap with n=100000 added %d. A single request must be "
            "clamped to ALT_CLAPS_PER_REQUEST (10) server side, whatever the "
            "browser sends." % res["data"]["claps"]))

    def test_a_non_positive_amount_still_counts_one(self):
        for n in (0, -7):
            with self.subTest(n=n):
                self.setUp()
                res = self.harness("endpoint", 101, n)
                self.assertEqual(res["data"]["claps"], 1,
                                 "n=%d should floor to one clap, got %r" % (n, res["data"]))

    def test_the_route_is_public_post_only_and_stands_alone(self):
        routes = self.harness("routes")["routes"]
        clap = [r for r in routes if r["route"] == "/clap"]
        self.assertEqual(len(clap), 1,
                         "expected exactly one /clap route, found %r" % (routes,))
        self.assertEqual(clap[0]["methods"], "POST",
                         "/clap must be POST only, got %r" % clap[0]["methods"])
        self.assertEqual(clap[0]["callback"], "alt_api_clap")
        self.assertEqual(
            [r["route"] for r in routes], ["/clap"],
            "includes/blog-claps.php registered a second route (%r). This file "
            "may expose exactly one public write and it may write nothing but "
            "the counter." % ([r["route"] for r in routes],))

    def test_the_response_is_never_cached(self):
        ok = self.harness("endpoint", 101, 1)
        self.assertEqual(ok["headers"].get("Cache-Control"), "no-store", (
            "the clap response must be no-store: a cached total is a number "
            "that stops moving, and readers read it as a broken button"))


class BatchHelper(HarnessMixin):
    def test_many_ids_cost_exactly_one_query(self):
        ids = list(range(201, 241))            # forty posts, a listing page
        res = self.harness("batch", ",".join(str(i) for i in ids))
        selects = [q for q in res["queries"] if "alt_post_claps" in q]
        self.assertEqual(len(selects), 1, (
            "alt_claps_counts() issued %d statements for %d ids. The helper "
            "exists so a post LISTING costs one round trip; one query per card "
            "is how a counter becomes a performance incident on an archive "
            "page. Statements were:\n%s"
            % (len(selects), len(ids), "\n".join(selects))))
        self.assertIn(" IN (", selects[0],
                      "the one statement must be an IN list, got %r" % selects[0])

    def test_every_id_asked_for_comes_back_even_with_no_row(self):
        res = self.harness("batch", "201,202,203")
        self.assertEqual(res["counts"], {"201": 0, "202": 0, "203": 0}, (
            "alt_claps_counts() must return a value for EVERY id asked for. "
            "'no row yet' and 'zero claps' are the same thing to a reader, and "
            "dropping the id pushes an isset() into every caller. Got %r"
            % (res["counts"],)))

    def test_junk_ids_are_dropped_before_they_reach_sql(self):
        res = self.harness("batch", "201,0,-3")
        self.assertEqual(sorted(res["counts"].keys()), ["201"],
                         "non-positive ids must not reach the query, got %r" % (res["counts"],))

    def test_the_single_post_read_goes_through_the_batch_helper(self):
        src = _strip_php_comments(CLAPS_PHP)
        body = src[src.index("function alt_claps_count("):]
        body = body[:body.index("\nfunction ")]
        self.assertIn("alt_claps_counts(", body, (
            "alt_claps_count() must read through alt_claps_counts() so there is "
            "ONE read path. Two SQL read paths drift, and the one the listing "
            "uses is the one nobody looks at."))


class NoIdentityIsStored(HarnessMixin):
    def test_the_schema_has_two_integer_columns_and_no_third(self):
        cols = self.harness("install")["columns"]
        names = [c["name"] for c in cols]
        self.assertEqual(names, ["post_id", "claps"], (
            "wp_alt_post_claps must hold exactly post_id and claps. A third "
            "column is where an ip, a visitor id or a timestamp would go, and "
            "the site publishes that it stores no visitor identity. Found: %r"
            % (names,)))
        for c in cols:
            self.assertRegex(c["type"].upper(), r"^(BIGINT|INT)\b", (
                "column %r is %r. Both columns must be integers: a text column "
                "in this table is a place to put a person."
                % (c["name"], c["type"])))

    def test_a_real_request_leaves_no_trace_of_the_visitor_anywhere(self):
        ip = "192.0.2.77"
        self.harness("endpoint", 101, 3, ip)
        dump = self.harness("render", 101)["dump"]
        blob = json.dumps(dump)
        for needle, what in ((ip, "the visitor's address"),
                             ("RenderAgent", "the user agent"),
                             ("HarnessAgent", "the user agent")):
            self.assertNotIn(needle, blob, (
                "%s (%r) reached durable storage. Nothing about a reader may be "
                "written by this feature: one integer per post, and nothing "
                "else. Database contents were:\n%s" % (what, needle, blob)))
        rows = dump.get("wp_alt_post_claps", [])
        self.assertEqual(rows, [{"post_id": 101, "claps": 3}],
                         "the whole store after three claps should be one row of "
                         "two integers, found %r" % (rows,))

    def test_the_throttle_key_lives_in_a_short_transient_and_nowhere_else(self):
        res = self.harness("endpoint", 101, 1, "192.0.2.31")
        keys = list(res["transients"].keys())
        self.assertEqual(len(keys), 1,
                         "expected one throttle transient, got %r" % (keys,))
        self.assertTrue(keys[0].startswith("alt_clap_"),
                        "unexpected transient key %r" % keys[0])
        self.assertNotIn("192.0.2.31", keys[0], (
            "the throttle key carries the raw address (%r). It must be hashed: "
            "a key is readable by anyone who can list transients." % keys[0]))
        ttl = res["transients"][keys[0]]["ttl"]
        self.assertTrue(0 < ttl <= 900, (
            "the throttle transient expires in %r seconds. A key derived from a "
            "request may live only briefly; a long or absent expiry is a "
            "visitor record with a different name." % ttl))

    def test_the_source_writes_nothing_but_the_counter(self):
        """Every write statement in the file, and the table each one names.

        Read off the SQL string literals with comments already stripped, so a
        docblock cannot supply the word this looks for. A write whose table
        comes from anywhere but alt_claps_table() is the failure: this file may
        create and increment one counter row and do nothing else.
        """
        src = _strip_php_comments(CLAPS_PHP)
        # A statement is written as literal . table . literal, so splice the
        # table expression back in and read each statement whole. {T} therefore
        # means "the table name came from alt_claps_table()", and a statement
        # naming any other table simply will not contain it.
        spliced = re.sub(r"'\s*\.\s*(?:\$table|alt_claps_table\(\))\s*\.\s*'", "{T}", src)
        statements = [lit for lit in re.findall(r"'([^']*)'", spliced)
                      if re.match(r"\s*(INSERT|UPDATE|REPLACE|DELETE)\b", lit, re.I)]
        self.assertTrue(statements, "found no SQL at all; has the file moved?")
        for lit in statements:
            self.assertIn("{T}", lit, (
                "the write %r names a table that does not come from "
                "alt_claps_table(). This file may write ONE integer to ONE "
                "counter table and nothing else." % lit))
            self.assertRegex(
                lit,
                r"^(INSERT IGNORE INTO \{T\} \(post_id, claps\) VALUES \(%d, 0\)"
                r"|UPDATE \{T\} SET claps = claps \+ %d WHERE post_id = %d)$", (
                    "unexpected write shape %r. The only two writes here are "
                    "the INSERT IGNORE that creates a row at zero and the "
                    "single atomic increment." % lit))
        self.assertEqual(len(statements), 2,
                         "expected exactly two write statements, found %r" % (statements,))
        for banned in ("DELETE", "REPLACE", "TRUNCATE"):
            self.assertNotIn(banned, src.upper().replace("DELETED", ""), (
                "includes/blog-claps.php contains a %s. The public endpoint "
                "must not be able to remove or overwrite a row." % banned))
        for banned in ("update_option(", "add_post_meta(", "update_post_meta(",
                       "wp_insert_post(", "setcookie(", "wp_set_auth_cookie("):
            self.assertNotIn(banned, src, (
                "includes/blog-claps.php calls %s. This feature writes ONE "
                "integer to ONE table and stores nothing about a reader, so "
                "there is no durable store here to reach for." % banned))

    def test_the_throttle_declines_to_count_without_refusing_the_reader(self):
        res = self.harness("throttle", 101, 70, timeout=180)
        self.assertEqual(res["counted"], 60, (
            "the per connection ceiling is 60 increments in five minutes; %d "
            "of 70 calls counted." % res["counted"]))
        self.assertEqual(res["claps"], 60,
                         "the stored total should stop at the ceiling, got %r" % res["claps"])


class TheControlOnThePage(HarnessMixin):
    def setUp(self):
        super().setUp()
        self.html = self.harness("render", 101)["html"]

    def render_with(self, claps):
        """The markup for a post that already has `claps` on it."""
        left = int(claps)
        while left > 0:                       # one call may carry at most ten
            step = min(left, ALT_CLAPS_PER_REQUEST)
            self.harness("bump", 101, 1, step)
            left -= step
        return self.harness("render", 101)["html"]

    @staticmethod
    def count_text(html):
        m = re.search(r'<span class="alt-clap-count"[^>]*>(.*?)</span>\s*$',
                      html, re.S)
        if m is None:
            m = re.search(r'<span class="alt-clap-count"[^>]*>(.*?)</span>',
                          html, re.S)
        assert m is not None, "no count element in:\n%s" % html
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()

    def test_the_count_renders_without_javascript(self):
        self.assertIn(
            "12 people found this helpful", self.render_with(12), (
                "the count must be server rendered text so the page is right "
                "with scripting off"))

    def test_the_button_speaks_to_this_audience(self):
        """The readers here are mid job search, plus recruiters and
        journalists. "Applaud" is Medium's word for Medium's readers."""
        self.assertIn(
            ">This helped<", self.html,
            "the button does not say 'This helped'. Markup was:\n%s" % self.html)
        self.assertNotIn(
            "Applaud", self.html,
            "the button still says 'Applaud' somewhere in the markup")

    def test_one_is_a_person_and_the_rest_are_people(self):
        cases = ((1, "1 person found this helpful"),
                 (2, "2 people found this helpful"),
                 (12, "12 people found this helpful"))
        for claps, want in cases:
            with self.subTest(claps=claps):
                self.setUp()
                got = self.count_text(self.render_with(claps))
                self.assertEqual(got, want, (
                    "with %d on the row the page says %r, expected %r. A "
                    "count that says '1 people' is the first thing a reader "
                    "notices about a number." % (claps, got, want)))

    def test_zero_says_nothing_rather_than_saying_zero(self):
        got = self.count_text(self.html)
        self.assertEqual(got, "", (
            "an article nobody has marked yet renders %r. '0 people found "
            "this helpful' is a worse thing to publish under an article than "
            "silence, and it is the state most articles are in on the day "
            "they go up." % got))

    def test_the_sentence_reaches_the_script_as_a_template(self):
        """One definition, in PHP, carried to the browser as markup.

        Two languages cannot share a string literal, so what they share is the
        template: the singular and plural forms are emitted as attributes and
        blog-claps.js substitutes the number. This asserts the attributes are
        the SAME function's output, so PHP cannot say one thing on load and
        the script another after a tap.
        """
        m = re.search(r'data-count-one="([^"]*)"', self.html)
        n = re.search(r'data-count-many="([^"]*)"', self.html)
        self.assertTrue(m and n, (
            "the markup carries no data-count-one / data-count-many "
            "templates, so assets/blog-claps.js has to hold its own copy of "
            "the sentence and the two will drift. Markup was:\n%s" % self.html))
        for name, got, count in (("data-count-one", m.group(1), 1),
                                 ("data-count-many", n.group(1), 2)):
            want = self.harness("phrase", count, "{n}")["phrase"]
            self.assertEqual(got, want, (
                "%s is %r but alt_claps_count_phrase(%d) says %r. The "
                "attribute must BE that function's output, not a second copy "
                "of the words." % (name, got, count, want)))
        self.assertIn("{n}", m.group(1),
                      "the singular template has no {n} placeholder")
        self.assertIn("{n}", n.group(1),
                      "the plural template has no {n} placeholder")

    def test_the_button_is_a_real_button_and_ships_inert(self):
        self.assertRegex(self.html, r"<button[^>]*type=\"button\"", (
            "the control must be a real <button>, not a div with a click "
            "handler: a div is not focusable, not announced as a button and "
            "not operated by the space bar"))
        self.assertIn("disabled", self.html, (
            "the button must ship disabled and be enabled by blog-claps.js. An "
            "enabled button that silently does nothing is announced as "
            "available and tapped twice."))

    def test_there_is_a_live_region_and_it_starts_empty(self):
        m = re.search(r'<p class="alt-clap-live"[^>]*>(.*?)</p>', self.html, re.S)
        self.assertIsNotNone(m, "no aria-live region in:\n%s" % self.html)
        self.assertIn('aria-live="polite"', m.group(0))
        self.assertEqual(m.group(1), "", (
            "the live region must start EMPTY. A region that already holds the "
            "same words announces nothing when they are replaced."))

    def test_the_note_is_tied_to_the_button(self):
        described = re.search(r'aria-describedby="([^"]+)"', self.html)
        self.assertIsNotNone(described, "the button must reference the note")
        self.assertIn('id="%s"' % described.group(1), self.html,
                      "aria-describedby points at an id that is not on the page")

    def test_the_page_says_the_number_is_approximate(self):
        note = re.search(r'<p class="alt-clap-note"[^>]*>(.*?)</p>', self.html, re.S).group(1)
        self.assertIn("Anonymous", note)
        self.assertIn("approximate", note, (
            "there are no accounts here, so the number can be inflated. The "
            "page must say so rather than present it as a measurement. Note "
            "read: %r" % note))

    def test_a_draft_renders_nothing_at_all(self):
        self.assertEqual(self.harness("render", 102)["html"], "", (
            "alt_claps_render() emitted markup for a draft. The renderer and "
            "the endpoint must agree on what is applaudable."))

    def test_no_em_dash_in_reader_copy(self):
        for name, text in (("markup", self.html),
                           ("stylesheet", CLAPS_CSS.read_text())):
            self.assertNotIn("—", text,
                             "em-dash in %s, which UI copy may not use" % name)


class ReaderCopyMeetsTheStandard(unittest.TestCase):
    """docs/STYLE.md, scored by the real scorer, without editing it.

    railway/style_check.py is byte-digest-pinned across both products
    (test_style_standard.SharedStandardDoesNotDrift), so adding this file to its
    target list is a coordinated two-repo change and not something one feature
    should do on its way past. The scorer is importable, so the copy is measured
    here with the same functions instead of being taken on trust.
    """

    FILES = ("wordpress-plugin/ai-layoff-tracker/includes/blog-claps.php",
             "wordpress-plugin/ai-layoff-tracker/assets/blog-claps.js")

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT / "railway"))
        import style_check
        cls.sc = style_check

    def test_the_copy_a_reader_sees_has_no_style_findings(self):
        for rel in self.FILES:
            with self.subTest(file=rel):
                segs = self.sc.extract_file(str(ROOT / rel), "post", str(ROOT))
                findings, stats = self.sc.check_segments(segs)
                self.assertEqual(findings, [], (
                    "%s carries reader copy that fails docs/STYLE.md: %r"
                    % (rel, findings)))
                page = stats.get("post")
                if not page or not page["grades"]:
                    continue
                mean = sum(page["grades"]) / len(page["grades"])
                self.assertLessEqual(mean, 11.0, (
                    "%s reads at grade %.1f, over the 11.0 bar" % (rel, mean)))
                self.assertLessEqual(page["passive"], page["sent"] * 0.25, (
                    "%s is %d of %d sentences passive, over the 25%% ceiling"
                    % (rel, page["passive"], page["sent"])))


class Assets(unittest.TestCase):
    """Shape rules read off the shipped files, with no PHP needed."""

    @classmethod
    def setUpClass(cls):
        cls.css = _strip_css_comments(CLAPS_CSS.read_text())
        cls.js = _strip_js_comments(CLAPS_JS.read_text())
        cls.php = CLAPS_PHP.read_text()
        cls.main = MAIN_PHP.read_text()

    def _rule(self, selector):
        i = self.css.find(selector)
        self.assertGreater(i, -1, "blog-claps.css has no rule %r" % selector)
        j = self.css.index("{", i)
        return self.css[j + 1:self.css.index("}", j)]

    def test_the_button_clears_forty_four_pixels_on_both_axes(self):
        body = self._rule(".alt-clap-btn {")
        for prop in ("min-height: 44px", "min-width: 44px"):
            self.assertIn(prop, body, (
                "the applause button declares no %s. 44px on both axes is the "
                "floor the rest of this plugin is held to "
                "(railway/tests/test_tap_targets.py)." % prop))

    def test_the_focus_state_is_visible_and_ours(self):
        body = self._rule(".alt-clap-btn:focus-visible {")
        self.assertRegex(body, r"outline:\s*2px solid", (
            "focus must be a visible 2px outline. On the accent fill a UA "
            "default can land at the same lightness as the button."))
        self.assertIn("outline-offset", body)

    def test_motion_is_optional(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css, (
            "the tap animation must be switched off for a reader who asked for "
            "reduced motion"))
        i = self.css.index("@media (prefers-reduced-motion: reduce)")
        self.assertIn("animation: none", self.css[i:i + 400])

    def test_no_external_asset_is_referenced(self):
        for name, text in (("blog-claps.css", self.css),
                           ("blog-claps.js", self.js),
                           ("blog-claps.php", self.php)):
            for pattern in (r"https?://(?!example\.test)[^\s'\"]*\.(?:png|jpe?g|gif|svg|woff2?|css|js)",
                            r"url\(\s*['\"]?https?:", r"@import"):
                self.assertIsNone(re.search(pattern, text), (
                    "%s reaches for a remote asset (%r). The site promises no "
                    "images and no tracking pixels, and an icon fetched from "
                    "anywhere is a request and a log line on someone else's "
                    "server. The icon is inline SVG." % (name, pattern)))
        self.assertIn("<svg", self.php, "the icon must be inline SVG in the markup")

    def test_the_component_carries_its_own_colours(self):
        """On a blog post assets/layoffs.css is not enqueued, so a bare var()
        with no fallback resolves to nothing. Same lesson as subscribe.php."""
        for m in re.finditer(r"var\(\s*(--alt-[a-z0-9-]+)\s*([,)])", self.css):
            token, nxt = m.group(1), m.group(2)
            if token.startswith("--alt-cl-"):
                continue          # the component's own token, defined above
            self.assertEqual(nxt, ",", (
                "%s is read with no fallback. blog-claps.css loads on single "
                "posts, where layoffs.css does not, so that resolves to an "
                "unstyled control." % token))

    def test_the_stylesheet_declares_no_dark_block_it_cannot_honour(self):
        """subscribe.php's judgement, held here so it is not 'fixed' later: the
        blog article is pinned to white, so a dark box on it is a hole, and the
        surfaces that DO have dark load layoffs.css and are served by the var()
        half of every token."""
        self.assertNotIn("prefers-color-scheme", self.css.replace(
            "prefers-reduced-motion", ""), (
            "blog-claps.css declared a prefers-color-scheme block. The one "
            "surface that relies on these literals is the blog, which has no "
            "dark palette; the surfaces that have one resolve the var() half."))

    def test_the_include_is_guarded_in_the_main_plugin_file(self):
        self.assertIn("$alt_blog_claps = ALT_PLUGIN_DIR . 'includes/blog-claps.php';", self.main)
        i = self.main.index("$alt_blog_claps =")
        self.assertIn("is_readable($alt_blog_claps)", self.main[i:i + 200], (
            "the new include must be require'd behind is_readable. An FTPS "
            "deploy lands files one at a time, and a hard require of a "
            "not-yet-uploaded include fatals the whole plugin (2.19.20)."))

    def test_the_include_declares_each_function_once(self):
        names = re.findall(r"^function\s+(alt_[a-z0-9_]+)\s*\(", self.php, re.M)
        self.assertEqual(sorted(names), sorted(set(names)),
                         "a function is declared twice in blog-claps.php")
        others = []
        for path in (PLUGIN / "includes").glob("*.php"):
            if path.name == "blog-claps.php":
                continue
            others += re.findall(r"^function\s+(alt_[a-z0-9_]+)\s*\(",
                                 path.read_text(), re.M)
        others += re.findall(r"^function\s+(alt_[a-z0-9_]+)\s*\(", self.main, re.M)
        clash = sorted(set(names) & set(others))
        self.assertEqual(clash, [], (
            "blog-claps.php redeclares %r, which another include already "
            "defines. Two includes declaring one name is a PHP fatal on every "
            "request, and that took /blog down for nine minutes." % (clash,)))

    def test_the_assets_load_on_single_posts_and_nowhere_else(self):
        body = self.php[self.php.index("function alt_claps_enqueue("):]
        body = body[:body.index("\nadd_action")]
        self.assertIn("if (!is_singular('post')) return;", body, (
            "the stylesheet and script must be enqueued only on single posts, "
            "gated the same way the signup placement is"))
        self.assertIn("blog-claps.css", body)
        self.assertIn("blog-claps.js", body)

    def test_the_reader_ceiling_is_stated_in_one_place(self):
        self.assertIn("define('ALT_CLAPS_READER_MAX', 50)", self.php)
        self.assertIn("data-max=", self.php,
                      "the ceiling must reach the browser as an attribute, not "
                      "as a literal duplicated in the script")
        self.assertNotIn("= 50;", self.js,
                         "blog-claps.js hard-codes the reader ceiling; it must "
                         "read data-max so the two cannot drift")

    def test_the_script_sends_no_credentials(self):
        self.assertIn("credentials: 'omit'", self.js, (
            "the clap request must not carry cookies. It is anonymous by "
            "design, and a cookie is an identity the endpoint would then be "
            "able to read."))


class Contrast(unittest.TestCase):
    """AA, recomputed from the values actually shipped, in both palettes.

    A contrast claim in a comment rots. These are the numbers, measured here.
    """

    # The component reads site tokens with light literals as fallbacks, so each
    # pair below is (light literal in blog-claps.css, dark value of the same
    # token in layoffs.css).
    PALETTES = {
        "light": {"page": "#ffffff", "ink": "#16181d", "note": "#696d77",
                  "accent": "#1f6fd0", "accent-strong": "#1c5cab"},
        "dark": {"page": "#12141a", "ink": "#e9eaee", "note": "#9aa0ac",
                 "accent": "#6fabf2", "accent-strong": "#9ac8f8"},
    }

    @staticmethod
    def _lum(hexcolor):
        c = hexcolor.lstrip("#")
        parts = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        f = [(v / 12.92) if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
        return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2]

    @classmethod
    def ratio(cls, a, b):
        la, lb = cls._lum(a), cls._lum(b)
        hi, lo = max(la, lb), min(la, lb)
        return (hi + 0.05) / (lo + 0.05)

    def setUp(self):
        self.css = _strip_css_comments(CLAPS_CSS.read_text())

    def test_the_shipped_light_literals_are_the_ones_measured(self):
        for name, value in self.PALETTES["light"].items():
            token = "--alt-cl-%s:" % name
            i = self.css.find(token)
            self.assertGreater(i, -1, "blog-claps.css defines no %s" % token)
            decl = self.css[i:self.css.index(";", i)]
            self.assertIn(value, decl.lower(), (
                "%s ships %r but this test measures %r. The ratios below would "
                "then be about a colour nobody sees." % (token, decl, value)))

    def test_text_meets_AA_in_both_palettes(self):
        # (label, foreground key, background key, floor)
        checks = (
            ("button label and edge", "accent", "page", 4.5),
            ("the count", "ink", "page", 4.5),
            ("the note", "note", "page", 4.5),
            ("focus outline", "accent-strong", "page", 3.0),
        )
        failures = []
        for palette, colors in self.PALETTES.items():
            for label, fg, bg, floor in checks:
                r = self.ratio(colors[fg], colors[bg])
                if r < floor:
                    failures.append("%s in %s: %s on %s is %.2f:1, needs %.1f:1"
                                    % (label, palette, colors[fg], colors[bg], r, floor))
        self.assertEqual(failures, [], (
            "the applause control fails WCAG AA:\n  " + "\n  ".join(failures)))

    def test_the_hover_fill_is_still_readable(self):
        # On hover the button inverts: --alt-cl-on-accent on --alt-cl-accent.
        for palette, on_accent in (("light", "#ffffff"), ("dark", "#12141a")):
            fill = self.PALETTES[palette]["accent"]
            r = self.ratio(on_accent, fill)
            self.assertGreaterEqual(round(r, 2), 4.5, (
                "the hovered button in %s is %s on %s at %.2f:1, under AA. A "
                "hover state is not exempt: a reader with a mouse sits in it."
                % (palette, on_accent, fill, r)))


if __name__ == "__main__":
    unittest.main()
