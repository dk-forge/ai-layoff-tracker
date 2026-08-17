"""Measurement: how far does a NO-MODEL parser get on 8-K Item 2.05?

DRY RUN ONLY, WIRED TO NOTHING. Posts nothing, writes no row, reports no source
health, and — the point of the exercise — **calls no model**. Manual dispatch
only, in the dormant-source style: it exists to produce one number that decides
whether a cheaper path is viable, not to become a path.

THE QUESTION
------------
SEC Item 2.05 gold-set recall is 24/57. The 2026-08-01 forensics
(docs/TECHLOG.md, "where the missing SEC Item 2.05 filings actually go")
established the 33 misses are not judgment failures: replayed through the real
pipeline, 29 were accepted and 28 recovered the exact stated headcount. They
were never fetched. Closing that gap means sweeping those months, and every
swept candidate is a model call.

An 8-K Item 2.05 is unusually structured: the item heading is fixed, the filer
and the filing date are in the EDGAR header, and the headcount is stated
verbatim in the text — which is precisely why `extractor._count_in_text` can
verify it literally. So: how much of the gold set can a deterministic parser
recover on its own, and — the number that actually decides it — at what
precision?

WHAT IT REFUSES, AND WHY REFUSING IS A CORRECT ANSWER
-----------------------------------------------------
A cheap parser that is confidently wrong is far worse than an expensive one that
is right. Two refusals are therefore scored as CORRECT, not as misses:

  * **Derived counts.** Wabash National's 270 is the sum of four separately
    stated components ("3 salaried and 53 hourly" + "21 salaried and 193
    hourly"). `extractor.py` refuses derived counts by design; a parser that
    "helpfully" sums them has reintroduced the hole that once published Intuit
    as 17 jobs. This parser refuses on AMBIGUITY — two or more distinct
    headcount candidates in the section and it declines — which is the same
    refusal reached by a rule rather than by a special case.
  * **Counts that are not in the primary document at all.** Codexis (46) and
    PLAYSTUDIOS (177) state the figure only in the EX-99.1 exhibit. The parser
    cannot invent it and must not.

THE GUARD IS IMPORTED, NEVER RE-IMPLEMENTED
-------------------------------------------
`_count_in_text` and `_percent_only_mention` come from `extractor.py`. This repo
has been bitten repeatedly by a second copy of a rule drifting from the first
(recall_precision.py carries its own smaller `_count_in_text` and it already
disagrees about the year trap and about grouped-number prefixes). A number this
probe calls verified is verified by the SAME function the production path uses,
or the measurement is not about production.

WHAT IT MEASURED (2026-08-12, full 57-event set — docs/TECHLOG.md)
------------------------------------------------------------------
43 resolved and correct, **0 resolved and wrong**, 1 correctly refused
(Wabash), 8 whose count is only in the EX-99.1 exhibit, 5 that genuinely need a
model. Recall 43/57 = 75.4%, precision 43/43 = 100%. The verdict was NOT that
the cheap path pays for itself: Item 2.05 filings are 15 of the 271 documents a
month's sweep reads, and the whole twelve-month gap costs about $1.01 of model
time. It is a precision instrument, not a saving. Read the TECHLOG entry before
wiring this to anything.

DO NOT RUN THIS PARSER ON UNSTRUCTURED TEXT. Inside the item section it scored
43/43. Over the EX-99.1 press-release bodies it read GitLab's "2021 Employee
Stock Purchase Plan" as a headcount of 2021 for a 350-person cut. The heading
anchor is the hypothesis, not a convenience.

`extractor.py` imports the openai SDK at module scope. The deterministic path
calls no model and needs none, so when the SDK is absent a stub is installed
before the import purely so the guard can be imported rather than copied. If
that stub were ever exercised by a real call it would raise, loudly.

RUN
---
    python3 railway/sec_205_deterministic_probe.py

Env:
    EDGAR_USER_AGENT   required by SEC fair-access; defaults to the UA CLAUDE.md
                       mandates.
    D205_ONLY          'misses' | 'matched' | 'all' (default 'all')
    D205_CACHE         directory for fetched EDGAR documents (default a temp
                       dir). Cached so a re-run does not hit SEC again.
    D205_OUT           write the per-filing JSON artifact here.
    D205_HELD          also measure the "do we already hold this?" pre-check
                       against the public /query API (no key, read-only).
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time
import types
import urllib.parse
import urllib.request
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if "openai" not in sys.modules:
    try:
        import openai  # noqa: F401
    except ImportError:
        sys.modules["openai"] = types.ModuleType("openai")

import extractor  # noqa: E402  (after the stub, on purpose)
# Every rate this repo prints carries a Wilson interval — n=57 is a WIDE
# INTERVAL, not a precise number (recall_precision.py's header, 2026-08-01).
# Imported, so this file cannot grow its own second opinion about what 75% means.
from recall_goldset import format_interval  # noqa: E402

GOLDSET = os.environ.get(
    "D205_GOLDSET",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "docs", "recall-reference-sets",
                 "sec-item-205-us-2025-07_2026-06.goldset.json"))

UA = os.environ.get("EDGAR_USER_AGENT",
                    "AiLayoffTracker/1.0 (+https://asktherecruiter.com)")
SEC_DELAY = 0.15          # under SEC's 10 req/s, and we are in no hurry
MAX_DOC_BYTES = 2_000_000
SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")

# The parser reads the Item 2.05 SECTION, not the whole filing. The structure is
# the whole hypothesis: a number outside the item the filer coded 2.05 is not
# what the item discloses, and reading the whole document is how a parser starts
# picking up share counts and dollar figures.
SECTION_CHARS = 6000

_HEADCOUNT_NOUN = (r"employees?|positions?|roles?|jobs?|workers?|staff|colleagues|"
                   r"personnel|associates|employee\s+positions?|staff\s+positions?")
# Up to three descriptive words may sit between the figure and the noun —
# "250 corporate and sales roles", "600 manufacturing positions". Bounded at
# three on purpose: unbounded, a sentence like "December 31, 2025, with most of
# the related employee departures" starts handing 2025 to the guard as a
# headcount, which is the year trap _count_in_text exists to catch and which a
# parser should not be leaning on it to catch.
_QUALIFIER = (r"(?:[A-Za-z][A-Za-z-]{1,14}\s+|and\s+){0,3}")
_NUM = r"(?<!\$)(\d{1,3}(?:[,\s]\d{3})+|\d+)"

# Two shapes, both requiring the number to SIT BESIDE a headcount noun:
#   forward   "approximately 800 roles", "1,300 full-time employees"
#   reverse   "reduce its workforce by approximately 800", "headcount by ~250"
_FORWARD = re.compile(
    rf"(?<![\d.,]){_NUM}\s*(?!%|\s*percent)\s+{_QUALIFIER}(?:{_HEADCOUNT_NOUN})\b",
    re.I)
_REVERSE = re.compile(
    rf"\b(?:workforce|headcount|staffing|employee\s+base|global\s+workforce)\b"
    rf"[^.;]{{0,40}}?\bby\s+(?:approximately|about|roughly|up\s+to|~)?\s*{_NUM}"
    rf"(?![\d.,]*\s*%)",
    re.I)
# A RANGE IS ONE COUNT, AND IT IS THE LOWER BOUND. Not a rule invented here:
# extractor.py's system prompt says "If a range is given, use the lower bound"
# and carries the upper in job_count_max. Without this, HP's "workforce
# reductions of approximately 4,000 - 6,000 employees" parses as 6,000 — the
# single WRONG answer the first pass of this measurement produced, and the exact
# failure mode that makes a cheap parser dangerous. The upper bound is recorded
# so it is suppressed rather than counted as a second, ambiguity-triggering
# figure.
_RANGE = re.compile(
    rf"(?<![\d.,]){_NUM}\s*(?:-|–|—|to)\s*{_NUM}\s*"
    rf"(?!%|\s*percent)\s*{_QUALIFIER}(?:{_HEADCOUNT_NOUN})\b", re.I)

# A filing that says "eliminate approximately 4% of its workforce" and nothing
# else has no headcount to parse. Recorded as its own reason so "no number" and
# "percentage only" never collapse into one bucket.
_PERCENT_ONLY_CLUE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent)\b", re.I)


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "identity"})
    time.sleep(SEC_DELAY)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read(MAX_DOC_BYTES).decode("utf-8", "replace")


_CACHE = os.environ.get("D205_CACHE") or os.path.join(
    tempfile.gettempdir(), "sec205-cache")


def fetch(url):
    """Fetch with an on-disk cache. EDGAR is public; do not hammer it."""
    os.makedirs(_CACHE, exist_ok=True)
    key = urllib.parse.quote(url, safe="")[-180:]
    path = os.path.join(_CACHE, key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    body = _get(url)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return body


def strip_html(markup):
    """Same shape as sources/edgar.py._strip_html — tags out, entities decoded,
    whitespace flattened. Kept here rather than imported because that module
    needs `requests`, which this stdlib-only probe deliberately does not."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- header

