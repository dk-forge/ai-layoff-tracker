"""
LLM extraction + classification.

Extraction runs on google/gemini-2.5-flash-lite via OpenRouter (changed
2026-08-07 from deepseek/deepseek-chat; see MODEL below for the two gold sets
that decided it). Classification still runs on deepseek/deepseek-chat, on
purpose: nothing has measured it. Both are one environment variable away from
anything else.

OpenRouter serves the OpenAI-compatible chat-completions API, so this module
uses the openai SDK with a base_url override — the anthropic SDK cannot talk
to OpenRouter (different wire format/endpoint).
"""
import datetime
import hashlib
import json
import os
import re

import openai

import spend

# THE EXTRACTION MODEL, AND THE ONLY ONE ANYTHING HAS MEASURED.
#
# Changed 2026-08-07 from deepseek/deepseek-chat, on two gold sets rather than
# on a price list. Against the SEC Item 2.05 set (2026-08-06) both scored 16/16.
# Against the corroborated NEWS set (2026-08-07, 35 scorable events, counts two
# independent sources both state) both accepted 30 and got 30 right, with ZERO
# wrong counts either way, at $0.000339 per item against $0.000875 -- 0.387x,
# reproducing the SEC ratio almost exactly on the messier corpus.
#
# The two models disagreed on exactly two of the 35, one in each direction:
# flash-lite recovered Alphabet 12,000 where the incumbent called the article
# not a layoff event, and returned no count on TikTok 150 where the incumbent
# recovered it. That is a tie decided by price, not a win.
#
# Why a cheaper extraction model is a COVERAGE change and not a saving: the
# Railway cron hits its per-run spend ceiling on every run and defers the
# remainder unread, so cost per candidate is what decides how many candidates
# get read at all (see the 2026-08-06 gate entry in docs/TECHLOG.md).
#
# Rollback is one environment variable and no deploy: OPENROUTER_MODEL.
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

# THE CLASSIFIER, WHICH NOTHING HAS MEASURED, AND WHICH THEREFORE DOES NOT MOVE.
#
# Industry, roles, reason tags and context: "pick one label from a fixed list"
# over up to 6,000 characters, and the bulk of the call volume. Until 2026-08-07
# this defaulted to MODEL, so an extraction benchmark would have silently moved
# a classifier that benchmark never looked at -- three surfaces changed by a
# measurement of one. The default is now written out, so the extraction swap
# above leaves it exactly where it was and moving it needs its own A/B against
# its own answer key. Pinned by tests/test_extraction_model_choice.py.
#
# The correctness-critical calls (full extraction, AI-causation) always use
# MODEL, never this.
CLASSIFY_MODEL = os.environ.get("OPENROUTER_CLASSIFY_MODEL", "deepseek/deepseek-chat")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("OPENROUTER_TIMEOUT_SECONDS", "45"))

# How much of a source's raw_text the extraction prompt reads.
#
# This MUST NOT be smaller than the window any collector deliberately builds, or
# the collector's care is silently discarded here. It was 2000 while
# sources/edgar.py built a 3000-char keyword-centred window "so the relevant
# passage survives the length cap" — so the last third of every SEC filing
# window was cut off before the model ever saw it, and any headcount living
# there could not pass the verbatim guard at line ~757 no matter what the model
# returned. Measured on the SEC Item 2.05 gold set (2026-08-01): EnerSys
# 2026-03-25 stated "approximately 474 employees" 1,756 characters after the
# Item 2.05 heading — inside edgar's window, outside this limit. Pinned against
# every collector's window by tests/test_extractor_text_budget.py.
RAW_TEXT_LIMIT = int(os.environ.get("EXTRACTOR_RAW_TEXT_LIMIT", "3000"))

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
    "bankruptcy",
    "federal_workforce",
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
5. For job_count: the total for THIS newly announced event only. TIMELINE TRAP: articles cite older layoffs for context ("after cutting 10,000 last year, X announced 500 new cuts") — NEVER use a historical/contextual number; use the number for the new announcement (500 here). SUBSET TRAP: if a division figure and a companywide total for the SAME new announcement both appear ("500 in cloud, part of 3,000 overall"), use the companywide total (3,000). If a range is given, use the lower bound. CEILING TRAP: when the source states ONLY an upper bound ("up to 600", "as many as 600", "could reach 600") with no floor, that figure is a ceiling, not a measured total: set job_count to it (it is the only number the source gives, and we never invent a floor) and set job_count_max to the SAME figure, then copy the qualifying words into ai_language-style evidence by keeping the qualifier in the excerpt so the ceiling is never displayed as a hard count. Never turn a percentage, dollar figure, future work-equivalence, or projected automation number into a layoff count.
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
- closure: source states a plant, store, site or facility is closing or shutting permanently
- bankruptcy: source cites bankruptcy, insolvency, administration, receivership, Chapter 7/11 or liquidation
- federal_workforce: source describes a government/public-sector workforce action (federal RIF, agency reduction, public-service cuts)

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

