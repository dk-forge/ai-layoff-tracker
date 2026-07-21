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
    "closure",
}

AI_CAUSATION = {
    "primary_cause",
    "contributing_cause",
    "selection_or_operations",
    "context_only",
    "explicitly_denied",
    "unknown",
}

# Fixed role-category vocabulary, shared verbatim with the WordPress side
# (alt_role_categories). The server re-validates, but rejecting unknown slugs
# here keeps a drifted model from burning a batch on rejected items.
ROLE_CATEGORIES = {
    "engineering",
    "product_design",
    "customer_support",
    "sales_marketing",
    "hr_recruiting",
    "operations_warehouse",
    "content_trust_safety",
    "finance_admin",
    "manufacturing",
    "retail_staff",
}

# The closed industry vocabulary, mirrored verbatim from the WordPress side
# (alt_industry_rules() keys / alt_industry_vocabulary()). The /industry-backfill
# endpoint re-validates against alt_industry_vocabulary() and rejects anything
# outside it, but constraining the model here keeps a drifted classifier from
# burning a batch on server-rejected labels. Order matches the PHP map so the
# parity test (tests/test_industry_backfill.py) can catch any drift in either
# direction. Kept as a tuple: the prompt lists them and the worker validates
# membership.
INDUSTRY_VOCABULARY = (
    "Healthcare & Pharma",
    "Finance & Insurance",
    "Education",
    "Aerospace & Defense",
    "Airlines & Travel",
    "Automotive",
    "Technology",
    "Telecom",
    "Media & Entertainment",
    "Retail & E-commerce",
    "Food & Hospitality",
    "Energy",
    "Logistics & Transport",
    "Real Estate & Construction",
    "Manufacturing",
    "Consumer Goods",
    "Professional Services",
    "Agriculture",
    "Government & Nonprofit",
)

