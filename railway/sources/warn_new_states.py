"""
Custom WARN collectors for four states the open-source warn-scraper does not
cover: MS, WV, HI, NM.

STATUS: UNVALIDATED. These parsers were written from a live recon of each
state's pages/PDFs (2026-07-20), but their OUTPUT has NOT yet been spot-checked
against the source documents by a human. They are intentionally NOT wired into
`CUSTOM_STATES` in warn_custom.py, so the daily cron never calls them. Gate them
in only after a manual run (`python3 -m sources.warn_new_states`) confirms each
fetcher returns sane company/count/date rows. Every entry flows through the same
`_entry(...)` factory as warn_custom.py, so hashes/dedup match the rest of WARN.

Design notes / parsing assumptions per state (see each fetcher docstring for the
gory details):

  MS  Mississippi MDES quarterly PDFs. Gridded tables; most quarters render as a
      clean 9-column grid, one older quarter renders each logical column as three
      physical columns. Both collapse to the same 9-field order once empty cells
      are dropped, so rows are parsed by compressed position. Rows are validated
      (a real Layoff/Closure token + numeric count + parseable date) and skipped
      otherwise, which also throws out header/continuation rows.

  WV  WorkForce WV. The rolling listing links per-notice PDFs that are freeform
      letters (often image-only scans) with NO reliable count -> NOT parsed.
      Instead we parse the periodic multi-year SUMMARY PDFs (label/value "record
      cards": Company / Projected Date / Number Affected / ...), which are the
      only structured WV source. Consequence: brand-new individual notices are
      missed until WV rolls them into a summary PDF. Conservative by design.

  HI  Hawaii WDC per-year pages. The HTML lists only "<date> - <company>"; there
      is NO headcount in the listing and the linked notice PDFs are image scans
      with no text layer. Per the "skip, don't guess" rule this fetcher emits a
      row ONLY when an explicit headcount appears inline in the listing text
      (rare/none today), so it typically returns 0. It is written so that if HI
      ever adds counts inline, they get picked up automatically.

  NM  New Mexico DWS annual PDFs. Clean gridded table (Notice Date | Job Site |
      County | WDA | Total Layoff Number | Layoff Date | Received Date | City).
      Header-keyed column map, effective date falls back Layoff -> Received ->
      Notice, city falls back to county.

CRITICAL: conservative parsing throughout. If a row does not cleanly yield
company + count + date, it is SKIPPED (fewer rows) rather than guessed. A wrong
number is far worse than a missing one.
"""
import re
from datetime import date as _date

import requests

from .warn import _count, _to_iso_date, STATE_WARN_URL
from .warn_custom import _entry, _pdf_tables, _pdf_text  # noqa: F401  (_pdf_text kept for parity)

# Browser-ish UA — ModSecurity/host WAFs block python-requests (see warn.py).
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
TIMEOUT = 45


def _iso(value):
    """Strict ISO date or "". Wraps warn._to_iso_date but additionally requires a
    real YYYY-MM-DD with a 4-digit year in the tracker's window. _to_iso_date
    will happily turn a truncated source value like '10/05/202' into '202-10-05',
    which then slips past _entry's *lexical* 2015..2028 bound check — so reject
    anything that isn't a clean 4-digit-year date here, at the parse site."""
    iso = _to_iso_date(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso or "") and "2015-01-01" <= iso <= "2028-12-31":
        return iso
    return ""


def _cell(row, i):
    """Stripped string for physical column `i` of a pdfplumber table row."""
    if i < 0 or i >= len(row):
        return ""
    v = row[i]
    return "" if v is None else str(v).strip()


def _kind_norm(value):
    """Map a free 'closure/mass layoff' descriptor to Closure/Layoff."""
    lc = (value or "").lower()
    return "Closure" if ("clos" in lc or "idl" in lc) else "Layoff"


# --------------------------------------------------------------------------- MS
_MS_LANDING = "https://mdes.ms.gov/information-center/warn-information/"
_MS_ORIGIN = "https://www.mdes.ms.gov"
# MDES logical columns, left to right (verified across every quarterly PDF,
# 2026-07-20). Most quarters render as a clean 9-column grid; one older quarter
# renders each logical column as three physical columns (value in the first).
# BOTH collapse to this same 9-field order once empty/None cells are dropped, so
# we parse by compressed position rather than fragile physical indices.
#   0 Date of Notice | 1 Company Name (City)(County) | 2 Workforce Area |
#   3 Event Number | 4 NAICS | 5 Type of Action | 6 Number Affected |
#   7 Date of Action (effective) | 8 Reason
_MS_POS = {"notice": 0, "company": 1, "kind": 5, "jobs": 6, "eff": 7}