def parse_header(index_html, cik):
    """Employer, filing date and item codes from the EDGAR filing header.

    This is the free half of the hypothesis: none of it needs a model, and in
    production the same three fields arrive in the EFTS hit (`display_names`,
    `file_date`, `items`) without even this request.
    """
    filers = []
    for m in re.finditer(
            r'class="companyName">\s*(.*?)\s*(?:\(Filer\))?\s*<acronym[^>]*>CIK'
            r'</acronym>:\s*<a[^>]*>\s*(\d+)', index_html, re.S):
        name = re.sub(r"\s*\(Filer\)\s*$", "", unescape(m.group(1))).strip()
        filers.append((name, str(int(m.group(2)))))
    employer = None
    for name, fcik in filers:
        if fcik == str(int(cik)):
            employer = name
            break
    if employer is None and filers:
        employer = filers[0][0]

    date_m = re.search(r"Filing Date\s*</div>\s*<div[^>]*>\s*([\d-]{10})",
                       index_html)
    if not date_m:
        flat = strip_html(index_html)
        date_m = re.search(r"Filing Date\s+(\d{4}-\d{2}-\d{2})", flat)
    items = re.findall(r"Item\s+(\d\.\d\d)\s*:", strip_html(index_html))
    return {"employer": employer, "filing_date": date_m.group(1) if date_m else None,
            "items": sorted(set(items)), "filers": filers}


