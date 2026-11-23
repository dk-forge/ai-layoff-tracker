"""Compare an ALT static artifact with independently fetched live sitemap pages."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from static_parity_html import FIELDS, extract

ORIGIN = 'https://asktherecruiter.com'
PREFIXES = ('/blog/ai-layoff-tracker', '/blog/layoff-tracker', '/blog/company-layoffs',
            '/blog/country-layoffs', '/blog/state-layoffs', '/blog/industry-layoffs', '/blog/layoff')
DEFAULT_SITEMAPS = ['sitemap_index.xml', 'company-layoffs-sitemap.xml', 'layoff-facets-sitemap.xml',
                    'layoff-reports-sitemap.xml', 'layoff-editions-sitemap.xml',
                    'layoff-digest-sitemap.xml', 'layoff-logs-sitemap.xml']


def validate_url(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (parsed.scheme != 'https' or parsed.netloc != 'asktherecruiter.com'
            or parsed.query or parsed.fragment or not path.startswith('/blog/')
            or '\\' in path or '%' in path or any(p in ('.', '..') for p in path.split('/'))):
        raise ValueError('URL must be an unambiguous public path on the configured blog origin')
    return path


def tracker_url(url):
    path = validate_url(url).rstrip('/')
    return any(path == prefix or path.startswith(prefix + '/') for prefix in PREFIXES)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class FetchBudgetExceeded(OSError):
    pass


class LivePages:
    """Public GETs only; shared per-URL file locks, one-hour cache and pacing."""
    def __init__(self, cache, max_requests=500, interval=1.0, max_seconds=3000):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests
        self.interval = interval
        self.requests = 0
        self.last_request = 0.0
        self.deadline = time.monotonic() + max_seconds if max_seconds else float('inf')
        self.opener = build_opener(NoRedirect())

    def response(self, url):
        validate_url(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache / (key + '.json')
        with (self.cache / (key + '.lock')).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            cached = json.loads(path.read_text()) if path.exists() else None
            if cached and time.time() - cached['requested_at'] < 3600:
                return cached
            if (self.max_requests and self.requests >= self.max_requests) or time.monotonic() >= self.deadline:
                raise FetchBudgetExceeded('live request budget exhausted; comparison is incomplete')
            time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            result = {'requested_at': time.time(), 'status': 0, 'body': '', 'location': ''}
            self.requests += 1
            try:
                request = Request(url, headers={'User-Agent': 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)'})
                try:
                    response = self.opener.open(request, timeout=30)
                except HTTPError as exc:
                    response = exc
                with response:
                    result['status'] = response.status
                    result['location'] = response.headers.get('Location', '')
                    content = response.read(10_000_001)
                    if len(content) > 10_000_000:
                        raise OSError('live page exceeds capture size limit')
                    result['body'] = content.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
            except (OSError, LookupError):
                result['status'] = 0
            finally:
                self.last_request = time.monotonic()
                path.write_text(json.dumps(result))
            return result

    def __call__(self, url):
        seen = set()
        while url not in seen and len(seen) < 8:
            seen.add(url)
            result = self.response(url)
            if result['status'] == 200:
                return result['body']
            if result['status'] != 301:
                raise OSError('live GET did not return 200 or a permanent redirect')
            url = urljoin(url, result['location'])
        raise OSError('live redirect loop or excessive chain')


def sitemap_urls(sitemaps, fetch):
    pending, seen, urls, errors = list(sitemaps), set(), set(), []
    while pending:
        url = pending.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            validate_url(url)
            root = ET.fromstring(fetch(url))
            kind = root.tag.rsplit('}', 1)[-1]
            if kind not in ('urlset', 'sitemapindex'):
                raise ValueError('not a sitemap')
            locations = [n.text.strip() for n in root.iter() if n.tag.rsplit('}', 1)[-1] == 'loc' and n.text]
            for location in locations:
                validate_url(location)
                if kind == 'sitemapindex':
                    pending.append(location)
                elif tracker_url(location):
                    urls.add(location)
        except (OSError, ValueError, ET.ParseError):
            errors.append({'url': url, 'error': 'sitemap_unavailable_or_invalid'})
    if not urls:
        errors.append({'error': 'empty_tracker_sitemap_scope'})
    return sorted(urls), errors


def redirects(dist):
    path = dist / '_redirects'
    result = {}
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[2] in ('301', '301!') and not parts[0].startswith('#'):
                validate_url(ORIGIN + parts[0])
                validate_url(ORIGIN + parts[1])
                result[parts[0]] = parts[1]
    return result


def static_file(dist, url, mapping):
    path, seen = validate_url(url), set()
    while path in mapping:
        if path in seen:
            raise ValueError('static redirect loop')
        seen.add(path)
        path = mapping[path]
    candidate = (dist / path.lstrip('/')).resolve()
    if not candidate.is_relative_to(dist.resolve()):
        raise ValueError('static path escapes artifact')
    if not candidate.is_file():
        candidate = candidate / 'index.html'
    if not candidate.resolve().is_relative_to(dist.resolve()):
        raise ValueError('static path escapes artifact')
    return candidate


def compare(dist, sitemaps, fetch):
    dist = Path(dist)
    urls, errors = sitemap_urls(sitemaps, fetch)
    try:
        mapping = redirects(dist)
    except ValueError:
        mapping = {}
        errors.append({'error': 'invalid_static_redirect_map'})
    pages = []
    for url in urls:
        item = {'url': url, 'errors': [], 'differences': {}}
        pages.append(item)
        try:
            path = static_file(dist, url, mapping)
            if not path.is_file():
                item['errors'].append('missing_static_page')
                continue
            static = extract(path.read_text(encoding='utf-8'), url)
            if not static.cta:
                item['errors'].append('missing_static_cta')
            live = extract(fetch(url), url)
            if not live.cta:
                item['errors'].append('missing_live_cta')
            if static.invalid_jsonld or live.invalid_jsonld:
                item['errors'].append('invalid_jsonld')
            for field in FIELDS:
                if field in ('title', 'description', 'canonical', 'h1'):
                    if not static.values[field] or not all(static.values[field]):
                        item['errors'].append('missing_static_' + field)
                    if not live.values[field] or not all(live.values[field]):
                        item['errors'].append('missing_live_' + field)
                if static.values[field] != live.values[field]:
                    item['differences'][field] = {'live': live.values[field], 'static': static.values[field]}
        except FetchBudgetExceeded:
            item['errors'].append('not_compared_request_budget')
        except (OSError, ValueError):
            item['errors'].append('live_or_static_unavailable')
    passed = sum(not p['errors'] and not p['differences'] for p in pages)
    return {'passed': not errors and bool(pages) and passed == len(pages), 'errors': errors, 'pages': pages,
            'totals': {'discovered': len(pages), 'passed': passed, 'failed': len(pages) - passed},
            'cta_check': 'named, UTM-tagged link without hidden markup; computed CSS visibility is a separate layout check'}


def write_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, required=True)
    parser.add_argument('--sitemap', action='append')
    parser.add_argument('--cache', type=Path, default=Path('.cache/static-parity'))
    parser.add_argument('--report', type=Path, default=Path('parity-report.json'))
    parser.add_argument('--max-requests', type=int, default=500)
    parser.add_argument('--max-seconds', type=int, default=3000)
    args = parser.parse_args()
    if args.max_requests < 0 or args.max_seconds < 0:
        parser.error('budgets must be nonnegative; zero means unlimited')
    fetch = LivePages(args.cache, args.max_requests, max_seconds=args.max_seconds)
    report = compare(args.dist, args.sitemap or [ORIGIN + '/blog/' + p for p in DEFAULT_SITEMAPS], fetch)
    report['network_requests'] = fetch.requests
    write_report(report, args.report)
    print(json.dumps({'parity_passed': report['passed'], **report['totals'], 'report': str(args.report)}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
