"""
Custom WARN collectors for four states the open-source warn-scraper does not
cover: MS, WV, HI, NM.

STATUS: LIVE. Validated live on 2026-07-20 (MS 129 / WV 24 / NM 11 notices;
HI 0 by design) and wired into the daily sweep via `warn_import.py`, which calls
`NEW_CUSTOM_STATES` and guards each with a zero-result drift tripwire. Set
`WARN_SKIP_NEW_STATES=1` to disable if a source ever breaks. Every entry flows
through the same `_entry(...)` factory as warn_custom.py, so hashes/dedup match
the rest of WARN.

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

  AL  Alabama's headerless CSV export (workforce.alabama.gov). Taken over from
      the open scraper on 2026-08-02 after Alabama retired the madeinalabama.com
      page the released module still parses. Strict 8-column positional parse;
      keyed on date_action (the effective date), which is what the generic tier
      used, so re-imports upsert onto the existing dedup hashes.

CRITICAL: conservative parsing throughout. If a row does not cleanly yield
company + count + date, it is SKIPPED (fewer rows) rather than guessed. A wrong
number is far worse than a missing one.
"""
import html as _html_mod
import re
import time
from datetime import date as _date, timedelta as _timedelta

import requests

from .warn import _count, _to_iso_date, STATE_WARN_URL
from .warn_custom import _entry, _pdf_tables, _pdf_text  # noqa: F401  (_pdf_text kept for parity)
from .warn_llm import llm_count_from_text

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
                # Collapse away empty/None cells; survivors keep left-to-right
                # order in BOTH the old combined-locator layout AND the 2026+
                # layout that split "Company (City)(County)" into three columns.
                comp = [c.strip() for c in (("" if v is None else str(v)) for v in row)
                        if c and c.strip()]
                if len(comp) < 8:
                    continue
                # Anchor on the 'Type of Action' cell by its Layoff/Closure token
                # instead of a fixed index: MS shifted the grid right in 2026 by
                # splitting City/County into their own columns. In EVERY layout the
                # order is  Type | # Affected | Date of Action, so read the two
                # cells after Type. notice=comp[0] and company=comp[1] stay stable.
                # The token also rejects header and multi-line continuation rows.
                kind_idx = next((i for i, c in enumerate(comp)
                                 if re.fullmatch(r"(?:layoffs?|closures?)", c.strip(), re.I)),
                                None)
                if kind_idx is None or kind_idx < 2 or kind_idx + 2 >= len(comp):
                    continue
                kind_raw = comp[kind_idx]
                jobs = _count(comp[kind_idx + 1])
                date = _iso(comp[kind_idx + 2]) or _iso(comp[0])
                company, city = _ms_company_city(comp[1])
                # 2026+ split layout carries City as its own cell (comp[2]); the
                # old combined layout keeps it inside the company cell (already
                # handled by _ms_company_city), so only reach for comp[2] on the
                # wider shifted rows when no city was found.
                if not city and kind_idx >= 7:
                    city = re.sub(r"\s+", " ", comp[2]).strip()
                if jobs <= 0:  # grid shifted; let the LLM find the count in the row
                    jobs = llm_count_from_text(" ".join(comp), f"MS {company}")
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
# The summary filename carries its own coverage window: "...-1-1-22-to-1-3-25.pdf".
# We read the END of that window rather than hardcoding a cutoff, so the day WV
# posts a wider summary the per-notice tier stands down for the newly covered
# span on its own instead of double-sourcing it.
_WV_SUMMARY_SPAN_RE = re.compile(
    r"WV-WARN-Notices-[\d\-]+to-?(\d{1,2})-(\d{1,2})-(\d{2,4})", re.I)
