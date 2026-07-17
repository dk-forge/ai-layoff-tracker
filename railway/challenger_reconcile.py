"""Autonomously reconcile the US AI-primary announcement metric with Challenger.

Challenger's per-event database is not public, so this is a coverage signal,
not a command to alter tracker data.  A variance over the configured threshold
fails loudly, preserving the report URL and both definitions in the log.
"""
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
FEED = "https://www.challengergray.com/blog/category/job-cuts-report/feed/"


def _strip(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def latest_report():
    response = requests.get(FEED, headers=UA, timeout=45)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        url = ""
        published = ""
        for child in list(node):
            tag = child.tag.rsplit("}", 1)[-1].lower()
            if tag == "link" and child.text:
                url = child.text.strip()
            elif tag in ("pubdate", "date") and child.text:
                published = child.text.strip()
        if url:
            try:
                report_month = parsedate_to_datetime(published).strftime("%Y-%m")
            except (TypeError, ValueError, IndexError):
                report_month = date.today().strftime("%Y-%m")
            return url, report_month
    raise RuntimeError("No report URL found in Challenger job-cuts feed")


def challenger_ai_total(url):
    response = requests.get(url, headers=UA, timeout=45)
    response.raise_for_status()
    text = _strip(response.text)
    patterns = (
        r"So far this year, AI has been cited (?:in|for) ([\d,]+) job cut",
        r"Artificial Intelligence[^.]{0,160}?([\d,]+) cuts this year",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1).replace(",", ""))
    raise RuntimeError("Could not extract Challenger YTD AI total from latest report")


def tracker_total(site, query):
    url = site.rstrip("/") + "/wp-json/layoffs/v1/aggregate?" + query
    response = requests.get(url, headers=UA, timeout=90)
    response.raise_for_status()
    return int(response.json()["totals"]["jobs"]), url


def tracker_comparison_totals(site, year):
    """Return strict and visible figures without pretending they are equal."""
    strict, strict_url = tracker_total(
        site, f"years={year}&date_basis=announcement&employer_country=United%20States&ai_primary=1&stage=announced")
    observed, observed_url = tracker_total(
        site, f"years={year}&date_basis=announcement&country=United%20States&ai=1&stage=announced")
    return strict, strict_url, observed, observed_url


def publish_record(site, payload):
    key = os.environ.get("WP_API_KEY", "")
    if not key:
        raise RuntimeError("WP_API_KEY is required to retain the public reconciliation record")
    response = requests.post(site.rstrip("/") + "/wp-json/layoffs/v1/benchmarks/challenger",
        json=payload, headers={**UA, "X-Layoff-API-Key": key}, timeout=60)
    response.raise_for_status()


def main():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    year = int(os.environ.get("BENCHMARK_YEAR") or date.today().year)
    allowed = float(os.environ.get("CHALLENGER_ALLOWED_VARIANCE") or "0.10")
    report, report_month = latest_report()
    challenger = challenger_ai_total(report)
    tracker, tracker_url, observed, observed_url = tracker_comparison_totals(site, year)
    variance = (tracker - challenger) / challenger if challenger else 0.0
    payload = {
        "year": year, "report_month": report_month, "benchmark": "Challenger, Gray & Christmas",
        "benchmark_url": report, "challenger_ai_jobs_ytd": challenger,
        "tracker_strict_query": tracker_url,
        "tracker_ai_primary_announced_us_employer_jobs_ytd": tracker,
        "tracker_observed_query": observed_url,
        "tracker_ai_cited_announced_us_job_location_jobs_ytd": observed,
        "variance": round(variance, 4), "allowed_variance": allowed,
        "definition": "Strict: US-based employer + announced cuts + AI primary cause + canonical event. Observed: US job location + any explicit AI citation + announced; not comparable to Challenger.",
    }
    publish_record(site, payload)
    print(json.dumps(payload, indent=2))
    if abs(variance) > allowed:
        print("RECONCILIATION OUTSIDE THRESHOLD: trigger backfill/quality investigation; do not force totals.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
