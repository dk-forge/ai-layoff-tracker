#!/usr/bin/env python3
"""Re-probe of the eight excluded WARN states named in the measurement brief.

READ docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md FIRST.
That document fixed the selection rule (criteria a/b/c/d) and recorded a live
probe from 2026-08-13 that excluded NY, IL, OH, PA, WA, GA, NJ and MI. This
module re-runs that SAME probe, unchanged, against the SAME official
publications, now that a month has passed. None of these eight were excluded
on a publisher instruction the way VA and MD were, so re-probing is legitimate
and this module exists to make it repeatable.

THIS MODULE DOES NOT BUILD A FRAME, DOES NOT SAMPLE, AND DOES NOT MEASURE
RECALL. It answers exactly one question per state: does the official
publication still fail the same criterion, or does it now pass all four? It
never writes to warn_recall_measurement.json or to any existing reference-set
manifest. Its own report is a new, separate file:
docs/recall-reference-sets/us-warn-state-reprobe.json (+ a readable .md).

THE FOUR CRITERIA, applied unchanged from the definition, section 2:
  (a) reachable under a plain browser User-Agent and permitted by robots.txt
  (b) statically machine-readable -- a document or a documented open-data API,
      never a JavaScript-only page, a proprietary BI extract, or an
      undocumented internal endpoint
  (c) complete over the window in one document or one date-bounded query
  (d) publishes employer, an absolute headcount, and a notice or received date

RULES CARRIED OVER FROM THE DEFINITION, NOT REINVENTED HERE:
  - robots.txt is read for a state's host BEFORE any other request to that
    host, and the verdict is recorded even when robots.txt is silent.
  - `Content-Signal: ai-input=no` (as dllr.state.md.us carries) is OUT, the
    same call the definition made about MD.
  - This project's agent is never renamed to dodge a block aimed at it by
    name. A host that blocks AiLayoffTracker/1.0 is OUT and a finding, not an
    obstacle to route around.
  - An undocumented internal XHR endpoint (a nonce'd admin-ajax call, a
    Sitecore search API, a vizql bootstrap route) is not promoted to eligible
    under (b), even when this repo's own custom collector already reads it
    for delivery purposes. Reading it for ingestion and counting it as a
    PUBLIC, documented interface are different claims.

No model is called anywhere in this module. Every judgement is deterministic
code over an HTTP response. Cost against the $18 monthly allowance: $0.00.

ALL NETWORK ACCESS GOES THROUGH ONE FUNCTION, `_http_fetch`, threaded through
every other function as an injectable `fetch` parameter -- exactly so the
judgement logic can be unit-tested offline with stubbed responses. Nothing
else in this module imports `requests` or opens a socket.

USAGE
    python3 railway/warn_state_probe.py --probe   # re-probe all eight, write the report
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
REF_DIR = REPO_ROOT / "docs" / "recall-reference-sets"
REPORT_JSON = REF_DIR / "us-warn-state-reprobe.json"
REPORT_MD = REF_DIR / "us-warn-state-reprobe.md"
DEFINITION_DOC = "docs/recall-reference-sets/US-WARN-REFERENCE-SET-DEFINITION.md"

SITE_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
# The agent name a robots.txt block is tested against, and the one this
# project's own state-facing requests carry (sources/warn_custom.py UA). It is
# never renamed to evade a block aimed at it, here or anywhere else.
AGENT_NAME = "AiLayoffTracker"
AGENT_TOKEN = "AiLayoffTracker/1.0"

CRITERIA = {
    "a": "reachable under a plain browser User-Agent and permitted by robots.txt",
    "b": ("statically machine-readable -- a document or a documented open-data "
          "API, not a JavaScript-only page, a proprietary BI extract, or an "
          "undocumented internal endpoint"),
    "c": "complete over the window in one document or one date-bounded query",
    "d": "publishes employer, an absolute headcount, and a notice or received date",
}

# The eight states, their official publication as named in the definition's
# exclusion table, and the 2026-08-13 verdict being re-checked. `documented_
# open_data_api` is filled only when the state publishes a DOCUMENTED,
# machine-readable API or bulk file distinct from its interactive page; it is
# deliberately None everywhere an internal endpoint is undocumented, even
# though this repo's own collector may already read that endpoint.
STATES = {
    "NY": {
        "publisher": "New York State Department of Labor",
        "url": "https://dol.ny.gov/warn-dashboard",
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": ("Tableau Public visualization; the workbook downloads but "
                          "holds two .hyper extracts needing tableauhyperapi, a "
                          "dependency this repo will not add for a reference set"),
        "documented_open_data_api": None,
        "undocumented_endpoint_note": ("the vizql bootstrap route carries no session "
                                        "id and is an undocumented internal API; not "
                                        "used and not promoted to eligible"),
    },
    "IL": {
        "publisher": "Illinois Department of Commerce and Economic Opportunity",
        "url": "https://dceo.illinois.gov/workforcedevelopment/warn.html",
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
    },
    "OH": {
        "publisher": "Ohio Department of Job and Family Services",
        "url": ("https://jfs.ohio.gov/job-workforce-services/job-programs-and-services/"
                "submit-a-warn-notice/current-public-notices-of-layoffs-and-closures"),
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "a",
        "prior_reason": "every documented path to the agency's own WARN listing 404s",
        "documented_open_data_api": None,
    },
    "PA": {
        "publisher": "Pennsylvania Department of Labor and Industry",
        "url": ("https://www.pa.gov/agencies/dli/programs-services/workforce-development/"
                "warn-requirements/warn-notices.html"),
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
    },
    "WA": {
        "publisher": "Washington State Employment Security Department",
        "url": ("https://esd.wa.gov/about-employees/WARN/"
                "warn-layoff-and-closure-database"),
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
    },
    "GA": {
        "publisher": "Technical College System of Georgia",
        "url": "https://www.tcsg.edu/warn-public-view/",
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
        "undocumented_endpoint_note": ("sources/warn_custom.fetch_ga reads a nonce'd "
                                        "wp-admin/admin-ajax.php GravityView endpoint "
                                        "for ingestion; it is undocumented and public "
                                        "only by discovery, so it is not promoted to "
                                        "eligible under (b)"),
    },
    "NJ": {
        "publisher": "New Jersey Department of Labor and Workforce Development",
        "url": "https://www.nj.gov/labor/employer-services/warn/",
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
    },
    "MI": {
        "publisher": "Michigan Department of Labor and Economic Opportunity",
        "url": "https://www.michigan.gov/leo/bureaus-agencies/wd/warn-notices",
        "prior_verdict_2026_08_13": "out",
        "prior_failed_criterion": "b",
        "prior_reason": "HTTP 200 but the notice rows are populated client-side",
        "documented_open_data_api": None,
        "undocumented_endpoint_note": ("sources/warn_custom.fetch_mi reads a Sitecore "
                                        "SXA search results JSON endpoint for "
                                        "ingestion; it is an undocumented internal "
                                        "API and is not promoted to eligible under (b)"),
    },
}


# ---------------------------------------------------------------------------
# The one door. Every request in this module goes through this function (or
# through the `fetch` parameter that stands in for it in tests), so the
# judgement logic below never has to be exercised against a live host to be
# tested.
# ---------------------------------------------------------------------------
class ProbeResponse:
    """A normalised HTTP outcome: a real response, an HTTP error, or a
    transport failure (DNS, TLS, timeout, connection refused) -- the last of
    which carries status=None and is never treated as a pass on (a)."""

    def __init__(self, status, headers=None, body=b"", error=None):
        self.status = status
        self.headers = headers or {}
        self.body = body if isinstance(body, (bytes, bytearray)) else bytes(body or b"")
        self.error = error


def _http_fetch(url, ua=SITE_UA, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return ProbeResponse(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return ProbeResponse(exc.code, dict(exc.headers or {}), body)
    except Exception as exc:                                       # noqa: BLE001
        return ProbeResponse(None, {}, b"", error=f"{type(exc).__name__}: {exc}")


def robots_url(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


# ---------------------------------------------------------------------------
# robots.txt: a minimal parser, just enough to answer "is this agent, or *,
# disallowed under /" and "does this file carry Content-Signal: ai-input=no".
# It does not implement path-specific precedence (longest-match) because
# every case this repo has needed to reason about -- VA's ClaudeBot block,
# MD's Content-Signal line -- is a whole-site `Disallow: /`.
# ---------------------------------------------------------------------------
def parse_robots(text):
    blocks = []                       # [(set(agents), [disallow paths])]
    cur_agents, cur_dis, saw_disallow = set(), [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            if saw_disallow:          # a new group starts after Disallow lines
                blocks.append((cur_agents, cur_dis))
                cur_agents, cur_dis, saw_disallow = set(), [], False
            cur_agents.add(val)
        elif key == "disallow":
            cur_dis.append(val)
            saw_disallow = True
    if cur_agents or cur_dis:
        blocks.append((cur_agents, cur_dis))
    content_signal_ai_input_no = "ai-input=no" in text.replace(" ", "").lower()
    return blocks, content_signal_ai_input_no


def robots_blocks_agent(blocks, agent_name):
    """A block naming the agent by name takes precedence over `*`, the same
    reading the definition applied to VA's ClaudeBot line."""
    agent_l = agent_name.lower()
    named = [dis for agents, dis in blocks if agent_l in {a.lower() for a in agents}]
    if named:
        return any(d.strip() == "/" for dis in named for d in dis), agent_name
    star = [dis for agents, dis in blocks if "*" in {a.lower() for a in agents}]
    if star:
        return any(d.strip() == "/" for dis in star for d in dis), "*"
    return False, None


