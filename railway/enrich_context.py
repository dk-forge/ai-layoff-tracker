"""Evidence-bounded legacy context enrichment.

Fetches a small batch of source-linked rows and fills only currently blank
employer domicile or public announcement date when exact source text supports
the value. It never changes count, layoff date, stage, source, or AI label.

Unreadable-source fallbacks (both fail-soft, both inside the same evidence
gates — exact quotes only, blank fields only, never inferred):

1. Wayback snapshot: when the cited article itself is blocked or paywalled,
   the SAME article text is read from its newest Internet Archive snapshot,
   and the evidence string records that the quote was verified against the
   snapshot, with the snapshot URL.
2. Alternate trusted source: when the cited article AND its snapshot are both
   unreadable, the GDELT BigQuery mirror is queried narrowly (company name in
   the page title + the shared layoff vocabulary + a bounded date window) for
   OTHER trusted-domain coverage of the same event. The first accessible
   article that yields exact quotes becomes the evidence source and its own
   URL is recorded inside the evidence string. Quotes are never assembled
   across sources.
"""
import os
import re
import sys
import time
from datetime import date, datetime, time as dt_time, timedelta

import requests

from extractor import extract_context_evidence
from reclassify_legacy_ai import UA, clean_html
from source_registry import discovery_terms
from sources import gdelt_bq
from sources.gdelt import _domain, _is_trusted

SITE = os.environ.get("WP_SITE_URL", "").rstrip("/")
KEY = os.environ.get("WP_API_KEY", "")
BATCH = max(1, min(50, int(os.environ.get("CONTEXT_ENRICH_BATCH", "5"))))
MODE = os.environ.get("CONTEXT_ENRICH_MODE", "default")
# The fallbacks add bounded network work per row; stopping between rows keeps
# the daily job inside its GitHub Actions ceiling and the queue resumes safely.
DEADLINE_SECONDS = max(60, min(1100, int(os.environ.get("CONTEXT_DEADLINE_SECONDS", "900"))))

WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"
WAYBACK_TIMEOUT = 20
# A tag-stripped real article is far longer than a bot-block or paywall stub.
MIN_ARTICLE_CHARS = 300
ALT_WINDOW_DAYS = 45     # announcement coverage clusters near the event date
ALT_FETCH_LIMIT = 3      # bounded candidate fetches per row, fail-soft


def query_params(batch, mode="default"):
    """Return a narrow, evidence-only candidate query for the selected mode."""
    params = {
        "context_missing": "1", "per_page": batch, "page": 1,
        "sort": "id", "dir": "asc",
    }
    if mode == "challenger_priority":
        # These are candidates for the strict US-announcement comparator, not
        # pre-judged US employers or AI-primary events. The worker still needs
        # exact source text before it can fill either context field.
        params.update({
            "ai": "1", "stage": "announced", "country": "United States",
            "sort": "job_count", "dir": "desc",
        })
    return params


