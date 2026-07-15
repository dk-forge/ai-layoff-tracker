"""
Custom WARN collectors for states the open-source warn-scraper can no longer
read (their sites changed). Each fetcher was built from a machine-verified
recon spec (2026-07-15) and returns entries in the exact same shape — and with
the exact same dedup-hash formula — as sources/warn.py, so re-imports upsert
instead of duplicating.

States: TX (Socrata JSON), FL (POST form -> HTML table), GA (WP admin-ajax),
OH (CSV on the Ohio DAM), MI (Sitecore search JSON), CO (Google Sheets xlsx),
ID (text PDF), LA (per-year text PDFs).
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


def fetch_oh():
    """Ohio DAM CSV, url discovered from the JFS notices page (headers on row 3)."""
    import csv as _csv
    from datetime import date as _date
    landing = "https://jfs.ohio.gov/job-services-and-unemployment/job-services/warn/warn-current-public-notices"
    urls = []
    try:
        page = requests.get(landing, headers=UA, timeout=TIMEOUT).text
        urls = re.findall(r'https://dam\.assets\.ohio\.gov/raw/upload/[^"\\ ]+\.csv', page)
    except Exception as e:
        print(f"OH landing fetch failed ({e}), falling back to versionless URLs")
    for y in (_date.today().year, _date.today().year - 1):
        urls.append(f"https://dam.assets.ohio.gov/raw/upload/jfs.ohio.gov/{y}/{y}-warn-notice.csv")
    out, seen_urls = [], set()
    for u in urls:
        if u in seen_urls:
            continue
        seen_urls.add(u)
        try:
            text = requests.get(u, headers=UA, timeout=TIMEOUT).text
        except Exception:
            continue
        lines = text.splitlines()
        # headers may sit a couple of renderer-metadata rows down
        start = next((i for i, ln in enumerate(lines[:6]) if "company" in ln.lower()), None)
        if start is None:
            continue
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


def fetch_la():
    """Louisiana: per-year text-layer PDFs (2025+), updated in place."""
    from datetime import date as _date
    out = []
    for y in range(2025, _date.today().year + 1):
        url = f"https://www.laworks.net/Downloads/WFD/WarnNotices{y}.pdf"
        try:
            resp = requests.get(url, headers=UA, timeout=60)
            if resp.status_code != 200 or not resp.content[:4] == b"%PDF":
                continue
        except Exception:
            continue
        for table in _pdf_tables(resp.content):
            for row in table:
                cells = ["" if c is None else str(c).strip().replace("\n", " ") for c in row]
                if len(cells) < 5 or "company" in (cells[0] or "").lower():
                    continue
                if len(cells) >= 6:   # 2026: Company|Address|Notice|Layoff|Affected|Industry
                    company, notice, layoff, affected = cells[0], cells[2], cells[3], cells[4]
                else:                 # 2025: Company(+addr)|Notice|Layoff|Affected|Industry
                    company, notice, layoff, affected = cells[0], cells[1], cells[2], cells[3]
                jobs = _count(affected)
                date = _to_iso_date(layoff) or _to_iso_date(notice)
                e = _entry("LA", company, jobs, date, detail_url=url)
                if e:
                    out.append(e)
    return out


CUSTOM_STATES = {
    "TX": fetch_tx, "FL": fetch_fl, "GA": fetch_ga, "OH": fetch_oh,
    "MI": fetch_mi, "CO": fetch_co, "ID": fetch_id, "LA": fetch_la,
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
