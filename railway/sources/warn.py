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

# Landing page for each state's WARN program (individual notices have no URL).
STATE_WARN_URL = {
    "CA": "https://edd.ca.gov/en/jobs_and_training/layoff_services_warn/",
    "NY": "https://dol.ny.gov/warn-notices",
    "TX": "https://www.twc.texas.gov/programs/rapid-response-program",
    "WA": "https://esd.wa.gov/about-employees/WARN",
    "IL": "https://dceo.illinois.gov/aboutdceo/reportsrequiredbystatute/warnreports.html",
    "NJ": "https://www.nj.gov/labor/employer-services/warn/",
    "OH": "https://jfs.ohio.gov/warn/index.stm",
    "FL": "https://floridajobs.org/office-directory/division-of-workforce-services/workforce-programs/reemployment-and-emergency-assistance-coordination-team-react/warn-notices",
    "PA": "https://www.pa.gov/en/agencies/dli/programs-services/workforce-development/warn.html",
    "GA": "https://www.dol.state.ga.us/public/es/warn/searchwarns/list",
}


def _pick(row, *names):
    """Case-insensitively return the first non-empty value among the columns."""
    lowered = {(k or "").lower().strip(): (v or "") for k, v in row.items()}
    for n in names:
        v = lowered.get(n, "").strip()
        if v:
            return v
    return ""


def _to_iso_date(s):
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        y = m.group(3)
        if len(y) == 2:
            y = "20" + y
        return f"{y}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    return ""


def _count(s):
    digits = re.sub(r"[^0-9]", "", (s or "").split(".")[0])
    return int(digits) if digits else 0


def _run_scraper(states, workdir):
    cmd = ["warn-scraper", "--data-dir", workdir,
           "--cache-dir", os.path.join(workdir, "cache"), "-l", "error"] + states
    try:
        subprocess.run(cmd, check=False, timeout=1800)
    except Exception as e:
        print(f"warn-scraper error: {e}")


def pull_warn(states, min_employees=0, start_date=""):
    """Return normalized WARN entries for the given state codes.

    states         list of 2-letter codes (e.g. ["CA", "NY"]), or ["all"] to
                   scrape every state warn-scraper supports
    min_employees  drop notices below this headcount (volume control)
    start_date     'YYYY-MM-DD'; drop notices with an earlier effective date
    """
    scrape_all = len(states) == 1 and states[0].lower() == "all"
    workdir = tempfile.mkdtemp(prefix="warn_")
    _run_scraper(["all"] if scrape_all else [s.upper() for s in states], workdir)

    if scrape_all:
        # warn-scraper writes one CSV per state it scraped; derive the code from
        # the filename (ca.csv -> CA), skipping the cache dir.
        import glob
        files = sorted(glob.glob(os.path.join(workdir, "*.csv")))
        state_files = [(os.path.splitext(os.path.basename(f))[0].upper(), f) for f in files]
    else:
        state_files = [(s.upper(), os.path.join(workdir, f"{s.lower()}.csv")) for s in states]

    results = []
    for st, path in state_files:
        if not os.path.exists(path):
            print(f"WARN: no output file for {st}")
            continue

        kept = 0
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                company = _pick(row, "company", "company name", "employer",
                                "employer name", "name")
                jobs = _count(_pick(row, "num_employees", "number of employees",
                                    "employees affected", "affected employees",
                                    "employees", "# affected", "workers affected"))
                date = _to_iso_date(_pick(row, "effective_date", "effective date",
                                          "layoff date", "notice_date",
                                          "notice date", "received_date",
                                          "date received"))
                city = _pick(row, "city", "location", "city name")
                kind = _pick(row, "layoff_or_closure", "closure/layoff",
                             "closure or layoff", "type", "notice type")

                if not company or jobs <= 0 or not date:
                    continue
                # Guard against source data-entry typos (e.g. "3030-03-30").
                # WARN effective dates are at most ~a year out from filing.
                if date < "2015-01-01" or date > "2028-12-31":
                    continue
                if min_employees and jobs < min_employees:
                    continue
                if start_date and date < start_date:
                    continue

                where = f"{city}, {st}" if city else st
                excerpt = (f"{kind or 'Layoff'} at {company} in {where}. "
                           f"{jobs:,} employees affected, effective {date} "
                           f"(state WARN Act notice).")
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
                    "country": "US",
                    "state": st,
                    "roles": None,
                    "excerpt": excerpt,
                    "reason_tags": [],
                    "ai_explicit": False,
                    "ai_language": None,
                    "source_url": STATE_WARN_URL.get(st, ""),
                    "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
                    "is_layoff_event": True,
                })
                kept += 1
        print(f"WARN {st}: {kept} notices kept")

    return results
