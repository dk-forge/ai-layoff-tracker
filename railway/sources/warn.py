"""
Pulls US state WARN Act notices (legally-required mass-layoff filings) via the
open-source `warn-scraper` package from Big Local News, and maps them to the
tracker's schema.

WARN notices are authoritative government filings: company, employee count,
effective date, and location are all stated on the form. They never mention AI
(they're standardized legal forms), so these entries are posted directly without
the LLM extractor, with ai_explicit=False and a dedicated 'warn' source tier.
"""
import csv
import hashlib
import os
import re
import subprocess
import tempfile

# Official WARN program page per state — the fallback link when a notice has
# no per-row detail URL of its own.
STATE_WARN_URL = {
    "AK": "https://jobs.alaska.gov/RR/WARN_notices.htm",
    "AL": "https://www.madeinalabama.com/warn-list/",
    "AZ": "https://www.azcommerce.com/arizona-warn-notices",
    "CA": "https://edd.ca.gov/en/jobs_and_training/layoff_services_warn/",
    "CO": "https://cdle.colorado.gov/employers/layoff-separations/layoff-warn-list",
    "CT": "https://www.ctdol.state.ct.us/progsupt/bussrvce/warnreports/warnreports.htm",
    "DC": "https://does.dc.gov/page/industry-closings-and-layoffs-warn-notifications",
    "DE": "https://joblink.delaware.gov/search/warn_lookups",
    # FloridaCommerce moved the WARN page 2026-07 (old REACT path now 404s)
    "FL": "https://floridajobs.org/workforce-resources/worker-adjustment-and-retraining-notification-(warn)",
    "GA": "https://www.dol.state.ga.us/public/es/warn/searchwarns/list",
    "HI": "https://labor.hawaii.gov/wdc/warn-notices/",
    "IA": "https://www.iowaworkforcedevelopment.gov/worker-adjustment-and-retraining-notification-act",
    "ID": "https://www.labor.idaho.gov/businesss/layoff-assistance/",
    "IL": "https://dceo.illinois.gov/workforcedevelopment/warn.html",
    "IN": "https://www.in.gov/dwd/warn-notices/",
    "KS": "https://www.kansasworks.com/search/warn_lookups",
    "KY": "https://kcc.ky.gov/employer/Pages/Business-Downsizing-Assistance---WARN.aspx",
    "LA": "https://www.laworks.net/Downloads/Downloads_WFD.asp",
    "MD": "https://www.dllr.state.md.us/employment/warn.shtml",
    "ME": "https://joblink.maine.gov/search/warn_lookups",
    "MI": "https://milmi.org/warn/",
    "MO": "https://jobs.mo.gov/warn",
    "MT": "https://wsd.dli.mt.gov/wioa/related-links/warn-notice-page",
    "NE": "https://dol.nebraska.gov/ReemploymentServices/LayoffServices/LayoffsAndDownsizingWARN",
    "NJ": "https://www.nj.gov/labor/employer-services/warn/",
    "NM": "https://www.dws.state.nm.us/Rapid-Response",
    "NY": "https://dol.ny.gov/warn-notices",
    "OH": "https://jfs.ohio.gov/warn/index.stm",
    "OK": "https://oklahoma.gov/oesc/businesses/warn-notices.html",
    "OR": "https://ccwd.hecc.oregon.gov/Layoff/WARN",
    "PA": "https://www.pa.gov/en/agencies/dli/programs-services/workforce-development/warn.html",
    "RI": "https://dlt.ri.gov/employers/worker-adjustment-and-retraining-notification-warn",
    "SC": "https://scworks.org/employer/employer-programs/at-risk-of-closing/layoff-notification-reports",
    "SD": "https://dlr.sd.gov/workforce_services/businesses/warn_notices.aspx",
    "TN": "https://www.tn.gov/workforce/general-resources/major-publications0/major-publications-redirect/reports.html",
    "TX": "https://www.twc.texas.gov/programs/rapid-response-program",
    "UT": "https://jobs.utah.gov/employer/business/warnnotices.html",
    "VA": "https://www.vec.virginia.gov/warn-notices",
    "VT": "https://www.vermontjoblink.com/search/warn_lookups",
    "WA": "https://esd.wa.gov/about-employees/WARN",
    "WI": "https://dwd.wisconsin.gov/dislocatedworker/warn/",
}


