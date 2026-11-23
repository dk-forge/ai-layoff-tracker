"""Independent sitemap and live HTML fixtures gate static URL/SEO parity."""
import json
import io
from email.message import Message
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import static_parity as parity

ORIGIN = 'https://asktherecruiter.com'
HUB = ORIGIN + '/blog/ai-layoff-tracker/'
COMPANY = ORIGIN + '/blog/company-layoffs/example/'
SITEMAP = ORIGIN + '/blog/layoff-pages.xml'


def page(url=HUB):
    return f'''<!doctype html><html><head><title>Tracker &amp; sources</title>
<meta name="description" content="Recorded source documents.">
<link rel="canonical" href="{url}"><link rel="alternate" hreflang="en" href="{url}">
<script type="application/ld+json">{{"@type":"WebPage","name":"Tracker"}}</script>
</head><body><h1>Recorded sources</h1>
<a href="https://asktherecruiter.com/resume-score?utm_source=ai-layoff-tracker&amp;utm_medium=referral&amp;utm_campaign=hub">Check my match, free</a>
</body></html>'''


class Parity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dist = Path(self.temp.name) / 'dist'
        self.dist.mkdir()
        self.live = {SITEMAP: '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                     f'<url><loc>{HUB}</loc></url><url><loc>{COMPANY}</loc></url></urlset>',
                     HUB: page(), COMPANY: page(COMPANY)}
        self.write(HUB, page())
        self.write(COMPANY, page(COMPANY))

    def write(self, url, text):
        path = self.dist / url.split(ORIGIN + '/', 1)[1] / 'index.html'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def fetch(self, url):
        if url not in self.live:
            raise OSError('unreachable fixture')
        return self.live[url]

    def check(self):
        return parity.compare(self.dist, [SITEMAP], self.fetch)

    def test_every_independent_sitemap_url_is_compared(self):
        report = self.check()
        self.assertTrue(report['passed'])
        self.assertEqual({p['url'] for p in report['pages']}, {HUB, COMPANY})
        self.assertEqual(report['totals']['passed'], 2)

    def test_missing_static_page_fails_even_when_others_match(self):
        (self.dist / 'blog/company-layoffs/example/index.html').unlink()
        report = self.check()
        self.assertFalse(report['passed'])
        self.assertIn('missing_static_page', report['pages'][1]['errors'])

    def test_each_seo_difference_is_reported(self):
        variants = {
            'title': page().replace('Tracker &amp; sources', 'Different title'),
            'description': page().replace('Recorded source documents.', 'Different description'),
            'canonical': page().replace(f'rel="canonical" href="{HUB}"', 'rel="canonical" href="https://example.org/"'),
            'h1': page().replace('<h1>Recorded sources</h1>', '<h1>Different heading</h1>'),
            'jsonld': page().replace('"WebPage"', '"Dataset"'),
            'hreflang': page().replace('hreflang="en"', 'hreflang="fr"'),
        }
        for field, html in variants.items():
            with self.subTest(field=field):
                self.write(HUB, html)
                result = self.check()
                self.assertFalse(result['passed'])
                self.assertIn(field, result['pages'][0]['differences'])

    def test_empty_seo_link_hrefs_never_pass(self):
        for rel in ('canonical', 'alternate'):
            for broken in ('', ' href=""', ' href="   "'):
                with self.subTest(rel=rel, broken=broken):
                    original = f'rel="{rel}"' + (' hreflang="en"' if rel == 'alternate' else '')
                    self.write(HUB, page().replace(original + f' href="{HUB}"', original + broken))
                    self.assertFalse(self.check()['passed'])

    def test_missing_or_hidden_or_untagged_cta_fails(self):
        for html in (page().replace('<a href=', '<a hidden href='),
                     page().replace('<a href=', '<a class="hidden" href='),
                     page().replace('<body>', '<body><div style="display:none">').replace('</body>', '</div></body>'),
                     page().replace('utm_campaign=hub', 'campaign=hub'),
                     page().replace('/resume-score?', '/privacy?')):
            with self.subTest(html=html):
                self.write(HUB, html)
                result = self.check()
                self.assertFalse(result['passed'])
                self.assertIn('missing_static_cta', result['pages'][0]['errors'])

    def test_a_tagged_brand_or_navigation_link_cannot_stand_in_for_the_cta(self):
        for label in ('Ask The Recruiter', 'Home', 'Resume'):
            with self.subTest(label=label):
                self.write(HUB, page().replace('Check my match, free', label))
                result = self.check()
                self.assertFalse(result['passed'])
                self.assertIn('missing_static_cta', result['pages'][0]['errors'])

    def test_partial_opacity_does_not_hide_a_visible_cta(self):
        self.write(HUB, page().replace('<a href=', '<a style="opacity:0.5" href='))
        self.assertTrue(self.check()['passed'])

    def test_only_an_actual_301_map_can_replace_a_missing_path(self):
        old = self.dist / 'blog/company-layoffs/example/index.html'
        replacement = ORIGIN + '/blog/company-layoffs/renamed/'
        old.unlink()
        self.write(replacement, page(COMPANY))
        redirects = self.dist / '_redirects'
        redirects.write_text('/blog/company-layoffs/example/ /blog/company-layoffs/renamed/ 302\n')
        self.assertFalse(self.check()['passed'])
        redirects.write_text('/blog/company-layoffs/example/ /blog/company-layoffs/renamed/ 301\n')
        self.assertTrue(self.check()['passed'])

    def test_sitemap_index_is_recursive_and_skips_other_products(self):
        self.live[SITEMAP] = '<sitemapindex><sitemap><loc>' + SITEMAP + '/child</loc></sitemap></sitemapindex>'
        self.live[SITEMAP + '/child'] = '<urlset><url><loc>' + HUB + '</loc></url><url><loc>' + ORIGIN + '/blog/talent-intelligence-tracker/</loc></url></urlset>'
        result = self.check()
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['pages']), 1)

    def test_unreachable_live_pages_or_sitemaps_never_pass(self):
        del self.live[HUB]
        self.assertFalse(self.check()['passed'])
        del self.live[SITEMAP]
        self.assertFalse(self.check()['passed'])

    def test_semantically_identical_json_and_whitespace_match(self):
        self.write(HUB, page().replace('{"@type":"WebPage","name":"Tracker"}', '{"name": "Tracker", "@type": "WebPage"}')
                   .replace('Recorded sources</h1>', 'Recorded\n sources</h1>'))
        self.assertTrue(self.check()['passed'])

    def test_invalid_jsonld_and_unsafe_urls_are_rejected(self):
        self.write(HUB, page().replace('{"@type":"WebPage","name":"Tracker"}', 'not json'))
        self.assertFalse(self.check()['passed'])
        with self.assertRaises(ValueError):
            parity.validate_url('https://other.example/blog/ai-layoff-tracker/')
        with self.assertRaises(ValueError):
            parity.validate_url(ORIGIN + '/blog/%2e%2e/wp-admin/')

    def test_report_is_written_even_when_the_live_comparison_fails(self):
        del self.live[HUB]
        report = self.check()
        output = self.dist.parent / 'report.json'
        parity.write_report(report, output)
        self.assertFalse(json.loads(output.read_text())['passed'])

    def test_parity_workflow_is_read_only_and_keeps_failure_reports(self):
        workflow = (Path(__file__).resolve().parents[2] / '.github/workflows/static-parity.yml').read_text()
        self.assertIn('pull_request:', workflow)
        self.assertIn('workflow_dispatch:', workflow)
        self.assertIn('download-artifact@v4', workflow)
        self.assertIn('static_parity.py', workflow)
        self.assertIn('if: always()', workflow)
        self.assertIn('parity-report.json', workflow)
        self.assertNotIn('secrets.', workflow)


