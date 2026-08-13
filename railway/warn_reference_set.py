#!/usr/bin/env python3
"""The US WARN reference set: enumerate, sample, measure, and hand to a human.

READ docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md FIRST. It was
committed before this file ran once, it fixes every choice this module
implements, and if the two disagree the document is right and this file is a bug.

WHAT IT IS
----------
US recall has been measured only over SEC Form 8-K Item 2.05 filings — public
companies that file 8-Ks, 53 of 57. Private employers are not in that set at all
and neither is any state or industry dimension. State WARN notices are mandatory
disclosure, already inside this pipeline, and cover exactly the private employers
Item 2.05 cannot see. Nothing had ever measured what fraction of them we hold.

Four states — CA, TX, FL, TN — chosen by an employment-order walk over an
eligibility rule fixed in the definition, twelve months (2025-07-01..2026-06-30)
counted on the notice date, one event per (state, employer, notice date).

WHAT IT IS NOT
--------------
It does not touch railway/recall_measurement.json, railway/recall_adjudications
.json, the SEC manifest or MATCHED_FLOOR. The published SEC figure is not this
module's business and a test asserts it.

It also does not decide a match. EVERY candidate — including one carrying the
identical job count, state and date — ships as `candidates_needing_adjudication`
with `match_decision: not_matched`, so the editor-confirmed numerator starts at
zero. A machine must not promote its own recall. The machine's proposal is
reported beside it as an explicit upper bound, split into `exact` and `loose`
so a reviewer can see which tier is carrying the number before believing either.

No model is called. Enumeration, matching and classification are deterministic
code and read-only GETs. Cost against the $18 monthly allowance: $0.00.

USAGE
    python3 railway/warn_reference_set.py --build     # re-enumerate frame, redraw sample
    python3 railway/warn_reference_set.py --measure   # frozen set vs the live API
    python3 railway/warn_reference_set.py --pack      # per-row adjudication sheet
"""
import html as _html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recall_goldset import name_matches, wilson, format_interval  # noqa: E402
from warn_pdf import PDF, page_items                              # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
REF_DIR = REPO_ROOT / "docs" / "recall-reference-sets"
MANIFEST_PATH = REF_DIR / "us-warn-ca-tx-fl-tn-2025-07_2026-06.goldset.json"
MEASUREMENT_PATH = HERE / "warn_recall_measurement.json"
QUEUE_JSON = REF_DIR / "us-warn-adjudication-queue.json"
QUEUE_MD = REF_DIR / "us-warn-adjudication-queue.md"

REFERENCE_SET_ID = "us-warn-ca-tx-fl-tn-2025-07_2026-06"
WINDOW = ("2025-07-01", "2026-06-30")
STATES = ("CA", "TX", "FL", "TN")
SAMPLE_N = 25                     # per state, primary systematic sample
LARGE_BAND_FLOOR = 500            # the L stratum, censused separately

API = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"
API_UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"
# The state agencies are read with a plain browser UA. Every one of the four was
# checked against its own robots.txt on 2026-08-13; two states that would have
# qualified on content (VA, MD) are NOT in this list because they asked agents
# like this one not to read them. See the definition, §2.
SITE_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

SOURCES = {
    "CA": {
        "publisher": "California Employment Development Department",
        "document": "WARN Report for 7/1/25 to 6/30/26 (archived fiscal-year report)",
        "url": ("https://edd.ca.gov/siteassets/files/jobs_and_training/warn/"
                "warn-report-for-7-1-25-to-6-30-26.pdf"),
        "note": ("A DIFFERENT DOCUMENT from the one our CA collector reads. "
                 "sources/warn.py points at warn_report1.xlsx, a rolling file the "
                 "EDD refreshes every Tuesday and Thursday which currently holds "
                 "FY 2026-27 only. This is the closed archival PDF for the window."),
    },
    "TX": {
        "publisher": "Texas Workforce Commission",
        "document": "WARN Notices, Texas Open Data Portal dataset 8w53-c4f6",
        "url": "https://data.texas.gov/resource/8w53-c4f6.json",
        "note": ("THE SAME dataset sources/warn_custom.fetch_tx reads. Independent "
                 "of our selection and our parser and our ordering, not of our "
                 "design. Stated plainly rather than implied otherwise."),
    },
    "FL": {
        "publisher": "FloridaCommerce (Department of Commerce)",
        "document": "WARN Notice list, Records view, by notification year",
        "url": "https://reactwarn.floridajobs.org/WarnList/Records?year={year}",
        "note": "No robots.txt is published at this host (HTTP 404), so nothing is disallowed.",
    },
    "TN": {
        "publisher": "Tennessee Department of Labor and Workforce Development",
        "document": "WARN Notices report table",
        "url": ("https://www.tn.gov/workforce/general-resources/major-publications0/"
                "major-publications-redirect/reports.html"),
        "note": ("Publishes a POSTING date, not the employer's notice date; the "
                 "window is counted on it, per the definition §3. Each row links "
                 "the employer's own WARN letter, which is the per-row citation."),
    },
}