SYSTEM_PROMPT = """You are a data extraction specialist for a verified AI layoff tracker.

Your job is to extract structured layoff data from news articles and SEC filings.

CRITICAL RULES:
1. Only extract data that is EXPLICITLY STATED in the source text. Never infer.
2. Classify AI causation carefully. `primary_cause` means the company/source says AI, automation, machine learning or robots caused the reduction. `contributing_cause` means it is one stated cause. `selection_or_operations` means AI was used to select, monitor or manage workers; this is NOT a cause. `context_only` means AI investment, strategy or a passing mention is not stated as a cause. `explicitly_denied` means the source says the cuts were not because of AI. Use `unknown` if the source is unclear.
3. For ai_explicit: true ONLY for `primary_cause` or `contributing_cause`, and only with an exact supporting phrase. Never infer it from a company's AI investment, a future automation projection, or AI use during selection.
4. For ai_language: copy the EXACT supporting phrase from the source. If none, return null.
5. For job_count: the total for THIS newly announced event only. TIMELINE TRAP: articles cite older layoffs for context ("after cutting 10,000 last year, X announced 500 new cuts") — NEVER use a historical/contextual number; use the number for the new announcement (500 here). SUBSET TRAP: if a division figure and a companywide total for the SAME new announcement both appear ("500 in cloud, part of 3,000 overall"), use the companywide total (3,000). If a range is given, use the lower bound. Never turn a percentage, dollar figure, future work-equivalence, or projected automation number into a layoff count.
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
  "job_count_max": "integer or null — the UPPER bound if the source gives a range ('up to 6,000'->6000; '400 to 500'->500); otherwise equal to job_count",
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


def _percent_only_mention(job_count, raw_text):
    """True when a small count appears in the text ONLY as "N%" / "N percent".

    That is a mis-parse of a percentage, not a headcount (Intuit: "17% of its
    staff" was stored as 17 jobs). Rejecting is honest — a corrected count
    must come from an explicit figure, never be derived here.
    """
    if not raw_text or not job_count or job_count > 100:
        return False
    as_percent = re.search(rf"\b{job_count}\s*(%|percent\b)", raw_text, re.I)
    as_count = re.search(rf"\b{job_count}\b(?!\s*(%|percent))", raw_text, re.I)
    return bool(as_percent and not as_count)


def _count_in_text(job_count, raw_text):
    """True when the extracted count literally appears in the source text.

    The AI quote already requires a verbatim receipt; the headcount itself did
    not, so a model misread (e.g. deriving 4,000 from "10% of 40,000 staff")
    could publish with a receipt attached — the worst failure class, because it
    looks audited. Accepts common written variants: 12000 / 12,000 / 12 000 /
    12.000 (EU) / 12k. Counts the model derived rather than read fail here and
    are rejected loudly (never silently), matching the "never derive" rule.
    """
    if not raw_text or not job_count:
        return False
    n = int(job_count)
    grouped = f"{n:,}"
    variants = {str(n), grouped, grouped.replace(",", " "), grouped.replace(",", "."),
                grouped.replace(",", " ")}
    if n % 1000 == 0 and n >= 1000:
        variants.update({f"{n // 1000}k", f"{n // 1000}K"})
    return any(
        re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d])", raw_text)
        for v in variants
    )


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


def classify_reason_tags(raw_text):
    """Assign fixed-vocabulary reason tags from an event's STORED excerpt only.

    This narrow reassessment cannot alter counts, dates, stages, sources or AI
    labels — it returns tags for the corrections endpoint to write. An event
    whose stored evidence names no reason honestly stays untagged: returning
    {"reason_tags": []} is a definitive skip, while None is a model failure the
    caller may retry on a later run.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return None
    prompt = """Assign layoff reason tags for the text below. Return STRICT JSON only:
{"reason_tags":["zero or more of: ai_automation, possible_ai, revenue_decline, restructuring, merger_acquisition, offshoring, product_discontinuation, cost_reduction, macroeconomic"],"ai_evidence":"exact quote where the EMPLOYER states AI/automation as a reason, or null"}

Rules:
- Use ONLY the tag definitions from your instructions; a tag needs explicit
  supporting language in this text. Multiple tags are allowed.
- If the text states no reason for the cuts, return {"reason_tags":[],"ai_evidence":null}.
- ai_automation ONLY when the employer itself states AI/automation/robots/
  machine learning as a reason, with the exact quote in ai_evidence.
- possible_ai when the text ties the cuts to AI without the employer stating
  it (press framing, productivity/automation implications).
- Never infer a reason from the company's industry, reputation, or anything
  outside this text.

TEXT:\n""" + raw_text
    try:
        response = _get_client().chat.completions.create(
            model=MODEL, max_tokens=200,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"Reason-tag classification failed: {exc}")
        return None
    return _validate_reason_result(result, raw_text)


def _validate_reason_result(result, raw_text):
    """Vocabulary + quote gates on a reason-tag reply (pure, unit-tested)."""
    if not isinstance(result, dict) or not isinstance(result.get("reason_tags"), list):
        return None
    tags = list(dict.fromkeys(t for t in result["reason_tags"] if t in ALLOWED_REASON_TAGS))
    # The strict tag needs the employer's own words in the supplied evidence;
    # an unsupported claim is dropped rather than downgraded — possible_ai is
    # the model's call to make, not a consolation default.
    if "ai_automation" in tags and not _quote_is_supported(result.get("ai_evidence"), raw_text):
        tags.remove("ai_automation")
    return {"reason_tags": tags}


def _validate_industry_result(result):
    """Map a model reply to exactly one canonical industry label, or "".

    Pure and unit-tested. The model is asked to answer with a single label from
    INDUSTRY_VOCABULARY or "unknown"; anything not an exact vocabulary member
    (including "unknown", empty, or a hallucinated label) collapses to "" — a
    definitive "the evidence doesn't place this company", not a guess. Returns
    None only for a malformed (non-dict) reply so the caller can retry it.
    """
    if not isinstance(result, dict):
        return None
    label = result.get("industry")
    label = label.strip() if isinstance(label, str) else ""
    return {"industry": label if label in INDUSTRY_VOCABULARY else ""}


def classify_industry(company, raw_text):
    """Classify one blank-industry row into the closed industry vocabulary.

    Uses ONLY the row's own company name + stored excerpt — no external fetch.
    Never invents a label: an ambiguous or unstated sector returns
    {"industry": ""} (a definitive skip that leaves the row in the visible
    backlog), while a model/transport failure returns None (a retry on a later
    daily rotation). This narrow call cannot touch counts, dates, sources or AI
    labels; the /industry-backfill endpoint additionally re-validates the label
    and writes it only when the field is still blank.
    """
    company = (company or "").strip()[:200]
    raw_text = (raw_text or "")[:6000]
    if not company and not raw_text.strip():
        return {"industry": ""}
    vocab = "\n".join("- " + label for label in INDUSTRY_VOCABULARY)
    prompt = (
        "Classify the employer's PRIMARY industry from the company name and the "
        "layoff excerpt below. Return STRICT JSON only:\n"
        '{"industry":"exactly one label from the list, or \\"unknown\\""}\n\n'
        "Rules:\n"
        "- Choose the SINGLE best-fit label from this closed list; copy it verbatim:\n"
        f"{vocab}\n"
        "- Base the call on what the company actually does. The company name is "
        "strong evidence; the excerpt may add sector context.\n"
        "- If the company's sector is genuinely unclear from the given text, "
        'answer {"industry":"unknown"}. Never guess to fill the field.\n\n'
        f"COMPANY: {company}\nEXCERPT: {raw_text}"
    )
    try:
        response = _get_client().chat.completions.create(
            model=MODEL, max_tokens=40,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"Industry classification failed: {exc}")
        return None
    return _validate_industry_result(result)


def _sanitize_role_categories(values):
    """Order-preserving filter of model output onto the fixed vocabulary."""
    if not isinstance(values, list):
        return []
    seen = []
    for value in values:
        slug = value.strip().lower() if isinstance(value, str) else ""
        if slug in ROLE_CATEGORIES and slug not in seen:
            seen.append(slug)
    return seen


def extract_role_categories(raw_text):
    """Extract only explicitly stated affected-role categories.

    Returns ``{"categories": [slugs], "evidence": "exact quote"}``. An empty
    categories list means the supplied text does not state which roles were
    affected — the caller marks the row checked-unknown so the bounded queue
    drains. ``None`` means a model/parse failure only, so the row stays queued
    for a later run. A claimed category whose evidence quote is not verbatim
    in the text is treated as not stated, never trusted.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return {"categories": [], "evidence": ""}
    prompt = """Read this layoff source text and return STRICT JSON only:
{"categories":["zero or more of: engineering|product_design|customer_support|sales_marketing|hr_recruiting|operations_warehouse|content_trust_safety|finance_admin|manufacturing|retail_staff"],"evidence":"exact source phrase naming the affected roles/teams/departments, or null"}

Category guide: engineering = software/IT/technical staff; product_design =
product management, design, UX; customer_support = customer support/service/
success staff, call centers; sales_marketing = sales, marketing, advertising;
hr_recruiting = HR, people teams, recruiting; operations_warehouse =
operations, warehouse, logistics, drivers; content_trust_safety = content,
moderation, trust & safety, editorial; finance_admin = finance, accounting,
legal, administrative; manufacturing = factory/production/assembly workers;
retail_staff = store/retail staff.

Rules: include a category ONLY when the text explicitly names the roles,
teams or departments affected by THESE cuts. Company-wide or unspecified
cuts return []. Never infer roles from the company's business (a retailer
cutting "corporate staff" is NOT retail_staff). The evidence phrase must be
copied exactly from TEXT and is REQUIRED whenever categories is non-empty.

