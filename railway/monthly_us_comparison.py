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
"""
import json
import ssl
import sys
import time
import urllib.request

API = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/aggregate"
UA = "AiLayoffTracker/1.0 (+https://asktherecruiter.com)"

#: Published national monthly totals, announcement basis, US.
#: Read 2026-08-13 from the survey's own monthly releases (the same figures
#: recorded in docs/TECHLOG.md 2026-08-13 and docs/COVERAGE_GAP_CLOSURE_PLAN.md).
#: A None means the survey has not published that month yet.
SURVEY_READ_DATE = "2026-08-13"
SURVEY_TOTAL = {
    "2026-01": 108435,
    "2026-02": 48307,
    "2026-03": 60620,
    "2026-04": 83387,
    "2026-05": 97006,
    "2026-06": 45849,
    "2026-07": 33429,
    "2026-08": None,
}
#: The survey's monthly AI-attributed line, same source and read date.
#: July onward had not been published as a monthly AI split when read.
SURVEY_AI = {
    "2026-01": 7624,
    "2026-02": 4680,
    "2026-03": 15341,
    "2026-04": 21490,
    "2026-05": 38579,
    "2026-06": 14029,
    "2026-07": None,
    "2026-08": None,
}

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


def main():
    months = sorted(SURVEY_TOTAL)
    print("# US 2026, month by month, ours beside the national announcement survey")
    print()
    print(f"Ours: measured live at run time, strict US job location. "
          f"Theirs: announcement basis, read {SURVEY_READ_DATE}.")
    print()
    print("| Month | Ours, effective basis | Ours, notice basis | National, announcement basis | Effective vs national | Notice vs national | National AI line |")
    print("|---|---|---|---|---|---|---|")
    sums = {"eff": 0, "notice": 0, "survey": 0}
    unknown = False
    for m in months:
        eff = month_totals(m, "effective")
        notice = month_totals(m, "notice")
        eff_j = eff["jobs"] if eff else None
        notice_j = notice["jobs"] if notice else None
        survey = SURVEY_TOTAL[m]
        ai = SURVEY_AI[m]
        if eff_j is None or notice_j is None:
            unknown = True
        else:
            if survey is not None:
                sums["eff"] += eff_j
                sums["notice"] += notice_j
                sums["survey"] += survey
        print(f"| {m} "
              f"| {eff_j if eff_j is not None else 'UNKNOWN'} "
              f"| {notice_j if notice_j is not None else 'UNKNOWN'} "
              f"| {survey if survey is not None else 'not published yet'} "
              f"| {pct(eff_j, survey)} "
              f"| {pct(notice_j, survey)} "
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
    return 3 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
