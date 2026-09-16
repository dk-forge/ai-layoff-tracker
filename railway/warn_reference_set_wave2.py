#!/usr/bin/env python3
"""US WARN reference set, wave 2 — Illinois, Ohio, Pennsylvania.

READ docs/recall-reference-sets/US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md FIRST.
It was committed before this file ran once, and if the two disagree the document
is right and this file is a bug. Wave 1's definition governs everything the
wave-2 document does not restate.

WHY IT EXISTS
-------------
Wave 1 measured four states — CA, TX, FL, TN — and said in its own §2 that it
had no Midwest state and no Northeast state, because NY, PA, IL, OH, MI, NJ and
MA were each excluded by the format of their own publication on 2026-08-13. It
said the honest expectation was therefore that its figure is an optimistic
bound on national WARN recall. Nothing measured that.

A live re-probe on 2026-09-16 found three of the four largest excluded states
now pass wave 1's own eligibility rule, unaltered:

  IL  monthly WARN report XLSX, one per month since 1999, on Illinois workNet
  OH  the state asset host's per-year WARN CSVs (the agency's index pages are
      still 404 — see the definition §2 and §5, the independence cost is real)
  PA  the department's own listing, server-side rendered, 2023..2026, on a URL
      wave 1 did not probe because the URL wave 1 probed 404s

New York remains out and the evidence is fresher than wave 1's: the legacy list
is frozen at 2025-04-01, three months before this window opens, and the Tableau
workbook wave 1 could at least download now returns 404.

WHAT IS IMPORTED RATHER THAN COPIED
-----------------------------------
Everything that decides a number. The collapse rule, the alias and query-term
derivation, the size bands, the exclusion reasons, the systematic draw, the seed,
the two candidate tiers, the match window, the summary and its Wilson intervals
all come from `warn_reference_set`. This module contributes THREE FRAME READERS
and its own constants, and nothing else. Two waves whose unit of measurement had
drifted apart could not be pooled at all, and a second copy of a collapse rule
is how that happens quietly.

WHAT IT MUST NOT DO
-------------------
It does not write wave 1's manifest or measurement, the SEC set's manifest or
measurement, or MATCHED_FLOOR. It does not promote its own recall: every
candidate arrives `not_matched` and the editor-confirmed numerator starts at
zero. A query that could not be sent or completed is UNKNOWN, never a miss.

No model is called. Cost against the monthly allowance: $0.00.

USAGE
    python3 railway/warn_reference_set_wave2.py --build     # re-enumerate, redraw
    python3 railway/warn_reference_set_wave2.py --measure   # frozen set vs live API
    python3 railway/warn_reference_set_wave2.py --pack      # adjudication sheet
"""
import csv
import html as _html
import io
import json
import re
import sys
import time
import urllib.parse
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_reference_set as W                                     # noqa: E402

HERE = Path(__file__).resolve().parent
REF_DIR = HERE.parent / "docs" / "recall-reference-sets"

REFERENCE_SET_ID = "us-warn-il-oh-pa-2025-07_2026-06"
MANIFEST_PATH = REF_DIR / "us-warn-il-oh-pa-2025-07_2026-06.goldset.json"
MEASUREMENT_PATH = HERE / "warn_recall_measurement_wave2.json"
QUEUE_JSON = REF_DIR / "us-warn-wave2-adjudication-queue.json"
QUEUE_MD = REF_DIR / "us-warn-wave2-adjudication-queue.md"
DEFINITION_DOC = ("docs/recall-reference-sets/"
                  "US-WARN-WAVE2-REFERENCE-SET-DEFINITION.md")

STATES = ("IL", "OH", "PA")
WINDOW = W.WINDOW                      # the same twelve months, imported

# Wave 1 read the state agencies behind a Chrome UA. This wave identifies
# itself instead, under the project's own agent string, and every one of the
# three publications answered it during the 2026-09-16 eligibility probe with
# nothing in its robots.txt disallowing it. Self-identifying is the direction
# this repo already chose when it refused to rename its agent to get past
# Virginia's block, and it costs nothing here.
SITE_UA = W.API_UA

DATE_FIELD_NOTE = (
    "published state RECEIVED date for IL and OH; PA publishes no per-notice "
    "date and its window is counted on the MONTH heading the notice is filed "
    "under, anchored at the first of that month -- see the wave-2 definition, "
    "SS3. Both window boundaries are month boundaries, so no PA event can "
    "straddle the frame edge.")

