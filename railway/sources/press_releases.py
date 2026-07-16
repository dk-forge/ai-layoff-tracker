"""Opt-in collector for official company newsroom and IR RSS/Atom feeds.

Feeds are configuration, not scraped guesses.  Set PRESS_RELEASE_FEEDS to a
JSON array of objects such as:
[{"name":"Example Corp","url":"https://investor.example.com/rss","country":"United States"}]

Only feeds controlled by the company or an exchange should be added.  The
collector is intentionally dormant until a reviewed feed registry is supplied.
"""
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

from source_registry import discovery_terms

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}


def _feeds():
    raw = os.environ.get("PRESS_RELEASE_FEEDS", "[]")
    try:
        feeds = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("PRESS_RELEASE_FEEDS must be valid JSON")
    if not isinstance(feeds, list):
        raise RuntimeError("PRESS_RELEASE_FEEDS must be a JSON array")
    return [f for f in feeds if isinstance(f, dict) and f.get("url") and f.get("name")]


def _text(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value or ""))).strip()


def _node_text(node, *names):
    for child in list(node):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names and child.text:
            return _text(child.text)
    return ""


def _items(payload):
    root = ET.fromstring(payload)
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in {"item", "entry"}:
            continue
        title = _node_text(node, "title")
        link = _node_text(node, "link")
        if not link:
            for child in list(node):
                if child.tag.rsplit("}", 1)[-1].lower() == "link":
                    link = child.attrib.get("href", "")
                    if link:
                        break
        description = _node_text(node, "description", "summary", "content")
        published = _node_text(node, "pubdate", "published", "updated")
        yield title, link, description, published


def pull_press_releases(days_back=3):
    """Return recent, layoff-shaped official releases from configured feeds."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    terms = tuple(t.lower() for t in discovery_terms())
    out = []
    for feed in _feeds():
        response = requests.get(feed["url"], headers=UA, timeout=30)
        response.raise_for_status()
        for title, url, description, published in _items(response.content):
            text = f"{title} {description}".strip()
            if not url or not any(term in text.lower() for term in terms):
                continue
            # Feed dates vary widely; retain the item if missing/unparseable
            # rather than silently losing a primary-source announcement.
            filing_date = ""
            is_recent = True
            for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(published[:31], fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        is_recent = False
                        break
                    filing_date = dt.date().isoformat()
                    break
                except ValueError:
                    continue
            else:
                filing_date = ""
            if not is_recent:
                continue
            out.append({
                "source_type": "press_release",
                "source_name": feed["name"],
                "verification_level": "silver",
                "raw_text": text,
                "source_url": url,
                "company_name": feed.get("company_name") or feed["name"],
                "ticker": feed.get("ticker"),
                "filing_date": filing_date,
                "country": feed.get("country"),
                "employer_country": feed.get("employer_country") or feed.get("country"),
            })
    print(f"Press releases: {len(out)} matched official-feed item(s)")
    return out
