#!/usr/bin/env python3
"""Census of the rows with no job-location country: how many, and WHY each.

    WP_SITE_URL=https://asktherecruiter.com/blog python3 railway/blank_country_census.py

READ-ONLY: the public /query only, no key, no model, no write path in this file.
It sorts every blank row into one cause so the owner can see which of the
three existing tools would move it, and what the rest would cost:

  (b) deterministic, place now      a US state code on the row, or a WARN /
                                    federal notice from a US government host.
                                    The SAME judgement `legacy_row_repair`
                                    applies, imported and never copied.
                                    Dispatch: Legacy row repair --only country
  filing                            an SEC filing whose excerpt does not say
                                    where the cuts were. The filing venue is
                                    not the job location (TECHLOG 2026-08-18)
                                    and the filer's EDGAR record gives its
                                    DOMICILE, which makes the row findable
                                    under country_basis=any and is written to
                                    employer_country, never to country.
                                    Dispatch: Employer domicile backfill
  (c) news, body readable           the excerpt did not say; the article might.
                                    One metered read each, evidence-quoted.
                                    Dispatch: Blank-country source re-read
  (a) news, body unreadable         a news.google.com redirect that no longer
                                    resolves and that Wayback never held. No
                                    spend moves this; the blank is permanent
                                    unless a second source arrives.

Two things it counts and REFUSES to treat as a placement, because both were
measured wrong on real rows: the country named in the excerpt (on 2026-09-02
six of 93 named exactly one, and five of the six were the OUTLET: Times of
Suriname, Business News Nigeria, Euronews Albania, Business Insider Japan),
and the publisher's country in any other form, ccTLD included. A Swedish
company in a Serbian outlet is neither a Serbian layoff nor a Serbian
employer. Those rows are reported as `suggestive` and left blank.

Nothing here decides for the owner. A row with a filled `employer_country`
is already reachable under the front-end's default country filter; the
census says how many are, so the invisible count is the one that matters.
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from employer_domicile_backfill import fetch_blank_country_rows   # noqa: E402
from legacy_row_repair import _infer_country                      # noqa: E402

#: The one host whose stored article URL is a redirect that no longer
#: resolves (measured 2026-08-18: every one returns an 11-byte page and
#: Wayback holds no snapshot of an RSS redirect).
UNREADABLE_HOSTS = {"news.google.com"}

CAUSES = ("deterministic", "filing", "news_readable", "news_unreadable")


def _countries_named(text):
    """Countries the excerpt names, via the extractor's own reader; a reader
    that cannot be imported returns None, which the census reports as
    UNKNOWN rather than as "names nothing"."""
    try:
        from extractor import _countries_named_in
    except Exception:
        return None
    return _countries_named_in(text)


def classify(row):
    """One cause per row, from CAUSES, plus the flags the report needs."""
    country = _infer_country(row)
    host = (urllib.parse.urlparse(str(row.get("source_url") or "")).hostname or "").lower()
    if country:
        cause = "deterministic"
    elif str(row.get("source_type") or "").lower() != "news":
        cause = "filing"
    elif host in UNREADABLE_HOSTS:
        cause = "news_unreadable"
    else:
        cause = "news_readable"
    named = _countries_named(row.get("excerpt") or "")
    return {
        "id": int(row["id"]),
        "cause": cause,
        "deterministic_country": country,
        "findable": bool(str(row.get("employer_country") or "").strip()),
        # Suggestive, never a placement: the excerpt names exactly one country.
        "suggestive": (None if named is None else len(named) == 1),
    }


def census(rows):
    out = {"rows": len(rows), "by_cause": {c: 0 for c in CAUSES},
           "findable": 0, "invisible": 0, "suggestive": 0, "suggestive_unknown": 0,
           "deterministic_ids": []}
    for row in rows:
        c = classify(row)
        out["by_cause"][c["cause"]] += 1
        out["findable" if c["findable"] else "invisible"] += 1
        if c["suggestive"] is None:
            out["suggestive_unknown"] += 1
        elif c["suggestive"]:
            out["suggestive"] += 1
        if c["cause"] == "deterministic":
            out["deterministic_ids"].append((c["id"], c["deterministic_country"]))
    return out


def report(c):
    k = c["by_cause"]
    lines = [
        f"rows with no job-location country       {c['rows']:>5}",
        f"  findable by employer_country           {c['findable']:>5}  (country_basis=any reaches these)",
        f"  invisible to every country filter      {c['invisible']:>5}  (both fields blank)",
        "",
        "by cause",
        f"  (b) deterministic, place now           {k['deterministic']:>5}  -> Legacy row repair --only country",
        f"  filing, domicile only                  {k['filing']:>5}  -> Employer domicile backfill (employer_country)",
        f"  (c) news, body readable                {k['news_readable']:>5}  -> Blank-country source re-read (one metered read each)",
        f"  (a) news, body unreadable              {k['news_unreadable']:>5}  (google redirect; no spend moves this)",
        "",
        "refused as a placement, reported so nobody re-derives it",
    ]
    if c["suggestive_unknown"]:
        lines.append(f"  excerpt names exactly one country      UNKNOWN  (country reader unavailable)")
    else:
        lines.append(f"  excerpt names exactly one country      {c['suggestive']:>5}  (usually the outlet; left blank)")
    for row_id, country in c["deterministic_ids"]:
        lines.append(f"    id={row_id} -> {country}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=2000)
    args = ap.parse_args(argv)
    site = os.environ.get("WP_SITE_URL", "").rstrip("/")
    if not site:
        print("WP_SITE_URL is required")
        return 1
    rows = fetch_blank_country_rows(site, args.max)
    print(report(census(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
