"""SEO audit 2026-10-12, items 2, 4, 5 and 10 (ALT's share).

- #2: every self-served sitemap prints <lastmod> (date of the latest entry).
- #4: the report sitemap lists clean paths (/report/2023/, /report/archive/),
  never ?period= / ?view= URLs; the bare query forms 301 to the clean path.
  (The "trailing &" internal links in the audit were the crawler cutting
  WordPress's `&#038;` entity at the `#`; the links are well formed.)
- #5: Article/NewsArticle publisher is the Organization "Ask The Recruiter".
- #10: generated meta descriptions are capped at 155 characters.
"""
import re
import shutil
import subprocess
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "wordpress-plugin" / "ai-layoff-tracker"
MOD = PLUGIN / "includes" / "seo-sitemap-meta.php"
REPORT = PLUGIN / "includes" / "report-seo.php"

STUBS = r"""
define('ABSPATH', '/');
function esc_url($s){ return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function home_url($p = '/'){ return 'https://example.org/blog' . $p; }
function add_filter(){} function add_action(){} function add_rewrite_rule(){}
"""


def _fn(path, name):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"\nfunction " + name + r"\s*\(.*?\n\}", src, re.S)
    assert m, name + " is missing"
    return m.group(0)


def _php(code):
    p = subprocess.run(["php", "-r", STUBS + code], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr + p.stdout
    return p.stdout


def _meta():
    return MOD.read_text(encoding="utf-8").replace("<?php", "", 1)


def _report_fns():
    return "".join(_fn(REPORT, n) for n in (
        "alt_report_clean_url", "alt_report_clean_slug_ok",
        "alt_report_query_redirect_target", "alt_report_url_lastmod"))


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Descriptions(unittest.TestCase):
    def test_long_description_capped_at_word(self):
        long = "Verified job cuts recorded in September 2026: totals by company, industry, " \
               "country and US state, plus the layoffs employers themselves attributed to AI. " \
               "Every figure links to the filing."
        out = _php(_meta() + "echo alt_seo_cap_description(%r);" % long)
        self.assertLessEqual(len(out), 155)
        self.assertTrue(out.endswith("\u2026"))
        self.assertTrue(long.startswith(out[:-1].rstrip()))

    def test_short_description_untouched(self):
        self.assertEqual(_php(_meta() + "echo alt_seo_cap_description('Short one.');"), "Short one.")

    def test_every_template_filter_caps(self):
        for f, fn in (("company-directory.php", "alt_company_directory_seo_description"),
                      ("facet-pages.php", "alt_facet_seo_description"),
                      ("report-seo.php", "alt_report_seo_description")):
            self.assertIn("alt_seo_cap_description", _fn(PLUGIN / "includes" / f, fn), f)

    def test_report_archive_description_fits(self):
        body = _fn(REPORT, "alt_report_seo_description")
        lit = re.search(r"return 'Every AskTheRecruiter(.*?)';", body, re.S).group(0)
        text = "".join(re.findall(r"'([^']*)'", lit))
        self.assertLessEqual(len(text), 155)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Lastmod(unittest.TestCase):
    def test_url_line_with_and_without_date(self):
        out = _php(_meta() + "echo alt_sitemap_url_line('https://e.org/a/', '2026-10-01 12:00:00');"
                   "echo alt_sitemap_url_line('https://e.org/b/', '');")
        self.assertIn("<url><loc>https://e.org/a/</loc><lastmod>2026-10-01</lastmod></url>", out)
        self.assertIn("<url><loc>https://e.org/b/</loc></url>", out)

    def test_future_date_clamped_to_today(self):
        out = _php(_meta() + "echo alt_sitemap_lastmod_value('2099-01-01') === gmdate('Y-m-d') ? 'ok' : 'bad';")
        self.assertEqual(out, "ok")

    def test_every_sitemap_renderer_prints_lastmod(self):
        for f in ("company-directory.php", "facet-pages.php", "report-seo.php", "digest-archive.php"):
            src = (PLUGIN / "includes" / f).read_text(encoding="utf-8")
            self.assertIn("alt_sitemap_url_line(", src, f)
            self.assertNotIn("'  <url><loc>' . esc_url(", src, f)

    def test_report_lastmod_rolls_up_months(self):
        months = "array('2025-01'=>'2025-02-03','2025-02'=>'2025-03-09','2025-05'=>'2025-06-01','2024-12'=>'2025-01-05')"
        code = _meta() + _report_fns() + (
            "$m=%s; foreach (array('2025','2025-Q1','2025-02','archive','2024') as $s)"
            " echo $s, '=', alt_report_url_lastmod('https://example.org/blog/ai-layoff-tracker/report/'.$s.'/', $m), \"\\n\";" % months)
        got = dict(l.split("=") for l in _php(code).strip().splitlines())
        self.assertEqual(got, {"2025": "2025-06-01", "2025-Q1": "2025-03-09", "2025-02": "2025-03-09",
                               "archive": "2025-06-01", "2024": "2025-01-05"})


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class CleanReportUrls(unittest.TestCase):
    def test_clean_paths(self):
        out = _php(_report_fns() + "foreach (array(array('archive',''),array('year','2023'),"
                   "array('quarter','2024-Q2'),array('month','2026-09')) as $a) echo alt_report_clean_url($a[0],$a[1]), \"\\n\";")
        self.assertEqual(out.split(), [
            "https://example.org/blog/ai-layoff-tracker/report/archive/",
            "https://example.org/blog/ai-layoff-tracker/report/2023/",
            "https://example.org/blog/ai-layoff-tracker/report/2024-Q2/",
            "https://example.org/blog/ai-layoff-tracker/report/2026-09/"])

    def test_sitemap_lists_no_query_urls(self):
        body = _fn(REPORT, "alt_report_indexable_urls")
        out = _php(_report_fns() + body + "echo implode(\"\\n\", alt_report_indexable_urls());")
        urls = out.split()
        self.assertGreater(len(urls), 30)
        for u in urls:
            self.assertNotIn("?", u)
            self.assertNotIn("&", u)
            self.assertTrue(u.endswith("/"))

    def test_bare_query_urls_redirect_others_stay(self):
        out = _php(_report_fns() +
                   "echo alt_report_query_redirect_target(array('period'=>'2023'),'year','2023'), \"\\n\";"
                   "echo alt_report_query_redirect_target(array('view'=>'archive'),'archive',''), \"\\n\";"
                   "echo '[', alt_report_query_redirect_target(array('period'=>'2023','scope'=>'us'),'year','2023'), \"]\\n\";"
                   "echo '[', alt_report_query_redirect_target(array('period'=>'2026-W03'),'week','2026-W03'), \"]\\n\";")
        lines = out.splitlines()
        self.assertEqual(lines[0], "https://example.org/blog/ai-layoff-tracker/report/2023/")
        self.assertEqual(lines[1], "https://example.org/blog/ai-layoff-tracker/report/archive/")
        self.assertEqual(lines[2:], ["[]", "[]"])

    def test_route_registered(self):
        src = REPORT.read_text(encoding="utf-8")
        self.assertIn("alt_rpath=$matches[1]", src)
        self.assertIn("'redirect_canonical'", src)


@unittest.skipUnless(shutil.which("php"), "UNKNOWN, NOT RUN: php not installed")
class Publisher(unittest.TestCase):
    def test_org_is_brand(self):
        out = _php(_meta() + "echo alt_publisher_name();")
        self.assertEqual(out, "Ask The Recruiter")
        main = (PLUGIN / "ai-layoff-tracker.php").read_text(encoding="utf-8")
        self.assertNotIn("'name' => get_bloginfo('name')", main)
