"""Retain a source-linked US AI-announcement comparison with Challenger.

Challenger's event-level corpus is not public.  This worker therefore measures
coverage against its monthly published aggregates; it never changes tracker
events merely to match those aggregates.  It records both the individual
reference-month comparison and the cumulative year-to-date comparison so a
reader can distinguish a new discovery shortfall from an inherited gap.
"""
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from calendar import monthrange
from datetime import date
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import requests

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
FEED = "https://www.challengergray.com/blog/category/job-cuts-report/feed/"

# These historical figures are transcribed from the linked official 2026
# monthly reports.  Keeping the source URL next to each figure makes the
# starting benchmark reproducible without pretending Challenger publishes a
# downloadable event-level database.  New months are parsed from its official
# feed and appended automatically below.
HISTORICAL_REPORTS = {
    2026: (
        {"reference_month": "2026-01", "report_month": "2026-02", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-january-job-cuts-surge-lowest-january-hiring-on-record/", "ai_jobs_month": 7624, "ai_jobs_ytd": 7624},
        {"reference_month": "2026-02", "report_month": "2026-03", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-february-cuts-plunge-hiring-falls-56-percent/", "ai_jobs_month": 4680, "ai_jobs_ytd": 12304},
        {"reference_month": "2026-03", "report_month": "2026-04", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-march-cuts-rise-25-from-february-ai-leads-reasons/", "ai_jobs_month": 15341, "ai_jobs_ytd": 27645},
        {"reference_month": "2026-04", "report_month": "2026-05", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-april-job-cuts-rise-38-from-march-ytd-cuts-down-50/", "ai_jobs_month": 21490, "ai_jobs_ytd": 49135},
        {"reference_month": "2026-05", "report_month": "2026-06", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-may-job-cuts-rise-16-from-april-highest-may-total-since-2020/", "ai_jobs_month": 38579, "ai_jobs_ytd": 87714},
        {"reference_month": "2026-06", "report_month": "2026-07", "benchmark_url": "https://www.challengergray.com/blog/challenger-report-june-layoffs-cool-to-45849-down-53-from-may-ai-leads-reasons-for-fourth-consecutive-month/", "ai_jobs_month": 14029, "ai_jobs_ytd": 101743},
    ),
}
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


def _strip(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text))).strip()


def previous_month(month):
    """Return the data month immediately before a YYYY-MM report month."""
    year, number = (int(part) for part in month.split("-", 1))
    if number == 1:
        return f"{year - 1}-12"
    return f"{year}-{number - 1:02d}"


def month_window(reference_month, ytd=False):
    year, number = (int(part) for part in reference_month.split("-", 1))
    start = f"{year}-01-01" if ytd else f"{year}-{number:02d}-01"
    end = f"{year}-{number:02d}-{monthrange(year, number)[1]:02d}"
    return start, end


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
            return {"reference_month": previous_month(report_month), "report_month": report_month, "benchmark_url": url}
    raise RuntimeError("No report URL found in Challenger job-cuts feed")


def _first_number(text, patterns, label):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1).replace(",", ""))
    raise RuntimeError(f"Could not extract Challenger {label} AI total")


def challenger_ai_totals(url, reference_month, page_text=None):
    """Parse a new official report.  Historical records stay source-cited above."""
    text = page_text if page_text is not None else _fetch_report_text(url)
    month_name = MONTH_NAMES[int(reference_month[5:7]) - 1]
    monthly = _first_number(text, (
        rf"In {month_name}, Artificial Intelligence(?: \(AI\))?[^.]{{0,180}}?\bwith\s+([\d,]+)\s+announced",
        rf"Artificial Intelligence \(AI\) was cited for\s+([\d,]+)\s+job cuts in {month_name}",
        rf"Artificial Intelligence(?: \(AI\))?[^.]{{0,140}}?\b([\d,]+)\s+announced(?:\s+job)? cuts?[^.]{{0,80}}?\b{month_name}\b",
    ), "monthly")
    ytd = _first_number(text, (
        r"AI has been cited (?:in|for)\s+([\d,]+)\s+(?:job )?cut announcements",
        r"This reason has been cited for\s+([\d,]+)\s+cuts this year",
        r"AI ranks [^.]{0,80}?with\s+([\d,]+)\s+cuts",
        r"Artificial Intelligence(?: \(AI\))?[^.]{{0,180}}?\b([\d,]+)\s+cuts this year",
    ), "YTD")
    return monthly, ytd


def _fetch_report_text(url):
    response = requests.get(url, headers=UA, timeout=45)
    response.raise_for_status()
    return _strip(response.text)


def challenger_all_cut_totals(url, reference_month, page_text=None):
    """Fail-soft parse of Challenger's headline TOTAL announced cuts.

    The AI figures above remain strict (a parse failure fails the run); the
    all-cuts pair is an additional labeled comparator, so a wording change in
    an old report degrades to (None, None) with a printed warning instead of
    blocking the AI reconciliation.
    """
    try:
        text = page_text if page_text is not None else _fetch_report_text(url)
        month_name = MONTH_NAMES[int(reference_month[5:7]) - 1]
        monthly = _first_number(text, (
            rf"announced\s+([\d,]+)\s+(?:job )?cuts in {month_name}",
            rf"announced plans to cut\s+([\d,]+)\s+jobs in {month_name}",
            rf"{month_name}[^.]{{0,120}}?announced\s+([\d,]+)\s+(?:job )?cuts",
            rf"job cuts (?:cool(?:ed)?|fell|rose|surged|climbed)[^.]{{0,80}}?to\s+([\d,]+)",
            rf"cut\s+([\d,]+)\s+jobs in {month_name}",
        ), "monthly total")
        ytd = _first_number(text, (
            r"(?:So far this year|Year to date|This year)[^.]{0,160}?announced(?: plans to cut)?\s+([\d,]+)",
            r"employers have announced\s+([\d,]+)\s+(?:job )?cuts",
            r"announced\s+([\d,]+)\s+job cuts (?:so far )?this year",
            r"a total of\s+([\d,]+)\s+(?:job )?cuts (?:have been )?announced",
        ), "YTD total")
        return monthly, ytd
    except Exception as exc:
        print(f"WARNING: all-cuts totals unavailable for {reference_month}: {exc}")
        return None, None


def reports_for_year(year):
    reports = [dict(item) for item in HISTORICAL_REPORTS.get(year, ())]
    known_months = {item["reference_month"] for item in reports}
    # The rolling feed is intentionally only used for the current year.  A
    # manual historical run without a reviewed source manifest fails rather
    # than accidentally benchmarking the current report against another year.
    if year == date.today().year:
        latest = latest_report()
        if latest["reference_month"] not in known_months:
            monthly, ytd = challenger_ai_totals(latest["benchmark_url"], latest["reference_month"])
            latest.update({"ai_jobs_month": monthly, "ai_jobs_ytd": ytd})
            reports.append(latest)
    if not reports:
        raise RuntimeError(f"No reviewed Challenger report manifest exists for {year}")
    return sorted(reports, key=lambda item: item["reference_month"])


def tracker_total(site, query):
    url = site.rstrip("/") + "/wp-json/layoffs/v1/aggregate?" + urlencode(query)
    response = requests.get(url, headers=UA, timeout=90)
    response.raise_for_status()
    return int(response.json()["totals"]["jobs"]), url


def tracker_comparison_totals(site, reference_month):
    """Return strict and diagnostic monthly/YTD figures without equating them."""
    year = int(reference_month[:4])
    groups = {
        "strict": {"employer_country": "United States", "ai_primary": "1"},
        "observed": {"country": "United States", "ai": "1"},
        # All-cuts comparator: identical strict gates minus the AI
        # requirement, against Challenger's headline total announced cuts.
        "strict_all": {"employer_country": "United States"},
    }
    totals = {}
    urls = {}
    for name, filters in groups.items():
        for period, is_ytd in (("month", False), ("ytd", True)):
            start, end = month_window(reference_month, ytd=is_ytd)
            query = {
                "years": str(year), "date_basis": "announcement", "from": start, "to": end,
                "stage": "announced", **filters,
            }
            totals[f"{name}_{period}"], urls[f"{name}_{period}"] = tracker_total(site, query)
    return totals, urls


def publish_record(site, payload):
    key = os.environ.get("WP_API_KEY", "")
    if not key:
        raise RuntimeError("WP_API_KEY is required to retain the public reconciliation record")
    response = requests.post(site.rstrip("/") + "/wp-json/layoffs/v1/benchmarks/challenger",
        json=payload, headers={**UA, "X-Layoff-API-Key": key}, timeout=60)
    response.raise_for_status()


def payload_for_report(site, report, allowed):
    totals, urls = tracker_comparison_totals(site, report["reference_month"])
    challenger_ytd = int(report["ai_jobs_ytd"])
    challenger_month = int(report["ai_jobs_month"])
    total_month, total_ytd = challenger_all_cut_totals(report["benchmark_url"], report["reference_month"])
    variance = (totals["strict_ytd"] - challenger_ytd) / challenger_ytd if challenger_ytd else 0.0
    monthly_variance = (totals["strict_month"] - challenger_month) / challenger_month if challenger_month else 0.0
    return {
        "challenger_total_jobs_month": total_month, "challenger_total_jobs_ytd": total_ytd,
        "tracker_announced_us_employer_jobs_month": totals["strict_all_month"],
        "tracker_announced_us_employer_jobs_ytd": totals["strict_all_ytd"],
        "tracker_all_month_query": urls["strict_all_month"],
        "tracker_all_query": urls["strict_all_ytd"],
        "year": int(report["reference_month"][:4]), "reference_month": report["reference_month"],
        "report_month": report["report_month"], "benchmark": "Challenger, Gray & Christmas",
        "benchmark_url": report["benchmark_url"], "challenger_ai_jobs_month": challenger_month,
        "challenger_ai_jobs_ytd": challenger_ytd,
        "tracker_strict_month_query": urls["strict_month"],
        "tracker_ai_primary_announced_us_employer_jobs_month": totals["strict_month"],
        "tracker_strict_query": urls["strict_ytd"],
        "tracker_ai_primary_announced_us_employer_jobs_ytd": totals["strict_ytd"],
        "tracker_observed_month_query": urls["observed_month"],
        "tracker_ai_cited_announced_us_job_location_jobs_month": totals["observed_month"],
        "tracker_observed_query": urls["observed_ytd"],
        "tracker_ai_cited_announced_us_job_location_jobs_ytd": totals["observed_ytd"],
        "monthly_variance": round(monthly_variance, 4), "variance": round(variance, 4),
        "allowed_variance": allowed,
        "definition": "Strict AI pair: US employer + source-evidenced announcement date + announced + AI primary + canonical event, against Challenger AI-attributed cuts. All-cuts pair: same strict gates without the AI requirement, against Challenger total announced cuts. Diagnostic figure is US job location + any explicit AI citation and is not Challenger-comparable.",
    }


def main():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    year = int(os.environ.get("BENCHMARK_YEAR") or date.today().year)
    allowed = float(os.environ.get("CHALLENGER_ALLOWED_VARIANCE") or "0.10")
    fail_on_gap = os.environ.get("CHALLENGER_FAIL_ON_GAP", "").lower() in {"1", "true", "yes"}
    payloads = [payload_for_report(site, report, allowed) for report in reports_for_year(year)]
    for payload in payloads:
        publish_record(site, payload)
    outside = [item for item in payloads if abs(item["variance"]) > allowed]
    summary = {
        "year": year, "reports_retained": len(payloads), "allowed_variance": allowed,
        "coverage_alert": bool(outside), "fail_on_gap": fail_on_gap, "reports": payloads,
    }
    print(json.dumps(summary, indent=2))
    if outside:
        print("COVERAGE ALERT: source-evidenced discovery/enrichment must be prioritised; totals were not changed.")
    return 2 if outside and fail_on_gap else 0


if __name__ == "__main__":
    sys.exit(main())
