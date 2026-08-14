"""Internal monthly US comparison: our totals on both date bases beside the
published national monthly announcement figures.

Read-only, stdlib-only, keyless. Prints a markdown table; changes nothing.

WHY THIS EXISTS. The owner keeps asking "where are we against the national
monthly number" and the answer has been re-derived by hand each time, which is
how the stale-percentage defect happened (a 2026-07-27 coverage figure quoted
for sixteen days after its denominator moved, TECHLOG 2026-08-13). This script
recomputes OUR side live on every run and types THEIR side as constants with
the source date attached, so a stale comparator is visible as a dated constant
rather than hidden inside prose.

THE BASES ARE NAMED BECAUSE THEY ARE NOT THE SAME MEASUREMENT (TECHLOG
2026-08-13, "the comparability claim had decayed"):

- effective basis  - our layoff_date window: when the jobs end. WARN months
  keep filling for weeks after they close.
- notice basis     - COALESCE(announcement_date, layoff_date): closest we can
  get to "when it was announced" for the whole corpus. Only a small minority
  of rows carry announcement_date, so this mostly follows the effective date.
- the national figures are an ANNOUNCEMENT survey: it books an event in the
  month it was announced, and it also counts categories that never produce a
  public document we could cite - federal reductions, voluntary buyout
  offers, employer estimates, and unnamed small announcements. Those are the
  known receiptless categories; parity with them is not promisable from
  receipts, which is why no target percentage is printed here.

The comparator constants follow the survey_reconcile convention: no
organization name in the repo, figures only, with the date they were read.

SINCE 2026-08-14 THE CONSTANTS LIVE IN ONE FILE, SHARED WITH THE PUBLIC PAGE:
wordpress-plugin/ai-layoff-tracker/data/survey-monthly.json. page-press.php
renders the same figures on the public monthly comparison table, so a second
copy here would be two hand-entered comparators waiting to disagree. This
script also carries the STALENESS verdict: a month whose end is more than
DUE_AFTER_DAYS behind today with no constant entered is reported STALE (exit
2, a human task, not an outage), and the page prints an awaiting note for the
same months from the same file. The due window must equal $alt_mc_due_days in
page-press.php; test_stage_tier_and_survey_table pins both.
"""
import json
import ssl
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import urllib.request

API = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: Days after a month closes before a missing survey constant is STALE.
#: Must equal $alt_mc_due_days in page-press.php.
DUE_AFTER_DAYS = 40

#: The one copy of the hand-entered comparator, shared with the public page.
SURVEY_FILE = (Path(__file__).resolve().parents[1]
               / "wordpress-plugin" / "ai-layoff-tracker" / "data"
               / "survey-monthly.json")


def load_survey():
    """Constants dict from the shared JSON, or None (UNKNOWN, not empty)."""
    try:
        data = json.loads(SURVEY_FILE.read_text())
    except (OSError, ValueError) as exc:
        print(f"UNKNOWN: {SURVEY_FILE} -> {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None
    if not isinstance(data.get("total"), dict) or not data.get("read_date"):
        print(f"UNKNOWN: {SURVEY_FILE} is missing 'total' or 'read_date'",
              file=sys.stderr)
        return None
    return data

RECEIPTLESS = (
    "Known receiptless categories in the national figure: federal reductions, "
    "voluntary buyout offers, employer estimates never filed anywhere, and "
    "unnamed small announcements. We count only cuts with a filing or a named "
    "public report behind them."
)

MONTH_DAYS = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31,
              9: 30, 10: 31, 11: 30, 12: 31}


def fetch(params):
    """One aggregate call; returns totals dict or None (UNKNOWN, not zero)."""
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API}?{qs}&cb={int(time.time() * 1000) % 100000}"
    req = urllib.request.Request(url.replace(" ", "%20"),
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45,
                                    context=ssl.create_default_context()) as r:
            return json.load(r).get("totals")
    except Exception as exc:
        print(f"UNKNOWN: {url} -> {type(exc).__name__}: {exc}", file=sys.stderr)
        return None


def month_totals(month, basis):
    year, num = (int(p) for p in month.split("-"))
    frm = f"{month}-01"
    to = f"{month}-{MONTH_DAYS[num]:02d}"
    params = {"country": "United States", "from": frm, "to": to}
    if basis == "notice":
        params["date_basis"] = "notice"
    return fetch(params)


def pct(ours, theirs):
    if ours is None:
        return "UNKNOWN"
    if not theirs:
        return "n/a"
    return f"{100.0 * ours / theirs:.0f}%"


def month_is_due(month):
    """True once the month's end is more than DUE_AFTER_DAYS behind today."""
    year, num = (int(p) for p in month.split("-"))
    month_end = date(year, num, MONTH_DAYS[num])
    return date.today() > month_end + timedelta(days=DUE_AFTER_DAYS)


def main():
    survey = load_survey()
    if survey is None:
        return 3
    totals = survey["total"]
    ai_line = survey.get("ai", {})
    months = sorted(totals)
    print("# US 2026, month by month, ours beside the national announcement survey")
    print()
    print(f"Ours: measured live at run time, strict US job location. "
          f"Theirs: announcement basis, read {survey['read_date']}.")
    print()
    print("| Month | Ours, effective basis | Ours, notice basis | National, announcement basis | Effective vs national | Notice vs national | National AI line |")
    print("|---|---|---|---|---|---|---|")
    sums = {"eff": 0, "notice": 0, "survey": 0}
    unknown = False
    stale = []
    for m in months:
        eff = month_totals(m, "effective")
        notice = month_totals(m, "notice")
        eff_j = eff["jobs"] if eff else None
        notice_j = notice["jobs"] if notice else None
        month_survey = totals[m]
        ai = ai_line.get(m)
        if eff_j is None or notice_j is None:
            unknown = True
        else:
            if month_survey is not None:
                sums["eff"] += eff_j
                sums["notice"] += notice_j
                sums["survey"] += month_survey
        if month_survey is None and month_is_due(m):
            stale.append(m)
        print(f"| {m} "
              f"| {eff_j if eff_j is not None else 'UNKNOWN'} "
              f"| {notice_j if notice_j is not None else 'UNKNOWN'} "
              f"| {month_survey if month_survey is not None else 'not published yet'} "
              f"| {pct(eff_j, month_survey)} "
              f"| {pct(notice_j, month_survey)} "
              f"| {ai if ai is not None else 'not published'} |")
    if not unknown and sums["survey"]:
        print(f"| published months | {sums['eff']} | {sums['notice']} "
              f"| {sums['survey']} | {pct(sums['eff'], sums['survey'])} "
              f"| {pct(sums['notice'], sums['survey'])} | |")
    print()
    print(RECEIPTLESS)
    print()
    print("An UNKNOWN row means the live API could not be read from here. "
          "It is not a zero and not a pass.")
    read_age = (date.today()
                - date(*[int(p) for p in survey["read_date"].split("-")])).days
    if read_age > DUE_AFTER_DAYS:
        stale.append(f"read_date {survey['read_date']} is {read_age}d old")
    if stale:
        print()
        print(f"STALE: {', '.join(stale)} -> the survey has released figures "
              f"this repo has not entered. Update {SURVEY_FILE.name} (the one "
              f"copy, shared with the public press-page table). A stale "
              f"comparator is a human task, not an outage.")
        return 2
    return 3 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