def probe_robots(url, fetch):
    """robots.txt for `url`'s host -- fetched and judged before anything else."""
    rurl = robots_url(url)
    resp = fetch(rurl, SITE_UA)
    if resp.status != 200:
        return {
            "robots_url": rurl, "http_status": resp.status, "fetched": False,
            "blocked": False, "blocked_by": None,
            "content_signal_ai_input_no": False,
            "note": (f"no robots.txt (HTTP {resp.status}); nothing is disallowed"
                     if resp.status is not None else
                     f"robots.txt could not be fetched ({resp.error}); UNKNOWN, not permitted"),
            "unreachable": resp.status is None,
        }
    text = resp.body.decode("utf-8", "replace")
    blocks, content_signal = parse_robots(text)
    blocked, by = robots_blocks_agent(blocks, AGENT_NAME)
    note = ("Disallow: / for " + str(by) if blocked else
            ("Content-Signal: ai-input=no" if content_signal else "permitted"))
    return {
        "robots_url": rurl, "http_status": resp.status, "fetched": True,
        "blocked": blocked, "blocked_by": by,
        "content_signal_ai_input_no": content_signal,
        "note": note, "unreachable": False,
    }


# ---------------------------------------------------------------------------
# Criterion (b): statically machine-readable.
# ---------------------------------------------------------------------------
_TD_TEXT = re.compile(r"<td[^>]*>\s*([^<\s][^<]{1,80})</td>", re.I)