def _row_lower(row):
    """{lowercased/trimmed header: trimmed value}, dropping the None key csv adds
    for trailing commas."""
    out = {}
    for k, v in row.items():
        if k is None:
            continue
        out[k.lower().strip()] = (v or "").strip()
    return out


def _match(rl, *groups):
    """Return the first non-empty value whose header contains one of the keywords,
    trying each keyword group in priority order (so 'effective date' beats
    'notice date', etc.)."""
    for keywords in groups:
        for k, v in rl.items():
            if v and any(kw in k for kw in keywords):
                return v
    return ""


def _date_from(rl, *groups):
    """Like _match, but only accepts values that PARSE as dates — Illinois has
    a boolean 'WARN Notice' column whose 'True' would otherwise win the
    'notice' tier and block the real date columns behind it."""
    for keywords in groups:
        for k, v in rl.items():
            if not v or not any(kw in k for kw in keywords):
                continue
            iso = _to_iso_date(v)
            if iso:
                return iso
    return ""


# Count column detection in priority tiers: layoff-specific columns first
# (IL publishes BOTH "Approximate Total # of Full-Time Employees" — site
# headcount — and "Expected Layoff"; the latter is the real number), generic
# jobs/workers second, bare "employee" columns last. Never an address/site/
# reason/id column (those hold digits that look like counts).
_COUNT_TIERS = [
    ["affected", "laid off", "expected layoff", "revised layoff", "total_layoff", "layoff_number", "workforce"],
    ["worker", "headcount", "jobs", "job ", "emp #"],
    ["employee"],
]
# "company"/"employer" excluded: CT DOL publishes an "affected_company"
# column, which tier-1 "affected" matched — so counts were parsed out of the
# company NAME (names without digits -> 0 -> row dropped; CT collection was
# effectively dead, e.g. the 313-worker CVS/Aetna notice).
_COUNT_EXCL = ["address", "site", "county", "zip", "postal", "code", "reason", "index",
               "name", "date", "phone", "area", "region", "wda", "lwib", "url", "page",
               "company", "employer"]


def _count_col(rl):
    # Prefer a positive "Revised" figure first: Illinois keeps ONE cumulative
    # row per site event and revises it in place, so the original "Expected
    # Layoff" understates every later notification (Capital One/Discover
    # Riverwoods: expected 215 vs revised 2,027 across six notice dates).
    for k, v in rl.items():
        if not v or any(x in k for x in _COUNT_EXCL):
            continue
        if "revised" in k:
            digits = re.search(r"\d[\d,]*", str(v))
            if digits and int(digits.group(0).replace(",", "")) > 0:
                return v
    for tier in _COUNT_TIERS:
        for k, v in rl.items():
            if not v or any(x in k for x in _COUNT_EXCL):
                continue
            if any(kw in k for kw in tier) or k.strip() == "jobs":
                return v
    return ""


_MON3 = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def _to_iso_date(s):
    s = (s or "").strip()
    if not s:
        return ""
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)               # 2026-09-04 [00:00:00]
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)             # 8/7/2026 (US M/D/Y)
    if m:
        y = m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    # "Jan 22, 2026" — searched anywhere, not anchored, because states embed
    # dates in prose ("Beginning: January 23, 2023; Ending: March 24, 2023" —
    # the first date is the start, which matches our lower-bound convention).
    m = re.search(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m:
        mon = _MON3.get(m.group(1)[:3].lower())
        if mon:
            return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return ""


def _count(s):
    """Parse the FIRST number in the field. Stripping all non-digits is wrong:
    RI publishes values like '9,891 Remote Workers (2 from RI)', which would
    concatenate into 98912. First-number also makes ranges ('50-100') resolve
    to the lower bound, matching the tracker's stated methodology.

    A date-shaped value means the column matcher grabbed the wrong field — a
    first-number parse of '2026-07-01' would fabricate a plausible-looking
    2,026-worker count, so reject those outright."""
    s = (s or "").strip()
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", s) or re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", s):
        return 0
    m = re.search(r"\d{1,3}(?:,\d{3})+|\d+", s)
    return int(m.group(0).replace(",", "")) if m else 0


# States warn-scraper supports (used for the "all" sweep). Keep in sync with
# site-packages/warn/scrapers/ — an audit found HI, IL, PA missing from an
# earlier version of this list (IL and PA are top-5 layoff states!).
ALL_STATES = [
    "AK", "AL", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA", "ID",
    "IL", "IN", "KS", "KY", "LA", "MD", "ME", "MI", "MO", "MS", "MT", "ND", "NE",
    "NJ", "NM", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
    "VA", "VT", "WA", "WI",
]


