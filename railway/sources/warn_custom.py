"""
Custom WARN collectors for states the open-source warn-scraper can no longer
read (their sites changed). Each fetcher was built from a machine-verified
recon spec (2026-07-15) and returns entries in the exact same shape — and with
the exact same dedup-hash formula — as sources/warn.py, so re-imports upsert
instead of duplicating.

States: TX (Socrata JSON), FL (POST form -> HTML table), GA (WP admin-ajax),
OH (per-year CSVs on the Ohio DAM, archives to 2020), MI (Sitecore search
JSON), CO (Google Sheets xlsx), ID (text PDF), LA (per-year text PDFs, 2015+
via Wayback for the years laworks.net dropped), NC (per-year CSV + archive
PDFs to 2015), NV (master PDFs), MN (report PDFs), MA (CSV + FY xlsx), and
NY history (the retired dol.ny.gov database, frozen 4/1/2025 — supplements
warn-scraper's live-dashboard NY coverage; identical hashes dedup the overlap).
"""
import hashlib
import html as _html
import io
import json
import re

import requests

from .warn import _count, _to_iso_date, STATE_WARN_URL

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")}
TIMEOUT = 40


def _entry(st, company, jobs, date, city="", kind="", detail_url=""):
    """Normalized entry — MUST mirror sources/warn.py exactly (incl. the hash)."""
    company = (company or "").strip()
    city = (city or "").strip()
    if not company or jobs <= 0 or jobs > 100000 or not date:
        return None
    if date < "2015-01-01" or date > "2028-12-31":
        return None
    loc = f" in {city}" if city else ""
    excerpt = (f"{kind or 'Layoff'} at {company}{loc}. "
               f"{jobs:,} employees affected, effective {date}. "
               f"Filed under the {st} WARN Act.")
    hash_input = f"warn{company.lower().strip()}{date}{jobs}{city.lower().strip()}{st}"
    return {
        "source_type": "warn",
        "source_name": f"{st} WARN notice",
        "verification_level": "warn",
        "company_name": company,
        "ticker": None,
        "job_count": jobs,
        "layoff_date": date,
        "industry": None,
        "country": "United States",
        "state": st,
        "roles": None,
        "excerpt": excerpt,
        "reason_tags": [],
        "ai_explicit": False,
        "ai_language": None,
        "source_url": detail_url or STATE_WARN_URL.get(st, ""),
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def _strip_tags(markup):
    return _html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup or "")).strip())


def fetch_tx():
    """Official TWC Socrata dataset (full history 2019+, updated ~weekly)."""
    url = ("https://data.texas.gov/resource/8w53-c4f6.json"
           "?$limit=5000&$order=notice_date%20DESC")
    rows = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for r in rows:
        jobs = _count(str(r.get("total_layoff_number") or ""))
        date = _to_iso_date((r.get("layoff_date") or r.get("notice_date") or "")[:10])
        e = _entry("TX", r.get("job_site_name"), jobs, date, r.get("city_name") or "",
                   detail_url="https://data.texas.gov/d/8w53-c4f6")
        if e:
            out.append(e)
    return out


