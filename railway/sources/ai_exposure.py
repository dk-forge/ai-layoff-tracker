"""AI exposure by occupation and metro: reference data, LABELLED CONTEXT.

WHAT THIS IS
------------
One reference document joined on the 6-digit SOC occupation code from four
free, openly licensed sources:

  * Eloundou, Manning, Mishkin and Rock, "GPTs are GPTs: Labor market impact
    potential of LLMs" (Science, 2024; arXiv 2303.10130, 2023). Occupation
    scores from github.com/openai/GPTs-are-GPTs, data/occ_level.csv, MIT
    licence, read at a PINNED commit so the score cannot change under us.
    We use `dv_rating_beta` (GPT-4 rated; share of a job's tasks an LLM
    system could speed up by half or more, counting tasks that need extra
    software at half weight), the paper's headline measure. O*NET-SOC
    detail codes are averaged up to the 6-digit SOC code.
  * O*NET database (USDOL/ETA, CC BY 4.0): occupation titles for those
    codes, from `Occupation Data.txt` in the current release's text zip.
  * BLS OEWS (public domain): national employment and median annual wage per
    detailed occupation, and employment per occupation in the MAX_METROS
    largest metro areas (MSA file).
  * BLS Employment Projections (public domain): 10-year projected change per
    occupation, Table 1.2 of occupation.xlsx.

IMPORTANT LABELLING
-------------------
Exposure means "tasks an AI system could speed up", per the study. It is not
a forecast of job loss and nothing here touches layoff counts, ingest or
classification.

SHAPE
-----
datasets.occupations       [soc, title, exposure, employment, median_wage, growth_pct]
datasets.metros            [area, title, total_employment, exposed_employment]
datasets.metro_occupations [area, soc, employment]   top MAX_METRO_OCCS exposed jobs per metro
`columns` names them. `threshold` is the exposure at or above which an
occupation counts as highly exposed. median_wage is null when BLS suppresses
it and "#" when it is above the BLS top code.

Parsing is pure and tested offline (rows in, rows out); fetch() needs
openpyxl only for the two BLS spreadsheets.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
import urllib.request
import zipfile
from datetime import date, datetime, timezone

SOURCE = "ai_exposure"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com; info@asktherecruiter.com)"

STUDY_COMMIT = "0471612fef3cc22b74fb884d27bff9dbd3770582"
STUDY_URL = ("https://raw.githubusercontent.com/openai/GPTs-are-GPTs/"
             f"{STUDY_COMMIT}/data/occ_level.csv")
STUDY = {
    "name": "GPTs are GPTs",
    "short": "Eloundou et al. (2024)",
    "citation": ("Eloundou, T., Manning, S., Mishkin, P. and Rock, D. (2024). GPTs are GPTs: "
                 "Labor market impact potential of LLMs. Science 384(6702), 1306-1308. "
                 "Preprint: arXiv:2303.10130 (2023)."),
    "measure": "dv_rating_beta (GPT-4 rated, E1 + 0.5 x E2)",
    "data": "https://github.com/openai/GPTs-are-GPTs",
    "commit": STUDY_COMMIT,
    "licence": "MIT",
}
ONET_PAGE = "https://www.onetcenter.org/database.html"
ONET_ZIP = "https://www.onetcenter.org/dl_files/database/db_{v}_text.zip"
ONET_FALLBACK = "31_0"
OEWS_ZIP = "https://www.bls.gov/oes/special-requests/oesm{yy}{kind}.zip"
EP_XLSX = "https://www.bls.gov/emp/ind-occ-matrix/occupation.xlsx"

#: At or above this exposure an occupation counts as highly exposed: at least
#: half its tasks on the study's beta weighting (about the top quarter).
THRESHOLD = 0.5
MAX_METROS = 50
MAX_METRO_OCCS = 10

LICENCE = ("Mixed open: study data MIT; O*NET CC BY 4.0; BLS OEWS and Employment "
           "Projections public domain")
ATTRIBUTION = (
    "Exposure scores: Eloundou, Manning, Mishkin and Rock, \"GPTs are GPTs\" (Science, 2024), "
    "data from github.com/openai/GPTs-are-GPTs (MIT licence). Occupation titles: O*NET {onet} "
    "Database by the U.S. Department of Labor, Employment and Training Administration "
    "(USDOL/ETA), used under the CC BY 4.0 licence; O*NET is a trademark of USDOL/ETA. "
    "Employment and wages: U.S. Bureau of Labor Statistics, Occupational Employment and Wage "
    "Statistics ({oews}). Projections: U.S. Bureau of Labor Statistics, Employment "
    "Projections ({ep}).")

COLUMNS = {
    "occupations": ["soc", "title", "exposure", "employment", "median_wage", "growth_pct"],
    "metros": ["area", "title", "total_employment", "exposed_employment"],
    "metro_occupations": ["area", "soc", "employment"],
}

SOC_RE = re.compile(r"^\d\d-\d{4}$")


# ---------------------------------------------------------------- parsing

def parse_study(text: str) -> dict:
    """occ_level.csv -> {soc6: mean dv_rating_beta}."""
    acc: dict = {}
    for rec in csv.DictReader(io.StringIO(text)):
        code = (rec.get("O*NET-SOC Code") or "").strip()
        try:
            v = float(rec.get("dv_rating_beta") or "")
        except ValueError:
            continue
        if not SOC_RE.match(code[:7]) or not 0 <= v <= 1:
            continue
        acc.setdefault(code[:7], []).append(v)
    return {k: round(statistics.mean(v), 4) for k, v in acc.items()}


def parse_onet(text: str) -> dict:
    """Occupation Data.txt (tab-separated) -> {soc6: title of its .00 code}."""
    out, other = {}, {}
    for line in text.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 2 or not SOC_RE.match(parts[0][:7]):
            continue
        (out if parts[0].endswith(".00") else other).setdefault(parts[0][:7], parts[1].strip())
    for k, v in other.items():
        out.setdefault(k, v)
    return out


def onet_version(html: str) -> str:
    found = re.findall(r"db_(\d+)_(\d+)_(?:text|excel)", html or "")
    if not found:
        return ONET_FALLBACK
    a, b = max((int(x), int(y)) for x, y in found)
    return f"{a}_{b}"


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip().replace(",", "")
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _wage(v):
    if isinstance(v, str) and v.strip() == "#":
        return "#"
    n = _num(v)
    return int(n) if n is not None else None


def _header(rows):
    it = iter(rows)
    for r in it:
        if r and "OCC_CODE" in r:
            return {str(h): i for i, h in enumerate(r) if h is not None}, it
    raise RuntimeError("OEWS sheet has no OCC_CODE header")


def parse_oews_national(rows) -> dict:
    """national_M<year>_dl rows -> {soc: (employment, median annual wage, BLS title)}, detailed only."""
    ix, it = _header(rows)
    out = {}
    for r in it:
        if str(r[ix["O_GROUP"]]).strip() != "detailed":
            continue
        if "NAICS" in ix and str(r[ix["NAICS"]]).strip() not in ("000000", "0"):
            continue
        soc = str(r[ix["OCC_CODE"]]).strip()
        emp = _num(r[ix["TOT_EMP"]])
        if SOC_RE.match(soc) and emp:
            out[soc] = (int(emp), _wage(r[ix["A_MEDIAN"]]), str(r[ix["OCC_TITLE"]] or "").strip())
    return out


def parse_oews_metros(rows) -> dict:
    """MSA_M<year>_dl rows -> {area: {"title", "total", "occ": {soc: emp}}}."""
    ix, it = _header(rows)
    out: dict = {}
    for r in it:
        area = str(r[ix["AREA"]]).strip()
        grp = str(r[ix["O_GROUP"]]).strip()
        if grp not in ("total", "detailed"):
            continue
        m = out.setdefault(area, {"title": str(r[ix["AREA_TITLE"]]).strip(), "total": None, "occ": {}})
        emp = _num(r[ix["TOT_EMP"]])
        if grp == "total":
            m["total"] = int(emp) if emp else None
        elif emp:
            m["occ"][str(r[ix["OCC_CODE"]]).strip()] = int(emp)
    return out


def parse_ep(rows) -> tuple:
    """Table 1.2 rows -> ({soc: percent change}, "2025-35")."""
    it = iter(rows)
    span, ix = None, None
    for r in it:
        cells = [str(c) if c is not None else "" for c in r]
        if any(c.startswith("Employment change, percent") for c in cells):
            ix = {c: i for i, c in enumerate(cells)}
            pct = next(i for i, c in enumerate(cells) if c.startswith("Employment change, percent"))
            m = re.search(r"(\d{4})\D+(\d{2,4})$", cells[pct])
            span = f"{m.group(1)}-{m.group(2)[-2:]}" if m else None
            break
    if ix is None:
        raise RuntimeError("Employment Projections table has no percent-change header")
    code = next(i for c, i in ix.items() if c.endswith("Matrix code"))
    typ = ix.get("Occupation type")
    out = {}
    for r in it:
        if len(r) <= pct:
            continue
        soc = str(r[code] or "").strip()
        if typ is not None and str(r[typ]).strip() != "Line item":
            continue
        v = _num(r[pct])
        if SOC_RE.match(soc) and v is not None:
            out[soc] = round(float(v), 1)
    return out, span


# ---------------------------------------------------------------- joining

def build_payload(scores, titles, national, metros, growth, versions, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    occ = []
    for soc, rec in sorted(national.items()):
        if soc not in scores:
            continue
        emp, wage = rec[0], rec[1]
        title = titles.get(soc) or (rec[2] if len(rec) > 2 else "") or soc
        occ.append([soc, title, scores[soc], emp, wage, growth.get(soc)])
    exposed = {r[0] for r in occ if r[2] >= THRESHOLD}
    biggest = sorted((a for a, m in metros.items() if m.get("total")),
                     key=lambda a: -metros[a]["total"])[:MAX_METROS]
    mrows, morows = [], []
    for a in biggest:
        m = metros[a]
        hits = sorted(((s, e) for s, e in m["occ"].items() if s in exposed), key=lambda x: -x[1])
        mrows.append([a, m["title"], m["total"], sum(e for _, e in hits)])
        morows.extend([a, s, e] for s, e in hits[:MAX_METRO_OCCS])
    oews_year = versions.get("oews_year")
    ep_span = versions.get("ep") or ""
    onet = versions.get("onet", ONET_FALLBACK).replace("_", ".")
    latest = {}
    if oews_year:
        latest["oews"] = f"{oews_year}-05"
    if ep_span[:4].isdigit():
        latest["ep"] = f"{ep_span[:4]}-12"
    return {
        "source": SOURCE,
        "updated": now.isoformat(),
        "licence": LICENCE,
        "attribution": ATTRIBUTION.format(onet=onet, oews=f"May {oews_year}", ep=ep_span),
        "url": STUDY["data"],
        "label": ("Context: exposure means tasks an AI system could speed up, per the study. "
                  "It is not a forecast of job loss and is never part of tracker counts."),
        "study": STUDY,
        "versions": {"onet": onet, "oews": f"May {oews_year}", "ep": ep_span},
        "threshold": THRESHOLD,
        "latest": latest,
        "columns": COLUMNS,
        "rows": len(occ) + len(mrows) + len(morows),
        "datasets": {"occupations": occ, "metros": mrows, "metro_occupations": morows},
    }


# ---------------------------------------------------------------- network

def _get(url: str, opener=None, timeout=180) -> bytes:
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with opener(req, timeout=timeout) as resp:
        return resp.read()


def _xlsx_rows(body: bytes, sheet_prefix=None):
    import openpyxl  # full lock only; the parsers above take plain rows
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    if sheet_prefix:
        ws = next(w for w in wb.worksheets if w.title.startswith(sheet_prefix))
    return list(ws.iter_rows(values_only=True))


def _zip_member(body: bytes, suffix: str) -> bytes:
    z = zipfile.ZipFile(io.BytesIO(body))
    name = next(n for n in z.namelist() if n.endswith(suffix))
    return z.read(name)


def pull(opener=None, today=None) -> dict:
    """Fetch all four sources and return {"payload": ..., "errors": [...]}."""
    today = today or date.today()
    errors, versions = [], {}
    scores = titles = national = metros = growth = {}
    try:
        scores = parse_study(_get(STUDY_URL, opener).decode("utf-8", "replace"))
    except Exception as exc:
        errors.append(f"study: {str(exc)[:200]}")
    try:
        try:
            v = onet_version(_get(ONET_PAGE, opener).decode("utf-8", "replace"))
        except Exception:
            v = ONET_FALLBACK
        versions["onet"] = v
        titles = parse_onet(_zip_member(_get(ONET_ZIP.format(v=v), opener),
                                        "/Occupation Data.txt").decode("utf-8", "replace"))
    except Exception as exc:
        errors.append(f"onet: {str(exc)[:200]}")
    for year in (today.year, today.year - 1, today.year - 2):
        try:
            nat = _get(OEWS_ZIP.format(yy=f"{year % 100:02d}", kind="nat"), opener)
        except Exception:
            continue
        try:
            national = parse_oews_national(_xlsx_rows(_zip_member(nat, f"_M{year}_dl.xlsx")))
            ma = _get(OEWS_ZIP.format(yy=f"{year % 100:02d}", kind="ma"), opener)
            metros = parse_oews_metros(_xlsx_rows(_zip_member(ma, f"MSA_M{year}_dl.xlsx")))
            versions["oews_year"] = year
        except Exception as exc:
            errors.append(f"oews {year}: {str(exc)[:200]}")
        break
    else:
        errors.append("oews: no release found for the last three years")
    try:
        growth, versions["ep"] = parse_ep(_xlsx_rows(_get(EP_XLSX, opener), "Table 1.2"))
    except Exception as exc:
        errors.append(f"ep: {str(exc)[:200]}")
    payload = build_payload(scores, titles, national, metros, growth, versions)
    return {"payload": payload, "errors": errors,
            "counts": {"scores": len(scores), "titles": len(titles), "national": len(national),
                       "metros": len(metros), "growth": len(growth)}}
