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
from urllib.parse import urlparse

import requests

from source_registry import discovery_terms

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}


REVIEWED_FEEDS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reviewed_feeds.json"
)


def _registry_feeds():
    """Load the versioned, repo-committed reviewed-feed registry.

    The registry file is the durable, auditable admission record (each change
    is a reviewed commit).  It goes through the exact same validation gate as
    environment-supplied entries; a malformed registry fails loudly rather
    than silently shrinking coverage.
    """
    if not os.path.exists(REVIEWED_FEEDS_PATH):
        return []
    try:
        data = json.loads(open(REVIEWED_FEEDS_PATH, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"reviewed_feeds.json is unreadable or invalid JSON: {exc}")
    feeds = data.get("feeds") if isinstance(data, dict) else data
    if not isinstance(feeds, list):
        raise RuntimeError("reviewed_feeds.json must contain a 'feeds' JSON array")
    return feeds


def _feeds():
    raw = os.environ.get("PRESS_RELEASE_FEEDS", "[]")
    try:
        env_feeds = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("PRESS_RELEASE_FEEDS must be valid JSON")
    if not isinstance(env_feeds, list):
        raise RuntimeError("PRESS_RELEASE_FEEDS must be a JSON array")
    accepted, seen_urls = [], set()
    for index, feed in enumerate(_registry_feeds() + env_feeds, start=1):
        if not isinstance(feed, dict):
            raise RuntimeError(f"Reviewed feed entry {index} must be an object")
        validated = _validate_feed(feed, index)
        if validated["url"] in seen_urls:
            continue  # env override duplicating a registry entry
        seen_urls.add(validated["url"])
        accepted.append(validated)
    return accepted


def _validate_feed(feed, index=1):
    """Reject an unreviewed or third-party feed before any request is made.

    A URL being public is not enough to make it a primary source.  The
    configuration must record the company/exchange-owned host, a terms page,
    and the date it was manually reviewed.  This is deliberately a gate, not
    an attempt to infer ownership from a brand name.
    """
    required = ("name", "url", "owner_domain", "terms_url", "reviewed_at")
    missing = [key for key in required if not str(feed.get(key, "")).strip()]
    if missing:
        raise RuntimeError(
            f"PRESS_RELEASE_FEEDS entry {index} is not a reviewed official feed; "
            f"missing {', '.join(missing)}"
        )
    url = urlparse(str(feed["url"]).strip())
    terms = urlparse(str(feed["terms_url"]).strip())
    owner_domain = str(feed["owner_domain"]).strip().lower().lstrip(".")
    host = (url.hostname or "").lower()
    terms_host = (terms.hostname or "").lower()
    if url.scheme != "https" or not host:
        raise RuntimeError(f"PRESS_RELEASE_FEEDS entry {index} url must be an HTTPS feed URL")
    if terms.scheme != "https" or not terms.hostname:
        raise RuntimeError(f"PRESS_RELEASE_FEEDS entry {index} terms_url must be an HTTPS URL")
    if not owner_domain or (host != owner_domain and not host.endswith("." + owner_domain)):
        raise RuntimeError(
            f"PRESS_RELEASE_FEEDS entry {index} url host must match its reviewed owner_domain"
        )
    if terms_host != owner_domain and not terms_host.endswith("." + owner_domain):
        raise RuntimeError(
            f"PRESS_RELEASE_FEEDS entry {index} terms_url host must match its reviewed owner_domain"
        )
    try:
        reviewed_at = datetime.strptime(str(feed["reviewed_at"]), "%Y-%m-%d").date()
    except ValueError as exc:
        raise RuntimeError(
            f"PRESS_RELEASE_FEEDS entry {index} reviewed_at must be YYYY-MM-DD"
        ) from exc
    if reviewed_at > datetime.now(timezone.utc).date():
        raise RuntimeError(f"PRESS_RELEASE_FEEDS entry {index} reviewed_at cannot be in the future")
    return dict(feed, owner_domain=owner_domain)


def reviewed_feed_count():
    """Return the count only after validating every manually reviewed feed."""
    return len(_feeds())


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
    """Return recent, layoff-shaped official releases from configured feeds.

    One slow or failing feed must not lose the others' primary-source items:
    each feed is isolated, failures are reported per feed, and the run raises
    only when EVERY reviewed feed failed (a genuine outage, kept loud).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    terms = tuple(t.lower() for t in discovery_terms())
    out = []
    feeds = _feeds()
    failed = []
    for feed in feeds:
        try:
            response = requests.get(feed["url"], headers=UA, timeout=30)
            response.raise_for_status()
            payload = response.content
        except Exception as exc:
            failed.append(f"{feed['name']}: {exc.__class__.__name__}: {exc}")
            print(f"Press-release feed failed (continuing): {feed['name']}: {exc}")
            continue
        for title, url, description, published in _items(payload):
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
    if feeds and failed and len(failed) == len(feeds):
        raise RuntimeError(
            "All reviewed press-release feeds failed: " + " | ".join(failed)
        )
    print(
        f"Press releases: {len(out)} matched official-feed item(s) from "
        f"{len(feeds) - len(failed)}/{len(feeds)} reviewed feed(s)"
        + (f"; failed: {'; '.join(failed)}" if failed else "")
    )
    return out
