"""
POSTs extracted layoff data to WordPress REST API.
"""

try:
    import blog_read_cache as blog_reads
except ModuleNotFoundError:
    from railway import blog_read_cache as blog_reads
import os

import requests


def _server_message(resp):
    """The server's own one-line reason for a 409, or "" if it sent none.

    WP_Error bodies are {"code", "message", "data": {...}}; the fuzzy branch
    also puts matched_row / matched_count / matched_date in `data`. Only the
    message is printed, and it is capped so a surprising body cannot flood
    the run log.
    """
    try:
        body = resp.json()
    except Exception:
        return ""
    if not isinstance(body, dict):
        return ""
    msg = body.get("message")
    return str(msg)[:200] if msg else ""


_HELD_READY = {}


def _held_queue_ready(wp_url, api_key):
    """True once the keyed /held route answers 200 (cached per site per process)."""
    if wp_url not in _HELD_READY:
        try:
            r = blog_reads.get(f"{wp_url}/wp-json/layoffs/v1/held", timeout=30, headers={
                "X-Layoff-API-Key": api_key,
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}, getter=requests.get)
            _HELD_READY[wp_url] = r.status_code == 200
        except Exception:  # noqa: BLE001 - unknown is not ready
            return False
    return _HELD_READY[wp_url]


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
        "title": (f"{company}, ~{job_count:,} jobs (estimate), {layoff_date}"
                  if entry.get("job_count_is_estimate")
                  else f"{company}, {job_count:,} jobs, {layoff_date}"),
        "status": "publish",
        "meta": {
            "company_name": company,
            "ticker": entry.get("ticker"),
            "job_count": job_count,
            "job_count_max": entry.get("job_count_max") or job_count,
            "layoff_date": entry.get("layoff_date"),
            "announcement_date": entry.get("announcement_date"),
            "industry": entry.get("industry"),
            "country": entry.get("country"),
            "employer_country": entry.get("employer_country"),
            "employer_country_evidence": entry.get("employer_country_evidence"),
            "announcement_evidence": entry.get("announcement_evidence"),
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
            # Owner ruling 2026-11-05: a pct x 10-K headcount is an ESTIMATE,
            # labelled with its formula and source (headcount_estimate.py).
            "job_count_is_estimate": bool(entry.get("job_count_is_estimate")),
            "headcount_estimate": entry.get("headcount_estimate"),
            # Set by a guard that cannot decide (negation_guard): WordPress
            # stores the row as a HELD post, outside every public surface,
            # until review-held.yml releases or trashes it.
            "held_reason": entry.get("held_reason"),
        },
    }

    # FAIL CLOSED ON A HOLD. A plugin older than the held-rows store ignores
    # held_reason and would PUBLISH the row (the Railway worker and the
    # WordPress plugin deploy separately). So a held row is sent only after the
    # site has proved it has the queue; otherwise it is not posted at all and,
    # never stored, is re-read on the next run.
    if entry.get("held_reason") and not _held_queue_ready(wp_url, api_key):
        print(f"~ NOT POSTED: {company} must be held, and the site has no held queue yet")
        return "failed"

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
            try:
                held = bool(resp.json().get("held"))
            except Exception:  # noqa: BLE001 - an unreadable body is still a 201
                held = False
            if held:
                print(f"~ HELD for review (not published): {company} - {entry.get('held_reason')}")
                return "held"
            if entry.get("held_reason"):
                print(f"::error::{company}: sent as HELD but the site stored it as published")
                return "failed"
            print(f"+ Posted: {company}")
            return "posted"
        if resp.status_code == 409:
            # Server-side dedup caught it (race with the pre-check, or the
            # pre-check failed open) — not an error worth alerting on. Print
            # the server's reason: since 2.20.161 a fuzzy 409 names the row
            # that absorbed the report (id, count, date), which is the only
            # way to tell a repeat of a known event from a distinct one that
            # was swallowed (Uber 3,300 into a 500-job row, 2026-09-02).
            reason = _server_message(resp)
            print(f"= Skipped duplicate at server: {company}"
                  + (f" ({job_count}) - {reason}" if reason else ""))
            return "duplicate"

        print(f"x Failed: {company} — {resp.status_code} — {resp.text[:300]}")
        return "failed"

    except Exception as e:
        print(f"WP post error for {company}: {e}")
        return "failed"
