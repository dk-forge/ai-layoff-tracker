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

    def test_version_is_read_from_the_body_not_a_header(self):
        html = '<link href="/a.css?ver=2.19.275"><script src="/b.js?ver=2.19.275">'
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.275")

    def test_a_single_stray_version_does_not_win(self):
        html = ('<link href="/a.css?ver=2.19.275"><link href="/b.css?ver=2.19.275">'
                '<link href="/third-party.css?ver=1.9.2">')
        self.assertEqual(reader_freshness.version_in_html(html), "2.19.275")

    def test_no_version_is_not_a_version(self):
        self.assertIsNone(reader_freshness.version_in_html("<html></html>"))

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

    def _patch(self, served, deployed, cache_control="public, max-age=60, s-maxage=60"):
        reader_freshness.reader_view = lambda *a, **k: (served, {"cache-control": cache_control})
        reader_freshness.deployed_version = lambda *a, **k: deployed

    def setUp(self):
        self._real_view = reader_freshness.reader_view
        self._real_deployed = reader_freshness.deployed_version

    def tearDown(self):
        reader_freshness.reader_view = self._real_view
        reader_freshness.deployed_version = self._real_deployed

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


class TheGuardIsActuallyWired(unittest.TestCase):
    def test_deploy_workflow_runs_the_reader_check(self):
        body = re.sub(r"^\s*#.*$", "", DEPLOY_YML, flags=re.M)
        self.assertIn("reader_freshness.py", body,
                      "the deploy workflow must verify the deploy reached readers")
        self.assertIn("--wait-for", body)

    def test_ops_status_reports_the_reader_view(self):
        ops = (REPO / "railway" / "ops_status.py").read_text(encoding="utf-8")
        ops = re.sub(r'""".*?"""', "", ops, flags=re.S)
        ops = re.sub(r"^\s*#.*$", "", ops, flags=re.M)
        self.assertIn("reader_freshness", ops)


if __name__ == "__main__":
    unittest.main()
