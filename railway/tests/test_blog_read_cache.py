"""An on-disk public-page budget survives workers, retries and failures."""
import io
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import blog_read_cache as cache

URL = 'https://asktherecruiter.com/blog/ai-layoff-tracker/'
UA = {'User-Agent': 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)'}


class Budget(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'reads'
        self.now = 10000
        self.clock = lambda: self.now
        self.reader = cache.ReadCache(self.root, clock=self.clock)
        self.calls = 0

    def fetch(self):
        self.calls += 1
        return 200, {'Content-Type': 'text/html'}, b'<h1>Recorded page</h1>'

    def test_workers_and_retries_fetch_once_in_an_hour(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: cache.ReadCache(self.root, clock=self.clock).get(URL, self.fetch), range(12)))
        self.assertEqual(self.calls, 1)
        self.assertTrue(all(r['body'] == b'<h1>Recorded page</h1>' for r in results))
        self.now += 3599
        self.reader.get(URL, self.fetch)
        self.assertEqual(self.calls, 1)
        self.now += 1
        self.reader.get(URL, self.fetch)
        self.assertEqual(self.calls, 2)

    def test_cache_busters_cannot_evade_the_budget(self):
        self.reader.get(URL + '?cb=first&year=2026', self.fetch)
        self.reader.get(URL + '?year=2026&cb=second', self.fetch)
        self.assertEqual(self.calls, 1)
        self.reader.get(URL + '?year=2025', self.fetch)
        self.assertEqual(self.calls, 2)

    def test_a_failed_attempt_is_not_retried_in_the_same_hour(self):
        def fail():
            self.calls += 1
            raise OSError('transport unavailable')
        with self.assertRaises(OSError):
            self.reader.get(URL, fail)
        with self.assertRaises(cache.ReadLimited):
            cache.ReadCache(self.root, clock=self.clock).get(URL, fail)
        self.assertEqual(self.calls, 1)

    def test_only_public_responses_are_cacheable_but_all_bot_reads_are_limited(self):
        self.assertTrue(cache.eligible(URL, UA))
        for url, headers in [(URL, {**UA, 'Authorization': 'not-a-real-credential'}),
                             (URL, {**UA, 'Cookie': 'session=synthetic'}),
                             (URL, {**UA, 'X-Layoff-Api-Key': 'synthetic'}),
                             (URL + '?token=synthetic', UA),
                             ('https://asktherecruiter.com/blog/wp-json/layoffs/v1/query', UA),
                             ('https://asktherecruiter.com/blog/wp-admin/', UA),
                             ('https://other.example/blog/', UA),
                             (URL, {'User-Agent': 'OtherReader'})]:
            with self.subTest(url=url, headers=headers):
                self.assertFalse(cache.cacheable(url, headers))

    def test_cache_files_are_private_and_do_not_store_cookies(self):
        self.reader.get(URL, lambda: (200, {'Set-Cookie': 'synthetic=private'}, b'Public page'))
        payload = next(self.root.glob('*.json'))
        self.assertEqual(payload.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('synthetic=private', payload.read_text())
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)

    def test_redirect_targets_obey_the_same_budget(self):
        calls = []
        target = URL + 'sources/'
        def open_one(request, **kwargs):
            calls.append(request.full_url)
            return (301, {'Location': target}, b'') if request.full_url == URL else self.fetch()
        first = cache.urlopen(URL, headers=UA, reader=self.reader, open_one=open_one)
        self.assertEqual(first.read(), b'<h1>Recorded page</h1>')
        self.assertEqual(cache.urlopen(target, headers=UA, reader=self.reader, open_one=open_one).read(), b'<h1>Recorded page</h1>')
        self.assertEqual(calls, [URL, target])

    def test_authenticated_api_reads_share_the_cap_without_replaying_a_batch(self):
        import requests
        api = 'https://asktherecruiter.com/blog/wp-json/layoffs/v1/query'
        headers = {**UA, 'X-Layoff-API-Key': 'synthetic-key'}
        calls = []
        def fetch(url, **options):
            calls.append(url)
            response = requests.Response()
            response.status_code = 200
            response._content = b'{"rows":["synthetic-batch"]}'
            return response
        response = cache.get(api, headers=headers, params={'_fresh': 'one'}, getter=fetch, reader=self.reader)
        self.assertIn('synthetic-batch', response.text)
        with self.assertRaises(requests.RequestException):
            cache.get(api, headers=headers, params={'_fresh': 'two'}, getter=fetch, reader=self.reader)
        self.assertEqual(len(calls), 1)
        stored = ''.join(p.read_text() for p in self.root.glob('*.json'))
        self.assertNotIn('synthetic-key', stored)
        self.assertNotIn('synthetic-batch', stored)

    def test_pinned_stream_opener_is_preserved_and_not_retried(self):
        calls = []
        def stream(request, timeout):
            calls.append(request.full_url)
            response = cache.addinfourl(io.BytesIO(b'public'), {}, request.full_url, 200)
            return response
        self.assertEqual(cache.urlopen(URL, headers=UA, reader=self.reader, stream_opener=stream).read(), b'public')
        with self.assertRaises(cache.ReadLimited):
            cache.urlopen(URL, headers=UA, reader=self.reader, stream_opener=stream)
        self.assertEqual(calls, [URL])

    def test_private_requests_preserve_the_supplied_transport(self):
        calls = []
        def stream(request, timeout):
            calls.append(request.full_url)
            return 'private response'
        url = 'https://other.example/blog/wp-json/layoffs/v1/query'
        self.assertEqual(cache.urlopen(url, headers=UA, stream_opener=stream), 'private response')
        self.assertEqual(calls, [url])

    def test_public_human_challenge_cannot_bypass_the_hourly_cap(self):
        import http_retry
        from unittest.mock import patch
        import requests
        calls = []
        def get(url, **options):
            calls.append(url)
            response = requests.Response()
            response.status_code = 409
            response._content = b'<script>document.cookie="humans_123=1"</script>'
            response.url = url
            return response
        with patch.object(cache, 'ReadCache', return_value=self.reader):
            http_retry.get_with_retry(URL, headers=UA, get=get, sleep=lambda _: None)
        self.assertEqual(calls, [URL])

    def test_authenticated_ops_panel_reports_a_limited_read_as_unknown(self):
        import json
        import ops_status
        from unittest.mock import patch
        with patch.object(cache, 'ReadCache', return_value=self.reader), \
             patch.object(cache, '_open_one', return_value=(200, {'Content-Type': 'application/json'},
                                                          json.dumps({'available': False}).encode())) as send, \
             patch.dict('os.environ', {'WP_API_KEY': 'synthetic-key'}):
            first = ' '.join(ops_status.subscriber_lines())
            second = ' '.join(ops_status.subscriber_lines())
        self.assertIn('cannot see', first)
        self.assertIn('UNKNOWN', second)
        self.assertIn('already attempted', second)
        self.assertEqual(send.call_count, 1)

    def test_a_head_read_spends_the_budget_without_becoming_a_get_body(self):
        from urllib.request import Request
        calls = []
        def open_one(request, **kwargs):
            calls.append(request.get_method())
            return 200, {}, b''
        cache.urlopen(Request(URL, headers=UA, method='HEAD'), reader=self.reader, open_one=open_one)
        with self.assertRaises(cache.ReadLimited):
            cache.urlopen(URL, headers=UA, reader=self.reader, open_one=open_one)
        self.assertEqual(calls, ['HEAD'])


if __name__ == '__main__':
    unittest.main()
