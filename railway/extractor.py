"""
LLM extraction + classification.
Uses DeepSeek-V3 (deepseek/deepseek-chat) via OpenRouter.

OpenRouter serves the OpenAI-compatible chat-completions API, so this module
uses the openai SDK with a base_url override — the anthropic SDK cannot talk
to OpenRouter (different wire format/endpoint).
"""
import hashlib
import json
import os
import re

import openai

# Swap models without a code change: set OPENROUTER_MODEL in the environment
# (e.g. "google/gemini-2.0-flash-001" for an even cheaper option). DeepSeek-V3
# is the default — near the price floor while staying strong at extraction.
MODEL = os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

ALLOWED_REASON_TAGS = {
    "ai_automation",
    "revenue_decline",
    "restructuring",
    "merger_acquisition",
    "offshoring",
    "product_discontinuation",
    "cost_reduction",
    "macroeconomic",
    "possible_ai",
}

SYSTEM_PROMPT = """You are a data extraction specialist for a verified AI layoff tracker.

Your job is to extract structured layoff data from news articles and SEC filings.

CRITICAL RULES:
1. Only extract data that is EXPLICITLY STATED in the source text. Never infer.
2. For ai_explicit: set true ONLY if the source text explicitly names AI, artificial intelligence, machine learning, automation, or robots as a reason for the layoffs. Not implied. Explicitly named.
3. For ai_language: copy the EXACT phrase from the source that mentions AI/automation. If none, return null.
4. For job_count: use the exact number stated. If a range is given, use the lower bound.
5. For reason_tags: only assign tags that are supported by explicit language in the source.
6. If you cannot determine a required field with confidence, return null for that field.
7. Return ONLY valid JSON. No preamble. No explanation. No markdown.

Reason tag definitions (only assign if explicitly supported):
- ai_automation: source explicitly names AI, automation, robots, machine learning as reason
- revenue_decline: source cites revenue, financial performance, earnings
- restructuring: source uses reorganization, realignment, restructuring language
- merger_acquisition: source cites M&A activity
- offshoring: source mentions moving jobs to another country
- product_discontinuation: source mentions shutting down a product or division
- cost_reduction: generic efficiency or cost-cutting language with no specific reason
- macroeconomic: source cites economic conditions, market environment
- possible_ai: source uses productivity, efficiency, or automation language that implies but does not explicitly name AI

Response format:
{
  "company_name": "string or null",
  "ticker": "string or null",
  "job_count": "integer or null",
  "layoff_date": "YYYY-MM-DD or null",
  "industry": "one of: Technology, Media & Entertainment, Finance & Insurance, Healthcare & Pharma, Retail & E-commerce, Manufacturing, Automotive, Aerospace & Defense, Airlines & Travel, Energy, Telecom, Education, Logistics & Transport, Food & Hospitality, Real Estate & Construction, Consumer Goods, Professional Services, Agriculture, Government & Nonprofit — or null if unclear",
  "country": "the single country where the cuts happen (or where most of them happen if the source gives a breakdown). If the cuts span several countries with no clear majority, use exactly 'Multiple countries'. Use 'United States' and 'United Kingdom' (never US/USA/UK). Null if not stated.",
  "state": "2-letter US state abbreviation (e.g. CA, TX, NY) if the source states a US location for the cuts, otherwise null",
  "roles": "the specific roles, teams, or departments affected, exactly as stated in the source (e.g. 'customer service and engineering'), or null if not stated",
  "excerpt": "2-3 sentence excerpt from the source that confirms the layoff. Exact text from source.",
  "reason_tags": ["array", "of", "tags"],
  "ai_explicit": true or false,
  "ai_language": "exact phrase from source or null",
  "announced": "true if this is an ANNOUNCEMENT of planned future cuts that have not yet begun (e.g. 'will cut 5,000 over the next year', 'plans to reduce'); false if the cuts are already executed, underway, or legally filed",
  "is_layoff_event": true or false
}"""

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY environment variable is not set")
        _client = openai.OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                # optional OpenRouter attribution headers
                "HTTP-Referer": "https://asktherecruiter.com",
                "X-Title": "AI Layoff Tracker",
            },
        )
    return _client


def _parse_json_response(text):
    """Parse the model's response, tolerating markdown fences or stray preamble."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fall back to the outermost {...} block
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def _coerce_job_count(value):
    """The model occasionally returns '9,000' or '9000' as a string."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        digits = value.replace(",", "").strip()
        if digits.isdigit() and int(digits) > 0:
            return int(digits)
    return None


def _normalize_date(value):
    if isinstance(value, str):
        candidate = value.strip()[:10]
        if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
            return candidate
    return None


_US_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
_US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC", "washington dc": "DC", "washington d.c.": "DC",
}