# One `<details><summary>YYYY WARN Listings</summary> ... </details>` block per
# year on the landing page; each holds one `<p><a href="...pdf">Label</a></p>`
# per notice. The YEAR is the block's, which is what dates a notice whose
# filename carries no date at all ("WARN-VIMO-INC.pdf").
_WV_DETAILS_RE = re.compile(r"<details[^>]*>(.*?)</details>", re.S | re.I)
_WV_YEAR_RE = re.compile(r"<summary[^>]*>\s*(20\d\d)\b", re.I)
_WV_PDF_LINK_RE = re.compile(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
# A date inside the label or the filename: "6-4-26", "8-1-24", "6-4-2021",
# "04_1_2026". Two-digit years are 20xx (WV has posted nothing pre-2000).
# The separator may be "-", "_" OR a space, because underscores in a filename
# ("Mettiki_Supplemental_..._04_1_2026") become spaces before the name is
# cleaned. Without the space alternative that date survived into the employer
# name as "Mettiki 04 1 2026".
_WV_LABEL_DATE_RE = re.compile(r"(\d{1,2})[-_ ](\d{1,2})[-_ ](\d{2,4})\b")
# Boilerplate around the employer name in a link label: "Greenbrier Minerals
# WARN 2-13-26", "WARN Notice State - West Virginia Conduent", "Carter Roag WARN
# Update 6-19-23", "CV2 Prep Plant r1 WARN 6-4-25".
_WV_LABEL_NOISE_RE = re.compile(
    r"\b(?:warn(?:ing)?|notice[sd]?|state|received|revised|signed|update[sd]?|"
    r"supplemental|listing[s]?|download|pdf|west\s+virginia|wv|r\d)\b", re.I)
# Counts as WV letters actually phrase them. Deliberately narrow: each pattern
# binds the number to layoff language, so a ZIP code, a street number or a
# year can never be read as a headcount. Anything these miss falls through to
# the shared LLM fallback, which is itself gated and must find the number
# verbatim in the text.
_WV_COUNT_RES = [
    re.compile(r"(?:terminate|separat\w*|eliminat\w*|affect\w*|lay(?:ing|\s*)?off\w*)"
               r"[^.\n]{0,60}?\b(?:approximately\s+|about\s+|up\s+to\s+)?"
               r"(\d[\d,]*)\s+(?:employees|workers|positions|jobs|people)", re.I),
    # The number and its unit word are often separated by the employer's own
    # name: "approximately 71 Greenbrier Mineral employees ... will be
    # terminated". Allow a few capitalised words between the two, but still
    # require the layoff verb after them, so a street number cannot qualify.
    re.compile(r"\b(?:approximately|about|up\s+to)\s+(\d[\d,]*)\s+"
               r"(?:[A-Z][\w.&-]*\s+){0,4}"
               r"(?:employees|workers|positions|jobs|people)\b"
               r"[^.\n]{0,80}?(?:will\s+be|are|shall\s+be|to\s+be)\s+"
               r"(?:terminated|separated|laid\s+off|affected|impacted|eliminated)", re.I),
    re.compile(r"\b(\d[\d,]*)\s+(?:employees|workers|positions|jobs)\b"
               r"[^.\n]{0,60}?(?:will\s+be|are|shall\s+be)\s+"
               r"(?:terminated|separated|laid\s+off|affected|impacted)", re.I),
    re.compile(r"(?:total\s+)?number\s+of\s+(?:affected\s+)?(?:employees|workers|"
               r"positions)[^.\n]{0,40}?\bis\s+(\d[\d,]*)", re.I),
    re.compile(r"(?:employees|workers|positions)\s+affected\s*[:\-]\s*(\d[\d,]*)", re.I),
]


def _wv_label_company(label, filename):
    """Employer name out of a listing link label (falls back to the filename).

    The label is the only place WV names the employer for a per-notice letter --
    the letter itself leads with a signatory and an address, not a company
    field. Strip the WARN boilerplate and the date, keep the rest verbatim; a
    label that cleans away to nothing yields "" and the notice is dropped rather
    than published under a guessed name."""
    text = _html_mod.unescape(re.sub(r"<[^>]+>", " ", label or ""))
    text = text.replace("_", " ")
    if not re.search(r"[A-Za-z]", text):
        text = re.sub(r"[-_]+", " ", (filename or "").rsplit(".", 1)[0])
    text = _WV_LABEL_DATE_RE.sub(" ", text)
    text = _WV_LABEL_NOISE_RE.sub(" ", text)
    # Leftover separators and a trailing bare month ("Greenbrier Minerals July").
    text = re.sub(r"^[\s\-–—:,]+|[\s\-–—:,]+$", " ", text)
    text = re.sub(r"\s*(?:January|February|March|April|May|June|July|August|"
                  r"September|October|November|December)\s*$", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -–—:,")
    return text if re.search(r"[A-Za-z]", text) else ""


def _wv_notice_count(text, label):
    """Affected-employee count from one WV notice letter, or 0."""
    for rx in _WV_COUNT_RES:
        m = rx.search(text or "")
        if m:
            n = _count(m.group(1))
            if 0 < n <= 100000:
                return n
    return llm_count_from_text(text, label)


def _wv_ocr_enabled():
    """WV OCR is opt-in (WV_OCR=1). Dormant by default: it needs the tesseract
    system binary, which the lean daily workflows deliberately do not install,
    and its counts must be eyeballed in a dry run before they are published."""
    import os
    return os.environ.get("WV_OCR") == "1"


def _wv_ocr(content, label=""):
    """OCR one image-only WV notice, or "" if OCR is unavailable. Never raises.

    Delegates to the Hawaii OCR renderer so there is ONE OCR implementation:
    the two states pose the identical problem (a scanned WARN letter whose
    headcount exists only as pixels) and a second copy would drift."""
    try:
        from .warn_hi_ocr import _ocr_pdf
        return _ocr_pdf(content)
    except Exception as exc:
        print(f"    WV {label}: OCR unavailable/failed ({exc})")
        return ""


def _wv_summary_cutoff(urls):
    """Latest ISO date the cumulative summary PDFs already cover, or ""."""
    best = ""
    for u in urls:
        m = _WV_SUMMARY_SPAN_RE.search(u)
        if not m:
            continue
        mo, day, yr = m.groups()
        yr = int(yr)
        iso = _iso(f"{mo}/{day}/{yr if yr > 99 else 2000 + yr}")
        if iso > best:
            best = iso
    return best


def _wv_per_notice(page_html, cutoff, out, seen):
    """Parse the rolling listing's per-notice PDFs (the tier the summaries stop
    short of). The summaries end 2025-01-03 and WV has not published a newer
    one, so from 2025 onward these letters ARE the state's WARN record -- the
    old 'freeform, therefore skip' rule silently zeroed WV for two years."""
    kept = 0
    for block in _WV_DETAILS_RE.findall(page_html or ""):
        ym = _WV_YEAR_RE.search(block)
        block_year = ym.group(1) if ym else ""
        for href, label in _WV_PDF_LINK_RE.findall(block):
            if _WV_SUMMARY_RE.search(f'href="{href}"'):
                continue  # the cumulative summary, parsed by the other tier
            url = href if href.lower().startswith("http") else _WV_ORIGIN + href
            fname = url.rsplit("/", 1)[-1]
            dm = (_WV_LABEL_DATE_RE.search(_html_mod.unescape(re.sub(r"<[^>]+>", " ", label)))
                  or _WV_LABEL_DATE_RE.search(fname))
            date = ""
            if dm:
                mo, day, yr = dm.groups()
                yr = int(yr)
                date = _iso(f"{mo}/{day}/{yr if yr > 99 else 2000 + yr}")
            # A notice the cumulative summary already carries would be a second
            # copy of the same event under a differently-spelled employer, which
            # is exactly the cross-collector duplicate _entry's hash cannot
            # catch. Undated notices are judged by their block's year.
            if cutoff:
                if date and date <= cutoff:
                    continue
                if not date and block_year and block_year <= cutoff[:4]:
                    continue
            company = _wv_label_company(label, fname)
            if not company:
                print(f"    WV {fname}: no employer name in the link label; skipped")
                continue
            try:
                resp = requests.get(url, headers=UA, timeout=90)
                if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                    continue
                text = _pdf_text(resp.content)
            except Exception as exc:
                print(f"    WV {fname}: fetch/parse failed ({exc})")
                continue
            if len(re.sub(r"\s+", "", text or "")) < 40:
                # Image-only scan. 21 of WV's 27 post-cutoff letters are these,
                # so they are the state's real coverage ceiling, not an edge
                # case. OCR is the same problem Hawaii already solved, so it
                # reuses that module rather than growing a second extractor --
                # and it stays DORMANT (WV_OCR=1) until a human has eyeballed a
                # dry run, exactly as the HI path was promoted.
                ocr_text = _wv_ocr(resp.content, fname) if _wv_ocr_enabled() else ""
                if len(re.sub(r"\s+", "", ocr_text)) < 40:
                    print(f"    ::notice:: WV {fname}: image-only scan, no text layer "
                          f"— {company} not countable")
                    continue
                text = ocr_text
            if not date:
                date = _iso_from_text(text)
            jobs = _wv_notice_count(text, f"WV {company}")
            if jobs <= 0:
                print(f"    ::notice:: WV {fname}: no affected-employee count in the "
                      f"letter — {company} not countable")
                continue
            kind = "Closure" if re.search(r"\bclosure|closing|shut\s*down|wind\s*down"
                                          r"|permanent(?:ly)?\s+clos", text, re.I) else "Layoff"
            e = _entry("WV", company, jobs, date, kind=kind, detail_url=url)
            if e and e["dedup_hash"] not in seen:
                seen.add(e["dedup_hash"])
                out.append(e)
                kept += 1
    return kept


_WV_TEXT_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2}),?\s+(20\d\d)\b", re.I)