def looks_statically_readable(content_type, body):
    ct = (content_type or "").lower()
    if "json" in ct or "csv" in ct:
        return True, f"Content-Type {ct}"
    text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            json.loads(stripped)
            return True, "response body parses as JSON"
        except ValueError:
            pass
    cells = _TD_TEXT.findall(text)
    if len(cells) >= 6:
        return True, f"{len(cells)} populated <td> cells found in the served HTML"
    return False, ("HTTP 200 but no populated data rows found in the served markup "
                    "-- the table is populated client-side, same as 2026-08-13")


# ---------------------------------------------------------------------------
# Criterion (d): employer, absolute headcount, a notice/received date.
# Best-effort label scan -- only reached when (b) and (c) already passed.
# ---------------------------------------------------------------------------
def has_required_fields(body):
    text = body.decode("utf-8", "replace") if isinstance(body, (bytes, bytearray)) else str(body)
    tl = text.lower()
    has_employer = any(k in tl for k in ("employer", "company"))
    has_count = any(k in tl for k in ("employee", "affected", "headcount", "workers"))
    has_date = "date" in tl
    if has_employer and has_count and has_date:
        return True, "employer / headcount / date field labels all found"
    missing = [n for n, ok in
               (("employer", has_employer), ("headcount", has_count), ("date", has_date))
               if not ok]
    return False, f"missing field label(s): {', '.join(missing)}"


