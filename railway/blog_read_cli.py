"""Read a blog URL for a workflow through the shared hourly budget."""
import argparse
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

from blog_read_cache import ReadLimited, urlopen
from authenticated_blog_reads import blog_host, RequestBudgetExceeded

UA = 'AiLayoffTracker/1.0 (+https://asktherecruiter.com)'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--key-env')
    parser.add_argument('--status-code', action='store_true')
    parser.add_argument('--allow-http-error', action='store_true')
    args = parser.parse_args(argv)
    headers = {'User-Agent': UA}
    if not args.url.startswith('https://') or not blog_host(args.url):
        parser.error('only HTTPS reads of the blog host are supported')
    if args.key_env:
        value = os.environ.get(args.key_env)
        if not value:
            parser.error('the requested key environment variable is missing')
        headers['X-Layoff-API-Key'] = value
    args.output.unlink(missing_ok=True)
    try:
        try:
            response = urlopen(Request(args.url, headers=headers), timeout=90)
        except HTTPError as exc:
            response = exc
        with response:
            args.output.write_bytes(response.read())
            if args.status_code:
                print(response.status)
            return 0 if args.allow_http_error or 200 <= response.status < 300 else 1
    except RequestBudgetExceeded:
        print('DEFERRED: authenticated per-run request budget exhausted', file=sys.stderr)
        return 75
    except ReadLimited:
        print('DEFERRED: this URL already spent its hourly read budget', file=sys.stderr)
        return 75
    except OSError as exc:
        print(f'blog read failed ({type(exc).__name__})', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
