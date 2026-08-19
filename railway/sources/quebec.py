"""Quebec collective-dismissal notices (avis de licenciements collectifs).

Quebec's Ministere de l'Emploi et de la Solidarite sociale (MESS) publishes a
monthly PDF of collective-dismissal notices employers must file under the Act
respecting labour standards. This is Canada's closest analog to a US WARN
notice: a legal advance notice of a mass layoff, with employer, headcount and
effective date. We parse the monthly PDFs and route them through the same
structured /bulk path as WARN (no LLM).

It is also the ONLY named per-employer layoff register in Canada, and its
statutory floor is 10 employees against US WARN's 50, so it sees cuts no other
collector in this repo can see. That is why a zero here is an outage and not a
quiet month (see `zero_is_outage` in source_value.py).

Source: https://www.quebec.ca/gouvernement/ministeres-organismes/emploi-solidarite-sociale/publications
PDFs:   https://cdn-contenu.quebec.ca/.../avis_licenciements_collectifs/LI_licenciement-collectif_YYYY-MM_MESS.pdf

TWO ROUTES TO THE SAME PDFS, because one route is a single point of failure.
On 2026-08-13 this collector had been reporting 0 for days. The PDFs were fine
and the parser was fine: the LANDING PAGE fetch from a GitHub runner came back
without the links (`no monthly PDF links found`), while the identical fetch from
a laptop returned all 13. One scraped HTML page stood between us and a statutory
register, and when it stopped answering we reported "check PDF layout" and
waited for a human. So discovery is now the UNION of:
  A. the landing page (authoritative: catches a change to the URL pattern), and
  B. URLs CONSTRUCTED from the documented CDN template for the last N months
     (needs no HTML at all, so a WAF, a redesign or a geo-block cannot zero us).
Route B alone would go blind to a renamed file, and route A alone is what broke.
Neither is a fallback for the other in the "try if desperate" sense: both run,
their candidates merge, and 404s are skipped quietly.

COMPLETENESS IS CHECKED AGAINST THE DOCUMENT ITSELF. Each region block ends with
`Nombre d'avis : N  Nombre de salaries licencies : M`, so the PDF states how many
notices it contains. We parse those totals and compare, which turns "we returned
some rows" into "we returned 41 of the 44 this document says it holds". A thin
parse can no longer read as a healthy one.

Parser note: the PDF is a multi-column, glyph-positioned layout. Each notice's
core (employer, NEQ business number, address, notice date, effective date,
headcount) lands on one physical line; the reason/activity columns wrap. We
parse per line and keep ONLY rows whose employer is clearly valid, dropping a
wrapped row rather than posting a garbled company name (documented-floor rule).
"""
import datetime
import hashlib
import io
import re

import requests

PUBLICATIONS_URL = ("https://www.quebec.ca/gouvernement/ministeres-organismes/"
                    "emploi-solidarite-sociale/publications")
# The documented CDN template. Route B builds month URLs straight from this, so
# discovery never depends on the HTML page rendering or answering.
CDN_TEMPLATE = ("https://cdn-contenu.quebec.ca/cdn-contenu/adm/min/"
                "emploi-solidarite-sociale/publications-adm/documents-administratifs/"
                "avis_licenciements_collectifs/LI_licenciement-collectif_%s_MESS.pdf")
