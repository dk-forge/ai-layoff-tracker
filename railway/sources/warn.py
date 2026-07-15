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


# Count column detection: a header that names a headcount, but never an
# address/site/reason/id column (those hold digits that look like counts).
_COUNT_INCL = ["affected", "employee", "worker", "workforce", "total_layoff", "layoff_number", "headcount"]
_COUNT_EXCL = ["address", "site", "county", "zip", "postal", "code", "reason", "index",
               "name", "date", "phone", "area", "region", "wda", "lwib", "url", "page"]


def _count_col(rl):
    for k, v in rl.items():
        if not v or any(x in k for x in _COUNT_EXCL):
            continue
        if any(kw in k for kw in _COUNT_INCL):
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
    m = re.match(r"^([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})", s)  # Jan 22, 2026
    if m:
        mon = _MON3.get(m.group(1)[:3].lower())
        if mon:
            return f"{m.group(3)}-{mon:02d}-{int(m.group(2)):02d}"
    return ""


def _count(s):
    digits = re.sub(r"[^0-9]", "", (s or "").split(".")[0])
    return int(digits) if digits else 0


# States warn-scraper supports (used for the "all" sweep).
ALL_STATES = [
    "AK", "AL", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "IA", "ID", "IN",
    "KS", "KY", "LA", "MD", "ME", "MI", "MO", "MT", "NE", "NJ", "NM", "NY", "OH",
    "OK", "OR", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA", "WI",
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

    results = []
    for st, path in state_files:
        if not os.path.exists(path):
            print(f"WARN: no output file for {st}")
            continue

        kept = 0
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            for row in csv.DictReader(fh):
                rl = _row_lower(row)
                company = _match(rl, ["company", "employer", "business", "job_site",
                                      "job site", "organization", "establishment", "firm"])
                jobs = _count(_count_col(rl))
                date = _to_iso_date(_match(rl,
                    ["effective", "layoff start", "layoff_date", "closure start",
                     "starts", "layoff/closure"],   # preferred: effective / start dates
                    ["notice"],                       # then notice date
                    ["received"],                     # then received date
                    ["date"]))                        # any remaining date column
                city = _match(rl, ["city"], ["location"])
                kind = _match(rl, ["closure", "warn_type", "type of layoff", "layoff or closure"])

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
