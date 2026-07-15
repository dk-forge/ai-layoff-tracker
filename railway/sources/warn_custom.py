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


def fetch_nc():
    """NC Commerce Drupal year page -> rotating date-stamped CSV on files.nc.gov."""
    from datetime import date as _date
    out = []
    for y in (_date.today().year, _date.today().year - 1):  # Jan rollover safety
        page = requests.get(
            "https://www.commerce.nc.gov/data-tools-reports/labor-market-data-tools/"
            f"workforce-warn-reports/report-workforce-warn-summary-list-{y}",
            headers=UA, timeout=TIMEOUT)
        if page.status_code != 200:
            continue
        m = re.search(r'href="(https://files\.nc\.gov/[^"]+\.csv[^"]*)"', page.text)
        if not m:
            continue
        text = requests.get(_html.unescape(m.group(1)), headers=UA, timeout=TIMEOUT).text
        import csv as _csv
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
_MN_SEED_PDFS = [  # verified-live 2026-07-15; CDX discovery adds the rest
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-report-2023_tcm1045-663809.pdf",
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-october-2025_tcm1045-712065.pdf",
    "https://mn.gov/deed/assets/plant-closing-mass-layoff-warn-2026-january_tcm1045-722872.pdf",
]

def fetch_mn():
    """MN DEED monthly/annual report PDFs (assets bypass the bot wall)."""
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
                    idx = None
                    for row in table:
                        # header cells wrap ('Affected\nWorkers') — normalize
                        cells = [re.sub(r"\s+", " ", (c or "")).strip() for c in row]
                        if idx is None:
                            if any("Layoff Name" in c for c in cells):
                                idx = {name: i for i, c in enumerate(cells)
                                       for name in ("Layoff Name", "Account: City", "Layoff Start",
                                                    "WARN Received", "Affected Workers") if name in c}
                            continue
                        if len(idx) < 3 or not cells[0] or cells[0].startswith(("RR Start", "Count")):
                            continue
                        get = lambda k: cells[idx[k]] if k in idx and idx[k] < len(cells) else ""
                        company = re.sub(r"\s+20\d\d$", "", get("Layoff Name"))
                        e = _entry("MN", company, _count(get("Affected Workers")),
                                   _to_iso_date(get("Layoff Start")) or _to_iso_date(get("WARN Received")),
                                   get("Account: City"), detail_url=url)
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


CUSTOM_STATES = {
    "TX": fetch_tx, "FL": fetch_fl, "GA": fetch_ga, "OH": fetch_oh,
    "MI": fetch_mi, "CO": fetch_co, "ID": fetch_id, "LA": fetch_la,
    "NC": fetch_nc, "NV": fetch_nv, "MN": fetch_mn, "MA": fetch_ma,
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