# The filename is ALMOST deterministic. Six months are not, and a generated URL
# 404s on every one of them, so route B would silently lose half a year while
# reporting success. Verified 2026-08-13 by probing every month 2019-01..2026-12:
# the live CDN serves 2023-08 through 2026-07 continuously ONLY if these are
# hard-coded. The 2032 pair is a genuine ministry typo, not a guess -- the PDF's
# own /Subject metadata reads "pour le mois d'octobre 2023".
_MONTH_URL_EXCEPTIONS = {
    "2023-10": "LI_licenciement-collectif_2032-10_MESS.pdf",   # ministry typo: 2032
    "2023-11": "LI_licenciement-collectif_2032-11_MESS.pdf",   # ministry typo: 2032
    "2023-12": "LI_MENS_Internet_2023-12.pdf",
    "2024-01": "LI_MENS_Internet_2024-01.pdf",
    "2024-02": "LI_MENS_2024-02_Internet.pdf",
    "2024-03": "LI_MENS_2024-03_Internet.pdf",
}
_CDN_DIR = CDN_TEMPLATE.rsplit("/", 1)[0] + "/"
# Earliest month on the live CDN (2026-08-13 probe). Older months exist only in
# the Wayback Machine, and on a RETIRED host (travail.gouv.qc.ca) back to
# 2021-03 under at least four different naming schemes. Backfilling those is a
# separate job: enumerate with the CDX API rather than guessing filenames.
EARLIEST_LIVE_MONTH = "2023-08"
_LANDING_RX = re.compile(
    r'https://cdn-contenu\.quebec\.ca/[^"\'\s<>]+/avis_licenciements_collectifs/'
    r'LI_licenciement-collectif_(\d{4}-\d{2})_MESS\.pdf')
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 30

# One notice per line: <employer> <NEQ(10 digits)> <address...> <notice date>
# <effective date> <headcount>. Non-greedy up to the first ISO date pair.
_LINE_RX = re.compile(
    r"^(?P<emp>.+?)\s+\d{10}\s+.*?"
    r"(?P<notice>\d{4}-\d{2}-\d{2})\s+(?P<eff>\d{4}-\d{2}-\d{2})\s+(?P<count>\d{1,5})\b")
# Same row, but the NEQ wrapped onto the CONTINUATION line, so the employer name
# is followed straight by the date pair ("Amdocs Canadian Managed Services Inc.
# 2026-07-22 2026-07-31 13 ..."). Tried only after _LINE_RX misses, and gated by
# the same _valid_emp, so it widens recall without loosening the name floor.
_LINE_NO_NEQ_RX = re.compile(
    r"^(?P<emp>.+?)\s+(?P<notice>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<eff>\d{4}-\d{2}-\d{2})\s+(?P<count>\d{1,5})\b")
# The tally the document prints for itself. Our audit against it.
#
# It prints TWICE: once per region block, then once as a grand total. Summing
# every match double-counts the whole document (2026-07 read as 40 notices when
# it holds 20), which would have made a complete parse look like it was missing
# half the register — an audit that cries wolf gets switched off, so it has to
# be right. The grand total wins when present; the region lines are summed only
# when it is absent.
#
# French-Canadian typography groups thousands with a SPACE, so the document says
# "1 006" and a `\d{1,6}` reads it as 1. That understated the register by three
# orders of magnitude in exactly the months that mattered most (a big month is
# the one with four digits), and it would have shown up as "we parsed 1,006 of
# the 1 the document declares" -- an audit line absurd enough to be ignored.
_NUM = r"\d[\d\s  ]{0,8}\d|\d"
_REGION_TOTAL_RX = re.compile(
    r"Nombre\s+d.avis\s*:\s*(?P<notices>" + _NUM + r").*?"
    r"Nombre\s+de\s+salari.s\s+licenci.s\s*:\s*(?P<jobs>" + _NUM + r")")
_GRAND_TOTAL_RX = re.compile(
    r"Total\s*-\s*Nombre\s+d.avis\s*:\s*(?P<notices>" + _NUM + r").*?"
    r"Total\s*-\s*Nombre\s+de\s+salari.s\s+licenci.s\s*:\s*(?P<jobs>" + _NUM + r")")


def _num(s):
    """Read a French-typography integer: '1 006' -> 1006."""
    return int(re.sub(r"[\s  ]", "", s or "0") or 0)

# Filled by pull_quebec so warn_import can report WHY a run was thin or empty,
# instead of guessing "check PDF layout" at a parser that was never the problem.
_LAST_REPORT = {}


