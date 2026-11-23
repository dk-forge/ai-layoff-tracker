"""Authenticated API traffic has its own bounded, fresh-read policy."""
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

import requests
import blog_read_cache as pages

URL = 'https://asktherecruiter.com/blog/ai-layoff-tracker/'
API = 'https://asktherecruiter.com/blog/wp-json/layoffs/v1/query'
HEADERS = {'User-Agent': 'AiLayoffTracker/1.0', 'X-Layoff-API-Key': 'synthetic'}


def response(status=200, body=b'fresh'):
    result = requests.Response()
    result.status_code = status
    result._content = body
    result._content_consumed = True
    return result


class AuthenticatedReads(unittest.TestCase):
    def test_authenticated_requests_are_never_blocked_by_public_cap(self):
        with tempfile.TemporaryDirectory() as root:
            reader = pages.ReadCache(Path(root) / 'public')
            reader.get(URL, lambda: (200, {}, b'public'))
            calls = []
            def fetch(url, **options):
                calls.append(url)
                return response(body=str(len(calls)).encode())
            for target in (URL, API):
                for expected in (len(calls) + 1, len(calls) + 2):
                    actual = pages.get(target, headers=HEADERS, getter=fetch, reader=reader)
                    self.assertEqual(actual.content, str(expected).encode())
            self.assertEqual(len(calls), 4)
            self.assertNotIn('synthetic', ''.join(p.read_text() for p in Path(root).rglob('*.json')))

    def test_authenticated_urllib_reads_are_never_blocked_by_public_cap(self):
        calls = []
        def transport(req, **options):
            calls.append(req.full_url)
            return pages.addinfourl(io.BytesIO(str(len(calls)).encode()), {}, req.full_url, 200)
        with tempfile.TemporaryDirectory() as root:
            reader = pages.ReadCache(Path(root) / 'public')
            reader.get(URL, lambda: (200, {}, b'public'))
            for expected in (1, 2):
                result = pages.urlopen(Request(URL, headers=HEADERS), reader=reader, stream_opener=transport)
                self.assertEqual(result.read(), str(expected).encode())
        self.assertEqual(len(calls), 2)

    def test_public_eligibility_excludes_apis_and_credentials(self):
        for url, headers in [(API, {}), (URL, HEADERS), (URL + '?token=synthetic', {}),
                             (URL, {'Cookie': 'session=synthetic'}),
                             ('https://synthetic:password@asktherecruiter.com/blog/', {})]:
            self.assertFalse(pages.eligible(url, headers))

    def test_authenticated_backoff_budget_and_separate_report(self):
        import authenticated_blog_reads as auth
        policy = auth.RunBudget(limit=4, sleep=lambda delay: delays.append(delay))
        delays = []
        replies = iter([response(429), response(502), response()])
        with patch.object(auth, 'RUN', policy):
            self.assertEqual(pages.get(API, headers=HEADERS, getter=lambda *a, **k: next(replies)).status_code, 200)
            self.assertEqual(delays, [1, 2])
            pages.get(API, headers=HEADERS, getter=lambda *a, **k: response())
            with self.assertRaises(auth.RequestBudgetExceeded):
                pages.get(API, headers=HEADERS, getter=lambda *a, **k: self.fail('over budget'))
        report = policy.report()
        self.assertEqual(report['authenticated_api']['requests'], 4)
        self.assertEqual(report['authenticated_api']['retries'], 2)
        self.assertEqual(report['authenticated_api']['budget_refusals'], 1)
        self.assertEqual(report['public_blog']['requests'], 0)
        self.assertNotIn('synthetic', str(report))

    def test_urllib_retries_5xx_and_honors_retry_after(self):
        import authenticated_blog_reads as auth
        delays = []
        policy = auth.RunBudget(limit=5, sleep=delays.append)
        calls = []
        def transport(req, **options):
            calls.append(req.full_url)
            if len(calls) < 3:
                raise HTTPError(req.full_url, 503, 'busy', {'Retry-After': '3'}, io.BytesIO(b'busy'))
            return pages.addinfourl(io.BytesIO(b'fresh'), {}, req.full_url, 200)
        with patch.object(auth, 'RUN', policy):
            self.assertEqual(pages.urlopen(Request(API, headers=HEADERS), stream_opener=transport).read(), b'fresh')
        self.assertEqual(delays, [3, 3])
        self.assertEqual(len(calls), 3)

    def test_session_auth_and_params_credentials_bypass_public_cap(self):
        session = requests.Session()
        session.auth = ('synthetic', 'password')
        with patch.object(session, 'send', return_value=response()) as send:
            with tempfile.TemporaryDirectory() as root:
                reader = pages.ReadCache(Path(root) / 'public')
                reader.get(URL, lambda: (200, {}, b'public'))
                pages.get(URL, getter=session.get, reader=reader)
                pages.get(URL, getter=session.get, reader=reader)
                self.assertEqual(send.call_count, 2)
        with patch.object(requests, 'get', return_value=response()) as send:
            pages.get(URL, params={'api_key': 'synthetic'})
            pages.get(URL, params={'api_key': 'synthetic'})
            self.assertEqual(send.call_count, 2)

    def test_existing_retry_helper_owns_one_exponential_loop(self):
        import authenticated_blog_reads as auth
        import http_retry
        delays = []
        policy = auth.RunBudget(limit=4, sleep=lambda _: self.fail('nested retry loop'))
        replies = iter([response(501), response(599), response(429), response()])
        with patch.object(auth, 'RUN', policy):
            result = http_retry.get_with_retry(API, headers=HEADERS, attempts=4,
                       get=lambda *a, **k: next(replies), sleep=delays.append, backoff=5)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(delays, [5, 10, 20])
        self.assertEqual(policy.report()['authenticated_api']['requests'], 4)
        self.assertEqual(policy.report()['authenticated_api']['retries'], 3)

    def test_new_invocation_has_a_new_authenticated_budget(self):
        import authenticated_blog_reads as auth
        for _ in range(2):
            policy = auth.RunBudget(limit=1)
            with patch.object(auth, 'RUN', policy):
                self.assertEqual(pages.get(API, headers=HEADERS, getter=lambda *a, **k: response()).status_code, 200)
                with self.assertRaises(auth.RequestBudgetExceeded):
                    pages.get(API, headers=HEADERS, getter=lambda *a, **k: self.fail('over budget'))

    def test_retry_also_spends_authenticated_budget(self):
        import authenticated_blog_reads as auth
        policy = auth.RunBudget(limit=1, sleep=lambda _: None)
        calls = []
        def fetch(*args, **kwargs):
            calls.append(1)
            return response(503)
        with patch.object(auth, 'RUN', policy):
            with self.assertRaises(auth.RequestBudgetExceeded):
                pages.get(API, headers=HEADERS, getter=fetch)
        self.assertEqual(calls, [1])
        self.assertEqual(policy.report()['authenticated_api']['budget_refusals'], 1)