# The narrow classify calls (industry/roles/reason/context) carry their FULL
# task spec in their own user prompt, so they never needed the ~1,400-token
# extraction SYSTEM_PROMPT above - sending it was ~80% wasted input tokens on the
# highest-volume jobs. A tiny system message keeps the JSON output disciplined.
MINI_SYSTEM = ("You are a precise data-classification assistant. Follow the "
               "instructions exactly and return only strict JSON, no preamble.")

# Ask OpenRouter to return the CHARGED cost on every response (`usage.cost`,
# plus cached-token detail). spend.record_usage() prefers that figure over its
# own price-table estimate, so the meter IS the bill instead of arithmetic
# beside it. NOTE on prompt caching, so nobody claims a saving that does not
# exist: the sibling tracker verified (2026-07-29/30, against OpenRouter's
# endpoints API) that NO endpoint serving deepseek/deepseek-chat publishes a
# cache-read price, so the static SYSTEM_PROMPT (~62% of a typical extraction
# prompt) is billed at the full input rate every call and a "cached system
# prompt" saving here is exactly $0. The SYSTEM_PROMPT is live context for the
# extraction call (it defines the output contract); the dead-context instance
# in this module was classify_ai_evidence sending it to a task with its own
# spec, fixed below. If MODEL is ever pointed at a slug that does price cache
# reads, the charged figure makes the saving visible without another change.
USAGE_ACCOUNTING = {"usage": {"include": True}}

# ---------------------------------------------------------------------------
# The pre-extraction gate (cost-funnel port from the sibling tracker).
#
# Most candidates the cron pulls are NOT layoff events (typically well over
# half are discarded by the extractor), and every one of those rejects used to
# pay a FULL extraction: ~1,400-token system prompt + up to 3,000 chars of
# body + up to 1,000 output tokens (~$0.0008/call at DeepSeek list). The gate
# asks a far smaller question - "could this be a workforce-reduction event?" -
# with a ~150-token prompt and a ONE-WORD answer on a cheaper model, so a
# reject costs ~$0.00003 (sibling's measured figure for the same model and
# shape), about 1/25 of an extraction.
#
# WHY A MODEL AND NOT A VOCABULARY: a free keyword gate was measured here on
# 150 live Google News candidates (2026-08) and rejected 44% of them,
# including "Zillow lays off 7% of its workforce" (the list had "layoffs" but
# not "lays off") and non-English headlines. A vocabulary can only match the
# phrasings someone remembered to list; the gate must read any language and
# any euphemism, which is exactly what the collectors are built to surface.
#
# THE RULES, all load-bearing:
#   * Three verdicts, not two. NO is a judgement; ERROR is an outage or a
#     parse failure and is NEVER treated as a judgement - it fails OPEN to
#     extraction, so a provider blip can only cost money, never coverage.
#   * Uncertain -> YES, by prompt. The gate exists to drop the obvious
#     non-events, not to adjudicate the close calls.
#   * Gate rejects are NOT marked seen. The seen-URL store only ever holds
#     URLs the site itself retains, so a wrong NO today is re-pulled and
#     re-judged tomorrow; a systematic gate fault self-surfaces instead of
#     permanently burying its own mistakes.
#   * The default model mirrors the sibling's production gate. Override with
#     OPENROUTER_GATE_MODEL; set it to MODEL's value to gate on the extractor
#     model (still ~1/10 the cost, from prompt size alone).
# ---------------------------------------------------------------------------
GATE_MODEL = os.environ.get("OPENROUTER_GATE_MODEL", "google/gemini-2.5-flash-lite")
GATE_CHARS = int(os.environ.get("ALT_GATE_CHARS", "1000"))

GATE_YES, GATE_NO, GATE_ERROR = "YES", "NO", "ERROR"

