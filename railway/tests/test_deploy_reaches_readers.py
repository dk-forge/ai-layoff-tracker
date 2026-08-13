"""A deploy is not finished until READERS see it.

2026-08-05: 2.19.274 finished deploying at 07:34:35Z and the bare tracker URL
kept serving HTML built by 2.19.272 (superseded at 07:22) until 07:42:25Z. Every
check in the repo read green throughout, because every check asked for the URL
with a cache-busting query string, which no cache has an entry for and which the
origin therefore always answers. The origin was never the problem. Two chained
shared caches were, and the page's own `stale-while-revalidate=600` is what
licensed them to serve a superseded build for that long.

This file pins the two halves of the fix:

  * the tracker page's Cache-Control is short and carries NO
    stale-while-revalidate, in BOTH places that set it, which must agree,
  * while the public API keeps its longer lifetime, which was measured working
    and is a real speed win. A test that let the API cache be weakened along
    the way would be trading one defect for another.
  * `reader_freshness` compares what readers get against what is deployed, and
    resolves to UNKNOWN rather than PASS whenever it cannot tell propagation
    apart from staleness,
  * and the deploy workflow actually runs it.

Comments are stripped before matching, and header values are extracted from the
directive itself, so nothing here can pass because the right string appears in
prose near the wrong code.
"""
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import reader_freshness
from reader_freshness import FAIL, PASS, UNKNOWN

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PLUGIN = REPO / "wordpress-plugin" / "ai-layoff-tracker"
SHORTCODES = (PLUGIN / "includes" / "shortcodes.php").read_text(encoding="utf-8")
HTACCESS = (PLUGIN / "includes" / "htaccess.php").read_text(encoding="utf-8")
DEPLOY_YML = (REPO / ".github" / "workflows" / "deploy-plugin.yml").read_text(encoding="utf-8")

# The reader-visible ceiling. Two shared caches chain in front of the origin and
# their windows add, so this is per hop, not in total.
MAX_PAGE_S_MAXAGE = 60


def _php():
    """The php binary, or None. A missing interpreter is UNKNOWN, not a pass."""
    from shutil import which
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if Path(path).exists():
            return path
    return which("php")


