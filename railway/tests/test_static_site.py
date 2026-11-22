"""Offline build contract, using an independent synthetic sitemap baseline."""
import copy
import hashlib
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import static_site


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class StaticSite(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.output = self.root / "dist"
        self.urls = ["https://asktherecruiter.com/blog/ai-layoff-tracker/",
                     "https://asktherecruiter.com/blog/company-layoffs/acme/"]
        xml = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               '<url><loc>https://asktherecruiter.com/blog/ai-layoff-tracker/</loc></url>'
               '<url><loc>https://asktherecruiter.com/blog/company-layoffs/acme/</loc></url>'
               '</urlset>')
        self.files = {"sitemap.xml": xml.encode(), "robots.txt": b"User-agent: *\nAllow: /\n"}
        self.manifest = {
            "schema": 1, "captured_at": "2026-11-22T06:44:13Z",
            "source_revision": "synthetic-test-only", "sitemaps": [
                "https://asktherecruiter.com/blog/sitemap.xml"],
            "files": [self.file("sitemap.xml", "/blog/sitemap.xml"),
                      self.file("robots.txt", "/robots.txt")],
            "pages": [self.page(url, index) for index, url in enumerate(self.urls)],
        }

    def file(self, name, path):
        data = self.files[name]
        (self.snapshot / name).write_bytes(data)
        return {"url": "https://asktherecruiter.com" + path, "source": name,
                "sha256": hashlib.sha256(data).hexdigest()}

    def page(self, url, index):
        return {"url": url, "title": f"Recorded title {index} & evidence",
                "description": f"Recorded description {index}", "canonical": url,
                "robots": "index, follow", "schema": [
                    {"@context": "https://schema.org", "@type": "Dataset", "name": str(index)}],
                "body": f"<h1>Recorded heading {index}</h1><p>Published content.</p>",
                "rows": [{"company": "Acme", "date": "2026-11-01", "country": "France",
                          "jobs": 12, "source_url": "https://example.org/filing"}]}

    def build(self):
        path = self.snapshot / "manifest.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return static_site.build(path, self.output)

    def test_every_independent_sitemap_url_has_unchanged_head_and_tracked_cta(self):
        self.build()
        for index, url in enumerate(self.urls):
            path = self.output / url.split("asktherecruiter.com/", 1)[1] / "index.html"
            parser = Head()
            parser.feed(path.read_text())
            self.assertIn(f"Recorded title {index} & evidence", parser.text)
            self.assertIn(("link", {"rel": "canonical", "href": url}), parser.tags)
            self.assertIn(("meta", {"name": "description", "content": f"Recorded description {index}"}), parser.tags)
            cta = [attrs for tag, attrs in parser.tags if tag == "a" and attrs.get("data-match-cta") == "true"]
            self.assertEqual(len(cta), 1)
            self.assertIn("utm_source=ai-layoff-tracker", cta[0]["href"])
            self.assertIn("start=1", cta[0]["href"])
            self.assertIn("Check my match, free", parser.text)
        self.assertEqual((self.output / "blog/sitemap.xml").read_bytes(), self.files["sitemap.xml"])
        self.assertEqual((self.output / "robots.txt").read_bytes(), self.files["robots.txt"])

    def test_missing_sitemap_page_fails_before_dist_exists(self):
        self.manifest["pages"].pop()
        with self.assertRaisesRegex(ValueError, "sitemap URL has no page"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_missing_metadata_is_never_invented(self):
        for field in ("title", "description", "canonical", "robots", "schema"):
            with self.subTest(field=field):
                original = copy.deepcopy(self.manifest)
                del self.manifest["pages"][0][field]
                with self.assertRaisesRegex(ValueError, field):
                    self.build()
                self.assertFalse(self.output.exists())
                self.manifest = original

    def test_missing_child_sitemap_and_changed_asset_fail(self):
        self.manifest["sitemaps"] = ["https://asktherecruiter.com/blog/absent.xml"]
        with self.assertRaisesRegex(ValueError, "missing sitemap"):
            self.build()
        self.manifest["sitemaps"] = [self.manifest["files"][0]["url"]]
        (self.snapshot / "robots.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.build()

    def test_wordpress_runtime_and_active_forms_fail_closed(self):
        for body in ('<h1>Title</h1><script src="/blog/wp-json/data"></script>',
                     '<h1>Title</h1><form action="/blog/"></form>',
                     '<h1 onclick="send()">Title</h1>'):
            with self.subTest(body=body):
                self.manifest["pages"][0]["body"] = body
                with self.assertRaisesRegex(ValueError, "active content"):
                    self.build()
                self.assertFalse(self.output.exists())

    def test_path_escape_is_rejected(self):
        self.manifest["pages"][0]["url"] = "https://asktherecruiter.com/blog/%2e%2e/escape/"
        with self.assertRaisesRegex(ValueError, "unsafe URL"):
            self.build()
        self.assertFalse((self.root / "escape").exists())

    def test_non_html_active_content_and_missing_image_are_rejected(self):
        for fragment in ('<svg><a xlink:href="javascript:alert(1)">x</a></svg>',
                         '<img src="https://asktherecruiter.com/blog/wp-content/uploads/missing.png" alt="Chart">'):
            with self.subTest(fragment=fragment):
                self.manifest["pages"][0]["body"] = "<h1>Title</h1>" + fragment
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
