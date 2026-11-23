"""Build a non-indexable ALT preview from checksum-pinned public backups."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from xml.sax.saxutils import escape

import static_site

TABLES = ("layoffs", "company_directory")


def checked_backup(content: bytes, state: dict, name: str) -> bytes:
    try:
        raw = gzip.decompress(content)
    except (OSError, EOFError) as exc:
        raise ValueError(f"backup checksum cannot be verified: {name}") from exc
    if hashlib.sha256(raw).hexdigest() != state["tables"][name]["sha256"]:
        raise ValueError(f"backup checksum mismatch: {name}")
    return raw


def read_table(root: Path, state: dict, name: str) -> list[dict]:
    raw = checked_backup((root / f"{name}.jsonl.gz").read_bytes(), state, name)
    return [json.loads(line) for line in raw.splitlines() if line]


def build_preview(state_path: Path, backups: Path, output: Path) -> int:
    state = json.loads(state_path.read_text())
    captured = datetime.fromisoformat(state["recorded_at"].replace("Z", "+00:00"))
    rows = [r for r in read_table(backups, state, "layoffs")
            if r.get("review_status") == "verified" and str(r.get("superset_of")) == "0"]
    if not rows:
        raise ValueError("no reviewed, non-superset backup rows available for preview")
    companies = read_table(backups, state, "company_directory")
    by_company = {}
    for row in rows:
        by_company.setdefault(row["company_key"], []).append(row)
    base = static_site.ORIGIN
    pages = []

    def page(path: str, label: str, selected: list[dict], links: str = ""):
        url = base + path
        pages.append({
            "url": url, "title": "Preview: " + label, "canonical": url,
            "description": "Offline preview of reviewed source records from the public ALT backup.",
            "robots": "noindex, nofollow", "schema": [{
                "@context": "https://schema.org", "@type": "WebPage", "url": url,
                "name": "Preview: " + label}],
            "body": (f"<h1>Preview: {html.escape(label)}</h1>"
                     f"<p>Backup captured {captured.date().isoformat()}. Reviewed source rows only. "
                     "This is not the live tracker, a complete event inventory or a layoff total. "
                     "Production URL and SEO parity have not been verified.</p>" + links),
            "rows": [{"company": r["company"], "date": r.get("layoff_date") or "Not stated",
                      "country": r.get("country") or "Not stated",
                      "jobs": r["job_count"] if r.get("job_count") is not None else "Not stated",
                      "source_url": r["source_url"]} for r in selected],
        })

    links, seen = [], set()
    for company in companies:
        selected = by_company.get(company["company_key"])
        if not selected:
            continue
        slug = company["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError("invalid or duplicate recorded company slug")
        seen.add(slug)
        path = f"/blog/company-layoffs/{slug}/"
        label = company["display_name"]
        page(path, label, selected)
        links.append(f'<li><a href="{path}">{html.escape(label)}</a></li>')
    page("/blog/company-layoffs/", "Companies in the reviewed backup", [], "<ul>" + "".join(links) + "</ul>")
    page("/blog/ai-layoff-tracker/", "AI Layoff Tracker", rows,
         '<p><a href="/blog/company-layoffs/">Browse companies in this preview</a></p>')
    with tempfile.TemporaryDirectory(prefix="alt-preview-input-") as temporary:
        root = Path(temporary)
        sitemap = ('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   + "".join(f'<url><loc>{escape(p["url"])}</loc></url>' for p in pages) + '</urlset>')
        files = []
        for name, path, content in [
            ("sitemap.xml", "/blog/preview-sitemap.xml", sitemap),
            ("robots.txt", "/robots.txt", "User-agent: *\nDisallow: /\n"),
        ]:
            data = content.encode()
            (root / name).write_bytes(data)
            files.append({"url": base + path, "source": name, "sha256": hashlib.sha256(data).hexdigest()})
        manifest = {"schema": 1, "preview": True, "captured_at": state["recorded_at"],
                    "source_revision": "backup-" + captured.date().isoformat(),
                    "files": files, "sitemaps": [base + "/blog/preview-sitemap.xml"], "pages": pages}
        snapshot = root / "manifest.json"
        snapshot.write_text(json.dumps(manifest))
        return static_site.build(snapshot, output)


def download_backups(state: dict, destination: Path):
    day = datetime.fromisoformat(state["recorded_at"].replace("Z", "+00:00")).date().isoformat()
    destination.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        url = f"https://github.com/dk-forge/ai-layoff-tracker/releases/download/backup-{day}/{name}.jsonl.gz"
        with urlopen(url, timeout=60) as response:
            content = response.read()
        checked_backup(content, state, name)
        (destination / f"{name}.jsonl.gz").write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("railway/backup_state.json"))
    parser.add_argument("--backups", type=Path)
    parser.add_argument("--out", type=Path, default=Path("dist"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="alt-public-backup-") as temporary:
        backups = args.backups or Path(temporary)
        if args.backups is None:
            download_backups(json.loads(args.state.read_text()), backups)
        print(f"Built {build_preview(args.state, backups, args.out)} preview pages; no deployment")


if __name__ == "__main__":
    main()
