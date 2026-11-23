"""Offline build contract, using an independent synthetic sitemap baseline."""
import copy
import hashlib
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import static_site


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []
        self.titles = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "title":
            self.in_title = True
            self.titles.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        self.text.append(data)
        if self.in_title:
            self.titles[-1] += data


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
        archive = "https://asktherecruiter.com/blog/ai-layoff-tracker/editions/daily/recorded/"
        page = self.page(archive, 2)
        page["robots"] = "noindex, follow"
        self.manifest["pages"].append(page)
        self.assertEqual(self.build(), 3)
        baseline = static_site.sitemap_urls(
            self.manifest["sitemaps"], {
                item["url"]: self.files[item["source"]] for item in self.manifest["files"]
            },
        )
        self.assertEqual(baseline, set(self.urls))
        for index, url in enumerate([*self.urls, archive]):
            path = self.output / url.split("asktherecruiter.com/", 1)[1] / "index.html"
            parser = Head()
            parser.feed(path.read_text())
            self.assertEqual(parser.titles, [f"Recorded title {index} & evidence"])
            canonicals = [attrs["href"] for tag, attrs in parser.tags
                          if tag == "link" and attrs.get("rel") == "canonical"]
            self.assertEqual(canonicals, [url])
            self.assertIn(("meta", {"name": "description", "content": f"Recorded description {index}"}), parser.tags)
            cta = [attrs for tag, attrs in parser.tags if tag == "a" and attrs.get("data-match-cta") == "true"]
            self.assertEqual(len(cta), 1)
            self.assertEqual(
                cta[0]["href"],
                "https://asktherecruiter.com/?start=1&utm_source=ai-layoff-tracker"
                "&utm_medium=referral&utm_campaign=static_tracker#start-intake",
            )
            self.assertIn("Check my match, free", parser.text)
        self.assertEqual((self.output / "blog/sitemap.xml").read_bytes(), self.files["sitemap.xml"])
        self.assertEqual((self.output / "robots.txt").read_bytes(), self.files["robots.txt"])

    def test_preserves_recorded_feed_and_advertises_it_on_tracker(self):
        url = "https://asktherecruiter.com/blog/feed/layoffs"
        self.files["layoffs.xml"] = (
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f'<title>Recorded feed</title><atom:link href="{url}" rel="self" />'
            '<item><title>Recorded item</title><guid>alt-12-stable</guid>'
            '<link>https://example.org/report</link></item></channel></rss>'
        ).encode()
        self.manifest["files"].append(self.file("layoffs.xml", "/blog/feed/layoffs"))
        self.build()
        self.assertEqual((self.output / "blog/feed/layoffs").read_bytes(), self.files["layoffs.xml"])
        self.assertIn("Content-Type: application/rss+xml", (self.output / "_headers").read_text())
        tracker = (self.output / "blog/ai-layoff-tracker/index.html").read_text()
        self.assertIn(f'rel="alternate" type="application/rss+xml" href="{url}"', tracker)

    def test_pilot_links_to_working_backend_forms_outside_static_output(self):
        self.manifest["wordpress_forms"] = True
        self.build()
        tracker = (self.output / "blog/ai-layoff-tracker/index.html").read_text()
        self.assertIn('href="https://asktherecruiter.com/blog/contact/"', tracker)
        self.assertIn('href="https://asktherecruiter.com/blog/layoff-tracker/#alt-digest"', tracker)
        self.assertNotIn("<form", tracker)

    def test_pilot_cannot_shadow_the_backend_forms(self):
        self.manifest["wordpress_forms"] = True
        self.manifest["pages"].append(self.page("https://asktherecruiter.com/blog/contact/", 2))
        with self.assertRaisesRegex(ValueError, "backend form page"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_build_shares_projection_with_noindex_widget_and_chart_embed(self):
        projection = self.root / "tracker-data.json"
        projection.write_text(json.dumps({
            "schema": 1, "exported_at": "2026-11-22T06:44:13Z",
            "records": [{"company": "Acme", "job_count": "12"},
                        {"company": "Other", "job_count": "7"}],
        }))
        manifest = self.snapshot / "manifest.json"
        manifest.write_text(json.dumps(self.manifest))
        with patch.object(static_site, "TRACKER_CHUNK_BYTES", 48):
            static_site.build(manifest, self.output, projection)
        tracker = self.output / "blog/ai-layoff-tracker"
        embed = (tracker / "embed/index.html").read_text()
        self.assertIn('content="noindex, follow"', embed)
        self.assertIn('data-tracker-embed', embed)
        self.assertIn('data-match-cta="true"', embed)
        self.assertIn('href="/blog/ai-layoff-tracker/embed/?view=chart"', (tracker / "index.html").read_text())
        index_path = self.output / static_site.TRACKER_DATA_PATH
        index = json.loads(index_path.read_text())
        self.assertEqual(len(index["chunks"]), 2)
        records = []
        for filename in index["chunks"]:
            chunk = (index_path.parent / filename).read_bytes()
            self.assertLessEqual(len(chunk), 48)
            records.extend(json.loads(chunk))
        self.assertEqual(records, json.loads(projection.read_text())["records"])

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
        self.files["index.xml"] = (
            b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b'<sitemap><loc>https://asktherecruiter.com/blog/absent.xml</loc></sitemap>'
            b'</sitemapindex>'
        )
        index = self.file("index.xml", "/blog/index.xml")
        self.manifest["files"].append(index)
        self.manifest["sitemaps"] = [index["url"]]
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

    def test_truncated_html_tokens_never_join_generated_markup(self):
        for index, ending in enumerate(('<script src="https://example.org/legacy.js" ',
                                         '<a href="https://example.org/', '<!-- unfinished')):
            with self.subTest(ending=ending):
                self.output = self.root / f"output-{index}"
                self.manifest["pages"][0]["body"] = "<h1>Title</h1>" + ending
                with self.assertRaisesRegex(ValueError, "incomplete HTML"):
                    self.build()
                self.assertFalse(self.output.exists())

    def test_normalized_file_destinations_cannot_overwrite_each_other(self):
        self.files["other.xml"] = b"different recorded bytes"
        item = self.file("other.xml", "/blog/%73itemap.xml")
        self.manifest["files"].append(item)
        with self.assertRaisesRegex(ValueError, "duplicate normalized"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_comments_and_declarations_cannot_hide_active_content(self):
        fragments = ('<!--><script>alert(1)</script>-->', '<!-- harmless -->',
                     '<!DOCTYPE html>', '<?xml version="1.0"?>')
        for index, fragment in enumerate(fragments):
            with self.subTest(fragment=fragment):
                self.output = self.root / f"markup-{index}"
                self.manifest["pages"][0]["body"] = "<h1>Title</h1>" + fragment
                with self.assertRaises(ValueError):
                    self.build()
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