# ---------------------------------------------------------------------------
# Reference-side normalisation. Written for this measurement and used ONLY for
# the collapse key; the aliases actually queried come from the state's full
# published name, so a defect in warn_import's own cleaning is still visible.
# ---------------------------------------------------------------------------
_TAGS = re.compile(r"<[^>]*>")
_ADDRESS = re.compile(
    r"[\s(,]+\d{1,6}(?:\s*-\s*\d{1,6})?\s+[\w.'-]+(?:\s+[\w.'-]+){0,4}\s*"
    r"(?:st|street|rd|road|ave|avenue|hwy|highway|blvd|boulevard|dr|drive|ln|lane|"
    r"pkwy|parkway|way|ct|court|cir|circle|pl|place|ter|terrace|route|rte|"
    r"trail|trl|loop|row|walk)\b\.?", re.I)
_CITY_ST_ZIP = re.compile(r"[\s,(]*[A-Za-z .'-]+,\s*[A-Z]{2},?\s*\d{5}(?:-\d{4})?\b")
_SITE_TAIL = re.compile(r"\s+[-–—]\s+.*$")
_PARENS = re.compile(r"\s*\([^)]*\)\s*$")
_SUFFIX = {"inc", "corp", "corporation", "co", "company", "ltd", "limited", "llc",
           "l", "lp", "llp", "plc", "nv", "sa", "se", "ag", "the", "holdings",
           "holding", "group", "usa", "us"}
_RESCINDED = re.compile(r"\b(rescind\w*|cancell?ed|withdraw\w*|void(?:ed)?)\b", re.I)
COLLAPSE_TOKENS = 4


def clean_published_name(raw):
    """The state's published employer string, with markup and entities removed."""
    name = _html.unescape(_TAGS.sub(" ", str(raw or "")))
    name = re.sub(r"\s+", " ", name).strip(" ,;-")
    return name


def collapse_key_name(raw):
    """Definition §4 (as amended 2026-08-13): the four-token collapse key."""
    name = clean_published_name(raw)
    for rx in (_ADDRESS, _CITY_ST_ZIP):
        m = rx.search(name)
        if m and m.start() > 0:
            head = name[:m.start()].strip(" ,;-([")
            if len(head) >= 3 and re.search(r"[A-Za-z]{3}", head):
                name = head
    name = _PARENS.sub("", name)
    name = _SITE_TAIL.sub("", name) if _SITE_TAIL.search(name) else name
    toks = [t for t in re.sub(r"[^A-Za-z0-9]+", " ", name.lower()).split()
            if t and t not in _SUFFIX]
    return " ".join(toks[:COLLAPSE_TOKENS])


def _cut_at(name, *patterns):
    """Cut the name at the first address-ish match, KEEPING THE HEAD.

    It has to be a cut and not a substitution, and this is not a nicety. The
    first version of `aliases_for` used `_CITY_ST_ZIP.sub("", name)`, whose
    leading `[A-Za-z .'-]+` is greedy: on Florida's glued
    `Essendant 2405 Commerce Park Dr ORLANDO, FL, 32819` it matched
    `Essendant ORLANDO, FL, 32819` and deleted the employer along with the
    address. The alias list came back EMPTY for 14 events, so no query was sent
    for them at all — and the first measurement run scored all 14 as misses.
    A query that was never sent is UNKNOWN, never a miss. `measure()` now also
    refuses to score an event with no alias, so the two guards are independent.
    """
    for rx in patterns:
        m = rx.search(name)
        if m and m.start() > 0:
            head = name[:m.start()].strip(" ,;-([")
            if len(head) >= 3 and re.search(r"[A-Za-z]{3}", head):
                name = head
    return name


def aliases_for(raw):
    """Query aliases: the cleaned full name and its leading 2 and 3 tokens.

    Deliberately NOT built from the collapse key — the collapse key throws away
    the site tail, and an alias list that only ever queried a truncated name
    would be measuring our storage of a name this set invented.
    """
    cleaned = clean_published_name(raw)
    name = _PARENS.sub("", _cut_at(cleaned, _ADDRESS, _CITY_ST_ZIP)).strip(" ,;-")
    toks = [t for t in re.sub(r"[^A-Za-z0-9]+", " ", name).split() if t]
    if not toks:                               # never return [] — see _cut_at
        toks = [t for t in re.sub(r"[^A-Za-z0-9]+", " ", cleaned).split() if t]
    out, seen = [], set()
    for cand in (" ".join(toks), " ".join(toks[:3]), " ".join(toks[:2])):
        key = cand.lower()
        if cand and key not in seen:
            seen.add(key)
            out.append(cand)
    return out