SOURCES = {
    "IL": {
        "publisher": "Illinois Department of Commerce and Economic Opportunity, "
                     "published through Illinois workNet",
        "document": "Monthly WARN Report, one XLSX per month (archive index)",
        "url": ("https://www.illinoisworknet.com/LayoffRecovery/Pages/"
                "ArchivedWARNReports.aspx"),
        "note": ("A DIFFERENT DOCUMENT from anything our Illinois collection "
                 "reads: a per-month spreadsheet archive, not the WARN search "
                 "application the DCEO page embeds. Carries the department's "
                 "own Total Layoff Events / Total Impacted footer, which this "
                 "module checks its parse against rather than trusting it."),
    },
    "OH": {
        "publisher": "Ohio Department of Job and Family Services",
        "document": "Per-year WARN notice CSV on the Ohio state asset host",
        "url": "https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/",
        "note": ("THE SAME FILES sources/warn_custom.fetch_oh reads, reached by "
                 "the same path, because every jfs.ohio.gov WARN index page "
                 "returns 404 and there is no second document. Independent of "
                 "our parser, cleaning, ordering, unit and matching; NOT "
                 "independent of our input file. Mitigated, not cured, by "
                 "transcription-verifying each sampled event against the "
                 "employer's own notice PDF, which the CSV links per row."),
    },
    "PA": {
        "publisher": "Pennsylvania Department of Labor and Industry",
        "document": "WARN Notices listing, 2023-2026, server-side rendered",
        "url": ("https://www.pa.gov/agencies/dli/programs-services/"
                "workforce-development-home/warn-requirements/warn-notices"),
        "note": ("Found from pa.gov's own published sitemap. Wave 1 recorded PA "
                 "as client-side rendered against a URL under "
                 "/workforce-development/ that now returns 404 -- a 404 is not "
                 "evidence about a publisher. Publishes no per-notice date; the "
                 "month heading is the window basis. The per-item CMS "
                 "repo:modifyDate is captured as supplementary evidence ONLY, "
                 "because a modify date moves when an entry is corrected and a "
                 "date that moves cannot define a frozen frame."),
    },
}

_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"), start=1)}
_MONTH_RX = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)(?![A-Za-z])", re.I)
# The trailing guard is a NEGATIVE LOOKAHEAD and not \b on purpose: Illinois
# names half its files `Jan2026MonthlyWARNReport.xlsx`, with no separator
# between the month and the year, so a word boundary after the month never
# matched and the 2026 half of the window looked like six missing months.
# A leading STATUS MARKER the state prepends to its own row when a notice is
# amended: `UPDATE Senior Resource Connection`, `UPDATED Eagle Machining - ...`.
# Six of Ohio's 81 in-window rows carry one. It is the state's bookkeeping, not
# part of the employer's name, and leaving it on makes every alias start with
# the word UPDATE -- so no query for that employer is ever sent and the event
# scores as a miss while the row sits in the table. That is the same defect
# class wave 1's address-cutting amendment fixed, handled the same way: cut it
# on the REFERENCE side, keep the raw string on the component row, and count
# how often it fired. See the wave-2 definition, AMENDMENT 2026-09-16.
_STATUS_MARKER = re.compile(
    r"^\s*(?:update[d]?|amend(?:ed|ment)?|revis(?:ed|ion)|corrected)\b[\s:.,-]*",
    re.I)
_XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_EXCEL_EPOCH = date(1899, 12, 30)       # Excel's own off-by-two serial origin


def _first_date(value):
    """The FIRST published date in a cell. Ohio writes ranges into Layoff Date(s)."""
    m = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}", str(value or ""))
    return W._iso(m.group(0)) if m else None


def _month_number(word):
    w = (word or "").strip().lower()
    if w in _MONTHS:
        return _MONTHS[w]
    for name, n in _MONTHS.items():
        if len(w) >= 3 and name.startswith(w):
            return n
    return None


def _window_months():
    """Every YYYY-MM the window touches, in order. Twelve of them."""
    out, cur = [], date.fromisoformat(WINDOW[0]).replace(day=1)
    last = date.fromisoformat(WINDOW[1]).replace(day=1)
    while cur <= last:
        out.append((cur.year, cur.month))
        cur = (cur.replace(day=28) + timedelta(days=7)).replace(day=1)
    return out


