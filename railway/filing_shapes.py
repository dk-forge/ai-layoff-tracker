"""Shapes a filing-derived row can take that are NOT the filer's own, current
headcount. Pure functions, stdlib only, ONE definition.

Imported by two layers that must agree: the ingest gate in
`extractor.finalize_extraction` (refuses the row before it is posted) and the
live invariant `data_integrity.FilingShapeInvariant` (scans what is already
published). A rule that lived in only one of them would let the other drift,
which is how the 2026-08 Applied Aerospace shape got an ingest guard on
2026-08-13 and stayed live in the published data for a month.

THE THREE INSTANCES THIS IS WRITTEN FROM (docs/findings-july-august-2026-us-accuracy.md):

  * Row 176990, 20,000 jobs, "Aeternum Health". A Form 10-style 8-K quoting a
    federal agency's own press language inside its RISK FACTORS: "HHS announced
    that it intends to reduce OUR workforce by approximately 10,000". The
    extractor bound "our" to the registrant, a shell company. The row said so
    itself: announcement_date 2025-03-27, layoff_date 2026-07-07, 467 days
    apart. An Item 2.05 8-K is filed within four business days of the
    commitment, so a filing's OWN event cannot have been announced a year
    before the filing's effective date.
  * Row 177216, 4,320 jobs, "Applied Aerospace & Defense". $4,320K of
    "integration and restructuring costs" in an earnings-release table, in
    thousands, with no headcount anywhere in the filing. The number is in the
    text; it is not a count of anything.
  * Row 176490, 3,500 jobs, "Aon plc", live today: announcement_date 2014-04-01
    against a layoff_date of 2020-05-12, 2,233 days apart, read out of an
    EX-99.4 exhibit.

And one news shape recorded here as a WARN-level tripwire, never a refusal:
rows 178667 and 177173 (Paramount, 4,500 and 2,500) store a COUNTY ECONOMIC
IMPACT PROJECTION ("the merger could cost about 4,500 film and TV jobs ...
according to a new report issued by Los Angeles County") as an employer
announcement. Projection language is a hint about a row, not proof against it,
so it is printed and counted, and it never decides anything on its own.
"""
from __future__ import annotations

import re
from datetime import date

#: Announcement-to-effective lead, in days, beyond which an 8-K row is REFUSED.
#: Chosen from the live distribution of the 252 8-K rows that carry both dates
#: (measured 2026-09-16): p50 0, p90 41, p95 120, p99 292; seven rows exceed
#: 180 and one exceeds 365. Every row over 300 that has been read is wrong (Aon
#: 2,233; Aeternum 467 before it was trashed), and the longest span a filing
#: plausibly states for its own event is a plant closure announced in May for
#: year end (Koppers, 237). 365 is the first round number no legitimate row
#: reaches, and Item 2.05's four-business-day filing rule makes a year-old
#: announcement someone else's event by construction.
MAX_8K_LEAD_DAYS = 365

#: Above this the row is stored and NAMED for adjudication: the 181-365 band
#: holds legitimate year-end closures beside rows that turned out to be a
#: third party's figure (a biotech quoting NIH's 1,500 at 292 days). Quiet and
#: broken are different states; this is the quiet one.
REVIEW_8K_LEAD_DAYS = 180

RISK_FACTORS_SECTION = "risk_factors"
EXHIBIT_SECTION = "exhibit"

_ITEM_HEADING = re.compile(r"\bItem\s+(\d\.\d\d)\b")
# The heading form only: title case, not inside quotes, and not the reference
# "see the Risk Factors section of our Form 10-K" that forward-looking
# boilerplate puts in every filing. A heading is followed by another heading or
# by the first risk ("Risks Related to our Company", "Summary of Risk Factors").
_RISK_HEADING = re.compile(
    r"(?<![\"'“‘(])\bRisk\s+Factors\b(?![\"'”’)])"
    r"(?!\s+(?:section|of|in|under|described|discussed|set\s+forth|contained|"
    r"included|and|or|that|which|for)\b)")


def filing_section(text, idx):
    """Which part of a stripped filing the character at `idx` sits in.

    Returns `"item_2.05"`-style for the nearest preceding 8-K item heading,
    `RISK_FACTORS_SECTION` when a Risk Factors heading is nearer than any item
    heading, or None when nothing that looks like a heading precedes `idx`.
    Nearest-preceding is the whole rule: a risk-factor block inside Item 2.01
    (a reverse merger's Form 10 information) is still a risk-factor block.
    """
    if not text or idx is None or idx < 0:
        return None
    # `m.start() <= idx`, not `text[:idx]`: the collector anchors its window on
    # the first layoff keyword, and one of those keywords IS "item 2.05". A
    # heading that begins exactly at idx governs idx.
    item = None
    for m in _ITEM_HEADING.finditer(text):
        if m.start() > idx:
            break
        item = m
    risk = None
    for m in _RISK_HEADING.finditer(text):
        if m.start() > idx:
            break
        risk = m
    if risk is not None and (item is None or risk.start() > item.start()):
        return RISK_FACTORS_SECTION
    if item is not None:
        return f"item_{item.group(1)}"
    return None


def _as_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def lead_days(announcement_date, layoff_date):
    """layoff_date minus announcement_date in days, or None if either is unusable."""
    a, b = _as_date(announcement_date), _as_date(layoff_date)
    if a is None or b is None:
        return None
    return (b - a).days


