"""Quota-independent GDELT GKG discovery from official 15-minute ZIP files.

GDELT publishes separate English and Translingual GKG streams.  Both are
required for a global verdict.  This reader applies the same page-title/theme
contract as the BigQuery mirror and returns ``complete=False`` when any
required interval cannot be read; missing data never becomes an empty success.
"""
from __future__ import annotations

import html
import io
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, timezone
from urllib.parse import urlparse

import requests


BASE_URL = "https://data.gdeltproject.org/gdeltv2"
USER_AGENT = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
INTERVAL = timedelta(minutes=15)
FILE_TIMEOUT_SECONDS = max(10, min(90, int(os.environ.get("GDELT_RAW_TIMEOUT", "45"))))
FILE_WORKERS = max(1, min(16, int(os.environ.get("GDELT_RAW_WORKERS", "8"))))
MAX_FILE_BYTES = 32 * 1024**2
MAX_MEMBER_BYTES = 256 * 1024**2
MAX_FILES = 1400  # both streams for at most seven days plus an endpoint interval
MAX_WINDOW_BYTES = 16 * 1024**3

THEMES = (
    "UNEMPLOYMENT",
    "WB_2806_DISMISSAL_PROCEDURES",
    "WB_2790_LABOR_REDUNDANCY",
    "WB_2792_COLLECTIVE_REDUNDANCY_PROCEDURES",
)
TITLE_RX = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.DOTALL)


def _floor_interval(value):
    value = value.astimezone(timezone.utc)
    return value.replace(minute=(value.minute // 15) * 15, second=0, microsecond=0)


def file_urls(start, end):
    """Yield every required (timestamp, stream, URL), endpoints included."""
    current = _floor_interval(start)
    last = _floor_interval(end)
    while current <= last:
        stamp = current.strftime("%Y%m%d%H%M%S")
        yield current, "english", f"{BASE_URL}/{stamp}.gkg.csv.zip"
        yield current, "translation", f"{BASE_URL}/{stamp}.translation.gkg.csv.zip"
        current += INTERVAL


def _download(url, deadline=None):
    remaining = None if deadline is None else deadline - time.monotonic()
    if remaining is not None and remaining <= 0:
        raise TimeoutError("raw GKG collection deadline reached")
    timeout = FILE_TIMEOUT_SECONDS if remaining is None else max(1, min(FILE_TIMEOUT_SECONDS, remaining))
    response = requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=(10, timeout), stream=True)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    declared = int(response.headers.get("Content-Length") or 0)
    if declared > MAX_FILE_BYTES:
        raise ValueError("raw GKG file exceeds the per-file byte ceiling")
    chunks = []
    size = 0
    for chunk in response.iter_content(1024 * 1024):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            raise ValueError("raw GKG file exceeded the per-file byte ceiling")
        chunks.append(chunk)
    return b"".join(chunks)


def _articles_from_zip(payload, start_int, end_int, folded_terms):
    articles = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [item for item in archive.infolist() if not item.is_dir()]
        if len(members) != 1 or members[0].file_size > MAX_MEMBER_BYTES:
            raise ValueError("raw GKG archive has an unsafe member layout or size")
        with archive.open(members[0]) as raw:
            for encoded in raw:
                fields = encoded.decode("utf-8", errors="replace").rstrip("\r\n").split("\t")
                if len(fields) < 27:
                    continue
                try:
                    stamp = int(fields[1])
                except (TypeError, ValueError):
                    continue
                if stamp < start_int or stamp > end_int:
                    continue
                extras = fields[26]
                match = TITLE_RX.search(extras)
                title = html.unescape(match.group(1)).strip() if match else ""
                title_folded = title.casefold()
                themes = fields[8]
                if not (any(term in title_folded for term in folded_terms)
                        or any(theme in themes for theme in THEMES)):
                    continue
                url = fields[4].strip()
                domain = fields[3].strip().lower()
                if not domain and url:
                    domain = (urlparse(url).hostname or "").lower()
                if not url or not domain:
                    continue
                articles.append({
                    "url": url,
                    "domain": domain,
                    "title": title,
                    "seendate": f"{stamp:014d}"[0:8] + "T" + f"{stamp:014d}"[8:14] + "Z",
                })
    return articles


def query_window_walk(start, end, terms, *, fetch_fn=None, workers=FILE_WORKERS,
                      deadline=None):
    """Read the two official GKG streams for a bounded window.

    Returns ``(articles, complete)``.  A 404, corrupt archive, byte ceiling,
    download error, or deadline makes the answer partial while retaining every
    article recovered from the other files.
    """
    tasks = list(file_urls(start, end))
    if len(tasks) > MAX_FILES:
        tasks = tasks[:MAX_FILES]
        complete = False
    else:
        complete = True
    downloader = fetch_fn or (lambda url: _download(url, deadline=deadline))
    folded_terms = tuple(dict.fromkeys(
        (term or "").strip().casefold() for term in terms if (term or "").strip()
    ))
    start_int = int(start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))
    end_int = int(end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))
    articles = []
    compressed_bytes = 0
    failures = {}

    with ThreadPoolExecutor(max_workers=max(1, min(16, int(workers)))) as pool:
        future_to_task = {pool.submit(downloader, url): (stamp, stream, url)
                          for stamp, stream, url in tasks}
        for future in as_completed(future_to_task):
            if deadline is not None and time.monotonic() >= deadline:
                complete = False
                for pending in future_to_task:
                    pending.cancel()
                break
            try:
                payload = future.result()
                if payload is None:
                    complete = False
                    _stamp, stream, _url = future_to_task[future]
                    failures[(stream, "missing")] = failures.get((stream, "missing"), 0) + 1
                    continue
                compressed_bytes += len(payload)
                if compressed_bytes > MAX_WINDOW_BYTES:
                    complete = False
                    for pending in future_to_task:
                        pending.cancel()
                    break
                articles.extend(_articles_from_zip(
                    payload, start_int, end_int, folded_terms))
            except Exception as exc:
                complete = False
                _stamp, stream, _url = future_to_task[future]
                reason = type(exc).__name__
                failures[(stream, reason)] = failures.get((stream, reason), 0) + 1

    if failures:
        summary = ", ".join(
            f"{stream}:{reason}={count}"
            for (stream, reason), count in sorted(failures.items())
        )
        print(f"GDELT raw incomplete intervals ({summary})")

    unique = {}
    for article in articles:
        unique.setdefault(article["url"], article)
    ordered = sorted(unique.values(), key=lambda item: (item.get("seendate", ""), item["url"]))
    return ordered, complete
