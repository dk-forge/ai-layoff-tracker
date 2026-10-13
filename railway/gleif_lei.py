#!/usr/bin/env python3
"""Attach GLEIF Legal Entity Identifiers to employers on SEC 8-K and news rows.

    WP_SITE_URL=https://asktherecruiter.com/blog python3 railway/gleif_lei.py          # dry run
    WP_SITE_URL=... python3 railway/gleif_lei.py --write   # rewrite plugin data/company_lei.json
    ... --golden gc.csv.zip                                # local golden copy, no download

READ-ONLY ON THE SITE. It reads the public /query (no key) and never POSTs.
No model, no paid API: the GLEIF golden copy is CC0 1.0 (licence confirmed on
gleif.org 2026-10-13) and needs no account.

WARN IS EXCLUDED BY DESIGN. A read-only probe (2026-10-13) found WARN rows are
mostly local employers and subsidiaries whose notice names a site operator,
so only rows whose `source_type` is `8K` or `news` are read.

THE MATCH RULE. An employer name gets an LEI only when
  1. it normalises (case, accents, punctuation, trailing legal forms) to the
     same string as a GLEIF legal name or other name,
  2. the GLEIF legal-address country equals the row's ONE country
     (employer_country, the domicile, where set, else country), and
  3. exactly ONE active LEI answers. Ambiguous gets nothing.
Country is required because the probe matched "Hook Media, Inc." (US) to
"HÖÖK media AB" (Sweden). A wrong identifier is worse than none.

WHERE IT GOES. `wordpress-plugin/ai-layoff-tracker/data/company_lei.json`,
keyed by the exact `company_name` string, read by includes/company-lei.php on
the company page. Not the database: an LEI is a fact about an employer, not a
layoff, and no row is touched.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LATEST_API = "https://goldencopy.gleif.org/api/v2/golden-copies/publishes/latest"
OUT = (Path(__file__).resolve().parent.parent / "wordpress-plugin" / "ai-layoff-tracker"
       / "data" / "company_lei.json")
UA = {"User-Agent": "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"}
PAGE_SIZE = 200

#: Only these row sources are matched. Never WARN (see the docstring).
SOURCE_TYPES = ("8K", "news")

LIVE_REGISTRATION = {"ISSUED", "LAPSED", "PENDING_TRANSFER", "PENDING_ARCHIVAL"}

#: The tracker stores country NAMES (alt_normalize_country). Anything not here
#: has no ISO code, and an employer with no code gets no LEI.
COUNTRY_ISO2 = {
    "Afghanistan": "AF", "Argentina": "AR", "Australia": "AU", "Austria": "AT",
    "Bangladesh": "BD", "Belgium": "BE", "Bermuda": "BM", "Bosnia and Herzegovina": "BA",
    "Botswana": "BW", "Brazil": "BR", "Bulgaria": "BG", "Cambodia": "KH", "Canada": "CA",
    "Cayman Islands": "KY", "Chile": "CL", "China": "CN", "Colombia": "CO",
    "Costa Rica": "CR", "Croatia": "HR", "Cyprus": "CY", "Czechia": "CZ",
    "Czech Republic": "CZ", "Denmark": "DK", "Egypt": "EG", "Estonia": "EE",
    "Finland": "FI", "France": "FR", "Germany": "DE", "Ghana": "GH", "Greece": "GR",
    "Hong Kong": "HK", "Hungary": "HU", "Iceland": "IS", "India": "IN",
    "Indonesia": "ID", "Ireland": "IE", "Isle of Man": "IM", "Israel": "IL",
    "Italy": "IT", "Jamaica": "JM", "Japan": "JP", "Jersey": "JE", "Kenya": "KE",
    "Kuwait": "KW", "Latvia": "LV", "Lithuania": "LT", "Luxembourg": "LU",
    "Malaysia": "MY", "Malta": "MT", "Mauritius": "MU", "Mexico": "MX",
    "Morocco": "MA", "Netherlands": "NL", "New Zealand": "NZ", "Nigeria": "NG",
    "Norway": "NO", "Pakistan": "PK", "Palestine": "PS", "Paraguay": "PY",
    "Peru": "PE", "Philippines": "PH", "Poland": "PL", "Portugal": "PT",
    "Qatar": "QA", "Romania": "RO", "Saudi Arabia": "SA", "Serbia": "RS",
    "Singapore": "SG", "Slovakia": "SK", "Slovenia": "SI", "South Africa": "ZA",
    "South Korea": "KR", "Spain": "ES", "Sri Lanka": "LK", "Sweden": "SE",
    "Switzerland": "CH", "Taiwan": "TW", "Thailand": "TH", "Türkiye": "TR",
    "Turkey": "TR", "Ukraine": "UA", "United Arab Emirates": "AE",
    "United Kingdom": "GB", "United States": "US", "Uruguay": "UY", "Vietnam": "VN",
    "Zimbabwe": "ZW",
}

# Trailing legal-form tokens only. Descriptive words ("holdings", "group")
# stay: they are how two different entities are told apart.
LEGAL_SUFFIXES = frozenset("""
inc incorporated corp corporation co company ltd limited llc llp lp plc pllc
gmbh ag kg mbh ug se sa sas sarl de cv nv bv ab as asa oy oyj aps spa srl
sl sll kk pte pty bhd sdn tbk pt jsc pjsc ojsc oao zao ooo sro spol kft zrt
lda ltda eirl cia sociedad anonima aktiengesellschaft
""".split())
_PUNCT = re.compile(r"[^\w\s]")
_SPACE = re.compile(r"\s+")
_LEI_RX = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def normalise_name(name):
    """Case, accents, punctuation and trailing legal forms removed."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).casefold()
    s = s.replace("&", " and ").replace(".", "")
    s = _PUNCT.sub(" ", s.replace("_", " "))
    words = _SPACE.sub(" ", s).strip().split(" ")
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    while words and words[-1] == "and":
        words.pop()
        while words and words[-1] in LEGAL_SUFFIXES:
            words.pop()
    if words and words[0] == "the":
        words = words[1:]
    return " ".join(w for w in words if w)