def _get(url, **kw):
    return W._get(url, ua=SITE_UA, **kw)


def _employer(raw):
    """(name for the frame, raw published string, whether a marker was cut)."""
    published = W.clean_published_name(raw)
    cut = _STATUS_MARKER.sub("", published).strip(" ,;-")
    # Never cut a name down to nothing, and never cut when what is left is too
    # short to identify an employer -- a marker that IS the name is not a marker.
    if len(cut) < 3 or not re.search(r"[A-Za-z]{3}", cut):
        return published, published, False
    return cut, published, cut != published


# ---------------------------------------------------------------------------
# Illinois: the monthly WARN report spreadsheets.
# ---------------------------------------------------------------------------
def _xlsx_rows(blob):
    """[{column letter: text}] for the first worksheet. Stdlib only.

    Written for this measurement. It resolves shared strings, keeps the cell's
    column letter so a blank cell cannot shift a row, and converts a numeric
    cell that a date style formats into an ISO date -- Illinois stores its
    WARN RECEIVED DATE as a bare Excel serial, and a serial read as a number is
    a silent wrong date rather than a parse error.
    """
    z = zipfile.ZipFile(io.BytesIO(blob))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter(_XL + "t")))
    # Which style ids are date formats: numFmtId in the built-in date range or
    # a custom format whose code contains a y/m/d pattern.
    date_styles = set()
    if "xl/styles.xml" in z.namelist():
        st = ET.fromstring(z.read("xl/styles.xml"))
        custom = {f.get("numFmtId"): (f.get("formatCode") or "")
                  for f in st.iter(_XL + "numFmt")}
        cellxfs = st.find(_XL + "cellXfs")
        for i, xf in enumerate(cellxfs or []):
            fmt = xf.get("numFmtId") or "0"
            code = custom.get(fmt, "")
            if fmt in {"14", "15", "16", "17", "22"} or re.search(r"[yY].*[dD]|[dD].*[yY]", code):
                date_styles.add(str(i))
    names = [n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)]
    sheet = ET.fromstring(z.read(sorted(names)[0]))
    rows = []
    for row in sheet.iter(_XL + "row"):
        cells = {}
        for c in row.iter(_XL + "c"):
            col = re.match(r"[A-Z]+", c.get("r") or "A").group()
            v = c.find(_XL + "v")
            kind = c.get("t")
            if kind == "s" and v is not None:
                text = shared[int(v.text)] if v.text and v.text.isdigit() else ""
            elif kind == "inlineStr":
                text = "".join(x.text or "" for x in c.iter(_XL + "t"))
            else:
                text = (v.text or "") if v is not None else ""
                if text and c.get("s") in date_styles:
                    try:
                        text = (_EXCEL_EPOCH + timedelta(days=int(float(text)))).isoformat()
                    except (ValueError, OverflowError):
                        pass
            cells[col] = (text or "").strip()
        if any(cells.values()):
            rows.append(cells)
    return rows


# Filled by frame_il and written into the manifest. The department publishes a
# Total Layoff Events / Total Impacted footer on every monthly report, which is
# a free arithmetic check on this module's own parse -- so the parse is checked
# against the publisher rather than trusted. A disagreement is RECORDED, not
# corrected: it means one of the two is wrong and an editor should know which
# month to look at.
IL_FOOTER_CHECK = []


def _il_monthly_urls():
    """The archive index -> {(year, month): absolute XLSX url} for the window."""
    index = SOURCES["IL"]["url"]
    markup = _get(index).decode("utf-8", "replace")
    found = {}
    for href in re.findall(r'href="([^"]+)"', markup):
        url = _html.unescape(href)
        m = re.search(r"SourceUrl=(.+)$", url)
        target = urllib.parse.unquote(m.group(1)) if m else url
        if not target.lower().endswith(".xlsx"):
            continue
        leaf = target.rsplit("/", 1)[-1]
        if "warn" not in leaf.lower():
            continue
        mo = _MONTH_RX.search(leaf)
        yr = re.search(r"(20\d\d)", leaf)
        if not (mo and yr):
            continue
        key = (int(yr.group(1)), _month_number(mo.group(1)))
        if key and key not in found:
            found[key] = urllib.parse.urljoin(index, url)
    return found