def last_run_report():
    """What the most recent pull_quebec() actually saw, for the health detail."""
    return dict(_LAST_REPORT)


# A civic address tail the column split leaves glued to the employer name
# ("Les Chantiers de Chibougameau Ltee 67 Rue"). Stripped, not dropped: the
# notice is real and only its name is dirty.
_ADDR_TAIL_RX = re.compile(
    r"\s+\d{1,5}\s*[A-Za-z]?\s+(Rue|Av\.?|Avenue|Boul\.?|Boulevard|Ch\.?|Chemin|"
    r"Route|Rang|Place|Mont(?:ee|ée)|Terrasse|Impasse)\b.*$", re.I)


def _clean_emp(e):
    e = re.sub(r"\s+", " ", e or "").strip()
    e = re.sub(r"^\d{2}-[A-Za-zÀ-ü\-' ]+?\s{2,}", "", e)   # strip a leading region label
    e = _ADDR_TAIL_RX.sub("", e)
    e = re.sub(r"\s+\d{1,5}$", "", e)          # a dangling civic number
    return e.strip(" -,")


def _valid_emp(e):
    """Reject wrap fragments so a garbled row is dropped, never posted."""
    if len(e) < 3 or len(e) > 70:
        return False
    # A date leaked into the name. Matched as a FULL ISO date, or as a 4-2 group
    # with nothing numeric after it (a truncated one). The old `\d{4}-\d{2}`
    # also matched Quebec NUMBERED companies -- "2534-1215 Quebec Inc." reads as
    # "2534-12" plus junk -- and silently dropped every one of them. Numbered
    # corporations are a large share of this register, so that guard was quietly
    # deleting real statutory notices while the collector reported success.
    if re.search(r"\d{4}-\d{2}-\d{2}", e):
        return False
    if re.search(r"\d{4}-\d{2}(?!\d)", e):
        return False
    if not re.match(r"[A-Za-zÀ-ü0-9]", e):
        return False
    if e[0].islower():                        # continuation fragment ("mentale")
        return False
    # Leading digits are fine for a numbered company, which is a legal employer
    # name and not a fragment: Quebec provincial ones read "2534-1215 Quebec
    # Inc." and federal ones "7806302 Canada Inc - Planchers Mistral". Only a
    # bare digit-run with no following name is a wrapped address line. This is
    # safe because a continuation line carries no date pair, so it never reaches
    # here at all.
    if re.match(r"^\d", e) and not re.match(r"^(\d{3,9}\s|\d{4}-\d{4}\b)", e):
        return False
    return True


# THE MINISTRY'S OWN CAVEATS, on the row, because they change what the number
# means. MESS states them on every monthly list: the list holds notices RECEIVED
# in the period (a dismissal may fall outside it); a notice is an INTENTION to
# dismiss; a cancelled layoff is never removed; and the monthly list is a
# snapshot that is not retroactively corrected. A Quebec-derived figure
# therefore runs structurally HIGH against dismissals actually carried out, and
# a reader who is not told that will read it as executed cuts. Kept short
# because it renders in the public table's excerpt; the fuller statement is on
# the methodology page.
_NOTICE_CAVEAT = ("This is an employer's notice of INTENDED dismissal. The "
                  "ministry's monthly list is a snapshot that is not corrected "
                  "afterwards, so a layoff later cancelled or reduced stays on "
                  "it.")