def row_country(row):
    """ISO2 of the employer's domicile, else the job location, else ''."""
    for field in ("employer_country", "country"):
        code = COUNTRY_ISO2.get(str(row.get(field) or "").strip())
        if code:
            return code
    return ""


def employers_from_rows(rows):
    """company_name -> set of ISO2 countries, from 8-K and news rows only."""
    out = {}
    for row in rows:
        if str(row.get("source_type") or "") not in SOURCE_TYPES:
            continue
        name = str(row.get("company_name") or "").strip()
        if not name:
            continue
        cc = row_country(row)
        out.setdefault(name, set()).update([cc] if cc else [])
    return out


def match_all(employers, records):
    """company_name -> LEI, on a unique normalised-name + country match only."""
    wanted = {}
    for name, countries in employers.items():
        norm = normalise_name(name)
        if norm and len(countries) == 1:
            wanted[name] = (norm, next(iter(countries)))
    keys = set(wanted.values())
    hits = {}
    for code, names, country in records:
        for n in names:
            k = (normalise_name(n), (country or "").upper())
            if k in keys:
                hits.setdefault(k, set()).add(code)
    out = {}
    for name, key in wanted.items():
        found = hits.get(key, set())
        if len(found) == 1:
            out[name] = next(iter(found))
    return out


_NAME_COLUMNS = (["Entity.LegalName"]
                 + [f"Entity.OtherEntityNames.OtherEntityName.{i}" for i in range(1, 6)]
                 + [f"Entity.TransliteratedOtherEntityNames.TransliteratedOtherEntityName.{i}"
                    for i in range(1, 6)])


def iter_golden_copy(zip_path):
    """Yield (lei, [names], country) for every live, ACTIVE record."""
    with zipfile.ZipFile(zip_path) as z:
        member = next(n for n in z.namelist() if n.endswith(".csv"))
        with z.open(member) as raw:
            for r in csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline="")):
                if r.get("Entity.EntityStatus") != "ACTIVE":
                    continue
                if r.get("Registration.RegistrationStatus") not in LIVE_REGISTRATION:
                    continue
                if not _LEI_RX.match(r.get("LEI") or ""):
                    continue
                yield (r["LEI"], [r[c] for c in _NAME_COLUMNS if r.get(c)],
                       r.get("Entity.LegalAddress.Country") or "")


def write_output(path, matches, golden_date):
    doc = {
        "source": {
            "name": "GLEIF Golden Copy (LEI-CDF)",
            "url": "https://www.gleif.org/en/lei-data/gleif-golden-copy",
            "licence": "CC0 1.0",
            "golden_copy": golden_date,
            "rows": "SEC 8-K and news only, never WARN",
            "rule": "unique normalised name and matching legal-address country",
        },
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "companies": dict(sorted(matches.items())),
    }
    Path(path).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_rows(site):
    """Every 8-K and news row from the public /query. Read-only, no key."""
    import host_call
    rows, page = [], 1
    while True:
        payload = host_call.get_json(
            site + "/wp-json/layoffs/v1/query",
            params={"per_page": PAGE_SIZE, "page": page, "sources": ",".join(SOURCE_TYPES),
                    "sort": "layoff_date", "dir": "desc"},
            headers=UA, timeout=60)
        data = payload.get("data", [])
        rows.extend(data)
        if len(data) < PAGE_SIZE:
            return rows
        page += 1


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def download_latest(dest_dir):
    meta = json.loads(_get(LATEST_API))["data"]
    url = meta["lei2"]["full_file"]["csv"]["url"]
    dest = Path(dest_dir) / "golden-copy.csv.zip"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=600) as resp, open(dest, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    return dest, meta["publish_date"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="rewrite company_lei.json")
    ap.add_argument("--golden", help="local golden-copy CSV zip (skips the download)")
    args = ap.parse_args(argv)
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    employers = employers_from_rows(fetch_rows(site))
    with tempfile.TemporaryDirectory() as tmp:
        if args.golden:
            golden, date = Path(args.golden), "local file"
        else:
            golden, date = download_latest(tmp)
        matches = match_all(employers, iter_golden_copy(golden))
    one = sum(1 for c in employers.values() if len(c) == 1)
    print(f"golden copy: {date}")
    print(f"8-K/news employer names: {len(employers)}  with one country: {one}  "
          f"LEI attached: {len(matches)} ({100 * len(matches) / max(len(employers), 1):.1f}%)")
    if args.write:
        write_output(OUT, matches, date)
        print(f"wrote {OUT}")
    else:
        print("dry run: nothing written (pass --write)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