def exhibit_urls(index_html, base_url):
    """EX-99.x documents listed in the filing index, in document order."""
    folder = base_url.rsplit("/", 1)[0]
    out = []
    for m in re.finditer(r'href="([^"]+\.(?:htm|html|txt))"[^>]*>[^<]*</a>\s*</td>\s*'
                         r'<td[^>]*>\s*(EX-99[^<\s]*)', index_html, re.I):
        href = m.group(1).split("?")[0]
        out.append((m.group(2), "https://www.sec.gov" + href
                    if href.startswith("/") else f"{folder}/{href}"))
    return out


# ---------------------------------------------------------------- section

_ITEM_HEAD = re.compile(r"Item\s*2\.05\b", re.I)
_NEXT_ITEM = re.compile(r"Item\s*(?!2\.05)\d\.\d\d\b", re.I)
_SIGNATURE = re.compile(r"\bSIGNATURES?\b")


def item_205_section(text):
    """The Item 2.05 passage: heading to the next item heading (or SIGNATURES).

    EDGAR documents repeat the item headings in a table of contents at the top,
    so the LAST heading occurrence with real prose after it is taken, not the
    first.
    """
    starts = [m.start() for m in _ITEM_HEAD.finditer(text)]
    if not starts:
        return None
    best = None
    for s in starts:
        window = text[s:s + SECTION_CHARS]
        nxt = _NEXT_ITEM.search(window, 8)
        sig = _SIGNATURE.search(window, 8)
        end = min([x.start() for x in (nxt, sig) if x] or [len(window)])
        body = window[:end]
        if best is None or len(body) > len(best):
            best = body
    return best


# ---------------------------------------------------------------- counts

def _to_int(s):
    try:
        n = int(re.sub(r"[,\s]", "", s))
    except ValueError:
        return None
    return n if 0 < n <= 60000 else None      # extractor's implausible ceiling