def fetch_fl():
    """FloridaCommerce REACT export: POST returns a fake-Excel HTML table."""
    resp = requests.post(
        "https://reactwarn.floridajobs.org/warnlist/reports",
        data={"StateNotificationStartDate": "2019-01-01",
              "StateNotificationEndDate": "2028-12-31", "appForm": "export"},
        headers=UA, timeout=120)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.S | re.I)
    out = []
    skipped_test = 0
    for tr in rows[1:]:  # first <tr> is the header (td cells, no th)
        cells = [_strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        if len(cells) < 14:
            continue
        # WarnNo, LWDB, Company, Addr1, Addr2, City, State, Zip, County,
        # NotifDate, LayoffBegin, LayoffEnd, Affected, Industry
        # Florida's export contains staff TEST rows ("test testie", "BOEING
        # test", "test2" — one carried 78,788 fake workers under an AT&T name
        # and briefly topped our whole tracker). "test" as its own token skips
        # them without touching legit names like "DuctTesters, Inc.".
        if re.search(r"(?:^|[^a-z])test(?:[^a-z]|\d|$)", cells[2], re.I):
            skipped_test += 1
            continue
        jobs = _count(cells[12])
        date = _to_iso_date(cells[10]) or _to_iso_date(cells[9])
        e = _entry("FL", cells[2], jobs, date, cells[5])
        if e:
            out.append(e)
    if skipped_test:
        print(f"    FL: skipped {skipped_test} state-side test row(s)")
    return out


def fetch_ga():
    """TCSG GravityView DataTables endpoint (nonce scraped from the page)."""
    landing = "https://www.tcsg.edu/warn-public-view/"
    page = requests.get(landing, headers=UA, timeout=TIMEOUT).text
    m = re.search(r'"action":"gv_datatables_data"[^}]*?"nonce":"([0-9a-f]{10})"', page)
    if not m:
        m = re.search(r'"nonce":"([0-9a-f]{10})"[^}]*?"action":"gv_datatables_data"', page)
    if not m:
        raise RuntimeError("GA: nonce not found on landing page")
    resp = requests.post(
        "https://www.tcsg.edu/wp-admin/admin-ajax.php",
        data={"action": "gv_datatables_data", "view_id": "77460", "post_id": "77462",
              "nonce": m.group(1), "getData": "false", "draw": "1",
              "start": "0", "length": "-1"},
        headers={**UA, "Referer": landing}, timeout=120)
    data = resp.json().get("data", [])
    out = []
    for row in data:
        # Rows are heterogeneous: plain arrays OR dicts keyed "0".."4"
        if isinstance(row, dict):
            cells = [row.get(str(i)) or row.get(i) or "" for i in range(5)]
        else:
            cells = list(row)
        if len(cells) < 4:
            continue
        link = re.search(r'href="([^"]+)"', str(cells[0]) or "")
        jobs = _count(_strip_tags(str(cells[3])))
        date = _to_iso_date(_strip_tags(str(cells[2])))
        e = _entry("GA", _strip_tags(str(cells[1])), jobs, date,
                   detail_url=link.group(1) if link else "")
        if e:
            out.append(e)
    return out


# Ohio's 2026 site rebuild moved WARN under /job-workforce-services and added
# per-year archive pages. Archives exist for 2020+ only — the 2015-2019 slugs
# 404 (never migrated; verified 2026-07-18). Each page links its year's CSV
# on the Ohio DAM, now with f_auto/q_auto/v<nnn> segments in the path.
_OH_WARN_BASE = ("https://jfs.ohio.gov/job-workforce-services/"
                 "job-programs-and-services/submit-a-warn-notice")
_OH_ARCHIVE_START = 2020
_OH_CSV_RE = re.compile(r'https://dam\.assets\.ohio\.gov/raw/upload/[^"\\ ]+\.csv')


def _oh_entries_from_csv(text):
    """Parse one Ohio DAM CSV (headers may sit a couple of metadata rows down)."""
    import csv as _csv
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines[:6]) if "company" in ln.lower()), None)
    if start is None:
        return []
    out = []
    for row in _csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        rl = {(k or "").lower().strip(): (v or "").strip() for k, v in row.items() if k}
        company = rl.get("company") or ""
        jobs = _count(rl.get("potential number affected") or rl.get("number affected") or "")
        date = (_to_iso_date(rl.get("layoff date(s)") or "")
                or _to_iso_date(rl.get("date received") or ""))
        city = (rl.get("city/county") or "").split("/")[0]
        e = _entry("OH", company, jobs, date, city, detail_url=rl.get("url") or "")
        if e:
            out.append(e)
    return out