def _iso_from_text(text):
    """First long-form date in a notice letter (its dateline), or ""."""
    m = _WV_TEXT_DATE_RE.search(text or "")
    return _iso(f"{m.group(1)} {m.group(2)}, {m.group(3)}") if m else ""


def _wv_flush(rec, url, out, seen):
    """Turn one accumulated WV record-card dict into an entry (dedup by hash)."""
    company = rec.get("company", "")
    jobs = _count(rec.get("number", ""))
    if jobs <= 0:  # card label may have changed; read the whole record card
        jobs = llm_count_from_text(" ".join(f"{k}: {v}" for k, v in rec.items()), f"WV {company}")
    date = _iso(rec.get("projected", "")) or _iso(rec.get("notice", ""))
    e = _entry("WV", company, jobs, date, kind=_kind_norm(rec.get("kind", "")),
               detail_url=url)
    if e and e["dedup_hash"] not in seen:
        seen.add(e["dedup_hash"])
        out.append(e)


def fetch_wv():
    """WorkForce WV, in two tiers.

    1. The multi-year cumulative SUMMARY PDFs (label/value record cards). These
       parse cleanly but the newest one WV has published stops at 2025-01-03.
    2. The rolling listing's PER-NOTICE PDFs, for everything after that cutoff.

    Tier 2 used to be skipped on the grounds that the letters are freeform and
    some are image-only scans. Both facts are true and neither justified the
    result: with no newer summary, skipping them meant WV reported ZERO notices
    for all of 2025 and 2026 while the state was publishing them the whole time.
    Tier 2 now reads each letter, takes the count only from layoff-bound
    phrasing (or the gated LLM fallback), and prints a per-notice line for the
    scans it genuinely cannot read, so the residue is visible rather than
    silent. The cutoff comes from the summary filenames, so a newer summary
    hands its span back to tier 1 automatically.

    Summaries overlap heavily, so entries are de-duplicated by hash within this
    fetcher. Fail-isolated per PDF."""
    urls = list(_WV_KNOWN_SUMMARIES)
    page_html = ""
    try:
        page = requests.get(_WV_LANDING, headers=UA, timeout=TIMEOUT)
        page_html = page.text
        for href in _WV_SUMMARY_RE.findall(page_html):
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

    summary_n = len(out)
    cutoff = _wv_summary_cutoff(urls)
    if page_html:
        kept = _wv_per_notice(page_html, cutoff, out, seen)
        print(f"    WV: {summary_n} from summary PDFs (through {cutoff or 'unknown'}), "
              f"{kept} from per-notice letters after that")
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
    return _html_mod.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


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
            jobs = _count(tds[3].get_text(strip=True))
            if jobs <= 0:  # column may have shifted; read the whole row
                jobs = llm_count_from_text(" ".join(td.get_text(" ", strip=True) for td in tds),
                                           f"WA {tds[0].get_text(strip=True)}")
            e = _entry("WA", tds[0].get_text(strip=True), jobs,
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


# Hawaii is handled by the dedicated OCR importer (railway/hi_warn_import.py +
# sources/warn_hi_ocr.py) because its notices are image scans, so it is NOT in
# this list. The old no-op fetch_hi (list-page parse, never yielded a count) is
# kept below only for reference.

# --------------------------------------------------------------------------- KS
# Kansas (kansasworks.com). The open warn-scraper's KS module walks the ENTIRE
# warn_lookups history and started timing out (420s per run, every run) around
# 2026-05, leaving Kansas dark for ~3 months. The portal itself is fine when
# asked a bounded question: a Ransack date filter returns instantly. So this
# fetcher asks only for notices from the last ~15 months and reads each row's
# detail page for the one field the listing omits, the affected-employee count.
# Historical KS rows (799 of them) already exist from when the generic tier
# worked; re-imports upsert by dedup_hash, so no purge is needed.
#
# ORDERING (2026-08-19). The bounds below are RUNTIME bounds, and they are only
# ever allowed to decide HOW MANY notices a run reads, never WHICH ones. That
# distinction was not being kept. kansasworks serves this listing OLDEST-FIRST by
# default -- page 1 is 1998-2000 and the newest notice sits ~35 pages in -- so
# truncating in listing order reads the oldest N notices every run, keeps
# returning a healthy-looking non-zero count, and never reaches a new filing.
# Raising the cap does not fix it; a cap over an unordered listing is unsafe at
# every value, because it breaks again one notice past the new one.
#
# So the fetcher asks for `q[s]=notice_on desc` (Ransack's sort, which the
# portal's own column headers use) AND re-establishes that order locally from
# each row's Notice Date. Nothing depends on the server honouring the sort: if it
# ignores the parameter, the local sort still puts the newest first, and the cap
# can then only ever discard the OLDEST rows. `tests/test_ks_warn_ordering.py`
# serves a deliberately oldest-first listing to pin exactly that.
_KS_BASE = "https://www.kansasworks.com"
_KS_LIST = (_KS_BASE + "/search/warn_lookups?commit=Search"
            "&q%5Bnotice_on_gteq%5D={since}&q%5Bs%5D=notice_on+desc&page={page}")
_KS_DETAIL_RX = re.compile(r'href="(/search/warn_lookups/(\d+))"')
_KS_ROW_DATE_RX = re.compile(r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})")
_KS_MAX_DETAILS = 150   # bound the per-run detail fetches; the window is small
_KS_MAX_PAGES = 8       # listing pages to walk; 25/page, the window holds ~12