def frame_il():
    """Illinois: twelve monthly spreadsheets, oldest first.

    A MISSING MONTH IS AN ERROR AND NOT A SMALLER DENOMINATOR. A frame silently
    assembled from eleven of twelve months would report a recall figure over a
    denominator nobody could see was short, which is the shape of the defect
    that let a stale coverage percentage be quoted for sixteen days. If the
    archive index does not offer every month of the window, this raises.
    """
    IL_FOOTER_CHECK.clear()
    urls = _il_monthly_urls()
    want = _window_months()
    missing = [f"{y}-{m:02d}" for y, m in want if (y, m) not in urls]
    if missing:
        raise RuntimeError("Illinois archive index is missing monthly reports for "
                           + ", ".join(missing) + " -- the frame would be short and "
                           "a short frame is not a smaller denominator, it is a bug")
    out = []
    for y, m in want:
        url = urls[(y, m)]
        rows = _xlsx_rows(_get(url))
        header, body, footer = None, [], None
        for r in rows:
            joined = " ".join(r.values()).lower()
            if header is None:
                if "company name" in joined and "workers affected" in joined:
                    header = {col: re.sub(r"[^a-z ]+", "", (v or "").lower()).strip()
                              for col, v in r.items()}
                continue
            if "total layoff events" in joined or "total impacted" in joined:
                nums = [W._jobs(v) for v in r.values() if W._jobs(v) is not None]
                footer = {"month": f"{y}-{m:02d}",
                          "published_totals": nums[:2] if nums else None}
                break                      # the department's own footer
            body.append(r)

        def col(name):
            for c, label in (header or {}).items():
                if label.startswith(name):
                    return c
            return None

        c_company, c_dba = col("company name"), col("dba")
        c_recv, c_first = col("warn received date"), col("first layoff date")
        c_jobs, c_city = col("workers affected"), col("city state zip")
        c_type, c_kind = col("type of company"), col("type of event")
        if not (c_company and c_recv and c_jobs):
            raise RuntimeError(f"Illinois {y}-{m:02d}: the monthly report's header "
                               f"no longer carries company / received date / workers "
                               f"affected ({header})")
        before = len(out)
        for i, r in enumerate(body):
            if not (r.get(c_company) or "").strip():
                continue                   # a wrapped address tail, not a notice
            name, raw_name, cut = _employer(r.get(c_company))
            out.append({
                "state": "IL",
                "employer_published": name,
                "employer_published_raw": raw_name,
                "status_marker_cut": cut,
                "notice_date": W._iso(r.get(c_recv)),
                "state_received_date": W._iso(r.get(c_recv)),
                "effective_date": W._iso(r.get(c_first)) if c_first else None,
                "job_count": W._jobs(r.get(c_jobs)),
                "location": (r.get(c_city) or "") if c_city else "",
                "notice_type": (r.get(c_kind) or "") if c_kind else None,
                "industry": (r.get(c_type) or "") if c_type else None,
                "dba": (r.get(c_dba) or "") if c_dba else "",
                "source_url": url,
                "source_locator": f"{y}-{m:02d} monthly report, data row {i + 1}",
            })
        mine = out[before:]
        check = dict(footer or {"month": f"{y}-{m:02d}", "published_totals": None})
        check.update({"parsed_rows": len(mine),
                      "parsed_impacted": sum(r["job_count"] or 0 for r in mine)})
        pub = check.get("published_totals") or []
        check["agrees"] = (len(pub) == 2
                           and pub[0] == check["parsed_rows"]
                           and pub[1] == check["parsed_impacted"])
        # WHERE A MONTH DISAGREES, SAY BY HOW MUCH AND WHETHER IT IS ONE ROW.
        # A bare False would read as "our parse is wrong somewhere", and on the
        # 2026-09-16 build it is not: the ROW COUNT agrees in all twelve months,
        # and in each of the four disagreeing months the gap equals exactly one
        # published row's headcount -- the publisher's own footer total omits a
        # row that its own list carries. The frame is built from the LIST, so
        # the denominator is unaffected and the finding belongs to the source.
        check["impacted_delta"] = ((check["parsed_impacted"] - pub[1])
                                   if len(pub) == 2 else None)
        check["delta_equals_one_published_row"] = bool(
            check["impacted_delta"]
            and any(r["job_count"] == check["impacted_delta"] for r in mine))
        IL_FOOTER_CHECK.append(check)
        time.sleep(1)
    return out