# A NUMBER BESIDE AN EMPLOYEE NOUN IS NOT ALWAYS THE NUMBER BEING CUT, and the
# two shapes where it is not are stated in the sentence right in front of it:
#
#   RETAINED   Atara, 2025-10-07: "impact approximately 29% of its current
#              employees, RETAINING approximately 15 employees" — 15 is who
#              stays. The editor excluded this filing for exactly that reason.
#   BASE       Geron, 2025-12-16: "a reduction in workforce of approximately
#              one-third OF ITS CURRENT approximately 260 employees" — 260 is
#              the pre-cut total, and the cut is a fraction of it.
#
# Both were read as cut counts by this parser until 2026-08-17, when the rolling
# measurement put them in its denominator and scored two filings the tracker is
# CORRECT not to hold as coverage misses. extractor.py already refuses derived
# counts by design; this is the same refusal reached one step earlier, at the
# point where the number is read rather than where it is stored.
#
# THE MARKER LIST IS DELIBERATELY NARROW and every entry was checked against the
# cut phrasings in the same corpus by running the parser with and without it and
# reading the four filings that moved. Two rules came out of that:
#
#   "of approximately" alone is NOT a marker — Elanco's "a global headcount
#   reduction OF APPROXIMATELY 300 employees" is a real cut count and the
#   commonest phrasing in the corpus.
#
#   "workforce of" is NOT a marker either, and it was in the first draft of this
#   list. It cost Cibus: "a reduction in WORKFORCE OF approximately 34" is a cut,
#   and the same three words appear in "retaining a workforce of 34", which is
#   not. The retention word carries the meaning; the noun phrase does not.
#
# Only possessive-current and explicit retention frames qualify.
_NOT_A_CUT_FRAME = re.compile(
    r"(?:retain(?:ing|s|ed)?|remaining|out\s+of(?:\s+its)?|"
    r"of\s+(?:its|the)\s+current|current(?:ly)?\s+(?:has|employs|employed)|"
    r"end\s+the\s+year\s+with)"
    r"[^.;]{0,30}$", re.I)
# How far back to look for the frame. One clause, not one sentence: a sentence
# may legitimately contain a retention clause AND a separate cut count.
_FRAME_LOOKBACK = 60


def _is_cut_count(section, match_start):
    """False when the figure at `match_start` is framed as retained or as the
    base of a proportional reduction rather than as the reduction itself."""
    return not _NOT_A_CUT_FRAME.search(
        section[max(0, match_start - _FRAME_LOOKBACK):match_start])


def candidate_counts(section):
    """Every headcount the section states LITERALLY, deduped, in order.

    Returns (counts, upper_bounds). A range contributes its LOWER bound to
    counts and its upper bound to upper_bounds, where it is suppressed rather
    than treated as a second figure.
    """
    found, uppers = [], set()
    for m in _RANGE.finditer(section):
        lo, hi = _to_int(m.group(1)), _to_int(m.group(2))
        if lo is None or hi is None or hi <= lo:
            continue
        uppers.add(hi)
        if lo not in found:
            found.append(lo)
    for rx in (_FORWARD, _REVERSE):
        for m in rx.finditer(section):
            n = _to_int(m.group(1))
            if n is None or n in uppers:
                continue
            if not _is_cut_count(section, m.start(1)):
                continue
            # The production guards, imported, not re-implemented.
            if extractor._percent_only_mention(n, section):
                continue
            if not extractor._count_in_text(n, section):
                continue
            if n not in found:
                found.append(n)
    return found, uppers


def parse(section):
    """(count, reason). count is None whenever the parser declines."""
    if section is None:
        return None, "no_item_2_05_section"
    counts, _ = candidate_counts(section)
    if not counts:
        if _PERCENT_ONLY_CLUE.search(section):
            return None, "percentage_stated_no_headcount"
        return None, "no_headcount_in_section"
    if len(counts) > 1:
        # THE WABASH RULE. Two or more distinct stated headcounts and the parser
        # declines rather than choosing or summing. Choosing is a coin flip on a
        # published number; summing is the Intuit hole.
        return None, f"ambiguous_multiple_counts:{','.join(str(c) for c in counts)}"
    return counts[0], "single_stated_count"


# ---------------------------------------------------------------- pre-check

HELD_WINDOW_DAYS = int(os.environ.get("D205_HELD_WINDOW_DAYS", "45"))