def fetch_oh():
    """Ohio DAM CSVs discovered from the JFS current page + per-year archive
    pages (2020+). Every page and every CSV is fail-isolated."""
    from datetime import date as _date
    this_year = _date.today().year
    pages = [f"{_OH_WARN_BASE}/current-public-notices-of-layoffs-and-closures"]
    pages += [f"{_OH_WARN_BASE}/{y}-public-notices-of-layoffs-and-closures"
              for y in range(_OH_ARCHIVE_START, this_year)]
    urls = []
    for page_url in pages:
        slug = page_url.rsplit("/", 1)[-1]
        try:
            page = requests.get(page_url, headers=UA, timeout=TIMEOUT)
            if page.status_code != 200:
                print(f"    OH: {slug} -> HTTP {page.status_code}")
                continue
            found = _OH_CSV_RE.findall(page.text)
            if not found:
                print(f"    OH: no DAM CSV link on {slug}")
            urls += found
        except Exception as exc:
            print(f"    OH: {slug} failed ({exc})")
    # versionless fallback keeps the current years importable through a
    # landing-page redesign (pre-2026 pattern; still resolves for {year})
    for y in (this_year, this_year - 1):
        urls.append(f"https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/{y}/{y}-warn-notice.csv")
    out, seen = [], set()
    for u in urls:
        # same file relinked under new renderer flags / version segments
        key = re.sub(r"(?:f_auto/|q_auto/|v\d+/)", "", u)
        if key in seen:
            continue
        seen.add(key)
        try:
            resp = requests.get(u, headers=UA, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            out += _oh_entries_from_csv(resp.text)
        except Exception:
            continue
    return out


def fetch_mi():
    """Michigan.gov Sitecore SXA search API: JSON of HTML fragments in two
    shapes — older records use <a class="content-title-link"> + <p> pairs with
    'Commencing date'; newer ones use <h3> + <li> items with 'Layoff date'."""
    url = ("https://www.michigan.gov/leo/sxa/search/results/"
           "?s={8E97AB1D-D2D4-47F8-8CC4-3F1039C8854F}"
           "&itemid={BE81F7C2-36A8-4FDE-853C-B05B6E090055}"
           "&v={1FFFCC21-5151-4A2B-ABFC-F7FE4E5C9783}&p=500"
           "&o=Created%20Date%20sort,Descending")
    data = requests.get(url, headers=UA, timeout=TIMEOUT).json()
    out = []
    for res in data.get("Results", []):
        html = (res.get("Html") or "").replace("&nbsp;", " ")
        m = (re.search(r'class="content-title-link"[^>]*>(.*?)</a>', html, re.S)
             or re.search(r"<h3[^>]*>(.*?)</h3>", html, re.S))
        title = _strip_tags(m.group(1)) if m else ""

        def field(label):
            fm = re.search(rf"<strong>\s*{label}[^<]*</strong>\s*:?\s*([^<]+)", html, re.I)
            return fm.group(1).strip() if fm else ""

        jobs = _count(field("Number of jobs impacted"))
        date = (_to_iso_date(field("Layoff date")) or _to_iso_date(field("Commencing date"))
                or _to_iso_date(field("Date of layoff")) or _to_iso_date(field("Date WARN received")))
        county = field("County")
        link = res.get("Url") or ""
        if link and link.startswith("/"):
            link = "https://www.michigan.gov" + link
        e = _entry("MI", title, jobs, date, county, detail_url=link)
        if e:
            out.append(e)
    return out


def fetch_co():
    """Colorado CDLE: per-year Google Sheets workbooks linked from the landing page."""
    from openpyxl import load_workbook
    landing = "https://cdle.colorado.gov/employers/layoff-separations/layoff-warn-list"
    ids = []
    try:
        page = requests.get(landing, headers=UA, timeout=TIMEOUT).text
        ids = list(dict.fromkeys(re.findall(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})", page)))
    except Exception as e:
        print(f"CO landing fetch failed: {e}")
    # known workbooks (2026 current + 2025 archive) as fallback
    for known in ("19jmo4Cwj933cmSBKV1t0zZ5O-2H5IpiLIhSH9MF8WF0",
                  "1aFv4ntRhjnTMFKqBnuzbIkExCWgp6vnblYGm_h9GUeI"):
        if known not in ids:
            ids.append(known)
    out = []
    for sid in ids[:6]:
        try:
            xls = requests.get(
                f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx",
                headers=UA, timeout=60)
            wb = load_workbook(io.BytesIO(xls.content), read_only=True, data_only=True)
        except Exception as e:
            print(f"CO workbook {sid[:8]} failed: {e}")
            continue
        for ws in wb.worksheets:
            if "warn" not in ws.title.lower() or "archiv" in ws.title.lower():
                continue
            rows = ws.iter_rows(values_only=True)
            headers = None
            for row in rows:
                vals = ["" if c is None else str(c).strip() for c in row]
                if headers is None:
                    if any("company" in v.lower() for v in vals):
                        headers = [v.lower() for v in vals]
                    continue
                rl = dict(zip(headers, vals))
                company = rl.get("company") or ""
                jobs = _count(rl.get("total notified") or rl.get("co notifications") or "")
                date = (_to_iso_date(rl.get("begin date") or "")
                        or _to_iso_date(rl.get("warn date") or "")
                        or _to_iso_date(rl.get("received") or ""))
                e = _entry("CO", company, jobs, date)
                if e:
                    out.append(e)
    return out


def _pdf_tables(content):
    import pdfplumber
    tables = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables() or []:
                tables.append(t)
    return tables


def _pdf_text(content):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def fetch_id():
    """Idaho: one cumulative text-layer PDF; link rotates, scraped from landing."""
    landing = "https://www.labor.idaho.gov/businesss/layoff-assistance/"
    page = requests.get(landing, headers=UA, timeout=TIMEOUT).text
    m = re.search(r'href="(https://www\.labor\.idaho\.gov/wp-content/uploads/\d{4}/\d{2}/Idaho-WARN-Notices-[\dx.]+\.pdf)"', page)
    if not m:
        raise RuntimeError("ID: WARN pdf link not found on landing page")
    pdf = requests.get(m.group(1), headers=UA, timeout=60)
    out = []
    for table in _pdf_tables(pdf.content):
        for row in table:
            cells = ["" if c is None else str(c).strip() for c in row]
            if len(cells) < 9 or "company" in cells[2].lower():
                continue
            # Date of Letter | Updates | Company | Address | City | State | Zip | Affected | Effective
            jobs = _count(cells[7])
            date = _to_iso_date(cells[8]) or _to_iso_date(cells[0])
            e = _entry("ID", cells[2], jobs, date, cells[4], detail_url=m.group(1))
            if e:
                out.append(e)
    return out


def _la_entries_from_tables(tables, url):
    """LA row shapes: 2026+ is Company|Address|Notice|Layoff|Affected|Industry;
    2015-2025 is Company(+addr)|Notice|Layoff|Affected|Industry."""
    out = []
    for table in tables:
        for row in table:
            cells = ["" if c is None else str(c).strip().replace("\n", " ") for c in row]
            if len(cells) < 5 or "company" in (cells[0] or "").lower():
                continue
            if len(cells) >= 6:
                company, notice, layoff, affected = cells[0], cells[2], cells[3], cells[4]
            else:
                company, notice, layoff, affected = cells[0], cells[1], cells[2], cells[3]
            jobs = _count(affected)
            date = _to_iso_date(layoff) or _to_iso_date(notice)
            e = _entry("LA", company, jobs, date, detail_url=url)
            if e:
                out.append(e)
    return out


def fetch_la():
    """Louisiana: per-year text-layer PDFs, updated in place. laworks.net now
    hosts only the current two years — WarnNotices2015-2024.pdf all 404 on the
    live site (verified 2026-07-18) — so removed years fall back to a Wayback
    Machine snapshot taken after the year closed (same trust as MN's CDX
    discovery). Every year is fail-isolated."""
    from datetime import date as _date
    out = []
    for y in range(2015, _date.today().year + 1):
        live = f"https://www.laworks.net/Downloads/WFD/WarnNotices{y}.pdf"
        content, source = None, live
        try:
            resp = requests.get(live, headers=UA, timeout=60)
            if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                content = resp.content
        except Exception:
            pass
        if content is None:
            # April-after-year-end targets a complete-year snapshot while
            # steering clear of later capture dates that archived the 404
            wayback = f"https://web.archive.org/web/{y + 1}0401id_/{live}"
            for attempt in range(2):  # Wayback is slow and flaky — retry once
                try:
                    resp = requests.get(wayback, headers=UA, timeout=90)
                    if resp.status_code == 200 and resp.content[:4] == b"%PDF":
                        content, source = resp.content, wayback
                    break
                except Exception:
                    continue
        if content is None:
            print(f"    LA {y}: no live or archived PDF")
            continue
        try:
            out += _la_entries_from_tables(_pdf_tables(content), source)
        except Exception as exc:
            print(f"    LA {y}: PDF parse failed ({exc})")
    return out


_NC_WARN_BASE = ("https://www.commerce.nc.gov/data-tools-reports/"
                 "labor-market-data-tools/workforce-warn-reports")


def _nc_year_csv(y):
    """Current NC vintage: Drupal year page -> rotating date-stamped CSV on
    files.nc.gov (the page slug only exists for the current year or two)."""
    import csv as _csv
    page = requests.get(f"{_NC_WARN_BASE}/report-workforce-warn-summary-list-{y}",
                        headers=UA, timeout=TIMEOUT)
    if page.status_code != 200:
        return []
    m = re.search(r'href="(https://files\.nc\.gov/[^"]+\.csv[^"]*)"', page.text)
    if not m:
        return []
    text = requests.get(_html.unescape(m.group(1)), headers=UA, timeout=TIMEOUT).text
    out = []
    for r in _csv.DictReader(io.StringIO(text)):
        jobs = _count(r.get("Number affected at this location") or "")
        date = (_to_iso_date(r.get("Effective Date") or "")
                or _to_iso_date(r.get("Date of Notice") or ""))
        e = _entry("NC", r.get("WARN Notice: WARN Notice Name"), jobs, date,
                   r.get("City") or "", kind=r.get("WARN notice type") or "",
                   detail_url=page.url)
        if e:
            out.append(e)
    return out


def _nc_header_cols(cells):
    """Map the heterogeneous NC header spellings (2018-2021 grids, 2022+
    grids/CSV) to field indexes; None unless the row looks like a header."""
    idx = {}
    for i, c in enumerate(cells):
        lc = re.sub(r"\s+", " ", str(c or "")).strip().lower()
        if "warn notice name" in lc or lc == "company":
            idx["company"] = i
        elif "number affected" in lc or "no. of employees" in lc:
            idx["jobs"] = i
        elif lc == "effective date":
            idx["eff"] = i
        elif lc in ("date of notice", "notice date"):
            idx["notice"] = i
        elif lc == "city":
            idx["city"] = i
        elif "warn notice type" in lc or lc.replace(" ", "") == "layoff/closure":
            idx["kind"] = i
    return idx if "company" in idx and "jobs" in idx else None


def _nc_grid_entries(tables, url):
    """Header-keyed rows from the gridded NC archive PDFs (2018+). The 2022+
    files only carry the header on page 1, so the column map persists across
    tables/pages."""
    out, cols = [], None
    for table in tables:
        for row in table:
            cells = ["" if c is None else re.sub(r"\s+", " ", str(c)).strip() for c in row]
            hdr = _nc_header_cols(cells)
            if hdr:
                cols = hdr
                continue
            if not cols:
                continue
            get = lambda k: cells[cols[k]] if k in cols and cols[k] < len(cells) else ""
            e = _entry("NC", get("company"), _count(get("jobs")),
                       _to_iso_date(get("eff")) or _to_iso_date(get("notice")),
                       get("city"), kind=get("kind"), detail_url=url)
            if e:
                out.append(e)
    return out


# 2015-2017 NC reports have no table grid and interleave monthly summary
# blocks between data rows; these markers identify non-data lines.
_NC_TEXT_NOISE = re.compile(
    r"WARN Notice|Date Range|Effective Date|Month:|Total Notices|Sum of|"
    r"Layoff:|Closure:|Grand Total")


def _nc_text_rows(words, url):
    """2015-2017 NC vintage: bucket pdfplumber words into columns using the
    x-positions of the per-page header row (Notice Date | Effective Date |
    Company Name | City | # Emp. Affected + kind). Wrapped company/city
    continuation lines merge into the previous row."""
    anchors = {}
    for w in words:
        if w["text"] in ("Notice", "Effective", "Company", "City", "#"):
            anchors.setdefault(round(w["top"]), {}).setdefault(w["text"], w["x0"])
    header_top = cols = None
    for top, d in sorted(anchors.items()):
        if {"Notice", "Effective", "Company", "City"} <= set(d):
            header_top = top
            cols = [d["Notice"], d["Effective"], d["Company"], d["City"],
                    d.get("#", d["City"] + 55)]
            break
    if cols is None:
        return []
    lines, cur_top = [], None
    for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
        if w["top"] <= header_top + 2:
            continue
        if cur_top is None or w["top"] - cur_top > 3:
            lines.append([])
            cur_top = w["top"]
        lines[-1].append(w)
    rows = []  # [notice, effective, company, city, count+kind tail]
    for ws in lines:
        cells = ["", "", "", "", ""]
        for w in sorted(ws, key=lambda x: x["x0"]):
            ci = 0
            for i, cx in enumerate(cols):
                if w["x0"] >= cx - 6:
                    ci = i
            cells[ci] = f"{cells[ci]} {w['text']}".strip()
        if _NC_TEXT_NOISE.search(" ".join(cells)):
            continue
        if _to_iso_date(cells[0]) or _to_iso_date(cells[1]):
            rows.append(cells)
        elif rows:  # wrapped continuation of the previous row
            for i in (2, 3):
                if cells[i]:
                    rows[-1][i] = f"{rows[-1][i]} {cells[i]}".strip()
    out = []
    for cells in rows:
        kind_m = re.search(r"Layoffs?|Closures?", cells[4])
        e = _entry("NC", cells[2], _count(cells[4]),
                   _to_iso_date(cells[1]) or _to_iso_date(cells[0]), cells[3],
                   kind=kind_m.group(0) if kind_m else "", detail_url=url)
        if e:
            out.append(e)
    return out


def fetch_nc():
    """NC Commerce, three vintages (verified 2026-07-18): the current year or
    two live on Drupal pages with a rotating CSV; 2015-2025 hang off the
    warn-summary-report-archives page as per-year PDFs — gridded tables for
    2018+, headerless text columns for 2015-2017. Everything fail-isolated."""
    from datetime import date as _date
    out = []
    for y in (_date.today().year, _date.today().year - 1):  # Jan rollover safety
        try:
            out += _nc_year_csv(y)
        except Exception as exc:
            print(f"    NC {y}: summary-list failed ({exc})")
    try:
        arch = requests.get(f"{_NC_WARN_BASE}/warn-summary-report-archives",
                            headers=UA, timeout=TIMEOUT)
        hrefs = re.findall(r'href="([^"]*warn[^"]*/open)"', arch.text, re.I)
    except Exception as exc:
        print(f"    NC: archive index failed ({exc})")
        hrefs = []
    seen = set()
    for href in hrefs:
        ym = re.search(r"(20\d\d)", href)
        # 2014 exists on the page but predates the tracker's 2015 cutoff
        if not ym or int(ym.group(1)) < 2015 or href in seen:
            continue
        seen.add(href)
        url = href if href.startswith("http") else "https://www.commerce.nc.gov" + href
        try:
            resp = requests.get(url, headers=UA, timeout=60)
            if resp.status_code != 200 or resp.content[:4] != b"%PDF":
                raise RuntimeError(f"HTTP {resp.status_code} / not a PDF")
            entries = _nc_grid_entries(_pdf_tables(resp.content), url)
            if not entries:  # 2015-2017 vintage
                import pdfplumber
                with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                    for p in pdf.pages:
                        entries += _nc_text_rows(p.extract_words(), url)
            out += entries
        except Exception as exc:
            print(f"    NC {ym.group(1)} archive: failed ({exc})")
    return out


# Nevada's master PDF glues tokens ("209SK Food Group"), so rows are parsed
# from text lines; the trailing County token is stripped via this vocabulary.
_NV_COUNTIES = (
    "Carson City|Churchill|Clark|Douglas|Elko|Esmeralda|Eureka|Humboldt|Lander|"
    "Lincoln|Lyon|Mineral|Nye|Pershing|Storey|Washoe|White Pine|Statewide|Remote|Various"
)
_NV_ROW = re.compile(
    r"^(?:(?P<recv>\d{1,2}/\d{1,2}/\d{2,4})|Unknown|Multiple)?\s*"
    r"(?:(?P<eff>\d{1,2}/\d{1,2}/\d{2,4})|Unknown|Multiple)?\s*"
    r"(?P<kind>Layoffs?|Closures?)\s*"
    r"(?P<jobs>[\d,]+|Unknown|NR)\s*"
    r"(?P<rest>.+?)\s*"
    r"(?P<warn>Non-?WARN|WARN)?$")

# Known NV municipalities, longest first — the text line is
# "<company> <city> <county>" with no delimiters, so the split must be
# vocabulary-driven ("Spirit Airlines Las Vegas Clark" is genuinely ambiguous
# to a regex: company names may end in place-like words).
_NV_CITIES = [
    "North Las Vegas", "Incline Village", "Boulder City", "Carson City", "Sun Valley",
    "Battle Mountain", "West Wendover", "Spring Creek", "Indian Springs", "Mound House",
    "Las Vegas", "Henderson", "Reno", "Sparks", "Stateline", "Primm", "Elko",
    "Mesquite", "Fernley", "Minden", "Gardnerville", "Winnemucca", "Fallon",
    "Pahrump", "Laughlin", "Verdi", "Sloan", "Jean", "McCarran", "Ely", "Yerington",
    "Lovelock", "Tonopah", "Hawthorne", "Caliente", "Wells", "Jackpot", "Dayton",
    "Silver Springs", "Moapa", "Overton", "Amargosa Valley", "Crystal Bay", "Genoa",
    "Zephyr Cove", "Round Mountain", "Eureka", "Remote", "Statewide", "Various",
]

def fetch_nv():
    """Nevada DETR: one cumulative print-to-PDF master per year, filename rotates."""
    import pdfplumber
    landing = requests.get("https://detr.nv.gov/Page/WARN", headers=UA, timeout=TIMEOUT)
    pdfs = re.findall(
        r'href="(/[Cc]ontent/[Mm]edia/[^"]+\.pdf|https://detr\.nv\.gov/[Cc]ontent/[Mm]edia/[^"]+\.pdf)"[^>]*>\s*(20\d\d)\s*WARN',
        landing.text)
    county_re = re.compile(r"\s+(?:%s)(?:\s*/\s*(?:%s))*$" % (_NV_COUNTIES, _NV_COUNTIES))
    out = []
    for href, year in pdfs:
        if int(year) < 2022:
            continue
        url = href if href.startswith("http") else "https://detr.nv.gov" + href
        resp = requests.get(url, headers=UA, timeout=TIMEOUT)
        if resp.status_code != 200:
            continue
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                for line in (page.extract_text() or "").splitlines():
                    line = line.strip()
                    if "Employer" in line or not re.search(r"Layoffs?|Closures?", line):
                        continue
                    m = _NV_ROW.match(line)
                    if not m:
                        continue
                    rest = county_re.sub("", m.group("rest").strip()).strip()
                    city = ""
                    for c in _NV_CITIES:
                        if rest.endswith(" " + c) or rest == c:
                            city, rest = c, rest[: -len(c)].strip() if rest != c else ""
                            break
                    e = _entry("NV", rest, _count(m.group("jobs")),
                               _to_iso_date(m.group("eff") or "") or _to_iso_date(m.group("recv") or ""),
                               city, kind=m.group("kind"), detail_url=url)
                    if e:
                        out.append(e)
    return out


# Radware bot-walls mn.gov HTML pages but NOT /deed/assets/*.pdf — discovery
# of the unpredictable tcm1045 ids falls back to the Wayback CDX index, and a
# seed list keeps known history importable through a total discovery outage.
_MN_SEED_PDFS = [  # verified-live 2026-07-19; CDX discovery adds the rest
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-report-2023_tcm1045-663809.pdf",
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-october-2025_tcm1045-712065.pdf",
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-2026-january_tcm1045-722872.pdf",
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-2026-june_tcm1045-758364.pdf",
    # keep recent months here until CDX archives them or a JS-render discovery lands
]


def _mn_parse_table(table):
    """(company, jobs, date, city) rows from one MN report table, template-agnostic.

    DEED changed the monthly template mid-2026: multi-word headers now wrap
    across TWO physical rows ('Affected' / 'Workers'), a leading blank column
    and a trailing 'Layoff Count' column appear, and 'Account: City' became
    'City'. The old parser matched whole header strings in single cells, so it
    silently returned 0 rows on every new-template report. This merges a wrapped
    continuation header row before keyword-matching, handling both layouts."""
    def cell(row, j):
        return re.sub(r"\s+", " ", (row[j] or "")).strip() if j < len(row) else ""
    hdr_i = next((i for i, r in enumerate(table[:3])
                  if any("Layoff Name" in (c or "") for c in r)), None)
    if hdr_i is None:
        return []
    ncol = len(table[hdr_i])
    combined = []
    for j in range(ncol):
        h = cell(table[hdr_i], j)
        if hdr_i + 1 < len(table):
            nxt = cell(table[hdr_i + 1], j)
            if nxt and not re.search(r"\d", nxt) and len(nxt) <= 12 and not _to_iso_date(nxt):
                h = f"{h} {nxt}".strip()
        combined.append(h.lower())

    def find(*keys):
        return next((j for j, h in enumerate(combined) if any(k in h for k in keys)), None)
    ci_name = find("layoff name")
    ci_city = find("city")
    ci_date = find("layoff start")
    ci_recv = find("warn received")
    ci_jobs = find("affected worker")
    if ci_name is None or ci_jobs is None:
        return []
    start = hdr_i + 1
    if start < len(table):
        first = [cell(table[start], j) for j in range(ncol)]
        if not any(re.search(r"\d", x) for x in first):
            start += 1  # skip the wrapped-continuation header row
    out = []
    for row in table[start:]:
        cells = [cell(row, j) for j in range(ncol)]
        name = re.sub(r"\s+20\d\d$", "", cells[ci_name] if ci_name < len(cells) else "")
        if not name or name.lower().startswith(("total", "rr start", "count")):
            continue
        jobs = _count(cells[ci_jobs]) if ci_jobs < len(cells) else 0
        date = _to_iso_date(cells[ci_date]) if (ci_date is not None and ci_date < len(cells)) else ""
        if not date and ci_recv is not None and ci_recv < len(cells):
            date = _to_iso_date(cells[ci_recv])
        city = cells[ci_city] if (ci_city is not None and ci_city < len(cells)) else ""
        out.append((name, jobs, date, city))
    return out


def fetch_mn():
    """MN DEED monthly/annual report PDFs (assets bypass the bot wall).
    Discovery = seed list + Wayback CDX; parsing via template-agnostic table map."""
    import pdfplumber
    urls = set(_MN_SEED_PDFS)
    for attempt in range(2):  # Wayback CDX is slow and flaky — retry once
        try:
            cdx = requests.get(
                "https://web.archive.org/cdx/search/cdx",
                params={"url": "mn.gov/deed/assets/plant-closing*",
                        "collapse": "urlkey", "fl": "original", "limit": "500"},
                headers=UA, timeout=90)
            for u in cdx.text.split():
                if re.search(r"/deed/assets/plant-closing[^\s]*_tcm1045-\d+\.pdf$", u):
                    urls.add(u.replace("http://", "https://"))
            break
        except Exception as exc:  # discovery outage -> seeds still import
            print(f"    MN: CDX discovery failed ({exc}); "
                  + ("retrying" if attempt == 0 else "using seed list"))
    out = []
    for url in sorted(urls):
        try:
            resp = requests.get(url, headers=UA, timeout=TIMEOUT)
        except Exception:
            continue
        if resp.status_code != 200 or b"%PDF" not in resp.content[:1024]:
            continue
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for company, jobs, date, city in _mn_parse_table(table):
                        e = _entry("MN", company, jobs, date, city, detail_url=url)
                        if e:
                            out.append(e)
    return out


# mass.gov (Akamai) rejects HTTP/1.1 outright and demands a full Chrome header
# fingerprint — hence httpx with http2 rather than requests (recon-verified:
# same headers 403 over HTTP/1.1, 200 over HTTP/2).
_MA_HEADERS = {
    "User-Agent": UA["User-Agent"],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none", "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Chromium";v="126", "Not/A)Brand";v="8"',
    "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"macOS"',
    "Upgrade-Insecure-Requests": "1",
}
_MA_LANDING = ("https://www.mass.gov/info-details/worker-adjustment-and-retraining-"
               "notification-act-warn-layoff-and-closure-updates")

def _ma_first_date(value):
    """First parseable date from free text ('8/15/26 & 11/30/26', ranges, serials)."""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    for token in re.split(r"\s*(?:-|&|,|\band\b|\bending\b|\bthrough\b)\s*", str(value or "")):
        d = _to_iso_date(token)
        if d:
            return d
    return None

def fetch_ma():
    """Massachusetts: weekly CSV (current FY) + one XLSX per archived FY."""
    import httpx
    from openpyxl import load_workbook
    client = httpx.Client(http2=True, headers=_MA_HEADERS, follow_redirects=True, timeout=TIMEOUT)
    landing = client.get(_MA_LANDING)
    out = []

    def add(company, jobs_raw, date_raw, fallback_date, city):
        company = re.sub(r"^\*Updated\*\s*", "", str(company or ""))
        city = re.sub(r",\s*MA$", "", str(city or "")).strip()
        date = _ma_first_date(date_raw) or _ma_first_date(fallback_date)
        e = _entry("MA", company, _count(str(jobs_raw or "")), date, city, detail_url=_MA_LANDING)
        if e:
            out.append(e)

    csv_urls = re.findall(r'href="(https://www\.mass\.gov/files/csv/[^"]+\.csv)"', landing.text)
    import csv as _csv
    for url in csv_urls[:1]:
        r = client.get(_html.unescape(url))
        if r.status_code == 200:
            try:  # the CSV mixes encodings ("Labouré College" is cp1252)
                text = r.content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = r.content.decode("cp1252", errors="replace")
            for row in _csv.DictReader(io.StringIO(text)):
                add(row.get("EMPLOYER"), row.get("# EMPLOYEES IMPACTED"),
                    row.get("DATE(S) OF LAYOFFS"), row.get("RECEIVED"), row.get("CITY/TOWN"))

    fy_urls = re.findall(r'href="(https://www\.mass\.gov/doc/fy\d\d-warn-report[^"]*/download)"', landing.text)
    for url in sorted(set(fy_urls)):
        r = client.get(_html.unescape(url))
        if r.status_code != 200:
            continue
        wb = load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
        for ws in wb.worksheets:
            header, cols = None, {}
            for row in ws.iter_rows(values_only=True):
                cells = ["" if c is None else c for c in row]
                if header is None:
                    joined = " ".join(str(c).upper() for c in cells)
                    if "EMPLOYER" in joined or "COMPANY NAME" in joined:
                        header = [str(c).strip().upper() for c in cells]
                        for i, h in enumerate(header):
                            if "EMPLOYER" in h or "COMPANY" in h: cols["company"] = i
                            elif "IMPACT" in h or "AFFECT" in h:  cols["jobs"] = i
                            elif "LAYOFF" in h and "DATE" in h.replace("(S)", "S"): cols["date"] = i
                            elif h in ("RECEIVED", "DATE RECEIVED"): cols["recv"] = i
                            elif "CITY" in h:                     cols["city"] = i
                    continue
                if "company" not in cols or "jobs" not in cols:
                    continue
                get = lambda k: cells[cols[k]] if k in cols and cols[k] < len(cells) else ""
                if not str(get("company")).strip():
                    continue
                add(get("company"), get("jobs"), get("date"), get("recv"), get("city"))
    client.close()
    return out


# --- New York history: the retired dol.ny.gov database (frozen 4/1/2025) ---
# The hub page itself lists the final Jan-Apr 2025 notices and links plain-
# HTML year archives for 2023/2024. All three share one 4-column table
# (Company | Region | Date Posted | Notice Dated) with NO headcount — the
# count and layoff date live in the per-notice PDF behind each company link
# (verified 2026-07-18). Live NY data comes from warn-scraper's dashboard
# scraper; identical dedup hashes make the overlap upsert-safe.
_NY_HUB = "https://dol.ny.gov/warn-notices"


def _ny_listing_rows(page_html):
    """(company, detail_url, notice_date_text) rows from a retired-NY listing."""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        if len(cells) < 4:
            continue
        link = re.search(r'href="\s*(/warn-[^"]+)"', cells[0])
        company = _strip_tags(cells[0])
        if not link or not company:
            continue
        rows.append((company, "https://dol.ny.gov" + link.group(1).strip(),
                     _strip_tags(cells[3])))
    return rows


def _ny_fields_from_text(text):
    """(jobs, layoff_date_iso) from the uniform NY WARN-unit notice layout.
    Dates wrap across lines in the PDF text layer ('February\\n12, 2024'), so
    the field windows are whitespace-flattened first. Amended notices list the
    original count before the '• Amended to N' bullet — the first-number parse
    keeps the original, matching the tracker's lower-bound convention."""
    flat = re.sub(r"\s+", " ", text or "")
    jm = (re.search(r"Total Number of Affected Workers\s*:?\s*([\d,]+)", flat, re.I)
          or re.search(r"Number of Affected Employees at Site\s*:?\s*([\d,]+)", flat, re.I))
    jobs = _count(jm.group(1)) if jm else 0
    dm = re.search(r"(?:Layoff|Closure)[^:]{0,15}Start Date\s*:\s*(.{0,220})", flat, re.I)
    date = _to_iso_date(dm.group(1)) if dm else ""
    if not date:
        nm = re.search(r"Date of Notice\s*:\s*(.{0,60})", flat, re.I)
        date = _to_iso_date(nm.group(1)) if nm else ""
    return jobs, date


def fetch_ny_history():
    """History backfill for NY from the retired database: walk each frozen
    listing, then fetch every linked per-notice PDF for its count/start date
    (falling back to the listing's notice date). Listings and notices are each
    fail-isolated."""
    listings = [("2025 hub", _NY_HUB),
                ("2024", "https://dol.ny.gov/2024-warn-notices"),
                ("2023", "https://dol.ny.gov/2023-warn-notices")]
    out = []
    for label, listing_url in listings:
        try:
            page = requests.get(listing_url, headers=UA, timeout=TIMEOUT)
            if page.status_code != 200:
                raise RuntimeError(f"HTTP {page.status_code}")
            rows = _ny_listing_rows(page.text)
        except Exception as exc:
            print(f"    NY {label}: listing failed ({exc})")
            continue
        kept = failed = 0
        for company, detail_url, notice_text in rows:
            try:
                resp = requests.get(detail_url, headers=UA, timeout=60)
                if resp.status_code != 200:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                text = (_pdf_text(resp.content) if resp.content[:4] == b"%PDF"
                        else _strip_tags(resp.text))
                jobs, date = _ny_fields_from_text(text)
            except Exception:
                failed += 1
                continue
            e = _entry("NY", company, jobs, date or _to_iso_date(notice_text),
                       detail_url=detail_url)
            if e:
                out.append(e)
                kept += 1
        print(f"    NY {label}: {kept} kept, {failed} failed of {len(rows)} rows")
    return out


CUSTOM_STATES = {
    "TX": fetch_tx, "FL": fetch_fl, "GA": fetch_ga, "OH": fetch_oh,
    "MI": fetch_mi, "CO": fetch_co, "ID": fetch_id, "LA": fetch_la,
    "NC": fetch_nc, "NV": fetch_nv, "MN": fetch_mn, "MA": fetch_ma,
    "NY": fetch_ny_history,
}


def pull_warn_custom(states):
    """Fetch the custom states (intersection with `states`, or all when 'all')."""
    scrape_all = len(states) == 1 and str(states[0]).lower() == "all"
    wanted = list(CUSTOM_STATES) if scrape_all else [s.upper() for s in states if s.upper() in CUSTOM_STATES]
    results = []
    for st in wanted:
        try:
            entries = CUSTOM_STATES[st]()
            print(f"WARN {st} (custom): {len(entries)} notices kept")
            results.extend(entries)
        except Exception as e:
            print(f"WARN {st} (custom) FAILED: {e}")
    return results