def strip_php_comments(src):
    """Drop /* ... */ and // ... comments.

    Deliberately does NOT touch `#`, because htaccess.php holds Apache comment
    lines inside PHP string literals and those are data, not commentary.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def page_header_from_shortcodes():
    """The Cache-Control alt_public_page_cache_headers() actually sends."""
    body = strip_php_comments(SHORTCODES)
    func = re.search(r"function\s+alt_public_page_cache_headers\s*\(\s*\)\s*\{(.*?)\n\}", body, re.S)
    assert func, "alt_public_page_cache_headers() not found"
    call = re.search(r"header\(\s*['\"]Cache-Control:\s*([^'\"]+)['\"]\s*\)", func.group(1))
    assert call, "no Cache-Control header call inside alt_public_page_cache_headers()"
    return call.group(1).strip()


def htaccess_header_values():
    """Every `Header set Cache-Control` value, in source order, with the block it
    belongs to. Reading the directive itself keeps neighbouring comment strings
    out of the match."""
    body = strip_php_comments(HTACCESS)
    lines = body.splitlines()
    out = []
    current = None
    for line in lines:
        if "<If " in line:
            if "wp-json" in line or "query|aggregate" in line:
                current = "api"
            elif "assets/" in line:
                current = "assets"
            elif "[ ?]#" in line:
                current = "page"
            else:
                current = "other"
        found = re.search(r'Header set Cache-Control "([^"]+)"', line)
        if found:
            out.append((current, found.group(1).strip()))
    return out


def directives(value):
    return reader_freshness.parse_cache_control(value)


class TrackerPageCacheLifetime(unittest.TestCase):
    def test_page_header_has_no_stale_while_revalidate(self):
        """swr lets each shared cache serve a superseded build, and nothing in
        this repo can purge those caches."""
        cc = directives(page_header_from_shortcodes())
        self.assertNotIn("stale-while-revalidate", cc,
                         "the tracker page must not license shared caches to serve stale HTML: "
                         "a deploy cannot purge them, so the lifetime is the only bound")

    def test_page_s_maxage_is_short(self):
        cc = directives(page_header_from_shortcodes())
        self.assertIn("s-maxage", cc)
        self.assertLessEqual(cc["s-maxage"], MAX_PAGE_S_MAXAGE)

    def test_htaccess_page_block_matches_shortcodes(self):
        """Apache's block runs last and wins, so a disagreement means the PHP
        header is decorative and the real lifetime is whatever htaccess says."""
        values = dict(htaccess_header_values())
        self.assertIn("page", values, "no Cache-Control set for the tracker page block")
        self.assertEqual(values["page"], page_header_from_shortcodes())

    def test_htaccess_page_block_has_no_stale_while_revalidate(self):
        values = dict(htaccess_header_values())
        self.assertNotIn("stale-while-revalidate", directives(values["page"]))

    def test_reader_visible_staleness_is_bounded_to_minutes(self):
        """The number that matters is the one a reader can experience, which is
        the per-hop window times the number of hops."""
        worst = reader_freshness.max_reader_staleness_s(page_header_from_shortcodes())
        self.assertLessEqual(worst, 180,
                             f"a reader could be {worst}s behind a deploy")

    def test_api_cache_is_not_weakened(self):
        """The API edge cache was measured working and is a genuine speed win.
        Bounding the PAGE must not quietly bound the API too."""
        values = dict(htaccess_header_values())
        self.assertIn("api", values)
        cc = directives(values["api"])
        self.assertGreaterEqual(cc.get("s-maxage", 0), 300)

    def test_asset_immutability_is_not_weakened(self):
        values = dict(htaccess_header_values())
        self.assertIn("assets", values)
        self.assertGreaterEqual(directives(values["assets"]).get("max-age", 0), 31536000)


class ReaderFreshnessMeasuresTheReaderSurface(unittest.TestCase):
    def test_page_url_carries_no_query_string(self):
        """The entire point of the module. A cache buster here would turn it
        back into an origin check."""
        self.assertNotIn("?", reader_freshness.PAGE_URL)

    def test_reader_view_does_not_add_a_cache_buster(self):
        import inspect
        src = inspect.getsource(reader_freshness.reader_view)
        src = re.sub(r'""".*?"""', "", src, flags=re.S)
        for token in ("cb=", "uuid", "?", "time()"):
            self.assertNotIn(token, src,
                             f"reader_view() must not add {token!r} to the reader's URL")

    # The shapes below are the LIVE page's, read from
    # https://asktherecruiter.com/blog/ai-layoff-tracker/ on 2026-08-06 with a
    # browser UA and no cache buster. The plugin fingerprints its two assets as
    # ?ver=ALT_VERSION.filemtime, so the stamp carries a FOURTH segment that is
    # not part of the version; everything else on the page is somebody else's
    # asset carrying somebody else's version.
    PLUGIN_ASSETS = (
        '<link rel="stylesheet" href="https://asktherecruiter.com/blog/wp-content/plugins/'
        'ai-layoff-tracker/assets/layoffs.css?ver={v}.1785920771">'
        '<script src="https://asktherecruiter.com/blog/wp-content/plugins/'
        'ai-layoff-tracker/assets/layoffs.js?ver={v}.1785920766"></script>'
    )
    # Verbatim from the same page, and the COUNTS matter as much as the values:
    # three separate assets carry ver=2.0.86 while the plugin has only two. That
    # is how a majority vote over "the first ver= on the page" was won by
    # somebody else's version, and a fixture with one 2.0.86 in it would let the
    # broken matcher pass. Faithfulness to the live page IS the test here.
    FOREIGN_ASSETS = (
        '<link href="https://asktherecruiter.com/blog/wp-content/plugins/'
        'easy-table-of-contents/assets/css/screen.min.css?ver=2.0.86">'
        '<script src="https://asktherecruiter.com/blog/wp-content/plugins/'
        'easy-table-of-contents/assets/js/front.min.js?ver=2.0.86"></script>'
        '<script src="https://asktherecruiter.com/blog/wp-content/plugins/'
        'easy-table-of-contents/assets/js/smooth_scroll.min.js?ver=2.0.86"></script>'
        '<script src="https://asktherecruiter.com/blog/wp-content/plugins/'
        'easy-table-of-contents/vendor/sticky-kit/jquery.sticky-kit.min.js?ver=1.9.2"></script>'
        '<script src="https://asktherecruiter.com/blog/wp-includes/js/jquery/'
        'jquery.min.js?ver=3.7.1"></script>'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/'
        'chart.umd.min.js?ver=4.4.0"></script>'
    )

    def test_version_is_read_from_the_body_not_a_header(self):
        html = self.PLUGIN_ASSETS.format(v="2.19.275")
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.275")

    def test_a_foreign_version_does_not_win(self):
        """THE MEASURED INCIDENT, 2026-08-07. The guard matched the first ver=
        on the page. The theme's assets are enqueued BEFORE the plugin's, so it
        answered 2.0.86 and reported every reader on a superseded build while a
        direct read of layoffs.css showed them current. The guard built to catch
        measuring-the-wrong-surface was measuring the wrong surface."""
        html = self.FOREIGN_ASSETS + self.PLUGIN_ASSETS.format(v="2.19.275")
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.275")

    def test_a_single_stray_plugin_stamp_does_not_win(self):
        """Majority vote, still. Both plugin assets are stamped by the same
        render, so a lone odd one out is a half-uploaded FTP deploy, not the
        version the page was built from."""
        html = (self.PLUGIN_ASSETS.format(v="2.19.275")
                + '<link href="/wp-content/plugins/ai-layoff-tracker/assets/'
                  'layoffs.css?ver=2.19.100.1785000000">')
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.275")

    def test_a_superseded_build_is_still_read_as_superseded(self):
        """The point of the whole module. Narrowing WHAT is matched must not
        narrow the guard's ability to see a stale build: a reader served an old
        plugin version must still report that old version, not the new one and
        not None."""
        html = self.FOREIGN_ASSETS + self.PLUGIN_ASSETS.format(v="2.19.274")
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.274")

    def test_a_page_without_the_plugins_assets_is_not_a_version(self):
        """A page carrying only OTHER people's ver= stamps has told us nothing
        about the plugin. None routes to UNKNOWN in check(); answering 2.0.86
        here is what produced the false FAIL."""
        self.assertIsNone(reader_freshness.version_in_html(self.FOREIGN_ASSETS))

    def test_no_version_is_not_a_version(self):
        self.assertIsNone(reader_freshness.version_in_html("<html></html>"))

    def test_the_matcher_names_assets_the_plugin_actually_enqueues(self):
        """If an asset is renamed, VERSION_RE matches nothing, version_in_html
        returns None and the guard goes PERMANENTLY UNKNOWN while still running
        daily and reporting no failure. That is the species of defect this repo
        keeps finding: a mechanism that would never tell us it had stopped
        working. Pin the two names to the enqueues in the plugin source."""
        pattern = reader_freshness.VERSION_RE.pattern
        names = re.findall(r"layoffs\\\.\(\?:([a-z|]+)\)", pattern)
        self.assertTrue(names, f"VERSION_RE no longer names the plugin assets: {pattern}")
        php = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
        for ext in names[0].split("|"):
            self.assertIn(f"assets/layoffs.{ext}", php,
                          f"VERSION_RE matches layoffs.{ext} but the plugin does not "
                          f"enqueue it, so the reader check can never find a version")

    def test_staleness_counts_every_hop(self):
        """One 300s window in front of another 300s window is not 300s."""
        one_hop = 300 + 600
        self.assertEqual(
            reader_freshness.max_reader_staleness_s("public, s-maxage=300, stale-while-revalidate=600"),
            one_hop * reader_freshness.SHARED_CACHE_HOPS)

    def test_stale_if_error_is_not_counted_as_deploy_staleness(self):
        """stale-if-error only applies when the origin is failing, which is the
        one case where a stale page is the better answer."""
        self.assertEqual(
            reader_freshness.max_reader_staleness_s("public, s-maxage=60, stale-if-error=600"),
            60 * reader_freshness.SHARED_CACHE_HOPS)


class ReaderFreshnessVerdicts(unittest.TestCase):
    """check() must never turn "I could not tell" into "healthy"."""

    def _patch(self, served, deployed, cache_control="public, max-age=60, s-maxage=60",
               served_build="same", deployed_build="same"):
        # Default: the two builds AGREE, so these cases keep testing exactly what
        # they were written to test, which is the VERSION comparison.
        reader_freshness.reader_view = lambda *a, **k: reader_freshness.ReaderView(
            served, served_build, {"cache-control": cache_control})
        reader_freshness.origin_build = lambda *a, **k: (deployed, deployed_build)

    def setUp(self):
        self._real_view = reader_freshness.reader_view
        self._real_origin = reader_freshness.origin_build

    def tearDown(self):
        reader_freshness.reader_view = self._real_view
        reader_freshness.origin_build = self._real_origin

    def test_match_is_a_pass(self):
        self._patch("2.19.275", "2.19.275")
        self.assertEqual(reader_freshness.check(deploy_finished_at=None).verdict, PASS)

    def test_mismatch_without_a_deploy_time_is_unknown_not_pass(self):
        self._patch("2.19.272", "2.19.275")
        result = reader_freshness.check(deploy_finished_at=None)
        self.assertEqual(result.verdict, UNKNOWN)
        self.assertFalse(result.ok)

    def test_mismatch_inside_the_window_is_propagation(self):
        self._patch("2.19.272", "2.19.275")
        now = datetime.now(timezone.utc)
        result = reader_freshness.check(deploy_finished_at=now - timedelta(seconds=30), now=now)
        self.assertEqual(result.verdict, PASS)

    def test_mismatch_past_the_window_fails(self):
        self._patch("2.19.272", "2.19.275")
        now = datetime.now(timezone.utc)
        result = reader_freshness.check(deploy_finished_at=now - timedelta(minutes=18), now=now)
        self.assertEqual(result.verdict, FAIL)
        self.assertFalse(result.ok)

    def test_the_measured_incident_would_have_failed(self):
        """The exact 2026-08-05 shape: 2.19.274 deployed 07:34:35Z, readers
        still on 2.19.272 at 07:42:25Z, under the OLD headers."""
        self._patch("2.19.272", "2.19.274",
                    cache_control="public, max-age=180, s-maxage=300, stale-while-revalidate=600")
        deployed_at = datetime(2026, 8, 5, 7, 34, 35, tzinfo=timezone.utc)
        observed_at = datetime(2026, 8, 5, 7, 42, 25, tzinfo=timezone.utc)
        # Under the old headers the permitted window was so wide it swallowed
        # the incident, which is the second half of why nobody saw it.
        self.assertEqual(
            reader_freshness.check(deploy_finished_at=deployed_at, now=observed_at).verdict, PASS)
        # Under the new headers the same observation is a fault.
        self._patch("2.19.272", "2.19.274", cache_control="public, max-age=60, s-maxage=60")
        self.assertEqual(
            reader_freshness.check(deploy_finished_at=deployed_at, now=observed_at).verdict, FAIL)

    def test_an_unreadable_reader_view_is_unknown(self):
        """The host 504s under load. An outage is not evidence of a stale
        deploy, and it is not evidence of a healthy one either."""
        import urllib.error

        def boom(*a, **k):
            raise urllib.error.URLError("host unreachable")

        reader_freshness.reader_view = boom
        result = reader_freshness.check(deploy_finished_at=None)
        self.assertEqual(result.verdict, UNKNOWN)
        self.assertFalse(result.ok)


class TheRacedRenderOf2_20_21(unittest.TestCase):
    """THE MEASURED INCIDENT, 2026-08-12/13. Version right, BODY wrong.

    2.20.21 deployed cleanly. The reader check then requested the bare URL, as
    it must, and that request arrived while FTPS was still uploading:
    ai-layoff-tracker.php (which carries ALT_VERSION) had landed,
    templates/page-tracker.php had not. WP Super Cache stored that render, so
    every reader got asset URLs stamped `ver=2.20.21` wrapped around the
    PREVIOUS template, for about twenty-five minutes.

    `reader_freshness.check()` compared the served version against the deployed
    version, they were both 2.20.21, and it returned PASS the whole time. It
    dated the build, not the content.

    The fixture below is not a fabricated pair of hashes. It materialises two
    real plugin trees whose ALT_VERSION is byte-identical and whose
    page-tracker.php is not, which is precisely the raced pair, and runs the
    real stamp function over them.
    """

    def _trees(self):
        """(new_tree, raced_tree): same version, one template different."""
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        new, raced = root / "new", root / "raced"
        shutil.copytree(PLUGIN, new)
        shutil.copytree(PLUGIN, raced)
        # The one file that had not landed yet. Its PREVIOUS content is what the
        # reader was served; any different bytes reproduce that, and the version
        # file is untouched on purpose, because that is the whole defect.
        tpl = raced / "templates" / "page-tracker.php"
        current = tpl.read_text(encoding="utf-8")
        old_body = self._previous_revision(tpl)
        if not old_body or old_body == current:
            old_body = current + \
                "\n<!-- the copy of this template that had not finished uploading -->\n"
        tpl.write_text(old_body, encoding="utf-8")
        self.assertNotEqual((new / "templates" / "page-tracker.php").read_bytes(),
                            tpl.read_bytes(), "the raced tree must differ in the body")
        return new, raced

    @staticmethod
    def _previous_revision(tpl):
        """The template's actual previous content, when git history is here.

        Preferred, because then the pair is two real builds rather than one real
        build and an edit. CI checks out shallow, so this is often unavailable;
        a byte-level edit reproduces the same shape and the verdict logic cannot
        tell the difference, since all it ever sees is two stamps.
        """
        import subprocess
        rel = "wordpress-plugin/ai-layoff-tracker/templates/page-tracker.php"
        try:
            out = subprocess.run(["git", "-C", str(REPO), "show", f"HEAD~1:{rel}"],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout if out.returncode == 0 and out.stdout else None

    def test_the_two_trees_agree_on_the_version_and_that_is_the_point(self):
        new, raced = self._trees()
        main = "ai-layoff-tracker.php"
        self.assertEqual((new / main).read_bytes(), (raced / main).read_bytes(),
                         "the fixture must differ ONLY in the body, or it is not the "
                         "2.20.21 shape")

    def test_the_old_rule_passes_the_raced_page(self):
        """The rule this file used to hold, stated as code: served version ==
        deployed version, and nothing else. Both are 2.20.21."""
        new, raced = self._trees()
        served_version = deployed_version = re.search(
            r"define\('ALT_VERSION',\s*'([^']+)'\)",
            (raced / "ai-layoff-tracker.php").read_text(encoding="utf-8")).group(1)
        self.assertEqual(served_version, deployed_version,
                         "the version-only rule cannot see this, which is why it passed")
        # And the bodies really do differ, so a check that could see content
        # would have something to see.
        self.assertNotEqual(
            reader_freshness.checkout_build_stamp(new),
            reader_freshness.checkout_build_stamp(raced))

    def test_the_new_rule_refuses_the_raced_page(self):
        new, raced = self._trees()
        served_build = reader_freshness.checkout_build_stamp(raced)
        deployed_build = reader_freshness.checkout_build_stamp(new)
        version = "2.20.21"
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build
        reader_freshness.reader_view = lambda *a, **k: reader_freshness.ReaderView(
            version, served_build, {"cache-control": "public, max-age=60, s-maxage=60"})
        reader_freshness.origin_build = lambda *a, **k: (version, deployed_build)
        try:
            now = datetime.now(timezone.utc)
            result = reader_freshness.check(
                deploy_finished_at=now - timedelta(minutes=25), now=now)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
        self.assertEqual(result.verdict, FAIL, result.detail)
        self.assertFalse(result.ok)
        self.assertIn("2.20.21", result.detail)

    def test_the_same_page_inside_the_window_is_propagation_not_a_fault(self):
        """A stamp mismatch seconds after a deploy is a cache that has not
        turned over yet. Reporting that as a fault on every deploy is how a
        check gets removed."""
        new, raced = self._trees()
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build
        reader_freshness.reader_view = lambda *a, **k: reader_freshness.ReaderView(
            "2.20.21", reader_freshness.checkout_build_stamp(raced),
            {"cache-control": "public, max-age=60, s-maxage=60"})
        reader_freshness.origin_build = lambda *a, **k: (
            "2.20.21", reader_freshness.checkout_build_stamp(new))
        try:
            now = datetime.now(timezone.utc)
            result = reader_freshness.check(
                deploy_finished_at=now - timedelta(seconds=30), now=now)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
        self.assertEqual(result.verdict, PASS, result.detail)


class TheBuildStampTiesTheBodyToTheBuild(unittest.TestCase):
    STAMP = '<!-- alt-build ver=2.20.29 build=0123456789abcdef -->'

    def test_a_stamp_is_read_out_of_the_body(self):
        self.assertEqual(reader_freshness.build_in_html("<div>x</div>" + self.STAMP),
                         "0123456789abcdef")

    def test_a_page_without_a_stamp_is_not_a_build(self):
        """None routes to UNKNOWN in check(). A page that cannot say which bytes
        rendered it has not told us it is current."""
        self.assertIsNone(reader_freshness.build_in_html("<html><body>x</body></html>"))

    def test_two_different_stamps_on_one_page_are_not_a_build(self):
        """Half a page from one build and half from another is exactly the state
        this exists to catch, and it is not a value to compare."""
        other = self.STAMP.replace("0123456789abcdef", "fedcba9876543210")
        self.assertIsNone(reader_freshness.build_in_html(self.STAMP + other))

    def test_the_stamp_covers_the_templates(self):
        """A stamp that ignored the templates would have passed 2.20.21 too."""
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        tree = root / "p"
        shutil.copytree(PLUGIN, tree)
        before = reader_freshness.checkout_build_stamp(tree)
        tpl = tree / "templates" / "page-tracker.php"
        tpl.write_text(tpl.read_text(encoding="utf-8") + "\n<!-- x -->", encoding="utf-8")
        self.assertNotEqual(before, reader_freshness.checkout_build_stamp(tree))

    def test_the_stamp_covers_the_assets_a_reader_loads(self):
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        tree = root / "p"
        shutil.copytree(PLUGIN, tree)
        before = reader_freshness.checkout_build_stamp(tree)
        css = tree / "assets" / "layoffs.css"
        css.write_text(css.read_text(encoding="utf-8") + "\n/* x */", encoding="utf-8")
        self.assertNotEqual(before, reader_freshness.checkout_build_stamp(tree))

    def test_the_rendered_page_actually_carries_the_stamp(self):
        """alt_template() is EXECUTED, not read. The stamp only does its job if
        it leaves with the body, once, ahead of it, and a source-reading test
        cannot tell whether it does."""
        php = _php()
        if not php:
            self.skipTest("UNKNOWN, NOT passing: php not installed here")
        import shutil
        import subprocess
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        tree = root / "p"
        shutil.copytree(PLUGIN, tree)
        (tree / "templates" / "stub.php").write_text("<div>BODY</div>", encoding="utf-8")

        src = SHORTCODES
        needle = "function alt_template("
        body = src[src.index(needle):]
        alt_template = body[:body.index("\n}\n") + 3]
        script = ("define('ABSPATH','/'); define('ALT_VERSION','9.9.9');"
                  "define('ALT_PLUGIN_DIR','%s/');"
                  "function trailingslashit($p){return rtrim($p,'/').'/';}"
                  "function esc_html($s){return $s;}"
                  "require '%s/includes/build-stamp.php';"
                  "%s"
                  "echo alt_template('stub.php'); echo alt_template('stub.php');"
                  % (tree, tree, alt_template))
        out = subprocess.run([php, "-r", script], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        stamps = reader_freshness.BUILD_RE.findall(out.stdout)
        self.assertEqual(len(stamps), 1,
                         "a rendered page must carry exactly ONE build stamp, ahead of "
                         "the body it belongs to; got %r" % out.stdout[:200])
        self.assertEqual(stamps[0], reader_freshness.checkout_build_stamp(tree))
        self.assertLess(out.stdout.index("alt-build"), out.stdout.index("BODY"))

    def test_php_and_python_compute_the_same_stamp(self):
        """Two implementations of one number is a drift risk, so it is executed
        rather than read: the PHP the server runs is called on the same tree the
        Python reads, and the answers must be equal."""
        php = _php()
        if not php:
            self.skipTest("UNKNOWN, NOT passing: php not installed here")
        import subprocess
        script = ("define('ABSPATH', '/'); define('ALT_PLUGIN_DIR', '%s/');"
                  "function trailingslashit($p){return rtrim($p,'/').'/';}"
                  "require '%s'; echo alt_build_stamp();"
                  % (PLUGIN, PLUGIN / "includes" / "build-stamp.php"))
        out = subprocess.run([php, "-r", script], capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(),
                         reader_freshness.checkout_build_stamp(PLUGIN),
                         "the PHP that stamps the page and the Python that grades it "
                         "disagree about what this build is")


class TheCheckDoesNotFillTheCacheItIsMeasuring(unittest.TestCase):
    """2.20.21 was cached BY THE VERIFICATION REQUEST. The bare URL is the
    surface, so the request cannot be avoided; what can be avoided is making it
    while the origin is still incoherent."""

    def test_wait_for_asks_the_origin_first(self):
        calls = []
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build

        def origin(*a, **k):
            calls.append("origin")
            # Incoherent twice (mid-upload), then coherent.
            return ("2.20.29", "new") if len(calls) > 2 else ("2.20.29", "raced")

        def view(*a, **k):
            calls.append("reader")
            return reader_freshness.ReaderView("2.20.29", "new", {})

        reader_freshness.origin_build, reader_freshness.reader_view = origin, view
        try:
            delay = reader_freshness.wait_for("2.20.29", expected_build="new",
                                              timeout=60, interval=0, log=lambda *a: None)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
        self.assertIsNotNone(delay)
        self.assertNotIn("reader", calls[:calls.index("reader")],
                         "sanity")
        self.assertEqual(calls[:3], ["origin", "origin", "origin"],
                         "the bare URL must not be requested until the ORIGIN reports "
                         "the expected build: a request made before that is what filled "
                         "the page cache with the raced render on 2.20.21")


    def test_an_origin_that_never_matches_the_checkout_is_adopted_and_announced(self):
        """A file on the server that is not in this checkout would otherwise
        redden every deploy forever, and a check that cries wolf on every deploy
        gets deleted. The gate adopts the ORIGIN's build, says so loudly, and
        keeps the comparison that actually catches a cached mid-upload render."""
        said = []
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build
        real_gate = reader_freshness.ORIGIN_GATE_S
        reader_freshness.ORIGIN_GATE_S = 0        # the gate expires immediately
        reader_freshness.origin_build = lambda *a, **k: ("2.20.31", "origin-build")
        reader_freshness.reader_view = lambda *a, **k: reader_freshness.ReaderView(
            "2.20.31", "origin-build", {})
        try:
            delay = reader_freshness.wait_for("2.20.31", expected_build="checkout-build",
                                              timeout=60, interval=0, log=said.append)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
            reader_freshness.ORIGIN_GATE_S = real_gate
        self.assertIsNotNone(delay, "the deploy must not go red over a file inventory "
                                    "difference that no reader can see")
        self.assertTrue(any("::warning::" in line and "not byte-identical" in line
                            for line in said), said)

    def test_an_origin_with_no_stamp_degrades_loudly_to_the_version(self):
        """A running build older than the stamp has nothing to compare a body
        against. Degrade to the version-only wait and SAY that it is the check
        which passed 2.20.21, rather than failing a deploy for it."""
        said = []
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build
        real_gate = reader_freshness.ORIGIN_GATE_S
        reader_freshness.ORIGIN_GATE_S = 0
        reader_freshness.origin_build = lambda *a, **k: ("2.20.32", None)
        reader_freshness.reader_view = lambda *a, **k: reader_freshness.ReaderView(
            "2.20.32", None, {})
        try:
            delay = reader_freshness.wait_for("2.20.32", expected_build="checkout-build",
                                              timeout=60, interval=0, log=said.append)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
            reader_freshness.ORIGIN_GATE_S = real_gate
        self.assertIsNotNone(delay)
        self.assertTrue(any("::warning::" in line and "2.20.21" in line for line in said), said)

    def test_an_origin_that_never_reports_the_version_is_not_adopted(self):
        """Adoption is for a build difference, never for a deploy that did not
        land. A version that never arrives still fails, and the bare URL is
        never requested, so nothing is cached by the attempt."""
        said = []
        real_view, real_origin = reader_freshness.reader_view, reader_freshness.origin_build
        real_gate = reader_freshness.ORIGIN_GATE_S
        reader_freshness.ORIGIN_GATE_S = 0
        reader_freshness.origin_build = lambda *a, **k: ("2.20.30", "old-build")
        reader_freshness.reader_view = lambda *a, **k: self.fail(
            "the bare URL must not be requested when the origin never reported the "
            "expected version")
        try:
            delay = reader_freshness.wait_for("2.20.31", expected_build="checkout-build",
                                              timeout=1, interval=0, log=said.append)
        finally:
            reader_freshness.reader_view, reader_freshness.origin_build = real_view, real_origin
            reader_freshness.ORIGIN_GATE_S = real_gate
        self.assertIsNone(delay)


class TheGuardIsActuallyWired(unittest.TestCase):
    def test_deploy_workflow_runs_the_reader_check(self):
        body = re.sub(r"^\s*#.*$", "", DEPLOY_YML, flags=re.M)
        self.assertIn("reader_freshness.py", body,
                      "the deploy workflow must verify the deploy reached readers")
        self.assertIn("--wait-for", body)

    def test_the_deploy_gate_is_the_checkout_build_not_just_the_version(self):
        """The deploy workflow passes only ALT_VERSION, so the module must
        derive the expected BUILD from the checkout itself. A deploy that waited
        on the version alone is the check that passed 2.20.21."""
        import inspect
        src = inspect.getsource(reader_freshness.main)
        self.assertIn("checkout_build_stamp", src)

    def test_the_plugin_emits_the_stamp_from_the_template_funnel(self):
        """The stamp has to be produced by the same render as the body. Emitted
        anywhere else it is another version string with extra steps."""
        body = strip_php_comments(SHORTCODES)
        func = re.search(r"function\s+alt_template\s*\(.*?\n\}", body, re.S)
        self.assertIsNotNone(func, "alt_template() not found")
        self.assertIn("alt_build_stamp", func.group(0),
                      "alt_template() must stamp what it renders")

    def test_the_origin_reports_its_own_build(self):
        api = strip_php_comments((PLUGIN / "includes" / "api.php").read_text(encoding="utf-8"))
        status = re.search(r"function\s+alt_api_status_get\s*\(.*?\n\}", api, re.S)
        self.assertIsNotNone(status)
        self.assertIn("alt_build_stamp", status.group(0),
                      "/status must report the build the origin would render, or the "
                      "reader's stamp has nothing cache-immune to be compared against")

    def test_ops_status_reports_the_reader_view(self):
        ops = (REPO / "railway" / "ops_status.py").read_text(encoding="utf-8")
        ops = re.sub(r'""".*?"""', "", ops, flags=re.S)
        ops = re.sub(r"^\s*#.*$", "", ops, flags=re.M)
        self.assertIn("reader_freshness", ops)

    def test_the_job_outlives_the_wait_it_is_asked_to_perform(self):
        """MEASURED 2026-08-07. The reader check polls up to --timeout 600s
        inside a job with timeout-minutes: 6 (360s), so the wait could never
        run to completion: the job was killed first. Every deploy from
        2026-08-05 08:00 onward ran all of its steps successfully, including
        this one, and was then reported CANCELLED at 366 to 380 seconds.
        Successful deploys before the reader step took 61 to 114 seconds.

        Two things that costs. CLAUDE.md tells an egress-blocked session that a
        green deploy run IS the proof a change is live, and there had been no
        green deploy run for two days. And red CI mails the owner, so a
        timeout that fires on every single deploy is a subscription to noise.

        It is also the same shape as the archive defect fixed the same day: a
        knob configured for a capacity its container never permits.
        """
        body = re.sub(r"^\s*#.*$", "", DEPLOY_YML, flags=re.M)
        job = re.search(r"timeout-minutes:\s*(\d+)", body)
        self.assertIsNotNone(job, "deploy-plugin.yml lost its job timeout")
        wait = re.search(r"--timeout\s+(\d+)", body)
        self.assertIsNotNone(wait, "the reader check lost its --timeout")
        job_s, wait_s = int(job.group(1)) * 60, int(wait.group(1))
        # 114s is the slowest deploy measured WITHOUT the reader wait.
        self.assertGreater(
            job_s, wait_s + 114,
            f"deploy-plugin.yml allows the job {job_s}s but asks the reader check to "
            f"wait up to {wait_s}s on top of a deploy measured at up to 114s. The wait "
            f"can never finish, so a fully successful deploy is reported as cancelled.")


if __name__ == "__main__":
    unittest.main()