def already_held(company, filing_date):
    """Do we ALREADY hold an event for this employer, and how near the filing?

    The second cost lever: 23 of the 24 current gold-set matches arrived via
    WARN, ERM or news rather than the 8-K, so a pre-check before any extraction
    would skip them and save the call. Read-only, public API, no key.

    TWO ANSWERS, because they are not the same question and conflating them is
    how a cost lever quietly becomes a coverage cut:

      employer_year  do we hold ANY row for this employer in the filing year?
      near_date      ...whose own date is within HELD_WINDOW_DAYS of the filing?

    Each is True / False / None, and None means UNKNOWN — never a silent 'no'.
    """
    token = _first_token(company)
    if not token:
        return {"employer_year": None, "near_date": None}
    year = int((filing_date or "0")[:4] or 0)
    rows = []
    for y in (year, year + 1):
        url = (f"{SITE}/wp-json/layoffs/v1/query?" + urllib.parse.urlencode({
            "company": token, "years": str(y), "per_page": 100,
            "date_basis": "notice"}))
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                rows += json.loads(resp.read().decode("utf-8", "replace")).get("data", [])
        except Exception:
            return {"employer_year": None, "near_date": None}
    pat = re.compile(r"\b" + re.escape(token) + r"\b", re.I)
    named = [r for r in rows if pat.search(r.get("company_name") or "")]
    same_year = [r for r in named if (r.get("announcement_date") or
                                      r.get("layoff_date") or "")[:4] == str(year)]
    filed = _days(filing_date)
    near = False
    for r in named:
        d = _days(r.get("announcement_date") or r.get("layoff_date") or "")
        if d is not None and filed is not None and abs(d - filed) <= HELD_WINDOW_DAYS:
            near = True
            break
    return {"employer_year": bool(same_year), "near_date": near}


def _days(iso):
    """ISO date -> ordinal day. Returns None on anything unparseable."""
    try:
        y, m, d = (int(x) for x in (iso or "")[:10].split("-"))
        return datetime.date(y, m, d).toordinal()
    except (ValueError, TypeError):
        return None


_STOP = {"inc", "corp", "co", "ltd", "plc", "llc", "the", "group", "sa", "se",
         "ag", "holdings", "holding", "company", "corporation", "incorporated"}


def _first_token(name):
    for w in re.split(r"[^A-Za-z0-9]+", name or ""):
        if w and w.lower() not in _STOP:
            return w
    return (name or "").strip()


# ---------------------------------------------------------------- run

def probe(event, want_held=False):
    rec = {"filer": event["filer"], "filing_date": event["filing_date"],
           "accession": event["accession"], "gold_count": event["stated_job_count"],
           "match_decision": event["match_decision"]}
    acc = event["accession"]
    cik = str(int(event["cik"]))
    folder = acc.replace("-", "")
    index_url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/"
                 f"{acc}-index.htm")
    try:
        index_html = fetch(index_url)
    except Exception as exc:
        rec["bucket"] = "unknown"
        rec["reason"] = f"index_unreachable:{type(exc).__name__}"
        return rec
    hdr = parse_header(index_html, cik)
    rec["header_employer"] = hdr["employer"]
    rec["header_date"] = hdr["filing_date"]
    rec["header_items"] = hdr["items"]

    try:
        primary = strip_html(fetch(event["official_source_url"]))
    except Exception as exc:
        rec["bucket"] = "unknown"
        rec["reason"] = f"primary_unreachable:{type(exc).__name__}"
        return rec

    section = item_205_section(primary)
    count, reason = parse(section)
    rec["parsed_count"] = count
    rec["reason"] = reason
    rec["gold_in_primary_section"] = bool(
        section and extractor._count_in_text(event["stated_job_count"], section))
    rec["gold_in_primary_doc"] = extractor._count_in_text(
        event["stated_job_count"], primary)

    if count is not None:
        rec["bucket"] = ("resolved_correct" if count == event["stated_job_count"]
                         else "resolved_wrong")
    else:
        # A refusal is CORRECT when the stated count is not literally in the
        # primary document — the pipeline as designed cannot and must not
        # produce it. Split further: is it in an EX-99 exhibit (a fetch problem,
        # fixable without a model) or nowhere (a derived count, e.g. Wabash)?
        if rec["gold_in_primary_doc"]:
            rec["bucket"] = "unresolved_needs_model"
        else:
            found_in, ex_count, ex_reason = None, None, None
            for label, url in exhibit_urls(index_html, event["official_source_url"]):
                try:
                    ex = strip_html(fetch(url))
                except Exception:
                    continue
                if extractor._count_in_text(event["stated_job_count"], ex):
                    found_in = label
                    # Would the SAME parser recover it from the exhibit? The
                    # exhibit is a press release with no item heading to anchor
                    # on, so this measures the cost of losing the structure that
                    # is the whole reason a deterministic path works at all.
                    ex_count, ex_reason = parse(ex)
                    break
            if found_in:
                rec["bucket"] = "needs_exhibit"
                rec["exhibit"] = found_in
                rec["exhibit_parsed_count"] = ex_count
                rec["exhibit_reason"] = ex_reason
                rec["exhibit_correct"] = ex_count == event["stated_job_count"]
            else:
                rec["bucket"] = "correctly_refused"

    if want_held:
        rec["already_held"] = already_held(event["filer"], event["filing_date"])
    return rec


