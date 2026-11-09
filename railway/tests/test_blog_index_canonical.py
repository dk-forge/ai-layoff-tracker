"""Guardrail (the live /blog/ is a STATIC front page, page 36: is_front_page(), not is_home()): the blog posts index and its /page/N/ pages self-canonicalise.

Live 2026-11-09: /blog/, /blog/page/2/, /blog/page/3/ and /blog/?utm_*= all
served <link rel="canonical" href=".../blog/blog/">, a URL that 404s. Google
ignores a canonical that points at a 404 and picks its own, which Search
Console reports as "Duplicate without user-selected canonical".
"""
import subprocess
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "wordpress-plugin/ai-layoff-tracker"
MODULE_PATH = PLUGIN / "includes/blog-canonical.php"
BOOTSTRAP = (PLUGIN / "ai-layoff-tracker.php").read_text()


class BlogIndexCanonical(unittest.TestCase):
    def test_module_is_loaded(self):
        self.assertIn("includes/blog-canonical.php", BOOTSTRAP)

    def test_both_seo_plugins_are_hooked(self):
        src = MODULE_PATH.read_text()
        for hook in ("wpseo_canonical", "rank_math/frontend/canonical"):
            self.assertIn(f"'{hook}'", src)

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_canonical_is_request_path_without_query(self):
        harness = f"""<?php
        define('ABSPATH', '/');
        $GLOBALS['alt_is_home'] = false; $GLOBALS['alt_is_front'] = true;
        function add_filter() {{}}
        function is_home() {{ return $GLOBALS['alt_is_home']; }}
        function is_front_page() {{ return $GLOBALS['alt_is_front']; }}
        function home_url($p = '') {{ return 'https://asktherecruiter.com/blog' . $p; }}
        require '{MODULE_PATH}';
        $cases = array(
          '/blog/' => 'https://asktherecruiter.com/blog/',
          '/blog/?utm_source=x&ref=y' => 'https://asktherecruiter.com/blog/',
          '/blog/page/2/' => 'https://asktherecruiter.com/blog/page/2/',
          '/blog/page/3' => 'https://asktherecruiter.com/blog/page/3/',
        );
        foreach ($cases as $uri => $want) {{
          $_SERVER['REQUEST_URI'] = $uri;
          $got = alt_blog_index_canonical('https://asktherecruiter.com/blog/blog/');
          if ($got !== $want) {{ echo "FAIL $uri => $got\\n"; exit(1); }}
        }}
        $GLOBALS['alt_is_home'] = true; $GLOBALS['alt_is_front'] = false;
        $_SERVER['REQUEST_URI'] = '/blog/page/2/';
        if (alt_blog_index_canonical('X') !== 'https://asktherecruiter.com/blog/page/2/') {{ echo "FAIL posts-page\n"; exit(1); }}
        $GLOBALS['alt_is_home'] = false;
        $_SERVER['REQUEST_URI'] = '/blog/some-post/';
        if (alt_blog_index_canonical('X') !== 'X') {{ echo "FAIL non-home\\n"; exit(1); }}
        echo "OK";
        """
        r = subprocess.run(["php", "-r", harness.replace("<?php", "", 1)],
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "OK", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
