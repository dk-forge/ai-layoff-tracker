#!/usr/bin/env python3
"""ROLLING recall — a coverage figure whose denominator ages with the data.

WHAT THIS ADDS TO WHAT ALREADY EXISTED (read this before touching it)
---------------------------------------------------------------------
`railway/recall_goldset.py` measures the FROZEN, editor-adjudicated SEC Item
2.05 gold set (57 events, 2025-07-01..2026-06-30). That set answers "have we
LOST events an editor confirmed we held?" — it is a retention tripwire, its
denominator cannot move between runs, and that immovability is the whole point
of its floor. Nothing here replaces it, weakens it, or re-implements it. It
still runs weekly and it still owns `MATCHED_FLOOR`.

What it CANNOT answer is "what is our coverage NOW", because its window closed
on 2026-06-30 and extending it costs a human afternoon of adjudication. So the
one figure the owner is asked for most — "we cover X%" — has been ageing with
somebody's memory rather than with the data. That is the same defect
`benchmark_freshness.py` exists to catch one floor down, and the hand-maintained
comparison file it watches is 24 days stale as this is written.

THIS MODULE MEASURES A ROLLING WINDOW, AUTOMATICALLY, AND CAN ADVANCE ITSELF.
Same primary index, same selection rule, no editor in the loop — and because
there is no editor in the loop it reports a BAND, never a point (see below).

WHY SEC ITEM 2.05 AND NOT SOMETHING BIGGER
-------------------------------------------
Almost all recall work has to sample, because the true universe is unknowable.
Item 2.05 is the rare exception: every US public company recording a material
charge for exit or disposal activities files an 8-K carrying that structured
item code in its SGML header, and EDGAR full-text search enumerates them for a
period EXACTLY. So the denominator is not a sample of the universe, it IS the
universe for that slice — free, keyless, primary, and re-derivable by anyone who
repeats the query. A figure computed this way is falsifiable, which is the only
kind worth publishing.

It is emphatically NOT "the tracker's recall". It describes US public companies
filing Item 2.05 with a stated headcount. It says nothing about private
employers, non-US employers, WARN-only or news-only events. Quoting it as
overall coverage would be the exact overreach the gold-set manifest forbids.

THE BAND, AND WHY THERE IS NO SINGLE NUMBER
--------------------------------------------
On 2026-08-01 the deterministic alias/window matcher scored 31 of 57 against the
editor's 24 — twelve points of recall the machine awarded itself, on a Hormel
Georgia WARN filed ten weeks before the announcement it was meant to represent,
an Italian composites maker for HP Inc, and Dow Jones for Dow. CLAUDE.md's rule
followed: a machine must not promote its own recall.

An automatic measurement has no editor, so it cannot be allowed to publish the
loose rule's number. It publishes both ends instead:

    CONFIRMED  name + window + the tracker row's job_count AGREES with the
               headcount stated in the filing. The count is the discriminator
               the 2026-08-01 false positives all failed: Dow Jones does not
               carry Dow's 800.
    PROPOSED   name + window only — the loose rule, which is what the editor
               was given to adjudicate and which over-accepts.

Recall is reported as [confirmed/denominator, (confirmed+proposed)/denominator].
The true value lies inside it as long as CONFIRMED admits no false positive and
PROPOSED misses no true one — both of which are CALIBRATED against the 57
adjudicated events by `tests/test_rolling_recall.py`, not asserted here. A band
is less quotable than a point and that is the correct trade: the point would be
a number nobody checked.

THREE STATES AT EVERY LEVEL, NEVER TWO
---------------------------------------
Per filing, after the deterministic parse:

    in_scope      an absolute headcount is stated in the Item 2.05 section and
                  the parser resolved it unambiguously -> denominator
    out_of_scope  the section states a percentage / a retained headcount and no
                  absolute cut count. extractor.py rejects derived counts by
                  design, so scoring these as misses would be measuring a
                  documented design decision -> excluded, and COUNTED as
                  excluded so the exclusion is visible
    undecidable   the parser declined (two distinct headcounts — the Wabash
                  rule), the count lives only in an EX-99.1 exhibit, or the
                  document could not be fetched -> UNKNOWN. Excluded from BOTH
                  numerator and denominator, listed by name, and never silently
                  dropped into either.

DO NOT "FIX" THE UNDECIDABLE SHARE BY PARSING THE EXHIBITS. The probe this
parser comes from measured what that costs: over EX-99.1 press-release bodies it
read GitLab's "2021 Employee Stock Purchase Plan" as a headcount of 2021 for a
350-person cut. The heading anchor is the hypothesis, not a convenience. An
honest UNKNOWN is worth more than a wrong denominator.

Per slice: measured / not_measurable / unknown. A slice that could not be
computed this run does NOT drop out of the report and is never averaged away.

THE SETTLE LAG
--------------
The window ends SETTLE_DAYS before today, and that lag is a fairness rule, not a
convenience. A filing made last Tuesday that we do not yet hold is ingest
latency, not a coverage gap, and counting it as a miss would measure the clock.
45 days clears the daily EDGAR cron plus a full rotation of the news paths.
It does NOT clear `backfill.rotating_month`, which re-verifies every month of
the last twelve within 120 days — so this figure is a LOWER bound in one further
respect: the sweep is still working on the newest months of every window.

COST: $0.00. EDGAR full-text search and the Archives are free and keyless; the
tracker's /query is a public read. No model is called on any path, and none
should ever be added — a measurement that spends money is a measurement that
gets switched off in a lean month.

USAGE
    python3 railway/rolling_recall.py             # measure, print, exit 0/2/3
    python3 railway/rolling_recall.py --write     # ...and commit the result
    python3 railway/rolling_recall.py --calibrate # score the matcher against
                                                  # the 57 adjudicated events

Env: RR_CACHE (EDGAR document cache dir), WP_SITE_URL, RR_WINDOW_END (pin the
window end for a reproducible re-run, YYYY-MM-DD).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recall_goldset import (PASS, FAIL, UNKNOWN, format_interval,  # noqa: E402
                            name_matches, wilson)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
# Committed for the same reason railway/headline_baseline.json is: the thing
# being measured changes without a commit, so a result that lives only in a
# runner is a result that resets every night and can never be shown to have
# aged.
MEASUREMENT_PATH = HERE / "rolling_recall_measurement.json"

UA = os.environ.get("EDGAR_USER_AGENT",
                    "AiLayoffTracker/1.0 (+https://asktherecruiter.com)")
SITE = (os.environ.get("WP_SITE_URL") or "https://asktherecruiter.com/blog").rstrip("/")
EFTS = "https://efts.sec.gov/LATEST/search-index"
SEC_DELAY = 0.15                 # under SEC's 10 req/s; we are in no hurry

# ---------------------------------------------------------------------------
# THE BOUNDS. Every one of these is a judgement; each says why it is that value.
# ---------------------------------------------------------------------------

# Twelve months, matching the frozen gold set's window length on purpose: the
# first run of this module covers exactly the adjudicated window, which is what
# makes the head-to-head calibration possible. It then advances on its own.
WINDOW_MONTHS = 12

# See THE SETTLE LAG above. Do not shorten this to make the figure feel current;
# that measures ingest latency and calls it coverage.
SETTLE_DAYS = 45

# Above this share of enumerated filings landing in `undecidable`, the slice
# reports UNKNOWN rather than a band: at that point the denominator is a small
# and possibly unrepresentative corner of the enumeration and the band would be
# describing the parser rather than the tracker. 0.40 is set above the 0.28
# measured on the adjudicated window (the parser declines on exhibit-only counts
# and on genuine ambiguity) with room for a bad fetch day, and below the point
# where more is unknown than known.
MAX_UNDECIDABLE_SHARE = 0.40

# Below this many in-scope filings there is no figure worth printing — a band
# over eight events is two events wide. UNKNOWN, not a number.
MIN_DENOMINATOR = 20

# Enumeration is the one step that must be complete or the denominator is a lie.
# If any month of the window fails to enumerate, the slice is UNKNOWN.
# (A partial enumeration would shrink the denominator and INFLATE recall, which
# is the direction a broken measurement must never fail in.)

# Refreshed weekly by rolling-recall.yml. Ceiling matches the real cadence — a
# 2-day ceiling on a weekly job is permanent noise that hides real breakage.
MAX_MEASUREMENT_AGE_DAYS = 9

# The loose rule's window, taken verbatim from the frozen manifest's
# `matching_rule` so the two measurements cannot drift apart in what they call
# "around the filing". An 8-K may follow a WARN by weeks and precede the
# effective date by months.
WINDOW_DAYS_BEFORE = 90
WINDOW_DAYS_AFTER = 270

# A tracker row counts as CONFIRMED when its job_count agrees with the filing's
# stated headcount. Exact agreement is required, with one deliberate exception:
# a WARN component row legitimately carries part of a multi-site total, so a row
# whose count is a strict part of the filing's is NOT confirmed and NOT
# rejected — it stays in PROPOSED, which is exactly what the band is for.
IN_SCOPE, OUT_OF_SCOPE, UNDECIDABLE = "in_scope", "out_of_scope", "undecidable"
CONFIRMED, PROPOSED, ABSENT = "confirmed", "proposed", "absent"

MEASURED, NOT_MEASURABLE = "measured", "not_measurable"


# ---------------------------------------------------------------------------
# window
# ---------------------------------------------------------------------------

def _month_start(d):
    return date(d.year, d.month, 1)


def _add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def window_for(today=None):
    """(start, end) — WINDOW_MONTHS whole calendar months, ending at the last
    month that closed at least SETTLE_DAYS ago.

    Whole months, because the enumeration is issued one month per request and a
    half month at either end would be a denominator nobody could re-derive.
    """
    today = today or date.today()
    pin = os.environ.get("RR_WINDOW_END")
    if pin:
        end = date(*(int(x) for x in pin.split("-")))
        return _add_months(_month_start(end), -(WINDOW_MONTHS - 1)), end
    cutoff = today - timedelta(days=SETTLE_DAYS)
    end_month = _add_months(_month_start(cutoff), -1) if cutoff.day < 28 \
        else _month_start(cutoff)
    # `end_month` is the first day of the last month wholly settled; the window
    # ends on its last day.
    end = _add_months(end_month, 1) - timedelta(days=1)
    start = _add_months(end_month, -(WINDOW_MONTHS - 1))
    return start, end


def months_in(start, end):
    out, cur = [], _month_start(start)
    while cur <= end:
        nxt = _add_months(cur, 1)
        out.append((cur, min(nxt - timedelta(days=1), end)))
        cur = nxt
    return out


# ---------------------------------------------------------------------------
# fetching
# ---------------------------------------------------------------------------

_CACHE = Path(os.environ.get("RR_CACHE")
              or (Path(os.environ.get("TMPDIR", "/tmp")) / "rolling-recall-cache"))
MAX_DOC_BYTES = 2_000_000


def _http(url, timeout=45):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "identity"})
    time.sleep(SEC_DELAY)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(MAX_DOC_BYTES).decode("utf-8", "replace")


def fetch_cached(url, http=None):
    """EDGAR is public and rate-limited; a re-run must not re-hammer it.

    The cache is keyed on the URL and holds immutable Archives documents, so it
    can never serve a stale answer: an accession's document does not change.
    """
    http = http or _http
    _CACHE.mkdir(parents=True, exist_ok=True)
    path = _CACHE / urllib.parse.quote(url, safe="")[-180:]
    if path.exists():
        return path.read_text(encoding="utf-8")
    body = http(url)
    path.write_text(body, encoding="utf-8")
    return body


# ---------------------------------------------------------------------------
# 1. ENUMERATION — the closed set
# ---------------------------------------------------------------------------

EXIT_COST_ITEM = "2.05"
# One request per calendar month, exactly as the frozen manifest's step 1
# describes, so the two enumerations are the same query at different dates.
ENUM_QUERY = '"Item 2.05"'
EFTS_PAGE = 100
# EFTS refuses `from` beyond 10000 and a month of Item 2.05 filings runs to
# tens, not thousands. If a month ever exceeds this the enumeration is NOT
# complete and the slice must go UNKNOWN rather than silently truncate — the
# pagination cap that hid 33 gold events for a year (TECHLOG 2026-08-01) is
# exactly this failure, and it is asserted rather than warned about.
MAX_HITS_PER_MONTH = 900


def enumerate_month(start, end, http=None):
    """Every 8-K accession in [start, end] whose STRUCTURED items array carries
    2.05. Raises on any transport fault — a partial enumeration inflates recall.

    The item code is the filer's own, out of the SGML header, never a text
    match: the text query is only the retrieval handle, and the structured array
    is the selection rule.
    """
    http = http or _http
    out, frm = {}, 0
    while True:
        url = EFTS + "?" + urllib.parse.urlencode({
            "q": ENUM_QUERY, "forms": "8-K", "dateRange": "custom",
            "startdt": start.isoformat(), "enddt": end.isoformat(), "from": frm})
        payload = json.loads(http(url))
        hits = (payload.get("hits") or {}).get("hits") or []
        total = (((payload.get("hits") or {}).get("total")) or {}).get("value") or 0
        if total > MAX_HITS_PER_MONTH:
            raise RuntimeError(
                f"{start:%Y-%m}: {total} hits exceeds MAX_HITS_PER_MONTH "
                f"({MAX_HITS_PER_MONTH}) — the enumeration would be truncated and "
                f"a truncated denominator INFLATES recall. Split the window.")
        for hit in hits:
            src = hit.get("_source") or {}
            if EXIT_COST_ITEM not in (src.get("items") or []):
                continue
            accession, _, doc = (hit.get("_id") or "").partition(":")
            if not accession or not doc:
                continue
            cik = (src.get("ciks") or [""])[0]
            out[accession] = {
                "accession": accession,
                "cik": cik,
                "filer": (src.get("display_names") or [""])[0],
                "filing_date": src.get("file_date"),
                "sec_items": src.get("items") or [],
                "primary_doc_url": _archive_url(cik, accession, doc),
            }
        frm += EFTS_PAGE
        if frm >= total or not hits:
            break
    return list(out.values())


def _archive_url(cik, accession, doc):
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik or 0)}/"
            f"{accession.replace('-', '')}/{doc}")


def clean_filer(name):
    """'DOW INC.  (DOW)  (CIK 0001751788)' -> 'DOW INC.'

    EFTS display names glue the tickers and the CIK onto the name. Taken
    VERBATIM up to that glue and never reconstructed: a reference set that
    constructs its query terms instead of taking them from the source
    under-reports, and it under-reports in the direction that looks like a
    finding (TECHLOG 2026-08-13).

    Two EDGAR-OWN conventions are also removed, and only these two, because they
    are artifacts of the index rather than parts of the company's name:
    `/NEW/`-style state-of-incorporation and re-registration markers, which
    appear on no filing's letterhead and on no tracker row. Leaving them in cost
    International Paper and Goodyear their match during calibration.
    """
    # ALL trailing groups, repeatedly. EFTS emits BOTH the tickers and the CIK
    # ("Elanco Animal Health Inc  (ELAN)  (CIK 0001739104)"), and a single
    # non-greedy strip leaves "(ELAN)" glued on — which tokenises as a fourth
    # word and cost Elanco its match in the first full run, a row we hold at the
    # exact count on the exact date.
    out = (name or "").strip()
    while True:
        stripped = re.sub(r"\s*\([^()]*\)\s*$", "", out).strip()
        if stripped == out:
            break
        out = stripped
    out = re.sub(r"\s*/[A-Za-z]{2,4}/\s*$", " ", out)
    return out.strip()


def retrieval_term(alias):
    """The literal leading substring to send to `/query?company=`.

    RETRIEVAL AND MATCHING ARE SEPARATE OBJECTS, and this is the whole reason
    the 2026-08-13 WARN measurement moved 79 -> 99 without a line of the
    pipeline changing. `/query?company=` is a substring LIKE, and the stored
    name can be LONGER than the filer name ("STARBUCKS CORP" finds nothing while
    "Starbucks Corporation" sits in the table) or SHORTER than it ("ZoomInfo
    Technologies Inc." finds nothing while the row says "ZoomInfo"). Both were
    observed in calibration, in the same run.

    A substring query cannot straddle that, so retrieval sends the SHORTEST
    distinctive leading run — the first word of the name — and the PREFIX rule
    (name_matches) does all the deciding afterwards. Widening retrieval cannot
    create a false match; it can only stop hiding a true one. What it CAN do is
    bury a true row past the page cap, and `query_rows` refuses to score a
    capped result rather than calling it absent.
    """
    for w in re.split(r"[\s,]+", clean_filer(alias)):
        bare = re.sub(r"[^A-Za-z0-9&]", "", w).lower()
        if bare and bare not in _RETRIEVAL_SUFFIXES:
            return w.strip(".,")
    return clean_filer(alias)


# Stop at the first corporate suffix: everything after it is form, not identity,
# and it is exactly what the stored name spells differently ("CORP" vs
# "Corporation"). Deliberately small — an over-eager list starts truncating
# "Group 1 Automotive" to "Group".
_RETRIEVAL_SUFFIXES = {"inc", "inc.", "corp", "corporation", "co", "company",
                       "ltd", "limited", "llc", "lp", "plc", "nv", "sa", "se",
                       "ag", "holdings", "holding", "incorporated", "&"}


# ---------------------------------------------------------------------------
# 2. SCOPE — the deterministic parse, three ways
# ---------------------------------------------------------------------------

def _parser():
    """Imported, never re-implemented. `sec_205_deterministic_probe` owns the
    Item 2.05 section anchor and the count rules, and it in turn imports
    extractor's `_count_in_text` / `_percent_only_mention`, so a number this
    module calls stated is stated by the SAME function the production path uses.
    This repo has been bitten repeatedly by a second copy of a rule drifting
    from the first.
    """
    import sec_205_deterministic_probe as d205
    return d205


_EX99 = re.compile(r"ex-?99", re.I)


def has_exhibit(filing, fetch=None):
    """True/False/None — does this accession carry an EX-99 exhibit?

    True/False/None and not a bool, because the answer decides whether a filing
    with no headcount in its Item 2.05 section is OUT OF SCOPE or UNKNOWN, and
    a failed index fetch must land in UNKNOWN rather than quietly in either.
    """
    fetch = fetch or fetch_cached
    try:
        index = fetch(filing["primary_doc_url"].rsplit("/", 1)[0] + "/")
    except Exception:                              # noqa: BLE001
        return None
    return bool(_EX99.search(index))


def classify(filing, fetch=None, index_fetch=None):
    """(scope, count, reason) for one enumerated filing. Never raises.

    THE HARD CASE IS "no headcount in the section", and it is 157 of the 215
    filings in the first window — so how it is resolved decides the whole
    measurement. It covers two genuinely different filings:

      * an Item 2.05 that quantifies only the CHARGE ("a pre-tax charge of
        $42 million") and never the headcount. There is no count in the filing
        at all, extractor.py would store nothing from it, and scoring it as a
        recall miss would be scoring a documented design decision.
      * an Item 2.05 whose count is stated only in the EX-99.1 press release —
        eight of the frozen gold set are exactly this.

    They are separated by the ONE deterministic fact available without reading
    the exhibit: whether an EX-99 exhibit exists on the accession. No exhibit
    and no count in the section means no count anywhere -> out of scope. An
    exhibit present means the count MIGHT be in it and this parser must not go
    and look (the GitLab "2021 Employee Stock Purchase Plan" reading) -> UNKNOWN.

    Measured on 2025-07..2026-06: 101 with no exhibit, 48 with one, 8 whose
    index could not be read. That is what keeps the UNKNOWN share at 29% rather
    than the 76% a rule that lumped all 157 together produced.
    """
    d205 = _parser()
    fetch = fetch or fetch_cached
    try:
        markup = fetch(filing["primary_doc_url"])
    except Exception as exc:                       # noqa: BLE001 — any transport fault
        return UNDECIDABLE, None, f"unfetchable:{type(exc).__name__}"
    section = d205.item_205_section(d205.strip_html(markup))
    count, reason = d205.parse(section)
    if count is not None:
        return IN_SCOPE, count, reason
    if reason == "percentage_stated_no_headcount":
        # A documented design decision of extractor.py, not a miss. Excluded
        # exactly as the hand-adjudicated set excluded Intel, Atara and Geron.
        return OUT_OF_SCOPE, None, reason
    if reason == "no_headcount_in_section":
        exhibit = has_exhibit(filing, fetch=index_fetch or fetch)
        if exhibit is False:
            return OUT_OF_SCOPE, None, "no_headcount_anywhere_no_exhibit"
        if exhibit is None:
            return UNDECIDABLE, None, "exhibit_index_unreadable"
        return UNDECIDABLE, None, "headcount_may_be_exhibit_only"
    # What remains is ambiguity (the Wabash rule: two distinct stated headcounts
    # and the parser declines rather than choosing or summing) and a missing
    # section. Both UNKNOWN.
    return UNDECIDABLE, None, reason


# ---------------------------------------------------------------------------
# 3. MATCHING — confirmed / proposed / absent
# ---------------------------------------------------------------------------

def _iso_ord(value):
    try:
        return date(*(int(x) for x in str(value)[:10].split("-"))).toordinal()
    except (ValueError, TypeError):
        return None


# A one-word retrieval term is deliberately broad, so it can return more rows
# than one page. Paginate to this many pages and then REFUSE: an unfetched tail
# is a row we cannot see, and calling that "absent" is precisely the pagination
# cap that hid 33 gold events for a year (TECHLOG 2026-08-01). Raising makes it
# unreachable — UNKNOWN — instead.
MAX_QUERY_PAGES = 6
QUERY_PER_PAGE = 100


def query_rows(alias, fetch=None):
    """Public read of /query for one alias, all pages. Raises on a transport
    fault OR on an exhausted page budget, so the caller scores the filing
    UNREACHABLE rather than absent."""
    fetch = fetch or _http
    rows, page, total = [], 1, None
    while page <= MAX_QUERY_PAGES:
        url = (SITE + "/wp-json/layoffs/v1/query?" + urllib.parse.urlencode({
            "company": alias, "per_page": QUERY_PER_PAGE, "page": page,
            "date_basis": "notice", "cb": os.urandom(5).hex()}))
        payload = json.loads(fetch(url)) or {}
        batch = payload.get("data") or []
        total = payload.get("total") if total is None else total
        rows += batch
        if len(batch) < QUERY_PER_PAGE:
            return rows
        page += 1
    raise RuntimeError(
        f"'{alias}' returns {total} rows, past the {MAX_QUERY_PAGES}-page budget — "
        f"the tail is unread, and an unread tail must not be scored as absent")


def names_align(filer, stored):
    """Token-prefix in EITHER direction.

    `name_matches` is one-directional — the stored name must start with every
    token of the alias — and that is right for the frozen set, whose aliases a
    human wrote to be the shorter side ("ZoomInfo" for ZoomInfo Technologies
    Inc.). Nothing writes aliases here, so the filer name arrives at its full
    EDGAR length and the stored name may be either longer ("Starbucks
    Corporation") or shorter ("ZoomInfo"). A one-directional rule silently drops
    the second case, which is how ZoomInfo's 600 — a row we hold, at the exact
    count, on the exact filing date — scored as a miss in the first calibration.

    Direction-blindness DOES over-accept: "Dow Inc." aligns with a row called
    "Dow Jones". That is deliberate and it is contained, because this rule only
    ever decides PROPOSED, which is the upper end of the band and is SUPPOSED to
    over-accept. CONFIRMED additionally requires the count to agree, and the
    calibration run scores exactly that: zero of the editor's rejected
    candidates reach CONFIRMED.

    `name_matches` itself is imported and left alone — the frozen measurement
    depends on its exact semantics.
    """
    return name_matches(filer, stored) or name_matches(stored, filer)


def match(filing, rows):
    """(tier, event_ids) — CONFIRMED, PROPOSED or ABSENT.

    CONFIRMED needs the count to agree. That is the discriminator every
    2026-08-01 false positive failed, and it is why this tier can be published
    without an editor having looked at it.
    """
    filed = _iso_ord(filing["filing_date"])
    alias = clean_filer(filing["filer"])
    lo, hi = filed - WINDOW_DAYS_BEFORE, filed + WINDOW_DAYS_AFTER
    proposed, confirmed = [], []
    for row in rows:
        if not names_align(alias, row.get("company_name") or ""):
            continue
        when = _iso_ord(row.get("announcement_date") or row.get("layoff_date"))
        if when is None or not (lo <= when <= hi):
            continue
        eid = row.get("event_id") if row.get("event_id") is not None else row.get("id")
        proposed.append(eid)
        if row.get("job_count") == filing.get("stated_job_count"):
            confirmed.append(eid)
    if confirmed:
        return CONFIRMED, sorted(set(confirmed))
    if proposed:
        return PROPOSED, sorted(set(proposed))
    return ABSENT, []


# ---------------------------------------------------------------------------
# 4. THE SLICE
# ---------------------------------------------------------------------------

def measure_sec_item_205(today=None, http=None, doc_fetch=None, api_fetch=None,
                         progress=None):
    """The whole slice, as a dict. Never raises: a fault becomes UNKNOWN."""
    start, end = window_for(today)
    slice_ = {
        "key": "sec_item_205_us",
        "label": "US SEC 8-K Item 2.05 (exit/disposal costs) with a stated headcount",
        "denominator_basis": "closed_enumeration_primary_regulator_index",
        "window": {"from": start.isoformat(), "to": end.isoformat(),
                   "date_field": "EDGAR file_date"},
        "enumeration_query": ENUM_QUERY,
        "settle_days": SETTLE_DAYS,
    }
    # --- enumerate
    filings = []
    try:
        for m_start, m_end in months_in(start, end):
            filings += enumerate_month(m_start, m_end, http=http)
            if progress:
                progress(f"enumerated {m_start:%Y-%m}: {len(filings)} cumulative")
    except Exception as exc:                       # noqa: BLE001
        slice_.update(state=UNKNOWN, detail=(
            f"enumeration failed ({type(exc).__name__}: {exc}) — a PARTIAL "
            f"enumeration shrinks the denominator and INFLATES recall, so no "
            f"figure is reported. This is not a coverage regression"))
        return slice_
    slice_["enumerated_filings"] = len(filings)

    # --- scope
    in_scope, out_of_scope, undecidable = [], [], []
    for f in filings:
        scope, count, reason = classify(f, fetch=doc_fetch)
        f["stated_job_count"], f["scope_reason"] = count, reason
        {IN_SCOPE: in_scope, OUT_OF_SCOPE: out_of_scope,
         UNDECIDABLE: undecidable}[scope].append(f)
    slice_.update(in_scope=len(in_scope), out_of_scope=len(out_of_scope),
                  undecidable=len(undecidable))
    slice_["undecidable_filings"] = [
        {"accession": f["accession"], "filer": clean_filer(f["filer"]),
         "filing_date": f["filing_date"], "why": f["scope_reason"]}
        for f in sorted(undecidable, key=lambda x: x["filing_date"] or "")]

    share = len(undecidable) / len(filings) if filings else 1.0
    if share > MAX_UNDECIDABLE_SHARE:
        slice_.update(state=UNKNOWN, detail=(
            f"{len(undecidable)} of {len(filings)} enumerated filings could not be "
            f"scoped deterministically ({share:.0%}, ceiling "
            f"{MAX_UNDECIDABLE_SHARE:.0%}) — the remaining denominator is too small a "
            f"corner of the enumeration to describe the tracker. UNKNOWN, not a "
            f"regression"))
        return slice_
    if len(in_scope) < MIN_DENOMINATOR:
        slice_.update(state=UNKNOWN, detail=(
            f"only {len(in_scope)} in-scope filings (minimum {MIN_DENOMINATOR}) — a "
            f"band over that few events is wider than it is informative"))
        return slice_

    # --- match
    confirmed, proposed, absent, unreachable = [], [], [], []
    for f in in_scope:
        try:
            rows = query_rows(retrieval_term(f["filer"]), fetch=api_fetch)
        except Exception as exc:                   # noqa: BLE001
            unreachable.append({"accession": f["accession"],
                                "filer": clean_filer(f["filer"]),
                                "why": f"{type(exc).__name__}: {exc}"})
            continue
        tier, ids = match(f, rows)
        rec = {"accession": f["accession"], "filer": clean_filer(f["filer"]),
               "filing_date": f["filing_date"],
               "stated_job_count": f["stated_job_count"], "tracker_event_ids": ids}
        {CONFIRMED: confirmed, PROPOSED: proposed, ABSENT: absent}[tier].append(rec)

    # An event we could not look up is UNKNOWN, never a miss — a Bluehost 504
    # must not manufacture a recall regression (the 2026-07-31 rule).
    judged = len(confirmed) + len(proposed) + len(absent)
    slice_.update(confirmed=len(confirmed), proposed=len(proposed),
                  absent=len(absent), unreachable=len(unreachable),
                  judged=judged,
                  absent_filings=sorted(absent, key=lambda x: x["filing_date"] or ""),
                  proposed_filings=sorted(proposed, key=lambda x: x["filing_date"] or ""),
                  unreachable_filings=unreachable)
    if judged < MIN_DENOMINATOR:
        slice_.update(state=UNKNOWN, detail=(
            f"{len(unreachable)} of {len(in_scope)} in-scope filings could not be looked "
            f"up, leaving only {judged} judged (minimum {MIN_DENOMINATOR}) — the host was "
            f"unreachable for too much of the set. NOT a recall regression"))
        return slice_

    _, lo_lo, lo_hi = wilson(len(confirmed), judged)
    hi_n = len(confirmed) + len(proposed)
    _, hi_lo, hi_hi = wilson(hi_n, judged)
    slice_.update(
        state=MEASURED,
        recall_confirmed=len(confirmed) / judged,
        recall_upper=hi_n / judged,
        confirmed_interval=[lo_lo, lo_hi],
        upper_interval=[hi_lo, hi_hi],
        detail=(f"recall is between {len(confirmed)}/{judged} = "
                f"{len(confirmed) / judged:.1%} (count-confirmed) and {hi_n}/{judged} = "
                f"{hi_n / judged:.1%} (name+window proposed, unadjudicated); "
                f"{len(undecidable)} of {len(filings)} enumerated filings UNKNOWN, "
                f"{len(out_of_scope)} out of scope (percentage only), "
                f"{len(unreachable)} unreachable"))
    return slice_


# ---------------------------------------------------------------------------
# 5. THE REPORT — slices never average, and never drop out
# ---------------------------------------------------------------------------

def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Declared here, not discovered at runtime, so a slice that fails to compute
# still APPEARS in the report as UNKNOWN instead of vanishing from it. A slice
# that can silently stop being reported is the "absence of a signal is not a
# pass" defect wearing a schedule.
DECLARED_SLICES = ("sec_item_205_us", "state_warn_official_totals")

# ---------------------------------------------------------------------------
# THE SLICE THAT IS NOT MEASURABLE, AND WHY THAT IS A RESULT
# ---------------------------------------------------------------------------
# We ingest every state's WARN listing, so our own collectors can never be the
# denominator for WARN recall. The independent denominator would be a state's
# OWN published period total — a notice count or an affected-employee count, in
# a document separate from the row listing we scrape. Seventeen states plus the
# federal DOL were checked on 2026-08-17. The finding is negative and it is
# worth as much as a number:
#
#   * There is NO national aggregate. US DOL neither maintains a WARN database
#     nor requires notices be sent to it, and BLS Mass Layoff Statistics was
#     discontinued in 2013. A national WARN denominator does not exist.
#   * WISCONSIN publishes exactly the right thing — a state-computed annual
#     affected-worker total for closed calendar years — and its robots.txt sets
#     `Disallow: /` for ClaudeBot, GPTBot, CCBot, Google-Extended and others.
#     This project does not rename an agent to get around a block aimed at the
#     agent (the same reading that kept the FCA National Storage Mechanism out
#     of the UK set), so Wisconsin is refused. It is the one real loss.
#   * WASHINGTON's annual legislative report carries both counts and is
#     fetchable, but its windows are ad hoc and change between editions
#     ("as of Nov. 21, 2024"; "Sept 18, 2024 through Nov 19, 2025"), the figures
#     are narrative prose in a PDF, and one state is a thin denominator. It is
#     the only live candidate and it would need a PDF dependency added to a
#     hash-pinned lock to serve a single state.
#   * MARYLAND signals `ai-input=no`; MASSACHUSETTS and DOL return 403 to
#     non-browser clients; NEW YORK's dashboard is a Tableau embed with no
#     documented export. NORTH CAROLINA, ILLINOIS, OHIO, CALIFORNIA, TEXAS,
#     MICHIGAN, NEW JERSEY, PENNSYLVANIA, COLORADO, GEORGIA, VIRGINIA, OREGON,
#     MINNESOTA and SOUTH CAROLINA publish row listings only, or a moving
#     year-to-date total on the same page as the rows.
#
# So this slice reports NOT MEASURABLE, by name, with its date — rather than
# being quietly left out of a report whose reader would then assume US coverage
# had been measured everywhere it matters.
WARN_ASSESSED_AT = "2026-08-17"
# Re-check twice a year. A standing "not measurable" that nobody revisits is a
# stale claim wearing a permanent exemption, which is the defect
# benchmark_freshness.py exists to catch. Past this age the slice goes UNKNOWN
# and a human has to look again.
WARN_ASSESSMENT_MAX_AGE_DAYS = 183


def assess_state_warn(today=None):
    today = today or date.today()
    age = (today - date(*(int(x) for x in WARN_ASSESSED_AT.split("-")))).days
    slice_ = {
        "key": "state_warn_official_totals",
        "label": "US state WARN recall against a state's own published period total",
        "denominator_basis": "official_state_period_aggregate",
        "assessed_at": WARN_ASSESSED_AT,
        "states_checked": 17,
    }
    if age > WARN_ASSESSMENT_MAX_AGE_DAYS:
        slice_.update(state=UNKNOWN, detail=(
            f"the 'no usable state total' assessment is {age} days old (max "
            f"{WARN_ASSESSMENT_MAX_AGE_DAYS}) — states publish new reports, so this is "
            f"UNVERIFIED rather than still true. Re-check per RUNBOOK 'is there an "
            f"independent WARN denominator yet?'"))
        return slice_
    slice_.update(state=NOT_MEASURABLE, detail=(
        "no independent denominator exists that this project may use. There is no "
        "national WARN aggregate at all (US DOL keeps no database; BLS Mass Layoff "
        "Statistics ended 2013). Wisconsin publishes the right figure and its "
        "robots.txt disallows AI agents, so it is refused. Washington's annual "
        "legislative report is the only live candidate and its periods are ad hoc "
        "prose in a PDF for one state. Every other state checked publishes rows "
        "only, or a moving year-to-date total on the same page as the rows. "
        f"Assessed {WARN_ASSESSED_AT} over 17 states plus US DOL"))
    return slice_


def measure(today=None, progress=None, **kw):
    slices = {}
    for key in DECLARED_SLICES:
        try:
            if key == "sec_item_205_us":
                slices[key] = measure_sec_item_205(today=today, progress=progress, **kw)
            elif key == "state_warn_official_totals":
                slices[key] = assess_state_warn(today=today)
        except Exception as exc:                   # noqa: BLE001 — a crash is UNKNOWN
            slices[key] = {"key": key, "state": UNKNOWN,
                           "detail": f"measurement raised {type(exc).__name__}: {exc}"}
    return {
        "note": ("Rolling recall against denominators the tracker does not construct. "
                 "Written by rolling-recall.yml. Committed on purpose: the data being "
                 "measured changes without a commit. NEVER hand-edit a figure here — "
                 "re-run the module. Recall is a BAND, not a point, because no editor "
                 "adjudicated these matches; see the module docstring."),
        "measured_at": _utc_now_iso(),
        "declared_slices": list(DECLARED_SLICES),
        "slices": slices,
    }


def _days_since(stamp, now=None):
    try:
        then = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return ((now or datetime.now(timezone.utc)) - then).total_seconds() / 86400.0


def judge(measurement, now=None):
    """(state, detail) for the whole report. The single definition, imported by
    data_integrity, ops_status, the digest and the tests.

    THIS DOES NOT HAVE A FLOOR, AND THAT IS DELIBERATE. `recall_goldset` owns
    the tripwire, on a frozen denominator where a drop cannot be sampling noise.
    Here the denominator moves every month, so a fall could be a quiet month of
    filings rather than a coverage loss, and a floor over a moving denominator
    is a false alarm generator — this repo already learned what eight identical
    emails in one afternoon do to an alert channel. What this DOES enforce is
    that the figure exists, is fresh, and says which of its slices it could not
    compute.
    """
    if not isinstance(measurement, dict):
        return UNKNOWN, ("no rolling-recall measurement has been written yet — coverage "
                         "is UNMEASURED, not fine. Run "
                         "`python3 railway/rolling_recall.py --write`")
    age = _days_since(measurement.get("measured_at"), now)
    if age is None:
        return UNKNOWN, (f"measurement has no readable timestamp: "
                         f"{measurement.get('measured_at')!r}")
    if age > MAX_MEASUREMENT_AGE_DAYS:
        return UNKNOWN, (f"the rolling-recall measurement is {age:.0f} days old (max "
                         f"{MAX_MEASUREMENT_AGE_DAYS}) — either this checkout is behind "
                         f"main or rolling-recall.yml has stopped. Coverage is "
                         f"UNVERIFIED, not passing")
    declared = measurement.get("declared_slices") or []
    slices = measurement.get("slices") or {}
    missing = [k for k in declared if k not in slices]
    if missing:
        return UNKNOWN, (f"declared slice(s) absent from the report: {', '.join(missing)} "
                         f"— a slice that cannot be computed must say so, not disappear")
    unknown = [k for k, s in slices.items() if s.get("state") == UNKNOWN]
    if unknown:
        first = slices[unknown[0]]
        return UNKNOWN, (f"{len(unknown)} of {len(slices)} slice(s) UNKNOWN: "
                         f"{unknown[0]} — {first.get('detail')}")
    parts = []
    for key, s in sorted(slices.items()):
        if s.get("state") == NOT_MEASURABLE:
            parts.append(f"{key}: not measurable ({s.get('detail')})")
        else:
            parts.append(f"{key}: {s['recall_confirmed']:.1%}-{s['recall_upper']:.1%} "
                         f"of {s['judged']} ({s['window']['from']}..{s['window']['to']})")
    return PASS, "; ".join(parts)


def load_measurement(path=None):
    try:
        return json.loads(Path(path or MEASUREMENT_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_measurement(measurement, path=None):
    path = Path(path or MEASUREMENT_PATH)
    path.write_text(json.dumps(measurement, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# calibration — the matcher is scored against the editor, not trusted
# ---------------------------------------------------------------------------

GOLDSET_PATH = (REPO_ROOT / "docs" / "recall-reference-sets"
                / "sec-item-205-us-2025-07_2026-06.goldset.json")


def calibrate(manifest_path=None, api_fetch=None):
    """Score CONFIRMED/PROPOSED against the 57 hand-adjudicated events.

    The two properties the band rests on:
      * CONFIRMED admits no event the editor rejected  -> the lower end is a
        genuine lower bound
      * PROPOSED misses no event the editor matched    -> the upper end is a
        genuine upper bound
    """
    manifest = json.loads(Path(manifest_path or GOLDSET_PATH).read_text(encoding="utf-8"))
    out = {"confirmed_on_editor_matched": 0, "confirmed_on_editor_notmatched": 0,
           "proposed_on_editor_matched": 0, "absent_on_editor_matched": 0,
           "editor_matched": 0, "editor_notmatched": 0, "unreachable": 0,
           "false_positives": [], "upper_bound_misses": []}
    for ev in manifest["reference_events"]:
        editor = ev.get("match_decision") == "matched"
        out["editor_matched" if editor else "editor_notmatched"] += 1
        filing = {"filer": ev["filer"], "filing_date": ev["filing_date"],
                  "stated_job_count": ev.get("stated_job_count")}
        try:
            rows = query_rows(retrieval_term(ev["filer"]), fetch=api_fetch)
        except Exception:                          # noqa: BLE001
            out["unreachable"] += 1
            continue
        tier, _ = match(filing, rows)
        if editor:
            if tier == CONFIRMED:
                out["confirmed_on_editor_matched"] += 1
            elif tier == PROPOSED:
                out["proposed_on_editor_matched"] += 1
            else:
                out["absent_on_editor_matched"] += 1
                out["upper_bound_misses"].append(
                    {"filer": ev["filer"], "filing_date": ev["filing_date"]})
        elif tier == CONFIRMED:
            out["confirmed_on_editor_notmatched"] += 1
            out["false_positives"].append(
                {"filer": ev["filer"], "filing_date": ev["filing_date"]})
    return out


# ---------------------------------------------------------------------------

def _render(measurement):
    lines = [f"ROLLING RECALL  measured_at={measurement.get('measured_at')}"]
    for key in measurement.get("declared_slices") or []:
        s = (measurement.get("slices") or {}).get(key) or {
            "state": UNKNOWN, "detail": "absent from the report"}
        lines.append(f"  [{s.get('state', UNKNOWN).upper()}] {key}")
        lines.append(f"      {s.get('label', '')}")
        if s.get("state") == MEASURED:
            w = s["window"]
            lines.append(f"      window {w['from']}..{w['to']}  "
                         f"({s['enumerated_filings']} enumerated, {s['in_scope']} in scope, "
                         f"{s['out_of_scope']} out of scope, {s['undecidable']} UNKNOWN)")
            lines.append(f"      confirmed  {format_interval(s['confirmed'], s['judged'])}")
            lines.append(f"      upper      "
                         f"{format_interval(s['confirmed'] + s['proposed'], s['judged'])}")
            for miss in (s.get("absent_filings") or [])[:12]:
                lines.append(f"      MISS  {miss['filing_date']}  {miss['filer']}"
                             f"  ({miss['stated_job_count']} jobs)")
        else:
            lines.append(f"      {s.get('detail')}")
    state, detail = judge(measurement)
    lines.append(f"  VERDICT {state.upper()}: {detail}")
    return "\n".join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--calibrate" in argv:
        result = calibrate()
        print(json.dumps(result, indent=2))
        ok = (not result["false_positives"]) and (not result["upper_bound_misses"])
        print("CALIBRATION", "OK" if ok else "REVIEW NEEDED")
        return 0 if ok else 2
    measurement = measure(progress=lambda m: print(f"  .. {m}", file=sys.stderr))
    if "--write" in argv:
        print(f"wrote {write_measurement(measurement)}", file=sys.stderr)
    print(_render(measurement))
    state, _ = judge(measurement)
    return {PASS: 0, FAIL: 2, UNKNOWN: 3}[state]


if __name__ == "__main__":
    sys.exit(main())
