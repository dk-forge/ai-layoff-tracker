"""Quebec collective-dismissal notices (avis de licenciements collectifs).

Quebec's Ministere de l'Emploi et de la Solidarite sociale (MESS) publishes a
monthly PDF of collective-dismissal notices employers must file under the Act
respecting labour standards. This is Canada's closest analog to a US WARN
notice: a legal advance notice of a mass layoff, with employer, headcount and
effective date. We parse the monthly PDFs and route them through the same
structured /bulk path as WARN (no LLM).

Source: https://www.quebec.ca/gouvernement/ministeres-organismes/emploi-solidarite-sociale/publications
PDFs:   https://cdn-contenu.quebec.ca/.../avis_licenciements_collectifs/LI_licenciement-collectif_YYYY-MM_MESS.pdf

Parser note: the PDF is a multi-column, glyph-positioned layout. Each notice's
core (employer, NEQ business number, address, notice date, effective date,
headcount) lands on one physical line; the reason/activity columns wrap. We
parse per line and keep ONLY rows whose employer is clearly valid, dropping a
wrapped row rather than posting a garbled company name (documented-floor rule).
"""
import hashlib
import io
import re

import requests

PUBLICATIONS_URL = ("https://www.quebec.ca/gouvernement/ministeres-organismes/"
                    "emploi-solidarite-sociale/publications")
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
TIMEOUT = 30

# One notice per line: <employer> <NEQ(10 digits)> <address...> <notice date>
# <effective date> <headcount>. Non-greedy up to the first ISO date pair.
_LINE_RX = re.compile(
    r"^(?P<emp>.+?)\s+\d{10}\s+.*?"
    r"(?P<notice>\d{4}-\d{2}-\d{2})\s+(?P<eff>\d{4}-\d{2}-\d{2})\s+(?P<count>\d{1,5})\b")


def _clean_emp(e):
    e = re.sub(r"\s+", " ", e or "").strip()
    e = re.sub(r"^\d{2}-[A-Za-zÀ-ü\-' ]+?\s{2,}", "", e)   # strip a leading region label
    return e.strip(" -,")


def _valid_emp(e):
    """Reject wrap fragments so a garbled row is dropped, never posted."""
    if len(e) < 3 or len(e) > 70:
        return False
    if re.search(r"\d{4}-\d{2}", e):          # a date leaked into the name
        return False
    if not re.match(r"[A-Za-zÀ-ü0-9]", e):
        return False
    if e[0].islower():                        # continuation fragment ("mentale")
        return False
    if re.match(r"^\d", e) and not re.match(r"^\d{3,4}\s", e):
        return False
    return True


def _entry(company, jobs, date, region="", reason=""):
    company = (company or "").strip()
    if not company or jobs <= 0 or jobs > 100000 or not date:
        return None
    if date < "2015-01-01" or date > "2028-12-31":
        return None
    loc = f" ({region})" if region else ""
    is_closure = "fermeture" in (reason or "").lower()
    excerpt = (f"{'Closure' if is_closure else 'Collective dismissal'} at "
               f"{company}{loc}, Quebec. {jobs:,} employees affected, effective "
               f"{date}. Filed under Quebec's collective-dismissal notice rules (MESS).")
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
        "source_url": PUBLICATIONS_URL,
        "dedup_hash": hashlib.md5(hash_input.encode("utf-8")).hexdigest(),
        "is_layoff_event": True,
    }


def _parse_pdf(content):
    import pdfplumber
    lines = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            lines += (page.extract_text() or "").splitlines()
    out, region = [], ""
    for ln in lines:
        rm = re.match(r"^(\d{2}-[A-Za-zÀ-ü].+)$", ln.strip())
        if rm and not re.search(r"\d{4}-\d{2}-\d{2}", ln):
            region = rm.group(1).strip()
        m = _LINE_RX.match(ln)
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
    return out


def pull_quebec(months_back=4):
    """Fetch the most recent `months_back` monthly PDFs and parse notices."""
    try:
        page = requests.get(PUBLICATIONS_URL, headers=UA, timeout=TIMEOUT).text
    except Exception as e:
        print(f"Quebec landing fetch failed: {e}")
        return []
    urls = re.findall(
        r'https://cdn-contenu\.quebec\.ca/[^"]+/avis_licenciements_collectifs/'
        r'LI_licenciement-collectif_\d{4}-\d{2}_MESS\.pdf', page)
    urls = list(dict.fromkeys(urls))[:max(1, months_back)]
    if not urls:
        print("Quebec: no monthly PDF links found (page structure changed?)")
        return []
    out, seen = [], set()
    for url in urls:
        try:
            content = requests.get(url, headers=UA, timeout=60).content
            recs = _parse_pdf(content)
        except Exception as e:
            print(f"Quebec PDF failed ({url[-30:]}): {e}")
            continue
        for emp, eff, cnt, region in recs:
            key = (emp.lower(), eff, cnt)
            if key in seen:
                continue
            seen.add(key)
            e = _entry(emp, cnt, eff, region=region)
            if e:
                out.append(e)
    print(f"Quebec: {len(out)} collective-dismissal notices parsed from {len(urls)} monthly PDFs")
    return out


if __name__ == "__main__":
    for e in pull_quebec(2):
        print(f"  {e['job_count']:>5}  {e['layoff_date']}  {e['company_name']}")
