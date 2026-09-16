"""The 8-K filing-shape invariant, over the LIVE published data.

Split out of data_integrity.py the way published_figures.py is, and for the
same two reasons: the registry stays one registry, and the RULE stays one rule.
Everything this asserts comes from `filing_shapes`, which the ingest gate in
`extractor.finalize_extraction` imports too, so the layer that refuses a row
and the layer that scans what is already published cannot drift apart.

What it is written from is in `filing_shapes` and in
docs/findings-july-august-2026-us-accuracy.md: row 176990 (HHS's 20,000 quoted
in a risk factor and bound to a shell company), row 177216 ($4,320 thousand of
restructuring cost read as 4,320 jobs) and row 176490 (Aon, announced 2014 for
2020, still live).
"""
import json
import re
import urllib.error
import urllib.parse

from filing_shapes import (MAX_8K_LEAD_DAYS, REVIEW_8K_LEAD_DAYS,
                           filing_lead_verdict, projection_language)

BASE = "https://asktherecruiter.com/blog/wp-json/layoffs/v1/"


def _di():
    """data_integrity lazily, because it imports this module at the bottom.

    Result and the three states live there and stay there: a second definition
    of what "failing" means is the one thing this must not introduce.
    """
    import data_integrity
    return data_integrity


#: One /query page of 8-K rows, largest first, because a wrong 8-K figure's
#: damage is its job_count and the shapes this looks for arrive large (20,000;
#: 4,320; 3,500). The window is unbounded on purpose: the Aon row is dated
#: 2020 and a trailing window would have hidden it.
FILING_SHAPE_ROWS = 200


def filing_shape_findings(rows, refuse_after=MAX_8K_LEAD_DAYS,
                          review_after=REVIEW_8K_LEAD_DAYS):
    """Sort 8-K rows into the shapes `filing_shapes` names. Pure; no network.

    Returns {"refuse": [...], "review": [...], "count_absent": [...],
    "projection": [...]}. Only "refuse" is a defect by itself: an
    announcement more than `refuse_after` days before the row's own effective
    date is not this filing's event. The other three are ADVISORY worklists,
    and the reason is measured, not assumed: applying the ingest gate's
    excerpt rule to the 991 live 8-K rows on 2026-09-16 failed 260 of them,
    most legitimate ("36,000 U.S.-based employees" trips a regex on the dots),
    so a _di().FAIL on that tell would be noise and noise is how an alert channel
    gets filtered. "count_absent" is the row 177216 shape (a job_count that
    its own excerpt never states, beside cost words); "projection" is the
    Paramount shape (a region's forecast stored as an announcement).
    """
    out = {"refuse": [], "review": [], "count_absent": [], "projection": []}
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        if str(row.get("source_type") or "") != "8K":
            continue
        try:
            jobs = int(row.get("job_count") or 0)
        except (TypeError, ValueError):
            jobs = 0
        verdict, days = filing_lead_verdict(row.get("announcement_date"),
                                            row.get("layoff_date"),
                                            refuse_after=refuse_after,
                                            review_after=review_after)
        item = {"id": row.get("id"), "job_count": jobs, "lead_days": days,
                "announcement_date": row.get("announcement_date"),
                "layoff_date": row.get("layoff_date")}
        if verdict == "refuse":
            out["refuse"].append(item)
        elif verdict == "review":
            out["review"].append(item)
        excerpt = str(row.get("excerpt") or "")
        if jobs > 0 and excerpt and not re.search(rf"(?<![\d.,]){jobs:,}(?![\d])|(?<![\d.,]){jobs}(?![\d])", excerpt) \
                and re.search(r"(?i)[$€£]|\bcosts?\b|\bexpenses?\b|\bcharges?\b|severance", excerpt):
            out["count_absent"].append(item)
        if projection_language(excerpt):
            out["projection"].append(item)
    for key in out:
        out[key].sort(key=lambda r: (-(r["lead_days"] or 0), -r["job_count"], str(r["id"])))
    return out


