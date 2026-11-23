"""The preview uses public backup facts without claiming production parity."""
import gzip
import hashlib
import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import static_preview


class Preview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = {"recorded_at": "2026-11-22T06:44:13Z", "tables": {}}
        self.rows = [{"company": "Example & Co", "company_key": "example", "country": "France",
                      "layoff_date": "2026-11-01", "job_count": 12,
                      "source_url": "https://example.org/source", "review_status": "verified",
                      "superset_of": 0, "excerpt": "NOT PUBLIC IN THIS PROJECTION"}]

    def write(self, companies=None):
        tables = {"layoffs": self.rows, "company_directory": companies if companies is not None else [
            {"company_key": "example", "slug": "recorded-slug", "display_name": "Example & Co"}]}
        for name, rows in tables.items():
            raw = "\n".join(json.dumps(r) for r in rows).encode()
            content = gzip.compress(raw)
            (self.root / f"{name}.jsonl.gz").write_bytes(content)
            self.state["tables"][name] = {"sha256": hashlib.sha256(raw).hexdigest()}
        path = self.root / "state.json"
        path.write_text(json.dumps(self.state))
        return path

    def test_preview_builds_existing_paths_with_facts_and_cta(self):
        count = static_preview.build_preview(self.write(), self.root, self.root / "dist")
        self.assertEqual(count, 3)
        for path in ("ai-layoff-tracker", "company-layoffs", "company-layoffs/recorded-slug"):
            page = (self.root / "dist/blog" / path / "index.html").read_text()
            self.assertIn("Check my match, free", page)
            self.assertIn("utm_source=ai-layoff-tracker", page)
            self.assertIn('content="noindex, nofollow"', page)
            self.assertIn("Preview", page)
            self.assertIn("2026-11-22", page)
            self.assertNotIn("NOT PUBLIC IN THIS PROJECTION", page)
            self.assertNotIn("wp-json", page)
        company = (self.root / "dist/blog/company-layoffs/recorded-slug/index.html").read_text()
        self.assertIn("<td>12</td>", company)
        self.assertIn("https://example.org/source", company)
        self.assertEqual((self.root / "dist/robots.txt").read_text(), "User-agent: *\nDisallow: /\n")

    def test_held_and_superset_rows_are_not_promoted(self):
        self.rows += [dict(self.rows[0], review_status="provisional", job_count=987654),
                      dict(self.rows[0], superset_of=1, job_count=987655)]
        static_preview.build_preview(self.write(), self.root, self.root / "dist")
        page = (self.root / "dist/blog/ai-layoff-tracker/index.html").read_text()
        self.assertNotIn("987654", page)
        self.assertNotIn("987655", page)

    def test_changed_backup_fails_before_output(self):
        state = self.write()
        (self.root / "layoffs.jsonl.gz").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum"):
            static_preview.build_preview(state, self.root, self.root / "dist")
        self.assertFalse((self.root / "dist").exists())

    def test_no_reviewed_rows_is_not_presented_as_zero_layoffs(self):
        self.rows[0]["review_status"] = "provisional"
        with self.assertRaisesRegex(ValueError, "reviewed"):
            static_preview.build_preview(self.write(), self.root, self.root / "dist")

    def test_preview_workflow_builds_on_pr_and_backup_completion(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/static-site.yml").read_text()
        self.assertIn("workflow_run:", workflow)
        self.assertIn("railway/backup_state.json", workflow)
        self.assertIn("static_preview.py", workflow)
        self.assertNotIn("if: github.event_name != 'pull_request'", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("path: dist/", workflow)

    def test_downloader_uses_only_the_recorded_public_release(self):
        self.write()
        payloads = [(self.root / f"{name}.jsonl.gz").read_bytes() for name in static_preview.TABLES]
        with patch("static_preview.urlopen", side_effect=[io.BytesIO(p) for p in payloads]) as fetch:
            static_preview.download_backups(self.state, self.root / "download")
        for call, name in zip(fetch.call_args_list, static_preview.TABLES):
            self.assertEqual(call.args, ("https://github.com/dk-forge/ai-layoff-tracker/releases/"
                                        f"download/backup-2026-11-22/{name}.jsonl.gz",))
        self.assertEqual(static_preview.read_table(self.root / "download", self.state, "layoffs"), self.rows)

    def test_recorded_percent_encoded_company_slug_builds_without_double_encoding(self):
        slug = "example%e2%80%a0"
        companies = [{"company_key": "example", "slug": slug, "display_name": "Example & Co"}]
        self.assertEqual(3, static_preview.build_preview(self.write(companies), self.root, self.root / "dist"))
        page = (self.root / "dist/blog/company-layoffs/example†/index.html").read_text()
        directory = (self.root / "dist/blog/company-layoffs/index.html").read_text()
        self.assertIn(f'href="https://asktherecruiter.com/blog/company-layoffs/{slug}/"', page)
        self.assertIn(f'href="/blog/company-layoffs/{slug}/"', directory)
        self.assertNotIn("%25e2", directory)
        self.assertIn("Check my match, free", page)
        self.assertIn("utm_source=ai-layoff-tracker", page)

    def test_encoded_slugs_cannot_escape_a_single_safe_directory(self):
        for slug in ("example%2fchild", "%2e%2e", "example%5cchild", "example%00",
                     "example%252fchild", "example%zz", "example%ff"):
            with self.subTest(slug=slug):
                companies = [{"company_key": "example", "slug": slug, "display_name": "Example & Co"}]
                with self.assertRaises(ValueError):
                    static_preview.build_preview(self.write(companies), self.root, self.root / "dist")
                self.assertFalse((self.root / "dist").exists())

    def test_encoded_aliases_cannot_overwrite_a_company_page(self):
        companies = [{"company_key": "example", "slug": slug, "display_name": "Example & Co"}
                     for slug in ("recorded-slug", "%72ecorded-slug")]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            static_preview.build_preview(self.write(companies), self.root, self.root / "dist")
        self.assertFalse((self.root / "dist").exists())