def _run_scraper(states, workdir):
    """Scrape each state as its own subprocess with a per-state timeout, so a
    single slow or broken state site can't kill the whole sweep."""
    for st in states:
        cmd = ["warn-scraper", "--data-dir", workdir,
               "--cache-dir", os.path.join(workdir, "cache"), "-l", "error", st]
        try:
            subprocess.run(cmd, check=False, timeout=420)
        except Exception as e:
            print(f"warn-scraper {st} error/timeout: {e}")


def pull_warn(states, min_employees=0, start_date=""):
    """Return normalized WARN entries for the given state codes.

    states         list of 2-letter codes (e.g. ["CA", "NY"]), or ["all"] to
                   scrape every state warn-scraper supports
    min_employees  drop notices below this headcount (volume control)
    start_date     'YYYY-MM-DD'; drop notices with an earlier effective date
    """
    scrape_all = len(states) == 1 and states[0].lower() == "all"
    to_scrape = ALL_STATES if scrape_all else [s.upper() for s in states]
    workdir = tempfile.mkdtemp(prefix="warn_")
    _run_scraper(to_scrape, workdir)

    # Read whatever CSVs actually got written (one per state, code from filename).
    import glob
    files = sorted(glob.glob(os.path.join(workdir, "*.csv")))
    state_files = [(os.path.splitext(os.path.basename(f))[0].upper(), f) for f in files]

    # States whose CSVs ship with NO header row (Maryland writes data from
    # line 1); supply the column names so DictReader doesn't eat row 1.
    headerless = {
        "MD": ["notice_date", "naics", "company", "address", "county",
               "affected", "effective_date", "layoff_type"],
    }

    results = []
    for st, path in state_files:
        if not os.path.exists(path):
            print(f"WARN: no output file for {st}")
            continue

        kept = 0
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh, fieldnames=headerless.get(st)):
                rl = _row_lower(row)
                company = _match(rl, ["company", "employer", "business", "job_site",
                                      "job site", "organization", "establishment", "firm",
                                      "location name"])  # Illinois names it "Location Name"
                jobs = _count(_count_col(rl))
                date = _date_from(rl,
                    ["effective", "layoff start", "layoff_date", "layoff date",
                     "layoff begin", "closure start", "starts", "layoff/closure",
                     "impact date"],                  # preferred: effective/impact
                    ["notice"],                       # then notice date
                    ["received"],                     # then received date
                    ["date"])                         # any remaining date column
                city = _match(rl, ["city"], ["location"])
                kind = _match(rl, ["closure", "warn_type", "type of layoff", "layoff or closure"])
                # Some states publish a per-notice detail link (e.g. VT's
                # detail_page_url) — prefer it over the program landing page.
                detail = _match(rl, ["detail_page_url", "detail page", "notice_url", "url", "link"])
                if not detail.lower().startswith("http"):
                    detail = ""

                # jobs cap rejects parse errors (no real single WARN notice is
                # anywhere near 100K workers).
                if not company or jobs <= 0 or jobs > 100000 or not date:
                    continue
                # Guard against source data-entry typos (e.g. "3030-03-30").
                # WARN effective dates are at most ~a year out from filing.
                if date < "2015-01-01" or date > "2028-12-31":
                    continue
                if min_employees and jobs < min_employees:
                    continue
                if start_date and date < start_date:
                    continue

                # `city` sometimes already contains a state ("Minneapolis, MN"),
                # so never glue the filing state onto it.
                loc = f" in {city}" if city else ""
                excerpt = (f"{kind or 'Layoff'} at {company}{loc}. "
                           f"{jobs:,} employees affected, effective {date}. "
                           f"Filed under the {st} WARN Act.")
                hash_input = (f"warn{company.lower().strip()}{date}{jobs}"
                              f"{city.lower().strip()}{st}")

                results.append({
                    "source_type": "warn",
                    "source_name": f"{st} WARN notice",
                    "verification_level": "warn",
                    "company_name": company.strip(),
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
                    "source_url": detail or STATE_WARN_URL.get(st, ""),
                    "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
                    "is_layoff_event": True,
                })
                kept += 1
        print(f"WARN {st}: {kept} notices kept")

    return results