GATE_SYSTEM = (
    "You decide whether a text could be reporting an actual workforce "
    "reduction by ONE NAMED employer: layoffs, job cuts, redundancies, a "
    "reduction in force, mass dismissal, buyouts or early-retirement "
    "programs, a plant, store, office or site closure with job losses, or a "
    "company filing that discusses exit or disposal costs, severance, or "
    "restructuring affecting employees - in ANY language. Answer YES when it "
    "plausibly is, and YES whenever you are unsure. Answer NO only when the "
    "text is clearly not about an actual workforce reduction event: hiring "
    "or expansion news, opinion or advice pieces, market roundups or "
    "statistics with no named employer, product, earnings or stock coverage "
    "with no job cuts, or AI-strategy stories with no job cuts. Reply with "
    "exactly one word: YES or NO."
)


def gate_verdict(raw_entry):
    """One cheap call: could this candidate be a layoff event? YES/NO/ERROR.

    ERROR means "the gate could not judge" (outage, empty reply, spend
    ceiling) and callers MUST treat it as a keep - folding it into NO would
    let a provider outage read as a quiet news day, the exact failure the
    sibling measured at 4,849 of 5,656 calls once. Never raises.
    """
    text = (raw_entry.get("raw_text") or "").strip()
    if not text:
        return GATE_NO  # extract_layoff_data returns None for these anyway
    if not spend.paid_reads_enabled():
        return GATE_ERROR  # not judged; extraction will defer and say so
    outlet = raw_entry.get("source_name") or raw_entry.get("source_type") or ""
    try:
        response = spend.metered_call(GATE_MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=GATE_MODEL, max_tokens=4, temperature=0,
            messages=[{"role": "system", "content": GATE_SYSTEM},
                      {"role": "user",
                       "content": f"Published by: {outlet}\n\n{text[:GATE_CHARS]}"}],
        ), what="the pre-extraction gate")
        content = ""
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
    except Exception as exc:
        print(f"gate error (fails open to extraction): {exc}")
        return GATE_ERROR
    if not content.strip():
        return GATE_ERROR
    return GATE_NO if "NO" in content.upper() and "YES" not in content.upper() else GATE_YES

_client = None


class CreditsExhaustedError(RuntimeError):
    """The LLM provider returned HTTP 402 / 'insufficient credits'.

    This is a BILLING condition, not a code fault or a transient outage: no
    amount of retrying fixes it, and every subsequent call in the run will fail
    the same way. Batch jobs catch this to stop immediately (rather than burning
    hundreds of doomed calls) and report a distinct, human-actionable state
    ("top up OpenRouter credits") instead of paging as if the code broke.
    """


# Once one call reports credits exhausted, every further call in THIS process is
# guaranteed to fail the same way. The flag lets classify_* short-circuit so a
# 200-row batch stops in seconds, not minutes. Reset per process (each workflow
# run is fresh), so a mid-run top-up is picked up on the next scheduled run.
_credits_exhausted = False


def _is_credits_exhausted(exc):
    """True when an exception is the provider's out-of-credits (402) signal."""
    msg = str(exc).lower()
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 402 or "insufficient credits" in msg or "code': 402" in msg \
        or "error code: 402" in msg


def _guard_credits(exc):
    """Call from an LLM except-block: if this is the out-of-credits signal, trip
    the circuit breaker and raise CreditsExhaustedError; otherwise return (the
    caller's existing transient-failure handling continues)."""
    global _credits_exhausted
    if _is_credits_exhausted(exc):
        _credits_exhausted = True
        raise CreditsExhaustedError(
            "OpenRouter credits exhausted (HTTP 402). Top up at "
            "https://openrouter.ai/settings/credits") from exc


_spend_deferrals = 0


def _defer_for_spend(what):
    """Return None because paid reads are off, and say so once per run.

    None is the "not decided, retry later" value for EVERY paid function in this
    module (see each docstring): the caller leaves the row queued and the
    seen-URL pre-check never marks a URL the site does not hold. So a deferred
    candidate is read on a later run rather than lost, which is what makes a
    spend ceiling safe to enforce here at all.

    Deliberately NOT an exception: an exception would land in each caller's
    transient-failure counter and could trip a "posted 0 with N failures" loud
    failure, turning a budget decision into a red data job.
    """
    global _spend_deferrals
    _spend_deferrals += 1
    if _spend_deferrals == 1:
        print(f"::notice::paid reads are OFF (spend ceiling) — deferring {what} "
              f"and every later paid call this run. Free ingest continues; "
              f"deferred candidates are UNMARKED and return on a later run.")
    return None


