"""Compile an audited public snapshot offline; never contact WordPress."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ORIGIN = "https://asktherecruiter.com"
CTA = (ORIGIN + "/?start=1&utm_source=ai-layoff-tracker&utm_medium=referral"
       "&utm_campaign=static_tracker#start-intake")
TRACKER_URL = ORIGIN + "/blog/ai-layoff-tracker/"
FEED_URL = ORIGIN + "/blog/feed/layoffs"
TRACKER_DATA_PATH = "blog/static-assets/tracker-data.json"
ASSETS = Path(__file__).with_name("static_site_assets")
FIELDS = ("company", "date", "country", "jobs", "source_url")
BODY_TAGS = set("h1 h2 h3 h4 h5 h6 p div section article aside header footer main nav span strong em b i small abbr u sup sub ol ul li dl dt dd table thead tbody tfoot tr th td caption colgroup col figure figcaption img details summary blockquote q cite pre code br hr time a".split())


def output_path(url: str, *, page: bool = False) -> Path:
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (parsed.scheme != "https" or parsed.netloc != "asktherecruiter.com"
            or parsed.query or parsed.fragment or "\\" in path or "%" in path
            or any(part in (".", "..") for part in path.split("/"))
            or not (path.startswith("/blog/") or path == "/robots.txt")):
        raise ValueError(f"unsafe URL: {url}")
    if page and not path.endswith("/"):
        raise ValueError(f"page URL must retain its trailing slash: {url}")
    result = Path(path.lstrip("/"))
    return result / "index.html" if page else result


def safe_link(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc
            or parsed.username or parsed.password):
        raise ValueError("unsafe source URL")
    return html.escape(value, quote=True)


class BodyAudit(HTMLParser):
    """Reject active legacy widgets instead of silently dropping features."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1s = 0
        self.resources = []

    def handle_starttag(self, tag, attrs):
        if tag not in BODY_TAGS:
            raise ValueError(f"active content needs migration: {tag}")
        for name, value in attrs:
            if name.lower().startswith("on") or name in {"style", "srcdoc", "srcset", "xlink:href"}:
                raise ValueError("active content needs migration: attribute")
            if name in {"href", "src"} and value and urlsplit(value).scheme.lower() in {"javascript", "data"}:
                raise ValueError("active content needs migration: URL")
            if value and any(part in value for part in ("wp-json/", "admin-ajax.php", "wp-admin/")):
                raise ValueError("active content needs migration: WordPress dependency")
            if name == "src" and value:
                self.resources.append(value)
        self.h1s += tag == "h1"

    handle_startendtag = handle_starttag

    def handle_comment(self, data):
        raise ValueError("HTML comments must be removed from captured fragments")

    def handle_decl(self, data):
        raise ValueError("HTML declarations are not supported in captured fragments")

    handle_pi = handle_decl
    unknown_decl = handle_decl


def load_snapshot(path: Path) -> tuple[dict, dict[str, bytes]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not data.get("captured_at") or not data.get("source_revision"):
        raise ValueError("snapshot needs schema, captured_at and source_revision")
    if not data.get("pages") or not data.get("sitemaps"):
        raise ValueError("snapshot needs pages and independent baseline sitemaps")
    files, destinations = {}, set()
    root = path.parent.resolve()
    for item in data.get("files", []):
        url = item["url"]
        destination = output_path(url)
        if destination in destinations:
            raise ValueError(f"duplicate normalized snapshot destination: {url}")
        destinations.add(destination)
        source = (root / item["source"]).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise ValueError("snapshot source escapes input directory or is missing")
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"snapshot checksum mismatch: {url}")
        if url in files:
            raise ValueError(f"duplicate snapshot file: {url}")
        files[url] = content
    if ORIGIN + "/robots.txt" not in files:
        raise ValueError("recorded robots.txt is missing")
    return data, files