TEXT:\n""" + raw_text
    try:
        response = _get_client().chat.completions.create(
            model=MODEL, max_tokens=250,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"Role-category extraction failed: {exc}")
        return None
    if not isinstance(result, dict):
        return None
    categories = _sanitize_role_categories(result.get("categories"))
    evidence = result.get("evidence")
    if categories and not _quote_is_supported(evidence, raw_text):
        return {"categories": [], "evidence": ""}
    return {
        "categories": categories,
        "evidence": evidence.strip() if categories and isinstance(evidence, str) else "",
    }


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
    if _percent_only_mention(job_count, raw_text):
        print(f"Extraction rejected: job_count {job_count} appears only as a percentage "
              f"— source: {raw_entry.get('source_url')}")
        return None
    if raw_text and not _count_in_text(job_count, raw_text):
        print(f"Extraction rejected: job_count {job_count} not found verbatim in source "
              f"(model likely derived it) — source: {raw_entry.get('source_url')}")
        return None
    extracted["job_count"] = job_count
    # Range upper bound: store it too so a query can report the "announced
    # intentions" framing (upper) or our conservative executed floor (job_count),
    # instead of the floor-only bias the review flagged. Must also appear verbatim
    # or we fall back to the floor (never fabricate the ceiling).
    jc_max = _coerce_job_count(extracted.get("job_count_max"))
    if not jc_max or jc_max < job_count or (raw_text and not _count_in_text(jc_max, raw_text)):
        jc_max = job_count
    extracted["job_count_max"] = jc_max

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