def _ms_company_city(block):
    """Split the 'Company\\nCity (County)' cell into (company, city).

    The company name itself may wrap across several lines; the LAST line that
    contains a '(...)' is the 'City (County)' locator. Everything before it is
    the company. If no parenthesised locator is present, treat the whole block
    as the company and leave city empty (never guess a city)."""
    lines = [ln.strip() for ln in (block or "").split("\n") if ln.strip()]
    if not lines:
        return "", ""
    loc_idx = next((i for i, ln in enumerate(lines) if "(" in ln and ")" in ln), None)
    if loc_idx is None:
        return " ".join(lines), ""
    company = " ".join(lines[:loc_idx]) or (lines[loc_idx].split("(")[0].strip())
    city = lines[loc_idx].split("(")[0].strip()
    return company, city


def _ms_pdf_links(page_html):
    """Absolute URLs for every /media/<id>/...warn...pdf on the landing page."""
    out = []
    for href in re.findall(r'href="([^"]+\.pdf)"', page_html, re.I):
        if "warn" not in href.lower():
            continue
        url = href if href.lower().startswith("http") else _MS_ORIGIN + href
        if url not in out:
            out.append(url)
    return out


def fetch_ms():
    """Mississippi MDES quarterly WARN PDFs discovered from the landing page.

    Each quarter is fail-isolated. Rows are emitted only when the type cell is a
    real Layoff/Closure token AND the count parses AND a date parses — which
    also filters out the wrapped header rows and any continuation lines."""
    try:
        page = requests.get(_MS_LANDING, headers=UA, timeout=TIMEOUT)
        page.raise_for_status()
        pdf_urls = _ms_pdf_links(page.text)
    except Exception as exc:
        print(f"    MS: landing page failed ({exc})")
        return []
    out = []
    for url in pdf_urls:
        try:
            resp = requests.get(url, headers=UA, timeout=60)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                continue
            tables = _pdf_tables(resp.content)
        except Exception as exc:
            print(f"    MS {url.rsplit('/', 1)[-1]}: fetch/parse failed ({exc})")
            continue
        for table in tables:
            for row in table:
                # Collapse to the logical 9-field order (see _MS_POS).
                comp = [c.strip() for c in (("" if v is None else str(v)) for v in row)
                        if c and c.strip()]
                if len(comp) < 8:
                    continue
                kind_raw = comp[_MS_POS["kind"]]
                # A real 'Layoff'/'Closure' token here is the row's fingerprint;
                # it rejects header rows, continuation lines, and any layout that
                # didn't collapse to the expected order (never guess).
                if not re.fullmatch(r"(?:layoffs?|closures?)", kind_raw.strip(), re.I):
                    continue
                jobs = _count(comp[_MS_POS["jobs"]])
                date = (_iso(comp[_MS_POS["eff"]])
                        or _iso(comp[_MS_POS["notice"]]))
                company, city = _ms_company_city(comp[_MS_POS["company"]])
                e = _entry("MS", company, jobs, date, city,
                           kind=_kind_norm(kind_raw), detail_url=url)
                if e:
                    out.append(e)
    return out


# --------------------------------------------------------------------------- WV
_WV_LANDING = "https://workforcewv.org/job-seeker/layoffs-downsizing/warn-listing/"
_WV_ORIGIN = "https://workforcewv.org"
# Known cumulative summary PDF (verified live 2026-07-20). Discovery also scans
# the landing page for newer "WV-WARN-Notices-...to....pdf" summaries.
_WV_KNOWN_SUMMARIES = [
    "https://workforcewv.org/wp-content/uploads/2024/10/WV-WARN-Notices-1-1-22-to-10-7-24-.pdf",
]
_WV_SUMMARY_RE = re.compile(r'href="([^"]*WV-WARN-Notices-[\d\-]+to[\d\-]+\.pdf)"', re.I)


def _wv_flush(rec, url, out, seen):
    """Turn one accumulated WV record-card dict into an entry (dedup by hash)."""
    company = rec.get("company", "")
    jobs = _count(rec.get("number", ""))
    date = _iso(rec.get("projected", "")) or _iso(rec.get("notice", ""))
    e = _entry("WV", company, jobs, date, kind=_kind_norm(rec.get("kind", "")),
               detail_url=url)
    if e and e["dedup_hash"] not in seen:
        seen.add(e["dedup_hash"])
        out.append(e)