# ---------------------------------------------------------------------------
# Ohio: the state asset host's per-year CSVs.
# ---------------------------------------------------------------------------
def _oh_csv_urls():
    """The per-year files that actually resolve, with the separator they use.

    Ohio re-uploads every archive year into the CURRENT year's folder and flips
    the separator between years (2024_warn_notice.csv, 2022-warn-notice.csv), so
    both are tried and the one that answers 200 is the one recorded. Every URL
    that resolved is written into the manifest, because "which file did you
    read" is the first question a reviewer asks of a frame assembled this way.
    """
    base = SOURCES["OH"]["url"]
    folder = date.today().year
    out = {}
    for year in (2025, 2026):
        for sep in ("_", "-"):
            url = f"{base}{folder}/{year}{sep}warn{sep}notice.csv"
            try:
                blob = _get(url)
            except Exception:                                      # noqa: BLE001
                time.sleep(1)
                continue
            if blob and b"Company" in blob[:400]:
                out[year] = (url, blob)
                break
            time.sleep(1)
    return out


def frame_oh():
    """Ohio: the 2025 and 2026 CSVs, unioned, filtered later by the window."""
    files = _oh_csv_urls()
    missing = [y for y in (2025, 2026) if y not in files]
    if missing:
        raise RuntimeError(f"Ohio: no WARN CSV resolved for {missing} -- the frame "
                           f"would be short and a short frame is a bug, not a "
                           f"smaller denominator")
    out = []
    for year in (2025, 2026):
        url, blob = files[year]
        text = blob.decode("utf-8-sig", "replace")
        lines = text.splitlines()
        start = next((i for i, ln in enumerate(lines[:6])
                      if "company" in ln.lower() and "received" in ln.lower()), None)
        if start is None:
            raise RuntimeError(f"Ohio {year}: no header row in the first six lines")
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        for i, row in enumerate(reader):
            r = {(k or "").lower().strip(): (v or "").strip()
                 for k, v in row.items() if k}
            name, raw_name, cut = _employer(r.get("company"))
            out.append({
                "state": "OH",
                "employer_published": name,
                "employer_published_raw": raw_name,
                "status_marker_cut": cut,
                "notice_date": W._iso(r.get("date received")),
                "state_received_date": W._iso(r.get("date received")),
                "effective_date": _first_date(r.get("layoff date(s)")),
                "job_count": W._jobs(r.get("potential number affected")),
                "location": r.get("city/county") or "",
                "notice_type": r.get("layoff/closure") or None,
                "industry": None,
                "notice_pdf_url": r.get("url") or "",
                "source_url": url,
                "source_locator": f"{year} CSV, data row {i + 1}",
            })
        time.sleep(1)
    return out


# ---------------------------------------------------------------------------
# Pennsylvania: the department's own listing, year -> month -> notice.
# ---------------------------------------------------------------------------
# Two markers, read in document order. The YEAR is a standalone <h2> and not an
# accordion title, so a parser that read only accordion titles saw 355 months
# and notices with no year to hang them on and returned an EMPTY frame.
#
# AND THE YEAR HEADING IS NOT ALWAYS CLASSED. 2026 and 2025 render as
# `<h2 class="cmp-accordion__main-heading--large">2025</h2>`; **2024 and 2023
# render as a bare `<h2>2024</h2>`**. A first version matched only the classed
# form, so every 2024 and 2023 notice inherited year=2025: PA's in-window frame
# filled with notices from one and two years earlier, and the measurement read
# 36% because it was asking whether we hold 2023 notices under 2025 dates. The
# rows we "missed" were in the table with the published headcount exactly right.
# The class is therefore NOT part of the match, and `_pa_year_month_is_sane`
# below makes the same mistake impossible to repeat silently.
_PA_TITLE = re.compile(
    r'class="cmp-accordion__title"[^>]*>(.*?)</span>'
    r'|<h\d[^>]*>\s*(20\d\d)\s*</h\d>', re.S)
_PA_MODIFY = re.compile(r'repo:modifyDate&#34;:&#34;([0-9T:\-]+Z)&#34;')


