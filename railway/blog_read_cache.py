"""An hourly cap for public blog pages; authenticated reads have a separate run budget."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import io
import json
import math
import os
import tempfile
import time
import uuid
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.response import addinfourl

try:
    import authenticated_blog_reads as auth_reads
except ModuleNotFoundError:
    from railway import authenticated_blog_reads as auth_reads

TTL = 3600
MAX_BODY = 8 * 1024 * 1024
_PARAMS_UNSET = object()
BUSTERS = {'cb', '_', '_fresh', 'cache_bust', 'cachebuster'}
PRIVATE_PARAMS = {'key', 'api_key', 'token', 'email', 'password', 'auth', 'nonce', '_wpnonce', 'preview', 'rest_route'}
PRIVATE_HEADERS = {'authorization', 'cookie', 'x-layoff-api-key', 'x-wp-nonce', 'range'}


class ReadLimited(OSError):
    def __init__(self, remaining=TTL):
        super().__init__('blog read already attempted in this hour; no new request was sent')
        self.retry_after = max(1, math.ceil(remaining))


def cacheable(url, headers, method='GET'):
    try:
        parsed = urlsplit(url)
        path = unquote(parsed.path)
        sent = {k.lower(): str(v) for k, v in headers.items()}
        return (method == 'GET' and parsed.scheme in ('https', 'http')
                and parsed.netloc == 'asktherecruiter.com'
                and (path == '/blog' or path.startswith('/blog/'))
                and not any(part in path for part in ('/wp-json', '/wp-admin', '/wp-login', '/wp-cron', '/xmlrpc'))
                and not ({k.lower() for k, _ in parse_qsl(parsed.query)} & PRIVATE_PARAMS)
                and not (set(sent) & PRIVATE_HEADERS)
                and 'ailayofftracker/1.0' in sent.get('user-agent', '').lower())
    except ValueError:
        return False


def eligible(url, headers, method='GET'):
    """Only anonymous public page reads spend the hourly URL budget."""
    if method not in ('GET', 'HEAD') or not auth_reads.blog_host(url):
        return False
    if auth_reads.authenticated(url, headers):
        return False
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    return not any(part in path for part in ('/wp-json', '/wp-admin', '/wp-login', '/wp-cron', '/xmlrpc')) and not any(
        key.lower() == 'rest_route' for key, _ in parse_qsl(parsed.query))


def _fresh_url(url, headers):
    sent = {key.lower() for key in headers}
    if not sent.intersection({'authorization', 'x-layoff-api-key', 'x-wp-nonce'}):
        return url
    parsed = urlsplit(url)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == '_fresh' for key, _ in query):
        query.append(('_fresh', uuid.uuid4().hex))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def cache_key(url):
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in BUSTERS | PRIVATE_PARAMS]
    query.sort(key=lambda pair: pair[0])
    canonical = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ''))
    return hashlib.sha256(canonical.encode()).hexdigest()


class ReadCache:
    def __init__(self, root=None, clock=time.time):
        self.root = Path(root or os.environ.get('ALT_BLOG_CACHE_DIR') or Path.home() / '.cache/alt-public-pages')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.stat().st_mode & 0o077:
            raise OSError('blog cache directory must be private to its worker owner')
        self.clock = clock

    def write(self, path, data):
        with tempfile.NamedTemporaryFile(mode='w', dir=self.root, delete=False) as handle:
            temporary = Path(handle.name)
            try:
                json.dump(data, handle)
                handle.flush()
                os.fsync(handle.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, path)

    def get(self, url, fetch, variant='', retain=True):
        key = cache_key(url)
        path = self.root / (key + '.json')
        descriptor = os.open(self.root / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                existing = json.loads(path.read_text()) if path.exists() else None
            except (OSError, ValueError):
                raise ReadLimited() from None
            now = self.clock()
            if existing and now - existing['requested_at'] < TTL:
                if not retain or existing['kind'] != 'response' or existing.get('variant', '') != variant:
                    auth_reads.RUN.count('public_blog', 'cap_refusals')
                    raise ReadLimited(TTL - (now - existing['requested_at']))
                auth_reads.RUN.count('public_blog', 'cache_hits')
                return {'requested_at': existing['requested_at'], 'status': existing['status'], 'headers': existing['headers'],
                        'body': base64.b64decode(existing['body'])}
            record = {'requested_at': now, 'kind': 'pending', 'variant': variant}
            self.write(path, record)
            try:
                auth_reads.RUN.count('public_blog', 'requests')
                status, headers, body = fetch()
            except BaseException:
                self.write(path, {**record, 'kind': 'error'})
                raise
            public_headers = {k: v for k, v in headers.items() if k.lower() not in
                              {'set-cookie', 'set-cookie2', 'authentication-info'}}
            result = {'requested_at': now, 'status': status, 'headers': public_headers, 'body': body}
            if not retain or body is None or len(body) > MAX_BODY:
                self.write(path, {**record, 'kind': 'not_retained'})
            else:
                self.write(path, {**record, 'kind': 'response', 'status': status,
                                  'headers': public_headers, 'body': base64.b64encode(body).decode()})
            return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_one(request, timeout=30, **kwargs):
    from urllib.request import HTTPSHandler
    handlers = [NoRedirect()]
    if kwargs.get('context') is not None:
        handlers.append(HTTPSHandler(context=kwargs['context']))
    try:
        response = build_opener(*handlers).open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise OSError('public page exceeds safe buffered-read size')
        return response.status, dict(response.headers.items()), body


def _variant(headers):
    values = {k.lower(): v for k, v in headers.items()}
    return hashlib.sha256(json.dumps({k: values.get(k, '') for k in ('user-agent', 'accept', 'accept-language', 'authorization', 'cookie', 'x-layoff-api-key', 'x-wp-nonce')}, sort_keys=True).encode()).hexdigest()


def urlopen(request, data=None, timeout=30, *, headers=None, reader=None, open_one=None, stream_opener=None, _auth_attempts=3, **kwargs):
    from urllib.request import urlopen as direct
    if isinstance(request, str):
        request = Request(request, data=data, headers=headers or {})
    elif data is not None:
        import copy
        request = copy.copy(request)
        request.data = data
    sent = dict(request.header_items())
    if request.get_method() in ('GET', 'HEAD') and auth_reads.authenticated(request.full_url, sent):
        transport = stream_opener or direct
        request.full_url = _fresh_url(request.full_url, sent)
        return auth_reads.read(lambda: transport(request, timeout=timeout, **kwargs), attempts=_auth_attempts)
    if not eligible(request.full_url, sent, request.get_method()):
        return (stream_opener or direct)(request, timeout=timeout, **kwargs)
    fresh_url = _fresh_url(request.full_url, sent)
    if fresh_url != request.full_url:
        import copy
        request = copy.copy(request)
        request.full_url = fresh_url
    reader = reader or ReadCache()
    if stream_opener:
        fresh = []
        def fetch_stream():
            response = stream_opener(request, timeout=timeout)
            fresh.append(response)
            return response.status, dict(response.headers.items()), None
        result = reader.get(request.full_url, fetch_stream, _variant(sent) + ':stream')
        if fresh:
            return fresh[0]
        raise ReadLimited()
    seen = set()
    current = request.full_url
    while current not in seen and len(seen) < 8:
        seen.add(current)
        req = Request(current, headers=sent, data=request.data, method=request.get_method())
        result = reader.get(current, lambda: (open_one or _open_one)(req, timeout=timeout, **kwargs), _variant(sent) + ':urllib:' + request.get_method(), retain=cacheable(current, sent, request.get_method()))
        message = Message()
        for name, value in result['headers'].items():
            message[name] = value
        if result['status'] in (301, 302, 303, 307, 308):
            current = urljoin(current, message.get('Location', ''))
            if not eligible(current, sent):
                raise OSError('public blog redirect left the cache scope')
            continue
        if result['status'] >= 400:
            raise HTTPError(current, result['status'], 'cached public-page HTTP error', message, io.BytesIO(result['body']))
        response = addinfourl(io.BytesIO(result['body']), message, current, result['status'])
        response.msg = 'Public page'
        return response
    raise OSError('public blog redirect loop or excessive chain')


def get(url, params=_PARAMS_UNSET, *, getter=None, reader=None, _method='GET', _auth_attempts=3, **kwargs):
    if params is not _PARAMS_UNSET:
        kwargs["params"] = params
    import requests
    getter = getter or requests.get
    session = getattr(getter, '__self__', None)
    headers = {**(getattr(session, 'headers', None) or {}), **(kwargs.get('headers') or {})}
    if not auth_reads.blog_host(url):
        return getter(url, **kwargs)
    params_value = kwargs.get('params')
    query = urlencode(params_value, doseq=True) if isinstance(params_value, (dict, list, tuple)) else (params_value or '')
    parsed = urlsplit(url)
    combined_query = '&'.join(value for value in (parsed.query, query) if value)
    prepared = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, combined_query, parsed.fragment))
    if auth_reads.authenticated(prepared, headers, auth=kwargs.get('auth') or getattr(session, 'auth', None),
                                cookies=kwargs.get('cookies') or getattr(session, 'cookies', None)):
        return auth_reads.read(lambda: getter(_fresh_url(url, headers), **kwargs), attempts=_auth_attempts)
    if not eligible(prepared, headers, _method):
        return getter(url, **kwargs)
    prepared = _fresh_url(prepared, headers)
    reader = reader or ReadCache()
    seen = set()
    current = prepared
    follow = kwargs.get('allow_redirects', True)
    while current not in seen and len(seen) < 8:
        seen.add(current)
        fresh = []
        def fetch():
            options = {**kwargs, 'allow_redirects': False}
            options.pop('params', None)
            response = getter(current, **options)
            fresh.append(response)
            return response.status_code, dict(response.headers), None if kwargs.get('stream') else response.content
        try:
            result = reader.get(current, fetch, _variant(headers) + ':requests:' + _method, retain=cacheable(current, headers, _method))
        except ReadLimited as exc:
            raise requests.RequestException(str(exc)) from None
        if fresh:
            response = fresh[0]
        else:
            response = requests.Response()
            response.status_code = result['status']
            response.headers.update(result['headers'])
            response._content = result['body']
            response._content_consumed = True
            response.url = current
        if follow and response.status_code in (301, 302, 303, 307, 308):
            current = urljoin(current, response.headers.get('Location', ''))
            response.close()
            if not eligible(current, headers, _method):
                raise requests.RequestException('public blog redirect left the cache scope')
            continue
        return response
    raise requests.RequestException('public blog redirect loop or excessive chain')


def request(method, url, *, requester=None, **kwargs):
    if requester is None:
        import requests
        requester = requests.request
    if method.upper() not in ('GET', 'HEAD'):
        return requester(method, url, **kwargs)
    return get(url, _method=method.upper(), getter=lambda target, **options: requester(method, target, **options), **kwargs)
