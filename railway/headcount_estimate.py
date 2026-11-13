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

Owner ruling 2026-11-13 ("yes extend estimates to news, labelled"): a NEWS
item that states a share of the total workforce and no count takes the same
estimate, with two extra conditions because a headline names a company and not
a filing: the company must resolve to exactly ONE SEC registrant (the name is
normalised and matched against SEC's company_tickers.json; ambiguous or absent
is no estimate), and the report's own sentence is kept verbatim as "Report
states". A share of a QUALIFIED workforce (salaried, corporate, one division)
is never applied to total headcount.
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
    r"(?:employees|persons|people|team\s+members|associates)", re.I)

COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def _filer_word(company):
    """The first word of the filer's own name, lowercased ("Workday, Inc." ->
    "workday"), or None. Only THIS word may own the workforce in a
    possessive: "2.5% of Workday's current workforce" is the filer's own
    share, "10% of Acme's workforce" is not."""
    m = re.match(r"\s*([A-Za-z0-9&]+)", str(company or ""))
    return m.group(1).lower() if m and len(m.group(1)) >= 3 else None


def _rxs(company):
    rxs = [_PCT_OF, _BY_PCT]
    word = _filer_word(company)
    if word:
        own = r"(?:" + re.escape(word) + r"(?:\s+[A-Za-z0-9&.,]+){0,3}?['\u2019]s\s+)"
        rxs.append(re.compile(PCT + r"\s+of\s+" + own + WORKFORCE, re.I))
        rxs.append(re.compile(
            r"\b(?:reduc\w*|cut\w*|eliminat\w*|decreas\w*|affect\w*)\s+" + own
            + WORKFORCE + r"\s+by\s+(?:approximately\s+|about\s+|roughly\s+|"
            r"around\s+|nearly\s+|up\s+to\s+)?" + PCT, re.I))
    return rxs


def workforce_percent(text, company=None):
    """(percent, matched sentence text) for a workforce share, else None.

    `company` (the filer's name) additionally admits the filer's own
    possessive ("of Workday's current workforce"); without it only
    its/our/the company's/the are read as the owner."""
    text = str(text or "")
    for rx in _rxs(company):
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


#: A 10-K runs 2 MB+ of HTML; the human-capital sentence sits deep inside it.
_TEN_K_MAX_BYTES = 3_000_000


def _fetch_text(url):
    """The WHOLE stripped document, not the 8-K keyword window.

    `edgar._fetch_filing_text` returns ~3,000 characters centred on the first
    layoff keyword, which is right for an 8-K and useless here: a filer with no
    dei:EntityNumberOfEmployees tag (FICO) states its headcount in a sentence
    hundreds of thousands of characters in, so the fallback never saw it and
    every percent-only 8-K from such a filer was refused.
    """
    from sources import edgar
    resp = edgar._get(url)
    resp.raise_for_status()
    return edgar._strip_html(resp.text[:_TEN_K_MAX_BYTES])


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


#: Why the LAST estimate_for_filing call returned None, for one log line.
LAST_REFUSAL = [None]
#: Why the LAST cik_for_company call found nothing (None when it found one).
LAST_INDEX_STATE = [None]


def _refuse(why):
    LAST_REFUSAL[0] = why
    return None


_NAME_SUFFIX = {"inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
                "limited", "plc", "llc", "lp", "holdings", "holding", "group", "sa",
                "nv", "ag", "de", "new"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_INDEX = {}


def _norm_name(name):
    """"The Trade Desk, Inc." -> "trade desk"; "CAMPBELL'S CO" -> "campbells"."""
    t = re.sub(r"[\u2019']", "", str(name or "").lower().replace("&", " and "))
    toks = re.sub(r"[^a-z0-9]+", " ", t).split()
    if toks and toks[0] == "the":
        toks = toks[1:]
    while toks and toks[-1] in _NAME_SUFFIX:
        toks.pop()
    return " ".join(toks)


def cik_for_company(name, fetch_json=None):
    """The CIK of the ONE SEC registrant whose normalised name equals `name`'s,
    else None. Share classes of one registrant count as one; two registrants
    with the same normalised name are ambiguous and give None, never a guess.
    LAST_INDEX_STATE says which of the three ways it found nothing."""
    LAST_INDEX_STATE[0] = None
    key = _norm_name(name)
    if not key:
        LAST_INDEX_STATE[0] = "no company name"
        return None
    index = _INDEX.get("map") if fetch_json is None else None
    if index is None:
        try:
            raw = (fetch_json or _fetch_json)(TICKERS_URL) or {}
            index = {}
            for rec in (raw.values() if isinstance(raw, dict) else raw):
                index.setdefault(_norm_name(rec.get("title")), set()).add(str(int(rec["cik_str"])))
        except Exception:
            LAST_INDEX_STATE[0] = "SEC company index unreadable"
            return None
        if not index:
            LAST_INDEX_STATE[0] = "SEC company index unreadable"
            return None                      # an unreadable index is never cached
        if fetch_json is None:
            _INDEX["map"] = index
    ciks = index.get(key, set())
    if len(ciks) == 1:
        return next(iter(ciks))
    LAST_INDEX_STATE[0] = ("no SEC registrant has that name" if not ciks
                           else "several SEC registrants share that name")
    return None


def default_cik_finder(name):
    return cik_for_company(name)


def default_lookup(cik):
    return sec_lookup(cik)


def estimate_for_filing(raw_entry, raw_text, lookup=None, company=None, cik_finder=None):
    """The labelled estimate for a percent-only 8-K or news item, or None."""
    LAST_REFUSAL[0] = None
    stype = str(raw_entry.get("source_type") or "")
    is_news = stype == "news"
    if stype.upper() != "8K" and not is_news:
        return _refuse("source type is not an 8-K or news")
    from filing_shapes import RISK_FACTORS_SECTION
    if raw_entry.get("sec_section") == RISK_FACTORS_SECTION:
        return _refuse("the share sits in a risk-factors section")
    name = company or raw_entry.get("company_name")
    if is_news:
        word = _filer_word(name)
        if not word or word not in str(raw_text or "").lower():
            return _refuse("the company name is not in the text")
    found = workforce_percent(raw_text, company=name)
    if not found:
        return _refuse("no share of the total workforce is stated")
    pct, sentence = found
    if is_news:
        cik = (cik_finder or default_cik_finder)(name)
    else:
        cik = cik_from_url(raw_entry.get("source_url"))
    if not cik:
        return _refuse("no single SEC registrant matches the company name"
                       + (f" ({LAST_INDEX_STATE[0]})" if is_news and LAST_INDEX_STATE[0] else ""))
    facts = (lookup or default_lookup)(cik)
    if not facts or not facts.get("employees"):
        return _refuse("no 10-K employee count could be read for it")
    employees = int(facts["employees"])
    n = int(round(pct * employees / 100.0))
    if n <= 0:
        return _refuse("the estimate rounds to zero")
    pct_s = f"{pct:g}%"
    fy = facts.get("fiscal_year_end") or "latest"
    source = (f"{facts.get('form') or '10-K'} for fiscal year ended {fy}, "
              f"{facts.get('basis')}, accession {facts.get('accession')}")
    return {
        "label": "estimate",
        "origin": "news" if is_news else "filing",
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
            f"{'Report' if estimate.get('origin') == 'news' else 'Filing'} states: \"{estimate['reported_text']}\"")
    return head if not excerpt or excerpt == estimate["reported_text"] else f"{head} {excerpt}"