def _pa_text(segment):
    """The visible paragraphs of one accordion panel, entities resolved.

    The data-layer attribute is removed FIRST and by name. AEM puts a copy of
    the panel's own HTML inside `data-cmp-data-layer`, entity-escaped, so a
    plain tag strip leaves that copy behind as text: the first parse read an
    effective-date field of `beginning 11/16/2026, ending 4/1/2027<br> CLOSURE
    OR LAYOFF: Closure</p>"}}">`. The attribute's value is entity-escaped and so
    contains no raw double quote, which is what makes `[^"]*` exact here.
    """
    body = re.sub(r'data-cmp-data-layer="[^"]*"', "", segment)
    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"</p>", "\n", body, flags=re.I)
    body = _html.unescape(W._TAGS.sub(" ", body))
    body = body.replace("\u00a0", " ").replace("\u200b", "")
    return "\n".join(ln.strip() for ln in body.splitlines() if ln.strip())


def frame_pa():
    """Pennsylvania: order-based walk of the nested accordions.

    The nesting is read from the ORDER of the accordion titles, not from their
    heading level: PA renders month headings as <h2> under 2024-2026 and as
    <h3> under 2023, and a parser keyed on the tag would have silently dropped
    or mis-parented a year. A title that is a bare year opens a year, a title
    that is a month name opens a month, and anything else is a notice belonging
    to the year and month most recently opened.
    """
    doc = SOURCES["PA"]
    markup = _get(doc["url"]).decode("utf-8", "replace")
    hits = list(_PA_TITLE.finditer(markup))
    year = month = None
    out, seq = [], 0
    for idx, m in enumerate(hits):
        end = hits[idx + 1].start() if idx + 1 < len(hits) else len(markup)
        segment = markup[m.end():end]
        if m.group(2):                     # a bare-year heading, classed or not
            year, month = int(m.group(2)), None
            continue
        title = _html.unescape(
            re.sub(r"\s+", " ", W._TAGS.sub("", m.group(1) or ""))).strip()
        if title.lower() in _MONTHS:
            month = _MONTHS[title.lower()]
            continue
        if not (year and month):
            continue                       # a navigation accordion above the list
        seq += 1
        text = _pa_text(segment)
        affected = re.search(r"#?\s*AFFECTED\s*:?\s*([\d,]+)", text, re.I)
        effective = re.search(r"EFFECTIVE DATE\s*:?\s*(.+)", text, re.I)
        county = re.search(r"COUNT(?:Y|IES)\s*:?\s*(.+)", text, re.I)
        eff_raw = (effective.group(1) if effective else "")
        eff_first = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", eff_raw)
        modify = _PA_MODIFY.search(segment)
        name, raw_name, cut = _employer(title)
        out.append({
            "state": "PA",
            "employer_published": name,
            "employer_published_raw": raw_name,
            "status_marker_cut": cut,
            # PA publishes no per-notice date. The month heading is the basis and
            # the first of that month is the earliest date consistent with it.
            "notice_date": date(year, month, 1).isoformat(),
            "state_received_date": None,
            "effective_date": W._iso(eff_first.group(0)) if eff_first else None,
            "job_count": W._jobs(affected.group(1)) if affected else None,
            "location": "; ".join(x for x in (
                (county.group(1).strip() if county else ""),
                (text.splitlines()[0].strip() if text else "")) if x),
            "notice_type": ("Closure" if re.search(r"clos", text, re.I)
                            else ("Layoff" if re.search(r"layoff", text, re.I) else None)),
            "industry": None,
            "published_month": f"{year}-{month:02d}",
            "published_effective_text": eff_raw.strip()[:120],
            # Evidence only. NOT the window basis -- a modify date moves when an
            # entry is corrected, and a date that moves cannot freeze a frame.
            "cms_modify_date": modify.group(1)[:10] if modify else None,
            "source_url": doc["url"] + f"#{year}-{month:02d}",
            "source_locator": (f"{year} > {date(year, month, 1):%B} > accordion "
                               f"item {seq}"),
        })
    _pa_year_month_is_sane(out)
    return out


PA_MAX_AUTHORED_BEFORE_DAYS = 120