def spend_deferral_count():
    """How many paid calls this run declined to make. Reported by callers so a
    degraded run is visible in the logs and the health ledger rather than
    looking like a quiet, cheap, successful run."""
    return _spend_deferrals


def spend_deferred_since(before):
    """True when the paid call made since ``before = spend_deferral_count()``
    was DECLINED for budget, rather than attempted and failed.

    Every paid function in this module returns None for both, and a caller that
    cannot tell them apart reports the guard working as the model breaking. On
    2026-08-13 `industry-backfill` printed 200 lines of "FAILED", raised "All
    200 attempted industry classifications failed", was retried three times and
    paged the owner, on a run where the budget guard had behaved perfectly and
    the job had already decided to exit 0.

    So: NOT ASKED is a fourth status, not a kind of failure. A caller that
    counts a None must ask this before counting it. See
    `tests/test_budget_stop_is_not_a_failure.py`, and the same lesson one module
    over in `ai_evidence_sweep._ai_quote` (None is "we did not ask", '' is "we
    asked and the employer did not name AI").
    """
    return _spend_deferrals > before


def _precheck_credits():
    """Short-circuit at the top of a classify call once the breaker has tripped,
    so a big batch stops in seconds instead of firing hundreds of doomed calls."""
    if _credits_exhausted:
        raise CreditsExhaustedError(
            "OpenRouter credits exhausted (HTTP 402). Top up at "
            "https://openrouter.ai/settings/credits")


class PaidReadsDisabled(RuntimeError):
    """Raised by _get_client() when the spend ceiling has switched paid reads
    off. Distinct from CreditsExhaustedError: there is money, policy says not to
    spend it right now."""


def _get_client():
    """Build (once) the shared OpenRouter client.

    The spend gate is repeated HERE, not only in the public functions, because
    three modules reach past them and call this directly:
    `sources/warn_llm.py`, `sources/warn_hi_ocr.py` and `edgar_recall_probe.py`.
    All three already wrap the call and degrade correctly on any exception —
    warn_llm returns 0 so the WARN row still imports with its deterministic
    count, and the recall probe returns "unknown" rather than a false pass — so
    raising here is both safe and the right shape. It also means a future direct
    caller is covered by default instead of silently spending.
    """
    if not spend.paid_reads_enabled():
        raise PaidReadsDisabled(
            "paid reads are OFF (spend ceiling); this call was not made and the "
            "candidate is left unmarked for a later run")
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
    # A number binds to its percent sign TIGHTLY and on ONE LINE. This was `\s*`,
    # and `\s` matches `\n`, so on any path that does not flatten whitespace
    # (PDF/OCR, tables) a headcount at the end of one line and a "Percent of
    # workforce" column header at the start of the next read as a single
    # "17 percent" and the record was thrown away — a figure that IS verbatim in
    # the source, discarded as though the model had invented it. That is the same
    # defect the sibling tracker hit. `[^\S\r\n]` is "whitespace, but not a line
    # break"; the {0,2} bound also stops a percent sign several columns away from
    # capturing the number.
    gap = r"[^\S\r\n]{0,2}"
    as_percent = re.search(rf"\b{job_count}{gap}(%|percent\b)", raw_text, re.I)
    as_count = re.search(rf"\b{job_count}\b(?!{gap}(%|percent))", raw_text, re.I)
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
    # Every thousands separator listed in `sep` below must ALSO be generated as
    # a variant here, or the guard rejects a number that is plainly present.
    # U+202F was in `sep` but not in this set, so "12 000" written with the
    # narrow no-break space — the standard French/Swiss/Canadian grouping, and
    # what Word and many CMSs emit — failed the verbatim check and the record
    # was discarded as though the model had invented a figure that was sitting
    # right there. U+2009 (thin space) is the same story from typeset sources.
    # Widening this cannot admit a DERIVED number: each variant is still matched
    # as an exact literal, fenced by the same lookarounds.
    variants = {str(n), grouped, grouped.replace(",", " "), grouped.replace(",", "."),
                grouped.replace(",", " "), grouped.replace(",", " "),
                grouped.replace(",", " ")}
    if n % 1000 == 0 and n >= 1000:
        variants.update({f"{n // 1000}k", f"{n // 1000}K"})
    # A variant must not be the PREFIX of a longer grouped number: the old
    # lookahead only blocked a trailing digit, so "500" matched inside
    # "$500,000" and "12" inside "12,500 employees" — the guard's whole job is
    # to stop exactly that misread. Also forbid a following thousands-group
    # (separator + 3 digits). Lookbehind already blocks matching from the left.
    # Must stay in lockstep with `variants` above: a separator that can GROUP a
    # number must also be one this lookahead refuses to match across, or "12"
    # is accepted as a standalone count out of "12 500". U+2009 was missing
    # here and the whitespace test caught it the moment variants gained it.
    sep = r"[.,    ]"
    if not any(
        re.search(rf"(?<![\d.,]){re.escape(v)}(?![\d])(?!{sep}\d{{3}})", raw_text)
        for v in variants
    ):
        return False
    # Year trap: a 4-digit value in 1990-2099 that appears ONLY in a date phrase
    # ("in 2020", "by 2026", "fiscal 2024") and never beside a headcount noun is
    # a calendar year the model misread as a count. A documented floor prefers a
    # dropped row over a wrong number, so reject it.
    if 1990 <= n <= 2099:
        noun = (r"jobs?|employe|workers?|positions?|staff|roles?|layoff|headcount|"
                r"people|workforce|personnel|hires?|staffers?")
        dateword = (r"in|by|since|before|after|through|during|fiscal|fy|year|of|the|"
                    r"january|february|march|april|may|june|july|august|september|"
                    r"october|november|december|q[1-4]")
        near_noun = re.search(
            rf"(?<![\d.,]){n}(?![\d])(?!{sep}\d{{3}})\W{{0,4}}(?:{noun})"
            rf"|(?:{noun})\w*\W{{0,6}}(?:of\s+|about\s+|~)?{n}(?![\d])(?!{sep}\d{{3}})",
            raw_text, re.I)
        only_dateish = re.search(rf"(?:{dateword})\s+{n}(?![\d])(?!{sep}\d{{3}})",
                                 raw_text, re.I)
        if only_dateish and not near_noun:
            return False
    return True


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


