"""Related-post titles override theme wrapping on article pages (todo#2784).

Offline cascade fixture, not a capture of the current production stylesheet.
It models a more-specific WordPress title rule ahead of the plugin stylesheet.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "railway"))
from cdp import Browser  # noqa: E402

CSS = ROOT / "wordpress-plugin/ai-layoff-tracker/assets/blog-reading.css"
THEME = """
body { margin: 0; }
body .wp-block-post-template h3.wp-block-post-title { text-wrap: wrap; }
.wp-block-post-template { width: min(90vw, 360px); }
"""
TITLES = """
<section class="wp-block-post-template">
  <h3 class="wp-block-post-title">Can You Apply to Two Jobs at the Same Company?</h3>
  <h3 class="wp-block-post-title">Check your resume against the job description</h3>
</section>
"""


def measure(browser, body_class, plugin_css):
    html = ("<!doctype html><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<style>{THEME}</style><style>{plugin_css}</style>"
            f"<body class='{body_class}'>{TITLES}</body>")
    class FixtureHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            browser.navigate(f"http://127.0.0.1:{server.server_port}/")
        finally:
            server.shutdown()
            thread.join()
    return browser.eval_js("""[...document.querySelectorAll(
        '.wp-block-post-template h3.wp-block-post-title'
    )].map(el => getComputedStyle(el).textWrap)""")


class RelatedTitleWrapping(unittest.TestCase):
    def test_article_titles_balance_at_phone_and_desktop_widths(self):
        for width in (390, 1280):
            with self.subTest(width=width), Browser(width=width) as browser:
                self.assertEqual(measure(browser, "single-post", CSS.read_text()),
                                 ["balance", "balance"])

    def test_theme_wrap_is_reproduced_without_the_plugin(self):
        with Browser(width=390) as browser:
            self.assertEqual(measure(browser, "single-post", ""), ["wrap", "wrap"])

    def test_non_article_pages_keep_their_theme_wrapping(self):
        with Browser(width=390) as browser:
            self.assertEqual(measure(browser, "archive", CSS.read_text()),
                             ["wrap", "wrap"])


if __name__ == "__main__":
    unittest.main()
