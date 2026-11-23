"""Fresh authenticated WordPress reads with a process-run budget, not an hourly cap."""
from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlsplit

PRIVATE_HEADERS = {'authorization', 'cookie', 'x-layoff-api-key', 'x-wp-nonce'}
PRIVATE_PARAMS = {'key', 'api_key', 'token', 'email', 'password', 'auth', 'nonce', '_wpnonce', 'preview'}


class RequestBudgetExceeded(OSError):
    """This invocation has spent its authenticated request allowance."""


def blog_host(url):
    try:
        parsed = urlsplit(url)
        return (parsed.scheme in ('https', 'http') and parsed.hostname == 'asktherecruiter.com'
                and (parsed.path == '/blog' or parsed.path.startswith('/blog/')))
    except ValueError:
        return False


def authenticated(url, headers, *, auth=None, cookies=None):
    if not blog_host(url):
        return False
    parsed = urlsplit(url)
    return bool(auth or cookies or parsed.username or parsed.password
                or {key.lower() for key in headers} & PRIVATE_HEADERS
                or {key.lower() for key, _ in parse_qsl(parsed.query)} & PRIVATE_PARAMS)


class RunBudget:
    def __init__(self, limit=200, sleep=None):
        if limit < 1:
            raise ValueError('authenticated request budget must be positive')
        self.limit = limit
        self.sleep = sleep or (lambda delay: time.sleep(delay))
        self.lock = threading.Lock()
        self.counts = {'authenticated_api': {'requests': 0, 'retries': 0, 'budget_refusals': 0},
                       'public_blog': {'requests': 0, 'cache_hits': 0, 'cap_refusals': 0}}

    def count(self, group, field):
        with self.lock:
            self.counts[group][field] += 1

    def reserve(self):
        with self.lock:
            counts = self.counts['authenticated_api']
            if counts['requests'] >= self.limit:
                counts['budget_refusals'] += 1
                raise RequestBudgetExceeded('authenticated WordPress per-run request budget exhausted')
            counts['requests'] += 1

    def report(self):
        with self.lock:
            return json.loads(json.dumps(self.counts))

    def read(self, fetch, attempts=3):
        for attempt in range(attempts):
            self.reserve()
            error = None
            try:
                result = fetch()
                status = getattr(result, 'status_code', getattr(result, 'status', 200))
            except HTTPError as exc:
                result, status, error = exc, exc.code, exc
            if status != 429 and not 500 <= status < 600:
                if error:
                    raise error
                return result
            if attempt == attempts - 1:
                if error:
                    raise error
                return result
            delay = 2 ** attempt
            try:
                asked = float((getattr(result, 'headers', None) or {}).get('Retry-After', 0))
                delay = max(delay, min(60, asked))
            except (ValueError, TypeError):
                pass
            result.close()
            self.count('authenticated_api', 'retries')
            self.sleep(delay)


RUN = RunBudget(limit=int(os.environ.get('ALT_AUTH_READ_BUDGET', '200')))


def read(fetch, attempts=3):
    return RUN.read(fetch, attempts=attempts)


def report():
    counts = RUN.report()
    if any(value for group in counts.values() for value in group.values()):
        print('WordPress read traffic: ' + json.dumps(counts, sort_keys=True), file=sys.stderr)


atexit.register(report)