# The AI-causation ask and the guard that admits its answer, lifted out of
# classify_ai_evidence() so a HARNESS can score the production decision rule
# instead of a copy of it (railway/ab_ai_causation.py, 2026-08-18). Two
# functions rather than one string constant because the guard is half the rule:
# a causal label without a verbatim receipt is downgraded to `unknown`, and a
# scorer that skipped that step would be measuring a model this pipeline never
# takes at its word. Nothing about the production call changes — it calls these.
AI_CAUSATION_TEXT_LIMIT = 6000


def ai_causation_prompt(raw_text):
    """The exact user prompt the AI-causation call sends."""
    return """Classify AI causation in this layoff source. Return STRICT JSON only:
{"ai_causation":"primary_cause|contributing_cause|selection_or_operations|context_only|explicitly_denied|unknown","ai_language":"exact source phrase or null","confidence":0-100}

AI is primary/contributing only if this text explicitly says AI, automation,
machine learning or robots caused the cuts. A general AI strategy, investment,
or use of AI in operations is not causal. Never infer. The phrase must be an
exact quote from the supplied text.

TEXT:\n""" + raw_text


def finalize_ai_causation(result, raw_text):
    """Admit (or downgrade) a model's raw AI-causation JSON.

    Returns the stored shape, or None when the model did not return an object.
    A causal label whose claimed quote is not verbatim in `raw_text` becomes
    `unknown` — the guard that stops a fabricated or context-only quote
    reaching the AI headline metric.
    """
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
    return {"ai_causation": cause,
            "ai_language": quote.strip() if isinstance(quote, str) else "",
            "confidence": confidence}


def ai_explicit_from_causation(cause):
    """The single definition of `ai_explicit`, shared by the extraction path,
    the reassessment path and anything scoring either of them."""
    return cause in {"primary_cause", "contributing_cause"}


def classify_ai_evidence(raw_text):
    """Reassess only AI causation for an already-recorded event.

    Historical rows keep their source, count and date. This deliberately
    narrow call avoids an LLM "correcting" unrelated fields while allowing a
    fresh read of the linked document to replace an old keyword-based AI flag.
    """
    raw_text = (raw_text or "")[:AI_CAUSATION_TEXT_LIMIT]
    if not raw_text.strip():
        return None
    if not spend.paid_reads_enabled():
        return _defer_for_spend("AI-causation reassessment")
    prompt = ai_causation_prompt(raw_text)
    try:
        # MODEL (never CLASSIFY_MODEL): AI-causation is correctness-critical.
        # But MINI_SYSTEM, not SYSTEM_PROMPT: this narrow call carries its
        # full spec in its own prompt, and the ~1,400-token extraction
        # preamble it used to send described a different task (full-record
        # JSON with fields this call must not return) — dead context on every
        # call of the daily ai-evidence-sweep.
        response = spend.metered_call(MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=MODEL, max_tokens=250,
            messages=[{"role": "system", "content": MINI_SYSTEM}, {"role": "user", "content": prompt}],
        ), what="AI-causation reassessment")
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"AI evidence reassessment failed: {exc}")
        return None
    return finalize_ai_causation(result, raw_text)