def _ks_listing_rows(html_text):
    """Ordered unique [(id, notice_iso_or_"")] from a listing page.

    A listing row is the detail link followed by City / ZIP / LWIB area / Notice
    Date / WARN Type. The date is read for ORDERING ONLY -- the detail page stays
    the sole authority for every field that gets stored -- so a miss here costs
    ordering precision, never correctness of a row.
    """
    seen, out = set(), []
    for block in re.split(r"<tr\b", html_text or "", flags=re.I)[1:]:
        m = _KS_DETAIL_RX.search(block)
        if not m:
            continue
        nid = m.group(2)
        if nid in seen:
            continue
        seen.add(nid)
        d = _KS_ROW_DATE_RX.search(re.sub(r"<[^>]+>", " ", block))
        out.append((nid, _iso(d.group(1)) if d else ""))
    return out


def _ks_listing_ids(html_text):
    """Ordered unique detail-page ids from a listing page."""
    return [nid for nid, _ in _ks_listing_rows(html_text)]


def _ks_newest_first(rows):
    """[(id, iso)] -> ids, newest notice first, so a cut can only drop the oldest.

    A row whose Notice Date did not parse has UNKNOWN recency, and unknown is
    NOT old: it sorts FIRST, so a markup change to that one column can cost a
    wasted detail fetch but can never push a new notice into the tail the
    per-run bound discards.
    """
    undated = [nid for nid, iso in rows if not iso]
    dated = sorted(((iso, nid) for nid, iso in rows if iso), reverse=True)
    return undated + [nid for _, nid in dated]