def sitemap_urls(roots: list[str], files: dict[str, bytes]) -> set[str]:
    found, visited = set(), set()

    def walk(url):
        if url in visited:
            return
        visited.add(url)
        if url not in files:
            raise ValueError(f"missing sitemap snapshot: {url}")
        root = ET.fromstring(files[url])
        kind = root.tag.rsplit("}", 1)[-1]
        if kind not in {"sitemapindex", "urlset"}:
            raise ValueError(f"invalid sitemap: {url}")
        for node in root:
            loc = node.find("{*}loc")
            if loc is None or not loc.text:
                raise ValueError(f"missing sitemap loc: {url}")
            target = loc.text.strip()
            if kind == "sitemapindex":
                walk(target)
            else:
                output_path(target, page=True)
                found.add(target)

    for url in roots:
        walk(url)
    if not found:
        raise ValueError("baseline sitemap contains no pages")
    return found


def validate_pages(data: dict, files: dict[str, bytes]) -> None:
    pages, outputs = {}, {output_path(url) for url in files}
    for page in data["pages"]:
        for key in ("url", "title", "description", "canonical", "robots", "body", "schema"):
            if key not in page or (key != "schema" and not page[key]):
                raise ValueError(f"page is missing {key}")
        url = page["url"]
        dest = output_path(url, page=True)
        output_path(page["canonical"], page=True)
        if url in pages or dest in outputs:
            raise ValueError(f"duplicate page or output collision: {url}")
        if not isinstance(page["schema"], list) or any(not isinstance(n, dict) for n in page["schema"]):
            raise ValueError("schema must record the original JSON-LD node list")
        audit = BodyAudit()
        audit.feed(page["body"])
        if audit.rawdata:
            raise ValueError(f"incomplete HTML fragment: {url}")
        audit.close()
        if audit.h1s != 1:
            raise ValueError(f"page needs exactly one captured h1: {url}")
        for source in audit.resources:
            if urljoin(url, source) not in files:
                raise ValueError(f"missing static resource snapshot: {source}")
        for row in page.get("rows", []):
            if set(row) != set(FIELDS):
                raise ValueError("rows must be a public projection with exactly the allowed fields")
            safe_link(row["source_url"])
        pages[url] = page
        outputs.add(dest)
    for url in sitemap_urls(data["sitemaps"], files):
        if url not in pages:
            raise ValueError(f"sitemap URL has no page: {url}")


def records_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    parts = ['<section data-records><h2>Recorded sources</h2>',
             '<label>Search records <input type="search" data-search></label>',
             '<p role="status" data-result-count></p><div class="table-wrap"><table>',
             '<thead><tr><th scope="col">Company</th><th scope="col">Date</th>',
             '<th scope="col">Country</th><th scope="col">Jobs</th><th scope="col">Source</th></tr></thead><tbody>']
    for row in rows:
        values = "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in FIELDS[:-1])
        parts.append(f'<tr>{values}<td><a href="{safe_link(row["source_url"])}">Source</a></td></tr>')
    parts.append('</tbody></table></div></section>')
    return "".join(parts)


def tracker_panel() -> str:
    selects = "".join(
        f'<label>{label} <select name="{key}" multiple size="4"></select></label>'
        for key, label in (("country", "Country"), ("industry", "Industry"),
                           ("state", "US state"), ("source_type", "Source type"))
    )
    return (
        f'<section data-tracker="/{TRACKER_DATA_PATH}"><h2>Search layoff records</h2>'
        '<form class="tracker-filters" hidden><label>Company <input type="search" name="search"></label>'
        '<label>From <input type="date" name="from"></label><label>To <input type="date" name="to"></label>'
        f'{selects}<label><input type="checkbox" name="ai"> AI explicitly cited</label>'
        '<button type="submit">Apply filters</button>'
        '<button type="button" data-export="csv">Download CSV</button>'
        '<button type="button" data-export="json">Download JSON</button></form>'
        '<p role="status">Loading tracker data.</p><h3>Jobs by month</h3><ul data-chart></ul>'
        '<div class="table-wrap"><table><thead><tr><th scope="col">Company</th>'
        '<th scope="col">Date</th><th scope="col">Country</th><th scope="col">Jobs</th>'
        '<th scope="col">Source</th></tr></thead><tbody></tbody></table></div>'
        '<button type="button" data-more hidden>Show 50 more records</button>'
        '<noscript>Enable JavaScript to use tracker filters and charts.</noscript></section>'
        '<script type="module" src="/blog/static-assets/tracker.mjs"></script>'
    )


