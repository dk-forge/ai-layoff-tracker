"""Read-only Companies House identity lookup.

This adapter is deliberately *not* a layoff collector.  It accepts only an
already-known Companies House number and returns a source-linked registered
identity candidate for a later human/evidence review.  It never searches by
company name, creates a layoff event, or writes ``employer_country``: a
registered office is not proof of an employer's headquarters or of the
location of affected jobs.

The official API documents authenticated GET requests and a 600 requests / 5
minutes default limit.  Callers must keep this connector bounded and report
their own source-health result when it is admitted to a workflow.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests


API_BASE = "https://api.company-information.service.gov.uk"
PUBLIC_PROFILE_BASE = "https://find-and-update.company-information.service.gov.uk/company"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"


def _company_number(value: str) -> str:
    """Return a conservative Companies House number or reject the input.

    Numbers may be digits or standard two-letter jurisdiction prefixes plus
    digits.  Rejecting arbitrary text ensures this adapter cannot silently
    become a fuzzy identity-matching system.
    """
    number = str(value or "").strip().upper()
    if not re.fullmatch(r"(?:[A-Z]{2})?\d{6,8}", number):
        raise ValueError("company_number must be a Companies House number")
    return number


def public_profile_url(company_number: str) -> str:
    """Return the public, source-linkable profile URL for an exact number."""
    return f"{PUBLIC_PROFILE_BASE}/{_company_number(company_number).lower()}"


def fetch_registered_identity(company_number: str, api_key: str | None = None, *, session=requests) -> dict:
    """Fetch one exact official company profile without publishing or mutating data.

    The return value deliberately calls the address country
    ``registered_office_country``.  A future review process must not reinterpret
    it as employer domicile/HQ without separate supporting evidence.
    """
    number = _company_number(company_number)
    key = api_key or os.environ.get("COMPANIES_HOUSE_API_KEY_UK", "")
    if not key:
        raise RuntimeError("COMPANIES_HOUSE_API_KEY_UK is required")
    response = session.get(
        f"{API_BASE}/company/{number}",
        auth=(key, ""),
        headers={"User-Agent": UA, "Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    profile = response.json()
    if not isinstance(profile, dict):
        raise RuntimeError("Companies House returned a non-object profile")
    address = profile.get("registered_office_address")
    address = address if isinstance(address, dict) else {}
    return {
        "company_number": number,
        "company_name": str(profile.get("company_name") or ""),
        "company_status": str(profile.get("company_status") or ""),
        "jurisdiction": str(profile.get("jurisdiction") or ""),
        "registered_office_country": str(address.get("country") or ""),
        "source_name": "Companies House company profile",
        "source_url": public_profile_url(number),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Identity candidate only; not a layoff source and not evidence of employer domicile or affected-job location.",
    }
