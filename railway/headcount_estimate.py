"""Labelled headcount ESTIMATES for percent-only 8-K filings.

Owner ruling 2026-11-05 ("yes estimates", docs/DECISIONS.md): most Item 2.05
8-Ks state only a share of the workforce (FICO ~15%, HubSpot ~7%) and the
extractor refuses a percentage as a count by design. For those filings the row
carries

    estimate = reported percent x employees the company reported in its latest
               10-K (SEC XBRL dei:EntityNumberOfEmployees, else the 10-K's own
               "we had approximately N employees" sentence)

clearly labelled "estimate", with the formula and the 10-K it came from, and
the filing's own reported figure (the percentage sentence) kept verbatim
beside it. Nothing here guesses: no percentage in workforce context, or no
reported employee count, means no estimate and the filing stays refused.

All reads are SEC's free, keyless endpoints (data.sec.gov), cached per process
and per CIK, so a run that sees ten filings from one filer reads its facts
once. No model call.
"""
import re

PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s?(?:%|percent\b|per\s+cent\b)"
WORKFORCE = (r"(?:(?:global|total|overall|worldwide|current|full-time)\s+)?"
             r"(?:workforce|employees|employee\s+base|headcount|staff|positions)")
_OWNER = r"(?:(?:its|our|the\s+company'?s|the\s+company’s|the)\s+)?"
_PCT_OF = re.compile(PCT + r"\s+of\s+" + _OWNER + WORKFORCE, re.I)
_BY_PCT = re.compile(
    r"\b(?:reduc\w*|cut\w*|eliminat\w*|decreas\w*|affect\w*)\s+" + _OWNER
    + WORKFORCE + r"\s+by\s+(?:approximately\s+|about\s+|roughly\s+|around\s+|"
    r"nearly\s+|up\s+to\s+)?" + PCT, re.I)

_CIK_IN_URL = re.compile(r"/Archives/edgar/data/(\d{1,10})/", re.I)
_EMPLOYEES_SENTENCE = re.compile(
    r"\b(?:we|the\s+company)\s+(?:had|employed|have|employ)\s+(?:a\s+total\s+of\s+)?"
    r"(?:approximately\s+|about\s+|roughly\s+|around\s+|over\s+|more\s+than\s+)?"
    r"(\d{1,3}(?:,\d{3})+|\d{3,7})\s+(?:full[- ]time\s+|total\s+|global\s+)?"
    r"(?:employees|people|team\s+members|associates)", re.I)

COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def workforce_percent(text):
    """(percent, matched sentence text) for a workforce share, else None."""
    text = str(text or "")
    for rx in (_PCT_OF, _BY_PCT):
        m = rx.search(text)
        if m:
            pct = float(m.group(1))
            if 0 < pct < 100:
                start = max(text.rfind(".", 0, m.start()) + 1, 0)
                end = text.find(".", m.end())
                return pct, text[start:end + 1 if end != -1 else len(text)].strip()
    return None


def cik_from_url(url):
    m = _CIK_IN_URL.search(str(url or ""))
    return str(int(m.group(1))) if m else None


def employees_from_companyfacts(facts):
    """The latest 10-K dei:EntityNumberOfEmployees fact, or None. Pure."""
    try:
        units = facts["facts"]["dei"]["EntityNumberOfEmployees"]["units"]
    except (KeyError, TypeError):
        return None
    best = None
    for vals in (units or {}).values():
        for v in vals or ():
            if not str(v.get("form", "")).startswith("10-K"):
                continue
            try:
                n = int(v.get("val"))
            except (TypeError, ValueError):
                continue
            if n <= 0:
                continue
            key = (str(v.get("filed", "")), str(v.get("end", "")))
            if best is None or key > best[0]:
                best = (key, {"employees": n, "fiscal_year_end": v.get("end"),
                              "form": v.get("form"), "accession": v.get("accn"),
                              "basis": "dei:EntityNumberOfEmployees"})
    return best[1] if best else None


def employees_from_10k_text(text):
    """N from "we had approximately N employees" in a 10-K body, else None."""
    m = _EMPLOYEES_SENTENCE.search(str(text or ""))
    if not m:
        return None
    n = int(m.group(1).replace(",", ""))
    return n if n >= 10 else None


_CACHE = {}


def _fetch_json(url):
    from sources import edgar
    r = edgar._get(url)
    return r.json() if getattr(r, "status_code", 0) == 200 else None


def _fetch_text(url):
    from sources import edgar
    return edgar._fetch_filing_text(url)


def sec_lookup(cik, fetch_json=None, fetch_text=None):
    """Latest 10-K employee count for a CIK from SEC's free endpoints. Cached."""
    if cik in _CACHE:
        return _CACHE[cik]
    fetch_json = fetch_json or _fetch_json
    fetch_text = fetch_text or _fetch_text
    out = None
    try:
        out = employees_from_companyfacts(fetch_json(COMPANYFACTS.format(cik=cik)))
    except Exception:
        out = None
    if out:
        out["source_url"] = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                             f"&CIK={cik}&type=10-K")
    else:
        try:
            sub = fetch_json(SUBMISSIONS.format(cik=cik)) or {}
            recent = sub.get("filings", {}).get("recent", {})
            for i, form in enumerate(recent.get("form", [])):
                if form != "10-K":
                    continue
                acc = recent["accessionNumber"][i]
                url = ARCHIVE.format(cik=cik, acc=acc.replace("-", ""),
                                     doc=recent["primaryDocument"][i])
                n = employees_from_10k_text(fetch_text(url))
                if n:
                    out = {"employees": n, "fiscal_year_end": recent["reportDate"][i],
                           "form": "10-K", "accession": acc, "source_url": url,
                           "basis": "10-K human capital text"}
                break
        except Exception:
            out = None
    _CACHE[cik] = out
    return out


def default_lookup(cik):
    return sec_lookup(cik)


def estimate_for_filing(raw_entry, raw_text, lookup=None):
    """The labelled estimate for a percent-only 8-K, or None."""
    if str(raw_entry.get("source_type") or "").upper() != "8K":
        return None
    from filing_shapes import RISK_FACTORS_SECTION
    if raw_entry.get("sec_section") == RISK_FACTORS_SECTION:
        return None
    found = workforce_percent(raw_text)
    if not found:
        return None
    pct, sentence = found
    cik = cik_from_url(raw_entry.get("source_url"))
    if not cik:
        return None
    facts = (lookup or default_lookup)(cik)
    if not facts or not facts.get("employees"):
        return None
    employees = int(facts["employees"])
    n = int(round(pct * employees / 100.0))
    if n <= 0:
        return None
    pct_s = f"{pct:g}%"
    fy = facts.get("fiscal_year_end") or "latest"
    source = (f"{facts.get('form') or '10-K'} for fiscal year ended {fy}, "
              f"{facts.get('basis')}, accession {facts.get('accession')}")
    return {
        "label": "estimate",
        "job_count": n,
        "reported_percent": pct,
        "reported_text": sentence,
        "employees": employees,
        "formula": f"{pct_s} x {employees:,} employees = {n:,} (rounded)",
        "source": source,
        "source_url": facts.get("source_url"),
    }


def label_excerpt(estimate, excerpt=None):
    """The excerpt a reader sees: the label and formula, then the filing's words."""
    head = (f"Estimate: {estimate['formula']}. Employees from {estimate['source']}. "
            f"Filing states: \"{estimate['reported_text']}\"")
    return head if not excerpt or excerpt == estimate["reported_text"] else f"{head} {excerpt}"