#: Country names as a reader writes them, mapped to the canonical label. Only
#: the ones whose everyday form differs from the stored value need an entry; a
#: country spelled the way it is stored matches on its own name.
_COUNTRY_ALIASES = {
    "United States": ("united states", "u.s.", "u.s", "us", "usa", "u.s.a.", "america", "american"),
    "United Kingdom": ("united kingdom", "uk", "u.k.", "britain", "british", "england", "scotland", "wales"),
    "Netherlands": ("netherlands", "dutch", "holland"),
    "Germany": ("germany", "german"),
    "France": ("france", "french"),
    "Spain": ("spain", "spanish"),
    "Italy": ("italy", "italian"),
    "Sweden": ("sweden", "swedish"),
    "Japan": ("japan", "japanese"),
    "China": ("china", "chinese"),
    "India": ("india", "indian"),
    "Ireland": ("ireland", "irish"),
    "Switzerland": ("switzerland", "swiss"),
    "Canada": ("canada", "canadian"),
    "Australia": ("australia", "australian"),
    "Brazil": ("brazil", "brazilian"),
    "Poland": ("poland", "polish"),
    "South Korea": ("south korea", "korea", "korean"),
}


def _countries_named_in(quote):
    """The canonical countries a quote actually NAMES, as a set.

    The repo's one country list lives in generate_country_table; imported
    lazily so this module keeps its import graph. If it cannot be read, the
    caller must treat the quote as unverifiable rather than as clean.
    """
    from generate_country_table import COUNTRIES        # the one list

    words = re.findall(r"[a-z.&']+", str(quote or "").lower())
    text = " " + " ".join(words) + " "
    named = set()
    for country in COUNTRIES:
        for alias in _COUNTRY_ALIASES.get(country, (country.lower(),)):
            if f" {alias} " in text:
                named.add(country)
                break
    return named


def _canonical_country(value):
    """A stored country label from whatever the model returned, or ''.

    The server normalises again, but a value it would reject must not travel
    this far pretending to be an answer: the model returned "US" for the one
    row that survived every other gate.
    """
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        from generate_country_table import COUNTRIES
    except Exception:
        return ""
    if raw in COUNTRIES:
        return raw
    lowered = raw.lower()
    for country in COUNTRIES:
        if lowered == country.lower():
            return country
    for country, aliases in _COUNTRY_ALIASES.items():
        if lowered in aliases:
            return country
    return ""


def _quote_names_exactly(country, quote):
    """True when the quote names `country` and no other country.

    Measured on the 2026-08-18 blank-country backlog, this is the difference
    between a supported quote and an ANSWERING one, and the quote gate alone
    could not tell them apart. Of the four rows a first pass "recovered":
      * Zepz -> Poland, quoting "closure of business units in Kenya and
        Poland". Two countries, one written. That is a wrong public number.
      * Bosch -> Germany, quoting "Bundesweit gehen 25.000 Beschaeftigte auf
        die Strasse" - a nationwide PROTEST, naming no country at all.
      * Thermo Fisher -> United States, quoting "Cambridge and Plainville".
        Correct only if you already know where Plainville is; the quote does
        not say, and Cambridge is in two countries.
      * Stellantis -> United States, quoting "U.S. plant workers". The only
        one where the quote states the answer.
    One rule rejects the first three and keeps the fourth.
    """
    try:
        named = _countries_named_in(quote)
    except Exception as exc:                     # unreadable list, not a pass
        print(f"country-name check unavailable ({exc}); treating quote as unverified")
        return False
    return named == {country}


