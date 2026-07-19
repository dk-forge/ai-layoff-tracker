"""
Stage-1 compliance-evidence builder for the separate WARN transparency register.

Given WARN rows that record BOTH an official notice date and an official
effective (affected) date, this module computes the notice gap in days as PURE
ARITHMETIC on the source-recorded fields and pairs each result with fixed
statutory context. It exists to prepare evidence *candidates* for editorial
review — its output is never posted anywhere by automation and never enters
layoff or AI totals.

Non-negotiable invariants (guarded by tests/test_warn_transparency_guards.py):

- NO VERDICTS. The WARN Act's 60-day requirement (29 U.S.C. § 2102(a)) has
  legally legitimate exceptions — faltering company (§ 2102(b)(1)),
  unforeseeable business circumstances (§ 2102(b)(2)(A)) and natural disaster
  (§ 2102(b)(2)(B)) — and only a court may adjudicate them (29 U.S.C. § 2104;
  20 C.F.R. § 639.1(d)). A gap below 60 days is therefore emitted only as a
  'short_notice_candidate' timing observation with statutory context attached.
  This module must never label an employer non-compliant, in violation, or
  illegal, and it deliberately cannot emit the register's court-adjudicated
  status.
- NO IMPUTATION. Rows missing either date, carrying a non-ISO date, or dated
  outside the plausible WARN window are excluded and counted — never guessed,
  parsed leniently, or defaulted.
- EVIDENCE REQUIRED. A candidate without an official source URL is excluded;
  the register admits nothing without a citable primary source.
- AMENDMENTS. Amended/revised notices for the same (state, employer,
  effective date) reduce to one candidate using the EARLIEST recorded notice
  date — the employer's first service of notice is what the statute times.
- OFFLINE. Pure stdlib; no network, no LLM, no API keys. Posting to the keyed
  register writer stays a manual editorial act.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date

# 29 U.S.C. § 2102(a): written notice must be served 60 days ahead.
STATUTORY_NOTICE_DAYS = 60

# WARN effective dates are at most ~a year past filing; same plausibility
# window sources/warn.py enforces. Outside it we exclude, never clamp.
MIN_PLAUSIBLE_DATE = date(2015, 1, 1)
MAX_PLAUSIBLE_DATE = date(2028, 12, 31)

# The ONLY observations this builder may emit. Both are timing observations;
# neither is, or may ever become, a compliance or violation label.
OBSERVATION_SHORT_NOTICE_CANDIDATE = "short_notice_candidate"
OBSERVATION_60_PLUS = "notice_recorded_60_plus_days"
OBSERVATION_LABELS = (OBSERVATION_SHORT_NOTICE_CANDIDATE, OBSERVATION_60_PLUS)

# Compact per-candidate note; the full cited block travels once per build in
# the methodology so 100K candidates don't repeat the statute.
STATUTORY_CONTEXT_NOTE = (
    "The federal WARN Act requires 60 days' written notice (29 U.S.C. "
    "§ 2102(a)), but reduced notice can be lawful under the faltering-company, "
    "unforeseeable-business-circumstances and natural-disaster exceptions "
    "(29 U.S.C. § 2102(b); 20 C.F.R. § 639.9). Only a court may decide whether "
    "an exception applies (29 U.S.C. § 2104). This gap is a timing "
    "observation, not a verdict, and does not indicate non-compliance."
)

STATUTORY_CONTEXT = {
    "notice_requirement": (
        "29 U.S.C. § 2102(a): an employer may not order a plant closing or "
        "mass layoff until the end of a 60-day period after serving written "
        "notice."
    ),
    "recognized_exceptions": {
        "faltering_company": (
            "29 U.S.C. § 2102(b)(1); 20 C.F.R. § 639.9(a): shutdown-only "
            "exception for an employer actively seeking capital or business "
            "that would have avoided or postponed the shutdown, where giving "
            "notice would have precluded obtaining it."
        ),
        "unforeseeable_business_circumstances": (
            "29 U.S.C. § 2102(b)(2)(A); 20 C.F.R. § 639.9(b): the closing or "
            "layoff was caused by business circumstances not reasonably "
            "foreseeable when notice would have been required."
        ),
        "natural_disaster": (
            "29 U.S.C. § 2102(b)(2)(B); 20 C.F.R. § 639.9(c): the closing or "
            "layoff is due to any form of natural disaster (flood, "
            "earthquake, drought, storm)."
        ),
    },
    "reduced_notice_duty": (
        "29 U.S.C. § 2102(b)(3): an employer relying on an exception must "
        "still give as much notice as practicable, with a brief statement of "
        "the basis for reducing the period."
    ),
    "burden_of_proof": (
        "20 C.F.R. § 639.9: the employer bears the burden of proof that the "
        "conditions for an exception have been met."
    ),
    "enforcement": (
        "29 U.S.C. § 2104 and 20 C.F.R. § 639.1(d): WARN is enforced "
        "exclusively through civil actions in U.S. district courts; the "
        "Department of Labor has no enforcement standing. No administrative "
        "body issues compliance verdicts, and neither does this dataset."
    ),
    "state_law_caveat": (
        "Several states operate mini-WARN laws with different thresholds and "
        "longer notice periods (e.g., 90 days in some states). The arithmetic "
        "here is computed against the federal 60-day period only and says "
        "nothing about state-law obligations."
    ),
    "disclaimer": (
        "A notice gap below 60 days is a timing observation on officially "
        "recorded dates. It is explicitly not a violation label, not legal "
        "advice, and never a verdict about any employer."
    ),
}

_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date(value):
    """Strictly parse an official YYYY-MM-DD field to a date, else None.

    Deliberately refuses every other format (03/01/2026, 'TBD', prose ranges):
    ambiguous forms would require interpretation, and the register's rule is
    that dates are recorded, never inferred.
    """
    s = str(value or "").strip()
    if not _ISO_RE.match(s):
        return None
    try:
        d = date.fromisoformat(s)
    except ValueError:
        return None
    if d < MIN_PLAUSIBLE_DATE or d > MAX_PLAUSIBLE_DATE:
        return None
    return d


def notice_gap_days(notice_date, effective_date):
    """Days between official notice and effective dates, or None.

    Pure calendar arithmetic — identical semantics to the register writer's
    floor((affected - notice) / DAY). None when either side is missing or
    invalid; negative when the effective date precedes the notice date (the
    caller excludes those rather than treating them as short notice).
    """
    n = _iso_date(notice_date)
    e = _iso_date(effective_date)
    if n is None or e is None:
        return None
    return (e - n).days


def earliest_notice_date(values):
    """Earliest valid ISO notice date among amended/revised recordings.

    Returns the ISO string, or None when nothing parses (never a guess).
    """
    parsed = sorted(d for d in (_iso_date(v) for v in values) if d is not None)
    return parsed[0].isoformat() if parsed else None


def _group_key(row):
    state = str(row.get("state") or "").strip().upper()
    employer = " ".join(str(row.get("employer") or "").split()).casefold()
    effective = str(row.get("effective_date") or "").strip()
    return (state, employer, effective)


def build_compliance_evidence(rows):
    """Compute notice-gap candidates from WARN rows with both official dates.

    Input rows are dicts with: state, employer, notice_date, effective_date,
    source_url, and optionally source_name. Output::

        {"methodology": {...statutory context, invariants...},
         "candidates": [ {state, employer, notice_date, effective_date,
                          notice_gap_days, observation, statutory_context,
                          evidence: {source_name, source_url},
                          amended_notice_dates?}, ... ],
         "excluded": {missing_dates, invalid_dates, effective_precedes_notice,
                      missing_source_url}}

    Excluded rows are counted, never imputed. Amendments (same state/employer/
    effective date) collapse to one candidate on the earliest notice date, and
    the evidence URL is taken from the row that recorded that earliest date.
    """
    groups = {}
    order = []
    excluded = {
        "missing_dates": 0,
        "invalid_dates": 0,
        "effective_precedes_notice": 0,
        "missing_source_url": 0,
    }

    for row in rows:
        raw_notice = str(row.get("notice_date") or "").strip()
        raw_effective = str(row.get("effective_date") or "").strip()
        if not raw_notice or not raw_effective:
            excluded["missing_dates"] += 1
            continue
        notice = _iso_date(raw_notice)
        effective = _iso_date(raw_effective)
        if notice is None or effective is None:
            excluded["invalid_dates"] += 1
            continue
        # An effective date before the notice date is either a source data
        # error or an after-the-fact notice; both need human review and the
        # register's timing labels cannot hold them (its writer rejects
        # negative intervals), so they are excluded — not called short notice.
        if effective < notice:
            excluded["effective_precedes_notice"] += 1
            continue
        if not str(row.get("source_url") or "").strip():
            excluded["missing_source_url"] += 1
            continue
        key = _group_key(row)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    candidates = []
    for key in order:
        group = groups[key]
        recorded = sorted({str(r.get("notice_date")).strip() for r in group})
        earliest = earliest_notice_date(recorded)
        # Evidence must cite the source that recorded the governing (earliest)
        # notice date; first-seen wins on exact ties.
        evidence_row = next(
            r for r in group if str(r.get("notice_date")).strip() == earliest)
        effective = str(evidence_row.get("effective_date")).strip()
        gap = notice_gap_days(earliest, effective)
        candidate = {
            "state": str(evidence_row.get("state") or "").strip().upper(),
            "employer": str(evidence_row.get("employer") or "").strip(),
            "notice_date": earliest,
            "effective_date": effective,
            "notice_gap_days": gap,
            "observation": (OBSERVATION_SHORT_NOTICE_CANDIDATE
                            if gap < STATUTORY_NOTICE_DAYS
                            else OBSERVATION_60_PLUS),
            "statutory_context": STATUTORY_CONTEXT_NOTE,
            "evidence": {
                "source_name": str(evidence_row.get("source_name") or "").strip(),
                "source_url": str(evidence_row.get("source_url") or "").strip(),
            },
        }
        if len(recorded) > 1:
            candidate["amended_notice_dates"] = recorded
        candidates.append(candidate)

    candidates.sort(key=lambda c: (c["state"], c["employer"].casefold(),
                                   c["effective_date"], c["notice_date"]))
    return {
        "methodology": {
            "scope": (
                "Editorial-review candidates for the separate WARN "
                "transparency register. Pure date arithmetic on officially "
                "recorded fields; not included in layoff or AI totals, "
                "charts, exports or compliance rates."
            ),
            "no_verdicts": (
                "No candidate labels an employer non-compliant. "
                "short_notice_candidate is a timing observation queued for "
                "human review against the statutory exceptions."
            ),
            "no_imputation": (
                "Rows missing either official date are excluded and counted, "
                "never imputed. Amended/revised notices use the earliest "
                "recorded notice date."
            ),
            "statutory_context": STATUTORY_CONTEXT,
            "statutory_notice_days": STATUTORY_NOTICE_DAYS,
            "observation_labels": list(OBSERVATION_LABELS),
        },
        "candidates": candidates,
        "excluded": excluded,
    }


def main(argv):
    """Offline CLI: read a JSON array of rows, print the evidence build.

    Usage: python3 warn_transparency_evidence.py rows.json [out.json]
    Reads and writes local files only — this tool never talks to the API.
    """
    if not argv:
        print("usage: warn_transparency_evidence.py rows.json [out.json]")
        return 2
    with open(argv[0], "r", encoding="utf-8") as fh:
        rows = json.load(fh)
    result = build_compliance_evidence(rows)
    payload = json.dumps(result, indent=2, sort_keys=False)
    if len(argv) > 1:
        with open(argv[1], "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        print(f"wrote {len(result['candidates'])} candidates to {argv[1]} "
              f"(excluded: {result['excluded']})")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