def filing_lead_verdict(announcement_date, layoff_date, filing_date=None,
                        refuse_after=MAX_8K_LEAD_DAYS, review_after=REVIEW_8K_LEAD_DAYS):
    """("refuse" | "review" | "ok" | None, days).

    Judged on the longer of two leads: announcement to effective date, and
    announcement to the FILING date when one is known. The second is the
    sharper tell at ingest (a filing is about something that just happened) and
    the first is the only one a published row still carries. None means the
    row does not carry the dates to judge, which is not a pass.
    """
    spans = [d for d in (lead_days(announcement_date, layoff_date),
                         lead_days(announcement_date, filing_date)) if d is not None]
    if not spans:
        return None, None
    days = max(spans)
    if days > refuse_after:
        return "refuse", days
    if days > review_after:
        return "review", days
    return "ok", days


_SEP = r"[.,    ]"


def _count_variants(n):
    grouped = f"{n:,}"
    variants = {str(n), grouped, grouped.replace(",", " "), grouped.replace(",", "."),
                grouped.replace(",", " "), grouped.replace(",", " "),
                grouped.replace(",", " ")}
    if n % 1000 == 0 and n >= 1000:
        variants.update({f"{n // 1000}k", f"{n // 1000}K"})
    return sorted(variants, key=len, reverse=True)


_NUMBER_TOKEN = r"\(?[\d][\d,.]*\)?%?"

#: A units declaration governs every figure in the table it heads. Row 177216's
#: 4,320 sits 424 characters after "(in thousands, except percentages)" in an
#: Adjusted EBITDA reconciliation, so the filing states plainly that the number
#: is not a count of anything. Looked for within UNITS_REACH characters before
#: the occurrence, which is about one stripped table's worth.
_UNITS_HEADER = re.compile(r"\(\s*(?:amounts?\s+)?in\s+(?:thousands|millions|billions)\b",
                           re.I)
UNITS_REACH = 1500

#: What a headcount looks like beside its number. A units header CANNOT bind an
#: occurrence that sits next to one of these: a press release routinely declares
#: units for its financial tables and then states a real headcount in prose, and
#: refusing that row would be the guard sharing its target's blind spot.
_PEOPLE_NOUN = re.compile(
    r"\b(?:employees?|positions?|roles?|jobs?|workers?|staff(?:ers)?|colleagues|"
    r"personnel|associates|people|team\s+members?|headcount|workforce|FTEs?)\b", re.I)


def count_only_as_cost(job_count, text):
    """True when every occurrence of the count in `text` is a money or table figure.

    An occurrence is BOUND when any of four things is true:

      * a currency sign or code sits against it ("$4,320", "USD 500");
      * a scale word or percent sign follows it ("4,320K", "4.3 million", "12%");
      * it sits in a run of bare numbers with another number on BOTH sides,
        which is what a financial table looks like once the HTML is stripped:
        "costs (2) 2,047 1,336 4,320 3,377";
      * a units declaration heads the table it sits in ("(in thousands, except
        percentages)") AND no people-noun sits beside the occurrence. Row
        177216's 4,320 is 424 characters past exactly that header, in an
        Adjusted EBITDA reconciliation, and the filing states no headcount
        anywhere.

    A count that appears even once unbound is not this shape and this returns
    False; a count that does not appear at all is the verbatim guard's
    business, and this returns False for that too.
    """
    try:
        n = int(job_count)
    except (TypeError, ValueError):
        return False
    if n <= 0 or not text:
        return False
    alts = "|".join(re.escape(v) for v in _count_variants(n))
    exact = re.compile(rf"(?<![\d.,]){'(?:' + alts + ')'}(?![\d])(?!{_SEP}\d{{3}})")
    seen = False
    for m in exact.finditer(text):
        seen = True
        before = text[max(0, m.start() - 12):m.start()]
        after = text[m.end():m.end() + 14]
        currency = (re.search(r"[$€£¥]\s*$", before)
                    or re.search(r"\b(?:USD|EUR|GBP|US\$|C\$)\s*$", before))
        scale = re.match(r"\s*(?:%|percent\b|[kK]\b|thousand|million|billion|mm\b|bn\b)", after)
        table = (re.search(rf"{_NUMBER_TOKEN}\s{{1,3}}$", before)
                 and re.match(rf"\s{{1,3}}(?:{_NUMBER_TOKEN}|[—–-])", after))
        neighbourhood = text[max(0, m.start() - 45):m.end() + 45]
        units = (_UNITS_HEADER.search(text[max(0, m.start() - UNITS_REACH):m.start()])
                 and not _PEOPLE_NOUN.search(neighbourhood))
        if not (currency or scale or table or units):
            return False
    return seen


#: A number in a sentence shaped like this is somebody's forecast about a
#: region, not an employer saying what it will do. WARN-level: printed and
#: counted, never a refusal on its own, because "could cut 500 jobs" is also
#: how an employer's own announcement is sometimes reported.
_PROJECTION_PHRASES = (
    r"\bcould\s+(?:cost|lose|result\s+in|see|eliminate|put)\b",
    r"\bprojected\b|\bprojections?\b|\bforecasts?\b",
    r"\beconomic\s+(?:impact|analysis|report|study)\b",
    r"\baccording\s+to\s+(?:a|an)\s+(?:new\s+)?(?:report|analysis|study|estimate)\b",
    r"\b(?:county|region|regional|state|city|metro)\b[^.;]{0,60}\b(?:could|would|may|might)\b",
    r"\bwould\s+accelerate\b|\bripple\s+effects?\b|\bindirect\s+jobs?\b",
)
_PROJECTION_RX = re.compile("|".join(_PROJECTION_PHRASES), re.I)


def projection_language(text):
    """The projection phrases found in `text`, in order, deduplicated."""
    if not text:
        return []
    out = []
    for m in _PROJECTION_RX.finditer(text):
        phrase = re.sub(r"\s+", " ", m.group(0)).strip().lower()
        if phrase not in out:
            out.append(phrase)
    return out