def _ks_detail_fields(html_text):
    """(company, city, notice_iso, jobs) from a detail page, all "" / 0 when absent.

    The page is a label/value list: Company Name / Address / Notice Date /
    Number of Employees Affected. Parsed as flattened text lines so markup
    changes that keep the labels do not break it.
    """
    txt = re.sub(r"<script.*?</script>", " ", html_text or "", flags=re.S)
    txt = re.sub(r"<[^>]+>", "\n", txt)
    lines = [_html_mod.unescape(l).strip() for l in txt.split("\n")]
    lines = [l for l in lines if l]
    company = city = date = ""
    jobs = 0
    for i, line in enumerate(lines):
        low = line.lower()
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if low == "company name" and not company:
            company = nxt
        elif low == "address" and not city:
            # Address block: street, then "City, Kansas 66801". Take the city
            # from the LAST address-looking line before the next label.
            for cand in lines[i + 1:i + 4]:
                m = re.match(r"([A-Za-z .\'-]+),\s*Kansas\b", cand)
                if m:
                    city = m.group(1).strip()
                    break
        elif low == "notice date" and not date:
            date = _iso(nxt)
        elif low == "number of employees affected" and not jobs:
            m = re.search(r"\d[\d,]*", nxt)
            if m:
                jobs = int(m.group(0).replace(",", ""))
    return company, city, date, jobs


