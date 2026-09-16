"""AN ORDINARY RENDER MUST NOT HASH THE PLUGIN, AND A PAGE THAT EXISTS MUST NOT
BE LOOKED UP ON EVERY REQUEST FOREVER.

WHY THIS FILE EXISTS. On 2026-09-12/13 the shared blog host fell over four
times in twenty hours, and the investigation ranked per-request plugin work
third among the causes. Two shapes, both in wordpress-plugin/ai-layoff-tracker:

  1. alt_build_stamp() hashed every deployed file (66 files, about 3.1 MB,
     sha256) on every uncached render of every plugin surface, and since
     2.20.191 on the contact page too. Its docblock refused a cross-request
     cache on purpose: a stamp cached during an FTPS upload would outlive the
     race it exists to expose. That guarantee is kept a different way. The
     stamp is cached in a transient keyed by the plugin version AND a stat
     pass over the same file set (count, sizes, mtimes). A half-uploaded tree
     has a different key from the finished one, so a stamp cached mid-upload
     is invalidated by the next file that lands, and an ordinary render costs
     one stat pass instead of 66 digests. /status?build=1 still forces a fresh
     hash, because that is the reader check's source of truth twice a deploy.

  2. Seven alt_ensure_*_page_once hooks at init priority 20 each called
     get_page_by_path on every request and returned early without recording
     that the page exists, and alt_ensure_quarterly_report_page_once had no
     guard at all and called get_page_by_path twice per request. Each now
     mirrors alt_ensure_contact_page_once: a done-option, written only once the
     page is verified to exist, and a short-lived lock around the create.

The tests read the PHP as text (the shape) and run the stamp under the php CLI
with fake transient functions (the behaviour). What they create is unchanged;
the pinned thing is that a request after the page exists does no page lookup.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from shutil import which

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "wordpress-plugin" / "ai-layoff-tracker"
MAIN = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
STAMP = (PLUGIN / "includes" / "build-stamp.php").read_text(encoding="utf-8")
API = (PLUGIN / "includes" / "api.php").read_text(encoding="utf-8")

# Every page hook that runs on public init, with the path it verifies.
PAGE_HOOKS = {
    "alt_ensure_tracker_health_page_once": "ai-layoff-tracker/ai-tracker-health",
    "alt_ensure_report_page_once": "ai-layoff-tracker/report",
    "alt_ensure_sources_page_once": "ai-layoff-tracker/sources",
    "alt_ensure_ai_quotes_page_once": "ai-layoff-tracker/ai-quotes",
    "alt_ensure_methodology_page_once": "ai-layoff-tracker/methodology",
    "alt_ensure_publisher_page_once": "ai-layoff-tracker/publisher-tools",
    "alt_ensure_press_page_once": "ai-layoff-tracker/press",
    "alt_ensure_quarterly_report_page_once": "ai-layoff-tracker/state-of-layoffs",
}


def _function_body(src, name):
    start = src.index("function %s(" % name)
    end = src.index("\n}\n", start) + 3
    return src[start:end]


def _php():
    for path in ("/opt/homebrew/bin/php", "/usr/bin/php", "/usr/local/bin/php"):
        if os.path.exists(path):
            return path
    return which("php")


class EveryPageHookRecordsThatThePageExists(unittest.TestCase):
    def test_each_hook_reads_a_done_option_before_any_page_lookup(self):
        for name, path in PAGE_HOOKS.items():
            body = _function_body(MAIN, name)
            self.assertIn(path, body, name)
            opt = re.search(r"get_option\('(alt_[a-z_]+_page_done)'\)", body)
            self.assertIsNotNone(opt, "%s has no done-option guard" % name)
            self.assertLess(body.index("get_option("), body.index("get_page_by_path("),
                            "%s must read its done-option before it queries pages" % name)

    def test_the_done_option_is_written_only_when_the_page_is_verified(self):
        for name in PAGE_HOOKS:
            body = _function_body(MAIN, name)
            opt = re.search(r"get_option\('(alt_[a-z_]+_page_done)'\)", body).group(1)
            self.assertIn("update_option('%s'" % opt, body,
                          "%s never records success" % name)
            # The write sits inside the branch that found the page, never
            # unconditionally after the insert: a failed insert must retry.
            found = body.index("get_page_by_path(")
            self.assertGreater(body.index("update_option('%s'" % opt), found, name)

    def test_done_options_are_distinct_per_page(self):
        opts = [re.search(r"get_option\('(alt_[a-z_]+_page_done)'\)",
                          _function_body(MAIN, n)).group(1) for n in PAGE_HOOKS]
        self.assertEqual(len(opts), len(set(opts)), opts)
        self.assertNotIn("alt_contact_page_done", opts)

    def test_each_hook_takes_the_short_lived_lock_the_contact_hook_takes(self):
        for name in PAGE_HOOKS:
            body = _function_body(MAIN, name)
            self.assertRegex(body, r"get_transient\('alt_[a-z_]+_page_lock'\)", name)
            self.assertRegex(body, r"set_transient\('alt_[a-z_]+_page_lock', 1, MINUTE_IN_SECONDS\)", name)

    def test_the_quarterly_hook_no_longer_queries_twice_on_every_request(self):
        body = _function_body(MAIN, "alt_ensure_quarterly_report_page_once")
        self.assertIn("get_option('alt_quarterly_report_page_done')", body)


class TheBuildStampIsCachedAcrossRequestsByWhatIsOnDisk(unittest.TestCase):
    def test_the_stamp_reads_a_transient_keyed_on_version_and_a_stat_pass(self):
        body = _function_body(STAMP, "alt_build_stamp")
        self.assertIn("get_transient(", body)
        self.assertIn("set_transient(", body)
        self.assertIn("alt_build_stat_key(", body)
        key = _function_body(STAMP, "alt_build_stat_key")
        for needle in ("ALT_VERSION", "filemtime(", "filesize("):
            self.assertIn(needle, key)

    def test_the_stamp_still_answers_without_wordpress(self):
        """Standalone use survives: a mid-upload request may have no WP yet."""
        body = _function_body(STAMP, "alt_build_stamp")
        self.assertIn("function_exists('get_transient')", body)
        self.assertIn("function_exists('set_transient')", body)

    def test_status_build_forces_a_fresh_hash(self):
        self.assertIn("$payload['build_stamp'] = alt_build_stamp(true);", API)

    def _run(self, tree, fake, call="alt_build_stamp()"):
        php = _php()
        if not php:
            self.skipTest("UNKNOWN, NOT passing: php not installed here")
        script = ("define('ABSPATH','/'); define('ALT_VERSION','9.9.9');"
                  "define('ALT_PLUGIN_DIR','%s/');"
                  "function trailingslashit($p){return rtrim($p,'/').'/';}"
                  "%s require '%s/includes/build-stamp.php'; echo %s;"
                  % (tree, fake, tree, call))
        out = subprocess.run([php, "-r", script], capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def _tree(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        tree = root / "plugin"
        shutil.copytree(PLUGIN, tree)
        return tree

    FAKE_EMPTY = ("$GLOBALS['t']=array();"
                  "function get_transient($k){return isset($GLOBALS['t'][$k])?$GLOBALS['t'][$k]:false;}"
                  "function set_transient($k,$v,$e=0){$GLOBALS['t'][$k]=$v;return true;}")

    def test_a_cached_stamp_with_a_matching_key_is_served_without_hashing(self):
        tree = self._tree()
        real = self._run(tree, self.FAKE_EMPTY)
        self.assertRegex(real, r"^[a-f0-9]{16}$")
        # A transient that holds a different stamp under the key this tree
        # produces right now. If the cache is consulted, that is the answer.
        fake = ("function get_transient($k){return array('key'=>alt_build_stat_key(),"
                "'stamp'=>'cafecafecafecafe');}"
                "function set_transient($k,$v,$e=0){return true;}")
        self.assertEqual(self._run(tree, fake), "cafecafecafecafe")
        # And the forced path ignores it: this is what /status?build=1 reads.
        self.assertEqual(self._run(tree, fake, "alt_build_stamp(true)"), real)

    def test_a_file_that_lands_after_the_cache_was_written_invalidates_it(self):
        """The mid-upload guarantee from the old docblock, restated."""
        tree = self._tree()
        before = self._run(tree, self.FAKE_EMPTY, "alt_build_stat_key()")
        tpl = tree / "templates" / "page-tracker.php"
        tpl.write_text(tpl.read_text(encoding="utf-8") + "\n<!-- landed later -->\n",
                       encoding="utf-8")
        os.utime(tpl, (os.path.getmtime(tpl) + 5, os.path.getmtime(tpl) + 5))
        after = self._run(tree, self.FAKE_EMPTY, "alt_build_stat_key()")
        self.assertNotEqual(before, after)
        # A stamp cached under the OLD key is not served for the new tree.
        fake = ("function get_transient($k){return array('key'=>'%s','stamp'=>'cafecafecafecafe');}"
                "function set_transient($k,$v,$e=0){return true;}" % before)
        self.assertNotEqual(self._run(tree, fake), "cafecafecafecafe")

    def test_the_cached_value_is_the_same_number_the_python_half_computes(self):
        import sys
        sys.path.insert(0, str(REPO / "railway"))
        import reader_freshness
        tree = self._tree()
        self.assertEqual(self._run(tree, self.FAKE_EMPTY),
                         reader_freshness.checkout_build_stamp(tree))


if __name__ == "__main__":
    unittest.main()
