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

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
FEED = "https://www.challengergray.com/blog/category/job-cuts-report/feed/"


def _strip(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def latest_report_url():
    response = requests.get(FEED, headers=UA, timeout=45)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        for child in list(node):
            if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.text:
                return child.text.strip()
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


def tracker_ai_primary_total(site, year):
    url = (site.rstrip("/") + "/wp-json/layoffs/v1/aggregate"
           f"?years={year}&employer_country=United%20States&ai_primary=1&stage=announced")
    response = requests.get(url, headers=UA, timeout=90)
    response.raise_for_status()
    return int(response.json()["totals"]["jobs"]), url


def main():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    year = int(os.environ.get("BENCHMARK_YEAR") or date.today().year)
    allowed = float(os.environ.get("CHALLENGER_ALLOWED_VARIANCE") or "0.10")
    report = latest_report_url()
    challenger = challenger_ai_total(report)
    tracker, tracker_url = tracker_ai_primary_total(site, year)
    variance = (tracker - challenger) / challenger if challenger else 0.0
    payload = {
        "year": year, "benchmark": "Challenger, Gray & Christmas",
        "benchmark_url": report, "challenger_ai_jobs_ytd": challenger,
        "tracker_query": tracker_url, "tracker_ai_primary_announced_jobs_ytd": tracker,
        "variance": round(variance, 4), "allowed_variance": allowed,
        "definition": "US-based employer + announced cuts + AI primary cause + canonical event",
    }
    print(json.dumps(payload, indent=2))
    if abs(variance) > allowed:
        print("RECONCILIATION OUTSIDE THRESHOLD: trigger backfill/quality investigation; do not force totals.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