# ---------------------------------------------------------------------------
def probe_state(code, fetch=None):
    """Judge one state against criteria a/b/c/d, in order, stopping at the
    first failure -- robots.txt for the host is always fetched FIRST."""
    fetch = fetch or _http_fetch
    cfg = STATES[code]
    result = {
        "state": code,
        "publisher": cfg["publisher"],
        "official_publication_url": cfg["url"],
        "probed_at": _utc_now(),
        "agent": AGENT_TOKEN,
        "prior_verdict_2026_08_13": cfg["prior_verdict_2026_08_13"],
        "prior_failed_criterion_2026_08_13": cfg["prior_failed_criterion"],
        "prior_reason_2026_08_13": cfg["prior_reason"],
    }
    if cfg.get("undocumented_endpoint_note"):
        result["undocumented_endpoint_note"] = cfg["undocumented_endpoint_note"]

    robots = probe_robots(cfg["url"], fetch)
    result["robots"] = robots
    if robots["unreachable"]:
        result.update(verdict="UNKNOWN", failed_criterion=None,
                       reason="robots.txt for this host could not be fetched this run")
        return result
    if robots["blocked"]:
        result.update(
            verdict="OUT", failed_criterion="a", http_status=None,
            reason=(f"robots.txt disallows {robots['blocked_by']} under /; the agent "
                     "is never renamed to evade a block aimed at it by name"))
        return result
    if robots["content_signal_ai_input_no"]:
        result.update(
            verdict="OUT", failed_criterion="a", http_status=robots["http_status"],
            reason=("robots.txt carries Content-Signal: ai-input=no, an explicit "
                     "publisher request not to use this content as AI input -- OUT "
                     "on the same principle as MD in the definition"))
        return result

    resp = fetch(cfg["url"], SITE_UA)
    result["http_status"] = resp.status
    if resp.status != 200:
        result.update(
            verdict="OUT" if resp.status is not None else "UNKNOWN",
            failed_criterion="a" if resp.status is not None else None,
            reason=(f"HTTP {resp.status} on the documented path" if resp.status is not None
                     else f"could not be reached this run ({resp.error})"))
        return result

    content_type = resp.headers.get("Content-Type") or resp.headers.get("content-type")
    readable, why = looks_statically_readable(content_type, resp.body)
    result["static_readability"] = {"readable": readable, "why": why}
    if not readable:
        result.update(verdict="OUT", failed_criterion="b", reason=why)
        return result

    api = cfg.get("documented_open_data_api")
    if api:
        complete, c_reason = True, f"documented open-data API / date-bounded query: {api}"
    else:
        complete, c_reason = False, (
            "no documented open-data API or single date-bounded document is known for "
            "this publication. Its rows now parse, but an undocumented internal XHR "
            "endpoint is NOT promoted to eligible under criterion (b), and no other "
            "date-bounded, single-document route is documented, so (c) is not met.")
    result["criterion_c"] = {"pass": complete, "reason": c_reason}
    if not complete:
        result.update(verdict="OUT", failed_criterion="c", reason=c_reason)
        return result

    fields_ok, d_reason = has_required_fields(resp.body)
    result["criterion_d"] = {"pass": fields_ok, "reason": d_reason}
    if not fields_ok:
        result.update(verdict="OUT", failed_criterion="d", reason=d_reason)
        return result

    result.update(
        verdict="IN", failed_criterion=None,
        reason=("reachable and permitted, statically readable, complete via a "
                 "documented date-bounded query, and publishes employer, headcount "
                 "and a date"))
    return result


