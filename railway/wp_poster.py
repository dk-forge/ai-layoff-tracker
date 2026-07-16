"""
POSTs extracted layoff data to WordPress REST API.
"""
import os

import requests


def post_to_wordpress(entry):
    """POST a layoff entry to the WordPress custom post type.

    Returns "posted", "duplicate", or "failed" — duplicates are an expected
    outcome (the pre-check fails open), not an error.
    """
    wp_url = (os.environ.get("WP_SITE_URL") or "").rstrip("/")
    api_key = os.environ.get("WP_API_KEY")
    if not wp_url or not api_key:
        print("WP post error: WP_SITE_URL or WP_API_KEY not set")
        return "failed"

    company = entry.get("company_name") or "Unknown"
    job_count = entry.get("job_count") or 0
    layoff_date = entry.get("layoff_date") or "date unknown"

    payload = {
        "title": f"{company}, {job_count:,} jobs, {layoff_date}",
        "status": "publish",
        "meta": {
            "company_name": company,
            "ticker": entry.get("ticker"),
            "job_count": job_count,
            "layoff_date": entry.get("layoff_date"),
            "industry": entry.get("industry"),
            "country": entry.get("country"),
            "employer_country": entry.get("employer_country"),
            "state": entry.get("state"),
            "roles": entry.get("roles"),
            "source_url": entry.get("source_url"),
            "source_type": entry.get("source_type"),
            "source_name": entry.get("source_name"),
            "verification_level": entry.get("verification_level"),
            "excerpt": entry.get("excerpt"),
            "reason_tags": entry.get("reason_tags", []),
            "ai_explicit": entry.get("ai_explicit", False),
            "ai_causation": entry.get("ai_causation", "unknown"),
            "confidence": entry.get("confidence", 0),
            "review_status": entry.get("review_status", "provisional"),
            "announced": entry.get("announced", False),
            "ai_language": entry.get("ai_language"),
            "dedup_hash": entry.get("dedup_hash"),
        },
    }

    try:
        resp = requests.post(
            f"{wp_url}/wp-json/layoffs/v1/add",
            json=payload,
            headers={
                "X-Layoff-API-Key": api_key,
                "Content-Type": "application/json",
                # ModSecurity on the host blocks the default python-requests UA
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)",
            },
            timeout=30,
        )

        if resp.status_code == 201:
            print(f"+ Posted: {company}")
            return "posted"
        if resp.status_code == 409:
            # Server-side dedup caught it (race with the pre-check, or the
            # pre-check failed open) — not an error worth alerting on
            print(f"= Skipped duplicate at server: {company}")
            return "duplicate"

        print(f"x Failed: {company} — {resp.status_code} — {resp.text[:300]}")
        return "failed"

    except Exception as e:
        print(f"WP post error for {company}: {e}")
        return "failed"