class LiveFetch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.client = parity.LivePages(Path(self.temp.name), interval=0)

    def response(self, text=page()):
        response = io.BytesIO(text.encode())
        response.status = 200
        response.headers = Message()
        return response

    def test_repeated_reads_across_instances_use_one_hour_cache(self):
        with patch.object(self.client.opener, 'open', return_value=self.response()) as request:
            self.assertEqual(self.client(HUB), page())
            self.assertEqual(self.client(HUB), page())
        self.assertEqual(request.call_count, 1)
        second = parity.LivePages(Path(self.temp.name), interval=0)
        with patch.object(second.opener, 'open', side_effect=AssertionError('unexpected network')):
            self.assertEqual(second(HUB), page())

    def test_failures_are_cached_without_retry_storms(self):
        with patch.object(self.client.opener, 'open', side_effect=OSError('unreachable')) as request:
            for _ in range(2):
                with self.assertRaises(OSError):
                    self.client(HUB)
        self.assertEqual(request.call_count, 1)

    def test_budget_exhaustion_is_explicit(self):
        self.client.max_requests = 1
        with patch.object(self.client.opener, 'open', return_value=self.response()):
            self.client(HUB)
        with self.assertRaises(parity.FetchBudgetExceeded):
            self.client(COMPANY)

    def test_wrong_origin_is_rejected_before_open(self):
        with patch.object(self.client.opener, 'open') as request:
            with self.assertRaises(ValueError):
                self.client('https://example.org/blog/private/')
        request.assert_not_called()

    def test_elapsed_deadline_fails_before_another_request(self):
        self.client.deadline = 0
        with patch.object(self.client.opener, 'open', return_value=self.response()) as request:
            with self.assertRaises(parity.FetchBudgetExceeded):
                self.client(HUB)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