def fetch_wv():
    """WorkForce WV multi-year SUMMARY PDFs (label/value record cards).

    The rolling listing's per-notice PDFs are freeform letters (many are
    image-only scans) with no reliable count, so they are deliberately NOT
    parsed. We only read the structured summary PDFs. Summaries overlap heavily,
    so entries are de-duplicated by hash within this fetcher. Fail-isolated per
    PDF."""
    urls = list(_WV_KNOWN_SUMMARIES)
    try:
        page = requests.get(_WV_LANDING, headers=UA, timeout=TIMEOUT)
        for href in _WV_SUMMARY_RE.findall(page.text):
            url = href if href.lower().startswith("http") else _WV_ORIGIN + href
            if url not in urls:
                urls.append(url)
    except Exception as exc:
        print(f"    WV: landing page failed ({exc}); using known summary only")

    out, seen = [], set()
    for url in urls:
        try:
            resp = requests.get(url, headers=UA, timeout=90)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                continue
            tables = _pdf_tables(resp.content)
        except Exception as exc:
            print(f"    WV {url.rsplit('/', 1)[-1]}: fetch/parse failed ({exc})")
            continue
        rec = {}
        for table in tables:
            for row in table:
                label = _cell(row, 0).lower()
                value = " ".join(c for c in (_cell(row, i) for i in range(1, len(row))) if c)
                if label.startswith("company"):
                    if rec:
                        _wv_flush(rec, url, out, seen)
                    rec = {"company": value}
                elif label.startswith("date of notice"):
                    rec["notice"] = value
                elif label.startswith("projected date"):
                    rec["projected"] = value
                elif label.startswith("closure/mass") or label.startswith("closure"):
                    rec["kind"] = value
                elif label.startswith("number affected"):
                    rec["number"] = value
        if rec:
            _wv_flush(rec, url, out, seen)
    return out


# --------------------------------------------------------------------------- HI
_HI_YEAR_URL = "https://labor.hawaii.gov/wdc/{year}-warn-notices/"
# Inline count is essentially never present in the HI listing, but if it is, it
# looks like "45 employees" / "45 workers" / "45 positions affected".
_HI_COUNT_RE = re.compile(r"(\d[\d,]*)\s*(?:employees|workers|positions|jobs|affected)", re.I)
# A listing paragraph: "<Month> <day>, <year> - <a href=pdf>Company</a> ...".
_HI_ENTRY_RE = re.compile(
    r"<p>\s*("
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4})"
    r".*?<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>(.*?)</p>",
    re.I | re.S)