def _normalize_state(value):
    """Return a 2-letter US state code, or None. Accepts codes or full names."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    up = re.sub(r"[^A-Z]", "", v.upper())
    if up in _US_STATE_ABBR:
        return up
    key = re.sub(r"\s+", " ", v.lower().replace(".", "")).strip()
    return _US_STATE_NAMES.get(key)


def extract_layoff_data(raw_entry):
    """Send raw source text to DeepSeek-V3, get structured layoff data back.

    Returns a dict ready for wp_poster, or None if the entry should be skipped.
    """
    raw_text = (raw_entry.get("raw_text") or "")[:2000]
    if not raw_text.strip():
        return None

    prompt = f"""Extract layoff data from this source:

SOURCE TYPE: {raw_entry.get('source_type')}
SOURCE NAME: {raw_entry.get('source_name')}
COMPANY (if known): {raw_entry.get('company_name') or 'Unknown'}
TICKER (if known): {raw_entry.get('ticker') or 'Unknown'}
DATE: {raw_entry.get('filing_date') or 'Unknown'}

TEXT:
{raw_text}"""

    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as e:
        # Per error-handling requirements: log the raw text that failed, skip entry
        print(f"OpenRouter/DeepSeek API error: {e} — source: {raw_entry.get('source_url')} "
              f"— text head: {raw_text[:200]!r}")
        return None

    choice = response.choices[0] if response.choices else None
    response_text = ""
    if choice and choice.message and choice.message.content:
        response_text = choice.message.content.strip()
    if not response_text:
        print(f"Extraction error: empty response — source: {raw_entry.get('source_url')}")
        return None

    try:
        extracted = _parse_json_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"JSON parse error: {e} — response head: {response_text[:300]!r}")
        return None

    if not isinstance(extracted, dict):
        print(f"Extraction error: non-object JSON — response head: {response_text[:300]!r}")
        return None

    # Skip if the model determined this isn't a layoff event
    if not extracted.get("is_layoff_event"):
        return None

    # Skip if no usable job count
    job_count = _coerce_job_count(extracted.get("job_count"))
    if not job_count:
        return None
    extracted["job_count"] = job_count

    company_name = extracted.get("company_name")
    extracted["company_name"] = (
        company_name.strip() if isinstance(company_name, str) and company_name.strip()
        else None
    )
    if not extracted["company_name"]:
        # No company means the dedup hash and every display surface degrade
        print(f"Extraction skipped: no company_name — source: {raw_entry.get('source_url')}")
        return None

    extracted["layoff_date"] = (
        _normalize_date(extracted.get("layoff_date"))
        or _normalize_date(raw_entry.get("filing_date"))
    )
    # Coverage floor: filings/articles often reference older restructurings;
    # a date before 2015 means the model grabbed a historical date from the
    # text. Fall back to the source's own date, else leave undated.
    if extracted["layoff_date"] and extracted["layoff_date"] < "2015-01-01":
        fallback = _normalize_date(raw_entry.get("filing_date"))
        extracted["layoff_date"] = fallback if (fallback and fallback >= "2015-01-01") else None

    # Plausibility cap: no single verified company layoff event reaches this
    # size (largest in US history ~60K). Bigger numbers are industry-wide
    # estimates or cumulative headcount stories misread as one event.
    if job_count and job_count > 60000:
        print(f"Extraction skipped: implausible single-event count {job_count} "
              f"({extracted['company_name']}) — {raw_entry.get('source_url')}")
        return None

    tags = extracted.get("reason_tags")
    if not isinstance(tags, list):
        tags = []
    extracted["reason_tags"] = [t for t in tags if t in ALLOWED_REASON_TAGS]

    extracted["ai_explicit"] = bool(extracted.get("ai_explicit"))
    # Announcement-stage vs executed/filed: SEC filings and WARN notices are by
    # definition filed events, so only news can carry the announced flag.
    extracted["announced"] = (
        bool(extracted.get("announced"))
        and raw_entry.get("source_type") == "news"
    )
    if not isinstance(extracted.get("ai_language"), str) or not extracted["ai_language"].strip():
        extracted["ai_language"] = None

    if not isinstance(extracted.get("roles"), str) or not extracted["roles"].strip():
        extracted["roles"] = None

    extracted["state"] = _normalize_state(extracted.get("state"))
    # A stated US state implies the country, even when the source doesn't say so.
    if extracted["state"] and not (isinstance(extracted.get("country"), str) and extracted["country"].strip()):
        extracted["country"] = "United States"

    # Add source metadata
    extracted["source_url"] = raw_entry.get("source_url")
    extracted["source_type"] = raw_entry.get("source_type")
    extracted["source_name"] = raw_entry.get("source_name")
    extracted["verification_level"] = raw_entry.get("verification_level")

    # Dedup hash — inputs normalized so casing/whitespace differences between
    # sources reporting the same event still collide (that's the point)
    hash_input = (
        f"{extracted['company_name'].lower().strip()}"
        f"{extracted.get('layoff_date') or ''}"
        f"{extracted['job_count']}"
    )
    extracted["dedup_hash"] = hashlib.md5(hash_input.encode("utf-8")).hexdigest()

    return extracted