def run():
    gold = json.load(open(GOLDSET))
    events = gold["reference_events"]
    only = os.environ.get("D205_ONLY", "all")
    if only == "misses":
        events = [e for e in events if e["match_decision"] != "matched"]
    elif only == "matched":
        events = [e for e in events if e["match_decision"] == "matched"]
    want_held = bool(os.environ.get("D205_HELD"))

    results = []
    for i, e in enumerate(events, 1):
        rec = probe(e, want_held=want_held)
        results.append(rec)
        print(f"[{i}/{len(events)}] {e['filer'][:38]:38s} gold={e['stated_job_count']:>6} "
              f"parsed={str(rec.get('parsed_count')):>6}  {rec['bucket']:<22} "
              f"{rec['reason'][:60]}", flush=True)

    print("\n" + "=" * 78)
    print("CONFUSION MATRIX — deterministic Item 2.05 parser, no model")
    print("=" * 78)
    order = ["resolved_correct", "resolved_wrong", "correctly_refused",
             "needs_exhibit", "unresolved_needs_model", "unknown"]
    tally = {k: sum(1 for r in results if r["bucket"] == k) for k in order}
    for k in order:
        print(f"  {tally[k]:>3}  {k}")
    n = len(results)
    resolved = tally["resolved_correct"] + tally["resolved_wrong"]
    print()
    if resolved:
        print("  PRECISION (of what it resolves): "
              + format_interval(tally["resolved_correct"], resolved))
    print("  RECALL (deterministic path alone): "
          + format_interval(tally["resolved_correct"], n))
    correct = tally["resolved_correct"] + tally["correctly_refused"]
    print("  correct behaviours (resolved-right + rightly-refused): "
          + format_interval(correct, n))

    ex = [r for r in results if r["bucket"] == "needs_exhibit"]
    if ex:
        ok = sum(1 for r in ex if r.get("exhibit_correct"))
        bad = sum(1 for r in ex if r.get("exhibit_parsed_count") is not None
                  and not r.get("exhibit_correct"))
        print(f"\n  EX-99.1 VARIANT: of the {len(ex)} whose count lives only in the "
              f"exhibit, the same parser run over the exhibit body resolves "
              f"{ok + bad} and gets {ok} right, {bad} WRONG:")
        for r in ex:
            print(f"    {r['filer'][:32]:32s} exhibit={r.get('exhibit')} "
                  f"parsed={r.get('exhibit_parsed_count')} vs {r['gold_count']}  "
                  f"{str(r.get('exhibit_reason'))[:56]}")

    wrong = [r for r in results if r["bucket"] == "resolved_wrong"]
    if wrong:
        print("\n  WRONG — named individually, these are the ones that bite later:")
        for r in wrong:
            print(f"    {r['filing_date']} {r['filer'][:34]:34s} parsed {r['parsed_count']}"
                  f" vs stated {r['gold_count']}")

    if want_held:
        print("\n  PRE-CHECK — would a 'do we already hold this?' test skip the candidate,")
        print("  and would skipping it have been RIGHT? A skip is right only when the")
        print("  gold set adjudicated this filing as an event we already hold (matched).")
        for kind, label in (("employer_year", f"employer + filing year"),
                            ("near_date", f"employer + within {HELD_WINDOW_DAYS}d")):
            skip = [r for r in results if (r.get("already_held") or {}).get(kind) is True]
            unk = sum(1 for r in results
                      if (r.get("already_held") or {}).get(kind) is None)
            right = sum(1 for r in skip if r["match_decision"] == "matched")
            print(f"    {label:<32} skips {len(skip):>2}/{n}  "
                  f"of which WRONGLY {len(skip) - right} (a real event dropped unread)"
                  f"{f'  [{unk} UNKNOWN]' if unk else ''}")

    out = os.environ.get("D205_OUT")
    if out:
        with open(out, "w") as fh:
            json.dump({"n": n, "tally": tally, "results": results}, fh, indent=1)
        print(f"\nwrote {out}")
    return results


if __name__ == "__main__":
    run()