def query_terms_for(raw):
    """LITERAL leading substrings of the published name, for the API's filter.

    THIS IS NOT THE MATCHING RULE. It is how candidate rows are RETRIEVED, and
    the two have to be different objects because `/query?company=` is a substring
    LIKE against the stored name while `name_matches` is a token comparison.

    The first measurement run conflated them and it cost seven points. Aliases
    are punctuation-stripped (`Mattel Inc`, `Raley s`, `Frito Lay`,
    `Albertsons 4286`, `Saks Company LLC`), and none of those is a substring of
    what is actually stored (`Mattel, Inc.`, `Raley's`, `Frito-Lay, Inc`,
    `Albertsons #4286`, `Saks & Company LLC`). Every employer whose name carries
    a comma, an apostrophe, a hyphen, an ampersand or a `#` was therefore
    UNFINDABLE BY CONSTRUCTION: the query returned nothing and the event scored
    as a miss while the row sat in the table. Eleven of sixteen misses were that.

    So a query term is a leading run of the published name with its punctuation
    intact, at 1, 2 and 3 tokens plus the whole head. The match test that runs
    afterwards is unchanged.
    """
    name = _PARENS.sub("", _cut_at(clean_published_name(raw), _ADDRESS, _CITY_ST_ZIP))
    parts = name.split()
    out, seen = [], set()
    for n in (1, 2, 3, len(parts)):
        if not 0 < n <= len(parts):
            continue
        term = " ".join(parts[:n]).strip(" ,;:-&/")
        key = term.lower()
        if len(term) >= 2 and key not in seen:
            seen.add(key)
            out.append(term)
    return out or [clean_published_name(raw)[:60]]


def size_band(jobs):
    if jobs is None:
        return "UNKNOWN"
    if jobs >= LARGE_BAND_FLOOR:
        return "L"
    return "M" if jobs >= 100 else "S"