def extract_job_location_evidence(raw_text, company=""):
    """Job-LOCATION country stated outright in a source, or None.

    This exists for the 2026-08-18 blank-country backlog: rows the extractor
    correctly left unplaced because the excerpt it read never said where the
    jobs were. Sometimes the ARTICLE does say and the excerpt did not carry it,
    and re-reading the body is the only honest way to find out.

    It answers ONE question - where are the cut jobs - and returns nothing
    else, so it cannot move a count, a date, a stage or an AI label. Three
    things it must never do, each of which is a way a real dataset acquires
    invented geography:
      * read the publisher's nationality as the job location. A Swedish
        company reported in a Serbian outlet is neither a Serbian layoff nor a
        Serbian employer.
      * read the employer's headquarters as the job location. That conflation
        is the whole reason `country` and `employer_country` are two fields.
      * name a country because a global company obviously has staff there.

    Returning None is a correct and expected answer. Most sources in this
    backlog genuinely do not state a location, and a row that stays blank is
    honest; `employer_country` is the field that makes such a row findable.

    Uses MODEL, not CLASSIFY_MODEL: this is reading a fact out of a body, the
    same act as extraction, and it feeds a published per-country figure.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return None
    if not spend.paid_reads_enabled():
        return _defer_for_spend("job-location re-read")
    prompt = ("""Read this layoff source and return STRICT JSON only:
{"country":"the country the CUT JOBS were located in, or null","country_evidence":"exact source phrase stating that location, or null"}

The question is WHERE THE ELIMINATED JOBS WERE, nothing else.

Return null unless the text states the location of the cuts. In particular:
- The publisher's country is NOT the job location.
- The company's headquarters is NOT the job location.
- "A global company must have staff there" is NOT a stated location.
- A cut described as global, worldwide or spanning several countries has no
  single country: return null.
If the text names a city, region or state, return the country it is in.
"country_evidence" must be copied EXACTLY from TEXT, character for character.

"""
              + (f"The employer is {company}.\n\n" if str(company or "").strip() else "")
              + "TEXT:\n" + raw_text)
    try:
        response = spend.metered_call(MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=MODEL, max_tokens=250,
            messages=[{"role": "system", "content": MINI_SYSTEM},
                      {"role": "user", "content": prompt}],
        ), what="job-location re-read")
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        print(f"Job-location re-read failed: {exc}")
        return None
    if not isinstance(result, dict):
        return None
    country = _canonical_country(result.get("country"))
    quote = result.get("country_evidence")
    if not country:
        return None
    if not _quote_is_supported(quote, raw_text):
        # An unquotable location is an invented one. Blank is the right answer.
        return None
    if not _quote_names_exactly(country, quote):
        # SUPPORTED IS NOT ANSWERING. See _quote_names_exactly: three of the
        # first four "recoveries" passed the quote gate and still could not
        # place a row, one of them by naming two countries and returning one.
        return None
    return {"country": country, "country_evidence": quote.strip()}


def extract_context_evidence(raw_text):
    """Extract only explicit domicile and public announcement-date evidence.

    This narrow reassessment cannot alter job counts, layoff dates, stages or
    causal labels. Quotes are checked locally before the result is sent to the
    keyed enrichment endpoint.
    """
    raw_text = (raw_text or "")[:6000]
    if not raw_text.strip():
        return None
    if not spend.paid_reads_enabled():
        return _defer_for_spend("context/domicile evidence extraction")
    prompt = """Read this layoff source and return STRICT JSON only:
{"employer_country":"canonical country or null","employer_country_evidence":"exact source phrase or null","announcement_date":"YYYY-MM-DD or null","announcement_evidence":"exact source phrase containing the announcement date or null"}

Rules: employer_country is only the employer's HQ/domicile when the text says
so; never infer it from job location or brand familiarity. announcement_date is
the public announcement date only when an exact date is stated in the text;
never substitute an effective layoff date or page-access date. Return null for
any unsupported field. Evidence phrases must be copied exactly from TEXT.

TEXT:\n""" + raw_text
    try:
        response = spend.metered_call(CLASSIFY_MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=CLASSIFY_MODEL, max_tokens=350,
            messages=[{"role": "system", "content": MINI_SYSTEM}, {"role": "user", "content": prompt}],
        ), what="context-evidence reassessment")
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
    if not spend.paid_reads_enabled():
        return _defer_for_spend("reason-tag classification")
    prompt = """Assign layoff reason tags for the text below. Return STRICT JSON only:
{"reason_tags":["zero or more of: ai_automation, possible_ai, revenue_decline, restructuring, merger_acquisition, offshoring, product_discontinuation, cost_reduction, macroeconomic, closure, bankruptcy, federal_workforce"],"ai_evidence":"exact quote where the EMPLOYER states AI/automation as a reason, or null"}