def _hi_clean(text):
    import html as _html
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def fetch_hi():
    """Hawaii WDC per-year listing pages.

    HI publishes only "<date> - <company>" in HTML and its notice PDFs are image
    scans (no text layer, no OCR here), so there is no headcount to read. This
    fetcher therefore emits a row ONLY when a count appears inline in the listing
    text -- which is currently never -- and SKIPS the rest rather than guess. It
    will start yielding rows automatically if HI ever adds inline counts. Each
    year is fail-isolated."""
    out = []
    years = sorted({2023, 2024, 2025, _date.today().year, _date.today().year + 1})
    for year in years:
        url = _HI_YEAR_URL.format(year=year)
        try:
            resp = requests.get(url, headers=UA, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            html_text = re.sub(r"<script.*?</script>", "", resp.text, flags=re.S | re.I)
        except Exception as exc:
            print(f"    HI {year}: listing failed ({exc})")
            continue
        for m in _HI_ENTRY_RE.finditer(html_text):
            date = _iso(_hi_clean(m.group(1)))
            company = _hi_clean(m.group(3))
            href = m.group(2).strip()
            tail = _hi_clean(m.group(4))
            cm = _HI_COUNT_RE.search(tail) or _HI_COUNT_RE.search(_hi_clean(m.group(3)))
            if not cm:
                continue  # no headcount in the listing -> skip, never guess
            jobs = _count(cm.group(1))
            e = _entry("HI", company, jobs, date, detail_url=href or url)
            if e:
                out.append(e)
    return out


# --------------------------------------------------------------------------- NM
_NM_PDF_URL = "https://www.dws.nm.gov/Portals/0/DM/Business/{year}_WARN.pdf"


def _nm_header_map(cells):
    """Map an NM header row to field->index, or None if it isn't the header."""
    idx = {}
    for i, c in enumerate(cells):
        lc = re.sub(r"\s+", " ", (c or "")).strip().lower()
        if "job site" in lc:
            idx["company"] = i
        elif "total layoff" in lc or lc == "number" or "layoff number" in lc:
            idx["jobs"] = i
        elif "layoff date" in lc:
            idx["eff"] = i
        elif "received" in lc:
            idx["recv"] = i
        elif "notice date" in lc:
            idx["notice"] = i
        elif "city" in lc:
            idx["city"] = i
        elif "county" in lc:
            idx["county"] = i
    return idx if "company" in idx and "jobs" in idx else None


def fetch_nm():
    """New Mexico DWS annual WARN PDFs (gridded table).

    Effective date falls back Layoff -> Received -> Notice; city falls back to
    county. Header-keyed columns so a year with a slightly different layout still
    parses (or yields nothing, never a guess). Each year fail-isolated."""
    out = []
    years = sorted({_date.today().year, _date.today().year - 1, _date.today().year - 2},
                   reverse=True)
    for year in years:
        url = _NM_PDF_URL.format(year=year)
        try:
            resp = requests.get(url, headers=UA, timeout=60)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                continue
            tables = _pdf_tables(resp.content)
        except Exception as exc:
            print(f"    NM {year}: fetch/parse failed ({exc})")
            continue
        for table in tables:
            cols = None
            for row in table:
                cells = [_cell(row, i) for i in range(len(row))]
                hdr = _nm_header_map(cells)
                if hdr:
                    cols = hdr
                    continue
                if not cols:
                    continue
                get = lambda k: cells[cols[k]] if k in cols and cols[k] < len(cells) else ""
                jobs = _count(get("jobs"))
                date = (_iso(get("eff")) or _iso(get("recv"))
                        or _iso(get("notice")))
                city = get("city") or get("county")
                e = _entry("NM", get("company"), jobs, date, city, detail_url=url)
                if e:
                    out.append(e)
    return out


# Gated: intentionally separate from warn_custom.CUSTOM_STATES until validated.
# --- Washington (ESD "fortress" GridView, per-notice PDF links) -------------
# WA is served here (not via generic warn-scraper) so each entry's source_url is
# the notice's OWN DownloadFile PDF, not just the ESD landing page. source_list_url
# stays the landing page (set server-side from STATE_WARN_URL). Re-imports upsert
# by dedup_hash (URL-independent), so existing area-only WA rows get their PDF
# link retroactively. Verified live: 81 2026 notices, all unique real PDFs.
_WA_SEARCH = "https://fortress.wa.gov/esd/file/WARN/Public/SearchWARN.aspx"
_WA_BASE = "https://fortress.wa.gov"


def _wa_city(loc):
    loc = re.sub(r"\s+", " ", (loc or "").strip())
    return "" if (not loc or re.search(r"various|statewide|multiple|throughout|remote", loc, re.I)) else loc


def fetch_wa(max_pages=200):
    """WA ESD WARN via the fortress ASP.NET GridView. Newest-first by received
    date; each row carries its own PDF link. _entry drops pre-2015 rows (coverage
    floor), so old pages yield nothing and we stop after two dry pages."""
    from bs4 import BeautifulSoup  # provided by warn-scraper's deps
    s = requests.Session()
    r = s.get(_WA_SEARCH, headers=UA, timeout=TIMEOUT); r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out, seen, page, dry = [], set(), 1, 0
    while page <= max_pages:
        gv = soup.find("table", id="ucPSW_gvMain")
        kept_this_page = 0
        for tr in (gv.find_all("tr") if gv else []):
            tds = tr.find_all("td", recursive=False)
            if len(tds) != 8:
                continue
            link = tds[7].find("a", href=lambda h: h and "DownloadFile" in h)
            if not link:
                continue
            url = link["href"] if link["href"].startswith("http") else _WA_BASE + link["href"]
            if url in seen:
                continue
            date = _to_iso_date(tds[2].get_text(strip=True)) or _to_iso_date(tds[6].get_text(strip=True))
            e = _entry("WA", tds[0].get_text(strip=True), _count(tds[3].get_text(strip=True)),
                       date, _wa_city(tds[1].get_text()), detail_url=url)
            if e:
                seen.add(url); out.append(e); kept_this_page += 1
        dry = dry + 1 if kept_this_page == 0 else 0
        if dry >= 2:
            break
        nxt = "Page$%d" % (page + 1)
        if not any(nxt in a.get("href", "") for a in soup.find_all("a")):
            break
        form = {i.get("name"): i.get("value", "") for i in soup.find_all("input", type="hidden") if i.get("name")}
        form["__EVENTTARGET"] = "ucPSW$gvMain"; form["__EVENTARGUMENT"] = nxt; form["ucPSW$txtSearch"] = ""
        r = s.post(_WA_SEARCH, data=form, headers={**UA, "Referer": _WA_SEARCH}, timeout=TIMEOUT)
        r.raise_for_status(); soup = BeautifulSoup(r.text, "html.parser"); page += 1
    return out


NEW_CUSTOM_STATES = {"MS": fetch_ms, "WV": fetch_wv, "HI": fetch_hi, "NM": fetch_nm, "WA": fetch_wa}


if __name__ == "__main__":
    # Smoke test: hit one real page/PDF per state and report counts so a manual
    # run can validate before these get wired into the cron. No fake data.
    for st, fn in NEW_CUSTOM_STATES.items():
        try:
            rows = fn()
            print(f"{st}: {len(rows)} entries")
            for r in rows[:3]:
                print(f"    {r['company_name']!r} | {r['job_count']} | "
                      f"{r['layoff_date']} | {r.get('state')}")
        except Exception as exc:
            print(f"{st}: FAILED ({exc})")