# ---------------------------------------------------------------------------
# Fetching. Read-only GETs, one per document, with the state's crawl-delay.
# ---------------------------------------------------------------------------
def _get(url, ua=SITE_UA, timeout=90, accept=None):
    headers = {"User-Agent": ua}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _iso(value, order="mdy"):
    """A published date string -> ISO, or None. Never guesses a century wrongly."""
    s = str(value or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", s)
    if not m:
        return None
    a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    mo, day = (a, b) if order == "mdy" else (b, a)
    try:
        return date(y, mo, day).isoformat()
    except ValueError:
        return None


def _jobs(value):
    """FIRST integer only — the same rule the tracker applies to freeform counts."""
    m = re.search(r"\d[\d,]*", str(value or ""))
    if not m:
        return None
    try:
        n = int(m.group(0).replace(",", ""))
    except ValueError:
        return None
    return n if 0 < n <= 200000 else None


def _table_rows(markup):
    """[(cells, raw_row_html)] for every <tr>, cells flattened to text."""
    out = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", markup, re.S | re.I):
        cells = [_html.unescape(re.sub(r"\s+", " ", _TAGS.sub(" ", c))).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", raw, re.S | re.I)]
        if cells:
            out.append((cells, raw))
    return out


def frame_ca():
    """California: the archived FY 2025-26 PDF, read by column position."""
    doc = SOURCES["CA"]
    pdf = PDF(_get(doc["url"]))
    rows, page_no = [], 0
    for content in pdf.pages():
        page_no += 1
        by_y = {}
        for x, y, text in page_items(content):
            by_y.setdefault(y, []).append((x, text))
        for y in sorted(by_y, reverse=True):
            cells = [t for _, t in sorted(by_y[y])]
            if len(cells) < 8:
                continue                       # header, footer, or a wrapped tail
            notice, processed, effective, company = cells[0], cells[1], cells[2], cells[3]
            if not re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", notice):
                continue                       # the header row and its repeats
            county, jobs, kind = cells[4], cells[5], cells[6]
            address = cells[7] if len(cells) > 7 else ""
            rows.append({
                "state": "CA", "employer_published": company,
                "notice_date": _iso(notice), "state_received_date": _iso(processed),
                "effective_date": _iso(effective), "job_count": _jobs(jobs),
                "location": f"{county}; {address}".strip("; "),
                "notice_type": kind, "industry": None,
                "source_url": doc["url"],
                "source_locator": f"page {page_no}, text row at y={y}",
            })
    return rows


def frame_tx():
    """Texas: the TWC Socrata dataset, date-bounded server-side."""
    doc = SOURCES["TX"]
    out, offset = [], 0
    while True:
        query = urllib.parse.urlencode({
            "$limit": 2000, "$offset": offset, "$order": "notice_date",
            "$where": (f"notice_date >= '{WINDOW[0]}T00:00:00' "
                       f"AND notice_date <= '{WINDOW[1]}T23:59:59'"),
        })
        batch = json.loads(_get(doc["url"] + "?" + query, accept="application/json"))
        if not batch:
            break
        for i, r in enumerate(batch):
            out.append({
                "state": "TX", "employer_published": r.get("job_site_name"),
                "notice_date": _iso(r.get("notice_date")),
                "state_received_date": _iso(r.get("wfdd_received_date")),
                "effective_date": _iso(r.get("layoff_date")),
                "job_count": _jobs(r.get("total_layoff_number")),
                "location": ", ".join(x for x in (r.get("city_name"),
                                                  r.get("county_name")) if x),
                "notice_type": None, "industry": None,
                "source_url": doc["url"],
                "source_locator": (f"$order=notice_date, $offset={offset + i} "
                                   f"within the window filter"),
            })
        offset += len(batch)
        if len(batch) < 2000:
            break
        time.sleep(1)                          # data.texas.gov robots: Crawl-delay 1
    return out


def frame_fl():
    """Florida: the Records view, every page of the two notification years."""
    doc = SOURCES["FL"]
    out = []
    for year in (2025, 2026):
        page, previous = 1, None
        while page <= 40:                      # a hard stop; FL runs 2-3 pages/year
            url = doc["url"].format(year=year) + f"&page={page}"
            markup = _get(url).decode("utf-8", "replace")
            rows = [(c, raw) for c, raw in _table_rows(markup) if len(c) >= 4]
            data = [(c, raw) for c, raw in rows
                    if re.match(r"^\d{2}-\d{2}-\d{2}$", c[1] or "")]
            if not data:
                break
            # FL CLAMPS: asking for a page past the last one re-serves the last
            # one forever rather than returning empty. Without this the loop ran
            # 40 pages a year at ~16s each. Stop when a page repeats its
            # predecessor, and do it on the row signature rather than on an
            # assumed page count, so a year that grows a page still works.
            signature = tuple(tuple(c) for c, _ in data)
            if signature == previous:
                break
            previous = signature
            for i, (c, raw) in enumerate(data):
                link = re.search(r'href="([^"]+)"', raw)
                out.append({
                    "state": "FL", "employer_published": c[0],
                    "notice_date": _iso(c[1]), "state_received_date": None,
                    "effective_date": _iso((c[2] or "").split("thru")[0].strip()),
                    "job_count": _jobs(c[3]),
                    "location": "", "notice_type": None,
                    "industry": c[4] if len(c) > 4 else None,
                    "source_url": (urllib.parse.urljoin(url, link.group(1))
                                   if link else url),
                    "source_locator": f"year={year} page={page} row {i + 1}",
                })
            page += 1
            time.sleep(1)
    return out


def frame_tn():
    """Tennessee: the WARN report table, with each row's own notice letter."""
    doc = SOURCES["TN"]
    markup = _get(doc["url"]).decode("utf-8", "replace")
    out = []
    for i, (c, raw) in enumerate(_table_rows(markup)):
        if len(c) < 5 or not _iso(c[0]):
            continue
        link = re.search(r'href="([^"]+\.pdf)"', raw, re.I)
        out.append({
            "state": "TN", "employer_published": c[1],
            "notice_date": _iso(c[0]),         # posting date; definition §3
            "state_received_date": _iso(c[0]),
            "effective_date": _iso(re.split(r"\bto\b|thru", c[4] or "")[0].strip()),
            "job_count": _jobs(c[3]),
            "location": c[2], "notice_type": c[5] if len(c) > 5 else None,
            "industry": None,
            "source_url": (urllib.parse.urljoin(doc["url"], link.group(1))
                           if link else doc["url"]),
            "source_locator": f"report table row {i + 1}",
        })
    return out


FRAMES = {"CA": frame_ca, "TX": frame_tx, "FL": frame_fl, "TN": frame_tn}


# ---------------------------------------------------------------------------
# Frame -> events. Exclusions are RECORDED, never silently dropped.
# ---------------------------------------------------------------------------
def build_events(rows):
    events, excluded = {}, []
    for row in rows:
        name = clean_published_name(row.get("employer_published"))
        reason = None
        if _RESCINDED.search(name):
            reason = ("rescinded_or_cancelled — the state marks this notice "
                      "withdrawn, so it is a layoff that did not happen; "
                      "warn_import._RESCINDED_RX drops it on the way in too")
        elif not re.search(r"[A-Za-z0-9]", name):
            reason = "no_identifiable_employer"
        elif not row.get("notice_date"):
            reason = "no_published_notice_date"
        elif not (WINDOW[0] <= row["notice_date"] <= WINDOW[1]):
            reason = f"notice_date {row['notice_date']} outside the window"
        elif not row.get("job_count"):
            reason = "no_absolute_headcount_published"
        if reason:
            excluded.append({**row, "excluded_because": reason})
            continue
        key = (row["state"], collapse_key_name(name), row["notice_date"])
        ev = events.get(key)
        if ev is None:
            ev = events[key] = {
                "reference_row_id": "",
                "state": row["state"],
                "employer_published": name,
                "collapse_key": key[1],
                "notice_date": row["notice_date"],
                "effective_dates": [],
                "stated_job_count": 0,
                "component_rows": [],
                "employer_aliases": aliases_for(name),
                "query_terms": query_terms_for(name),
                "official_source_url": row["source_url"],
            }
        ev["stated_job_count"] += row["job_count"]
        if row.get("effective_date"):
            ev["effective_dates"].append(row["effective_date"])
        ev["component_rows"].append({
            "employer_published": name, "job_count": row["job_count"],
            "effective_date": row.get("effective_date"),
            "location": row.get("location"), "notice_type": row.get("notice_type"),
            "industry": row.get("industry"),
            "state_received_date": row.get("state_received_date"),
            "source_url": row.get("source_url"),
            "source_locator": row.get("source_locator"),
        })
    out = []
    for (st, key, notice), ev in events.items():
        ev["reference_row_id"] = (f"warn-{st.lower()}-{notice}-"
                                  f"{re.sub(r'[^a-z0-9]+', '-', key).strip('-')[:40]}")
        ev["size_band"] = size_band(ev["stated_job_count"])
        ev["published_rows"] = len(ev["component_rows"])
        ev["effective_date_min"] = min(ev["effective_dates"]) if ev["effective_dates"] else None
        ev["effective_date_max"] = max(ev["effective_dates"]) if ev["effective_dates"] else None
        ev.pop("effective_dates")
        ev["match_window"] = _match_window(notice)
        ev["match_decision"] = "not_matched"
        ev["match_notes"] = ("NOT ADJUDICATED. Every candidate goes to the "
                             "adjudication queue; the numerator counts only what "
                             "an editor has confirmed.")
        ev["rejected_candidate_event_ids"] = []
        out.append(ev)
    out.sort(key=lambda e: (e["state"], e["notice_date"], e["employer_published"]))
    return out, excluded


def _match_window(notice_date):
    """notice-30d .. notice+400d. Lopsided on purpose: we store the EFFECTIVE date."""
    d = date.fromisoformat(notice_date).toordinal()
    return [date.fromordinal(d - 30).isoformat(), date.fromordinal(d + 400).isoformat()]


def systematic_sample(events, n, seed):
    """Definition §7: chronological re-sort, fixed interval, reproducible start."""
    ordered = sorted(events, key=lambda e: (e["notice_date"], e["employer_published"]))
    total = len(ordered)
    if total <= n:
        return ordered, {"frame": total, "drawn": total, "interval": 1, "start": 0,
                         "note": "frame smaller than the target; taken whole"}
    k = total // n
    start = seed % k
    picked = [ordered[start + i * k] for i in range(n) if start + i * k < total]
    return picked, {"frame": total, "drawn": len(picked), "interval": k, "start": start,
                    "note": "systematic on (notice_date, employer)"}


def _seed(state):
    """A fixed function of the state code. Recorded so the draw cannot be re-rolled."""
    return sum((i + 1) * ord(c) for i, c in enumerate(state))


# ---------------------------------------------------------------------------
def build():
    frames, excluded_all, draws, events_all = {}, [], {}, []
    lag_samples = []
    for st in STATES:
        print(f"[{st}] fetching {SOURCES[st]['document']} ...")
        rows = FRAMES[st]()
        print(f"[{st}] {len(rows)} published rows")
        events, excluded = build_events(rows)
        for ev in events:
            for c in ev["component_rows"]:
                if c.get("state_received_date") and ev["notice_date"] and st == "CA":
                    lag_samples.append(
                        date.fromisoformat(c["state_received_date"]).toordinal()
                        - date.fromisoformat(ev["notice_date"]).toordinal())
        frames[st] = events
        excluded_all += excluded
        print(f"[{st}] {len(events)} in-window events, {len(excluded)} rows excluded")
        picked, meta = systematic_sample(events, SAMPLE_N, _seed(st))
        draws[st] = meta
        for ev in picked:
            ev["stratum"] = "primary"
        events_all += picked
    # The L census: every 500+ event in every state's frame, reported apart.
    chosen = {e["reference_row_id"] for e in events_all}
    large = []
    for st in STATES:
        for ev in frames[st]:
            if ev["size_band"] == "L" and ev["reference_row_id"] not in chosen:
                ev["stratum"] = "large_census"
                large.append(ev)
    lag = None
    if lag_samples:
        lag_samples.sort()
        lag = {"n": len(lag_samples), "min": lag_samples[0], "max": lag_samples[-1],
               "median": lag_samples[len(lag_samples) // 2],
               "mean": round(sum(lag_samples) / len(lag_samples), 2)}
    manifest = {
        "manifest_version": 1,
        "reference_set_id": REFERENCE_SET_ID,
        "publication_status": ("internal_reference_not_published_to_benchmarks_recall"),
        "reference_basis": "official_state_warn_publications_systematic_enumeration",
        "country": "United States",
        "states": list(STATES),
        "definition_document": "docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md",
        "period": {"from": WINDOW[0], "to": WINDOW[1],
                   "date_field": ("published notice date; TN publishes a posting "
                                  "date and the window is counted on it — §3")},
        "assembled_at": _utc_now(),
        "assembled_by": ("Claude Code session, single actor. NOT through the "
                         "three-actor review chain docs/RECALL_BENCHMARK_PROTOCOL.md "
                         "requires before a recall number may be posted to "
                         "/benchmarks/recall, and therefore NOT posted there."),
        "sources": SOURCES,
        "ca_notice_to_processed_lag_days": lag,
        "frame_sizes": {st: len(frames[st]) for st in STATES},
        "frame_jobs": {st: sum(e["stated_job_count"] for e in frames[st]) for st in STATES},
        # Recorded because a state that publishes on a lag has an EMPTY tail to
        # the window, and a frame that stops early is a smaller denominator, not
        # a recall result. Read this before comparing two states' figures.
        "frame_notice_date_range": {
            st: {"min": min((e["notice_date"] for e in frames[st]), default=None),
                 "max": max((e["notice_date"] for e in frames[st]), default=None),
                 "months_covered": len({e["notice_date"][:7] for e in frames[st]})}
            for st in STATES},
        "frame_size_bands": {
            st: {b: sum(1 for e in frames[st] if e["size_band"] == b)
                 for b in ("S", "M", "L")} for st in STATES},
        "frame_multi_row_events": {
            st: sum(1 for e in frames[st] if e["published_rows"] > 1) for st in STATES},
        "sample_draws": draws,
        "collapse_rule": (f"one event per (state, first-{COLLAPSE_TOKENS}-token "
                          f"normalised employer name, notice date); component rows kept"),
        "match_rule": {
            "company_match": "recall_goldset.name_matches — token PREFIX, not substring",
            "state_match": "row state must equal the reference state when the row carries one",
            "window_days_before_notice": 30,
            "window_days_after_notice": 400,
            "why_lopsided": ("our WARN rows store the EFFECTIVE date, which trails "
                             "the notice by 60-90 days and sometimes far more"),
            "numerator": ("events whose match_decision is 'matched' — editor-confirmed "
                          "ONLY. Machine proposals are an upper bound, never a numerator."),
            "unreachable_policy": ("an event whose query could not be completed is "
                                   "UNKNOWN, never a miss"),
        },
        "reference_events": events_all,
        "large_event_census": large,
        "excluded_rows": excluded_all,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nmanifest written: {MANIFEST_PATH}")
    print(f"  primary sample     {len(events_all)} events")
    print(f"  large-event census {len(large)} events (reported separately)")
    print(f"  excluded rows      {len(excluded_all)}")
    return manifest


# ---------------------------------------------------------------------------
def _cachebust():
    import uuid
    return uuid.uuid4().hex[:10]


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _api(path, attempts=4):
    """One read-only GET, retried on a transient fault.

    Bluehost under /blog returns 503/504 in short bursts (2026-07-31: two
    outages of 6 and 7 minutes). Without a retry a burst turns a run of events
    into UNKNOWN — the first full run lost ten consecutive Texas events that
    way. UNKNOWN is the correct verdict for a query that could not complete, and
    it is still the verdict here if every attempt fails; the retry just stops a
    six-minute host wobble from deleting a tenth of the sample.
    """
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(API + path,
                                     headers={"User-Agent": API_UA,
                                              "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except Exception as exc:                                   # noqa: BLE001
            last = exc
            if attempt < attempts - 1:
                time.sleep(3 * (attempt + 1))
    raise last


def candidates_for(event, rows):
    """Rows the §6 rule proposes for this event, each with its OWN flags.

    Per-row attribution is not a style choice. On 2026-08-12 an adjudication
    sheet pooled the flags of several proposed rows into one summary line and a
    reviewer rejected a correct Dow row because the summary described a
    co-proposed one. Nothing in this function or in the sheet it feeds ever
    describes more than one row at a time.
    """
    lo, hi = (date.fromisoformat(x) for x in event["match_window"])
    comp_counts = {c["job_count"] for c in event["component_rows"]}
    comp_counts.add(event["stated_job_count"])
    out = []
    for row in rows:
        name = row.get("company_name") or ""
        if not any(name_matches(a, name) for a in event["employer_aliases"]):
            continue
        row_state = (row.get("state") or "").strip().upper()
        if row_state and row_state != event["state"]:
            continue
        when = row.get("layoff_date") or row.get("announcement_date")
        try:
            when_d = date.fromisoformat(str(when)[:10])
        except (TypeError, ValueError):
            continue
        if not (lo <= when_d <= hi):
            continue
        jobs = row.get("job_count")
        is_warn = "warn" in str(row.get("source_type") or "").lower()
        tier = "exact" if (is_warn and jobs in comp_counts) else "loose"
        out.append({
            "tier": tier,
            "tracker_event_id": row.get("event_id"),
            "tracker_row_id": row.get("id"),
            "company_name": name,
            "job_count": jobs,
            "row_date": str(when)[:10],
            "state": row_state or None,
            "source_type": row.get("source_type"),
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            # Flags describe THIS ROW ONLY.
            "flags": _flags(event, name, jobs, when_d, row_state, is_warn),
        })
    out.sort(key=lambda c: (c["tier"] != "exact", c["row_date"]))
    return out


def _flags(event, name, jobs, when_d, row_state, is_warn):
    flags = []
    if not is_warn:
        flags.append(f"row source is {'news/filing' if not is_warn else 'warn'}, "
                     f"not a WARN-tier row")
    if jobs in {c["job_count"] for c in event["component_rows"]}:
        flags.append("job_count equals one published component row of this notice")
    elif jobs == event["stated_job_count"]:
        flags.append("job_count equals the summed notice total")
    else:
        flags.append(f"job_count {jobs} matches neither a component row nor the "
                     f"notice total {event['stated_job_count']}")
    if event.get("effective_date_min") and str(when_d) == event["effective_date_min"]:
        flags.append("row date equals this notice's earliest published effective date")
    else:
        lag = when_d.toordinal() - date.fromisoformat(event["notice_date"]).toordinal()
        flags.append(f"row date is {lag} day(s) after the notice date")
    if not row_state:
        flags.append("row carries no state, so the state test could not be applied")
    if clean_published_name(name).lower() != event["employer_published"].lower():
        flags.append(f"stored name {name!r} differs from the published "
                     f"{event['employer_published']!r}")
    return flags


def measure(manifest=None):
    manifest = manifest or json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    results = {"primary": [], "large_census": []}
    unreachable = []
    for stratum, key in (("primary", "reference_events"),
                         ("large_census", "large_event_census")):
        for ev in manifest[key]:
            rows, failed = {}, None
            if not ev.get("employer_aliases") or not ev.get("query_terms"):
                # No alias means no query was sent. That is UNKNOWN, and the one
                # thing it must never be is a miss — see _cut_at.
                unreachable.append({"id": ev["reference_row_id"], "stratum": stratum,
                                    "why": "no alias could be derived, so no query "
                                           "was sent — UNKNOWN, not a miss"})
                continue
            for alias in ev["query_terms"]:
                # state + the match window are pushed into the QUERY as well as
                # tested afterwards, so a very common leading token ('Amazon',
                # 'Sodexo' — 93 stored rows) cannot push the one row we need past
                # the page cap. The match test below is unchanged by this.
                q = urllib.parse.urlencode({"company": alias, "state": ev["state"],
                                            "from": ev["match_window"][0],
                                            "to": ev["match_window"][1],
                                            "per_page": 200, "cb": _cachebust()})
                try:
                    payload = _api("query?" + q) or {}
                except Exception as exc:                       # noqa: BLE001
                    failed = f"{type(exc).__name__}: {exc}"
                    continue
                for row in payload.get("data") or []:
                    rows[row.get("id")] = row
                time.sleep(0.15)
            if failed and not rows:
                unreachable.append({"id": ev["reference_row_id"], "why": failed,
                                    "stratum": stratum})
                continue
            cands = candidates_for(ev, list(rows.values()))
            results[stratum].append({
                "id": ev["reference_row_id"], "state": ev["state"],
                "employer": ev["employer_published"],
                "notice_date": ev["notice_date"],
                "stated_job_count": ev["stated_job_count"],
                "size_band": ev["size_band"],
                "match_decision": ev.get("match_decision", "not_matched"),
                "candidates": cands,
                "machine_tier": ("exact" if any(c["tier"] == "exact" for c in cands)
                                 else ("loose" if cands else "none")),
            })
        print(f"  {stratum}: {len(results[stratum])} measured")
    out = {
        "note": ("Recall of the frozen US WARN reference set against the live API. "
                 "The numerator is EDITOR-CONFIRMED ONLY; machine_* figures are an "
                 "upper bound and must never be quoted as recall. This file is "
                 "separate from the SEC Item 2.05 set's own measurement file on "
                 "purpose — that published figure is not this set's business, and "
                 "tests/test_warn_reference_set.py asserts no module here can "
                 "reach it."),
        "reference_set_id": manifest["reference_set_id"],
        "definition_document": manifest["definition_document"],
        "measured_at": _utc_now(),
        "unreachable": len(unreachable),
        "unreachable_events": unreachable,
        "results": results,
        "cost_usd": 0.0,
    }
    out["summary"] = summarise(out, manifest)
    MEASUREMENT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"measurement written: {MEASUREMENT_PATH}")
    return out


def _rate(rows, pred):
    hit = sum(1 for r in rows if pred(r))
    return {"n": len(rows), "k": hit,
            "interval": format_interval(hit, len(rows)) if rows else "no sample",
            "point": (wilson(hit, len(rows))[0] if rows else None),
            "low": (wilson(hit, len(rows))[1] if rows else None),
            "high": (wilson(hit, len(rows))[2] if rows else None)}


def summarise(measurement, manifest):
    prim = measurement["results"]["primary"]
    confirmed = lambda r: r["match_decision"] == "matched"          # noqa: E731
    any_cand = lambda r: bool(r["candidates"])                      # noqa: E731
    exact = lambda r: r["machine_tier"] == "exact"                  # noqa: E731
    summary = {
        "editor_confirmed_overall": _rate(prim, confirmed),
        "machine_upper_bound_any_candidate": _rate(prim, any_cand),
        "machine_exact_tier": _rate(prim, exact),
        "by_state": {}, "by_size_band": {},
        "large_event_census": _rate(measurement["results"]["large_census"], any_cand),
    }
    for st in STATES:
        rows = [r for r in prim if r["state"] == st]
        summary["by_state"][st] = {
            "editor_confirmed": _rate(rows, confirmed),
            "machine_any": _rate(rows, any_cand),
            "machine_exact": _rate(rows, exact),
        }
    for band in ("S", "M", "L"):
        rows = [r for r in prim if r["size_band"] == band]
        summary["by_size_band"][band] = {
            "editor_confirmed": _rate(rows, confirmed),
            "machine_any": _rate(rows, any_cand),
            "machine_exact": _rate(rows, exact),
        }
    # Notice-volume-weighted machine bound: each state's own frame size as weight.
    weights = manifest["frame_sizes"]
    total_w = sum(weights.get(st, 0) for st in STATES)
    if total_w:
        summary["machine_any_volume_weighted"] = round(sum(
            (weights.get(st, 0) / total_w) *
            (summary["by_state"][st]["machine_any"]["point"] or 0.0)
            for st in STATES), 4)
    return summary


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--build" in argv:
        build()
        return 0
    if "--measure" in argv:
        m = measure()
        s = m["summary"]
        print("\nUS WARN REFERENCE SET")
        print(f"  editor-confirmed  {s['editor_confirmed_overall']['interval']}")
        print(f"  machine any       {s['machine_upper_bound_any_candidate']['interval']}"
              "   <- UPPER BOUND, not recall")
        print(f"  machine exact     {s['machine_exact_tier']['interval']}")
        for st in STATES:
            print(f"    {st}  machine any {s['by_state'][st]['machine_any']['interval']}")
        for band in ("S", "M", "L"):
            print(f"    {band}   machine any {s['by_size_band'][band]['machine_any']['interval']}")
        return 0
    if "--pack" in argv:
        from warn_adjudication_pack import write_pack
        write_pack()
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