def fetch_ks():
    """Kansas WARN via bounded kansasworks queries + per-notice detail pages."""
    since = (_date.today() - _timedelta(days=456)).isoformat()   # ~15 months
    rows, seen, out = [], set(), []
    for page in range(1, _KS_MAX_PAGES + 1):
        try:
            resp = requests.get(_KS_LIST.format(since=since, page=page),
                                headers=UA, timeout=45)
            if resp.status_code != 200:
                break
            page_rows = _ks_listing_rows(resp.text)
        except Exception as exc:
            print(f"    KS listing page {page}: {exc}")
            break
        new = [r for r in page_rows if r[0] not in seen]
        if not new:
            break                                                # past the end
        seen.update(nid for nid, _ in new)
        rows.extend(new)
    # Newest first, so the bound below trims the OLDEST tail and can never be
    # the reason a new notice went unread. See the ordering note above _KS_LIST.
    ids = _ks_newest_first(rows)
    if len(ids) > _KS_MAX_DETAILS:
        print(f"    KS: {len(ids)} notices listed, reading the newest "
              f"{_KS_MAX_DETAILS}")
    for nid in ids[:_KS_MAX_DETAILS]:
        try:
            resp = requests.get(f"{_KS_BASE}/search/warn_lookups/{nid}",
                                headers=UA, timeout=45)
            if resp.status_code != 200:
                continue
            company, city, date, jobs = _ks_detail_fields(resp.text)
        except Exception as exc:
            print(f"    KS detail {nid}: {exc}")
            continue
        e = _entry("KS", company, jobs, date, city,
                   detail_url=f"{_KS_BASE}/search/warn_lookups/{nid}")
        if e:
            out.append(e)
        time.sleep(0.4)                                          # polite
    print(f"WARN KS (custom): {len(out)} notices kept from {len(ids)} listed")
    return out


# --------------------------------------------------------------------------- AL
# Alabama. The open warn-scraper's AL module (PyPI 1.2.143, the newest release)
# still parses an HTML <table> on the OLD madeinalabama.com page. Alabama moved
# the list to workforce.alabama.gov during 2026 and now blocks automated reads of
# the human-facing page, so the table selector matches nothing and the module
# dies on `table[0]` with IndexError. `_run_scraper` calls it with check=False,
# so the traceback went to the log and the sweep carried on with no al.csv --
# Alabama simply vanished from the per-state counts (851 -> 0 on 2026-08-02).
#
# The state does still publish the same data as a headerless CSV, and that
# endpoint is not blocked (robots.txt disallows only /wp-content/uploads/).
# Upstream git has already switched to it, but that fix is unreleased and imports
# `niquests`, which is not in the installed dependency set -- injecting the file
# the way the workflow injects nd.py would ImportError. So AL follows the same
# route KS and WA took: a bounded custom fetcher here, and AL dropped from
# warn.ALL_STATES so the broken module is no longer run at all.
#
# Columns are positional and headerless:
#   0 _id1 | 1 action_type | 2 date_notice | 3 date_action | 4 company
#   5 location | 6 affected | 7 _id2
#
# layoff_date is keyed on date_NOTICE, not date_action, and that is deliberate.
# date_action is the effective date, which is the tracker's usual preference, but
# the retired HTML-table module wrote an al.csv whose column names made warn.py's
# `_date_from` land on the notice date, so that is what every stored Alabama row
# already holds -- verified 2026-08-02 against the live API for six notices where
# the two dates differ (BASF 07/22 not 09/30, LineQuest 04/23 not 08/01, Legacy
# Cabinets 06/11 not 06/06, Serta 04/15 not 04/17, ...). dedup_hash is
# company+date+jobs+state, so switching to the effective date would give all 272
# rows NEW hashes and duplicate Alabama against the 825 rows already published
# rather than upserting onto them. Re-keying to the effective date is a real
# improvement, but it is a /bulk-purge + full re-import job (see CLAUDE.md), not
# something to slip into an outage fix.
_AL_CSV = "https://workforce.alabama.gov/documents/warn-list/"
_AL_COLS = 8


