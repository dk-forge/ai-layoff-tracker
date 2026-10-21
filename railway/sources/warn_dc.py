"""District of Columbia WARN notices, read straight off the DOES year pages.

WHY THIS EXISTS (2026-10-20). The open warn-scraper DC module walks a list of
year links on the current page before it parses anything. DOES replaced that
list with relative "Rapid Response" links, so the module raised MissingSchema
on '/page/rapid-response' and DC returned nothing, while the current year's
table was still on the page. This reads the table on the current and previous
year pages only (the history is already stored) and follows no link.

Entries go through warn_custom._entry, so the dedup hash is the generic tier's
and a notice already stored from the open scraper is not published twice. The
date is the effective date, falling back to the notice date, matching the
generic tier's preference in sources/warn.py.
"""
import datetime as _dt

import requests

from .warn import _count, _to_iso_date
from .warn_custom import _entry

_PAGE = "https://does.dc.gov/page/industry-closings-and-layoffs-warn-notifications-{year}"
UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")}
TIMEOUT = 45


def _rows(html):
    from bs4 import BeautifulSoup
    table = BeautifulSoup(html, "html.parser").find("table")
    if table is None:
        return []
    out = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 4 and tr.find("td") is not None:
            out.append(cells)
    return out


def fetch_dc(today=None):
    year = (today or _dt.date.today()).year
    out, seen, served = [], set(), 0
    for y in (year, year - 1):
        url = _PAGE.format(year=y)
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
        except Exception as exc:                           # noqa: BLE001
            print(f"    DC {y}: {exc}")
            continue
        if r.status_code != 200:
            print(f"    DC {y}: HTTP {r.status_code}")
            continue
        served += 1
        for notice, company, jobs, effective, *_ in _rows(r.text):
            date = _to_iso_date(effective) or _to_iso_date(notice)
            e = _entry("DC", company, _count(jobs), date, detail_url=url)
            if e and e["dedup_hash"] not in seen:
                seen.add(e["dedup_hash"])
                out.append(e)
    if not served:
        raise RuntimeError("DC: no DOES WARN year page was served")
    print(f"WARN DC (custom): {len(out)} notices kept")
    return out
