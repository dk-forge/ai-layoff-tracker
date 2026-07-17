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
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "45"))

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

AI_CAUSATION = {
    "primary_cause",
    "contributing_cause",
    "selection_or_operations",
    "context_only",
    "explicitly_denied",
    "unknown",
}

SYSTEM_PROMPT = """You are a data extraction specialist for a verified AI layoff tracker.

Your job is to extract structured layoff data from news articles and SEC filings.

CRITICAL RULES:
1. Only extract data that is EXPLICITLY STATED in the source text. Never infer.
2. Classify AI causation carefully. `primary_cause` means the company/source says AI, automation, machine learning or robots caused the reduction. `contributing_cause` means it is one stated cause. `selection_or_operations` means AI was used to select, monitor or manage workers; this is NOT a cause. `context_only` means AI investment, strategy or a passing mention is not stated as a cause. `explicitly_denied` means the source says the cuts were not because of AI. Use `unknown` if the source is unclear.
3. For ai_explicit: true ONLY for `primary_cause` or `contributing_cause`, and only with an exact supporting phrase. Never infer it from a company's AI investment, a future automation projection, or AI use during selection.
4. For ai_language: copy the EXACT supporting phrase from the source. If none, return null.
5. For job_count: use the exact number stated. If a range is given, use the lower bound. Never turn a percentage, dollar figure, future work-equivalence, or projected automation number into a layoff count.
6. For reason_tags: only assign tags that are supported by explicit language in the source.
7. If you cannot determine a required field with confidence, return null for that field.
8. Return ONLY valid JSON. No preamble. No explanation. No markdown.

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
  "announcement_date": "YYYY-MM-DD when the source states the public announcement date, otherwise null",
  "announcement_evidence": "exact source phrase containing that date, or null",
  "industry": "one of: Technology, Media & Entertainment, Finance & Insurance, Healthcare & Pharma, Retail & E-commerce, Manufacturing, Automotive, Aerospace & Defense, Airlines & Travel, Energy, Telecom, Education, Logistics & Transport, Food & Hospitality, Real Estate & Construction, Consumer Goods, Professional Services, Agriculture, Government & Nonprofit — or null if unclear",
  "country": "the single country where the cuts happen (or where most of them happen if the source gives a breakdown). If the cuts span several countries with no clear majority, use exactly 'Multiple countries'. Use 'United States' and 'United Kingdom' (never US/USA/UK). Null if not stated.",
  "employer_country": "country where the employer is headquartered or domiciled, only if explicitly stated in this source. Use canonical names; null if unknown. This is NOT the job-location country.",
  "employer_country_evidence": "exact source phrase supporting employer domicile, or null",
  "state": "2-letter US state abbreviation (e.g. CA, TX, NY) if the source states a US location for the cuts, otherwise null",
  "roles": "the specific roles, teams, or departments affected, exactly as stated in the source (e.g. 'customer service and engineering'), or null if not stated",
  "excerpt": "2-3 sentence excerpt from the source that confirms the layoff. Exact text from source.",
  "reason_tags": ["array", "of", "tags"],
  "ai_causation": "primary_cause|contributing_cause|selection_or_operations|context_only|explicitly_denied|unknown",
  "ai_explicit": true or false,
  "ai_language": "exact phrase from source or null",
  "announced": "true if this is an ANNOUNCEMENT of planned future cuts that have not yet begun (e.g. 'will cut 5,000 over the next year', 'plans to reduce'); false if the cuts are already executed, underway, or legally filed",
  "confidence": "integer 0-100 for the event identity, count and causation together",
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
            # A stalled model call must not block a scheduled ingestion or
            # history-recovery job for many minutes. Per-entry callers handle
            # a timeout as a recorded failed candidate and continue.
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_retries=1,
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


def _quote_is_supported(quote, raw_text):
    """Reject invented evidence quotes before they can affect public totals."""
    if not isinstance(quote, str) or not isinstance(raw_text, str):
        return False
    q = re.sub(r"\s+", " ", quote).strip().lower()
    source = re.sub(r"\s+", " ", raw_text).strip().lower()
    return len(q) >= 12 and q in source


def classify_ai_evidence(raw_text):
    """Reassess only AI causation for an already-recorded event.

    Historical rows keep their source, count and date. This deliberately
    narrow call avoids an LLM "correcting" unrelated fields while allowing a
    fresh read of the linked document to replace an old keyword-based AI flag.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return None
    prompt = """Classify AI causation in this layoff source. Return STRICT JSON only:
{"ai_causation":"primary_cause|contributing_cause|selection_or_operations|context_only|explicitly_denied|unknown","ai_language":"exact source phrase or null","confidence":0-100}

AI is primary/contributing only if this text explicitly says AI, automation,
machine learning or robots caused the cuts. A general AI strategy, investment,
or use of AI in operations is not causal. Never infer. The phrase must be an
exact quote from the supplied text.

TEXT:\n""" + raw_text
    try:
        response = _get_client().chat.completions.create(
            model=MODEL, max_tokens=250,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"AI evidence reassessment failed: {exc}")
        return None
    if not isinstance(result, dict):
        return None
    cause = result.get("ai_causation")
    cause = cause if cause in AI_CAUSATION else "unknown"
    quote = result.get("ai_language")
    if cause in {"primary_cause", "contributing_cause"} and not _quote_is_supported(quote, raw_text):
        cause, quote = "unknown", None
    try:
        confidence = max(0, min(100, int(result.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0
    return {"ai_causation": cause, "ai_language": quote.strip() if isinstance(quote, str) else "", "confidence": confidence}


def extract_context_evidence(raw_text):
    """Extract only explicit domicile and public announcement-date evidence.

    This narrow reassessment cannot alter job counts, layoff dates, stages or
    causal labels. Quotes are checked locally before the result is sent to the
    keyed enrichment endpoint.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return None
    prompt = """Read this layoff source and return STRICT JSON only:
{"employer_country":"canonical country or null","employer_country_evidence":"exact source phrase or null","announcement_date":"YYYY-MM-DD or null","announcement_evidence":"exact source phrase containing the announcement date or null"}

Rules: employer_country is only the employer's HQ/domicile when the text says
so; never infer it from job location or brand familiarity. announcement_date is
the public announcement date only when an exact date is stated in the text;
never substitute an effective layoff date or page-access date. Return null for
any unsupported field. Evidence phrases must be copied exactly from TEXT.

TEXT:\n""" + raw_text
    try:
        response = _get_client().chat.completions.create(
            model=MODEL, max_tokens=350,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"Context evidence reassessment failed: {exc}")
        return None
    if not isinstance(result, dict):
        return None
    out = {}
    country = result.get("employer_country")
    country_quote = result.get("employer_country_evidence")
    if isinstance(country, str) and country.strip() and _quote_is_supported(country_quote, raw_text):
        out["employer_country"] = country.strip()
        out["employer_country_evidence"] = country_quote.strip()
    announcement_date = _normalize_date(result.get("announcement_date"))
    announcement_quote = result.get("announcement_evidence")
    if announcement_date and _quote_is_supported(announcement_quote, raw_text):
        out["announcement_date"] = announcement_date
        out["announcement_evidence"] = announcement_quote.strip()
    return out or None


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
    # Announcement date is deliberately separate from the effective layoff
    # date. It enables valid monthly announcement comparisons and is retained
    # only when the source/model supplies a real date (never copied from the
    # effective date as a convenience).
    announcement_evidence = extracted.get("announcement_evidence")
    extracted["announcement_date"] = (
        _normalize_date(extracted.get("announcement_date"))
        if _quote_is_supported(announcement_evidence, raw_text) else None
    )
    extracted["announcement_evidence"] = announcement_evidence.strip() if extracted["announcement_date"] else None
    domicile_evidence = extracted.get("employer_country_evidence")
    if not _quote_is_supported(domicile_evidence, raw_text):
        extracted["employer_country"] = None
        extracted["employer_country_evidence"] = None
    else:
        extracted["employer_country_evidence"] = domicile_evidence.strip()
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

    causation = extracted.get("ai_causation")
    causation = causation if causation in AI_CAUSATION else "unknown"
    quote = extracted.get("ai_language")
    # A model-provided classification is only admissible if its claimed quote
    # actually appears in the supplied source passage.  This stops context-only
    # mentions (and fabricated quotes) inflating the AI headline metric.
    quote_supported = _quote_is_supported(quote, raw_text)
    if causation in {"primary_cause", "contributing_cause"} and not quote_supported:
        causation = "unknown"
    extracted["ai_causation"] = causation
    extracted["ai_explicit"] = causation in {"primary_cause", "contributing_cause"}
    # Announcement-stage vs executed/filed: SEC filings and WARN notices are by
    # definition filed events, so only news can carry the announced flag.
    extracted["announced"] = (
        bool(extracted.get("announced"))
        and raw_entry.get("source_type") == "news"
    )
    if not quote_supported:
        extracted["ai_language"] = None
    else:
        extracted["ai_language"] = quote.strip()

    try:
        extracted["confidence"] = max(0, min(100, int(extracted.get("confidence") or 0)))
    except (TypeError, ValueError):
        extracted["confidence"] = 0
    # A source-backed event with a precise count should never enter as an
    # unlabelled high-confidence claim.  This score controls future automated
    # review/reporting; it does not replace the visible source evidence.
    if extracted["confidence"] == 0:
        extracted["confidence"] = 85 if raw_entry.get("verification_level") in {"gold", "silver"} else 65

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
