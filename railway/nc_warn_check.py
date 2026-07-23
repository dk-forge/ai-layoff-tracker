"""Dry check for the NC WARN parsers. Posts NOTHING.

Runs fetch_nc() and reports the row count plus any row whose company field still
looks misaligned (a bare number, a date, or no real word) — the symptom the LLM
fallback probe surfaced (company='0'/'18'). Use it to measure before/after a
parser fix: suspect rows should go to 0 while the legitimate row count stays
roughly stable.

    python nc_warn_check.py
"""
import re
import sys


def suspect(name):
    """A real company name has letters and isn't a bare number or a date."""
    s = re.sub(r"\s+", " ", str(name or "")).strip()
    if not s:
        return True
    if re.fullmatch(r"[\d,.\s/-]+", s):      # bare number or date-ish
        return True
    if not re.search(r"[A-Za-z]{2,}", s):     # no real word
        return True
    return False


def main():
    from sources.warn_custom import fetch_nc
    try:
        rows = fetch_nc()
    except Exception as exc:
        print(f"fetch_nc FAILED: {exc}")
        return 1
    bad = [r for r in rows if suspect(r.get("company_name"))]
    print(f"NC rows parsed:      {len(rows)}")
    print(f"suspect company rows: {len(bad)}")
    for r in bad[:40]:
        print(f"   company={r.get('company_name')!r:<24} jobs={r.get('job_count')} "
              f"date={r.get('layoff_date')}")
    if not bad:
        print("CLEAN: no misaligned company rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