def render(page: dict, *, tracker: bool = False, feed: bool = False) -> str:
    esc = html.escape
    content = tracker_panel() if tracker else records_table(page.get("rows", []))
    alternate = (
        f'<link rel="alternate" type="application/rss+xml" href="{FEED_URL}">' if feed else ""
    )
    nodes = []
    for node in page["schema"]:
        encoded = json.dumps(node, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        nodes.append(f'<script type="application/ld+json">{encoded}</script>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(page["title"])}</title>'
            f'<meta name="description" content="{esc(page["description"], quote=True)}">'
            f'<meta name="robots" content="{esc(page["robots"], quote=True)}">'
            f'<link rel="canonical" href="{esc(page["canonical"], quote=True)}">'
            '<link rel="stylesheet" href="/blog/static-assets/site.css">'
            + alternate + "".join(nodes) + '</head><body><header><a href="/blog/ai-layoff-tracker/">AI Layoff Tracker</a>'
            f'<a class="match-cta" data-match-cta="true" href="{esc(CTA, quote=True)}">Check my match, free</a>'
            f'</header><main>{page["body"]}{content}</main>'
            '<script src="/blog/static-assets/site.js" defer></script></body></html>')


def build(snapshot: Path, output: Path, tracker_data: Path | None = None) -> int:
    data, files = load_snapshot(snapshot)
    validate_pages(data, files)
    feed = FEED_URL in files
    if feed:
        root = ET.fromstring(files[FEED_URL])
        self_links = root.findall("channel/{http://www.w3.org/2005/Atom}link")
        if (root.tag != "rss" or root.get("version") != "2.0"
                or not root.findtext("channel/title")
                or [link.get("href") for link in self_links if link.get("rel") == "self"] != [FEED_URL]):
            raise ValueError("RSS snapshot needs its recorded title and canonical self link")
    if tracker_data is not None:
        projection = json.loads(tracker_data.read_text(encoding="utf-8"))
        if (projection.get("schema") != 1 or not projection.get("exported_at")
                or not isinstance(projection.get("records"), list)
                or not projection["records"]):
            raise ValueError("expected a populated static tracker data projection")
        if not any(page["url"] == TRACKER_URL for page in data["pages"]):
            raise ValueError("snapshot needs the main tracker page to use tracker data")
    if output.exists():
        raise ValueError("output already exists; choose a clean build directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="alt-static-", dir=output.parent) as temporary:
        stage = Path(temporary) / "site"
        stage.mkdir()
        for url, content in files.items():
            dest = stage / output_path(url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        for page in data["pages"]:
            dest = stage / output_path(page["url"], page=True)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tracker = tracker_data is not None and page["url"] == TRACKER_URL
            dest.write_text(
                render(page, tracker=tracker, feed=feed and page["url"] == TRACKER_URL),
                encoding="utf-8",
            )
        shutil.copytree(ASSETS, stage / "blog/static-assets")
        if tracker_data is not None:
            shutil.copyfile(tracker_data, stage / TRACKER_DATA_PATH)
        if feed:
            (stage / "_headers").write_text(
                "/blog/feed/layoffs\n  Content-Type: application/rss+xml; charset=utf-8\n",
                encoding="utf-8",
            )
        os.replace(stage, output)
    return len(data["pages"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument("--tracker-data", type=Path, help="verified output from static_data.py")
    args = parser.parse_args(argv)
    print(f"Built {build(args.snapshot, args.out, args.tracker_data)} pages from the supplied public snapshot")


if __name__ == "__main__":
    main()
