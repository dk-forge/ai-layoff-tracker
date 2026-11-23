"""Extract public SEO and match-link metadata without running page scripts."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

FIELDS = ('title', 'description', 'canonical', 'h1', 'jsonld', 'hreflang')
VOID = set('area base br col embed hr img input link meta param source track wbr'.split())


class Metadata(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.values = {key: [] for key in FIELDS}
        self.stack = []
        self.capture = None
        self.text = []
        self.anchor = None
        self.cta = False
        self.invalid_jsonld = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (any(item[1] for item in self.stack) or 'hidden' in attrs
                  or attrs.get('aria-hidden', '').lower() == 'true'
                  or bool(re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?\s*(?:!important\s*)?(?:;|$))',
                                    attrs.get('style', ''), re.I))
                  or bool({'hidden', 'sr-only'} & set(attrs.get('class', '').split())))
        if tag not in VOID:
            self.stack.append((tag, hidden))
        if tag == 'meta' and attrs.get('name', '').lower() == 'description':
            self.values['description'].append(attrs.get('content', '').strip())
        if tag == 'link':
            rel = attrs.get('rel', '').lower().split()
            raw_href = (attrs.get('href') or '').strip()
            href = urljoin(self.url, raw_href) if raw_href else ''
            if 'canonical' in rel:
                self.values['canonical'].append(href)
            if 'alternate' in rel and attrs.get('hreflang'):
                self.values['hreflang'].append((attrs['hreflang'].lower(), href))
        if tag in ('title', 'h1') or (tag == 'script' and attrs.get('type', '').lower() == 'application/ld+json'):
            self.capture = 'jsonld' if tag == 'script' else tag
            self.text = []
        if tag == 'a':
            self.anchor = {'href': attrs.get('href', ''), 'hidden': hidden,
                           'label': attrs.get('aria-label', ''), 'text': []}

    def handle_data(self, data):
        if self.capture:
            self.text.append(data)
        if self.anchor:
            self.anchor['text'].append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == ('script' if self.capture == 'jsonld' else self.capture):
            text = ''.join(self.text)
            if self.capture == 'jsonld':
                try:
                    self.values['jsonld'].append(json.dumps(json.loads(text), sort_keys=True, ensure_ascii=True))
                except (ValueError, TypeError):
                    self.invalid_jsonld = True
            else:
                self.values[self.capture].append(' '.join(text.split()))
            self.capture = None
        if tag == 'a' and self.anchor:
            anchor = self.anchor
            url = urlsplit(urljoin(self.url, anchor['href']))
            query = parse_qs(url.query)
            named = bool((''.join(anchor['text']) or anchor['label']).strip())
            if (url.scheme == 'https' and url.netloc == 'asktherecruiter.com'
                    and url.path in ('/', '/resume-score', '/resume-score/')
                    and all(query.get(key, [''])[0].strip() for key in ('utm_source', 'utm_medium', 'utm_campaign'))
                    and named and not anchor['hidden']):
                self.cta = True
            self.anchor = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def extract(html, url):
    parser = Metadata(url)
    parser.feed(html)
    parser.close()
    parser.values['jsonld'].sort()
    parser.values['hreflang'].sort()
    return parser