class FilingShapeInvariant:
    """An 8-K row states its filer's own, current headcount.

    WHAT IT ASSERTS. Over the largest 8-K rows: no row's announcement_date
    leads its layoff_date by more than MAX_8K_LEAD_DAYS. That span is the one
    tell of the third-party-figure shape a published row still carries after
    the filing text is gone (docs/findings-july-august-2026-us-accuracy.md,
    row 176990: 467 days; live row 176490: 2,233 days). Everything else this
    module knows about the shape is applied at INGEST in
    extractor.finalize_extraction, from the same `filing_shapes` definitions.

    WHAT IT REPORTS WITHOUT FAILING. The 181-365 day band, excerpts that never
    state their own count beside cost words, and projection language, each as
    a count with row ids, so the _di().PASS sentence is a worklist rather than a
    clean zero. A guard whose clean zero has never caught a real case is
    worthless; this one names the row it is failing on today.

    ONE REQUEST, largest first, floor printed. Never a page walk.
    """

    key = "filing_shape_tells"
    label = "8-K rows are the filer's own current cuts"
    reads_live_data = True

    ROWS = FILING_SHAPE_ROWS

    def run(self, ctx):
        params = {"sources": "8K", "sort": "job_count", "dir": "desc",
                  "per_page": self.ROWS, "page": 1, "cb": ctx.cachebust}
        url = BASE + "query?" + urllib.parse.urlencode(params)
        try:
            payload = json.loads(ctx.fetch(url, ctx.timeout)) or {}
        except urllib.error.HTTPError as exc:
            why = ("site is in its deploy maintenance window (HTTP 503)"
                   if exc.code == 503 else f"/query returned HTTP {exc.code}")
            return _di().Result(self, _di().UNKNOWN, detail=why, error=exc)
        except Exception as exc:
            return _di().Result(self, _di().UNKNOWN,
                          detail=f"could not read /query ({exc})", error=exc)

        rows = payload.get("data")
        if not isinstance(rows, list) or not rows:
            return _di().Result(self, _di().UNKNOWN,
                          detail="/query returned no 8-K rows — this check did not "
                                 "run, which is not the same as finding nothing")
        counts = []
        for row in rows:
            try:
                counts.append(int((row or {}).get("job_count") or 0))
            except (TypeError, ValueError):
                pass
        floor = min(counts) if counts else 0
        try:
            total = int(payload.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        dated = sum(1 for r in rows if isinstance(r, dict)
                    and r.get("announcement_date") and r.get("layoff_date"))
        scope = (f"{len(rows)} largest of {total:,} 8-K rows, down to {floor:,} jobs, "
                 f"{dated} carrying both dates")

        found = filing_shape_findings(rows)

        def ids(items, n=4):
            return ", ".join(str(i["id"]) for i in items[:n]) + (" ..." if len(items) > n else "")

        advisory = []
        if found["review"]:
            advisory.append(f"{len(found['review'])} row(s) announced {REVIEW_8K_LEAD_DAYS}-"
                            f"{MAX_8K_LEAD_DAYS} days before their effective date "
                            f"(rows {ids(found['review'])}): adjudicate, not failed")
        if found["count_absent"]:
            advisory.append(f"{len(found['count_absent'])} row(s) whose excerpt never states "
                            f"their own count beside cost words, the row-177216 shape "
                            f"(rows {ids(found['count_absent'])}): adjudicate, not failed")
        if found["projection"]:
            advisory.append(f"{len(found['projection'])} row(s) with projection language "
                            f"(rows {ids(found['projection'])}): adjudicate, not failed")
        advice = ("; ".join(advisory)) if advisory else "no advisory shapes in this sample"

        if found["refuse"]:
            worst = found["refuse"][0]
            return _di().Result(self, _di().FAIL, observed=sum(i["job_count"] for i in found["refuse"]),
                          detail=f"{len(found['refuse'])} 8-K row(s) carry an announcement more "
                                 f"than {MAX_8K_LEAD_DAYS} days before their own effective date, "
                                 f"the third-party-figure shape of row 176990. Worst: row "
                                 f"{worst['id']}, {worst['job_count']:,} jobs, announced "
                                 f"{worst['announcement_date']} for {worst['layoff_date']} "
                                 f"({worst['lead_days']:,} days). Read the cited filing, then "
                                 f"correct through the machinery (RUNBOOK: a published row is "
                                 f"wrong), never by hand. Also: {advice} ({scope})")
        return _di().Result(self, _di().PASS, observed=0,
                      detail=f"no 8-K row is announced more than {MAX_8K_LEAD_DAYS} days before "
                             f"its own effective date; {advice} ({scope}); a row below "
                             f"{floor:,} jobs is outside this sweep and is NOT claimed clean")