def _entry(company, jobs, date, region="", reason="", source_url=None):
    company = (company or "").strip()
    if not company or jobs <= 0 or jobs > 100000 or not date:
        return None
    if date < "2015-01-01" or date > "2028-12-31":
        return None
    loc = f" ({region})" if region else ""
    is_closure = "fermeture" in (reason or "").lower()
    excerpt = (f"{'Closure' if is_closure else 'Collective dismissal'} at "
               f"{company}{loc}, Quebec. {jobs:,} employees affected, effective "
               f"{date}. Filed under Quebec's collective-dismissal notice rules "
               f"(MESS). {_NOTICE_CAVEAT}")
    hash_input = f"warnqc{company.lower().strip()}{date}{jobs}"
    return {
        "source_type": "warn",
        "source_name": "Quebec collective dismissal (MESS)",
        "verification_level": "warn",
        "company_name": company,
        "ticker": None,
        "job_count": jobs,
        "layoff_date": date,
        "industry": None,
        "country": "Canada",
        "state": "",
        "roles": None,
        "excerpt": excerpt,
        "reason_tags": (["closure"] if is_closure else []),
        "ai_explicit": False,
        "ai_language": None,
        # The MONTHLY PDF this notice was read out of, not the publications
        # index. Every row cited the index until 2026-08-18, which meant a
        # reader who wanted to check one landed on a page listing every
        # ministry publication and had to work out which month to open. A
        # source link that does not reach the document is a citation in
        # appearance only. Falls back to the index if a caller has no URL.
        "source_url": source_url or PUBLICATIONS_URL,
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def _month_keys(months_back):
    """The last `months_back` YYYY-MM keys, most recent first.

    Starts one month BACK, not at the current month: the ministry publishes a
    month's list in the first days of the FOLLOWING month, so the current month
    is a guaranteed 404 for most of its length. Including it anyway is harmless
    (404s are skipped) and it picks the new file up the day it appears.
    """
    today = datetime.date.today()
    out, y, m = [], today.year, today.month
    for _ in range(max(1, months_back) + 1):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def _discover(months_back):
    """Candidate monthly-PDF URLs, most recent month first, from BOTH routes.

    Returns (urls, notes). `notes` records what each route contributed so a
    thin or empty run can name the route that went quiet rather than blaming
    the parser.
    """
    wanted = _month_keys(months_back)
    by_month, notes = {}, {}

    # Route A: the landing page. Authoritative for the URL pattern itself.
    try:
        r = requests.get(PUBLICATIONS_URL, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            notes["landing"] = f"HTTP {r.status_code}"
        else:
            found = {m: u for u, m in
                     ((mt.group(0), mt.group(1)) for mt in _LANDING_RX.finditer(r.text))}
            notes["landing"] = f"{len(found)} link(s)"
            for month, url in found.items():
                by_month.setdefault(month, url)
    except Exception as exc:
        notes["landing"] = f"fetch failed: {type(exc).__name__}"

    # Route B: construct from the documented template. Needs no HTML, so a WAF,
    # a redesign or a geo-block on www.quebec.ca cannot take the register away.
    # It also reaches FURTHER than the page does: the landing page shows a
    # rolling 13 months, the CDN holds 36.
    built = 0
    for month in wanted:
        if month in by_month or month < EARLIEST_LIVE_MONTH:
            continue
        exc = _MONTH_URL_EXCEPTIONS.get(month)
        by_month[month] = (_CDN_DIR + exc) if exc else (CDN_TEMPLATE % month)
        built += 1
    notes["constructed"] = f"{built} url(s)"

    urls = [by_month[m] for m in sorted(by_month, reverse=True)
            if m <= wanted[0]][:max(1, months_back)]
    return urls, notes


def _parse_pdf(content):
    """Return (rows, declared_notices, declared_jobs) for one monthly PDF."""
    import pdfplumber
    lines = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            lines += (page.extract_text() or "").splitlines()
    out, region = [], ""
    reg_notices = reg_jobs = 0
    grand = None
    for ln in lines:
        gm = _GRAND_TOTAL_RX.search(ln)
        if gm:
            grand = (_num(gm.group("notices")), _num(gm.group("jobs")))
            continue
        tm = _REGION_TOTAL_RX.search(ln)
        if tm:
            # The document's own tally for the region block just ended.
            reg_notices += _num(tm.group("notices"))
            reg_jobs += _num(tm.group("jobs"))
            continue
        rm = re.match(r"^(\d{2}-[A-Za-zÀ-ü].+)$", ln.strip())
        if rm and not re.search(r"\d{4}-\d{2}-\d{2}", ln):
            region = rm.group(1).strip()
        m = _LINE_RX.match(ln) or _LINE_NO_NEQ_RX.match(ln)
        if not m:
            continue
        emp = _clean_emp(m.group("emp"))
        if not _valid_emp(emp):
            continue
        try:
            cnt = int(m.group("count"))
        except ValueError:
            continue
        out.append((emp[:60], m.group("eff"), cnt, region))
    dec_notices, dec_jobs = grand if grand else (reg_notices, reg_jobs)
    return out, dec_notices, dec_jobs


def pull_quebec(months_back=4):
    """Fetch the most recent `months_back` monthly PDFs and parse notices."""
    global _LAST_REPORT
    urls, notes = _discover(months_back)
    _LAST_REPORT = {"routes": notes, "urls": len(urls), "fetched": 0,
                    "parsed": 0, "declared_notices": 0, "declared_jobs": 0,
                    "jobs": 0, "errors": []}
    if not urls:
        # Cannot happen while CDN_TEMPLATE stands, and that is the point: the
        # old code reached here whenever the HTML page changed shape.
        print("Quebec: no candidate PDF URLs from either route")
        return []
    out, seen = [], set()
    for url in urls:
        try:
            resp = requests.get(url, headers=UA, timeout=60)
            if resp.status_code == 404:
                continue          # month not published yet, or older than the archive
            if resp.status_code != 200:
                _LAST_REPORT["errors"].append(f"HTTP {resp.status_code} {url[-24:]}")
                continue
            recs, dec_n, dec_j = _parse_pdf(resp.content)
            _LAST_REPORT["fetched"] += 1
            _LAST_REPORT["declared_notices"] += dec_n
            _LAST_REPORT["declared_jobs"] += dec_j
        except Exception as exc:
            _LAST_REPORT["errors"].append(f"{type(exc).__name__} {url[-24:]}")
            print(f"Quebec PDF failed ({url[-30:]}): {exc}")
            continue
        for emp, eff, cnt, region in recs:
            key = (emp.lower(), eff, cnt)
            if key in seen:
                continue
            seen.add(key)
            e = _entry(emp, cnt, eff, region=region, source_url=url)
            if e:
                out.append(e)
    _LAST_REPORT["parsed"] = len(out)
    _LAST_REPORT["jobs"] = sum(e["job_count"] for e in out)
    dn = _LAST_REPORT["declared_notices"]
    cover = f", {len(out)}/{dn} the documents declare" if dn else ""
    print(f"Quebec: {len(out)} collective-dismissal notices parsed from "
          f"{_LAST_REPORT['fetched']} monthly PDFs{cover} "
          f"(landing: {notes.get('landing')}, constructed: {notes.get('constructed')})")
    return out


def health_detail(kept):
    """One line for the source-health ledger that says what actually happened."""
    r = _LAST_REPORT
    base = "Quebec collective-dismissal notices (MESS)"
    if not r:
        return base
    if not r.get("fetched"):
        return (f"{base} — NO monthly PDF was readable this run "
                f"(landing route: {r['routes'].get('landing')}; "
                f"{r.get('urls', 0)} candidate URL(s) tried). The register itself may be "
                f"fine; this is a fetch/discovery failure, not a parser one.")
    dn = r.get("declared_notices") or 0
    got = r.get("parsed") or 0
    tally = f"{got}/{dn}" if dn else str(got)
    return (f"{base} — {tally} notices, {r.get('jobs', 0):,} jobs from "
            f"{r['fetched']} monthly PDF(s)")


if __name__ == "__main__":
    import sys
    months = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    rows = pull_quebec(months)
    for e in rows:
        print(f"  {e['job_count']:>5}  {e['layoff_date']}  {e['company_name']}")
    print(f"\nreport: {last_run_report()}")
    print(f"health: {health_detail(rows)}")