def rotating_page(total, batch, today=None):
    """Rotate bounded batches so inaccessible sources cannot starve the queue."""
    pages = max(1, (max(0, int(total)) + batch - 1) // batch)
    day = (today or date.today()).toordinal()
    return 1 + (day % pages)


def report_health(status, entries=0, detail=""):
    try:
        requests.post(
            f"{SITE}/wp-json/layoffs/v1/source-health",
            json={"source": "context_enrichment", "status": status, "entries": entries, "detail": detail},
            headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=30,
        ).raise_for_status()
    except Exception as exc:
        print(f"context health report failed: {exc}")


def fetch_text(url):
    if not url.startswith(("http://", "https://")):
        return ""
    response = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    response.raise_for_status()
    return clean_html(response.content[:2_000_000].decode(response.encoding or "utf-8", errors="replace"))


def usable_article_text(text):
    """An empty page, bot-block interstitial or bare stub is not evidence."""
    return bool(text) and len(text.strip()) >= MIN_ARTICLE_CHARS


def wayback_snapshot(url):
    """Newest archived snapshot URL for ``url`` ('' when none; never raises)."""
    try:
        response = requests.get(
            WAYBACK_AVAILABILITY_API,
            # Asking for "closest to today" resolves the newest snapshot.
            params={"url": url, "timestamp": date.today().strftime("%Y%m%d")},
            headers={"User-Agent": UA}, timeout=WAYBACK_TIMEOUT,
        )
        response.raise_for_status()
        closest = (response.json().get("archived_snapshots") or {}).get("closest") or {}
        snapshot = (closest.get("url") or "").strip()
        if closest.get("available") and snapshot.startswith(("http://", "https://")):
            return snapshot.replace("http://", "https://", 1)
    except Exception as exc:
        print(f"wayback availability lookup failed for {url}: {exc}")
    return ""


def wayback_raw_url(snapshot_url):
    """The ``id_`` variant serves the original page bytes without archive chrome."""
    return re.sub(r"(/web/\d{4,14})(/)", r"\1id_\2", snapshot_url, count=1)


def fetch_primary_or_snapshot(url):
    """Article text from the cited URL, else from its newest Wayback snapshot.

    Returns ``(text, snapshot_url)``; ``snapshot_url`` is '' when the original
    page supplied the text. The snapshot serves the SAME article, so quotes
    stay verifiable against the cited source. Fail-soft: any archive failure
    re-raises/returns the original outcome unchanged.
    """
    text, fetch_error = "", None
    try:
        text = fetch_text(url)
    except Exception as exc:
        fetch_error = exc
    if usable_article_text(text):
        return text, ""
    if url.startswith(("http://", "https://")) and os.environ.get("CONTEXT_WAYBACK", "1") not in ("0", "false", "no"):
        snapshot = wayback_snapshot(url)
        if snapshot:
            try:
                archived = fetch_text(wayback_raw_url(snapshot))
                if usable_article_text(archived):
                    print(f"recovered unreadable source via Wayback snapshot: {snapshot}")
                    return archived, snapshot
            except Exception as exc:
                print(f"wayback snapshot fetch failed for {url}: {exc}")
    if fetch_error is not None:
        raise fetch_error
    return text, ""


def annotate_evidence(result, note):
    """Append verification provenance to every evidence quote that was filled."""
    for key in ("employer_country_evidence", "announcement_evidence"):
        if result.get(key):
            result[key] = f"{result[key]} {note}"
    return result


def parse_iso_date(value):
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def alternate_source_evidence(row):
    """Quote the same event from a different trusted outlet, fail-soft.

    Runs only when the cited article and its snapshot are both unreadable.
    The GDELT BigQuery mirror is queried narrowly; only trusted-domain
    candidates from OTHER outlets are fetched (a bot-blocking publisher will
    block its sibling pages too), and the quote is extracted from — and
    validated against — the alternate article alone. On success the alternate
    article's own URL is recorded inside the evidence string. Any failure
    leaves the row unsupported_or_unreadable for a later rotation.
    """
    company = (row.get("company_name") or "").strip()
    anchor = parse_iso_date(row.get("announcement_date") or row.get("layoff_date") or "")
    if not (company and anchor and gdelt_bq.available()):
        return None, ""
    if os.environ.get("CONTEXT_ALT_SOURCE", "1") in ("0", "false", "no"):
        return None, ""
    try:
        start = datetime.combine(anchor - timedelta(days=ALT_WINDOW_DAYS), dt_time.min)
        end = datetime.combine(anchor + timedelta(days=ALT_WINDOW_DAYS), dt_time(23, 59, 59))
        articles = gdelt_bq.query_company_articles(company, start, end, discovery_terms())
    except Exception as exc:
        print(f"alternate-source lookup failed for id {row.get('id')}: {exc}")
        return None, ""
    original_url = (row.get("source_url") or "").strip()
    original_domain = _domain({"domain": original_url.split("/")[2] if original_url.count("/") >= 2 else ""})
    fetched = 0
    for article in articles:
        url = (article.get("url") or "").strip()
        domain = _domain(article)
        if not url or url == original_url or not _is_trusted(domain):
            continue
        if original_domain and (domain == original_domain or domain.endswith("." + original_domain)):
            continue
        if fetched >= ALT_FETCH_LIMIT:
            break
        fetched += 1
        try:
            text = fetch_text(url)
        except Exception as exc:
            print(f"alternate candidate unreadable {url}: {exc}")
            continue
        if not usable_article_text(text):
            continue
        result = extract_context_evidence(text)
        if result:
            annotate_evidence(result, f"[quote from alternate trusted source reporting the same event: {url}]")
            print(f"alternate-source evidence for id {row.get('id')}: {url}")
            return result, "alternate"
    return None, ""


def evidence_for_row(row):
    """Evidence for one row via cited article → Wayback snapshot → alternate.

    Returns ``(result, channel)`` where channel is ``primary``, ``wayback``,
    ``alternate`` or ''. The server-side gates are unchanged: only blank
    fields are ever filled and every value needs its exact supporting quote.
    """
    url = row.get("source_url") or ""
    text, snapshot = "", ""
    try:
        text, snapshot = fetch_primary_or_snapshot(url)
    except Exception as exc:
        print(f"unreadable id {row.get('id')}: {exc}")
    if usable_article_text(text):
        result = extract_context_evidence(text)
        if result and snapshot:
            annotate_evidence(result, f"[quote verified via the cited article's Wayback snapshot: {snapshot}]")
            return result, "wayback"
        return result, "primary" if result else ""
    return alternate_source_evidence(row)


def main():
    if not (SITE and KEY and os.environ.get("OPENROUTER_API_KEY")):
        print("WP_SITE_URL / WP_API_KEY / OPENROUTER_API_KEY required")
        return 1
    report_health("running", detail="Re-reading source evidence")
    try:
        params = query_params(BATCH, MODE)
        response = requests.get(
            f"{SITE}/wp-json/layoffs/v1/query",
            params=params,
            headers={"User-Agent": UA}, timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        page = rotating_page(payload.get("total", 0), BATCH)
        if page != 1:
            params["page"] = page
            response = requests.get(
                f"{SITE}/wp-json/layoffs/v1/query", params=params,
                headers={"User-Agent": UA}, timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        rows = payload.get("data", [])
        updates, unreadable, checked = [], 0, 0
        recovered = {"wayback": 0, "alternate": 0}
        started_at = time.monotonic()
        for row in rows:
            # No fact is changed by stopping between rows: the daily rotation
            # simply resumes the queue inside the Actions time ceiling.
            if time.monotonic() - started_at >= DEADLINE_SECONDS:
                print(f"Reached CONTEXT_DEADLINE_SECONDS={DEADLINE_SECONDS}; stopping safely after {checked} row(s)")
                break
            checked += 1
            try:
                result, channel = evidence_for_row(row)
                if result:
                    updates.append({"id": row["id"], **result})
                    if channel in recovered:
                        recovered[channel] += 1
                else:
                    unreadable += 1
            except Exception as exc:
                unreadable += 1
                print(f"unreadable id {row.get('id')}: {exc}")
        updated = 0
        if updates:
            posted = requests.post(
                f"{SITE}/wp-json/layoffs/v1/enrich-context", json={"items": updates},
                headers={"X-Layoff-API-Key": KEY, "User-Agent": UA}, timeout=60,
            )
            posted.raise_for_status()
            result = posted.json()
            updated = len(result.get("updated", []))
            print(f"enriched={updated} rejected={len(result.get('rejected', []))}")
        detail = (
            f"mode={MODE} page={payload.get('page', 1)} checked={checked} "
            f"unsupported_or_unreadable={unreadable} "
            f"wayback_verified={recovered['wayback']} alternate_source={recovered['alternate']}"
        )
        report_health("ok", updated, detail)
        print(f"{detail} queued={len(updates)}")
        return 0
    except Exception as exc:
        report_health("degraded", detail=str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