def build_report(fetch=None, sleep=0.5):
    fetch = fetch or _http_fetch
    results = []
    for i, code in enumerate(STATES):
        if i:
            time.sleep(sleep)          # a small courtesy delay between hosts
        results.append(probe_state(code, fetch=fetch))
    changed = [r["state"] for r in results if r["verdict"] != "OUT"]
    return {
        "report_id": "us-warn-eight-state-reprobe",
        "purpose": ("Re-probe of the eight WARN states excluded from "
                     "US-WARN-REFERENCE-SET-DEFINITION.md on 2026-08-13 -- NY, IL, "
                     "OH, PA, WA, GA, NJ, MI -- against the SAME four criteria. This "
                     "report judges eligibility ONLY. It builds no frame, draws no "
                     "sample, and measures no recall; no existing reference-set "
                     "manifest or measurement file is touched."),
        "definition_document": DEFINITION_DOC,
        "criteria": CRITERIA,
        "agent": AGENT_TOKEN,
        "generated_at": _utc_now(),
        "cost_usd": 0.0,
        "no_recall_measured": True,
        "states_probed": list(STATES),
        "states_no_longer_out": changed,
        "results": results,
    }


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_md(report):
    lines = [
        "# US WARN eight-state re-probe",
        "",
        f"Generated {report['generated_at']}. Definition document: "
        f"`{report['definition_document']}`.",
        "",
        "This re-probes NY, IL, OH, PA, WA, GA, NJ and MI against the four "
        "eligibility criteria fixed in the definition document. **It has NOT "
        "produced a recall figure for any of these states and does not build a "
        "frame or draw a sample.** Cost: $0.00, no model calls.",
        "",
        "| State | Prior verdict (2026-08-13) | This run | Failed criterion | HTTP | Reason |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        lines.append(
            f"| {r['state']} | out ({r['prior_failed_criterion_2026_08_13']}) "
            f"| **{r['verdict']}** | {r.get('failed_criterion') or '-'} "
            f"| {r.get('http_status', '-')} | {r['reason']} |")
    lines += ["", "## Criteria", ""]
    for k, v in report["criteria"].items():
        lines.append(f"- **({k})** {v}")
    lines += ["", "## Detail", ""]
    for r in report["results"]:
        lines.append(f"### {r['state']} -- {r['publisher']}")
        lines.append(f"- URL: {r['official_publication_url']}")
        lines.append(f"- robots.txt: {r['robots']['note']} "
                      f"(`{r['robots']['robots_url']}`, HTTP {r['robots']['http_status']})")
        if r.get("static_readability"):
            lines.append(f"- static readability: {r['static_readability']['readable']} "
                          f"-- {r['static_readability']['why']}")
        if r.get("undocumented_endpoint_note"):
            lines.append(f"- undocumented endpoint: {r['undocumented_endpoint_note']}")
        lines.append(f"- verdict: **{r['verdict']}**"
                      + (f" on criterion ({r['failed_criterion']})" if r.get("failed_criterion") else ""))
        lines.append(f"- {r['reason']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_report(report):
    REPORT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text(render_md(report), encoding="utf-8")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--probe" in argv:
        report = build_report()
        write_report(report)
        print(f"report written: {REPORT_JSON}")
        for r in report["results"]:
            print(f"  {r['state']}: {r['verdict']}"
                  + (f" ({r['failed_criterion']})" if r.get("failed_criterion") else ""))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
