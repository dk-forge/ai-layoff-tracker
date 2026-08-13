"""Retain a source-linked US AI-announcement comparison with Survey.

Survey's event-level corpus is not public.  This worker therefore measures
coverage against its monthly published aggregates; it never changes tracker
events merely to match those aggregates.  It records both the individual
reference-month comparison and the cumulative year-to-date comparison so a
reader can distinguish a new discovery shortfall from an inherited gap.

SAFE TO DEFER: every figure is recomputed from the live aggregate on each run
and each record is an upsert keyed by reference month, so a run the host never
answered leaves yesterday's record standing and tomorrow's run replaces it with
a fresher one. It changes no tracker event.
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

import host_call

#: Ledger key. Must match the `job:` given to the commit-deferral-ledger step.
JOB = "survey-reconcile"

UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
# Competitor benchmark data lives in a SECRET, never the repo (standalone-brand
# rule). SURVEY_FEED_URL = the survey's RSS feed for new months; SURVEY_BENCHMARK_JSON
# = the historical monthly figures as JSON: {"2026":[{"reference_month":..,
# "report_month":..,"benchmark_url":..,"ai_jobs_month":..,"ai_jobs_ytd":..}, ...]}.
# Unset -> the reconciliation ships DORMANT (nothing to compare), so the public
# repo carries zero competitor names, numbers or URLs.
FEED = os.environ.get("SURVEY_FEED_URL", "")

def _load_historical():
    """Historical survey figures from the SURVEY_BENCHMARK_JSON secret, or {}.
    Empty -> dormant, so no competitor data is ever committed."""
    raw = os.environ.get("SURVEY_BENCHMARK_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        # keys may be str years from JSON; normalise to int
        return {int(k): tuple(v) for k, v in data.items()}
    except Exception as exc:
        print(f"SURVEY_BENCHMARK_JSON parse failed ({type(exc).__name__}); running dormant")
        return {}


HISTORICAL_REPORTS = _load_historical()

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
    raise RuntimeError("No report URL found in Survey job-cuts feed")


def _first_number(text, patterns, label):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1).replace(",", ""))
    raise RuntimeError(f"Could not extract Survey {label} AI total")


def survey_ai_totals(url, reference_month, page_text=None):
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


def survey_all_cut_totals(url, reference_month, page_text=None):
    """Fail-soft parse of Survey's headline TOTAL announced cuts.

    The AI figures above remain strict (a parse failure fails the run); the
    all-cuts pair is an additional labeled comparator, so a wording change in
    an old report degrades to (None, None) with a printed warning instead of
    blocking the AI reconciliation.
    """
    try:
        text = page_text if page_text is not None else _fetch_report_text(url)
    except Exception as exc:
        print(f"WARNING: all-cuts totals unavailable for {reference_month}: {exc}")
        return None, None
    month_name = MONTH_NAMES[int(reference_month[5:7]) - 1]
    monthly = ytd = None
    try:
        monthly = _first_number(text, (
            rf"announced\s+([\d,]+)\s+(?:job )?cuts in {month_name}",
            rf"announced plans to cut\s+([\d,]+)\s+jobs in {month_name}",
            rf"{month_name}[^.]{{0,120}}?announced\s+([\d,]+)\s+(?:job )?cuts",
            rf"job cuts (?:cool(?:ed)?|fell|rose|surged|climbed)[^.]{{0,80}}?to\s+([\d,]+)",
            rf"cut\s+([\d,]+)\s+jobs in {month_name}",
        ), "monthly total")
    except Exception as exc:
        print(f"WARNING: monthly all-cuts total unavailable for {reference_month}: {exc}")
    try:
        ytd = _first_number(text, (
            r"(?:So far this year|Year to date|This year)[^.]{0,160}?announced(?: plans to cut)?\s+([\d,]+)\s+(?:job )?cuts",
            r"employers have announced(?: plans to cut)?\s+([\d,]+)\s+(?:job )?cuts",
            r"announced\s+([\d,]+)\s+job cuts (?:so far )?this year",
            r"a total of\s+([\d,]+)\s+(?:job )?cuts (?:have been )?announced this year",
        ), "YTD total")
    except Exception as exc:
        print(f"WARNING: YTD all-cuts total unavailable for {reference_month}: {exc}")
    # Plausibility floors: Survey headline totals are always tens of
    # thousands, and a YTD figure can never be below its own month. A number
    # failing these is a mis-parse — storing null is honest; storing a wrong
    # benchmark figure is not.
    if monthly is not None and monthly < 5000:
        print(f"WARNING: dropping implausible monthly all-cuts parse {monthly} for {reference_month}")
        monthly = None
    if ytd is not None and (ytd < 5000 or (monthly is not None and ytd < monthly)):
        print(f"WARNING: dropping implausible YTD all-cuts parse {ytd} for {reference_month}")
        ytd = None
    return monthly, ytd


def reports_for_year(year):
    reports = [dict(item) for item in HISTORICAL_REPORTS.get(year, ())]
    known_months = {item["reference_month"] for item in reports}
    # The rolling feed is intentionally only used for the current year.  A
    # manual historical run without a reviewed source manifest fails rather
    # than accidentally benchmarking the current report against another year.
    if year == date.today().year:
        latest = latest_report()
        if latest["reference_month"] not in known_months:
            monthly, ytd = survey_ai_totals(latest["benchmark_url"], latest["reference_month"])
            latest.update({"ai_jobs_month": monthly, "ai_jobs_ytd": ytd})
            reports.append(latest)
    if not reports:
        raise RuntimeError(f"No reviewed Survey report manifest exists for {year}")
    return sorted(reports, key=lambda item: item["reference_month"])


def tracker_total(site, query):
    url = site.rstrip("/") + "/wp-json/layoffs/v1/aggregate?" + urlencode(query)
    payload = host_call.get_json(url, headers=UA, timeout=90)
    return int(payload["totals"]["jobs"]), url


def tracker_comparison_totals(site, reference_month):
    """Return strict and diagnostic monthly/YTD figures without equating them."""
    year = int(reference_month[:4])
    groups = {
        # Headline AI comparison — the most honest Survey-comparable basis that
        # KEEPS the "the source must state AI" bar: ai=1 => ai_explicit
        # (ai_causation in primary_cause/contributing_cause), every row of which
        # carries a verbatim quote where the source names AI as a reason. This is
        # how the Survey attributes a reason (the company cited it), without
        # importing ai_linked press-framing (which ai_broad would). Country basis
        # is employer-domicile WITH the blank -> job-location fallback the
        # front-end already uses, so US-located rows whose HQ field is blank are
        # not silently dropped.
        "ai_cited": {"country_basis": "employer", "country": "United States", "ai": "1"},
        # Stricter sub-line: AI named as THE primary cause (a subset of ai_cited).
        "strict": {"employer_country": "United States", "ai_primary": "1"},
        "observed": {"country": "United States", "ai": "1"},
        # All-cuts comparator: identical strict gates minus the AI
        # requirement, against Survey's headline total announced cuts.
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
    host_call.post_json(site.rstrip("/") + "/wp-json/layoffs/v1/benchmarks/survey",
                        payload, headers={**UA, "X-Layoff-API-Key": key},
                        timeout=60)


def payload_for_report(site, report, allowed):
    totals, urls = tracker_comparison_totals(site, report["reference_month"])
    survey_ytd = int(report["ai_jobs_ytd"])
    survey_month = int(report["ai_jobs_month"])
    total_month, total_ytd = survey_all_cut_totals(report["benchmark_url"], report["reference_month"])
    variance = (totals["strict_ytd"] - survey_ytd) / survey_ytd if survey_ytd else 0.0
    monthly_variance = (totals["strict_month"] - survey_month) / survey_month if survey_month else 0.0
    # Honest headline: quote-backed AI-cited (ai_explicit) vs the Survey's AI figure.
    ai_cited_variance = (totals["ai_cited_ytd"] - survey_ytd) / survey_ytd if survey_ytd else 0.0
    ai_cited_monthly_variance = (totals["ai_cited_month"] - survey_month) / survey_month if survey_month else 0.0
    return {
        "survey_total_jobs_month": total_month, "survey_total_jobs_ytd": total_ytd,
        "tracker_announced_us_employer_jobs_month": totals["strict_all_month"],
        "tracker_announced_us_employer_jobs_ytd": totals["strict_all_ytd"],
        "tracker_all_month_query": urls["strict_all_month"],
        "tracker_all_query": urls["strict_all_ytd"],
        "year": int(report["reference_month"][:4]), "reference_month": report["reference_month"],
        "report_month": report["report_month"], "benchmark": "Announcement survey",
        "benchmark_url": report["benchmark_url"], "survey_ai_jobs_month": survey_month,
        "survey_ai_jobs_ytd": survey_ytd,
        "tracker_strict_month_query": urls["strict_month"],
        "tracker_ai_primary_announced_us_employer_jobs_month": totals["strict_month"],
        "tracker_strict_query": urls["strict_ytd"],
        "tracker_ai_primary_announced_us_employer_jobs_ytd": totals["strict_ytd"],
        "tracker_observed_month_query": urls["observed_month"],
        "tracker_ai_cited_announced_us_job_location_jobs_month": totals["observed_month"],
        "tracker_observed_query": urls["observed_ytd"],
        "tracker_ai_cited_announced_us_job_location_jobs_ytd": totals["observed_ytd"],
        # Honest headline pair: quote-backed AI-cited (ai_explicit), employer basis
        # with job-location fallback. This is the Survey-comparable AI number.
        "tracker_ai_cited_announced_us_employer_jobs_month": totals["ai_cited_month"],
        "tracker_ai_cited_announced_us_employer_jobs_ytd": totals["ai_cited_ytd"],
        "tracker_ai_cited_month_query": urls["ai_cited_month"],
        "tracker_ai_cited_query": urls["ai_cited_ytd"],
        "ai_cited_monthly_variance": round(ai_cited_monthly_variance, 4),
        "ai_cited_variance": round(ai_cited_variance, 4),
        "monthly_variance": round(monthly_variance, 4), "variance": round(variance, 4),
        "allowed_variance": allowed,
        "definition": "Headline AI pair (ai_cited): US employer domicile with job-location fallback + source-evidenced announcement date + announced + AI explicitly cited as a reason (ai_explicit: primary OR contributing cause, each backed by a verbatim source quote naming AI) + canonical event, against Survey AI-attributed cuts. This is the most honest Survey-comparable AI basis that still requires the source to state AI; it excludes ai_linked press-framing. Strict AI sub-pair: the same but AI-primary-cause only (stricter subset). All-cuts pair: strict gates without the AI requirement, against Survey total announced cuts. Diagnostic figure is US job location + any explicit AI citation and is not Survey-comparable.",
    }


def main():
    """Deferral boundary. Each record is an upsert keyed by reference month."""
    try:
        code = _run()
    except host_call.Deferred as exc:
        return host_call.defer(JOB, str(exc))
    host_call.clear(JOB)
    return code


def _run():
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    year = int(os.environ.get("BENCHMARK_YEAR") or date.today().year)
    allowed = float(os.environ.get("SURVEY_ALLOWED_VARIANCE") or "0.10")
    fail_on_gap = os.environ.get("SURVEY_FAIL_ON_GAP", "").lower() in {"1", "true", "yes"}
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