def _al_name(value):
    """Alabama company/location text in the form the tracker already stores.

    company feeds dedup_hash, so this fetcher has to reproduce the retired HTML
    module's strings EXACTLY or every Alabama notice publishes a second copy of a
    layoff already on the site. The CSV export differs from the page in three
    mechanical ways, all verified against all 825 stored AL rows on 2026-08-02:

      * the CSV pads names ("Salon Centric  Inc") where the page does not;
      * the page renders the apostrophe as U+2019 ("David's" -> "David’s"),
        37 stored rows;
      * the page renders the SPACED separator as an en dash U+2013
        ("WALMART - STORE #763" -> "WALMART – STORE #763"), 17 stored rows.

    Only the SPACED form becomes an en dash. Unspaced hyphens are part of the
    name ("Winn-Dixie", "JELD-WEN", "KMART CORPORATION-STORE 4836") and stay
    ASCII in all 80 stored rows that carry one, which is why this is a
    space-anchored substitution and not a bare character swap.

    With this applied, all 259 distinct notices the CSV yields hash onto rows
    that already exist -- 259 upserts, 0 new rows, 0 duplicates.
    """
    s = re.sub(r"\s+", " ", value or "").strip()
    return re.sub(r" - ", " – ", s.replace("'", "’"))


def fetch_al():
    """Alabama WARN via the state's headerless CSV export.

    Positional parse with a strict width check: a row that is not exactly 8
    fields is skipped rather than guessed at, so if Alabama ever adds or removes
    a column this returns fewer rows (which trips the zero-result drift alarm)
    instead of silently mis-assigning company/count/date.

    Note the coverage floor: `_entry` drops anything before 2015, which is the
    convention for every custom scraper, while the generic tier accepted 2002+.
    The pre-2015 Alabama rows are ALREADY stored from when the generic module
    worked and nothing purges them, so this narrows what is RE-imported each run,
    not what the tracker holds.
    """
    out = []
    try:
        resp = requests.get(_AL_CSV, headers=UA, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"    AL csv: HTTP {resp.status_code}")
            return out
        text = resp.text
    except Exception as exc:
        print(f"    AL csv: fetch failed ({exc})")
        return out
    # A blocked/redirected fetch returns the HTML page, not the CSV. Say so
    # loudly rather than returning 0 rows that look like a quiet week.
    if "<html" in text[:2000].lower():
        print("    AL csv: got HTML, not CSV — endpoint may now be blocked")
        return out
    import csv as _csv
    from io import StringIO as _StringIO
    for row in _csv.reader(_StringIO(text)):
        if len(row) != _AL_COLS:
            continue
        _, kind, date_notice, _date_action, company, location, affected, _ = row
        e = _entry("AL", _al_name(company), _count(affected), _iso(date_notice),
                   _al_name(location), kind=kind,
                   detail_url=STATE_WARN_URL.get("AL", ""))
        if e:
            out.append(e)
    print(f"WARN AL (custom): {len(out)} notices kept")
    return out


NEW_CUSTOM_STATES = {"MS": fetch_ms, "WV": fetch_wv, "NM": fetch_nm, "WA": fetch_wa,
                     "KS": fetch_ks, "AL": fetch_al}


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