def _pa_year_month_is_sane(rows):
    """Raise if a month bucket holds notices the CMS authored long before it.

    THIS EXISTS BECAUSE THE FIRST PA PARSE WAS WRONG AND NOTHING SAID SO. The
    year heading is `<h2 class="...">2025</h2>` for recent years and a bare
    `<h2>2024</h2>` for older ones; matching only the classed form filed every
    2024 and 2023 notice under 2025, and the ONLY symptom was a recall figure of
    36% that looked like a coverage finding. A frame that is wrong in a way that
    reads as a result is worse than a frame that fails.

    The check is one-sided on purpose. An entry may be edited long AFTER the
    month it is filed under -- a correction, a re-publish -- and that is
    ordinary. An entry cannot be AUTHORED months before the month the department
    received the notice. So a month whose MEDIAN authored date sits more than
    `PA_MAX_AUTHORED_BEFORE_DAYS` before its own first day means the rows are
    parented to the wrong year, and the median (not the minimum) is used so one
    re-published old entry cannot trip it.
    """
    buckets = {}
    for r in rows:
        if r.get("cms_modify_date"):
            buckets.setdefault(r["published_month"], []).append(r["cms_modify_date"])
    bad = []
    for month, dates in sorted(buckets.items()):
        if len(dates) < 3:
            continue
        dates.sort()
        median = date.fromisoformat(dates[len(dates) // 2])
        first = date.fromisoformat(month + "-01")
        lead = (first - median).days
        if lead > PA_MAX_AUTHORED_BEFORE_DAYS:
            bad.append(f"{month} (median authored {median}, {lead} days before "
                       f"the month it is filed under, n={len(dates)})")
    if bad:
        raise RuntimeError(
            "Pennsylvania: the year/month parse is wrong -- these month buckets "
            "hold notices the CMS authored long before them: " + "; ".join(bad)
            + ". Do NOT widen PA_MAX_AUTHORED_BEFORE_DAYS; find which heading "
              "form the walk stopped recognising.")
    return True


FRAMES = {"IL": frame_il, "OH": frame_oh, "PA": frame_pa}


# ---------------------------------------------------------------------------
# Ohio transcription verification: the sampled events against the state's own
# notice PDFs. It does not make the Ohio frame independent and is not claimed to.
# ---------------------------------------------------------------------------
def _distinctive_tokens(name):
    """Tokens worth looking for in a notice: no corporate suffixes, 4+ chars."""
    toks = [w for w in re.sub(r"[^A-Za-z0-9]+", " ", name or "").split()
            if len(w) >= 4 and w.lower() not in W._SUFFIX]
    return toks or [w for w in re.sub(r"[^A-Za-z0-9]+", " ", name or "").split()]


def verify_oh_transcription(manifest):
    """Read each sampled Ohio event's own notice PDF and check what we recorded.

    FOUR STATES, NOT TWO, AND THE THIRD ONE IS THE POINT. A WARN letter is a
    letter: the employer is very often only in a letterhead IMAGE, and the total
    headcount is very often only the sum of a per-job-title table. So a notice
    whose extractable text carries neither is **not** a disagreement and must
    never be recorded as one -- on the first run this check called 17 of 25
    Ohio notices `disagrees_or_not_stated`, every one of which was the checker's
    own blind spot rather than a transcription fault.

      confirmed            both a distinctive employer token and the headcount
                           appear in the notice's own text
      partially_confirmed  one of the two appears
      not_stated_in_text   neither appears, AND the notice has a text layer --
                           an honest UNKNOWN about this notice, not a fault
      not_verified         no PDF link, no text layer, or the fetch failed

    A disagreement is never corrected in place either way: the frame is what the
    state published, and an editor deciding a match is entitled to see it.
    """
    from warn_pdf import PDF, page_items                            # noqa: PLC0415
    tally = {"confirmed": 0, "partially_confirmed": 0,
             "not_stated_in_text": 0, "not_verified": 0}
    for key in ("reference_events", "large_event_census"):
        for ev in manifest.get(key, []):
            if ev["state"] != "OH":
                continue
            urls = [c.get("notice_pdf_url") for c in ev["component_rows"]
                    if c.get("notice_pdf_url")]
            if not urls:
                ev["transcription_check"] = {
                    "status": "not_verified",
                    "why": "the state's CSV row carries no notice PDF link"}
                tally["not_verified"] += 1
                continue
            try:
                text = []
                pdf = PDF(_get(urls[0], timeout=60))
                for content in pdf.pages():
                    text += [x for _, _, x in page_items(content)]
                flat = re.sub(r"\s+", " ", " ".join(text))
            except Exception as exc:                                # noqa: BLE001
                ev["transcription_check"] = {
                    "status": "not_verified", "notice_pdf": urls[0],
                    "why": f"{type(exc).__name__}: {exc}"}
                tally["not_verified"] += 1
                time.sleep(1)
                continue
            time.sleep(1)
            if len(flat) < 80:
                # An EMPTY READ IS NOT A ZERO. A scanned notice with no text
                # layer tells us nothing and says so.
                ev["transcription_check"] = {
                    "status": "not_verified", "notice_pdf": urls[0],
                    "why": (f"the notice has no usable text layer "
                            f"({len(flat)} characters extracted), so it is a "
                            f"scan and this check cannot read it")}
                tally["not_verified"] += 1
                continue
            low = flat.lower()
            name_seen = any(tok.lower() in low for tok in
                            _distinctive_tokens(ev["employer_published"]))
            wanted = {ev["stated_job_count"]}
            wanted |= {c["job_count"] for c in ev["component_rows"] if c["job_count"]}
            count_seen = any(re.search(r"(?<![\d,])" + f"{n:,}".replace(",", "[,]?")
                                       + r"(?![\d,])", flat)
                             for n in wanted if n)
            status = ("confirmed" if (name_seen and count_seen)
                      else ("partially_confirmed" if (name_seen or count_seen)
                            else "not_stated_in_text"))
            tally[status] += 1
            ev["transcription_check"] = {
                "status": status,
                "notice_pdf": urls[0],
                "employer_token_in_notice": name_seen,
                "headcount_in_notice": count_seen,
                "extracted_characters": len(flat),
                "note": ("The CSV row and the employer's own notice are compared "
                         "BEFORE any tracker query exists. `not_stated_in_text` "
                         "is an UNKNOWN about this notice and NOT a "
                         "disagreement: a WARN letter commonly carries the "
                         "employer only in a letterhead image and the total only "
                         "as a per-job-title table. Nothing is corrected from "
                         "the notice; the frame is what the state published."),
            }
    return tally


# ---------------------------------------------------------------------------
def build():
    manifest = W.build(states=STATES, sources=SOURCES, frames_by_state=FRAMES,
                       manifest_path=MANIFEST_PATH,
                       reference_set_id=REFERENCE_SET_ID,
                       definition_document=DEFINITION_DOC,
                       date_field_note=DATE_FIELD_NOTE)
    manifest["wave"] = 2
    manifest["companion_reference_set_id"] = W.REFERENCE_SET_ID
    manifest["excluded_states"] = {
        "NY": ("out on criterion (b), re-probed 2026-09-16: dol.ny.gov/warn-notices "
               "301s to the legacy list, frozen at 2025-04-01 and therefore holding "
               "zero in-window notices; the current list is a Tableau Public embed "
               "whose workbook download now returns HTTP 404, leaving only the "
               "undocumented vizql route. New York is the third-largest US labour "
               "market and publishes no machine-readable WARN list without a BI "
               "tool. This set says NOTHING about our New York coverage."),
    }
    manifest["site_user_agent"] = SITE_UA
    manifest["il_monthly_footer_check"] = list(IL_FOOTER_CHECK)
    manifest["status_marker_rows_cut"] = {
        st: sum(1 for key in ("reference_events", "large_event_census")
                for ev in manifest[key] if ev["state"] == st
                for c in ev["component_rows"] if c.get("status_marker_cut"))
        for st in STATES}
    manifest["ohio_transcription_check"] = verify_oh_transcription(manifest)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"  ohio notices vs their own PDFs: {manifest['ohio_transcription_check']}")
    return manifest


def measure():
    return W.measure(manifest_path=MANIFEST_PATH, out_path=MEASUREMENT_PATH)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--build" in argv:
        build()
        return 0
    if "--measure" in argv:
        m = measure()
        s = m["summary"]
        print("\nUS WARN REFERENCE SET, WAVE 2 (IL/OH/PA)")
        print(f"  editor-confirmed  {s['editor_confirmed_overall']['interval']}")
        print(f"  machine any       {s['machine_upper_bound_any_candidate']['interval']}"
              "   <- UPPER BOUND, not recall")
        print(f"  machine exact     {s['machine_exact_tier']['interval']}")
        for st in STATES:
            print(f"    {st}  machine any {s['by_state'][st]['machine_any']['interval']}")
        print(f"  census (500+, never pooled) machine any "
              f"{s['large_event_census']['machine_any']['interval']}")
        return 0
    if "--pack" in argv:
        from warn_adjudication_pack import write_pack                # noqa: PLC0415
        write_pack(manifest_path=MANIFEST_PATH, measurement_path=MEASUREMENT_PATH,
                   queue_json=QUEUE_JSON, queue_md=QUEUE_MD)
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