Tag definitions (the ONLY guidance for this call - it uses a minimal system prompt):
- ai_automation: employer itself names AI/automation/robots/ML as a reason
- possible_ai: text ties the cuts to AI without the employer stating it
- revenue_decline: revenue/financial performance/earnings cited
- restructuring: reorganization/realignment/restructuring language
- merger_acquisition: M&A cited; offshoring: jobs moving to another country
- product_discontinuation: a product/division shutting down
- cost_reduction: generic efficiency/cost language with no specific reason
- macroeconomic: economic conditions/market environment cited
- closure: a plant/store/site/facility closing permanently
- bankruptcy: bankruptcy/insolvency/administration/receivership/Chapter 7 or 11/liquidation
- federal_workforce: a government/public-sector workforce action (federal RIF, agency reduction, public-service cuts) - NOT a private contractor losing government work

Rules:
- A tag needs explicit supporting language in this text. Multiple tags are allowed.
- If the text states no reason for the cuts, return {"reason_tags":[],"ai_evidence":null}.
- ai_automation ONLY when the employer itself states AI/automation/robots/
  machine learning as a reason, with the exact quote in ai_evidence.
- possible_ai when the text ties the cuts to AI without the employer stating
  it (press framing, productivity/automation implications).
- Never infer a reason from the company's industry, reputation, or anything
  outside this text.

TEXT:\n""" + raw_text
    _precheck_credits()
    try:
        response = spend.metered_call(CLASSIFY_MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=CLASSIFY_MODEL, max_tokens=200,
            messages=[{"role": "system", "content": MINI_SYSTEM}, {"role": "user", "content": prompt}],
        ), what="reason-tag classification")
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        _guard_credits(exc)
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
    if not spend.paid_reads_enabled():
        return _defer_for_spend("industry classification")
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
    _precheck_credits()
    try:
        response = spend.metered_call(CLASSIFY_MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=CLASSIFY_MODEL, max_tokens=40,
            messages=[{"role": "system", "content": MINI_SYSTEM}, {"role": "user", "content": prompt}],
        ), what="industry classification")
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        _guard_credits(exc)
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
    if not spend.paid_reads_enabled():
        return _defer_for_spend("affected-role extraction")
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
    _precheck_credits()
    try:
        response = spend.metered_call(CLASSIFY_MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=CLASSIFY_MODEL, max_tokens=250,
            messages=[{"role": "system", "content": MINI_SYSTEM}, {"role": "user", "content": prompt}],
        ), what="role-category extraction")
        content = response.choices[0].message.content if response.choices else ""
        result = _parse_json_response(content or "")
    except Exception as exc:
        _guard_credits(exc)
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
    raw_text = (raw_entry.get("raw_text") or "")[:RAW_TEXT_LIMIT]
    if not raw_text.strip():
        return None

    if not spend.paid_reads_enabled():
        return _defer_for_spend("layoff extraction")
    prompt = f"""Extract layoff data from this source:

SOURCE TYPE: {raw_entry.get('source_type')}
SOURCE NAME: {raw_entry.get('source_name')}
COMPANY (if known): {raw_entry.get('company_name') or 'Unknown'}
TICKER (if known): {raw_entry.get('ticker') or 'Unknown'}
DATE: {raw_entry.get('filing_date') or 'Unknown'}

TEXT:
{raw_text}"""

    try:
        response = spend.metered_call(MODEL, lambda: _get_client().chat.completions.create(
            extra_body=USAGE_ACCOUNTING,
            model=MODEL,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        ), what="layoff extraction")
    except spend.PaidReadsOff:
        # The ceiling tripped between the check at the top of this function and
        # the call (another paid call in between spent the last of it). Same
        # answer as the check itself gives: undecided, row stays queued.
        return _defer_for_spend("layoff extraction")
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
    # Future ceiling (defense in depth; the DB re-checks the same bound): a date
    # implausibly far out is a model misreading a projection ("by 2050") as an
    # effective date. Generous ~3y margin keeps genuine announced closures dated
    # a couple years out; anything past it falls back to the source date or undated.
    _max_future = (datetime.date.today() + datetime.timedelta(days=366 * 3)).isoformat()
    if extracted["layoff_date"] and extracted["layoff_date"] > _max_future:
        fallback = _normalize_date(raw_entry.get("filing_date"))
        extracted["layoff_date"] = fallback if (fallback and fallback <= _max_future) else None

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
    extracted["ai_explicit"] = ai_explicit_from_causation(causation)
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
